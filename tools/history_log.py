#!/usr/bin/env python3
"""Manage sharded chronological history and its generated root index."""

from __future__ import annotations

import argparse
import calendar
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / 'CHANGELOG.md'
LEDGER_DIR = ROOT / 'docs' / 'repo_history' / 'changelog'
MANAGED_DIR = LEDGER_DIR / 'entries'
MONTH_PATTERN = re.compile(r'^(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])$')
ENTRY_PATTERN = re.compile(r'^## (?P<date>\d{4}-\d{2}-\d{2})(?:\s|$)', re.MULTILINE)
IMPACT_PATTERN = re.compile(
    r'^Plan impact: `(?P<impact>none|updates:[a-z0-9][a-z0-9-]{1,79}|completes:[a-z0-9][a-z0-9-]{1,79})`\.$',
    re.MULTILINE,
)
MANAGED_START = '<!-- managed-entries:start -->'
MANAGED_END = '<!-- managed-entries:end -->'
LEGACY_START = '<!-- legacy-entries:start -->'
LEGACY_END = '<!-- legacy-entries:end -->'


class HistoryError(ValueError):
    """Raised when chronological history cannot be migrated or validated."""


def month_label(month: str) -> str:
    match = MONTH_PATTERN.fullmatch(month)
    if not match:
        raise HistoryError(f'invalid month: {month!r}')
    return f'{calendar.month_name[int(match["month"])]} {match["year"]}'


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)


def shard_path(month: str, root: Path = ROOT) -> Path:
    return root / 'docs' / 'repo_history' / 'changelog' / f'{month}.md'


def render_shard(month: str, legacy_entries: str = '') -> str:
    legacy = legacy_entries.strip('\n')
    lines = [
        f'# Chronological History — {month_label(month)}',
        '',
        'Append new entries with `python3 tools/history_log.py add`; do not edit',
        'the generated root `CHANGELOG.md` directly.',
        '',
        MANAGED_START,
    ]
    lines.extend([MANAGED_END, '', LEGACY_START])
    if legacy:
        lines.extend([legacy, ''])
    lines.extend([LEGACY_END, ''])
    return '\n'.join(lines)


def parse_legacy_root(text: str) -> dict[str, str]:
    if not text.startswith('# Changelog\n'):
        raise HistoryError('root changelog is not in the legacy monolithic format')
    matches = list(ENTRY_PATTERN.finditer(text))
    if not matches:
        raise HistoryError('legacy changelog contains no dated entries')
    prefix = text[len('# Changelog'):matches[0].start()].strip()
    if prefix:
        raise HistoryError('unexpected text exists before the first dated entry')
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.start():end].strip('\n')
        grouped[match['date'][:7]].append(section)
    return {month: '\n\n'.join(sections) + '\n' for month, sections in grouped.items()}


def ledger_months(root: Path = ROOT) -> list[str]:
    directory = root / 'docs' / 'repo_history' / 'changelog'
    if not directory.is_dir():
        return []
    months = [path.stem for path in directory.glob('????-??.md') if MONTH_PATTERN.fullmatch(path.stem)]
    return sorted(months, reverse=True)


def managed_months(root: Path = ROOT) -> list[str]:
    directory = root / 'docs' / 'repo_history' / 'changelog' / 'entries'
    if not directory.is_dir():
        return []
    months = [path.name for path in directory.iterdir() if path.is_dir() and MONTH_PATTERN.fullmatch(path.name)]
    return sorted(months, reverse=True)


def render_index(root: Path = ROOT) -> str:
    months = ledger_months(root)
    entry_months = managed_months(root)
    lines = [
        '# Changelog',
        '',
        'This is the generated index for the append-only chronological ledger.',
        'Completed work is stored in monthly shards under',
        '`docs/repo_history/changelog/`; curated archived context remains separate',
        'under `docs/repo_history/`. Do not add entries directly to this file.',
        '',
        'Use:',
        '',
        '```bash',
        'python3 tools/history_log.py add --title "short title" --plan-impact none \\',
        '  --summary "verified completed result"',
        '```',
        '',
        '## Structured Entries',
        '',
    ]
    if entry_months:
        for month in entry_months:
            lines.append(
                f'- [{month_label(month)} entries](docs/repo_history/changelog/entries/{month}/)'
            )
    else:
        lines.append('- No structured completion entries yet.')
    lines.extend([
        '',
        '## Legacy Monthly Ledger',
        '',
    ])
    if months:
        for month in months:
            lines.append(
                f'- [{month_label(month)}](docs/repo_history/changelog/{month}.md)'
            )
    else:
        lines.append('- No chronological history shards exist.')
    lines.append('')
    return '\n'.join(lines)


