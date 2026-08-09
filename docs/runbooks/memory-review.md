# Memory Review Runbook

Use when the user asks to review, audit, or improve the memory system.

## Goal

Make memory self-limiting. A review should identify objective failures, not
reopen the whole design every session.

## Fixed Review

1. Run `git status --short`.
2. Run `python3 tools/check_memory_system.py`.
3. Run `python3 tools/project_knowledge.py check`.
4. Check only these rubric items:
   - Required memory/runbook files exist.
   - Static handoff files are absent from current surfaces; live task state is
     Git-local and tracked resume packets are bounded, future-only transfers.
   - Task-state worktree, branch, and HEAD metadata derives from live Git.
   - Topic memory contains current sections only, with history in
     `docs/repo_history/`.
   - Topic routing is bidirectional: every topic file is routed and every
     routed target exists.
   - `docs/plans/` contains only resumable deferred, blocked, or postponed work,
     not retired records that belong in `docs/repo_history/`. Every plan is
     indexed and declares exactly one `Status:`, `Next action:`, and `Exit
     condition:`.
   - Risky or parallel work has scoped Git-local state, and the staged-diff
     scope gate is installed in the shared pre-commit path.
   - `CHANGELOG.md` is generated; chronological history uses one structured
     file per completion and declares its plan impact.
   - Agent-facing instructions do not override the repo startup hierarchy.
   - Reported user failures are addressed at the smallest durable layer.
   - Structural recommendations are based on the whole relevant memory system,
     not a partial read or search-only scan.
5. If the automated checks pass and no rubric item fails, say the memory system
   is healthy and do not propose structural revisions.
6. If a rubric item fails, propose or make only the smallest change that fixes
   that failure.

## Anti-Churn Rule

Do not propose structural memory revisions when checks pass. Do not re-propose
accepted tradeoffs from `docs/memory/workflow.md` as new issues unless fresh
evidence shows they are causing failures.

## Completion

For actual memory changes, follow `docs/runbooks/memory-maintenance.md`.
