# Documentation And Repo-Maintenance Runbook

Use for docs-only, memory-system, runbook, task-state, history, or repo
maintenance changes that do not affect the running system.

## Steps

1. Inspect `python3 tools/task_state.py list` and any matching resume packet.
2. Read relevant topic memory/runbooks only.
3. Before editing files, use `docs/runbooks/task-memory-triage.md`; for
   self-contained docs fixes, proceed without tracking-memory churn.
4. Make the scoped docs or repo-maintenance change.
5. Run appropriate verification:
   - `git diff --check`
   - syntax/lint checks for any changed scripts
   - `python3 tools/check_memory_system.py` when touching memory-system files
   - `python3 tools/project_knowledge.py check` for semantic placement and
     reference integrity
6. Add one structured entry with `tools/history_log.py add`.
7. Update or finish Git-local task state when applicable.
8. Commit locally, push, and verify CI when the project workflow requires it.

## No Deploy

Documentation-only and repo-maintenance changes do not require deployment unless
they affect runtime files or the user explicitly requests it.

## No Backup Sync By Default

If your project has a recovery-backup workflow, reserve it for runtime or
deployed-system changes. Docs-only and memory-system changes do not need backup
sync unless the user asks or the change also affects deployed behavior.
