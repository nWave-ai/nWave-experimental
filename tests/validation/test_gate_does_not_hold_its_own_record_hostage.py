"""A three-state gate must not block the write that would resolve its own complaint.

WHY THIS TEST EXISTS. On 2026-07-30 the Mikado tree-coherence gate returned
``VERDICT NOT_VERIFIABLE`` with 88 unverifiable findings across 68 of 108 nodes
and ZERO rejects, every one of them because ``git gc`` had moved a closure sha
into a packfile. The gate exits non-zero on the third state and pre-commit
blocks on non-zero, so for hours the Mikado SSOT was uncommittable: four
prepared rows sat in staging across three commit attempts, twelve nodes closed
on trunk could not be recorded, and one of the refused commits was a CORRECTION
TO THE VERY ROWS the gate was complaining about. Nothing in any of those commits
caused the condition.

THE FIX THAT IS NOT THE FIX. Making ``UNVERIFIABLE`` non-blocking would unblock
the document by making it meaningless -- "I looked and it is bad" and "I cannot
see whether it is bad" are different facts, and collapsing them is the defect
class this whole tree keeps finding. So these tests pin a RATCHET instead: the
decision is on the DELTA the change introduces, the findings stay printed and
counted, and REJECTS keep blocking absolutely at any count.

THE TWO CASES MOST LIKELY TO EMBARRASS THE AUTHOR are the ones that prove it is
not a bypass, and they are both here: an allowance must remain LOUD (the
findings printed, the allowance named as an allowance over an unverifiable
document), and a real reject must keep blocking while the unverifiable count is
unchanged. A third guards the gap a count-only ratchet would leave -- swapping
one unverifiable claim for a different one keeps the total flat.

NO ``git`` BINARY ANYWHERE IN THIS FILE. The fixture writes loose objects with
``zlib`` + ``hashlib``, the same discipline
``test_mikado_tree_coherence_gate.py`` follows: the checkout under test must be
readable by the gate with Python as its only dependency, so the test must not
smuggle in a tool the gate is forbidden to need.
"""

from __future__ import annotations

import hashlib
import shlex
import subprocess
import sys
import zlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from gate_ratchet import RatchetOutcome, decide_ratchet, undecidable_baseline
from git_commit_contents import BlobOutcome, build_contents
from git_commit_reachability import build_reachability


TRUNK_REF = "feature/atdd-pure-staging"
DOC_REL = "docs/mikado/tree.md"


# ---------------------------------------------------------------------------
# a checkout built with zlib only: blobs, trees, commits, refs, HEAD
# ---------------------------------------------------------------------------


def _write_object(objects: Path, kind: str, body: bytes) -> str:
    raw = kind.encode() + b" " + str(len(body)).encode() + b"\x00" + body
    sha = hashlib.sha1(raw).hexdigest()
    target = objects / sha[:2] / sha[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zlib.compress(raw))
    return sha


def _write_tree(objects: Path, entries: dict[str, tuple[str, str]]) -> str:
    body = b"".join(
        f"{mode} {name}".encode() + b"\x00" + bytes.fromhex(oid)
        for name, (mode, oid) in sorted(entries.items())
    )
    return _write_object(objects, "tree", body)


def _write_commit(objects: Path, tree: str, parents: list[str], message: str) -> str:
    lines = [f"tree {tree}"]
    lines += [f"parent {p}" for p in parents]
    lines.append("author T <t@example.com> 1700000000 +0000")
    lines.append("committer T <t@example.com> 1700000000 +0000")
    body = ("\n".join(lines) + "\n\n" + message + "\n").encode()
    return _write_object(objects, "commit", body)


def _nest(objects: Path, rel_path: str, blob_oid: str) -> str:
    """Build the tree chain for ``rel_path`` and return the ROOT tree oid."""
    parts = rel_path.split("/")
    oid = blob_oid
    mode = "100644"
    for name in reversed(parts):
        oid = _write_tree(objects, {name: (mode, oid)})
        mode = "40000"
    return oid


