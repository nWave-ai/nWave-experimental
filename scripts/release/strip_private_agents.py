"""Strip private agents and skills from a target directory.

Uses the agent catalog SSOT (``framework-catalog.yaml``) to determine
which agents are public. Everything NOT in the public allow-list is
removed -- this is **fail-closed** by design: uncatalogued agents are
stripped rather than leaked.

Skills are stripped using the ownership map derived from agent
frontmatter. A skill is kept only if at least one of its owning
agents is public.

Usage::

    python scripts/release/strip_private_agents.py <target-dir>

``<target-dir>`` is the root of the rsynced public repo clone
(contains ``nWave/`` subdirectory).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


# Ensure project root is in sys.path for standalone CLI invocation
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import yaml  # noqa: E402

from scripts.shared.agent_catalog import (  # noqa: E402
    detect_command_skills,
    is_public_agent,
    is_public_skill,
    load_public_agents,
    normalize_agent_name,
)


class FrontmatterParseError(ValueError):
    """Raised when agent frontmatter cannot be parsed during skill stripping."""


def _strip_catalog(catalog_path: Path, public_agents: set[str]) -> int:
    """Remove non-public agent entries from the catalog YAML.

    Also strips their command entries if present. Returns the number
    of entries removed.
    """
    with catalog_path.open(encoding="utf-8") as fh:
        catalog = yaml.safe_load(fh)

    count = 0

    # Strip from agents section: keep only public
    agents = catalog.get("agents", {})
    for name in list(agents):
        if name not in public_agents:
            del agents[name]
            count += 1

    # Strip from commands section (commands referencing non-public agents)
    commands = catalog.get("commands", {})
    for cmd_name in list(commands):
        cmd = commands[cmd_name]
        cmd_agents = cmd.get("agents") or []
        non_public = [a for a in cmd_agents if a not in public_agents]
        if non_public:
            if len(non_public) == len(cmd_agents):
                del commands[cmd_name]
                count += 1
            else:
                cmd["agents"] = [a for a in cmd_agents if a in public_agents]

    with catalog_path.open("w", encoding="utf-8") as fh:
        yaml.dump(catalog, fh, default_flow_style=False, sort_keys=False)

    return count


def _strip_reference_docs(target_dir: Path, non_public_agents: set[str]) -> list[str]:
    """Remove generated reference docs for non-public agents.

    Deletes individual agent doc files and scrubs index files
    (``docs/reference/agents/index.md``, ``docs/reference/skills/index.md``).
    """
    removed: list[str] = []
    ref_agents_dir = target_dir / "docs" / "reference" / "agents"
    ref_skills_index = target_dir / "docs" / "reference" / "skills" / "index.md"

    # Build set of all names to match (agent + reviewer variants)
    private_names: set[str] = set()
    for name in non_public_agents:
        private_names.add(name)
        private_names.add(f"{name}-reviewer")

    # Delete individual agent reference files
    if ref_agents_dir.exists():
        for name in sorted(private_names):
            doc_file = ref_agents_dir / f"nw-{name}.md"
            if doc_file.exists():
                doc_file.unlink()
                removed.append(str(doc_file.relative_to(target_dir)))

        # Scrub agent index: remove lines referencing non-public agents
        agent_index = ref_agents_dir / "index.md"
        if agent_index.exists():
            _scrub_index_file(agent_index, private_names)
            removed.append(f"scrubbed {agent_index.relative_to(target_dir)}")

    # Scrub skills index: remove sections for non-public agents
    if ref_skills_index.exists():
        _scrub_index_file(ref_skills_index, private_names)
        removed.append(f"scrubbed {ref_skills_index.relative_to(target_dir)}")

    # Scrub public reviewer docs that link to private skill paths
    if ref_agents_dir.exists():
        for reviewer_doc in sorted(ref_agents_dir.glob("nw-*-reviewer.md")):
            _scrub_private_links(reviewer_doc, private_names)

    return removed


def _scrub_index_file(index_path: Path, private_names: set[str]) -> None:
    """Remove lines from an index file that reference private agents."""
    content = index_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    filtered: list[str] = []
    skip_section = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##") and any(
            f"nw-{name}" in stripped for name in private_names
        ):
            skip_section = True
            continue

        if skip_section and stripped.startswith("##"):
            skip_section = False

        if skip_section:
            continue

        if any(f"nw-{name}" in line or f"/{name}" in line for name in private_names):
            continue

        filtered.append(line)

    index_path.write_text("".join(filtered), encoding="utf-8")


def _scrub_private_links(doc_path: Path, private_names: set[str]) -> None:
    """Remove lines containing links to private skill directories."""
    content = doc_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    filtered = [
        line
        for line in lines
        if not any(f"skills/{name}/" in line for name in private_names)
    ]
    if len(filtered) != len(lines):
        doc_path.write_text("".join(filtered), encoding="utf-8")


def _build_ownership_map_strict(agents_dir: Path) -> dict[str, set[str]]:
    """Build ownership map with strict parsing -- raises on corrupted frontmatter.

    Unlike the shared ``build_ownership_map()`` which silently skips
    corrupt files, this version raises ``FrontmatterParseError`` to
    prevent silent data loss during stripping.
    """
    if not agents_dir.exists():
        return {}

    ownership: dict[str, set[str]] = {}

    for agent_file in sorted(agents_dir.glob("nw-*.md")):
        agent_name = agent_file.stem.removeprefix("nw-")
        text = agent_file.read_text(encoding="utf-8")

        if not text.startswith("---"):
            continue

        end = text.find("---", 3)
        if end == -1:
            continue

        try:
            frontmatter = yaml.safe_load(text[3:end])
        except Exception as exc:
            msg = f"Corrupted frontmatter in {agent_file.name}: {exc}"
            raise FrontmatterParseError(msg) from exc

        if frontmatter is None or not isinstance(frontmatter, dict):
            continue

        skills = frontmatter.get("skills")
        if not isinstance(skills, list):
            continue

        for skill in skills:
            skill_key = skill if skill.startswith("nw-") else f"nw-{skill}"
            ownership.setdefault(skill_key, set()).add(agent_name)

    return ownership


def strip(target_dir: Path) -> dict[str, list[str]]:
    """Remove non-public agent files and skill dirs from *target_dir*.

    Uses the allow-list approach: only agents in the public set from
    ``framework-catalog.yaml`` are kept. Everything else (private and
    uncatalogued) is stripped.

    Raises ``CatalogNotFoundError`` if the catalog file is missing.

    Returns a dict with ``agents``, ``skills``, ``docs``, and ``catalog``
    keys listing removed paths (relative to *target_dir*).
    """
    nwave_dir = target_dir / "nWave"

    # Fail-closed: raises CatalogNotFoundError if catalog missing
    public_agents = load_public_agents(nwave_dir, strict=True)

    removed: dict[str, list[str]] = {
        "agents": [],
        "skills": [],
        "docs": [],
        "catalog": [],
    }

    agents_dir = nwave_dir / "agents"
    skills_dir = nwave_dir / "skills"

    # 1. Build ownership map (strict -- fails on corrupted frontmatter)
    ownership_map = _build_ownership_map_strict(agents_dir)
    command_skills = detect_command_skills(skills_dir)

    # 2. Strip agent files: remove anything NOT in public allow-list
    non_public_agents: set[str] = set()
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("nw-*.md")):
            if not is_public_agent(agent_file.name, public_agents):
                agent_file.unlink()
                removed["agents"].append(str(agent_file.relative_to(target_dir)))
                name = normalize_agent_name(agent_file.name)
                non_public_agents.add(name)

    # 3. Strip skill directories using ownership map
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not skill_dir.name.startswith("nw-"):
                continue
            if not is_public_skill(
                skill_dir.name,
                public_agents,
                ownership_map=ownership_map,
                command_skills=command_skills,
            ):
                shutil.rmtree(skill_dir)
                removed["skills"].append(str(skill_dir.relative_to(target_dir)))

    # 4. Strip reference documentation
    removed["docs"] = _strip_reference_docs(target_dir, non_public_agents)

    # 5. Strip catalog entries
    catalog_path = nwave_dir / "framework-catalog.yaml"
    catalog_count = _strip_catalog(catalog_path, public_agents)
    if catalog_count:
        removed["catalog"].append(
            f"{catalog_count} entries from framework-catalog.yaml"
        )

    # Summary
    total = (
        len(removed["agents"])
        + len(removed["skills"])
        + len(removed["docs"])
        + catalog_count
    )
    print(f"Stripped {total} private items:")
    for category, paths in removed.items():
        for p in paths:
            print(f"  [{category}] {p}")

    return removed


def verify_strip(target_dir: Path) -> list[str]:
    """Verify that only public agents remain after stripping.

    Returns an empty list if verification passes, or a list of error
    messages describing unexpected agents found.
    """
    nwave_dir = target_dir / "nWave"
    public_agents = load_public_agents(nwave_dir, strict=True)

    agents_dir = nwave_dir / "agents"
    errors: list[str] = []

    if not agents_dir.exists():
        return errors

    for agent_file in sorted(agents_dir.glob("nw-*.md")):
        if not is_public_agent(agent_file.name, public_agents):
            errors.append(f"Unexpected agent after strip: {agent_file.name}")

    return errors


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <target-dir>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.is_dir():
        print(f"ERROR: not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    strip(target)


if __name__ == "__main__":
    main()
