"""Marker Completeness Policy - validates DES marker completeness.

Pure domain policy that ensures when DES-VALIDATION is present,
the required identifiers (DES-PROJECT-ID, DES-STEP-ID) are also present.
Prevents tasks from proceeding with null identifiers that break
downstream services (SubagentStop cannot locate execution log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from des.domain.des_marker_parser import dispatch_is_phaseless


if TYPE_CHECKING:
    from des.domain.des_marker_parser import DesMarkers


@dataclass(frozen=True)
class CompletenessResult:
    """Result of a marker completeness validation.

    Attributes:
        is_valid: True if markers are complete
        reason: Block reason if invalid, None otherwise
        recovery_suggestions: Actionable steps to fix the block
    """

    is_valid: bool
    reason: str | None = None
    recovery_suggestions: list[str] = field(default_factory=list)


class MarkerCompletenessPolicy:
    """Validates that DES markers are complete when present.

    Business rules:
    1. Non-DES tasks always valid (no markers to check)
    2. DES tasks require DES-PROJECT-ID
    3. classic DES tasks require DES-STEP-ID (unless orchestrator mode)
    4. atdd_pure DES tasks require DES-PHASE + DES-SLICE instead of DES-STEP-ID
       (the marker-set completeness contract is mode-aware — T-B / F-08 G-2;
       an atdd_pure dispatch is roadmap-free and carries no step-id)
    """

    def validate(self, markers: DesMarkers) -> CompletenessResult:
        """Validate marker completeness (mode-aware)."""
        if not markers.is_des_task:
            return CompletenessResult(is_valid=True)

        if markers.mode == "atdd_pure":
            return self._validate_atdd_pure(markers)
        return self._validate_classic(markers)

    def _validate_classic(self, markers: DesMarkers) -> CompletenessResult:
        """Classic dispatch completeness — DES-PROJECT-ID + DES-STEP-ID."""
        missing = []
        if not markers.project_id:
            missing.append("DES-PROJECT-ID")
        if not markers.step_id and not markers.is_orchestrator_mode:
            missing.append("DES-STEP-ID")

        return self._result_for(
            missing,
            recovery_lead=(
                "GENERATE the dispatch -- `des dispatch` emits these markers for "
                "you. This prompt declares the DEPRECATED classic mode; new work "
                "runs atdd_pure (`des dispatch --project-id <id> --slice "
                "<slice-NN> --phase <phase>`, the default). If you hand-write a "
                "classic prompt anyway, it needs:"
            ),
            marker_template_lines=(
                "<!-- DES-PROJECT-ID : {project-id} -->",
                "<!-- DES-STEP-ID : {step-id} -->",
            ),
        )

    def _validate_atdd_pure(self, markers: DesMarkers) -> CompletenessResult:
        """atdd_pure dispatch completeness — DES-PROJECT-ID + DES-PHASE + DES-SLICE.

        A phaseless dispatch (``dispatch_is_phaseless`` — the ONE predicate
        every validity-deciding locus consults, fix-dispatch-validity-ssot)
        declares no DES-PHASE: a ``PHASELESS_LANES`` lane (charter authoring
        is not one of the 3 canonical DELIVER phases,
        fix-po-charter-dispatch-marker-lane) or an authoring wave (discuss /
        design / devops / distill run no ``ATDDPurePhase`` machinery) both
        omit the phase marker instead of borrowing an unrelated one. Every
        OTHER marker is still required — the vocabulary widens, the
        enforcement does not weaken. Combining a phaseless dispatch with an
        EXPLICIT DES-PHASE is the self-contradictory inverse -- rejected
        outright, mirroring ``classify_atdd_pure_dispatch``'s 'defective'.
        """
        phaseless = dispatch_is_phaseless(
            lane=markers.lane, declared_wave=markers.declared_wave
        )
        if phaseless and markers.atdd_pure_phase is not None:
            return CompletenessResult(
                is_valid=False,
                reason=(
                    "DES_MARKERS_INCOHERENT: DES-PHASE present on a "
                    "phaseless dispatch (phaseless lane or authoring wave)"
                ),
                recovery_suggestions=[
                    "Drop --phase -- a phaseless lane/wave declares no "
                    "ATDDPurePhase by construction; do not borrow one from "
                    "a different role.",
                ],
            )

        missing = []
        if not markers.project_id:
            missing.append("DES-PROJECT-ID")
        if not markers.atdd_pure_phase and not phaseless:
            missing.append("DES-PHASE")
        if not markers.slice_id:
            missing.append("DES-SLICE")

        return self._result_for(
            missing,
            recovery_lead=(
                "GENERATE the dispatch -- `des dispatch --mode atdd_pure "
                "--project-id <id> --slice <slice-NN> --phase <phase>` emits these "
                "markers for you (add `--lane bugfix --defect <d> "
                "--regression-test <path>` for a single-slice bugfix; the lane "
                "markers and justification are generated too). If you hand-write "
                "the prompt instead, it needs:"
            ),
            marker_template_lines=(
                "<!-- DES-PROJECT-ID : {project-id} -->",
                "<!-- DES-PHASE : {phase} -->",
                "<!-- DES-SLICE : {slice-NN} -->",
            ),
        )

    @staticmethod
    def _result_for(
        missing: list[str],
        *,
        recovery_lead: str,
        marker_template_lines: tuple[str, ...],
    ) -> CompletenessResult:
        """Build the CompletenessResult for a checked marker set.

        Centralises the valid/invalid branch shared by the classic and
        atdd_pure completeness checks: an empty ``missing`` list is valid;
        otherwise the same DES_MARKERS_INCOMPLETE reason and recovery
        scaffold is produced, parametrised by the mode-specific lead line
        and marker template lines.
        """
        if not missing:
            return CompletenessResult(is_valid=True)

        return CompletenessResult(
            is_valid=False,
            reason=f"DES_MARKERS_INCOMPLETE: {', '.join(missing)} missing",
            recovery_suggestions=[
                recovery_lead,
                *marker_template_lines,
                "Read ~/.claude/skills/nw-execute/SKILL.md for the full template.",
            ],
        )
