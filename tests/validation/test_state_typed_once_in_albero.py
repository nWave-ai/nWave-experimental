"""State is typed once, in `## STATO NODO PER NODO`.

`## L'ALBERO` used to carry a second copy of a node's state, effort and wave
on every node row, duplicating `## STATO NODO PER NODO` -- and it drifted
from that table eight times across five classes (two states, one effort, one
Verdetto, one title's item count, three closure-sha citations naming another
node's commit), and `carrier-contradiction` caught NONE of them: every one
was OPEN-vs-OPEN or a non-state field, the one shape that rule cannot see
(full account in the module docstring of validate_mikado_tree_coherence.py).

`state-typed-outside-its-carrier` closes that gap by refusing a state word
anywhere on an `## L'ALBERO` node row, and `mikado_board.py
--withdraw-tree-state` is the producing tool the rejection's HOW points at.

These tests pin:
  (a) a state word on an L'ALBERO node row -> REJECT, exit 1.
  (b) the same document withdrawn -> COHERENT, `L'ALBERO` absent from
      `carriers_seen`.
  (c) a `: key | value` detail line quoting a state word in prose is never
      mistaken for a second typing.
  (d) `withdraw_tree_state` is idempotent -- two runs, byte-identical
      (sha256).
  (e) a glued `  : ▶ Corsia | ...` attribute tail survives withdrawal
      verbatim.
  (f) `carrier-contradiction` still fires on a CORSIE-vs-node-table
      CLOSED/OPEN split once L'ALBERO carries no state -- the surviving
      second axis (pins the `D24-probe` reproduction: CORSIE **INTEGRATA**
      against a node table CONTESO).
  (g) the withdrawn document keeps >= 2 carriers, so `population-floor`
      never fires on it -- and, as the other edge of that same floor,
      collapsing BOTH remaining carriers (an empty CORSIE) still trips it.

No git binary anywhere: reachability is the `UnavailableReachability` stub,
exactly like `state-typed-outside-its-carrier` needs nothing from the object
store to fire, and the CLI-exit-code case in (a) points `--repo` at this
checkout's own real `.git` (read-only) purely to let `main()` construct its
ports; no sha in these fixtures is ever resolved against it.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = PROJECT_ROOT / "scripts" / "validation"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(VALIDATION_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import mikado_board as board
import validate_mikado_tree_coherence as gate
from git_commit_reachability import UnavailableReachability
from validate_mikado_tree_coherence import (
    Severity,
    Verdict,
    check_tree_coherence,
)


TRUNK_REF = "feature/atdd-pure-staging"


def _doc(
    tmp_path: Path, *, corsie: str, albero: str, nodi: str, name: str = "tree.md"
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


def _run(doc: Path):
    return check_tree_coherence(
        doc,
        reachability=UnavailableReachability("ancestry not needed by these tests"),
        trunk_ref=TRUNK_REF,
    )


# --------------------------------------------------------------------------
# (a) a state word on an L'ALBERO node row is rejected
# --------------------------------------------------------------------------


def test_state_word_in_albero_node_row_is_refused(tmp_path):
    doc = _doc(
        tmp_path,
        corsie="| `lane-d01` | nodo D01 | `x.py` | **PRONTO** |",
        albero="  D01 | qualcosa | FATTO | XS | onda 1",
        nodi="| `D01` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    )

    report = _run(doc)

    assert report.verdict is Verdict.INCOHERENT, report.findings
    rejects = [
        f for f in report.findings if f.rule == "state-typed-outside-its-carrier"
    ]
    assert rejects, f"the state word was never rejected: {report.findings}"
    assert rejects[0].node_id == "D01"
    assert rejects[0].severity is Severity.REJECT
    assert "FATTO" in rejects[0].what

    exit_code = gate.main(
        ["--file", str(doc), "--repo", str(PROJECT_ROOT), "--trunk-ref", TRUNK_REF]
    )
    assert exit_code == 1


# --------------------------------------------------------------------------
# (b) withdrawn -> coherent, L'ALBERO drops out of carriers_seen
# --------------------------------------------------------------------------


def test_withdrawn_document_is_coherent_and_albero_leaves_carriers_seen(tmp_path):
    raw = _doc(
        tmp_path,
        corsie="| `lane-d01` | nodo D01 | `x.py` | **PRONTO** |",
        albero="  D01 | qualcosa | FATTO | XS | onda 1",
        nodi="| `D01` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    ).read_text(encoding="utf-8")
    doc = tmp_path / "withdrawn.md"
    doc.write_text(board.withdraw_tree_state(raw), encoding="utf-8")

    report = _run(doc)

    assert not any(f.rule == "state-typed-outside-its-carrier" for f in report.findings)
    assert report.verdict is Verdict.COHERENT, report.findings
    assert "L'ALBERO" not in report.carriers_seen
    assert set(report.carriers_seen) == {"CORSIE", "STATO NODO PER NODO"}

    exit_code = gate.main(
        ["--file", str(doc), "--repo", str(PROJECT_ROOT), "--trunk-ref", TRUNK_REF]
    )
    assert exit_code == 0


# --------------------------------------------------------------------------
# (c) prose in a detail line is never mistaken for a state typing
# --------------------------------------------------------------------------


def test_state_word_inside_a_detail_line_does_not_trip_the_rule(tmp_path):
    doc = _doc(
        tmp_path,
        corsie="| `lane-d02` | nodo D02 | `x.py` | **NON_MISURATO** |",
        albero=(
            "  D02 | qualcosa\n"
            "      : Verdetto | NON_MISURATO\n"
            "      : Cosa serve | il lavoro e' FATTO `1c912f391`, resta da misurare"
        ),
        nodi="| `D02` | qualcosa | TIENI | XS | NON_MISURATO | _(da compilare)_ |",
    )

    report = _run(doc)

    assert not any(
        f.rule == "state-typed-outside-its-carrier" for f in report.findings
    ), report.findings
    assert report.verdict is Verdict.COHERENT, report.findings


# --------------------------------------------------------------------------
# (d) withdrawal is idempotent -- byte-identical, proved by sha256
# --------------------------------------------------------------------------


def test_withdraw_tree_state_is_idempotent_by_sha256(tmp_path):
    doc = _doc(
        tmp_path,
        corsie="| `lane-d07` | nodo D07 | `x.py` | **FATTO** |",
        albero=(
            "  R0 · anello con una | pipe propria\n"
            "    D07 | titolo | FATTO `1c912f391` | XS | onda 1"
            "      : ▶ Corsia | worktree `wt/advisory-throttle`\n"
            "      : Riferimento di chiusura | commit `1c912f391`"
        ),
        nodi="| `D07` | titolo | TIENI | XS | FATTO | `1c912f391` |",
    )
    text = doc.read_text(encoding="utf-8")

    once = board.withdraw_tree_state(text)
    twice = board.withdraw_tree_state(once)

    assert once != text, "the fixture must actually carry state to withdraw"
    assert (
        hashlib.sha256(once.encode()).hexdigest()
        == hashlib.sha256(twice.encode()).hexdigest()
    )
    assert once == twice


# --------------------------------------------------------------------------
# (e) a glued attribute tail rides through verbatim
# --------------------------------------------------------------------------


def test_withdraw_preserves_a_glued_corsia_attribute_tail_verbatim(tmp_path):
    tail = "      : ▶ Corsia | worktree `wt/advisory-throttle` — prima accertare"
    doc = _doc(
        tmp_path,
        corsie="| `lane-d07` | nodo D07 | `x.py` | **FATTO** |",
        albero=(f"    D07 | titolo | FATTO `1c912f391` | XS | onda 1{tail}"),
        nodi="| `D07` | titolo | TIENI | XS | FATTO | `1c912f391` |",
    )
    text = doc.read_text(encoding="utf-8")

    withdrawn = board.withdraw_tree_state(text)

    assert tail in withdrawn, withdrawn
    assert "    D07 | titolo" in withdrawn
    assert "FATTO `1c912f391` | XS | onda 1" not in withdrawn


# --------------------------------------------------------------------------
# (f) carrier-contradiction survives as the live second axis
# --------------------------------------------------------------------------


def test_carrier_contradiction_still_fires_corsie_vs_node_table_after_withdrawal(
    tmp_path,
):
    """Pins the `D24-probe` reproduction: CORSIE INTEGRATA vs table CONTESO."""
    doc = _doc(
        tmp_path,
        corsie="| `d24-probe` | nodo D24 | `x.py` | **INTEGRATA** `1c912f391` |",
        albero="  D24 | qualcosa",
        nodi="| `D24` | qualcosa | TIENI | M | CONTESO | _(da compilare)_ |",
    )

    report = _run(doc)

    assert not any(f.rule == "state-typed-outside-its-carrier" for f in report.findings)
    assert report.verdict is Verdict.INCOHERENT, report.findings
    contradictions = [
        f
        for f in report.findings
        if f.rule == "carrier-contradiction" and f.node_id == "D24"
    ]
    assert contradictions, (
        f"CORSIE-vs-node-table split was not caught: {report.findings}"
    )


# --------------------------------------------------------------------------
# (g) the population floor: >= 2 carriers survives withdrawal, and collapsing
# BOTH remaining carriers still trips it
# --------------------------------------------------------------------------


def test_withdrawn_document_keeps_two_carriers_never_trips_population_floor(
    tmp_path,
):
    raw = _doc(
        tmp_path,
        corsie="| `lane-d01` | nodo D01 | `x.py` | **PRONTO** |",
        albero="  D01 | qualcosa | PRONTO | XS | onda 1",
        nodi="| `D01` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    ).read_text(encoding="utf-8")
    doc = tmp_path / "withdrawn.md"
    doc.write_text(board.withdraw_tree_state(raw), encoding="utf-8")

    report = _run(doc)

    assert not any(f.rule == "population-floor" for f in report.findings)
    assert len(report.carriers_seen) >= 2


def test_collapsing_both_remaining_carriers_still_trips_population_floor(tmp_path):
    """The floor this fix must stop at: withdrawing CORSIE too is REJECTED."""
    doc = _doc(
        tmp_path,
        corsie="",
        albero="  D01 | qualcosa",
        nodi="| `D01` | qualcosa | TIENI | XS | PRONTO | _(da compilare)_ |",
    )

    report = _run(doc)

    assert any(f.rule == "population-floor" for f in report.findings)
    assert report.verdict is not Verdict.COHERENT
