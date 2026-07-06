"""slice-02 ATs -- the Green-to-Green Seal (``check_at_review`` D7-D12).

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone). Design reference:
`docs/feature/f-prefactoring-dispatch-clears-honestly/feature-delta.md`
(`## Wave: DESIGN / [REF] Green-to-Green Seal (slice-02, REDUCED SCOPE)`) +
`docs/feature/f-prefactoring-dispatch-clears-honestly/design/
green-to-green-seal-design.md` (the grounded substance-of-behavior-preserved
design).

A PREFACTORING (0-AT, behavior-preserving refactor) has no RED->GREEN seal
analog -- the honest evidence a commit-time gate can check is 3 REUSED facts:
green-before (the predecessor slice's suite was green), green-after (this
commit's own suite is green), and no-test-file-in-diff (anti-gaming: a
"prefactoring" that also touches a test file is a disguised behavior change).
`check_at_review` (`des.cli.carpaccio_slice_gate.py:399`) gains three
ADD-not-mutate, keyword-only, default-``None`` parameters -- ``plan``,
``commit_sha``, ``commit_diff_port`` -- that thread this evidence through the
SAME single seam both its production callers already use
(`carpaccio_slice_gate.main` at ENTRY, `verify_commit_trailers._audit_slice`
at COMMIT), per D7/D12.

Driving port (Mandate 13, no-direct-domain-testing): every AT below drives
`check_at_review`/`check_carpaccio` directly -- the SAME production functions
`carpaccio_slice_gate.main`/`verify_commit_trailers._audit_slice` call -- never
a domain-object shape assertion with no port between. Location note (S2,
`nw-at-completeness-check-structural-invariants`): a NEW behavioral AT never
ships under `tests/des/unit/(domain|cli)/*` (reserved for pre-existing legacy +
arch tests); this file lives under `tests/des/cli/<feature-name>/` instead,
mirroring the established sibling layout (`tests/des/cli/atdd_pure_carpaccio_spine/`,
`tests/des/cli/fix_slice_id_regex_suffix_support/`).

GREEN (production-wired): `check_at_review` and `check_carpaccio` are STABLE
production functions extended with the D7-D12 green-to-green kwargs / D11
lane-datum consultation. `check_at_review` ACCEPTS the `plan=`/`commit_sha=`/
`commit_diff_port=` keyword-only, default-``None`` parameters, AND both
production callers now PASS them: the ENTRY caller `carpaccio_slice_gate.main`
passes `plan=plan` (`carpaccio_slice_gate.py:912`) and the COMMIT caller
`verify_commit_trailers._audit_slice` threads the commit-time trio -- so the
seal fires through a real dispatch. Every AT in THIS file drives
`check_at_review` DIRECTLY with hand-supplied `plan=`/`commit_sha=`/
`commit_diff_port=` kwargs (unit-level seal coverage); the end-to-end coverage
that the production call site is actually wired -- and would catch a regression
in it -- lives in the sibling file
`test_slice_02_entry_point_wires_green_to_green.py`. The `_invoke`
helper below captures any `GateError` refusal as a plain return value so EVERY
assertion below reaches its own explicit `assert`, never an uncaught exception
escaping the test body. The
new attestation labels (`_AT_EVIDENCE_GREEN_TO_GREEN` /
`_AT_EVIDENCE_GREEN_TO_GREEN_PENDING`, D8) are resolved via `getattr` on the
(stable, already-importable) `carpaccio_slice_gate` module rather than a
module-top `from ... import` -- an absent attribute never breaks collection,
it fails the one test that needs it, cleanly, via `pytest.fail`.

`CommitDiffPort` (D8, CREATE_NEW at
`src/des/ports/driven_ports/commit_diff_port.py`) does not exist yet either --
`_FakeCommitDiffPort` below is a plain duck-typed fake (no ABC inheritance)
exposing the ``changed_paths(repo, commit_sha)`` shape the design's
`_verify_green_to_green` consumes; ``Indeterminate`` is REUSED from the
already-shipped `committed_scope_port` (the same degrade-LOUD VO every sibling
port reuses, per the Reuse Analysis' `CommitDiffPort` row).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import carpaccio_slice_gate as _gate_module
from des.cli.carpaccio_format import GateError, SlicePlan, SlicePlanRow, check_carpaccio
from des.cli.carpaccio_slice_gate import check_at_review
from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "synthetic-green-to-green-feature"
_SLICE_MAX = 10


# --- fixtures ----------------------------------------------------------------


def _prefactoring_plan(entering_slice: str) -> SlicePlan:
    """A single-row plan whose entering-slice row carries ``@prefactoring``.

    Only the entering slice's OWN row matters to `_lane_profile_for_slice`
    (D11/D12 -- a `plan.row_for(slice_id)` lookup); the predecessor's ledger
    membership (green-before) is a SEPARATE fact read from
    `AtCompletionLedger.verified_slices()`, not from the plan.
    """
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=entering_slice,
                value_statement="a behavior-preserving refactor introduces the seam",
                status="pending",
                annotation="@prefactoring",
                justification="green-to-green seal AT fixture (slice-02)",
            ),
        )
    )


def _unannotated_plan(entering_slice: str) -> SlicePlan:
    """A single-row plan whose entering-slice row carries NO lane annotation."""
    return SlicePlan(
        rows=(
            SlicePlanRow(
                slice_id=entering_slice,
                value_statement="an ordinary slice with zero acceptance tests",
                status="pending",
                annotation="",
                justification="",
            ),
        )
    )


def _mark_verified(repo: Path, slice_id: str) -> None:
    """Append a `SliceCommitVerified` record for ``slice_id`` (legacy per-feature ledger)."""
    AtCompletionLedger(_FEATURE_ID, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=slice_id
    )


class _FakeCommitDiffPort:
    """Duck-typed fake for the not-yet-existing ``CommitDiffPort`` (D8).

    Exposes exactly the ``changed_paths(repo, commit_sha)`` shape the design's
    `_verify_green_to_green` consumes -- no ABC inheritance needed, since the
    real port does not exist yet (P1: never import an absent SUT name at
    module top).
    """

    def __init__(
        self, paths: tuple[str, ...] = (), *, indeterminate_reason: str | None = None
    ) -> None:
        self._paths = paths
        self._indeterminate_reason = indeterminate_reason

    def changed_paths(self, repo: Path, commit_sha: str):
        if self._indeterminate_reason is not None:
            return Indeterminate(reason=self._indeterminate_reason)
        return list(self._paths)


class _SeamNotYetImplemented:
    """Sentinel: `check_at_review` does not yet accept the green-to-green
    kwargs (``plan``/``commit_sha``/``commit_diff_port``, D7)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover -- diagnostic only
        return f"_SeamNotYetImplemented({self.detail!r})"


