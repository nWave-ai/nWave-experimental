"""des dispatch -- render a GATE-VALID atdd_pure dispatch prompt from the
dispatch SSOT (feature ``des-dispatch-ssot-renderer``, Fase-2, the GENERATOR).

Today a human orchestrator hand-assembles the atdd_pure crafter dispatch
(marker triple + DES-PROJECT-ID + DES-WAVE + DES-LANE + the 12 mandatory
``# SECTION`` headers + a DESIGN_CONTEXT ADR citation) and gets it REJECTED
one-requirement-at-a-time by ``AtddPurePromptValidator`` (empirically: 8
rounds for FR-11's small fix). ``des dispatch`` GENERATES a dispatch that
PASSES the dispatch gates BY CONSTRUCTION -- the system produces the checked
artifact, the operator supplies only the fuzzy fills (system-pays principle,
2026-07-06).

SSOT reuse (no parallel logic):
  * section IDs (no ``--lane``) -- ``dispatch_lane_ssot._read_full_sections``
    reads ``profiles.full.sections`` DIRECTLY from
    ``nWave/dispatch/atdd_pure.yaml`` at render time.
  * section IDs (``--lane`` given) -- ``des.domain.lane_profile.LANE_PROFILES``
    (the SAME datum ``AtddPurePromptValidator`` and the readiness gate consult).
  * marker syntax -- ``nWave/dispatch/vendors.yaml`` (``claude_code`` vendor),
    read via ``des._internal.subset_parser`` (the ONLY stdlib-only YAML reader
    legal inside the bundled ``des`` module).

Design: docs/feature/des-dispatch-ssot-renderer/design/dispatch-ssot-design.md
Regression ATs: tests/des/unit/cli/test_des_dispatch_generator.py
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from des._internal import subset_parser
from des.application.dispatch_lane_ssot import _DISPATCH_YAML_PARTS, _read_full_sections
from des.cli.validate_feature_delta import (
    VERDICT_METHODOLOGY_EXEMPT,
    VERDICT_MISSING_PREFACTORING_ASSESSMENT,
    VERDICT_NO_OVERLAP_DECLARED,
    VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED,
    VERDICT_PREFACTORING_NOT_REQUIRED,
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
    validate_prefactoring_assessment_content,
    validate_reuse_analysis_content,
)
from des.cli.verify_readiness_pre_dispatch import _design_skip_witness_present
from des.domain.agent_capability import (
    ClaimRegister,
    DeclaredCapability,
    resolve_declared_capability,
)
from des.domain.atdd_pure_phases import (
    FEATURE_END_PHASES,
    FEATURE_END_RETURN_PHASE,
    ATDDPurePhase,
)
from des.domain.des_marker_parser import dispatch_is_phaseless
from des.domain.expectation_charter_mapping import (
    CharterMappingState,
    resolve_slice_charter,
)
from des.domain.lane_profile import LANE_PROFILES, PHASELESS_LANES
from des.domain.repo_path_resolver import resolve_repo_root
from des.domain.wave_active import WAVE_VOCABULARY
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES


#: Deliberate, distinguishable exit for "bad input" (missing/invalid CLI
#: argument, unreadable/malformed SSOT file) -- never a Python traceback.
_EXIT_USAGE_ERROR = 2

#: Reuse Analysis verdicts that mean the feature-delta IS readiness-ready
#: (GDP-1/2: proactive readiness ADVISORY, see `_feature_delta_readiness_
#: advisory` below) -- mirrors `verify_readiness_pre_dispatch._check_reuse_
#: first_or_design_skip`'s reuse leg, minus the design-skip-witness fallback
#: (no AT requires that leg at generation time; the readiness gate remains
#: the authority that still ALSO accepts a design-skip witness).
_REUSE_READY_VERDICTS = frozenset(
    {
        VERDICT_STRUCTURALLY_ACCEPTED,
        VERDICT_METHODOLOGY_EXEMPT,
        VERDICT_NO_OVERLAP_DECLARED,
    }
)

#: Prefactoring Assessment verdicts that mean the feature-delta IS
#: readiness-ready -- sibling of `_REUSE_READY_VERDICTS`, mirrors
#: `verify_readiness_pre_dispatch._check_prefactoring_assessment`'s clear set
#: (the scoping no-op when no `## Wave: DESIGN` section is present, plus a
#: substantive accepted assessment).
_PREFACTORING_READY_VERDICTS = frozenset(
    {
        VERDICT_PREFACTORING_NOT_REQUIRED,
        VERDICT_PREFACTORING_ASSESSMENT_ACCEPTED,
    }
)

#: Verdicts a Design-Skipped witness can still rescue -- mirrors
#: `verify_readiness_pre_dispatch._PREFACTORING_WITNESS_RESCUABLE_VERDICTS`
#: byte-for-byte: `_feature_delta_has_design_wave` matches the `## Wave:
#: DESIGN` SUBSTRING, which a Design-Skipped delta's own
#: `## Wave: DESIGN / [REF] Design Skipped` heading also satisfies, so these
#: two verdicts alone would be a false positive for a feature that
#: deliberately skipped DESIGN.
_PREFACTORING_WITNESS_RESCUABLE_VERDICTS = frozenset(
    {
        VERDICT_MISSING_PREFACTORING_ASSESSMENT,
        VERDICT_UNMOTIVATED_PREFACTORING_ASSESSMENT,
    }
)

#: The dispatch SSOT literal -- SSOT-of-SSOT is `dispatch_lane_ssot.py` (this
#: module already imports `_read_full_sections` from there); imported, never
#: redefined, so the two consumers cannot silently diverge (feature-delta:
#: fix-dispatch-ssot-consuming-repo).
_VENDORS_YAML_PARTS = ("nWave", "dispatch", "vendors.yaml")
_VENDOR_ID = "claude_code"

# nWave/dispatch/ ships as a sibling of the code root in BOTH layouts this
# module runs from: a dev checkout (src/des/cli/dispatch.py -> parents[3] ==
# checkout root) and an installed tree (lib/python/des/cli/dispatch.py ->
# parents[3] == <claude_dir>/lib). Mirrors the sibling-of-lib/python formula
# `session_start_handler.py`'s `_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR` uses for
# its own asset dir (same pattern, different parents[N] for this module's
# shallower path). Resolved fresh at import time -- never cached beyond that.
_INSTALLED_DISPATCH_ASSETS_DIR = (
    Path(__file__).resolve().parents[3] / "nWave" / "dispatch"
)

#: Fallback marker syntax -- used only if the vendors.yaml SSOT cannot be
#: read/parsed (degrade-loud path); mirrors the claude_code vendor row so a
#: transient read failure never blocks a dispatch outright.
_FALLBACK_MARKER_SYNTAX = "<!-- {key} : {value} -->"

#: Lanes whose dispatch MUST combine ``--defect`` + ``--regression-test`` into
#: one ``DES-LANE-JUSTIFICATION`` marker (mirrors
#: ``nWave/dispatch/atdd_pure.yaml:profiles.lane.bugfix.requires`` --
#: today's only lane declaring ``requires: [lane_justification]``; the
#: existing readiness gate special-cases the SAME lane by name in
#: ``verify_readiness_pre_dispatch._run_bugfix_lane``).
_LANES_REQUIRING_JUSTIFICATION = frozenset({"bugfix"})

#: The feature-end-cycle dispatch scope literal (ADR-028 D6, Option A) -- the
#: ONLY coherent ``--slice`` value for a ``FEATURE_END_PHASES`` member (e.g.
#: ``D_DISTILL``). Mirrors ``des.domain.des_marker_parser._FEATURE_END_SCOPE``.
_FEATURE_END_SCOPE = "feature-end"

#: Default AGENT_IDENTITY -- every phase not named in ``_PHASE_AGENTS`` below
#: (all current implementation phases: ``A_GREEN``, ``D_REFACTOR_COMMIT``, the
#: feature-end review return, ...) keeps naming the crafter. Mirrors ADR-025's
#: SLIM-crafter contract: the crafter implements, it never authors tests.
_DEFAULT_AGENT = "nw-software-crafter"

#: The non-code-facing examiner (Vera) -- the EXAMINE step (``C_REVIEWER_AUDIT``)
#: owner (deliver_phase_shape, velocity-v2: "cleared via an ExamineVerdict...
#: an independent execution-observation, NOT an LLM reviewer-audit",
#: ``atdd_pure_phases.py:57-59``). Her spec forbids technical/code-reasoning
#: skills; her spec also INSTRUCTS her away from source/design access -- an
#: instruction, NOT a mechanism (RCA fix-examiner-blindness-enforced: her own
#: frontmatter grants `Read` and `Bash`, so the constraint is declared, not
#: enforced; what the envelope may CLAIM about it is derived per-dispatch from
#: `resolve_declared_capability`, never asserted here).
_EXAMINER_AGENT = "nw-user-examiner"

#: The code-facing fallback for an unarmed C_REVIEWER_AUDIT slot.  A project
#: without a slice-matching charter retains the legacy AT-completeness gate;
#: the examiner is selected only when the domain resolver arms the slot.
_LEGACY_MIDDLE_SLOT_REVIEWER = "nw-acceptance-designer-reviewer"

#: The feature-end deep code review agent (ADR-027) -- the ONLY agent
#: ``F_FINAL_REVIEW`` may resolve to: a code-reading reviewer, never the
#: examiner (whose ROLE excludes reading source -- the whole epistemic value
#: of her verdict) and never the bare implementing crafter
#: (fix-dispatch-cannot-generate-feature-end-phases).
_FEATURE_END_REVIEWER_AGENT = "nw-software-crafter-reviewer"

#: Phase -> agent override map (GDP-5, the producing tool derives the correct
#: agent per phase instead of hardcoding one for every phase). ``D_DISTILL``
#: is the AT-authoring phase -- ADR-025 reserves acceptance-test authorship to
#: ``nw-acceptance-designer``; the SLIM crafter never authors tests.
#: ``C_REVIEWER_AUDIT`` is the EXAMINE step -- routed to the examiner, never
#: the crafter (Face B fix). ``F_FINAL_REVIEW`` (the feature-end LLM
#: reviewer-audit return, ``FEATURE_END_RETURN_PHASE``) routes to the
#: code-reading reviewer -- its own frontmatter names ``F_FINAL_REVIEW`` as
#: one of its two ATDD-pure review phases.
_PHASE_AGENTS: dict[str, str] = {
    ATDDPurePhase.D_DISTILL.value: "nw-acceptance-designer",
    ATDDPurePhase.C_REVIEWER_AUDIT.value: _EXAMINER_AGENT,
    ATDDPurePhase.FEATURE_END_EXAMINE.value: _EXAMINER_AGENT,
    FEATURE_END_RETURN_PHASE: _FEATURE_END_REVIEWER_AGENT,
}

#: The ONLY phases that legitimately fall back to the crafter default when
#: absent from ``_PHASE_AGENTS`` (bugfix fix-feature-end-examine-agent, Cause
#: C): the two code-facing DELIVER phases the SLIM crafter itself runs. Any
#: OTHER phase absent from both this set and ``_PHASE_AGENTS`` is a routing
#: gap, not a legitimate default -- ``_resolve_agent`` refuses it loudly
#: instead of silently handing it to the crafter (a phase absent from
#: ``_PHASE_AGENTS`` used to degrade SILENTLY toward the PERMISSIVE default,
#: which is exactly how ``FEATURE_END_EXAMINE`` reached the crafter before
#: this fix).
_PHASES_DEFAULT_TO_CRAFTER: frozenset[str] = frozenset(
    {ATDDPurePhase.A_GREEN.value, ATDDPurePhase.D_REFACTOR_COMMIT.value}
)

#: Lane -> agent override map for a cross-wave-child lane whose dispatch is
#: NOT one of the 3 canonical DELIVER phases (RCA fix-po-charter-dispatch-
#: marker-lane, Face A, §7(a)): a PO authoring an expectation charter. Widens
#: the SAME agent-resolution concept ``_PHASE_AGENTS`` already carries,
#: keyed on lane instead of phase for the phaseless lanes in
#: ``PHASELESS_LANES``.
_LANE_AGENTS: dict[str, str] = {
    "charter": "nw-product-owner",
}

#: The ``--lane`` choice set IS the ``LANE_PROFILES`` domain SSOT (which now
#: carries the phaseless ``charter`` lane too) -- one definition, no fork.
#: ``PHASELESS_LANES`` (the SAME SSOT module) names the lanes whose dispatch
#: declares NO ``DES-PHASE``; ``--phase`` stays required for every other one.
_KNOWN_LANES: frozenset[str] = frozenset(LANE_PROFILES)

#: ONE set of every NON-CODE-FACING agent this generator can dispatch (RCA
#: fix-po-charter-dispatch-marker-lane follow-up: "the cure relocated the
#: disease" -- the false phase moved out of the marker block, then the design
#: pointer relocated INTO the SKILL_LOADING/DESIGN_CONTEXT section bodies).
#: DERIVED from ``_LANE_AGENTS`` (the SAME map ``_resolve_agent`` already
#: reads for phaseless lanes) plus ``_EXAMINER_AGENT`` -- deliberately NOT
#: derived from ``_PHASE_AGENTS`` wholesale, since that map also carries
#: ``nw-acceptance-designer`` (D_DISTILL), a CODE-FACING agent that needs the
#: real design citation and TDD/quality skills. Never a second,
#: independently-maintained list that can drift: both ``_skill_loading_body``
#: and ``_design_context_body`` consult this ONE set, so a future
#: non-code-facing lane/phase widens it once and both bodies stay honest by
#: construction (the class-level negative AT: no reference to
#: design/source/ATs).
_NON_CODE_FACING_AGENTS: frozenset[str] = frozenset(
    {_EXAMINER_AGENT, *_LANE_AGENTS.values()}
)


def _canonical_phase_values() -> tuple[str, ...]:
    """The live ``--phase`` choice set: the ``ATDDPurePhase`` canonical member
    values (aliases excluded -- enum iteration already skips value-aliases
    like ``EXAMINE``) UNIONED with every live ``FEATURE_END_PHASES`` member --
    so a phase the guard's own SSOT already treats as feature-end-coherent
    (e.g. ``F_FINAL_REVIEW``) is always generable too, with no second,
    separately-maintained choices literal (fix-dispatch-cannot-generate-
    feature-end-phases: one authority, two readers).

    Reads ``FEATURE_END_PHASES`` via a bare module-global name lookup, so it
    resolves LIVE at call time through this module's own namespace -- a
    monkeypatch of ``dispatch.FEATURE_END_PHASES`` changes what this returns
    immediately, with no other code change. This is what proves derivation
    rather than two lists hand-synced to match today's values.
    """
    canonical = (member.value for member in ATDDPurePhase)
    return tuple(dict.fromkeys((*canonical, *sorted(FEATURE_END_PHASES))))


#: The wave-owning agent for each AUTHORING wave -- the third resolution axis,
#: consulted when a dispatch declares neither lane nor phase. Without it a
#: DISCUSS/DESIGN/DEVOPS dispatch fell to ``_DEFAULT_AGENT`` (the software
#: crafter) and NAMED THE CRAFTER as the recipient of a wave whose output is a
#: document, not code. Values mirror the wave table in CLAUDE.md; DELIVER is
#: absent on purpose -- its recipient is phase-resolved, and feature-end
#: likewise.
_WAVE_AGENTS: dict[str, str] = {
    "discuss": "nw-product-owner",
    "design": "nw-solution-architect",
    "devops": "nw-platform-architect",
    "distill": "nw-acceptance-designer",
}


def _resolve_agent(phase: str | None, lane: str | None, wave: str | None = None) -> str:
    """Resolve the AGENT_IDENTITY for a dispatch from its (phase, lane, wave).

    A phaseless cross-wave-child lane (e.g. ``charter``) resolves via
    ``_LANE_AGENTS`` first -- it has no phase to key on. Then the phase-keyed
    resolution (``_PHASE_AGENTS``). Then the WAVE-keyed resolution, which is
    what an authoring wave travels: it declares neither lane nor phase, so
    without this axis it silently resolved to the crafter. Only a dispatch
    matching none of the three falls to ``_DEFAULT_AGENT``.
    """
    if lane is not None and lane in _LANE_AGENTS:
        return _LANE_AGENTS[lane]
    if phase is not None:
        if phase in _PHASE_AGENTS:
            return _PHASE_AGENTS[phase]
        if phase in _PHASES_DEFAULT_TO_CRAFTER:
            return _DEFAULT_AGENT
        # FEATURE_END_PHASES (bare module-global, referenced live -- not
        # snapshotted at import) is the feature-end-cycle's OWN closed-world
        # SSOT (ADR-028 D6): a phase this generator's own --phase choices
        # already treat as feature-end-coherent (_canonical_phase_values())
        # is a legitimate crafter-default fallback too, never a routing gap
        # -- this is what keeps `test_generator_phase_choices_derive_live_
        # from_feature_end_phases_ssot`'s live-SSOT-propagation proof
        # (patching this binding must widen what is generable) true after
        # the closed-world refusal below is introduced.
        if phase in FEATURE_END_PHASES:
            return _DEFAULT_AGENT
        raise ValueError(
            f"phase {phase!r} is unmapped -- no agent is registered for it "
            "in _PHASE_AGENTS, it is not in _PHASES_DEFAULT_TO_CRAFTER, and "
            "it is not a FEATURE_END_PHASES member (the only phases that "
            "legitimately default to the crafter). WHY: an unmapped phase "
            "used to silently resolve to the crafter default, which is "
            "unsafe for a non-code-facing phase. HOW: add phase "
            f"{phase!r} to _PHASE_AGENTS in src/des/cli/dispatch.py naming "
            "its correct agent, or to _PHASES_DEFAULT_TO_CRAFTER if it is "
            "genuinely crafter-run."
        )
    if wave is not None and wave in _WAVE_AGENTS:
        return _WAVE_AGENTS[wave]
    return _DEFAULT_AGENT


def _feature_delta_missing_advisory(project_root: Path, feature_id: str) -> str | None:
    """Return a proactive readiness ADVISORY string when NO feature-delta.md
    exists on disk for ``feature_id``, or ``None`` when one does (GDP-1/2:
    catch it at generation time, before the crafter is dispatched and the
    separate readiness gate ``verify-readiness-pre-dispatch`` rejects it
    after the fact).

    EXISTENCE-only leg of the readiness check -- gated at the call site on
    ``LaneProfile.feature_readiness`` (True for bugfix, so a bugfix dispatch
    with no feature-delta.md now gets this existence advisory too; the
    reuse-analysis CONTENT leg in ``_feature_delta_content_advisory`` stays
    gated on ``_LANES_REQUIRING_JUSTIFICATION`` -- bugfix-exempt, unchanged).
    Split out of the former combined ``_feature_delta_readiness_advisory``
    (RCA fix-des-dispatch-broken-design-context-pointer, fix B: existence and
    content are orthogonal checks that were wrongly sharing one gate).

    ``project_root`` is the PROJECT axis (the caller's own repo), resolved
    independently of the SSOT axis (``ssot_dir`` in ``main``) -- never the
    installed-runtime asset dir, so a real project's feature-delta is never
    silently looked up under the wrong tree (RCA fix-dispatch-ssot-consuming
    -repo, Branch B).

    ADVISORY-ONLY -- the caller prints this to stderr and generation
    continues unconditionally; this function never raises and never causes
    ``main`` to change its exit code.
    """
    delta_path = project_root / "docs" / "feature" / feature_id / "feature-delta.md"
    if delta_path.is_file():
        return None
    return (
        f"advisory: the feature-delta for '{feature_id}' is not "
        f"readiness-ready -- no feature-delta.md found at {delta_path}; "
        "fix it before dispatching the crafter (the readiness gate will "
        "otherwise reject it)"
    )


def _feature_delta_content_advisory(project_root: Path, feature_id: str) -> str | None:
    """Return a proactive readiness ADVISORY string when an EXISTING
    feature-delta.md's Reuse Analysis content is not readiness-ready, or
    ``None`` when it is ready, absent, or unreadable/unparsable.

    CONTENT-only leg of the readiness check -- gated at the call site on
    ``_LANES_REQUIRING_JUSTIFICATION`` (bugfix stays exempt, unchanged from
    before the fix-B split: a bugfix has no Reuse Analysis to validate).

    ADVISORY-ONLY -- same contract as ``_feature_delta_missing_advisory``.

    Degrade-loud-but-safe: a missing/unreadable file is not this leg's
    concern (the existence leg owns that signal) -- swallowed to ``None``
    here rather than double-reporting; an unexpected error while validating
    content is likewise swallowed (``None`` -- skip the advisory) rather
    than crashing prompt generation.
    """
    delta_path = project_root / "docs" / "feature" / feature_id / "feature-delta.md"
    try:
        content = delta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        result = validate_reuse_analysis_content(content)
    except Exception:
        return None
    if result.verdict in _REUSE_READY_VERDICTS:
        return None
    return (
        f"advisory: the feature-delta for '{feature_id}' is not "
        f"readiness-ready -- {result.detail}; fix it before dispatching the "
        "crafter (the readiness gate will otherwise reject it)"
    )


def _feature_delta_prefactoring_advisory(
    project_root: Path, feature_id: str
) -> str | None:
    """Return a proactive readiness ADVISORY string when an EXISTING
    feature-delta.md's Prefactoring Assessment content is not
    readiness-ready, or ``None`` when it is ready, not-required, exempted by
    a Design-Skipped witness, absent, or unreadable/unparsable.

    CONTENT-only leg of the readiness check, sibling of
    ``_feature_delta_content_advisory`` -- gated at the SAME call site
    (``_cites_design``, ``_LANES_REQUIRING_JUSTIFICATION`` bugfix-exempt): a
    bugfix has no Prefactoring Assessment to validate either.

    Layers the SAME ``_design_skip_witness_present`` helper
    ``verify_readiness_pre_dispatch._check_prefactoring_assessment`` uses ON
    TOP of the pure verdict -- never a second design-skip parser -- so a
    Design-Skipped feature-delta (whose ``## Wave: DESIGN / [REF] Design
    Skipped`` heading otherwise satisfies the pure validator's `## Wave:
    DESIGN` substring match) does not get advised to author a section it has
    no design to have bent.

    ADVISORY-ONLY -- same contract as ``_feature_delta_missing_advisory``.

    Degrade-loud-but-safe (GDP-6): a missing/unreadable file is not this
    leg's concern (the existence leg owns that signal) -- swallowed to
    ``None`` here rather than double-reporting; an unexpected error while
    validating content is likewise swallowed (``None`` -- skip the advisory)
    rather than crashing prompt generation.
    """
    delta_path = project_root / "docs" / "feature" / feature_id / "feature-delta.md"
    try:
        content = delta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        result = validate_prefactoring_assessment_content(content)
    except Exception:
        return None
    if result.verdict in _PREFACTORING_READY_VERDICTS:
        return None
    if result.verdict in _PREFACTORING_WITNESS_RESCUABLE_VERDICTS:
        try:
            if _design_skip_witness_present(content):
                return None
        except Exception:
            return None
    return (
        f"advisory: the feature-delta for '{feature_id}' is not "
        f"readiness-ready -- {result.detail}; fix it before dispatching the "
        "crafter (the readiness gate will otherwise reject it)"
    )


def _read_marker_syntax(ssot_dir: Path) -> str:
    """Read the claude_code vendor's marker syntax from ``vendors.yaml``.

    ``ssot_dir`` is the RUNTIME axis (the same directory ``vendors.yaml`` and
    ``atdd_pure.yaml`` are read from) -- never the PROJECT axis.

    Degrades to the literal fallback (matching the same vendor row) on any
    read/parse failure or missing vendor entry -- a transient SSOT read
    problem must not crash the generator; the fallback is byte-identical to
    the vendors.yaml SSOT's current claude_code row.
    """
    vendors_path = ssot_dir.joinpath(*_VENDORS_YAML_PARTS)
    try:
        text = vendors_path.read_text(encoding="utf-8")
        document = subset_parser.load(text)
        vendors = document["vendors"]
        vendor = vendors[_VENDOR_ID]  # type: ignore[index]
        marker_syntax = vendor["marker_syntax"]
    except (OSError, ValueError, KeyError, TypeError):
        return _FALLBACK_MARKER_SYNTAX
    if not isinstance(marker_syntax, str) or not marker_syntax:
        return _FALLBACK_MARKER_SYNTAX
    return marker_syntax


#: Default SKILL_LOADING body -- code-facing agents (the crafter, the
#: acceptance-designer) load TDD/quality methodology skills.
_DEFAULT_SKILL_LOADING = (
    "Before starting, read your skill files for methodology guidance.\n"
    "Always load at phase entry: nw-tdd-methodology, nw-quality-framework.\n"
)

#: SKILL_LOADING body for the examiner -- NO technical/code-reasoning skills
#: (RCA fix-po-charter-dispatch-marker-lane, Face B: handing her
#: ``nw-tdd-methodology`` is the loaded-gun defect that fix removed). It
#: deliberately makes NO claim about her access: the ONE claim site is the
#: capability-derived sentence in DESIGN_CONTEXT (``_capability_claim``), so a
#: claim can never be stated in a register the declaration does not support
#: (RCA fix-examiner-blindness-enforced -- this body used to assert "no source
#: or design access by construction" over an unenforced constraint).
_EXAMINER_SKILL_LOADING = (
    "No technical or code-reasoning skills to load -- examining is not "
    "implementation, and code-reasoning knowledge corrupts the examiner's "
    "epistemology.\n"
)

#: SKILL_LOADING body for the charter-authoring product-owner -- POSITIVE
#: naming of the charter-authoring competence (``nw-expectation-charter``),
#: never the crafter's code-reasoning/TDD skills (RCA follow-up: "the cure
#: relocated the disease" -- SKILL_LOADING still handed the fresh PO
#: ``nw-tdd-methodology`` after Face A was fixed).
_CHARTER_SKILL_LOADING = (
    "Load nw-expectation-charter for charter-authoring competence -- no "
    "code-reasoning or TDD/quality-framework skills; charter authoring is "
    "not implementation.\n"
)

#: Agent -> SKILL_LOADING body override for every NON-CODE-FACING agent.
#: Consults the SAME ``_NON_CODE_FACING_AGENTS`` SSOT set; ``agent`` not in
#: this map falls through to ``_DEFAULT_SKILL_LOADING``.
_NON_CODE_FACING_SKILL_LOADING: dict[str, str] = {
    _EXAMINER_AGENT: _EXAMINER_SKILL_LOADING,
    "nw-product-owner": _CHARTER_SKILL_LOADING,
}


def _skill_loading_body(agent: str) -> str:
    """SKILL_LOADING section body, keyed on the resolved dispatch agent."""
    return _NON_CODE_FACING_SKILL_LOADING.get(agent, _DEFAULT_SKILL_LOADING)


#: DESIGN_CONTEXT body for every NON-CODE-FACING agent -- NO path/word naming
#: the design, the source, or the ATs (RCA follow-up, the durable
#: class-level fix): the whole reason a fresh PO writes the charter is that
#: they have NOT seen the design, and the examiner's exclusion from design is
#: the instrument, not an omission. Mirrors the neutral body the guard
#: already accepts for an examine dispatch (``design_context_carries_
#: architecture`` is not applied to a non-code-facing dispatch).
#: The WITHHOLDING half of the body -- keyed on ROLE INTENT, never on
#: capability. Deriving the ROUTING from capability instead would classify the
#: examiner as code-facing today (she holds ``Read``/``Bash``) and start
#: handing her the design pointers whose absence IS her epistemic value.
#: Only the CLAIM REGISTER below is derived.
_NON_CODE_FACING_DESIGN_CONTEXT = (
    "N/A -- this dispatch is non-code-facing by ROLE INTENT: no source, "
    "design, or acceptance-test material is routed to it.\n"
)


def _armed_middle_slot_section_body(section_id: str, charter_path: str) -> str:
    """Render the charter-only EXAMINE envelope for an armed middle slot."""
    bodies = {
        "SKILL_LOADING": (
            "Your only specification is the named expectation charter. "
            "Do not load technical or code-reasoning skills.\n"
        ),
        "TASK_CONTEXT": (
            f"Charter: {charter_path}\n"
            "Walk the promised outcome through the real surface as a user "
            "or API consumer.\n"
        ),
        "DESIGN_CONTEXT": f"Charter: {charter_path}\n",
        "ATDD_PURE_PHASES": (
            "Exercise the charter through the real surface and report only "
            "what you observe.\n"
        ),
        "QUALITY_GATES": (
            "Exercise the real product surface directly; do not substitute "
            "an implementation review for observation.\n"
        ),
        "AT_COMPLETION_LEDGER": (
            "Record the resulting ExamineVerdict for this charter.\n"
        ),
        "RECORDING_INTEGRITY": (
            "Report observed evidence honestly; never manufacture a passing outcome.\n"
        ),
        "BOUNDARY_RULES": (
            "Stay within the charter's promised outcome and its stated observations.\n"
        ),
        "TERMINATING_RUN": (
            "Report what worked, what did not, and any discrepancy from the "
            "charter after walking the real surface.\n"
        ),
        "TIMEOUT_INSTRUCTION": (
            "STOP once the real surface has been exercised end to end and "
            "your ExamineVerdict is ready.\n"
        ),
    }
    return bodies.get(section_id, "")


def _legacy_middle_slot_section_body(section_id: str) -> str | None:
    """Return explicit technical-audit instructions for an unarmed slot."""
    bodies = {
        "SKILL_LOADING": (
            "Load nw-at-completeness-check for the legacy 15-item "
            "AT-completeness audit.\n"
        ),
        "TASK_CONTEXT": (
            "Review the slice's code, design reference, and acceptance-test "
            "material as the legacy technical reviewer.\n"
        ),
        "QUALITY_GATES": (
            "Conduct the 15-item AT-completeness audit; do not clear the "
            "middle slot on a partial review.\n"
        ),
        "AT_COMPLETION_LEDGER": (
            "Emit a PhaseCReviewerVerdict with the technical audit findings.\n"
        ),
        "TERMINATING_RUN": (
            "Report the 15-item AT-completeness audit and its PhaseCReviewerVerdict.\n"
        ),
    }
    return bodies.get(section_id)


def _granting_phrase(capability: DeclaredCapability) -> str:
    """Name the tools the claim is derived FROM, so the reader can check."""
    if capability.declared_tools is None:
        return (
            "every tool -- its spec declares no `tools:` key at all, an "
            "omission that INHERITS the full tool set"
        )
    if capability.register is ClaimRegister.INSTRUCTED:
        return ", ".join(capability.source_reaching_tools)
    if not capability.declared_tools:
        return "no tool at all"
    return ", ".join(capability.declared_tools)


def _capability_claim(agent: str, capability: DeclaredCapability) -> str:
    """The ONE sentence this generator may say about a dispatch's access --
    DERIVED from the agent's declared capability, never asserted (RCA
    fix-examiner-blindness-enforced, root causes A + D).

    Three mutually exclusive registers (``des.domain.agent_capability``):

      * ``UNKNOWN``    -- the declaration could not be read. Say so plainly.
        Degrading to the permissive wording here would launder an absence of
        evidence into evidence of absence (GDP-6).
      * ``INSTRUCTED`` -- the declaration DOES grant a source-reaching tool.
        The honest register: instructed, not prevented -- and FALSIFIABLE, so
        the sentence names the exact file and field the reader can check.
      * ``ENFORCED``   -- the declaration grants nothing that reaches the
        tree. An absolute is EARNED only here: an ungranted tool is genuinely
        uncallable, so the declaration IS the mechanism.

    Forward-compatible by construction of the derivation itself: when real
    enforcement lands and the examiner's declared capability is genuinely
    restricted, this same code starts reporting ``ENFORCED`` with no edit.
    """
    reference = capability.spec_reference(agent)
    if capability.register is ClaimRegister.UNKNOWN:
        return (
            f"Access constraint -- UNVERIFIED: {agent}'s declared capability "
            f"could not be determined ({reference} carries no parseable "
            "`tools:` frontmatter). It was NOT read, which is not the same as "
            "read-and-clear -- treat the constraint as instructed only, and "
            "verify the surface this dispatch actually exercised.\n"
        )
    if capability.register is ClaimRegister.INSTRUCTED:
        return (
            f"Access constraint -- INSTRUCTED, not enforced: {agent}'s "
            f"declared capability ({reference}, `tools:` frontmatter) grants "
            f"{_granting_phrase(capability)}, which DO reach the tree. "
            "Nothing mechanically prevents this dispatch from reading "
            "implementation, design or acceptance tests -- the constraint is "
            "a role instruction, never a property of the system. Verify the "
            "surface actually exercised before trusting the verdict.\n"
        )
    return (
        f"Access constraint -- ENFORCED: {agent}'s declared capability "
        f"({reference}, `tools:` frontmatter) grants "
        f"{_granting_phrase(capability)}, none of which reaches the tree, so "
        "source, design and acceptance-test access is prevented by "
        "construction -- read from the declaration, never asserted.\n"
    )


#: DESIGN_CONTEXT body for a bugfix-lane dispatch whose feature-id has NO
#: feature-delta.md on disk (RCA fix-des-dispatch-broken-design-context-
#: pointer): a bugfix has no design delta by design (the RCA/regression-test
#: pair IS its design source, per ADR-025's SLIM-crafter discipline) -- this
#: fallback names that explicitly, never the dangling pointer. Deliberately
#: carries NO ``docs/feature/.../feature-delta.md``-shaped substring (the
#: downstream shape-gate ``_FEATURE_DELTA_PATH_SHAPE_PATTERN`` in the AT would
#: catch a merely-reworded dangling path) while still citing a real
#: design-reference token (``ADR-025``) so the body keeps satisfying the REAL
#: production predicate ``design_context_carries_architecture`` -- the same
#: gate a bugfix (code-facing) dispatch is held to.
_BUGFIX_MISSING_FEATURE_DELTA_DESIGN_CONTEXT = (
    "No feature-delta.md exists for this bugfix (bugfix lane carries no "
    "design delta by design, per ADR-025 SLIM-crafter discipline). Design "
    "context for this bugfix: consult the RCA / dispatch intent, plus the "
    "regression test named in DES-REGRESSION-TEST-FILE.\n"
)


def _design_ownership_envelope(feature_id: str) -> str:
    """Return the non-substitutable ownership/readiness contract for DESIGN."""
    return (
        f"nw-solution-architect owns docs/feature/{feature_id}/feature-delta.md "
        "canonical DESIGN sections `## Reuse Analysis` and "
        "`## Prefactoring Assessment`.\n"
        "Standalone design documents never substitute for feature-delta.md.\n"
        "Before handoff, run `des verify-readiness-pre-dispatch`.\n"
    )


#: QUALITY_GATES / TERMINATING_RUN / TIMEOUT_INSTRUCTION bodies for every
#: NON-CODE-FACING agent (bugfix fix-feature-end-examine-agent, Cause B):
#: these three sections used to branch ONLY on ``runs_tests``, so a
#: non-code-facing dispatch (e.g. the examiner) still received crafter-shaped
#: prose ("No new tests authored by the crafter", "STOP after the ATs are
#: green") regardless of who was actually named -- the examiner's whole
#: epistemic value is that she EXERCISES the real product surface and
#: reports a VERDICT on what she OBSERVED, never runs/authors tests. Mirrors
#: the SAME ``_NON_CODE_FACING_AGENTS`` SSOT set ``_skill_loading_body`` and
#: ``_design_context_body`` already key on.
_NON_CODE_FACING_QUALITY_GATES = (
    "There are no tests to run and no ATs to author. Exercise the real "
    "product surface directly and form a verdict on what you observed.\n"
)
_NON_CODE_FACING_TERMINATING_RUN = (
    "Report your verdict on what you observed while exercising the real "
    "product surface -- what worked, what did not, and any discrepancy "
    "from the expected behavior.\n"
)
_NON_CODE_FACING_TIMEOUT_INSTRUCTION = (
    "Target ~60 turns. STOP once you have exercised the real product "
    "surface end to end and can report your verdict on what you observed.\n"
)


#: Appended to EVERY TIMEOUT_INSTRUCTION body -- ONE shared constant, never a
#: per-branch paraphrase (three copies of the prose are three things to keep in
#: step). Bugfix fix-dispatched-agent-background-job-never-wakes: a dispatched
#: agent that starts a long command in the BACKGROUND and then ends its turn
#: waiting for the task-notification waits forever, because that notification
#: is delivered to the ORCHESTRATOR and never to a dispatched agent for its own
#: shell job. The failure disguises itself as slowness -- the agent is alive
#: and coherent, so from outside it is indistinguishable from a merely slow one
#: and nobody intervenes. The rule belongs in THIS section because the section
#: an agent reads when it is about to stop is its own termination contract.
_NO_BACKGROUND_TURN_CLOSE = (
    "Never end your turn waiting for a background job you started: that "
    "notification reaches the ORCHESTRATOR, never a dispatched agent, so the "
    "turn waits forever while merely looking slow and nobody intervenes. If "
    "you need a long-running command's result, run it in the FOREGROUND in "
    "this turn, or poll for it within the SAME turn. Backgrounding is an "
    "orchestrator's tool, not a dispatched agent's.\n"
)


def _design_context_body(
    agent: str,
    feature_id: str,
    lane: str | None,
    wave: str,
    project_root: Path,
    capability: DeclaredCapability,
) -> str:
    """DESIGN_CONTEXT section body, keyed on the resolved dispatch agent
    (and, for a bugfix-lane code-facing dispatch, on whether a
    feature-delta.md genuinely exists on disk).

    A NON-CODE-FACING agent (``_NON_CODE_FACING_AGENTS``) never receives the
    ``docs/feature/<id>/feature-delta.md`` pointer, and its body carries the
    capability-DERIVED access claim (``_capability_claim``) -- the withholding
    stays keyed on ROLE INTENT, only the claim's REGISTER is derived, so
    honesty about the claim never becomes a licence to route implementation
    context to a role whose whole value is that it has seen none. Every other
    (code-facing) agent keeps the real design citation, UNLESS ``lane ==
    "bugfix"`` and the file does not actually exist under ``project_root``
    (RCA fix-des-dispatch-broken-design-context-pointer): a bugfix has no
    feature-delta.md by design, so pointing the crafter at one that will
    never resolve is the exact defect this branch fixes.
    """
    if agent in _NON_CODE_FACING_AGENTS:
        return _NON_CODE_FACING_DESIGN_CONTEXT + _capability_claim(agent, capability)
    if agent == "nw-solution-architect" and wave == "design":
        return _design_ownership_envelope(feature_id)
    if lane == "bugfix":
        delta_path = project_root / "docs" / "feature" / feature_id / "feature-delta.md"
        if not delta_path.is_file():
            return _BUGFIX_MISSING_FEATURE_DELTA_DESIGN_CONTEXT
    return f"Design reference: docs/feature/{feature_id}/feature-delta.md\n"


def _section_body(
    section_id: str,
    *,
    feature_id: str,
    phase: str | None,
    slice_id: str,
    intent: str,
    agent: str,
    lane: str | None,
    wave: str,
    runs_tests: bool,
    project_root: Path,
    capability: DeclaredCapability,
    middle_slot_charter: str | None,
    legacy_middle_slot: bool,
) -> str:
    """Render one section's scaffold body.

    Every body is a minimal, self-consistent stand-in for the section's
    purpose -- the DESIGN_CONTEXT body is the one with a hard content-presence
    gate downstream (``design_context_carries_architecture``) for a
    CODE-FACING agent, so it MUST carry a real design-reference token (a
    ``docs/feature/<id>/feature-delta.md`` path). A NON-CODE-FACING agent
    (``_NON_CODE_FACING_AGENTS``) is exempt from that gate -- the SAME
    predicate the guard itself consults (``_is_non_code_facing_dispatch``)
    exempts it, and ``_design_context_body`` renders the neutral body plus the
    capability-derived access claim instead. A section id
    absent from this map (e.g. a section newly added to the SSOT that this
    generator does not yet know how to word) still gets its header emitted by
    the caller with an empty body -- the header is the contract; the prose is
    not asserted downstream.
    """
    if middle_slot_charter is not None and section_id != "AGENT_IDENTITY":
        armed_body = _armed_middle_slot_section_body(section_id, middle_slot_charter)
        # The capability-derived access claim is a property of the AGENT's
        # DECLARATION, not of how the middle slot was resolved: arming the slot
        # narrows the SPECIFICATION the examiner works from, never what its
        # tools can reach.  Dropping the claim here would leave the reader of an
        # armed envelope believing an unstated constraint held -- the exact
        # silent-wrong this register exists to prevent (GDP-6), and the reason
        # the claim is DERIVED from the declaration rather than asserted.
        if section_id == "DESIGN_CONTEXT":
            return armed_body + _capability_claim(agent, capability)
        return armed_body
    if legacy_middle_slot:
        legacy_body = _legacy_middle_slot_section_body(section_id)
        if legacy_body is not None:
            return legacy_body

    bodies: dict[str, str] = {
        "DES_METADATA": (
            f"Slice: {slice_id}\nFeature: {feature_id}\n"
            # A phaseless dispatch (authoring wave / phaseless lane) declares
            # NO phase -- print the wave instead of an empty `Phase:` label,
            # which reads as a dropped field rather than an absent one.
            + (f"Phase: {phase}\n" if phase else f"Wave: {wave}\n")
        ),
        "AGENT_IDENTITY": f"Agent: {agent}\n",
        "SKILL_LOADING": _skill_loading_body(agent),
        "TASK_CONTEXT": (
            (
                f"Slice {slice_id} of feature {feature_id}.\n"
                if runs_tests
                else f"Wave {wave} for feature {feature_id} (scope: {slice_id}).\n"
            )
            + (f"{intent}\n" if intent else "")
        ),
        "DESIGN_CONTEXT": _design_context_body(
            agent, feature_id, lane, wave, project_root, capability
        ),
        "ATDD_PURE_PHASES": (
            "Execute the phase named in the DES-PHASE marker.\n"
            + (f"{intent}\n" if intent else "")
        ),
        "QUALITY_GATES": (
            _NON_CODE_FACING_QUALITY_GATES
            if agent in _NON_CODE_FACING_AGENTS
            else (
                (
                    "All the slice's ATs pass before commit. No new tests authored "
                    "by the crafter.\n"
                )
                if runs_tests
                else (
                    f"The {wave} wave's own gate stack decides this dispatch "
                    f"(see nWave/waves/{wave}.yaml for the authoritative gate-ids "
                    "and the output contract). Author the wave's [REF] sections; "
                    "run no tests and write no production code.\n"
                )
            )
        ),
        "AT_COMPLETION_LEDGER": (
            "Record phase outcomes to the AT-completion ledger.\n"
        ),
        "RECORDING_INTEGRITY": (
            "Do not fake green. Never weaken, skip, or rewrite a DISTILL-authored AT.\n"
        ),
        "BOUNDARY_RULES": (
            f"Stay within slice {slice_id}'s value statement.\n"
            if runs_tests
            else (
                f"Produce only the {wave} wave's artifacts. Do NOT implement, "
                "and do NOT pre-empt a downstream wave's decisions.\n"
            )
        ),
        "TERMINATING_RUN": (
            _NON_CODE_FACING_TERMINATING_RUN
            if agent in _NON_CODE_FACING_AGENTS
            else "Report files created/modified; RAW pass/fail of the slice's ATs.\n"
        ),
        "TIMEOUT_INSTRUCTION": (
            (
                _NON_CODE_FACING_TIMEOUT_INSTRUCTION
                if agent in _NON_CODE_FACING_AGENTS
                else (
                    "Target ~60 turns -- a crafter/AT run needs room to seal, run "
                    "static checks, and REPORT after the last command; too small a "
                    "budget kills the agent between the work and its confirmation. "
                    "STOP after the ATs are green.\n"
                    if runs_tests
                    else (
                        f"Target ~60 turns. STOP once the {wave} wave's artifacts are "
                        "authored and their gate has been RUN -- report its raw "
                        "verdict. Do not continue into a downstream wave.\n"
                    )
                )
            )
            + _NO_BACKGROUND_TURN_CLOSE
        ),
    }
    return bodies.get(section_id, "")


def _build_prompt(
    *,
    marker_syntax: str,
    feature_id: str,
    phase: str | None,
    slice_id: str,
    wave: str,
    lane: str | None,
    intent: str,
    defect: str | None,
    regression_test: str | None,
    section_ids: tuple[str, ...],
    runs_tests: bool,
    at_kind: str,
    regression_test_file: str | None,
    agent: str,
    project_root: Path,
    capability: DeclaredCapability,
    declared_project_root: Path | None = None,
    middle_slot_charter: str | None = None,
    legacy_middle_slot: bool = False,
) -> str:
    """Assemble the full dispatch prompt: marker block, then section headers.

    ``phase`` is ``None`` for a phaseless cross-wave-child lane (e.g.
    ``charter``, RCA fix-po-charter-dispatch-marker-lane Face A) -- charter
    authoring is not one of the 3 canonical DELIVER phases, so the
    ``DES-PHASE`` marker is omitted entirely rather than borrowing an
    unrelated phase word.

    ``declared_project_root`` is the tree the CALLER explicitly named
    (``--repo-root``); when set it is stamped as the ``DES-PROJECT-ROOT``
    marker. Without that marker a cross-worktree dispatch is indistinguishable
    from a same-tree one: every hook-side gate then resolves the feature-delta
    against the ORCHESTRATOR's cwd and refuses a feature that exists, complete,
    in the declared worktree. Cross-worktree dispatch is the normal shape here,
    and a feature-delta is born in a worktree before it ever reaches trunk --
    so the declaration has to travel WITH the envelope, in the marker grammar
    the parser actually reads, not in prose the operator adds by hand.
    ``None`` (no ``--repo-root``) stamps nothing: nothing was declared, and the
    hook's cwd default is then the right answer.
    """

    def marker(key: str, value: str) -> str:
        return marker_syntax.format(key=key, value=value)

    marker_lines = [
        marker("DES-VALIDATION", "required"),
        marker("DES-PROJECT-ID", feature_id),
        marker("DES-MODE", "atdd_pure"),
        marker("DES-CAUSAL-ID", uuid.uuid4().hex),
    ]
    if declared_project_root is not None:
        marker_lines.append(marker("DES-PROJECT-ROOT", str(declared_project_root)))
    if phase is not None:
        marker_lines.append(marker("DES-PHASE", phase))
    marker_lines.append(marker("DES-SLICE", slice_id))
    marker_lines.append(marker("DES-WAVE", wave))
    if lane is not None:
        marker_lines.append(marker("DES-LANE", lane))
        if lane in _LANES_REQUIRING_JUSTIFICATION:
            justification = f"{defect} -- regression test: {regression_test}"
            marker_lines.append(marker("DES-LANE-JUSTIFICATION", justification))
    if at_kind == "pytest-regression" and regression_test_file is not None:
        marker_lines.append(marker("DES-AT-KIND", at_kind))
        marker_lines.append(marker("DES-REGRESSION-TEST-FILE", regression_test_file))

    section_lines = [
        f"# {section_id}\n"
        + _section_body(
            section_id,
            feature_id=feature_id,
            phase=phase,
            slice_id=slice_id,
            intent=intent,
            agent=agent,
            lane=lane,
            wave=wave,
            runs_tests=runs_tests,
            project_root=project_root,
            capability=capability,
            middle_slot_charter=middle_slot_charter,
            legacy_middle_slot=legacy_middle_slot,
        )
        for section_id in section_ids
    ]

    return "\n".join(marker_lines) + "\n\n" + "\n".join(section_lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des dispatch",
        description=(
            "Generate a gate-valid atdd_pure dispatch prompt from the "
            "dispatch SSOT (nWave/dispatch/atdd_pure.yaml + vendors.yaml) "
            "and LANE_PROFILES -- the prompt passes the dispatch gates BY "
            "CONSTRUCTION."
        ),
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("atdd_pure",),
        help="Workflow mode (only atdd_pure is supported today).",
    )
    parser.add_argument(
        "--project-id",
        required=True,
        dest="project_id",
        help="The feature id this dispatch targets.",
    )
    parser.add_argument(
        "--slice",
        required=True,
        dest="slice_id",
        help="The slice id (e.g. slice-01) this dispatch targets.",
    )
    parser.add_argument(
        "--phase",
        required=False,
        default=None,
        choices=_canonical_phase_values(),
        help=(
            "The ATDDPurePhase this dispatch executes. Required UNLESS "
            f"--lane is one of the phaseless cross-wave-child lanes "
            f"({', '.join(sorted(PHASELESS_LANES))}), or --wave names an "
            "authoring wave "
            f"({', '.join(sorted(w for w, p in WAVE_DISPATCH_PROFILES.items() if not p.runs_tests))}) "
            "-- neither runs one of the 3 canonical DELIVER phases."
        ),
    )
    parser.add_argument(
        "--wave",
        default="deliver",
        choices=tuple(sorted(WAVE_VOCABULARY)),
        help=(
            "Which WAVE this dispatch belongs to (default: deliver). The value "
            "is stamped as the DES-WAVE marker, which is how a hook knows what "
            "discipline to arm. It was hardcoded to 'deliver' until 2026-07-18, "
            "so a DISCUSS or DESIGN dispatch generated here was LABELLED deliver "
            "-- and the operator, to satisfy the deliver template, ended up "
            "handing a DESIGN context to a wave that runs BEFORE design. The "
            "choices come from the WAVE_VOCABULARY SSOT, never a second list."
        ),
    )
    parser.add_argument(
        "--lane",
        default=None,
        choices=tuple(_KNOWN_LANES),
        help="Optional non-standard lane (e.g. bugfix, prefactoring, charter).",
    )
    parser.add_argument("--intent", default="", help="Free-text task intent.")
    parser.add_argument(
        "--defect",
        default=None,
        help="Bugfix lane only: free text naming the defect.",
    )
    parser.add_argument(
        "--regression-test",
        dest="regression_test",
        default=None,
        help="Bugfix lane only: the regression test name (test_<name>).",
    )
    parser.add_argument(
        "--repo-root",
        dest="repo_root",
        type=Path,
        default=None,
        help="Repo root holding nWave/dispatch/*.yaml (default: cwd).",
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        default="gherkin",
        choices=("gherkin", "pytest-regression"),
        help=(
            "The acceptance-test kind driving this slice (default: gherkin). "
            "'pytest-regression' + --regression-test-file emits the "
            "DES-AT-KIND/DES-REGRESSION-TEST-FILE markers so "
            "carpaccio_intercept runs its pytest-regression entry-gate path."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        dest="regression_test_file",
        default=None,
        help=(
            "Repo-relative path to the pytest regression file (paired with "
            "--at-kind pytest-regression)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse args, render the dispatch prompt, print to stdout.

    Returns 0 on success. Argparse itself degrades loud (clean non-zero exit,
    no traceback) for a missing/unknown ``--project-id`` / ``--phase`` /
    ``--lane``, naming the offending value via ``choices``/``required``.
    """
    args = _build_parser().parse_args(argv)

    phase: str | None = args.phase
    # An AUTHORING wave is phaseless for the SAME structural reason a
    # phaseless lane is: the 3 canonical phases (A_GREEN / EXAMINE / COMMIT)
    # are DELIVER's, and a wave that authors a document runs none of them.
    # Demanding one here forced the operator to borrow an unrelated DELIVER
    # phase word just to get a dispatch out -- writing a false step into the
    # audit trail to satisfy a flag. ``dispatch_is_phaseless`` is the ONE
    # predicate every validity-deciding locus consults (fix-dispatch-
    # validity-ssot) -- this generator is locus 1, never a private
    # re-derivation of the lane/wave union.
    _wave_profile = WAVE_DISPATCH_PROFILES.get(args.wave)
    _phaseless = dispatch_is_phaseless(lane=args.lane, declared_wave=args.wave)
    if phase is None and not _phaseless:
        print(
            "error: --phase is required for a DELIVER-scope dispatch. It is "
            "NOT required when --lane is one of the phaseless cross-wave-child "
            f"lanes ({', '.join(sorted(PHASELESS_LANES))}), nor when --wave "
            "names an authoring wave "
            f"({', '.join(sorted(w for w, p in WAVE_DISPATCH_PROFILES.items() if not p.runs_tests))}) "
            "-- neither runs one of the 3 canonical DELIVER phases. Do NOT "
            "borrow a DELIVER phase word to satisfy this flag: pass the right "
            "--wave instead.",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    # COHERENCE guard (as opposed to the SHAPE guard above, which checks each
    # flag in isolation): a phaseless dispatch (phaseless lane OR authoring
    # wave) declares NO `ATDDPurePhase` by construction -- combining it with
    # an explicit --phase is a self-contradictory request (each part
    # individually valid, the COMBINATION nonsense). Refuse loudly (GDP-3/6)
    # instead of silently inventing a best-guess envelope naming one role's
    # agent with another role's phase.
    if phase is not None and _phaseless:
        print(
            f"error: --lane {args.lane} / --wave {args.wave} is phaseless (it "
            "belongs to a non-code-facing cross-wave-child dispatch, or an "
            "authoring wave, that declares no ATDDPurePhase) and cannot be "
            f"combined with --phase {phase} (a phase belonging to a "
            "different role) -- drop --phase, or use a phase-bearing "
            "lane/wave instead.",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    slice_id: str = args.slice_id
    if (
        phase is not None
        and phase in FEATURE_END_PHASES
        and slice_id != _FEATURE_END_SCOPE
    ):
        print(
            f"note: --phase {args.phase} is a feature-end-cycle phase -- its "
            "ONLY coherent scope is 'feature-end' (ADR-028 D6, Option A). "
            f"auto-correcting --slice {slice_id!r} to 'feature-end'.",
            file=sys.stderr,
        )
        slice_id = _FEATURE_END_SCOPE

    # SSOT resolution order (RUNTIME axis -- a dispatch SSOT is an
    # install/checkout concern, never a project one): explicit --repo-root
    # wins ONLY IF it actually carries nWave/dispatch/atdd_pure.yaml > cwd IF
    # cwd/nWave/dispatch/atdd_pure.yaml exists > the installed-runtime assets
    # dir > the LOUD refusal below (naming both cures). An explicit
    # --repo-root pointing at a consuming project (no nWave/dispatch/ of its
    # own -- the exact reported defect, RCA fix-dispatch-ssot-consuming-repo
    # Branch A) now FALLS THROUGH to the installed-runtime fallback instead
    # of unconditionally winning and refusing.
    if (
        args.repo_root is not None
        and args.repo_root.joinpath(*_DISPATCH_YAML_PARTS).is_file()
    ):
        ssot_dir: Path = args.repo_root
    elif Path.cwd().joinpath(*_DISPATCH_YAML_PARTS).is_file():
        ssot_dir = Path.cwd()
    else:
        ssot_dir = _INSTALLED_DISPATCH_ASSETS_DIR.parent.parent

    # PROJECT axis (feature-delta lookup, below): resolved INDEPENDENTLY of
    # the SSOT axis above via the existing, already-reused `repo_path_
    # resolver` SSOT (flag -> NWAVE_REPO_ROOT env -> cwd) -- never the
    # installed-runtime directory, so a real project's feature-delta is never
    # silently looked up under the wrong tree (RCA Branch B). `--repo-root`
    # keeps driving BOTH axes when given explicitly (no new flag, no silent
    # meaning-swap): it now means "the project root, and the SSOT source IF
    # it happens to carry one" -- a strict widening of the prior "the SSOT
    # source, unconditionally" reading, never a narrowing.
    project_root = resolve_repo_root(
        str(args.repo_root) if args.repo_root is not None else None
    )

    dispatch_yaml_path = ssot_dir.joinpath(*_DISPATCH_YAML_PARTS)

    try:
        yaml_text = dispatch_yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        installed_dispatch_yaml = _INSTALLED_DISPATCH_ASSETS_DIR / "atdd_pure.yaml"
        if installed_dispatch_yaml.is_file():
            # The installed runtime DOES ship the SSOT -- reinstalling would
            # not change a byte of it. The real cure is resolution-order:
            # neither cwd nor an explicit --repo-root pointed at a directory
            # that carries nWave/dispatch/atdd_pure.yaml.
            cure = (
                "fix: neither the current directory nor --repo-root "
                f"({args.repo_root}) carries nWave/dispatch/atdd_pure.yaml -- "
                "pass --repo-root pointing at a checkout that has it, or "
                "omit --repo-root to let the installed-runtime SSOT resolve "
                "automatically"
                if args.repo_root is not None
                else "fix: pass --repo-root pointing at a checkout containing "
                "nWave/dispatch/atdd_pure.yaml"
            )
        else:
            # The installed runtime itself is missing/broken -- reinstalling
            # is the TRUE cure here (an install-plugin defect, not something
            # --repo-root can fix).
            cure = (
                "fix: the installed runtime's nWave/dispatch/atdd_pure.yaml "
                f"is missing/unreadable at {installed_dispatch_yaml} -- this "
                "is an install-plugin defect, not something --repo-root can "
                "cure; reinstall nWave (python -m nwave_ai.cli install) so "
                "the installed runtime ships nWave/dispatch/atdd_pure.yaml, "
                "or pass --repo-root pointing at a checkout that has it"
            )
        print(
            f"error: cannot read dispatch SSOT at {dispatch_yaml_path}: {exc}\n{cure}",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    try:
        full_sections = _read_full_sections(yaml_text)
    except ValueError as exc:
        print(
            f"error: malformed dispatch SSOT at {dispatch_yaml_path}: {exc}",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    if args.lane in _LANES_REQUIRING_JUSTIFICATION and not (
        args.defect and args.regression_test
    ):
        print(
            f"error: --lane {args.lane} requires --defect and "
            "--regression-test (naming the defect + a regression test "
            "test_<name>)",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    # Profile precedence: lane (the KIND of work) beats wave (WHICH wave),
    # because a prefactoring lane inside DELIVER is still a prefactoring. A
    # dispatch with neither reads the wave datum; only an unrecognised wave
    # falls to the full implementation set (fail-closed, never downgraded).
    # Profile precedence: lane (the KIND of work) beats wave (WHICH wave),
    # because a prefactoring lane inside DELIVER is still a prefactoring.
    #
    # A DELIVER-scope dispatch (``runs_tests``) keeps reading its sections
    # from the dispatch SSOT YAML at render time -- the wave datum's deliver
    # row exists for the GUARD (which cannot read that YAML) and must never
    # become a second, drifting source for the generator. Only an AUTHORING
    # wave, absent from the YAML's single full profile, reads the datum.
    if args.lane is not None:
        section_ids = LANE_PROFILES[args.lane].required_sections
        runs_tests = True
    elif _wave_profile is not None and not _wave_profile.runs_tests:
        section_ids = _wave_profile.required_sections
        runs_tests = False
    else:
        section_ids = full_sections
        runs_tests = True

    # Fix B (RCA fix-des-dispatch-broken-design-context-pointer): the
    # EXISTENCE leg and the reuse-analysis CONTENT leg are orthogonal checks
    # that used to share one gate (`_LANES_REQUIRING_JUSTIFICATION`), which
    # wrongly exempted the bugfix lane from BOTH -- a bugfix genuinely has no
    # Reuse Analysis to validate (CONTENT stays exempt, unchanged), but it
    # DOES have a feature-delta.md existence question worth flagging
    # (EXISTENCE now keys on `LaneProfile.feature_readiness`, True for
    # bugfix).
    # The EXISTENCE leg carries the same wave constraint as the CONTENT leg
    # below: DISCUSS is the wave that CREATES the feature-delta, so demanding
    # one before it runs asks for an artifact that cannot exist yet (and in
    # epic mode never will -- fractal JIT authors only the epic-delta).
    lane_profile = LANE_PROFILES.get(args.lane) if args.lane is not None else None
    _cites_design = _wave_profile is None or _wave_profile.cites_design
    if _cites_design and (lane_profile is None or lane_profile.feature_readiness):
        missing_advisory = _feature_delta_missing_advisory(
            project_root, args.project_id
        )
        if missing_advisory is not None:
            print(missing_advisory, file=sys.stderr)

    # The Reuse Analysis is a DESIGN artifact. Advising its absence on a
    # dispatch for DISCUSS -- the wave that runs BEFORE design -- demands an
    # artifact that cannot exist yet, the same inversion the section profile
    # above closes. Only waves that CITE a design are held to it.
    if args.lane not in _LANES_REQUIRING_JUSTIFICATION and _cites_design:
        content_advisory = _feature_delta_content_advisory(
            project_root, args.project_id
        )
        if content_advisory is not None:
            print(content_advisory, file=sys.stderr)

        prefactoring_advisory = _feature_delta_prefactoring_advisory(
            project_root, args.project_id
        )
        if prefactoring_advisory is not None:
            print(prefactoring_advisory, file=sys.stderr)

    # C_REVIEWER_AUDIT is an evidence-mode slot, not an unconditional examiner
    # assignment.  Resolve its charter map before rendering an AGENT_IDENTITY:
    # an arbitrary role after malformed/ambiguous evidence would corrupt the
    # gate, so those outcomes refuse before any prompt is emitted.
    middle_slot_charter: str | None = None
    legacy_middle_slot = False
    if phase == ATDDPurePhase.C_REVIEWER_AUDIT.value:
        charter_mapping = resolve_slice_charter(project_root, args.project_id, slice_id)
        if charter_mapping.state is CharterMappingState.INDETERMINATE:
            print(
                "INDETERMINATE: WHAT: the C_REVIEWER_AUDIT expectation-charter "
                f"mapping is malformed or ambiguous ({charter_mapping.detail}); "
                "WHY: selecting either the technical reviewer or the user "
                "examiner without one valid slice-matching charter would make the "
                "middle-slot evidence arbitrary; HOW: repair each charter's single "
                "`Spec rows:` mapping to comma-separated `slice-NN` values so this "
                f"slice ({slice_id}) matches exactly one charter, then rerun `des "
                "dispatch`.",
                file=sys.stderr,
            )
            return _EXIT_USAGE_ERROR
        if charter_mapping.state is CharterMappingState.ARMED:
            assert charter_mapping.charter_path is not None
            middle_slot_charter = str(
                charter_mapping.charter_path.relative_to(project_root)
            )
            agent = _EXAMINER_AGENT
        elif charter_mapping.state is CharterMappingState.UNARMED:
            # The feature carries NO charter directory: the expectation-charter
            # practice is not adopted here, so there is no omission to report
            # and nothing to refuse.  The phase keeps its declared role -- the
            # examiner -- exactly as it did before charters existed.  Silently
            # handing the slot to the technical reviewer instead would give the
            # operator an AT-completeness audit while they believe they asked
            # for an examine, and the two answer different questions.
            agent = _EXAMINER_AGENT
        else:
            # UNMAPPED: charters ARE written for this feature and this slice is
            # not in one.  That is an omission, and it is refused OUT LOUD --
            # never silently traded for a different role.  Refusing names what
            # is missing; substituting hides it (GDP-6, GDP-8).
            print(
                "INDETERMINATE: WHAT: no expectation charter maps slice "
                f"{slice_id} of feature {args.project_id}, so the "
                "C_REVIEWER_AUDIT middle slot has no evidence to arm; WHY: the "
                f"user examiner ({_EXAMINER_AGENT}) examines a PROMISED "
                "OUTCOME, and without a charter there is no promise to walk -- "
                "selecting the technical reviewer instead would return an "
                "AT-completeness audit under the name of an examine, which "
                "answers a different question; HOW: author the slice's "
                "expectation charter (`des dispatch --lane charter "
                f"--project-id {args.project_id} --slice {slice_id}`) so its "
                f"`Spec rows:` names {slice_id}, then rerun `des dispatch`.",
                file=sys.stderr,
            )
            return _EXIT_USAGE_ERROR
    else:
        agent = _resolve_agent(phase, args.lane, args.wave)

    # The CLAIM the envelope may make about this dispatch's access is DERIVED
    # from the recipient's own published declaration, resolved on the SSOT axis
    # (the checkout/installed tree that carries the nWave assets -- agent specs
    # live under `nWave/agents/` in a checkout and `<claude_dir>/agents/nw/`
    # when installed, NOT under the installed `nWave` SSOT dir). Degrades LOUD
    # to the UNKNOWN register; never to a permissive default.
    capability = resolve_declared_capability(agent, repo_root=ssot_dir)

    prompt = _build_prompt(
        marker_syntax=_read_marker_syntax(ssot_dir),
        feature_id=args.project_id,
        phase=phase,
        slice_id=slice_id,
        wave=args.wave,
        lane=args.lane,
        intent=args.intent,
        defect=args.defect,
        regression_test=args.regression_test,
        section_ids=section_ids,
        runs_tests=runs_tests,
        at_kind=args.at_kind,
        regression_test_file=args.regression_test_file,
        agent=agent,
        project_root=project_root,
        capability=capability,
        # Stamped ONLY when the caller explicitly declared a tree. `project_root`
        # is also the cwd default, and stamping that would turn every envelope
        # into a declaration the caller never made.
        declared_project_root=project_root if args.repo_root is not None else None,
        middle_slot_charter=middle_slot_charter,
        legacy_middle_slot=legacy_middle_slot,
    )
    print(prompt, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
