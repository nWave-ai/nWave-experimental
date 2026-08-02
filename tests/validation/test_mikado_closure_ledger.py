# @feature-f-mikado-node-closure-record @slice-02
"""Acceptance tests -- D70 `mikado_closure_ledger` (slice-02, reader).

Feature: f-mikado-node-closure-record, slice-02. Full design:
docs/feature/f-mikado-node-closure-record/feature-delta.md +
docs/feature/f-mikado-node-closure-record/design/adrs/adr-D70-mikado-node-closure-record.md
(ADR-D70 D70-6).

SCOPE: `scripts/validation/mikado_closure_ledger.py` (NEW sibling module to
`validate_mikado_tree_coherence.py`) -- the pure-function reconciliation
logic promoted from `docs/mikado/prototypes/d70_closure_record_probe.py`,
now sourcing real records via `UnifiedEventStoreAdapter.read()` instead of
an in-memory list, and re-deriving each closure claim independently against
a real (fixture) git object store via the SAME two ports
`validate_mikado_tree_coherence.py` already uses. NOT in scope here: the
gate's own fourth-carrier REJECT/ADVISORY findings (see sibling file
`test_mikado_tree_coherence_gate.py`, "ledger carrier" section).

Given-setup reuses the REAL, ALREADY-SHIPPED slice-01 writer
(`des.cli.mikado_node_closure_attest.main`) to attest every closure record
this file's scenarios need (Pillar 2/3 -- the SAME production path a real
closer would use, never a hand-rolled JSONL row; `AtCompletionLedger`'s own
row shape is an implementation detail this file does not re-derive). The git
object store is a real, hand-built loose-object repo (zlib + hashlib only,
never the `git` binary), reusing the exact fixture-builder pattern
`tests/validation/test_mikado_closure_carries_work.py` already established
(`_store`/`_write_tree`/`_write_commit`) so a "reachable AND carries the
cited path" scenario is genuinely decidable, not merely asserted.

CRITICAL, dispatch-named constraint: `.nwave/telemetry/mikado/` is
per-worktree and gitignored -- on the real trunk it may hold ZERO records
for most nodes. No scenario in this file ever reads the REAL repo's own
ledger; every node id here is fixture-local (a fresh `tmp_path` per test),
and the "zero records for a node" case is a FIRST-CLASS scenario (#1 below),
asserting `COULD_NOT_DETERMINE`, never a silent `OPEN`/`CLOSED`.

RED-for-right-reason: every public function in `mikado_closure_ledger.py` is
a DISTILL scaffold that raises a bare `AssertionError("__SCAFFOLD__: ...")`
uncaught. Every scenario below reaches that scaffold in its FINAL assertion
step -- the GIVEN-setup (real writer attestations, real git fixture) always
succeeds first, so a failure here is that same semantic `AssertionError`,
never a collection-time `ImportError`.
"""

from __future__ import annotations

import hashlib
import sys
import zlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from git_commit_contents import LooseObjectContents
from git_commit_reachability import (
    LooseObjectReachability,
    UnavailableReachability,
)
from mikado_closure_ledger import (
    NodeState,
    RefusalCause,
    evaluate_node,
    independently_verify,
    node_refusal_cause,
    refusal_cause,
)

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.cli import mikado_node_closure_attest
from des.domain.telemetry_paths import LedgerFamily, telemetry_root
from des.testing.output_capture import CapturingOutput


TRUNK_REF = "feature/atdd-pure-staging"


# ===========================================================================
# a real, hand-built loose-object git repo -- zlib + hashlib only, reusing
# the tree/blob fixture builder from test_mikado_closure_carries_work.py
# ===========================================================================


def _store(objects: Path, kind: bytes, body: bytes) -> str:
    raw = kind + b" " + str(len(body)).encode() + b"\x00" + body
    sha = hashlib.sha1(raw).hexdigest()
    target = objects / sha[:2] / sha[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zlib.compress(raw))
    return sha


def _write_tree(objects: Path, layout: dict) -> str:
    """``{"name": "content"}`` for a blob, ``{"name": {...}}`` for a subtree."""
    entries = []
    for name in sorted(layout):
        value = layout[name]
        if isinstance(value, dict):
            mode, oid = b"40000", _write_tree(objects, value)
        else:
            mode, oid = b"100644", _store(objects, b"blob", value.encode())
        entries.append(mode + b" " + name.encode() + b"\x00" + bytes.fromhex(oid))
    return _store(objects, b"tree", b"".join(entries))


