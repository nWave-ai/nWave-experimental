# @feature-f-mikado-node-closure-record @slice-01
"""Acceptance tests -- D70 `mikado_node_closure_attest` (slice-01, writer).

Feature: f-mikado-node-closure-record, slice-01. Full design:
docs/feature/f-mikado-node-closure-record/feature-delta.md +
docs/feature/f-mikado-node-closure-record/design/adrs/adr-D70-mikado-node-closure-record.md
(ADR-D70).

SCOPE: `src/des/cli/mikado_node_closure_attest.py` (NEW `des`-importing CLI,
registered as `des mikado-attest-node-closure`). Writes exactly one PRIMARY
`LedgerFamily.MIKADO` record via `EventStorePort.append` for every well-formed
`--transition {closed,work_started}` invocation. Never independently verifies
`--cited-sha`/`--cited-artifact-path` against `.git/` (D70-5) -- the record's
own claim is a DESIGNATION, re-derived independently only at READ time by the
slice-02 reader (`scripts/validation/mikado_closure_ledger.py`, OUT OF SCOPE
for this file). NOT in scope here: slice-02's fourth carrier in
`validate_mikado_tree_coherence.py`.

Driving port (Mandate 16, no-direct-domain-testing; Mandate 2, IN-PROCESS
default): every scenario except the single `@walking_skeleton` drives the
REAL `mikado_node_closure_attest.main(argv, output=CapturingOutput())`
in-process (no interpreter fork) against a REAL `UnifiedEventStoreAdapter` on
`tmp_path` -- no double, per feature-delta.md's own Unobservability
Declaration ("a test double substituted for EventStorePort... cannot attest
that the REAL D80 store... actually accepts the write"). The single
`@walking_skeleton @driving_port` scenario drives the installed `des` console
entry as a real subprocess (`python -m des.cli ...`), proving the subcommand
is wired end-to-end through the real registry -- the ONE subprocess-e2e this
FEATURE gets (Mandate 2's "ONE per feature", authored with this, its first,
slice).

NO `.git/` DIRECTORY IS EVER CREATED ANYWHERE IN THIS FILE. This is
deliberate and load-bearing: D70-5 requires the writer to perform ZERO git
verification, and the strongest possible proof of that is a writer that
succeeds in a repository that has no `.git/` at all (see
`test_writer_never_independently_verifies_the_cited_sha_against_git_...`
below). An AT that asserts the writer verifies a SHA against git would
contradict the design and must not be authored (dispatch instruction).

RED-for-right-reason: `mikado_node_closure_attest._attest` is a DISTILL
scaffold that raises a bare `AssertionError` uncaught (module docstring).
Every scenario below that reaches past argparse therefore fails on that SAME
semantic AssertionError today, never a collection-time `ImportError` (the
module, `add_repo_root_argument`, `UnifiedEventStoreAdapter`, `CapturingOutput`
all import cleanly). The pure-argparse scenarios (the `--transition`
closed-vocabulary refusal, `--help` discoverability) exercise REAL argparse
behaviour and may already pass at scaffold stage -- that is real production
behaviour, not fixture theater, and DELIVER must not regress it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.application.how_executability import invocations_in, rejections
from des.cli import mikado_node_closure_attest
from des.domain.telemetry_paths import LedgerFamily, telemetry_root
from des.ports.driven_ports.event_store_port import EventRecord, PartitionKeyRequired
from des.ports.driven_ports.probeable_port import StoreProbeFailed
from des.testing.output_capture import CapturingOutput


_WRITER_SCRIPT = Path(mikado_node_closure_attest.__file__)
_REPO_ROOT = Path(__file__).resolve().parents[4]


# ===========================================================================
# Shared fixture-writing + driving + assertion helpers
# ===========================================================================


def _provision_healthy_telemetry_root(repo_root: Path) -> None:
    """The ONE place a happy-path scenario provisions `.nwave/telemetry/` --
    mirrors `unified_event_store` slice-02's own `given_healthy_sandbox`
    fixture technique (`tests/des/acceptance/unified_event_store/steps/
    composition.py::given_healthy_sandbox`). A scenario that omits this call
    exercises the missing-directory probe-failure path instead (R11)."""
    telemetry_root(repo_root).mkdir(parents=True, exist_ok=True)


def _argv(
    repo_root: Path,
    *,
    node_id: str = "D70-close",
    transition: str = "closed",
    cited_sha: str = "a" * 40,
    cited_artifact_path: str = "docs/mikado/EXECUTION-SSOT-des-optimization.md",
    attesting_act: str = "human:quinn",
) -> list[str]:
    """The full, well-formed argv -- every scenario overrides only the ONE
    flag it is exercising, never rebuilds the whole invocation (Pillar 2)."""
    return [
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


def _run(argv: list[str]) -> tuple[int, CapturingOutput]:
    """Drive the REAL writer in-process (Mandate 2 L2 default)."""
    cap = CapturingOutput()
    exit_code = mikado_node_closure_attest.main(argv, output=cap)
    return exit_code, cap


def _mikado_ledger_file(repo_root: Path, node_id: str) -> Path:
    return repo_root / ".nwave" / "telemetry" / "mikado" / f"{node_id}.jsonl"


def _no_ledger_file_written_anywhere(repo_root: Path) -> bool:
    """True iff `.nwave/telemetry/mikado/` holds no per-node ledger file at
    all -- the strongest "nothing was written" observable, used by refusal
    scenarios where the writer's own pre-check may not yet know the
    partition key it would have written under."""
    mikado_dir = repo_root / ".nwave" / "telemetry" / "mikado"
    if not mikado_dir.is_dir():
        return True
    return not any(mikado_dir.glob("*.jsonl"))


# ===========================================================================
# 1. ROUND-TRIP -- a well-formed invocation preserves the D70-3 record shape
#    verbatim -- R1, R2, R3, R4
# ===========================================================================


@pytest.mark.parametrize(
    ("transition", "expected_event"),
    [
        pytest.param("closed", "NodeClosureAttested", id="closed"),
        pytest.param("work_started", "NodeWorkStartedAttested", id="work_started"),
    ],
)
def test_a_well_formed_invocation_round_trips_with_the_d70_record_shape_preserved(
    tmp_path: Path, transition: str, expected_event: str
) -> None:
    """CONTRACT_SHAPE: bounded-change -- appends exactly one well-formed
    EventRecord to LedgerFamily.MIKADO's partition for node_id."""
    # covers: R1, R2, R3, R4
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(
        tmp_path,
        node_id="D70-close",
        transition=transition,
        cited_sha="b" * 40,
        cited_artifact_path="docs/mikado/EXECUTION-SSOT-des-optimization.md",
        attesting_act="human:quinn",
    )

    exit_code, _cap = _run(argv)

    assert exit_code == 0, f"a well-formed --transition {transition} must exit 0"
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.MIKADO, "D70-close")
    matching = [r for r in result.records if r.get("event") == expected_event]
    assert len(matching) == 1, (
        f"expected exactly one {expected_event!r} record on this partition -- "
        f"got records={result.records!r}"
    )
    row = matching[0]
    assert row.get("scope") == "node", (
        f"scope must be 'node' (D70-3) -- got {row.get('scope')!r}, row={row!r}"
    )
    assert row.get("agent_id") is None, (
        f"agent_id must be null (D70-2 -- the population this writer serves "
        f"is 100% null-agent_id) -- got {row.get('agent_id')!r}, row={row!r}"
    )
    assert row.get("feature_id") is None, (
        f"feature_id must be null (D70-4 -- a Mikado node is not one "
        f"feature's property) -- got {row.get('feature_id')!r}, row={row!r}"
    )
    assert row.get("node_id") == "D70-close", (
        f"node_id must be self-describing inside fields (D70-3) -- "
        f"got {row.get('node_id')!r}, row={row!r}"
    )
    assert row.get("transition") == transition
    assert row.get("attesting_act") == "human:quinn"
    assert row.get("cited_artifact") == {
        "sha": "b" * 40,
        "path": "docs/mikado/EXECUTION-SSOT-des-optimization.md",
    }, (
        f"cited_artifact must round-trip as a nested {{sha, path}} object "
        f"verbatim (D70-4) -- got {row.get('cited_artifact')!r}, row={row!r}"
    )