def _doc_text(corsie: str, albero: str, nodi: str) -> str:
    return f"""# tree

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


def _rows(
    *, unknown_states: tuple[tuple[str, str], ...], contradict: bool, sha: str
) -> str:
    """A document body with one coherent closed node plus N unknown-state nodes.

    ``unknown_states`` is ``(node_id, state_word)`` pairs, spelled out rather
    than generated, because WHICH node carries the unverifiable claim is the
    variable the swap case turns on.

    An out-of-vocabulary state word is the cheapest HONEST way to construct the
    third state: `_rule_unknown_state` reports it as ``unverifiable`` with no
    dependency on the object store at all, so the construction cannot be
    mistaken for the environmental condition it stands in for.
    """
    corsie = [f"| `lane-d90` | nodo D90 | `w.py` | **INTEGRATA** `{sha}` |"]
    # L'ALBERO carries only id + title: state is typed once, in the node
    # table below (`state-typed-outside-its-carrier` rejects a state word
    # here -- see validate_mikado_tree_coherence.py).
    albero = [
        "  D90 | nodo coerente",
        f"      : Riferimento di chiusura | commit `{sha}`",
    ]
    nodi = [
        "| `D90` | nodo coerente | TIENI | XS | "
        + ("PRONTO" if contradict else "FATTO")
        + f" | `{sha}` |"
    ]
    for node, word in unknown_states:
        albero.append(f"  {node} | nodo con stato ignoto")
        # The closure-reference cell must not itself hold a state word: the
        # parser's column-drift rescue scans every cell after the first, and an
        # em-dash there reads as the NOT_WORK state, which would swallow the
        # out-of-vocabulary word this fixture exists to plant.
        nodi.append(
            f"| `{node}` | nodo con stato ignoto | TIENI | XS | {word} "
            "| _(da compilare)_ |"
        )
    return _doc_text("\n".join(corsie), "\n".join(albero), "\n".join(nodi))


@pytest.fixture
def checkout(tmp_path: Path) -> dict:
    """A checkout whose HEAD commit already carries ONE unverifiable claim.

    The committed document is the ratchet's baseline; every test below rewrites
    only the working-tree copy, which is exactly the shape of a pending commit.
    """
    git_dir = tmp_path / ".git"
    objects = git_dir / "objects"
    objects.mkdir(parents=True)
    (objects / "pack").mkdir()

    root_commit = _write_commit(objects, _write_tree(objects, {}), [], "root")
    baseline_text = _rows(
        unknown_states=(("D91", "BANANA"),), contradict=False, sha=root_commit
    )
    baseline_blob = _write_object(objects, "blob", baseline_text.encode())
    tip = _write_commit(
        objects, _nest(objects, DOC_REL, baseline_blob), [root_commit], "record"
    )

    ref = git_dir / "refs" / "heads" / "feature" / "atdd-pure-staging"
    ref.parent.mkdir(parents=True)
    ref.write_text(tip + "\n")
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/atdd-pure-staging\n")

    doc = tmp_path / DOC_REL
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(baseline_text)

    return {
        "path": tmp_path,
        "doc": doc,
        "sha": root_commit,
        "tip": tip,
        "baseline_blob": baseline_blob,
        "baseline_text": baseline_text,
    }


def _run(checkout: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_mikado_tree_coherence.py"),
            "--file",
            str(checkout["doc"]),
            "--repo",
            str(checkout["path"]),
            "--trunk-ref",
            TRUNK_REF,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# the fixture must actually construct the condition, or every test is vacuous
# ---------------------------------------------------------------------------


def test_the_committed_document_already_carries_one_unverifiable_claim(
    checkout: dict,
) -> None:
    """Guard against a green earned by a fixture that constructs nothing."""
    completed = _run(checkout)

    assert "VERDICT NOT_VERIFIABLE" in completed.stdout, completed.stdout
    assert "state-not-in-vocabulary" in completed.stdout, completed.stdout
    assert "--- reject" not in completed.stdout, (
        "the fixture must carry the third state and NO reject, or the ratchet "
        f"cases below prove nothing:\n{completed.stdout}"
    )


# ---------------------------------------------------------------------------
# case 1 -- a change that ADDS an unverifiable claim is still blocked
# ---------------------------------------------------------------------------


def test_a_change_that_adds_an_unverifiable_claim_is_refused(checkout: dict) -> None:
    checkout["doc"].write_text(
        _rows(
            unknown_states=(("D91", "BANANA"), ("D92", "MANGO")),
            contradict=False,
            sha=checkout["sha"],
        )
    )

    completed = _run(checkout)

    assert completed.returncode != 0, completed.stdout
    assert "state-not-in-vocabulary · D92" in completed.stdout, completed.stdout
    assert "D92" in completed.stdout.split("RATCHET", 1)[-1], (
        "the refusal must NAME the claim that is new, not report only a total:\n"
        f"{completed.stdout}"
    )


def test_the_refusal_carries_a_how_that_actually_runs(checkout: dict) -> None:
    """A HOW is evidence only once it has been EXECUTED, never once it is present."""
    checkout["doc"].write_text(
        _rows(
            unknown_states=(("D91", "BANANA"), ("D92", "MANGO")),
            contradict=False,
            sha=checkout["sha"],
        )
    )

    block = _run(checkout).stdout.split("RATCHET BLOCK", 1)[-1]
    how = next(
        (
            line.split("HOW", 1)[1].strip()
            for line in block.splitlines()
            if "HOW" in line
        ),
        None,
    )

    assert how is not None, block
    assert "--explain D92" in how, ("the HOW must interrogate the NEW claim", how)
    replayed = subprocess.run(
        shlex.split(how.replace("python3", sys.executable, 1)),
        capture_output=True,
        text=True,
        timeout=180,
        cwd=PROJECT_ROOT,
    )
    assert replayed.returncode == 0, replayed.stderr
    assert "MANGO" in replayed.stdout, replayed.stdout


# ---------------------------------------------------------------------------
# case 2 -- an unchanged population is allowed, and the allowance is LOUD
# ---------------------------------------------------------------------------


def test_an_unchanged_unverifiable_population_is_allowed(checkout: dict) -> None:
    """The commit did not cause the condition, so it is not held hostage by it."""
    checkout["doc"].write_text(
        checkout["baseline_text"].replace("nodo coerente", "nodo coerente (riscritto)")
    )

    completed = _run(checkout)

    assert completed.returncode == 0, completed.stdout


def test_an_allowed_run_still_prints_every_unverifiable_finding(
    checkout: dict,
) -> None:
    """If the allowance goes quiet it has become a bypass wearing a ratchet's clothes."""
    checkout["doc"].write_text(
        checkout["baseline_text"].replace("nodo coerente", "nodo coerente (riscritto)")
    )

    out = _run(checkout).stdout

    assert "VERDICT NOT_VERIFIABLE" in out, out
    assert "--- unverifiable (1) ---" in out, out
    assert "state-not-in-vocabulary · D91" in out, out