def _write_commit(objects: Path, tree: str, parents: list[str], message: str) -> str:
    lines = [f"tree {tree}"] + [f"parent {p}" for p in parents]
    lines.append("author T <t@example.com> 1700000000 +0000")
    lines.append("committer T <t@example.com> 1700000000 +0000")
    body = ("\n".join(lines) + "\n\n" + message + "\n").encode()
    return _store(objects, b"commit", body)


@pytest.fixture
def repo(tmp_path: Path):
    """A real trunk of two commits: a base, and one that rewrites
    ``docs/mikado/plan.md`` -- the ONE real path a "carries the cited path"
    scenario cites. Also provisions the healthy telemetry substrate the
    real slice-01 writer's `probe()` requires (Earned Trust, DD-14)."""
    git_dir = tmp_path / ".git"
    objects = git_dir / "objects"
    objects.mkdir(parents=True)
    (objects / "pack").mkdir()

    base_layout = {"docs": {"mikado": {"plan.md": "v1"}}, "src": {"cli.py": "v1"}}
    base = _write_commit(objects, _write_tree(objects, base_layout), [], "base")

    on_trunk_layout = {
        "docs": {"mikado": {"plan.md": "v2 -- closes D70"}},
        "src": {"cli.py": "v1"},
    }
    on_trunk = _write_commit(
        objects, _write_tree(objects, on_trunk_layout), [base], "closes D70"
    )

    ref = git_dir / "refs" / "heads" / "feature" / "atdd-pure-staging"
    ref.parent.mkdir(parents=True)
    ref.write_text(on_trunk + "\n")

    telemetry_root(tmp_path).mkdir(parents=True, exist_ok=True)

    return {
        "path": tmp_path,
        "on_trunk": on_trunk,
        "trunk_path": "docs/mikado/plan.md",
        "reachability": LooseObjectReachability(tmp_path),
        "contents": LooseObjectContents(tmp_path),
    }


def _attest(
    repo_root: Path,
    node_id: str,
    *,
    transition: str = "closed",
    cited_sha: str,
    cited_artifact_path: str,
    attesting_act: str = "human:quinn",
) -> None:
    """Given-setup: attest a real MIKADO record through the SHIPPED slice-01
    writer -- never a hand-rolled JSONL row."""
    argv = [
        "--repo-root",
        str(repo_root),
        "--node-id",
        node_id,
        "--transition",
        transition,
        "--cited-sha",
        cited_sha,
        "--cited-artifact-path",
        cited_artifact_path,
        "--attesting-act",
        attesting_act,
    ]
    exit_code = mikado_node_closure_attest.main(argv, output=CapturingOutput())
    assert exit_code == 0, (
        f"fixture setup: attesting {node_id!r} through the real writer must "
        f"succeed -- got exit_code={exit_code}"
    )


def _closed_record(repo_root: Path, node_id: str) -> dict:
    """The one closed-transition record on ``node_id``'s partition -- read
    back through the real store, never reconstructed by hand."""
    adapter = UnifiedEventStoreAdapter(project_root=repo_root)
    result = adapter.read(LedgerFamily.MIKADO, node_id)
    closed = [r for r in result.records if r.get("transition") == "closed"]
    assert closed, f"fixture setup: expected >=1 closed record for {node_id!r}"
    return closed[-1]


# ===========================================================================
# 1. ABSENCE -- zero records for a node is COULD_NOT_DETERMINE, NEVER OPEN
#    and NEVER CLOSED. First-class scenario, per the design's own module
#    docstring AND the dispatch's own CRITICAL constraint: on the real
#    trunk, this IS the common case for most nodes (per-worktree, gitignored
#    ledger).
# ===========================================================================


