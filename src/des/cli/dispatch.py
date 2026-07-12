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
from des.domain.atdd_pure_phases import FEATURE_END_PHASES, ATDDPurePhase
from des.domain.lane_profile import LANE_PROFILES


#: Deliberate, distinguishable exit for "bad input" (missing/invalid CLI
#: argument, unreadable/malformed SSOT file) -- never a Python traceback.
_EXIT_USAGE_ERROR = 2

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


def _canonical_phase_values() -> tuple[str, ...]:
    """The live ``ATDDPurePhase`` canonical member values (aliases excluded --
    enum iteration already skips value-aliases like ``EXAMINE``)."""
    return tuple(member.value for member in ATDDPurePhase)


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


def _section_body(
    section_id: str,
    *,
    feature_id: str,
    phase: str,
    slice_id: str,
    intent: str,
) -> str:
    """Render one section's scaffold body.

    Every body is a minimal, self-consistent stand-in for the section's
    purpose -- the DESIGN_CONTEXT body is the one with a hard content-presence
    gate downstream (``design_context_carries_architecture``), so it MUST
    carry a real design-reference token (a ``docs/feature/<id>/feature-
    delta.md`` path). A section id absent from this map (e.g. a section newly
    added to the SSOT that this generator does not yet know how to word)
    still gets its header emitted by the caller with an empty body -- the
    header is the contract; the prose is not asserted downstream.
    """
    bodies: dict[str, str] = {
        "DES_METADATA": (f"Slice: {slice_id}\nFeature: {feature_id}\nPhase: {phase}\n"),
        "AGENT_IDENTITY": "Agent: nw-software-crafter\n",
        "SKILL_LOADING": (
            "Before starting, read your skill files for methodology guidance.\n"
            "Always load at phase entry: nw-tdd-methodology, nw-quality-framework.\n"
        ),
        "TASK_CONTEXT": f"Slice {slice_id} of feature {feature_id}.\n",
        "DESIGN_CONTEXT": (
            f"Design reference: docs/feature/{feature_id}/feature-delta.md\n"
        ),
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
        "TIMEOUT_INSTRUCTION": "Target ~30 turns. STOP after the ATs are green.\n",
    }
    return bodies.get(section_id, "")


def _build_prompt(
    *,
    marker_syntax: str,
    feature_id: str,
    phase: str,
    slice_id: str,
    lane: str | None,
    intent: str,
    defect: str | None,
    regression_test: str | None,
    section_ids: tuple[str, ...],
    at_kind: str,
    regression_test_file: str | None,
) -> str:
    """Assemble the full dispatch prompt: marker block, then section headers."""

    def marker(key: str, value: str) -> str:
        return marker_syntax.format(key=key, value=value)

    marker_lines = [
        marker("DES-VALIDATION", "required"),
        marker("DES-PROJECT-ID", feature_id),
        marker("DES-MODE", "atdd_pure"),
        marker("DES-PHASE", phase),
        marker("DES-SLICE", slice_id),
        marker("DES-WAVE", "deliver"),
    ]
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
        required=True,
        choices=_canonical_phase_values(),
        help="The ATDDPurePhase this dispatch executes.",
    )
    parser.add_argument(
        "--lane",
        default=None,
        choices=tuple(LANE_PROFILES),
        help="Optional non-standard lane (e.g. bugfix, prefactoring).",
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

    slice_id: str = args.slice_id
    if args.phase in FEATURE_END_PHASES and slice_id != _FEATURE_END_SCOPE:
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

    prompt = _build_prompt(
        marker_syntax=_read_marker_syntax(repo_root),
        feature_id=args.project_id,
        phase=args.phase,
        slice_id=slice_id,
        lane=args.lane,
        intent=args.intent,
        defect=args.defect,
        regression_test=args.regression_test,
        section_ids=section_ids,
        at_kind=args.at_kind,
        regression_test_file=args.regression_test_file,
    )
    print(prompt, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
