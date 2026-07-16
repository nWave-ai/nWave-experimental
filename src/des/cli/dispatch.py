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
from pathlib import Path

from des._internal import subset_parser
from des.application.dispatch_lane_ssot import _read_full_sections
from des.cli.validate_feature_delta import (
    VERDICT_METHODOLOGY_EXEMPT,
    VERDICT_NO_OVERLAP_DECLARED,
    VERDICT_STRUCTURALLY_ACCEPTED,
    validate_reuse_analysis_content,
)
from des.domain.atdd_pure_phases import FEATURE_END_PHASES, ATDDPurePhase
from des.domain.lane_profile import LANE_PROFILES, PHASELESS_LANES


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

_DISPATCH_YAML_PARTS = ("nWave", "dispatch", "atdd_pure.yaml")
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
#: skills and source/design access BY CONSTRUCTION (RCA
#: fix-po-charter-dispatch-marker-lane, Face B).
_EXAMINER_AGENT = "nw-user-examiner"

#: Phase -> agent override map (GDP-5, the producing tool derives the correct
#: agent per phase instead of hardcoding one for every phase). ``D_DISTILL``
#: is the AT-authoring phase -- ADR-025 reserves acceptance-test authorship to
#: ``nw-acceptance-designer``; the SLIM crafter never authors tests.
#: ``C_REVIEWER_AUDIT`` is the EXAMINE step -- routed to the examiner, never
#: the crafter (Face B fix). ``F_FINAL_REVIEW`` (the feature-end LLM
#: reviewer-audit return) is intentionally NOT overridden here -- it stays on
#: ``_DEFAULT_AGENT`` (out of this fix's scope).
_PHASE_AGENTS: dict[str, str] = {
    ATDDPurePhase.D_DISTILL.value: "nw-acceptance-designer",
    ATDDPurePhase.C_REVIEWER_AUDIT.value: _EXAMINER_AGENT,
}

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
    """The live ``ATDDPurePhase`` canonical member values (aliases excluded --
    enum iteration already skips value-aliases like ``EXAMINE``)."""
    return tuple(member.value for member in ATDDPurePhase)


def _resolve_agent(phase: str | None, lane: str | None) -> str:
    """Resolve the AGENT_IDENTITY for a dispatch from its (phase, lane).

    A phaseless cross-wave-child lane (e.g. ``charter``) resolves via
    ``_LANE_AGENTS`` first -- it has no phase to key on. Otherwise the
    existing phase-keyed resolution (``_PHASE_AGENTS``, default the crafter)
    applies unchanged.
    """
    if lane is not None and lane in _LANE_AGENTS:
        return _LANE_AGENTS[lane]
    if phase is not None:
        return _PHASE_AGENTS.get(phase, _DEFAULT_AGENT)
    return _DEFAULT_AGENT


def _feature_delta_readiness_advisory(repo_root: Path, feature_id: str) -> str | None:
    """Return a proactive readiness ADVISORY string, or ``None`` when the
    feature-delta is readiness-ready (GDP-1/2: catch it at generation time,
    before the crafter is dispatched and the separate readiness gate
    ``verify-readiness-pre-dispatch`` rejects it after the fact).

    ADVISORY-ONLY -- the caller prints this to stderr and generation
    continues unconditionally; this function never raises and never causes
    ``main`` to change its exit code.

    Degrade-loud-but-safe: a missing feature-delta file for a feature-phase
    dispatch IS itself advisory-worthy (the file will be required later); an
    unexpected error while validating its content is swallowed (``None`` --
    skip the advisory) rather than crashing prompt generation.
    """
    delta_path = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    try:
        content = delta_path.read_text(encoding="utf-8")
    except OSError:
        return (
            f"advisory: the feature-delta for '{feature_id}' is not "
            f"readiness-ready -- no feature-delta.md found at {delta_path}; "
            "fix it before dispatching the crafter (the readiness gate will "
            "otherwise reject it)"
        )
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


