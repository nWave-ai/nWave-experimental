"""Platform-agnostic feature-end-cycle use-case (DDD-7, slice-03).

slice-03 of oss-feature-end-emit-cli. The ORCHESTRATOR half of the feature-end
cycle: it RUNS the two already-CLI'd feature-end gates whose heartbeats prove
they ran -- the walking-skeleton gate (``WalkingSkeletonGateRan``) and the
environmental-e2e gate (``EnvironmentalE2eGateRan``) -- then SIGNS the
deep-review verdict (reuse slice-02 ``feature_end_sign_service``) and EMITS the
two feature-end records (reuse slice-01 ``AtCompletionLedger.append_feature_end_
event``).

DDD-7 separation: this is the platform-agnostic DECISION logic. BOTH the
``des feature-end run`` CLI shim AND the eventual SubagentStop hook shim invoke
this SAME use-case -- one logic, two thin driving adapters. The shims carry NO
orchestration logic.

ANTI-THEATER INVARIANT (DDD-6, load-bearing, per ``feedback_earned_trust_
mechanical_evidence_not_llm_verdict``): the cycle RUNS the REAL gate CLIs and
derives their verdicts from the REAL gate runs -- never from an input flag (the
verdict-laundering the C_REVIEWER_AUDIT caught and this revision closes). Each
gate appends its heartbeat as the cycle reaches and runs that leg (RM-1: a
heartbeat present means "the cycle reached and ran this gate"). The
walking-skeleton gate appends its own ``WalkingSkeletonGateRan`` on entry
(``walking_skeleton_gate.py:177``); the cycle appends ``EnvironmentalE2eGateRan``
immediately before it invokes the real env-e2e gate (the gate CLI does not yet
emit it). When a REAL gate run FAILS, the cycle fail-closes: it emits NO signed
verdict and NO ``EBatchRefactorCompleted`` / ``FeatureEndReviewVerdict`` record,
and returns a structured refusal -- never a fake pass, never a false
"feature-end complete".

COVERAGE-MAP LEG (DDD-8, slice-04, option (b) RM-1-HONEST): after the env-e2e
leg passes and before sign/emit, the cycle RUNS the ported §5.3 coverage-map
verify core IN-PROCESS (``coverage_map_verify_service.verify_coverage_map``, a
byte-for-byte relocation of the ``scripts/cli/verify_coverage_map.py`` §5.3 core
-- COPIED, never imported, per F-D-09). On a GENUINE human-signed PASS the cycle
appends BOTH ``CoverageMapVerifiedAt{Distill,Deliver}Exit`` records (RM-1: the
heartbeat is written ONLY after a REAL verify pass, so heartbeat-present <=>
gate-ran-AND-passed). On an UNSIGNED / stale / structurally-incomplete /
attestation-gap / malformed coverage-map the verify core REFUSES, the cycle
fail-closes (``CycleRefusal`` -> ``FeatureEndCycleRefused`` exit 2), and NEITHER
coverage-map record is minted. So after slice-04 the cycle runs ALL SIX legs and,
on a genuine signed pass, emits ALL SIX records -> ``des verify-integrity``
reports the feature FULLY reconciled. The signed digest is, by the upstream
``fix-distill-human-signoff`` design, a HUMAN act -- an autonomous orchestrator
cannot mint it, so a genuinely-unsigned feature CORRECTLY refuses (no human
signoff <=> no ``CoverageMapVerified*`` record <=> the feature-end is genuinely
incomplete).

Stdlib + PyYAML at this layer (the ledger + signer SSOTs are stdlib HMAC + JSONL;
the gates are invoked as subprocesses over the ``des`` dispatcher, never
imported; the coverage-map verify is an in-process ``src/des`` call, no
subprocess), so the use-case is bundle-safe and host-agnostic.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import subprocess

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.logging.at_completion_ledger import (
    EBATCH_REFACTOR_COMPLETED,
    FEATURE_END_REVIEW_VERDICT,
    AtCompletionLedger,
)
from des.application.coverage_map_verify_service import (
    CoverageMapRefused,
    verify_coverage_map,
)
from des.application.feature_end_sign_service import (
    SignRefusal,
    sign_feature_end_review,
)
from des.cli.record_examine_verdict import examine_ledger_path
from des.cli.verify_fresh_clone import RECIPE_RELPATH
from des.domain.examine_verdict_signing import charter_seal as _charter_seal
from des.runtime.interpreter import des_spawn


_MANIFEST_NAME = "walking-skeleton.json"
_FEATURE_DELTA_NAME = "feature-delta.md"

# The examine-verdict ledger's event name (mirrors ``commit_slice.py``'s
# ``_EXAMINE_VERDICT_EVENT``) and the feature-end scope marker: a feature-end
# examine is recorded with ``--slice feature-end`` (never a real slice-id), so
# it cannot be confused with a per-slice PASS recorded during delivery.
_EXAMINE_VERDICT_RECORDED_EVENT = "ExamineVerdictRecorded"
_FEATURE_END_EXAMINE_SLICE_ID = "feature-end"


@dataclass(frozen=True)
class CycleSuccess:
    """The cycle ran every gate, signed the verdict, and emitted both records."""

    verdict_hash: str


@dataclass(frozen=True)
class CycleRefusal:
    """The cycle fail-closed: a gate failed or the verdict could not be signed.

    No signed verdict was produced and no feature-end record was emitted -- the
    anti-theater invariant: a failed gate yields no fake "feature-end complete".
    """

    error: str


@dataclass(frozen=True)
class FullSuiteLegRan:
    """The feature-end full-suite leg ran ONCE and passed (slice-05, AT-19).

    slice-05 / §V.B ATs@slice / full-suite-once@feature-end allocation: a
    DISTINCT clean full-suite leg added to the feature-end cycle. It runs the
    FULL contract suite ONCE at feature-end (via the RETAINED whole-tree
    ``run_contract_gate`` full-suite mode -- ``_full_suite_marker_args``), NOT at
    every commit-slice (the obsolete behavior C10 removes from the per-slice
    path). Carries the suite's pytest exit code: presence of this arm <=> the
    full-suite leg RAN AND passed (anti-theater: a failed full suite fail-closes
    the cycle, no ``FullSuiteLegRan``).
    """

    pytest_exit_code: int


@dataclass(frozen=True)
class FullSuiteLegNotApplicable:
    """The feature-end full-suite leg had no contract suite to run (slice-05, AT-19).

    The genericità counterpart of :class:`FullSuiteLegRan` (mirrors the empty
    arch-set "CLEARS" rule in ``run_contract_gate._arch_invariant_paths`` and the
    coverage-map / env-e2e NA legs): the feature-end cycle runs on the TARGET
    repo, and a repo that carries NO collectable contract suite (an external
    target, or a minimal feature workspace) has NO full suite to run. There is
    nothing to certify, so the leg is NOT_APPLICABLE and the cycle PROCEEDS --
    never a fake pass, never a fail-close on an absent suite. Carries the reason
    naming WHY the leg was inapplicable (degrade-LOUD, no silent skip).

    Anti-theater is preserved: a PRESENT-but-RED full suite still fail-closes
    (``CycleRefusal``); only a genuinely-ABSENT suite is NA.
    """

    reason: str


@dataclass(frozen=True)
class FreshCloneLegRan:
    """The fresh-clone leg ran the REAL ``des verify-fresh-clone`` gate and the
    committed tree verified in a fresh export (exit 0, slice-01, D-2/D-3)."""


@dataclass(frozen=True)
class FreshCloneLegNotApplicable:
    """The fresh-clone leg found no ``.nwave/demo-recipe.json`` declared
    (slice-01, D-2). The gate's own exit-2 INDETERMINATE degrades to a
    non-blocking NA here: a repo never asked to have a demo recipe is not
    held to one, and the cycle PROCEEDS.
    """

    reason: str


@dataclass(frozen=True)
class ExecutionReachLegRan:
    """The execution-reach leg ran the REAL ``des verify-execution-reach``
    gate and every production file under the conventional source root showed
    >0 observed line hits (exit 0, slice-02, D-2/D-3)."""


@dataclass(frozen=True)
class ExecutionReachLegNotApplicable:
    """The execution-reach leg found no coverage XML at the conventional path
    (slice-02, D-2). The gate's own exit-2 INDETERMINATE degrades to a
    non-blocking NA here: a repo never asked to instrument coverage is not
    held to a reach check over it, and the cycle PROCEEDS.
    """

    reason: str


@dataclass(frozen=True)
class DocCoherenceLegRan:
    """The doc-coherence leg ran the REAL ``des verify-doc-coherence``
    gate and every checked doc claim is true of the tree (exit 0, slice-03,
    D-2/D-3)."""


@dataclass(frozen=True)
class DocCoherenceLegNotApplicable:
    """The doc-coherence leg found no README* / ``docs/`` at all (slice-03,
    D-2). The gate's own exit-2 INDETERMINATE degrades to a non-blocking NA
    here: a repo that ships no docs claims at all is not held to this check,
    and the cycle PROCEEDS.
    """

    reason: str


@dataclass(frozen=True)
class WalkingSkeletonNotApplicable:
    """The walking-skeleton floor granted NOT_APPLICABLE (slice-04, DDD-1).

    A THIRD return arm of the WS leg, distinguishing the un-gameable
    not-applicable verdict from a proceed-with-root PASS and a refuse. The cycle
    PROPAGATES this NA to the env-e2e leg (the feature ships no installable
    artifact by the SAME delta cross-check, so there is nothing to build /
    install / run in a real environment). Carries the WS rationale so the
    env-e2e NA marker can record WHY the leg was inapplicable.
    """

    rationale: str


def run_feature_end_cycle(
    *,
    repo_root: Path,
    feature_id: str,
    feature_dir: Path,
    reviewer_agent_id: str | None,
    verdict: str | None,
) -> CycleSuccess | CycleRefusal:
    """Run the feature-end cycle: run the REAL gates, then sign + emit.

    Returns :class:`CycleSuccess` carrying the signed ``verdict_hash`` when both
    REAL gate runs passed and the deep-review verdict signed; otherwise
    :class:`CycleRefusal` naming the violated precondition -- no record emitted.

    The two gate legs run the REAL gate CLIs (``des walking-skeleton-gate
    --feature-dir`` and ``des verify-environmental-e2e --mode run``) and the
    cycle derives each verdict from the gate's REAL exit code -- never from an
    input flag. The walking-skeleton gate appends its own
    ``WalkingSkeletonGateRan`` heartbeat on entry; the cycle appends
    ``EnvironmentalE2eGateRan`` right before it runs the env-e2e gate (RM-1), so
    every heartbeat reflects a genuine gate run.
    """
    ledger = AtCompletionLedger(feature_id, repo_root)

    # ROOT FIX (adversarial swarm 2026-06-29): refuse to seal a TRUNCATED feature
    # BEFORE running the gates (fail-fast). A Slice-Plan slice declared but never
    # delivered (no `.feature` / no attested prose) means the feature-end cycle
    # was DECOUPLED from verify-integrity's truncation oracle -- it could emit a
    # FeatureEnd record that `des verify-integrity` then REJECTS (the swarm proved
    # P1+P2 were sealed-but-truncated theater-seals). Run the SAME un-gameable
    # oracle here, fail-closed (no record emitted), so the seal and its integrity
    # check can no longer disagree.
    from des.cli.verify_deliver_integrity import _undelivered_slice_plan_slices

    undelivered = _undelivered_slice_plan_slices(repo_root, feature_id)
    if undelivered:
        return CycleRefusal(
            f"cannot seal {feature_id!r}: its Slice-Plan declares "
            f"{sorted(undelivered)} with no delivered acceptance-test (.feature) "
            "file or attested prose -- the feature is TRUNCATED. Deliver or "
            "reconcile the missing slice(s) before the feature-end seal "
            "(verify-integrity parity: the seal must not emit a record its own "
            "integrity check would reject)."
        )

    walking_skeleton = _run_walking_skeleton_gate(
        repo_root=repo_root, feature_dir=feature_dir
    )
    if isinstance(walking_skeleton, CycleRefusal):
        return walking_skeleton

    environmental = _run_environmental_e2e_gate(
        ledger=ledger,
        repo_root=repo_root,
        feature_id=feature_id,
        feature_dir=feature_dir,
        walking_skeleton=walking_skeleton,
    )
    if isinstance(environmental, CycleRefusal):
        return environmental

    coverage_map = _run_coverage_map_verify_leg(
        ledger=ledger,
        repo_root=repo_root,
        feature_id=feature_id,
        feature_dir=feature_dir,
    )
    if isinstance(coverage_map, CycleRefusal):
        return coverage_map

    full_suite = _run_full_suite_leg(repo_root=repo_root)
    if isinstance(full_suite, CycleRefusal):
        return full_suite
    # FullSuiteLegRan / FullSuiteLegNotApplicable both PROCEED: a green suite and
    # a genuinely-absent suite are equally non-blocking (only a PRESENT-but-RED
    # suite returns CycleRefusal above). f-nonbypassable-attestation slice-01
    # (DDD-4): EMIT the leg's outcome as a feature-end ledger record so the
    # done-gate can make it `required` and refuse on its ABSENCE -- the leg was
    # a control-flow return type only, written by NO ledger call before.
    if isinstance(full_suite, FullSuiteLegRan):
        ledger.append_full_suite_leg_ran(feature_id=feature_id)
    else:
        ledger.append_full_suite_leg_not_applicable(feature_id=feature_id)

    # P0 evidence-by-execution gate block (evolution-plan P0.1/P0.4/P0.5,
    # "wiring into the feature-end stack = P2.2"): ordered
    # doc-coherence -> execution-reach -> fresh-clone (D-1, the cheapest
    # static check runs first).
    doc_coherence = _run_doc_coherence_gate(
        ledger=ledger, repo_root=repo_root, feature_id=feature_id
    )
    if isinstance(doc_coherence, CycleRefusal):
        return doc_coherence
    if isinstance(doc_coherence, DocCoherenceLegRan):
        ledger.append_doc_coherence_verified(feature_id=feature_id)
    else:
        ledger.append_doc_coherence_not_applicable(feature_id=feature_id)

    execution_reach = _run_execution_reach_gate(
        ledger=ledger, repo_root=repo_root, feature_id=feature_id
    )
    if isinstance(execution_reach, CycleRefusal):
        return execution_reach
    if isinstance(execution_reach, ExecutionReachLegRan):
        ledger.append_execution_reach_verified(feature_id=feature_id)
    else:
        ledger.append_execution_reach_not_applicable(feature_id=feature_id)

    fresh_clone = _run_fresh_clone_gate(
        ledger=ledger, repo_root=repo_root, feature_id=feature_id
    )
    if isinstance(fresh_clone, CycleRefusal):
        return fresh_clone
    if isinstance(fresh_clone, FreshCloneLegRan):
        ledger.append_fresh_clone_verified(feature_id=feature_id)
    else:
        ledger.append_fresh_clone_not_applicable(feature_id=feature_id)

    feature_end_examine = _run_feature_end_examine_leg(
        repo_root=repo_root, feature_id=feature_id
    )
    if isinstance(feature_end_examine, CycleRefusal):
        return feature_end_examine

    signed = sign_feature_end_review(
        feature_id=feature_id,
        reviewer_agent_id=reviewer_agent_id,
        verdict=verdict,
        repo_root=repo_root,
    )
    if isinstance(signed, SignRefusal):
        return CycleRefusal(signed.error)

    ledger.append_feature_end_event(
        EBATCH_REFACTOR_COMPLETED, None, feature_id=feature_id
    )
    ledger.append_feature_end_event(
        FEATURE_END_REVIEW_VERDICT, signed.verdict_hash, feature_id=feature_id
    )
    return CycleSuccess(signed.verdict_hash)


def _run_walking_skeleton_gate(
    *, repo_root: Path, feature_dir: Path
) -> Path | WalkingSkeletonNotApplicable | CycleRefusal:
    """Run the REAL walking-skeleton gate; surface its PASS-vs-NA distinction.

    Invokes ``des walking-skeleton-gate --feature-dir <dir> --repo-root <repo>``
    as a subprocess. The gate appends its own ``WalkingSkeletonGateRan`` heartbeat
    on entry (RM-1) and emits its verdict as single-line JSON on STDOUT.

    slice-04 DDD-1: the WS gate maps BOTH ``pass`` and ``not_applicable`` to exit
    0 (parity is load-bearing for the downstream ``proceeds`` contract), so the
    cycle reads the gate's emitted ``WalkingSkeletonGateVerdict`` ``verdict``
    field to distinguish them -- a pure parse of the captured stdout, no new gate
    change:

      * ``verdict == "pass"`` -> the manifest ``feature_root`` Path so the
        env-e2e leg can build the same project (today's proceed path).
      * ``verdict == "not_applicable"`` -> :class:`WalkingSkeletonNotApplicable`
        carrying the gate's rationale; the cycle propagates NA to the env-e2e
        leg (DDD-2).
      * non-zero exit (FAIL / USAGE / INDETERMINATE) -> :class:`CycleRefusal`
        with the slice-01 diagnostic filter.

    Degrade LOUD: an exit 0 whose stdout carries no parseable
    ``WalkingSkeletonGateVerdict`` line is NOT silently assumed PASS or NA -- the
    cycle returns a :class:`CycleRefusal` naming the unreadable verdict, never a
    fabricated proceed.
    """
    completed = _dispatch(
        repo_root,
        [
            "walking-skeleton-gate",
            "--feature-dir",
            str(feature_dir),
            "--repo-root",
            str(repo_root),
        ],
    )
    if completed.returncode != 0:
        return CycleRefusal(
            "the walking-skeleton gate failed; the feature-end cycle refuses to "
            "certify the feature-end is complete (anti-theater): "
            + _gate_diagnostic(completed)
        )
    verdict = _walking_skeleton_verdict(completed.stdout)
    if verdict is None:
        return CycleRefusal(
            "the walking-skeleton gate exited 0 but emitted no readable verdict; "
            "the feature-end cycle refuses to certify the feature-end is complete "
            "(anti-theater): " + _gate_diagnostic(completed)
        )
    name, rationale = verdict
    if name == "not_applicable":
        return WalkingSkeletonNotApplicable(rationale=rationale)
    return _feature_root_from_manifest(feature_dir, repo_root)


def _walking_skeleton_verdict(stdout: str) -> tuple[str, str] | None:
    """Parse the gate's ``WalkingSkeletonGateVerdict`` (verdict, rationale) from stdout.

    The gate emits a single-line JSON object (``cli/walking_skeleton_gate.py``
    ``_emit``) carrying ``event`` / ``verdict`` / ``reason`` / ``diagnostic``.
    Returns the ``(verdict, rationale)`` pair -- rationale prefers ``diagnostic``
    (where ``not_applicable`` carries its rationale) and falls back to ``reason``
    -- or ``None`` when no such line is present (the LOUD-refusal trigger).
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("event") != "WalkingSkeletonGateVerdict":
            continue
        verdict = payload.get("verdict")
        if not isinstance(verdict, str):
            return None
        diagnostic = payload.get("diagnostic")
        reason = payload.get("reason")
        rationale = ""
        if isinstance(diagnostic, str) and diagnostic.strip():
            rationale = diagnostic
        elif isinstance(reason, str):
            rationale = reason
        return verdict, rationale
    return None


def _run_environmental_e2e_gate(
    *,
    ledger: AtCompletionLedger,
    repo_root: Path,
    feature_id: str,
    feature_dir: Path,
    walking_skeleton: Path | WalkingSkeletonNotApplicable,
) -> None | CycleRefusal:
    """Run the REAL environmental-e2e gate; fail-close on a REAL FAIL.

    slice-04 DDD-2: when the walking-skeleton floor granted NOT_APPLICABLE the
    feature ships no installable artifact, so the env-e2e leg is inapplicable by
    the SAME mechanical delta cross-check. The cycle SKIPS the
    ``des verify-environmental-e2e --mode run`` subprocess (running it would be
    wasted work + risk a spurious build) and records the leg NOT_APPLICABLE: it
    appends the ``EnvironmentalE2eGateRan`` heartbeat ("the cycle reached the
    leg") AND the DISTINCT ``EnvironmentalE2eNotApplicable`` marker carrying the
    propagated WS rationale -- NEVER ``EnvironmentalE2eVerified`` (minting it on
    an un-run leg would be theater). The propagation is un-gameable because the
    WS-NA is ALREADY the slice-03 delta cross-check: a feature whose delta ADDS a
    new installable root is WS-FAILed, so leg 1 returns a refusal and this NA
    branch is never reached.

    On the WS-PASS path the env-e2e leg runs as today: RM-1 appends the
    ``EnvironmentalE2eGateRan`` heartbeat BEFORE it invokes the gate, then runs
    ``des verify-environmental-e2e --mode run`` against the installable
    ``feature_root`` (build + install + run the feature's env-e2e test, exit 0 =
    PASS). On a REAL PASS the cycle ALSO appends the
    ``EnvironmentalE2eVerified`` positive-proof record (R3 -- the cycle wrote
    only the heartbeat before; the record is NOT yet added to the integrity
    ``required`` set, a separate deliberate tightening). A non-zero exit
    fail-closes the cycle.
    """
    if isinstance(walking_skeleton, WalkingSkeletonNotApplicable):
        ledger.append_environmental_e2e_gate_ran(feature_id=feature_id)
        ledger.append_environmental_e2e_not_applicable(feature_id=feature_id)
        return None

    ledger.append_environmental_e2e_gate_ran(feature_id=feature_id)
    completed = _dispatch(
        repo_root,
        [
            "verify-environmental-e2e",
            "--mode",
            "run",
            "--feature-id",
            feature_id,
            "--feature-delta",
            str(feature_dir / _FEATURE_DELTA_NAME),
            "--source-tree",
            str(walking_skeleton),
        ],
    )
    if completed.returncode != 0:
        return CycleRefusal(
            "the environmental-e2e gate failed; the feature-end cycle refuses to "
            "certify the feature-end is complete (anti-theater): "
            + _gate_diagnostic(completed)
        )
    ledger.append_environmental_e2e_verified(feature_id=feature_id)
    return None


def _run_coverage_map_verify_leg(
    *,
    ledger: AtCompletionLedger,
    repo_root: Path,
    feature_id: str,
    feature_dir: Path,
) -> None | CycleRefusal:
    """Run the REAL ported §5.3 coverage-map verify IN-PROCESS; emit on a genuine pass.

    DDD-8 / option (b): the cycle runs the ported pure verify core against the
    feature's ``distill/coverage-map.md`` (no subprocess -- ``src/des`` calling
    ``src/des``, mirroring the in-process ledger appends). RM-1-HONEST: the two
    ``CoverageMapVerifiedAt{Distill,Deliver}Exit`` heartbeats are appended ONLY
    after a REAL verify PASS, so heartbeat-present <=> the leg ran AND passed.

    slice-04 DDD-3 (opt-in-until-adopted, anti-theater-FIRST): coverage-map NA is
    granted when AND ONLY when adoption is INACTIVE repo-wide AND the map is
    GENUINELY ABSENT. The adoption switch is the ``coverage_map_adoption`` key in
    ``repo_root/.nwave/des-config.json``, read through the STANDARD ``DESConfig``
    loader (NO hand-rolled second JSON read -- SSOT) from ``repo_root`` ONLY (the
    LOAD-BEARING un-per-feature-gameability invariant: a feature self-shipping its
    own ``feature_dir/.nwave/des-config.json`` is IGNORED -- it cannot flip its
    own adoption state). The degrade is asymmetric (CONCERN-2): an absent key ⇒
    inactive (permissive NA); a malformed/unreadable config ⇒ active (hard-verify,
    toward MORE rigour). On the NA path the cycle mints the DISTINCT
    ``CoverageMapNotApplicableAt{Distill,Deliver}Exit`` markers (never the
    verified records).

    A PRESENT map is ALWAYS held to the real verify, never NA -- so a half-baked
    map cannot dodge by claiming NA. While adoption is ACTIVE an absent map
    hard-refuses (today's behaviour). On a genuine human-signed PASS, append BOTH
    verified records. On ANY verify refusal (unsigned ``_pending_`` digest, stale
    digest, structural-incomplete, attestation-gap, malformed) the cycle
    fail-closes carrying the verify core's own structured reason and mints
    NEITHER coverage-map record.
    """
    coverage_map_path = feature_dir / "distill" / "coverage-map.md"
    adoption = DESConfig(cwd=repo_root).coverage_map_adoption
    if adoption == "inactive" and not coverage_map_path.is_file():
        ledger.append_coverage_map_not_applicable_at_distill_exit(feature_id=feature_id)
        ledger.append_coverage_map_not_applicable_at_deliver_exit(feature_id=feature_id)
        return None

    verdict = verify_coverage_map(feature_root=feature_dir)
    if isinstance(verdict, CoverageMapRefused):
        return CycleRefusal(
            "the coverage-map verify refused; the feature-end cycle refuses to "
            "certify the feature-end is complete (anti-theater): "
            f"{verdict.token}: {verdict.message}"
        )
    ledger.append_coverage_map_verified_at_distill_exit(feature_id=feature_id)
    ledger.append_coverage_map_verified_at_deliver_exit(feature_id=feature_id)
    return None


def _run_full_suite_leg(
    *, repo_root: Path
) -> FullSuiteLegRan | FullSuiteLegNotApplicable | CycleRefusal:
    """Run the FULL contract suite ONCE at feature-end (slice-05, AT-19, §V.B).

    The full-suite-once@feature-end allocation: a DISTINCT clean leg that runs
    the FULL whole-tree contract suite ONE time at feature-end -- the RETAINED
    full-suite leg the per-commit-slice path no longer runs (C10). It invokes the
    REAL ``des run-contract-gate`` default (full-suite) mode (the retained
    whole-tree run owned by ``run_contract_gate._full_suite_marker_args``) and
    derives the verdict from its REAL exit code -- never an input flag
    (anti-theater, DDD-6).

    Genericità (STANDING mandate, the same "empty set CLEARS" rule as
    ``run_contract_gate._arch_invariant_paths``): the feature-end cycle runs on
    the TARGET repo, and a repo that carries NO collectable contract suite (an
    external target, or a minimal feature workspace) has NO full suite to run.
    Such a repo gets :class:`FullSuiteLegNotApplicable` and the cycle PROCEEDS --
    refusing here would break feature-end on every target without an nWave-shaped
    contract tree. Only a PRESENT suite is held to the run: a green suite yields
    ``FullSuiteLegRan`` (gate exit 0); a PRESENT-but-RED suite fail-closes
    (``CycleRefusal``), so a real regression still yields no signed verdict.
    """
    if not _repo_has_contract_suite(repo_root):
        return FullSuiteLegNotApplicable(
            "the target repository carries no collectable contract suite; the "
            "feature-end full-suite leg is not applicable (no full suite to run)"
        )
    completed = _dispatch(repo_root, ["run-contract-gate", "--repo", str(repo_root)])
    if completed.returncode != 0:
        return CycleRefusal(
            "the feature-end full-suite leg failed; the feature-end cycle refuses "
            "to certify the feature-end is complete (anti-theater): "
            + _gate_diagnostic(completed)
        )
    return FullSuiteLegRan(pytest_exit_code=completed.returncode)


def _repo_has_contract_suite(repo_root: Path) -> bool:
    """Whether ``repo_root`` carries at least one collectable contract node-id.

    Reuses the single contract-collection seam (``run_contract_gate.
    _collect_node_ids``, DDD-12 -- no new pytest call site) to ask the genuine
    question "does this repo have a full suite to run?". Returns True when the
    collection finds at least one node-id; False when the repo collects nothing
    (no full suite -> the leg is NOT_APPLICABLE). An untrustworthy collection is
    treated as "no suite to certify here" rather than crashing the cycle -- the
    PRESENT-but-RED anti-theater path is the gate run itself, not this presence
    probe.
    """
    from des.cli.run_contract_gate import _collect_node_ids, _CollectionError
    from des.runtime.interpreter import InterpreterUnavailable

    try:
        return bool(_collect_node_ids(repo_root))
    except (_CollectionError, OSError, InterpreterUnavailable):
        # InterpreterUnavailable: a non-pytest repo (e.g. Rust-only: cargo, no
        # pytest interpreter) collects no pytest contract suite -> NOT_APPLICABLE,
        # the cycle PROCEEDS (the documented graceful-degradation intent above).
        # Aligned with the lib edit Lyra@tsunami applied 2026-06-28 (Ale option-B);
        # sibling of #73. Mirrors worktree commit 6c9ac9cea (FIX2).
        return False


_DOC_COHERENCE_DOCS_DIRNAME = "docs"


def _run_doc_coherence_gate(
    *, ledger: AtCompletionLedger, repo_root: Path, feature_id: str
) -> DocCoherenceLegRan | DocCoherenceLegNotApplicable | CycleRefusal:
    """Run the REAL ``des verify-doc-coherence`` gate (slice-03, evolution-plan
    P0.5, L-2). Derives the verdict from the gate's REAL exit code -- never an
    input flag (anti-theater, DDD-6). Mirrors :func:`_run_execution_reach_gate`'s
    ``LegRan | LegNotApplicable | CycleRefusal`` three-arm shape; runs FIRST of
    the three P0 legs (D-1: the cheapest static check runs first).

    D-2 PRECONDITION-FIRST (L-4 NA rule): a target repo shipping no README* at
    its root and no ``docs/`` directory has nothing honest for the
    doc-coherence gate to check -- so the leg returns
    :class:`DocCoherenceLegNotApplicable` and the cycle PROCEEDS WITHOUT
    spawning the gate (never a false hard-block on a repo that ships no docs
    claims at all). The presence check runs FIRST, before ANY subprocess,
    mirroring the gate's own default doc-location convention (L-5: this reads
    the same convention without importing ``verify_doc_coherence.py``).

    When docs ARE present, RM-1 appends the ``DocCoherenceGateRan`` heartbeat
    BEFORE the verdict is known (its presence means "the cycle reached and ran
    this leg"), then dispatches the REAL gate and derives the verdict from its
    REAL exit code (anti-theater, DDD-6): exit 0 -> :class:`DocCoherenceLegRan`
    (every checked doc claim is true of the tree); exit 2 ->
    :class:`DocCoherenceLegNotApplicable` (the gate's own INDETERMINATE, e.g.
    an unreadable docs location surviving the presence check); any OTHER
    non-zero exit (1: >=1 doc claim is false of the actual tree) fail-closes
    the cycle carrying the gate's own diagnostic (which names every false
    claim).
    """
    if not _repo_has_doc_claims(repo_root):
        return DocCoherenceLegNotApplicable(
            "no README or docs/ directory found; the doc-coherence gate is "
            "not applicable"
        )
    ledger.append_doc_coherence_gate_ran(feature_id=feature_id)
    completed = _dispatch(repo_root, ["verify-doc-coherence", "--repo", str(repo_root)])
    if completed.returncode == 2:
        return DocCoherenceLegNotApplicable(
            "the doc-coherence gate degraded to INDETERMINATE; not applicable"
        )
    if completed.returncode != 0:
        return CycleRefusal(
            "the feature-end doc-coherence gate failed; the feature-end "
            "cycle refuses to certify the feature-end is complete "
            "(anti-theater): " + _gate_diagnostic(completed)
        )
    return DocCoherenceLegRan()


def _repo_has_doc_claims(repo_root: Path) -> bool:
    """Whether ``repo_root`` ships any README* file or a ``docs/`` directory
    (mirrors ``verify_doc_coherence._find_doc_files``'s default doc-location
    convention; L-5: does not import ``verify_doc_coherence.py``)."""
    if any(repo_root.glob("README*")):
        return True
    return (repo_root / _DOC_COHERENCE_DOCS_DIRNAME).is_dir()


_COVERAGE_XML_RELPATH = "coverage.xml"
_EXECUTION_REACH_SRC_DIR = "src"


def _run_execution_reach_gate(
    *, ledger: AtCompletionLedger, repo_root: Path, feature_id: str
) -> ExecutionReachLegRan | ExecutionReachLegNotApplicable | CycleRefusal:
    """Run the REAL ``des verify-execution-reach`` gate (slice-02, evolution-plan
    P0.4, L-2). Derives the verdict from the gate's REAL exit code -- never an
    input flag (anti-theater, DDD-6). Mirrors :func:`_run_fresh_clone_gate`'s
    ``LegRan | LegNotApplicable | CycleRefusal`` three-arm shape.

    D-2 PRECONDITION-FIRST (L-4 NA rule): a target repo that never produced a
    Cobertura coverage report at the conventional path (``<repo>/coverage.xml``)
    has nothing honest for the execution-reach gate to judge -- so the leg
    returns :class:`ExecutionReachLegNotApplicable` and the cycle PROCEEDS
    WITHOUT spawning the gate (never a false hard-block on a repo that never
    opted into coverage instrumentation). The presence check runs FIRST,
    before ANY subprocess, so a minimal target tree (no coverage XML) is NA
    rather than a spurious refusal on the gate's own environment-degrade exit
    code.

    When the coverage XML IS present, RM-1 appends the ``ExecutionReachGateRan``
    heartbeat BEFORE the verdict is known (its presence means "the cycle
    reached and ran this leg"), then dispatches the REAL gate and derives the
    verdict from its REAL exit code (anti-theater, DDD-6): exit 0 ->
    :class:`ExecutionReachLegRan` (every production file under the
    conventional source root shows >0 observed line hits); exit 2 ->
    :class:`ExecutionReachLegNotApplicable` (the gate's own INDETERMINATE,
    e.g. a ``--src-dir`` that does not resolve under a non-conventional
    source layout, or a malformed/empty coverage report -- a repo the gate
    cannot judge, per R8 genericita -- mirrors :func:`_run_doc_coherence_gate`
    and :func:`_run_fresh_clone_gate`'s own ``== 2`` NA branch); any OTHER
    non-zero exit (1: >=1 production file with zero hits or absent from the
    report) fail-closes the cycle carrying the gate's own diagnostic (which
    names every unreached file).
    """
    coverage_xml_path = repo_root / _COVERAGE_XML_RELPATH
    if not coverage_xml_path.is_file():
        return ExecutionReachLegNotApplicable(
            "no coverage XML found at the conventional path; the "
            "execution-reach gate is not applicable"
        )
    ledger.append_execution_reach_gate_ran(feature_id=feature_id)
    completed = _dispatch(
        repo_root,
        [
            "verify-execution-reach",
            "--coverage-xml",
            str(coverage_xml_path),
            "--src-dir",
            _EXECUTION_REACH_SRC_DIR,
            "--repo",
            str(repo_root),
        ],
    )
    if completed.returncode == 2:
        return ExecutionReachLegNotApplicable(
            "the execution-reach gate degraded to INDETERMINATE; not applicable"
        )
    if completed.returncode != 0:
        return CycleRefusal(
            "the feature-end execution-reach gate failed; the feature-end "
            "cycle refuses to certify the feature-end is complete "
            "(anti-theater): " + _gate_diagnostic(completed)
        )
    return ExecutionReachLegRan()


def _run_fresh_clone_gate(
    *, ledger: AtCompletionLedger, repo_root: Path, feature_id: str
) -> FreshCloneLegRan | FreshCloneLegNotApplicable | CycleRefusal:
    """Run the REAL ``des verify-fresh-clone`` gate (slice-01, evolution-plan
    P0.1, L-2). Derives the verdict from the gate's REAL exit code -- never an
    input flag (anti-theater, DDD-6). Mirrors :func:`_run_full_suite_leg`'s
    ``LegRan | LegNotApplicable | CycleRefusal`` three-arm shape.

    D-2 PRECONDITION-FIRST (L-4 NA rule): a target repo that never declared a
    ``.nwave/demo-recipe.json`` has nothing honest for the fresh-clone gate to
    execute -- so the leg returns :class:`FreshCloneLegNotApplicable` and the
    cycle PROCEEDS WITHOUT spawning the gate (never a false hard-block on a repo
    that was never asked to have a demo recipe). The presence check runs FIRST,
    before ANY subprocess, so a minimal target tree (no recipe, no
    git-archivable install manifest -- the exact shape of the examine-leg unit
    fixtures) is NA rather than a spurious refusal on the gate's own
    environment-degrade exit code.

    When the recipe IS present, RM-1 appends the ``FreshCloneGateRan`` heartbeat
    BEFORE the verdict is known (its presence means "the cycle reached and ran
    this leg"), then dispatches the REAL gate and derives the verdict from its
    REAL exit code (anti-theater, DDD-6): exit 0 -> :class:`FreshCloneLegRan` (a
    genuine fresh-export build pass); exit 2 -> :class:`FreshCloneLegNotApplicable`
    (the gate's own INDETERMINATE on a malformed/absent recipe); any OTHER
    non-zero exit (1: a real recipe step failed in the fresh export of the
    committed tree; 78: an environment degrade) fail-closes the cycle carrying
    the gate's own diagnostic.
    """
    recipe_path = repo_root / RECIPE_RELPATH
    if not recipe_path.is_file():
        return FreshCloneLegNotApplicable(
            "no demo recipe declared; the fresh-clone gate is not applicable"
        )
    ledger.append_fresh_clone_gate_ran(feature_id=feature_id)
    completed = _dispatch(repo_root, ["verify-fresh-clone", "--repo", str(repo_root)])
    if completed.returncode == 2:
        return FreshCloneLegNotApplicable(
            "the fresh-clone gate degraded to INDETERMINATE; not applicable"
        )
    if completed.returncode != 0:
        return CycleRefusal(
            "the feature-end fresh-clone gate failed; the feature-end cycle "
            "refuses to certify the feature-end is complete (anti-theater): "
            + _gate_diagnostic(completed)
        )
    return FreshCloneLegRan()


def _charter_dir(repo_root: Path, feature_id: str) -> Path:
    """Where a feature's User-Examiner charters live, per the P1.2 convention."""
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _repo_relative_str(path: Path, repo_root: Path) -> str:
    """Repo-relative string form of ``path`` (mirrors ``commit_slice._repo_relative``)."""
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _feature_end_examine_remediation(feature_id: str, charter_relpath: str) -> str:
    return (
        "dispatch nw-user-examiner against the charter at FEATURE scope, then "
        f"record its verdict: `des record-examine-verdict --repo <repo> "
        f"--feature-id {feature_id} --slice {_FEATURE_END_EXAMINE_SLICE_ID} "
        f"--charter {charter_relpath} --verdict PASS --observations <text> "
        "--examiner nw-user-examiner`"
    )


def _latest_feature_end_examine_verdict(
    repo_root: Path, feature_id: str, charter_relpath: str
) -> dict[str, object] | None:
    """The latest feature-end-scoped ``ExamineVerdict`` for one charter, or None.

    Mirrors ``commit_slice._latest_examine_verdict`` but additionally filters
    on ``charter_path`` (a feature can carry SEVERAL charters, each requiring
    its OWN fresh PASS) and pins ``slice_id == "feature-end"`` (never a real
    slice-id -- a per-slice PASS recorded during delivery can never satisfy
    the feature-end requirement).
    """
    ledger_path = examine_ledger_path(repo_root, feature_id)
    if not ledger_path.is_file():
        return None
    latest: dict[str, object] | None = None
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") != _EXAMINE_VERDICT_RECORDED_EVENT:
            continue
        if record.get("slice_id") != _FEATURE_END_EXAMINE_SLICE_ID:
            continue
        if record.get("charter_path") != charter_relpath:
            continue
        latest = record
    return latest


def _check_feature_end_examine(
    repo_root: Path, feature_id: str, charter_path: Path
) -> CycleRefusal | None:
    """Assert ``charter_path`` has a fresh feature-end PASS; else refuse LOUD.

    Mirrors ``commit_slice.check_examine_verdict``'s refusal taxonomy
    (Missing / Refused / Indeterminate / Stale), scoped to ``slice_id ==
    "feature-end"`` and to THIS charter. Every refusal states WHAT charter
    failed, WHY, and HOW to remediate -- never a bare event name.
    """
    charter_relpath = _repo_relative_str(charter_path, repo_root)
    record = _latest_feature_end_examine_verdict(repo_root, feature_id, charter_relpath)

    if record is None:
        return CycleRefusal(
            f"charter {charter_relpath!r} has no recorded FEATURE-END "
            "examine-verdict (ExamineVerdictMissing); the feature-end cycle "
            "refuses to certify the feature is done (anti-theater): a charter "
            "exists under docs/product/expectations, so a fresh PASS "
            "ExamineVerdict recorded at feature scope "
            f"(slice={_FEATURE_END_EXAMINE_SLICE_ID}) is required before done. "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    verdict = record.get("verdict")

    if verdict == "FAIL":
        return CycleRefusal(
            f"charter {charter_relpath!r} was examined at feature scope and "
            "FAILED (ExamineVerdictRefused): "
            f"{record.get('observations', '')}; the feature-end cycle refuses "
            "to certify the feature is done. Fix the feature per the "
            f"examiner's observations, then "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    if verdict == "INDETERMINATE":
        return CycleRefusal(
            f"charter {charter_relpath!r}'s recorded feature-end examine-verdict "
            "is INDETERMINATE (ExamineVerdictIndeterminate); an unexaminable "
            "feature carries no observable done-proof (never a silent pass). "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    if verdict != "PASS":
        return CycleRefusal(
            f"charter {charter_relpath!r}'s recorded feature-end verdict is "
            f"unrecognised: {verdict!r} (ExamineVerdictStale); only PASS / "
            "FAIL / INDETERMINATE are valid examine verdicts. "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    recorded_seal = record.get("charter_seal")
    if not isinstance(recorded_seal, str):
        return CycleRefusal(
            f"charter {charter_relpath!r}'s feature-end PASS record is "
            "malformed (missing charter_seal, ExamineVerdictStale) and cannot "
            "be re-verified. "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    if not charter_path.is_file():
        return CycleRefusal(
            f"the examined charter no longer exists: {charter_relpath!r} "
            "(ExamineVerdictStale); a PASS verdict is bound to the charter "
            "bytes at exam time -- an absent charter cannot be re-verified. "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )

    current_seal = _charter_seal(charter_path.read_bytes())
    if current_seal != recorded_seal:
        return CycleRefusal(
            f"the charter changed after its feature-end examination: "
            f"{charter_relpath!r} (ExamineVerdictStale); the recorded "
            "charter_seal no longer matches the charter's CURRENT bytes -- the "
            "PASS verdict is void (stale-seal, never a silent pass). "
            + _feature_end_examine_remediation(feature_id, charter_relpath)
        )
    return None


def _run_feature_end_examine_leg(
    *, repo_root: Path, feature_id: str
) -> None | CycleRefusal:
    """Require a fresh feature-end PASS for EVERY charter; ARMED only when any exist.

    ADD-not-mutate, mirrors the per-slice ``commit_slice`` examine gate at
    FEATURE scope: the per-slice gate already requires execution-observation
    before a slice may commit; this leg requires the SAME discipline again, at
    feature scope, before the feature-end cycle may sign + declare done.

    ARMING (backward-compat): a no-op when the feature carries NO charters
    under ``docs/product/expectations/{feature_id}/*.md`` -- so the entire
    pre-existing feature-end test suite (no charters) stays green, byte-
    identical to the pre-P2.2 cycle. A feature that HAS adopted the charter
    convention must re-examine EVERY charter at feature scope; any charter
    with no feature-end PASS / a FAIL / INDETERMINATE / stale-seal fail-closes
    the WHOLE cycle (no signed verdict, no feature-end record).
    """
    charter_dir = _charter_dir(repo_root, feature_id)
    if not (charter_dir.is_dir() and any(charter_dir.glob("*.md"))):
        return None
    for charter_path in sorted(charter_dir.glob("*.md")):
        refusal = _check_feature_end_examine(repo_root, feature_id, charter_path)
        if refusal is not None:
            return refusal
    return None


def _feature_root_from_manifest(feature_dir: Path, repo_root: Path) -> Path:
    """Read the installable ``feature_root`` from the walking-skeleton manifest.

    The manifest the walking-skeleton gate already consumes declares
    ``feature_root`` -- the installable project the env-e2e gate must build. A
    relative root resolves against ``feature_dir`` (the same rule the gate uses);
    a missing manifest resolves to ``repo_root`` so a degenerate stage still
    points the env-e2e gate at a real tree.
    """
    manifest_path = feature_dir / _MANIFEST_NAME
    if not manifest_path.is_file():
        return repo_root
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    feature_root = manifest.get("feature_root")
    if not isinstance(feature_root, str):
        return repo_root
    root = Path(feature_root)
    if not root.is_absolute():
        root = (feature_dir / root).resolve()
    return root


def _strip_runtime_event_lines(text: str) -> str:
    """Drop ``des.runtime.*`` event lines that shadow the gate's real reason.

    On a dev checkout the freshness probe prints a ``des.runtime.freshness``
    JSON event to STDERR via ``.git/`` adjacency. That noise would otherwise
    win the stderr-or-stdout precedence and garble the reported refusal cause.
    A line is dropped only when it parses to a JSON object whose ``event`` is a
    string starting ``des.runtime.``; every other line (non-JSON, JSON without
    such an ``event``) is kept verbatim.
    """
    kept: list[str] = []
    for line in text.splitlines():
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            kept.append(line)
            continue
        event = parsed.get("event") if isinstance(parsed, dict) else None
        if isinstance(event, str) and event.startswith("des.runtime."):
            continue
        kept.append(line)
    return "\n".join(kept)


def _gate_diagnostic(completed: subprocess.CompletedProcess[str]) -> str:
    """The gate's own diagnostic for the refusal error (the REAL fail reason)."""
    stderr = _strip_runtime_event_lines(completed.stderr)
    return (stderr.strip() or completed.stdout.strip()) or (
        f"gate exited {completed.returncode} with no diagnostic"
    )


def _dispatch(repo_root: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a ``des <argv>`` subcommand over the real ``des`` dispatcher.

    Nested gate dispatches run with the des-runtime freshness gate DISABLED
    (``NWAVE_FRESHNESS=skip``): the feature-end cycle is the OUTER command and
    owns freshness once, at its own entry -- a nested ``des <gate>`` spawned
    against a TARGET repo (a plain tmp fixture with no ``_install_manifest.json``
    and no ``.git/`` adjacency to auto-skip) would otherwise trip the freshness
    gate's DEGRADED exit 78 and mask the gate's OWN execution verdict (0/1/2).
    Skipping freshness here lets each leg derive its verdict from the REAL gate
    exit code (anti-theater, DDD-6) -- the audit-bearing ``des.runtime.freshness.
    skipped`` event still records the bypass on the child's stderr.
    """
    env = {**os.environ, "NWAVE_FRESHNESS": "skip"}
    return des_spawn(
        None,
        "des.cli.__main__",
        *argv,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
    )


__all__ = [
    "CycleRefusal",
    "CycleSuccess",
    "DocCoherenceLegNotApplicable",
    "DocCoherenceLegRan",
    "ExecutionReachLegNotApplicable",
    "ExecutionReachLegRan",
    "FreshCloneLegNotApplicable",
    "FreshCloneLegRan",
    "FullSuiteLegNotApplicable",
    "FullSuiteLegRan",
    "WalkingSkeletonNotApplicable",
    "run_feature_end_cycle",
]
