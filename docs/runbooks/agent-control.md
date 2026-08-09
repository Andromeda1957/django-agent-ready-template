# Agent Control Runbook

Use agent control only when work crosses a protected boundary, must survive a
session, or needs explicit rollback evidence. Routine work does not require a
checkpoint.

## Protected work

1. Capture the owner's exact prompt with `checkpoint create`.
2. Declare the actions, targets, and exclusions with `envelope`.
3. Prepare one exact `manifest` for each protected tool call.
4. Perform the work. The post-tool hook closes the matching manifest.
5. Record corrections as `event --type correction` before preparing a new
   protected manifest. Corrections never prevent ordinary diagnostic or repair
   work outside protected boundaries.
6. Record a terminal event only after verification is complete.

## Live incident

Use `urgent begin` when delay itself harms active users. Give it exact path
patterns and exact protected commands, written as `command:<shell command>`.
The hook permits only that scope and records deferred bookkeeping. Repair and
verify first, then run `urgent close --verification ...`. Before-images and tool
outcomes are captured as the repair runs; close reconciles those records and
the stop gate remains closed until verification is recorded.

Urgent mode is not a blanket bypass. Destructive action still needs explicit
owner authority, and a command or target outside the declared incident scope
is denied.

## Waiting

Keep real commands foreground and observable. The live-wait gate rejects actual
`while`/`until` loops, fixed sleeps, and fixed timeout wrappers. It tokenizes
shell syntax and removes heredoc bodies first, so those words in prose, quoted
text, patches, or generated files are not treated as control flow.

## Recovery

Prepared manifests capture file before-images beneath the repository's Git
common directory. `rollback` restores existing files and moves newly created
files into a task-specific quarantine. Inspect the result and record fresh
verification; rollback evidence does not prove the application is healthy.
