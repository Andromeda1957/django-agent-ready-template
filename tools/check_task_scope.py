#!/usr/bin/env python3
"""Reject protected or out-of-scope staged changes without Git-local task state."""

from __future__ import annotations

import argparse
import subprocess
import sys

sys.dont_write_bytecode = True

import history_log  # noqa: E402
from task_state import TaskStateError  # noqa: E402
from task_state import current_records  # noqa: E402
from task_state import current_worktree  # noqa: E402
from task_state import path_is_authorized  # noqa: E402
from task_state import path_matches  # noqa: E402
from task_state import run_git  # noqa: E402

PROTECTED_PATTERNS = (
    '.agents/**',
    '.claude/**',
    '.github/**',
    '.gitignore',
    'AGENTS.md',
    'CHANGELOG.md',
    'CLAUDE.md',
    'PROJECT_MEMORY.md',
    'docs/memory/**',
    'docs/plans/**',
    'docs/resume/**',
    'docs/runbooks/**',
    'docs/repo_history/**',
    'hooks/**',
    'tools/**',
)


def staged_paths(diff_filter: str = 'ACMRDTUXB') -> list[str]:
    output = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', f'--diff-filter={diff_filter}', '-z'],
        cwd=current_worktree(), check=True, capture_output=True,
    ).stdout
    return [item.decode('utf-8', errors='surrogateescape') for item in output.split(b'\0') if item]


def staged_text(path: str) -> str:
    result = subprocess.run(
        ['git', 'show', f':{path}'], cwd=current_worktree(), check=True,
        capture_output=True, text=True,
    )
    return result.stdout


def lifecycle_errors(
    added: set[str], modified: set[str], deleted: set[str], renamed: set[str],
) -> list[str]:
    errors: list[str] = []
    immutable_prefixes = (
        'docs/repo_history/changelog/entries/',
        'docs/repo_history/completed-plans/',
    )
    for path in sorted(modified | deleted | renamed):
        if path.startswith(immutable_prefixes):
            errors.append(f'append-only historical file may not be changed or removed: {path}')
        name = path.rsplit('/', 1)[-1]
        if (
            path.startswith('docs/repo_history/changelog/')
            and path.count('/') == 3
            and name.endswith('.md')
            and history_log.MONTH_PATTERN.fullmatch(name[:-3])
        ):
            errors.append(f'legacy monthly ledger is read-only: {path}')

    for path in sorted(added):
        if not path.startswith('docs/repo_history/changelog/entries/') or not path.endswith('.md'):
            continue
        impacts = history_log.IMPACT_PATTERN.findall(staged_text(path))
        if len(impacts) != 1:
            errors.append(f'new structured history entry needs exactly one Plan impact: {path}')
            continue
        impact = impacts[0]
        if impact == 'none':
            continue
        action, slug = impact.split(':', 1)
        plan = f'docs/plans/{slug}.md'
        archive = f'docs/repo_history/completed-plans/{slug}.md'
        if action == 'updates' and plan not in (added | modified):
            errors.append(f'{path} says updates:{slug} but {plan} is not staged')
        if action == 'completes':
            if plan not in deleted:
                errors.append(f'{path} says completes:{slug} but {plan} is not staged for removal')
            if archive not in added:
                errors.append(f'{path} says completes:{slug} but {archive} is not staged')
            if 'docs/plans/README.md' not in modified:
                errors.append(f'{path} completes a plan but the planning dashboard is not staged')
    return errors


def active_record() -> dict[str, object] | None:
    records = [record for _, record in current_records(active_only=True)]
    if len(records) > 1:
        raise TaskStateError('multiple active task records exist for this worktree')
    return records[0] if records else None


def protected_paths(paths: list[str]) -> list[str]:
    return [
        path for path in paths
        if any(path_matches(path, pattern) for pattern in PROTECTED_PATTERNS)
    ]


def primary_branch() -> str:
    configured_result = subprocess.run(
        ['git', 'config', '--get', 'memory.primaryBranch'], cwd=current_worktree(),
        check=False, capture_output=True, text=True,
    )
    configured = configured_result.stdout.strip()
    if configured:
        return configured
    for candidate in ('main', 'master'):
        result = subprocess.run(
            ['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{candidate}'],
            cwd=current_worktree(), check=False,
        )
        if result.returncode == 0:
            return candidate
    return run_git('branch', '--show-current', cwd=current_worktree())


def check_paths(paths: list[str]) -> tuple[str, list[str]]:
    record = active_record()
    branch = run_git('branch', '--show-current', cwd=current_worktree())
    if record is None:
        protected = protected_paths(paths)
        if branch != primary_branch() and paths:
            return ('non-primary-branch work requires Git-local task state', paths)
        if protected:
            return ('protected paths require Git-local task state', protected)
        return ('not-required', [])
    if record['branch'] != branch:
        raise TaskStateError(
            f'local task branch is {record["branch"]!r}; current branch is {branch!r}'
        )
    rejected = [path for path in paths if not path_is_authorized(record, path)]
    return (str(record['task']), rejected)


def self_test() -> None:
    record = {
        'authorized_scope': ['docs/example/**', '.github/**'],
        'excluded_scope': ['docs/example/private/**'],
    }
    assert path_is_authorized(record, 'docs/example/public.md')
    assert path_is_authorized(record, '.github/workflows/ci.yml')
    assert not path_is_authorized(record, 'docs/example/private/secret.md')
    assert not path_is_authorized(record, 'src/app.py')
    assert protected_paths(['AGENTS.md']) == ['AGENTS.md']
    assert protected_paths(['README.md']) == []
    assert lifecycle_errors(set(), set(), set(), set()) == []
    immutable = lifecycle_errors(
        set(), {'docs/repo_history/changelog/entries/2026-07/test.md'}, set(), set(),
    )
    assert immutable and 'append-only' in immutable[0]
    print('task scope self-test passed')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--paths', nargs='*')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.staged and args.paths is None:
        parser.error('choose --staged, --paths, or --self-test')
    try:
        paths = staged_paths() if args.staged else list(args.paths or [])
        task, rejected = check_paths(paths)
        lifecycle = []
        if args.staged:
            lifecycle = lifecycle_errors(
                set(staged_paths('A')), set(staged_paths('M')),
                set(staged_paths('D')), set(staged_paths('R')),
            )
    except (OSError, subprocess.CalledProcessError, TaskStateError) as error:
        print(f'task scope check failed: {error}')
        return 1
    if rejected:
        print(f'task scope check failed: {task}:')
        for path in rejected:
            print(f'  blocked path: {path}')
        print('Start or expand task state with python3 tools/task_state.py.')
        return 1
    if lifecycle:
        print('task scope check failed: memory lifecycle:')
        for error in lifecycle:
            print(f'  {error}')
        return 1
    if task == 'not-required':
        print(f'task scope check not required for {len(paths)} unprotected primary-branch path(s)')
    else:
        print(f'task scope check passed for {task}: {len(paths)} path(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
