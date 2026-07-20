"""Regression AT (driving-port level): `des validate-feature-delta
--require-prefactoring-assessment` (fix-slice-third-phase-commit-only,
CHANGE 2).

The sibling `test_prefactoring_assessment_gate.py` covers the pure-function
core (`validate_prefactoring_assessment_content`) directly. This file drives
the REAL CLI EDGE `des.cli.validate_feature_delta.main` IN-PROCESS (P1-P4
in-process active-RED pattern, `nw-distill-red-scaffolding`) via
`des.cli.__main__`'s `validate-feature-delta --require-prefactoring-assessment`
subcommand -- the same driving surface `test_validate_feature_delta_routes_
to_doctor.py` uses for its sibling `--require-reuse-analysis` gate -- against
fixture feature-delta files written to `tmp_path`, exercising the flag
parsing + file I/O + verdict-printing path the pure-function test cannot
reach on its own (Driving-Port-Only Boundary mandate).

Covers the three cases named in the crafter dispatch, plus the scoping
boundary and the skip-requires-justification floor:

  1. Section absent / empty / a bare "not applicable" (no justification) on
     a DESIGN-having feature-delta -- REJECT (non-zero exit,
     `missing-prefactoring-assessment` / `unmotivated-prefactoring-assessment`).
  2. A justified NONE (names what was examined + why the shape fits) --
     ACCEPT (exit 0, `prefactoring-assessment-accepted`).
  3. A `@prefactoring` slice reference -- ACCEPT (exit 0,
     `prefactoring-assessment-accepted`).
  4. No `## Wave: DESIGN` section at all -- the gate is scoped out, ACCEPT
     regardless of whether a Prefactoring Assessment section is present
     (exit 0, `prefactoring-not-required`).

RED-for-right-reason (verified manually, see crafter's commit message and
the sibling pure-function AT's docstring): `--require-prefactoring-assessment`
did not exist as a CLI flag before CHANGE 2 -- `_parse_args` rejected it as
an unrecognized flag (malformed invocation, exit 1 with the `_USAGE` string
on stderr), never a crash unrelated to the defect. Re-confirmed empirically
in this authoring session (see Phase 3 report) by temporarily swapping in
the pre-fix `validate_feature_delta.py` and re-running this file.

covers: fix-slice-third-phase-commit-only (CHANGE 2)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.validate_feature_delta import (
    VERDICT_MISSING_PREFACTORING_ASSESSMENT,
    VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED,
    VERDICT_PREFACTORING_NOT_REQUIRED,
    VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
)
from tests.common.in_process_cli import run_cli_in_process


_DESIGN_HEADING = "## Wave: DESIGN / [REF] Architecture\n\nSome architecture text.\n"
_TRAILING_SECTION = "\n## Wave: DISCUSS / [REF] Slice Plan\n\n| Slice |\n|-------|\n"


def _design_delta(prefactoring_body: str | None) -> str:
    """A minimal feature-delta carrying `## Wave: DESIGN`, optionally
    followed by a `## Prefactoring Assessment` section carrying `body`.
    `prefactoring_body=None` omits the section heading entirely."""
    text = _DESIGN_HEADING
    if prefactoring_body is not None:
        text += f"\n## Prefactoring Assessment\n\n{prefactoring_body}\n"
    return text + _TRAILING_SECTION


def _run_require_prefactoring_assessment(target: Path) -> tuple[int, str, str]:
    """Drive the real `des validate-feature-delta
    --require-prefactoring-assessment` CLI EDGE IN-PROCESS (no interpreter
    fork) -- the in-process analogue of `python -m des.cli.__main__
    validate-feature-delta --require-prefactoring-assessment --format=json
    <path>`."""
    return run_cli_in_process(
        [
            "validate-feature-delta",
            "--require-prefactoring-assessment",
            "--format=json",
            str(target),
        ],
        cwd=target.parent,
    )


# ---------------------------------------------------------------------------
# REJECT cases -- absent / empty / bare "not applicable"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case_name", "prefactoring_body", "expected_verdict"),
    [
        (
            "absent",
            None,
            VERDICT_MISSING_PREFACTORING_ASSESSMENT,
        ),
        (
            "empty",
            "",
            VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
        ),
        (
            "bare_not_applicable",
            "Not applicable.",
            VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
        ),
    ],
)
def test_unjustified_prefactoring_assessment_is_rejected(
    tmp_path: Path, case_name: str, prefactoring_body: str | None, expected_verdict: str
) -> None:
    """A DESIGN-having feature-delta whose Prefactoring Assessment is absent,
    empty, or a bare unmotivated dismissal is REJECTED via the real CLI edge
    (non-zero exit, the specific verdict named in the JSON payload)."""
    target = tmp_path / "feature-delta.md"
    target.write_text(_design_delta(prefactoring_body), encoding="utf-8")

    exit_code, stdout, stderr = _run_require_prefactoring_assessment(target)

    assert exit_code != 0, (
        f"case={case_name!r}: expected a non-zero exit for an unjustified "
        f"Prefactoring Assessment; got exit_code=0. stdout={stdout!r} "
        f"stderr={stderr!r}"
    )
    assert expected_verdict in stdout, (
        f"case={case_name!r}: expected verdict {expected_verdict!r} in "
        f"stdout -- got stdout={stdout!r} stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# ACCEPT cases -- justified NONE, @prefactoring slice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case_name", "prefactoring_body"),
    [
        (
            "justified_none",
            "**NONE -- justified.** This feature extends `FooPort` at its "
            "EXISTING generic seam with no shape compromise; no component is "
            "bent into an unnatural shape to receive this feature.",
        ),
        (
            "prefactoring_slice_recorded",
            "A dedicated `@prefactoring` slice-00 extends `FooPort` to accept "
            "the new parameter before slice-01 begins, avoiding a mid-feature "
            "shape change.",
        ),
    ],
)
def test_justified_prefactoring_assessment_is_accepted(
    tmp_path: Path, case_name: str, prefactoring_body: str
) -> None:
    """A DESIGN-having feature-delta whose Prefactoring Assessment is a
    justified NONE, or names a `@prefactoring` slice doing the reshaping
    work, is ACCEPTED via the real CLI edge (exit 0, `prefactoring-
    assessment-accepted` in the JSON payload)."""
    target = tmp_path / "feature-delta.md"
    target.write_text(_design_delta(prefactoring_body), encoding="utf-8")

    exit_code, stdout, stderr = _run_require_prefactoring_assessment(target)

    assert exit_code == 0, (
        f"case={case_name!r}: expected exit 0 for a justified Prefactoring "
        f"Assessment; got exit_code={exit_code}. stdout={stdout!r} "
        f"stderr={stderr!r}"
    )
    assert VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED in stdout, (
        f"case={case_name!r}: expected verdict "
        f"{VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED!r} in stdout -- got "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# Scoping boundary -- no DESIGN wave section, gate is a no-op ACCEPT
# ---------------------------------------------------------------------------


def test_no_design_wave_scopes_the_gate_out_via_cli(tmp_path: Path) -> None:
    """A feature-delta with no `## Wave: DESIGN` section has nothing to
    assess -- the CLI edge exits 0 with `prefactoring-not-required`,
    regardless of the (absent) Prefactoring Assessment section."""
    target = tmp_path / "feature-delta.md"
    target.write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n| Slice |\n|---|\n",
        encoding="utf-8",
    )

    exit_code, stdout, stderr = _run_require_prefactoring_assessment(target)

    assert exit_code == 0, (
        f"expected exit 0 for a DESIGN-skipped feature-delta (scoping "
        f"no-op); got exit_code={exit_code}. stdout={stdout!r} "
        f"stderr={stderr!r}"
    )
    assert VERDICT_PREFACTORING_NOT_REQUIRED in stdout, (
        f"expected verdict {VERDICT_PREFACTORING_NOT_REQUIRED!r} in stdout "
        f"-- got stdout={stdout!r} stderr={stderr!r}"
    )
