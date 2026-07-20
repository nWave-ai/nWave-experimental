"""Composition root for the slice-dependency-justification acceptance slice.

`docs/feature/parallel-by-default-slice-plan/feature-delta.md` D-1..D-6 /
slice-01 (Mandate-12, Pillar 3). Wires the PRODUCTION validate-feature-delta
CLI entry point (``des.cli.validate_feature_delta.main``) against a tmp_path
feature-delta / epic-delta fixture. Business logic lives here as the single
source of truth; step bodies delegate to
``SliceDependencyJustificationComposition`` methods and never inline logic.

Driving-Port-Only Boundary (SSOT: nw-test-design-mandates): every scenario
drives the REAL CLI surface named by the feature-delta's own DoD --
``des validate-feature-delta --require-slice-plan --format=json`` (six of the
seven scenarios) and ``--require-feature-plan --format=json`` (the isolation
scenario) -- via ``main(argv)`` (Layer 3 subprocess/FS acceptance), exactly
the pattern the shipped ``atdd_pure_validate_feature_delta_slice_plan`` and
``_feature_plan`` sibling suites already established (EXTEND, not reinvent --
see this feature's own Test Reuse & Consolidation Analysis).

Structured-verdict contract (pins the slice-01 CLI's machine output -- the
contract the crafter MUST implement, not a guess). Under
``--require-slice-plan --format=json`` the CLI's closed set gains ONE token
this feature introduces:

    accepted | missing-slice-plan | malformed-slice-plan
             | malformed-wave-heading | rejected-infra-only
             | unjustified-slice-dependency

Under ``--require-feature-plan --format=json`` the closed set is UNCHANGED BY
THIS FEATURE (D-6 -- this suite's isolation scenario proves ``unjustified-
slice-dependency`` never appears there). It DID grow one token since this
suite was first authored -- the sibling feature `parallel-by-default-
feature-plan` slice-01 (row 4) generalizes the identical D-1/D-2 rule to
feature granularity, adding its OWN ``unjustified-feature-dependency`` token.
The isolation scenario below was updated to assert THAT token fires (not
``unjustified-slice-dependency``) -- still proving the cross-mode boundary,
now against feature-plan mode's own six-token set:

    accepted | missing-feature-plan | malformed-feature-plan
             | malformed-wave-heading | rejected-infra-only
             | unjustified-feature-dependency

Active-RED note (atdd_pure, incremental-extension shape). Unlike a
brand-new-flag slice, ``--require-slice-plan --format=json`` already ships
(slice-06) -- so ONLY the scenarios exercising genuinely NEW behaviour are
RED on the current tip:

- the "declared dependency, empty Justification -> rejected" scenario is RED
  today: nothing in ``_validate_plan_content`` checks per-row Justification
  in slice-plan mode, so a `depends-on` row with an empty Justification cell
  currently comes back ``accepted`` -- the wrong verdict.
- the "structurally malformed dependency row -> malformed slice plan"
  scenario is RED today for the same root cause: no per-row cell-count guard
  exists in slice-plan mode (unlike Reuse Analysis's ``_classify_component_
  row``), so a row missing its Justification column entirely is silently
  accepted rather than rejected.

Every other scenario pins EXISTING, already-shipped behaviour (D-2's
"no burden on a non-dependency row" is already true today, and the
feature-plan isolation is trivially true before this feature exists at all)
-- they are non-regression guards, correctly green now and required to stay
green once slice-01 lands. This is the expected shape for an INCREMENTAL
verdict-set extension (mirrors how Reuse Analysis's own verdict-set growth
only reddened its own new-token scenario, per DDD-3/DDD-9 history) -- not
every scenario in an atdd_pure slice need be individually RED when the slice
adds one classification arm to an already-accepted surface.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the validate-feature-delta CLI. Both
# --require-slice-plan and --require-feature-plan already exist (slice-06 /
# discuss-epic-mode slice-01); slice-01 of THIS feature EXTENDS the
# slice-plan mode's per-row classification with the new dependency check.
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import CheckMode, DependencyVerdict, FeatureId, SecondRowShape


# The closed `verdict` token set this composition can observe, across BOTH
# plan modes (token strings never collide between modes -- see module
# docstring). An off-contract or absent token raises (see
# `ValidationResult.verdict`) rather than silently defaulting, so a crafter
# that widens either mode's set, or misspells a token, fails loudly.
_VERDICT_TOKEN: dict[str, DependencyVerdict] = {
    "accepted": DependencyVerdict.ACCEPTED,
    "missing-slice-plan": DependencyVerdict.MISSING_SLICE_PLAN,
    "malformed-slice-plan": DependencyVerdict.MALFORMED_SLICE_PLAN,
    "malformed-wave-heading": DependencyVerdict.MALFORMED_WAVE_HEADING,
    "rejected-infra-only": DependencyVerdict.REJECTED_INFRA_ONLY,
    "unjustified-slice-dependency": DependencyVerdict.UNJUSTIFIED_SLICE_DEPENDENCY,
    "missing-feature-plan": DependencyVerdict.MISSING_FEATURE_PLAN,
    "malformed-feature-plan": DependencyVerdict.MALFORMED_FEATURE_PLAN,
    "unjustified-feature-dependency": DependencyVerdict.UNJUSTIFIED_FEATURE_DEPENDENCY,
}

# The fixed first row every slice-plan fixture carries -- keeps the
# pre-existing cohesion-MECC floor (`_classify_slice_cohesion`) from vetoing
# a plan whose only row happens to be `@infrastructure`/`@coupled`, so each
# scenario isolates exactly the second row's Annotation/Justification shape.
_ANCHOR_SLICE_ROW = (
    "| slice-01 | Operator ships the walking skeleton | pending | "
    "@walking_skeleton | thinnest end-to-end vertical |"
)

# Second-row builders, one per `SecondRowShape`. Module-level dispatch keeps
# `provision_slice_plan` a single typed lookup (Mandate-12 criterion 3).
_SECOND_SLICE_ROW_BY_SHAPE: dict[SecondRowShape, str] = {
    SecondRowShape.NO_ANNOTATION: (
        "| slice-02 | Operator applies the change | pending |  |  |"
    ),
    SecondRowShape.WALKING_SKELETON: (
        "| slice-02 | Operator applies the change | pending | @walking_skeleton |  |"
    ),
    SecondRowShape.INFRASTRUCTURE: (
        "| slice-02 | Operator applies the change | pending | @infrastructure |  |"
    ),
    SecondRowShape.COUPLED: (
        "| slice-02 | Operator applies the change | pending | @coupled |  |"
    ),
    SecondRowShape.DEPENDENCY_JUSTIFIED: (
        "| slice-02 | Operator applies the change | pending | "
        "depends-on slice-01 | consumes the schema slice-01 defines |"
    ),
    SecondRowShape.DEPENDENCY_UNJUSTIFIED: (
        "| slice-02 | Operator applies the change | pending | depends-on slice-01 |  |"
    ),
    # Deliberately only FOUR cells -- the Justification column is dropped
    # entirely (no trailing `| ... |` segment), simulating a malformed row
    # that still LOOKS like a dependency claim.
    SecondRowShape.DEPENDENCY_MALFORMED_ROW: (
        "| slice-02 | Operator applies the change | pending | depends-on slice-01 |"
    ),
}

# The Feature Plan fixture (feature granularity, epic-delta) used ONLY by the
# isolation scenario -- proves the new rule does not leak one level up.
_FEATURE_PLAN_ANCHOR_ROW = (
    "| billing-webhook-retry | Maintainer ships the anchor feature | pending | "
    "@walking_skeleton | thinnest end-to-end vertical |"
)
_FEATURE_PLAN_UNJUSTIFIED_DEPENDENCY_ROW = (
    "| search-relevance-tuning | Maintainer ships the dependent feature | "
    "pending | depends-on billing-webhook-retry |  |"
)


@dataclass
class ValidationResult:
    """Observable outcome of one validate-feature-delta CLI invocation.

    The ``--require-slice-plan --format=json`` / ``--require-feature-plan
    --format=json`` contract is a single JSON object with a stable
    ``verdict`` token. The verdict is read from that structured token so a
    crafter that phrases its diagnostic differently cannot cause a silent
    misclassification.
    """

    exit_code: int
    output: str

    @property
    def _verdict_json(self) -> dict[str, object] | None:
        """The single JSON object the CLI emits to stdout, or None.

        Returns the parsed object (not just the verdict token) so callers can
        also read ``detail`` -- the diagnostic naming the offending row
        (GDP-3).
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
        on either mode's shipped flags). An off-contract token -> ValueError,
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
        """
        obj = self._verdict_json
        if obj is None:
            return ""
        return str(obj.get("detail", ""))


@dataclass
class SliceDependencyJustificationComposition:
    """Production-wired composition root for the slice-01 acceptance slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    ``active_path`` tracks whichever document the most recent ``provision_*``
    call wrote, so ``run_check``/``capture_universe`` always target the
    fixture the current scenario actually built.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("parallel-by-default-slice-plan"))
    active_path: Path = field(init=False, default=None)  # type: ignore[assignment]

    # --- paths -----------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    @property
    def _epic_delta_path(self) -> Path:
        return (
            self.repo_dir
            / "docs"
            / "epic"
            / "swarm-parallel-delivery"
            / "epic-delta.md"
        )

    # --- Given: repo -------------------------------------------------------

    def create_feature(self, feature_id: FeatureId) -> None:
        """Create the feature directory skeleton."""
        self.feature_id = feature_id
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Given: fixtures ---------------------------------------------------

    def provision_slice_plan(self, shape: SecondRowShape) -> None:
        """Write a feature-delta whose Slice Plan's second row is `shape`."""
        second_row = _SECOND_SLICE_ROW_BY_SHAPE[shape]
        body = (
            "# Feature Delta: slice-dependency-justification fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            f"{_ANCHOR_SLICE_ROW}\n{second_row}"
        )
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(body, encoding="utf-8")
        self.active_path = self._feature_delta_path

    def provision_feature_plan_with_unjustified_dependency(self) -> None:
        """Write an epic-delta whose Feature Plan carries an unjustified
        `depends-on` row -- the isolation fixture (D-6)."""
        body = (
            "# Epic Delta: slice-dependency-justification isolation fixture\n\n"
            "## Wave: DISCUSS / [REF] Feature Plan\n\n"
            "| Feature | Value statement | Status | Annotation | Justification |\n"
            "|---------|-----------------|--------|------------|---------------|\n"
            f"{_FEATURE_PLAN_ANCHOR_ROW}\n{_FEATURE_PLAN_UNJUSTIFIED_DEPENDENCY_ROW}"
        )
        self._epic_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._epic_delta_path.write_text(body, encoding="utf-8")
        self.active_path = self._epic_delta_path

    # --- When: run the validator --------------------------------------------

    def run_check(self, mode: CheckMode) -> ValidationResult:
        """Invoke the production validate-feature-delta CLI via its argv entry."""
        target = (
            self._feature_delta_path
            if mode is CheckMode.SLICE_PLAN
            else self._epic_delta_path
        )
        argv = _ARGV_BY_MODE[mode](target)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return ValidationResult(exit_code=exit_code, output=buffer.getvalue())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The validator has a pure-function contract: it reads the document and
        MUST NOT mutate it. The universe is `active_path`'s existence and
        bytes -- the state-delta guard proves the read-only contract.
        """
        path = self.active_path
        return {
            "document.exists": path is not None and path.exists(),
            "document.bytes": (
                path.read_bytes() if path is not None and path.exists() else None
            ),
        }


# --- argv builders ------------------------------------------------------
# Each builder keeps `run_check` a single typed dispatch + a single CLI call
# (Mandate-12 criterion 3: no control flow in the service method body).


def _argv_require_slice_plan(path: Path) -> list[str]:
    return ["--require-slice-plan", "--format=json", str(path)]


def _argv_require_feature_plan(path: Path) -> list[str]:
    return ["--require-feature-plan", "--format=json", str(path)]


_ARGV_BY_MODE: dict[CheckMode, Callable[[Path], list[str]]] = {
    CheckMode.SLICE_PLAN: _argv_require_slice_plan,
    CheckMode.FEATURE_PLAN: _argv_require_feature_plan,
}
