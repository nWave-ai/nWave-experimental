"""Validate that every skill referenced by a public artifact survives the strip.

The dangling-reference class recurs because skill references live in THREE
channels — an agent's declared frontmatter ``skills:`` list, free-text
``skills/nw-*/SKILL.md`` body mentions, and native executable
``Invoke Skill(nw-*)`` calls. Distribution ownership is the union
centralized by build_ownership_map: frontmatter plus role-skill-loading
conditional ownership. A public artifact can still reference a skill that
neither ownership channel captures; the strip then drops it as orphan
work, and the public package ships with a dangling skill reference.

This validator closes the loop: it scans every PUBLIC artifact (public
agents + public skills) for skill references in all channels, and flags
any referenced skill the privacy strip would remove.

Usage::

    python scripts/validation/validate_skill_references.py <nwave-dir>

``check_references`` returns a list of dangling-reference strings
(empty == every public-artifact skill reference survives).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# Ensure project root is in sys.path for standalone CLI invocation
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


from scripts.shared.agent_catalog import (  # noqa: E402
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    is_public_skill,
    load_public_agents,
)


# Matches free-text body references of the form ``skills/nw-foo/SKILL.md``.
_BODY_SKILL_REFERENCE = re.compile(r"skills/(nw-[a-z0-9-]+)/SKILL\.md")

# Matches exact native executable references of the form
# ``Invoke Skill(nw-foo)``. Placeholder names such as ``nw-{skill-name}``
# contain characters outside ``[a-z0-9-]`` and so never match -- they are
# template text, not an executable reference to a real skill.
_INVOKE_SKILL_REFERENCE = re.compile(r"Invoke Skill\((nw-[a-z0-9-]+)\)")


def _read_text(path: Path) -> str:
    """Read a file, returning an empty string on any OS error."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _frontmatter_skills(text: str) -> list[str]:
    """Extract the declared ``skills:`` list from markdown frontmatter."""
    if not text.startswith("---"):
        return []
    end = text.find("---", 3)
    if end == -1:
        return []
    try:
        import yaml

        frontmatter = yaml.safe_load(text[3:end])
    except Exception:
        return []
    if not isinstance(frontmatter, dict):
        return []
    skills = frontmatter.get("skills")
    if not isinstance(skills, list):
        return []
    return [str(s) for s in skills]


def _referenced_skills(text: str) -> set[str]:
    """Collect nw-prefixed skill names referenced in ALL channels.

    Channel 1: declared frontmatter ``skills:`` list.
    Channel 2: free-text body mentions of ``skills/nw-*/SKILL.md``.
    Channel 3: native executable ``Invoke Skill(nw-*)`` calls.
    """
    referenced: set[str] = set()
    for skill in _frontmatter_skills(text):
        referenced.add(skill if skill.startswith("nw-") else f"nw-{skill}")
    for match in _BODY_SKILL_REFERENCE.findall(text):
        referenced.add(match)
    for match in _INVOKE_SKILL_REFERENCE.findall(text):
        referenced.add(match)
    return referenced


