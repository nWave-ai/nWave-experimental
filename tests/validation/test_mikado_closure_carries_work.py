"""Acceptance tests: a closure sha must CARRY the work, not merely exist.

The gate that enforces "decide on the property, never the designation" was
itself deciding on a designation. Node D32 closed citing a sha that is a real,
reachable ancestor of trunk, with the note «lettore + `des
report-delivery-metrics`, verificato su dati veri» -- and that commit rewrote
three lines of one feature-delta document and nothing else. Ancestry resolved,
pointer present, gate green.

These tests pin the properties:
- a closure note that NAMES an artifact, over commits that rewrote only
  bookkeeping documentation, is a rejection;
- the same note over a commit that rewrote product code is not;
- a commit whose diff cannot be read is UNVERIFIABLE and reaches the verdict,
  never a silent pass;
- a note that names no artifact is counted as unfalsifiable and is neither
  passed off as verified nor charged as a rejection;
- the rejection's HOW routes to a producing affordance that names the sha that
  DOES carry the work.

No git binary anywhere: the object store is written with zlib, exactly like the
reader reads it.
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

from git_commit_contents import (
    ContentAvailability,
    LooseObjectContents,
    UnavailableContents,
)
from git_commit_reachability import LooseObjectReachability
from validate_mikado_tree_coherence import (
    Severity,
    Verdict,
    artifact_claims,
    check_tree_coherence,
    is_bookkeeping_path,
)


TRUNK_REF = "feature/atdd-pure-staging"


# --------------------------------------------------------------------------
# an object store written with zlib only
# --------------------------------------------------------------------------


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
    """Trunk of four commits: a docs-only one, a code one, and a merge."""
    git_dir = tmp_path / ".git"
    objects = git_dir / "objects"
    objects.mkdir(parents=True)
    (objects / "pack").mkdir()

    base_layout = {
        "docs": {"mikado": {"plan.md": "v1"}},
        "src": {"cli.py": "v1"},
    }
    base_tree = _write_tree(objects, base_layout)
    base = _write_commit(objects, base_tree, [], "base")

    docs_only_layout = {
        "docs": {"mikado": {"plan.md": "v2"}},
        "src": {"cli.py": "v1"},
    }
    docs_only = _write_commit(
        objects, _write_tree(objects, docs_only_layout), [base], "docs only"
    )

    code_layout = {
        "docs": {"mikado": {"plan.md": "v2"}},
        "src": {"cli.py": "v1", "report_delivery_metrics.py": "the reader"},
    }
    with_code = _write_commit(
        objects, _write_tree(objects, code_layout), [docs_only], "the reader"
    )

    ref = git_dir / "refs" / "heads" / "feature" / "atdd-pure-staging"
    ref.parent.mkdir(parents=True)
    ref.write_text(with_code + "\n")

    return {
        "path": tmp_path,
        "objects": objects,
        "base": base,
        "docs_only": docs_only,
        "with_code": with_code,
        "reachability": LooseObjectReachability(tmp_path),
        "contents": LooseObjectContents(tmp_path),
    }


#: A decorative CORSIA row, unrelated to any node id a test asserts on. Keeps
#: `## CORSIE` populated so the gate still sees its floor of >= 2 carriers
#: once `## L'ALBERO` carries no state (see the module docstring in
#: validate_mikado_tree_coherence.py: state is typed once, in
#: `## STATO NODO PER NODO`, and `## L'ALBERO` no longer contributes to
#: `carriers_seen` at all).
_DECOR_CORSIA = "| `lane-decor` | decor | `x.py` | **PRONTO** |"


def _doc(
    tmp_path: Path, nodi: str, corsie: str = _DECOR_CORSIA, name: str = "tree.md"
) -> Path:
    text = f"""# tree

## CORSIE

| Corsia | Tipo | `owns` | Stato |
|---|---|---|---|
{corsie}

## L'ALBERO

```nwtree
GOAL | esempio
  D99 | qualcosa
```

## STATO NODO PER NODO

