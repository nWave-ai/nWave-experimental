"""Test-side composition for slice-02: arrange a feature-delta, drive the spine CLI.

slice-02 of sustainable-test-suite — the SECTION SCHEMA (DDD-3) + its output-contract
registration (DDD-11). Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine
entry `des validate-feature-delta --require-registry-sections distill --format=json`
invoked as a real subprocess. The subprocess IS the SUT — NO production module is
imported and called at the step boundary. The feature-delta fixtures are written to a
hermetic tmp_path; the check runs against the REAL `nWave/waves/distill.yaml` registry
(the default --waves-dir), because DDD-11 registration lives in that real SSOT file.

`des`/`git` are never required by the assertions themselves — the assertions read a JSON
verdict token + exit code from the subprocess; Python + filesystem only.

Active-RED: at HEAD the real `distill.yaml` does NOT register the canonical sustainability
section, so the check emits `undeclared-section` (exit 1). Every scenario asserts the
post-registration `accepted` behaviour, so each fails for the right reason
(MISSING_FUNCTIONALITY — the section is not yet a declared output) with a clean
AssertionError, not an ImportError. DELIVER makes them GREEN by ADDING the ref_section to
distill.yaml.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .slice_02_domain_types import (
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    CANONICAL_SECTION_ID,
    Verdict,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


# The repo root the spine resolves against — this file lives at
# tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so parents[6] is the
# repo root (steps[0] acceptance[1] sustainable-test-suite[2] acceptance[3] des[4]
# tests[5] repo[6]). The subprocess runs with cwd=repo-root so `python -m des` and the
# default --waves-dir (the real nWave/waves) resolve exactly as in production.
_REPO_ROOT = Path(__file__).resolve().parents[6]
_LIVE_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"


@dataclass(frozen=True)
class CliResult:
    """The observable surface of a `des validate-feature-delta` subprocess call."""

    exit_code: int
    stdout: str
    stderr: str

    def verdict_payload(self) -> dict[str, object]:
        """Parse the last JSON object from stdout (the `--format=json` verdict).

        The spine prefixes an unrelated freshness JSON line in a developer checkout;
        the verdict is the LAST JSON object. Parse line-by-line, keep the last that
        decodes to a mapping carrying a `verdict` key.
        """
        payload: dict[str, object] | None = None
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "verdict" in obj:
                payload = obj
        assert payload is not None, (
            f"no JSON verdict object on stdout; got {self.stdout!r} (stderr {self.stderr!r})"
        )
        return payload


def _run(args: Sequence[str]) -> CliResult:
    proc = subprocess.run(
        [sys.executable, "-m", "des", "validate-feature-delta", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return CliResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _canonical_section_block() -> str:
    """A schema-shaped sustainability section: heading + 5 fixed columns + one row.

    This is the SCHEMA (DDD-3) the slice-02 author produces. slice-02 only requires the
    section be RECOGNISED as a declared output; the slice-03 content gate (NOT here)
    validates the rows. One CREATE_NEW row with a sufficiently-long justification keeps
    the section well-formed for downstream gates without depending on slice-03 logic.
    """
    header = "| " + " | ".join(CANONICAL_SECTION_COLUMNS) + " |"
    separator = "|" + "|".join(["---"] * len(CANONICAL_SECTION_COLUMNS)) + "|"
    row = (
        "| the generic framework engine | nWave/data/test-dsl/engine.py | "
        "no prior engine | CREATE_NEW | "
        "the keystone engine does not exist and is authored once for all targets |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", header, separator, row])


_MINIMAL_DELTA = """# Feature Delta: slice-02 fixture

## Wave: DISTILL / [REF] {section_id}