def check_references(nwave_dir: Path) -> list[str]:
    """Return public artifacts whose referenced skills are missing or would be stripped.

    Empty list == every skill referenced by a public agent or public skill
    exists on disk AND survives the privacy strip. A non-empty entry names
    the referrer and either the nonexistent skill it names or the
    strippable skill it depends on.

    Args:
        nwave_dir: the ``nWave/`` directory (contains ``agents/`` +
            ``skills/`` + ``framework-catalog.yaml``).

    Returns:
        list of dangling-reference strings, sorted.
    """
    agents_dir = nwave_dir / "agents"
    skills_dir = nwave_dir / "skills"

    public_agents = load_public_agents(nwave_dir, strict=True)
    ownership_map = build_ownership_map(agents_dir)
    command_skills = detect_command_skills(skills_dir)

    def survives_strip(skill_name: str) -> bool:
        return is_public_skill(
            skill_name,
            public_agents,
            ownership_map=ownership_map,
            command_skills=command_skills,
        )

    existing_skills: set[str] = set()
    if skills_dir.exists():
        existing_skills = {
            child.name
            for child in skills_dir.iterdir()
            if child.is_dir() and child.name.startswith("nw-")
        }

    dangling: list[str] = []

    # --- Channel: public agents ------------------------------------------
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("nw-*.md")):
            if not is_public_agent(agent_file.name, public_agents):
                continue
            text = _read_text(agent_file)
            for skill in sorted(_referenced_skills(text)):
                if skill not in existing_skills:
                    dangling.append(
                        f"public agent {agent_file.name} references skill "
                        f"{skill} which does not exist"
                    )
                    continue
                if not survives_strip(skill):
                    dangling.append(
                        f"public agent {agent_file.name} references skill "
                        f"{skill} which the release strip removes"
                    )

    # --- Channel: public skills ------------------------------------------
    if skills_dir.exists():
        for skill_dir in sorted(existing_skills):
            if not survives_strip(skill_dir):
                continue
            skill_file = skills_dir / skill_dir / "SKILL.md"
            text = _read_text(skill_file)
            for skill in sorted(_referenced_skills(text)):
                if skill == skill_dir:
                    continue
                if skill not in existing_skills:
                    dangling.append(
                        f"public skill {skill_dir} references skill "
                        f"{skill} which does not exist"
                    )
                    continue
                if not survives_strip(skill):
                    dangling.append(
                        f"public skill {skill_dir} references skill "
                        f"{skill} which the release strip removes"
                    )

    return sorted(dangling)


def check_frontmatter_completeness(nwave_dir: Path) -> list[str]:
    """Return agents whose ownership omits a skill they LOAD in body text.

    An agent that references ``skills/nw-X/SKILL.md`` in its body (its
    loading-table / load instruction) but does not own ``nw-X`` through
    either channel -- its frontmatter ``skills:`` list (eager preload) or
    the ``role-skill-loading.yaml`` registry (conditional on-demand/phase
    use, folded in by ``build_ownership_map``) -- is drifted: a
    loaded-but-unowned skill ships incompletely. The union-based
    ``check_references`` MISSES this class (the body reference itself
    counts as satisfying the reference). Empty == every loaded skill is
    owned via one of the two channels; a non-empty entry names the agent +
    the missing skill.
    """
    agents_dir = nwave_dir / "agents"
    skills_dir = nwave_dir / "skills"
    if not agents_dir.exists():
        return []
    existing_skills: set[str] = set()
    if skills_dir.exists():
        existing_skills = {
            child.name
            for child in skills_dir.iterdir()
            if child.is_dir() and child.name.startswith("nw-")
        }

    ownership_map = build_ownership_map(agents_dir)

    drift: list[str] = []
    for agent_file in sorted(agents_dir.glob("nw-*.md")):
        agent_name = agent_file.stem.removeprefix("nw-")
        text = _read_text(agent_file)
        owned = {
            skill for skill, owners in ownership_map.items() if agent_name in owners
        }
        loaded = {
            m for m in _BODY_SKILL_REFERENCE.findall(text) if m in existing_skills
        }
        for missing in sorted(loaded - owned):
            drift.append(
                f"agent {agent_file.name} loads skill {missing} via a "
                f"skills/{missing}/SKILL.md reference but it is not owned "
                f"via frontmatter skills: or the role-skill-loading.yaml registry"
            )
    return sorted(drift)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <nwave-dir>", file=sys.stderr)
        sys.exit(1)

    nwave_dir = Path(sys.argv[1])
    if not nwave_dir.is_dir():
        print(f"ERROR: not a directory: {nwave_dir}", file=sys.stderr)
        sys.exit(1)

    failures = check_references(nwave_dir) + check_frontmatter_completeness(nwave_dir)
    if failures:
        print(f"FAIL: {len(failures)} skill-reference issue(s):")
        for entry in failures:
            print(f"  - {entry}")
        sys.exit(1)

    print(
        "PASS: every public-artifact skill reference survives the strip AND "
        "every loaded skill is owned via frontmatter or the role-skill "
        "registry"
    )


if __name__ == "__main__":
    main()
