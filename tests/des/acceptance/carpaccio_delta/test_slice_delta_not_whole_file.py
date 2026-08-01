"""Regression -- the carpaccio size gate charges a slice for tests it did NOT
add, when the regression file is SHARED with earlier features/bugfixes.

DEFECT (defects.md: ``carpaccio-pytest-route-counts-whole-file-not-slice-
delta``). Measured 2026-07-28 delivering slice-06 of ``declared-facts-
reachable-recorded``: extending ``test_verify_red_green.py`` (5 tests already
on disk from PRIOR features and bugfixes) with 3 new ATs made
``des carpaccio-slice-gate --at-kind pytest-regression`` reject
``CARPACCIO_SLICE_TOO_LARGE`` with ``at_count=8`` against the ceiling of 7 --
though the slice added 3.

RCA (established, NOT assumed -- and it FALSIFIES the recorded hypothesis).
The hypothesis in defects.md was that the ceiling is applied to the whole-file
total while ``count_net_new_pytest_regression_ats`` sits unused. That is FALSE:
``check_carpaccio`` (``carpaccio_format.py:1295``) DOES route the ceiling
comparison through ``count_net_new_pytest_regression_ats``. The real cause is
one level down -- that function's "net" subtracts only
``_predecessor_attested_at_total``, which reads ``ATReviewVerdict`` records
from ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``: a FEATURE-SCOPED
ledger, keyed by the entering slice's OWN feature. Tests that a PRIOR feature
or a bugfix left in the file are attested in a different ledger (or in none at
all, for a bugfix), so they subtract 0 and are charged to the entering slice.
The verdict record carries no file path (``at_review_verdict.py:79-89``), so
the ledger cannot be made to answer the per-file question at all.

This is GDP-8: the gate decides on a DESIGNATION (what my own feature's ledger
says about my predecessor slices) rather than on the PROPERTY (which of this
file's tests is this slice actually introducing). The perverse consequence is
that the gate PENALISES reusing an existing test file and REWARDS spawning new
ones -- the exact inverse of the reuse-first discipline DESIGN enforces
upstream.

The property IS observable, filesystem-only and git-free (GDP-7), and is
already produced by the flow one step earlier: the RED seal
``.nwave/telemetry/red-green/{slug}.json`` written by ``des verify-red-green
--record-red``. Its ``outcomes`` map marks exactly the ATs this slice is
introducing ``fail`` (they witness behavior that does not exist yet) and every
already-delivered test ``pass``. The seal is content-bound
(``content_sha256``), so it cannot be stretched to cover tests added after RED
was recorded. No new artifact is invented: the validation DERIVES from the
flow.

The fix (crafter's job, NOT implemented by these ATs -- test-authoring only,
zero ``src/`` edits): ``count_net_new_pytest_regression_ats`` must prefer the
fresh RED seal's failing set, intersected with the module-level ``test_*``
names the existing AST rules already recognise, and fall back to today's
whole-file-minus-feature-ledger behavior whenever the seal is absent, stale or
unusable. These ATs pin the OUTCOME (which count reaches the ceiling), never
the mechanism.

Driving port (Mandate 16, no-direct-domain-testing): every AT drives the REAL
``des carpaccio-slice-gate`` CLI EDGE (``des.cli.carpaccio_slice_gate.main``)
in-process via ``tests.common.in_process_cli.run_cli_in_process`` -- the same
entry point the operator invokes, never the counting helper called directly.
The seal fixture is written to disk at the path the PRODUCER itself resolves
(``verify_red_green._seal_path``) rather than at a re-derived one, so the
fixture can never drift from the producer's slug rule.

RED-for-right-reason: today all three scenarios observe ``at_count=8`` against
the ceiling of 7. The positive AT asserts a genuine semantic ``AssertionError``
(``CARPACCIO_SLICE_TOO_LARGE`` fires where the delta of 3 is under the
ceiling), never an import or collection error; the two negative ATs pass today
and guard the fix against overcorrecting into a blanket permit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process

from des.cli.carpaccio_slice_gate import main as carpaccio_slice_gate_main
from des.cli.verify_red_green import _seal_path


_FEATURE_ID = "carpaccio-slice-delta"
_ENTERING_SLICE = "slice-01"
_FRAMEWORK_DEFAULT = 15  # raised from 7 (Ale, 2026-08-01) -- see carpaccio_format.py
_REGRESSION_REL = "tests/regression/test_shared_fixture.py"


def _write_feature_delta(repo: Path) -> None:
    """A minimal one-row Slice Plan -- no annotation/justification, so
    assertions 3 (walking-skeleton-first) and 4 (value-annotation) pass
    trivially and the size-ceiling check (assertion 1) is the only gate that
    can fire on size."""
    path = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | a cohesive regression AT group | pending | | |\n",
        encoding="utf-8",
    )


def _write_regression_file(repo: Path, *, delivered: int, entering: int) -> Path:
    """A real pytest regression file carrying `delivered` already-shipped
    tests plus `entering` tests the slice under gate is introducing.

    Both groups are ordinary module-level ``def test_*`` functions -- to the
    AST counter the file is indistinguishable from one whose every test is
    net-new, which is precisely the confusion under test.
    """
    path = repo / _REGRESSION_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    shipped = [
        f"def test_delivered_by_an_earlier_feature_{i}():\n    assert True"
        for i in range(delivered)
    ]
    fresh = [
        f"def test_introduced_by_this_slice_{i}():\n    assert True"
        for i in range(entering)
    ]
    path.write_text("\n\n".join(shipped + fresh) + "\n", encoding="utf-8")
    return path


def _record_red_seal(
    repo: Path,
    regression_file: Path,
    *,
    delivered: int,
    entering: int,
    content_sha: str | None = None,
) -> None:
    """Write the RED seal `des verify-red-green --record-red` would have
    written for this file: the slice's own ATs FAIL (they witness behavior
    that does not exist yet), every already-delivered test PASSES.

    ``content_sha`` overrides the recorded hash so a scenario can present a
    STALE seal (one recorded before further tests were appended).
    """
    module = _REGRESSION_REL.removesuffix(".py").replace("/", ".")
    outcomes: dict[str, str] = {
        f"{module}::test_delivered_by_an_earlier_feature_{i}": "pass"
        for i in range(delivered)
    }
    outcomes.update(
        {
            f"{module}::test_introduced_by_this_slice_{i}": "fail"
            for i in range(entering)
        }
    )
    seal = _seal_path(repo, regression_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": _REGRESSION_REL,
                "content_sha256": content_sha
                or hashlib.sha256(regression_file.read_bytes()).hexdigest(),
                "outcomes": outcomes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_carpaccio_slice_gate(repo: Path) -> tuple[int, str, str]:
    """Drive the REAL `des carpaccio-slice-gate` CLI EDGE in-process."""
    return run_cli_in_process(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE,
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            _REGRESSION_REL,
        ],
        cwd=repo,
        main=carpaccio_slice_gate_main,
    )


def _diagnostic(stdout: str) -> dict[str, object]:
    """The gate's single JSON verdict line, as a dict ({} when it emitted none)."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        parsed = json.loads(lines[0])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ===========================================================================
