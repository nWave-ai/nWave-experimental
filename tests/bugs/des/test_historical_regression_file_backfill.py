"""Regression (feature-delta ``fix-shipped-regression-file-backfill``, gap
#2 -- the HISTORICAL-GAP half): a shipped slice whose regression-evidence
bookkeeping predates the ``regression_test_file`` field (#59,
``fix-commit-slice-reverify-uses-stored-file``) has NO stored declaration
AND, when its real file happens to live outside the naming convention, NO
resolvable path at all -- ``_shipped_and_entering_regression_files``
(``verify_slice_commit_completeness.py:793-848``) degrades the ENTIRE
commit to ``SliceCommitIndeterminate`` (reason
``shipped_regression_file_unresolvable``) with NO recovery path today.

Charter: docs/product/expectations/fix-shipped-regression-file-backfill/
a-developer-unblocks-commit-slice-past-an-earlier-shipped-slices-
regression-gap.md (Fixture A -- the historical-gap half).

THE FIX (crafter's job, NOT implemented by this AT -- test-authoring only,
zero ``src/`` edits): a NEW CLI subcommand, ``des backfill-regression-file``
(module ``src/des/cli/backfill_regression_file.py``, ``main(argv) -> int``,
registered in ``des.cli.__main__``'s dispatcher registry AND in
``tests/des/acceptance/single_entry_point/steps/domain_types.py``'s
``SUBCOMMAND_TABLE`` mirror -- that mirror-table AT already exists and is
NOT re-authored here). It attests, with a REAL commit + a REAL file-existing
check, that a named shipped slice's regression file genuinely existed and
passed at a genuine point in this branch's own history, and records a
``RegressionFileHistoricalBackfill`` ledger record via the SAME per-feature
``AtCompletionLedger`` ``des commit-slice`` already writes to. A later
``des commit-slice`` for a NEW entering slice then resolves a shipped
slice's regression file via, in priority order: (1) the slice's OWN stored
``SliceCommitVerified.regression_test_file`` (existing, #59, unchanged),
(2) a ``RegressionFileHistoricalBackfill`` record for that slice (NEW,
THIS fix), (3) the naming-convention glob (existing, unchanged, still last
resort) -- whichever resolves, the SAME on-tree existence check applies
before it is trusted.

CLI contract this AT PRESCRIBES (the crafter implements EXACTLY this --
Quinn, the acceptance-designer, is the author of this contract, not merely
its consumer):

    des backfill-regression-file
        --repo <path>                 (required)
        --feature-id <id>             (required)
        --slice-id <id>               (required -- the SHIPPED slice being backfilled)
        --regression-test-file <path> (required, repo-relative)
        --at-kind {pytest-regression,native-regression,rust-regression}  (required;
                                        'rust-regression' normalizes to
                                        'native-regression', mirroring commit_slice.py)
        --commit <commit-ish>         (required -- where this file was genuinely shipped)
        --reason <text>               (required, non-empty human justification)
        --override                   (flag, default off)

Validation order, each refusal exit 1 with a single-line JSON payload on
stdout carrying ``"event": "RegressionFileBackfillRefused"`` and a
DISTINCT, named ``"reason"`` per cause:

    a. ``--reason`` empty/whitespace           -> reason ``reason_required``
    b. slice-id never SHIPPED (no SliceCommitVerified record for
       feature-id in this repo's ledger)       -> reason ``slice_never_shipped``
    c. ``--commit`` is NOT an ancestor of (and
       not equal to) current HEAD              -> reason ``commit_not_ancestor_of_head``
    d. ``--regression-test-file`` does not
       exist in ``--commit``'s committed tree  -> reason ``regression_test_file_missing_at_commit``
    e. a backfill record for this EXACT
       (feature-id, slice-id) already exists
       and ``--override`` was NOT passed        -> reason ``duplicate_backfill_without_override``

    f. otherwise: exit 0, ``"event":
       "RegressionFileBackfillRecorded"``, appends ONE
       ``RegressionFileHistoricalBackfill`` ledger record (feature_id,
       slice_id, regression_test_file, at_kind, commit_sha, content_digest
       [sha256 over the file's REAL bytes AT that commit], reason, override)
       to ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` via the SAME
       ``AtCompletionLedger`` ``des commit-slice`` uses.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.backfill_regression_file.main()`` CLI driver (once the crafter
creates it) composed with the REAL ``des.cli.commit_slice.main()`` CLI
driver -- both in-process with ``capsys``, mirroring this feature's sibling
regression file
``test_prefactoring_exempt_shipped_slice_unblocks_commit.py`` and its own
precedent ``test_commit_slice_reverify_uses_stored_regression_file.py``.

GIT SAFETY: every git call below targets a DISPOSABLE ``tmp_path`` fixture
only. No git WRITE ever touches this repository.

RED-for-right-reason (Mandate-7): ``des.cli.backfill_regression_file`` does
not exist yet on this branch -- the module import is wrapped in a
try/except so file COLLECTION always succeeds, and every test starts with
``_require_backfill_module()``, which turns the absence into a genuine,
message-carrying ``pytest.fail`` (never a bare, uncaught
``ModuleNotFoundError`` traceback) naming exactly what is missing and why.
This is the acceptable RED shape for a wholly NET-NEW CLI subcommand (per
task brief): "expect ModuleNotFoundError/ImportError initially ... make sure
the FAILURE MESSAGE/test docstring makes clear this is not yet implemented,
not a mistake."

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass. This test must NEVER be weakened or skipped to reach GREEN.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


try:
    from des.cli.backfill_regression_file import main as backfill_regression_file_main

    _BACKFILL_MODULE_AVAILABLE = True
except ModuleNotFoundError:
    _BACKFILL_MODULE_AVAILABLE = False
    backfill_regression_file_main = None  # type: ignore[assignment]


_BACKFILL_NOT_IMPLEMENTED_MSG = (
    "des.cli.backfill_regression_file does not exist yet -- NOT YET "
    "IMPLEMENTED (feature-delta fix-shipped-regression-file-backfill, "
    "Fixture A -- the historical-gap recovery path). This is the expected "
    "RED shape for this bugfix's DISTILL-authored regression tests: the "
    "whole CLI subcommand is net-new, so its module is absent until the "
    "crafter implements it -- see this test module's docstring (the CLI "
    "contract Quinn prescribes) and the charter at "
    "docs/product/expectations/fix-shipped-regression-file-backfill/"
    "a-developer-unblocks-commit-slice-past-an-earlier-shipped-slices-"
    "regression-gap.md."
)


def _require_backfill_module() -> None:
    if not _BACKFILL_MODULE_AVAILABLE:
        pytest.fail(_BACKFILL_NOT_IMPLEMENTED_MSG)


# ---------------------------------------------------------------------------
# fixture builders (disposable git repos; every git write targets `root` only)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_scratch_repo(root: Path, name: str = "repo") -> Path:
    """A minimal, disposable git repo -- baseline commit only.

    ``name`` is threaded into BOTH the committed file content and the commit
    message (not just the directory name): git is content-addressed, so two
    scratch repos built with identical tree + message + author/committer +
    no parent collide on the SAME root commit SHA regardless of wall-clock
    timing or directory path. Two "unrelated" scratch repos must never
    accidentally share a root commit -- see
    ``test_backfill_refuses_when_the_commit_is_not_an_ancestor_of_head``,
    which relies on ``fixture`` and ``unrelated_repo`` being genuinely
    disjoint histories.
    """
    fixture = root / name
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text(f"# scratch fixture: {name}\n", encoding="utf-8")
    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "atdd@nwave.ai")
    _git(fixture, "config", "user.name", "atdd")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", f"chore: scratch fixture baseline ({name})")
    return fixture


def _write_trivial_regression_file(
    fixture: Path, rel_path: str, feature_id: str, slice_id: str, marker: int
) -> Path:
    """A self-contained, tagged, trivially-passing pytest regression file."""
    target = fixture / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        f"def test_{slice_id.replace('-', '_')}_thing():\n"
        f"    assert {marker} + {marker} == {marker * 2}\n",
        encoding="utf-8",
    )
    return target


def _write_rust_regression_file(fixture: Path, rel_path: str) -> Path:
    """A real, controlled .rs fixture with genuine #[test] functions."""
    target = fixture / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "// Regression fixture -- historical slice-01 (backfilled).\n\n"
        "#[test]\n"
        "fn slice_01_behaviour_holds() {\n"
        "    assert_eq!(2 + 2, 4);\n"
        "}\n",
        encoding="utf-8",
    )
    return target


