"""Composition root for f-declarative-gate-composition slice-03 (removal-only).

DRIVING SURFACES (Mandate-13 driving-port-only):
  * ABSENCE -- a repo-source read over the SHIPPED production modules
    ``pre_tool_use_service.py`` / ``subagent_stop_service.py`` asserting the
    superseded imperative DISCUSS gate-stack branches are GONE (the
    ``if markers.wave == "discuss"`` gate-IN hinge + the ``_discuss_gate_out`` /
    ``_discuss_review_veto`` gate-OUT methods). The shipped source file IS the
    artifact (Mandate-13 prose-surface case: read the real file from the repo, not
    an inline string; assert on a discriminating multi-token phrase).
  * NON-REGRESSION -- the REAL SubagentStopService.validate via the production
    composition root (Layer 3 composition): after the imperative branch is removed,
    the DISCUSS gate-OUT still VETOES (now via the declared wave_gate_stacks.discuss
    composition). The veto must SURVIVE the removal -- removal of the imperative
    wiring must not drop enforcement.

slice-03 is a removal-only consolidation slice (C10): the deliverable is the
ABSENCE of the stale imperative wiring + the NON-REGRESSION witness. The single
AT-8 carries both as one scenario (absence + still-vetoes).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the imperative branches are
PRESENT (the lift has not happened) -- so the absence assertion fires RED (the
discriminating phrases are still in the shipped source). GREEN once DELIVER removes
the superseded branches AND the DISCUSS gate-OUT still vetoes via the declared
composition. The Then fires a semantic AssertionError naming the surviving branch,
never a collection / import error.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_declarative_gate_composition import GateDecision


REPO_ROOT = Path(__file__).resolve().parents[5]

_PRE_TOOL_USE_SRC = (
    REPO_ROOT / "src" / "des" / "application" / "pre_tool_use_service.py"
)
_SUBAGENT_STOP_SRC = (
    REPO_ROOT / "src" / "des" / "application" / "subagent_stop_service.py"
)

_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_GATE_OUT_FEATURE_ID = "f-declarative-gate-composition-removal-probe"
_FEATURE_DELTA_REL = f"docs/feature/{_GATE_OUT_FEATURE_ID}/feature-delta.md"

_INFRA_ONLY_FEATURE_DELTA = f"""\
# Feature Delta: {_GATE_OUT_FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | wire the logging adapter | pending | @infrastructure | plumbing only |
| slice-02 | configure the CI matrix | pending | @infrastructure | plumbing only |
"""

# Discriminating multi-token phrases that exist ONLY in the imperative DISCUSS
# gate-stack branches the declarative lift supersedes (Mandate-13 prose-surface:
# discriminating phrases, never a common substring). Each is the method-def /
# branch signature the removal must delete.
_SUPERSEDED_IMPERATIVE_MARKERS: tuple[tuple[Path, str], ...] = (
    # the gate-IN hinge `def _discuss_gate_in(` is the imperative gate-IN method.
    (_PRE_TOOL_USE_SRC, "def _discuss_gate_in("),
    # the gate-OUT structural method `def _discuss_gate_out(`.
    (_SUBAGENT_STOP_SRC, "def _discuss_gate_out("),
    # the PO-review consumer veto method `def _discuss_review_veto(`.
    (_SUBAGENT_STOP_SRC, "def _discuss_review_veto("),
)


@dataclass
class RemovalComposition:
    """Asserts the imperative DISCUSS branches are gone + the veto still fires."""

    _project_root: Path | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _surviving: list[str] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_discuss_wave_migrated_to_declarative(self, tmp_path: Path) -> None:
        """Arm a discuss gate-OUT veto precondition for the non-regression witness."""
        self._project_root = tmp_path
        self._write_floor(
            tmp_path, json.dumps({"wave": "discuss", "provenance": "command"})
        )
        self._write_feature_delta(tmp_path, _INFRA_ONLY_FEATURE_DELTA)

    # ---- when ---------------------------------------------------------------

    def when_the_codebase_is_inspected_and_the_gate_runs(self) -> None:
        """Read the shipped source for surviving branches; drive the REAL gate-OUT."""
        self._surviving = self._surviving_imperative_markers()
        self._run_subagent_stop_gate()

    # ---- then (AT-8: absence + non-regression) ------------------------------

    def then_no_imperative_discuss_branch_survives(self) -> None:
        """ABSENCE: no superseded imperative DISCUSS gate-stack branch survives.

        RED at HEAD: the imperative branches are PRESENT (the lift has not happened)
        -> surviving markers is non-empty -> RED. GREEN once DELIVER removes the
        superseded `if markers.wave == "discuss"` gate-IN hinge + the
        `_discuss_gate_out` / `_discuss_review_veto` gate-OUT branch (git is the
        archive).
        """
        surviving = self._surviving or []
        assert not surviving, (
            "the superseded imperative DISCUSS gate-stack branches must be REMOVED "
            "once the declarative wave_gate_stacks.discuss composition supersedes "
            "them (C10, git is the archive); these discriminating branch signatures "
            f"still survive in the shipped source: {surviving!r}. "
            f"{self._observed()}"
        )

    def then_discuss_gate_out_still_vetoes(self) -> None:
        """NON-REGRESSION: the DISCUSS gate-OUT veto SURVIVES the removal.

        Driven through the REAL SubagentStopService (Layer 3 composition): removing
        the imperative wiring must NOT drop enforcement -- the infra-only slice plan
        must STILL be vetoed, now via the declared composition.
        """
        assert self._gate_decision() is GateDecision.BLOCK, (
            "removing the imperative DISCUSS gate-OUT branch must NOT drop "
            "enforcement -- the infra-only feature-delta slice plan must STILL be "
            "vetoed via the declared wave_gate_stacks.discuss.gate-out composition; "
            f"the gate returned {self._decision_action!r}. {self._observed()}"
        )

    # ---- driving-port invocations -------------------------------------------

    def _surviving_imperative_markers(self) -> list[str]:
        """Read the SHIPPED source files; return any surviving branch signatures."""
        surviving: list[str] = []
        for src_path, marker in _SUPERSEDED_IMPERATIVE_MARKERS:
            text = src_path.read_text(encoding="utf-8")
            if marker in text:
                surviving.append(f"{src_path.name}::{marker}")
        return surviving

    def _run_subagent_stop_gate(self) -> None:
        """Drive the REAL SubagentStopService.validate via the production composition root."""
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    execution_log_path="",
                    project_id=_GATE_OUT_FEATURE_ID,
                    step_id="",
                    cwd=str(self._project_root),
                    mode="atdd_pure",
                    slice_id="slice-01",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
        self._decision_action = decision.action  # type: ignore[attr-defined]
        self._decision_reason = decision.reason  # type: ignore[attr-defined]

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the gate must run (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- substrate ----------------------------------------------------------

    def _write_floor(self, root: Path, content: str) -> None:
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(content, encoding="utf-8")

    def _write_feature_delta(self, root: Path, content: str) -> None:
        delta_path = root / _FEATURE_DELTA_REL
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        delta_path.write_text(content, encoding="utf-8")

    def _observed(self) -> str:
        return (
            f"surviving={self._surviving!r}; decision=({self._decision_action!r}, "
            f"{self._decision_reason!r}); project_root={self._project_root!r}"
        )