def test_an_allowed_run_says_it_is_an_allowance_and_not_a_clean_pass(
    checkout: dict,
) -> None:
    checkout["doc"].write_text(
        checkout["baseline_text"].replace("nodo coerente", "nodo coerente (riscritto)")
    )

    out = _run(checkout).stdout

    assert "RATCHET ALLOW" in out, out
    assert "NOT a clean pass" in out, out
    assert "introduced none of them" in out, out


def test_an_allowed_run_states_a_baseline_provenance_a_reader_can_check(
    checkout: dict,
) -> None:
    """A baseline nobody can verify is a licence, not a measurement."""
    checkout["doc"].write_text(
        checkout["baseline_text"].replace("nodo coerente", "nodo coerente (riscritto)")
    )

    out = _run(checkout).stdout

    assert checkout["tip"][:9] in out, ("the commit the baseline was read from", out)
    assert checkout["baseline_blob"][:9] in out, ("the blob bytes measured", out)
    assert DOC_REL in out, out


# ---------------------------------------------------------------------------
# case 3 -- a real reject blocks at ANY unverifiable count
# ---------------------------------------------------------------------------


def test_a_real_reject_blocks_even_when_the_unverifiable_count_is_unchanged(
    checkout: dict,
) -> None:
    """The ratchet applies to could-not-verify ONLY. A contradiction is never ratcheted."""
    checkout["doc"].write_text(
        _rows(unknown_states=(("D91", "BANANA"),), contradict=True, sha=checkout["sha"])
    )

    completed = _run(checkout)

    assert completed.returncode == 1, completed.stdout
    assert "VERDICT INCOHERENT" in completed.stdout, completed.stdout
    assert "carrier-contradiction · D90" in completed.stdout, completed.stdout
    assert "RATCHET" not in completed.stdout, (
        "a rejected document must not even reach the ratchet -- an allowance "
        f"printed beside a reject is an invitation to misread it:\n{completed.stdout}"
    )


# ---------------------------------------------------------------------------
# case 4 -- a clean document is untouched by the ratchet, by construction
# ---------------------------------------------------------------------------


def test_a_clean_document_passes_with_no_ratchet_output(checkout: dict) -> None:
    checkout["doc"].write_text(
        _rows(unknown_states=(), contradict=False, sha=checkout["sha"])
    )

    completed = _run(checkout)

    assert completed.returncode == 0, completed.stdout
    assert "VERDICT COHERENT" in completed.stdout, completed.stdout
    assert "RATCHET" not in completed.stdout, completed.stdout


