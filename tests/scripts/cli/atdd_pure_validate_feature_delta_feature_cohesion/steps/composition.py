"""Composition root for the discuss-epic-mode slice-03 acceptance slice.

discuss-epic-mode slice-03 (feature-granularity cohesion-MECC) + the DESIGN
slice-03 code-design (Mandate-12, Pillar 3). Wires the PRODUCTION
validate-feature-delta CLI entry point (``des.cli.validate_feature_delta.main``)
against a tmp_path epic-delta fixture. Business logic lives here as the single
source of truth; step bodies delegate to ``FeatureCohesionComposition`` methods
and never inline logic.

Driving-Port-Only Boundary (SSOT: nw-test-design-mandates): the slice-03 value
statement names the mechanical rejection of an all-@infrastructure epic. This
composition drives the REAL CLI surface ``des validate-feature-delta
--require-feature-plan --format=json`` via its argv entry point ``main(argv)``
(Layer 3 subprocess/FS acceptance), NOT the ``validate_feature_plan_content`` /
``_classify_slice_cohesion`` internal functions the DESIGN AT note named as a
convenience. The cohesion floor is reached THROUGH the real CLI: flag-parse ->
``_validate_plan_content`` -> ``_classify_slice_cohesion(rows, "feature")`` ->
``rejected-infra-only`` verdict -> JSON stdout -> exit-int. Driving the internal
pure function would be a Layer-1 unit test masquerading as an AT (Mandate-13
violation); the witness must exercise the seam through the production entry point.

Layer 3 (subprocess/FS acceptance): the validator CLI is the driving port; the
only driven port is the real filesystem (tmp_path). No PBT machinery
(Mandate 9/11) -- the cohesion shapes form a finite, enumerable closed set.

Pure-function contract: the CLI reads the epic-delta and returns a verdict (exit
code + stdout); it performs NO filesystem mutation. ``capture_universe`` snapshots
the epic-delta so the Then-step state-delta guard proves the read-only contract
(Mandate 8).

Structured-verdict contract (pins the slice-03 CLI's machine output):

    ``--require-feature-plan`` is invoked with ``--format=json``. In that mode the
    CLI emits to stdout exactly ONE JSON object (single line) carrying a stable
    ``"verdict"`` field and a ``"detail"`` field. The cohesion concern reads two
    verdict tokens over a structurally well-formed Feature Plan::

        rejected-infra-only | accepted

    The ``rejected-infra-only`` token is SHARED with the slice-plan mode; the
    plan-kind disambiguator is the ``detail`` field, which reads
    ``"all N feature rows are annotated @infrastructure; ..."`` for the feature
    mode (token-coupling constraint H3/M1, NORMATIVE for consumers). The
    composition exposes both the token (``verdict``) and the detail
    (``names_cause_in_feature_terms``) so the ATs pin the disambiguator
    empirically -- a bare-token check would not distinguish a slice-plan veto from
    a feature-plan veto.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the validate-feature-delta CLI. The module exists
# today; the slice-03 cohesion floor is reached through its `main` entry point
# under --require-feature-plan (the feature spec carries row_noun="feature").
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import CohesionShape, CohesionVerdict, EpicId


# The two cohesion `verdict` tokens the slice-03 CLI emits under
# --require-feature-plan --format=json over a well-formed Feature Plan. The AT
# reads the token (a structured contract), never a free-text stdout substring. An
# off-contract token raises (see `CohesionResult.verdict`) so a wrong token fails
# loudly, never silently misclassifies.
_VERDICT_TOKEN: dict[str, CohesionVerdict] = {
    "rejected-infra-only": CohesionVerdict.REJECTED_INFRA_ONLY,
    "accepted": CohesionVerdict.CLEARS_FLOOR,
}

# The plan-kind disambiguator the feature mode's `rejected-infra-only` detail
# MUST carry (token-coupling H3/M1). The slice-plan mode renders "slice rows";
# the feature mode renders "feature rows". Asserting this substring pins that the
# cohesion floor was reached at FEATURE granularity, not slice granularity.
_FEATURE_TERMS_MARKER = "feature rows"

# A well-formed five-column Feature Plan header + separator. Every fixture shares
# the same structurally-valid shape; only the Annotation column varies, so the
# only verdict driver under test is the cohesion floor (not column shape).
_HEADER = "| Feature | Value statement | Status | Annotation | Justification |"
_SEPARATOR = "|---------|-----------------|--------|------------|---------------|"

_INFRA_ROW_A = (
    "| DESIGN-wave migration | Maintainer migrates the DESIGN wave | pending "
    "| @infrastructure | plumbing only |"
)
_INFRA_ROW_B = (
    "| DEVOPS-wave migration | Maintainer migrates the DEVOPS wave | pending "
    "| @infrastructure | plumbing only |"
)
# A value-bearing row: an empty Annotation cell normalises to value-bearing (NOT
# infrastructure), so the cohesion floor does not veto it.
_VALUE_ROW = (
    "| DISTILL-wave migration | Maintainer ships the DISTILL migration outcome "
    "| pending | | user-visible wave migration |"
)


@dataclass
class CohesionResult:
    """Observable outcome of one validate-feature-delta cohesion invocation.

    The ``--require-feature-plan --format=json`` contract is a single JSON object
    with a stable ``verdict`` token and a ``detail`` string. The verdict is read
    from the structured token; ``detail`` carries the plan-kind disambiguator.
    """

    exit_code: int
    output: str

    @property
    def _json_object(self) -> dict[str, object] | None:
        """The single JSON object the CLI emits, or None when stdout carries none.

        Under ``--require-feature-plan --format=json`` the CLI emits exactly one
        JSON object (single line) to stdout. Returns it parsed, or ``None`` when
        no parseable object with a ``verdict`` key is present.
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
    def verdict(self) -> CohesionVerdict:
        """Map the CLI output onto the maintainer-observable cohesion verdict.

        Reads the stable ``verdict`` token of the single emitted JSON object (one
        of the closed set in ``_VERDICT_TOKEN``) -- a MACHINE token, never
        free-text stdout substrings. No structured token -> ``UNRECOGNISED`` (the
        CLI produced no JSON object). An off-contract token raises ``ValueError``
        so the test fails loudly; the mapping never silently defaults.
        """
        obj = self._json_object
        if obj is None:
            return CohesionVerdict.UNRECOGNISED
        token = str(obj["verdict"])
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"slice-03 CLI emitted an off-contract verdict token {token!r}; "
                f"expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]

    @property
    def names_cause_in_feature_terms(self) -> bool:
        """True iff the rejection detail names the cause at FEATURE granularity.

        The ``rejected-infra-only`` token is shared with the slice-plan mode; the
        feature mode's detail MUST read ``"... feature rows are annotated
        @infrastructure ..."`` (token-coupling H3/M1). This reads the structured
        ``detail`` field of the emitted JSON object, never an arbitrary substring
        of the whole stdout.
        """
        obj = self._json_object
        if obj is None:
            return False
        detail = str(obj.get("detail", ""))
        return _FEATURE_TERMS_MARKER in detail