# ===========================================================================
# 2. DESTINATION PIN -- the record physically lands at the LITERAL per-node
#    mikado path, never recomputed through the resolver under test -- R5
# ===========================================================================


def test_the_written_record_lands_at_the_literal_per_node_mikado_path(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- the record physically lands at the
    literal .nwave/telemetry/mikado/{node_id}.jsonl path, pinned literally."""
    # covers: R5
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(tmp_path, node_id="D80-close")

    exit_code, _cap = _run(argv)

    assert exit_code == 0
    raw_path = tmp_path / ".nwave" / "telemetry" / "mikado" / "D80-close.jsonl"
    assert raw_path.is_file(), (
        f"the record must physically land at the LITERAL path {raw_path} -- "
        "a family with no reachable path is a defect, not a not-yet-written "
        "state (the exact LedgerFamily.RED_GREEN class D80 exists to kill)"
    )
    lines = [ln for ln in raw_path.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 1, f"expected exactly one physical line -- got {lines!r}"


# ===========================================================================
# 3. NEGATIVE -- an empty/whitespace-only required string is refused BEFORE
#    any EventStorePort call; no record written -- R6, R7, R8
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "flag_name",
    ["--attesting-act", "--cited-sha", "--cited-artifact-path"],
)
@pytest.mark.parametrize(
    "blank_value",
    ["", "   ", "\t\n"],
    ids=["empty", "spaces", "tab-newline"],
)
def test_a_blank_required_field_is_refused_before_any_write_no_record_persisted(
    tmp_path: Path, flag_name: str, blank_value: str
) -> None:
    """CONTRACT_SHAPE: bounded-change -- a blank required string is refused
    before any EventStorePort call; the mikado partition stays untouched."""
    # covers: R6, R7, R8
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(tmp_path, node_id="D70-blank-field")
    flag_index = argv.index(flag_name)
    argv[flag_index + 1] = blank_value

    exit_code, cap = _run(argv)

    assert exit_code != 0, (
        f"a blank {flag_name}={blank_value!r} must be refused (non-zero "
        "exit), never silently accepted as a 'closed because I said so' claim"
    )
    text = cap.captured_text()
    assert "WHAT" in text and "WHY" in text and "HOW" in text, (
        f"the refusal must state WHAT/WHY/HOW -- got {text!r}"
    )
    assert flag_name.lstrip("-").replace("-", "_") in text or flag_name in text, (
        f"the refusal must name the offending flag ({flag_name}) -- got {text!r}"
    )
    assert _no_ledger_file_written_anywhere(tmp_path), (
        "a blank required field must refuse BEFORE any EventStorePort call "
        "-- found a ledger file written under .nwave/telemetry/mikado/"
    )


# ===========================================================================
# 4. NEGATIVE -- --transition outside {closed, work_started} is refused by
#    argparse's own choices=, exit code 2 -- R9
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "bogus_transition",
    ["clsoed", "OPEN", "Closed", "work-started", ""],
)
def test_an_out_of_vocabulary_transition_is_refused_by_argparse_exit_2(
    tmp_path: Path, bogus_transition: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: bounded-change -- an out-of-vocabulary --transition
    is refused by argparse's own closed choices=, exit code 2."""
    # covers: R9
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(tmp_path, transition="closed")
    flag_index = argv.index("--transition")
    argv[flag_index + 1] = bogus_transition

    with pytest.raises(SystemExit) as excinfo:
        mikado_node_closure_attest.main(argv, output=CapturingOutput())

    assert excinfo.value.code == 2, (
        f"an out-of-vocabulary --transition={bogus_transition!r} must exit "
        f"with argparse's usage-error code 2 -- got {excinfo.value.code!r}"
    )
    stderr = capsys.readouterr().err
    assert "invalid choice" in stderr, (
        f"argparse's own 'invalid choice' wording must name the accepted "
        f"set -- got stderr={stderr!r}"
    )
    assert "closed" in stderr and "work_started" in stderr, (
        f"the accepted vocabulary must be named verbatim -- got {stderr!r}"
    )


# ===========================================================================
# 5. NEGATIVE -- a store-side refusal for a case the writer's own pre-check
#    did not anticipate (empty --node-id -> PartitionKeyRequired) surfaces
#    verbatim, exit non-zero, writes nothing -- R10
# ===========================================================================


def _independent_partition_key_required_text(tmp_path: Path) -> str:
    """Independently reproduce the EXACT store-side exception text (F1) --
    any node-scoped `EventRecord` with an empty `partition_key` raises the
    identical `PartitionKeyRequired` message, regardless of the record's
    other fields (`event_store_port.py`'s own `_resolve_partition_key` reads
    only `scope` + `partition_key`, never `fields`) -- so this reproduction
    is deterministic and independent of the writer's own field-building,
    the strongest possible verbatim-preservation oracle (never a hardcoded
    string this file and the store's own message could silently drift
    apart from)."""
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    with pytest.raises(PartitionKeyRequired) as excinfo:
        adapter.append(
            EventRecord(
                family=LedgerFamily.MIKADO,
                event="NodeClosureAttested",
                scope="node",
                feature_id=None,
                partition_key="",
                agent_id=None,
                fields={},
            )
        )
    return str(excinfo.value)


@pytest.mark.negative_at
def test_a_store_side_refusal_for_a_precheck_uncovered_case_surfaces_verbatim_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- a store-side PartitionKeyRequired
    refusal (empty --node-id) surfaces verbatim, WHAT/WHY/HOW-encapsulated
    with a re-runnable HOW, and nothing is written."""
    # covers: R10, R17
    _provision_healthy_telemetry_root(tmp_path)
    expected_verbatim_store_text = _independent_partition_key_required_text(tmp_path)
    argv = _argv(tmp_path, node_id="")

    exit_code, cap = _run(argv)

    assert exit_code != 0, (
        "a store-side PartitionKeyRequired refusal (an empty --node-id, "
        "which the writer's own three-string pre-check does not cover) "
        "must exit non-zero"
    )
    text = cap.captured_text()
    assert "PartitionKeyRequired" in text or "partition_key" in text, (
        f"the store's own exception must be surfaced verbatim -- got {text!r}"
    )
    assert "WHAT" in text and "WHY" in text and "HOW" in text, (
        f"the writer must encapsulate the store-side refusal in ITS OWN "
        f"WHAT/WHY/HOW envelope (F1) -- the store's own HOW names a D80-level "
        f"remediation ('pass partition_key=...'), never a re-runnable `des "
        f"mikado-attest-node-closure` invocation, so the writer's busta must "
        f"add its own WHAT/WHY/HOW on top -- got {text!r}"
    )
    _assert_how_clause_is_cli_parseable(text)
    assert expected_verbatim_store_text in text, (
        "the ORIGINAL store-side exception text must remain present and "
        f"recoverable verbatim inside the writer's own busta (R10) -- "
        f"expected {expected_verbatim_store_text!r} to be a substring of "
        f"{text!r}"
    )
    assert _no_ledger_file_written_anywhere(tmp_path), (
        "a store-side refusal must leave zero physical records written"
    )


# ===========================================================================
# 6. NEGATIVE -- a UnifiedEventStoreAdapter.probe() failure refuses BEFORE
#    any append() is attempted (Earned Trust, wire-then-probe-then-use) --
#    R11
# ===========================================================================


def _independent_store_probe_failed_text(tmp_path: Path) -> str:
    """Independently reproduce the EXACT store-side probe exception text
    (F1) -- `StoreAvailabilityProbe.probe()`'s missing-directory fault is a
    deterministic function of `project_root` alone and has NO filesystem
    side effect (it raises before any `mkdir`/canary write), so calling it
    a second time (once here, once inside the CLI below) against the same
    still-missing directory yields the byte-identical message -- never a
    hardcoded string this file and the store's own message could silently
    drift apart from."""
    with pytest.raises(StoreProbeFailed) as excinfo:
        UnifiedEventStoreAdapter(project_root=tmp_path).probe()
    return str(excinfo.value)


@pytest.mark.negative_at
def test_a_probe_failure_refuses_before_any_append_is_attempted(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- a UnifiedEventStoreAdapter.probe()
    failure refuses before any append() attempt (wire-then-probe-then-use),
    WHAT/WHY/HOW-encapsulated with a re-runnable HOW."""
    # covers: R11, R17
    # Deliberately DOES NOT call _provision_healthy_telemetry_root -- the
    # missing .nwave/telemetry/ root is the fault StoreAvailabilityProbe
    # classifies as fault="missing-directory" (store_availability_probe.py).
    expected_verbatim_store_text = _independent_store_probe_failed_text(tmp_path)
    argv = _argv(tmp_path, node_id="D70-probe-fail")

    exit_code, cap = _run(argv)

    assert exit_code != 0, (
        "a broken telemetry substrate must refuse loudly, never report "
        "success by silently skipping the probe"
    )
    text = cap.captured_text()
    assert "WHAT" in text and "WHY" in text and "HOW" in text, (
        f"the probe refusal must be WHAT/WHY/HOW-shaped -- got {text!r}"
    )
    _assert_how_clause_is_cli_parseable(text)
    assert expected_verbatim_store_text in text, (
        "the ORIGINAL store-side probe exception text must remain present "
        f"and recoverable verbatim inside the writer's own busta (R11) -- "
        f"expected {expected_verbatim_store_text!r} to be a substring of "
        f"{text!r}"
    )
    assert not (tmp_path / ".nwave" / "telemetry" / "mikado").exists(), (
        "the probe failure must refuse BEFORE any append() attempt -- the "
        "mikado ledger directory must never even be created"
    )


# ===========================================================================
# 7. NEGATIVE-OF-A-NEGATIVE -- the writer performs ZERO independent git
#    verification, by design (D70-5): a fabricated SHA and a nonexistent
#    path, in a repo with NO .git/ AT ALL, still writes successfully -- R12.
#    "An AT that asserts the writer verifies a SHA against git contradicts
#    the design and must not be authored" (dispatch instruction) -- this is
#    the AT that pins the OPPOSITE, and is the strongest possible proof: if
#    the writer ever touched git internals, this scenario would necessarily
#    fail, because there is no .git/ anywhere under tmp_path.
# ===========================================================================


def test_writer_never_independently_verifies_the_cited_sha_against_git_a_fabricated_citation_still_writes(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- a fabricated SHA/path, in a repo
    with no .git/ at all, still writes successfully (D70-5, designation)."""
    # covers: R12
    assert not (tmp_path / ".git").exists(), (
        "test setup invariant: this scenario's whole point is a repo with "
        "NO .git/ at all -- if this fails, the fixture itself regressed"
    )
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(
        tmp_path,
        node_id="D70-fabricated",
        cited_sha="0000000000000000000000000000000000dead",
        cited_artifact_path="nonexistent/path/that/was/never/tracked.py",
    )

    exit_code, _cap = _run(argv)

    assert exit_code == 0, (
        "a fabricated SHA + nonexistent path must NOT be refused -- the "
        "writer's own claim is a DESIGNATION (D70-5); independent "
        "verification is the READER's job at read time, never the writer's"
    )
    adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
    result = adapter.read(LedgerFamily.MIKADO, "D70-fabricated")
    matching = [r for r in result.records if r.get("event") == "NodeClosureAttested"]
    assert len(matching) == 1
    assert matching[0].get("cited_artifact") == {
        "sha": "0000000000000000000000000000000000dead",
        "path": "nonexistent/path/that/was/never/tracked.py",
    }, "the fabricated citation must round-trip verbatim, unexamined"


# ===========================================================================
# 8. ARCHITECTURE -- static AST pins on the writer module itself -- R13,
#    R14, R15
# ===========================================================================


def test_writer_never_calls_append_derived() -> None:
    """CONTRACT_SHAPE: unbounded-preservation -- static invariant, holds for
    every future edit: the writer source never calls .append_derived(."""
    # covers: R13
    source = _WRITER_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_WRITER_SCRIPT))

    violations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append_derived"
    ]
    assert not violations, (
        f"mikado_node_closure_attest.py must never call .append_derived(...) "
        f"-- agent_id is null for 100% of this writer's population, so DD-8 "
        f"(ReductionKeyIneligible) would refuse every such call -- found "
        f"{len(violations)} call site(s) at line(s) "
        f"{[getattr(v, 'lineno', '?') for v in violations]!r}"
    )


_ALLOWED_IMPORT_ROOTS = frozenset({"argparse", "sys", "pathlib", "typing", "des"})


def test_writer_imports_only_stdlib_and_des_zero_scripts_or_tests_roots() -> None:
    """CONTRACT_SHAPE: unbounded-preservation -- static invariant (F-D-09):
    the writer's import roots stay within {stdlib, des} for every edit."""
    # covers: R14
    source = _WRITER_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_WRITER_SCRIPT))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])

    forbidden = {"scripts", "tests"} & roots
    assert not forbidden, (
        f"mikado_node_closure_attest.py (src/des/**) must import only "
        f"{{stdlib, des}} roots (F-D-09) -- found forbidden root(s) "
        f"{sorted(forbidden)} among {sorted(roots)}"
    )


