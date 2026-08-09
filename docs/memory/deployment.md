# Deployment, Backup & Local Checks

How the project is built, checked, and shipped. Configure the specifics for your
own hosting via the `/install` skill.

## Current Setup

- Local quality gates run via the pre-commit hook and can be run by hand: Ruff,
  `import-linter`, `tools/check_security_patterns.py`,
  `tools/check_memory_system.py`, Django tests, TypeScript typecheck, and the
  JS build.
- CI (`.github/workflows/ci.yml`) runs the full gate sequence on push/PR.
- Production deploys default to the GitHub Actions `Deploy` workflow after
  exact-commit CI. `deploy.sh` packages the allowlisted runtime and invokes
  `ops/ansible/deploy.yml` over SSH.
- Releases extract under `<REMOTE_DIR>-releases/<commit>` and activate through
  an atomic `<REMOTE_DIR>` symlink. Failed activation or health verification
  restores the previous symlink when one exists.
- Runtime virtual environments are content-addressed by `requirements.txt` and
  `constraints.txt` under the shared directory, so ordinary code-only releases
  reuse the verified environment instead of reinstalling every package.
- Weekly host updates are opt-in through `.github/workflows/host-maintenance.yml`.
- Python runtime installs use `requirements.txt` plus the checked-in
  `constraints.txt`; `deploy.sh` ships both files to production.
- Runner-only Ansible is pinned separately in `requirements-deploy.txt` and is
  never installed into the application virtual environment.

## Current Rules

- Do not deploy a commit that has not passed CI unless it is an emergency
  recovery the user explicitly authorized.
- Keep the committed compiled JS under `static/web/js/` current; CI fails if it
  drifts from a fresh build.
- Run `collectstatic` as part of deploy; never serve with `DEBUG=True`.
- Refresh `constraints.txt` after changing Python runtime or gate dependencies.
- Ansible runs on the deployment runner and connects by SSH; the server does not
  need an Ansible service or daemon.

## Runbooks

- Deployment and rollback: `docs/runbooks/deploy.md`.
- Production operations: `docs/runbooks/production-ops.md`.

## Lookup Anchors

- Deploy client: `deploy.sh`. Playbooks: `ops/ansible/`. CI and workflows:
  `.github/workflows/`.
- Service units: `*.service`, `*-health-monitor.*`. Web server: `*_nginx`.
