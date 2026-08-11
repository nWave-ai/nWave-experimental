"""Regression: wire the Prefactoring Assessment validator into the TWO
enforcement surfaces that never consulted it -- it shipped
(`validate_prefactoring_assessment_content` +
`--require-prefactoring-assessment`, `src/des/cli/validate_feature_delta.py`,
commits 8fd3f2b40/beff813fe/6818e71b3) but stayed opt-in: no gate called it
automatically, so a DESIGN-having feature-delta with no Prefactoring
Assessment section sailed through every dispatch untouched -- catalogued,
never wired.

THE FIX this test targets (crafter's job, not implemented here):

  1. `des verify-readiness-pre-dispatch` gains an 8th, REFUSING invariant
     `prefactoring_assessment` -- mirrors invariant 6 (`reuse_first_or_design_
     skip`, `_check_reuse_first_or_design_skip`) byte-for-byte in shape,
     INCLUDING its Design-Skipped witness fallback: `_feature_delta_has_
     design_wave` (inside the pure validator) matches the `## Wave: DESIGN`
     SUBSTRING, which a Design-Skipped delta's own `## Wave: DESIGN / [REF]
     Design Skipped` heading also satisfies -- so the pure validator alone
     would falsely refuse a feature that deliberately skipped DESIGN (nothing
     was designed, so nothing could have been bent out of shape). The
     invariant layers the SAME `_design_skip_witness_present` helper
     `_check_reuse_first_or_design_skip` already uses ON TOP of the pure
     verdict. Reuses the shipped `validate_prefactoring_assessment_content`,
     refuses a REAL-DESIGN-having feature-delta lacking a substantive
     Prefactoring Assessment (and lacking a Design-Skipped witness), clears
     when no `## Wave: DESIGN` heading is present at all OR a valid
     Design-Skipped witness is present. The bugfix lane stays exempt from it
     exactly as it is from `reuse_first_or_design_skip` today.

  2. `des dispatch` gains a proactive readiness ADVISORY (GDP-1/2, sibling of
     `_feature_delta_content_advisory`) -- printed to stderr, advisory-only
     (exit code + stdout envelope untouched), naming the same gap at
     generation time, before the crafter is even dispatched. Mirrors the SAME
     Design-Skipped witness fallback: no advisory when the witness clears it.

Driving port (Mandate 16, no-direct-domain-testing): AT-1/AT-2/AT-3 drive
`des.cli.verify_readiness_pre_dispatch.main(argv)` in-process -- the SAME
composition root `des verify-readiness-pre-dispatch` dispatches, mirroring
`test_readiness_gate_refuses_nonexistent_slice.py`'s established idiom. AT-4
drives the REAL `des dispatch` CLI in-process via
`tests.common.in_process_cli.run_cli_in_process`, mirroring
`test_dispatch_readiness_advisory.py`'s established idiom.

RED-for-right-reason: every scenario below fails today with a genuine
semantic `AssertionError` (the gate/advisory never look at the Prefactoring
Assessment section at all), never an import/collection error --
`validate_prefactoring_assessment_content` and its verdict tokens already
exist and import cleanly.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

import pytest

from des.cli import verify_readiness_pre_dispatch as gate
from tests.common.delivery_contract_fixture import contract_args
from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[4]

_FEATURE_ID = "synthetic-prefactoring-enforcement-wiring-feature"
_SLICE_ID = "slice-01"
_INV_PREFACTORING = "prefactoring_assessment"


#: A DESIGN-having feature-delta well-formed on every OTHER invariant --
#: valid Slice Plan row, a no-overlap Reuse Analysis exemption, and a
#: methodology-exempt sustainability marker -- isolating the Prefactoring
#: Assessment gap as the sole cause of any refusal. `prefactoring_body=None`
#: omits the section entirely (CASE: missing); a string authors it.
def _design_delta(prefactoring_body: str | None) -> str:
    text = (
        "# Feature Delta: synthetic-prefactoring-enforcement-wiring-feature\n\n"
        "## Wave: DESIGN / [REF] Architecture\n\n"
        "Some architecture text.\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n|---|---|\n"
        f"| {_SLICE_ID} | wires the prefactoring gate into enforcement |\n\n"
        "## Reuse Analysis\n\nReuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )
    if prefactoring_body is not None:
        text += f"\n## Prefactoring Assessment\n\n{prefactoring_body}\n"
    return text


#: A feature-delta with NO `## Wave: DESIGN` section at all (DISTILL-only,
#: atdd_pure JIT slices commonly skip DESIGN) -- carries the same other legs
#: so a refusal, if any, is attributable ONLY to the prefactoring dimension.
_NO_DESIGN_DELTA = (
    "# Feature Delta: synthetic-prefactoring-enforcement-wiring-feature\n\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement |\n|---|---|\n"
    f"| {_SLICE_ID} | wires the prefactoring gate into enforcement |\n\n"
    "## Reuse Analysis\n\nReuse-Analysis: no-overlap\n\n"
    "## Test Reuse & Consolidation Analysis\n\n"
    "Test-Reuse-Analysis: methodology-exempt\n"
)

_JUSTIFIED_NONE_BODY = (
    "**NONE -- justified.** This feature is a net-new gate-wiring change; no "
    "existing component is bent out of shape."
)

#: A bare, unmotivated dismissal -- no reasoning beyond the token itself.
#: `unmotivated-prefactoring-assessment` (NOT `missing-prefactoring-
#: assessment`) -- the section IS present, its body just carries no
#: justification.
_UNMOTIVATED_NONE_BODY = "NONE."


#: A feature-delta that deliberately skipped the optional DESIGN wave and
#: acknowledges the skip with a `## Wave: DESIGN / [REF] Design Skipped`
#: witness -- mirrors the canonical witness shape
#: `readiness_reuse_invariant`'s fixtures already establish, and the REAL
#: shape `docs/feature/autonomous-consolidation-and-bugfix-loops/
#: feature-delta.md` carries on trunk. Carries NO `## Prefactoring
#: Assessment` section -- the witness alone must rescue it.
#: `rationale=None` authors a bare heading with an EMPTY body (not a valid
#: witness); a string authors the heading with that body.
def _design_skip_witness_delta(rationale: str | None) -> str:
    text = (
        "# Feature Delta: synthetic-prefactoring-enforcement-wiring-feature\n\n"
        "## Wave: DESIGN / [REF] Design Skipped\n\n"
    )
    if rationale is not None:
        text += f"{rationale}\n\n"
    text += (
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n|---|---|\n"
        f"| {_SLICE_ID} | wires the prefactoring gate into enforcement |\n\n"
        "## Reuse Analysis\n\nReuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )
    return text


_DESIGN_SKIP_RATIONALE = (
    "The optional DESIGN wave was deliberately not run for this feature -- "
    "the atdd_pure floor is DISTILL->DELIVER (mandatory), DESIGN is "
    "advisory-optional, and this feature's DESIGN-shaped decisions were "
    "already discharged in DISCUSS."
)


def _author_feature_delta(repo_root: Path, content: str) -> None:
    workspace = repo_root / "docs" / "feature" / _FEATURE_ID
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(content, encoding="utf-8")


def _run_gate(repo_root: Path, *extra: str) -> tuple[int, dict]:
    """Invoke the readiness gate's `main(argv)` in-process, mirroring
    `test_readiness_gate_refuses_nonexistent_slice.py`'s `_run` verbatim."""
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--slice-id",
        _SLICE_ID,
        "--repo-root",
        str(repo_root),
        *extra,
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = gate.main(argv)
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _invariant(report: dict, invariant_id: str) -> dict:
    for inv in report.get("invariants", []):
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(
        f"invariant {invariant_id!r} missing from report entirely -- the "
        f"gate must always emit every invariant it evaluates. observed "
        f"report={report}"
    )


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> Path:
    """A bare `.git` marker (the gate has zero `git` dependency,
    target-machine agnosticism -- no real `git init` needed)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    return repo_root


# --- AT-1 (neg-A): readiness gate REFUSES a DESIGN-having delta with no ----
# assessment, and the remediation is self-explaining WHAT/WHY/HOW ----------


def test_readiness_gate_refuses_design_delta_without_assessment(
    hermetic_repo: Path,
) -> None:
    """(neg-A) A DESIGN-having feature-delta with NO `## Prefactoring
    Assessment` section must be REFUSED -- `prefactoring_assessment`
    `satisfied: false`, overall verdict not `cleared` -- while every other
    invariant stays satisfied (the gap is isolated). The remediation must be
    self-explaining WHAT/WHY/HOW: WHAT failed (no Prefactoring Assessment
    section), WHY (a real DESIGN can bend an existing component out of
    shape), HOW (author the section, or a Design-Skipped witness).
    """
    _author_feature_delta(hermetic_repo, _design_delta(None))

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is False, (
        "a DESIGN-having feature-delta with no Prefactoring Assessment "
        f"section must FAIL this invariant. observed={inv}"
    )
    remediation = inv.get("remediation") or ""
    assert remediation, (
        f"the refusal must carry a what/why/how remediation. observed={inv}"
    )
    assert "Prefactoring Assessment" in remediation, (
        "WHAT: the remediation must name the missing section. "
        f"observed remediation={remediation!r}"
    )
    assert "bend" in remediation and "shape" in remediation, (
        "WHY: the remediation must explain a real DESIGN can bend an "
        f"existing component out of shape. observed remediation={remediation!r}"
    )
    assert "@prefactoring" in remediation and (
        "NONE" in remediation or "Design Skipped" in remediation
    ), (
        "HOW: the remediation must name the concrete fix -- the "
        "@prefactoring slice, a justified NONE, or the Design-Skipped "
        f"witness. observed remediation={remediation!r}"
    )
    assert report.get("verdict") != "cleared" and code != 0, (
        "a missing Prefactoring Assessment on a DESIGN-having delta must "
        f"refuse the dispatch. observed verdict={report.get('verdict')!r}, "
        f"code={code}, invariants={report.get('invariants')}"
    )


def test_readiness_gate_refuses_design_delta_with_unmotivated_none(
    hermetic_repo: Path,
) -> None:
    """(neg-B) A DESIGN-having feature-delta whose `## Prefactoring
    Assessment` is a bare, unmotivated "NONE." (no reasoning) must be
    REFUSED -- distinct from AT-1's absent-section case (the section IS
    present here, its body just carries no justification)."""
    _author_feature_delta(hermetic_repo, _design_delta(_UNMOTIVATED_NONE_BODY))

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is False, (
        "an unmotivated, unjustified NONE must FAIL this invariant -- the "
        f"skip-requires-justification floor. observed={inv}"
    )
    assert report.get("verdict") != "cleared" and code != 0, (
        f"observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )


def test_readiness_gate_clears_once_justified_none_added(
    hermetic_repo: Path,
) -> None:
    """The SAME workspace clears once a justified NONE section is added --
    proves the fix does not over-refuse a legitimately-assessed feature."""
    _author_feature_delta(hermetic_repo, _design_delta(_JUSTIFIED_NONE_BODY))

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is True, (
        f"a substantive, justified NONE must clear. observed={inv}"
    )
    assert report.get("verdict") == "cleared" and code == 0, (
        "a workspace satisfying every invariant including a justified "
        f"Prefactoring Assessment must clear. observed verdict="
        f"{report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )


# --- AT-2 (pos-B): a no-DESIGN delta clears the invariant regardless -------


def test_readiness_gate_clears_no_design_delta_regardless(
    hermetic_repo: Path,
) -> None:
    """(pos-B) A feature-delta with NO `## Wave: DESIGN` section at all
    clears the `prefactoring_assessment` invariant unconditionally (scoping
    no-op -- nothing to assess), even though it carries no Prefactoring
    Assessment section either."""
    _author_feature_delta(hermetic_repo, _NO_DESIGN_DELTA)

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is True, (
        "a DESIGN-skipped feature-delta must clear the prefactoring "
        f"invariant unconditionally. observed={inv}"
    )
    assert report.get("verdict") == "cleared" and code == 0, (
        f"observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )


# --- AT-2b (pos-A): a Design-Skipped witness rescues a missing assessment --


def test_readiness_gate_clears_design_skipped_witness_with_rationale(
    hermetic_repo: Path,
) -> None:
    """(pos-A) The CRITICAL correction: a feature-delta whose `## Wave:
    DESIGN` heading is actually `## Wave: DESIGN / [REF] Design Skipped`
    (the DESIGN wave was deliberately NOT run) carries NO `## Prefactoring
    Assessment` section, and must still CLEAR via the witness -- there is no
    design, so nothing could have been bent out of shape. Without the
    witness fallback, `_feature_delta_has_design_wave`'s `## Wave: DESIGN`
    substring match would falsely refuse this (the real-world shape:
    `docs/feature/autonomous-consolidation-and-bugfix-loops/
    feature-delta.md` on trunk)."""
    _author_feature_delta(
        hermetic_repo, _design_skip_witness_delta(_DESIGN_SKIP_RATIONALE)
    )

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is True, (
        "a Design-Skipped witness with a non-empty rationale must CLEAR the "
        f"prefactoring_assessment invariant -- nothing was designed, so "
        f"nothing could have been bent out of shape. observed={inv}"
    )
    assert report.get("verdict") == "cleared" and code == 0, (
        f"observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )


def test_readiness_gate_refuses_design_skipped_witness_with_empty_rationale(
    hermetic_repo: Path,
) -> None:
    """NEGATIVE (must stay REFUSED): a BARE `## Wave: DESIGN / [REF] Design
    Skipped` heading with an EMPTY rationale is NOT a valid witness -- mirrors
    `_check_reuse_first_or_design_skip`'s identical treatment. Proves the
    witness fallback isn't a rubber stamp for the bare heading alone."""
    _author_feature_delta(hermetic_repo, _design_skip_witness_delta(None))

    code, report = _run_gate(hermetic_repo)

    inv = _invariant(report, _INV_PREFACTORING)
    assert inv["satisfied"] is False, (
        "a bare Design-Skipped heading with NO rationale is not a valid "
        f"witness -- must still FAIL. observed={inv}"
    )
    assert report.get("verdict") != "cleared" and code != 0, (
        f"observed verdict={report.get('verdict')!r}, code={code}, "
        f"invariants={report.get('invariants')}"
    )


