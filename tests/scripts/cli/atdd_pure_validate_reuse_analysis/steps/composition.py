"""Composition root for the Reuse Analysis gate acceptance slices.

F-DESIGN-REUSE-FIRST-GATE (DDD-1..DDD-11), Mandate-12 + Pillar 3. Wires the
PRODUCTION validate-feature-delta CLI entry point
(``des.cli.validate_feature_delta.main``) against a tmp_path
feature-delta fixture. Business logic lives here as the single source of
truth; step bodies delegate to ``ReuseAnalysisComposition`` methods and never
inline logic.

Layer 3 (subprocess/FS acceptance): the validator CLI is the driving port;
the only driven port is the real filesystem (tmp_path). No PBT machinery
(Mandate 9/11) -- the table shapes form a finite enumerable closed set.

Pure-function contract (DDD: ``validate_reuse_analysis_content`` is
return-only): the CLI reads the feature-delta and returns a verdict (exit
code + stdout); it performs NO filesystem mutation. ``capture_universe``
snapshots the feature-delta so the When-step state-delta guard proves the
read-only contract (Mandate 8).

Structured-verdict contract (pins the CLI machine output -- the contract the
crafter MUST implement, not a guess):

    The ``--require-reuse-analysis`` mode is invoked with ``--format=json``.
    In that mode the CLI emits exactly ONE JSON object (single line) to
    stdout carrying a stable ``"verdict"`` field whose value is one of the
    closed token set (DDD-2)::

        structurally-accepted | no-overlap-declared | methodology-exempt
        | missing-reuse-analysis | malformed-reuse-analysis
        | unjustified-create-new | malformed-wave-heading
        | ungrounded-reuse-analysis

    The verdict mapping below reads that ``verdict`` token -- a STRUCTURED
    contract -- never free-text stdout substrings. An unknown or absent token
    raises rather than silently defaulting.

RED scaffold note (Mandate 7): on master ``validate_feature_delta`` carries a
``validate_reuse_analysis_content`` RED scaffold that raises ``AssertionError``
and a ``_run_require_reuse_analysis`` runner that calls it. The import
resolves cleanly (the symbols exist as scaffolds); invoking the CLI in
``--require-reuse-analysis`` mode propagates the scaffold ``AssertionError``.
Every ``--require-reuse-analysis`` scenario therefore FAILS with a semantic
``AssertionError`` (MISSING_FUNCTIONALITY RED, not a collection error) and
PASSES once the DELIVER crafter implements the pure core.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the validate-feature-delta CLI. The module exists
# on master; F-DESIGN-REUSE-FIRST-GATE EXTENDS its `main` with the
# --require-reuse-analysis flag and a real pure core (DDD-1).
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import CheckMode, FeatureId, ReuseTableShape, ReuseVerdict


# The closed `verdict` token set the CLI emits under --require-reuse-analysis
# --format=json (DDD-2). This mapping IS the structured contract the crafter
# must implement -- the AT reads the token, never a free-text stdout
# substring. An off-contract or absent token raises (see
# `ValidationResult.verdict`) so a wrong token fails loudly.
_VERDICT_TOKEN: dict[str, ReuseVerdict] = {
    "structurally-accepted": ReuseVerdict.STRUCTURALLY_ACCEPTED,
    "no-overlap-declared": ReuseVerdict.NO_OVERLAP_DECLARED,
    "methodology-exempt": ReuseVerdict.METHODOLOGY_EXEMPT,
    "missing-reuse-analysis": ReuseVerdict.MISSING_REUSE_ANALYSIS,
    "malformed-reuse-analysis": ReuseVerdict.MALFORMED_REUSE_ANALYSIS,
    "unjustified-create-new": ReuseVerdict.UNJUSTIFIED_CREATE_NEW,
    "malformed-wave-heading": ReuseVerdict.MALFORMED_WAVE_HEADING,
    # F-fix-reuse-analysis-content-grounding (WS-9): a row's `Existing
    # Component | File` citation does not resolve through the CodeFactPort
    # chain (a phantom citation) -- caught regardless of Decision (EXTEND or
    # CREATE_NEW), since even a CREATE_NEW row names the nearest existing
    # component it was compared against and rejected.
    "ungrounded-reuse-analysis": ReuseVerdict.UNGROUNDED_REUSE_ANALYSIS,
}

# The canonical Reuse Analysis heading + five columns (DDD-8 / R1). Mirrors
# REUSE_ANALYSIS_HEADING / REUSE_ANALYSIS_COLUMNS in validate_feature_delta.py.
_REUSE_HEADING = "## Reuse Analysis"
_REUSE_COLUMNS = (
    "Existing Component",
    "File",
    "Overlap",
    "Decision",
    "Justification",
)


@dataclass
class ValidationResult:
    """Observable outcome of one validate-feature-delta CLI invocation.

    ``mode`` records which invocation produced this result -- the two modes
    have two DIFFERENT observable contracts:

    - ``CheckMode.PLAIN`` -- the pre-existing heading-form CLI. Contract is
      exit code only (0 valid / non-zero malformed); plain text, not JSON.
    - ``CheckMode.REQUIRE_REUSE_ANALYSIS`` -- the ``--format=json`` mode.
      Contract is a single JSON object with a stable ``verdict`` token.
    """

    mode: CheckMode
    exit_code: int
    output: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict`` field of the single JSON object the CLI emits.

        Returns the ``verdict`` field of the one JSON object on stdout, or
        ``None`` when stdout carries no parseable JSON object with a
        ``verdict`` key (the master state -- the scaffold runner raises
        before printing, so no JSON line exists).
        """
        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "verdict" in obj:
                    return str(obj["verdict"])
        return None

    @property
    def verdict(self) -> ReuseVerdict:
        """Map the CLI output onto the user-observable verdict, per mode.

        PLAIN mode -- the pre-existing heading-form contract: exit 0 ->
        STRUCTURALLY_ACCEPTED, any non-zero -> MALFORMED_WAVE_HEADING. Reads
        the EXIT CODE, the stable contract the plain CLI keeps forever.

        REQUIRE_REUSE_ANALYSIS mode -- the ``--format=json`` contract: the
        verdict is the stable ``verdict`` token of the single emitted JSON
        object. Reads a MACHINE token, never free-text substrings.

          - No ``verdict`` token at all -> UNRECOGNISED_INVOCATION: the CLI
            produced no structured output (the master/RED-scaffold state).
          - An off-contract token -> ``ValueError``, failing the test loudly.
        """
        if self.mode is CheckMode.PLAIN:
            if self.exit_code == 0:
                return ReuseVerdict.STRUCTURALLY_ACCEPTED
            return ReuseVerdict.MALFORMED_WAVE_HEADING
        token = self._verdict_token
        if token is None:
            return ReuseVerdict.UNRECOGNISED_INVOCATION
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"reuse-analysis CLI emitted an off-contract verdict token "
                f"{token!r}; expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]


