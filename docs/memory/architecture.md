# Architecture & Boundaries

Code organization and the boundary discipline the project enforces.

## Current Setup

- Django project: settings in `config/`, root URLconf `config/urls.py`.
- Application code lives in apps (the starter ships one: `web/`). Each app holds
  `models.py`, `services.py` (business logic), thin `views.py`, `urls.py`,
  `admin.py`, templates under `<app>/templates/<app>/`, and `tests/`.
- `import-linter` contracts in `.importlinter` enforce dependency direction.

## Current Rules

- Keep views thin: parse request, call a service, render. No business logic or
  data mutations in views.
- Business rules and mutations live in the service layer (`<app>/services.py`).
  The service layer must not import the view/form layer (enforced by
  `import-linter`).
- When you add a Django app: register it in `INSTALLED_APPS`, add it to the
  `SCAN_ROOTS` in `tools/check_security_patterns.py`, add it to the deploy
  allowlist in `deploy.sh`, and add an `import-linter` contract if it has a
  service layer.
- Prefer schema/data migrations over parallel control surfaces that avoid the DB.

## Runbooks

- Website/runtime changes: `docs/runbooks/website-change.md`.
- Security gate: `docs/runbooks/security-implementation.md`.

## Lookup Anchors

- Boundary contracts: `.importlinter`. Settings/apps: `config/settings.py`.
- Example app layout: `web/`.
