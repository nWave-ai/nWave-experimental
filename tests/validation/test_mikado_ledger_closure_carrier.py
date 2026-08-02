# @feature-f-mikado-node-closure-record @slice-02
"""Acceptance tests -- D70 slice-02, the MIKADO ledger fourth carrier in
`validate_mikado_tree_coherence.py` (`check_ledger_closure_reconciliation`,
rules `ledger-closure-refused`/`ledger-closure-unattested`).

Feature: f-mikado-node-closure-record, slice-02. Design:
docs/feature/f-mikado-node-closure-record/design/adrs/
adr-D70-mikado-node-closure-record.md (ADR-D70 D70-6). Feature-delta:
docs/feature/f-mikado-node-closure-record/feature-delta.md ([REF]
Contract-Tests row 3).

**Split from `test_mikado_tree_coherence_gate.py` into its OWN file/tag,
deliberately** (not the file this dispatch first landed these scenarios in):
the carpaccio/spec-coverage file-attribution scan reads a file-level
`# @feature-<id>` tag ONLY within the first 20 lines
(`feature_at_files._HEAD_SCAN_LINES`, a deliberate negative control -- never a
whole-file grep). `test_mikado_tree_coherence_gate.py` predates the
slice/tag convention and carries 16 pre-existing, unrelated scenarios;
tagging that file's head would have attributed ALL 16 to this feature for
EVERY `@feature-`-keyed gate (carpaccio discovery, AT-completeness-per-slice,
feature-end wiring -- not merely `verify-spec-coverage`, which was the one
that surfaced the gap). A file half-owned by one feature and mostly owned by
none is exactly the shape the 20-line window exists to refuse. This file
owns 100% of its own population; the 16 pre-existing scenarios in the
sibling file are untouched, unretagged, unmoved.

Given-setup attests real MIKADO records through the SHIPPED slice-01 writer
(`mikado_node_closure_attest.main`) -- never a hand-rolled JSONL row
(Pillar 2/3). A "carries the cited path" scenario needs a REAL tree/blob
object, so this file builds its own `ledger_repo` fixture with the full
`_store`/`_write_tree`/`_write_commit` builder (the SAME pattern
`test_mikado_closure_carries_work.py` already established) -- the sibling
file's own `fake_repo` fixture writes commits with a placeholder tree hash
and cannot answer "did this rewrite that path" at all. `_doc` is duplicated
here rather than cross-imported from the sibling file, matching this test
suite's own established precedent (`test_mikado_closure_carries_work.py`
already carries its own independent `_doc`, not a shared import).

RED-for-right-reason: `mikado_closure_ledger.evaluate_node` is a DISTILL
scaffold that raises `AssertionError("__SCAFFOLD__: ...")` uncaught. Every
scenario below that reaches a CLOSED-class node with a non-`None`
`ledger_root` therefore fails on that SAME semantic AssertionError today,
never a collection-time error.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import zlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from git_commit_contents import LooseObjectContents
from git_commit_reachability import LooseObjectReachability
from validate_mikado_tree_coherence import (
    Severity,
    Verdict,
    check_tree_coherence,
)

from des.cli import mikado_node_closure_attest
from des.domain.telemetry_paths import telemetry_root
from des.testing.output_capture import CapturingOutput


TRUNK_REF = "feature/atdd-pure-staging"


# ===========================================================================
# a real, hand-built loose-object git repo -- zlib + hashlib only
# ===========================================================================


def _ledger_store(objects: Path, kind: bytes, body: bytes) -> str:
    raw = kind + b" " + str(len(body)).encode() + b"\x00" + body
    sha = hashlib.sha1(raw).hexdigest()
    target = objects / sha[:2] / sha[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zlib.compress(raw))
    return sha


def _ledger_write_tree(objects: Path, layout: dict) -> str:
    entries = []
    for name in sorted(layout):
        value = layout[name]
        if isinstance(value, dict):
            mode, oid = b"40000", _ledger_write_tree(objects, value)
        else:
            mode, oid = b"100644", _ledger_store(objects, b"blob", value.encode())
        entries.append(mode + b" " + name.encode() + b"\x00" + bytes.fromhex(oid))
    return _ledger_store(objects, b"tree", b"".join(entries))


def _ledger_write_commit(
    objects: Path, tree: str, parents: list[str], message: str
) -> str:
    lines = [f"tree {tree}"] + [f"parent {p}" for p in parents]
    lines.append("author T <t@example.com> 1700000000 +0000")
    lines.append("committer T <t@example.com> 1700000000 +0000")
    body = ("\n".join(lines) + "\n\n" + message + "\n").encode()
    return _ledger_store(objects, b"commit", body)


@pytest.fixture
def ledger_repo(tmp_path: Path):
    """A real trunk of two commits (real tree/blob objects, so
    `changed_paths` can genuinely decide "did this rewrite that path"),
    plus the healthy telemetry substrate the real slice-01 writer needs."""
    git_dir = tmp_path / ".git"
    objects = git_dir / "objects"
    objects.mkdir(parents=True)
    (objects / "pack").mkdir()

    base_layout = {"docs": {"mikado": {"plan.md": "v1"}}, "src": {"cli.py": "v1"}}
    base = _ledger_write_commit(
        objects, _ledger_write_tree(objects, base_layout), [], "base"
    )
    on_trunk_layout = {
        "docs": {"mikado": {"plan.md": "v2 -- closes the node"}},
        "src": {"cli.py": "v1"},
    }
    on_trunk = _ledger_write_commit(
        objects, _ledger_write_tree(objects, on_trunk_layout), [base], "closes it"
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


def _attest_ledger(
    repo_root: Path,
    node_id: str,
    *,
    cited_sha: str,
    cited_artifact_path: str,
    attesting_act: str = "human:quinn",
) -> None:
    argv = [
        "--repo-root",
        str(repo_root),
        "--node-id",
        node_id,
        "--transition",
        "closed",
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


def _doc(
    tmp_path: Path, corsie: str, albero: str, nodi: str, name: str = "tree.md"
) -> Path:
    text = f"""# tree