# --- AT-3: the bugfix lane stays exempt, exactly as for reuse-first --------


def test_bugfix_lane_exempt_from_prefactoring_invariant(hermetic_repo: Path) -> None:
    """A `DES-LANE: bugfix` dispatch on a DESIGN-having delta with NO
    Prefactoring Assessment section must still CLEAR -- the bugfix lane skips
    `prefactoring_assessment` exactly as it already skips
    `reuse_first_or_design_skip`."""
    _author_feature_delta(hermetic_repo, _design_delta(None))

    _, report = _run_gate(
        hermetic_repo,
        "--lane",
        "bugfix",
        "--lane-justification",
        (
            "wires the prefactoring gate into enforcement; regression test: "
            "test_readiness_gate_refuses_design_delta_without_assessment"
        ),
    )

    assert _INV_PREFACTORING not in {
        inv["id"] for inv in report.get("invariants", [])
    }, (
        "the bugfix lane must SKIP the prefactoring_assessment invariant "
        f"entirely, exactly as it skips reuse_first_or_design_skip. "
        f"observed invariants={report.get('invariants')}"
    )


# --- AT-4: `des dispatch` emits the proactive advisory ---------------------


def _make_dispatch_repo_root(tmp_path: Path, *, feature_delta: str) -> Path:
    """A tmp repo-root carrying a COPY of the real dispatch SSOT plus the
    fixture feature-delta.md -- mirrors `_make_repo_root` in
    `tests/bugs/des/test_dispatch_readiness_advisory.py`."""
    dispatch_dir = tmp_path / "nWave" / "dispatch"
    dispatch_dir.mkdir(parents=True)
    for name in ("atdd_pure.yaml", "vendors.yaml"):
        shutil.copyfile(_REPO_ROOT / "nWave" / "dispatch" / name, dispatch_dir / name)
    feature_dir = tmp_path / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(feature_delta, encoding="utf-8")
    return tmp_path