def _commit_all(fixture: Path, message: str) -> str:
    """A plain `git commit` (NOT via commit_slice) -- simulates a historical
    slice that shipped BEFORE #59 (the regression_test_file ledger field)
    existed: the file is genuinely committed to this branch's own history,
    but no `des commit-slice` CLI ever ran for it."""
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", message)
    return _git(fixture, "rev-parse", "HEAD").strip()


def _inject_historical_slice_commit_verified(
    fixture: Path, feature_id: str, slice_id: str, commit_sha: str
) -> None:
    """Hand-inject a `SliceCommitVerified` record carrying NO
    `regression_test_file` field -- simulates a historical (pre-#59) record
    that predates the stored-declaration mechanism, per the task brief's
    suggested "write a SliceCommitVerified ledger record by hand (bypassing
    commit_slice)" construction (more hermetic than shipping normally then
    hand-stripping the JSONL field, which would break the record's
    tamper-evident `record_hash`)."""
    AtCompletionLedger(feature_id, fixture).append_gate_event(
        "SliceCommitVerified", slice_id, commit_sha=commit_sha
    )


def _git_bytes_at_commit(fixture: Path, commit: str, rel_path: str) -> bytes:
    """The REAL raw bytes of `rel_path` as committed at `commit` -- the
    independent oracle for `content_digest`, read via git directly (never
    assumed identical to the current working tree, even though this file's
    scenarios never mutate the file after the historical commit)."""
    return subprocess.run(
        ["git", "cat-file", "-p", f"{commit}:{rel_path}"],
        cwd=fixture,
        check=True,
        capture_output=True,
    ).stdout


