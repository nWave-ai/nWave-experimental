#!/usr/bin/env python3
"""Validate the few framework-template properties with mechanical value."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Expose src/ so `des` resolves under bare python3: this runs as a pre-commit
# hook with `language: system`, outside the uv venv, where the package is not
# importable by name. Guarded on existence: src/ is a dev-repo path, and this
# script never ships (absent from build_dist.py UTILITY_SCRIPTS and from both
# wheel force-include maps), so no installed layout reaches this branch.
_project_src = str(Path(__file__).resolve().parents[2] / "src")
if Path(_project_src).is_dir() and _project_src not in sys.path:
    sys.path.insert(0, _project_src)

from des.domain.agent_capability import (  # noqa: E402
    provider_tool_name,
    split_declared_tools,
)


@dataclass
class Finding:
    rule_id: str
    severity: str
    file: str
    message: str


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    def add(self, rule_id: str, file: str, message: str) -> None:
        self.findings.append(Finding(rule_id, "error", file, message))


def _load_yaml():
    try:
        import yaml
    except ModuleNotFoundError as exc:
        print("ERROR: PyYAML unavailable under this interpreter.", file=sys.stderr)
        raise SystemExit(2) from exc
    return yaml


def parse_frontmatter(filepath: Path) -> tuple[dict[str, object] | None, str]:
    """Return valid YAML frontmatter and the remaining Markdown body."""
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return None, content
    end = content.find("\n---\n", 4)
    if end < 0:
        return None, content
    try:
        frontmatter = _load_yaml().safe_load(content[4:end])
    except Exception:
        return None, content
    if not isinstance(frontmatter, dict):
        return None, content
    return frontmatter, content[end + 5 :]


def _frontmatter_or_error(
    filepath: Path, rule: str, result: ValidationResult
) -> tuple[dict[str, object] | None, str]:
    frontmatter, body = parse_frontmatter(filepath)
    if frontmatter is None:
        result.add(rule, filepath.stem, "Missing or invalid YAML frontmatter")
    return frontmatter, body


def _require_description(
    frontmatter: dict[str, object], rule: str, name: str, result: ValidationResult
) -> None:
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        result.add(rule, name, "Missing or empty description")


def validate_agent(filepath: Path, result: ValidationResult) -> None:
    """Validate identity, description, and reviewer write isolation."""
    name = filepath.stem
    frontmatter, _ = _frontmatter_or_error(filepath, "A01", result)
    if frontmatter is None:
        return
    if frontmatter.get("name") != name:
        result.add("A02", name, "Frontmatter name does not match filename")
    _require_description(frontmatter, "A04", name, result)
    if name.endswith("-reviewer"):
        tools = frontmatter.get("tools", "")
        granted = (
            {provider_tool_name(entry) for entry in split_declared_tools(tools)}
            if isinstance(tools, str)
            else set()
        )
        for forbidden in ("Write", "Edit"):
            if forbidden in granted:
                result.add("A12", name, f"Reviewer has forbidden tool: {forbidden}")


def validate_skill(filepath: Path, result: ValidationResult) -> None:
    """Validate stable frontmatter identity and description."""
    is_nw_skill = filepath.name == "SKILL.md" and filepath.parent.name.startswith("nw-")
    name = filepath.parent.name if is_nw_skill else filepath.stem
    frontmatter, _ = _frontmatter_or_error(filepath, "S01", result)
    if frontmatter is None:
        return
    declared_name = frontmatter.get("name")
    expected_bare = name.removeprefix("nw-")
    if is_nw_skill:
        matches_identity = declared_name in (name, expected_bare) or (
            isinstance(declared_name, str)
            and expected_bare.endswith(f"-{declared_name}")
        )
    else:
        matches_identity = declared_name == name
    if not matches_identity:
        result.add("S02", name, "Frontmatter name does not match skill identity")
    _require_description(frontmatter, "S04", name, result)


def validate_command(filepath: Path, result: ValidationResult) -> None:
    """Validate command frontmatter and its filesystem identity."""
    name = filepath.stem
    frontmatter, _ = _frontmatter_or_error(filepath, "C01", result)
    if frontmatter is None:
        return
    _require_description(frontmatter, "C02", name, result)
    if not re.fullmatch(r"[a-z][a-z0-9-]+", name):
        result.add("C12", name, "Filename is not kebab-case")


def validate_cross_references(project_root: Path, result: ValidationResult) -> None:
    """Ensure every skill declared by an agent exists in the skills tree."""
    skills_dir = project_root / "nWave" / "skills"
    available = {
        skill_file.parent.name if skill_file.name == "SKILL.md" else skill_file.stem
        for skill_file in skills_dir.glob("**/*.md")
    }
    available |= {name.removeprefix("nw-") for name in available}
    for agent_file in sorted((project_root / "nWave" / "agents").glob("nw-*.md")):
        frontmatter, _ = parse_frontmatter(agent_file)
        if frontmatter is None:
            continue
        skills = frontmatter.get("skills", [])
        if not isinstance(skills, list):
            result.add("X02", agent_file.stem, "Declared skills must be a list")
            continue
        for skill in skills:
            if not isinstance(skill, str) or skill not in available:
                result.add("X02", agent_file.stem, f"Skill '{skill}' is not present")


#: An executable directive that routes a role through the Skill tool. Prose
#: that merely names a skill is not one: only this shape reaches the tool.
_SKILL_INVOCATION_RE = re.compile(r"\bSkill\((nw-[a-z0-9-]+)\)")


def _uninvocable_skills(project_root: Path) -> set[str]:
    """Skills the Skill tool cannot reach, read from their own frontmatter."""
    uninvocable = set()
    for skill_file in sorted((project_root / "nWave" / "skills").glob("*/SKILL.md")):
        frontmatter, _ = parse_frontmatter(skill_file)
        if frontmatter and frontmatter.get("disable-model-invocation") is True:
            uninvocable.add(skill_file.parent.name)
    return uninvocable


def validate_invocability(project_root: Path, result: ValidationResult) -> None:
    """Reject a shipped spec that instructs invoking an unreachable skill.

    A role that reaches such a trigger stalls: the Skill tool refuses and the
    spec offers no fallback, so the wave stops mid-delivery. docgen renders the
    right verb for every GENERATED region, which leaves two routes into this
    state -- a hand-edited spec, and a region never re-rendered after its target
    gained the flag. Both land here."""
    uninvocable = _uninvocable_skills(project_root)
    if not uninvocable:
        return
    specs = [
        *sorted((project_root / "nWave" / "agents").glob("*.md")),
        *sorted((project_root / "nWave" / "tasks" / "nw").glob("*.md")),
        *sorted((project_root / "nWave" / "skills").glob("**/*.md")),
    ]
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        for target in sorted(set(_SKILL_INVOCATION_RE.findall(text))):
            if target not in uninvocable:
                continue
            result.add(
                "X03",
                spec.stem if spec.name != "SKILL.md" else spec.parent.name,
                f"instructs Invoke Skill({target}), but {target} carries "
                "disable-model-invocation: true, so the Skill tool cannot reach "
                "it and the role stalls at that trigger with no fallback. "
                f"If {target} is knowledge, the directive must instead READ "
                f"`~/.claude/skills/{target}/SKILL.md` -- inside a "
                "GENERATED:role-skill-loading region run `python "
                "scripts/docgen.py` and it renders that verb from the target's "
                f"own frontmatter. If {target} is a procedure this role must "
                "execute, drop disable-model-invocation from its frontmatter.",
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate nWave template identity and cross-references."
    )
    parser.add_argument("--project-root", type=Path, default=Path())
    parser.add_argument("--agents-only", action="store_true")
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--commands-only", action="store_true")
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    result = ValidationResult()
    selected = not (args.agents_only or args.skills_only or args.commands_only)
    agents = sorted((project_root / "nWave" / "agents").glob("nw-*.md"))
    skills = sorted((project_root / "nWave" / "skills").glob("**/*.md"))
    commands = sorted((project_root / "nWave" / "tasks" / "nw").glob("*.md"))
    if selected or args.agents_only:
        for agent in agents:
            validate_agent(agent, result)
    if selected or args.skills_only:
        for skill in skills:
            validate_skill(skill, result)
    if selected or args.commands_only:
        for command in commands:
            validate_command(command, result)
    if selected:
        validate_cross_references(project_root, result)
        validate_invocability(project_root, result)
    print(
        f"Validated: {len(agents)} agents, {len(skills)} skills, {len(commands)} commands"
    )
    for finding in result.errors:
        print(f"  [ERROR] {finding.rule_id} {finding.file}: {finding.message}")
    if result.errors:
        print(f"FAILED: {len(result.errors)} error(s)")
        return 1
    print("PASSED: all checks clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
