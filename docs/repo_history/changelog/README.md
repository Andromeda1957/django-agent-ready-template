# Chronological History

Add completion records with `python3 tools/history_log.py add`. New entries are
immutable, capped at 8 KiB, stored one file per completion under
`entries/YYYY-MM/`, and linked from the generated root `CHANGELOG.md`.

Legacy monolithic changelog entries may be migrated into read-only monthly
shards with `python3 tools/history_log.py migrate-root`.
