# django-agent-ready-template

A secure-by-default, **AI-agent-ready** Django template. Clone it, run the
`/install` skill with your coding agent, then tell the agent what to build. The
production scaffolding — quality gates, CI/CD, security controls, deploy, and a
repo-backed memory system that keeps agents coherent across sessions — is already
done.

> Risk-bearing features — logins, accounts, APIs — are opt-in, not bundled. The
> default install is minimal, and everything it ships is hardened out of the box.

## Why this exists

Most Django starters give you framework boilerplate. This one gives you the
**operating system for building with AI agents**: an enforced agent contract,
runbooks, durable project memory, and a security/quality gate suite that runs in
pre-commit and CI — so an agent (Claude, Codex, etc.) can do real work on your
project without drifting, leaking secrets, or shipping the obvious OWASP bugs.

Two gradients keep it coherent:

- **Opt-out** for things on by default because they're simply better:
  TypeScript, strict mode, the gates, the memory system.
- **Opt-in** for features that add attack surface: user accounts, 2FA, a REST
  API. Add them via the secure recipes below.

## Quick start

1. **Use this template** (green button on GitHub) or clone it, then `cd` in.
2. Open the repo with your agent and run the installer skill:
   - Claude Code: `/install`
   - Codex: `$install`
3. Answer the few questions it asks (GitHub repo, and — when you're ready —
   your deploy target). It sets up the local env, wires GitHub + CI/CD, and
   validates everything.
4. Tell your agent what you want the site to become.

### Prerequisites

- Python 3.12+, Node 22+, and the GitHub CLI (`gh`) authenticated.
- For deployment: a VPS or public-facing server reachable by SSH. GitHub Actions
  installs pinned Ansible automatically; a local fallback deploy also needs
  `ansible-core` and `gio` on the machine running `deploy.sh`.