def test_a_node_with_zero_ledger_records_reads_could_not_determine_never_open(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- zero records -> COULD_NOT_DETERMINE,
    never OPEN, never CLOSED (absence is not evidence of either)."""
    # covers: R19
    state = evaluate_node(
        "D-NEVER-SEEN-BY-THIS-WORKTREE",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.COULD_NOT_DETERMINE


# ===========================================================================
# 2. SEEN-BUT-NOT-CLOSED -- a work_started-only record reads OPEN
# ===========================================================================


def test_a_node_with_only_a_work_started_record_reads_open(repo: dict) -> None:
    """CONTRACT_SHAPE: pure-function -- one work_started record, zero
    closed records -> OPEN (the mechanism has SEEN this node)."""
    # covers: R20
    _attest(
        repo["path"],
        "D-WORK-STARTED-ONLY",
        transition="work_started",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
    )

    state = evaluate_node(
        "D-WORK-STARTED-ONLY",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.OPEN


# ===========================================================================
# 3. REFUSED (cause 1/2) -- a closed record citing a SHA that does not exist
#    in the object store at all reads REFUSED, cause=SHA_NOT_REACHABLE
# ===========================================================================


def test_a_closed_record_citing_a_fabricated_sha_reads_refused_sha_not_reachable(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- a fabricated (nonexistent) cited SHA
    -> REFUSED, distinguishable cause SHA_NOT_REACHABLE."""
    # covers: R21, R30
    _attest(
        repo["path"],
        "D-FABRICATED-SHA",
        cited_sha="d" * 40,
        cited_artifact_path="does/not/matter.py",
    )

    state = evaluate_node(
        "D-FABRICATED-SHA",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )
    assert state is NodeState.REFUSED

    cause = node_refusal_cause(
        "D-FABRICATED-SHA",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )
    assert cause is RefusalCause.SHA_NOT_REACHABLE, (
        "a fabricated SHA must name ITS OWN distinct cause -- never the "
        "'path not carried' cause a reachable-but-wrong-path record gets"
    )


# ===========================================================================
# 4. REFUSED (cause 2/2) -- a closed record citing a REAL, REACHABLE SHA
#    that did NOT rewrite the cited path reads REFUSED,
#    cause=PATH_NOT_CARRIED. Distinguishable from scenario 3's cause (the
#    orchestrator's own CRITICAL constraint: two distinct REFUSED causes,
#    never collapsed).
# ===========================================================================


def test_a_closed_record_citing_a_reachable_sha_with_the_wrong_path_reads_refused_path_not_carried(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- a reachable cited SHA that did NOT
    rewrite the cited path -> REFUSED, distinguishable cause
    PATH_NOT_CARRIED (never the same cause a fabricated SHA gets)."""
    # covers: R22, R30
    _attest(
        repo["path"],
        "D-WRONG-PATH",
        cited_sha=repo["on_trunk"],
        cited_artifact_path="never/rewrote/this/path.py",
    )

    state = evaluate_node(
        "D-WRONG-PATH",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )
    assert state is NodeState.REFUSED

    cause = node_refusal_cause(
        "D-WRONG-PATH",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )
    assert cause is RefusalCause.PATH_NOT_CARRIED, (
        "a reachable-but-wrong-path SHA must name ITS OWN distinct cause -- "
        "never the 'sha not reachable' cause a fabricated SHA gets"
    )


# ===========================================================================
# 5. CLOSED -- a closed record citing a real, reachable SHA that DOES carry
#    the cited path reads CLOSED
# ===========================================================================


def test_a_closed_record_citing_a_reachable_sha_that_carries_the_path_reads_closed(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- a reachable cited SHA that DID
    rewrite the cited path -> CLOSED."""
    # covers: R23
    _attest(
        repo["path"],
        "D-REAL-CLOSE",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
    )

    state = evaluate_node(
        "D-REAL-CLOSE",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.CLOSED


# ===========================================================================
# 6. MULTI-CLAIM RULE -- an earlier REFUSED record and a later CLOSED record
#    on the SAME node: CLOSED WINS (ADR-D70 D70-6 -- "the ledger is
#    append-only... a later verifying record supersedes the false one for
#    read purposes"). Order in the ledger is exactly EARLIER-then-LATER,
#    matching the Contract-Tests table's own wording.
# ===========================================================================


def test_a_later_verifying_record_supersedes_an_earlier_refused_one_closed_wins(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- multiple closed records where an
    earlier one is REFUSED and a later one CLOSED -> CLOSED wins (the
    ADR-D70 multi-claim rule, never the first-seen record deciding)."""
    # covers: R24
    _attest(
        repo["path"],
        "D-SUPERSEDED",
        cited_sha="e" * 40,
        cited_artifact_path="bogus/first/attempt.py",
        attesting_act="human:first-try",
    )
    _attest(
        repo["path"],
        "D-SUPERSEDED",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
        attesting_act="human:correction",
    )

    state = evaluate_node(
        "D-SUPERSEDED",
        project_root=repo["path"],
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.CLOSED, (
        "CLOSED must win if ANY closed-transition record independently "
        "verifies -- a corrected, later record supersedes an earlier false "
        "one for read purposes, without editing the append-only ledger"
    )


# ===========================================================================
# 7. ENVIRONMENTAL READ FAILURE -- an INDETERMINATE reachability answer (the
#    gate_ratchet.py-motivating mid-repack incident, one layer down) reads
#    COULD_NOT_DETERMINE, NEVER REFUSED and NEVER CLOSED
# ===========================================================================


def test_an_indeterminate_reachability_read_is_could_not_determine_never_refused_or_closed(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- an environmental read failure
    (object store mid-repack) is not evidence the claim is false: it must
    read COULD_NOT_DETERMINE, never REFUSED and never CLOSED."""
    # covers: R25
    _attest(
        repo["path"],
        "D-INDETERMINATE-READ",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
    )

    state = evaluate_node(
        "D-INDETERMINATE-READ",
        project_root=repo["path"],
        reachability=UnavailableReachability("object store mid-repack (simulated)"),
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.COULD_NOT_DETERMINE
    assert state is not NodeState.REFUSED
    assert state is not NodeState.CLOSED


# ===========================================================================
# 8. PER-RECORD PINS -- independently_verify()/refusal_cause() operate on
#    ONE record directly (the two functions the design contract names
#    explicitly), mirroring d70_closure_record_probe.py's own two
#    demonstrated observations, widened to the full state space
# ===========================================================================


def test_independently_verify_a_fabricated_record_reads_refused(repo: dict) -> None:
    """CONTRACT_SHAPE: pure-function -- mirrors the prototype's own
    Observation 1 (fabricated record -> REFUSED), at the per-record level."""
    # covers: R21
    _attest(
        repo["path"],
        "D-PER-RECORD-FABRICATED",
        cited_sha="f" * 40,
        cited_artifact_path="src/does/not/matter.py",
    )
    record = _closed_record(repo["path"], "D-PER-RECORD-FABRICATED")

    state = independently_verify(
        record,
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.REFUSED


def test_independently_verify_a_closed_record_with_carried_path_reads_closed(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- a record whose citation is fully
    verified (reachable AND carries the path) -> CLOSED, at the per-record
    level."""
    # covers: R23
    _attest(
        repo["path"],
        "D-PER-RECORD-REAL",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
    )
    record = _closed_record(repo["path"], "D-PER-RECORD-REAL")

    state = independently_verify(
        record,
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert state is NodeState.CLOSED


def test_refusal_cause_is_none_for_a_record_that_independently_verifies_closed(
    repo: dict,
) -> None:
    """CONTRACT_SHAPE: pure-function -- refusal_cause() is None whenever the
    SAME record's independently_verify() is not REFUSED (mutual
    consistency between the two sibling functions)."""
    # covers: R30
    _attest(
        repo["path"],
        "D-PER-RECORD-CAUSE-NONE",
        cited_sha=repo["on_trunk"],
        cited_artifact_path=repo["trunk_path"],
    )
    record = _closed_record(repo["path"], "D-PER-RECORD-CAUSE-NONE")

    cause = refusal_cause(
        record,
        reachability=repo["reachability"],
        contents=repo["contents"],
        trunk_ref=TRUNK_REF,
    )

    assert cause is None, (
        "a record that independently verifies CLOSED must never carry a "
        "REFUSED cause -- the two functions must agree on the same record"
    )


# ===========================================================================
# 9. REGRESSION -- mikado_board.py's own coupled imports still resolve
#    (Prefactoring Assessment: this module's three coupled names --
#    lane_id_candidate, resolve_node_reference, read_dependency_register --
#    are additive-only; the cheap, direct falsification of that claim rather
#    than trusting "additive, so safe" alone)
# ===========================================================================


def test_mikado_board_still_imports_the_three_coupled_names_unchanged() -> None:
    """CONTRACT_SHAPE: unbounded-preservation -- validate_mikado_tree_coherence.py
    still exports lane_id_candidate/resolve_node_reference/
    read_dependency_register byte-identically -- mikado_board.py's own
    blast-radius coupling (feature-delta.md Prefactoring Assessment)."""
    # covers: R32
    from validate_mikado_tree_coherence import (
        lane_id_candidate,
        read_dependency_register,
        resolve_node_reference,
    )

    assert lane_id_candidate("d07") == "D07"
    assert resolve_node_reference("D07", frozenset({"D07"})) == ("D07", ())
    edges, undecidable = read_dependency_register(Path("/does/not/exist.md"))
    assert edges == {} and undecidable == {}
