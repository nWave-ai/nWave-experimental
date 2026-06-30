"""Environmental e2e gate wiring verifier (slice-04, fix-oss-env-e2e-gate).

The CREATE-NEW arch test layer for residuality R3 + R10: statically asserts
the `verify_environmental_e2e` gate is wired into the floor at both wiring
points:

  (a) Registered in `pyproject.toml` `[project.scripts]` -- the shipped
      command set SSOT. R3 (`verify_environmental_e2e` CLI not shipped =
      F-11 recursion).
  (b) Named in the `## Feature-End Cycle` section of
      `nWave/skills/nw-deliver/SKILL.md` -- the load-bearing skill-doc that
      prescribes the DELIVER feature-end orchestration step. R10 (the
      feature-end cycle runs but its env-e2e sub-step is silently removed).

The grep for (b) is **scoped to the feature-end-cycle section** (between the
`## Feature-End Cycle` heading and the next `##`/`###`), NOT anywhere in the
~600-line file -- a token outside the bounded section does not count
(residuality RES-1). Grep is necessary-not-sufficient (cannot catch semantic
reorder), paired with the behavioural heartbeat enforcement in
`subagent_stop_handler._missing_feature_end_cycle_records` (RES-2).

Pure function -- callers pass the two paths in. Used by the build-tier arch
test `tests/build/test_environmental_gate_wiring.py` against the real repo,
and by the slice-04 acceptance composition against a corruptible fixture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


# Stdlib-only at import time -- the DES bundle (`scripts/des/` in installed
# plugins) is stdlib-only by contract (tests/build/acceptance/plugin/
# milestone-2-des-bundle.feature: "DES module works without external
# packages"). Pyproject parsing uses regex over the `[project.scripts]`
# section shape, NOT tomllib (which is 3.11+, would need a 3.10 fallback,
# and tomli substring-matches the bundle's stdlib-only guard).

GATE_TOKEN = "verify_environmental_e2e"
GATE_CONSOLE_SCRIPT_NAME = "verify-environmental-e2e"
FEATURE_END_CYCLE_HEADING_PATTERN = re.compile(
    r"^###?\s+Feature-End Cycle\b", re.MULTILINE
)
NEXT_SECTION_PATTERN = re.compile(r"^###?\s+\S", re.MULTILINE)
PROJECT_SCRIPTS_HEADER_PATTERN = re.compile(r"^\[project\.scripts\]\s*$", re.MULTILINE)
NEXT_TOML_SECTION_PATTERN = re.compile(r"^\[", re.MULTILINE)


@dataclass(frozen=True)
class WiringCheckResult:
    """Outcome of the gate-wiring check; both wiring points are reported."""

    passed: bool
    diagnostic: str


def verify_environmental_gate_wiring(
    pyproject_path: Path, deliver_skill_path: Path
) -> WiringCheckResult:
    """Assert the environmental e2e gate is wired into the floor at both points.

    Returns `passed=True, diagnostic=""` when both checks hold; otherwise
    `passed=False, diagnostic=<which wiring point lost the gate>`. The
    diagnostic NAMES the wiring point so a failure surfaces actionable
    repair guidance (residuality RM-1: fail-closed + named-fault).
    """
    project_scripts_ok, scripts_diagnostic = _check_project_scripts(pyproject_path)
    skill_section_ok, skill_diagnostic = _check_skill_feature_end_cycle_section(
        deliver_skill_path
    )
    if project_scripts_ok and skill_section_ok:
        return WiringCheckResult(passed=True, diagnostic="")
    parts: list[str] = []
    if not project_scripts_ok:
        parts.append(scripts_diagnostic)
    if not skill_section_ok:
        parts.append(skill_diagnostic)
    return WiringCheckResult(passed=False, diagnostic=" ; ".join(parts))


def _check_project_scripts(pyproject_path: Path) -> tuple[bool, str]:
    """Whether `verify-environmental-e2e` is declared in `[project.scripts]`.

    Regex-scans the `[project.scripts]` section text rather than parsing TOML
    so the DES bundle stays stdlib-only (the bundle scan in
    `tests/build/acceptance/plugin/milestone-2-des-bundle.feature` forbids
    importing `toml`/`tomli`, and `tomllib` is 3.11+ which would force a
    `tomli` fallback for 3.10 -- both substring-trip the guard).
    """
    text = pyproject_path.read_text(encoding="utf-8")
    section = _extract_project_scripts_section(text)
    if section is not None:
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                f"{GATE_CONSOLE_SCRIPT_NAME} "
            ) or stripped.startswith(f"{GATE_CONSOLE_SCRIPT_NAME}="):
                return True, ""
    return (
        False,
        f"gate console script '{GATE_CONSOLE_SCRIPT_NAME}' is missing from "
        f"pyproject.toml [project.scripts] -- the gate is no longer in the "
        f"shipped command set",
    )


def _extract_project_scripts_section(text: str) -> str | None:
    """Return the `[project.scripts]` section body, or None if absent."""
    header_match = PROJECT_SCRIPTS_HEADER_PATTERN.search(text)
    if header_match is None:
        return None
    section_start = header_match.end()
    next_section_match = NEXT_TOML_SECTION_PATTERN.search(text, section_start)
    section_end = (
        next_section_match.start() if next_section_match is not None else len(text)
    )
    return text[section_start:section_end]


def _check_skill_feature_end_cycle_section(
    deliver_skill_path: Path,
) -> tuple[bool, str]:
    """Whether the gate token is present within the bounded feature-end-cycle section."""
    text = deliver_skill_path.read_text(encoding="utf-8")
    section = _extract_feature_end_cycle_section(text)
    if section is None:
        return (
            False,
            "nw-deliver SKILL.md is missing the '## Feature-End Cycle' "
            "section -- the load-bearing skill-doc no longer prescribes "
            "the feature-end orchestration step the gate floor wires into",
        )
    if GATE_TOKEN in section:
        return True, ""
    return (
        False,
        f"gate token '{GATE_TOKEN}' is missing from the '## Feature-End "
        f"Cycle' section of nw-deliver SKILL.md -- the feature-end "
        f"orchestration step no longer names the gate",
    )


def _extract_feature_end_cycle_section(text: str) -> str | None:
    """Return the bounded `## Feature-End Cycle` section text, or None if absent."""
    heading_match = FEATURE_END_CYCLE_HEADING_PATTERN.search(text)
    if heading_match is None:
        return None
    section_start = heading_match.end()
    next_section_match = NEXT_SECTION_PATTERN.search(text, section_start)
    section_end = (
        next_section_match.start() if next_section_match is not None else len(text)
    )
    return text[section_start:section_end]
