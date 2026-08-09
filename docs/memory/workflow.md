# Workflow Memory

## Current Setup

- This repo uses a layered, repo-backed memory system:
  `AGENTS.md` / `CLAUDE.md`, `docs/runbooks/`, Git-local task state,
  `docs/resume/`, `PROJECT_MEMORY.md`, `docs/memory/`, `docs/plans/`, a
  generated `CHANGELOG.md`, and `docs/repo_history/`.
- `PROJECT_MEMORY.md` is the router. It should stay short and point agents to
  topic memory, plans, runbooks, and archives instead of becoming an
  encyclopedia.
- `tools/check_memory_system.py` validates the memory-system shape and should
  run before committing memory-system changes.
- `tools/project_knowledge.py` owns topic transactions, the topic registry,
  whole-Markdown review, source-prose references, skill drift, and domain
  coverage.
- Claude-specific startup glue lives under `.claude/`. Codex repo-scoped skills
  live under `.agents/skills/`.

## Current Rules

- Keep current facts separate from history. Current setup/rules live in topic
  memory; retired context and structured completion entries live in
  `docs/repo_history/`; `CHANGELOG.md` is only their generated index.
- Do not read `CHANGELOG.md` or `docs/repo_history/` at startup by default.
- Static handoff files are retired. Live state is Git-local in this scaffold;
  tracked resume packets exist only for deliberate pause or transfer and remain
  bounded and future-only.
- Keep plans future-only and declare exactly one `Status:`, `Next action:`, and
  `Exit condition:` in every plan.
- Keep `AGENTS.md` and `CLAUDE.md` byte-for-byte identical.
- Do not propose structural memory revisions when
  `python3 tools/check_memory_system.py` passes and the fixed review rubric in
  `docs/runbooks/memory-review.md` has no failures.
- Keep domain coverage and transaction receipts advisory during incremental
  adoption; enable their strict modes deliberately when the registry and team
  workflow are ready.

## Accepted Baseline / Known Tradeoffs

- The system intentionally favors explicit repo-backed markdown over hidden
  model memory, automatic capture, embeddings, or external memory daemons.
- The validator checks shape, not semantic truth. Human review and direct
  verification still matter.
- Git-local task state is intentionally disposable and worktree-aware. It is
  not committed or merged.
- A resume packet is exceptional transfer state, not a progress diary.
- The archive layer preserves context without making old facts authoritative.

## Runbooks

- `docs/runbooks/task-memory-triage.md`
- `docs/runbooks/task-state.md`
- `docs/runbooks/docs-change.md`
- `docs/runbooks/memory-maintenance.md`
- `docs/runbooks/memory-review.md`

## Lookup Anchors

- `AGENTS.md`
- `CLAUDE.md`
- `PROJECT_MEMORY.md`
- `tools/task_state.py`
- `tools/check_task_scope.py`
- `tools/plan_lifecycle.py`
- `tools/history_log.py`
- `docs/resume/`
- `tools/check_memory_system.py`
- `tools/project_knowledge.py`
- `tools/test_project_knowledge.py`
- `docs/memory/topics.json`
- `.claude/hooks/session-start-context.sh`
- `.agents/skills/`
