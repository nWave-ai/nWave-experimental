"""Composition root for the discuss-epic-mode slice-01 acceptance slice.

discuss-epic-mode R1 + slice-01 code-design (Mandate-12, Pillar 3). Wires the
PRODUCTION validate-feature-delta CLI entry point
(``des.cli.validate_feature_delta.main``) against a tmp_path epic-delta fixture.
Business logic lives here as the single source of truth; step bodies delegate to
``FeaturePlanValidationComposition`` methods and never inline logic.

Driving-Port-Only Boundary (SSOT: nw-test-design-mandates): the slice-01 value
statement names ``des validate-feature-delta --require-feature-plan
--format=json`` -- the REAL CLI surface. This composition drives THAT surface via
its argv entry point ``main(argv)`` (Layer 3 subprocess/FS acceptance), NOT the
``validate_feature_plan_content`` pure function the DESIGN AT table named as a
convenience. The pure function is an internal seam; the CLI flag-parse -> verdict
-> JSON stdout -> exit-int vertical is the keystone the slice promises, and it is
the only boundary that exercises ``--require-feature-plan`` argument handling,
JSON shape, and exit-code mapping together. The sibling slice-plan suite drives
its verdicts the same way (``main(argv)`` for every scenario), so this stays
consistent with the established convention.

Layer 3 (subprocess/FS acceptance): the validator CLI is the driving port; the
only driven port is the real filesystem (tmp_path). No PBT machinery
(Mandate 9/11) -- the Feature Plan shapes form a finite, enumerable closed set.

Pure-function contract: the CLI reads the epic-delta and returns a verdict (exit
code + stdout); it performs NO filesystem mutation. ``capture_universe``
snapshots the epic-delta so the When-step state-delta guard proves the read-only
contract (Mandate 8).

Structured-verdict contract (pins the slice-01 CLI's machine output -- the
contract the crafter MUST implement, not a guess):

    The slice-01 ``--require-feature-plan`` mode is invoked together with
    ``--format=json``. In that mode the CLI emits to stdout exactly ONE JSON
    object (single line) carrying a stable ``"verdict"`` field whose value is
    one of the slice-01 closed token set::

        accepted | missing-feature-plan | malformed-feature-plan
                 | malformed-wave-heading

    The verdict mapping below reads that ``verdict`` token -- a STRUCTURED
    contract -- never free-text stdout substrings. ``_VERDICT_TOKEN`` maps each
    token to a ``FeaturePlanVerdict``; an unknown or absent token raises rather
    than silently defaulting, so a crafter that emits an off-contract token
    fails loudly (no silent misclassification).

Active-RED note (atdd_pure): on the current tip ``main`` accepts neither
``--require-feature-plan`` nor (in this combination) the resulting JSON line --
invoked with the unknown flag it prints usage and returns exit 1, emitting no
JSON ``verdict`` line. Every ``--require-feature-plan`` assertion therefore FAILS
(no ``verdict`` token to read -> ``UNRECOGNISED_INVOCATION``) and PASSES once
slice-01 extends the CLI. The import resolves cleanly (the module exists today);
the RED signal is a missing structured verdict, not a collection error -- a
deliberate missing-functionality RED.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the validate-feature-delta CLI. The module exists
# today; slice-01 EXTENDS its `main` with the --require-feature-plan flag.
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import EpicId, FeaturePlanShape, FeaturePlanVerdict


# The closed `verdict` token set the slice-01 CLI emits under
# --require-feature-plan --format=json. This mapping IS the structured contract
# the slice-01 crafter must implement -- the AT reads the token, never a
# free-text stdout substring. An off-contract or absent token raises (see
# `ValidationResult.verdict`) so a wrong token fails loudly, never silently
# misclassifies. `rejected-infra-only` is the slice-03 cohesion concern and is
# intentionally absent from the slice-01 set.
_VERDICT_TOKEN: dict[str, FeaturePlanVerdict] = {
    "accepted": FeaturePlanVerdict.ACCEPTED,
    "missing-feature-plan": FeaturePlanVerdict.MISSING_FEATURE_PLAN,
    "malformed-feature-plan": FeaturePlanVerdict.MALFORMED_FEATURE_PLAN,
    "malformed-wave-heading": FeaturePlanVerdict.MALFORMED_WAVE_HEADING,
}

# A single well-formed, value-bearing Feature Plan row used by the happy path.
# `@walking-skeleton` annotation = value-bearing (NOT @infrastructure), so the
# cohesion floor does not veto it.
_KEYSTONE_ROW = (
    "| DESIGN-wave migration | Maintainer migrates the DESIGN wave to the "
    "declarative composition | pending | @walking-skeleton | keystone vertical |"
)


@dataclass
class ValidationResult:
    """Observable outcome of one validate-feature-delta CLI invocation.

    The slice-01 ``--require-feature-plan --format=json`` contract is a single
    JSON object with a stable ``verdict`` token. The verdict is read from that
    structured token so a crafter that phrases its diagnostic differently cannot
    cause a silent misclassification.
    """

    exit_code: int
    output: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict`` field of the single JSON object the CLI emits.

        Under ``--require-feature-plan --format=json`` the slice-01 CLI emits
        exactly one JSON object (single line) to stdout. This returns its
        ``verdict`` field, or ``None`` when stdout carries no parseable JSON
        object with a ``verdict`` key (the current-tip state -- the CLI does not
        emit JSON for the unknown flag, it prints a ``usage:`` banner).
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
    def verdict(self) -> FeaturePlanVerdict:
        """Map the CLI output onto the maintainer-observable verdict.

        The verdict is the stable ``verdict`` token of the single emitted JSON
        object (one of the closed set in ``_VERDICT_TOKEN``). This reads a
        MACHINE token, never free-text stdout substrings.

          - No ``verdict`` token at all -> UNRECOGNISED_INVOCATION: the CLI did
            not produce structured output. On the current tip the
            ``--require-feature-plan`` / ``--format=json`` combination is
            unknown, so EVERY feature-plan scenario lands here -- the
            unambiguous active-RED signal.
          - An off-contract token (a JSON ``verdict`` whose value is NOT in the
            closed set) is a contract violation -> ``ValueError``, failing the
            test loudly. The mapping never silently defaults.
        """
        token = self._verdict_token
        if token is None:
            return FeaturePlanVerdict.UNRECOGNISED_INVOCATION
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"slice-01 CLI emitted an off-contract verdict token {token!r}; "
                f"expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]


@dataclass
class FeaturePlanValidationComposition:
    """Production-wired composition root for the feature-plan-validation slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The epic-delta is provisioned via ``provision_epic_delta`` so each scenario
    builds exactly the Feature Plan shape it needs; the validator CLI is then
    invoked through its argv entry point against that file.
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

    def provision_epic_delta(self, shape: FeaturePlanShape) -> None:
        """Write the epic-delta with a Feature Plan of the requested shape."""
        builder = _EPIC_DELTA_BUILDERS[shape]
        builder(self)

    def _write(self, body: str) -> None:
        """Write the epic-delta document body."""
        self.epic_delta_path.write_text(body, encoding="utf-8")

    # --- When: run the validator ---------------------------------------------

    def run_feature_plan_check(self) -> ValidationResult:
        """Invoke the production validate-feature-delta CLI via its argv entry.

        Drives ``des validate-feature-delta --require-feature-plan
        --format=json <epic-delta>`` -- the slice-01 named CLI surface -- so the
        verdict is read from a structured ``verdict`` token.
        """
        argv = ["--require-feature-plan", "--format=json", str(self.epic_delta_path)]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return ValidationResult(exit_code=exit_code, output=buffer.getvalue())

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


