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

from des.domain.des_marker_parser import DesMarkerParser, DesMarkers


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
