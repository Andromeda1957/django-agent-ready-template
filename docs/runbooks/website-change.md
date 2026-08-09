# Website Change Runbook

Use for changes that affect the running site, Django code, templates, static
assets, migrations, production behavior, or user-facing content.

## Steps

1. Inspect `python3 tools/task_state.py list` and any matching resume packet.
2. Read relevant topic memory from `docs/memory/`.
3. Inspect the actual code/config before deciding implementation.
4. Before editing files, use `docs/runbooks/task-memory-triage.md`; if durable
   tracking is warranted, create or update the smallest relevant memory plan
   first.
5. Perform the `docs/runbooks/security-implementation.md` applicability check. If
   any trust boundary is touched, follow that runbook through implementation,
   tests, and closeout.
6. Make scoped changes.
7. Run required gates (activate your venv first):
   - `ruff check .`
   - `lint-imports`
   - `python3 tools/check_security_patterns.py`
   - `python3 manage.py test web`
   - `npm run typecheck`
8. Run targeted checks for the touched feature, including security negative tests
   required by `docs/runbooks/security-implementation.md`.
9. If TypeScript under `static/web/ts/` changed, run `npm run build:js` and commit
   the generated `static/web/js/*.js` assets.
10. If UI/layout changed, follow `docs/runbooks/ui-verification.md`.
11. Add one structured completion entry with `tools/history_log.py add`.
12. Update topic memory only for durable setup/rule/gotcha changes.
13. Update or finish matching Git-local task state.
14. Commit the completed change locally.
15. Push your default branch to your GitHub remote and wait for CI to pass on the
    exact commit.
16. Deploy through the GitHub Actions `Deploy` workflow unless the owner explicitly
    said not to deploy.
17. Live-verify the affected page/behavior.

## Notes

- Do not report completion from code inspection alone.
- If deploy is skipped by user request, say clearly what remains undeployed.
- Use local `./deploy.sh` only when the user explicitly requests it, GitHub
  Actions is unavailable, or emergency recovery requires it.
- When adding a Django app, register it in `INSTALLED_APPS`, add it to the scan
  roots in `tools/check_security_patterns.py`, and update the `deploy.sh`
  allowlist.
