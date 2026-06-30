"""Test-side composition for slice-03: arrange a feature-delta, drive the spine CLI.

slice-03 of sustainable-test-suite — the MECHANICAL CONTENT VALIDATION gate (DDD-2).
Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --format=json` invoked as a real
subprocess. The subprocess IS the SUT — NO production module is imported and called at
the step boundary. The feature-delta fixtures are written to a hermetic tmp_path.

`des`/`git` are never required by the assertions themselves — the assertions read a JSON
verdict token + exit code from the subprocess; Python + filesystem only (slice-03 is
git-free section-content validation).

Active-RED: at HEAD `des validate-feature-delta` has NO `--require-sustainability` mode
(`_parse_args` rejects the unknown flag → `main` prints usage to stderr + exit 1, no JSON
on stdout). Each scenario asserts a post-implementation verdict token, so
`verdict_payload()` raises AssertionError (no JSON verdict object on stdout) — a clean
MISSING_FUNCTIONALITY signal, not an ImportError. DELIVER makes them GREEN by adding
`validate_sustainability_content` + the `--require-sustainability` mode (a mirror of the
shipped `validate_reuse_analysis_content` + `--require-reuse-analysis`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .slice_03_domain_types import (
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    METHODOLOGY_EXEMPT_MARKER,
    Verdict,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


# The repo root the spine resolves against — this file lives at
# tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so parents[6] is the
# repo root. The subprocess runs with cwd=repo-root so `python -m des` resolves exactly
# as in production.
_REPO_ROOT = Path(__file__).resolve().parents[6]


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

        Active-RED at HEAD: with no `--require-sustainability` mode the subprocess emits
        no JSON verdict, so this assertion fires (MISSING_FUNCTIONALITY) — the right
        reason, not an ImportError.
        """
        payload: dict[str, object] | None = None
        for raw in self.stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "verdict" in obj:
                payload = obj
        assert payload is not None, (
            "no JSON verdict object on stdout — the "
            "`des validate-feature-delta --require-sustainability` content gate is not "
            f"yet implemented (MISSING_FUNCTIONALITY); got stdout {self.stdout!r} "
            f"(exit {self.exit_code}, stderr {self.stderr!r})"
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


# ---------------------------------------------------------------------------
# Section-block builders — the SCHEMA the maintainer authors (DDD-3, 5 columns).
# These are the test-arrangement fixtures, NOT production code. Each builder
# produces a feature-delta body the slice-03 content gate must classify.
# ---------------------------------------------------------------------------

_HEADER_ROW = "| " + " | ".join(CANONICAL_SECTION_COLUMNS) + " |"
_SEPARATOR_ROW = "|" + "|".join(["---"] * len(CANONICAL_SECTION_COLUMNS)) + "|"


def _delta_with_section(section_block: str) -> str:
    return (
        "# Feature Delta: slice-03 fixture\n\n"
        "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
        f"{section_block}\n"
    )


def _well_formed_section() -> str:
    """A schema-valid section: canonical heading + 5 columns + a justified row."""
    row = (
        "| the registry-section subprocess idiom "
        "| tests/des/acceptance/feature_delta_section_schema/steps/composition.py "
        "| the Layer-3 subprocess + closed-verdict assertion shape "
        "| REUSE "
        "| reuses the proven subprocess-driving and JSON-verdict-parse pattern |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", _HEADER_ROW, _SEPARATOR_ROW, row])


def _wrong_columns_section() -> str:
    """A section whose table header is NOT the canonical five columns (malformed)."""
    bad_header = "| Test | File | Decision |"
    bad_separator = "|---|---|---|"
    row = "| something | some/path.py | REUSE |"
    return "\n".join([CANONICAL_SECTION_HEADING, "", bad_header, bad_separator, row])


def _unjustified_create_new_section() -> str:
    """A CREATE_NEW row with an EMPTY Justification cell (unjustified-create-new)."""
    row = (
        "| a brand new helper "
        "| tests/des/acceptance/sustainable-test-suite/new_helper.py "
        "| no prior helper "
        "| CREATE_NEW "
        "|  |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", _HEADER_ROW, _SEPARATOR_ROW, row])


def _methodology_exempt_section() -> str:
    """A section carrying ONLY the DDD-9 methodology-exempt marker (no populated rows)."""
    return "\n".join([CANONICAL_SECTION_HEADING, "", METHODOLOGY_EXEMPT_MARKER])


class SustainabilityGateDriver:
    """Test-side driving facade over the spine content-gate subprocess (the SUT).

    Arranges a feature-delta on tmp_path whose `## Test Reuse & Consolidation Analysis`
    section is well-formed / malformed / unjustified / absent / exempt, runs the
    `--require-sustainability` content check as a real subprocess, and exposes the closed
    verdict token + exit code for assertion. git-free section-content validation only.
    """

    def __init__(self) -> None:
        self._delta_path: Path | None = None
        self._result: CliResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_well_formed_section(self, tmp_path: Path) -> None:
        self._write_delta(tmp_path, _delta_with_section(_well_formed_section()))

    def given_no_section(self, tmp_path: Path) -> None:
        body = "# Feature Delta: slice-03 fixture\n\n## Wave: DISTILL / [REF] WS Strategy\n\nStrategy C.\n"
        self._write_delta(tmp_path, body)

    def given_wrong_columns_section(self, tmp_path: Path) -> None:
        self._write_delta(tmp_path, _delta_with_section(_wrong_columns_section()))

    def given_unjustified_create_new_section(self, tmp_path: Path) -> None:
        self._write_delta(
            tmp_path, _delta_with_section(_unjustified_create_new_section())
        )

    def given_methodology_exempt_section(self, tmp_path: Path) -> None:
        self._write_delta(tmp_path, _delta_with_section(_methodology_exempt_section()))

    # -- act (When) ----------------------------------------------------------

    def when_content_check_runs(self) -> None:
        assert self._delta_path is not None, "no feature-delta was arranged"
        self._result = _run(
            ["--require-sustainability", "--format=json", str(self._delta_path)]
        )

    # -- assert (Then) -------------------------------------------------------

    def then_accepts(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code == 0, (
            "an accepted sustainability section must exit 0; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_rejects(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code != 0, (
            "a rejected sustainability section must exit non-zero; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_verdict_is(self, expected: Verdict) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert payload["verdict"] == expected.value, (
            f"the content gate must emit the {expected.value!r} verdict for this "
            f"feature-delta; got {payload!r} (exit {result.exit_code})"
        )

    # -- internals -----------------------------------------------------------

    def _write_delta(self, tmp_path: Path, body: str) -> None:
        path = tmp_path / "feature-delta.md"
        path.write_text(body, encoding="utf-8")
        self._delta_path = path

    def _require_result(self) -> CliResult:
        assert self._result is not None, "the sustainability content check was not run"
        return self._result