def managed_block(text: str, path: Path) -> str:
    if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1:
        raise HistoryError(f'{path} must contain exactly one managed-entry marker pair')
    before, remainder = text.split(MANAGED_START, 1)
    block, after = remainder.split(MANAGED_END, 1)
    if not before.startswith('# Chronological History — '):
        raise HistoryError(f'{path} has an invalid shard heading')
    if LEGACY_START not in after or LEGACY_END not in after:
        raise HistoryError(f'{path} must contain the legacy-entry marker pair')
    return block.strip()


def validate_shard(path: Path) -> None:
    month = path.stem
    if not MONTH_PATTERN.fullmatch(month):
        raise HistoryError(f'invalid ledger filename: {path.name}')
    text = path.read_text(encoding='utf-8')
    if not text.startswith(f'# Chronological History — {month_label(month)}\n'):
        raise HistoryError(f'{path} heading does not match its month')
    block = managed_block(text, path)
    if block:
        raise HistoryError(f'{path} is a read-only legacy shard; add a structured entry file')
    for match in ENTRY_PATTERN.finditer(text):
        if match['date'][:7] != month:
            raise HistoryError(f'{path} contains out-of-month entry {match["date"]}')


def validate_structured_entry(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if len(text.encode('utf-8')) > 8 * 1024:
        raise HistoryError(f'{path} exceeds the 8 KiB structured-entry limit')
    date_match = re.search(r'^Date: `(?P<date>\d{4}-\d{2}-\d{2})`\.$', text, re.MULTILINE)
    impacts = IMPACT_PATTERN.findall(text)
    if not text.startswith('# ') or date_match is None or len(impacts) != 1:
        raise HistoryError(f'{path} has invalid structured-entry metadata')
    if date_match['date'][:7] != path.parent.name:
        raise HistoryError(f'{path} is filed under the wrong month')
    if not re.search(r'^- \S', text, re.MULTILINE):
        raise HistoryError(f'{path} needs at least one summary bullet')


def structured_impact(path: Path) -> str:
    impacts = IMPACT_PATTERN.findall(path.read_text(encoding='utf-8'))
    if len(impacts) != 1:
        raise HistoryError(f'{path} needs exactly one Plan impact')
    return impacts[0]


def check(root: Path = ROOT) -> None:
    months = ledger_months(root)
    for month in months:
        validate_shard(shard_path(month, root))
    entries_root = root / 'docs' / 'repo_history' / 'changelog' / 'entries'
    if entries_root.is_dir():
        completed_slugs: set[str] = set()
        for path in sorted(entries_root.rglob('*.md')):
            if not MONTH_PATTERN.fullmatch(path.parent.name):
                raise HistoryError(f'{path} is not filed under an YYYY-MM directory')
            validate_structured_entry(path)
            impact = structured_impact(path)
            if impact == 'none':
                continue
            action, slug = impact.split(':', 1)
            active = root / 'docs' / 'plans' / f'{slug}.md'
            archived = root / 'docs' / 'repo_history' / 'completed-plans' / f'{slug}.md'
            if action == 'updates' and not (active.is_file() or archived.is_file()):
                raise HistoryError(f'{path} routes missing plan {slug}')
            if action == 'completes':
                if slug in completed_slugs:
                    raise HistoryError(f'multiple completion entries exist for plan {slug}')
                completed_slugs.add(slug)
                if active.exists() or not archived.is_file():
                    raise HistoryError(
                        f'{path} completion requires archived plan and no active plan: {slug}'
                    )
    index = root / 'CHANGELOG.md'
    expected = render_index(root)
    if not index.is_file() or index.read_text(encoding='utf-8') != expected:
        raise HistoryError('CHANGELOG.md is stale; run history_log.py render-index')


def migrate_root() -> None:
    if LEDGER_DIR.exists() and any(LEDGER_DIR.glob('????-??.md')):
        raise HistoryError('history shards already exist; refusing a second migration')
    original = INDEX_PATH.read_text(encoding='utf-8')
    grouped = parse_legacy_root(original)
    for month, entries in grouped.items():
        atomic_write(shard_path(month), render_shard(month, legacy_entries=entries))
    recovered: list[str] = []
    for month in sorted(grouped, reverse=True):
        text = shard_path(month).read_text(encoding='utf-8')
        legacy = text.split(LEGACY_START, 1)[1].split(LEGACY_END, 1)[0].strip('\n')
        recovered.append(legacy)
    original_entries = original[original.index('## '):].strip('\n')
    if '\n\n'.join(recovered) != original_entries:
        raise HistoryError('migration verification failed; root changelog was not replaced')
    atomic_write(INDEX_PATH, render_index())
    check()
    print(f'migrated {sum(len(ENTRY_PATTERN.findall(value)) for value in grouped.values())} entries into {len(grouped)} verified shards')


def slugify_title(title: str) -> str:
    value = re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-')
    return value[:60] or 'change'


def write_structured_entry(title: str, impact: str, summaries: list[str]) -> Path:
    title = title.strip()
    summaries = [summary.strip() for summary in summaries]
    if not title or '\n' in title:
        raise HistoryError('title must be one non-empty line')
    if not IMPACT_PATTERN.fullmatch(f'Plan impact: `{impact}`.'):
        raise HistoryError(f'invalid plan impact: {impact!r}')
    if not summaries or any(not summary or '\n' in summary for summary in summaries):
        raise HistoryError('every summary must be one non-empty line')
    timestamp = datetime.now().astimezone()
    day = timestamp.date().isoformat()
    month = day[:7]
    filename = f'{timestamp.strftime("%Y%m%dT%H%M%S%f%z")}-{slugify_title(title)}.md'
    path = MANAGED_DIR / month / filename
    if path.exists():
        raise HistoryError(f'structured history entry already exists: {path}')
    bullets = '\n'.join(f'- {summary}' for summary in summaries)
    rendered = (
        f'# {title}\n\n'
        f'Date: `{day}`.\n'
        f'Plan impact: `{impact}`.\n\n'
        f'{bullets}\n'
    )
    if len(rendered.encode('utf-8')) > 8 * 1024:
        raise HistoryError('structured history entry exceeds 8 KiB')
    atomic_write(path, rendered)
    atomic_write(INDEX_PATH, render_index())
    return path


def validate_plan_impact(impact: str) -> None:
    if impact == 'none':
        return
    action, slug = impact.split(':', 1)
    plan = ROOT / 'docs' / 'plans' / f'{slug}.md'
    if action == 'updates' and not plan.is_file():
        raise HistoryError(f'updated plan does not exist: {plan.relative_to(ROOT)}')
    if action == 'completes' and plan.exists():
        raise HistoryError(f'completed plan remains active: {plan.relative_to(ROOT)}')


def add_entry(args: argparse.Namespace) -> None:
    if '\n' in args.title or not args.title.strip():
        raise HistoryError('title must be one non-empty line')
    summaries = [summary.strip() for summary in args.summary if summary.strip()]
    if not summaries:
        raise HistoryError('at least one non-empty summary is required')
    if any('\n' in summary for summary in summaries):
        raise HistoryError('each summary must be one line')
    validate_plan_impact(args.plan_impact)
    path = write_structured_entry(args.title, args.plan_impact, summaries)
    check()
    print(f'added chronological entry to {path.relative_to(ROOT)}')


def self_test() -> None:
    legacy = '# Changelog\n\n## 2026-07-20 (new)\n\n- one\n\n## 2026-05-20\n\n- two\n'
    grouped = parse_legacy_root(legacy)
    assert set(grouped) == {'2026-07', '2026-05'}
    with TemporaryDirectory(prefix='agent-memory-history-') as temporary:
        root = Path(temporary)
        for month, entries in grouped.items():
            path = shard_path(month, root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_shard(month, legacy_entries=entries), encoding='utf-8')
        entry = root / 'docs' / 'repo_history' / 'changelog' / 'entries' / '2026-07' / 'fixture.md'
        entry.parent.mkdir(parents=True)
        entry.write_text(
            '# Test entry\n\nDate: `2026-07-20`.\nPlan impact: `none`.\n\n- passed\n',
            encoding='utf-8',
        )
        (root / 'CHANGELOG.md').write_text(render_index(root), encoding='utf-8')
        check(root)
    print('history-log self-test passed')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('migrate-root')
    sub.add_parser('render-index')
    sub.add_parser('check')
    sub.add_parser('self-test')
    add = sub.add_parser('add')
    add.add_argument('--title', required=True)
    add.add_argument('--plan-impact', required=True)
    add.add_argument('--summary', action='append', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'migrate-root':
            migrate_root()
        elif args.command == 'render-index':
            atomic_write(INDEX_PATH, render_index())
        elif args.command == 'check':
            check()
            print('history-log check passed')
        elif args.command == 'self-test':
            self_test()
        else:
            add_entry(args)
    except (OSError, HistoryError) as error:
        print(f'history log failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
