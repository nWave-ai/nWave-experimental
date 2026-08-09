"""DES marker parser domain logic.

Pure business rule for detecting and parsing DES HTML comment markers
in Task prompts. No I/O dependencies.

Replaces inline regex in claude_code_hook_adapter.handle_pre_tool_use()
(lines 123-134).

Marker formats:
  <!-- DES-VALIDATION : required -->
  <!-- DES-MODE : atdd_pure -->
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
from des.domain.lane_profile import PHASELESS_LANES
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES


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

# Anchored carpaccio slice shape: `slice-<digits>` with an OPTIONAL single
# trailing lowercase letter (the @coupled-split sub-slice convention, e.g.
# `slice-04a`), mirroring carpaccio's `_SLICE_ID_RE` (src/des/cli/carpaccio_format.py).
# `slice1` (no dash), `slice-3-->` (garbled tail), `slice-04ab` (two letters),
# and `slice-04A` (uppercase) fail.
_SLICE_SHAPE = re.compile(r"slice-\d+[a-z]?")

# Any DES marker KEY in either spelling -- the HTML-comment form
# (``<!-- DES-VALIDATION : required -->``) the orchestrator emits, OR the plain
# ``DES-VALIDATION: required`` line form a sub-dispatch may carry. Used by the
# wave-aware §95 hinge to tell a *markerless* in-wave child (S2 DENY) from one
# that *carries the wave's DES markers* (allowed): the discriminator is marker
# PRESENCE, not the HTML-comment ``is_des_task`` flag alone. Stays a pure
# prompt-parse concern (no I/O) -- the active wave is still never self-reported.
_DES_MARKER_KEY = re.compile(
    r"DES-(?:VALIDATION|MODE|PHASE|SLICE|PROJECT-ID|STEP-ID|PROJECT-ROOT)\s*:",
)

# The feature-end-cycle dispatch scope literal (ADR-028 D6, Option A). The
# `DES-SLICE` marker carries either a `slice-\d+` per-slice scope or this exact
# literal -- a closed two-member union, nothing else.
_FEATURE_END_SCOPE = "feature-end"

# The closed dispatch-gate class a DES-BOOTSTRAP marker may name (ADR-001 D6).
# A bootstrap marker claims a dispatch repairs a dispatch-gate G and must be
# exempted from G's OWN check only. Membership is the RARE + self-limiting
# dispatch-gate class; `feature-end-cycle-gate` is DELIBERATELY EXCLUDED
# (Critical-1: it is a standing-recurrence gate, not a rare/self-limiting
# dispatch-gate, so bootstrapping it would degrade into a standing routine
# bypass of the completion-attestation gate). An out-of-vocab gate-id is
# malformed (slice-02 fail-closed), keeping the unbounded-gate-name bug class
# non-representable -- mirrors `_parse_slice`'s closed-scope discipline.
BOOTSTRAPPABLE_GATES = frozenset(
    {
        "carpaccio-slice-gate",
        "verify-readiness-pre-dispatch",
        "verify-wave-dispatch",
    }
)

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
        is_orchestrator_mode: Always false; the former orchestrator carrier is
            retained only as untrusted historical input.
        project_id: Value of DES-PROJECT-ID marker, or None
        feature_id: Value of DES-FEATURE-ID marker, or None. The feature being
            delivered, distinct from DES-PROJECT-ID (the project-ROOT identity).
            The carpaccio resolution prefers this marker and falls back to
            project_id only when it is absent (AD-61).
        step_id: Value of DES-STEP-ID marker, or None
        project_root: Value of DES-PROJECT-ROOT marker, or None. Carries the
            worktree-rooted project path so hooks can resolve execution-log
            against the correct repo when the orchestrator's CWD differs
            from the executing worktree (Rex RCA F-DES-WORKTREE-EXECUTION-
            LOG-RESOLUTION). Adapter-layer validation is required before use.
        mode: Normalised DES-MODE marker value, or None when absent.
        atdd_pure_phase: The canonical ATDDPurePhase value when the DES-PHASE
            marker carries a valid in-vocabulary phase, else None (absent or
            out-of-vocabulary).
        slice_id: The DES-SLICE marker value when it is a well-formed dispatch
            scope -- either an anchored slice-\\d+ value or the feature-end
            literal -- else None (absent or malformed). Despite the field name,
            the value is a dispatch *scope*; use `is_feature_end` rather than
            string-matching the literal.
        declared_wave: Raw DES-WAVE marker value, or None when absent
            (slice-07d, nwave-flow-v2-enforcement -- F4 INFERRED fallback).
            Pure prompt-parse: validated at the USE site against
            ``WAVE_VOCABULARY`` (out-of-vocab == treated absent, no arm).
            NEVER the active-wave source -- ``wave`` stays reader-sourced
            (S22.7: the declaration is consumed ONLY to ARM enforcement,
            never an authorization; it can only ADD gating).
    """

    is_des_task: bool
    is_orchestrator_mode: bool
    project_id: str | None = None
    feature_id: str | None = None
    step_id: str | None = None
    project_root: str | None = None
    # --- atdd_pure dispatch marker set (U0 / ADR-030 D8 -- hg-slice-00) -------
    mode: str | None = None
    atdd_pure_phase: str | None = None
    slice_id: str | None = None
    # The raw DES-LANE marker value (e.g. "bugfix", "prefactoring", "charter"),
    # or None when absent. A PHASELESS lane (``PHASELESS_LANES`` -- the ONE
    # definition, in the lane-profile domain SSOT) declares NO DES-PHASE at all:
    # charter authoring is not one of the 3 canonical DELIVER phases
    # (fix-po-charter-dispatch-marker-lane), so its dispatch omits the phase
    # marker rather than borrowing an unrelated phase word.
    lane: str | None = None
    # has_des_markers: True when the prompt carries ANY DES marker key in EITHER
    # spelling (HTML-comment or plain ``DES-KEY: value`` line). Broader than
    # is_des_task (which keys only on the HTML-comment DES-VALIDATION marker): the
    # wave-aware hinge needs to distinguish a markerless in-wave child (S2 DENY)
    # from one that carries the wave's DES markers (allowed). A pure prompt-parse
    # output -- no I/O, nothing self-reported about the active wave.
    has_des_markers: bool = False
    # carries_validation_marker: True when the prompt carries DES-VALIDATION in
    # EITHER spelling -- the HTML-comment `<!-- DES-VALIDATION : required -->` OR
    # the plain `DES-VALIDATION: required` line a sub-dispatch may carry. is_des_task
    # keys ONLY on the HTML-comment form; this broader field backs the
    # `carries_des_validation` property (ADR-001 Amendment 1) so a plain-line-validated
    # dispatch is recognized as complete (not a partial-context bypass). Pure
    # prompt-parse output -- no I/O.
    carries_validation_marker: bool = False
    # --- declared wave (slice-07d, nwave-flow-v2-enforcement) -----------------
    # The raw `<!-- DES-WAVE: <wave> -->` value; vocabulary-validated at the
    # USE site (WaveActivationService.arm_inferred), never trusted as the
    # active wave.
    declared_wave: str | None = None
    # --- wave-active state (slice-04, nwave-flow-v2-enforcement) --------------
    # The ACTIVE wave from WaveActiveReader; None <=> NoWaveActive (S1). This is
    # NEVER set by DesMarkerParser.parse (the parser stays a pure prompt-parser
    # with no I/O -- wave is never self-reported). PreToolUseService reads the
    # WaveActiveReader port and composes this field onto the parsed markers.
    wave: str | None = None
    # --- DES-BOOTSTRAP dispatch-gate exemption markers (ADR-001) --------------
    # The gate-id a DES-BOOTSTRAP marker names (the dispatch-gate the dispatch
    # claims to repair, to be exempted from its OWN check only) + the mandatory
    # justification. Two SEPARATE HTML-comment markers (DES-LANE shape) so an
    # embedded colon in the justification is unambiguous. Both None when the
    # dispatch carries no DES-BOOTSTRAP marker (the ordinary case). Pure
    # prompt-parse output -- validated at the USE site via `classify_bootstrap`.
    bootstrap_gate: str | None = None
    bootstrap_justification: str | None = None
    # --- DES-SWARM-ISOLATED-DISPATCH exemption marker (swarm-parallel-delivery) ---
    # The free-text justification a swarm-isolated dispatch carries to exempt
    # ONLY the M8 carpaccio-order check: a slice N>1 developed in an isolated
    # parallel worktree does not see the predecessor's SliceCommitVerified
    # record until a later in-order integration folds it onto the shared line,
    # where the true ordering is still guaranteed. Distinct from DES-BOOTSTRAP:
    # this marker names NO gate-id (it exempts exactly one gate) and carries NO
    # reuse cap (it is ROUTINE for every slice N>1 of a swarmed feature, not a
    # rare self-limiting exception). None when the dispatch carries no such
    # marker (the ordinary case). Validated at the USE site by truthiness --
    # an empty justification fails CLOSED (the order check blocks as before).
    swarm_isolated_justification: str | None = None
    # --- DES-AT-KIND (fix-distill-exit-mechanical-seal-route slice-01) --------
    # Raw DES-AT-KIND marker value (e.g. "pytest-regression", "gherkin"), or
    # None when the marker is absent. Mirrors the grammar
    # `carpaccio_intercept.py::_parse_at_kind_from_prompt` already parses from
    # a dispatch prompt -- this field parses it from a RETURNING agent's own
    # transcript instead (a different call site, same marker vocabulary).
    at_kind: str | None = None

    @property
    def is_feature_end(self) -> bool:
        """True when the DES-SLICE scope is the feature-end-cycle literal.

        Downstream consumers read this derived property instead of
        string-matching the `feature-end` literal -- the closed-set check stays
        in one place (ADR-028 D6, Option A mitigation).
        """
        return self.slice_id == _FEATURE_END_SCOPE

    @property
    def carries_des_validation(self) -> bool:
        """True when the dispatch carries the required DES-VALIDATION marker in
        EITHER form -- the HTML-comment ``<!-- DES-VALIDATION : required -->`` OR the
        plain ``DES-VALIDATION: required`` line (ADR-001 Amendment 1).

        ``is_des_task`` keys only on the HTML-comment form; OR-ing it here keeps the
        invariant ``is_des_task ⟹ carries_des_validation`` even for ``DesMarkers``
        instances constructed directly (where ``carries_validation_marker`` defaults
        False). A complete dispatch -- validated in either spelling -- is excluded
        from ``carries_partial_wave_context`` so a legitimate plain-line-validated
        child is NOT false-positive-flagged as a wave-bypass. Pure derived property.
        """
        return self.is_des_task or self.carries_validation_marker

    @property
    def carries_partial_wave_context(self) -> bool:
        """True when the prompt positively signals a wave-owned child that dropped
        its required marker (ADR-001 positive-bypass-signal predicate).

        The prompt carries at least one DES-family marker -- any ``DES-*`` key
        INCLUDING ``DES-WAVE`` -- but NOT the required ``DES-VALIDATION`` marker in
        EITHER form. OR-ing ``declared_wave`` counts a ``DES-WAVE``-only child as wave
        context (closing the ``_DES_MARKER_KEY`` collision with no regex change); the
        ``not carries_des_validation`` clause (ADR-001 Amendment 1, superseding the
        HTML-comment-only ``not is_des_task``) excludes a complete DES dispatch
        validated in EITHER spelling. Pure derived property -- no I/O, the active
        wave is never read here (it still comes only from the floor reader). Mirrors
        ``is_feature_end``.
        """
        return (
            self.has_des_markers or self.declared_wave is not None
        ) and not self.carries_des_validation