{section_block}
"""


# A delta carrying the FULL set of DISTILL [REF] sections the live registry already
# declares (so the new section composes WITHOUT regressing the existing eight), PLUS the
# new canonical sustainability section.
_EXISTING_DISTILL_REF_SECTIONS: tuple[str, ...] = (
    "Wave-Decision Reconciliation",
    "Scenario List with Tags",
    "WS Strategy",
    "Adapter Coverage Table",
    "Scaffolds",
    "Test Placement",
    "Driving Adapter Coverage",
    "Pre-requisites",
)


def _complete_delta() -> str:
    lines = ["# Feature Delta: slice-02 complete fixture", ""]
    for section in _EXISTING_DISTILL_REF_SECTIONS:
        lines.append(f"## Wave: DISTILL / [REF] {section}")
        lines.append("")
        lines.append(f"(content for {section})")
        lines.append("")
    lines.append(f"## Wave: DISTILL / [REF] {CANONICAL_SECTION_ID}")
    lines.append("")
    lines.append(_canonical_section_block())
    lines.append("")
    return "\n".join(lines)


class SectionSchemaDriver:
    """Test-side driving facade over the spine registry-section subprocess (the SUT).

    Arranges a feature-delta on tmp_path that DECLARES the canonical sustainability
    section under DISTILL, runs the live-registry check as a real subprocess, and exposes
    the closed verdict token + exit code for assertion. Also exposes the live-registry
    declaration directly (the section's output-contract identity, DDD-11) so the schema's
    canonical id is pinned against the real SSOT.
    """

    def __init__(self) -> None:
        self._delta_path: Path | None = None
        self._result: CliResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_delta_declaring_sustainability_section(self, tmp_path: Path) -> None:
        path = tmp_path / "feature-delta.md"
        path.write_text(
            _MINIMAL_DELTA.format(
                section_id=CANONICAL_SECTION_ID,
                section_block=_canonical_section_block(),
            ),
            encoding="utf-8",
        )
        self._delta_path = path

    def given_complete_delta_with_sustainability_section(self, tmp_path: Path) -> None:
        path = tmp_path / "feature-delta.md"
        path.write_text(_complete_delta(), encoding="utf-8")
        self._delta_path = path

    # -- act (When) ----------------------------------------------------------

    def when_registry_section_check_runs(self) -> None:
        assert self._delta_path is not None, "no feature-delta was arranged"
        self._result = _run(
            [
                "--require-registry-sections",
                "distill",
                "--format=json",
                str(self._delta_path),
            ]
        )

    # -- assert (Then) -------------------------------------------------------

    def then_check_accepts(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert payload["verdict"] == Verdict.ACCEPTED.value, (
            "the live DISTILL registry must accept a feature-delta declaring the "
            f"canonical sustainability section; got {payload!r} (exit {result.exit_code})"
        )
        assert result.exit_code == 0, (
            f"accepted verdict must exit 0; got exit {result.exit_code}, {payload!r}"
        )

    def then_section_recognised_as_declared_output(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        # A recognised section is NOT reported as undeclared, and the canonical id is
        # NOT named as an offender in the detail (DDD-11: it is a declared output).
        assert payload["verdict"] != Verdict.UNDECLARED_SECTION.value, (
            f"the sustainability section must be a declared DISTILL output; got {payload!r}"
        )
        detail = str(payload.get("detail", ""))
        assert CANONICAL_SECTION_ID not in detail or "does not declare" not in detail, (
            f"the section must not be flagged undeclared; detail {detail!r}"
        )

    def then_live_registry_declares_canonical_section_id(self) -> None:
        """Pin the SCHEMA's canonical id against the REAL distill.yaml registry (DDD-11).

        Reads the live registry text and asserts the EXACT canonical id appears as a
        `- id:` entry. This proves the schema id the author writes is the SAME id the
        output-contract registers — a near-miss heading would not be a declared output.
        At HEAD the id is absent → RED; DELIVER adds it.
        """
        registry = (_LIVE_WAVES_DIR / "distill.yaml").read_text(encoding="utf-8")
        needle = f"- id: {CANONICAL_SECTION_ID}"
        assert needle in registry, (
            "the live DISTILL output-contract registry "
            f"({_LIVE_WAVES_DIR / 'distill.yaml'}) must declare the canonical "
            f"sustainability section by its exact id ({needle!r}); it is not yet "
            "registered (DDD-11 not applied)"
        )

    # -- internals -----------------------------------------------------------

    def _require_result(self) -> CliResult:
        assert self._result is not None, "the registry-section check was not run"
        return self._result
