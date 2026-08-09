---
name: install
description: >-
  Configure a fresh django-agent-ready-template clone: create the local
  environment, connect its GitHub repository and CI/CD, optionally configure a
  production target, personalize project memory, and validate the installation.
  Use immediately after cloning or to repair a partial install. Idempotent.
---

# Install django-agent-ready-template With Codex

Use `$install` to turn a fresh clone into a working project. Detect settled state and fill only
the missing pieces. Collect configuration once, then continue without repeated
confirmation pauses unless a command fails or the owner requested review.

## 0. Preflight And Scope

1. Run `git status --short`, `python3 tools/task_state.py list`, and confirm the
   current repository is a template clone.
2. Confirm Python 3.12+, Node 22+, and authenticated `gh`.
3. Inspect the current remote, `.env`, `.venv`, `node_modules`, and existing
   GitHub Actions variables/secrets so a rerun does not repeat work.
4. Start a scoped `install-template` task-state record when one does not already
   cover this installation. Never put `.env`, credentials, virtualenv content,
   or `node_modules` in Git.

## 1. Collect Configuration

Ask only for values not already discoverable:

- GitHub `owner/repository` and visibility.
- Project/app name; keep `webapp` when the owner does not want to rename it.
- Optional production configuration: SSH host, runtime user, remote directory,
  and public domain. Deployment may be deferred without blocking local setup.

Risk-bearing features such as accounts, 2FA, and APIs remain opt-in. TypeScript,
strict checks, memory, and agent controls remain defaults unless the owner asks
to remove them.

## 2. Local Environment

1. Create `.venv`, upgrade pip, and install `requirements.txt` plus
   `requirements-dev.txt`.
2. Run `npm install`.
3. Create `.env` from `.env.example` only when absent. Generate a real local
   secret, set `DEBUG=True`, and never print or commit the completed file.
4. Enable repository hooks with `git config core.hooksPath hooks`.
5. Run migrations and `npm run build:js`.
6. Run `python3 tools/agent_control.py doctor` and review the repo-owned Codex
   hook configuration before trusting the project.

## 3. App Naming

When the app name changes from `webapp`, rename the service, timer, and Nginx
template files and update all references together:

- `webapp.service`
- `webapp-health-monitor.service`
- `webapp-health-monitor.timer`
- `webapp_nginx`

Keep `deploy.sh`, GitHub workflows, topic memory, and production runbooks
consistent with the selected name.

## 4. GitHub And Deployment Configuration

1. Create or connect the GitHub repository, then push `main`.
2. Confirm CI runs for the exact pushed commit.
3. When production values were supplied, set Actions variables `APP_NAME`,
   `REMOTE_HOST`, `REMOTE_USER`, `REMOTE_DIR`, and `APP_DOMAIN`.
4. Set `PROD_SSH_PRIVATE_KEY` and `PROD_SSH_KNOWN_HOSTS` as secrets using
   file/stdin input. Never place private key material in a command argument,
   transcript, or repository file.
5. Keep production deployment manual until the first successful deploy and
   live verification establish the project-specific path.
6. Provision the server-side shared environment at
   `<REMOTE_DIR>-shared/.env`, owned by the runtime user with mode `0600` or
   `0640`. Enable `ENABLE_HOST_MAINTENANCE=true` only after its first manual
   maintenance run succeeds.

## 5. Personalize Durable Knowledge

1. Replace generic placeholders in `docs/memory/production.md` and
   `docs/memory/deployment.md` with verified project facts. Mark volatile host
   facts with a verification date and recheck command.
2. Add only project topics that already have real owners and anchors. Prefer
   `tools/project_knowledge.py create-topic` so the registry, router, and topic
   file change together.
3. Remove the template-only `Operating Modes` section from `AGENTS.md` and
   retire `docs/MAINTAINING.md`; this is the normal, Git-recoverable installer
   lifecycle transition. Mirror `AGENTS.md` to `CLAUDE.md` afterward.

## 6. Validate And Record

Run the complete fresh-clone gate:

```bash
.venv/bin/ruff check .
.venv/bin/lint-imports
.venv/bin/python tools/check_security_patterns.py
.venv/bin/python tools/check_memory_system.py
.venv/bin/python tools/project_knowledge.py check
.venv/bin/python tools/agent_control.py doctor
.venv/bin/python -m unittest tools.test_agent_control tools.test_dependabot_maintenance tools.test_project_knowledge
.venv/bin/python manage.py test web
npm run typecheck
npm run build:js
git diff --exit-code -- static/web/js
python3 tools/sync_agents.py --check
```

Add one structured completion entry with `python3 tools/history_log.py add`.
Commit the installation, push it, and wait for CI on the exact commit. If the
owner asked for the first deploy, run the deploy workflow and live-verify before
finishing task state. Report configured and deliberately deferred items clearly.

## Opt-In And Opt-Out Recipes

The README owns the TypeScript opt-out and secure accounts, 2FA, and REST API
recipes. Follow `docs/runbooks/security-implementation.md` when enabling any
trust boundary.