def _invoke_check_at_review(repo: Path, entering_slice: str, **kwargs: object):
    """Best-effort `check_at_review` call, uniformly captured as a return value.

    Catches the not-yet-extended-signature `TypeError` (seam missing) AND any
    `GateError` refusal, returning both as plain values -- every assertion
    below reaches its own explicit `assert`, never an uncaught exception.
    """
    try:
        return check_at_review(repo, _FEATURE_ID, entering_slice, [], **kwargs)
    except TypeError as exc:
        return _SeamNotYetImplemented(str(exc))
    except GateError as exc:
        return exc


def _invoke_check_carpaccio(repo: Path, plan: SlicePlan, entering_slice: str):
    """Best-effort `check_carpaccio` call, GateError captured as a return value."""
    try:
        return check_carpaccio(
            plan, [], entering_slice, _SLICE_MAX, repo=repo, feature_id=_FEATURE_ID
        )
    except GateError as exc:
        return exc


def _evidence_label(name: str) -> str:
    """Resolve a not-yet-implemented attestation label via `getattr` (never a
    module-top `from ... import`, so an absent name fails ONE test cleanly)."""
    if not hasattr(_gate_module, name):
        pytest.fail(
            f"des.cli.carpaccio_slice_gate.{name} does not exist yet -- the "
            "green-to-green seal (D8) is not yet implemented."
        )
    return str(getattr(_gate_module, name))


# AT-1 (green-before-absent -> refuse) -----------------------------------------


def test_green_before_absent_refuses(tmp_path: Path) -> None:
    """Entering slice-02's predecessor (slice-01) carries no
    `SliceCommitVerified` ledger record -- refused `"green-before-absent"`.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D9, green-before
    fact).
    """
    plan = _prefactoring_plan("slice-02")
    # No ledger records at all: slice-01 is unverified.
    result = _invoke_check_at_review(
        tmp_path,
        "slice-02",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(paths=("src/des/cli/x.py",)),
    )
    assert (
        isinstance(result, GateError)
        and result.payload.get("reason") == "green-before-absent"
    ), (
        "check_at_review must refuse green-before-absent when the predecessor "
        "slice (slice-01) carries no SliceCommitVerified ledger record (D9) -- "
        f"the green-to-green seal is not yet implemented. observed={result!r}"
    )


# AT-2 (green-after-red -> refuse) ---------------------------------------------


def test_green_after_red_refuses(tmp_path: Path) -> None:
    """Predecessor (slice-01) verified, entering slice (slice-02) itself is
    NOT yet verified -- refused `"green-after-red"`.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D9, green-after
    fact).
    """
    _mark_verified(tmp_path, "slice-01")
    plan = _prefactoring_plan("slice-02")
    result = _invoke_check_at_review(
        tmp_path,
        "slice-02",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(paths=("src/des/cli/x.py",)),
    )
    assert (
        isinstance(result, GateError)
        and result.payload.get("reason") == "green-after-red"
    ), (
        "check_at_review must refuse green-after-red when the entering slice "
        "itself carries no SliceCommitVerified record yet (D9) -- the "
        f"green-to-green seal is not yet implemented. observed={result!r}"
    )