# POSITIVE -- a populated file must not charge the slice for another
# feature's tests
# ===========================================================================


def test_populated_test_file_charges_slice_only_for_the_ats_it_adds(
    tmp_path: Path,
) -> None:
    """A slice adding 3 ATs to a file already carrying 5 tests delivered by
    EARLIER features/bugfixes must clear the size ceiling: its delta is 3,
    well under 7.

    The RED seal on disk states the split unambiguously -- 5 passing, 3
    failing -- so the property "how many ATs is this slice introducing" is
    observable at gate time without git and without the feature ledger.
    Today the gate ignores it and rejects on 5+3=8.
    """
    repo = tmp_path / "repo"
    _write_feature_delta(repo)
    regression_file = _write_regression_file(repo, delivered=5, entering=3)
    _record_red_seal(repo, regression_file, delivered=5, entering=3)

    exit_code, stdout, stderr = _run_carpaccio_slice_gate(repo)
    diagnostic = _diagnostic(stdout)

    assert diagnostic.get("event") != "CARPACCIO_SLICE_TOO_LARGE", (
        "a slice adding 3 ATs to a file holding 5 tests delivered by earlier "
        "features must NOT be rejected as oversized -- the ceiling is 7 and "
        "the slice's delta is 3. The RED seal on disk marks exactly 3 tests "
        f"failing. Got at_count={diagnostic.get('at_count')!r} "
        f"(the whole-file total), exit_code={exit_code}, "
        f"diagnostic={diagnostic!r}, stderr={stderr[:200]!r}"
    )