def test_dispatch_emits_prefactoring_advisory_for_design_delta_missing_assessment(
    tmp_path: Path,
) -> None:
    """POSITIVE (active-RED today): a feature-end non-test-executing
    `--phase FEATURE_END_EXAMINE` dispatch for a project whose DESIGN-having
    feature-delta LACKS a Prefactoring Assessment section must print a
    proactive readiness ADVISORY on STDERR naming the gap, while STILL emitting
    the valid envelope on STDOUT with exit code 0 -- advisory-only, mirroring
    the existing Reuse Analysis advisory (`_feature_delta_content_advisory`).
    ADR-SSOT-002: feature-delta is never consulted on test-executing DELIVER
    routes, so this AT targets the feature-end non-test-executing examiner
    phase instead.
    """
    repo_root = _make_dispatch_repo_root(tmp_path, feature_delta=_design_delta(None))

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "dispatch",
            "--mode",
            "atdd_pure",
            "--project-id",
            _FEATURE_ID,
            "--slice",
            _SLICE_ID,
            "--wave",
            "feature-end",
            "--phase",
            "FEATURE_END_EXAMINE",
            *contract_args(repo_root),
        ],
        cwd=repo_root,
    )

    assert exit_code == 0, (
        "the readiness advisory must be advisory-ONLY -- exit code must stay "
        f"0 even when the Prefactoring Assessment is missing. got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    assert "Prefactoring Assessment" in stderr, (
        "expected a proactive readiness advisory on STDERR naming the "
        "missing '## Prefactoring Assessment' section (GDP-1/2: catch it at "
        "generation time, before the crafter is dispatched and the separate "
        f"readiness gate rejects it). stderr={stderr!r}"
    )
    assert "<!-- DES-VALIDATION" in stdout, (
        "the crafter envelope must STILL be generated on stdout even when "
        f"the readiness advisory fires -- stdout={stdout!r}"
    )