@dataclass
class ReuseAnalysisComposition:
    """Production-wired composition root for the Reuse Analysis gate slices.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta is provisioned via ``provision_feature_delta`` so each
    scenario builds exactly the Reuse Analysis shape it needs; the validator
    CLI is then invoked through its argv entry point against that file.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("reuse-gate-demo"))

    # --- paths ---------------------------------------------------------------

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_dir / "feature-delta.md"

    # --- Given: repo ---------------------------------------------------------

    def create_feature(self, feature_id: FeatureId) -> None:
        """Create the feature directory skeleton."""
        self.feature_id = feature_id
        self._feature_dir.mkdir(parents=True, exist_ok=True)

    # --- Given: feature-delta + Reuse Analysis -------------------------------

    def provision_feature_delta(self, shape: ReuseTableShape) -> None:
        """Write the feature-delta with a Reuse Analysis of the given shape."""
        builder = _FEATURE_DELTA_BUILDERS[shape]
        builder(self)

    def _write(self, body: str) -> None:
        """Write the feature-delta document body."""
        self.feature_delta_path.write_text(body, encoding="utf-8")

    # --- When: run the validator ---------------------------------------------

    def run_check(self, mode: CheckMode) -> ValidationResult:
        """Invoke the production validate-feature-delta CLI via its argv entry.

        ``CheckMode.PLAIN`` invokes the heading-form-only contract (one path
        argument); ``CheckMode.REQUIRE_REUSE_ANALYSIS`` adds the
        ``--require-reuse-analysis --format=json`` flags, so the verdict is
        read from a structured ``verdict`` token.
        """
        argv = _ARGV_BY_MODE[mode](self.feature_delta_path)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return ValidationResult(
            mode=mode, exit_code=exit_code, output=buffer.getvalue()
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The validator has a pure-function contract: it reads the
        feature-delta and MUST NOT mutate it. The universe is the
        feature-delta's existence and bytes -- the state-delta guard proves
        the read-only contract.
        """
        return {
            "feature_delta.exists": self.feature_delta_path.exists(),
            "feature_delta.bytes": (
                self.feature_delta_path.read_bytes()
                if self.feature_delta_path.exists()
                else None
            ),
        }


