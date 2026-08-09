#!/usr/bin/env python3
"""Route, mutate, and audit durable project knowledge with Python stdlib only."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Iterable

sys.dont_write_bytecode = True

import task_state  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "memory" / "topics.json"
TOPIC_SECTIONS = ("Current Setup", "Current Rules", "Runbooks", "Lookup Anchors")
KNOWLEDGE_KINDS = {"current-setup", "current-rule", "workflow-step", "active-state"}
DOC_REF_RE = re.compile(r"docs/[A-Za-z0-9_./<>-]+\.md")
HISTORY_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:Deprecated|Historical|Retired|Obsolete|Latest Completed)\b",
    re.IGNORECASE | re.MULTILINE,
)
SKILL_RESOURCE_RE = re.compile(r"`((?:references|scripts|assets)/[^`]+)`")
DEFAULT_SOURCE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".css", ".html", ".sh", ".bash",
    ".zsh", ".toml", ".yml", ".yaml", ".json", ".ini", ".cfg",
    ".service", ".timer", ".kt", ".kts", ".rs", ".sql",
}


class KnowledgeError(ValueError):
    """Raised when knowledge placement, mutation, or auditing is invalid."""


def git(*args: str, root: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root or ROOT, capture_output=True, text=True, check=False,
    )
    if check and result.returncode:
        raise KnowledgeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def tracked(root: Path | None = None) -> list[str]:
    return [item for item in git("ls-files", "-z", root=root).split("\0") if item]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def read_registry(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    try:
        value = json.loads(
            (root / "docs" / "memory" / "topics.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeError(f"cannot read topic registry: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise KnowledgeError("topic registry must be a version-1 object")
    if not isinstance(value.get("settings"), dict) or not isinstance(value.get("topics"), list):
        raise KnowledgeError("topic registry must contain settings and topics")
    if not isinstance(value.get("no_memory", []), list):
        raise KnowledgeError("topic registry no_memory must be an array")
    return value


def topic_by_slug(registry: dict[str, Any], slug: str) -> dict[str, Any]:
    matches = [item for item in registry["topics"] if item.get("slug") == slug]
    if len(matches) != 1:
        raise KnowledgeError(f"topic {slug!r} is missing or duplicated")
    return matches[0]


def path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    return fnmatch.fnmatchcase(path, pattern)


def domain_for(path: str, registry: dict[str, Any]) -> str:
    matches: list[tuple[int, str]] = []
    for topic in registry["topics"]:
        for pattern in topic.get("includes", []):
            pattern = str(pattern)
            if path_matches(path, pattern):
                matches.append((len(pattern.replace("*", "")), str(topic["slug"])))
    if matches:
        return sorted(matches, reverse=True)[0][1]
    for decision in registry.get("no_memory", []):
        if any(path_matches(path, str(pattern)) for pattern in decision.get("paths", [])):
            return f"no-memory:{decision.get('domain', 'declared')}"
    return "unexplained"


def validate_registry(root: Path | None = None) -> list[str]:
    root = root or ROOT
    registry = read_registry(root)
    errors: list[str] = []
    slugs: set[str] = set()
    paths: set[str] = set()
    required = {
        "slug", "path", "ownership", "kind", "includes", "excludes",
        "prerequisites", "runbooks", "anchors", "volatility",
    }
    all_slugs = {str(item.get("slug")) for item in registry["topics"]}
    for topic in registry["topics"]:
        missing = sorted(required - topic.keys())
        if missing:
            errors.append(f"topic {topic.get('slug')} missing {', '.join(missing)}")
            continue
        slug, path = str(topic["slug"]), str(topic["path"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", slug):
            errors.append(f"invalid topic slug: {slug}")
        if slug in slugs or path in paths:
            errors.append(f"duplicate topic slug/path: {slug} {path}")
        slugs.add(slug)
        paths.add(path)
        topic_path = root / path
        if not topic_path.is_file():
            errors.append(f"topic file missing: {path}")
        else:
            text = topic_path.read_text(encoding="utf-8")
            for section in TOPIC_SECTIONS:
                if f"## {section}" not in text:
                    errors.append(f"{path} missing section {section}")
        for prerequisite in topic["prerequisites"]:
            if prerequisite not in all_slugs:
                errors.append(f"{slug} has missing prerequisite {prerequisite}")
        for runbook in topic["runbooks"]:
            if not (root / str(runbook)).is_file():
                errors.append(f"{slug} routes missing runbook {runbook}")
        for anchor in topic["anchors"]:
            if not (root / str(anchor)).exists():
                errors.append(f"{slug} routes missing anchor {anchor}")
    router_path = root / "PROJECT_MEMORY.md"
    if not router_path.is_file():
        return errors + ["PROJECT_MEMORY.md is missing"]
    router = router_path.read_text(encoding="utf-8")
    for path in sorted(paths):
        if f"`{path}`" not in router:
            errors.append(f"PROJECT_MEMORY.md does not route {path}")
    routed_text = re.sub(r"<!--.*?-->", "", router, flags=re.DOTALL)
    routed = set(re.findall(r"`(docs/memory/[^`]+\.md)`", routed_text))
    routed.discard("docs/memory/<topic>.md")
    for path in sorted(routed - paths):
        errors.append(f"router topic is absent from registry: {path}")
    settings = registry["settings"]
    if settings.get("coverage") not in {"advisory", "strict"}:
        errors.append("settings.coverage must be advisory or strict")
    if not isinstance(settings.get("contract_max_lines"), int):
        errors.append("settings.contract_max_lines must be an integer")
    return errors


def section_bounds(text: str, heading: str) -> tuple[int, int]:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        raise KnowledgeError(f"missing section {heading}")
    content_start = text.find("\n", start) + 1
    next_heading = text.find("\n## ", content_start)
    return content_start, len(text) if next_heading < 0 else next_heading + 1


def validate_record_text(text: str) -> str:
    value = text.strip()
    if not value or "\n" in value or len(value) > 1000:
        raise KnowledgeError("knowledge text must be one line of at most 1000 characters")
    return value


def insert_bullet(text: str, heading: str, value: str) -> str:
    start, end = section_bounds(text, heading)
    section = text[start:end].rstrip()
    return text[:start] + section + f"\n\n- {value}\n" + text[end:]


def remove_bullet(text: str, value: str) -> str:
    pattern = re.compile(rf"^- {re.escape(value)}\n?", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise KnowledgeError("source knowledge record must match exactly once")
    updated = text[:matches[0].start()] + text[matches[0].end():]
    return re.sub(r"\n{3,}", "\n\n", updated).rstrip() + "\n"


def receipt_root(root: Path | None = None) -> Path:
    path = task_state.state_root(root or ROOT) / "knowledge-receipts"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def record_receipt(
    operation: str, paths: Iterable[Path], details: dict[str, Any], root: Path | None = None,
) -> str:
    root = root or ROOT
    normalized = sorted(str(path.resolve().relative_to(root.resolve())) for path in paths)
    record: dict[str, Any] = {
        "version": 1,
        "operation": operation,
        "paths": normalized,
        "after": {
            path: digest((root / path).read_bytes()) if (root / path).is_file() else None
            for path in normalized
        },
        "details": details,
        "created_at": task_state.now_iso(),
        "head": git("rev-parse", "HEAD", root=root).strip(),
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["receipt"] = digest(canonical)
    atomic_json(receipt_root(root) / f"{record['receipt']}.json", record)
    return str(record["receipt"])


def write_transaction(
    operation: str,
    changes: dict[Path, str],
    details: dict[str, Any],
    validator: Callable[[], list[str]] | None = None,
) -> str:
    """Replace a prepared file set, validate it, and record exact digests."""
    before = {path: path.read_bytes() if path.exists() else None for path in changes}
    try:
        for path, text in changes.items():
            atomic_text(path, text)
        if validator:
            errors = validator()
            if errors:
                raise KnowledgeError("transaction validation failed: " + "; ".join(errors))
        return record_receipt(operation, changes, details)
    except Exception:
        for path, data in before.items():
            if data is None and path.exists():
                quarantine = task_state.state_root(ROOT) / "failed-knowledge-transactions"
                quarantine.mkdir(parents=True, exist_ok=True, mode=0o700)
                token = digest(f"{path}:{task_state.now_iso()}".encode())[:16]
                os.replace(path, quarantine / f"{token}-{path.name}")
            elif data is not None:
                atomic_bytes(path, data)
        raise


def create_topic(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", args.domain):
        raise KnowledgeError("topic slug must be lowercase kebab-case")
    registry = read_registry()
    if any(item["slug"] == args.domain for item in registry["topics"]):
        raise KnowledgeError("topic already exists")
    topic_path = ROOT / "docs" / "memory" / f"{args.domain}.md"
    if topic_path.exists():
        raise KnowledgeError("topic file already exists")
    for path in [*args.runbook, *args.anchor]:
        if not (ROOT / path).exists():
            raise KnowledgeError(f"routed path does not exist: {path}")
    missing_prerequisites = set(args.prerequisite) - {
        str(item["slug"]) for item in registry["topics"]
    }
    if missing_prerequisites:
        raise KnowledgeError(f"missing prerequisites: {sorted(missing_prerequisites)}")
    title = " ".join(part.capitalize() for part in args.domain.split("-"))
    topic_text = (
        f"# {title}\n\n## Current Setup\n\n- {args.ownership}\n\n"
        "## Current Rules\n\n- Add verified facts through `tools/project_knowledge.py`.\n\n"
        "## Runbooks\n\n" + "\n".join(f"- `{item}`" for item in args.runbook)
        + "\n\n## Lookup Anchors\n\n"
        + "\n".join(f"- `{item}`" for item in args.anchor) + "\n"
    )
    registry["topics"].append({
        "slug": args.domain, "path": str(topic_path.relative_to(ROOT)),
        "ownership": args.ownership, "kind": args.topic_kind,
        "includes": list(args.include), "excludes": list(args.exclude),
        "prerequisites": list(args.prerequisite), "runbooks": list(args.runbook),
        "anchors": list(args.anchor), "volatility": args.volatility,
    })
    registry["topics"] = sorted(registry["topics"], key=lambda item: item["slug"])
    router_path = ROOT / "PROJECT_MEMORY.md"
    router = router_path.read_text(encoding="utf-8")
    marker = "## Lookup Rules"
    if marker not in router:
        raise KnowledgeError("PROJECT_MEMORY.md lacks the Lookup Rules marker")
    route = f"- {args.ownership}: `docs/memory/{args.domain}.md`\n\n"
    receipt = write_transaction(
        "create-topic",
        {
            topic_path: topic_text,
            REGISTRY_PATH: json.dumps(registry, indent=2, sort_keys=True) + "\n",
            router_path: router.replace(marker, route + marker, 1),
        },
        {"domain": args.domain},
        validate_registry,
    )
    print(f"created and routed topic {args.domain}; receipt={receipt}")
    return 0


def destination_for(args: argparse.Namespace) -> tuple[Path, str]:
    registry = read_registry()
    topic = topic_by_slug(registry, args.domain)
    owner = domain_for(args.anchor, registry)
    if owner not in {args.domain, "unexplained"} and not owner.startswith("no-memory:"):
        raise KnowledgeError(f"anchor belongs to {owner}; use --domain {owner}")
    if args.kind == "active-state":
        raise KnowledgeError("active state belongs in transient task state, not durable Markdown")
    if args.kind == "current-setup":
        return ROOT / str(topic["path"]), "Current Setup"
    if args.kind == "current-rule":
        return ROOT / str(topic["path"]), "Current Rules"
    if args.kind == "workflow-step":
        if not args.destination or not args.destination.startswith("docs/runbooks/"):
            raise KnowledgeError("workflow steps require --destination docs/runbooks/<file>.md")
        return ROOT / args.destination, args.heading or "Steps"
    raise KnowledgeError(f"unsupported durable knowledge kind: {args.kind}")


def add_knowledge(args: argparse.Namespace) -> int:
    value = validate_record_text(args.text)
    destination, heading = destination_for(args)
    if not destination.is_file():
        raise KnowledgeError(f"destination does not exist: {destination.relative_to(ROOT)}")
    updated = insert_bullet(destination.read_text(encoding="utf-8"), heading, value)
    receipt = write_transaction(
        "add", {destination: updated},
        {"kind": args.kind, "domain": args.domain, "anchor": args.anchor},
        validate_registry,
    )
    print(f"added {args.kind} to {destination.relative_to(ROOT)}; receipt={receipt}")
    return 0


def update_knowledge(args: argparse.Namespace) -> int:
    registry = read_registry()
    path = ROOT / str(topic_by_slug(registry, args.domain)["path"])
    old, new = validate_record_text(args.old), validate_record_text(args.text)
    updated = insert_bullet(remove_bullet(path.read_text(encoding="utf-8"), old), args.heading, new)
    receipt = write_transaction(
        "update", {path: updated},
        {"domain": args.domain, "old_hash": digest(old.encode()), "anchor": args.anchor},
        validate_registry,
    )
    print(f"updated knowledge in {path.relative_to(ROOT)}; receipt={receipt}")
    return 0


def move_knowledge(args: argparse.Namespace) -> int:
    registry = read_registry()
    source = ROOT / str(topic_by_slug(registry, args.from_domain)["path"])
    destination = ROOT / str(topic_by_slug(registry, args.to_domain)["path"])
    value = validate_record_text(args.text)
    receipt = write_transaction(
        "move",
        {
            source: remove_bullet(source.read_text(encoding="utf-8"), value),
            destination: insert_bullet(
                destination.read_text(encoding="utf-8"), args.heading, value,
            ),
        },
        {"from": args.from_domain, "to": args.to_domain, "text_hash": digest(value.encode())},
        validate_registry,
    )
    print(f"moved knowledge from {args.from_domain} to {args.to_domain}; receipt={receipt}")
    return 0


def maintenance_receipt(args: argparse.Namespace) -> int:
    paths = [ROOT / item for item in args.path]
    staged_deletions = set(git("diff", "--cached", "--name-only", "--diff-filter=D").splitlines())
    for path in paths:
        relative = str(path.relative_to(ROOT))
        if not path.is_file() and relative not in staged_deletions:
            raise KnowledgeError(f"maintenance path does not exist: {relative}")
    receipt = record_receipt("maintenance", paths, {"reason": args.reason})
    print(f"recorded maintenance receipt={receipt}")
    return 0


def settings_roots(registry: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(
        str(item).rstrip("/") + "/" for item in registry["settings"].get(key, [])
    )


def markdown_classification(path: str, registry: dict[str, Any]) -> str:
    if path == "CHANGELOG.md" or path.startswith(settings_roots(registry, "history_roots")):
        return "historical/archive"
    if path.startswith("docs/resume/") and path != "docs/resume/README.md":
        return "explicit-resume"
    current_roots = settings_roots(registry, "current_markdown_roots")
    if path in {"AGENTS.md", "CLAUDE.md", "PROJECT_MEMORY.md"} or path.startswith(current_roots):
        return "current-authority"
    if path.endswith("README.md"):
        return "current-authority"
    return "project-documentation"


def markdown_findings(
    path: str, text: str, registry: dict[str, Any], root: Path | None = None,
) -> list[str]:
    root = root or ROOT
    classification = markdown_classification(path, registry)
    if classification == "historical/archive":
        return []
    findings: list[str] = []
    visible_text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for reference in sorted(set(DOC_REF_RE.findall(visible_text))):
        if "<" not in reference and not (root / reference).is_file():
            findings.append(f"missing-reference:{reference}")
    if "AGENT_HANDOFF.md" in text:
        findings.append("retired-static-handoff-reference")
    if (
        classification == "current-authority"
        and not path.endswith("README.md")
        and HISTORY_HEADING_RE.search(visible_text)
    ):
        findings.append("mixed-current-and-history-section")
    if path in {"AGENTS.md", "CLAUDE.md"}:
        limit = int(registry["settings"]["contract_max_lines"])
        if len(text.splitlines()) > limit:
            findings.append(f"agent-contract-over-{limit}-lines")
    return findings


def duplicate_markdown_findings(
    paths: Iterable[str], registry: dict[str, Any], root: Path | None = None,
) -> list[str]:
    root = root or ROOT
    groups: dict[str, list[str]] = {}
    for path in paths:
        if markdown_classification(path, registry) == "historical/archive":
            continue
        data = (root / path).read_bytes()
        if data.strip():
            groups.setdefault(digest(data), []).append(path)
    allowed = {"AGENTS.md", "CLAUDE.md"}
    return [
        "exact-current-duplicate:" + " | ".join(sorted(group))
        for group in groups.values() if len(group) > 1 and set(group) != allowed
    ]


def python_prose(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    found: dict[int, str] = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                found[token.start[0]] = token.string
    except (tokenize.TokenError, IndentationError):
        pass
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                value = ast.get_docstring(node, clean=False)
                if value and getattr(node, "body", None):
                    found[node.body[0].lineno] = value
    return sorted(found.items())


def generic_prose(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found: list[tuple[int, str]] = []
    in_block = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if in_block:
            found.append((number, stripped))
            if "*/" in stripped:
                in_block = False
        elif stripped.startswith(("#", "//", "<!--", ";")):
            found.append((number, stripped))
        elif "/*" in stripped:
            in_block = "*/" not in stripped.split("/*", 1)[1]
            found.append((number, stripped))
    return found


def source_prose_findings(path: str, root: Path | None = None) -> tuple[int, list[str]]:
    root = root or ROOT
    absolute = root / path
    rows = python_prose(absolute) if absolute.suffix == ".py" else generic_prose(absolute)
    findings: list[str] = []
    for line, prose in rows:
        if "AGENT_HANDOFF.md" in prose:
            findings.append(f"{path}:{line}:retired-static-handoff-reference")
        for reference in sorted(set(DOC_REF_RE.findall(prose))):
            if "<" not in reference and not (root / reference).is_file():
                findings.append(f"{path}:{line}:missing-reference:{reference}")
    return len(rows), findings


def skill_findings(path: str, root: Path | None = None) -> list[str]:
    root = root or ROOT
    skill = root / path
    text = skill.read_text(encoding="utf-8")
    findings: list[str] = []
    if len(text.splitlines()) > 500:
        findings.append(f"{path}:skill-over-500-lines")
    if "AGENT_HANDOFF.md" in text:
        findings.append(f"{path}:retired-static-handoff-reference")
    for relative in SKILL_RESOURCE_RE.findall(text):
        if "<" not in relative and not (skill.parent / relative).exists():
            findings.append(f"{path}:missing-skill-resource:{relative}")
    return findings


def audit(root: Path | None = None, strict: bool | None = None) -> dict[str, Any]:
    root = root or ROOT
    registry = read_registry(root)
    files = tracked(root)
    markdown = [path for path in files if path.endswith(".md")]
    suffixes = set(registry["settings"].get("source_suffixes", DEFAULT_SOURCE_SUFFIXES))
    source = [path for path in files if Path(path).suffix in suffixes]
    findings = validate_registry(root)
    markdown_lines = 0
    for path in markdown:
        text = (root / path).read_text(encoding="utf-8", errors="replace")
        markdown_lines += len(text.splitlines())
        findings.extend(f"{path}:{item}" for item in markdown_findings(path, text, registry, root))
    findings.extend(duplicate_markdown_findings(markdown, registry, root))
    prose_lines = 0
    for path in source:
        count, source_findings = source_prose_findings(path, root)
        prose_lines += count
        findings.extend(source_findings)
    skills = [path for path in files if path.endswith("/SKILL.md")]
    for path in skills:
        findings.extend(skill_findings(path, root))
    ignored = tuple(str(item) for item in registry["settings"].get("ignored_roots", []))
    coverage_paths = [path for path in files if path not in markdown and not path.startswith(ignored)]
    unexplained = sorted(path for path in coverage_paths if domain_for(path, registry) == "unexplained")
    strict_mode = registry["settings"]["coverage"] == "strict" if strict is None else strict
    if strict_mode:
        findings.extend(f"unexplained-domain:{path}" for path in unexplained)
    return {
        "version": 1,
        "markdown": {"files": len(markdown), "lines": markdown_lines},
        "source_prose": {"files": len(source), "lines": prose_lines},
        "skills": {"files": len(skills)},
        "domains": {"coverage": "strict" if strict_mode else "advisory", "unexplained": unexplained},
        "findings": sorted(set(findings)),
    }


def check(_args: argparse.Namespace | None = None) -> int:
    report = audit()
    if report["findings"]:
        raise KnowledgeError("knowledge audit failed: " + "; ".join(report["findings"]))
    print(
        "project-knowledge check passed: "
        f"{report['markdown']['files']} Markdown files, "
        f"{report['source_prose']['lines']} source-prose lines, "
        f"{len(report['domains']['unexplained'])} advisory unexplained paths"
    )
    return 0


def audit_command(args: argparse.Namespace) -> int:
    report = audit(strict=True if args.strict else None)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        atomic_text(output if output.is_absolute() else ROOT / output, rendered)
        print(f"wrote knowledge audit to {output}")
    else:
        print(rendered, end="")
    return 1 if report["findings"] else 0


def durable_path(path: str, registry: dict[str, Any]) -> bool:
    roots = settings_roots(registry, "current_markdown_roots")
    return path in {"AGENTS.md", "CLAUDE.md", "PROJECT_MEMORY.md"} or path.startswith(roots)


def transaction_check(_args: argparse.Namespace | None = None) -> int:
    registry = read_registry()
    if not registry["settings"].get("require_transaction_receipts", False):
        print("knowledge transaction receipts are optional in this scaffold")
        return 0
    staged: dict[str, str] = {}
    for line in git("diff", "--cached", "--name-status").splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            staged[parts[1]] = parts[0]
    targets = sorted(path for path in staged if durable_path(path, registry))
    receipts: list[dict[str, Any]] = []
    for path in receipt_root().glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                receipts.append(value)
        except json.JSONDecodeError:
            continue
    uncovered: list[str] = []
    for target in targets:
        staged_digest = None
        if not staged[target].startswith("D"):
            data = subprocess.run(
                ["git", "show", f":{target}"], cwd=ROOT, capture_output=True, check=False,
            ).stdout
            staged_digest = digest(data)
        if not any(item.get("after", {}).get(target) == staged_digest for item in receipts):
            uncovered.append(target)
    if uncovered:
        raise KnowledgeError("durable mutation lacks a receipt: " + ", ".join(uncovered))
    print(f"knowledge transaction check passed for {len(targets)} staged path(s)")
    return 0


def self_test() -> int:
    registry = read_registry()
    assert topic_by_slug(registry, "workflow")["kind"] == "mechanism"
    assert domain_for("tools/project_knowledge.py", registry) == "workflow"
    assert markdown_classification("docs/repo_history/example.md", registry) == "historical/archive"
    assert validate_registry() == []
    print("project-knowledge self-test passed")
    return 0


def add_topic_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain", required=True)
    parser.add_argument("--ownership", required=True)
    parser.add_argument("--topic-kind", choices=("mechanism", "project"), required=True)
    parser.add_argument("--include", action="append", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--prerequisite", action="append", default=[])
    parser.add_argument("--runbook", action="append", required=True)
    parser.add_argument("--anchor", action="append", required=True)
    parser.add_argument("--volatility", choices=("low", "medium", "high"), required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-topic")
    add_topic_arguments(create)
    create.set_defaults(func=create_topic)
    add = sub.add_parser("add")
    add.add_argument("--kind", choices=sorted(KNOWLEDGE_KINDS), required=True)
    add.add_argument("--domain", required=True)
    add.add_argument("--text", required=True)
    add.add_argument("--anchor", required=True)
    add.add_argument("--destination")
    add.add_argument("--heading")
    add.set_defaults(func=add_knowledge)
    update = sub.add_parser("update")
    update.add_argument("--domain", required=True)
    update.add_argument("--old", required=True)
    update.add_argument("--text", required=True)
    update.add_argument("--anchor", required=True)
    update.add_argument("--heading", choices=TOPIC_SECTIONS[:2], required=True)
    update.set_defaults(func=update_knowledge)
    move = sub.add_parser("move")
    move.add_argument("--from-domain", required=True)
    move.add_argument("--to-domain", required=True)
    move.add_argument("--text", required=True)
    move.add_argument("--heading", choices=TOPIC_SECTIONS[:2], required=True)
    move.set_defaults(func=move_knowledge)
    maintenance = sub.add_parser("maintenance-receipt")
    maintenance.add_argument("--path", action="append", required=True)
    maintenance.add_argument("--reason", required=True)
    maintenance.set_defaults(func=maintenance_receipt)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--strict", action="store_true")
    audit_parser.add_argument("--output")
    audit_parser.set_defaults(func=audit_command)
    sub.add_parser("check").set_defaults(func=check)
    sub.add_parser("check-transactions").set_defaults(func=transaction_check)
    sub.add_parser("self-test").set_defaults(func=lambda _args: self_test())
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (KnowledgeError, OSError, json.JSONDecodeError) as exc:
        print(f"project knowledge failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
