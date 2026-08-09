# Resume Packets

This directory is normally empty. `python3 tools/task_state.py pause` creates a
bounded packet here only when unfinished work must deliberately cross an agent
or machine boundary.

Packets contain future work only: authorized scope, exact next action, blocker,
and verification already run. They are not progress diaries, inventories, or
completed history. Resume with `python3 tools/task_state.py resume <packet>` and
remove the packet in the reviewed closeout commit after its work is complete.
