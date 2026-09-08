#!/usr/bin/env python3
"""Skill-agent mapping: real validation for two checks, a declared CENSUS
for a third.

Cross-references agent frontmatter skill lists against nWave/skills/
directories.

VALIDATED (a genuine defect, exit 1):
- Broken references: agent declares skill that has no matching directory
- Naming violations: skill directories without the required nw- prefix

CENSUSED, not validated (exit 0 always, never a verdict):
- Orphan directories: skill directory exists but no agent's frontmatter
  `skills:` list references it. An orphan is not, by itself, evidence of
  a defect: a skill can be load-bearing through a command body, a parent
  skill's routing table, or another agent's prose body -- channels this
  scanner cannot see, because it only reads frontmatter. Measured
  2026-08-24 (`docs/analysis/2026-08-24-decisione-gate-skill-orfane.md`):
  a 10-skill sample of the unexplained orphans found roughly half
  genuinely load-bearing through one of those channels, and roughly half
  a real defect (the `nw-fp-{language}` family, same class as the
  `nw-tlaplus-verification` gap the census in that document traces end
  to end). Failing this build on the raw orphan count would have frozen
  the real defects as accepted debt nobody had ever looked at -- the
  exact risk that document was written to avoid. This is therefore a
  DELIBERATE choice, not a forgotten TODO: F-SKILL-MAPPING-GATE-WARNS-
  NEVER-FAILS (backlog) names the follow-up -- triage the unexplained
  orphans and fix or delete what the triage finds. Never re-derive that
  decision from first principles here; read the document.

`PUBLIC_SHARED_SKILLS` (`scripts/shared/agent_catalog.py`) is the known
allow-list of orphans already explained by a non-frontmatter load path.
The census reports the split (explained / unexplained) so the residue
that still needs a look is visible at a glance, never buried in a raw
count.

Exit codes:
    0: no broken reference or naming violation (an orphan count, if any,
       is a census line, never a reason to fail by itself)
    1: broken reference(s) or naming violation(s) found -- a real defect

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

from scripts.shared.agent_catalog import PUBLIC_SHARED_SKILLS
from scripts.shared.frontmatter import parse_frontmatter_file


@dataclass
class ValidationResult:
    """Result of skill-agent mapping validation.

    `warnings` keeps its existing formatted-line shape (callers/tests that
    already read orphan text from it are unaffected). `orphan_directories`
    and `total_skill_directories` are the plain data `main()`'s census
    needs to cross-reference against `PUBLIC_SHARED_SKILLS` -- parsing
    directory names back out of a formatted warning string would be
    fragile where a clean field is not.
    """

    exit_code: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    orphan_directories: list[str] = field(default_factory=list)
    total_skill_directories: int = 0


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
    result.total_skill_directories = len(skill_dirs)

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

    # Check 3: Orphan directories -- directory not referenced by any agent.
    # A census line, never a defect by itself -- see the module docstring.
    for dir_name in sorted(skill_dirs):
        if dir_name not in all_referenced:
            result.orphan_directories.append(dir_name)
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

    # Report errors -- a real defect, this branch is a verdict and stays one.
    if result.errors:
        print(f"FAILED: {len(result.errors)} error(s) found:")
        for error in result.errors:
            print(f"  - {error}")

    # Report the orphan list itself, unchanged shape (existing readers of
    # this text are unaffected).
    if result.warnings:
        print(f"\nWARNING: {len(result.warnings)} orphan skill(s):")
        for warning in result.warnings:
            print(f"  - {warning}")

    # CENSUS line -- deliberately never says PASSED/OK/GREEN. This branch
    # reports what was MEASURED, not a property that was evaluated and
    # held: see the module docstring and docs/analysis/2026-08-24-
    # decisione-gate-skill-orfane.md for why. Only reached when errors is
    # empty (exit_code == 0 in that case, by construction of `validate`).
    if not result.errors:
        explained = sorted(set(result.orphan_directories) & PUBLIC_SHARED_SKILLS)
        unexplained = sorted(set(result.orphan_directories) - PUBLIC_SHARED_SKILLS)
        print(
            f"\nMEASURED: {result.total_skill_directories} skill(s) under "
            f"nWave/skills/; {len(result.orphan_directories)} without a "
            "resolvable owner in any agent's frontmatter `skills:` list "
            f"({len(explained)} explained by PUBLIC_SHARED_SKILLS, "
            f"{len(unexplained)} unexplained). This is a census, not a "
            "verdict -- no error means no broken reference or naming "
            "violation, never that the unexplained count is fine."
        )

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
