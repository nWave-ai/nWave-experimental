"""slice-02 AT -- the D1 catcher: ``main(argv)`` must WIRE ``plan=`` through.

# @feature-f-prefactoring-dispatch-clears-honestly
# @slice-02

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone). This AT closes the gap
a feature-end deep review found: `check_at_review`
(`des.cli.carpaccio_slice_gate.py`) gained the `plan=`/`commit_sha=`/
`commit_diff_port=` green-to-green-seal parameters (D7-D12), but its ONE
production ENTRY caller -- `carpaccio_slice_gate.main` (this module's own
`main()`, line ~896) -- calls it WITHOUT `plan=`. Every existing AT in
`test_slice_02_green_to_green_seal.py` drives `check_at_review` DIRECTLY with
hand-supplied kwargs, so none of them could ever catch a production caller
that omits the kwarg -- the seam is authored but never REACHED in production.
A real `@prefactoring` dispatch is REJECTED with exit 45 (`ATReviewGateRejected`,
reason "absent") even though `check_carpaccio`'s assertion 4 (which DOES
receive `plan=` today) already clears the SAME 0-AT slice with
`LaneAtExemptionAccepted`.

Driving port (Mandate 16, no-direct-domain-testing): this AT drives
`des.cli.carpaccio_slice_gate.main(argv)` -- the REAL CLI entry point (`des
carpaccio-slice-gate`) -- not the bare `check_at_review` function. Mirrors the
established `main(argv)` driving-port precedent for this gate
(`tests/scripts/cli/atdd_pure_carpaccio_slice_gate/steps/
test_carpaccio_entry_path_fixes.py::_run_gate`), adapted to the primary
`des.cli.carpaccio_slice_gate` module (the legacy `scripts.cli` module is a
thin re-export shim per this module's own docstring).

Litmus (the whole point of this AT): if `plan=plan` is ever removed from the
`check_at_review(...)` call inside `main()`, THIS test alone must go RED again
-- it is the only AT in the suite driving the ENTRY seam end-to-end rather
than the bare function.

Active-RED today (D1 unwired): `main()` clears assertion 4
(`LaneAtExemptionAccepted`, plan already threaded through `check_carpaccio`)
then REJECTS at assertion 5 with exit 45 / reason "absent" -- a genuine
business `AssertionError` on the expected exit-0 clearance, never an
import/collection error.

CONTRACT_SHAPE: bounded-change
Outcome anchor: docs/feature/f-prefactoring-dispatch-clears-honestly/
feature-delta.md (Wave: DESIGN / [REF] Green-to-Green Seal, slice-02 REDUCED
SCOPE) + design/green-to-green-seal-design.md (D7/D12 single-seam threading).
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import TYPE_CHECKING

from des.cli import carpaccio_slice_gate


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "synthetic-entry-wiring-feature"
_SLICE_ID = "slice-01"


def _write_feature_delta(repo: Path, feature_id: str) -> None:
    """A single-row Slice Plan whose only row is a 0-AT `@prefactoring` slice.

    `slice-01` (no predecessor) keeps the AT focused on the ENTRY wiring gap
    alone -- at ENTRY, `commit_sha` is always `None` (this CLI has no
    `--commit-sha` flag), so a correctly-wired `check_at_review` clears
    IMMEDIATELY with the PENDING label without ever touching the ledger or a
    predecessor lookup (see `_check_green_to_green`'s `commit_sha is None`
    branch).
    """
    delta = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text(
        "# Feature Delta: entry-wiring fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_SLICE_ID} | a behavior-preserving refactor introduces the seam "
        "| pending | @prefactoring | green-to-green seal AT fixture |\n",
        encoding="utf-8",
    )


def _run_gate(repo: Path, feature_id: str, entering_slice: str) -> tuple[int, dict]:
    """Drive the REAL `des.cli.carpaccio_slice_gate.main(argv)` entry point."""
    argv = [
        "--feature-id",
        feature_id,
        "--entering-slice",
        entering_slice,
        "--repo-root",
        str(repo),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        exit_code = carpaccio_slice_gate.main(argv)
    payload: dict = {}
    for line in out.getvalue().splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payload = json.loads(stripped)
    return exit_code, payload


def test_zero_at_prefactoring_slice_clears_end_to_end_through_main(
    tmp_path: Path,
) -> None:
    """A real 0-AT `@prefactoring` slice-01 dispatch through `main(argv)` must
    clear end-to-end (exit 0), never rejected at assertion 5 while assertion 4
    already accepted the SAME lane exemption.

    No `.feature` file is authored at all (genuinely zero scenarios for this
    feature -- `_feature_tag_files` returns an empty list) and no
    `ATReviewVerdict` ledger record exists -- the ONLY way this can clear is
    if `main()` threads `plan=` into `check_at_review` so the green-to-green
    bypass fires instead of the legacy record-presence check.
    """
    repo = tmp_path
    _write_feature_delta(repo, _FEATURE_ID)

    exit_code, payload = _run_gate(repo, _FEATURE_ID, _SLICE_ID)

    assert exit_code == 0, (
        "D1 REOPENED (or never closed): a 0-AT @prefactoring slice must clear "
        "carpaccio_slice_gate.main(argv) end-to-end (exit 0) -- check_at_review "
        "must receive plan= at the ENTRY seam so the green-to-green lane bypass "
        f"fires instead of the legacy record-presence check. observed exit_code="
        f"{exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "LaneAtExemptionAccepted", (
        "the cleared payload's event must be LaneAtExemptionAccepted (the "
        f"assertion-4 lane-exemption event, threaded through as the final "
        f"event) -- observed payload={payload!r}"
    )