# --- argv builders ----------------------------------------------------------
# Each builder keeps `run_check` a single typed dispatch + a single CLI call
# (Mandate-12 criterion 3: no control flow in the service method body).


def _argv_plain(path: Path) -> list[str]:
    return [str(path)]


def _argv_require_reuse_analysis(path: Path) -> list[str]:
    # --require-reuse-analysis is paired with --format=json so the verdict is
    # read from a structured `verdict` token, not free text.
    return ["--require-reuse-analysis", "--format=json", str(path)]


_ARGV_BY_MODE: dict[CheckMode, Callable[[Path], list[str]]] = {
    CheckMode.PLAIN: _argv_plain,
    CheckMode.REQUIRE_REUSE_ANALYSIS: _argv_require_reuse_analysis,
}


# --- feature-delta fixture builders -----------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).

_REUSE_HEADER_ROW = "| " + " | ".join(_REUSE_COLUMNS) + " |"
_REUSE_SEPARATOR = "|" + "|".join(["-------"] * len(_REUSE_COLUMNS)) + "|"


def _reuse_section(rows: str, *, heading: str = _REUSE_HEADING) -> str:
    """Assemble a Reuse Analysis section from a heading + table rows."""
    return f"{heading}\n\n{_REUSE_HEADER_ROW}\n{_REUSE_SEPARATOR}\n{rows}"


def _doc(*sections: str) -> str:
    """Assemble a feature-delta document body from its sections."""
    return "# Feature Delta: reuse-analysis gate fixture\n\n" + "\n\n".join(sections)


# An EXTEND row -- the structural happy path. Every cell populated.
#
# `Existing Component` cites a REAL, resolvable atom (a top-level function,
# per the AST CodeFact tier -- classes are not atoms there) so the row clears
# the F-fix-reuse-analysis-content-grounding (WS-9) content-grounding leg the
# CLI runs under `--require-reuse-analysis --format=json` (`project_root`
# is `Path.cwd()`, so `File` resolves relative to the repo root pytest is
# invoked from). A citation naming the FILE itself (not a symbol inside it)
# is a phantom citation and is correctly rejected as `ungrounded`.
_EXTEND_ROW = (
    "| validate_reuse_analysis_content | src/des/cli/validate_feature_delta.py "
    "| structural validation | EXTEND | a third validation aspect of the same "
    "artifact |"
)


def _build_well_formed(comp: ReuseAnalysisComposition) -> None:
    comp._write(_doc(_reuse_section(_EXTEND_ROW)))


