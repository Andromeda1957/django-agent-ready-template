"""Validate the project memory-system shape.

Generic, dependency-free shape check for the long-running-project-memory
layout. Run from anywhere; it resolves the repo root as the parent of this
file's directory (this script lives in <repo>/tools/).

Exit code 0 and "memory-system check passed" mean the structural invariants
hold. Any failure raises SystemExit(1) with a message naming the problem.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import history_log  # noqa: E402
import plan_lifecycle  # noqa: E402
import project_knowledge  # noqa: E402
import task_state  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    'AGENTS.md',
    'CLAUDE.md',
    '.claude/settings.json',
    '.claude/settings.agent-control.json',
    '.claude/hooks/session-start-context.sh',
    '.claude/hooks/live_wait_gate.py',
    '.claude/skills/long-running-project-memory/SKILL.md',
    '.agents/skills/long-running-project-memory/SKILL.md',
    '.agents/skills/long-running-project-memory/agents/openai.yaml',
    '.agents/skills/long-running-project-memory/references/memory-system-pattern.md',
    '.codex/config.toml',
    '.codex/hooks.json',
    '.codex/compact-prompt.md',
    'agent-control.json',
    'PROJECT_MEMORY.md',
    'CHANGELOG.md',
    'docs/resume/README.md',
    'docs/memory/topics.json',
    'docs/memory/workflow.md',
    'docs/plans/README.md',
    'docs/repo_history/README.md',
    'docs/repo_history/changelog/README.md',
    'docs/repo_history/completed-plans/README.md',
    'docs/runbooks/task-memory-triage.md',
    'docs/runbooks/task-state.md',
    'docs/runbooks/agent-control.md',
    'docs/runbooks/dependency-maintenance.md',
    'docs/runbooks/deploy.md',
    'docs/runbooks/host-maintenance.md',
    'docs/runbooks/docs-change.md',
    'docs/runbooks/memory-maintenance.md',
    'docs/runbooks/memory-review.md',
    'hooks/pre-commit',
    'tools/task_state.py',
    'tools/agent_control.py',
    'tools/test_agent_control.py',
    'tools/dependabot_maintenance.py',
    'tools/test_dependabot_maintenance.py',
    'tools/project_knowledge.py',
    'tools/test_project_knowledge.py',
    'tools/check_task_scope.py',
    'tools/plan_lifecycle.py',
    'tools/history_log.py',
]

REQUIRED_TOPIC_SECTIONS = [
    '## Current Setup',
    '## Current Rules',
    '## Runbooks',
    '## Lookup Anchors',
]

FORBIDDEN_TOPIC_HEADINGS = re.compile(
    r'^##\s+(?:Deprecated|Historical|History|Completed|Shipped|Deployed)\b',
    re.IGNORECASE | re.MULTILINE,
)

REQUIRED_MEMORY_REVIEW_PHRASES = [
    'Do not propose structural memory revisions when checks pass',
    'If the automated checks pass and no rubric item fails',
    'whole relevant memory system',
]

STARTUP_HOOK_COMMAND = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/session-start-context.sh'
MAX_AGENT_CONTRACT_LINES = 220
CURRENT_MARKDOWN_ROOTS = (
    '.agents',
    '.claude',
    'docs/memory',
    'docs/plans',
    'docs/resume',
    'docs/runbooks',
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def compact(text: str) -> str:
    return ' '.join(text.split())


def fail(message: str) -> None:
    raise SystemExit(f'memory-system check failed: {message}')


def require_startup_hook() -> None:
    settings_path = ROOT / '.claude' / 'settings.json'
    try:
        settings = json.loads(settings_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        fail(f'.claude/settings.json is invalid JSON: {exc}')

    session_hooks = settings.get('hooks', {}).get('SessionStart', [])
    if not isinstance(session_hooks, list):
        fail('.claude/settings.json SessionStart hooks must be a list')

    has_startup_hook = False
    for entry in session_hooks:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get('hooks', []):
            if not isinstance(hook, dict):
                continue
            if (
                hook.get('type') == 'command'
                and hook.get('command') == STARTUP_HOOK_COMMAND
            ):
                has_startup_hook = True

    if not has_startup_hook:
        fail('.claude/settings.json must register the SessionStart context hook')

    script_path = ROOT / '.claude' / 'hooks' / 'session-start-context.sh'
    if not script_path.stat().st_mode & 0o111:
        fail('.claude/hooks/session-start-context.sh must be executable')

    script = script_path.read_text(encoding='utf-8')
    for required_file in ('AGENTS.md', 'PROJECT_MEMORY.md', 'tools/task_state.py'):
        if required_file not in script:
            fail(f'SessionStart hook must inject {required_file}')
    if 'Before any tool use' not in script:
        fail('SessionStart hook must remind the agent to classify before tool use')


def routed_markdown(text: str, prefix: str) -> set[str]:
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return {
        match.group(1) for match in re.finditer(r'`([^`]+\.md)`', text)
        if match.group(1).startswith(prefix)
    }


def current_markdown_paths() -> list[Path]:
    paths = [ROOT / 'AGENTS.md', ROOT / 'CLAUDE.md', ROOT / 'PROJECT_MEMORY.md']
    for directory in CURRENT_MARKDOWN_ROOTS:
        paths.extend((ROOT / directory).rglob('*.md'))
    return sorted({path for path in paths if path.is_file()})


def require_current_markdown_hygiene() -> None:
    handoff_path = ROOT / 'AGENT_HANDOFF.md'
    if handoff_path.exists():
        fail('static AGENT_HANDOFF.md is retired; preserve useful content in history')

    duplicates: dict[str, list[str]] = {}
    for path in current_markdown_paths():
        relative = str(path.relative_to(ROOT))
        text = path.read_text(encoding='utf-8')
        if 'AGENT_HANDOFF.md' in text:
            fail(f'{relative} still routes the retired static handoff file')
        duplicates.setdefault(text, []).append(relative)

    allowed_mirror = {'AGENTS.md', 'CLAUDE.md'}
    for matching_paths in duplicates.values():
        if len(matching_paths) > 1 and set(matching_paths) != allowed_mirror:
            fail(f'duplicate current Markdown should have one owner: {matching_paths}')


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(f'missing required memory/runbook files: {", ".join(missing)}')

    require_current_markdown_hygiene()

    project_memory = read('PROJECT_MEMORY.md')
    if 'This file is the memory router' not in project_memory:
        fail('PROJECT_MEMORY.md must remain a routing/index file')
    if 'docs/plans/' not in project_memory:
        fail('PROJECT_MEMORY.md must route deferred implementation plans')
    if 'docs/repo_history/' not in project_memory:
        fail('PROJECT_MEMORY.md must route archived repository history')
    if (
        'docs/resume/' not in project_memory
        or 'tools/task_state.py list' not in project_memory
    ):
        fail('PROJECT_MEMORY.md must route task state and explicit resume packets')

    memory_dir = ROOT / 'docs' / 'memory'
    if memory_dir.is_dir():
        for topic_path in memory_dir.glob('*.md'):
            # README and underscore-prefixed templates are not topic files.
            if topic_path.name == 'README.md' or topic_path.name.startswith('_'):
                continue
            text = topic_path.read_text(encoding='utf-8')
            missing_sections = [s for s in REQUIRED_TOPIC_SECTIONS if s not in text]
            if missing_sections:
                fail(
                    f'{topic_path.relative_to(ROOT)} missing sections: '
                    f'{", ".join(missing_sections)}'
                )
            if FORBIDDEN_TOPIC_HEADINGS.search(text):
                fail(f'{topic_path.relative_to(ROOT)} must remain current-only')

    topic_files = {
        str(path.relative_to(ROOT)) for path in memory_dir.glob('*.md')
        if path.name != 'README.md' and not path.name.startswith('_')
    }
    routed_topics = routed_markdown(project_memory, 'docs/memory/')
    if topic_files != routed_topics:
        fail(
            'PROJECT_MEMORY.md topic routing mismatch: '
            f'missing={sorted(topic_files - routed_topics)}, '
            f'stale={sorted(routed_topics - topic_files)}'
        )

    agents = read('AGENTS.md')
    if len(agents.splitlines()) > MAX_AGENT_CONTRACT_LINES:
        fail(
            f'AGENTS.md exceeds the {MAX_AGENT_CONTRACT_LINES}-line behavior-contract ceiling; '
            'move project setup, workflows, and history to their owning layers'
        )
    if (
        '## Contract Boundary' not in agents
        or 'Put project architecture, stack setup, deployment mechanics' not in compact(agents)
    ):
        fail('AGENTS.md must keep project setup and history outside the behavior contract')
    if (
        'Do not read `CHANGELOG.md` or `docs/repo_history/` at startup by default.'
        not in agents
    ):
        fail('AGENTS.md must keep changelog and repo history out of default startup reads')
    if 'docs/repo_history/' not in agents:
        fail('AGENTS.md must include the archived repository history layer')
    if 'docs/runbooks/memory-review.md' not in agents:
        fail('AGENTS.md must route memory reviews to docs/runbooks/memory-review.md')
    if 'Do not make project-wide or structural recommendations from partial reads' not in compact(agents):
        fail('AGENTS.md must require proportional context before broad advice')
    if 'Treat sources outside the repo-backed hierarchy as leads' not in agents:
        fail('AGENTS.md must keep the repo-backed source authority rule')
    for phrase in ('tools/task_state.py list', 'docs/resume/', 'tools/history_log.py add'):
        if phrase not in agents:
            fail(f'AGENTS.md must include current lifecycle anchor {phrase!r}')

    claude = read('CLAUDE.md')
    if claude != agents:
        fail('CLAUDE.md must be an exact byte-for-byte mirror of AGENTS.md')

    require_startup_hook()

    memory_review = read('docs/runbooks/memory-review.md')
    for phrase in REQUIRED_MEMORY_REVIEW_PHRASES:
        if phrase not in memory_review:
            fail(f'memory-review runbook missing anti-churn phrase: {phrase!r}')
    if 'whole relevant memory system' not in memory_review:
        fail('memory-review runbook must require full relevant context for structural advice')
    if 'docs/repo_history/' not in memory_review:
        fail('memory-review runbook must route retired records to docs/repo_history/')

    workflow = read('docs/memory/workflow.md')
    if '## Accepted Baseline / Known Tradeoffs' not in workflow:
        fail('workflow memory must record accepted baseline/tradeoffs')
    if 'docs/plans/' not in workflow:
        fail('workflow memory must include the plans layer')
    if 'docs/repo_history/' not in workflow:
        fail('workflow memory must include the repo-history archive layer')

    local_claude_skill = read('.claude/skills/long-running-project-memory/SKILL.md')
    if 'docs/plans/' not in local_claude_skill:
        fail('Claude long-running memory skill must include docs/plans/')
    if 'docs/repo_history/' not in local_claude_skill:
        fail('Claude long-running memory skill must include docs/repo_history/')

    local_codex_skill = read('.agents/skills/long-running-project-memory/SKILL.md')
    if 'Plans' not in local_codex_skill or 'History' not in local_codex_skill:
        fail('Codex long-running memory skill must include plans and history layers')
    if 'transient task state' not in local_codex_skill.lower():
        fail('Codex long-running memory skill must include transient task state')

    if (ROOT / '.codex' / 'skills').exists():
        fail('Codex repo-scoped skills belong under .agents/skills/, not .codex/skills/')

    plan_index = read('docs/plans/README.md')
    plan_files = set()
    for plan_path in (ROOT / 'docs/plans').glob('*.md'):
        text = plan_path.read_text(encoding='utf-8')
        if 'historical record only' in text.lower():
            fail(
                f'{plan_path.relative_to(ROOT)} is a historical record; '
                'move it to docs/repo_history/'
            )
        if plan_path.name == 'README.md' and '## Completed Records' in text:
            fail('docs/plans/README.md must not keep a Completed Records section')
        if plan_path.name != 'README.md':
            plan_files.add(plan_path.name)
    indexed_plans = {
        Path(path).name for path in routed_markdown(plan_index, '')
        if '/' not in path and path != 'README.md'
    }
    if plan_files != indexed_plans:
        fail(
            'docs/plans/README.md routing mismatch: '
            f'missing={sorted(plan_files - indexed_plans)}, '
            f'stale={sorted(indexed_plans - plan_files)}'
        )

    for packet in sorted((ROOT / 'docs' / 'resume').glob('*.md')):
        if packet.name != 'README.md':
            try:
                task_state.parse_packet(packet)
            except task_state.TaskStateError as exc:
                fail(str(exc))

    for executable in (
        '.claude/hooks/session-start-context.sh',
        '.claude/hooks/live_wait_gate.py',
        'hooks/pre-commit',
        'tools/check_memory_system.py',
        'tools/check_task_scope.py',
        'tools/history_log.py',
        'tools/plan_lifecycle.py',
        'tools/project_knowledge.py',
        'tools/test_project_knowledge.py',
        'tools/task_state.py',
        'tools/agent_control.py',
        'tools/test_agent_control.py',
    ):
        if not (ROOT / executable).stat().st_mode & 0o111:
            fail(f'{executable} must be executable')

    try:
        plan_lifecycle.validate_all()
        history_log.check()
        project_knowledge.check()
    except (
        plan_lifecycle.PlanError,
        history_log.HistoryError,
        project_knowledge.KnowledgeError,
    ) as exc:
        fail(str(exc).replace(f'{ROOT}/', ''))

    print('memory-system check passed')


if __name__ == '__main__':
    main()
