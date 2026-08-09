# Task Memory Triage Runbook

Use before editing files or launching long-running work. The goal is to decide
whether the task needs durable tracking before implementation starts, not to
force memory edits for every small change.

## Decision

Create or update tracking memory before implementation when the task is likely
to be:

- multi-phase or cross-session;
- architecture, migration, toolchain, or workflow work;
- risky runtime work where partial progress matters;
- long-running, billable, deploy, recovery, or production-state work;
- dependent on owner approval or a deferred decision;
- useful for future agents to resume with a status checklist.

Skip tracking-memory edits when the task is:

- a question, status check, or narrow inspection;
- a typo, wording, or tiny one-file fix;
- a self-contained bug fix with immediate verification;
- already covered by Git-local task state or an existing future-work plan.

## Where To Record

- `.git/agent-memory/tasks/`: untracked local live state for risky, parallel,
  production, recovery, or multi-session work. Manage it only through
  `tools/task_state.py`; never copy it into durable memory.
- `docs/resume/<task>.md`: a bounded future-only transfer packet created only
  when unfinished work deliberately crosses an agent or machine boundary.
- `docs/memory/<topic>.md`: durable current setup, rules, gotchas, and
  decisions.
- `docs/runbooks/<workflow>.md`: reusable workflow steps and completion
  checklists.
- `docs/repo_history/`: retired plans, archived context, and large historical
  records that are not current authority.
- `docs/repo_history/changelog/entries/`: one structured completed-history file
  per task, created with `tools/history_log.py add` after work is done.

Do not put completed task history in task state or a resume packet. Do not put
broad workflow rules only in a topic-memory note when a runbook should enforce
them.

At closeout, place memory by state:

- Concise completed-work results and verification summaries go in one
  structured history entry. Detailed logs remain in their source system.
- Durable current setup, rules, gotchas, and recurring operational facts go in
  the relevant `docs/memory/<topic>.md` file.
- Deferred, multi-phase, blocked, or intentionally postponed implementation
  work goes in `docs/plans/<plan>.md` unless it must be resumed immediately.
- Retired plans and historical context that no longer describe current project
  status go in `docs/repo_history/`, with only active rules promoted to topic
  memory.
- Plans contain future work only and must declare exactly one `Status:`, `Next
  action:`, and `Exit condition:`. Completed evidence belongs in history.
- Git-local task state keeps only scoped live state, exact next actions,
  blockers, worktree/branch/HEAD truth, and exclusions.
- Authorized scope is immutable during ordinary updates. Expanding it requires
  an exact owner-confirmation quote recorded by `task_state.py expand-scope`.

## Status Values

When a task needs a status plan, use these exact values. Finished work must
leave `docs/plans/` and move to structured history or archived context.

- `Incomplete`: planned but not started or not finished.
- `Wait Not Yet`: intentionally deferred until a listed prerequisite or owner
  decision is satisfied.
- `Blocked`: cannot proceed because an external dependency or unresolved
  decision prevents useful progress.
- `Skipped`: deliberately abandoned with a short reason.

## Loop

1. Inspect `python3 tools/task_state.py list`, any matching resume packet,
   memory index, runbook, topic memory, and implementation context needed to
   scope the task.
2. Decide whether the task needs durable tracking before editing files or
   launching long-running work.
3. If tracking is warranted, create or update the smallest appropriate memory
   or runbook file first.
4. Implement the scoped task.
5. Verify directly.
6. Deploy and live-verify when the selected runbook requires it.
7. Update current memory, structured history, plans, task state, and commits
   according to the selected runbook.

Do not treat a tracked phase as finished from code inspection alone. It must
meet the documented closeout gate before it leaves `docs/plans/`.
