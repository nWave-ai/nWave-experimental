"""Regression: the `SliceCommitVerified` ledger record must carry the sealed
commit's real git sha -- no check today can join a seal to the commit it
attests.

RCA (this feature's dispatch, `fix-slice-seal-carries-commit-sha`):
``_run_verify_then_record`` (``src/des/cli/verify_slice_commit_completeness.py``
~line 1794) already COMPUTES ``verified_context.commit_sha`` (threaded through
``_VerifiedSliceContext``) and even PRINTS it on the console JSON payload
(``verified_payload["commit_sha"] = verified_context.commit_sha``, ~line
1816) -- but the value is never threaded into the one call that actually
persists the ledger record, ``_append_slice_commit_verified`` (~line 998),
which in turn calls ``AtCompletionLedger.append_gate_event`` (``adapters/
driven/logging/at_completion_ledger.py`` ~line 473) without a ``commit_sha``
kwarg. The printed line is honest; the durable record is not -- so nothing
that reads back a ``SliceCommitVerified`` record from the ledger (the
carpaccio chain, an audit, a future consumer check) can ever recover WHICH
commit that seal was for.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver (`des commit-slice`),
captured via ``capsys`` -- this is what a real ``des commit-slice`` run does,
folding in the canonical verify-then-record path
(``verify_slice_commit_completeness._run_verify_then_record``) itself.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
this file mirrors, verbatim, the AT-EXEMPT ``@prefactoring``-lane fixture
family from the proven GREEN precedent
``tests/bugs/des/test_commit_slice_writes_verified_record.py`` -- a 0-AT
``@prefactoring``-annotated entering slice makes E1+E2+E3 all genuinely
clear (E1 trivially -- empty ``.feature`` candidate set; E2 EXEMPT
short-circuit; E3 UNARMED -- no examine charter authored) without needing a
real feature-scoped pytest suite to pass. See that file's own docstring for
the full rationale; duplicated here per this test family's own convention
(each ``test_commit_slice_*`` file owns its fixture verbatim rather than
cross-importing another test module's private helpers).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main
from tests.des._helpers.commit_slice_git_template import provision_commit_slice_repo


_FEATURE_ID = "fix-slice-seal-carries-commit-sha-at"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"


# ---------------------------------------------------------------------------
# Shared fixture builders (mirrors test_commit_slice_writes_verified_record.py)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    provision_commit_slice_repo(root)


def _write_feature_delta_with_prefactoring_entering_slice(
    repo: Path, feature_id: str
) -> None:
    """A minimal feature-delta carrying the `[REF] Slice Plan` table --
    `_PREDECESSOR` is an ordinary AT-bearing row, `_ENTERING` is annotated
    `@prefactoring` (EXEMPT)."""
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_PREDECESSOR} | the predecessor slice ships a real scenario | "
        "pending | | a real AT-bearing slice |\n"
        f"| {_ENTERING} | a behavior-preserving refactor introduces the seam | "
        "pending | @prefactoring | a green-to-green prefactoring |\n",
        encoding="utf-8",
    )


def _commit_predecessor_with_at(repo: Path, feature_id: str) -> None:
    """Commit `_PREDECESSOR` with a real `@slice-01`-tagged `.feature` file
    (raw git -- not under test here)."""
    feat_dir = repo / "tests" / "acceptance" / feature_id.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{_PREDECESSOR}.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: the predecessor slice's behaviour\n\n"
        f"  @{_PREDECESSOR}\n"
        "  Scenario: the predecessor delivers its observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): predecessor behaviour\n\nSlice-Id: {_PREDECESSOR}",
    )


def _mark_predecessor_verified(repo: Path, feature_id: str) -> None:
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=_PREDECESSOR
    )


def _author_entering_slice_production_change(repo: Path) -> None:
    """The `_ENTERING` slice's behavior-preserving production-only change --
    NO new `.feature` file, mirroring the real 0-AT prefactoring shape."""
    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'refactored, same behaviour'\n",
        encoding="utf-8",
    )


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_slice_commit_verified_record_carries_commit_sha(
    tmp_path: Path, capsys
) -> None:
    """After a real `des commit-slice --feature-id ... --slice-id slice-02`
    run (E1+E2+E3 all genuinely clear via the AT-EXEMPT `@prefactoring`
    lane), the `SliceCommitVerified` ledger record it writes for slice-02
    must carry `commit_sha` equal to the ACTUAL sealed commit's real git sha
    -- resolved independently via `git rev-parse HEAD`, never hardcoded.

    RED for the right reason: `_append_slice_commit_verified` never threads
    `verified_context.commit_sha` (already computed by its caller,
    `_run_verify_then_record`) into `AtCompletionLedger.append_gate_event`,
    so the persisted record has no `commit_sha` key -- `record.get(
    "commit_sha")` is `None`, which never equals a real 40-character git
    sha. A semantic `AssertionError`, not a crash or collection error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta_with_prefactoring_entering_slice(repo, _FEATURE_ID)
    _commit_predecessor_with_at(repo, _FEATURE_ID)
    _mark_predecessor_verified(repo, _FEATURE_ID)
    _author_entering_slice_production_change(repo)

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _ENTERING,
            "--message",
            "refactor(slice): behavior-preserving seam introduces the exemption",
        ]
    )
    capsys.readouterr()  # drain stdout; this AT reads the ledger, not the console line

    assert exit_code == 0, (
        f"expected the slice commit to land and verify cleanly -- "
        f"exit_code={exit_code!r}"
    )

    actual_sha = _git(repo, "rev-parse", "HEAD").strip()
    assert len(actual_sha) == 40, (
        f"expected a real 40-character git sha resolved independently via "
        f"`git rev-parse HEAD`, got {actual_sha!r}"
    )

    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    records = ledger.read_records(event_type="SliceCommitVerified", slice_id=_ENTERING)
    assert records, (
        f"expected `des commit-slice`'s own fold-in to have written a "
        f"SliceCommitVerified record for {_ENTERING!r} -- observed zero "
        f"records in the ledger"
    )
    record = records[-1]
    assert record.get("commit_sha") == actual_sha, (
        f"WHAT: the SliceCommitVerified ledger record for {_ENTERING!r} does "
        f"not carry commit_sha={actual_sha!r} (the real sealed commit's git "
        f"sha, resolved independently via `git rev-parse HEAD`). WHY: "
        f"`_run_verify_then_record` "
        f"(src/des/cli/verify_slice_commit_completeness.py) already computes "
        f"`verified_context.commit_sha` and even prints it on the console "
        f"JSON payload, but never threads it into "
        f"`_append_slice_commit_verified` -> "
        f"`AtCompletionLedger.append_gate_event` -- so no check can join a "
        f"seal to the commit it attests. HOW: add an optional `commit_sha` "
        f"kwarg to both functions (default None, threaded into `fields` + "
        f"hashed into `record_hash`), following the exact existing precedent "
        f"of `attested_via`/`regression_test_file`/`predecessor`. observed "
        f"commit_sha={record.get('commit_sha')!r}, full record={record!r}"
    )


