#!/usr/bin/env python3
"""Audit skill files: catalog, detect collisions, map cross-references.

Scans nWave/skills/ directories and agent frontmatter to produce a JSON
report with:
- Full skill catalog with agent ownership
- Naming collisions across agent groups (with content hashes)
- Cross-agent skill references
- Orphan skills (not referenced by any agent)

Usage:
    python scripts/validation/audit_skills.py [SKILLS_DIR] [AGENTS_DIR]
    python scripts/validation/audit_skills.py nWave/skills/ nWave/agents/
"""

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


# Standalone-script bootstrap: invoked as `python3 scripts/...`, repo root not
# on sys.path by default. Prepend it so the `scripts.shared` SSOT helper resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.shared.frontmatter import parse_frontmatter_file


def _parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file (delegates to shared SSOT)."""
    metadata, _body = parse_frontmatter_file(filepath)
    return metadata


def _content_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content."""
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def catalog_skills(skills_dir: Path) -> list[dict]:
    """Catalog all skill .md files under skills_dir with agent group ownership.

    Supports two layouts:
    - Agent-grouped: skills/{agent-group}/{skill-name}.md
      skill_name = file stem, agent_group = directory name
    - nw-prefixed flat: skills/nw-{skill-name}/SKILL.md
      skill_name = directory name, agent_group = directory name

    Returns a list of dicts with keys: skill_name, agent_group, file_path.
    """
    catalog = []
    if not skills_dir.is_dir():
        return catalog

    for group_dir in sorted(skills_dir.iterdir()):
        if not group_dir.is_dir():
            continue
        agent_group = group_dir.name

        # nw-prefixed directories use SKILL.md as the canonical filename;
        # the skill identity is the directory name itself.
        if agent_group.startswith("nw-"):
            skill_file = group_dir / "SKILL.md"
            if skill_file.exists():
                catalog.append(
                    {
                        "skill_name": agent_group,
                        "agent_group": agent_group,
                        "file_path": str(skill_file),
                    }
                )
            continue

        for skill_file in sorted(group_dir.glob("*.md")):
            catalog.append(
                {
                    "skill_name": skill_file.stem,
                    "agent_group": agent_group,
                    "file_path": str(skill_file),
                }
            )

    return catalog


def detect_collisions(catalog: list[dict]) -> dict[str, list[dict]]:
    """Detect skill names that appear in multiple agent groups.

    Returns a dict mapping collision skill_name to list of entries,
    each with agent_group, file_path, and content_hash.
    Only includes names found in 2+ groups.
    """
    by_name: dict[str, list[dict]] = defaultdict(list)

    for entry in catalog:
        by_name[entry["skill_name"]].append(entry)

    collisions = {}
    for skill_name, entries in by_name.items():
        groups = {e["agent_group"] for e in entries}
        if len(groups) >= 2:
            collisions[skill_name] = [
                {
                    "agent_group": e["agent_group"],
                    "file_path": e["file_path"],
                    "content_hash": _content_hash(Path(e["file_path"])),
                }
                for e in entries
            ]

    return collisions


def _agent_name_to_group(agent_name: str) -> str:
    """Derive skill group name from agent name (strip 'nw-' prefix)."""
    if agent_name.startswith("nw-"):
        return agent_name[3:]
    return agent_name


def _get_agent_skills(agents_dir: Path) -> list[dict]:
    """Parse all agent frontmatter and extract skill references.

    Returns list of dicts with keys: agent, skills (list of str).
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
                agents.append(
                    {
                        "agent": fm.get("name", agent_file.stem),
                        "skills": skill_names,
                    }
                )

    return agents


def map_cross_references(catalog: list[dict], agents_dir: Path) -> list[dict]:
    """Identify cross-agent skill references.

    A cross-reference occurs when an agent lists a skill in its frontmatter
    that does not exist in its own skill group directory but does exist in
    another group's directory.

    Returns list of dicts with: agent, skill, owner_group.
    """
    # Build lookup: skill_name -> set of groups that have it
    skill_owners: dict[str, set[str]] = defaultdict(set)
    for entry in catalog:
        skill_owners[entry["skill_name"]].add(entry["agent_group"])

    agent_data = _get_agent_skills(agents_dir)
    cross_refs = []

    for agent_info in agent_data:
        agent_name = agent_info["agent"]
        own_group = _agent_name_to_group(agent_name)

        for skill in agent_info["skills"]:
            if skill not in skill_owners:
                continue
            owners = skill_owners[skill]
            if own_group not in owners:
                # This skill is not in the agent's own group -- cross-reference
                for owner_group in sorted(owners):
                    cross_refs.append(
                        {
                            "agent": agent_name,
                            "skill": skill,
                            "owner_group": owner_group,
                        }
                    )

    return cross_refs


def detect_orphans(catalog: list[dict], agents_dir: Path) -> list[dict]:
    """Detect skill files not referenced by any agent frontmatter.

    Returns list of dicts with: skill_name, agent_group, file_path.
    """
    agent_data = _get_agent_skills(agents_dir)

    # Collect all skill names referenced by any agent
    referenced: set[str] = set()
    for agent_info in agent_data:
        referenced.update(agent_info["skills"])

    orphans = []
    for entry in catalog:
        if entry["skill_name"] not in referenced:
            orphans.append(
                {
                    "skill_name": entry["skill_name"],
                    "agent_group": entry["agent_group"],
                    "file_path": entry["file_path"],
                }
            )

    return orphans


def audit_skills(skills_dir: Path, agents_dir: Path) -> dict:
    """Run full skill audit and return structured report.

    Returns dict with keys: skills, collisions, cross_references, orphans.
    """
    catalog = catalog_skills(skills_dir)
    collisions = detect_collisions(catalog)
    cross_refs = map_cross_references(catalog, agents_dir)
    orphans = detect_orphans(catalog, agents_dir)

    return {
        "skills": catalog,
        "collisions": collisions,
        "cross_references": cross_refs,
        "orphans": orphans,
    }


def main() -> int:
    """Main entry point. Outputs JSON report to stdout."""
    if len(sys.argv) >= 3:
        skills_dir = Path(sys.argv[1])
        agents_dir = Path(sys.argv[2])
    else:
        # Default to nWave directories relative to cwd
        skills_dir = Path("nWave/skills")
        agents_dir = Path("nWave/agents")

    if not skills_dir.is_dir():
        print(f"ERROR: Skills directory not found: {skills_dir}", file=sys.stderr)
        return 1

    if not agents_dir.is_dir():
        print(f"ERROR: Agents directory not found: {agents_dir}", file=sys.stderr)
        return 1

    report = audit_skills(skills_dir, agents_dir)

    # Summary to stderr
    print(
        f"Cataloged {len(report['skills'])} skills, "
        f"{len(report['collisions'])} collision groups, "
        f"{len(report['cross_references'])} cross-references, "
        f"{len(report['orphans'])} orphans",
        file=sys.stderr,
    )

    # Full report to stdout
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
