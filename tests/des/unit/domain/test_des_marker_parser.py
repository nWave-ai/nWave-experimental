"""Tests for DesMarkerParser DES-PROJECT-ROOT marker support.

Outcome anchor: DISCUSS "orchestrator dispatching crafter on a worktree sees
correct audit-trail validation, not stale-master false-positive halts."

The parser exposes a new field `project_root` which carries the worktree-rooted
project path so hooks can resolve execution-log against the correct repo when
the orchestrator's CWD differs from the worktree (Rex RCA Option A).

CONTRACT_SHAPE: pure-function
Universe: parsed-context dict (return value of DesMarkerParser.parse).
"""

from __future__ import annotations

import pytest

from des.domain.des_marker_parser import (
    DesMarkerParser,
    DesMarkers,
    classify_atdd_pure_dispatch,
)


class TestProjectRootMarkerParsing:
    """Parser recognises DES-PROJECT-ROOT and emits parsed field."""

    def test_extracts_project_root_when_marker_present(self):
        """Marker value MUST surface in DesMarkers.project_root."""
        parser = DesMarkerParser()
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-PROJECT-ID : my-feat -->\n"
            "<!-- DES-STEP-ID : 01-01 -->\n"
            "<!-- DES-PROJECT-ROOT : /worktrees/my-feat -->\n"
            "Execute step"
        )

        result = parser.parse(prompt)

        assert result.project_root == "/worktrees/my-feat"

    def test_project_root_is_none_when_marker_absent(self):
        """Backward compat: when marker absent, project_root is None."""
        parser = DesMarkerParser()
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-PROJECT-ID : my-feat -->\n"
            "<!-- DES-STEP-ID : 01-01 -->\n"
            "Execute step"
        )

        result = parser.parse(prompt)

        assert result.project_root is None

    @pytest.mark.parametrize(
        "marker_line,expected",
        [
            ("<!--DES-PROJECT-ROOT:/abs/path-->", "/abs/path"),
            ("<!-- DES-PROJECT-ROOT:/abs/path -->", "/abs/path"),
            ("<!--   DES-PROJECT-ROOT   :   /abs/path   -->", "/abs/path"),
        ],
    )
    def test_parser_handles_varied_whitespace_around_marker(
        self, marker_line, expected
    ):
        """Same whitespace tolerance as other DES markers."""
        parser = DesMarkerParser()
        prompt = f"<!-- DES-VALIDATION : required -->\n{marker_line}\n"

        result = parser.parse(prompt)

        assert result.project_root == expected

    def test_des_markers_dataclass_frozen_includes_project_root(self):
        """Frozen invariant preserved with new field."""
        markers = DesMarkers(
            is_des_task=True,
            is_orchestrator_mode=False,
            project_id="x",
            step_id="01-01",
            project_root="/path",
        )
        with pytest.raises(AttributeError):
            markers.project_root = "/other"  # type: ignore[misc]


