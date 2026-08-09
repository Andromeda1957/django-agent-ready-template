#!/usr/bin/env bash
set -eu

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if ! cd "$PROJECT_DIR"; then
  printf 'Startup context hook could not enter project dir: %s\n' "$PROJECT_DIR"
  exit 0
fi

cat <<'EOF'
# Project Startup Context

The following repo-backed files are injected by the project SessionStart hook.
Treat them as current startup context before any tool use.
EOF

for file in AGENTS.md PROJECT_MEMORY.md; do
  printf '\n\n## %s\n\n' "$file"
  if [ -f "$file" ]; then
    cat "$file"
  else
    printf 'Missing required startup file: %s\n' "$file"
  fi
done

printf '\n\n## Git-local task state\n\n'
if [ -f tools/task_state.py ]; then
  python3 tools/task_state.py list || printf '%s\n' 'Task-state lookup failed.'
else
  printf '%s\n' 'Missing required tool: tools/task_state.py'
fi

printf '\n## Explicit resume packets\n\n'
if find docs/resume -maxdepth 1 -type f -name '*.md' ! -name README.md \
  -print -quit 2>/dev/null | grep -q .; then
  find docs/resume -maxdepth 1 -type f -name '*.md' ! -name README.md \
    -print | sort
else
  printf '%s\n' 'No explicit resume packets.'
fi

cat <<'EOF'

## Required First Step

Before any tool use:

1. Classify the user turn.
2. Select and follow the relevant `docs/runbooks/` workflow.
3. Do not report completion from code inspection alone.
EOF