class DesMarkerParser:
    """Parses DES HTML comment markers from Task prompts.

    This is a stateless parser with no I/O dependencies.
    All patterns are compiled once at class level for efficiency.
    """

    _VALIDATION_PATTERN = re.compile(r"<!--\s*DES-VALIDATION\s*:\s*required\s*-->")
    # ADR-001 Amendment 1: DES-VALIDATION presence in EITHER spelling -- the
    # HTML-comment form (matched as a substring) OR the plain `DES-VALIDATION:
    # required` line a sub-dispatch may carry. Backs `carries_des_validation`.
    _VALIDATION_PRESENCE_PATTERN = re.compile(r"DES-VALIDATION\s*:\s*required")
    _MODE_PATTERN = re.compile(r"<!--\s*DES-MODE\s*:\s*(\S+)\s*-->")
    _PHASE_PATTERN = re.compile(r"<!--\s*DES-PHASE\s*:\s*(\S+)\s*-->")
    _SLICE_PATTERN = re.compile(r"<!--\s*DES-SLICE\s*:\s*(\S+)\s*-->")
    _PROJECT_ID_PATTERN = re.compile(r"<!--\s*DES-PROJECT-ID\s*:\s*(\S+)\s*-->")
    _FEATURE_ID_PATTERN = re.compile(r"<!--\s*DES-FEATURE-ID\s*:\s*(\S+)\s*-->")
    _STEP_ID_PATTERN = re.compile(r"<!--\s*DES-STEP-ID\s*:\s*(\S+)\s*-->")
    _PROJECT_ROOT_PATTERN = re.compile(r"<!--\s*DES-PROJECT-ROOT\s*:\s*(\S+)\s*-->")
    # slice-07d (F4): the wave-bearing declaration a dispatch may carry.
    _WAVE_PATTERN = re.compile(r"<!--\s*DES-WAVE\s*:\s*(\S+)\s*-->")
    # ADR-001: the two DES-BOOTSTRAP markers (DES-LANE two-comment shape so a
    # colon in the justification text is unambiguous). The gate-id is a single
    # token (`\S+`); the justification is free text captured non-greedily up to
    # the closing `-->`. `DES-BOOTSTRAP-JUSTIFICATION` cannot false-match the
    # gate pattern -- after `DES-BOOTSTRAP` the gate pattern requires `\s*:`, but
    # the justification line has `-JUSTIFICATION` there instead.
    _BOOTSTRAP_PATTERN = re.compile(r"<!--\s*DES-BOOTSTRAP\s*:\s*(\S+)\s*-->")
    # DES-SWARM-ISOLATED-DISPATCH carries ONLY a free-text justification (no
    # gate-id): it exempts exactly the M8 order check. Same non-greedy capture
    # shape as the bootstrap justification, so an embedded colon is unambiguous;
    # a whitespace-only/empty value does not match (`.+?` requires >=1 char),
    # surfacing as None -> the order check blocks (fail-closed).
    _SWARM_ISOLATED_PATTERN = re.compile(
        r"<!--\s*DES-SWARM-ISOLATED-DISPATCH\s*:\s*(.+?)\s*-->"
    )
    _BOOTSTRAP_JUSTIFICATION_PATTERN = re.compile(
        r"<!--\s*DES-BOOTSTRAP-JUSTIFICATION\s*:\s*(.+?)\s*-->"
    )
    # fix-distill-exit-mechanical-seal-route slice-01: the SAME grammar
    # `carpaccio_intercept.py::_DES_AT_KIND_PATTERN` already parses from a
    # dispatch PROMPT (emitted by `dispatch.py:180`) -- mirrored here (one
    # grammar, two independent parse sites) so a RETURNING agent's own
    # transcript can carry the marker back. Raw value, no normalisation
    # (mirrors `_parse_at_kind_from_prompt`'s un-normalised `group(1)`).
    _AT_KIND_PATTERN = re.compile(r"<!--\s*DES-AT-KIND\s*:\s*(\S+)\s*-->")
    # fix-po-charter-dispatch-marker-lane: the DES-LANE marker (the SAME grammar
    # `atdd_pure_prompt_validator._DES_LANE_MARKER` already reads from a prompt).
    _LANE_PATTERN = re.compile(r"<!--\s*DES-LANE\s*:\s*(\S+)\s*-->")

    def parse(self, prompt: str) -> DesMarkers:
        """Parse DES markers from a Task prompt string.

        Args:
            prompt: Full Task prompt text

        Returns:
            DesMarkers with detected marker values
        """
        is_des_task = bool(self._VALIDATION_PATTERN.search(prompt))
        carries_validation_marker = bool(
            self._VALIDATION_PRESENCE_PATTERN.search(prompt)
        )

        mode = self._parse_mode(prompt)

        project_id_match = self._PROJECT_ID_PATTERN.search(prompt)
        project_id = project_id_match.group(1) if project_id_match else None

        feature_id_match = self._FEATURE_ID_PATTERN.search(prompt)
        feature_id = feature_id_match.group(1) if feature_id_match else None

        step_id_match = self._STEP_ID_PATTERN.search(prompt)
        step_id = step_id_match.group(1) if step_id_match else None

        project_root_match = self._PROJECT_ROOT_PATTERN.search(prompt)
        project_root = project_root_match.group(1) if project_root_match else None

        declared_wave_match = self._WAVE_PATTERN.search(prompt)
        declared_wave = declared_wave_match.group(1) if declared_wave_match else None

        bootstrap_match = self._BOOTSTRAP_PATTERN.search(prompt)
        bootstrap_gate = bootstrap_match.group(1) if bootstrap_match else None
        bootstrap_justification_match = self._BOOTSTRAP_JUSTIFICATION_PATTERN.search(
            prompt
        )
        bootstrap_justification = (
            bootstrap_justification_match.group(1).strip()
            if bootstrap_justification_match
            else None
        )

        swarm_isolated_match = self._SWARM_ISOLATED_PATTERN.search(prompt)
        swarm_isolated_justification = (
            swarm_isolated_match.group(1).strip() if swarm_isolated_match else None
        )

        at_kind_match = self._AT_KIND_PATTERN.search(prompt)
        at_kind = at_kind_match.group(1) if at_kind_match else None

        lane_match = self._LANE_PATTERN.search(prompt)
        lane = lane_match.group(1) if lane_match else None

        return DesMarkers(
            is_des_task=is_des_task,
            is_orchestrator_mode=False,
            project_id=project_id,
            feature_id=feature_id,
            step_id=step_id,
            project_root=project_root,
            mode=mode,
            atdd_pure_phase=self._parse_phase(prompt),
            slice_id=self._parse_slice(prompt),
            lane=lane,
            has_des_markers=bool(_DES_MARKER_KEY.search(prompt)),
            carries_validation_marker=carries_validation_marker,
            declared_wave=declared_wave,
            bootstrap_gate=bootstrap_gate,
            bootstrap_justification=bootstrap_justification,
            swarm_isolated_justification=swarm_isolated_justification,
            at_kind=at_kind,
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
        anchored `slice-<digits>` per-slice value (with an optional single
        trailing lowercase letter for the @coupled-split sub-slice convention,
        e.g. `slice-04a`), OR the exact `feature-end` literal. Anything
        outside the closed set -- `slice1`, a garbled `slice-3-->` tail,
        `slice-04ab`, `slice-04A` -- yields None, keeping the unbounded-scope
        bug class non-representable.
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


def dispatch_is_phaseless(*, lane: str | None, declared_wave: str | None) -> bool:
    """The ONE predicate answering "is this dispatch phaseless by construction?"

    fix-dispatch-validity-ssot: three independent loci (the ``des dispatch``
    generator, this module's ``classify_atdd_pure_dispatch`` /
    ``atdd_pure_missing_marker``, and ``MarkerCompletenessPolicy``) each used
    to carry their OWN copy of this rule -- and one of them (the completeness
    policy) never learned the wave half, so the SAME dispatch was valid to
    two loci and invalid to a third. This function is the single answer every
    locus now CONSULTS instead of re-deriving.

    Two independent axes union into "phaseless": a ``PHASELESS_LANES`` lane
    (a non-code-facing cross-wave-child dispatch, e.g. ``charter``) OR an
    authoring wave (``WAVE_DISPATCH_PROFILES[declared_wave].runs_tests is
    False`` -- discuss / design / devops / distill run no ``ATDDPurePhase``
    machinery at all). Always derived from the queryable profile data, never
    a hand-written wave/lane-name list, so the exemption cannot silently go
    stale as either vocabulary grows. An unrecognised or absent
    ``declared_wave`` falls through to False -- fail-closed, phase stays
    required.
    """
    if lane in PHASELESS_LANES:
        return True
    if declared_wave is None:
        return False
    profile = WAVE_DISPATCH_PROFILES.get(declared_wave)
    return profile is not None and not profile.runs_tests


def classify_atdd_pure_dispatch(markers: DesMarkers) -> str:
    """Classify a parsed marker set as 'absent' / 'valid' / 'defective'.

    M3/M14 contract:
      * DES-MODE:atdd_pure absent            -> 'absent'  (unresolved)
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
    if markers.mode == "classic":
        return "defective"
    if markers.mode != "atdd_pure":
        return "absent"
    if markers.slice_id is None:
        return "defective"
    # A PHASELESS lane (fix-po-charter-dispatch-marker-lane) declares NO
    # DES-PHASE: charter authoring is not one of the 3 canonical DELIVER
    # phases, so the honest declaration omits the phase word rather than
    # BORROWING an unrelated one. It is coherent WITHOUT a phase -- and the
    # phase/scope XOR below (a phase-keyed invariant) simply does not apply.
    # This is the ONLY relaxation: a phaseless-lane dispatch still needs its
    # DES-MODE + DES-SLICE + (via the completeness policy) DES-PROJECT-ID, so a
    # genuinely defective dispatch is refused exactly as before. An authoring
    # wave (discuss/design/devops/distill) is phaseless BY CONSTRUCTION for the
    # SAME reason -- ``ATDDPurePhase`` stays DELIVER-carpaccio-scoped -- so it
    # gets the identical relaxation via the single ``dispatch_is_phaseless``
    # predicate (fix-dispatch-validity-ssot), never a second hand-written
    # lane-shaped list.
    if dispatch_is_phaseless(lane=markers.lane, declared_wave=markers.declared_wave):
        return "defective" if markers.atdd_pure_phase is not None else "valid"
    if markers.atdd_pure_phase is None:
        return "defective"
    phase_is_feature_end = markers.atdd_pure_phase in _FEATURE_END_PHASES
    if phase_is_feature_end != markers.is_feature_end:
        return "defective"
    return "valid"


def atdd_pure_missing_marker(markers: DesMarkers) -> str | None:
    """Name the marker that makes an atdd_pure dispatch defective, or None.

    Returns one of 'des-mode' / 'des-phase' / 'des-slice' when the corresponding
    marker is absent/malformed/invalid, and None when the dispatch is a valid
    atdd_pure dispatch. Any legacy or absent carrier is unresolved. The
    /nw-deliver phase-entry diagnostic
    consumes this to name its refusal.
    """
    if markers.mode != "atdd_pure":
        return "des-mode"
    if markers.atdd_pure_phase is None and not dispatch_is_phaseless(
        lane=markers.lane, declared_wave=markers.declared_wave
    ):
        return "des-phase"
    if markers.slice_id is None:
        return "des-slice"
    return None


# ---------------------------------------------------------------------------
# refactor / find dispatch recognition (D8, slice-03 -- des-refactor-fixer-swarm)
#
# __SCAFFOLD__ (Mandate-7 RED-ready). The fixer/finder swarm WIDENS the
# ALREADY-SHIPPED DES-MODE vocabulary with two sibling classifiers mirroring
# ``classify_atdd_pure_dispatch`` -- ZERO new marker grammar (``_MODE_PATTERN``
# already parses any mode value). A ``DES-MODE: refactor`` (resp. ``find``)
# dispatch is spine-recognized by a non-``absent`` / non-``defective`` verdict,
# so it is NOT forced through the classic-dispatch completeness check a
# markerless crafter dispatch receives (feature-delta AT-11 / D8: no per-dispatch
# ``DES-EXEMPT`` justification). The two-way rule A_GREEN must implement:
#   * ``markers.mode == "refactor"``  -> 'valid'   (refactor classifier)
#   * ``markers.mode == "find"``      -> 'valid'   (find classifier)
#   * any other / absent mode         -> 'absent'
# A well-formed fixer/finder dispatch is NEVER 'defective'.
#
# A_GREEN (slice-03, des-refactor-fixer-swarm) replaces the former raising
# stubs with the real two-way rule mirroring ``classify_atdd_pure_dispatch``'s
# mode check: a well-formed fixer/finder dispatch is NEVER 'defective', only
# 'valid' (own mode matches) or 'absent' (any other/absent mode).


def classify_refactor_dispatch(markers: DesMarkers) -> str:
    """Classify a parsed marker set: 'valid' for a refactor-mode dispatch, else
    'absent'."""
    return "valid" if markers.mode == "refactor" else "absent"


def classify_find_dispatch(markers: DesMarkers) -> str:
    """Classify a parsed marker set: 'valid' for a find-mode dispatch, else
    'absent'."""
    return "valid" if markers.mode == "find" else "absent"


def classify_bootstrap(markers: DesMarkers, firing_gate_id: str) -> str:
    """Classify a DES-BOOTSTRAP marker against the CURRENTLY-firing gate.

    Pure function (return-only, zero I/O): marker set + the gate this `_invoke`
    call is currently evaluating in, verdict out. The slice-01 verdict set
    (ADR-001 D4, Handoff-to-DISTILL (a)/(c)):

      * no DES-BOOTSTRAP marker                     -> 'absent-for-this-gate'
      * marker names THIS in-vocab firing gate      -> 'valid'
      * marker names a DIFFERENT in-vocab composed
        gate than THIS `_invoke` evaluates          -> 'absent-for-this-gate'

    The canonical divergence rule (Critical-2): `classify_bootstrap` runs FRESH
    per composed gate, so a marker naming gate G legitimately "does not match"
    the OTHER composed gates that fire in the same 4-gate dispatch.pre
    composition. That divergence is EXPECTED, not abuse -- it yields
    `absent-for-this-gate` (the real runner fires); the named gate is skipped
    only when ITS OWN `_invoke` fires.

    The slice-02 `malformed` verdict (ADR-001 D4, Handoff-to-DISTILL (b1)/(b2))
    is the ONLY fail-closed BLOCK case and is INTRINSIC to the marker -- decided
    independent of divergence-within-a-valid-composition:

      * gate-id NOT in `BOOTSTRAPPABLE_GATES` (out-of-vocab)  -> 'malformed'
      * missing / empty justification                         -> 'malformed'

    Both are genuine malformation, NOT the expected in-composition divergence, so
    they classify `malformed` regardless of which gate is currently firing. The
    intercept maps the single `malformed` verdict to the two DISTINCT block events
    (`BootstrapMarkerMalformed` vs `BootstrapJustificationMissing`).
    """
    if markers.bootstrap_gate is None:
        return "absent-for-this-gate"
    if markers.bootstrap_gate not in BOOTSTRAPPABLE_GATES:
        return "malformed"
    if not markers.bootstrap_justification:
        return "malformed"
    if markers.bootstrap_gate == firing_gate_id:
        return "valid"
    return "absent-for-this-gate"