| Nodo | Cosa | Verdetto | Effort | Stato | Riferimento di chiusura |
|---|---|---|---|---|---|
{nodi}
"""
    path = tmp_path / name
    path.write_text(text)
    return path


def _run(doc: Path, repo: dict, contents=None):
    return check_tree_coherence(
        doc,
        reachability=repo["reachability"],
        trunk_ref=TRUNK_REF,
        contents=repo["contents"] if contents is None else contents,
    )


# --------------------------------------------------------------------------
# the reader: what did this commit rewrite?
# --------------------------------------------------------------------------


def test_reader_names_exactly_the_rewritten_paths(repo):
    answer = repo["contents"].changed_paths(repo["with_code"])

    assert answer.outcome is ContentAvailability.AVAILABLE
    assert answer.paths == ("src/report_delivery_metrics.py",)


def test_reader_does_not_open_subtrees_the_commit_left_alone(repo):
    answer = repo["contents"].changed_paths(repo["docs_only"])

    assert answer.paths == ("docs/mikado/plan.md",)


def test_reader_diffs_a_merge_against_its_first_parent(repo, tmp_path):
    objects = repo["objects"]
    lane_layout = {
        "docs": {"mikado": {"plan.md": "v1"}},
        "src": {"cli.py": "v1", "lane_feature.py": "lane work"},
    }
    lane = _write_commit(
        objects, _write_tree(objects, lane_layout), [repo["base"]], "lane"
    )
    merged_layout = {
        "docs": {"mikado": {"plan.md": "v2"}},
        "src": {
            "cli.py": "v1",
            "report_delivery_metrics.py": "the reader",
            "lane_feature.py": "lane work",
        },
    }
    merge = _write_commit(
        objects,
        _write_tree(objects, merged_layout),
        [repo["with_code"], lane],
        "merge the lane",
    )

    answer = LooseObjectContents(repo["path"]).changed_paths(merge)

    assert answer.outcome is ContentAvailability.AVAILABLE
    assert answer.parent_count == 2
    # what the merge brought onto trunk, not an empty set
    assert answer.paths == ("src/lane_feature.py",)


def test_reader_is_indeterminate_when_the_object_is_not_readable(repo):
    unreadable = repo["objects"] / repo["with_code"][:2] / repo["with_code"][2:]
    unreadable.unlink()

    answer = LooseObjectContents(repo["path"]).changed_paths(repo["with_code"])

    assert answer.outcome is ContentAvailability.INDETERMINATE
    assert answer.paths == ()


# --------------------------------------------------------------------------
# the rule: a sha that exists is still a designation
# --------------------------------------------------------------------------


def test_rejects_closure_whose_commit_rewrote_only_bookkeeping_docs(repo, tmp_path):
    """The D32 shape, reproduced: real sha, real ancestor, no work in it."""
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D32` | lettore di costo | SEMPLIFICA | M | FATTO | "
            f"`{repo['docs_only']}` — lettore + `des report-delivery-metrics`, "
            f"verificato su dati veri |"
        ),
    )

    report = _run(doc, repo)

    rejects = [
        f
        for f in report.by_severity(Severity.REJECT)
        if f.rule == "closure-sha-does-not-carry-the-claim"
    ]
    assert len(rejects) == 1
    assert rejects[0].node_id == "D32"
    assert report.verdict is Verdict.INCOHERENT
    assert report.carry.not_carried == 1


def test_accepts_the_same_claim_when_the_commit_rewrote_product_code(repo, tmp_path):
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D32` | lettore di costo | SEMPLIFICA | M | FATTO | "
            f"`{repo['with_code']}` — lettore + `des report-delivery-metrics` |"
        ),
    )

    report = _run(doc, repo)

    assert not [
        f for f in report.findings if f.rule == "closure-sha-does-not-carry-the-claim"
    ]
    assert report.carry.carried == 1


def test_a_closure_claiming_a_named_source_path_is_checked_the_same_way(repo, tmp_path):
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D40` | ritiro proiezioni | SEMPLIFICA | S | FATTO | "
            f"`{repo['docs_only']}` — riscritto `src/report_delivery_metrics.py` |"
        ),
    )

    report = _run(doc, repo)

    assert [
        f for f in report.findings if f.rule == "closure-sha-does-not-carry-the-claim"
    ]


# --------------------------------------------------------------------------
# the same designation error, one level up: SOME work is not THE named work
# --------------------------------------------------------------------------


@pytest.fixture
def other_product_work(repo):
    """A commit on trunk that rewrites product code, but not the named artifact."""
    objects = repo["objects"]
    layout = {
        "docs": {"mikado": {"plan.md": "v2"}},
        "src": {
            "cli.py": "v1",
            "report_delivery_metrics.py": "the reader",
            "unrelated.py": "somewhere else entirely",
        },
    }
    sha = _write_commit(
        objects, _write_tree(objects, layout), [repo["with_code"]], "unrelated work"
    )
    ref = repo["path"] / ".git" / "refs" / "heads" / "feature" / "atdd-pure-staging"
    ref.write_text(sha + "\n")
    return sha


def test_rejects_a_closure_naming_a_path_no_cited_commit_ever_touched(
    repo, other_product_work, tmp_path
):
    """Product code moved, so the old check passed -- but not the code named."""
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D40` | lettore di costo | SEMPLIFICA | M | FATTO | "
            f"`{other_product_work}` — riscritto `src/report_delivery_metrics.py` |"
        ),
    )

    report = _run(doc, repo)

    rejects = [
        f
        for f in report.by_severity(Severity.REJECT)
        if f.rule == "closure-names-a-path-the-commit-never-touched"
    ]
    assert len(rejects) == 1
    assert "src/report_delivery_metrics.py" in rejects[0].what
    assert report.verdict is Verdict.INCOHERENT
    assert report.carry.not_carried == 1
    assert report.carry.carried == 0


def test_accepts_a_named_path_that_is_among_the_rewritten_paths(
    repo, other_product_work, tmp_path
):
    """The guard against over-rejection: a truthful note still passes."""
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D40` | altrove | SEMPLIFICA | M | FATTO | "
            f"`{other_product_work}` — riscritto `src/unrelated.py` |"
        ),
    )

    report = _run(doc, repo)

    assert not [f for f in report.findings if f.rule.startswith("closure-names-a-path")]
    assert report.carry.carried == 1


def test_a_des_subcommand_no_path_evidences_is_advisory_not_a_rejection(
    repo, other_product_work, tmp_path
):
    """`des next` ships in `deliver_loop_projection.py`: the fragment can miss.

    A subcommand name is matched by heuristic fragments, so an absent match is
    a weaker signal than an absent path and must not block. It still may never
    be counted as carrying the claim.
    """
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D41` | loop | SEMPLIFICA | M | FATTO | "
            f"`{other_product_work}` — `des next` |"
        ),
    )

    report = _run(doc, repo)

    advisories = [
        f
        for f in report.by_severity(Severity.ADVISORY)
        if f.rule == "closure-names-a-subcommand-no-path-evidences"
    ]
    assert len(advisories) == 1
    assert report.verdict is Verdict.COHERENT
    assert report.carry.carried == 0
    assert report.carry.not_carried == 0
    assert report.carry.unmatched == 1


# --------------------------------------------------------------------------
# the third state, and the unfalsifiable majority
# --------------------------------------------------------------------------


def test_unreadable_diff_is_unverifiable_and_never_coherent(repo, tmp_path):
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D32` | lettore | SEMPLIFICA | M | FATTO | "
            f"`{repo['docs_only']}` — `des report-delivery-metrics` |"
        ),
    )
    blind = UnavailableContents("object store not readable in this checkout")

    report = _run(doc, repo, contents=blind)

    assert report.verdict is Verdict.UNVERIFIABLE
    assert [f for f in report.findings if f.rule == "closure-carry-unverifiable"]
    assert report.carry.undecidable == 1
    assert report.carry.not_carried == 0, "undecidable is never charged as a rejection"


def test_a_note_naming_no_artifact_is_counted_not_asserted(repo, tmp_path):
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D19` | premessa falsa | TIENI | S | CHIUSO | "
            f"`{repo['docs_only']}` — premessa falsa, la leva non esiste |"
        ),
    )

    report = _run(doc, repo)

    assert not [f for f in report.findings if f.rule.startswith("closure-carry")]
    assert not [
        f for f in report.findings if f.rule == "closure-sha-does-not-carry-the-claim"
    ]
    assert report.carry.unfalsifiable == 1
    assert report.carry.evaluable == 0


def test_the_coverage_line_states_what_the_gate_cannot_catch(repo, tmp_path):
    doc = _doc(
        tmp_path,
        nodi=(
            f"| `D19` | premessa falsa | TIENI | S | CHIUSO | `{repo['docs_only']}` |"
        ),
    )

    rendered = _run(doc, repo).carry.render()

    assert "unfalsifiable" in rendered
    assert "cannot catch" in rendered


# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,bookkeeping",
    [
        ("docs/mikado/plan.md", True),
        ("docs/feature/x/feature-delta.md", True),
        ("README.md", True),
        ("nWave/skills/nw-design/SKILL.md", False),
        ("nWave/data/orchestrator-affordance/catalog.md", False),
        ("src/des/cli/report_delivery_metrics.py", False),
    ],
)
def test_only_the_plan_talking_about_itself_is_bookkeeping(path, bookkeeping):
    assert is_bookkeeping_path(path) is bookkeeping


@pytest.mark.parametrize(
    "note,expected",
    [
        (
            "`6962f717b` — lettore + `des report-delivery-metrics`",
            ("des report-delivery-metrics",),
        ),
        (
            "`abc1234` — riscritto `scripts/validation/x.py`",
            ("scripts/validation/x.py",),
        ),
        ("`abc1234` — premessa falsa, la leva non esiste", ()),
        ("`abc1234` — aggiornato `docs/mikado/plan.md`", ()),
    ],
)
def test_only_a_named_artifact_makes_a_note_falsifiable(note, expected):
    assert artifact_claims(note) == expected
