"""Composition root for the design-dimension coverage CLI acceptance slice-01.

F-OSS-UPSTREAM-WAVE-GATE-PAIRS pair-1 (DESIGN-dimensions <-> DISTILL-pbt),
Mandate-12 + Pillar 3. Wires the PRODUCTION
``check_design_dimension_coverage`` CLI entry point
(``scripts.cli.check_design_dimension_coverage.main``) against a tmp_path
feature project. Business logic lives here as the single source of truth; step
bodies delegate to ``DimensionCoverageFixture`` methods and never inline logic.

Layer 3 (in-process subprocess-equivalent / FS acceptance): the CLI is the
driving port (Mandate-13 driving-port-only -- the gate is invoked through its
``main(argv)`` argv entry point, NEVER via a direct-domain import of the
parser functions). The driven ports are the real filesystem (tmp_path for the
feature-delta + the AT corpus). No PBT machinery (Mandate 9/11) -- slice-01 is
the existence-join walking skeleton, a finite enumerable closed verdict set;
the falsifier-gate forbids PBT on a closed-world finite domain. The unbounded
input-axes (arbitrary feature-delta text, arbitrary carrier-comment text) are
PBT territory at the layer-1 parser unit scope, authored by DELIVER, not at
this layer-3 AT.

Pure-function / bounded-change contract (Contract Shapes: ``main`` is
bounded-change -- writes ONLY stdout/stderr + exit code, NO filesystem
mutation). ``capture_universe`` snapshots the feature-delta + the AT-corpus
carrier files so the @then step state-delta guard proves the read-only
contract (Mandate 8, @contract-shape:unbounded-preservation).

Structured-verdict contract: the CLI emits exactly ONE single-line stdout
token::

    design_dimension_coverage feature=<id> dimensions=<n> witnessed=<m> verdict=<PASS|INDETERMINATE|MALFORMED>

The verdict mapping below reads that ``verdict=`` substring -- a STRUCTURED
machine token, never a free-text natural-language stdout substring. An unknown
or absent token raises rather than silently defaulting.

RED scaffold note (Mandate 7): the production
``scripts/cli/check_design_dimension_coverage.py`` module does not exist on
master. The crafter authors a RED scaffold (``__SCAFFOLD__ = True``; ``main``
raises ``AssertionError``) in A_GREEN_ATS so the import resolves and the
invocation raises a semantic ``AssertionError`` (MISSING_FUNCTIONALITY RED),
not a collection-time ``ModuleNotFoundError``. ``run_check`` defends the
pre-scaffold state by catching ``ModuleNotFoundError`` and returning the
``UNRECOGNISED_INVOCATION`` verdict; once the scaffold lands, the path is
``AssertionError`` -> ``UNRECOGNISED_INVOCATION`` (still RED-for-the-right
reason at the AT layer); once the implementation lands, the path is the real
stdout token -> PASS / INDETERMINATE / MALFORMED.
"""

from __future__ import annotations

import contextlib
import importlib
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    UNWITNESSED_DIMENSION_ID,
    UNWITNESSED_DIMENSION_SUMMARY,
    DimensionCoverageVerdict,
    DimensionsHeadingStyle,
    FeatureCorpusShape,
    FeatureId,
)


# Type alias for the corpus-shape builder callbacks. Declared at module top so
# the dispatch dict's type is precise and step bodies remain a single
# composition call (Mandate-12 criterion 3).
_BuilderFn = Callable[["DimensionCoverageFixture"], None]


# Production module path -- imported lazily inside ``run_check`` so the AT
# module imports cleanly even before the crafter authors the RED scaffold.
_CLI_MODULE = "scripts.cli.check_design_dimension_coverage"

# The closed ``verdict`` token set the CLI emits on the single stdout line
# (the Gate Contract machine surface). This mapping IS the structured contract
# the crafter must implement -- the AT reads the token, never a free-text
# stdout substring. An off-contract or absent token raises (see
# ``CheckResult.verdict``) so a wrong token fails loudly.
_VERDICT_TOKEN: dict[str, DimensionCoverageVerdict] = {
    "PASS": DimensionCoverageVerdict.PASS,
    "INDETERMINATE": DimensionCoverageVerdict.INDETERMINATE,
    "MALFORMED": DimensionCoverageVerdict.MALFORMED,
}