# AT-3 (test-file-in-diff -> refuse, anti-gaming) ------------------------------


def test_test_file_in_diff_refuses(tmp_path: Path) -> None:
    """Both green-before AND green-after hold, but the commit's diff touches a
    test file -- refused `"test-file-in-diff"` (a behavior-preserving refactor
    that also weakens/adds a test is a disguised behavior change, D10).

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D10, anti-gaming
    no-test-file-in-diff fact).
    """
    _mark_verified(tmp_path, "slice-01")
    _mark_verified(tmp_path, "slice-02")
    plan = _prefactoring_plan("slice-02")
    result = _invoke_check_at_review(
        tmp_path,
        "slice-02",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(
            paths=("src/des/cli/x.py", "tests/des/unit/cli/test_x.py")
        ),
    )
    assert (
        isinstance(result, GateError)
        and result.payload.get("reason") == "test-file-in-diff"
    ), (
        "check_at_review must refuse test-file-in-diff when the commit's diff "
        "touches a test path (D10, is_test_path) -- the anti-gaming check is "
        f"not yet implemented. observed={result!r}"
    )


# AT-4 (git-absent -> INDETERMINATE, never silent-pass) ------------------------


@pytest.mark.parametrize(
    "indeterminate_reason",
    [
        pytest.param("git binary not found", id="git-binary-absent"),
        pytest.param("not a work-tree", id="not-a-work-tree"),
        pytest.param("unresolvable commit sha", id="unresolvable-sha"),
    ],
)
def test_git_absent_degrades_indeterminate_never_silent_pass(
    tmp_path: Path, indeterminate_reason: str
) -> None:
    """`CommitDiffPort.changed_paths` degrading to `Indeterminate` (ANY
    reason git could not answer) must surface `GateError(7,
    ATReviewIndeterminate)` -- fail-closed, never a silent pass. Both ledger
    facts hold, isolating the diff-port degrade as the sole cause.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (degrade-LOUD,
    never-silent-pass invariant).
    """
    _mark_verified(tmp_path, "slice-01")
    _mark_verified(tmp_path, "slice-02")
    plan = _prefactoring_plan("slice-02")
    result = _invoke_check_at_review(
        tmp_path,
        "slice-02",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(indeterminate_reason=indeterminate_reason),
    )
    assert (
        isinstance(result, GateError)
        and result.exit_code == 7
        and result.payload.get("event") == "ATReviewIndeterminate"
    ), (
        "a git-absent CommitDiffPort degrade must surface GateError(7, "
        "ATReviewIndeterminate) -- NEVER a silent pass -- regardless of the "
        f"underlying reason ({indeterminate_reason!r}). the green-to-green "
        f"seal's degrade-LOUD path is not yet implemented. observed={result!r}"
    )


# AT-5 (happy green-to-green -> clear) -----------------------------------------


@pytest.mark.parametrize(
    "changed_paths",
    [
        pytest.param((), id="zero-changed-paths"),
        pytest.param(("src/des/cli/x.py",), id="one-non-test-path"),
        pytest.param(
            ("src/des/cli/x.py", "src/des/domain/y.py"), id="many-non-test-paths"
        ),
    ],
)
def test_happy_green_to_green_clears(
    tmp_path: Path, changed_paths: tuple[str, ...]
) -> None:
    """All 3 facts hold (green-before, green-after, no test file in diff) --
    clears with `_AT_EVIDENCE_GREEN_TO_GREEN` (verified, D8). Parametrized over
    the `changed_paths` cardinality (C3 Zero-obligation, Grenning ZOMBIES): a
    ZERO-changed-files commit (e.g. a no-op prefactoring) must clear vacuously
    ("no test file in diff" holds trivially over an empty set) exactly like a
    ONE- or MANY-path diff that simply contains no test file.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D8, COMMIT-verified
    attestation label).
    """
    _mark_verified(tmp_path, "slice-01")
    _mark_verified(tmp_path, "slice-02")
    plan = _prefactoring_plan("slice-02")
    expected = _evidence_label("_AT_EVIDENCE_GREEN_TO_GREEN")
    result = _invoke_check_at_review(
        tmp_path,
        "slice-02",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(paths=changed_paths),
    )
    assert result == expected, (
        "a genuine green-to-green commit (predecessor verified, entering "
        "slice verified, no test file among the "
        f"{len(changed_paths)} changed path(s)) must clear with the "
        f"COMMIT-verified label {expected!r} (D8) -- the green-to-green seal "
        f"is not yet implemented. observed={result!r}"
    )


