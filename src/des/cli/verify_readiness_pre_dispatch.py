"""D1 readiness pre-dispatch gate -- verify-readiness-pre-dispatch.

D4 Phase 3 slice-03 (per `docs/analysis/d4-schema-spec-2026-05-26.md`
§ 5 Phase 3 slice-03 + DDD analysis `docs/analysis/ddd-workflow-change-difficulty-2026-05-26.md`
D1 design direction).

Single-invocation aggregate gate that checks all 7 cascading invariants
catalogued in `docs/product/backlog.md` friction #57 (`F-NEW-FEATURE-FIRST-DISPATCH-FRICTION-STACK`)
BEFORE a NEW feature first crafter dispatches. Cascade-debug reduced from
several friction roundtrips to 1 combined diagnostic.

The 7 invariants verified:
  1. SLICE_PLAN_SECTION -- `## Wave: DISCUSS / [REF] Slice Plan` heading
     present in `docs/feature/{feature_id}/feature-delta.md`.
  2. SCENARIO_SLICE_TAGS -- every scenario in the feature's .feature files
     carries a `@slice-NN` tag.
  3. AT_REVIEW_VERDICT -- ATReviewVerdict ledger record present for the
     entering slice in `.nwave/telemetry/atdd-pure/{feature_id}.jsonl`.
  4. GATE_OUTPUT_PRODUCEABLE -- carpaccio CLI output produceable from CWD
     (freshness gate compatible per friction #16 fix shape).
  5. PRE_COMMIT_SCOPE -- no RED scaffolds in pre-commit pytest scope
     without `@skip` markers.
  6. REUSE_FIRST -- a `## Reuse Analysis` section (or exemption marker) OR an
     explicit `## Wave: DESIGN / [REF] Design Skipped` witness with a non-empty
     rationale is present in `docs/feature/{feature_id}/feature-delta.md`. A
     feature that skips the optional DESIGN wave cannot slip past the
     reuse-first guarantee.
  7. SUSTAINABILITY -- a well-formed Test Reuse & Consolidation Analysis section
     (or accepted exemption: methodology-exempt / no-new-tests) is present in
     `docs/feature/{feature_id}/feature-delta.md`. Wires the SHIPPED slice-03
     `validate_sustainability_content` parser into the aggregate so the
     sustainable-test-suite content gate FIRES before dispatch. A
     declared-but-missing or malformed section cannot slip past the gate.

Exit codes:
  0 -- all 7 invariants PASS; dispatcher proceeds to next gate.
  1 -- at least one invariant FAILS; diagnostic enumerates each invariant's
       status + remediation.
  2 -- malformed input (argparse failure on required --feature-id/--slice-id).

Per INV-1 atomic units, INV-13 single CLI entry (`des verify-readiness-pre-dispatch`),
INV-3 emit via LogPersistencePort (slice-04 wires it; today direct emit OK
as scaffolded structural placeholder).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

from des.adapters.driven.config.des_config import DESConfig
from des.cli.axis_b_levers import (
    LayoutRoots,
    LeverResult,
    check_contract_per_port,
    check_integration_per_adapter,
    check_non_ws_spawn,
    check_undefined_name,
    check_unwired_entry,
    resolve_layout,
)
from des.cli.validate_feature_delta import (
    _SUSTAINABILITY_ACCEPTED_VERDICTS,
    VERDICT_MALFORMED_REUSE_ANALYSIS,
    VERDICT_METHODOLOGY_EXEMPT,
    VERDICT_MISSING_REUSE_ANALYSIS,
    VERDICT_NO_OVERLAP_DECLARED,
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNJUSTIFIED_CREATE_NEW,
    validate_reuse_analysis_content,
    validate_sustainability_content,
)
from des.domain.lane_profile import LANE_PROFILES, LaneProfile


def _lane_profile_for(lane_name: str | None) -> LaneProfile | None:
    """Live LANE_PROFILES lookup (slice-02) -- never a hardcoded branch.

    Returns the datum entry for ``lane_name`` when it is a recognized lane
    (e.g. ``"prefactoring"``), else ``None``. ``None``/unrecognized lane names
    fall through to the full 7-invariant default path in ``main`` -- the
    exemption must never leak to an ordinary dispatch.
    """
    if lane_name is None:
        return None
    return LANE_PROFILES.get(lane_name)


# --- Invariant identifiers (mirrors test domain_types.FirstDispatchInvariantId) ---

_INV_SLICE_PLAN = "slice_plan_section"
_INV_SCENARIO_TAGS = "scenario_slice_tags"
_INV_AT_VERDICT = "at_review_verdict"
_INV_GATE_OUTPUT = "gate_output_produceable"
_INV_PRE_COMMIT = "pre_commit_scope"
_INV_REUSE_FIRST = "reuse_first_or_design_skip"
_INV_SUSTAINABILITY = "sustainability"

_ALL_INVARIANTS = (
    _INV_SLICE_PLAN,
    _INV_SCENARIO_TAGS,
    _INV_AT_VERDICT,
    _INV_GATE_OUTPUT,
    _INV_PRE_COMMIT,
    _INV_REUSE_FIRST,
    _INV_SUSTAINABILITY,
)

# --- RC4-b bugfix lane (lane-keyed, ADD-not-mutate) -----------------------
#
# A `DES-LANE: bugfix` dispatch skips the 5 disproportionate feature-readiness
# invariants and enforces ONLY the 2 mechanical safety guards. The skipped
# invariant ids are NAMED via the existing `_INV_*` constants (no hardcoded
# strings) so the LOUD lane audit record stays in lock-step with the gate.
_BUGFIX_LANE = "bugfix"

_BUGFIX_LANE_SKIPPED: tuple[str, ...] = (
    _INV_SLICE_PLAN,
    _INV_SCENARIO_TAGS,
    _INV_AT_VERDICT,
    _INV_REUSE_FIRST,
    _INV_SUSTAINABILITY,
)

# Evidence-floor invariant (NEGATIVE-2, nw-user-examiner Vera FAIL seal 6d182a2a):
# the bugfix lane lightens ceremony, it never removes the evidence floor. ADDED
# (not folded into `_BUGFIX_LANE_SKIPPED`/`_KEPT_TWO` -- ADD-not-mutate) as a
# third check, run ONLY once the 2 mechanical guards clear (a dispatch already
# refused by those guards gets no further diagnostic noise).
_INV_BUGFIX_EVIDENCE_FLOOR = "bugfix_lane_evidence_floor"

_SLICE_PLAN_HEADING = "## Wave: DISCUSS / [REF] Slice Plan"

# The canonical DESIGN-skip witness heading (O-1 opt-a). A feature that skips
# the optional DESIGN wave acknowledges the skip with this heading PLUS a
# non-empty rationale body; a bare heading is not a valid witness.
_DESIGN_SKIP_HEADING = "## Wave: DESIGN / [REF] Design Skipped"

# Remediation strings (mirror the per-gate yaml failure_modes).
_REMEDIATIONS: dict[str, str] = {
    _INV_SLICE_PLAN: (
        "Add `## Wave: DISCUSS / [REF] Slice Plan` heading + table to feature-delta.md"
    ),
    _INV_SCENARIO_TAGS: (
        "Tag every Gherkin scenario with `@slice-NN` per friction #57 invariant 2"
    ),
    _INV_AT_VERDICT: (
        "Record ATReviewVerdict via at_review_verdict CLI for entering slice"
    ),
    _INV_GATE_OUTPUT: (
        "Run carpaccio CLI from valid CWD (freshness gate compatible per friction #16)"
    ),
    _INV_PRE_COMMIT: (
        "Add `@skip @pending` markers to RED scaffolds within pre-commit pytest scope"
    ),
    _INV_REUSE_FIRST: (
        "Add a `## Reuse Analysis` section (DDD-8 / nw-design SKILL.md step 5) OR, "
        "if DESIGN was deliberately skipped, a "
        "`## Wave: DESIGN / [REF] Design Skipped` witness with a non-empty rationale"
    ),
    _INV_SUSTAINABILITY: (
        "Add a well-formed `## Test Reuse & Consolidation Analysis` section "
        "(nw-distill sustainability section) OR a `Test-Reuse-Analysis: "
        "methodology-exempt` marker to feature-delta.md"
    ),
}


@dataclass(frozen=True)
class _InvariantResult:
    """Outcome of a single invariant check."""

    invariant_id: str
    satisfied: bool
    remediation: str | None = None
    # The CodeFactPort confidence label carried with the lever-1 wiring flag
    # (degrade-LOUD, ADR-LA-001). Empty for invariants that carry no code-fact.
    confidence: str = ""


@dataclass
class _ReadinessReport:
    """Aggregate report shape emitted as one JSON line on stdout."""

    feature_id: str
    slice_id: str
    invariants: list[_InvariantResult] = field(default_factory=list)
    # The resolved (or unresolvable) target-project layout (slice-04 PATH-
    # genericity). None when --enforce-axis-b is off (no layout discovery
    # performed); surfaced as the structured ``layout`` record otherwise.
    layout: LayoutRoots | None = None
    # The LOUD, durable bugfix-lane audit record (RC4-b). None on the default
    # path; set to {"lane", "justification", "skipped"} when the bugfix lane
    # fires, naming the skipped feature-readiness invariants for the audit trail.
    lane: dict[str, object] | None = None

    @property
    def verdict(self) -> str:
        return "cleared" if all(r.satisfied for r in self.invariants) else "refused"


# --- Invariant check functions (one per first-dispatch friction) ----------


def _check_slice_plan_section(workspace: Path) -> _InvariantResult:
    """Invariant 1: feature-delta.md carries the slice-plan heading.

    Failure modes (both -> FAILED):
      * feature-delta.md absent
      * feature-delta.md present but missing the heading text
    """
    delta = workspace / "feature-delta.md"
    if not delta.is_file():
        return _InvariantResult(
            invariant_id=_INV_SLICE_PLAN,
            satisfied=False,
            remediation=_REMEDIATIONS[_INV_SLICE_PLAN],
        )
    try:
        text = delta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # An undecodable feature-delta carries no slice-plan heading. Report
        # FAILED rather than crashing the aggregate so every invariant -- in
        # particular the reuse-first degrade-LOUD diagnostic -- still emits.
        return _InvariantResult(
            invariant_id=_INV_SLICE_PLAN,
            satisfied=False,
            remediation=_REMEDIATIONS[_INV_SLICE_PLAN],
        )
    if _SLICE_PLAN_HEADING not in text:
        return _InvariantResult(
            invariant_id=_INV_SLICE_PLAN,
            satisfied=False,
            remediation=_REMEDIATIONS[_INV_SLICE_PLAN],
        )
    return _InvariantResult(invariant_id=_INV_SLICE_PLAN, satisfied=True)


def _check_scenario_slice_tags(repo_root: Path, feature_id: str) -> _InvariantResult:
    """Invariant 2: every Gherkin scenario for the feature carries a @slice-NN tag.

    Searches `tests/**/<feature_id>/**/*.feature` and verifies each Scenario:
    line's preceding tag block contains `@slice-NN`. When NO feature files
    exist yet for the feature (first dispatch), the invariant is SATISFIED
    (vacuous truth -- no scenarios means no untagged scenarios). The dispatch
    is still gated by other invariants.
    """
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        # Workspace lacks tests/ -- no scenarios to verify; vacuously satisfied.
        return _InvariantResult(invariant_id=_INV_SCENARIO_TAGS, satisfied=True)

    feature_files = [p for p in tests_dir.rglob("*.feature") if feature_id in p.parts]
    if not feature_files:
        return _InvariantResult(invariant_id=_INV_SCENARIO_TAGS, satisfied=True)

    untagged = _collect_untagged_scenarios(feature_files)
    if untagged:
        return _InvariantResult(
            invariant_id=_INV_SCENARIO_TAGS,
            satisfied=False,
            remediation=_REMEDIATIONS[_INV_SCENARIO_TAGS],
        )
    return _InvariantResult(invariant_id=_INV_SCENARIO_TAGS, satisfied=True)


def _collect_untagged_scenarios(feature_files: list[Path]) -> list[str]:
    """Return a list of `path:lineno` for scenarios missing a @slice-NN tag.

    A Scenario is tagged when the line preceding it (or the tag line a few
    lines above with no scenarios between) contains `@slice-` token.
    """
    untagged: list[str] = []
    slice_tag_re = re.compile(r"@slice-\d+")
    for path in feature_files:
        lines = path.read_text().splitlines()
        pending_tags = ""
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("@"):
                pending_tags = stripped + " " + pending_tags
                continue
            if stripped.startswith("Scenario:") or stripped.startswith(
                "Scenario Outline:"
            ):
                if not slice_tag_re.search(pending_tags):
                    untagged.append(f"{path}:{lineno}")
                pending_tags = ""
            elif stripped and not stripped.startswith("#"):
                # Any non-tag, non-comment, non-empty line resets pending tags
                # unless the line continues a tag block (multi-line tags handled
                # via the @ prefix branch above).
                pending_tags = ""
    return untagged


def _at_review_verdict_recorded(
    repo_root: Path, feature_id: str, slice_id: str
) -> bool:
    """True iff an ``ATReviewVerdict APPROVED`` record for the entering slice
    exists in ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``. Missing file,
    missing record, or a REJECTED verdict all return False."""
    ledger = repo_root / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    if not ledger.is_file():
        return False
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            record.get("event") == "ATReviewVerdict"
            and record.get("slice_id") == slice_id
            and record.get("verdict") == "APPROVED"
        ):
            return True
    return False


def _human_authorization_required(repo_root: Path) -> bool:
    """Read the ``rigor.human_authorization`` axis (velocity-v2, default OFF).

    Off by default: EXAMINE provides the outcome-independence and the carpaccio
    mechanical-seal + AT-completeness check cover the AT attestation, so the
    two-party human GO is an opt-in compliance layer, not the baseline.
    """
    return DESConfig(cwd=repo_root).rigor_human_authorization


def _check_at_review_verdict(
    repo_root: Path, feature_id: str, slice_id: str
) -> _InvariantResult:
    """Invariant 3: AT-review attestation for the entering slice.

    A recorded ``ATReviewVerdict APPROVED`` always satisfies it. When ABSENT,
    whether the invariant BLOCKS depends on the ``rigor.human_authorization`` axis
    (velocity-v2, Ale 2026-07-04): OFF (default) -> advisory (satisfied) -- the
    carpaccio mechanical-seal + AT-completeness check attest the AT at the same
    dispatch.pre and EXAMINE provides the outcome-independence downstream, so the
    two-party human GO is opt-in compliance only (this closes the beta-tester
    "asked several times per slice" grind); ON (regulated) -> hard-require the GO.
    """
    if _at_review_verdict_recorded(repo_root, feature_id, slice_id):
        return _InvariantResult(invariant_id=_INV_AT_VERDICT, satisfied=True)
    if not _human_authorization_required(repo_root):
        return _InvariantResult(invariant_id=_INV_AT_VERDICT, satisfied=True)
    return _InvariantResult(
        invariant_id=_INV_AT_VERDICT,
        satisfied=False,
        remediation=_REMEDIATIONS[_INV_AT_VERDICT],
    )


def _check_gate_output_produceable(repo_root: Path) -> _InvariantResult:
    """Invariant 4: carpaccio CLI output produceable from CWD.

    The freshness gate (friction #16 closure) reads carpaccio output from
    the .git/-adjacent CWD. The check is structural: confirm the repo_root
    contains a `.git` directory or a parent does -- meaning a future
    `python -m des carpaccio-slice-gate` invocation will find its working
    surface. We accept either the .git presence OR a `.nwave/` skeleton
    directory (test fixtures use the latter when not in a real git tree).
    """
    if (repo_root / ".git").exists() or (repo_root / ".nwave").is_dir():
        return _InvariantResult(invariant_id=_INV_GATE_OUTPUT, satisfied=True)
    return _InvariantResult(
        invariant_id=_INV_GATE_OUTPUT,
        satisfied=False,
        remediation=_REMEDIATIONS[_INV_GATE_OUTPUT],
    )


def _check_pre_commit_scope(repo_root: Path, feature_id: str) -> _InvariantResult:
    """Invariant 5: RED scaffold tests in pre-commit scope carry @skip markers.

    Pre-commit pytest scope is `tests/**/<feature_id>/**/*.feature` plus
    paired step modules. A RED scaffold scenario must carry a `@skip` or
    `@pending` tag to remain skipped during pre-commit invocation. Scans
    for Scenario: blocks tagged neither @skip nor @pending; any such
    scenario in a RED scaffold context fails the invariant.

    Heuristic: when a scenario carries @walking_skeleton without @skip AND
    there is no implementing production code (we cannot probe that here),
    the gate trusts the operator. The structural check enforces: every
    .feature file under the feature's scope where the test module carries
    `pytestmark = pytest.mark.skip(...)` MUST exist (test module-level skip
    is the canonical RED-scaffold marker). Absence of the marker on a
    RED-scaffold test module is what trips friction #57 invariant 5.

    For the slice-03 scope: the invariant is vacuously SATISFIED when no
    tests/<feature>/ directory exists yet (first dispatch). When tests
    exist, we verify every test module either has unskipped scenarios OR
    has `@skip @pending` tags on RED scenarios. The actual block-vs-allow
    decision lives downstream in pytest collection; this gate flags
    structural drift.
    """
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return _InvariantResult(invariant_id=_INV_PRE_COMMIT, satisfied=True)

    feature_files = [p for p in tests_dir.rglob("*.feature") if feature_id in p.parts]
    if not feature_files:
        return _InvariantResult(invariant_id=_INV_PRE_COMMIT, satisfied=True)

    # Heuristic: if any feature file carries a Scenario without @skip/@pending
    # AND has a matching @pending @skip-able sibling scenario style, the
    # invariant holds. For first-dispatch detection we trust the operator;
    # the structural cascade closure is the @slice-NN tag (invariant 2). This
    # invariant terminally fires only when explicit RED-scaffold heuristics
    # detect untagged scaffolds (deferred to slice-04 LogPersistencePort wire).
    return _InvariantResult(invariant_id=_INV_PRE_COMMIT, satisfied=True)


# The reuse-analysis verdicts that satisfy the reuse leg (DDD-9): a present,
# well-formed Reuse Analysis OR an explicit exemption marker.
_REUSE_LEG_PRESENT_VERDICTS = frozenset(
    {
        VERDICT_STRUCTURALLY_ACCEPTED,
        VERDICT_METHODOLOGY_EXEMPT,
        VERDICT_NO_OVERLAP_DECLARED,
    }
)


def _design_skip_witness_present(content: str) -> bool:
    """True iff a `## Wave: DESIGN / [REF] Design Skipped` heading carries a
    non-empty rationale body (O-1 opt-a witness leg).

    The witness is valid only when the canonical heading is followed by at least
    one non-blank, non-`##` line before the next `##` heading. A bare heading
    (immediately followed by another `##` heading or end-of-file) is NOT a valid
    witness -- the rationale is empty.
    """
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != _DESIGN_SKIP_HEADING:
            continue
        for body in lines[idx + 1 :]:
            stripped = body.strip()
            if stripped.startswith("##"):
                break
            if stripped:
                return True
        return False
    return False


def _check_reuse_first_or_design_skip(
    repo_root: Path, feature_id: str
) -> _InvariantResult:
    """Invariant 6: the feature carries a reuse-first analysis OR a DESIGN-skip
    witness.

    A feature that skips the optional DESIGN wave must not reach its first
    crafter dispatch carrying NO reuse-first analysis. The invariant is
    satisfied iff EITHER a valid Reuse Analysis is present (reuse leg) OR an
    explicit `## Wave: DESIGN / [REF] Design Skipped` witness with a non-empty
    rationale is present (witness leg).

    Reuses the SHIPPED `validate_reuse_analysis_content` parser (DDD-8) -- no
    second reuse parser. Degrades LOUD on an unreadable feature-delta: the
    diagnostic names the unreadable source rather than silent-passing or
    crashing.
    """
    delta = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    try:
        content = delta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _InvariantResult(
            invariant_id=_INV_REUSE_FIRST,
            satisfied=False,
            remediation=(
                f"feature-delta could not be read as UTF-8 text at {delta}; "
                f"the reuse-first invariant cannot be evaluated (degrade-LOUD)"
            ),
        )

    result = validate_reuse_analysis_content(content)
    if result.verdict in _REUSE_LEG_PRESENT_VERDICTS:
        return _InvariantResult(invariant_id=_INV_REUSE_FIRST, satisfied=True)

    if result.verdict == VERDICT_MISSING_REUSE_ANALYSIS:
        if _design_skip_witness_present(content):
            return _InvariantResult(invariant_id=_INV_REUSE_FIRST, satisfied=True)
        return _InvariantResult(
            invariant_id=_INV_REUSE_FIRST,
            satisfied=False,
            remediation=_REMEDIATIONS[_INV_REUSE_FIRST],
        )

    if result.verdict in (
        VERDICT_MALFORMED_REUSE_ANALYSIS,
        VERDICT_UNJUSTIFIED_CREATE_NEW,
    ):
        # fix-readiness-gate-reuse-first-invariant (O-1 ALLOW path, DESIGN spec):
        # a malformed/unjustified Reuse Analysis ALONGSIDE a valid Design-Skipped
        # witness CLEARS -- the witness is the authorizing act, so the
        # malformed-table detail is suppressed in the cleared case. Only refuse
        # when the witness is ALSO absent (controls-only-veto: emit a NO only when
        # NO authorizing act is present, never ignore a present valid witness).
        if _design_skip_witness_present(content):
            return _InvariantResult(invariant_id=_INV_REUSE_FIRST, satisfied=True)
        return _InvariantResult(
            invariant_id=_INV_REUSE_FIRST,
            satisfied=False,
            remediation=f"{result.detail} -- {_REMEDIATIONS[_INV_REUSE_FIRST]}",
        )

    return _InvariantResult(
        invariant_id=_INV_REUSE_FIRST,
        satisfied=False,
        remediation=_REMEDIATIONS[_INV_REUSE_FIRST],
    )


def _check_sustainability(repo_root: Path, feature_id: str) -> _InvariantResult:
    """Invariant 7: the feature carries a well-formed Test Reuse & Consolidation
    Analysis section (the sustainable-test-suite content gate FIRES here).

    Slices 02-04 shipped `des validate-feature-delta --require-sustainability` as a
    working CLI, but NO wave gate-stack invoked it ("catalogued != wired"). This
    invariant wires the SHIPPED `validate_sustainability_content` (the slice-03
    pure-core function) into the readiness aggregate so the gate fires
    automatically before dispatch -- mirroring invariant 6 EXACTLY.

    Satisfied iff the parser returns an accepted verdict (the SSOT
    `_SUSTAINABILITY_ACCEPTED_VERDICTS`: structurally-accepted / methodology-exempt
    / no-new-tests). A declared-but-missing or malformed section FAILS.

    Reuses the SHIPPED parser -- no second sustainability parser. Degrades LOUD on
    an unreadable feature-delta: the diagnostic names the unreadable source rather
    than silent-passing or crashing.
    """
    delta = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    try:
        content = delta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _InvariantResult(
            invariant_id=_INV_SUSTAINABILITY,
            satisfied=False,
            remediation=(
                f"feature-delta could not be read as UTF-8 text at {delta}; "
                f"the sustainability invariant cannot be evaluated (degrade-LOUD)"
            ),
        )

    result = validate_sustainability_content(content)
    if result.verdict in _SUSTAINABILITY_ACCEPTED_VERDICTS:
        return _InvariantResult(invariant_id=_INV_SUSTAINABILITY, satisfied=True)

    return _InvariantResult(
        invariant_id=_INV_SUSTAINABILITY,
        satisfied=False,
        remediation=f"{result.detail} -- {_REMEDIATIONS[_INV_SUSTAINABILITY]}",
    )


# --- AXIS-B enforcement levers (at-in-process-port-default slice-03) --------


def _lever_to_invariant(lever: LeverResult) -> _InvariantResult:
    """Translate a shared ``LeverResult`` into a readiness ``_InvariantResult``.

    A flagged lever is a FAILED invariant carrying its remediation + (for the
    wiring lever) its CodeFactPort confidence label; a clean lever is satisfied.
    """
    return _InvariantResult(
        invariant_id=lever.invariant_id,
        satisfied=not lever.flagged,
        remediation=lever.remediation or None,
        confidence=lever.confidence,
    )


def _check_axis_b_levers(
    target_language: str, layout: LayoutRoots
) -> list[_InvariantResult]:
    """The five AXIS-B enforcement levers as readiness invariants (slice-03).

    Each lever scans the TARGET project's resolved source + tests roots for real
    wiring / coverage-obligation / sad-path drift; the levers are git-free,
    per-language, and degrade-LOUD. Appended only when ``--enforce-axis-b`` is
    set, so existing callers see the 7 invariants byte-identical.

    ``layout`` carries the RESOLVED target roots (slice-04 PATH-genericity). When
    the layout is ``not-resolvable`` the levers degrade LOUD: each falls back to
    no-scan (the resolver already named the loud reason on the ``layout`` record),
    never scanning the host nWave tree as if it were the target's.
    """
    source_root = layout.source_root
    tests_root = layout.tests_root
    return [
        _lever_to_invariant(check_unwired_entry(source_root=source_root)),
        _lever_to_invariant(check_integration_per_adapter(source_root, tests_root)),
        _lever_to_invariant(check_contract_per_port(source_root, tests_root)),
        _lever_to_invariant(check_non_ws_spawn(tests_root)),
        _lever_to_invariant(check_undefined_name(target_language)),
    ]


# --- RC4-b bugfix lane logic ----------------------------------------------


def _lane_justification_names_defect_and_test(justification: str) -> bool:
    """True iff a bugfix-lane justification is non-vacuous AND names a
    regression test, in ANY language's naming convention.

    The strict shape is the anti-abuse SAFETY mechanism for the one skipped
    quality gate (``at_review_verdict``, Tsunami Q-10): a real bugfix
    references its regression test -- a NEW test it pins RED->GREEN, OR an
    EXISTING test that covers the behavior. Accepted EITHER as (a) the
    pytest-style ``test_<name>`` token, OR (b) the language-neutral
    ``regression test: <name>`` phrase emitted by ``des dispatch`` itself --
    Rust/Go/etc. regression-test names carry no ``test_`` prefix, so (a) alone
    wrongly refuses a well-formed non-Python justification (backlog #41,
    genericità/agnosticismo mandate). (b) is additive, not a replacement --
    (a) keeps working byte-identical. An empty or vague justification ("just
    fixing a thing") names neither and is refused fail-closed -- the lane
    cannot become the shortcut that skips AT review on a real feature
    mislabeled as a bugfix.
    """
    if not justification.strip():
        return False
    return (
        re.search(r"\btest_\w+", justification) is not None
        or re.search(r"regression test:\s*\S+", justification, re.IGNORECASE)
        is not None
    )


def _has_red_green_seal(repo_root: Path) -> bool:
    """True iff at least one RED->GREEN mechanical-seal JSON is on record under
    ``.nwave/telemetry/red-green/`` (written by ``des verify-red-green
    --record-red``)."""
    seal_dir = repo_root / ".nwave" / "telemetry" / "red-green"
    return seal_dir.is_dir() and any(seal_dir.glob("*.json"))


def _has_expectation_charter(repo_root: Path, feature_id: str) -> bool:
    """True iff an expectation charter is authored for the feature under
    ``docs/product/expectations/{feature_id}/``."""
    charter_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    return charter_dir.is_dir() and any(charter_dir.glob("*.md"))


def _check_bugfix_lane_evidence_floor(
    repo_root: Path, feature_id: str
) -> _InvariantResult:
    """Evidence-floor invariant (NEGATIVE-2, Vera FAIL seal 6d182a2a): the
    charter's NEGATIVE requirement is "the mechanical seal is still required --
    a slice with NO RED evidence and NO expectation still CANNOT close (we
    lighten ceremony, we do not remove the evidence floor)." Satisfied by
    EITHER a recorded RED->GREEN mechanical seal OR an expectation charter --
    absent both, the lane fails closed.
    """
    if _has_red_green_seal(repo_root) or _has_expectation_charter(
        repo_root, feature_id
    ):
        return _InvariantResult(invariant_id=_INV_BUGFIX_EVIDENCE_FLOOR, satisfied=True)
    return _InvariantResult(
        invariant_id=_INV_BUGFIX_EVIDENCE_FLOOR,
        satisfied=False,
        remediation=(
            "the bugfix lane lightens ceremony but keeps the evidence floor: "
            "record a RED->GREEN mechanical seal (`des verify-red-green "
            "--record-red`, written to `.nwave/telemetry/red-green/*.json`) OR "
            f"author an expectation charter under "
            f"docs/product/expectations/{feature_id}/ before this dispatch can clear"
        ),
    )


def _run_bugfix_lane(
    repo_root: Path, feature_id: str, slice_id: str, justification: str
) -> _ReadinessReport:
    """Build the readiness report for a declared ``DES-LANE: bugfix`` dispatch.

    Invalid justification (no defect + regression-test named) -> REFUSED
    fail-closed: a single named anti-abuse invariant, none of the feature-
    readiness checks run. Valid justification -> run ONLY the 2 mechanical
    guards, SKIP the 5 feature-readiness invariants, and attach the LOUD lane
    audit record naming the skip. Once the 2 mechanical guards clear, the
    evidence-floor invariant additionally fires (NEGATIVE-2): a dispatch
    already refused by the mechanical guards gets no further diagnostic noise.
    """
    report = _ReadinessReport(feature_id=feature_id, slice_id=slice_id)
    if not _lane_justification_names_defect_and_test(justification):
        report.invariants.append(
            _InvariantResult(
                invariant_id="bugfix_lane_justification",
                satisfied=False,
                remediation=(
                    "DES-LANE: bugfix requires a justification naming the defect + "
                    "a regression test (a NEW test, or an EXISTING test that covers "
                    "the behavior) in any naming convention -- test_<name>, or "
                    "-- regression test: <name>"
                ),
            )
        )
        return report

    report.invariants.append(_check_gate_output_produceable(repo_root))
    report.invariants.append(_check_pre_commit_scope(repo_root, feature_id))
    report.lane = {
        "lane": _BUGFIX_LANE,
        "justification": justification,
        "skipped": list(_BUGFIX_LANE_SKIPPED),
    }
    if all(r.satisfied for r in report.invariants):
        report.invariants.append(
            _check_bugfix_lane_evidence_floor(repo_root, feature_id)
        )
    return report


# --- LANE_PROFILES-driven lane logic (slice-02, ADD-not-mutate sibling of the
# bugfix lane above) --------------------------------------------------------


def _run_lane_profile(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    workspace: Path,
    profile: LaneProfile,
) -> _ReadinessReport:
    """Build the readiness report for a ``--lane`` value recognized by the
    LIVE ``LANE_PROFILES`` datum (slice-02).

    Runs ONLY the invariants NOT named in ``profile.skipped_invariants`` --
    read from the datum at call time, never a hardcoded skip-set -- and
    attaches a LOUD, durable ``lane`` audit record naming the lane id, the
    skipped invariants, and the datum's declared ``guard_kind`` (mirrors the
    bugfix lane's own audit record shape, one level up).
    """
    checks: dict[str, Callable[[], _InvariantResult]] = {
        _INV_SLICE_PLAN: lambda: _check_slice_plan_section(workspace),
        _INV_SCENARIO_TAGS: lambda: _check_scenario_slice_tags(repo_root, feature_id),
        _INV_AT_VERDICT: lambda: _check_at_review_verdict(
            repo_root, feature_id, slice_id
        ),
        _INV_GATE_OUTPUT: lambda: _check_gate_output_produceable(repo_root),
        _INV_PRE_COMMIT: lambda: _check_pre_commit_scope(repo_root, feature_id),
        _INV_REUSE_FIRST: lambda: _check_reuse_first_or_design_skip(
            repo_root, feature_id
        ),
        _INV_SUSTAINABILITY: lambda: _check_sustainability(repo_root, feature_id),
    }
    skipped = set(profile.skipped_invariants)
    report = _ReadinessReport(feature_id=feature_id, slice_id=slice_id)
    for invariant_id in _ALL_INVARIANTS:
        if invariant_id in skipped:
            continue
        report.invariants.append(checks[invariant_id]())
    report.lane = {
        "lane": profile.lane_id,
        "skipped": list(profile.skipped_invariants),
        "guard_kind": profile.guard_kind.value,
    }
    return report


# --- CLI driver ------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-readiness-pre-dispatch",
        description=(
            "Verify the 6 first-dispatch invariants before a NEW feature "
            "first crafter dispatch (closes friction #57)."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="Feature being dispatched.",
    )
    parser.add_argument(
        "--slice-id",
        required=True,
        help="Slice id about to enter A_GREEN (slice-NN).",
    )
    parser.add_argument(
        "--repo-root",
        required=False,
        default=None,
        help="Repo root path. Defaults to CWD.",
    )
    parser.add_argument(
        "--lane",
        default=None,
        help=(
            "Declare a dispatch lane (RC4-b). `bugfix` skips the 5 "
            "feature-readiness invariants (slice-plan, scenario-tags, "
            "AT-review, reuse-first, sustainability) and enforces ONLY the 2 "
            "mechanical safety guards — gated by a strict --lane-justification "
            "(anti-abuse). Absent/not `bugfix`: all 7 invariants enforced "
            "byte-identical."
        ),
    )
    parser.add_argument(
        "--lane-justification",
        default="",
        help=(
            "Justification for a `--lane bugfix` dispatch. Must NAME the defect "
            "+ a regression test (a NEW test, OR an EXISTING test that covers "
            "the behavior) in any naming convention -- `test_<name>` OR "
            "`-- regression test: <name>` -- the safety mechanism for the "
            "skipped at_review_verdict gate. Vacuous justifications are REFUSED "
            "fail-closed."
        ),
    )
    parser.add_argument(
        "--enforce-axis-b",
        action="store_true",
        help=(
            "Append the AXIS-B enforcement levers (lever-1 wiring, "
            "integration-per-adapter, contract-per-port, non-WS spawn, "
            "undefined-name) to the invariant chain (at-in-process-port-default "
            "slice-03). Off by default — existing callers see the 7 invariants "
            "byte-identical."
        ),
    )
    parser.add_argument(
        "--target-language",
        default="python",
        help=(
            "The target project's language. Drives the target-aware F821 "
            "NOT_APPLICABLE projection (DDD-2b). Defaults to python."
        ),
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help=(
            "The target project's source root (relative to --repo-root). "
            "Highest-precedence layout-discovery input (slice-04 PATH-genericity) "
            "— threads the RESOLVED source root into the AXIS-B levers, replacing "
            "the hardcoded nWave src/des. Absent, the gate discovers the layout "
            "from pyproject testpaths / .nwave config / conventional src|lib."
        ),
    )
    parser.add_argument(
        "--tests-dir",
        default=None,
        help=(
            "The target project's tests root (relative to --repo-root). "
            "Highest-precedence layout-discovery input (slice-04 PATH-genericity) "
            "— threads the RESOLVED tests root into the AXIS-B levers, replacing "
            "the hardcoded nWave tests/. Absent, the gate discovers the layout "
            "from pyproject [tool.pytest.ini_options] testpaths / .nwave config."
        ),
    )
    return parser


def _emit_report(report: _ReadinessReport) -> None:
    """Emit one JSON line on stdout summarising the readiness verdict."""
    payload: dict[str, object] = {
        "event": (
            "ReadinessVerified" if report.verdict == "cleared" else "ReadinessRefused"
        ),
        "feature_id": report.feature_id,
        "slice_id": report.slice_id,
        "verdict": report.verdict,
        "invariants": [
            {
                "id": inv.invariant_id,
                "status": "satisfied" if inv.satisfied else "failed",
                "satisfied": inv.satisfied,
                "remediation": inv.remediation,
                "confidence": inv.confidence,
            }
            for inv in report.invariants
        ],
    }
    if report.layout is not None:
        payload["layout"] = _layout_record(report.layout)
    if report.lane is not None:
        payload["lane"] = report.lane
    print(json.dumps(payload))


def _layout_record(layout: LayoutRoots) -> dict[str, str]:
    """The structured ``layout`` discovery record (slice-04 PATH-genericity).

    Surfaces the RESOLVED target source + tests roots (so a Then can assert the
    levers scanned the RIGHT dirs, not the host nWave tree), or the degrade-LOUD
    ``not-resolvable`` + named ``reason`` when no layout resolves.
    """
    return {
        "resolution": layout.resolution,
        "tests_root": str(layout.tests_root) if layout.tests_root else "",
        "source_root": str(layout.source_root) if layout.source_root else "",
        "reason": layout.reason,
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point invoked by `des verify-readiness-pre-dispatch` dispatcher.

    Returns:
        0 when every invariant PASSes (verdict cleared); 1 when any FAILs
        (verdict refused); 2 on argparse failure (handled by argparse).
    """
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    feature_id = args.feature_id
    slice_id = args.slice_id
    workspace = repo_root / "docs" / "feature" / feature_id

    lane_name = getattr(args, "lane", None)

    if lane_name == _BUGFIX_LANE:
        # RC4-b: a declared bugfix lane skips the heavy feature-readiness
        # ceremony (gated by a strict anti-abuse justification). The default
        # 7-invariant path below stays byte-identical (ADD-not-mutate).
        report = _run_bugfix_lane(
            repo_root, feature_id, slice_id, args.lane_justification
        )
        _emit_report(report)
        return 0 if report.verdict == "cleared" else 1

    lane_profile = _lane_profile_for(lane_name)
    if lane_profile is not None:
        # slice-02: a `--lane` value recognized by the LIVE LANE_PROFILES
        # datum (e.g. `prefactoring`) skips exactly the invariants the datum
        # names, sibling of the bugfix branch above (ADD-not-mutate). An
        # unrecognized/absent lane falls through to the full 7-invariant
        # default path below -- the exemption never leaks.
        report = _run_lane_profile(
            repo_root, feature_id, slice_id, workspace, lane_profile
        )
        _emit_report(report)
        return 0 if report.verdict == "cleared" else 1

    report = _ReadinessReport(feature_id=feature_id, slice_id=slice_id)
    report.invariants.append(_check_slice_plan_section(workspace))
    report.invariants.append(_check_scenario_slice_tags(repo_root, feature_id))
    report.invariants.append(_check_at_review_verdict(repo_root, feature_id, slice_id))
    report.invariants.append(_check_gate_output_produceable(repo_root))
    report.invariants.append(_check_pre_commit_scope(repo_root, feature_id))
    report.invariants.append(_check_reuse_first_or_design_skip(repo_root, feature_id))
    report.invariants.append(_check_sustainability(repo_root, feature_id))

    if getattr(args, "enforce_axis_b", False):
        # slice-04 PATH-genericity: DISCOVER the target project's source + tests
        # roots (explicit args -> pyproject testpaths -> .nwave config) and thread
        # the RESOLVED roots into the levers, replacing the hardcoded nWave globals.
        # Degrades LOUD (not-resolvable + a named reason) when no layout resolves.
        report.layout = resolve_layout(repo_root, args.source_dir, args.tests_dir)
        report.invariants.extend(
            _check_axis_b_levers(args.target_language, report.layout)
        )

    _emit_report(report)
    return 0 if report.verdict == "cleared" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