_STDOUT_TOKEN_PREFIX = "design_dimension_coverage "


@dataclass
class CheckResult:
    """Observable outcome of one check_design_dimension_coverage invocation.

    The CLI emits exactly ONE single-line stdout token; the verdict is read
    from the ``verdict=<TOKEN>`` substring of that line.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict=`` token of the single-line stdout output.

        Returns the ``verdict=<TOKEN>`` substring's TOKEN, or ``None`` when
        stdout carries no parseable single-line token (the master/RED-scaffold
        state -- the scaffold raises before printing, so no token line exists).
        """
        for line in self.stdout.splitlines():
            stripped = line.strip()
            if not stripped.startswith(_STDOUT_TOKEN_PREFIX):
                continue
            for field_token in stripped.split():
                if field_token.startswith("verdict="):
                    return field_token[len("verdict=") :]
        return None

    @property
    def report(self) -> str:
        """The operator-facing report surface (stdout + stderr combined).

        slice-02 asserts on report GRANULARITY: the report must resolve every
        flagged dimension-ID to its summary text (DIM-4 comprehension-key
        contract) and must name the specific malformation reason (DIM-7), not
        emit a bare ID or an undifferentiated either/or. The report is the union
        of the machine stdout token line and the human ``print_human_summary``
        stderr line -- the acceptance designer reads BOTH at the terminal.
        """
        return self.stdout + "\n" + self.stderr

    @property
    def verdict(self) -> DimensionCoverageVerdict:
        """Map the CLI output onto the user-observable verdict.

        Reads the structured ``verdict=`` token (the stable machine contract),
        never free-text substrings.

          - No ``verdict=`` token at all -> UNRECOGNISED_INVOCATION: the CLI
            produced no structured output (the master/RED-scaffold state).
          - An off-contract token -> ``ValueError``, failing the test loudly.
        """
        token = self._verdict_token
        if token is None:
            return DimensionCoverageVerdict.UNRECOGNISED_INVOCATION
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"check_design_dimension_coverage CLI emitted an off-contract "
                f"verdict token {token!r}; expected one of "
                f"{sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]


