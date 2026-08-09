#!/usr/bin/env python3
"""Drain green, current-base Dependabot version bumps without blind merging."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

DEPENDABOT_LOGIN = 'app/dependabot'
QUALITY_GATE = 'Quality gates'
DEFAULT_BRANCH = os.environ.get('DEPENDENCY_BASE_BRANCH', 'main')
VERSION_BUMP_RE = re.compile(
    r'\bfrom\s+v?(?P<old>[0-9]+)(?:\.[^\s]+)?\s+'
    r'to\s+v?(?P<new>[0-9]+)(?:\.[^\s]+)?\s*$',
    re.IGNORECASE,
)
ALLOWED_FILE_PATTERNS = (
    'requirements*.txt',
    'package.json',
    'package-lock.json',
    '.github/workflows/*.yml',
    '.github/workflows/*.yaml',
)


@dataclass(frozen=True)
class PullRequestDecision:
    automatic: bool
    reason: str


def run_gh(*args: str, json_output: bool = False) -> Any:
    result = subprocess.run(
        ('gh', *args),
        check=True,
        capture_output=True,
        text=True,
    )
    if json_output:
        return json.loads(result.stdout)
    return result.stdout.strip()


def dependency_files_are_bounded(files: list[dict[str, Any]]) -> bool:
    paths = [item.get('path', '') for item in files]
    return bool(paths) and all(
        any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED_FILE_PATTERNS)
        for path in paths
    )


def version_bump_is_non_major(title: str) -> bool:
    match = VERSION_BUMP_RE.search(title)
    return bool(match and match.group('old') == match.group('new'))


def automatic_merge_decision(details: dict[str, Any]) -> PullRequestDecision:
    if details.get('author', {}).get('login') != DEPENDABOT_LOGIN:
        return PullRequestDecision(False, 'author is not Dependabot')
    if details.get('baseRefName') != DEFAULT_BRANCH:
        return PullRequestDecision(False, f'base branch is not {DEFAULT_BRANCH}')
    if not version_bump_is_non_major(details.get('title', '')):
        return PullRequestDecision(False, 'major or unrecognized version transition')
    if not dependency_files_are_bounded(details.get('files', [])):
        return PullRequestDecision(False, 'changed files exceed dependency manifests/workflows')
    return PullRequestDecision(True, 'bounded non-major Dependabot version bump')


def quality_gate_state(checks: list[dict[str, Any]]) -> str:
    matching = [
        check for check in checks
        if (check.get('name') or check.get('context')) == QUALITY_GATE
    ]
    if not matching:
        return 'missing'
    check = matching[-1]
    status = check.get('status', '').upper()
    conclusion = check.get('conclusion', '').upper()
    if status != 'COMPLETED':
        return 'pending'
    return 'success' if conclusion == 'SUCCESS' else 'failure'


def pull_request_details(number: int) -> dict[str, Any]:
    fields = ','.join((
        'author',
        'baseRefName',
        'baseRefOid',
        'createdAt',
        'files',
        'headRefName',
        'headRefOid',
        'mergeable',
        'mergeStateStatus',
        'number',
        'statusCheckRollup',
        'title',
        'url',
    ))
    return run_gh(
        'pr', 'view', str(number), '--json', fields,
        json_output=True,
    )


def open_dependabot_pull_requests() -> list[dict[str, Any]]:
    pull_requests = run_gh(
        'pr', 'list',
        '--state', 'open',
        '--author', 'app/dependabot',
        '--limit', '100',
        '--json', 'number,createdAt',
        json_output=True,
    )
    return sorted(pull_requests, key=lambda item: item['createdAt'])


def default_branch_sha(repository: str) -> str:
    return run_gh(
        'api', f'repos/{repository}/git/ref/heads/{DEFAULT_BRANCH}',
        '--jq', '.object.sha',
    )


def write_summary(lines: list[str]) -> None:
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not summary_path:
        return
    with open(summary_path, 'a', encoding='utf-8') as summary:
        summary.write('\n'.join(lines))
        summary.write('\n')


def dispatch_ci(ref: str) -> None:
    run_gh('workflow', 'run', 'ci.yml', '--ref', ref)


def process_one(repository: str) -> int:
    listed = open_dependabot_pull_requests()
    if not listed:
        message = 'Dependabot queue is empty.'
        print(message)
        write_summary(('## Dependency maintenance', '', message))
        return 0

    eligible: list[dict[str, Any]] = []
    manual: list[tuple[dict[str, Any], str]] = []
    for item in listed:
        details = pull_request_details(item['number'])
        decision = automatic_merge_decision(details)
        if decision.automatic:
            eligible.append(details)
        else:
            manual.append((details, decision.reason))

    if not eligible:
        lines = ['## Dependency maintenance', '', 'Manual Dependabot review required:']
        for details, reason in manual:
            lines.append(f"- [#{details['number']}]({details['url']}): {reason}")
        write_summary(lines)
        print('\n'.join(lines), file=sys.stderr)
        return 1

    details = eligible[0]
    number = details['number']
    current_base = default_branch_sha(repository)
    if details['baseRefOid'] != current_base:
        run_gh(
            'api', '--method', 'PUT',
            f'repos/{repository}/pulls/{number}/update-branch',
            '-f', f"expected_head_sha={details['headRefOid']}",
        )
        dispatch_ci(details['headRefName'])
        message = f"Updated Dependabot PR #{number} to current {DEFAULT_BRANCH} and dispatched exact-head CI."
        print(message)
        write_summary(('## Dependency maintenance', '', message))
        return 0

    gate_state = quality_gate_state(details.get('statusCheckRollup', []))
    if gate_state in {'missing', 'pending'}:
        message = f"Dependabot PR #{number} is current but its exact-head CI is {gate_state}."
        print(message)
        write_summary(('## Dependency maintenance', '', message))
        return 0
    if gate_state != 'success':
        message = f"Dependabot PR #{number} has failing exact-head CI and was not merged."
        print(message, file=sys.stderr)
        write_summary(('## Dependency maintenance', '', message))
        return 1
    if details.get('mergeable') != 'MERGEABLE':
        message = f"Dependabot PR #{number} is not mergeable and requires review."
        print(message, file=sys.stderr)
        write_summary(('## Dependency maintenance', '', message))
        return 1

    refreshed = pull_request_details(number)
    if (
        refreshed['headRefOid'] != details['headRefOid']
        or refreshed['baseRefOid'] != default_branch_sha(repository)
        or quality_gate_state(refreshed.get('statusCheckRollup', [])) != 'success'
    ):
        message = f"Dependabot PR #{number} changed during verification; leaving it unmerged."
        print(message, file=sys.stderr)
        write_summary(('## Dependency maintenance', '', message))
        return 1

    run_gh(
        'pr', 'merge', str(number),
        '--squash',
        '--delete-branch',
        '--match-head-commit', refreshed['headRefOid'],
    )
    dispatch_ci(DEFAULT_BRANCH)
    message = f"Merged current, green Dependabot PR #{number}; dispatched exact-{DEFAULT_BRANCH} CI."
    print(message)
    write_summary(('## Dependency maintenance', '', message))
    return 0


def main() -> int:
    repository = os.environ.get('GITHUB_REPOSITORY')
    if not repository or '/' not in repository:
        print('GITHUB_REPOSITORY must be set to owner/repository.', file=sys.stderr)
        return 2
    return process_one(repository)


if __name__ == '__main__':
    raise SystemExit(main())
