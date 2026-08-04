# @feature-fix-feature-at-files-quoted-tag-discriminant
# @slice-01
"""Regression AT -- per-format DECLARED-vs-CITED tag discriminant for
``src/des/application/feature_at_files.py`` (ADR-001,
``docs/feature/fix-feature-at-files-quoted-tag-discriminant/design/adrs/
adr-001-per-format-declared-vs-cited-tag-discriminant.md``).

@contract-shape:bounded-change

Defect (SSOT: ``defects.md``,
``feature-at-files-attributes-a-quoted-tag-in-prose-as-a-declared-tag``):
``feature_tagged_test_files`` and ``resolve_test_file_attribution`` scan the
raw first-20-lines head window of ANY file with a plain substring/regex
match, conflating a tag DECLARED as a file's own attribution with a tag
merely CITED as a quoted example inside a docstring or prose paragraph. Two
real files in THIS repo already trip it: ``test_shared_multi_slice_at_file_
attribution.py`` quotes a real 6-slice tag block verbatim as an RCA example
(indentation 4, inside a docstring exceeding the 20-line window), and
``test_slice_id_grammar_ssot.py`` mentions ``@slice-04a`` in a sentence at
column 0 (also inside its docstring). Both false-positively attribute the
citing file to slices it never claims, which cascades into
``AtKindAmbiguous`` and blocks ``des check-slice-at-completeness`` /
``carpaccio_slice_gate`` for ``gate-armed-state-derivation`` slice-07.

Covers the 7 observable constraints (a)-(g) from feature-delta.md Wave
DISCUSS [REF] Value:

    R1 (a) -- .feature 2-space-indented Gherkin tags stay attributed (no
             false negatives introduced by the fix)
    R2 (b) -- files carrying their own real tags AFTER a docstring stay
             attributed (no scan-window restriction)
    R3 (c) -- the 6 quoted indentation-4 lines in
             test_shared_multi_slice_at_file_attribution.py's docstring
             disappear as false positives (0 detected, was 6)
    R4 (d) -- the prose citation at column 0 in test_slice_id_grammar_ssot.py
             disappears as a false-positive slice attribution
    R5 (e) -- discover_at_kind_for_slice(., gate-armed-state-derivation,
             slice-07) resolves AtKindResolved (currently AtKindAmbiguous)
    R6 (f) -- run_contract_gate._node_belongs_to_slice stops returning True
             for the citing files
    R7 (g) -- the module docstring lists all 8 real consumers (doc
             correction, non-code assertion)

Driving surface (Mandate 16, Layer 3 composition-root default): every
scenario drives the REAL, existing production module
``des.application.feature_at_files`` (and, for R6, ``des.cli.
run_contract_gate._node_belongs_to_slice``, which composes
``resolve_test_file_attribution`` and has no isolated test seam of its own)
directly -- the exact application-layer composition root this module's own
docstring names as the SSOT for 8 real consumers. No new CLI driving port is
introduced by this fix (single-file, ADD-not-mutate per the design).

Two of the fixture families below use REAL files already committed in this
repo (``_CITING_SHARED_MULTI_SLICE``, ``_CITING_SLICE_ID_GRAMMAR``,
``_REAL_AT_FILE``) rather than synthetic ``tmp_path`` reconstructions --
these are the exact two confuted false positives the design measured
empirically against; pinning the real files (not a lookalike copy) is the
regression witness ADR-001's own "Validazione empirica" table used. The
Gherkin-population and after-docstring cases (R1, R2) use synthetic
``tmp_path`` fixtures since the real 62-file / 21-file populations cannot be
enumerated one-by-one here without becoming brittle to future authoring --
the synthetic fixtures reproduce the EXACT shapes (2-space scenario-tag
indentation; a real tag after a closed docstring) the design's own
validation table inspected.

RED-for-right-reason (Mandate-7 / ADR-025): every production symbol imported
below (``feature_tagged_test_files``, ``resolve_test_file_attribution``,
``discover_at_kind_for_slice``, ``AtKindResolved``,
``run_contract_gate._node_belongs_to_slice``) already exists and is called
exactly as production callers call it today -- the RED here is a genuine
behavioral gap (a semantic ``AssertionError`` on the false-positive
attribution), never an import/collection error. R1, R2 pin the SIBLING
branches the fix must NOT flatten (Critical Rule: pin the correct behaviour
of neighbouring branches) and are expected GREEN both before and after the
fix -- R3-R6 are the active-RED assertions this slice makes GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.feature_at_files import (
    AtKindResolved,
    discover_at_kind_for_slice,
    feature_tagged_test_files,
    resolve_test_file_attribution,
)
from des.cli.run_contract_gate import _node_belongs_to_slice


_REPO_ROOT = Path(__file__).resolve().parents[4]
_GATE_ARMED_FEATURE_ID = "gate-armed-state-derivation"
_REAL_AT_FILE = (
    _REPO_ROOT / "tests" / "des" / "acceptance" / "test_verify_gate_armed_state.py"
)
_CITING_SHARED_MULTI_SLICE = (
    _REPO_ROOT
    / "tests"
    / "des"
    / "unit"
    / "application"
    / "test_shared_multi_slice_at_file_attribution.py"
)
_CITING_SLICE_ID_GRAMMAR = (
    _REPO_ROOT / "tests" / "bugs" / "des" / "test_slice_id_grammar_ssot.py"
)


def _require_fixture_file(path: Path) -> None:
    """Fail with a clear message if a real fixture file has moved/vanished --
    never let a silent empty-window read masquerade as a passing assertion
    (the vacuous-check trap: a missing file also returns ``slice_ids == ()``,
    which would make the RED assertion pass for the WRONG reason)."""
    assert path.is_file(), (
        f"expected fixture file {path} to exist in this repo -- if it moved "
        "or was renamed, update this AT's path constant rather than let the "
        "assertion below pass vacuously on a missing/unreadable file"
    )


# ---------------------------------------------------------------------------
# R3 (c) -- the 6 quoted indentation-4 lines inside a docstring exceeding the
# 20-line head window must disappear as false positives.
# ---------------------------------------------------------------------------


def test_shared_multi_slice_file_citing_tags_in_docstring_resolves_no_slice_ids() -> (
    None
):
    """# covers: R3

    test_shared_multi_slice_at_file_attribution.py quotes a real 6-slice tag
    block (slice-02..slice-07) verbatim INSIDE its own module docstring as an
    RCA illustration, at indentation 4, past line 20 of the file -- these
    lines are STRING token content, never a declared attribution.
    """
    _require_fixture_file(_CITING_SHARED_MULTI_SLICE)

    attribution = resolve_test_file_attribution(_CITING_SHARED_MULTI_SLICE)

    assert attribution.slice_ids == (), (
        f"{_CITING_SHARED_MULTI_SLICE.name} only CITES a 6-slice tag block "
        "as a quoted RCA example inside its own docstring -- it never "
        f"DECLARES any of them. Expected slice_ids == (), got "
        f"{attribution.slice_ids!r} (the pre-fix raw-substring scan over the "
        "head window reads all 6 quoted lines as real declarations)."
    )


# ---------------------------------------------------------------------------
# R4 (d) -- the prose citation of @slice-04a at column 0 inside a docstring
# must disappear; the file's own real line-1 @feature- declaration must stay
# attributed (Pillar 2 sibling-branch pin).
# ---------------------------------------------------------------------------


def test_slice_id_grammar_ssot_file_prose_citation_resolves_no_slice_ids() -> None:
    """# covers: R4

    test_slice_id_grammar_ssot.py mentions ``@slice-04a`` in a sentence at
    column 0, inside its own module docstring -- a citation, not a
    declaration. The file's real line-1 ``# @feature-...`` comment tag must
    stay attributed (sibling branch, must not regress).
    """
    _require_fixture_file(_CITING_SLICE_ID_GRAMMAR)

    attribution = resolve_test_file_attribution(_CITING_SLICE_ID_GRAMMAR)

    assert attribution.slice_ids == (), (
        f"{_CITING_SLICE_ID_GRAMMAR.name} only CITES @slice-04a in a prose "
        "sentence inside its own docstring -- it never DECLARES a slice "
        f"attribution. Expected slice_ids == (), got "
        f"{attribution.slice_ids!r} (the pre-fix raw-substring scan reads "
        "the column-0 prose mention as a real declaration)."
    )

    real_feature_id = "fix-slice-id-grammar-drift-ssot"
    candidates = feature_tagged_test_files(_REPO_ROOT, real_feature_id)
    assert _CITING_SLICE_ID_GRAMMAR in candidates, (
        f"{_CITING_SLICE_ID_GRAMMAR.name}'s own real line-1 "
        f"`# @feature-{real_feature_id}` declaration must stay attributed "
        "after the fix -- the fix narrows candidacy of the CITED slice "
        "sub-tag only, it must never regress the file's own genuine "
        f"feature attribution; got candidates without it (len={len(candidates)})"
    )


# ---------------------------------------------------------------------------
# R5 (e) -- discover_at_kind_for_slice resolves the real AT file for
# gate-armed-state-derivation slice-07, no longer ambiguous against the
# citing file.
# ---------------------------------------------------------------------------


def test_discover_at_kind_resolves_slice_07_for_gate_armed_state_derivation() -> None:
    """# covers: R5

    Today ``discover_at_kind_for_slice`` reports ``AtKindAmbiguous`` for
    ``gate-armed-state-derivation``/``slice-07`` because the citing file
    (quoting ``@feature-gate-armed-state-derivation`` / ``@slice-02``..
    ``@slice-07`` verbatim in its RCA docstring, see R3) false-positively
    joins the real AT file as a second candidate.
    """
    _require_fixture_file(_REAL_AT_FILE)
    _require_fixture_file(_CITING_SHARED_MULTI_SLICE)

    result = discover_at_kind_for_slice(_REPO_ROOT, _GATE_ARMED_FEATURE_ID, "slice-07")

    assert isinstance(result, AtKindResolved), (
        "expected AtKindResolved once the citing file "
        f"{_CITING_SHARED_MULTI_SLICE.name!r} is no longer a false-positive "
        f"candidate for slice-07 of {_GATE_ARMED_FEATURE_ID!r}; got "
        f"{result!r} -- AtKindAmbiguous means the citing file's quoted tag "
        "block is still counted as a second candidate"
    )
    assert result.regression_test_file == _REAL_AT_FILE, (
        "the resolved AT file must be the real, declared AT "
        f"({_REAL_AT_FILE}), not the citing file; got "
        f"{result.regression_test_file}"
    )


# ---------------------------------------------------------------------------
# R6 (f) -- run_contract_gate._node_belongs_to_slice stops returning True for
# both citing files. Driven directly via resolve_test_file_attribution's
# composed consumer, since _node_belongs_to_slice carries no isolated test
# seam of its own (per dispatch instruction).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "citing_file,entering_slice",
    [
        pytest.param(
            _CITING_SHARED_MULTI_SLICE,
            "slice-07",
            id="shared-multi-slice-quoted-block",
        ),
        pytest.param(
            _CITING_SLICE_ID_GRAMMAR,
            "slice-04a",
            id="prose-citation-column-0",
        ),
    ],
)
def test_node_belongs_to_slice_stops_false_positive_for_citing_files(
    citing_file: Path, entering_slice: str
) -> None:
    """# covers: R6

    ``_node_belongs_to_slice`` composes ``is_pytest_collectible`` +
    ``resolve_test_file_attribution(path).slice_ids`` -- once R3/R4 close the
    false-positive ``slice_ids``, this consumer stops reporting the citing
    file as in-scope for any entering slice, with zero code change to
    ``_node_belongs_to_slice`` itself.
    """
    _require_fixture_file(citing_file)
    node_id = f"{citing_file.relative_to(_REPO_ROOT)}::test_placeholder"

    belongs = _node_belongs_to_slice(_REPO_ROOT, node_id, entering_slice)

    assert belongs is False, (
        f"{citing_file.name} must no longer be reported in-scope for "
        f"{entering_slice!r} -- it only CITES the tag as a quoted example, "
        f"it never DECLARES it; got belongs={belongs!r}"
    )


# ---------------------------------------------------------------------------
# R1 (a) -- Gherkin scenario tags stay attributed regardless of indentation
# (the real 62-file / 108-line population uses 2-space indentation); a
# comment DISCUSSING a tag in prose is the CITATION construct for this
# format and must not be read as a declaration (symmetric negative).
# ---------------------------------------------------------------------------


def _write_feature_file(tmp_path: Path, feature_id: str, body_lines: list[str]) -> Path:
    path = tmp_path / "acceptance" / "demo.feature"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{feature_id}\n" + "\n".join(body_lines) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "indent",
    ["", "  "],
    ids=["column-0-tag", "two-space-indented-tag-real-population-shape"],
)
def test_gherkin_scenario_tag_stays_attributed_regardless_of_indentation(
    tmp_path: Path, indent: str
) -> None:
    """# covers: R1

    Invariance pin (Pillar 2 sibling-branch rule): the real 62-.feature-file
    / 108-line population authors scenario tags at 2-space indentation
    (``  @slice-01``); a file-level tag sits at column 0. Both shapes are
    DECLARATIONS under the per-format Gherkin grammar (the whole stripped
    line is one or more ``@``-tokens, indentation-independent) and must stay
    attributed both BEFORE and AFTER the fix -- this is the branch the fix
    must NOT flatten (must not become a false negative).
    """
    feature_id = "demo-two-space-indent-regression"
    feature_file = _write_feature_file(
        tmp_path,
        feature_id,
        [
            "Feature: Demo",
            "",
            f"{indent}@slice-01",
            "  Scenario: something",
            "    Given a thing",
        ],
    )

    candidates = feature_tagged_test_files(tmp_path, feature_id)
    assert feature_file in candidates, (
        f"a Gherkin scenario tag at indent={indent!r} must stay a declared "
        f"attribution for {feature_id!r}; got candidates={candidates!r}"
    )

    attribution = resolve_test_file_attribution(feature_file)
    assert attribution.slice_ids == ("slice-01",), (
        f"a Gherkin scenario tag at indent={indent!r} must resolve "
        f"slice_ids == ('slice-01',); got {attribution.slice_ids!r}"
    )


def test_gherkin_comment_discussing_a_tag_is_not_a_declaration(tmp_path: Path) -> None:
    """# covers: R1

    Symmetric negative: a Gherkin ``#``-comment line that merely DISCUSSES a
    tag choice in prose (never a pure tag line) must not be read as a
    declared attribution -- the CITATION construct for this format.
    """
    feature_id = "demo-gherkin-prose-citation"
    feature_file = _write_feature_file(
        tmp_path,
        feature_id,
        [
            "Feature: Demo",
            "",
            "  # we picked @slice-09 here after discussing the split",
            "  Scenario: something",
            "    Given a thing",
        ],
    )

    attribution = resolve_test_file_attribution(feature_file)

    assert attribution.slice_ids == (), (
        "a Gherkin comment DISCUSSING a tag in prose must never be read as "
        f"a declared slice attribution; got slice_ids={attribution.slice_ids!r}"
    )


# ---------------------------------------------------------------------------
# R2 (b) -- a real declared tag AFTER a closed module docstring stays
# attributed (no scan-window restriction regresses this).
# ---------------------------------------------------------------------------


def _write_pytest_head_tagged_after_docstring(
    tmp_path: Path, feature_id: str, slice_id: str
) -> Path:
    path = tmp_path / "test_tags_after_docstring.py"
    path.write_text(
        '"""Short module docstring, closes on the same line."""\n'
        f"# @feature-{feature_id}\n"
        f"# @{slice_id}\n"
        "def test_x():\n    assert True\n",
        encoding="utf-8",
    )
    return path


def test_pytest_file_tagged_after_its_docstring_stays_attributed(
    tmp_path: Path,
) -> None:
    """# covers: R2

    Invariance pin: a file's REAL declared tag may sit AFTER its module
    docstring (not only before it) -- the discriminant's ``.py`` tokenize
    arm walks the WHOLE head window in token order, so a ``COMMENT`` token
    following a CLOSED ``STRING`` token is found identically to one
    preceding it. No scan window is restricted by the fix.
    """
    feature_id = "demo-tag-after-docstring"
    test_file = _write_pytest_head_tagged_after_docstring(
        tmp_path, feature_id, "slice-03"
    )

    candidates = feature_tagged_test_files(tmp_path, feature_id)
    assert test_file in candidates, (
        "a real declared tag AFTER the module docstring must stay "
        f"attributed to {feature_id!r}; got candidates={candidates!r}"
    )

    attribution = resolve_test_file_attribution(test_file)
    assert attribution.slice_ids == ("slice-03",), (
        "a real declared @slice-NN tag after the docstring must resolve "
        f"slice_ids == ('slice-03',); got {attribution.slice_ids!r}"
    )


# ---------------------------------------------------------------------------
# R7 (g) -- the module docstring lists all 8 real consumers (doc correction,
# non-code assertion: the oracle IS the literal consumer name text since a
# behavioral test cannot sensibly cover prose).
# ---------------------------------------------------------------------------


_REAL_CONSUMERS = (
    "subagent_stop_service",
    "slice_at_completeness",
    "carpaccio_format",
    "verify_spec_coverage",
    "carpaccio_slice_gate",
    "verify_deliver_entry_contract",
    "carpaccio_precheck",
    "run_contract_gate",
)


#: The docstring already mentions ``carpaccio_format`` INCIDENTALLY, as its
#: OWN pre-fix history ("It previously lived in ``des.cli.carpaccio_format``")
#: -- never as a listed consumer. A bare substring check would pass on this
#: name for the WRONG reason today (vacuous per `check:unfired-is-not-
#: evidence` -- falsified by actually running this test before trusting it).
#: Stripping the historical sentence before the substring check closes that
#: false-pass without dictating the crafter's exact consumer-listing wording.
_HISTORICAL_SELF_MENTION = "previously lived in ``des.cli.carpaccio_format``"


@pytest.mark.parametrize("consumer_name", _REAL_CONSUMERS)
def test_module_docstring_names_every_real_consumer(consumer_name: str) -> None:
    """# covers: R7

    Non-code, doc-correction assertion (dispatch-named exception: prose
    cannot sensibly be covered by a behavioral oracle, so this pins the
    literal consumer-name text in the module's own docstring instead). Today
    the docstring (``feature_at_files.py`` lines 1-17) names only 4 of the
    file's 8 real consumers -- the C4 Container diagram in this feature's
    DESIGN names all 8.
    """
    from des.application import feature_at_files

    docstring = feature_at_files.__doc__ or ""
    docstring_excluding_historical_self_mention = docstring.replace(
        _HISTORICAL_SELF_MENTION, ""
    )

    assert consumer_name in docstring_excluding_historical_self_mention, (
        f"feature_at_files.py's module docstring must name its real "
        f"consumer {consumer_name!r} as a CONSUMER (today it names only 4 "
        "of the 8 real consumers per ADR-001 / the C4 Container diagram; "
        "carpaccio_format's own incidental historical self-mention does "
        f"not count); docstring={docstring!r}"
    )
