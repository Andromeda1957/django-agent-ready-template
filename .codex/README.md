# Codex adapter

Trust the repository, review the hook commands and hashes, then enable project
hooks. The adapter sends lifecycle events to `tools/agent_control.py` and sends
shell calls through the syntax-aware live-wait gate.

Routine work is intentionally nonblocking. Protected paths or commands use the
checkpoint, envelope, and manifest flow documented in the repository README.