## CORSIE

| Corsia | Tipo | `owns` | Stato |
|---|---|---|---|
{corsie}

## L'ALBERO

```nwtree
GOAL | esempio
{albero}
```

## STATO NODO PER NODO

### ONDA 1

| Nodo | Cosa | Verdetto | Effort | Stato | Riferimento di chiusura |
|---|---|---|---|---|---|
{nodi}
"""
    path = tmp_path / name
    path.write_text(text)
    return path


#: A closed STATO NODO PER NODO row whose prose closure reference cites a
#: REAL, reachable sha with NO file path named -- deliberately, not a
#: placeholder: an empty/placeholder reference would ALSO trip the
#: PRE-EXISTING `closed-without-reference` (no sha at all) or
#: `closure-sha-not-on-trunk` (an unreachable sha) REJECT rules, confounding
#: every scenario below with a rejection that has nothing to do with the
#: ledger carrier under test. A real, reachable, artifact-less reference
#: satisfies both existing rules (attested + on trunk) while
#: `closure-does-not-carry` counts it `unfalsifiable` (no named artifact) and
#: emits no finding -- so ONLY the ledger carrier's own findings appear.
def _closed_doc(
    tmp_path: Path, node_id: str, *, closure_sha: str, name: str = "tree.md"
) -> Path:
    return _doc(
        tmp_path,
        corsie=(
            f"| `lane-{node_id.lower()}` | nodo {node_id} | `x.py` | "
            f"**FATTO** `{closure_sha}` |"
        ),
        albero=f"  {node_id} | qualcosa",
        nodi=f"| `{node_id}` | qualcosa | TIENI | XS | FATTO | `{closure_sha}` |",
        name=name,
    )


# ===========================================================================
# 1. ledger-closure-refused -- REJECT, unconditional
# ===========================================================================


def test_ledger_closure_refused_rejects_unconditionally_when_ledger_contradicts_closed_prose(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding to the existing
    GateReport, reads the MIKADO ledger and `.git/`, writes nothing.
    `ledger-closure-refused` (REJECT, unconditional): prose CLOSED, ledger
    REFUSED (a fabricated cited SHA) -> the gate blocks."""
    # covers: R26
    _attest_ledger(
        ledger_repo["path"],
        "D91",
        cited_sha="d" * 40,
        cited_artifact_path="does/not/matter.py",
    )
    doc = _closed_doc(tmp_path, "D91", closure_sha=ledger_repo["on_trunk"])

    report = check_tree_coherence(
        doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    assert report.verdict is Verdict.INCOHERENT, report.findings
    refused = [
        f
        for f in report.findings
        if f.rule == "ledger-closure-refused" and f.node_id == "D91"
    ]
    assert refused, f"the ledger contradiction was not rejected: {report.findings}"
    assert refused[0].severity is Severity.REJECT


# ===========================================================================
# 2. ledger-closure-refused -- never ratcheted, even beside an unrelated
#    third-state finding
# ===========================================================================


def test_ledger_closure_refused_is_never_ratcheted_even_beside_an_unrelated_third_state(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding to the existing
    GateReport, reads the MIKADO ledger and `.git/`, writes nothing.
    Mirrors test_skill_normative_gate_ratchets_its_indeterminate_population.py's
    own genuine-fail-is-never-ratcheted pin: a real ledger-closure-refused
    REJECT, beside an UNRELATED third-state (UNVERIFIABLE) finding in the
    SAME document, must still block absolutely -- no RATCHET line printed,
    no allowance -- because REJECTs are excluded from the ratchet by
    construction (gate_ratchet.py's own doctrine, reused here per ADR-D70
    D70-6's explicit "never ratcheted" decision).

    The unrelated third-state finding is built from `state-not-in-vocabulary`
    (an out-of-legend state word on an UNRELATED node) rather than from a
    broken/unavailable reachability port: `evaluate_node` shares the SAME
    `reachability` instance this test passes to `check_tree_coherence`, so an
    `UnavailableReachability` port here would ALSO turn the ledger's own
    REFUSED verdict into COULD_NOT_DETERMINE, defeating this test's whole
    point -- reachability must stay real and working for the REJECT to
    genuinely fire."""
    # covers: R27
    _attest_ledger(
        ledger_repo["path"],
        "D92",
        cited_sha="d" * 40,
        cited_artifact_path="does/not/matter.py",
    )
    refused_doc = _closed_doc(
        tmp_path, "D92", closure_sha=ledger_repo["on_trunk"], name="refused.md"
    )
    on_trunk_ref = f"`{ledger_repo['on_trunk']}`"
    text = refused_doc.read_text(encoding="utf-8")
    unverifiable_doc = tmp_path / "combined.md"
    unverifiable_doc.write_text(
        text.replace(
            f"| `D92` | qualcosa | TIENI | XS | FATTO | {on_trunk_ref} |",
            f"| `D92` | qualcosa | TIENI | XS | FATTO | {on_trunk_ref} |\n"
            "| `D89` | altro | TIENI | XS | MISTERIOSO | "
            "_(da compilare)_ |",
        )
    )

    report = check_tree_coherence(
        unverifiable_doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    assert report.verdict is Verdict.INCOHERENT, (
        f"a genuine REJECT must win over an unrelated UNVERIFIABLE finding, "
        f"never soften to NOT_VERIFIABLE: {report.findings}"
    )
    assert any(f.rule == "ledger-closure-refused" for f in report.findings)
    assert any(
        f.rule == "state-not-in-vocabulary" and f.node_id == "D89"
        for f in report.findings
    ), (
        "the unrelated third-state finding must still be present -- this "
        f"test's whole point is a REJECT beside it, not instead of it: "
        f"{report.findings}"
    )
    # `main()`'s own ratchet path only ever runs when `report.verdict is
    # Verdict.UNVERIFIABLE` (see check_tree_coherence's CLI caller) -- the
    # INCOHERENT assertion above is therefore already the complete pin:
    # verdict priority (REJECT > UNVERIFIABLE > COHERENT) means the ratchet
    # is structurally never reached while ANY REJECT is present, exactly
    # gate_ratchet.py's own "REJECTs are never ratcheted" doctrine, applied
    # here without needing to invoke the ratchet machinery at all.


# ===========================================================================
# 3. ledger-closure-unattested -- ADVISORY, never blocks, even at population
# ===========================================================================


def test_ledger_closure_unattested_is_advisory_and_never_blocks_even_with_many_closed_nodes(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding per node to the
    existing GateReport, reads the MIKADO ledger and `.git/`, writes
    nothing. `ledger-closure-unattested` (ADVISORY, unconditional, never
    blocks): many CLOSED-prose nodes, ZERO ledger records for any of them
    -- the gate must still exit COHERENT."""
    # covers: R28
    node_ids = [f"D9{4 + i}" for i in range(6)]
    on_trunk = ledger_repo["on_trunk"]
    corsie = "\n".join(
        f"| `lane-{n.lower()}` | nodo {n} | `x.py` | **FATTO** `{on_trunk}` |"
        for n in node_ids
    )
    albero = "\n".join(f"  {n} | qualcosa" for n in node_ids)
    nodi = "\n".join(
        f"| `{n}` | qualcosa | TIENI | XS | FATTO | `{on_trunk}` |" for n in node_ids
    )
    doc = _doc(tmp_path, corsie=corsie, albero=albero, nodi=nodi)

    report = check_tree_coherence(
        doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    assert report.verdict is Verdict.COHERENT, (
        f"an ADVISORY-only ledger carrier must never block, even with "
        f"{len(node_ids)} nodes involved: {report.findings}"
    )
    unattested = [f for f in report.findings if f.rule == "ledger-closure-unattested"]
    assert len(unattested) == len(node_ids), (
        f"every one of the {len(node_ids)} closed-but-unattested nodes must be "
        f"named individually (printed, named, counted every run) -- got "
        f"{[f.node_id for f in unattested]}"
    )
    assert all(f.severity is Severity.ADVISORY for f in unattested)


# ===========================================================================
# 4. ledger-closure-unattested -- the genuine zero-record case, first class
# ===========================================================================


def test_ledger_closure_unattested_fires_for_the_genuine_zero_record_case(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding to the existing
    GateReport, reads the MIKADO ledger and `.git/`, writes nothing.
    CRITICAL first-class scenario: a node with a genuinely CLOSED prose
    cell and ZERO MIKADO records anywhere -- on the real trunk this is the
    common case (the ledger is per-worktree and gitignored). Must read
    COULD_NOT_DETERMINE and fire the ADVISORY, never silently OPEN and
    never silently CLOSED."""
    # covers: R31
    doc = _closed_doc(tmp_path, "D80", closure_sha=ledger_repo["on_trunk"])

    report = check_tree_coherence(
        doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    assert report.verdict is Verdict.COHERENT
    unattested = [
        f
        for f in report.findings
        if f.rule == "ledger-closure-unattested" and f.node_id == "D80"
    ]
    assert unattested, f"the zero-record node was not reported: {report.findings}"
    assert "COULD_NOT_DETERMINE" in unattested[0].what


# ===========================================================================
# 5. agreement -- CLOSED prose + CLOSED ledger produces zero findings
# ===========================================================================


def test_ledger_closure_agrees_when_prose_and_ledger_both_read_closed_no_finding(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends zero Findings to the
    existing GateReport on agreement, reads the MIKADO ledger and `.git/`,
    writes nothing. Prose CLOSED and ledger CLOSED (a real, reachable,
    path-carrying closure record) -> no ledger-closure-* finding at all."""
    # covers: R29
    _attest_ledger(
        ledger_repo["path"],
        "D81",
        cited_sha=ledger_repo["on_trunk"],
        cited_artifact_path=ledger_repo["trunk_path"],
    )
    doc = _closed_doc(tmp_path, "D81", closure_sha=ledger_repo["on_trunk"])

    report = check_tree_coherence(
        doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    assert report.verdict is Verdict.COHERENT, report.findings
    assert not any(f.rule.startswith("ledger-closure-") for f in report.findings), (
        f"agreeing carriers must produce zero ledger-closure-* findings: "
        f"{report.findings}"
    )


# ===========================================================================
# 6. the two REFUSED causes are distinguishable, never collapsed
# ===========================================================================


def test_ledger_closure_refused_causes_are_distinguishable_never_collapsed(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding per node to the
    existing GateReport, reads the MIKADO ledger and `.git/`, writes
    nothing. The two distinct REFUSED causes (unreachable SHA vs.
    reachable-but-wrong-path) must render DIFFERENTLY in Finding.what --
    never one undifferentiated "REFUSED" message for both (orchestrator's
    own dispatch constraint)."""
    # covers: R30
    _attest_ledger(
        ledger_repo["path"],
        "D82",
        cited_sha="e" * 40,
        cited_artifact_path="does/not/matter.py",
    )
    _attest_ledger(
        ledger_repo["path"],
        "D83",
        cited_sha=ledger_repo["on_trunk"],
        cited_artifact_path="never/rewrote/this.py",
    )
    on_trunk = ledger_repo["on_trunk"]
    corsie = "\n".join(
        f"| `lane-{n.lower()}` | nodo {n} | `x.py` | **FATTO** `{on_trunk}` |"
        for n in ("D82", "D83")
    )
    albero = "\n".join(f"  {n} | qualcosa" for n in ("D82", "D83"))
    nodi = "\n".join(
        f"| `{n}` | qualcosa | TIENI | XS | FATTO | `{on_trunk}` |"
        for n in ("D82", "D83")
    )
    doc = _doc(tmp_path, corsie=corsie, albero=albero, nodi=nodi)

    report = check_tree_coherence(
        doc,
        reachability=ledger_repo["reachability"],
        contents=ledger_repo["contents"],
        trunk_ref=TRUNK_REF,
        ledger_root=ledger_repo["path"],
    )

    refused = {
        f.node_id: f.what for f in report.findings if f.rule == "ledger-closure-refused"
    }
    assert set(refused) == {"D82", "D83"}, refused
    assert refused["D82"] != refused["D83"], (
        "the two distinct REFUSED causes must never render as the same "
        f"undifferentiated message: {refused}"
    )
    assert "not reachable" in refused["D82"]
    assert "did not rewrite" in refused["D83"]


# ===========================================================================
# 7. ledger_root omitted -- the deliberate DISTILL-time default, see
#    feature-delta.md [REF] Scaffolds -- degrades to COULD_NOT_DETERMINE,
#    never crashes, never silently skips the carrier
# ===========================================================================


def test_ledger_root_omitted_degrades_to_could_not_determine_never_crashes(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- appends a Finding to the existing
    GateReport, reads `.git/` only (no ledger root supplied), writes
    nothing. The DISTILL-scoped default (`ledger_root=None`, current
    `main()` behaviour until DELIVER threads a real one): a caller that
    does not supply a ledger root gets the weakest honest answer
    (COULD_NOT_DETERMINE -> ADVISORY) for every CLOSED node, never a crash
    and never a silently-skipped carrier."""
    doc = _closed_doc(tmp_path, "D99", closure_sha=ledger_repo["on_trunk"])

    report = check_tree_coherence(
        doc, reachability=ledger_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.COHERENT, report.findings
    unattested = [f for f in report.findings if f.rule == "ledger-closure-unattested"]
    assert unattested and unattested[0].node_id == "D99"


# ===========================================================================
# 8. the REAL CLI entry point never wires `ledger_root` -- the fourth
#    carrier is dormant from `main()`, even though `evaluate_node` itself is
#    green in 34/34 unit tests. Drives the actual script via subprocess,
#    exactly as a human runs it -- never imports `check_tree_coherence` and
#    never supplies `ledger_root` itself. If this test could pass without
#    the CLI wiring existing, it would prove nothing.
# ===========================================================================


def test_cli_entry_point_never_wires_ledger_root_so_a_refused_closure_is_silently_advisory(
    ledger_repo, tmp_path
):
    """CONTRACT_SHAPE: bounded-change -- drives `main()` in
    `scripts/validation/validate_mikado_tree_coherence.py` as a real
    subprocess (the actual CLI entry point), reads the MIKADO ledger and
    `.git/`, writes nothing.

    Root cause (validate_mikado_tree_coherence.py ~line 2112): `main()`
    calls `check_tree_coherence(args.file, reachability=..., trunk_ref=...,
    contents=...)` and never passes `ledger_root`, leaving it at the
    default `None`. `check_ledger_closure_reconciliation` (~line 1363) then
    reads `if ledger_root is None: ledger_state = NodeState.COULD_NOT_DETERMINE`
    unconditionally -- so the verdict for every CLOSED node is ALWAYS
    COULD_NOT_DETERMINE from the real CLI, regardless of what the ledger
    actually contains. The 34 existing unit tests all call
    `check_tree_coherence` directly and pass `ledger_root` explicitly, so
    none of them can see this: they test the function, never the wiring.

    This scenario attests a CLOSED record for node D97 citing a FABRICATED
    sha (`deadbeef0000000000000000000000000000dead`) and a nonexistent
    path -- a `ledger-closure-refused` REJECT if the fourth carrier were
    actually reachable. The prose table independently declares D97 FATTO
    with a real, well-formed, reachable closure sha (never the fabricated
    one), so `closed-without-reference`/`closure-sha-not-on-trunk` never
    fire and only the ledger carrier's own findings are in play (same
    isolation technique as `_closed_doc`'s own docstring)."""
    # covers: R33
    _attest_ledger(
        ledger_repo["path"],
        "D97",
        cited_sha="deadbeef0000000000000000000000000000dead",
        cited_artifact_path="does/not/exist.py",
    )
    doc = _closed_doc(tmp_path, "D97", closure_sha=ledger_repo["on_trunk"])

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_mikado_tree_coherence.py"),
            "--file",
            str(doc),
            "--repo",
            str(ledger_repo["path"]),
            "--trunk-ref",
            TRUNK_REF,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode != 0, (
        "the real CLI entry point never wires `ledger_root` into "
        "`check_tree_coherence` -- a fabricated, unreachable ledger "
        "closure record for D97 must REJECT the tree "
        "(`ledger-closure-refused`), not exit clean. "
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert "ledger-closure-refused" in completed.stdout, (
        "expected the `ledger-closure-refused` REJECT to be reachable from "
        f"the real CLI entry point. stdout:\n{completed.stdout}"
    )


# Note: the mikado_board.py coupled-imports regression pin (R32) lives in
# the sibling tests/validation/test_mikado_closure_ledger.py, not duplicated
# here -- one witness per obligation, per this feature's own [REF] Scenario
# List (scenario #22).
