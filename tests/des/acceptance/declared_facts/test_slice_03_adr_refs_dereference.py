# @feature-declared-facts-reachable-recorded
# @slice-03
"""D6 -- a declared `adr-refs` reference resolves to a real ADR file, or is
NAMED dangling -- never silence.

declared-facts-reachable-recorded slice-03. Value statement (feature-delta.md
[REF] Slice Plan): "A declared `adr-refs` reference resolves to a real file
or is named dangling (D6)".

Two new pieces, per feature-delta.md DD-8/DD-9 (Target API is DESIGN-pinned;
this module never invents a different shape):

* `des.domain.feature_delta_source.dereference_adr_refs(section_body, *,
  repo_root, feature_id) -> tuple[AdrRefDereference, ...]` -- pure, read-only,
  never raises. Per-id algebra is exactly two states (PRESENT{adr_id,
  resolved_path} / ABSENT{adr_id}); the 4th-state locus resolver is explicitly
  OUT of scope (feature-delta.md Section 11 row 1, RIDIMENSIONA). Matching is
  case-insensitive on the id prefix against a DECLARED, CLOSED, ORDERED root
  tuple (Technology Choices row 2).
* `des.cli.feature_delta_doctor._dangling_adr_ref_gaps` wired into `diagnose`
  (gains a keyword-only, DEFAULTED `repo_root` parameter -- DD-9), and `main`
  gains an optional `--repo-root` flag. The AGGREGATE the doctor reports adds
  a THIRD state beyond per-id PRESENT/ABSENT: `dangling-adr-ref` (a real,
  declared-but-nonexistent id) versus `adr-ref-could-not-verify` (the
  resolved repo_root holds NONE of the 4 declared root directories -- the
  tree itself, not any one id, is the problem). Reporting zero gaps in the
  could-not-verify case is a GDP-6 silent-wrong -- exactly the defect class
  this slice closes. The two states are pinned here as distinct, literal gap
  ids (`dangling-adr-ref` / `adr-ref-could-not-verify`) because no gap id
  existed for either state before this slice -- DISTILL fixes the observable
  contract the crafter implements against, per the Target API section of the
  dispatch envelope.

Driving surface (P1-P4 in-process active-RED pattern, `nw-distill-red-
scaffolding`): both target modules already exist today (only the two named
symbols are missing/incomplete), so this file imports them directly --
`des.domain.feature_delta_source` and `des.cli.feature_delta_doctor` -- and
reaches the not-yet-existing capability through `getattr`/`inspect.signature`
guards that convert an absent symbol into a semantic `AssertionError` at
RUNTIME, never a collection-time `ImportError`. `feature_delta_doctor.main`
is the composition-root CLI entry (already registered as the `feature-delta-
doctor` subcommand in `des.cli.__main__`); scenario 6 drives it in-process
(Layer 3 composition, Mandate 13 default) rather than forking a subprocess.

Fixtures build a `tmp_path` replica of the 4 declared ADR root directories
(never the real repo's ADR inventory, which changes) and deliberately carry
BOTH casing conventions the repo really uses (`ADR-DFR-001-*.md` upper,
`adr-029-*.md` lower) so a resolver that only ever matches one casing cannot
pass.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from des.cli import feature_delta_doctor
from des.domain import feature_delta_source


_FEATURE_ID = "declared-facts-reachable-recorded"

#: The declared, closed, ordered root tuple (feature-delta.md Technology
#: Choices row 2) -- relative path SEGMENTS under a repo_root.
_DECLARED_ADR_ROOTS: tuple[tuple[str, ...], ...] = (
    ("docs", "product", "architecture"),
    ("docs", "feature", _FEATURE_ID, "design", "adrs"),
    ("docs", "architecture", "adrs"),
    ("docs", "adrs"),
)

_ADR_REFS_HEADING = "## Wave: DESIGN / [REF] ADR Refs"

#: Gap ids this slice's AT set PINS -- neither exists in production code
#: today (D6 is net-new); DISTILL fixes the literal contract the crafter
#: implements against, per the dispatch envelope's Target API + "third state"
#: sections.
_DANGLING_GAP_ID = "dangling-adr-ref"
_COULD_NOT_VERIFY_GAP_ID = "adr-ref-could-not-verify"


def _make_adr_root_tree(repo_root: Path) -> None:
    """Create all 4 declared ADR root directories, empty, under `repo_root`."""
    for parts in _DECLARED_ADR_ROOTS:
        repo_root.joinpath(*parts).mkdir(parents=True, exist_ok=True)


def _place_adr_file(repo_root: Path, root_index: int, filename: str) -> Path:
    """Write a stub ADR file named `filename` under declared root `root_index`."""
    root = repo_root.joinpath(*_DECLARED_ADR_ROOTS[root_index])
    root.mkdir(parents=True, exist_ok=True)
    target = root / filename
    target.write_text("# stub ADR fixture\n", encoding="utf-8")
    return target


def _clean_feature_delta(adr_refs_body: str) -> str:
    """A feature-delta body that is CLEAN on every OTHER doctor leg (malformed
    Wave headings, missing locked sections, Reuse Analysis, sustainability,
    Slice Plan header) -- reused verbatim shape from
    `tests/des/unit/cli/test_feature_delta_doctor.py::CLEAN_FEATURE_DELTA` so
    the only variable under test is the `adr-refs` body, never a confound
    from an unrelated leg.
    """
    return (
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
        "\n"
        "Some architecture prose.\n"
        "\n"
        f"{_ADR_REFS_HEADING}\n"
        "\n"
        f"{adr_refs_body}\n"
        "\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n"
        "\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | ships the walking skeleton | done |  | shipped |\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


# ---------------------------------------------------------------------------
# dereference_adr_refs (DD-8) -- the per-id PRESENT/ABSENT resolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("root_index", "declared_id", "filename"),
    [
        pytest.param(
            0,
            "ADR-DFR-001",
            "ADR-DFR-001-both-outcomes.md",
            id="same-case-upper-id-upper-file",
        ),
        pytest.param(
            3,
            "ADR-029",
            "adr-029-po-atd-role-resplit-atdd-pure.md",
            id="upper-id-lower-file-cross-case",
        ),
        pytest.param(
            2,
            "adr-flow-006",
            "ADR-FLOW-006-compiled-feature-context-bootstrap.md",
            id="lower-id-upper-file-cross-case",
        ),
    ],
)
def test_dereference_adr_refs_resolves_a_declared_id_to_its_real_file_case_insensitively(
    tmp_path: Path, root_index: int, declared_id: str, filename: str
) -> None:
    """`Path.glob` is case-SENSITIVE on Linux; the tree really holds both
    `ADR-DFR-001-*.md` (upper) and `adr-029-*.md` (lower) casing conventions
    (feature-delta.md Technology Choices row 2). An AT that only ever
    exercises one casing does not prove the case-insensitive contract -- this
    scenario is parametrized across BOTH directions (upper id / lower file,
    lower id / upper file) plus a same-case baseline, each under a DIFFERENT
    one of the 4 declared roots.
    """
    dereference_adr_refs = getattr(feature_delta_source, "dereference_adr_refs", None)
    assert dereference_adr_refs is not None, (
        "des.domain.feature_delta_source.dereference_adr_refs is not yet "
        "implemented (DD-8) -- the D6 ADR-ref resolver has not been authored."
    )

    _make_adr_root_tree(tmp_path)
    resolved_file = _place_adr_file(tmp_path, root_index, filename)
    section_body = f"- {declared_id}\n"

    records: Any = dereference_adr_refs(
        section_body, repo_root=tmp_path, feature_id=_FEATURE_ID
    )
    by_id = {getattr(record, "adr_id", None): record for record in records}
    assert declared_id in by_id, (
        f"expected exactly one dereference record for {declared_id!r} -- got "
        f"ids {list(by_id)!r} from records={records!r}"
    )
    resolved_path = getattr(by_id[declared_id], "resolved_path", None)
    assert resolved_path is not None, (
        f"{declared_id!r} names a real file at {resolved_file} under a "
        f"declared root -- expected a PRESENT resolution (case-insensitive "
        f"id match against the id prefix), got resolved_path=None "
        f"(record={by_id[declared_id]!r})"
    )
    assert Path(resolved_path).resolve() == resolved_file.resolve(), (
        f"resolved_path must point at the ACTUAL matching file {resolved_file} "
        f"-- got {resolved_path!r}"
    )


def test_dereference_adr_refs_never_resolves_an_id_that_exists_under_no_declared_root(
    tmp_path: Path,
) -> None:
    """A declared id with no matching file under ANY of the 4 roots must
    resolve ABSENT -- and must do so even in the SAME call that resolves a
    sibling id PRESENT, proving the ABSENT verdict is a genuine per-id
    classification, never an artifact of an empty/broken tree.
    """
    dereference_adr_refs = getattr(feature_delta_source, "dereference_adr_refs", None)
    assert dereference_adr_refs is not None, (
        "des.domain.feature_delta_source.dereference_adr_refs is not yet "
        "implemented (DD-8) -- the D6 ADR-ref resolver has not been authored."
    )

    _make_adr_root_tree(tmp_path)
    _place_adr_file(tmp_path, 0, "ADR-DFR-001-both-outcomes.md")
    section_body = "- ADR-DFR-001\n- ADR-GHOST-999\n"

    records: Any = dereference_adr_refs(
        section_body, repo_root=tmp_path, feature_id=_FEATURE_ID
    )
    by_id = {getattr(record, "adr_id", None): record for record in records}

    assert "ADR-GHOST-999" in by_id, (
        f"expected a dereference record for ADR-GHOST-999 -- got ids "
        f"{list(by_id)!r} from records={records!r}"
    )
    ghost_resolved_path = getattr(by_id["ADR-GHOST-999"], "resolved_path", None)
    assert ghost_resolved_path is None, (
        "ADR-GHOST-999 names no file under any of the 4 declared roots -- it "
        "must resolve ABSENT (resolved_path=None); it must NEVER be silently "
        f"treated as PRESENT. got record={by_id['ADR-GHOST-999']!r}"
    )

    present_record = by_id.get("ADR-DFR-001")
    assert present_record is not None and getattr(
        present_record, "resolved_path", None
    ), (
        f"ADR-DFR-001 (the sibling id in the SAME call) DOES resolve under "
        f"the tree -- got record={present_record!r}. If this also fails, the "
        f"tree/fixture is wrong, not the ABSENT classification under test."
    )


# ---------------------------------------------------------------------------
# feature_delta_doctor (DD-9) -- the aggregate 3-state gap report
# ---------------------------------------------------------------------------


def test_feature_delta_doctor_never_silently_passes_over_a_dangling_adr_ref(
    tmp_path: Path,
) -> None:
    """THE required negative AT (dispatch envelope: "a nonexistent ADR
    reference is NEVER passed over in silence"). Every declared root exists
    (so verification IS possible) and holds nothing matching the declared id
    -- the doctor MUST surface a `dangling-adr-ref` gap; reporting zero gaps
    here would be the D6 defect this slice exists to close, silently
    accepted.
    """
    sig = inspect.signature(feature_delta_doctor.diagnose)
    assert "repo_root" in sig.parameters, (
        "feature_delta_doctor.diagnose must accept a repo_root parameter "
        "(DD-9), wired to a dangling-ADR-ref check -- not yet implemented."
    )

    _make_adr_root_tree(tmp_path)  # all 4 declared roots exist, all EMPTY
    content = _clean_feature_delta("- ADR-GHOST-999\n")

    gaps = feature_delta_doctor.diagnose(content, repo_root=tmp_path)

    assert gaps, (
        "a feature-delta declaring ADR-GHOST-999 in its adr-refs section, "
        "with every declared root present but holding no matching file, MUST "
        "surface a Gap -- silently reporting zero gaps is exactly the D6 "
        "defect (a declared ADR reference is never dereferenced) this slice "
        "exists to close."
    )
    dangling_gaps = [gap for gap in gaps if gap["id"] == _DANGLING_GAP_ID]
    assert len(dangling_gaps) == 1, (
        f"expected exactly one gap id={_DANGLING_GAP_ID!r} for the single "
        f"dangling id ADR-GHOST-999 -- got gaps={gaps!r}"
    )
    gap = dangling_gaps[0]
    assert "ADR-GHOST-999" in gap["what"], (
        f"'what' must name the dangling id so the operator knows WHICH "
        f"reference is broken -- got gap={gap!r}"
    )
    assert gap["why"].strip() and gap["how"].strip(), (
        f"every gap carries the STANDING what/why/how triple -- got gap={gap!r}"
    )


def test_feature_delta_doctor_distinguishes_could_not_verify_from_dangling_when_repo_root_holds_no_declared_roots(
    tmp_path: Path,
) -> None:
    """The AGGREGATE third state: when the resolved `repo_root` contains
    NONE of the 4 declared root directories (wrong tree / wrong
    `--repo-root`), the doctor cannot answer at all -- reporting "0 gaps" is
    a GDP-6 silent-wrong. This state must be a DIFFERENT, distinguishable gap
    id from `dangling-adr-ref`: the two route the operator to DIFFERENT
    actions (fix the tree you pointed at vs. write the missing ADR).
    """
    sig = inspect.signature(feature_delta_doctor.diagnose)
    assert "repo_root" in sig.parameters, (
        "feature_delta_doctor.diagnose must accept a repo_root parameter "
        "(DD-9), wired to a dangling-ADR-ref check -- not yet implemented."
    )

    wrong_tree = tmp_path / "not-the-declared-repo-tree"
    wrong_tree.mkdir()  # exists, but holds none of the 4 declared roots
    content = _clean_feature_delta("- ADR-DFR-001\n")

    gaps = feature_delta_doctor.diagnose(content, repo_root=wrong_tree)

    assert gaps, (
        "when repo_root holds NONE of the 4 declared ADR root directories "
        "the doctor cannot verify ANY reference -- reporting 0 gaps there is "
        "silent-wrong (GDP-6); it must degrade LOUD as a distinct third "
        "state instead of silently agreeing everything resolved."
    )
    could_not_verify_gaps = [
        gap for gap in gaps if gap["id"] == _COULD_NOT_VERIFY_GAP_ID
    ]
    assert len(could_not_verify_gaps) == 1, (
        f"expected exactly one gap id={_COULD_NOT_VERIFY_GAP_ID!r} naming the "
        f"unverifiable tree -- got gaps={gaps!r}"
    )
    assert not any(gap["id"] == _DANGLING_GAP_ID for gap in gaps), (
        f"could-not-verify must NEVER be reported as {_DANGLING_GAP_ID!r} -- "
        f"dangling means 'this id has no file', could-not-verify means 'the "
        f"tree itself cannot be checked'; collapsing the two hides which "
        f"action the operator should take. got gaps={gaps!r}"
    )


def test_feature_delta_doctor_diagnose_keeps_a_single_argument_call_working_and_zero_gaps_on_a_clean_delta() -> (
    None
):
    """Backward compatibility is a contract, not a nicety:
    `src/des/application/deliver_loop_projection.py:160` calls
    `feature_delta_doctor.diagnose(content)` with ONE positional argument and
    that file is OUT of this slice's ownership. `repo_root` must be
    KEYWORD-ONLY and DEFAULTED so that exact call keeps working unchanged,
    and an otherwise-clean delta whose adr-refs body carries no ADR-id-shaped
    token reports zero gaps.
    """
    sig = inspect.signature(feature_delta_doctor.diagnose)
    repo_root_param = sig.parameters.get("repo_root")
    assert repo_root_param is not None, (
        "feature_delta_doctor.diagnose must gain a repo_root parameter "
        "(DD-9) -- not yet implemented."
    )
    assert repo_root_param.kind is inspect.Parameter.KEYWORD_ONLY, (
        f"repo_root must be KEYWORD-ONLY (DD-9: 'constrains the crafter to a "
        f"keyword-only, defaulted repo_root') -- got kind="
        f"{repo_root_param.kind!r}. deliver_loop_projection.py:160 calls "
        f"diagnose(content) with ONE positional argument; a positional "
        f"repo_root risks silently breaking that binding on any future "
        f"parameter reordering."
    )
    assert repo_root_param.default is not inspect.Parameter.empty, (
        "repo_root must carry a default (DD-9: 'defaulted repo_root') so "
        "diagnose(content) -- the ONE-argument call "
        "deliver_loop_projection.py:160 makes today -- keeps working "
        "unchanged."
    )

    content = _clean_feature_delta("No ADRs referenced by this slice.\n")
    # ONE positional argument, exactly as deliver_loop_projection.py:160 calls it.
    gaps = feature_delta_doctor.diagnose(content)

    assert gaps == [], (
        f"an otherwise-clean feature-delta whose adr-refs body carries no "
        f"ADR-id-shaped token must report ZERO gaps under the single-"
        f"argument call -- got gaps={gaps!r}"
    )


def test_feature_delta_doctor_main_wires_an_optional_repo_root_flag_surfacing_the_dangling_gap_as_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`main()` gains an optional `--repo-root` flag (DD-9) driving the SAME
    aggregate check `diagnose(content, repo_root=...)` exercises -- proving
    the wiring reaches the real CLI composition-root entry, not only the
    pure function.
    """
    parser = feature_delta_doctor._build_parser()
    option_strings = {
        opt for action in parser._actions for opt in action.option_strings
    }
    assert "--repo-root" in option_strings, (
        "feature_delta_doctor's CLI parser must gain an optional --repo-root "
        "flag (DD-9) -- not yet wired."
    )

    _make_adr_root_tree(tmp_path)  # all roots present, all EMPTY
    content = _clean_feature_delta("- ADR-GHOST-999\n")
    target = tmp_path / "feature-delta.md"
    target.write_text(content, encoding="utf-8")

    exit_code = feature_delta_doctor.main(
        [str(target), "--repo-root", str(tmp_path), "--format", "json"]
    )
    captured = capsys.readouterr()

    assert exit_code == 1, (
        f"expected exit 1 (a dangling ADR ref is >=1 gap) -- got {exit_code}. "
        f"stdout={captured.out!r} stderr={captured.err!r}"
    )
    report = json.loads(captured.out)
    gap_ids = {gap["id"] for gap in report["gaps"]}
    assert _DANGLING_GAP_ID in gap_ids, (
        f"main() must surface the dangling-adr-ref gap through --repo-root "
        f"-- got gaps={report['gaps']!r}"
    )
