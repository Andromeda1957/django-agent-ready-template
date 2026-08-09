# Runbooks

Required workflows and completion checklists. Pick the relevant runbook for the
task before using tools (see `AGENTS.md` → Start Of Session).

- `task-memory-triage.md` — decide whether durable tracking is needed first.
- `task-state.md` — scope protected, risky, runtime, or multi-session work.
- `website-change.md` — changes to the running site / Django code.
- `docs-change.md` — documentation and repo-maintenance changes.
- `security-implementation.md` — the security gate for runtime/trust-boundary work.
- `ui-verification.md` — verifying rendered UI/layout changes.
- `deploy.md` — exact-commit deployment, rollback, and recovery checks.
- `production-ops.md` — operating the running production site.
- `host-maintenance.md` — scheduled Ubuntu patching and host verification.
- `dependency-maintenance.md` — safely drain verified Dependabot updates.
- `agent-control.md` — checkpoints, protected manifests, urgent repair, waits.
- `memory-maintenance.md` — updating the memory system.
- `memory-review.md` — reviewing/auditing the memory system.
