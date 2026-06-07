#!/usr/bin/env python3
"""Validate skill-agent mapping consistency.

Cross-references agent frontmatter skill lists against nWave/skills/
directories. Detects:
- Broken references: agent declares skill that has no matching directory
- Orphan directories: skill directory exists but no agent references it
- Naming violations: skill directories without the required nw- prefix

Exit codes:
    0: All mappings valid (warnings may exist for orphans)
    1: Broken references or naming violations found

Usage:
    python scripts/validation/validate_skill_agent_mapping.py
    python scripts/validation/validate_skill_agent_mapping.py --project-root /path/to/repo
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Standalone-script bootstrap: this file is invoked as `python3 scripts/...`,
# so the repo root is not on sys.path by default. Prepend it so the
# `scripts.shared` SSOT helper resolves both locally and in CI.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.shared.frontmatter import parse_frontmatter_file


@dataclass
class ValidationResult:
    """Result of skill-agent mapping validation."""

    exit_code: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file (delegates to shared SSOT)."""
    metadata, _body = parse_frontmatter_file(filepath)
    return metadata


def _get_agent_skill_refs(agents_dir: Path) -> list[tuple[str, list[str]]]:
    """Parse all agent frontmatter and extract skill references.

    Returns list of (agent_name, skill_names) tuples.
    """
    agents = []
    if not agents_dir.is_dir():
        return agents

    for agent_file in sorted(agents_dir.glob("nw-*.md")):
        fm = _parse_frontmatter(agent_file)
        if fm and "skills" in fm:
            raw_skills = fm["skills"]
            if isinstance(raw_skills, list):
                skill_names = [s for s in raw_skills if isinstance(s, str)]
                agent_name = fm.get("name", agent_file.stem)
                agents.append((agent_name, skill_names))

    return agents


def _get_skill_directories(skills_dir: Path) -> set[str]:
    """Get all directory names under the skills directory."""
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir()}


def validate(project_root: Path) -> ValidationResult:
    """Validate skill-agent mapping consistency.

    Checks:
    1. Every agent skill reference has a matching nw-prefixed directory
    2. Every skill directory is referenced by at least one agent (warn if not)
    3. All skill directories start with nw- prefix

    Returns ValidationResult with exit_code, errors, and warnings.
    """
    result = ValidationResult()

    agents_dir = project_root / "nWave" / "agents"
    skills_dir = project_root / "nWave" / "skills"

    # Get all skill directories
    skill_dirs = _get_skill_directories(skills_dir)

    # Get all agent skill references
    agent_refs = _get_agent_skill_refs(agents_dir)

    # Check 1: Naming convention -- all dirs must start with nw-
    for dir_name in sorted(skill_dirs):
        if not dir_name.startswith("nw-"):
            result.errors.append(
                f"Naming violation: directory '{dir_name}' does not start "
                f"with required 'nw-' prefix"
            )
            result.exit_code = 1

    # Check 2: Broken references -- agent references non-existent directory
    all_referenced: set[str] = set()
    for agent_name, skill_names in agent_refs:
        for skill_name in skill_names:
            all_referenced.add(skill_name)
            if skill_name not in skill_dirs:
                result.errors.append(
                    f"Broken reference: agent '{agent_name}' references "
                    f"skill '{skill_name}' but no matching directory exists"
                )
                result.exit_code = 1

    # Check 3: Orphan directories -- directory not referenced by any agent
    for dir_name in sorted(skill_dirs):
        if dir_name not in all_referenced:
            result.warnings.append(
                f"Orphan skill: directory '{dir_name}' is not referenced by any agent"
            )

    return result


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="Validate skill-agent mapping consistency."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(),
        help="Project root directory (default: current directory)",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()

    agents_dir = project_root / "nWave" / "agents"
    skills_dir = project_root / "nWave" / "skills"

    if not agents_dir.is_dir():
        print(f"ERROR: Agents directory not found: {agents_dir}")
        return 1

    if not skills_dir.is_dir():
        print(f"ERROR: Skills directory not found: {skills_dir}")
        return 1

    result = validate(project_root)

    # Report errors
    if result.errors:
        print(f"FAILED: {len(result.errors)} error(s) found:")
        for error in result.errors:
            print(f"  - {error}")

    # Report warnings
    if result.warnings:
        print(f"\nWARNING: {len(result.warnings)} orphan skill(s):")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.exit_code == 0:
        if result.warnings:
            print("\nPASSED with warnings")
        else:
            print("PASSED: All skill-agent mappings are consistent")

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
