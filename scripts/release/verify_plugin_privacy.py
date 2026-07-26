"""Fail closed when a final plugin ZIP contains private agents or skills."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.release.verify_wheel_privacy import _extract_archive  # noqa: E402
from scripts.shared.agent_catalog import (  # noqa: E402
    CatalogNotFoundError,
    CatalogParseError,
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    is_public_skill,
    load_public_agents,
)


def verify_tree(plugin_dir: Path, catalog_dir: Path) -> list[str]:
    """Return violations in an extracted plugin using its matching catalog."""
    try:
        public_agents = load_public_agents(catalog_dir, strict=True)
    except (CatalogNotFoundError, CatalogParseError, RuntimeError) as exc:
        return [f"unverifiable catalog: {exc}"]
    if not public_agents:
        return ["unverifiable catalog: no public agents"]

    violations: list[str] = []
    agents_dir = plugin_dir / "agents"
    skills_dir = plugin_dir / "skills"
    if not agents_dir.is_dir():
        violations.append("unverifiable plugin layout: missing agents/")
    else:
        for agent_file in sorted(agents_dir.glob("nw-*.md")):
            if not is_public_agent(agent_file.name, public_agents):
                violations.append(f"private agent: agents/{agent_file.name}")
    if not skills_dir.is_dir():
        violations.append("unverifiable plugin layout: missing skills/")
    else:
        ownership_map = build_ownership_map(catalog_dir / "agents")
        command_skills = detect_command_skills(skills_dir)
        for skill_dir in sorted(skills_dir.iterdir()):
            if (
                skill_dir.is_dir()
                and skill_dir.name.startswith("nw-")
                and not is_public_skill(
                    skill_dir.name,
                    public_agents,
                    ownership_map=ownership_map,
                    command_skills=command_skills,
                )
            ):
                violations.append(f"private skill: skills/{skill_dir.name}")
    return violations


def verify(plugin_zip: Path, catalog_root: Path | None = None) -> list[str]:
    """Return privacy violations in a plugin ZIP, using the checked-out catalog."""
    catalog_dir = (catalog_root or Path.cwd()) / "nWave"
    with tempfile.TemporaryDirectory(prefix="nwave-plugin-") as temporary_dir:
        plugin_dir = Path(temporary_dir)
        extraction_error = _extract_archive(Path(plugin_zip), plugin_dir)
        if extraction_error:
            return [extraction_error]
        return verify_tree(plugin_dir, catalog_dir)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <plugin-zip>", file=sys.stderr)
        sys.exit(1)
    violations = verify(Path(sys.argv[1]))
    if violations:
        print(
            "FAIL: plugin carries private or unverifiable artifacts:", file=sys.stderr
        )
        print("\n".join(f"  {item}" for item in violations), file=sys.stderr)
        sys.exit(1)
    print("PASS: plugin carries no private artifact")


if __name__ == "__main__":
    main()