class TestSliceMarkerAcceptsCoupledSplitLetterSuffix:
    """DES-SLICE well-formedness must agree with carpaccio's `_SLICE_ID_RE`.

    Bug (confirmed RCA, not re-investigated here): `_SLICE_SHAPE` in
    `des_marker_parser.py` was anchored to `slice-\\d+` (digits-and-nothing-
    else), while `carpaccio_format.py:_SLICE_ID_RE` accepts an optional
    single lowercase-letter suffix (`^slice-\\d+(?:[a-z])?$`) -- the
    documented @coupled-SPLIT sub-slice convention (e.g. `slice-04a`,
    `slice-05b`). A feature authoring an @coupled-split slice passes the
    carpaccio gate but its dispatch is then rejected as "missing a
    well-formed des-slice marker" -- an SSOT inconsistency between the two
    parsers of the SAME slice-id grammar.

    Today (RED): `slice_id` for a coupled-split value comes back None
    (rejected) instead of the letter-suffixed value -- a genuine semantic
    AssertionError, not an import/setup failure.

    The fix (owned by DELIVER, not by this test): widen `_SLICE_SHAPE` to
    `slice-\\d+[a-z]?`, mirroring carpaccio's `[a-z]?` -- exactly one
    optional lowercase letter, nothing looser (pins below guard against
    over-widening: two letters, uppercase, and non-dash malformed shapes
    must stay rejected).

    CONTRACT_SHAPE: pure-function
    Universe: parsed-context dict (return value of DesMarkerParser.parse) --
    specifically `DesMarkers.slice_id`.
    """

    @pytest.mark.parametrize(
        "slice_token",
        ["slice-04a", "slice-05b"],
        ids=["coupled-split-04a", "coupled-split-05b"],
    )
    def test_coupled_split_letter_suffix_slice_is_well_formed(self, slice_token):
        """RED today: a @coupled-SPLIT sub-slice id (one lowercase letter
        suffix) must parse to a well-formed dispatch scope, matching
        carpaccio's `_SLICE_ID_RE`. Currently returns None -- the bug.
        """
        parser = DesMarkerParser()
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-SLICE : {slice_token} -->\n"
            "Execute step"
        )

        result = parser.parse(prompt)

        assert result.slice_id == slice_token, (
            f"expected well-formed slice scope {slice_token!r}, got "
            f"{result.slice_id!r} -- _SLICE_SHAPE must accept the "
            "@coupled-split single-lowercase-letter suffix, mirroring "
            "carpaccio_format._SLICE_ID_RE (`^slice-\\d+(?:[a-z])?$`)"
        )

    @pytest.mark.parametrize(
        "slice_token",
        ["slice-04", "feature-end"],
        ids=["plain-slice", "feature-end-literal"],
    )
    def test_pre_existing_well_formed_scopes_stay_well_formed(self, slice_token):
        """Passing pin: the fix must not disturb the two scopes that were
        already well-formed before the fix -- a plain `slice-NN` value and
        the `feature-end` literal.
        """
        parser = DesMarkerParser()
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            f"<!-- DES-SLICE : {slice_token} -->\n"
            "Execute step"
        )

        result = parser.parse(prompt)

        assert result.slice_id == slice_token

    @pytest.mark.parametrize(
        "slice_token",
        ["slice1", "slice-3-->", "slice-04ab", "slice-04A"],
        ids=[
            "no-dash",
            "garbled-tail",
            "two-letter-suffix",
            "uppercase-suffix",
        ],
    )
    def test_rejects_malformed_slice_scopes_outside_the_closed_grammar(
        self, slice_token
    ):
        """Negative AT (GS-8): malformed shapes must stay rejected (None) --
        pins that the fix accepts EXACTLY one optional lowercase letter and
        nothing looser than carpaccio's `[a-z]?`. `slice-04ab` (two letters)
        and `slice-04A` (uppercase) are the over-widening guards; `slice1`
        (no dash) and `slice-3-->` (garbled tail) are the pre-existing
        malformed-shape regression pins.
        """
        parser = DesMarkerParser()
        # slice_token may itself contain `-->`; build the marker comment so the
        # garbled-tail case still parses as a single marker value (the
        # pattern captures `\S+` up to the marker's own closing `-->`, so a
        # `-->` embedded in the token truncates the match -- exercising the
        # real garbled-input path rather than a well-formed one).
        prompt = (
            "<!-- DES-VALIDATION : required -->\n"
            f"<!-- DES-SLICE : {slice_token} -->\n"
            "Execute step"
        )

        result = parser.parse(prompt)

        assert result.slice_id is None, (
            f"expected {slice_token!r} to be rejected as malformed, got "
            f"slice_id={result.slice_id!r}"
        )


