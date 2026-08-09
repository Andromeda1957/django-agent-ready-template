# Production Infrastructure & Operations

Facts about the running site. Fill these in for your own deployment during
`/install` and keep them current.

## Current Setup

- Target topology (typical): a VPS / public server running the app under
  Gunicorn behind Nginx, with PostgreSQL as the database. Record your actual
  host role, domains, and service names here.
- Static files are served from `STATIC_ROOT` after `collectstatic`.
- Versioned application releases live beside a shared secret directory;
  `<REMOTE_DIR>` is the active-release symlink.
- The optional weekly host-maintenance workflow applies package updates and
  reboots only when required. Ubuntu release upgrades remain owner-reviewed.

## Current Rules

- Production runs with `DEBUG=False`, a real `SECRET_KEY`, and correct
  `ALLOWED_HOSTS`.
- Run the app as a least-privilege user; keep secrets in environment/secret
  stores, not the repo.
- Do not run heavy/long batch jobs on the web-serving process; use a separate
  worker or scheduled task.
- Keep `<REMOTE_DIR>-shared/.env` owned by the runtime user with mode `0600` or
  `0640`; never place production secrets in a release artifact.

## Runbooks

- Production operations: `docs/runbooks/production-ops.md`.
- Deployment and rollback: `docs/runbooks/deploy.md`.
- Host patching: `docs/runbooks/host-maintenance.md`.

## Lookup Anchors

- Service units: `*.service`. Web server config: `*_nginx`.
- Settings: `config/settings.py`.
