# Project Memory

This file is the memory router. It is intentionally short. Use it to choose the
right runbook and topic memory file; do not turn it back into a project
encyclopedia.

## Source Layers

- Agent behavior: `AGENTS.md`.
- Required workflows: `docs/runbooks/`.
- Live coordination: `python3 tools/task_state.py list` (Git-local, transient).
- Deliberately transferred unfinished work: `docs/resume/`.
- Current durable facts: `docs/memory/`.
- Deferred implementation plans: `docs/plans/`.
- Historical audit index: `CHANGELOG.md`; structured completion entries and
  archived context: `docs/repo_history/`.

## Topic Index

- Workflow and memory system: `docs/memory/workflow.md`
- Deployment, backup, and local checks: `docs/memory/deployment.md`
- Production infrastructure and operations: `docs/memory/production.md`
- Frontend, templates, and UI verification: `docs/memory/frontend.md`
- TypeScript build and client-code conventions: `docs/memory/typescript.md`
- Security, privacy, and the security gate: `docs/memory/security.md`
- Code organization and architecture boundaries: `docs/memory/architecture.md`

## Lookup Rules

- Run `python3 tools/task_state.py list` for worktree scope, next action, and
  blockers. Read a `docs/resume/` packet only for a matching transferred task.
- Use `python3 tools/project_knowledge.py check` for topic ownership, semantic
  Markdown, source-prose references, skill drift, and domain coverage.
- Read only the topic file(s) relevant to the user's request.
- Read `docs/plans/` only when the request, task state/resume packet, or topic
  memory routes to a specific plan.
- Use search and code/config inspection for implementation truth.
- Use `CHANGELOG.md` only to route history/audit lookup; never edit it directly.
- Use `docs/repo_history/` only for archived context, retired plans, audit, or
  when current memory points to a specific historical entry.

## Global Current Facts

- This is a Django 6 project: app code under `web/`, settings under `config/`,
  templates under `web/templates/web/`, source static assets under
  `static/web/`, and TypeScript under `static/web/ts/` compiled to
  `static/web/js/`.
- Local development uses SQLite with zero setup; production uses PostgreSQL via
  `DATABASE_URL`.
- `DEBUG` defaults to False (secure by default). Production requires `SECRET_KEY`
  and `ALLOWED_HOSTS`.
- Secrets stay out of the repo: use `.env` locally (git-ignored) and real
  environment variables / secret stores in production.
- Current work, if any, is reported by `python3 tools/task_state.py list`;
  cross-machine unfinished work exists only as an explicit `docs/resume/`
  packet.
