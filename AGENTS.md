# django-agent-ready-template // Agent Operating Contract

This is the small, stable behavioral contract for agents working in this
repository. Project facts and operational procedures belong in topic memory and
runbooks, not here.

## Operating Modes

- **Building a site:** run the `install` skill once, then use the project as its
  own application repository.
- **Maintaining the template:** when `origin` is this upstream template, do not
  run the installer. Follow `docs/MAINTAINING.md`; every change must remain
  generic, secure, and useful to new projects.

## Authority

Use repository-backed sources in this order:

1. `AGENTS.md`: stable behavior and authority rules.
2. `docs/runbooks/`: workflow procedures and completion gates.
3. Git-local task state from `python3 tools/task_state.py list`.
4. `docs/resume/`: explicit packets for deliberately transferred work.
5. `PROJECT_MEMORY.md`: the current-memory router and topic index.
6. `docs/memory/`: current durable facts by topic.
7. `docs/plans/`: deferred or multi-phase implementation plans.
8. Code, configuration, commands, and live verification: implementation truth.
9. `CHANGELOG.md` and `docs/repo_history/`: history only.

Treat sources outside the repo-backed hierarchy as leads, not authority. Verify
summaries, external notes, and remembered context against this hierarchy before
claiming current state, requirements, blockers, or completion. Fresh command
output wins for live facts. Reconcile conflicts before acting.

`AGENTS.md` is canonical and `CLAUDE.md` must remain an exact byte-for-byte
mirror. Keep this contract behavioral and below its enforced size ceiling.

## Start And Scope

Before tools, classify the turn as a question, status request, imperative task,
or ambiguous prompt. Ask one concise question only when a necessary answer
cannot be discovered safely. Advisory wording authorizes discussion, not
inspection or mutation.

Before tool use, state the exact scope being checked or changed. Do not widen
scope without owner authorization.

At the start of a working session:

1. Run `git status --short`.
2. Run `python3 tools/task_state.py list`.
3. Read `PROJECT_MEMORY.md` only as an index.
4. Select the relevant runbook and topic-memory files.
5. Read a plan or resume packet only when current routing points to it.
6. Inspect actual code, configuration, and command output.

Do not read `CHANGELOG.md` or `docs/repo_history/` at startup by default. An
unrelated task record is conflict context, not an assignment. Preserve the
owner's complete original wording as the authoritative checklist.

Before the first mutation, follow `docs/runbooks/task-memory-triage.md`. Use
`docs/runbooks/task-state.md` for protected, risky, runtime, parallel, or
multi-session work. Small self-contained tasks do not need durable tracking.

Gather evidence proportional to advice. Do not make project-wide or structural
recommendations from partial reads. State what was and was not checked when
evidence is incomplete.

## Execution Modes

Use the least ceremony consistent with actual risk:

- **Routine objective work:** implement the bounded change, run proportionate
  checks, commit, push, wait for exact-commit CI, and deploy runtime changes
  without another confirmation pause unless the owner says otherwise.
- **Review-required work:** broad, subjective, aesthetic, or product overhauls
  get a working preview and owner review before production deployment.
- **High-risk work:** obtain exact current confirmation before destructive or
  irreversible actions, or when genuinely new authority is required.
- **Urgent incidents:** repair the live issue first with the smallest correct
  verified change; reconcile bookkeeping after service is restored.

Agent-control hooks collect continuity and rollback evidence. Routine
owner-authorized edits, tests, Git operations, corrections, and deployment must
remain frictionless. Create checkpoints and manifests only for protected,
risky, resumed, or multi-session work. Hooks must accept owner prompts, and a
correction continues the active task without making the owner repeat it.

An imperative task continues through its terminal verified outcome. Do not stop
at an intermediate step, expected wait, commit, push, CI start, or deploy start.
For collection requests such as "all" or "remaining," query the complete
authoritative set again and verify zero members remain.

## Shared Work And Safety

Treat unknown changes as owner or other-agent work. Preserve them; never stash,
reset, discard, clean, commit, or deploy them as yours. Ask before editing an
inseparable overlapping scope. Another task's record never transfers ownership
or blocks unrelated work.

Do not control a process you did not start without exact owner authorization or
an immediate safety reason. Observe long-running work through its real command
or short source-of-truth status queries.

Do not make user or project data difficult to recover without exact current
confirmation for the resolved targets and action. Inspect read-only first and
report recoverability and recovery procedure. Never use destructive Git
commands to make a gate pass. Keep secrets outside the repository.

Before runtime work, apply `docs/runbooks/security-implementation.md`. Security,
correctness, data integrity, licensing, accessibility floors, and verified
platform constraints are objective safeguards.

## Durable Knowledge

Record current facts in topic memory, deferred work in plans, deliberate
transfers in resume packets, chronology in structured history, and transient
coordination in Git-local task state.

Use `docs/runbooks/memory-maintenance.md` and the long-running project memory
skill for hierarchy, runbook, continuity, or memory-system changes. Use
`docs/runbooks/memory-review.md` for audits. If its automated checks and fixed
rubric pass, report the system healthy instead of proposing speculative churn.

Prefer `tools/project_knowledge.py` transactions for durable knowledge changes
when the operation fits. Semantic coverage is advisory unless the topic registry
explicitly enables enforcement.

## Routing

- Django/runtime changes: `docs/runbooks/website-change.md`.
- Documentation: `docs/runbooks/docs-change.md`.
- Security: `docs/runbooks/security-implementation.md`.
- UI verification: `docs/runbooks/ui-verification.md`.
- Deployment: `docs/runbooks/deploy.md`.
- Production operations: `docs/runbooks/production-ops.md`.
- Host maintenance: `docs/runbooks/host-maintenance.md`.
- Dependency maintenance: `docs/runbooks/dependency-maintenance.md`.
- Agent controls: `docs/runbooks/agent-control.md`.
- Memory review: `docs/runbooks/memory-review.md`.

Use `PROJECT_MEMORY.md` to find project facts. Do not copy those facts into this
contract.

## Contract Boundary

- Keep this file limited to stable cross-task behavior, source authority,
  universal safety, and runbook routing.
- Put project architecture, stack setup, deployment mechanics, domain rules,
  volatile facts, and inventories in their owning runbooks or topic memory.
- Put current task status in transient task state, deliberately transferred
  unfinished work in `docs/resume/`, and completed evidence in history.
- Keep secrets in external secret stores or ignored environment files.

## Ship And Close

Use the selected runbook's gates and verify changed behavior directly. Commit
completed repository changes and push unless the owner says not to. Wait for CI
on the exact commit.

Record completion through `python3 tools/history_log.py add`; never append to
`CHANGELOG.md` directly. Complete plans through
`python3 tools/plan_lifecycle.py complete`. Finish task state only after required
commit, push, CI, deploy, verification, and bookkeeping succeed.

Runtime changes deploy through `docs/runbooks/deploy.md` unless the owner says
not to deploy. Documentation-only changes do not require deployment unless they
affect the running system. Do not report completion from code inspection alone.