def _read_marker_syntax(repo_root: Path) -> str:
    """Read the claude_code vendor's marker syntax from ``vendors.yaml``.

    Degrades to the literal fallback (matching the same vendor row) on any
    read/parse failure or missing vendor entry -- a transient SSOT read
    problem must not crash the generator; the fallback is byte-identical to
    the vendors.yaml SSOT's current claude_code row.
    """
    vendors_path = repo_root.joinpath(*_VENDORS_YAML_PARTS)
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
#: (RCA fix-po-charter-dispatch-marker-lane, Face B: her spec forbids
#: source/design access BY CONSTRUCTION -- handing her ``nw-tdd-methodology``
#: is the loaded-gun defect this fix removes).
_EXAMINER_SKILL_LOADING = (
    "No technical or code-reasoning skills to load -- the examiner has no "
    "source or design access by construction.\n"
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
_NON_CODE_FACING_DESIGN_CONTEXT = (
    "N/A -- this dispatch is non-code-facing; no source, design, or "
    "acceptance-test access by construction.\n"
)


def _design_context_body(agent: str, feature_id: str) -> str:
    """DESIGN_CONTEXT section body, keyed on the resolved dispatch agent.

    A NON-CODE-FACING agent (``_NON_CODE_FACING_AGENTS``) never receives the
    ``docs/feature/<id>/feature-delta.md`` pointer -- every other (code-facing)
    agent keeps the real design citation unchanged.
    """
    if agent in _NON_CODE_FACING_AGENTS:
        return _NON_CODE_FACING_DESIGN_CONTEXT
    return f"Design reference: docs/feature/{feature_id}/feature-delta.md\n"


def _section_body(
    section_id: str,
    *,
    feature_id: str,
    phase: str | None,
    slice_id: str,
    intent: str,
    agent: str,
) -> str:
    """Render one section's scaffold body.

    Every body is a minimal, self-consistent stand-in for the section's
    purpose -- the DESIGN_CONTEXT body is the one with a hard content-presence
    gate downstream (``design_context_carries_architecture``) for a
    CODE-FACING agent, so it MUST carry a real design-reference token (a
    ``docs/feature/<id>/feature-delta.md`` path). A NON-CODE-FACING agent
    (``_NON_CODE_FACING_AGENTS``) is exempt from that gate BY CONSTRUCTION --
    ``_design_context_body`` renders the neutral body instead. A section id
    absent from this map (e.g. a section newly added to the SSOT that this
    generator does not yet know how to word) still gets its header emitted by
    the caller with an empty body -- the header is the contract; the prose is
    not asserted downstream.
    """
    bodies: dict[str, str] = {
        "DES_METADATA": (
            f"Slice: {slice_id}\nFeature: {feature_id}\nPhase: {phase or ''}\n"
        ),
        "AGENT_IDENTITY": f"Agent: {agent}\n",
        "SKILL_LOADING": _skill_loading_body(agent),
        "TASK_CONTEXT": f"Slice {slice_id} of feature {feature_id}.\n",
        "DESIGN_CONTEXT": _design_context_body(agent, feature_id),
        "ATDD_PURE_PHASES": (
            "Execute the phase named in the DES-PHASE marker.\n"
            + (f"{intent}\n" if intent else "")
        ),
        "QUALITY_GATES": (
            "All the slice's ATs pass before commit. No new tests authored "
            "by the crafter.\n"
        ),
        "AT_COMPLETION_LEDGER": (
            "Record phase outcomes to the AT-completion ledger.\n"
        ),
        "RECORDING_INTEGRITY": (
            "Do not fake green. Never weaken, skip, or rewrite a DISTILL-authored AT.\n"
        ),
        "BOUNDARY_RULES": f"Stay within slice {slice_id}'s value statement.\n",
        "TERMINATING_RUN": (
            "Report files created/modified; RAW pass/fail of the slice's ATs.\n"
        ),
        "TIMEOUT_INSTRUCTION": "Target ~60 turns -- a crafter/AT run needs room to seal, run static checks, and REPORT after the last command; too small a budget kills the agent between the work and its confirmation. STOP after the ATs are green.\n",
    }
    return bodies.get(section_id, "")


def _build_prompt(
    *,
    marker_syntax: str,
    feature_id: str,
    phase: str | None,
    slice_id: str,
    lane: str | None,
    intent: str,
    defect: str | None,
    regression_test: str | None,
    section_ids: tuple[str, ...],
    at_kind: str,
    regression_test_file: str | None,
    agent: str,
) -> str:
    """Assemble the full dispatch prompt: marker block, then section headers.

    ``phase`` is ``None`` for a phaseless cross-wave-child lane (e.g.
    ``charter``, RCA fix-po-charter-dispatch-marker-lane Face A) -- charter
    authoring is not one of the 3 canonical DELIVER phases, so the
    ``DES-PHASE`` marker is omitted entirely rather than borrowing an
    unrelated phase word.
    """

    def marker(key: str, value: str) -> str:
        return marker_syntax.format(key=key, value=value)

    marker_lines = [
        marker("DES-VALIDATION", "required"),
        marker("DES-PROJECT-ID", feature_id),
        marker("DES-MODE", "atdd_pure"),
    ]
    if phase is not None:
        marker_lines.append(marker("DES-PHASE", phase))
    marker_lines.append(marker("DES-SLICE", slice_id))
    marker_lines.append(marker("DES-WAVE", "deliver"))
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
            f"({', '.join(sorted(PHASELESS_LANES))})."
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
    if phase is None and args.lane not in PHASELESS_LANES:
        print(
            "error: --phase is required unless --lane is one of the "
            f"phaseless cross-wave-child lanes ({', '.join(sorted(PHASELESS_LANES))}) "
            "-- charter authoring is not one of the 3 canonical DELIVER "
            "phases (RCA fix-po-charter-dispatch-marker-lane, Face A).",
            file=sys.stderr,
        )
        return _EXIT_USAGE_ERROR

    # COHERENCE guard (as opposed to the SHAPE guards above/below, which check
    # each flag in isolation): a phaseless lane (`PHASELESS_LANES`) declares NO
    # `ATDDPurePhase` by construction -- combining it with an explicit --phase
    # is a self-contradictory request (each part individually valid, the
    # COMBINATION nonsense). Refuse loudly (GDP-3/6) instead of silently
    # inventing a best-guess envelope naming one role's agent with another
    # role's phase.
    if phase is not None and args.lane in PHASELESS_LANES:
        print(
            f"error: --lane {args.lane} is phaseless (it belongs to a "
            "non-code-facing cross-wave-child dispatch that declares no "
            f"ATDDPurePhase) and cannot be combined with --phase {phase} "
            f"(a phase belonging to a different role) -- drop --phase, or "
            "use a phase-bearing lane instead.",
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

    # SSOT resolution order: explicit --repo-root wins > cwd IF
    # cwd/nWave/dispatch/atdd_pure.yaml exists > the installed-runtime
    # assets dir > the LOUD refusal below (naming both cures).
    if args.repo_root is not None:
        repo_root: Path = args.repo_root
    elif Path.cwd().joinpath(*_DISPATCH_YAML_PARTS).is_file():
        repo_root = Path.cwd()
    else:
        repo_root = _INSTALLED_DISPATCH_ASSETS_DIR.parent.parent

    dispatch_yaml_path = repo_root.joinpath(*_DISPATCH_YAML_PARTS)

    try:
        yaml_text = dispatch_yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"error: cannot read dispatch SSOT at {dispatch_yaml_path}: {exc}\n"
            "fix: pass --repo-root pointing at a checkout containing "
            "nWave/dispatch/atdd_pure.yaml, or reinstall nWave so the "
            "installed runtime ships nWave/dispatch/atdd_pure.yaml",
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

    section_ids = (
        LANE_PROFILES[args.lane].required_sections
        if args.lane is not None
        else full_sections
    )

    if args.lane not in _LANES_REQUIRING_JUSTIFICATION:
        advisory = _feature_delta_readiness_advisory(repo_root, args.project_id)
        if advisory is not None:
            print(advisory, file=sys.stderr)

    prompt = _build_prompt(
        marker_syntax=_read_marker_syntax(repo_root),
        feature_id=args.project_id,
        phase=phase,
        slice_id=slice_id,
        lane=args.lane,
        intent=args.intent,
        defect=args.defect,
        regression_test=args.regression_test,
        section_ids=section_ids,
        at_kind=args.at_kind,
        regression_test_file=args.regression_test_file,
        agent=_resolve_agent(phase, args.lane),
    )
    print(prompt, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
