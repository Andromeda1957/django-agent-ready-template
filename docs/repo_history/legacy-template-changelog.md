# Legacy Template Changelog

This preserves the pre-structured-history completion summary from the initial
template release. It is historical context only.

## Initial Snapshot

- Renamed the reusable template identity from `django-agent-native` to
  `django-agent-ready-template` across docs, agent instructions, demo metadata,
  and package metadata.
- Pinned runtime Python dependencies, added `constraints.txt`, routed CI and
  deployment through those constraints, and pinned GitHub Actions inputs.
- Added Nginx rate limiting for admin login and baseline request floods, plus
  `server_tokens off`.
- Added template maintainer/build modes and the original installer lifecycle.
- Created the secure-by-default Django 6 starter with Django, TypeScript,
  security gates, CI/CD, and the first-generation agent memory system.