def _build_section_absent(comp: ReuseAnalysisComposition) -> None:
    # A feature-delta with a valid wave heading but NO Reuse Analysis section
    # and no exemption marker.
    comp._write(
        _doc(
            "## Wave: DESIGN / [REF] Architecture\n\n"
            "Some architecture prose with no Reuse Analysis table."
        )
    )


def _build_this_feature_gold(comp: ReuseAnalysisComposition) -> None:
    # Gold test: a multi-row Reuse Analysis table shaped like this feature's
    # own (five EXTEND rows, canonical `## Reuse Analysis` heading), proving
    # multi-row content-grounding clears when every `Existing Component`
    # names a REAL, resolvable atom (a top-level function -- classes are not
    # atoms under the AST CodeFact tier) in its `File`. A `File` cell carries
    # a bare repo-relative path (no `:line,col` suffix) -- that suffix would
    # make the cited path unresolvable and the row would be (correctly)
    # rejected as `ungrounded` (F-fix-reuse-analysis-content-grounding, WS-9).
    # Markdown-prose citations (a SKILL.md step, an agent .md file) cannot
    # ground -- the AST tier parses Python only -- so this fixture cites five
    # distinct functions of the gate's own module instead of prose assets.
    rows = "\n".join(
        [
            "| validate_reuse_analysis_content | "
            "src/des/cli/validate_feature_delta.py | structural "
            "validation; pure-core + thin-shell | EXTEND | the content-grounding "
            "check was added as a mode on this same function |",
            "| _component_citation_is_grounded | "
            "src/des/cli/validate_feature_delta.py | phantom-citation "
            "resolution through the CodeFactPort chain | EXTEND | the "
            "grounding leg reuses this lookup rather than a bespoke resolver |",
            "| _parse_args | "
            "src/des/cli/validate_feature_delta.py | CLI flag "
            "parsing + mode dispatch | EXTEND | add one --require-reuse-analysis "
            "branch mirroring _run_require_slice_plan |",
            "| _classify_component_row | "
            "src/des/cli/validate_feature_delta.py | per-row Decision / "
            "Justification well-formedness classification | EXTEND | reuse "
            "the same row classifier ahead of the grounding leg |",
            "| main | "
            "src/des/cli/validate_feature_delta.py | CLI entry point "
            "dispatch | EXTEND | the --require-reuse-analysis mode is one "
            "more branch on the same entry point |",
        ]
    )
    comp._write(_doc(_reuse_section(rows)))


def _build_un_normalisable_decision(comp: ReuseAnalysisComposition) -> None:
    # A component row whose Decision cell normalises to neither EXTEND nor
    # CREATE_NEW (DDD-7) -> malformed-reuse-analysis.
    row = (
        "| some_module.py | src/some_module.py | overlap text | MAYBE_REWRITE "
        "| an ambiguous decision token |"
    )
    comp._write(_doc(_reuse_section(row)))


def _build_create_new_empty_justification(comp: ReuseAnalysisComposition) -> None:
    # A CREATE_NEW row with an empty Justification cell (DDD-3) ->
    # unjustified-create-new.
    row = "| brand_new.py | src/brand_new.py | no overlap | CREATE_NEW |  |"
    comp._write(_doc(_reuse_section(row)))


def _build_create_new_space_spelling(comp: ReuseAnalysisComposition) -> None:
    # A `CREATE NEW` (space) row -- DDD-7 normalisation collapses internal
    # whitespace to `_`, so it normalises to CREATE_NEW. With a non-empty
    # justification it is accepted -> structurally-accepted. `Existing
    # Component` cites a REAL, resolvable atom -- even a CREATE_NEW row names
    # the nearest existing component it was compared against and rejected,
    # so it must still clear content-grounding (WS-9); `brand_new.py` /
    # `src/brand_new.py` would be a phantom citation (neither the file nor
    # the "component" exist) and is correctly rejected as `ungrounded`.
    row = (
        "| validate_reuse_analysis_content | src/des/cli/validate_feature_delta.py "
        "| the nearest existing validator; insufficient overlap to extend "
        "| CREATE NEW | a real justification for the new path |"
    )
    comp._write(_doc(_reuse_section(row)))