# ---------------------------------------------------------------------------
# observables
# ---------------------------------------------------------------------------


def _run_commit_slice(
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    captured = capsys.readouterr()
    return exit_code, captured.out + "\n" + captured.err


def _run_backfill(
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    assert backfill_regression_file_main is not None  # narrows for mypy/runtime
    exit_code = backfill_regression_file_main(["--repo", str(repo), *argv_tail])
    captured = capsys.readouterr()
    return exit_code, captured.out + "\n" + captured.err


def _last_json_event(output: str) -> dict[str, object]:
    json_lines = [line for line in output.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON diagnostic line -- got none in {output!r}"
    payload = json.loads(json_lines[-1])
    assert isinstance(payload, dict)
    return payload


def _diag(exit_code: int, output: str) -> str:
    return f"\nexit_code={exit_code!r}\noutput={output!r}"


def _backfill_records(
    repo: Path, feature_id: str, slice_id: str
) -> list[dict[str, object]]:
    return AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="RegressionFileHistoricalBackfill"
    )


# ===========================================================================
# Scenario 2 -- historical backfill SUCCESS, pytest-regression.
# ===========================================================================


def test_backfilling_a_historical_pytest_regression_gap_unblocks_the_next_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """slice-01 shipped historically (a plain `git commit`, no #59-era
    `regression_test_file` stored) with a `.py` regression file at a
    NON-convention path. `des backfill-regression-file` records the
    historical gap; a subsequent `des commit-slice` for slice-02 (a
    genuinely new entering slice) must then clear end-to-end: real commit,
    valid `Gate-Scope:` trailer, `SliceCommitVerified` for slice-02.
    """
    _require_backfill_module()
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-historical-pytest"
    slice_one_rel = "tests/bugs/repro/historical_slice_01_gap.py"
    _write_trivial_regression_file(fixture, slice_one_rel, feature_id, "slice-01", 1)
    historical_commit = _commit_all(
        fixture, "feat(slice): slice-01 ships historically (pre-#59 record)"
    )
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-01", historical_commit
    )
    assert "slice-01" in AtCompletionLedger(feature_id, fixture).verified_slices(), (
        "test-setup precondition: the hand-injected historical record must "
        "register slice-01 as shipped."
    )

    expected_digest = hashlib.sha256(
        _git_bytes_at_commit(fixture, historical_commit, slice_one_rel)
    ).hexdigest()

    backfill_exit, backfill_output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            slice_one_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            historical_commit,
            "--reason",
            "slice-01 genuinely shipped and passed pre-#59; recovering the "
            "stored declaration retroactively",
        ],
        capsys,
    )
    assert backfill_exit == 0, (
        "a well-formed historical backfill (real ancestor commit, real "
        "on-tree file, non-empty reason, no prior backfill for this slice) "
        "must succeed." + _diag(backfill_exit, backfill_output)
    )
    backfill_event = _last_json_event(backfill_output)
    assert backfill_event.get("event") == "RegressionFileBackfillRecorded", (
        f"expected a RegressionFileBackfillRecorded event -- got "
        f"{backfill_event!r}." + _diag(backfill_exit, backfill_output)
    )

    records = _backfill_records(fixture, feature_id, "slice-01")
    assert len(records) == 1, (
        f"expected exactly one RegressionFileHistoricalBackfill record for "
        f"slice-01 -- observed records={records!r}."
        + _diag(backfill_exit, backfill_output)
    )
    record = records[0]
    assert record.get("regression_test_file") == slice_one_rel, (
        f"the ledger record must name the backfilled file -- observed "
        f"record={record!r}."
    )
    assert record.get("commit_sha") == historical_commit, (
        f"the ledger record must name the attested commit -- observed "
        f"record={record!r}."
    )
    assert record.get("content_digest") == expected_digest, (
        "the ledger record's content_digest must be the sha256 over the "
        f"file's REAL bytes AT that commit -- observed record={record!r}, "
        f"expected_digest={expected_digest!r}."
    )
    assert isinstance(record.get("reason"), str) and record["reason"], (
        f"the ledger record must carry the human reason -- observed record={record!r}."
    )

    # slice-02: a genuinely new, independent, passing regression file.
    slice_two_rel = "tests/bugs/repro/test_slice_02_after_historical_backfill.py"
    _write_trivial_regression_file(fixture, slice_two_rel, feature_id, "slice-02", 2)
    commit_exit, commit_output = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--message",
            "feat(slice): slice-02 lands after the historical backfill",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            slice_two_rel,
        ],
        capsys,
    )
    assert commit_exit == 0, (
        "slice-02's commit must clear des commit-slice end-to-end once "
        "slice-01's historical gap has been backfilled."
        + _diag(commit_exit, commit_output)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" in verified_slices, (
        f"slice-02 must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified_slices)!r}."
        + _diag(commit_exit, commit_output)
    )
    committed_event = next(
        (
            json.loads(line)
            for line in commit_output.splitlines()
            if line.strip().startswith("{") and '"SliceCommitted"' in line
        ),
        None,
    )
    assert committed_event is not None and committed_event.get("verified") is True, (
        "a genuinely sealed slice-02 must carry a SliceCommitted event with "
        f"verified: true -- observed committed_event={committed_event!r}."
        + _diag(commit_exit, commit_output)
    )


