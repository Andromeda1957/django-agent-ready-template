#!/usr/bin/env python3
"""Validate future-only plans and archive a plan safely at completion."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

sys.dont_write_bytecode = True

import history_log  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = ROOT / 'docs' / 'plans'
PLAN_INDEX = PLANS_DIR / 'README.md'
COMPLETED_DIR = ROOT / 'docs' / 'repo_history' / 'completed-plans'
MAX_PLAN_BYTES = 16 * 1024
VALID_STATUSES = frozenset({'Incomplete', 'Wait Not Yet', 'Blocked', 'Skipped'})
STATUS_PATTERN = re.compile(r'^Status: `(?P<status>[^`]+)`\.$', re.MULTILINE)
NEXT_PATTERN = re.compile(r'^Next action: (?P<value>\S.*)$', re.MULTILINE)
EXIT_PATTERN = re.compile(r'^Exit condition: (?P<value>\S.*)$', re.MULTILINE)
FORBIDDEN_HEADING_PATTERN = re.compile(
    r'^##\s+(?:Current|Existing Baseline|Historical|Status|Completed|Shipped|Deployed)\b',
    re.IGNORECASE | re.MULTILINE,
)
CHECKED_ITEM_PATTERN = re.compile(r'^\s*[-*]\s+\[[xX]\]', re.MULTILINE)
HISTORY_FACT_PATTERNS = (
    re.compile(r'\b(?:CI|Deploy) run [`#]*(?:\d{6,})', re.IGNORECASE),
    re.compile(r'\bmerged to [`*]*(?:main|master)', re.IGNORECASE),
    re.compile(r'\b(?:was|were|is|are|has been|have been) (?:already )?(?:shipped|deployed|production-imported|live-verified)\b', re.IGNORECASE),
    re.compile(r'\b(?:shipped|deployed|production-imported|live-verified)\s+20\d{2}-\d{2}-\d{2}\b', re.IGNORECASE),
    re.compile(r'\bdone-local\b', re.IGNORECASE),
    re.compile(r'\b[0-9a-f]{8,40}\b'),
    re.compile(
        r'^(?:The )?completed .+\b(?:is|are|was|were|has|have)\b',
        re.IGNORECASE | re.MULTILINE,
    ),
)


class PlanError(ValueError):
    """Raised when a plan is historical, malformed, or cannot transition."""


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)


def one_match(pattern: re.Pattern[str], text: str, field: str, path: Path) -> re.Match[str]:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise PlanError(f'{path} must declare exactly one {field}')
    return matches[0]


def validate_plan(path: Path, text: str | None = None) -> str:
    content = path.read_text(encoding='utf-8') if text is None else text
    if len(content.encode('utf-8')) > MAX_PLAN_BYTES:
        raise PlanError(f'{path} exceeds the {MAX_PLAN_BYTES}-byte future-plan limit')
    status = one_match(STATUS_PATTERN, content, 'Status', path)['status']
    if status not in VALID_STATUSES:
        raise PlanError(f'{path} uses invalid status {status!r}')
    one_match(NEXT_PATTERN, content, 'Next action', path)
    one_match(EXIT_PATTERN, content, 'Exit condition', path)
    heading = FORBIDDEN_HEADING_PATTERN.search(content)
    if heading:
        raise PlanError(f'{path} contains history/current-state heading {heading.group(0)!r}')
    if CHECKED_ITEM_PATTERN.search(content):
        raise PlanError(f'{path} contains checked work; move completed results to history')
    for pattern in HISTORY_FACT_PATTERNS:
        match = pattern.search(content)
        if match:
            raise PlanError(f'{path} contains completed-history evidence {match.group(0)!r}')
    return status


def validate_all(root: Path = ROOT) -> None:
    plans = root / 'docs' / 'plans'
    for path in sorted(plans.glob('*.md')):
        if path.name != 'README.md':
            validate_plan(path)


def remove_index_entry(text: str, filename: str) -> str:
    pattern = re.compile(
        rf'^- `{re.escape(filename)}`:.*?(?=^- `|^## |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise PlanError(f'planning dashboard must contain exactly one entry for {filename}')
    updated = text[:matches[0].start()] + text[matches[0].end():]
    return re.sub(r'\n{3,}', '\n\n', updated).rstrip() + '\n'


def archive_plan(args: argparse.Namespace) -> None:
    slug = args.plan.removesuffix('.md')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,79}', slug):
        raise PlanError('plan must be a filename slug')
    source = PLANS_DIR / f'{slug}.md'
    if not source.is_file():
        raise PlanError(f'active plan does not exist: {source.relative_to(ROOT)}')
    validate_plan(source)
    history_log.check()
    target = COMPLETED_DIR / source.name
    if target.exists():
        raise PlanError(f'completed-plan archive already exists: {target.relative_to(ROOT)}')
    index_text = PLAN_INDEX.read_text(encoding='utf-8')
    updated_index = remove_index_entry(index_text, source.name)
    if not args.summary.strip() or '\n' in args.title:
        raise PlanError('completion needs a one-line title and non-empty summary')

    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), target)
    try:
        atomic_write(PLAN_INDEX, updated_index)
        history_log.write_structured_entry(
            args.title.strip(),
            f'completes:{slug}',
            [args.summary.strip()],
        )
    except (OSError, PlanError, history_log.HistoryError):
        atomic_write(PLAN_INDEX, index_text)
        if target.exists() and not source.exists():
            shutil.move(str(target), source)
        raise
    print(f'archived completed plan at {target.relative_to(ROOT)}')


def self_test() -> None:
    valid = (
        '# Future plan\n\nStatus: `Incomplete`.\n\n'
        'Next action: Implement the bounded slice.\n'
        'Exit condition: The acceptance gate passes.\n\n'
        '## Remaining Work\n\n- Implement the bounded slice.\n'
    )
    invalid = {
        'missing-next.md': valid.replace('Next action: Implement the bounded slice.\n', ''),
        'checked.md': valid + '\n- [x] Old completed task\n',
        'history.md': valid + '\nThe feature was deployed to production.\n',
        'baseline.md': valid + '\n## Existing Baseline\n',
    }
    with TemporaryDirectory(prefix='agent-memory-plans-') as temporary:
        root = Path(temporary)
        good = root / 'good.md'
        good.write_text(valid, encoding='utf-8')
        validate_plan(good)
        for name, content in invalid.items():
            path = root / name
            path.write_text(content, encoding='utf-8')
            try:
                validate_plan(path)
            except PlanError:
                continue
            raise AssertionError(f'plan self-test accepted {name}')
    with TemporaryDirectory(prefix='agent-memory-plan-transition-') as temporary:
        root = Path(temporary)
        tools_dir = root / 'tools'
        plans_dir = root / 'docs' / 'plans'
        ledger_dir = root / 'docs' / 'repo_history' / 'changelog'
        tools_dir.mkdir(parents=True)
        plans_dir.mkdir(parents=True)
        ledger_dir.mkdir(parents=True)
        month = datetime.now().astimezone().strftime('%Y-%m')
        day = f'{month}-01'
        shutil.copy2(Path(__file__), tools_dir / 'plan_lifecycle.py')
        shutil.copy2(Path(history_log.__file__), tools_dir / 'history_log.py')
        (plans_dir / 'example.md').write_text(valid, encoding='utf-8')
        (plans_dir / 'README.md').write_text(
            '# Dashboard\n\n- `example.md`: **Status:** `Incomplete`. Test.\n',
            encoding='utf-8',
        )
        (ledger_dir / f'{month}.md').write_text(
            history_log.render_shard(
                month, legacy_entries=f'## {day} (fixture)\n\n- fixture\n',
            ),
            encoding='utf-8',
        )
        (root / 'CHANGELOG.md').write_text(history_log.render_index(root), encoding='utf-8')
        result = subprocess.run(
            [
                sys.executable, str(tools_dir / 'plan_lifecycle.py'), 'complete',
                '--plan', 'example', '--title', 'Complete example',
                '--summary', 'Verified the example acceptance gate.',
            ],
            cwd=root, check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise AssertionError(f'plan completion self-test failed: {detail}')
        archived = root / 'docs' / 'repo_history' / 'completed-plans' / 'example.md'
        assert archived.read_text(encoding='utf-8') == valid
        assert not (plans_dir / 'example.md').exists()
        assert 'example.md' not in (plans_dir / 'README.md').read_text(encoding='utf-8')
        entries = list((ledger_dir / 'entries').glob('????-??/*.md'))
        assert len(entries) == 1
        assert 'Plan impact: `completes:example`.' in entries[0].read_text(encoding='utf-8')
    print('plan-lifecycle self-test passed')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check')
    sub.add_parser('self-test')
    archive = sub.add_parser('complete')
    archive.add_argument('--plan', required=True)
    archive.add_argument('--title', required=True)
    archive.add_argument('--summary', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'check':
            validate_all()
            print('plan-lifecycle check passed')
        elif args.command == 'self-test':
            self_test()
        else:
            archive_plan(args)
    except (OSError, PlanError, history_log.HistoryError) as error:
        print(f'plan lifecycle failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
