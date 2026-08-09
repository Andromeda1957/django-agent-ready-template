# Task State And Explicit Resume Runbook

Use for protected, risky, runtime, parallel, production, worker, recovery, or
multi-session work. Small unprotected changes on the primary branch do not need
state. Configure a nonstandard primary branch with
`git config memory.primaryBranch <branch>`.

## Start

1. Run `git status --short` and resolve the dirty-worktree decision first.
2. Start one task for the current worktree:

   ```bash
   python3 tools/task_state.py start \
     --task <slug> --owner <owner> \
     --scope 'exact/path/**' --exclude 'explicitly/excluded/**' \
     --state 'current bounded state' --next 'one exact action'
   ```

3. Task state lives under the shared Git common directory at
   `.git/agent-memory/tasks/`. It is visible to linked worktrees, never staged,
   never merged, and never part of project history.
4. Inspect all worktrees with `python3 tools/task_state.py list`; use
   `--current` for only this worktree.

## During Work

- Update state by replacement, not narrative append:

  ```bash
  python3 tools/task_state.py update --state '...' --next '...' --blocker none
  ```

- Ordinary updates cannot change scope. If the owner explicitly authorizes a
  wider scope in the current conversation, record the exact quote before
  editing outside the original authorization:

  ```bash
  python3 tools/task_state.py expand-scope \
    --scope 'new/exact/path/**' \
    --owner-confirmation 'exact owner words authorizing this expansion'
  ```

  Scope expansions append to an audit list; they never silently replace the
  original scope or remove exclusions.
- The staged scope gate blocks protected paths without local task state, all
  staged work on a non-primary branch without state, and paths outside the
  active task's authorization.
- HEAD drift is informational because commits advance during a task; update
  refreshes the recorded HEAD and timestamp.

## Deliberate Pause Or Transfer

Create a tracked resume packet only when unfinished work must cross an agent or
machine boundary:

```bash
python3 tools/task_state.py pause \
  --reason 'why execution stopped' \
  --verification 'what has actually passed'
```

The packet under `docs/resume/` is future work only. It must not contain a
progress diary, completed batches, deployment history, or inventories.

Resume with:

```bash
python3 tools/task_state.py resume docs/resume/<task>.md
```

## Finish

1. Complete the task's normal tests, history entry, plan transition, commit,
   push, CI, deployment, live verification, and backup requirements.
2. If a tracked resume packet exists, remove it in the reviewed closeout commit
   after confirming its unfinished work is complete or moved to a future plan.
   Git preserves the exact packet. `task_state.py finish` never mutates tracked
   files.
3. Ensure the worktree is clean.
4. Run:

   ```bash
   python3 tools/task_state.py finish --verification 'exact verified result'
   ```

The command moves the exact local record and any completed resume packet into
`.git/agent-memory/task-history/`. It never deletes a worktree, branch, project
directory, or durable history.
