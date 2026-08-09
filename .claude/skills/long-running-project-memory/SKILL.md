---
name: long-running-project-memory
description: >-
  Design, audit, or repair a repo-backed memory system for long-lived agent
  continuity. Use when the user asks about agent instructions, runbooks,
  task state, resume packets, topic memory, plans, structured history,
  cross-session continuity, stale facts, or memory-system enforcement.
---

# Long-running project memory

Use this skill to keep a project's memory system durable, small, and usable by
any agent (Claude, Codex, or otherwise) across many sessions. The goal is
repo-backed continuity, not hidden model memory or chat-only notes.

## Core model

Keep these layers separate. No single file should carry more than one:

1. Agent contract: small, stable behavior rules.
2. Runbooks: repeatable task workflows and completion checklists.
3. Transient coordination: current task/process state in the project's native
   untracked or external mechanism.
4. Explicit resume/transfer: bounded packets created only when unfinished work
   is deliberately paused or handed over.
5. Topic memory: current durable facts by domain.
6. Plans: deferred or multi-phase implementation plans.
7. History: append-only chronology, completed plans, and archived context.

## Source hierarchy

Use the repo-backed hierarchy:

- `AGENTS.md` for the canonical agent contract.
- `CLAUDE.md` as an exact byte-for-byte mirror of `AGENTS.md` (for Claude Code).
- `docs/runbooks/` for required workflows.
- `python3 tools/task_state.py list` for transient live state.
- `docs/resume/` for deliberate unfinished-work transfers only.
- `PROJECT_MEMORY.md` as the memory router and topic index.
- `docs/memory/` for current durable facts.
- `docs/plans/` for deferred implementation plans.
- Code, config, and command output for implementation truth.
- `CHANGELOG.md` as the generated history index.
- `docs/repo_history/` for structured completion entries, retired plans, old
  memory snapshots, and archived context.

Fresh command output beats stored memory for live facts. Current topic memory
beats historical context. External notes and agent memories are leads, not
authority.

## Workflow

1. Follow the startup contract in `AGENTS.md`.
2. Read `PROJECT_MEMORY.md` only as an index, then read the relevant topic
   memory and runbook files.
3. For memory reviews, use `docs/runbooks/memory-review.md`; if the automated
   check and fixed rubric pass, report the system healthy instead of proposing
   speculative redesigns.
4. For actual memory changes, use `docs/runbooks/memory-maintenance.md` and
   `docs/runbooks/docs-change.md`.
5. Before edits or long-running work, apply
   `docs/runbooks/task-memory-triage.md` and create tracking memory only when
   the triage warrants it.
6. Identify whether the change belongs to behavior, workflow, task state,
   transfer state, durable fact, plan, or history before editing.
7. Edit the smallest appropriate repo-backed file.
8. Preserve useful old context as historical context instead of deleting it.
9. Verify with `git diff --check` and `python3 tools/check_memory_system.py`.
10. Use `tools/project_knowledge.py` when available for topic transactions,
    semantic audits, source-prose references, skill drift, and domain coverage.
11. Record completed maintenance with `tools/history_log.py add`, then commit.

## Placement rules

- Put behavior and source-of-truth rules in `AGENTS.md`, then mirror exactly to
  `CLAUDE.md`.
- Put reusable task steps in `docs/runbooks/*.md`.
- Put live state in the project's native transient task records and create
  `docs/resume/` packets only for deliberate pause or transfer.
- Put durable current facts, setup, decisions, and gotchas in
  `docs/memory/<topic>.md`.
- Put deferred implementation plans in `docs/plans/*.md`.
- Put completed-work audit entries in structured history; generate
  `CHANGELOG.md` as the index.
- Put retired plans, old memory snapshots, and large archived context in
  `docs/repo_history/`.
- Retire static handoff files when native task state exists; preserve useful
  old content in history and keep resume packets transfer-only.
- Do not expand `AGENTS.md` or `CLAUDE.md` for ordinary topic-memory changes.

## Good outputs

- A small agent contract.
- Small transient task state and bounded transfer packets.
- A topic index instead of an encyclopedia.
- Domain-specific current-only memory files.
- A structured completion ledger and preserved historical archive.
- Workflow runbooks with direct completion gates.
- Lightweight validation that catches memory-system drift.