# ---------------------------------------------------------------------------
# feature-end-examine-phase / slice-01 -- the closed-world (phase, scope) XOR
# table for a FEATURE-SCOPE examine.
#
# Feature: docs/feature/feature-end-examine-phase/feature-delta.md.
# `/nw-deliver`'s feature-end cycle prescribes an EXAMINE at step 2 of 5 -- an
# independent, execution-observing walk of the FINISHED feature -- but no DES
# dispatch phase word names it, so it cannot be dispatched at all (measured
# 2026-07-18: six refused dispatches across three distinct legal paths).
#
# PHASE-WORD: `FEATURE_END_EXAMINE` -- the new, DISTINCT `DES-PHASE` token this
# slice adds to the closed phase vocabulary. Distinct per DESIGN Decision D1
# (feature-delta.md): reusing the canonical `EXAMINE` / `C_REVIEWER_AUDIT` word
# would make every PER-SLICE examine dispatch ILLEGAL the moment that word also
# became a `FEATURE_END_PHASES` member -- exactly what the anti-regression test
# below guards against.
#
# The invariant under test (des_marker_parser.py:454-456, UNCHANGED by this
# feature): `phase in FEATURE_END_PHASES  <=>  scope == 'feature-end'`.
# `FEATURE_END_EXAMINE` is expected to become a new `FEATURE_END_PHASES` member
# (src/des/domain/atdd_pure_phases.py:318) once implemented; the XOR rule itself
# is reused verbatim, never weakened.
#
# Driving surface: the REAL `DesMarkerParser().parse(prompt)` ->
# `classify_atdd_pure_dispatch(markers)` pipeline -- the same surface the
# PreToolUse dispatch guard applies. A prompt fixture with an HTML-comment
# `DES-PHASE` marker exercises BOTH the marker-vocabulary lookup
# (`_NORMALISED_PHASE_BY_TOKEN`, derived from the live `ATDDPurePhase` enum) and
# the XOR classification in one pass -- never a hand-built `DesMarkers` that
# could paper over a missing vocabulary entry.
#
# CONTRACT_SHAPE: pure-function. Universe: the `classify_atdd_pure_dispatch`
# return value (`'absent' | 'valid' | 'defective'`) plus the parsed
# `atdd_pure_phase` field (the mechanism-level witness that the word was
# actually RECOGNISED, not merely that the outcome happened to match).
#
# Placement note: these are MODULE-LEVEL functions, deliberately kept in THIS
# module (the Reuse Analysis EXTEND decision) so the closed-world XOR table
# stays readable as ONE artifact alongside the sibling marker-grammar tables
# above.
# ---------------------------------------------------------------------------

_XOR_PROMPT_TEMPLATE = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-MODE : atdd_pure -->\n"
    "<!-- DES-PHASE : {phase} -->\n"
    "<!-- DES-SLICE : {slice} -->\n"
    "Execute step"
)

# The new phase word this slice introduces (DESIGN Decision D1).
FEATURE_END_EXAMINE_PHASE_WORD = "FEATURE_END_EXAMINE"

# The marker-vocabulary word for the CANONICAL per-slice examine slot.
# `ATDDPurePhase.EXAMINE` is a value alias of `ATDDPurePhase.C_REVIEWER_AUDIT`
# (atdd_pure_phases.py:97), so `C_REVIEWER_AUDIT` IS the per-slice EXAMINE word
# a dispatch carries.
_CANONICAL_PER_SLICE_EXAMINE_WORD = "C_REVIEWER_AUDIT"

_PHASE_NOT_IN_VOCABULARY = (
    "DES-PHASE : {word} did not parse into DesMarkers.atdd_pure_phase -- the "
    "word is not yet a recognised ATDDPurePhase member (add it to the enum, "
    "src/des/domain/atdd_pure_phases.py:54). got atdd_pure_phase={got!r}"
)


def test_feature_end_examine_phase_with_feature_end_scope_is_valid() -> None:
    """POSITIVE (R1): the new feature-scope examine phase word declared together
    with scope `feature-end` reaches the examiner -- classifies `valid`.

    RED today: `FEATURE_END_EXAMINE` is out-of-vocabulary
    (`_NORMALISED_PHASE_BY_TOKEN` has no entry for it), so
    `DesMarkers.atdd_pure_phase` parses to `None` and
    `classify_atdd_pure_dispatch` returns `'defective'` via the
    `atdd_pure_phase is None` branch -- not `'valid'`.
    """
    # covers: R1
    parser = DesMarkerParser()
    prompt = _XOR_PROMPT_TEMPLATE.format(
        phase=FEATURE_END_EXAMINE_PHASE_WORD, slice="feature-end"
    )

    markers = parser.parse(prompt)

    assert markers.atdd_pure_phase == FEATURE_END_EXAMINE_PHASE_WORD, (
        _PHASE_NOT_IN_VOCABULARY.format(
            word=FEATURE_END_EXAMINE_PHASE_WORD, got=markers.atdd_pure_phase
        )
    )
    classification = classify_atdd_pure_dispatch(markers)
    assert classification == "valid", (
        f"DES-PHASE : {FEATURE_END_EXAMINE_PHASE_WORD} + DES-SLICE : "
        f"feature-end must classify 'valid' -- got {classification!r}. Fix: "
        f"add {FEATURE_END_EXAMINE_PHASE_WORD} to FEATURE_END_PHASES "
        "(src/des/domain/atdd_pure_phases.py:318) so the XOR "
        "(phase in FEATURE_END_PHASES <=> scope == 'feature-end') resolves "
        "coherently for this combination."
    )


