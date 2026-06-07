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
import subprocess
from dataclasses import dataclass
from pathlib import Path

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
from des.runtime.interpreter import python_for


_MANIFEST_NAME = "walking-skeleton.json"
_FEATURE_DELTA_NAME = "feature-delta.md"


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
    """Run a ``des <argv>`` subcommand over the real ``des`` dispatcher."""
    return subprocess.run(
        [python_for(None), "-m", "des.cli.__main__", *argv],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )


__all__ = [
    "CycleRefusal",
    "CycleSuccess",
    "WalkingSkeletonNotApplicable",
    "run_feature_end_cycle",
]
