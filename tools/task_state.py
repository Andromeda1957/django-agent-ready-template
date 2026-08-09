#!/usr/bin/env python3
"""Manage live agent-task state outside Git across all linked worktrees."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
TASK_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{1,79}$')
SHA_PATTERN = re.compile(r'^[0-9a-f]{40}$')
MAX_TEXT = 300
MAX_PACKET_BYTES = 8 * 1024
BROAD_PATTERNS = frozenset({'*', '**', '**/*', '.'})


class TaskStateError(ValueError):
    """Raised when task state is missing, ambiguous, or malformed."""


def run_git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ['git', *args], cwd=cwd or Path.cwd(), check=False,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise TaskStateError(f'git {" ".join(args)} failed: {detail}')
    return result.stdout.strip()


def current_worktree() -> Path:
    return Path(run_git('rev-parse', '--show-toplevel')).resolve()


def common_git_dir(worktree: Path | None = None) -> Path:
    tree = worktree or current_worktree()
    raw = Path(run_git('rev-parse', '--git-common-dir', cwd=tree))
    return (raw if raw.is_absolute() else tree / raw).resolve()


def state_root(worktree: Path | None = None) -> Path:
    return common_git_dir(worktree) / 'agent-memory'


def tasks_dir(worktree: Path | None = None) -> Path:
    return state_root(worktree) / 'tasks'


def history_dir(worktree: Path | None = None) -> Path:
    return state_root(worktree) / 'task-history'


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def normalize_pattern(pattern: str) -> str:
    value = pattern.strip().replace('\\', '/')
    if (
        not value or value.startswith('/') or value in BROAD_PATTERNS
        or '..' in Path(value).parts
    ):
        raise TaskStateError(f'unsafe or repository-wide scope pattern: {pattern!r}')
    return value


def normalize_repo_path(path: str) -> str:
    value = path.strip().replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    if not value or value.startswith('/') or '..' in Path(value).parts:
        raise TaskStateError(f'unsafe repository path: {path!r}')
    return value


def path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith('/**'):
        prefix = pattern[:-3].rstrip('/')
        return path == prefix or path.startswith(f'{prefix}/')
    return fnmatch.fnmatchcase(path, pattern)


def path_is_authorized(record: dict[str, object], path: str) -> bool:
    normalized = normalize_repo_path(path)
    excluded = tuple(str(item) for item in record['excluded_scope'])
    authorized = tuple(str(item) for item in record['authorized_scope'])
    if any(path_matches(normalized, pattern) for pattern in excluded):
        return False
    return any(path_matches(normalized, pattern) for pattern in authorized)


def task_filename(worktree: Path, task: str) -> str:
    digest = hashlib.sha256(str(worktree).encode()).hexdigest()[:12]
    return f'{digest}-{task}.json'


def validate_text(record: dict[str, object], key: str) -> None:
    value = record.get(key)
    if (
        not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT
        or '\n' in value or '\r' in value
    ):
        raise TaskStateError(f'{key} must be one non-empty line of at most {MAX_TEXT} characters')


def validate_record(record: dict[str, object], source: Path | None = None) -> None:
    required = {
        'version', 'task', 'owner', 'worktree', 'branch', 'head',
        'authorized_scope', 'excluded_scope', 'state', 'next_action',
        'blocker', 'status', 'updated_at',
    }
    missing = sorted(required - record.keys())
    if missing:
        raise TaskStateError(f'{source or "task record"} missing: {", ".join(missing)}')
    if record['version'] != 1:
        raise TaskStateError(f'{source or "task record"} uses unsupported version')
    task = record.get('task')
    if not isinstance(task, str) or not TASK_PATTERN.fullmatch(task):
        raise TaskStateError(f'{source or "task record"} has invalid task slug')
    worktree = Path(str(record.get('worktree', '')))
    if not worktree.is_absolute():
        raise TaskStateError(f'{source or "task record"} worktree must be absolute')
    if not isinstance(record.get('branch'), str) or not str(record['branch']).strip():
        raise TaskStateError(f'{source or "task record"} has invalid branch')
    if not isinstance(record.get('head'), str) or not SHA_PATTERN.fullmatch(str(record['head'])):
        raise TaskStateError(f'{source or "task record"} has invalid head')
    for field in ('owner', 'state', 'next_action', 'blocker', 'updated_at'):
        validate_text(record, field)
    if record['status'] not in {'active', 'paused'}:
        raise TaskStateError(f'{source or "task record"} has invalid status')
    for field in ('authorized_scope', 'excluded_scope'):
        value = record.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise TaskStateError(f'{source or "task record"} {field} must be a string array')
        for item in value:
            normalize_pattern(item)
    if not record['authorized_scope']:
        raise TaskStateError(f'{source or "task record"} authorized_scope may not be empty')
    expansions = record.get('scope_expansions', [])
    if not isinstance(expansions, list):
        raise TaskStateError(f'{source or "task record"} scope_expansions must be an array')
    for expansion in expansions:
        if not isinstance(expansion, dict):
            raise TaskStateError(f'{source or "task record"} has an invalid scope expansion')
        if set(expansion) != {'scope', 'owner_confirmation', 'recorded_at'}:
            raise TaskStateError(f'{source or "task record"} has malformed scope expansion fields')
        normalize_pattern(str(expansion['scope']))
        for field in ('owner_confirmation', 'recorded_at'):
            if (
                not isinstance(expansion[field], str) or not str(expansion[field]).strip()
                or '\n' in str(expansion[field]) or '\r' in str(expansion[field])
            ):
                raise TaskStateError(f'{source or "task record"} scope expansion needs {field}')
        if len(str(expansion['owner_confirmation'])) > MAX_TEXT:
            raise TaskStateError('scope-expansion owner confirmation is too long')
    try:
        parsed = datetime.fromisoformat(str(record['updated_at']))
    except ValueError as exc:
        raise TaskStateError(f'{source or "task record"} has invalid updated_at') from exc
    if parsed.tzinfo is None:
        raise TaskStateError(f'{source or "task record"} updated_at needs a timezone')


def atomic_write_json(path: Path, record: dict[str, object]) -> None:
    validate_record(record, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def load_records(worktree: Path | None = None) -> list[tuple[Path, dict[str, object]]]:
    directory = tasks_dir(worktree)
    if not directory.exists():
        return []
    records: list[tuple[Path, dict[str, object]]] = []
    for path in sorted(directory.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise TaskStateError(f'unreadable task record {path}: {exc}') from exc
        if not isinstance(data, dict):
            raise TaskStateError(f'{path} must contain a JSON object')
        validate_record(data, path)
        records.append((path, data))
    return records


def current_records(active_only: bool = False) -> list[tuple[Path, dict[str, object]]]:
    tree = current_worktree()
    matches = [
        item for item in load_records(tree)
        if Path(str(item[1]['worktree'])).resolve() == tree
    ]
    if active_only:
        matches = [item for item in matches if item[1]['status'] == 'active']
    return matches


def one_current_record(active_only: bool = False) -> tuple[Path, dict[str, object]]:
    matches = current_records(active_only=active_only)
    if not matches:
        raise TaskStateError('no local task state exists for this worktree')
    if len(matches) > 1:
        raise TaskStateError('multiple local task records exist for this worktree')
    return matches[0]


def live_identity(worktree: Path) -> tuple[str, str]:
    branch = run_git('branch', '--show-current', cwd=worktree)
    head = run_git('rev-parse', 'HEAD', cwd=worktree)
    if not branch:
        raise TaskStateError('detached HEAD worktrees are not supported for active task state')
    return branch, head


def new_record(args: argparse.Namespace) -> dict[str, object]:
    tree = current_worktree()
    branch, head = live_identity(tree)
    return {
        'version': 1,
        'task': args.task,
        'owner': args.owner,
        'worktree': str(tree),
        'branch': branch,
        'head': head,
        'authorized_scope': [normalize_pattern(item) for item in args.scope],
        'excluded_scope': [normalize_pattern(item) for item in args.exclude],
        'scope_expansions': [],
        'state': args.state,
        'next_action': args.next_action,
        'blocker': args.blocker,
        'status': 'active',
        'updated_at': now_iso(),
    }


def command_start(args: argparse.Namespace) -> int:
    if current_records():
        raise TaskStateError('this worktree already has local task state; update or finish it first')
    if not TASK_PATTERN.fullmatch(args.task):
        raise TaskStateError('task must be a 2-80 character lowercase slug')
    record = new_record(args)
    path = tasks_dir() / task_filename(current_worktree(), args.task)
    atomic_write_json(path, record)
    print(f'started local task {args.task}: {path}')
    return 0


def command_update(args: argparse.Namespace) -> int:
    path, record = one_current_record()
    tree = current_worktree()
    branch, head = live_identity(tree)
    if branch != record['branch']:
        raise TaskStateError(f'task branch is {record["branch"]!r}; current branch is {branch!r}')
    for key, value in {
        'state': args.state, 'next_action': args.next_action, 'blocker': args.blocker,
    }.items():
        if value is not None:
            record[key] = value
    record['head'] = head
    record['updated_at'] = now_iso()
    atomic_write_json(path, record)
    print(f'updated local task {record["task"]}')
    return 0


def command_expand_scope(args: argparse.Namespace) -> int:
    path, record = one_current_record(active_only=True)
    confirmation = args.owner_confirmation.strip()
    if (
        len(confirmation) < 8 or len(confirmation) > MAX_TEXT
        or '\n' in confirmation or '\r' in confirmation
    ):
        raise TaskStateError('owner confirmation must be an exact 8-300 character quote')
    additions = [normalize_pattern(item) for item in args.scope]
    authorized = [str(item) for item in record['authorized_scope']]
    expansions = list(record.get('scope_expansions', []))
    for addition in additions:
        if addition in authorized:
            continue
        authorized.append(addition)
        expansions.append({
            'scope': addition,
            'owner_confirmation': confirmation,
            'recorded_at': now_iso(),
        })
    if authorized == record['authorized_scope']:
        raise TaskStateError('all requested scope patterns are already authorized')
    tree = current_worktree()
    branch, head = live_identity(tree)
    if branch != record['branch']:
        raise TaskStateError('cannot expand scope after changing branches')
    record['authorized_scope'] = authorized
    record['scope_expansions'] = expansions
    record['head'] = head
    record['updated_at'] = now_iso()
    atomic_write_json(path, record)
    print(f'expanded local task {record["task"]} scope with recorded owner confirmation')
    return 0


def packet_path(record: dict[str, object]) -> Path:
    return SCRIPT_ROOT / 'docs' / 'resume' / f'{record["task"]}.md'


def render_packet(record: dict[str, object], reason: str, verification: str) -> str:
    scopes = json.dumps(record['authorized_scope'], separators=(',', ':'))
    excluded = json.dumps(record['excluded_scope'], separators=(',', ':'))
    expansions = json.dumps(record.get('scope_expansions', []), separators=(',', ':'))
    return (
        f'# Resume: {record["task"]}\n\n'
        'Status: `Paused`.\n'
        f'Owner: `{record["owner"]}`\n'
        f'Task: `{record["task"]}`\n'
        f'Branch: `{record["branch"]}`\n'
        f'Last verified commit: `{record["head"]}`\n'
        f'Authorized scope: `{scopes}`\n'
        f'Excluded scope: `{excluded}`\n'
        f'Scope expansion audit: `{expansions}`\n'
        f'Paused because: {reason}\n'
        f'Exact next action: {record["next_action"]}\n'
        f'Blocker: {record["blocker"]}\n'
        f'Verification: {verification}\n'
        f'Last verified: `{record["updated_at"]}`\n'
    )


def command_pause(args: argparse.Namespace) -> int:
    path, record = one_current_record(active_only=True)
    tree = current_worktree()
    branch, head = live_identity(tree)
    if branch != record['branch']:
        raise TaskStateError('cannot pause after changing branches')
    record['head'] = head
    record['updated_at'] = now_iso()
    packet = packet_path(record)
    if packet.exists():
        raise TaskStateError(f'resume packet already exists: {packet}')
    packet.parent.mkdir(parents=True, exist_ok=True)
    for label, value in (('pause reason', args.reason), ('verification', args.verification)):
        if not value.strip() or len(value) > MAX_TEXT or '\n' in value or '\r' in value:
            raise TaskStateError(f'{label} must be one non-empty line of at most {MAX_TEXT} characters')
    rendered = render_packet(record, args.reason, args.verification)
    if len(rendered.encode('utf-8')) > MAX_PACKET_BYTES:
        raise TaskStateError('resume packet exceeds 8 KiB')
    packet.write_text(rendered, encoding='utf-8')
    record['status'] = 'paused'
    record['resume_packet'] = str(packet.relative_to(SCRIPT_ROOT))
    atomic_write_json(path, record)
    print(f'paused {record["task"]}; wrote {packet.relative_to(SCRIPT_ROOT)}')
    return 0


def clean_code_value(value: str) -> str:
    value = value.strip()
    if value.startswith('`') and value.endswith('`.'):
        return value[1:-2]
    if value.startswith('`') and value.endswith('`'):
        return value[1:-1]
    return value


def parse_packet(path: Path) -> dict[str, str]:
    if not path.is_file() or len(path.read_bytes()) > MAX_PACKET_BYTES:
        raise TaskStateError(f'invalid or oversized resume packet: {path}')
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        key, separator, value = line.partition(': ')
        if separator:
            values[key] = clean_code_value(value)
    required = {
        'Status', 'Owner', 'Task', 'Branch', 'Last verified commit',
        'Authorized scope', 'Excluded scope', 'Scope expansion audit',
        'Exact next action',
    }
    missing = sorted(required - values.keys())
    if missing or values.get('Status') != 'Paused':
        raise TaskStateError(f'{path} is not a valid paused resume packet')
    if not TASK_PATTERN.fullmatch(values['Task']):
        raise TaskStateError(f'{path} has an invalid task slug')
    if not values['Branch'].strip() or not SHA_PATTERN.fullmatch(values['Last verified commit']):
        raise TaskStateError(f'{path} has invalid Git identity metadata')
    try:
        authorized = json.loads(values['Authorized scope'])
        excluded = json.loads(values['Excluded scope'])
        expansions = json.loads(values['Scope expansion audit'])
    except json.JSONDecodeError as exc:
        raise TaskStateError(f'{path} has invalid JSON scope fields') from exc
    if not isinstance(authorized, list) or not authorized:
        raise TaskStateError(f'{path} needs at least one authorized scope')
    if not isinstance(excluded, list):
        raise TaskStateError(f'{path} excluded scope must be an array')
    if not isinstance(expansions, list):
        raise TaskStateError(f'{path} scope expansion audit must be an array')
    for pattern in [*authorized, *excluded]:
        if not isinstance(pattern, str):
            raise TaskStateError(f'{path} scope values must be strings')
        normalize_pattern(pattern)
    fixture = {
        'version': 1, 'task': values['Task'], 'owner': values['Owner'],
        'worktree': '/packet/validation', 'branch': values['Branch'],
        'head': values['Last verified commit'], 'authorized_scope': authorized,
        'excluded_scope': excluded, 'scope_expansions': expansions,
        'state': 'Paused transfer packet.', 'next_action': values['Exact next action'],
        'blocker': values.get('Blocker', 'none'), 'status': 'paused',
        'updated_at': values.get('Last verified', now_iso()),
    }
    validate_record(fixture, path)
    return values


def command_resume(args: argparse.Namespace) -> int:
    packet = Path(args.packet)
    if not packet.is_absolute():
        packet = SCRIPT_ROOT / packet
    packet = packet.resolve()
    resume_dir = (SCRIPT_ROOT / 'docs' / 'resume').resolve()
    if packet.parent != resume_dir or packet.name == 'README.md':
        raise TaskStateError('resume packet must be a Markdown file directly under docs/resume/')
    values = parse_packet(packet)
    existing = current_records()
    if existing:
        path, record = one_current_record()
        if record['task'] != values['Task']:
            raise TaskStateError('resume packet does not match this worktree task')
        if record['status'] != 'paused':
            raise TaskStateError('local task state is not paused')
        expected = {
            'owner': values['Owner'],
            'branch': values['Branch'],
            'authorized_scope': json.loads(values['Authorized scope']),
            'excluded_scope': json.loads(values['Excluded scope']),
            'scope_expansions': json.loads(values['Scope expansion audit']),
        }
        for key, value in expected.items():
            if record.get(key, [] if key == 'scope_expansions' else None) != value:
                raise TaskStateError(f'resume packet {key} does not match local paused state')
    else:
        tree = current_worktree()
        branch, head = live_identity(tree)
        if branch != values['Branch']:
            raise TaskStateError(f'resume packet requires branch {values["Branch"]!r}')
        record = {
            'version': 1,
            'task': values['Task'],
            'owner': values['Owner'],
            'worktree': str(tree),
            'branch': branch,
            'head': head,
            'authorized_scope': json.loads(values['Authorized scope']),
            'excluded_scope': json.loads(values['Excluded scope']),
            'scope_expansions': json.loads(values['Scope expansion audit']),
            'state': 'Resumed from an explicit durable packet.',
            'next_action': values['Exact next action'],
            'blocker': values.get('Blocker', 'none'),
            'status': 'active',
            'updated_at': now_iso(),
            'resume_packet': str(packet.relative_to(SCRIPT_ROOT)),
        }
        path = tasks_dir(tree) / task_filename(tree, values['Task'])
    record['status'] = 'active'
    record['head'] = run_git('rev-parse', 'HEAD', cwd=current_worktree())
    record['updated_at'] = now_iso()
    record['resume_packet'] = str(packet.relative_to(SCRIPT_ROOT))
    atomic_write_json(path, record)
    print(f'resumed local task {record["task"]}')
    return 0


def archive_record(path: Path, record: dict[str, object]) -> Path:
    target_dir = history_dir(current_worktree())
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
    target = target_dir / f'{stamp}-{path.name}'
    shutil.move(str(path), target)
    return target


def command_finish(args: argparse.Namespace) -> int:
    path, record = one_current_record()
    status = run_git('status', '--porcelain', cwd=current_worktree())
    if status:
        raise TaskStateError('worktree is dirty; commit closeout before finishing local state')
    packet_value = record.get('resume_packet')
    if isinstance(packet_value, str):
        packet = SCRIPT_ROOT / packet_value
        if packet.exists():
            raise TaskStateError(
                'tracked resume packet still exists; remove it in a reviewed '
                'Git closeout commit before finishing local state'
            )
    record['finished_at'] = now_iso()
    record['verification'] = args.verification
    target = archive_record(path, record)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'finished {record["task"]}; archived local state at {target}')
    return 0


def record_health(record: dict[str, object]) -> str:
    tree = Path(str(record['worktree']))
    if not tree.is_dir():
        return 'missing-worktree'
    try:
        branch, head = live_identity(tree)
    except TaskStateError:
        return 'unavailable'
    if branch != record['branch']:
        return 'branch-drift'
    if head != record['head']:
        return 'head-advanced'
    return str(record['status'])


def command_list(args: argparse.Namespace) -> int:
    records = current_records() if args.current else load_records()
    if args.json:
        print(json.dumps([record for _, record in records], indent=2, sort_keys=True))
        return 0
    if not records:
        print('No local agent tasks.')
        return 0
    for _, record in records:
        print(
            f'{record["task"]}: {record_health(record)}; owner={record["owner"]}; '
            f'worktree={record["worktree"]}; branch={record["branch"]}; '
            f'next={record["next_action"]}; blocker={record["blocker"]}'
        )
    return 0


def self_test() -> int:
    record = {
        'version': 1, 'task': 'self-test', 'owner': 'test',
        'worktree': '/tmp/example', 'branch': 'test', 'head': '0' * 40,
        'authorized_scope': ['docs/example/**', '.github/**'],
        'excluded_scope': ['docs/example/private/**'], 'scope_expansions': [],
        'state': 'Testing.',
        'next_action': 'Finish the test.', 'blocker': 'none', 'status': 'active',
        'updated_at': '2026-07-20T12:00:00-05:00',
    }
    validate_record(record)
    assert path_is_authorized(record, 'docs/example/public.md')
    assert path_is_authorized(record, '.github/workflows/ci.yml')
    assert not path_is_authorized(record, 'docs/example/private/secret.md')
    assert not path_is_authorized(record, 'src/app.py')
    rendered = render_packet(record, 'explicit transfer required', 'tests pass')
    assert 'Exact next action: Finish the test.' in rendered
    with TemporaryDirectory(prefix='agent-memory-task-packet-') as temporary:
        packet = Path(temporary) / 'self-test.md'
        packet.write_text(rendered, encoding='utf-8')
        parsed = parse_packet(packet)
        assert parsed['Task'] == 'self-test'
    with TemporaryDirectory(prefix='agent-memory-task-lifecycle-') as temporary:
        root = Path(temporary)
        tools_dir = root / 'tools'
        tools_dir.mkdir()
        shutil.copy2(Path(__file__), tools_dir / 'task_state.py')

        def fixture_run(*command: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                list(command), cwd=root, check=False, capture_output=True, text=True,
            )
            if result.returncode != expected:
                detail = result.stderr.strip() or result.stdout.strip()
                raise AssertionError(
                    f'task lifecycle command returned {result.returncode}, '
                    f'expected {expected}: {" ".join(command)}: {detail}'
                )
            return result

        fixture_run('git', 'init', '-b', 'main')
        fixture_run('git', 'config', 'user.name', 'Task State Self Test')
        fixture_run('git', 'config', 'user.email', 'task-state@example.invalid')
        fixture_run('git', 'add', 'tools/task_state.py')
        fixture_run('git', 'commit', '-m', 'fixture')
        command = (sys.executable, 'tools/task_state.py')
        fixture_run(
            *command, 'start', '--task', 'lifecycle-test', '--owner', 'test',
            '--scope', 'docs/**', '--exclude', 'docs/private/**',
            '--state', 'Testing lifecycle.', '--next', 'Pause the task.',
        )
        fixture_run(
            *command, 'expand-scope', '--scope', 'tools/**',
            '--owner-confirmation', 'Owner explicitly approved tools scope.',
        )
        fixture_run(*command, 'update', '--state', 'Ready to transfer.')
        fixture_run(
            *command, 'pause', '--reason', 'Transfer test.',
            '--verification', 'Self-test setup passed.',
        )
        packet = root / 'docs' / 'resume' / 'lifecycle-test.md'
        assert packet.is_file()
        fixture_run('git', 'add', 'docs/resume/lifecycle-test.md')
        fixture_run('git', 'commit', '-m', 'track resume packet')
        fixture_run(*command, 'resume', 'docs/resume/lifecycle-test.md')
        blocked = fixture_run(
            *command, 'finish', '--verification', 'Expected refusal.', expected=1,
        )
        assert 'tracked resume packet still exists' in blocked.stderr
        shutil.move(str(packet), root / '.git' / 'lifecycle-test-resume.md')
        fixture_run('git', 'add', '-A')
        fixture_run('git', 'commit', '-m', 'close resume packet')
        fixture_run(*command, 'finish', '--verification', 'Lifecycle test passed.')
        listing = fixture_run(*command, 'list', '--current')
        assert 'No local agent tasks.' in listing.stdout
        assert list((root / '.git' / 'agent-memory' / 'task-history').glob('*.json'))
    print('task-state self-test passed')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('start')
    start.add_argument('--task', required=True)
    start.add_argument('--owner', required=True)
    start.add_argument('--scope', action='append', required=True)
    start.add_argument('--exclude', action='append', default=[])
    start.add_argument('--state', required=True)
    start.add_argument('--next', dest='next_action', required=True)
    start.add_argument('--blocker', default='none')
    start.set_defaults(func=command_start)
    update = sub.add_parser('update')
    update.add_argument('--state')
    update.add_argument('--next', dest='next_action')
    update.add_argument('--blocker')
    update.set_defaults(func=command_update)
    expand = sub.add_parser('expand-scope')
    expand.add_argument('--scope', action='append', required=True)
    expand.add_argument('--owner-confirmation', required=True)
    expand.set_defaults(func=command_expand_scope)
    pause = sub.add_parser('pause')
    pause.add_argument('--reason', required=True)
    pause.add_argument('--verification', required=True)
    pause.set_defaults(func=command_pause)
    resume = sub.add_parser('resume')
    resume.add_argument('packet')
    resume.set_defaults(func=command_resume)
    finish = sub.add_parser('finish')
    finish.add_argument('--verification', required=True)
    finish.set_defaults(func=command_finish)
    listing = sub.add_parser('list')
    listing.add_argument('--current', action='store_true')
    listing.add_argument('--json', action='store_true')
    listing.set_defaults(func=command_list)
    test = sub.add_parser('self-test')
    test.set_defaults(func=lambda _args: self_test())
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (OSError, json.JSONDecodeError, TaskStateError) as error:
        print(f'task state failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
