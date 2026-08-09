# Frontend, Templates & UI

How the frontend is structured and verified.

## Current Setup

- Server-rendered Django templates under `<app>/templates/<app>/`.
- Client behavior is written in TypeScript under `static/web/ts/`, compiled to
  `static/web/js/` (see `docs/memory/typescript.md`).
- Static assets are served from `static/` in development and `STATIC_ROOT` in
  production.

## Current Rules

- New client behavior belongs in TypeScript modules, not inline `<script>`
  blocks (a tiny bridge to existing inline code is the only exception).
- Templates rely on Django auto-escaping; never disable it for untrusted data.
- Verify UI/layout changes by actually loading the page, per the UI runbook —
  do not report a visual change done from code inspection alone.

## Runbooks

- UI/layout verification: `docs/runbooks/ui-verification.md`.
- Website/runtime changes: `docs/runbooks/website-change.md`.

## Lookup Anchors

- Templates: `web/templates/web/`. TS source: `static/web/ts/`. Compiled JS:
  `static/web/js/`. Example page: `web/templates/web/home.html`.