def test_canonical_per_slice_examine_still_valid_at_slice_scope() -> None:
    """ANTI-REGRESSION (R2): the canonical per-slice examine slot
    (`DES-PHASE : C_REVIEWER_AUDIT`, the marker-vocabulary word for
    `ATDDPurePhase.EXAMINE` / `ATDDPurePhase.C_REVIEWER_AUDIT`) at a `slice-NN`
    scope STILL classifies `valid`.

    THE TRAP THIS GUARDS: if the implementation widens `FEATURE_END_PHASES` by
    adding `C_REVIEWER_AUDIT` (or by reusing the canonical `EXAMINE` word)
    instead of the DISTINCT `FEATURE_END_EXAMINE` word, every per-slice examine
    dispatch across all three live instances becomes `defective`. This
    assertion must fail LOUDLY the moment that mistake is made.

    GREEN from the start, by design: a regression guard, not a repro of an open
    defect -- its value is that it goes RED the instant someone widens the
    wrong side of the XOR.
    """
    # covers: R2
    parser = DesMarkerParser()
    prompt = _XOR_PROMPT_TEMPLATE.format(
        phase=_CANONICAL_PER_SLICE_EXAMINE_WORD, slice="slice-04"
    )

    markers = parser.parse(prompt)
    classification = classify_atdd_pure_dispatch(markers)

    assert classification == "valid", (
        f"DES-PHASE : {_CANONICAL_PER_SLICE_EXAMINE_WORD} + DES-SLICE : "
        f"slice-04 must stay 'valid' -- got {classification!r}. This is the "
        "per-slice EXAMINE slot (ADR-027); adding C_REVIEWER_AUDIT (or the "
        "EXAMINE alias) to FEATURE_END_PHASES would make EVERY per-slice "
        "examine dispatch defective -- use a DISTINCT feature-end-examine "
        "phase word instead (DESIGN Decision D1, feature-delta.md)."
    )


def test_feature_end_examine_phase_rejects_a_per_slice_scope() -> None:
    """NEGATIVE (R3): the new feature-scope examine phase word declared together
    with a `slice-NN` scope classifies `defective` -- the XOR still bites in
    the other direction.

    RED today for the RIGHT reason. Today's `'defective'` outcome is VACUOUS:
    `FEATURE_END_EXAMINE` is unrecognised, so `atdd_pure_phase` is `None` and
    ANY scope yields `'defective'` via the `atdd_pure_phase is None`
    short-circuit, never the XOR itself. The mechanism assertion below pins
    that the word IS recognised (post-fix, `atdd_pure_phase` must equal the new
    word), so the outcome assertion is proven by the REAL XOR (a feature-end
    phase at a non-feature-end scope), not by an unrelated out-of-vocabulary
    short-circuit.
    """
    # covers: R3
    parser = DesMarkerParser()
    prompt = _XOR_PROMPT_TEMPLATE.format(
        phase=FEATURE_END_EXAMINE_PHASE_WORD, slice="slice-04"
    )

    markers = parser.parse(prompt)

    assert markers.atdd_pure_phase == FEATURE_END_EXAMINE_PHASE_WORD, (
        _PHASE_NOT_IN_VOCABULARY.format(
            word=FEATURE_END_EXAMINE_PHASE_WORD, got=markers.atdd_pure_phase
        )
    )
    classification = classify_atdd_pure_dispatch(markers)
    assert classification == "defective", (
        f"DES-PHASE : {FEATURE_END_EXAMINE_PHASE_WORD} + DES-SLICE : slice-04 "
        f"must classify 'defective' -- got {classification!r}. "
        f"{FEATURE_END_EXAMINE_PHASE_WORD} is a FEATURE_END_PHASES member, so "
        "its only coherent scope is the 'feature-end' literal (ADR-028 D6, "
        "Option A) -- a slice-NN scope must still trip the XOR."
    )