# ===========================================================================
# NEGATIVE (no-overcorrection guard) -- the fix must not become a blanket
# permit
# ===========================================================================


@pytest.mark.negative_at
def test_genuinely_oversized_slice_is_not_excused_by_its_red_seal(
    tmp_path: Path,
) -> None:
    """A slice whose OWN 8 net-new ATs all fail at RED -- nothing pre-existing
    in the file -- must still be rejected as oversized.

    Guards the fix against degenerating into "a RED seal exists, therefore
    pass": consulting the seal must SHRINK the charge to the slice's true
    delta, never waive the ceiling.
    """
    repo = tmp_path / "repo"
    _write_feature_delta(repo)
    oversized = _FRAMEWORK_DEFAULT + 1
    regression_file = _write_regression_file(repo, delivered=0, entering=oversized)
    _record_red_seal(repo, regression_file, delivered=0, entering=oversized)

    exit_code, stdout, _stderr = _run_carpaccio_slice_gate(repo)
    diagnostic = _diagnostic(stdout)

    assert diagnostic.get("event") == "CARPACCIO_SLICE_TOO_LARGE", (
        f"a slice introducing {oversized} genuinely net-new ATs exceeds the "
        f"ceiling of {_FRAMEWORK_DEFAULT} and must still be rejected -- "
        "consulting the RED seal must never waive the ceiling for a slice "
        f"that really is too large. Got exit_code={exit_code}, "
        f"diagnostic={diagnostic!r}"
    )


@pytest.mark.negative_at
def test_stale_red_seal_never_shrinks_the_charged_at_count(tmp_path: Path) -> None:
    """A seal recorded BEFORE further tests were appended is content-stale and
    must never be trusted to reduce the charge.

    Fail-closed (GDP-6): were a stale seal honoured, an operator could record
    RED on 1 test and then append any number more, each of them invisible to
    the ceiling. The file holds more tests than the ceiling allows and the
    seal's ``content_sha256`` does not match it, so the gate must fall back
    to today's whole-file behavior and reject. Delivered/entering split
    raised (5/3 -> `_FRAMEWORK_DEFAULT`/1, Ale 2026-08-01) so the fixture's
    whole-file total still genuinely exceeds whatever ceiling is in effect.
    """
    repo = tmp_path / "repo"
    _write_feature_delta(repo)
    delivered = _FRAMEWORK_DEFAULT
    entering = 1
    oversized = delivered + entering
    regression_file = _write_regression_file(
        repo, delivered=delivered, entering=entering
    )
    _record_red_seal(
        repo,
        regression_file,
        delivered=delivered,
        entering=entering,
        content_sha="0" * 64,
    )
    assert hashlib.sha256(regression_file.read_bytes()).hexdigest() != "0" * 64, (
        "test setup invariant: the seal's recorded hash must genuinely mismatch"
    )

    exit_code, stdout, _stderr = _run_carpaccio_slice_gate(repo)
    diagnostic = _diagnostic(stdout)

    assert diagnostic.get("event") == "CARPACCIO_SLICE_TOO_LARGE", (
        "a content-stale RED seal must NEVER shrink the charged AT count -- "
        f"the file carries {oversized} module-level tests and the seal no "
        "longer describes it, so the gate must degrade to the whole-file "
        f"count and reject. Got exit_code={exit_code}, diagnostic={diagnostic!r}"
    )
