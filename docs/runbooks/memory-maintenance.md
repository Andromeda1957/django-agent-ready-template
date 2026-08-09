# Memory Maintenance Runbook

Use only when the user asks to update memory/docs, when the active task is memory
maintenance, or when stale memory would cause imminent risky action.

## Principles

- Keep `AGENTS.md` small and stable.
- Keep live state Git-local and replace it in place; use tracked resume packets
  only for deliberate transfer.
- Put current durable facts in `docs/memory/<topic>.md`.
- Put required workflow steps in `docs/runbooks/<workflow>.md`.
- Put chronological history in structured entries under
  `docs/repo_history/changelog/`, with `CHANGELOG.md` as a generated index.
- Put retired plans, archived context, and historical records in
  `docs/repo_history/`, never in topic-memory history bins.
- Preserve old context instead of deleting it when it may be useful later.

## Steps

1. Identify whether the change is behavior, workflow, current fact, active
   state, plan, audit history, or archived context.
2. Use `docs/runbooks/task-memory-triage.md` before editing if the maintenance
   task creates or changes a multi-phase plan, recurring workflow, or live task
   state.
3. Use `tools/project_knowledge.py create-topic`, `add`, `update`, or `move`
   when the operation fits; otherwise edit the smallest appropriate file and
   create a `maintenance-receipt` when strict receipts are enabled.
4. Do not update agent entrypoints (`AGENTS.md` / `CLAUDE.md`) for ordinary
   topic-memory changes.
5. For live coordination, follow `docs/runbooks/task-state.md`: one Git-local
   record per worktree, exact path scope, replacement rather than appended
   narrative, and an explicit resume packet only when transferring.
6. If you changed `AGENTS.md`, mirror it to `CLAUDE.md` (`cp AGENTS.md
   CLAUDE.md`).
7. Ensure every `docs/memory/*.md` file is routed from `PROJECT_MEMORY.md` and
   every active `docs/plans/*.md` file is indexed in `docs/plans/README.md`.
8. Mark volatile facts with `Last verified YYYY-MM-DD` plus a recheck command
   or lookup anchor.
9. Run `git diff --check`.
10. Run `python3 tools/project_knowledge.py check`,
    `python3 tools/check_memory_system.py`, and any syntax/lint checks for
    touched scripts.
11. Add one structured history entry, commit, push, and verify CI.

## Live-State Limits

Static handoff files do not belong in the current memory system. Git-local task
state is transient and machine-local. A tracked resume packet is created only
for deliberate pause or transfer, is capped at 8 KiB, and contains only
unfinished scope, exact next action, blocker, and verification already run.
Completed history, inventories, and broad durable rules never belong in either.

## Plans And History

`docs/plans/` is future work only. Every file has exactly one `Status:`, `Next
action:`, and `Exit condition:` and must pass `tools/plan_lifecycle.py check`.
Complete a plan with `python3 tools/plan_lifecycle.py complete` so its exact
content moves to historical storage, leaves the dashboard, and receives a
structured completion record.

The pre-commit hook runs `tools/check_task_scope.py --staged` and
`tools/check_memory_system.py`. It rejects staged paths outside Git-local task
authorization, tracked live-state misuse, plan/history lifecycle violations,
or missing required memory/runbook files.