def test_a_clean_document_never_pays_for_a_baseline_it_does_not_need(
    checkout: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Byte-identical output for a clean document, proved BY CONSTRUCTION.

    Rather than compare against a golden string, this asserts the baseline is
    never even computed: a code path that does not run cannot change a byte of
    the output, and it also cannot charge the healthy document a second 200s
    gate run.
    """
    import validate_mikado_tree_coherence as gate

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the baseline was computed for a clean document")

    monkeypatch.setattr(gate, "baseline_findings", _explode)
    checkout["doc"].write_text(
        _rows(unknown_states=(), contradict=False, sha=checkout["sha"])
    )

    exit_code = gate.main(
        [
            "--file",
            str(checkout["doc"]),
            "--repo",
            str(checkout["path"]),
            "--trunk-ref",
            TRUNK_REF,
        ]
    )

    assert exit_code == 0


# ---------------------------------------------------------------------------
# the gap a count-only ratchet would leave
# ---------------------------------------------------------------------------


def test_swapping_one_unverifiable_claim_for_another_is_refused(
    checkout: dict,
) -> None:
    """Equal totals, a NEW claim underneath. Decide on the property, not the count."""
    checkout["doc"].write_text(
        _rows(unknown_states=(("D92", "MANGO"),), contradict=False, sha=checkout["sha"])
    )

    completed = _run(checkout)

    assert completed.returncode != 0, (
        "the total is unchanged (1 -> 1) but the surviving claim is a DIFFERENT "
        f"one: an allowance here is the silent pass one level up:\n{completed.stdout}"
    )
    assert "RATCHET BLOCK" in completed.stdout, completed.stdout


# ---------------------------------------------------------------------------
# the ratchet's own input can be unavailable -- and that is never permission
# ---------------------------------------------------------------------------


def test_an_unreadable_baseline_refuses_instead_of_allowing(checkout: dict) -> None:
    """Fail-closed: an allowance granted by ignorance is worse than the hostage."""
    (checkout["path"] / ".git" / "HEAD").write_text("ref: refs/heads/does-not-exist\n")

    completed = _run(checkout)

    assert completed.returncode != 0, completed.stdout
    assert "RATCHET CANNOT DECIDE" in completed.stdout, completed.stdout


def test_a_document_outside_the_checkout_has_no_baseline_and_is_refused(
    checkout: dict, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside") / "tree.md"
    outside.write_text(checkout["baseline_text"])

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_mikado_tree_coherence.py"),
            "--file",
            str(outside),
            "--repo",
            str(checkout["path"]),
            "--trunk-ref",
            TRUNK_REF,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode != 0, completed.stdout
    assert "RATCHET CANNOT DECIDE" in completed.stdout, completed.stdout


# ---------------------------------------------------------------------------
# the ratchet decision, isolated from the 200s document it guards
# ---------------------------------------------------------------------------


def test_the_decision_is_a_multiset_so_a_repeated_key_still_counts_as_growth() -> None:
    """Two unverifiable findings on the SAME node are two claims, not one."""
    decision = decide_ratchet(
        current=("closure-sha-unverifiable · D22", "closure-sha-unverifiable · D22"),
        baseline=("closure-sha-unverifiable · D22",),
        provenance="test",
    )

    assert decision.outcome is RatchetOutcome.INCREASED
    assert decision.blocks


def test_a_shrinking_population_is_allowed_not_merely_an_equal_one() -> None:
    decision = decide_ratchet(
        current=("closure-sha-unverifiable · D22",),
        baseline=(
            "closure-sha-unverifiable · D22",
            "closure-sha-unverifiable · D23",
        ),
        provenance="test",
    )

    assert decision.outcome is RatchetOutcome.NOT_INCREASED
    assert not decision.blocks


def test_an_undecidable_baseline_blocks_and_carries_its_reason() -> None:
    decision = undecidable_baseline(
        current=("closure-sha-unverifiable · D22",),
        reason="HEAD does not resolve",
    )

    assert decision.blocks
    assert "HEAD does not resolve" in decision.render()


# ---------------------------------------------------------------------------
# the blob reader the baseline stands on
# ---------------------------------------------------------------------------


def test_the_blob_reader_returns_the_committed_bytes_and_their_oid(
    checkout: dict,
) -> None:
    contents = build_contents(checkout["path"])

    answer = contents.blob_at(checkout["tip"], DOC_REL)

    assert answer.outcome is BlobOutcome.PRESENT, answer.detail
    assert answer.data == checkout["baseline_text"].encode()
    assert answer.oid == checkout["baseline_blob"]


def test_the_blob_reader_tells_absent_apart_from_unreadable(checkout: dict) -> None:
    """ "The file is not there" is a decidable fact; it must never arrive as empty bytes."""
    contents = build_contents(checkout["path"])

    absent = contents.blob_at(checkout["tip"], "docs/mikado/never-written.md")
    unreadable = contents.blob_at("f" * 40, DOC_REL)

    assert absent.outcome is BlobOutcome.ABSENT, absent.detail
    assert absent.data is None
    assert unreadable.outcome is BlobOutcome.INDETERMINATE, unreadable.detail


def test_head_resolves_from_the_worktree_gitdir_not_the_shared_common_dir(
    checkout: dict,
) -> None:
    """A linked worktree keeps its own HEAD; the shared dir holds a DIFFERENT one.

    Resolving "HEAD" through the ref lookup would answer with the main
    checkout's HEAD -- a different commit, silently, and therefore a baseline
    measured on bytes nobody asked about.
    """
    reachability = build_reachability(checkout["path"])

    assert reachability.resolve_head() == checkout["tip"]