### Manual local setup (if you're not using `/install`)

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
npm install
cp .env.example .env            # then set DEBUG=True and a SECRET_KEY
git config core.hooksPath hooks # enable the pre-commit gate
python manage.py migrate
npm run build:js
python manage.py runserver
```

## What's included

- **Quality + security gates** (pre-commit and CI): Gitleaks (secrets), Ruff,
  `import-linter` (architecture boundaries), a project SAST checker
  (`tools/check_security_patterns.py`), Semgrep, `pip-audit`, `npm audit`,
  Django tests, TypeScript typecheck, and a "compiled assets are current" check.
- **Pinned supply chain inputs**: direct Python dependencies are pinned,
  transitive Python dependencies install through `constraints.txt`, npm uses
  `package-lock.json`, and GitHub Actions are pinned to full commit SHAs.
- **Secure-by-default settings**: `DEBUG` off by default; production security
  headers auto-enable; Argon2 password hashing; secrets only from the
  environment.
- **Layered agent memory**: compact contract, runbooks, Git-local task state,
  explicit resume packets, topic ownership, future-only plans, structured
  history, semantic audits, and deterministic shape checks.
- **Cross-agent controls**: exact prompt capture, bounded protected-operation
  manifests, urgent incident mode, rollback evidence, and a syntax-aware wait
  hook that ignores words such as `while` and `until` inside written content.
- **Failure-safe deployment**: a confirmation-gated GitHub Actions workflow
  invokes Ansible over SSH, prepares a versioned release, atomically changes the
  active symlink, health-checks it, and restores the previous release on failure.
- **Scheduled maintenance**: safe non-major Dependabot updates drain one green
  exact-head PR at a time; Ubuntu host patching is opt-in and independently
  gated.
- **TypeScript by default** with a tiny `tsc` build, no bundler.

## Agent tiers

Multiple agents are supported because people have different tools and
preferences. The contract is written once in `AGENTS.md` and mirrored:

| Agent | Tier | File |
|---|---|---|
| Claude Code | full read/write | `CLAUDE.md` (byte mirror of `AGENTS.md`) |
| Codex | full read/write | `AGENTS.md` |
| Gemini / Antigravity | read-only overlay | `GEMINI.md` |

Edit `AGENTS.md`, then run `python3 tools/sync_agents.py` to regenerate the
`CLAUDE.md` mirror (CI verifies they match).

Gemini defaults to read-only because of weaker agentic-coding reliability — it
can review and propose patches, but not modify files. If Gemini is your only
agent, you can promote it (replace `GEMINI.md` with a mirror of `AGENTS.md`), but
treat full install/deploy driven by Gemini as untested; the pre-commit and CI
gates are your safety net regardless of which agent writes the code.

Routine objective fixes may be shipped by an agent after exact-commit CI. Broad
subjective/product work still waits for preview review, and destructive work
still needs exact current confirmation. The `Deploy` workflow remains
manual-dispatch and environment-gated, so its production permissions stay
separate from ordinary CI.

Skills live per agent: `/install` ships for both Claude (`.claude/skills/`) and
Codex (`.agents/skills/`); other skills are intentionally per-agent so you can
use each agent for its strengths.

## Deploying

1. Provision a server and a deploy SSH key.
2. Run `/install` (or set them by hand): GitHub Actions **Variables**
   `APP_NAME`, `REMOTE_HOST`, `REMOTE_USER`, `REMOTE_DIR`, `APP_DOMAIN`, and
   optional `ENABLE_HOST_MAINTENANCE`; set **Secrets**
   `PROD_SSH_PRIVATE_KEY`, `PROD_SSH_KNOWN_HOSTS`.
3. Provision `<REMOTE_DIR>-shared/.env` on the server as the runtime user with
   mode `0600` or `0640`.
4. Push to the default branch and let exact-commit CI pass.
5. Run the **Deploy** workflow (type `deploy` to confirm). It installs Ansible on
   the runner, connects over SSH, activates the versioned release, and verifies
   it. The server does not run an Ansible daemon.

> The template secures the **code path** (gates, secret scanning, hardened
> settings, hardened systemd units). Securing the **infrastructure** — your VPS,
> SSH posture, firewall, TLS — is still your responsibility.

## Opt-out: removing TypeScript

If you want plain JS or no build step:

1. Delete `tsconfig.json`, `tsconfig.build.json`, and the `static/web/ts/`
   sources.
2. Remove the `typecheck` / `build:js` scripts and the `typescript` dev dep from
   `package.json`.
3. Remove the **TypeScript**, **Build JavaScript assets**, and **Generated
   assets are current** steps from `.github/workflows/ci.yml`.
4. Point templates at hand-written JS under `static/web/js/`.

## Opt-in: secure feature recipes

Add these only when you need them. Each keeps the template's security posture —
ask your agent to follow the recipe and the `security-implementation` runbook.

### User accounts

- Add `django.contrib.auth` views/URLs (login, logout, password reset) or a
  small accounts app. Keep registration/login logic in a service, not the view.
- Argon2 is already the default hasher. Keep the password validators.
- Add `accounts` to `INSTALLED_APPS`, `SCAN_ROOTS` in
  `tools/check_security_patterns.py`, and the `deploy.sh` allowlist.
- Add `docs/memory/<accounts>.md` (topic-memory shape) and ownership/IDOR negative
  tests next to the owning views.
- Add a login-endpoint `limit_req_zone` in `webapp_nginx` (the base already
  rate-limits `/admin/login/`; do the same for your own login route).

### Two-factor auth (requires accounts)

- Add `pyotp`, `qrcode`, and `cryptography` to `requirements.txt`, then refresh
  `constraints.txt`.
- Store the TOTP secret encrypted at rest (never plaintext), gate login on the
  second factor, and provide recovery codes.
- Add negative tests: wrong/replayed codes rejected, recovery-code single use.

### REST API

- Add `djangorestframework` to `requirements.txt`, then refresh
  `constraints.txt`.
- Authenticate machine endpoints with bearer tokens (not cookies); only then is
  `csrf_exempt` appropriate. Scope every queryset by token/owner.
- Add token-scope and IDOR negative tests.
- Add `limit_req_zone`s in `webapp_nginx` for the public/export endpoints (abuse
  control), keyed on client IP and returning 429.

## Project structure

```
config/            Django project (settings, urls, wsgi)
web/               Example app: model, services, thin views, templates, tests
static/web/ts/     TypeScript sources -> compiled to static/web/js/
constraints.txt    Resolved Python dependency constraints
tools/             Gates, task state, memory/history, and agent controls
docs/runbooks/     Required workflows
docs/memory/       Durable topic memory
docs/resume/       Explicit bounded transfer packets only
docs/repo_history/ Structured completion and archived context
ops/ansible/       Versioned deploy and host-maintenance playbooks
.claude/ .agents/  Per-agent skills, hooks, settings
deploy.sh          Ansible release client (run by the Deploy workflow)
AGENTS.md          Canonical agent contract (mirrored to CLAUDE.md)
```

## License

MIT — see [LICENSE](LICENSE).
