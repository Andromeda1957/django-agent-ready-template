# Memory System Pattern

Use this reference when implementing or reviewing a memory system for a
long-running project.

## Recommended Layout

```text
AGENTS.md
assistant adapters or exact mirrors, as the project defines
PROJECT_MEMORY.md
CHANGELOG.md
docs/runbooks/
docs/memory/
docs/plans/
docs/resume/ (only for deliberate pause or transfer)
project-native transient task state
docs/history/ (or the project-defined equivalent)
```

## File Responsibilities

### Agent Contract

Use for behavior that applies to every task:

- startup protocol;
- task classification;
- source-of-truth hierarchy;
- memory discipline;
- universal safety rules;
- links to runbooks.

Keep it small. Do not store domain setup details or history here.

### Assistant Adapters

Follow the project's declared adapter rule. Some projects use a small
assistant-specific overlay; others require an exact mirror of the canonical
contract. Never let an adapter become a second source of behavior or project
facts.

### Transient Task State

Prefer the project's native Git-local, external, or otherwise untracked
coordination mechanism. Keep only:

- active objective;
- last known state and timestamp;
- exact next action;
- blockers;
- immediate "do not do this now" facts;
- dirty-worktree caveats.

Avoid completed history, broad rules, old verification logs, and changelog
summaries. Do not introduce a static handoff file when the project already has
an authoritative task-state mechanism.

### Explicit Resume Or Transfer

Create a bounded tracked packet only when unfinished work is deliberately
paused or transferred. It records the exact next action and preservation
boundary; it is not routine startup context, live coordination, or a second
changelog.

### Project Memory Router

Use as an index. Include topic links and global current facts only. Do not let it
become the encyclopedia.

### Topic Memory

Use one file per domain. Suggested sections:

```markdown
# Topic

## Current Setup
Facts true now.

## Current Rules
Rules agents must follow now.

## Runbooks
Relevant workflow files.

## Lookup Anchors
Code paths, commands, models, templates, logs.

```

Topic memory contains current facts only. Move retired or superseded context to
the historical archive instead of keeping a mixed current/history section.

### Plans

Use for deferred or multi-phase implementation work that is not transient task
state and not general enough for a runbook. Plans should use explicit status
values, name a next action and exit condition, and avoid completed history.

### Runbooks

Use for recurring workflows:

- website/runtime changes;
- docs/repo-maintenance changes;
- deployment and disaster recovery;
- UI verification;
- production operations;
- data-worker jobs;
- memory maintenance.

Runbooks should be checklists. They preserve global steps that agents must not
forget.

### Changelog

Use as append-only history. Do not require default startup reads. Read it only
for history, audit, or when current memory points to a specific entry.

## Conflict Resolution

For live facts:

1. Fresh command output.
2. Native transient task state or an explicit resume packet.
3. Topic memory current sections.
4. Code/config.
5. Project memory router.
6. Plans, when the request or current memory routes to a specific plan.
7. Changelog/history.

For required behavior:

1. Agent contract.
2. Relevant runbooks.
3. Enforcing scripts/hooks/tests.
4. Topic memory rules.

## Enforcement Ideas

Add a small check script when the project is stable enough. It can fail if:

- required memory/runbook files are missing;
- transient state leaks into tracked startup files;
- resume packets become routine, unbounded, or historical;
- topic memory files lack required sections;
- project-local skills or memory routers omit the plans layer;
- project memory stops being a router;
- startup rules begin requiring broad changelog reads again.

For larger projects, add a dependency-free semantic knowledge tool that can
maintain a topic ownership registry, perform transactional fact placement, and
audit all tracked Markdown, source comments/docstrings, skill references, and
unexplained domains. Keep this tool independent of prompt hooks, tool-call
authorization, deployment policy, and other agent-runtime control.

Wire the checker into a pre-commit hook when available.

## Anti-Patterns

- One giant memory file loaded every session.
- Handoff as a second changelog.
- Recent behavioral corrections dominating normal work.
- Historical facts sitting beside current facts without labels.
- Deferred implementation plans hiding in transient state, topic memory, or
  root TODO files.
- Agent entrypoints duplicated across assistants.
- Memory edits triggered by every conversational correction.
- Recovery docs excluded from routine validation.
