#!/usr/bin/env python3
"""Portable checkpoint, authorization, urgent-override, and hook control."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "agent-control.json"
TASK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit", "apply_patch"}
READ_TOOLS = {"Read", "Glob", "Grep", "view_image", "update_plan"}


class AgentControlError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(*args: str, root: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root or ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise AgentControlError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def root_for(value: object = None) -> Path:
    cwd = Path(str(value)).resolve() if value else Path.cwd()
    return Path(git("rev-parse", "--show-toplevel", root=cwd)).resolve()


def common_git(root: Path) -> Path:
    raw = Path(git("rev-parse", "--git-common-dir", root=root))
    return (raw if raw.is_absolute() else root / raw).resolve()


def state_root(root: Path) -> Path:
    path = common_git(root) / "agent-control"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentControlError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentControlError(f"{path} must contain an object")
    return value


def config(root: Path) -> dict[str, Any]:
    path = root / "agent-control.json"
    value = read_json(path)
    if value.get("version") != 1:
        raise AgentControlError("agent-control.json must use version 1")
    return value


def path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    return fnmatch.fnmatchcase(path, pattern)


def normalize_target(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(root))
        except ValueError:
            return str(path.resolve())
    return str(Path(value).as_posix()).removeprefix("./")


def task_path(root: Path, task: str) -> Path:
    return state_root(root) / "checkpoints" / f"{task}.json"


def claim_path(root: Path, session: str) -> Path:
    return state_root(root) / "claims" / f"{sha(session.encode())[:24]}.json"


def prompt_path(root: Path, session: str) -> Path:
    return state_root(root) / "prompts" / f"{sha(session.encode())[:24]}.json"


def load_task(root: Path, task: str) -> dict[str, Any]:
    record = read_json(task_path(root, task))
    expected = record.pop("content_hash", None)
    if expected != sha(canonical(record)):
        raise AgentControlError("checkpoint hash does not match")
    record["content_hash"] = expected
    return record


def save_task(root: Path, record: dict[str, Any]) -> None:
    record = dict(record)
    record.pop("content_hash", None)
    record["updated_at"] = now_iso()
    record["content_hash"] = sha(canonical(record))
    atomic_json(task_path(root, str(record["task"])), record)


def session_key(payload: dict[str, Any]) -> str:
    return str(
        payload.get("session_key") or payload.get("session_id")
        or payload.get("conversation_id") or os.environ.get("AGENT_CONTROL_SESSION")
        or "unidentified-session"
    )


def record_prompt(root: Path, session: str, text: str) -> str:
    receipt = sha(text.encode())
    atomic_json(prompt_path(root, session), {
        "version": 1, "session": session, "text": text, "hash": receipt,
        "captured_at": now_iso(),
    })
    return receipt


def claimed_task(root: Path, session: str) -> str | None:
    path = claim_path(root, session)
    if not path.is_file():
        return None
    return str(read_json(path).get("task") or "") or None


def attach_prompt(root: Path, session: str, record: dict[str, Any]) -> bool:
    path = prompt_path(root, session)
    if not path.is_file():
        return False
    prompt = read_json(path)
    if any(item["hash"] == prompt["hash"] for item in record["owner_prompts"]):
        return False
    record["owner_prompts"].append(prompt)
    record["pending_correction"] = prompt["hash"]
    return True


def create_checkpoint(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    if not TASK_RE.fullmatch(args.task):
        raise AgentControlError("task must be a lowercase kebab-case slug")
    if task_path(root, args.task).exists():
        raise AgentControlError("checkpoint already exists")
    branch = git("branch", "--show-current", root=root)
    prompt_hash = record_prompt(root, args.session_key, args.prompt)
    record = {
        "version": 1, "task": args.task, "worktree": str(root), "branch": branch,
        "head": git("rev-parse", "HEAD", root=root), "objective": args.objective,
        "next_action": args.next_action, "blocker": "none", "status": "active",
        "authorized_scope": list(args.scope), "excluded_scope": list(args.exclude),
        "owner_prompts": [{"text": args.prompt, "hash": prompt_hash, "captured_at": now_iso()}],
        "pending_correction": None, "envelope": None, "manifests": [], "events": [],
        "urgent": None, "deferred_bookkeeping": [], "updated_at": now_iso(),
    }
    save_task(root, record)
    atomic_json(claim_path(root, args.session_key), {
        "task": args.task, "session": args.session_key, "worktree": str(root),
    })
    print(f"created and claimed checkpoint {args.task}")
    return 0


def claim_checkpoint(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    atomic_json(claim_path(root, args.session_key), {
        "task": args.task, "session": args.session_key, "worktree": str(root),
        "checkpoint_hash": record["content_hash"],
    })
    print(f"claimed checkpoint {args.task}")
    return 0


def update_checkpoint(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    if args.next_action:
        record["next_action"] = args.next_action
    if args.blocker:
        record["blocker"] = args.blocker
    if args.verification:
        record["events"].append({"type": "verification", "text": args.verification, "at": now_iso()})
    record["head"] = git("rev-parse", "HEAD", root=root)
    save_task(root, record)
    print(f"updated checkpoint {args.task}")
    return 0


def create_envelope(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    record["envelope"] = {
        "actions": list(args.action), "targets": list(args.target),
        "exclusions": list(args.exclusion),
        "prompt_hashes": [item["hash"] for item in record["owner_prompts"]],
        "created_at": now_iso(),
    }
    save_task(root, record)
    print(f"created envelope for {args.task}")
    return 0


def capture_images(root: Path, receipt: str, targets: Iterable[str]) -> list[dict[str, Any]]:
    snapshot_root = state_root(root) / "before-images" / receipt
    images: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        path = root / target
        image = {"target": target, "exists": path.exists(), "snapshot": None, "sha256": None}
        if path.is_file():
            snapshot_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            snapshot = snapshot_root / f"{index:05d}.bin"
            shutil.copy2(path, snapshot)
            image.update({"snapshot": str(snapshot), "sha256": sha(path.read_bytes())})
        images.append(image)
    return images


def create_manifest(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    if record.get("pending_correction"):
        raise AgentControlError("apply the pending owner correction before a protected manifest")
    envelope = record.get("envelope") or {}
    if args.action not in envelope.get("actions", []):
        raise AgentControlError("action is outside the authorization envelope")
    targets = [normalize_target(root, item) for item in args.target]
    if not all(any(path_matches(target, allowed) for allowed in envelope.get("targets", [])) for target in targets):
        raise AgentControlError("target is outside the authorization envelope")
    seed = {
        "task": args.task, "session": args.session_key, "tool": args.tool,
        "action": args.action, "targets": targets,
        "command_hash": sha(args.command.encode()) if args.command else None,
    }
    receipt = sha(canonical(seed))[:32]
    record["manifests"].append({
        **seed, "receipt": receipt, "state": "prepared", "created_at": now_iso(),
        "before_images": capture_images(root, receipt, targets),
    })
    save_task(root, record)
    print(f"prepared manifest {receipt}")
    return 0


def urgent_begin(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    if not config(root).get("urgent_override", {}).get("enabled", False):
        raise AgentControlError("urgent override is disabled")
    record = load_task(root, args.task)
    if record.get("urgent") and record["urgent"].get("state") == "active":
        raise AgentControlError("an urgent override is already active")
    record["urgent"] = {
        "state": "active", "session": args.session_key, "reason": args.reason,
        "scope": list(args.scope), "started_at": now_iso(),
    }
    save_task(root, record)
    print(f"urgent override active for {args.task}; bookkeeping deferred")
    return 0


def urgent_close(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    urgent = record.get("urgent") or {}
    if urgent.get("state") != "active":
        raise AgentControlError("no urgent override is active")
    unfinished = [
        item for item in record["deferred_bookkeeping"]
        if item.get("state") == "running"
    ]
    if unfinished:
        raise AgentControlError("urgent operations are still running; capture their outcomes first")
    reconciled_at = now_iso()
    for item in record["deferred_bookkeeping"]:
        item["state"] = "reconciled"
        item["reconciled_at"] = reconciled_at
    urgent.update({"state": "closed", "verification": args.verification, "closed_at": now_iso()})
    record["events"].append({
        "type": "terminal", "text": args.verification, "at": now_iso(),
        "urgent_operations_reconciled": len(record["deferred_bookkeeping"]),
    })
    record["pending_correction"] = None
    save_task(root, record)
    print(f"urgent override closed; deferred items={len(record['deferred_bookkeeping'])}")
    return 0


def issue_event(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    record["events"].append({"type": args.type, "text": args.text, "at": now_iso()})
    if args.type == "correction":
        record["pending_correction"] = None
    if args.type == "terminal":
        record["status"] = "complete"
    save_task(root, record)
    print(f"recorded {args.type} event for {args.task}")
    return 0


HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PATCH_PATH = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$|^\*\*\* Move to:\s*(.+?)\s*$",
    re.MULTILINE,
)
SHELL_SEPARATORS = {";", "&&", "||", "|", "&"}
SHELL_CONTROLS = {"do", "then", "else", "elif"}


def strip_heredoc_bodies(command: str) -> str:
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
            prefix = match.group(0).split(match.group(1) + match.group(2), 1)[0]
            delimiters.append((match.group(2), "<<-" in prefix))
    return "\n".join(output)


def command_segments(command: str) -> list[str]:
    lexer = shlex.shlex(strip_heredoc_bodies(command), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_SEPARATORS or token in SHELL_CONTROLS:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)
    return [" ".join(segment) for segment in segments if segment]


def command_is_protected(command: str, policy: dict[str, Any]) -> bool:
    return any(
        re.search(pattern, segment, re.IGNORECASE)
        for segment in command_segments(command)
        for pattern in policy["protected_command_patterns"]
    )


def payload_targets(root: Path, payload: dict[str, Any]) -> list[str]:
    inputs = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(inputs, dict):
        return []
    values = [inputs.get(key) for key in ("file_path", "path", "notebook_path")]
    targets = [normalize_target(root, str(value)) for value in values if isinstance(value, str)]
    tool = str(payload.get("tool_name") or "")
    if tool == "apply_patch":
        patch = next(
            (inputs.get(key) for key in ("patch", "command", "input") if isinstance(inputs.get(key), str)),
            "",
        )
        for match in PATCH_PATH.finditer(str(patch)):
            value = match.group(1) or match.group(2)
            targets.append(normalize_target(root, value))
    return list(dict.fromkeys(targets))


def protected_call(root: Path, payload: dict[str, Any]) -> tuple[bool, str, list[str], str]:
    policy = config(root)
    tool = str(payload.get("tool_name") or "")
    inputs = payload.get("tool_input") or payload.get("input") or {}
    inputs = inputs if isinstance(inputs, dict) else {}
    command = str(inputs.get("command") or "")
    targets = payload_targets(root, payload)
    protected = command_is_protected(command, policy) if tool == "Bash" else any(
        any(path_matches(target, pattern) for pattern in policy["protected_paths"])
        for target in targets
    )
    return protected, tool, targets, command


def urgent_operation_targets(targets: list[str], command: str) -> list[str]:
    """Return concrete values that an urgent scope must authorize."""
    if targets:
        return targets
    if command:
        return [f"command:{command.strip()}"]
    return []


def matching_manifest(record: dict[str, Any], session: str, tool: str, targets: list[str], command: str) -> dict[str, Any] | None:
    for item in reversed(record["manifests"]):
        if item["state"] != "prepared" or item["session"] != session or item["tool"] != tool:
            continue
        if command and item.get("command_hash") != sha(command.encode()):
            continue
        if not command and set(item["targets"]) != set(targets):
            continue
        return item
    return None


def hook_block(message: str) -> int:
    if os.environ.get("AGENT_CONTROL_EVENT") == "codex":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"[agent-control] {message}",
        }}))
        return 0
    print(f"[agent-control] {message}", file=sys.stderr)
    return 2


def hook_context(root: Path, session: str) -> int:
    task = claimed_task(root, session)
    context: dict[str, Any] = {"claimed_task": task, "routine_work": "nonblocking"}
    if task:
        record = load_task(root, task)
        context.update({
            "objective": record["objective"], "next_action": record["next_action"],
            "blocker": record["blocker"], "scope": record["authorized_scope"],
            "urgent": record.get("urgent"),
        })
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": json.dumps(context),
    }}))
    return 0


def hook_pre(root: Path, payload: dict[str, Any], session: str) -> int:
    protected, tool, targets, command = protected_call(root, payload)
    if not protected:
        return 0
    task = claimed_task(root, session)
    if not task:
        return hook_block("protected operation requires a claimed checkpoint")
    record = load_task(root, task)
    correction_attached = attach_prompt(root, session, record)
    urgent = record.get("urgent") or {}
    if urgent.get("state") == "active" and urgent.get("session") == session:
        scope = urgent.get("scope", [])
        operation_targets = urgent_operation_targets(targets, command)
        if not operation_targets or not all(
            any(path_matches(target, item) for item in scope) for target in operation_targets
        ):
            return hook_block("urgent operation exceeds its exact scope")
        seed = {
            "task": task, "session": session, "tool": tool,
            "targets": operation_targets, "command_hash": sha(command.encode()),
            "tool_use_id": str(payload.get("tool_use_id") or ""),
        }
        receipt = sha(canonical(seed))[:32]
        file_targets = [target for target in targets if not target.startswith("command:")]
        record["deferred_bookkeeping"].append({
            **seed, "receipt": receipt, "state": "running", "at": now_iso(),
            "before_images": capture_images(root, receipt, file_targets),
        })
        save_task(root, record)
        return 0
    if correction_attached or record.get("pending_correction"):
        save_task(root, record)
        return hook_block("record the pending owner correction before a protected operation")
    manifest = matching_manifest(record, session, tool, targets, command)
    if not manifest:
        save_task(root, record)
        return hook_block("protected operation needs an exact prepared manifest")
    manifest["state"] = "running"
    manifest["tool_use_id"] = str(payload.get("tool_use_id") or "")
    save_task(root, record)
    return 0


def hook_post(root: Path, payload: dict[str, Any], session: str) -> int:
    task = claimed_task(root, session)
    if not task:
        return 0
    record = load_task(root, task)
    tool_use_id = str(payload.get("tool_use_id") or "")
    for manifest in reversed(record["manifests"]):
        if manifest.get("state") == "running" and manifest.get("tool_use_id") == tool_use_id:
            manifest.update({
                "state": "completed", "completed_at": now_iso(),
                "response_hash": sha(canonical(payload.get("tool_response"))),
            })
            save_task(root, record)
            return 0
    for item in reversed(record["deferred_bookkeeping"]):
        if item.get("state") == "running" and item.get("tool_use_id") == tool_use_id:
            item.update({
                "state": "completed", "completed_at": now_iso(),
                "response_hash": sha(canonical(payload.get("tool_response"))),
            })
            save_task(root, record)
            return 0
    return 0


def hook_stop(root: Path, session: str) -> int:
    task = claimed_task(root, session)
    if not task:
        return 0
    record = load_task(root, task)
    attach_prompt(root, session, record)
    if (record.get("urgent") or {}).get("state") == "active":
        save_task(root, record)
        return hook_block("close the active urgent override with verification before stopping")
    if config(root).get("terminal_event_required") and record["status"] == "active":
        if not any(event["type"] == "terminal" for event in record["events"]):
            save_task(root, record)
            return hook_block("claimed protected task has no terminal event")
    save_task(root, record)
    return 0


def hook_command(_args: argparse.Namespace) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        root = root_for(payload.get("cwd"))
    except AgentControlError:
        return 0
    session = session_key(payload)
    event = str(payload.get("hook_event_name") or os.environ.get("CLAUDE_HOOK_EVENT_NAME") or "")
    if event == "SessionStart":
        return hook_context(root, session)
    if event == "UserPromptSubmit":
        text = str(payload.get("prompt") or payload.get("user_prompt") or "")
        if text:
            record_prompt(root, session, text)
        return 0
    if event == "PreToolUse":
        return hook_pre(root, payload, session)
    if event == "PostToolUse":
        return hook_post(root, payload, session)
    if event == "Stop":
        return hook_stop(root, session)
    return 0


def rollback(args: argparse.Namespace) -> int:
    root = root_for(args.cwd)
    record = load_task(root, args.task)
    manifest = next((item for item in record["manifests"] if item["receipt"] == args.manifest), None)
    if not manifest:
        raise AgentControlError("unknown manifest")
    quarantine = state_root(root) / "rollback-quarantine" / manifest["receipt"]
    restored = 0
    for index, image in enumerate(manifest["before_images"]):
        path = root / image["target"]
        if image["exists"] and image["snapshot"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image["snapshot"], path)
            restored += 1
        elif not image["exists"] and path.is_file():
            quarantine.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.replace(path, quarantine / f"{index:05d}-{path.name}")
            restored += 1
    manifest["state"] = "rolled-back"
    save_task(root, record)
    print(f"rollback restored or quarantined {restored} target(s)")
    return 0


def doctor(_args: argparse.Namespace) -> int:
    root = ROOT
    policy = config(root)
    required = [
        root / ".codex/hooks.json", root / ".codex/config.toml",
        root / ".claude/settings.agent-control.json",
        root / ".claude/hooks/live_wait_gate.py",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise AgentControlError("missing adapter files: " + ", ".join(missing))
    for pattern in policy.get("protected_command_patterns", []):
        re.compile(pattern)
    source = Path(__file__).read_text(encoding="utf-8")
    project_terms = (
        "andro" + "meda", "classic" + "chess", "djan" + "go", "master" + "db",
    )
    if any(term in source.lower() for term in project_terms):
        raise AgentControlError("shared core contains project-specific terms")
    print("agent-control doctor passed")
    return 0


def self_test() -> int:
    assert path_matches("infra/app.tf", "infra/**")
    policy = read_json(CONFIG)
    assert command_is_protected("terraform apply", policy)
    assert not command_is_protected("rg while docs", policy)
    assert not command_is_protected("printf 'deploy is a regular word'", policy)
    print("agent-control self-test passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook").set_defaults(func=hook_command)
    checkpoint = sub.add_parser("checkpoint")
    checkpoint_sub = checkpoint.add_subparsers(dest="checkpoint_command", required=True)
    create = checkpoint_sub.add_parser("create")
    create.add_argument("--task", required=True)
    create.add_argument("--session-key", required=True)
    create.add_argument("--prompt", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--next", dest="next_action", required=True)
    create.add_argument("--scope", action="append", required=True)
    create.add_argument("--exclude", action="append", default=[])
    create.add_argument("--cwd")
    create.set_defaults(func=create_checkpoint)
    claim = checkpoint_sub.add_parser("claim")
    claim.add_argument("--task", required=True)
    claim.add_argument("--session-key", required=True)
    claim.add_argument("--cwd")
    claim.set_defaults(func=claim_checkpoint)
    update = checkpoint_sub.add_parser("update")
    update.add_argument("--task", required=True)
    update.add_argument("--next", dest="next_action")
    update.add_argument("--blocker")
    update.add_argument("--verification")
    update.add_argument("--cwd")
    update.set_defaults(func=update_checkpoint)
    envelope = sub.add_parser("envelope")
    envelope.add_argument("--task", required=True)
    envelope.add_argument("--action", action="append", required=True)
    envelope.add_argument("--target", action="append", required=True)
    envelope.add_argument("--exclusion", action="append", default=[])
    envelope.add_argument("--cwd")
    envelope.set_defaults(func=create_envelope)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("--task", required=True)
    manifest.add_argument("--session-key", required=True)
    manifest.add_argument("--tool", required=True)
    manifest.add_argument("--action", required=True)
    manifest.add_argument("--target", action="append", required=True)
    manifest.add_argument("--command", default="")
    manifest.add_argument("--cwd")
    manifest.set_defaults(func=create_manifest)
    urgent = sub.add_parser("urgent")
    urgent_sub = urgent.add_subparsers(dest="urgent_command", required=True)
    begin = urgent_sub.add_parser("begin")
    begin.add_argument("--task", required=True)
    begin.add_argument("--session-key", required=True)
    begin.add_argument("--reason", required=True)
    begin.add_argument("--scope", action="append", required=True)
    begin.add_argument("--cwd")
    begin.set_defaults(func=urgent_begin)
    close = urgent_sub.add_parser("close")
    close.add_argument("--task", required=True)
    close.add_argument("--verification", required=True)
    close.add_argument("--cwd")
    close.set_defaults(func=urgent_close)
    event = sub.add_parser("event")
    event.add_argument("--task", required=True)
    event.add_argument(
        "--type", choices=("correction", "progress", "terminal"), required=True,
    )
    event.add_argument("--text", required=True)
    event.add_argument("--cwd")
    event.set_defaults(func=issue_event)
    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("--task", required=True)
    rollback_parser.add_argument("--manifest", required=True)
    rollback_parser.add_argument("--cwd")
    rollback_parser.set_defaults(func=rollback)
    sub.add_parser("doctor").set_defaults(func=doctor)
    sub.add_parser("self-test").set_defaults(func=lambda _args: self_test())
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (AgentControlError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"agent control failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
