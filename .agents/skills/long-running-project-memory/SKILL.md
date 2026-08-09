---
name: long-running-project-memory
description: Design, audit, or repair scalable memory systems for long-lived software projects. Use when Codex needs to organize agent instructions, runbooks, transient task state, explicit resume packets, project memory, changelogs, recovery docs, or multi-agent continuity; prevent stale facts from overriding current state; reduce startup context; or add enforcement for project memory discipline.
---

# Long-Running Project Memory

Use this skill to turn a growing project from ad hoc notes into a durable,
low-friction operational memory system.

## Core Model

Separate seven layers:

1. **Agent contract**: small, stable behavior rules.
2. **Runbooks**: repeatable task workflows and completion checklists.
3. **Transient coordination**: current task/process state in the project's
   native untracked or external state mechanism.
4. **Explicit resume/transfer**: bounded packets created only when unfinished
   work is deliberately paused or handed over.
5. **Topic memory**: current durable facts by domain.
6. **Plans**: deferred or multi-phase implementation plans.
7. **History**: append-only chronology and archived/retired notes.

Do not let one file carry all seven layers.

## Workflow

1. Inspect the existing contract, memory files, runbooks, plans, history,
   transient task state, and any explicit resume packets.
2. Identify where current facts, historical facts, behavior rules, and task
   checklists are mixed together.
3. Propose a source-of-truth hierarchy before editing.
4. Preserve old memory as historical context instead of deleting it.
5. Move required workflows into runbooks.
6. Move current durable facts into topic memory files.
7. Move deferred or multi-phase implementation work into plans.
8. Slim agent entrypoints to behavior and lookup rules.
9. Retire static handoff files when native task state exists; keep resume
   packets explicit, bounded, and transfer-only.
10. Add lightweight enforcement when possible.
11. When the project provides semantic knowledge tooling, use it for topic
    ownership, transactional placement, Markdown/source-prose review, skill
    drift, and domain coverage.
12. Verify references, line limits, and check scripts.

For detailed patterns and templates, read
`references/memory-system-pattern.md`.

## Operating Rules

- Current state beats history.
- Fresh command output beats repo memory for live facts.
- Changelog is audit history, not startup context.
- User corrections update working assumptions immediately; memory edits happen
  at end-of-task unless the user asked for memory maintenance or stale memory
  would cause imminent risky action.
- Runbooks preserve global steps so agents do not need huge startup context.
- Topic memory contains current facts only; retired facts belong in history.
- Plans preserve deferred implementation detail without making it active state.

## Good Outputs

- A small agent contract.
- Small transient task state plus an explicit resume packet only when needed.
- A topic index.
- Domain-specific memory files.
- Deferred implementation plans.
- Workflow runbooks.
- A preserved historical archive.
- Optional validation scripts or hooks that keep the system from regressing.
- Optional semantic routing and audit tooling that stays independent of agent
  prompt/tool authorization.