def _build_create_new_parenthetical_qualifier(
    comp: ReuseAnalysisComposition,
) -> None:
    # A CREATE_NEW row whose Decision cell carries a trailing parenthetical
    # qualifier (DDD-7 leniency) -- the bare token is extracted, so it
    # normalises to CREATE_NEW; with a non-empty justification -> accepted.
    # `Existing Component` cites a different real, resolvable atom (the
    # CodeFactPort's own `query` method) than the sibling scenario above, to
    # prove content-grounding (WS-9) resolves across distinct files, not just
    # the gate's own module.
    row = (
        "| query | src/des/ports/code_fact_port.py | a genuine overlapping "
        "component | CREATE_NEW (companion) | a real justification for the new path |"
    )
    comp._write(_doc(_reuse_section(row)))


def _build_methodology_exempt_marker(comp: ReuseAnalysisComposition) -> None:
    # No table; a `Reuse-Analysis: methodology-exempt` marker directly under
    # the canonical heading (DDD-9) -> methodology-exempt (accepted).
    comp._write(_doc(f"{_REUSE_HEADING}\n\nReuse-Analysis: methodology-exempt"))


def _build_no_overlap_marker(comp: ReuseAnalysisComposition) -> None:
    # No table; a `Reuse-Analysis: no-overlap` marker under the canonical
    # heading (DDD-9) -> no-overlap-declared (accepted).
    comp._write(_doc(f"{_REUSE_HEADING}\n\nReuse-Analysis: no-overlap"))


def _build_duplicate_heading(comp: ReuseAnalysisComposition) -> None:
    # Two `## Reuse Analysis` headings -- the first is normative, a second
    # occurrence is malformed (DDD-11) -> malformed-reuse-analysis.
    comp._write(
        _doc(
            _reuse_section(_EXTEND_ROW),
            _reuse_section(_EXTEND_ROW),
        )
    )


def _build_phantom_component_citation(comp: ReuseAnalysisComposition) -> None:
    # An otherwise well-formed EXTEND row whose `Existing Component` names a
    # symbol absent from the cited (real) `File` -- the phantom-citation
    # regression lock for F-fix-reuse-analysis-content-grounding (WS-9):
    # ungrounded-reuse-analysis.
    row = (
        "| this_symbol_does_not_exist_anywhere | "
        "src/des/cli/validate_feature_delta.py | structural validation "
        "| EXTEND | a citation naming a component absent from the file |"
    )
    comp._write(_doc(_reuse_section(row)))


_FEATURE_DELTA_BUILDERS: dict[
    ReuseTableShape, Callable[[ReuseAnalysisComposition], None]
] = {
    ReuseTableShape.WELL_FORMED: _build_well_formed,
    ReuseTableShape.SECTION_ABSENT: _build_section_absent,
    ReuseTableShape.THIS_FEATURE_GOLD: _build_this_feature_gold,
    ReuseTableShape.UN_NORMALISABLE_DECISION: _build_un_normalisable_decision,
    ReuseTableShape.CREATE_NEW_EMPTY_JUSTIFICATION: (
        _build_create_new_empty_justification
    ),
    ReuseTableShape.CREATE_NEW_SPACE_SPELLING: _build_create_new_space_spelling,
    ReuseTableShape.CREATE_NEW_PARENTHETICAL_QUALIFIER: (
        _build_create_new_parenthetical_qualifier
    ),
    ReuseTableShape.METHODOLOGY_EXEMPT_MARKER: _build_methodology_exempt_marker,
    ReuseTableShape.NO_OVERLAP_MARKER: _build_no_overlap_marker,
    ReuseTableShape.DUPLICATE_HEADING: _build_duplicate_heading,
    ReuseTableShape.PHANTOM_COMPONENT_CITATION: _build_phantom_component_citation,
}
