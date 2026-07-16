"""Regression (GDP-1): `des commit-slice` must write the `SliceCommitVerified`
ledger record ITSELF -- not depend on the SubagentStop hook (which never fires
on a folded lean-cycle commit) to invoke `des verify-slice-commit` afterward.

Charter: ``docs/product/expectations/fix-commit-slice-writes-verified-record/
commit-slice-guarantees-the-verified-record.md``.

Found in ``src/des/cli/commit_slice.py`` ``main()`` (~line 754): the command
stages, commits with a placeholder ``Gate-Scope:`` trailer, computes + amends
the committed-scope digest, runs the build-tier + examine-verdict exit checks,
verifies clean via ``run_contract_gate --verify-gate-scope``, and emits
``SliceCommitted`` -- but never invokes the canonical verify-then-record path
(E1 completeness + E2 feature-scoped contract gate + E3 examine,
``verify_slice_commit_completeness._run_verify_then_record``). That record is
today written ONLY by ``des verify-slice-commit --feature-id`` itself, invoked
via the SubagentStop hook -- which does not fire on a folded lean-cycle commit,
orphaning the slice for its successor's carpaccio-order check
(``AtCompletionLedger.verified_slices()``).

The fix direction (charter, NOT implemented here): after a successful verified
commit (when ``--feature-id`` is given), ``commit-slice`` folds in the SAME
verify-then-record on HEAD and writes exactly one `SliceCommitVerified` record
IFF E1+E2+E3 all clear -- the honesty invariant: never fabricated when any leg
fails.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``
-- NOT ``des verify-slice-commit`` and NOT the SubagentStop hook. The whole
point of this AT is to prove the record comes from ``commit-slice`` alone.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
  * ``_init_repo`` -- the exact pytest-collectible git work-tree shape from
    the proven GREEN precedent ``tests/des/integration/test_commit_slice.py``
    (pytest.ini + conftest.py + ``tests/unit/test_base.py`` + pinned
    ``core.hooksPath``). ``des commit-slice`` computes a WHOLE-TREE committed-
    scope digest (``_committed_scope_digest_value``) and re-verifies it
    (``run_contract_gate --verify-gate-scope``) BEFORE it ever reaches the
    (not-yet-implemented) fold-in -- this must succeed today exactly as it
    already does in that suite, so the same repo shape is reused verbatim.
  * The AT-EXEMPT ``@prefactoring`` lane (``LANE_PROFILES["prefactoring"]``,
    ``AtRequirement.EXEMPT``) -- the proven GREEN precedent
    ``tests/des/cli/f_prefactoring_dispatch_clears_honestly/
    test_bugfix_exit_gate_honors_prefactoring_lane.py`` -- to make E1+E2+E3
    of the (future) fold-in genuinely clear WITHOUT needing a real feature-
    scoped contract-gate subprocess to pass: a 0-AT `@prefactoring`-annotated
    slice has an EMPTY `.feature` candidate set (E1 trivially clears -- nothing
    missing), short-circuits E2 (the entry gate's own EXEMPT skip, honored
    symmetrically at exit), and carries no examine charter under
    ``docs/product/expectations/{feature_id}/`` (E3 UNARMED). This is the
    CHEAPEST reliable E1+E2+E3-clearing fixture available in the codebase --
    building a fixture where a REAL feature-scoped pytest suite passes would
    require materializing step-bindings for a genuine `.feature` scenario,
    which the cited precedents avoid via this exact same lane trick.

E3 note: neither fixture below authors a charter under
``docs/product/expectations/{feature_id}/`` -- the examine-verdict gate stays
UNARMED for both, so this AT does not additionally depend on
``des record-examine-verdict`` machinery (already exercised by
``tests/des/integration/test_commit_slice_examine_gate.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


_POSITIVE_FEATURE_ID = "fix-commit-slice-writes-verified-record-pos"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"

_NEGATIVE_FEATURE_ID = "fix-commit-slice-writes-verified-record-neg"
_NEGATIVE_SLICE = "slice-02"


# ---------------------------------------------------------------------------
# Shared fixture builders
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
    """Init a real pytest-collectible git work-tree (mirrors
    ``tests/des/integration/test_commit_slice.py``'s ``_init_repo`` verbatim
    -- the exact shape that already makes ``des commit-slice``'s whole-tree
    committed-scope digest + ``run_contract_gate --verify-gate-scope``
    succeed today).
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into the hook-count tests.
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


# --- POSITIVE fixture (the AT-EXEMPT @prefactoring lane) --------------------