def test_writer_never_imports_git_reachability_or_git_contents_ports() -> None:
    """CONTRACT_SHAPE: unbounded-preservation -- static invariant (D70-5):
    the writer never imports git_commit_reachability/git_commit_contents."""
    # covers: R15
    source = _WRITER_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_WRITER_SCRIPT))

    forbidden_modules = {"git_commit_reachability", "git_commit_contents"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[-1] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[-1])

    violations = forbidden_modules & imported
    assert not violations, (
        f"mikado_node_closure_attest.py must NEVER import "
        f"git_commit_reachability/git_commit_contents (D70-5: the writer "
        f"performs zero git verification, by design -- independent "
        f"reachability/content re-derivation stays in the read side only) "
        f"-- found {sorted(violations)}"
    )


# ===========================================================================
# 9. HOW-STRING EXECUTABILITY -- every refusal's HOW clause names a real,
#    argparse-parseable des mikado-attest-node-closure ... invocation
#    (GDP-3/GDP-4) -- R17
# ===========================================================================


def _blank_attesting_act_refusal_text(tmp_path: Path) -> str:
    """Drive the writer into ITS OWN blank-field refusal and return the
    captured text -- the shared trigger every HOW-clause scenario below
    inspects, so this file has exactly one place that builds it."""
    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(tmp_path, attesting_act="")
    _exit_code, cap = _run(argv)
    return cap.captured_text()


