# TypeScript Build & Client Code

TypeScript is the default for client code (opt-out, not opt-in). To remove it
entirely, follow the opt-out section in the README.

## Current Setup

- Source: `static/web/ts/*.ts`. Compiled output: `static/web/js/*.js`
  (committed).
- `tsconfig.json` (typecheck, `noEmit`) and `tsconfig.build.json` (emit to
  `static/web/js`). Strict mode is fully on.
- npm scripts: `npm run typecheck` and `npm run build:js`. Only dependency is
  `typescript`.

## Current Rules

- Write client behavior in `.ts` files; run `npm run build:js` and commit the
  compiled `.js`. CI's "generated assets are current" gate fails on drift.
- Keep `strict` on for new code; loosen per-flag only with a clear reason.

## Runbooks

- Website/runtime changes: `docs/runbooks/website-change.md`.
- UI/layout verification: `docs/runbooks/ui-verification.md`.

## Lookup Anchors

- Config: `tsconfig.json`, `tsconfig.build.json`, `package.json`.
- Source/output: `static/web/ts/`, `static/web/js/`.