def _write_feature_delta_with_prefactoring_entering_slice(
    repo: Path, feature_id: str
) -> None:
    """A minimal feature-delta carrying the `[REF] Slice Plan` table -- mirrors
    ``test_bugfix_exit_gate_honors_prefactoring_lane.py::_write_feature_delta``
    verbatim: ``_PREDECESSOR`` is an ordinary AT-bearing row, ``_ENTERING`` is
    annotated ``@prefactoring`` (EXEMPT).
    """
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
    (raw git -- mirrors the proven precedent's own predecessor commit, not
    under test here)."""
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


def test_commit_slice_writes_slice_commit_verified_record(
    tmp_path: Path, capsys
) -> None:
    """After a successful `des commit-slice --feature-id ... --slice-id
    slice-02` commit (E1+E2+E3 all genuinely clear via the AT-EXEMPT
    `@prefactoring` lane), a `SliceCommitVerified` ledger record for slice-02
    must exist -- written by `commit-slice` ITSELF, with NO
    `des verify-slice-commit` invocation and NO SubagentStop hook involved.

    RED for the right reason: `commit-slice.main()` today only emits
    `SliceCommitted`; it never invokes the verify-then-record fold-in, so
    `AtCompletionLedger.verified_slices()` never gains `slice-02` -- a
    semantic `AssertionError` on the absent record, not a crash or collection
    error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta_with_prefactoring_entering_slice(repo, _POSITIVE_FEATURE_ID)
    _commit_predecessor_with_at(repo, _POSITIVE_FEATURE_ID)
    _mark_predecessor_verified(repo, _POSITIVE_FEATURE_ID)
    _author_entering_slice_production_change(repo)

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            _POSITIVE_FEATURE_ID,
            "--slice-id",
            _ENTERING,
            "--message",
            "refactor(slice): behavior-preserving seam introduces the exemption",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    # The existing commit-slice behavior is unchanged (charter item 2) --
    # already true today, must stay true after the fix.
    assert exit_code == 0, (
        f"expected the slice commit to land and verify cleanly -- exit_code="
        f"{exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event
    assert event.get("verified") is True, event

    verified = AtCompletionLedger(_POSITIVE_FEATURE_ID, repo).verified_slices()
    assert _ENTERING in verified, (
        f"expected `des commit-slice` itself to write a SliceCommitVerified "
        f"ledger record for {_ENTERING} after its own successful verified "
        "commit (--feature-id given) -- with NO `des verify-slice-commit` "
        "invocation and NO SubagentStop hook involved. Today commit-slice "
        "writes NO such record (only SliceCommitted is emitted), so a folded "
        "lean-cycle commit (where the hook never fires) orphans the slice "
        f"for its successor's carpaccio-order check. observed verified_slices="
        f"{sorted(verified)!r}"
    )


# ===========================================================================
# NEGATIVE AT -- honesty invariant, green now AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_commit_slice_writes_no_verified_record_when_at_incomplete(
    tmp_path: Path, capsys
) -> None:
    """A slice commit that OMITS its declared `.feature` AT file (the RCA
    Branch-A defect the E1 completeness leg exists to catch) must NEVER earn
    a `SliceCommitVerified` record -- the fold-in's honesty invariant: no
    fabricated pass when the verify-then-record's E1 leg would fail.

    Post reorder+carve-out (fix-commit-slice-verify-before-commit slice-01),
    the E1 completeness leg now runs PRE-FLIGHT (before the commit lands),
    so this reproduction is refused outright (`SliceCommitRefused`, E1,
    naming the missing `.feature` file) rather than landing a commit with no
    verified record -- a STRONGER instance of the same honesty invariant:
    zero commit, therefore trivially zero fabricated record.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    feature_path = repo / "tests" / "acceptance" / "fixture_slice.feature"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(
        f"@feature-{_NEGATIVE_FEATURE_ID}\n"
        "Feature: fixture feature\n\n"
        f"  @{_NEGATIVE_SLICE}\n"
        "  Scenario: fixture scenario\n"
        "    Given a fixture precondition\n"
        "    When the fixture action occurs\n"
        "    Then the fixture outcome holds\n",
        encoding="utf-8",
    )
    # Deliberately NOT staged -- authored, never persisted into any commit
    # (RCA Branch-A: an AT file the slice authored but never committed).

    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'behaviour without its AT file'\n",
        encoding="utf-8",
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--path",
            str(prod_file.relative_to(repo)),
            "--feature-id",
            _NEGATIVE_FEATURE_ID,
            "--slice-id",
            _NEGATIVE_SLICE,
            "--message",
            "feat(slice): behaviour without its AT file",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    # Post reorder+carve-out: the E1 pre-flight now refuses this commit
    # BEFORE it lands (it names the missing .feature file), rather than
    # letting it land silently without a verified record.
    assert exit_code == 1, (
        f"expected the slice commit to be refused pre-flight (E1: missing "
        f".feature AT file) -- exit_code={exit_code!r}, event={event!r}"
    )
    assert event.get("event") == "SliceCommitRefused", event
    assert event.get("refused_half") == "E1", event

    verified = AtCompletionLedger(_NEGATIVE_FEATURE_ID, repo).verified_slices()
    assert _NEGATIVE_SLICE not in verified, (
        f"a slice commit missing its declared .feature AT file must NEVER "
        f"earn a fabricated SliceCommitVerified record -- observed "
        f"verified_slices={sorted(verified)!r}"
    )
