"""Composition root for the slice-plan-authorship-parity acceptance slice.

`docs/feature/parallel-by-default-distill-slicing/feature-delta.md` D-1..D-6 /
slice-01 (Mandate-12, Pillar 3). Wires the PRODUCTION validate-feature-delta
CLI entry point (``des.cli.validate_feature_delta.main``) against TWO tmp_path
fixtures per scenario -- a DISCUSS-shaped one and a DISTILL-shaped one --
carrying byte-identical Slice Plan table content. Business logic lives here as
the single source of truth; step bodies delegate to
``SlicePlanAuthorshipParityComposition`` methods and never inline logic.

Driving-Port-Only Boundary (SSOT: nw-test-design-mandates): every scenario
drives the REAL CLI surface named by the feature-delta's own DoD --
``des validate-feature-delta --require-slice-plan --format=json`` -- via
``main(argv)`` (Layer 3 subprocess/FS acceptance), the SAME pattern the
shipped ``atdd_pure_validate_feature_delta_slice_dependency_justification``
sibling suite (parallel-by-default-slice-plan slice-01) already established
(EXTEND, not reinvent).

D-2's claim, verified empirically (this feature's own value statement) before
this module was authored: building two fixtures --

- a DISCUSS-shaped one (``# Feature Delta`` H1 + `## Wave: DISCUSS / [REF]
  Job & Intent` + `Locked Decisions` + `Slice Plan` + `Guardrails` +
  `Out-of-Scope` + `Outcome KPIs` -- six `## Wave:`-prefixed headings, the
  shape a Product Owner's feature-delta actually carries), and
- a DISTILL-shaped one (the SAME H1 + only `## Wave: DISCUSS / [REF] Slice
  Plan`, zero other headings -- the minimal shape an acceptance-designer
  originating a plan directly in DISTILL would actually produce),

with the identical Slice Plan table underneath both -- and running
``--require-slice-plan --format=json`` against each returns a
byte-identical ``(verdict, detail)`` pair for all three tried combinations
(no-annotation, dependency+justified, dependency+unjustified). This holds
because ``_validate_plan_content`` classifies every ``## Wave:`` heading
PRESENT in the content (regardless of which ones those are) and then walks
the Slice Plan table alone -- it never asserts any OTHER named section is
present, so a document carrying fewer well-formed sections classifies
identically to one carrying more. No production code change resulted from
this finding (D-2 confirmed true) -- this AT set is itself the evidence,
authored GREEN from the moment it first runs, exactly as the feature-delta's
own D-2 anticipated as the possible (and, empirically, actual) outcome.
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the validate-feature-delta CLI. Already ships
# --require-slice-plan (parallel-by-default-slice-plan slice-06/slice-01);
# this slice drives it against a NEW fixture-pair shape, adding no new CLI
# surface of its own (D-6).
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import DependencyVerdict, FeatureId, SecondRowShape


# The closed `verdict` token set this composition can observe (D-2's claim
# constrains it to exactly two live outcomes across the three tried
# combinations). An off-contract or absent token raises (see
# `ValidationResult.verdict`) rather than silently defaulting, so a future
# widening of the validator's verdict set fails this AT loudly instead of
# silently mis-parsing.
_VERDICT_TOKEN: dict[str, DependencyVerdict] = {
    "accepted": DependencyVerdict.ACCEPTED,
    "unjustified-slice-dependency": DependencyVerdict.UNJUSTIFIED_SLICE_DEPENDENCY,
}

# The fixed first row every fixture carries -- keeps the pre-existing
# cohesion-MECC floor (`_classify_slice_cohesion`) from vetoing a plan whose
# only row happens to be `@infrastructure`/`@coupled`, so each scenario
# isolates exactly the second row's Annotation/Justification shape (mirrors
# the sibling parallel-by-default-slice-plan slice-01 fixture verbatim).
_ANCHOR_SLICE_ROW = (
    "| slice-01 | Operator ships the walking skeleton | pending | "
    "@walking_skeleton | thinnest end-to-end vertical |"
)

# Second-row builders, one per `SecondRowShape`. Module-level dispatch keeps
# `provision_pair` a single typed lookup (Mandate-12 criterion 3).
_SECOND_SLICE_ROW_BY_SHAPE: dict[SecondRowShape, str] = {
    SecondRowShape.NO_ANNOTATION: (
        "| slice-02 | Operator applies the change | pending |  |  |"
    ),
    SecondRowShape.DEPENDENCY_JUSTIFIED: (
        "| slice-02 | Operator applies the change | pending | "
        "depends-on slice-01 | consumes the schema slice-01 defines |"
    ),
    SecondRowShape.DEPENDENCY_UNJUSTIFIED: (
        "| slice-02 | Operator applies the change | pending | depends-on slice-01 |  |"
    ),
}

_SLICE_PLAN_TABLE_HEADER = (
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|"
)

# The DISCUSS-shaped template: six `## Wave:`-prefixed headings, the shape a
# Product Owner's own feature-delta actually carries (mirrors this feature's
# sibling parallel-by-default-slice-plan feature-delta.md's own DISCUSS
# section set). Every heading is well-formed per the D2 schema -- this
# fixture's job is to be a GENUINE rich document, not a minimal one dressed
# up.
_DISCUSS_SHAPED_TEMPLATE = (
    "# Feature Delta: authorship-parity fixture (DISCUSS-originated)\n\n"
    "## Wave: DISCUSS / [REF] Job & Intent\n\n"
    "A Product Owner authors this feature end-to-end before any DISTILL work "
    "begins.\n\n"
    "## Wave: DISCUSS / [REF] Locked Decisions\n\n"
    "| ID | Decision | Rationale |\n"
    "|----|----------|-----------|\n"
    "| D-1 | Slices ship serially unless a row declares otherwise | Default "
    "posture |\n\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "{table}\n\n"
    "## Wave: DISCUSS / [REF] Guardrails\n\n"
    "Advisory on truth, structural on form.\n\n"
    "## Wave: DISCUSS / [REF] Out-of-Scope\n\n"
    "Nothing beyond this plan's own rows.\n\n"
    "## Wave: DISCUSS / [REF] Outcome KPIs\n\n"
    "| # | Who | Does What |\n"
    "|---|-----|-----------|\n"
    "| 1 | An operator | ships the feature |\n"
)

# The DISTILL-shaped template: the SAME H1 + ONLY the Slice Plan section --
# zero other `## Wave:` headings. The minimal document an acceptance-designer
# originating a plan directly in DISTILL (no DISCUSS run) would actually
# produce.
_DISTILL_SHAPED_TEMPLATE = (
    "# Feature Delta: authorship-parity fixture (DISTILL-originated)\n\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "{table}\n"
)


def _slice_plan_table(second_row: str) -> str:
    return f"{_SLICE_PLAN_TABLE_HEADER}\n{_ANCHOR_SLICE_ROW}\n{second_row}"


@dataclass
class ValidationResult:
    """Observable outcome of one validate-feature-delta CLI invocation.

    The ``--require-slice-plan --format=json`` contract is a single JSON
    object with a stable ``verdict`` token. The verdict is read from that
    structured token so a crafter that phrases its diagnostic differently
    cannot cause a silent misclassification.
    """

    exit_code: int
    output: str

    @property
    def _verdict_json(self) -> dict[str, object] | None:
        """The single JSON object the CLI emits to stdout, or None.

        Returns the parsed object (not just the verdict token) so callers can
        also read ``detail`` -- the diagnostic naming the offending row.
        """
        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "verdict" in obj:
                    return obj
        return None

    @property
    def verdict(self) -> DependencyVerdict:
        """Map the CLI's structured `verdict` token onto the typed verdict.

        No structured token at all -> UNRECOGNISED_INVOCATION (never expected
        for either fixture shape). An off-contract token -> ValueError,
        failing loudly rather than silently misclassifying.
        """
        obj = self._verdict_json
        if obj is None:
            return DependencyVerdict.UNRECOGNISED_INVOCATION
        token = str(obj["verdict"])
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"validate-feature-delta emitted an off-contract verdict "
                f"token {token!r}; expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]

    @property
    def detail(self) -> str:
        """The `detail` diagnostic string of the emitted JSON verdict.

        Empty string when no structured verdict was emitted at all (mirrors
        `verdict`'s UNRECOGNISED_INVOCATION fallback -- never raises here).
        Deliberately excludes the `remedy` field: `remedy` echoes the
        fixture's own file path, which the two fixtures never share by
        construction -- comparing `detail` (never `remedy`) is what makes the
        parity assertion meaningful rather than trivially false.
        """
        obj = self._verdict_json
        if obj is None:
            return ""
        return str(obj.get("detail", ""))


@dataclass
class ParityResult:
    """The paired outcome of running the SAME check against both fixture
    shapes -- the observable this entire slice exists to produce."""

    discuss: ValidationResult
    distill: ValidationResult

    @property
    def verdicts_match(self) -> bool:
        """True iff the two fixtures produced byte-identical (verdict, detail).

        This IS D-2's authorship-blindness claim, expressed as a single
        boolean -- the property every Then-step in this slice ultimately
        checks.
        """
        return (
            self.discuss.verdict == self.distill.verdict
            and self.discuss.detail == self.distill.detail
        )


@dataclass
class SlicePlanAuthorshipParityComposition:
    """Production-wired composition root for the slice-01 acceptance slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    ``discuss_path``/``distill_path`` track the two fixtures the most recent
    ``provision_pair`` call wrote.
    """

    repo_dir: Path
    feature_id: FeatureId = field(
        default=FeatureId("parallel-by-default-distill-slicing")
    )
    discuss_path: Path = field(init=False, default=None)  # type: ignore[assignment]
    distill_path: Path = field(init=False, default=None)  # type: ignore[assignment]

    # --- Given: repo -------------------------------------------------------

    def create_feature(self, feature_id: FeatureId) -> None:
        """Create the feature directory skeleton."""
        self.feature_id = feature_id
        self._feature_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    # --- Given: fixtures -----------------------------------------------------

    def provision_pair(self, shape: SecondRowShape) -> None:
        """Write BOTH fixtures -- DISCUSS-shaped and DISTILL-shaped -- whose
        Slice Plan tables carry byte-identical content for `shape`."""
        table = _slice_plan_table(_SECOND_SLICE_ROW_BY_SHAPE[shape])
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        self.discuss_path = self._feature_dir / "discuss-shaped-feature-delta.md"
        self.distill_path = self._feature_dir / "distill-shaped-feature-delta.md"
        self.discuss_path.write_text(
            _DISCUSS_SHAPED_TEMPLATE.format(table=table), encoding="utf-8"
        )
        self.distill_path.write_text(
            _DISTILL_SHAPED_TEMPLATE.format(table=table), encoding="utf-8"
        )

    # --- When: run the validator against both fixtures -----------------------

    def run_check(self) -> ParityResult:
        """Invoke the production CLI against both fixtures, paired."""
        return ParityResult(
            discuss=self._run_one(self.discuss_path),
            distill=self._run_one(self.distill_path),
        )

    def _run_one(self, path: Path) -> ValidationResult:
        argv = ["--require-slice-plan", "--format=json", str(path)]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return ValidationResult(exit_code=exit_code, output=buffer.getvalue())

    # --- universe --------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The validator has a pure-function contract: it reads a document and
        MUST NOT mutate it. The universe is both fixtures' existence and
        bytes -- the state-delta guard proves the read-only contract holds
        for BOTH authoring shapes, not just one.
        """
        return {
            "discuss.exists": self.discuss_path is not None
            and self.discuss_path.exists(),
            "discuss.bytes": (
                self.discuss_path.read_bytes()
                if self.discuss_path is not None and self.discuss_path.exists()
                else None
            ),
            "distill.exists": self.distill_path is not None
            and self.distill_path.exists(),
            "distill.bytes": (
                self.distill_path.read_bytes()
                if self.distill_path is not None and self.distill_path.exists()
                else None
            ),
        }
