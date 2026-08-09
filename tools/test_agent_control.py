#!/usr/bin/env python3
"""Regression tests for the portable agent-control template."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


control = load_module("portable_agent_control", TOOLS / "agent_control.py")
wait_gate = load_module(
    "portable_live_wait_gate", TOOLS.parent / ".claude" / "hooks" / "live_wait_gate.py",
)


class RepositoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-control-test-")
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        policy = json.loads((TOOLS.parent / "agent-control.json").read_text(encoding="utf-8"))
        (self.root / "agent-control.json").write_text(
            json.dumps(policy, indent=2) + "\n", encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=self.root, check=True, capture_output=True)
        self.session = "session-one"
        self.task = "protected-change"
        control.create_checkpoint(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            prompt="Change the protected configuration", objective="Test protected control",
            next_action="Prepare the exact change", scope=["ops/**", "config/**"], exclude=[],
        ))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def envelope(self, *targets: str, actions: tuple[str, ...] = ("edit",)) -> None:
        control.create_envelope(argparse.Namespace(
            cwd=str(self.root), task=self.task, action=list(actions),
            target=list(targets), exclusion=[],
        ))


class ControlTests(RepositoryFixture):
    def test_checkpoint_captures_exact_owner_prompt_and_claim(self) -> None:
        record = control.load_task(self.root, self.task)
        self.assertEqual(record["owner_prompts"][0]["text"], "Change the protected configuration")
        self.assertEqual(control.claimed_task(self.root, self.session), self.task)

    def test_routine_work_passes_without_manifest(self) -> None:
        payload = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / "src" / "app.py")},
            "tool_use_id": "routine", "cwd": str(self.root),
        }
        self.assertEqual(control.hook_pre(self.root, payload, self.session), 0)

    def test_protected_path_requires_and_consumes_exact_manifest(self) -> None:
        target = "ops/ansible/app.yml"
        self.envelope("ops/**")
        control.create_manifest(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            tool="Write", action="edit", target=[target], command="",
        ))
        payload = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / target)},
            "tool_use_id": "protected-write", "cwd": str(self.root),
        }
        self.assertEqual(control.hook_pre(self.root, payload, self.session), 0)
        record = control.load_task(self.root, self.task)
        self.assertEqual(record["manifests"][-1]["state"], "running")

    def test_apply_patch_targets_are_parsed_and_protected(self) -> None:
        payload = {
            "tool_name": "apply_patch",
            "tool_input": {
                "patch": "*** Begin Patch\n*** Update File: ops/ansible/app.yml\n@@\n-old\n+new\n*** End Patch",
            },
            "tool_use_id": "patch", "cwd": str(self.root),
        }
        self.assertEqual(control.payload_targets(self.root, payload), ["ops/ansible/app.yml"])
        with redirect_stderr(StringIO()):
            self.assertEqual(control.hook_pre(self.root, payload, self.session), 2)

    def test_correction_does_not_block_routine_work_but_stops_stale_manifest(self) -> None:
        self.envelope("ops/**")
        control.create_manifest(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            tool="Write", action="edit", target=["ops/ansible/app.yml"], command="",
        ))
        control.record_prompt(self.root, self.session, "Use a different configuration value")
        routine = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / "src/app.py")},
            "tool_use_id": "routine", "cwd": str(self.root),
        }
        self.assertEqual(control.hook_pre(self.root, routine, self.session), 0)
        protected = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / "ops/ansible/app.yml")},
            "tool_use_id": "protected", "cwd": str(self.root),
        }
        with redirect_stderr(StringIO()):
            self.assertEqual(control.hook_pre(self.root, protected, self.session), 2)

    def test_urgent_override_is_fast_exact_and_records_deferred_work(self) -> None:
        control.urgent_begin(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            reason="Active production incident", scope=["ops/**", "command:terraform apply"],
        ))
        write_payload = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / "ops/ansible/app.yml")},
            "tool_use_id": "urgent-write", "cwd": str(self.root),
        }
        command_payload = {
            "tool_name": "Bash", "tool_input": {"command": "terraform apply"},
            "tool_use_id": "urgent-command", "cwd": str(self.root),
        }
        outside_payload = {
            "tool_name": "Write", "tool_input": {"file_path": str(self.root / ".claude/hooks/prod.py")},
            "tool_use_id": "outside", "cwd": str(self.root),
        }
        self.assertEqual(control.hook_pre(self.root, write_payload, self.session), 0)
        self.assertEqual(control.hook_pre(self.root, command_payload, self.session), 0)
        with redirect_stderr(StringIO()):
            self.assertEqual(control.hook_pre(self.root, outside_payload, self.session), 2)
        record = control.load_task(self.root, self.task)
        self.assertEqual(len(record["deferred_bookkeeping"]), 2)
        self.assertEqual(record["deferred_bookkeeping"][0]["before_images"][0]["target"], "ops/ansible/app.yml")

        for payload in (write_payload, command_payload):
            payload["tool_response"] = {"ok": True}
            self.assertEqual(control.hook_post(self.root, payload, self.session), 0)
        control.urgent_close(argparse.Namespace(
            cwd=str(self.root), task=self.task, verification="Incident fixed and verified",
        ))
        record = control.load_task(self.root, self.task)
        self.assertTrue(all(
            item["state"] == "reconciled" for item in record["deferred_bookkeeping"]
        ))
        self.assertEqual(record["events"][-1]["urgent_operations_reconciled"], 2)

    def test_active_urgent_override_blocks_stop_until_verified_close(self) -> None:
        control.urgent_begin(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            reason="Incident", scope=["ops/**"],
        ))
        with redirect_stderr(StringIO()):
            self.assertEqual(control.hook_stop(self.root, self.session), 2)
        control.urgent_close(argparse.Namespace(
            cwd=str(self.root), task=self.task, verification="Production recovered",
        ))
        self.assertEqual(control.hook_stop(self.root, self.session), 0)

    def test_before_image_rollback_restores_existing_file(self) -> None:
        path = self.root / "ops/ansible/app.yml"
        path.parent.mkdir(parents=True)
        path.write_text("before\n", encoding="utf-8")
        self.envelope("ops/**")
        control.create_manifest(argparse.Namespace(
            cwd=str(self.root), task=self.task, session_key=self.session,
            tool="Write", action="edit", target=["ops/ansible/app.yml"], command="",
        ))
        record = control.load_task(self.root, self.task)
        receipt = record["manifests"][-1]["receipt"]
        path.write_text("after\n", encoding="utf-8")
        control.rollback(argparse.Namespace(cwd=str(self.root), task=self.task, manifest=receipt))
        self.assertEqual(path.read_text(encoding="utf-8"), "before\n")


class LiveWaitGateTests(unittest.TestCase):
    def test_actual_wait_constructs_are_blocked(self) -> None:
        cases = {
            "while true; do curl -fsS example.invalid; done": "while",
            "until test -f ready; do date; done": "until",
            "sleep 30": "sleep",
            "timeout 60 pytest": "timeout",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertIn(expected, wait_gate.blocked_reason(command))

    def test_regular_words_in_prose_quotes_and_file_content_pass(self) -> None:
        cases = [
            "printf '%s\\n' 'work while writing until finished'",
            "rg 'while|until' docs/guide.md",
            "python3 - <<'PY'\ntext = 'while writing a file until done'\nprint(text)\nPY",
            "apply_patch <<'PATCH'\n*** Begin Patch\n+Use while and until as regular words.\n*** End Patch\nPATCH",
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertIsNone(wait_gate.blocked_reason(command))


class ShellProtectionParsingTests(unittest.TestCase):
    def test_command_matching_ignores_prose_and_heredoc_content(self) -> None:
        policy = json.loads((TOOLS.parent / "agent-control.json").read_text(encoding="utf-8"))
        cases = [
            "printf '%s\\n' 'deploy after verification'",
            "apply_patch <<'PATCH'\n+run deploy after CI\nPATCH",
            "rg 'terraform apply' docs",
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertFalse(control.command_is_protected(command, policy))

    def test_actual_protected_commands_are_detected_by_segment(self) -> None:
        policy = json.loads((TOOLS.parent / "agent-control.json").read_text(encoding="utf-8"))
        for command in ("./deploy.sh", "ruff check . && terraform apply", "ssh host"):
            with self.subTest(command=command):
                self.assertTrue(control.command_is_protected(command, policy))


if __name__ == "__main__":
    unittest.main()