def _feature_plan_section(header: str, separator: str, rows: str) -> str:
    """Assemble a `[REF] Feature Plan` section from header / separator / rows."""
    return f"## Wave: DISCUSS / [REF] Feature Plan\n\n{header}\n{separator}\n{rows}"


def _doc(*sections: str) -> str:
    """Assemble an epic-delta document body from its sections."""
    return "# Epic Delta: flow-v2-wave-migrations\n\n" + "\n\n".join(sections)


def _build_well_formed(comp: FeaturePlanValidationComposition) -> None:
    comp._write(
        _doc(
            _feature_plan_section(
                "| Feature | Value statement | Status | Annotation | Justification |",
                "|---------|-----------------|--------|------------|---------------|",
                f"{_KEYSTONE_ROW}\n| DEVOPS-wave migration | Maintainer migrates "
                "DEVOPS | pending | | |",
            )
        )
    )


def _build_section_absent(comp: FeaturePlanValidationComposition) -> None:
    # An epic-delta with a valid wave heading but NO Feature Plan section.
    comp._write(
        _doc(
            "## Wave: DISCUSS / [REF] Epic Job & Intent\n\n"
            "When my request is bigger than one feature, I want the tool to "
            "decompose it."
        )
    )


def _build_four_columns(comp: FeaturePlanValidationComposition) -> None:
    # The section is present, but the table drops the Justification column.
    comp._write(
        _doc(
            _feature_plan_section(
                "| Feature | Value statement | Status | Annotation |",
                "|---------|-----------------|--------|------------|",
                "| DESIGN-wave migration | Maintainer migrates DESIGN | pending "
                "| @walking-skeleton |",
            )
        )
    )


def _build_columns_reordered(comp: FeaturePlanValidationComposition) -> None:
    # All five columns present but in a different order. The Feature Plan reuses
    # the D2 "fixed order" contract (R1), so a re-order is a malformed plan.
    comp._write(
        _doc(
            _feature_plan_section(
                "| Status | Feature | Justification | Value statement | Annotation |",
                "|--------|---------|---------------|-----------------|------------|",
                "| pending | DESIGN-wave migration | keystone vertical | "
                "Maintainer migrates DESIGN | @walking-skeleton |",
            )
        )
    )


_EPIC_DELTA_BUILDERS: dict[
    FeaturePlanShape, Callable[[FeaturePlanValidationComposition], None]
] = {
    FeaturePlanShape.WELL_FORMED: _build_well_formed,
    FeaturePlanShape.SECTION_ABSENT: _build_section_absent,
    FeaturePlanShape.FOUR_COLUMNS: _build_four_columns,
    FeaturePlanShape.COLUMNS_REORDERED: _build_columns_reordered,
}
