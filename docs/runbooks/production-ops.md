# Production Operations Runbook

Use for operating the running production site: checking health, restarting
services, inspecting logs, and routine maintenance. Fill in your concrete host
details in `docs/memory/production.md`.

## Common Operations

- **Service status / restart:** manage the app service via systemd
  (e.g. `systemctl status <app>`, `systemctl restart <app>`). Service unit names
  are in the repo's `*.service` files.
- **Logs:** read application and web-server logs (e.g. `journalctl -u <app>`,
  Nginx access/error logs) when diagnosing.
- **Migrations:** apply with `python3 manage.py migrate` during deploy; never run
  untested data migrations directly against production.
- **Static files:** run `python3 manage.py collectstatic` on deploy.
- **Health monitor:** the optional health-monitor systemd timer can run periodic
  checks; enable it if desired.

## Rules

- Production runs with `DEBUG=False`, a real `SECRET_KEY`, and correct
  `ALLOWED_HOSTS`.
- Do not run heavy/long batch jobs on the web-serving process.
- Make production changes through the deploy workflow, not by hand-editing files
  on the server, except for genuine emergency recovery.
- Never expose secrets, debug pages, or admin paths publicly.

## Runbooks

- Deployment and rollback: `docs/runbooks/deploy.md`.
- Host package maintenance: `docs/runbooks/host-maintenance.md`.
- Security gate: `docs/runbooks/security-implementation.md`.
