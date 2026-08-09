# Plans

Plans are durable implementation plans for work that is not yet complete enough
to be a runbook or a current memory fact.

Use these files for multi-phase design and migration work that future agents may
need to resume. Active in-progress state belongs in Git-local task state,
deliberate cross-agent/machine transfers belong in `docs/resume/`, durable rules
belong in `docs/memory/`, and completed history belongs in structured entries
under `docs/repo_history/`.

## Status Values

Use the shared status values from `docs/runbooks/task-memory-triage.md`:

- `Incomplete`
- `Wait Not Yet`
- `Blocked`
- `Skipped`

## Current Plans

- None yet. Add one file per deferred plan and list it here.

Every plan must declare exactly one `Status:`, `Next action:`, and `Exit
condition:`. Checked items, shipped/deployed evidence, commit hashes, CI run
IDs, and current-state baselines are rejected. Finish a plan with
`python3 tools/plan_lifecycle.py complete` so the dashboard entry, historical
archive, and structured completion record change together.

Minimal plan shape:

```markdown
# Bounded future plan

Status: `Incomplete`.

Next action: Implement the first bounded slice.
Exit condition: The documented acceptance gate passes.

## Remaining Work

- Implement the first bounded slice.
```

## Retired Records

Retired plans and completed rollout records belong under `docs/repo_history/`.
They are historical context only unless current memory or a current plan
explicitly promotes a rule back into active work.
