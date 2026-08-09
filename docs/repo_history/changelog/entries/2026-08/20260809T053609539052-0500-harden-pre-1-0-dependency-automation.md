# Harden pre-1.0 dependency automation

Date: `2026-08-09`.
Plan impact: `none`.

- Restricted automatic Dependabot merges for 0.x packages to patch or prerelease movement within the same minor line.
- Added regression coverage for safe 0.58 prerelease updates and rejected 0.58-to-0.64 transitions.