# AT-6 (ENTRY-pending clear -- distinct label, D8) -----------------------------


def test_entry_pending_clears_with_distinct_label(tmp_path: Path) -> None:
    """At ENTRY (`commit_sha=None`) the commit does not exist yet -- an
    AT-EXEMPT prefactoring lane clears IMMEDIATELY with
    `_AT_EVIDENCE_GREEN_TO_GREEN_PENDING`, a label DISTINCT from the
    COMMIT-verified `_AT_EVIDENCE_GREEN_TO_GREEN` -- an honest ledger must
    never conflate provisional ENTRY acceptance with COMMIT-time verification
    (D8).

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D8, ENTRY-pending
    attestation label, distinct from COMMIT-verified).
    """
    plan = _prefactoring_plan("slice-01")
    pending = _evidence_label("_AT_EVIDENCE_GREEN_TO_GREEN_PENDING")
    verified = _evidence_label("_AT_EVIDENCE_GREEN_TO_GREEN")
    assert pending != verified, (
        "the ENTRY-pending label and the COMMIT-verified label must be "
        f"DISTINCT (D8) -- observed pending={pending!r} verified={verified!r}"
    )
    result = _invoke_check_at_review(tmp_path, "slice-01", plan=plan, commit_sha=None)
    assert result == pending, (
        "check_at_review(commit_sha=None) on a @prefactoring-annotated slice "
        f"must clear IMMEDIATELY with the ENTRY-pending label {pending!r} -- "
        f"substance is verified at COMMIT, not skipped. observed={result!r}"
    )


# AT-7 (negative-path leak-guard -- exercises BOTH loci) -----------------------


def test_unannotated_zero_at_slice_still_rejected_at_both_loci(tmp_path: Path) -> None:
    """KPI-2 guardrail: a 0-AT slice with NO `@prefactoring` annotation is
    STILL rejected `"no-scenarios-for-slice"` at `check_carpaccio` (assertion
    4) AND at `check_at_review` -- the exemption must not leak into the
    ordinary slice-with-AT path at either consulting locus.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: design/green-to-green-seal-design.md (KPI-2 no-leak
    guardrail, byte-identical rejection preserved).
    """
    plan = _unannotated_plan("slice-05")

    carpaccio_result = _invoke_check_carpaccio(tmp_path, plan, "slice-05")
    assert (
        isinstance(carpaccio_result, GateError)
        and carpaccio_result.payload.get("reason") == "no-scenarios-for-slice"
    ), (
        "check_carpaccio must still reject an unannotated 0-AT slice with "
        f"no-scenarios-for-slice (byte-identical, no leak). observed={carpaccio_result!r}"
    )

    review_result = _invoke_check_at_review(
        tmp_path,
        "slice-05",
        plan=plan,
        commit_sha="deadbeef",
        commit_diff_port=_FakeCommitDiffPort(paths=("src/des/cli/x.py",)),
    )
    assert isinstance(review_result, GateError), (
        "check_at_review must still reject an unannotated 0-AT slice (no "
        "@prefactoring lane resolved -> falls through to the existing "
        "record-presence check, which refuses on an absent ATReviewVerdict) "
        f"-- the plan= kwarg is not yet implemented. observed={review_result!r}"
    )


# AT-8 (assertion-4 blast-radius -- the shared _lane_profile_for_slice helper) --


def test_prefactoring_annotated_zero_at_slice_clears_check_carpaccio(
    tmp_path: Path,
) -> None:
    """Finding 1 / D11: a `@prefactoring`-annotated 0-AT slice must clear
    `check_carpaccio`'s no-scenarios-for-slice branch (assertion 4) via the
    SAME shared `_lane_profile_for_slice` helper `check_at_review` consults
    (D12) -- `check_carpaccio` gates STRICTLY BEFORE `check_at_review` in
    `main()` (`carpaccio_slice_gate.py:769` before `:779`), so without this,
    a 0-AT `@prefactoring` slice never reaches assertion 5's exemption at all
    (pairs with `test_entry_pending_clears_with_distinct_label`, AT-6, which
    proves the SAME helper clears `check_at_review`).

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: design/green-to-green-seal-design.md (D11/D12, shared
    `_lane_profile_for_slice` consulting mechanism).
    """
    plan = _prefactoring_plan("slice-02")
    result = _invoke_check_carpaccio(tmp_path, plan, "slice-02")
    assert (
        isinstance(result, dict) and result.get("event") == "LaneAtExemptionAccepted"
    ), (
        "a @prefactoring-annotated 0-AT slice must clear check_carpaccio's "
        "no-scenarios-for-slice branch via the shared _lane_profile_for_slice "
        "helper (D11/D12) -- the blast-radius fix (Finding 1) is not yet "
        f"wired. observed={result!r}"
    )