def _assert_how_clause_is_cli_parseable(text: str) -> None:
    """SSOT for the R17 HOW-clause execute-verification (GDP-3/GDP-4) --
    shared by every refusal-path scenario in this file (blank-field,
    store-side PartitionKeyRequired, probe failure), never re-derived
    per-scenario.

    F2 non-vacuity guard: `invocations_in` is a regex/AST extraction over
    `text` -- if the HOW-string format ever drifted (a re-wording, a
    different flag-render shape) the extractor could silently find ZERO
    invocations, and `not refused` would then pass VACUOUSLY (an empty list
    is never refused) while proving nothing. Asserting non-emptiness FIRST
    turns that silent pass into a loud, diagnosable failure.
    """
    invocations = invocations_in(
        f"how={text!r}", module=_WRITER_SCRIPT, line=1, key="how"
    )
    assert invocations, (
        "the HOW-invocation extractor found ZERO `des mikado-attest-node-"
        "closure ...` invocations in this refusal text -- a `not refused` "
        "check on an empty list would pass VACUOUSLY and prove nothing; "
        "either the refusal carries no re-runnable invocation at all, or "
        f"the extractor's regex/format has drifted from the HOW-string's "
        f"actual shape -- got text={text!r}"
    )
    refused, _unverifiable = rejections(invocations, cwd=_REPO_ROOT)
    assert not refused, (
        f"the HOW clause prescribes an invocation the des CLI refuses to "
        f"parse -- a consumer who pastes it gets an argument error, not a "
        f"repair: {refused}"
    )


