# Dependency Maintenance Runbook

Dependabot checks pinned Python, Node, and GitHub Actions inputs weekly. The
separate `Dependency Maintenance` workflow drains safe updates without making
ordinary branches responsible for an unrelated dependency backlog.

`constraints.txt` is generated resolver output and is excluded from independent
Dependabot discovery. Python pull requests update direct requirement files; a
maintainer regenerates constraints from all three requirement inputs before
merging when dependency resolution changes.

## Automated Gate

The workflow runs every Tuesday, can be dispatched manually, and continues
after successful CI runs until the safe queue is empty. It processes one pull
request at a time and verifies:

1. The author is the verified Dependabot App and the base is `main`.
2. The title is a non-major numeric version transition. For pre-1.0 packages,
   only changes inside the same `0.x` minor line are automatic.
3. Every changed path is a dependency manifest, lockfile, or Actions workflow.
4. The branch includes current `main`.
5. `Quality gates` passed for that exact head commit.
6. The pull request is unchanged, current, and mergeable immediately before the
   squash merge.

Major, opaque-version, conflicting, expanded-file, or failing updates remain
open for review. The automation never force-merges, weakens CI, or accepts an
old green run as evidence for a new head.

## Completion

A maintenance pass is complete only when a fresh query returns zero open
Dependabot pull requests:

```bash
gh pr list --state open --author app/dependabot
```

For manual updates, review release notes and migration impact, refresh against
current `main`, require exact-head CI, merge normally, and verify the resulting
exact-`main` CI run.
