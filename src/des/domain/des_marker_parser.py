"""DES marker parser domain logic.

Pure business rule for detecting and parsing DES HTML comment markers
in Task prompts. No I/O dependencies.

Replaces inline regex in claude_code_hook_adapter.handle_pre_tool_use()
(lines 123-134).

Marker formats:
  <!-- DES-VALIDATION : required -->
  <!-- DES-MODE : orchestrator -->
  <!-- DES-PROJECT-ID : my-project -->
  <!-- DES-STEP-ID : 01-01 -->
  <!-- DES-PROJECT-ROOT : /abs/path/to/worktree -->

atdd_pure dispatch markers (U0 / ADR-030 D8):
  <!-- DES-MODE : atdd_pure -->
  <!-- DES-PHASE : A_GREEN_ATS -->
  <!-- DES-SLICE : slice-01 -->
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from des.domain.atdd_pure_phases import (
    FEATURE_END_PHASES as _FEATURE_END_PHASES,
)
from des.domain.atdd_pure_phases import (
    LEGACY_PHASE_ALIASES,
    ATDDPurePhase,
)


def _normalise_marker_value(value: str) -> str:
    """Normalise a marker value: lowercase + dash/underscore unified.

    `atdd-pure` and `atdd_pure`, `a_green_ats` and `A_GREEN_ATS` are the same
    domain value cosmetically off. Normalisation collapses case and dash so the
    parser accepts either spelling. The canonical form is lowercase with
    underscores.
    """
    return value.strip().lower().replace("-", "_")


# The closed ATDD-pure phase vocabulary, normalised, for membership validation.
#
# Each normalised marker token maps to the recognised phase value, preserving
# the ORIGINAL word. A canonical member maps to itself; a retired legacy phase
# word (A_GREEN_ATS, B_COVERAGE_CLEANUP, E_BATCH_REFACTOR, F_FINAL_REVIEW,
# G_COMMIT) is recognised under its original spelling (lossless replay across the
# 7→3 reduction, fix-atdd-pure-spine-phase-count-reduction slice-02), so a
# returning agent that still speaks the old word is recognised as a valid
# dispatch. The original word is PRESERVED (not collapsed to canonical) because
# the SubagentStop handler routes U2 (per-slice commit) vs U4 (feature-end) on
# the exact word -- the legacy→canonical collapse for an operator query lives in
# ``atdd_pure_phases.resolve_phase`` (the resolver CLI), a separate read path.
# The retired routing marker D_GAP_ROUTING (alias value None) is NOT a phase
# marker -- it is omitted here so it parses as out-of-vocabulary.
_NORMALISED_PHASE_BY_TOKEN: dict[str, str] = {
    _normalise_marker_value(phase.value): phase.value for phase in ATDDPurePhase
}
_NORMALISED_PHASE_BY_TOKEN.update(
    {
        _normalise_marker_value(token): token
        for token, canonical in LEGACY_PHASE_ALIASES.items()
        if canonical is not None
    }
)

# Anchored carpaccio slice shape: `slice-` followed by one or more digits, and
# NOTHING else. `slice1` (no dash) and `slice-3-->` (garbled tail) fail.
_SLICE_SHAPE = re.compile(r"slice-\d+")

# The feature-end-cycle dispatch scope literal (ADR-028 D6, Option A). The
# `DES-SLICE` marker carries either a `slice-\d+` per-slice scope or this exact
# literal -- a closed two-member union, nothing else.
_FEATURE_END_SCOPE = "feature-end"

# The closed set of feature-end-cycle phases (ADR-028 D6) — imported from the
# phase-identity SSOT (``atdd_pure_phases.FEATURE_END_PHASES``) rather than
# restated here. A dispatch of one of these phases is, by definition, NOT
# per-slice; its only coherent scope is `feature-end`. The remaining phases are
# per-slice phases whose only coherent scope is a `slice-\d+` value. The
# canonical per-slice commit phase D_REFACTOR_COMMIT is NOT a feature-end phase
# (ADR-028 D6 runs it once per slice). The group carries the legacy
# E_BATCH_REFACTOR / F_FINAL_REVIEW replay words plus the per-FEATURE D_DISTILL
# routing node (oss-hook-side-phase-injection slice-01) — see the SSOT module.


@dataclass(frozen=True)
class DesMarkers:
    """Parsed DES markers from a Task prompt.

    Attributes:
        is_des_task: True if prompt contains DES-VALIDATION: required marker
        is_orchestrator_mode: True if the DES-MODE marker value is orchestrator
        project_id: Value of DES-PROJECT-ID marker, or None
        step_id: Value of DES-STEP-ID marker, or None
        project_root: Value of DES-PROJECT-ROOT marker, or None. Carries the
            worktree-rooted project path so hooks can resolve execution-log
            against the correct repo when the orchestrator's CWD differs
            from the executing worktree (Rex RCA F-DES-WORKTREE-EXECUTION-
            LOG-RESOLUTION). Adapter-layer validation is required before use.
        mode: Normalised DES-MODE marker value (e.g. "orchestrator",
            "atdd_pure"), or None when the marker is absent.
        atdd_pure_phase: The canonical ATDDPurePhase value when the DES-PHASE
            marker carries a valid in-vocabulary phase, else None (absent or
            out-of-vocabulary).
        slice_id: The DES-SLICE marker value when it is a well-formed dispatch
            scope -- either an anchored slice-\\d+ value or the feature-end
            literal -- else None (absent or malformed). Despite the field name,
            the value is a dispatch *scope*; use `is_feature_end` rather than
            string-matching the literal.
    """

    is_des_task: bool
    is_orchestrator_mode: bool
    project_id: str | None = None
    step_id: str | None = None
    project_root: str | None = None
    # --- atdd_pure dispatch marker set (U0 / ADR-030 D8 -- hg-slice-00) -------
    mode: str | None = None
    atdd_pure_phase: str | None = None
    slice_id: str | None = None

    @property
    def is_feature_end(self) -> bool:
        """True when the DES-SLICE scope is the feature-end-cycle literal.

        Downstream consumers read this derived property instead of
        string-matching the `feature-end` literal -- the closed-set check stays
        in one place (ADR-028 D6, Option A mitigation).
        """
        return self.slice_id == _FEATURE_END_SCOPE


class DesMarkerParser:
    """Parses DES HTML comment markers from Task prompts.

    This is a stateless parser with no I/O dependencies.
    All patterns are compiled once at class level for efficiency.
    """

    _VALIDATION_PATTERN = re.compile(r"<!--\s*DES-VALIDATION\s*:\s*required\s*-->")
    _MODE_PATTERN = re.compile(r"<!--\s*DES-MODE\s*:\s*(\S+)\s*-->")
    _PHASE_PATTERN = re.compile(r"<!--\s*DES-PHASE\s*:\s*(\S+)\s*-->")
    _SLICE_PATTERN = re.compile(r"<!--\s*DES-SLICE\s*:\s*(\S+)\s*-->")
    _PROJECT_ID_PATTERN = re.compile(r"<!--\s*DES-PROJECT-ID\s*:\s*(\S+)\s*-->")
    _STEP_ID_PATTERN = re.compile(r"<!--\s*DES-STEP-ID\s*:\s*(\S+)\s*-->")
    _PROJECT_ROOT_PATTERN = re.compile(r"<!--\s*DES-PROJECT-ROOT\s*:\s*(\S+)\s*-->")

    def parse(self, prompt: str) -> DesMarkers:
        """Parse DES markers from a Task prompt string.

        Args:
            prompt: Full Task prompt text

        Returns:
            DesMarkers with detected marker values
        """
        is_des_task = bool(self._VALIDATION_PATTERN.search(prompt))

        mode = self._parse_mode(prompt)

        project_id_match = self._PROJECT_ID_PATTERN.search(prompt)
        project_id = project_id_match.group(1) if project_id_match else None

        step_id_match = self._STEP_ID_PATTERN.search(prompt)
        step_id = step_id_match.group(1) if step_id_match else None

        project_root_match = self._PROJECT_ROOT_PATTERN.search(prompt)
        project_root = project_root_match.group(1) if project_root_match else None

        return DesMarkers(
            is_des_task=is_des_task,
            is_orchestrator_mode=mode == "orchestrator",
            project_id=project_id,
            step_id=step_id,
            project_root=project_root,
            mode=mode,
            atdd_pure_phase=self._parse_phase(prompt),
            slice_id=self._parse_slice(prompt),
        )

    def _parse_mode(self, prompt: str) -> str | None:
        """Normalised DES-MODE value, or None when the marker is absent."""
        match = self._MODE_PATTERN.search(prompt)
        if match is None:
            return None
        return _normalise_marker_value(match.group(1))

    def _parse_phase(self, prompt: str) -> str | None:
        """Canonical ATDDPurePhase value, or None when absent / out-of-vocabulary."""
        match = self._PHASE_PATTERN.search(prompt)
        if match is None:
            return None
        return _NORMALISED_PHASE_BY_TOKEN.get(_normalise_marker_value(match.group(1)))

    def _parse_slice(self, prompt: str) -> str | None:
        """DES-SLICE value when it is a well-formed dispatch scope, else None.

        The scope is a closed two-member union (ADR-028 D6, Option A): an
        anchored `slice-\\d+` per-slice value, OR the exact `feature-end`
        literal. Anything outside the closed set -- `slice1`, a garbled
        `slice-3-->` tail -- yields None, keeping the unbounded-scope bug class
        non-representable.
        """
        match = self._SLICE_PATTERN.search(prompt)
        if match is None:
            return None
        token = match.group(1)
        if token == _FEATURE_END_SCOPE:
            return token
        return token if _SLICE_SHAPE.fullmatch(token) else None


# ---------------------------------------------------------------------------
# atdd_pure dispatch recognition (U0 / ADR-030 D8 -- hg-slice-00)
#
# The recognition substrate the U1-U4 hook intercepts key on. Three-way
# (absent / valid / defective) classification of a parsed marker set, plus the
# missing-marker name the /nw-deliver phase-entry diagnostic consumes.
# ---------------------------------------------------------------------------


def classify_atdd_pure_dispatch(markers: DesMarkers) -> str:
    """Classify a parsed marker set as 'absent' / 'valid' / 'defective'.

    M3/M14 contract:
      * DES-MODE:atdd_pure absent            -> 'absent'  (a classic dispatch)
      * mode atdd_pure + valid phase + scope
        + a COHERENT (phase, scope) pair     -> 'valid'
      * mode atdd_pure + any marker missing/
        malformed/out-of-vocabulary, OR an
        incoherent (phase, scope) pair       -> 'defective'

    Closed-world cross-field invariant (ADR-028 D6): a feature-end-cycle phase
    (E_BATCH_REFACTOR / F_FINAL_REVIEW) is per-feature, so its only coherent
    scope is `feature-end`; every other phase -- including G_COMMIT, which
    ADR-028 D6 runs once per slice -- is per-slice, so its only coherent scope
    is a `slice-\\d+` value. The two fields must agree --
    `phase in feature-end-phases  XOR  scope == feature-end` -- neither
    half-valid combination is representable as 'valid'.
    """
    if markers.mode != "atdd_pure":
        return "absent"
    if markers.atdd_pure_phase is None or markers.slice_id is None:
        return "defective"
    phase_is_feature_end = markers.atdd_pure_phase in _FEATURE_END_PHASES
    if phase_is_feature_end != markers.is_feature_end:
        return "defective"
    return "valid"


def atdd_pure_missing_marker(markers: DesMarkers) -> str | None:
    """Name the marker that makes an atdd_pure dispatch defective, or None.

    Returns one of 'des-mode' / 'des-phase' / 'des-slice' when the corresponding
    marker is absent/malformed/invalid, and None when the dispatch is a valid
    atdd_pure dispatch or a classic one. The /nw-deliver phase-entry diagnostic
    consumes this to name its refusal.
    """
    if markers.mode != "atdd_pure":
        return None
    if markers.atdd_pure_phase is None:
        return "des-phase"
    if markers.slice_id is None:
        return "des-slice"
    return None
