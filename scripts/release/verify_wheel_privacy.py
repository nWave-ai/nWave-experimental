"""Verify a built wheel (or wheel tree) contains no private artifact.

The wheel-privacy gate (RCA Fix 1 hardening) — the release-pipeline check
that would have caught the nwave_ai-3.15.1 IP leak. It inspects a wheel
tree, loads the catalog allow-list (the privacy SSOT), and reports every
``public: false`` agent file and every privately-owned skill directory
that survived into the package.

This is the verification counterpart of ``strip_private_agents.strip``:
the strip removes private work, this gate detects-if-present. It reuses
the catalog-reading logic in ``scripts.shared.agent_catalog`` rather than
re-deriving the public/private partition.

Usage::

    python scripts/release/verify_wheel_privacy.py <wheel-or-tree>

``verify`` returns a list of privacy-violation strings (empty == clean).
"""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path


# Ensure project root is in sys.path for standalone CLI invocation
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.shared.agent_catalog import (  # noqa: E402
    CatalogNotFoundError,
    CatalogParseError,
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    is_public_skill,
    load_public_agents,
)


def _verify_tree(tree: Path) -> list[str]:
    """Return the list of private artifacts found in the wheel.

    Empty list == the wheel is clean. A non-empty list fails the gate.

    Args:
        wheel_or_tree: path to a directory tree containing an ``nWave/``
            subdirectory.

    Returns:
        list of violation strings (one per leaked private artifact).
    """
    nwave_dir = tree / "nWave"
    if not nwave_dir.is_dir():
        return ["unverifiable wheel layout: missing nWave/"]

    # Fail-closed: a missing or corrupt catalog raises CatalogNotFoundError /
    # CatalogParseError — the gate cannot prove the wheel is clean, so it
    # must report the unverifiable catalog as a violation and refuse the
    # wheel, never silently pass (and never crash with a traceback).
    try:
        public_agents = load_public_agents(nwave_dir, strict=True)
    except (CatalogNotFoundError, CatalogParseError, RuntimeError) as exc:
        return [f"unverifiable catalog: {exc}"]
    if not public_agents:
        return ["unverifiable catalog: no public agents"]

    violations: list[str] = []

    agents_dir = nwave_dir / "agents"
    skills_dir = nwave_dir / "skills"

    if not agents_dir.is_dir():
        violations.append("unverifiable wheel layout: missing nWave/agents/")
    else:
        for agent_file in sorted(agents_dir.glob("nw-*.md")):
            if not is_public_agent(agent_file.name, public_agents):
                violations.append(f"private agent: nWave/agents/{agent_file.name}")

    if not skills_dir.is_dir():
        violations.append("unverifiable wheel layout: missing nWave/skills/")
    else:
        ownership_map = build_ownership_map(agents_dir)
        command_skills = detect_command_skills(skills_dir)
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or not skill_dir.name.startswith("nw-"):
                continue
            if not is_public_skill(
                skill_dir.name,
                public_agents,
                ownership_map=ownership_map,
                command_skills=command_skills,
            ):
                violations.append(f"private skill: nWave/skills/{skill_dir.name}")

    return violations


def _extract_archive(archive: Path, destination: Path) -> str | None:
    """Extract a ZIP archive without accepting paths outside ``destination``."""
    try:
        with zipfile.ZipFile(archive) as contents:
            destination_root = destination.resolve()
            for member in contents.infolist():
                if (
                    not (destination / member.filename)
                    .resolve()
                    .is_relative_to(destination_root)
                ):
                    return f"unsafe archive member: {member.filename}"
            contents.extractall(destination)
    except (OSError, zipfile.BadZipFile) as exc:
        return f"unreadable archive: {exc}"
    return None


def verify(wheel_or_tree: Path) -> list[str]:
    """Return private-artifact violations for an extracted wheel or wheel ZIP."""
    target = Path(wheel_or_tree)
    if target.is_dir():
        return _verify_tree(target)
    if not target.is_file():
        return [f"missing wheel or tree: {target}"]

    with tempfile.TemporaryDirectory(prefix="nwave-wheel-") as temporary_dir:
        extraction_error = _extract_archive(target, Path(temporary_dir))
        if extraction_error:
            return [extraction_error]
        return _verify_tree(Path(temporary_dir))


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <wheel-or-tree>", file=sys.stderr)
        sys.exit(1)

    violations = verify(Path(sys.argv[1]))
    if violations:
        print(f"FAIL: {len(violations)} private artifact(s) in the wheel:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)

    print("PASS: wheel carries no private artifact")


if __name__ == "__main__":
    main()
