# Deployment And Rollback Runbook

Use after completed runtime work. Replace example repository and host values
during `install`; keep exact production facts in `docs/memory/production.md`.

## Default GitHub Deployment

1. Run the website-change gates and commit the complete runtime change.
2. Push the default branch and require successful CI for the exact commit:

   ```bash
   gh run list --workflow ci.yml --commit "$(git rev-parse HEAD)" --json conclusion,headSha,url
   ```

3. Trigger the manual production workflow:

   ```bash
   gh workflow run deploy.yml --ref main -f confirm=deploy
   ```

4. Watch that exact workflow run to completion.
5. Live-verify the changed URL or behavior. A green deploy job is not live
   verification.

The workflow transfers the release over SSH. Ansible, when enabled by a project,
also connects over SSH from the runner; it does not require a receiving daemon
on the server.

## Local Incident Fallback

Use local `./deploy.sh` only when the owner requests it, GitHub Actions is
unavailable, or an urgent incident requires immediate repair. The urgent
agent-control override remains bounded to the declared repair scope. Push the
resulting commit, require CI, and reconcile history/task state after service is
restored.

## Recovery And Rollback

- Provision independent database and media backups before the first production
  deploy; application source in Git is not a data backup.
- Keep the newest verified backup, restore command, and recovery owner in
  `docs/memory/production.md` once configured.
- Before a destructive recovery, identify the exact target and obtain current
  owner confirmation.
- After rollback or restore, verify migrations, service status, static assets,
  and the public health endpoint before reporting recovery complete.

## Completion

Deployment is complete only when exact-commit CI, the deploy workflow, direct
live verification, required backup checks, structured history, and task-state
closeout all succeed.
