#!/usr/bin/env python3
"""Reject hidden long waits while ignoring prose and heredoc file content."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import Any

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
DURATION = re.compile(r"^(?:\d+(?:\.\d+)?)(?:s|m|h|d)?$")
SEPARATORS = {";", "&&", "||", "|", "&"}
CONTROL_STARTS = {"do", "then", "else", "elif"}


def strip_heredoc_bodies(command: str) -> str:
    """Keep shell command lines but discard every heredoc body."""
    output: list[str] = []
    delimiters: list[tuple[str, bool]] = []
    for line in command.splitlines():
        if delimiters:
            delimiter, strip_tabs = delimiters[0]
            candidate = line.lstrip("\t") if strip_tabs else line
            if candidate == delimiter:
                delimiters.pop(0)
            continue
        output.append(line)
        for match in HEREDOC.finditer(line):
            operator = match.group(0).split(match.group(1) + match.group(2), 1)[0]
            delimiters.append((match.group(2), "<<-" in operator))
    return "\n".join(output)


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(strip_heredoc_bodies(command), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return list(lexer)
    except ValueError:
        return []


def command_starts(tokens: list[str]) -> list[int]:
    starts: list[int] = []
    at_start = True
    for index, token in enumerate(tokens):
        if token in SEPARATORS or token in CONTROL_STARTS:
            at_start = True
            continue
        if at_start:
            starts.append(index)
            at_start = False
    return starts


def blocked_reason(command: str) -> str | None:
    tokens = shell_tokens(command)
    if not tokens:
        return None
    for index in command_starts(tokens):
        token = tokens[index]
        if token in {"while", "until"} and "do" in tokens[index + 1 :]:
            return f"foreground {token} loop hides live progress"
        if token == "sleep" and index + 1 < len(tokens) and DURATION.fullmatch(tokens[index + 1]):
            return "fixed sleep hides live progress"
        if token == "timeout" and index + 2 < len(tokens) and DURATION.fullmatch(tokens[index + 1]):
            return "fixed timeout wrapper hides live progress"
    return None


def deny(reason: str) -> int:
    message = (
        f"[agent-control] {reason}; run the real command in the foreground or poll "
        "the authoritative state with short observable commands"
    )
    if os.environ.get("AGENT_CONTROL_EVENT") == "codex":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }}))
        return 0
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    try:
        payload: Any = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = str(payload.get("tool_name") or "")
    if tool not in {"Bash", "ScheduleWakeup"}:
        return 0
    inputs = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(inputs, dict):
        return 0
    command = str(inputs.get("command") or inputs.get("prompt") or "")
    reason = blocked_reason(command)
    return deny(reason) if reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
