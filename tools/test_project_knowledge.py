#!/usr/bin/env python3
"""Tests for portable durable-knowledge routing and auditing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_knowledge  # noqa: E402


class ProjectKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="project-knowledge-test-")
        self.root = Path(self.temporary.name)
        for directory in (
            "docs/memory", "docs/runbooks", "docs/plans", "docs/resume",
            "docs/repo_history", "tools",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "docs/runbooks/docs-change.md").write_text(
            "# Docs Change\n\n## Steps\n\n- Verify.\n", encoding="utf-8",
        )
        (self.root / "tools/project_knowledge.py").write_text(
            '"""Knowledge tool."""\n', encoding="utf-8",
        )
        (self.root / "tools/check_memory_system.py").write_text(
            '"""Memory check."""\n', encoding="utf-8",
        )
        workflow = (
            "# Workflow\n\n## Current Setup\n\n- Layered memory.\n\n"
            "## Current Rules\n\n- Keep facts current.\n\n"
            "## Runbooks\n\n- `docs/runbooks/docs-change.md`\n\n"
            "## Lookup Anchors\n\n- `tools/project_knowledge.py`\n"
        )
        (self.root / "docs/memory/workflow.md").write_text(workflow, encoding="utf-8")
        contract = "# Contract\n\nUse `docs/runbooks/docs-change.md`.\n"
        (self.root / "AGENTS.md").write_text(contract, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(contract, encoding="utf-8")
        (self.root / "PROJECT_MEMORY.md").write_text(
            "# Router\n\n- Workflow: `docs/memory/workflow.md`\n\n## Lookup Rules\n",
            encoding="utf-8",
        )
        registry = {
            "version": 1,
            "settings": {
                "contract_max_lines": 20,
                "coverage": "advisory",
                "current_markdown_roots": ["docs/memory", "docs/runbooks"],
                "history_roots": ["docs/repo_history"],
                "ignored_roots": [],
                "require_transaction_receipts": False,
                "source_suffixes": [".py"],
            },
            "topics": [{
                "slug": "workflow", "path": "docs/memory/workflow.md",
                "ownership": "Memory workflow.", "kind": "mechanism",
                "includes": [
                    "AGENTS.md", "CLAUDE.md", "PROJECT_MEMORY.md", "docs/**", "tools/**",
                ],
                "excludes": [], "prerequisites": [],
                "runbooks": ["docs/runbooks/docs-change.md"],
                "anchors": ["tools/project_knowledge.py"], "volatility": "low",
            }],
            "no_memory": [],
        }
        self.registry_path = self.root / "docs/memory/topics.json"
        self.registry_path.write_text(json.dumps(registry), encoding="utf-8")
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=self.root, check=True,
            capture_output=True,
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.root, check=True,
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"], cwd=self.root, check=True,
            capture_output=True,
        )
        self.original_root = project_knowledge.ROOT
        self.original_registry = project_knowledge.REGISTRY_PATH
        project_knowledge.ROOT = self.root
        project_knowledge.REGISTRY_PATH = self.registry_path

    def tearDown(self) -> None:
        project_knowledge.ROOT = self.original_root
        project_knowledge.REGISTRY_PATH = self.original_registry
        self.temporary.cleanup()

    def topic_args(self) -> argparse.Namespace:
        return argparse.Namespace(
            domain="frontend", ownership="Frontend behavior.", topic_kind="project",
            include=["src/frontend/**"], exclude=[], prerequisite=[],
            runbook=["docs/runbooks/docs-change.md"],
            anchor=["tools/check_memory_system.py"], volatility="medium",
        )

    def test_registry_routes_topics_and_domains(self) -> None:
        registry = project_knowledge.read_registry()
        self.assertEqual(project_knowledge.validate_registry(), [])
        self.assertEqual(project_knowledge.domain_for("tools/example.py", registry), "workflow")
        self.assertEqual(project_knowledge.domain_for("src/unknown.py", registry), "unexplained")

    def test_create_topic_updates_file_registry_router_and_receipt(self) -> None:
        project_knowledge.create_topic(self.topic_args())
        self.assertTrue((self.root / "docs/memory/frontend.md").is_file())
        self.assertIn(
            "`docs/memory/frontend.md`",
            (self.root / "PROJECT_MEMORY.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(project_knowledge.validate_registry(), [])
        self.assertTrue(any(project_knowledge.receipt_root().glob("*.json")))

    def test_add_update_and_move_keep_atomic_topic_records(self) -> None:
        project_knowledge.create_topic(self.topic_args())
        add = argparse.Namespace(
            kind="current-rule", domain="frontend", text="Keep browser state bounded.",
            anchor="src/frontend/app.js", destination=None, heading=None,
        )
        project_knowledge.add_knowledge(add)
        update = argparse.Namespace(
            domain="frontend", old=add.text, text="Keep browser state explicit and bounded.",
            anchor="src/frontend/app.js", heading="Current Rules",
        )
        project_knowledge.update_knowledge(update)
        move = argparse.Namespace(
            from_domain="frontend", to_domain="workflow", text=update.text,
            heading="Current Rules",
        )
        project_knowledge.move_knowledge(move)
        self.assertNotIn(
            update.text, (self.root / "docs/memory/frontend.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            update.text, (self.root / "docs/memory/workflow.md").read_text(encoding="utf-8"),
        )

    def test_active_state_is_rejected_from_durable_memory(self) -> None:
        args = argparse.Namespace(
            kind="active-state", domain="workflow", text="Currently editing.",
            anchor="tools/project_knowledge.py", destination=None, heading=None,
        )
        with self.assertRaisesRegex(project_knowledge.KnowledgeError, "transient task state"):
            project_knowledge.add_knowledge(args)

    def test_markdown_audit_detects_handoff_history_missing_refs_and_duplicates(self) -> None:
        registry = project_knowledge.read_registry()
        findings = project_knowledge.markdown_findings(
            "docs/runbooks/example.md",
            "AGENT_HANDOFF.md\n\n## Historical Notes\n\n`docs/missing.md`\n",
            registry,
        )
        self.assertEqual(
            findings,
            [
                "missing-reference:docs/missing.md",
                "retired-static-handoff-reference",
                "mixed-current-and-history-section",
            ],
        )
        (self.root / "ONE.md").write_text("duplicate\n", encoding="utf-8")
        (self.root / "TWO.md").write_text("duplicate\n", encoding="utf-8")
        duplicates = project_knowledge.duplicate_markdown_findings(
            ["AGENTS.md", "CLAUDE.md", "ONE.md", "TWO.md"], registry,
        )
        self.assertEqual(duplicates, ["exact-current-duplicate:ONE.md | TWO.md"])

    def test_source_prose_audit_detects_stale_references(self) -> None:
        source = self.root / "tools/source.py"
        source.write_text(
            '"""See docs/missing.md."""\n# AGENT_HANDOFF.md is current\n',
            encoding="utf-8",
        )
        count, findings = project_knowledge.source_prose_findings("tools/source.py")
        self.assertEqual(count, 2)
        self.assertEqual(len(findings), 2)

    def test_clean_fixture_audit_passes_with_advisory_coverage(self) -> None:
        report = project_knowledge.audit()
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["domains"]["coverage"], "advisory")

    def test_transaction_gate_is_optional_by_default(self) -> None:
        self.assertEqual(project_knowledge.transaction_check(), 0)

    def test_failed_transaction_restores_existing_files_and_quarantines_new_file(self) -> None:
        existing = self.root / "PROJECT_MEMORY.md"
        original = existing.read_text(encoding="utf-8")
        created = self.root / "docs/memory/broken.md"
        with self.assertRaisesRegex(project_knowledge.KnowledgeError, "forced failure"):
            project_knowledge.write_transaction(
                "test", {existing: "changed\n", created: "new\n"}, {},
                validator=lambda: ["forced failure"],
            )
        self.assertEqual(existing.read_text(encoding="utf-8"), original)
        self.assertFalse(created.exists())
        quarantine = project_knowledge.task_state.state_root(self.root) / "failed-knowledge-transactions"
        self.assertTrue(any(quarantine.iterdir()))


if __name__ == "__main__":
    unittest.main()