# ===========================================================================
# Scenario 3 -- historical backfill SUCCESS, native-regression (Rust),
# monkeypatched runner (no real cargo toolchain needed) -- proves the
# mechanism is at-kind-agnostic.
# ===========================================================================


def test_backfilling_a_historical_native_regression_gap_unblocks_the_next_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SAME shape as the pytest-regression scenario, for a `.rs` file,
    `--at-kind native-regression`. The runner-port execution seam is
    monkeypatched (mirroring
    ``test_at_discovery_facet_pair_unifies_rust_and_python_regression_
    slices.py``'s approach of faking the runner dispatch rather than
    shelling real cargo) so this AT stays hermetic and fast -- the CONCRETE
    proof the backfill mechanism is at-kind-agnostic.
    """
    _require_backfill_module()
    from des.cli import verify_slice_commit_completeness as vscc
    from des.ports.test_runner_port import RunnerAdapter, RunVerdict

    class _FakeCargoRunnerAdapter(RunnerAdapter):
        def run(
            self, target_root: Path, scoped_node_ids: tuple[str, ...]
        ) -> RunVerdict:
            return RunVerdict(passed=True, runner=self.name)

    def _fake_resolve_runner(repo: Path, context: object) -> RunnerAdapter:
        return _FakeCargoRunnerAdapter(name="cargo-test")

    monkeypatch.setattr(vscc, "resolve_runner", _fake_resolve_runner)

    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-historical-native"
    slice_one_rel = "tests/rust/regression/historical_slice_01_gap.rs"
    _write_rust_regression_file(fixture, slice_one_rel)
    historical_commit = _commit_all(
        fixture, "feat(slice): slice-01 (Rust) ships historically"
    )
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-01", historical_commit
    )

    expected_digest = hashlib.sha256(
        _git_bytes_at_commit(fixture, historical_commit, slice_one_rel)
    ).hexdigest()

    backfill_exit, backfill_output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            slice_one_rel,
            "--at-kind",
            "native-regression",
            "--commit",
            historical_commit,
            "--reason",
            "slice-01 (Rust) genuinely shipped and passed historically",
        ],
        capsys,
    )
    assert backfill_exit == 0, (
        "a well-formed historical backfill for a non-Python (.rs) file must "
        "succeed identically to the pytest-regression case."
        + _diag(backfill_exit, backfill_output)
    )
    record = _backfill_records(fixture, feature_id, "slice-01")[0]
    assert record.get("at_kind") == "native-regression", (
        f"the ledger record must carry the resolved at_kind -- observed "
        f"record={record!r}."
    )
    assert record.get("content_digest") == expected_digest, (
        f"content_digest must seal the REAL .rs raw source bytes at the "
        f"attested commit -- observed record={record!r}."
    )

    # slice-02: a genuinely new, independent, passing PYTHON regression
    # file -- proves per-file routing (the .rs shipped file routes through
    # the runner-port seam; the .py entering file keeps the pytest-native
    # path), exactly as `_routes_through_runner_port` already decides.
    slice_two_rel = "tests/bugs/repro/test_slice_02_after_native_historical_backfill.py"
    _write_trivial_regression_file(fixture, slice_two_rel, feature_id, "slice-02", 2)
    commit_exit, commit_output = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--message",
            "feat(slice): slice-02 lands after the native historical backfill",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            slice_two_rel,
        ],
        capsys,
    )
    assert commit_exit == 0, (
        "slice-02's commit must clear des commit-slice end-to-end once "
        "slice-01's HISTORICAL RUST gap has been backfilled -- the "
        "mechanism must be at-kind-agnostic." + _diag(commit_exit, commit_output)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-02" in verified_slices, (
        f"slice-02 must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified_slices)!r}."
        + _diag(commit_exit, commit_output)
    )


# ===========================================================================
# Scenario 4 -- backfill REFUSAL: the declared file does not exist at the
# declared commit.
# ===========================================================================


def test_backfill_refuses_when_the_file_does_not_exist_at_the_declared_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require_backfill_module()
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-refuse-missing-file"
    slice_one_rel = "tests/bugs/repro/historical_slice_01_gap.py"
    _write_trivial_regression_file(fixture, slice_one_rel, feature_id, "slice-01", 1)
    historical_commit = _commit_all(fixture, "feat(slice): slice-01 ships historically")
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-01", historical_commit
    )

    nonexistent_rel = "tests/bugs/repro/never_committed_anywhere.py"
    exit_code, output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            nonexistent_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            historical_commit,
            "--reason",
            "attempting to name a file that was never actually committed",
        ],
        capsys,
    )
    assert exit_code == 1, (
        "a backfill naming a file absent from the declared commit's "
        "committed tree must refuse (exit 1)." + _diag(exit_code, output)
    )
    event = _last_json_event(output)
    assert event.get("event") == "RegressionFileBackfillRefused", (
        f"expected RegressionFileBackfillRefused -- got {event!r}."
        + _diag(exit_code, output)
    )
    assert event.get("reason") == "regression_test_file_missing_at_commit", (
        f"expected reason=regression_test_file_missing_at_commit -- got "
        f"{event!r}." + _diag(exit_code, output)
    )
    assert not _backfill_records(fixture, feature_id, "slice-01"), (
        "a refused backfill attempt must append NO "
        "RegressionFileHistoricalBackfill ledger record." + _diag(exit_code, output)
    )


# ===========================================================================
# Scenario 5 -- backfill REFUSAL: the declared commit is not an ancestor of
# (nor equal to) HEAD.
# ===========================================================================


def test_backfill_refuses_when_the_commit_is_not_an_ancestor_of_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require_backfill_module()
    fixture = _init_scratch_repo(tmp_path, name="repo")
    feature_id = "fix-shipped-regression-gap-refuse-not-ancestor"
    slice_one_rel = "tests/bugs/repro/historical_slice_01_gap.py"
    _write_trivial_regression_file(fixture, slice_one_rel, feature_id, "slice-01", 1)
    historical_commit = _commit_all(fixture, "feat(slice): slice-01 ships historically")
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-01", historical_commit
    )

    # A REAL commit sha, but from a wholly UNRELATED, disposable second
    # repo -- unknown to `fixture`'s own object database, so it can never
    # be an ancestor of (or equal to) `fixture`'s HEAD.
    unrelated_repo = _init_scratch_repo(tmp_path, name="unrelated-repo")
    foreign_sha = _git(unrelated_repo, "rev-parse", "HEAD").strip()

    exit_code, output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            slice_one_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            foreign_sha,
            "--reason",
            "attempting to attest a commit from an unrelated repository",
        ],
        capsys,
    )
    assert exit_code == 1, (
        "a backfill naming a commit unknown to / not an ancestor of this "
        "repo's HEAD must refuse (exit 1)." + _diag(exit_code, output)
    )
    event = _last_json_event(output)
    assert event.get("event") == "RegressionFileBackfillRefused", (
        f"expected RegressionFileBackfillRefused -- got {event!r}."
        + _diag(exit_code, output)
    )
    assert event.get("reason") == "commit_not_ancestor_of_head", (
        f"expected reason=commit_not_ancestor_of_head -- got {event!r}."
        + _diag(exit_code, output)
    )
    assert not _backfill_records(fixture, feature_id, "slice-01"), (
        "a refused backfill attempt must append NO "
        "RegressionFileHistoricalBackfill ledger record." + _diag(exit_code, output)
    )


# ===========================================================================
# Scenario 6 -- backfill REFUSAL: duplicate without --override; the FIRST
# record still stands unchanged.
# ===========================================================================


def test_backfill_refuses_a_duplicate_without_override_and_the_first_record_stands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _require_backfill_module()
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-refuse-duplicate"
    first_rel = "tests/bugs/repro/historical_slice_01_first_target.py"
    _write_trivial_regression_file(fixture, first_rel, feature_id, "slice-01", 1)
    second_rel = "tests/bugs/repro/historical_slice_01_second_target.py"
    _write_trivial_regression_file(fixture, second_rel, feature_id, "slice-01", 9)
    historical_commit = _commit_all(
        fixture, "feat(slice): slice-01 ships historically with two candidate files"
    )
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-01", historical_commit
    )

    first_exit, first_output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            first_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            historical_commit,
            "--reason",
            "first, genuine backfill of slice-01's historical gap",
        ],
        capsys,
    )
    assert first_exit == 0, "the FIRST backfill attempt must succeed." + _diag(
        first_exit, first_output
    )

    second_exit, second_output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--regression-test-file",
            second_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            historical_commit,
            "--reason",
            "a SECOND, conflicting backfill attempt naming a different file",
        ],
        capsys,
    )
    assert second_exit == 1, (
        "a second backfill for the SAME (feature-id, slice-id) WITHOUT "
        "--override must refuse (exit 1) -- append-only, never a silent "
        "supersede." + _diag(second_exit, second_output)
    )
    second_event = _last_json_event(second_output)
    assert second_event.get("event") == "RegressionFileBackfillRefused", (
        f"expected RegressionFileBackfillRefused -- got {second_event!r}."
        + _diag(second_exit, second_output)
    )
    assert second_event.get("reason") == "duplicate_backfill_without_override", (
        f"expected reason=duplicate_backfill_without_override -- got "
        f"{second_event!r}." + _diag(second_exit, second_output)
    )

    records = _backfill_records(fixture, feature_id, "slice-01")
    assert len(records) == 1, (
        "the refused second attempt must NOT append a second "
        f"RegressionFileHistoricalBackfill record -- observed records="
        f"{records!r}." + _diag(second_exit, second_output)
    )
    assert records[0].get("regression_test_file") == first_rel, (
        "the FIRST record must remain unchanged (naming the FIRST target "
        f"file) -- observed records={records!r}."
    )

    # Confirm the FIRST backfill's file is what a later commit actually
    # resolves and executes -- not merely that a ledger record exists.
    slice_two_rel = "tests/bugs/repro/test_slice_02_after_duplicate_refusal.py"
    _write_trivial_regression_file(fixture, slice_two_rel, feature_id, "slice-02", 2)
    commit_exit, commit_output = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--message",
            "feat(slice): slice-02 lands after the duplicate-refused backfill",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            slice_two_rel,
        ],
        capsys,
    )
    assert commit_exit == 0, (
        "slice-02 must still commit cleanly via the FIRST (unrejected) "
        "backfill record." + _diag(commit_exit, commit_output)
    )
    verified_event = _last_json_event(commit_output)
    executed = verified_event.get("regression_test_files_executed")
    assert isinstance(executed, list) and first_rel in executed, (
        "the FIRST backfill's target file must be the one actually EXECUTED "
        f"for slice-01's re-check -- observed regression_test_files_executed="
        f"{executed!r}." + _diag(commit_exit, commit_output)
    )
    assert second_rel not in (executed or []), (
        "the SECOND (refused) backfill's target file must never be "
        f"executed -- observed regression_test_files_executed={executed!r}."
        + _diag(commit_exit, commit_output)
    )


# ===========================================================================
# Scenario 8 -- end-to-end: a fresh entering slice commits cleanly when BOTH
# a prefactoring-exempt shipped slice AND a backfilled shipped slice
# coexist in the same feature.
# ===========================================================================


def test_entering_slice_commits_past_both_a_prefactoring_exemption_and_a_backfill(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """slice-01 (`@prefactoring`, zero AT by design) and slice-02 (a
    historical gap, backfilled) both SHIP; slice-03, a genuinely new
    entering slice, must then commit cleanly -- real commit, valid
    `Gate-Scope:` trailer, `SliceCommitVerified` for slice-03. This is the
    "Outcome needed" acceptance bar: BOTH recovery mechanisms coexisting in
    one feature, neither interfering with the other.
    """
    _require_backfill_module()
    fixture = _init_scratch_repo(tmp_path)
    feature_id = "fix-shipped-regression-gap-e2e-both-mechanisms"

    delta_dir = fixture / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | prefactoring precondition for slice-02/03 | planned | "
        "@prefactoring | Behavior-preserving, no regression file by design |\n"
        "| slice-02 | earlier observable behaviour (historical gap) | "
        "planned | | |\n"
        "| slice-03 | the new observable behaviour | planned | | |\n",
        encoding="utf-8",
    )

    # slice-01: @prefactoring, ships with ZERO AT via des commit-slice
    # itself (the prefactoring-exemption half of this feature).
    exit_1, output_1 = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-01",
            "--message",
            "refactor(slice): slice-01 is a prefactoring precondition, no AT",
        ],
        capsys,
    )
    assert exit_1 == 0, "slice-01 (@prefactoring, zero AT) must ship cleanly." + _diag(
        exit_1, output_1
    )

    # slice-02: a HISTORICAL gap -- shipped via a plain git commit (no #59
    # stored declaration), then recovered via des backfill-regression-file.
    slice_two_rel = "tests/bugs/repro/historical_slice_02_gap.py"
    _write_trivial_regression_file(fixture, slice_two_rel, feature_id, "slice-02", 2)
    historical_commit = _commit_all(
        fixture, "feat(slice): slice-02 ships historically (pre-#59 record)"
    )
    _inject_historical_slice_commit_verified(
        fixture, feature_id, "slice-02", historical_commit
    )
    backfill_exit, backfill_output = _run_backfill(
        fixture,
        [
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-02",
            "--regression-test-file",
            slice_two_rel,
            "--at-kind",
            "pytest-regression",
            "--commit",
            historical_commit,
            "--reason",
            "slice-02 genuinely shipped and passed historically",
        ],
        capsys,
    )
    assert backfill_exit == 0, (
        "backfilling slice-02's historical gap must succeed."
        + _diag(backfill_exit, backfill_output)
    )

    # slice-03: a genuinely new entering slice.
    slice_three_rel = "tests/bugs/repro/test_slice_03_after_both_mechanisms.py"
    _write_trivial_regression_file(fixture, slice_three_rel, feature_id, "slice-03", 3)
    exit_3, output_3 = _run_commit_slice(
        fixture,
        [
            "--all",
            "--feature-id",
            feature_id,
            "--slice-id",
            "slice-03",
            "--message",
            "feat(slice): slice-03 delivers the new observable behaviour",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            slice_three_rel,
        ],
        capsys,
    )
    assert exit_3 == 0, (
        "slice-03 must commit cleanly with BOTH an earlier @prefactoring "
        "exemption AND an earlier historical backfill in play."
        + _diag(exit_3, output_3)
    )
    verified_slices = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert "slice-03" in verified_slices, (
        f"slice-03 must earn a SliceCommitVerified ledger record -- observed "
        f"verified_slices={sorted(verified_slices)!r}." + _diag(exit_3, output_3)
    )
    committed_event = next(
        (
            json.loads(line)
            for line in output_3.splitlines()
            if line.strip().startswith("{") and '"SliceCommitted"' in line
        ),
        None,
    )
    assert committed_event is not None and committed_event.get("verified") is True, (
        "a genuinely sealed slice-03 must carry a SliceCommitted event with "
        f"verified: true -- observed committed_event={committed_event!r}."
        + _diag(exit_3, output_3)
    )
    verified_event = _last_json_event(output_3)
    exempt_list = verified_event.get("prefactoring_exempt_shipped_slices")
    assert isinstance(exempt_list, list) and any(
        isinstance(entry, dict) and entry.get("slice_id") == "slice-01"
        for entry in exempt_list
    ), (
        "slice-01's @prefactoring exemption must still be named in the "
        f"final verdict -- observed exempt_list={exempt_list!r}."
        + _diag(exit_3, output_3)
    )
    executed = verified_event.get("regression_test_files_executed")
    assert isinstance(executed, list) and slice_two_rel in executed, (
        "slice-02's BACKFILLED file must be among the files actually "
        f"executed for this commit -- observed regression_test_files_executed="
        f"{executed!r}." + _diag(exit_3, output_3)
    )