def test_every_refusal_how_clause_names_a_cli_parseable_invocation(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- the refusal's HOW clause names a
    real, argparse-parseable des mikado-attest-node-closure invocation."""
    # covers: R17
    text = _blank_attesting_act_refusal_text(tmp_path)
    assert "HOW" in text, f"the refusal must carry a HOW clause -- got {text!r}"

    _assert_how_clause_is_cli_parseable(text)


# ===========================================================================
# 10. WALKING SKELETON -- the ONE subprocess-e2e for this whole feature:
#     proves `mikado-attest-node-closure` is discoverable and wired through
#     the REAL installed des dispatcher, not merely importable in-process --
#     R16
# ===========================================================================


@pytest.mark.walking_skeleton
def test_walking_skeleton_the_subcommand_is_registered_and_wired_through_the_real_des_dispatcher(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change -- @walking_skeleton @driving_port:
    the ONE subprocess-e2e for this feature, proving real dispatcher wiring."""
    # covers: R16
    help_result = subprocess.run(
        [sys.executable, "-m", "des.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=_REPO_ROOT,
    )
    assert "mikado-attest-node-closure" in help_result.stdout, (
        "the subcommand must be listed on `des --help` (the closer's "
        f"discovery surface) -- got: {help_result.stdout!r}"
    )

    _provision_healthy_telemetry_root(tmp_path)
    argv = _argv(tmp_path, node_id="D70-walking-skeleton")
    real_invocation = subprocess.run(
        [sys.executable, "-m", "des.cli", "mikado-attest-node-closure", *argv],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=_REPO_ROOT,
    )
    assert real_invocation.returncode == 0, (
        "a well-formed attestation invoked through the REAL installed des "
        "dispatcher (not merely importable in-process) must exit 0 -- got "
        f"returncode={real_invocation.returncode}, "
        f"stdout={real_invocation.stdout!r}, stderr={real_invocation.stderr!r}"
    )
    payload = json.loads(real_invocation.stdout.strip().splitlines()[-1])
    assert payload.get("event") == "NodeClosureAttested", (
        f"the real subprocess's own stdout payload must confirm the "
        f"attested event -- got {payload!r}"
    )
    assert payload.get("node_id") == "D70-walking-skeleton", (
        f"the payload must confirm the node id from THIS invocation -- got {payload!r}"
    )
    assert payload.get("transition") == "closed", (
        f"the payload must confirm the transition from THIS invocation -- got {payload!r}"
    )
    assert isinstance(payload.get("seq"), int), (
        f"the payload must carry the store-assigned sequence number, "
        f"proving a real write reached the real store through the real "
        f"dispatcher -- got {payload!r}"
    )


# ===========================================================================
# 11. DOCSTRING CORRECTION PIN -- event_store_port.py:176 no longer names
#     D70 as a future append_derived example (D70-2, ADR-D70 Consequences)
#     -- R18. Currently RED (docstring not yet corrected); DELIVER's one-line
#     prose edit turns this GREEN.
# ===========================================================================


def test_append_derived_docstring_no_longer_names_d70_closure_attestation() -> None:
    """CONTRACT_SHAPE: bounded-change -- append_derived's docstring no
    longer names D70 as a future DERIVED example (D70-2 correction)."""
    # covers: R18
    port_module = (
        _REPO_ROOT / "src" / "des" / "ports" / "driven_ports" / "event_store_port.py"
    )
    source = port_module.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(port_module))

    append_derived_docstring = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "append_derived"
            and ast.get_docstring(node) is not None
        ):
            append_derived_docstring = ast.get_docstring(node)
            break

    assert append_derived_docstring is not None, (
        "EventStorePort.append_derived must carry a docstring to correct"
    )
    assert "future D70 closure-attestation" not in append_derived_docstring, (
        "D70-2 corrects this stale docstring line: a closure record MUST "
        "use append() (PRIMARY), never append_derived() -- the docstring "
        f"still names D70 as a future DERIVED example: "
        f"{append_derived_docstring!r}"
    )
