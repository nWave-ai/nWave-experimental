"""Regression AT -- `des validate-feature-delta` rejection routes to
`des feature-delta-doctor` (fix-validate-feature-delta-routes-to-doctor).

DEFECT: when `des validate-feature-delta` REJECTS a malformed feature-delta,
its rejection message names only the specific rule violated (e.g.
`unjustified-create-new`, `malformed-wave-heading`) -- it does NOT route the
author to `des feature-delta-doctor <path>`, the tool that reports ALL
structural gaps in ONE pass with per-gap what/why/how
(`src/des/cli/feature_delta_doctor.py`). The author fixes one rejection,
re-runs, hits the next, N times, instead of getting the full gap list once.

Standing principle: a gate's HOW-to-fix invokes the producing/diagnosing
system tool (`des feature-delta-doctor`) rather than sending the operator
into one-at-a-time manual repair.

Charter: docs/product/expectations/fix-validate-feature-delta-routes-to-doctor/
the-rejection-routes-you-to-des-feature-delta-doctor.md

Target (RED reason): `src/des/cli/validate_feature_delta.py` -- the
`_run_require_reuse_analysis` rejection-printing path prints only
`f"{result.verdict}: {result.detail}"` (or the equivalent JSON payload);
neither carries the string `des feature-delta-doctor`.

Driving surface (P1-P4 in-process active-RED pattern, `nw-distill-red-
scaffolding`): the REAL `des validate-feature-delta` CLI EDGE, driven
IN-PROCESS via `tests/common/in_process_cli.run_cli_in_process` against the
production dispatcher `des.cli.__main__.main` -- the in-process analogue of
`python -m des.cli.__main__ validate-feature-delta --require-reuse-analysis
--format=json <path>` (the same subcommand + dispatcher the sibling
`test_validate_feature_delta.py` / `test_feature_delta_doctor.py` drive).

covers: fix-validate-feature-delta-routes-to-doctor
"""

from __future__ import annotations

from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# Fixtures -- feature-delta content
# ---------------------------------------------------------------------------

#: A Reuse Analysis section with one CREATE_NEW row carrying an EMPTY
#: Justification cell -- rejected by `validate_reuse_analysis_content` as
#: `VERDICT_UNJUSTIFIED_CREATE_NEW` (DDD-3), *before* the content-grounding
#: leg runs (`_classify_component_row` is evaluated ahead of the
#: CodeFactPort grounding check in `validate_reuse_analysis_content`), so
#: this verdict is reached regardless of whether `src/foo.py` resolves.
#: Verified empirically against the production validator (mirrors the
#: `GAPPY_FEATURE_DELTA` fixture in the sibling `test_feature_delta_doctor.py`).
MALFORMED_FEATURE_DELTA = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
    "\n"
    "Some architecture prose.\n"
    "\n"
    "## Reuse Analysis\n"
    "\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|---|---|---|---|---|\n"
    "| SomeHelper | src/foo.py | none | CREATE_NEW |  |\n"
)

#: A well-formed feature-delta whose single Reuse Analysis row is a
#: well-justified EXTEND citing a component that genuinely resolves through
#: the CodeFactPort chain (`_component_citation_is_grounded`) -- so the CLI's
#: `_run_require_reuse_analysis` exits 0 (it returns 0 ONLY for
#: `VERDICT_STRUCTURALLY_ACCEPTED`, e.g. a DDD-9 exemption marker still
#: exits 1). The companion `HELPER_MODULE_SOURCE` is written to
#: `<tmp_path>/helper.py` so `existing_helper` resolves as a real atom in
#: that file when `project_root` (the CLI's `Path.cwd()`) is `tmp_path`.
WELL_FORMED_FEATURE_DELTA = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
    "\n"
    "Some architecture prose.\n"
    "\n"
    "## Reuse Analysis\n"
    "\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|---|---|---|---|---|\n"
    "| existing_helper | helper.py | full | EXTEND | reuses the existing helper |\n"
)