def test_dispatch_emits_no_prefactoring_advisory_for_design_skipped_witness(
    tmp_path: Path,
) -> None:
    """(pos-A mirror) A feature-delta carrying a Design-Skipped witness with
    a rationale, and NO `## Prefactoring Assessment` section, must emit NO
    prefactoring advisory -- the SAME witness fallback the readiness gate
    applies (`_design_skip_witness_present`), mirrored here so the two
    surfaces never disagree."""
    repo_root = _make_dispatch_repo_root(
        tmp_path,
        feature_delta=_design_skip_witness_delta(_DESIGN_SKIP_RATIONALE),
    )

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "dispatch",
            "--mode",
            "atdd_pure",
            "--project-id",
            _FEATURE_ID,
            "--slice",
            _SLICE_ID,
            "--phase",
            "A_GREEN",
            *contract_args(repo_root),
        ],
        cwd=repo_root,
    )

    assert exit_code == 0, (
        f"got exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    assert "Prefactoring Assessment" not in stderr, (
        "a Design-Skipped witness with a rationale must suppress the "
        "prefactoring advisory entirely -- there is no design to have bent "
        f"anything. stderr={stderr!r}"
    )
    assert "<!-- DES-VALIDATION" in stdout, (
        f"the crafter envelope must still be generated. stdout={stdout!r}"
    )