# ===========================================================================
# NEGATIVE AT -- additive/optional invariant, green now AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_slice_commit_verified_record_never_carries_commit_sha_when_not_passed(
    tmp_path: Path,
) -> None:
    """A `SliceCommitVerified` record written the OLD way -- with no
    `commit_sha` ever threaded, exactly as every one of the pre-existing
    historical records was written -- must carry NO `commit_sha` key at all.

    The field must stay purely additive/optional, never required, never
    breaking historical record parsing: this must hold both BEFORE this fix
    (trivially -- the kwarg does not exist yet) and AFTER it (the kwarg
    defaults to `None` and is only added to `fields` when not-`None`, per the
    exact existing precedent of `attested_via` / `regression_test_file` /
    `predecessor` in `AtCompletionLedger.append_gate_event`).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    historical_slice_id = "slice-99-historical"
    ledger = AtCompletionLedger(_FEATURE_ID + "-historical", repo)
    ledger.append_gate_event(
        "SliceCommitVerified",
        historical_slice_id,
        attested_via=None,
        regression_test_file=None,
    )

    records = ledger.read_records(
        event_type="SliceCommitVerified", slice_id=historical_slice_id
    )
    assert records, "expected the historical-shape record to have been written"
    record = records[-1]
    assert "commit_sha" not in record, (
        f"WHAT: a SliceCommitVerified record written the OLD way (no "
        f"commit_sha ever passed) unexpectedly carries a commit_sha key. "
        f"WHY: this breaks the additive/optional contract -- historical "
        f"records (written before this field existed) must parse exactly as "
        f"before. HOW: the commit_sha kwarg must default to None and be "
        f"added to `fields` only when not-None, mirroring "
        f"attested_via/regression_test_file/predecessor. observed keys="
        f"{sorted(record.keys())!r}"
    )