#: The real, grounded companion source `WELL_FORMED_FEATURE_DELTA` cites.
HELPER_MODULE_SOURCE = "def existing_helper() -> None:\n    pass\n"


def _run_validate_feature_delta(target: Path) -> tuple[int, str, str]:
    """Drive the real `des validate-feature-delta --require-reuse-analysis`
    CLI EDGE IN-PROCESS (no interpreter fork) -- the in-process analogue of
    `python -m des.cli.__main__ validate-feature-delta --require-reuse-analysis
    --format=json <path>`.
    """
    return run_cli_in_process(
        [
            "validate-feature-delta",
            "--require-reuse-analysis",
            "--format=json",
            str(target),
        ],
        cwd=target.parent,
    )


# ---------------------------------------------------------------------------
# Positive AT -- a rejection routes the author to `des feature-delta-doctor`
# ---------------------------------------------------------------------------


def test_rejection_routes_author_to_feature_delta_doctor(tmp_path: Path) -> None:
    """A REJECTED feature-delta's message NAMES `des feature-delta-doctor` as
    the primary remedy -- the one-pass gap-list tool -- in addition to naming
    the specific rule violated. The check itself stays intact: the malformed
    delta is still REJECTED (non-zero exit / rejection verdict).

    FAILS TODAY: the rejection message/JSON payload names only
    `unjustified-create-new`; `des feature-delta-doctor` appears nowhere in
    stdout or stderr.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(MALFORMED_FEATURE_DELTA, encoding="utf-8")

    exit_code, stdout, stderr = _run_validate_feature_delta(target)

    assert exit_code != 0, (
        "the malformed feature-delta must still be REJECTED (the check "
        f"stays intact); got exit_code=0. stdout={stdout!r} stderr={stderr!r}"
    )
    assert "unjustified-create-new" in stdout, (
        "expected the specific rule violated to still be named in the "
        f"rejection (context is preserved, not replaced); stdout={stdout!r}"
    )

    combined = stdout + stderr
    assert "des feature-delta-doctor" in combined, (
        "expected the rejection to route the author to the one-pass "
        "diagnosing tool `des feature-delta-doctor <path>` as the PRIMARY "
        "remedy -- instead of naming only the specific rule and forcing a "
        "fix-one/re-run/hit-the-next loop across N gate invocations; "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT -- a well-formed delta is NOT rejected and NOT steered to the
# doctor (no false positive, no spurious routing message on a clean delta)
# ---------------------------------------------------------------------------


def test_well_formed_delta_is_not_rejected_and_does_not_route_to_doctor(
    tmp_path: Path,
) -> None:
    """A WELL-FORMED feature-delta is NOT rejected, and its accepted output
    does NOT mention `des feature-delta-doctor` -- no false steer on a clean
    delta.

    Negative AT (detected by `des verify-negative-at` via the `_not_` name
    token, GS-8): asserts the WRONG outcome (rejection / doctor-routing
    message) is NOT produced. GREEN today; must stay GREEN after the fix --
    the fix only touches the rejection path, never the accepted path.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(WELL_FORMED_FEATURE_DELTA, encoding="utf-8")
    (tmp_path / "helper.py").write_text(HELPER_MODULE_SOURCE, encoding="utf-8")

    exit_code, stdout, stderr = _run_validate_feature_delta(target)

    assert exit_code == 0, (
        "a well-formed feature-delta must NOT be rejected; got exit_code="
        f"{exit_code}. stdout={stdout!r} stderr={stderr!r}"
    )
    assert "structurally-accepted" in stdout, (
        f"expected the accepted verdict in stdout; stdout={stdout!r}"
    )

    combined = stdout + stderr
    assert "des feature-delta-doctor" not in combined, (
        "a clean, accepted feature-delta must never mention the "
        f"doctor-routing remedy -- no false steer; stdout={stdout!r} "
        f"stderr={stderr!r}"
    )
