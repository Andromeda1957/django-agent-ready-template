# Topic Memory

One file per domain topic (`accounts.md`, `deployment.md`, `frontend.md`, ...).
Each holds **current durable facts** for that topic. History stays under
`docs/repo_history/`.

Copy `_topic-template.md` to start a new topic, then add a line for it in
`PROJECT_MEMORY.md`'s topic index and an ownership record in `topics.json`.
Prefer `python3 tools/project_knowledge.py create-topic` so all three surfaces
and their Git-local transaction receipt change together.

Every topic file must contain these four sections (the validator enforces it):

- `## Current Setup`
- `## Current Rules`
- `## Runbooks`
- `## Lookup Anchors`

`README.md` and any file beginning with `_` are skipped by the validator, so the
template itself is not required to follow the shape.

Keep topic files current-only. Move superseded facts, completed evidence,
cross-topic context, and retired plans to `docs/repo_history/`; leave a targeted
pointer in current memory only when an audit genuinely needs it.

`topics.json` also controls semantic audit policy. Domain coverage starts in
`advisory` mode for incremental adoption; switch it to `strict` only after all
project paths are owned by a topic or an explicit `no_memory` decision.