@dataclass
class DimensionCoverageFixture:
    """Production-wired composition root for the dimension-coverage CLI slices.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta + AT corpus are provisioned via
    ``provision_corpus_shape`` so each scenario builds exactly the
    declared-dimension-vs-carrier-comment shape it needs; the CLI is then
    invoked through its argv entry point against that feature.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("design-dimension-coverage-demo"))

    # --- paths ---------------------------------------------------------------

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_dir / "feature-delta.md"

    @property
    def at_corpus_root(self) -> Path:
        """The AT corpus directory the carrier-comment parser scopes.

        DESIGN default #3 (ratified): the gate takes an ``--at-corpus-root``
        flag pointing at the feature's acceptance dir (mirrors the reuse-first
        gate's explicit ``--repo-root``). The carrier-comment parser scans
        ``.feature`` / ``.py`` files under this root only (non-vacuity
        invariant (c): a carrier comment in a non-corpus file does NOT count).
        """
        return self.repo_dir / "corpus"

    @property
    def _carrier_file_path(self) -> Path:
        """The AT-corpus file carrying ``# dimension: DIM-N`` comments."""
        return self.at_corpus_root / "test_dimension_properties.py"

    # --- Given: feature provisioning ----------------------------------------

    def create_feature(self, feature_id: FeatureId) -> None:
        """Create the feature directory skeleton."""
        self.feature_id = feature_id
        self._feature_dir.mkdir(parents=True, exist_ok=True)

    def provision_corpus_shape(self, shape: FeatureCorpusShape) -> None:
        """Write the feature-delta + AT corpus for the chosen shape."""
        builder = _CORPUS_SHAPE_BUILDERS[shape]
        builder(self)

    def _write_feature_delta(self, body: str) -> None:
        self.feature_delta_path.write_text(body, encoding="utf-8")

    def _write_carrier_file(self, carrier_lines: list[str]) -> None:
        self._carrier_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._carrier_file_path.write_text(
            "\n".join(carrier_lines) + "\n", encoding="utf-8"
        )

    # --- When: run the CLI --------------------------------------------------

    def run_check(self) -> CheckResult:
        """Invoke the production check_design_dimension_coverage CLI.

        Uses ``--feature-id <id>`` + ``--repo-root <dir>`` +
        ``--at-corpus-root <dir>`` to point the CLI at the tmp_path feature
        project. Captures stdout/stderr in-process for token reading.

        Defends the pre-scaffold state: if the production module does not
        exist yet (``ModuleNotFoundError``), returns a synthetic
        UNRECOGNISED_INVOCATION result so the AT fails with a semantic
        assertion error in the @then step rather than a collection-time import
        error. Once the crafter authors the scaffold the path becomes
        ``AssertionError`` propagated from the scaffold's ``main``; once the
        implementation lands, the path is the real stdout token.
        """
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
            "--at-corpus-root",
            str(self.at_corpus_root),
        ]
        try:
            cli_module = importlib.import_module(_CLI_MODULE)
        except ModuleNotFoundError:
            return CheckResult(
                exit_code=-1,
                stdout="",
                stderr=f"production module {_CLI_MODULE!r} not yet authored",
            )
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exit_code = cli_module.main(argv)
        return CheckResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The CLI has a bounded-change contract: it reads the feature-delta and
        the AT corpus and MUST NOT mutate either (it writes ONLY stdout/stderr
        + an exit code). The universe is the feature-delta's existence + bytes
        + the carrier file's existence + bytes -- the state-delta guard proves
        the read-only contract (@contract-shape:unbounded-preservation, DIM-10
        tree-safe half).
        """
        return {
            "feature_delta.exists": self.feature_delta_path.exists(),
            "feature_delta.bytes": (
                self.feature_delta_path.read_bytes()
                if self.feature_delta_path.exists()
                else None
            ),
            "carrier_file.exists": self._carrier_file_path.exists(),
            "carrier_file.bytes": (
                self._carrier_file_path.read_bytes()
                if self._carrier_file_path.exists()
                else None
            ),
        }


# --- dimensions-block + carrier corpus builders -----------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in step
# bodies). The builders write the gate's CANONICAL DESIGN dimensions heading
# (## DESIGN Dimensions) or the carpaccio variant (## Wave: DESIGN / [REF]
# Dimensions) -- the heading SSOT the production parser must anchor on
# (DESIGN default #1). These are the gate's INPUT fixtures; they are NOT this
# feature-delta's own dogfood block.


def _dimensions_block(heading_style: DimensionsHeadingStyle, rows: str) -> str:
    """Assemble a DESIGN dimensions block under the chosen heading SSOT.

    The block is the fixed GFM table shape: ``dimension-ID | summary |
    input-axis | invalid-subspace | rationale`` (column-1 is the immutable
    join-key, form ``DIM-[A-Za-z0-9-]+``). ``rows`` is the pre-rendered table
    body (may be empty for the MALFORMED empty-block shape).
    """
    heading = {
        DimensionsHeadingStyle.CANONICAL: "## DESIGN Dimensions",
        DimensionsHeadingStyle.CARPACCIO: "## Wave: DESIGN / [REF] Dimensions",
    }[heading_style]
    header = (
        f"{heading}\n\n"
        "| dimension-ID | summary | input-axis | invalid-subspace | rationale |\n"
        "|---|---|---|---|---|\n"
    )
    return header + rows


def _doc(*sections: str) -> str:
    return (
        "# Feature Delta: design-dimension coverage fixture\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


# Canonical two-dimension table body used by the witnessed shapes.
_TWO_DIMENSION_ROWS = (
    "| DIM-1 | block parsed from feature-delta | feature-delta GFM table "
    "| table absent / <4 cols -> MALFORMED | input half |\n"
    "| DIM-2 | carrier comments parsed from corpus | `# dimension: DIM-N` "
    "comment lines | comment in non-corpus file -> not counted | join half |\n"
)


def _build_all_dimensions_witnessed(fixture: DimensionCoverageFixture) -> None:
    """PASS happy path: two declared dimensions, both carried in the corpus.

    The feature-delta declares DIM-1 and DIM-2 under the canonical
    ``## DESIGN Dimensions`` heading; the AT corpus carries a
    ``# dimension: DIM-1`` AND a ``# dimension: DIM-2`` carrier comment. Every
    declared dimension-ID is witnessed -> verdict PASS, exit 0.
    """
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, _TWO_DIMENSION_ROWS))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-1",
            "def test_block_parsed(): ...",
            "",
            "# dimension: DIM-2",
            "def test_carrier_parsed(): ...",
        ]
    )


def _build_one_dimension_unwitnessed(fixture: DimensionCoverageFixture) -> None:
    """INDETERMINATE sad path: a declared dimension with zero carriers (DIM-3).

    The feature-delta declares DIM-1 and DIM-2; the AT corpus carries only a
    ``# dimension: DIM-1`` comment. DIM-2 appears in zero carrier comments ->
    it is unwitnessed -> verdict INDETERMINATE, exit 1. This is the exact
    drift the gate targets: a DESIGN axis of behavior silently never witnessed
    by any downstream property.
    """
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, _TWO_DIMENSION_ROWS))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-1",
            "def test_block_parsed(): ...",
        ]
    )


def _build_all_dimensions_witnessed_carpaccio(
    fixture: DimensionCoverageFixture,
) -> None:
    """PASS happy path under the carpaccio heading (heading SSOT, default #1).

    Identical witnessed shape to ``_build_all_dimensions_witnessed`` but the
    dimensions block lives under ``## Wave: DESIGN / [REF] Dimensions``. The
    production parser MUST anchor on BOTH headings via a regex (mirroring the
    reuse-first ``_REUSE_ANALYSIS_HEADING_RE``) -> verdict PASS, exit 0.
    """
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CARPACCIO, _TWO_DIMENSION_ROWS))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-1",
            "def test_block_parsed(): ...",
            "",
            "# dimension: DIM-2",
            "def test_carrier_parsed(): ...",
        ]
    )


def _build_empty_dimensions_block(fixture: DimensionCoverageFixture) -> None:
    """MALFORMED probe: heading + table header present, ZERO data rows.

    Non-vacuity invariant (a): PASS requires >=1 declared dimension. A block
    with the heading but no data rows is MALFORMED (exit 2), NEVER a vacuous
    all-witnessed PASS. The corpus exists (so the MALFORMED comes from the
    empty declaration, not the absent corpus).
    """
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, rows=""))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-1",
            "def test_block_parsed(): ...",
        ]
    )


def _build_absent_at_corpus(fixture: DimensionCoverageFixture) -> None:
    """MALFORMED probe: dimensions declared but the corpus path does not exist.

    Earned-trust probe: the gate must NEVER silent-pass an empty join as "all
    witnessed" when the corpus is simply absent. A declared-dimensions
    feature-delta with a missing ``--at-corpus-root`` directory is MALFORMED
    (exit 2), never PASS. The builder writes the feature-delta but deliberately
    does NOT create the corpus directory.
    """
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, _TWO_DIMENSION_ROWS))
    )
    # Intentionally no _write_carrier_file: at_corpus_root never created.


# --- slice-02 corpus builders (report granularity + column-1 non-vacuity) ---
# Each builder writes a named-and-summarised dimension shape so the slice-02
# Then steps can assert the report resolves DIM-N (summary), not the bare ID.
# The declared dimension-ID + summary text are the SSOT in domain_types
# (UNWITNESSED_DIMENSION_ID / UNWITNESSED_DIMENSION_SUMMARY).

# A single declared dimension keyed UNWITNESSED_DIMENSION_ID, carrying its
# summary text in column 2. The carrier file deliberately does NOT carry a
# matching ``# dimension:`` comment, so the dimension is unwitnessed -> the
# report MUST resolve the ID to its summary (DIM-4).
_NAMED_UNWITNESSED_ROW = (
    f"| {UNWITNESSED_DIMENSION_ID} | {UNWITNESSED_DIMENSION_SUMMARY} "
    "| config file size | size > MAX_BYTES | oversize negative class |\n"
)


def _build_unwitnessed_dimension_named_in_report(
    fixture: DimensionCoverageFixture,
) -> None:
    """DIM-4: a named dimension is unwitnessed; the report resolves ID->summary.

    The feature-delta declares one dimension (UNWITNESSED_DIMENSION_ID) whose
    summary is UNWITNESSED_DIMENSION_SUMMARY. The AT corpus carries a comment
    for an UNRELATED dimension only, so the declared dimension has zero
    witnessing carriers -> verdict INDETERMINATE. The report MUST name the
    dimension as ``DIM-N (summary)`` -- the comprehension-key contract -- never
    the bare ``DIM-N``.
    """
    fixture._write_feature_delta(
        _doc(
            _dimensions_block(DimensionsHeadingStyle.CANONICAL, _NAMED_UNWITNESSED_ROW)
        )
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-UNRELATED",
            "def test_unrelated(): ...",
        ]
    )


def _build_prose_cell_mention_does_not_witness(
    fixture: DimensionCoverageFixture,
) -> None:
    """DIM-6: a prose-cell mention of the ID does NOT satisfy the join.

    The feature-delta declares one dimension (UNWITNESSED_DIMENSION_ID) in
    column 1; the SAME ID is ALSO mentioned in a prose / rationale cell of a
    SECOND row whose own column-1 is a different (witnessed) dimension. The
    column-1 read counts the declaration once; the prose-cell mention is NOT a
    witness. With no carrier comment for UNWITNESSED_DIMENSION_ID, the dimension
    stays unwitnessed and the report resolves its summary -- proving the prose
    mention is non-vacuous (it neither inflates the declared count nor silently
    witnesses the dimension).
    """
    rows = (
        _NAMED_UNWITNESSED_ROW + "| DIM-WITNESSED | join half "
        f"| corpus | non-corpus file | see {UNWITNESSED_DIMENSION_ID} for context |\n"
    )
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, rows))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-WITNESSED",
            "def test_witnessed(): ...",
        ]
    )


def _build_vacuous_column_one_block(fixture: DimensionCoverageFixture) -> None:
    """DIM-7: a block whose only rows carry a blank / non-DIM column-1.

    The feature-delta carries the DESIGN Dimensions heading + table header and
    TWO data rows, but neither row's column-1 is a ``DIM-<token>`` join-key
    (one blank, one non-DIM garbage). A vacuous column-1 is MALFORMED -- never a
    silent zero-dimensions PASS (non-vacuity invariant) -- and the report MUST
    name the column-1 vacuity reason, distinguishing it from an absent corpus.
    """
    rows = (
        "|   | a summary | axis | sub | blank identifier column |\n"
        "| not-a-dimension | another summary | axis | sub | non-DIM column-1 |\n"
    )
    fixture._write_feature_delta(
        _doc(_dimensions_block(DimensionsHeadingStyle.CANONICAL, rows))
    )
    fixture._write_carrier_file(
        [
            "# dimension: DIM-WITNESSED",
            "def test_witnessed(): ...",
        ]
    )


_CORPUS_SHAPE_BUILDERS: dict[FeatureCorpusShape, _BuilderFn] = {
    FeatureCorpusShape.ALL_DIMENSIONS_WITNESSED: _build_all_dimensions_witnessed,
    FeatureCorpusShape.ONE_DIMENSION_UNWITNESSED: _build_one_dimension_unwitnessed,
    FeatureCorpusShape.ALL_DIMENSIONS_WITNESSED_CARPACCIO: (
        _build_all_dimensions_witnessed_carpaccio
    ),
    FeatureCorpusShape.EMPTY_DIMENSIONS_BLOCK: _build_empty_dimensions_block,
    FeatureCorpusShape.ABSENT_AT_CORPUS: _build_absent_at_corpus,
    FeatureCorpusShape.UNWITNESSED_DIMENSION_NAMED_IN_REPORT: (
        _build_unwitnessed_dimension_named_in_report
    ),
    FeatureCorpusShape.PROSE_CELL_MENTION_DOES_NOT_WITNESS: (
        _build_prose_cell_mention_does_not_witness
    ),
    FeatureCorpusShape.VACUOUS_COLUMN_ONE_BLOCK: _build_vacuous_column_one_block,
}
