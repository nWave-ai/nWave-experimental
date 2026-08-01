"""Acceptance tests for the Mikado tree-coherence gate.

The gate exists because a single document carried two incompatible statements
about the same node -- one table said INTEGRATA with a sha, another said PRONTO
with an empty closure reference -- and nothing compared them.

These tests pin the properties, not the shapes:
- two carriers disagreeing about one node is a rejection;
- a closure reference naming a sha that trunk cannot reach is a rejection;
- "I could not tell" never becomes "coherent";
- the gate fails when its own population collapses to zero (the checker is not
  exempt from the class it checks).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import zlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from git_commit_reachability import (
    LooseObjectReachability,
    Reachability,
    UnavailableReachability,
)
from validate_mikado_tree_coherence import (
    Severity,
    Verdict,
    check_tree_coherence,
)


REAL_TREE_DOC = PROJECT_ROOT / "docs" / "mikado" / "EXECUTION-SSOT-des-optimization.md"
TRUNK_REF = "feature/atdd-pure-staging"


# --------------------------------------------------------------------------
# a throwaway object store, written with zlib only -- no git binary anywhere
# --------------------------------------------------------------------------


def _write_loose_commit(objects_dir: Path, parents: list[str], message: str) -> str:
    import hashlib

    lines = ["tree " + "0" * 40]
    lines += [f"parent {p}" for p in parents]
    lines.append("author T <t@example.com> 1700000000 +0000")
    lines.append("committer T <t@example.com> 1700000000 +0000")
    body = ("\n".join(lines) + "\n\n" + message + "\n").encode()
    raw = b"commit " + str(len(body)).encode() + b"\x00" + body
    sha = hashlib.sha1(raw).hexdigest()
    target = objects_dir / sha[:2] / sha[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zlib.compress(raw))
    return sha


@pytest.fixture
def fake_repo(tmp_path: Path):
    """A minimal ``.git`` with a trunk of two commits plus one off-trunk commit."""
    git_dir = tmp_path / ".git"
    objects = git_dir / "objects"
    objects.mkdir(parents=True)
    (git_dir / "objects" / "pack").mkdir()
    root = _write_loose_commit(objects, [], "root")
    on_trunk = _write_loose_commit(objects, [root], "on trunk")
    off_trunk = _write_loose_commit(objects, [root], "abandoned lane")
    ref = git_dir / "refs" / "heads" / "feature" / "atdd-pure-staging"
    ref.parent.mkdir(parents=True)
    ref.write_text(on_trunk + "\n")
    return {
        "path": tmp_path,
        "on_trunk": on_trunk,
        "off_trunk": off_trunk,
        "reachability": LooseObjectReachability(tmp_path),
    }


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


# --------------------------------------------------------------------------
# rule 1 -- the two tables must not contradict each other
# --------------------------------------------------------------------------


def test_rejects_node_closed_in_one_carrier_and_open_in_another(fake_repo, tmp_path):
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d99` | nodo D99 | `x.py` | **INTEGRATA** `{sha}` |",
        albero=f"  D99 | qualcosa | FATTO | XS | onda 1\n"
        f"      : Riferimento di chiusura | commit `{sha}`",
        nodi="| `D99` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.INCOHERENT
    contradictions = [
        f
        for f in report.findings
        if f.rule == "carrier-contradiction" and f.node_id == "D99"
    ]
    assert contradictions, f"nessuna contraddizione rilevata: {report.findings}"
    finding = contradictions[0]
    assert "CORSIE" in finding.what and "PRONTO" in finding.what
    assert len(finding.locations) >= 2, "il payload deve nominare entrambe le righe"


def test_agreeing_carriers_with_a_trunk_sha_are_coherent(fake_repo, tmp_path):
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d99` | nodo D99 | `x.py` | **INTEGRATA** `{sha}` |",
        # L'ALBERO carries id + title only: state lives once, in STATO NODO
        # PER NODO (state-typed-outside-its-carrier).
        albero=f"  D99 | qualcosa\n      : Riferimento di chiusura | commit `{sha}`",
        nodi=f"| `D99` | qualcosa | TIENI | XS | FATTO | `{sha}` |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.COHERENT, report.findings
    assert report.nodes_examined == 1


# --------------------------------------------------------------------------
# rule 2 -- a sha cited as closure must be reachable from trunk (NEGATIVE AT)
# --------------------------------------------------------------------------


def test_rejects_closure_sha_that_trunk_never_reaches(fake_repo, tmp_path):
    """A node sealed on a commit that is not in the product is not closed."""
    off = fake_repo["off_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d98` | nodo D98 | `y.py` | **INTEGRATA** `{off}` |",
        albero=f"  D98 | altro | FATTO | XS | onda 1\n"
        f"      : Riferimento di chiusura | commit `{off}`",
        nodi=f"| `D98` | altro | TIENI | XS | FATTO | `{off}` |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.INCOHERENT
    off_trunk = [f for f in report.findings if f.rule == "closure-sha-not-on-trunk"]
    assert off_trunk, f"the off-trunk sha was not rejected: {report.findings}"
    assert off_trunk[0].node_id == "D98"
    assert off[:9] in off_trunk[0].what


def test_checks_the_sha_of_a_lane_that_closes_no_tree_node(fake_repo, tmp_path):
    """A feature lane cites a closure sha too, and it is not exempt."""
    off = fake_repo["off_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `df-slice-01` | feature | `a.py` | **INTEGRATA** `{off}` |",
        albero="  D93 | settimo | PRONTO | XS | onda 1",
        nodi="| `D93` | settimo | TIENI | XS | PRONTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    off_trunk = [f for f in report.findings if f.rule == "closure-sha-not-on-trunk"]
    assert off_trunk, f"sha di corsia non controllato: {report.findings}"
    assert off_trunk[0].node_id == "df-slice-01"
    assert report.verdict is Verdict.INCOHERENT


def test_never_reports_a_sha_as_on_trunk_when_the_object_is_unknown(
    fake_repo, tmp_path
):
    bogus = "9" * 40
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d97` | nodo D97 | `z.py` | **INTEGRATA** `{bogus}` |",
        albero="  D97 | terzo | FATTO | XS | onda 1\n"
        f"      : Riferimento di chiusura | commit `{bogus}`",
        nodi=f"| `D97` | terzo | TIENI | XS | FATTO | `{bogus}` |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.INCOHERENT
    assert any(f.rule == "closure-sha-not-on-trunk" for f in report.findings)


# --------------------------------------------------------------------------
# rule 3 -- closed means closed WITH a reference (the document's own legend)
# --------------------------------------------------------------------------


def test_rejects_closed_node_whose_closure_reference_is_a_placeholder(
    fake_repo, tmp_path
):
    doc = _doc(
        tmp_path,
        corsie="| `lane-x` | feature | `q.py` | **INTEGRATA** |",
        albero="  D96 | quarto | FATTO | XS | onda 1\n"
        "      : Riferimento di chiusura | *(da compilare)*",
        nodi="| `D96` | quarto | TIENI | XS | FATTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.INCOHERENT
    unattested = [f for f in report.findings if f.rule == "closed-without-reference"]
    assert unattested, f"closure without reference was not rejected: {report.findings}"
    assert unattested[0].node_id == "D96"


# --------------------------------------------------------------------------
# the third state must reach the aggregate, never collapse into the first
# --------------------------------------------------------------------------


def test_unverifiable_reachability_never_collapses_into_coherent(tmp_path):
    sha = "a" * 40
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d95` | nodo D95 | `w.py` | **INTEGRATA** `{sha}` |",
        albero=f"  D95 | quinto\n      : Riferimento di chiusura | commit `{sha}`",
        nodi=f"| `D95` | quinto | TIENI | XS | FATTO | `{sha}` |",
    )

    report = check_tree_coherence(
        doc,
        reachability=UnavailableReachability("nessun object store"),
        trunk_ref=TRUNK_REF,
    )

    assert report.verdict is Verdict.UNVERIFIABLE, report.findings
    assert report.by_severity(Severity.UNVERIFIABLE), (
        "il terzo stato deve essere elencato"
    )


def test_reachability_port_reports_three_distinct_states(fake_repo):
    port = fake_repo["reachability"]
    assert (
        port.reachable_from(fake_repo["on_trunk"], TRUNK_REF).outcome
        is Reachability.REACHABLE
    )
    assert (
        port.reachable_from(fake_repo["off_trunk"], TRUNK_REF).outcome
        is Reachability.NOT_REACHABLE
    )
    assert (
        port.reachable_from(fake_repo["on_trunk"], "refs/heads/does-not-exist").outcome
        is Reachability.INDETERMINATE
    )


# --------------------------------------------------------------------------
# the checker is not exempt from the class it checks
# --------------------------------------------------------------------------


def test_fails_instead_of_passing_by_absence_when_no_node_is_found(fake_repo, tmp_path):
    """Zero nodes must be a failure, never a green-by-empty-population."""
    doc = _doc(tmp_path, corsie="", albero="", nodi="")

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is not Verdict.COHERENT
    assert any(f.rule == "population-floor" for f in report.findings)


def test_real_execution_ssot_yields_a_named_population_on_two_state_carriers():
    """Second axis: the gate must actually see the tree it was built for.

    L'ALBERO carries no state (state-typed-outside-its-carrier withdrew it
    with `mikado_board.py --withdraw-tree-state`), so it never contributes to
    `carriers_seen` -- CORSIE and STATO NODO PER NODO remain the two live
    carriers of state, still >= the population-floor of 2.
    """
    assert REAL_TREE_DOC.is_file(), REAL_TREE_DOC
    report = check_tree_coherence(
        REAL_TREE_DOC,
        reachability=UnavailableReachability("ancestry not required by this test"),
        trunk_ref=TRUNK_REF,
    )

    seen = {claim.node_id for claim in report.claims}
    for expected in ("D22", "D29", "D05", "D52"):
        assert expected in seen, (
            f"node `{expected}` missing from the population: {sorted(seen)}"
        )
    assert report.nodes_examined >= 40, report.nodes_examined
    assert set(report.carriers_seen) == {"CORSIE", "STATO NODO PER NODO"}
    assert not any(f.rule == "state-typed-outside-its-carrier" for f in report.findings)


# --------------------------------------------------------------------------
# the HOW must be executable, not merely present
# --------------------------------------------------------------------------


def test_every_rejection_carries_a_how_that_actually_runs(fake_repo, tmp_path):
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d99` | nodo D99 | `x.py` | **INTEGRATA** `{sha}` |",
        albero=f"  D99 | qualcosa\n      : Riferimento di chiusura | commit `{sha}`",
        nodi="| `D99` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    )
    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )
    rejections = report.by_severity(Severity.REJECT)
    assert rejections

    for finding in rejections:
        argv = shlex.split(finding.how)
        assert argv, finding.how
        completed = subprocess.run(
            [sys.executable, *argv[1:]],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode in (0, 1, 2), completed.stderr
        assert finding.node_id in completed.stdout, completed.stdout[:2000]


def test_explain_prints_every_carrier_claim_for_the_node(fake_repo, tmp_path):
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `lane-d99` | nodo D99 | `x.py` | **INTEGRATA** `{sha}` |",
        albero=f"  D99 | qualcosa | FATTO | XS | onda 1\n"
        f"      : Riferimento di chiusura | commit `{sha}`",
        nodi="| `D99` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_mikado_tree_coherence.py"),
            "--file",
            str(doc),
            "--repo",
            str(fake_repo["path"]),
            "--trunk-ref",
            TRUNK_REF,
            "--explain",
            "D99",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = completed.stdout
    assert "CORSIE" in out and "STATO NODO PER NODO" in out and "L'ALBERO" in out
    assert "INTEGRATA" in out and "PRONTO" in out


# --------------------------------------------------------------------------
# the re-calibrated predictor is a hint, never a veto
# --------------------------------------------------------------------------


def test_completion_word_without_a_pointer_is_advisory_and_does_not_reject(
    fake_repo, tmp_path
):
    """A lexicon match is an INFERRED signal, so it may warn but never block."""
    doc = _doc(
        tmp_path,
        # Non-empty CORSIE keeps two carriers of state present (CORSIE +
        # STATO NODO PER NODO) once L'ALBERO carries none -- population-floor
        # needs >= 2, and L'ALBERO no longer contributes to that count.
        corsie="| `lane-decor` | decor | `x.py` | **PRONTO** |",
        albero="  D94 | sesto\n"
        "      : Cosa serve | sigillato; resta la chiusura d'installazione\n"
        "      : Riferimento di chiusura | *(da compilare)*",
        nodi="| `D94` | sesto | TIENI | S | QUARANTENA | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    advisories = [
        f for f in report.findings if f.rule == "completion-word-without-pointer"
    ]
    assert advisories, f"predittore muto: {report.findings}"
    assert advisories[0].severity is Severity.ADVISORY
    assert report.verdict is Verdict.COHERENT, "un avviso non deve far fallire il gate"


# --------------------------------------------------------------------------
# the join decides on the PROPERTY -- does this row assert closure for node N?
# -- never on the DESIGNATION -- how the row happened to spell N. Found on the
# real document: eight already-merged nodes carried a CORSIA row named after
# the lane (`d07`, `d25-deadtests`, ...), not the node id, and the gate never
# compared them against the node's other two carriers.
# --------------------------------------------------------------------------


def test_lane_named_by_its_bare_id_still_joins_the_node_it_closes(fake_repo, tmp_path):
    """A CORSIA row named `d07` (no "nodo D07" phrase) must still join `D07`.

    Reproduces the real gap: the lane is CHIUSO with a sha, but STATO NODO PER
    NODO still carries PRONTO -- exactly the shape that shipped unnoticed.
    """
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `d07` | nodo Mikado XS | `freshness.py` | **CHIUSO** `{sha}` |",
        albero="  D07 | throttle | PRONTO | XS | onda 1",
        nodi="| `D07` | throttle | SEMPLIFICA | XS | PRONTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    assert report.verdict is Verdict.INCOHERENT, report.findings
    contradictions = [
        f
        for f in report.findings
        if f.rule == "carrier-contradiction" and f.node_id == "D07"
    ]
    assert contradictions, (
        f"the lane-named row was never joined to D07: {report.findings}"
    )


def test_ambiguous_lane_base_reaches_the_aggregate_and_never_guesses(
    fake_repo, tmp_path
):
    """`d25-deadtests` names a base shared by D25A and D25B -- neither exactly.

    The claim must surface as the third state (UNVERIFIABLE), never silently
    vanish and never be guessed onto one of the two candidates as a fabricated
    contradiction.
    """
    sha = fake_repo["on_trunk"]
    doc = _doc(
        tmp_path,
        corsie=f"| `d25-deadtests` | rimozione | test | **CHIUSO** `{sha}` |",
        albero="  D25a | dead a\n  D25b | dead b",
        nodi="| `D25a` | dead a | RIMUOVI | S | PRONTO | _(da compilare)_ |\n"
        "| `D25b` | dead b | RIMUOVI | S | PRONTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    ambiguous = [f for f in report.findings if f.rule == "lane-closure-join-ambiguous"]
    assert ambiguous, f"the ambiguous join vanished silently: {report.findings}"
    assert ambiguous[0].severity is Severity.UNVERIFIABLE
    assert report.verdict is Verdict.UNVERIFIABLE, (
        "an unjoinable closure claim must reach the aggregate, never collapse "
        "into a silent COHERENT"
    )
    assert not any(f.rule == "carrier-contradiction" for f in report.findings), (
        "an ambiguous base must never be guessed onto a candidate as a "
        "fabricated contradiction"
    )


def test_short_lane_id_never_cross_joins_a_longer_node_id(fake_repo, tmp_path):
    """`D3` must not match `D30` -- over-joining is worse than the prior silence."""
    doc = _doc(
        tmp_path,
        corsie="| `d3` | qualcosa | `x.py` | **INTEGRATA** |",
        albero="  D30 | altro",
        nodi="| `D30` | altro | TIENI | M | PRONTO | _(da compilare)_ |",
    )

    report = check_tree_coherence(
        doc, reachability=fake_repo["reachability"], trunk_ref=TRUNK_REF
    )

    seen = {claim.node_id for claim in report.claims}
    assert "d3" in seen, "the lane claim must still be recorded, just not joined"
    assert not any(f.node_id == "D30" for f in report.findings), (
        f"D3 must never be attributed to D30: {report.findings}"
    )