@dataclass
class FeatureCohesionComposition:
    """Production-wired composition root for the feature-cohesion slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root. The
    epic-delta is provisioned via ``provision_epic_delta`` so each scenario builds
    exactly the cohesion shape it needs; the validator CLI is then invoked through
    its argv entry point against that file.
    """

    repo_dir: Path
    epic_id: EpicId = field(default=EpicId("flow-v2-wave-migrations"))

    # --- paths ---------------------------------------------------------------

    @property
    def _epic_dir(self) -> Path:
        return self.repo_dir / "docs" / "epic" / self.epic_id

    @property
    def epic_delta_path(self) -> Path:
        return self._epic_dir / "epic-delta.md"

    # --- Given: epic workspace -----------------------------------------------

    def create_epic(self, epic_id: EpicId) -> None:
        """Create the epic directory skeleton."""
        self.epic_id = epic_id
        self._epic_dir.mkdir(parents=True, exist_ok=True)

    # --- Given: epic-delta + Feature Plan ------------------------------------

    def provision_epic_delta(self, shape: CohesionShape) -> None:
        """Write the epic-delta with a Feature Plan of the requested cohesion."""
        builder = _EPIC_DELTA_BUILDERS[shape]
        builder(self)

    def _write(self, body: str) -> None:
        """Write the epic-delta document body."""
        self.epic_delta_path.write_text(body, encoding="utf-8")

    # --- When: run the validator ---------------------------------------------

    def run_feature_plan_check(self) -> CohesionResult:
        """Invoke the production validate-feature-delta CLI via its argv entry.

        Drives ``des validate-feature-delta --require-feature-plan --format=json
        <epic-delta>`` -- the real CLI surface -- so the cohesion floor is reached
        through the production entry point and the verdict + detail are read from
        a structured JSON object.
        """
        argv = ["--require-feature-plan", "--format=json", str(self.epic_delta_path)]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return CohesionResult(exit_code=exit_code, output=buffer.getvalue())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The validator has a pure-function contract: it reads the epic-delta and
        MUST NOT mutate it. The universe is the epic-delta's existence and bytes
        -- the state-delta guard proves the read-only contract.
        """
        return {
            "epic_delta.exists": self.epic_delta_path.exists(),
            "epic_delta.bytes": (
                self.epic_delta_path.read_bytes()
                if self.epic_delta_path.exists()
                else None
            ),
        }


# --- epic-delta fixture builders --------------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _feature_plan_section(*rows: str) -> str:
    """Assemble a `[REF] Feature Plan` section from a well-formed header + rows."""
    body = "\n".join(rows)
    return f"## Wave: DISCUSS / [REF] Feature Plan\n\n{_HEADER}\n{_SEPARATOR}\n{body}"


def _doc(*sections: str) -> str:
    """Assemble an epic-delta document body from its sections."""
    return "# Epic Delta: flow-v2-wave-migrations\n\n" + "\n\n".join(sections)


def _build_all_infrastructure(comp: FeatureCohesionComposition) -> None:
    # Many feature rows, every one @infrastructure -> infrastructure-only epic.
    comp._write(_doc(_feature_plan_section(_INFRA_ROW_A, _INFRA_ROW_B)))


def _build_one_value_bearing(comp: FeatureCohesionComposition) -> None:
    # @infrastructure rows plus exactly one value-bearing row -> clears the floor.
    comp._write(_doc(_feature_plan_section(_INFRA_ROW_A, _VALUE_ROW, _INFRA_ROW_B)))


def _build_single_infrastructure(comp: FeatureCohesionComposition) -> None:
    # A single feature row, @infrastructure -> still infrastructure-only (C3 One).
    comp._write(_doc(_feature_plan_section(_INFRA_ROW_A)))


_EPIC_DELTA_BUILDERS: dict[
    CohesionShape, Callable[[FeatureCohesionComposition], None]
] = {
    CohesionShape.ALL_INFRASTRUCTURE: _build_all_infrastructure,
    CohesionShape.ONE_VALUE_BEARING: _build_one_value_bearing,
    CohesionShape.SINGLE_INFRASTRUCTURE: _build_single_infrastructure,
}
