# Repository History

Use this directory for archived context that is useful to preserve but must not
load as current project state.

Good fits:

- structured one-file-per-completion entries under `changelog/entries/`;
- completed plans moved by `tools/plan_lifecycle.py`;
- retired implementation plans;
- old memory snapshots before a cleanup or source-of-truth split;
- large historical notes that would bloat `CHANGELOG.md` or topic memory;
- migration background that future agents may need for audit, not startup.

Rules:

- Do not read this directory at startup by default.
- Do not let files here override Git-local task state, explicit resume packets,
  `docs/memory/`, code/config, or fresh command output.
- Link here from current memory only when a specific historical record is useful
  for an audit or future investigation.
- Promote any still-operative rule, setup fact, or gotcha back into
  `docs/memory/`, `docs/runbooks/`, or `AGENTS.md` as appropriate.

This is a preservation layer, not a second memory router.
