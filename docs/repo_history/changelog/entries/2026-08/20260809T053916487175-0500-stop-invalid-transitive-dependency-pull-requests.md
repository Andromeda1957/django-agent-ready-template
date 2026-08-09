# Stop invalid transitive dependency pull requests

Date: `2026-08-09`.
Plan impact: `none`.

- Excluded generated constraints.txt from independent Dependabot discovery while retaining direct Python, Node, and Actions update coverage.
- Documented that direct Python upgrades must regenerate the resolver-owned constraints lock before exact-head CI and merge.
