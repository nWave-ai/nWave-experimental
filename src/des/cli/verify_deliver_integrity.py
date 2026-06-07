"""CLI: Verify deliver integrity before finalize.

Usage:
    des verify-integrity docs/feature/{project-id}/

Reads roadmap.json and execution-log.json from the project directory,
cross-references step IDs against execution-log entries, and reports
violations (steps without DES traces or with incomplete TDD phases).

Workflow-mode awareness (ADR-028 D4.2):
    Under `workflow.mode: atdd_pure` (resolved from `.nwave/config.yaml`),
    the DELIVER spine is roadmap-free and execution-log-free. In that mode
    `--roadmap-only` and the execution-log cross-reference are no-ops: a
    missing roadmap.json is the expected state (never exit 2), a leftover
    roadmap.json is a WARNING, and the verifier validates the AT-completion
    ledger instead. An absent ledger is an integrity violation (exit 1),
    never a crash. An absent `workflow.mode` key OR an absent config file now
    resolves to `atdd_pure` (DDD-7, slice-03: the canonical absent default);
    only an EXPLICIT `workflow.mode: classic` selects the classic roadmap +
    execution-log path (the 0/1/2 exit-code contract preserved byte-for-byte).

Exit codes:
    0 = All steps verified
    1 = Integrity violations found
    2 = Usage error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.config.des_config import DESConfig
from des.application.workflow_mode import ATDD_PURE_MODE, resolve_workflow_mode
from des.domain._roadmap_helpers import (
    extract_step_ids as _extract_step_ids,
)
from des.domain.deliver_integrity_verifier import DeliverIntegrityVerifier
from des.domain.roadmap_schema import RoadmapSchemaLoader
from des.domain.roadmap_validator import RoadmapValidator
from des.domain.tdd_schema import TDDSchemaLoader


__all__ = ["_extract_step_ids"]  # re-export for tests/des/unit/cli/


def _parse_execution_log(exec_log: dict) -> dict[str, list[str]]:
    """Parse execution-log.json events into step_id -> list[phase_name] mapping.

    Supports both v2.0 pipe format ("sid|phase|status|data|ts")
    and v3.0 structured format ({sid, p, s, d, t}).
    """
    entries: dict[str, list[str]] = {}
    for event in exec_log.get("events", []):
        if isinstance(event, str):
            parts = event.split("|")
            if len(parts) >= 2:
                step_id = parts[0]
                phase_name = parts[1]
                entries.setdefault(step_id, []).append(phase_name)
        elif isinstance(event, dict):
            step_id = event.get("sid", "")
            phase_name = event.get("p", "")
            if step_id and phase_name:
                entries.setdefault(step_id, []).append(phase_name)
    return entries


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-integrity",
        description=(
            "Verify TDD phase completeness for all steps in a feature deliver. "
            "Reads roadmap.json and execution-log.json, cross-references step IDs "
            "against execution-log entries, and reports violations."
        ),
        epilog=(
            "Exit codes: 0 = all steps verified | 1 = integrity violations | "
            "2 = usage / format error."
        ),
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "Path to the feature deliver directory containing roadmap.json "
            "and execution-log.json (e.g. docs/feature/<id>/deliver/)"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help=(
            "Path to the project root holding the .nwave/ ledger substrate. An "
            "alias for the positional project_dir used by the consolidated "
            "feature-end-cycle driving surface (atdd_pure spine is roadmap-free, "
            "so the project root IS the verification target)."
        ),
    )
    parser.add_argument(
        "--roadmap-only",
        action="store_true",
        help=(
            "Validate roadmap.json only (RoadmapValidator); skip the "
            "execution-log.json cross-reference. Intended for Phase 1 "
            "hard-gate use before crafter dispatch has produced any "
            "execution-log entries."
        ),
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help=(
            "The feature id under verification. In atdd_pure mode the verifier "
            "targets exactly `{feature-id}.jsonl` in the AT-completion telemetry "
            "directory. When omitted, the feature id is derived from the "
            "deliver directory layout (docs/feature/<id>/deliver/). A multi-"
            "feature telemetry directory MUST be disambiguated by this flag -- "
            "the verifier never falls through to an unrelated feature's ledger."
        ),
    )
    return parser


def _derive_feature_id(project_dir: Path) -> str | None:
    """Derive the feature id from the deliver-directory layout.

    The DELIVER spine runs against `docs/feature/<feature-id>/deliver/`, so the
    feature id is the parent directory name when `project_dir` is a `deliver`
    directory. Returns None when the layout does not match -- the caller then
    requires an explicit `--feature-id`.
    """
    resolved = project_dir.resolve()
    if resolved.name == "deliver":
        return resolved.parent.name
    return None


def _find_at_completion_ledger(
    project_dir: Path,
    feature_id: str | None = None,
    *,
    explicit: bool = False,
) -> Path | None:
    """Locate the AT-completion ledger for an atdd_pure feature (ADR-028 D3).

    The ledger is a single per-feature append-only JSONL file at
    `{project_dir}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl`.

    F-DELIVER-INTEGRITY-LEDGER-TARGETING: the verifier no longer
    glob-and-picks the alphabetically-first file -- in a multi-feature
    telemetry directory that selected an unrelated already-shipped feature's
    ledger, yielding a false-PASS. Resolution rules:

    - `explicit=True` (operator passed `--feature-id`): target
      `{feature_id}.jsonl` EXACTLY. An absent named ledger returns None -- a
      verification failure, never a fall-through to another file.
    - `explicit=False` with a derived `feature_id`: prefer the derived
      ledger; if it is absent, fall back to the single-ledger rule below so
      callers whose project layout does not encode the feature id still work.
    - no usable `feature_id`: return the sole `*.jsonl` ledger if exactly one
      exists; a multi-feature directory returns None so the caller emits a
      disambiguation diagnostic (the false-PASS guard).

    Returns the ledger path, or None when no unambiguous ledger is found.
    """
    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    if not ledger_dir.is_dir():
        return None
    if feature_id is not None:
        named = ledger_dir / f"{feature_id}.jsonl"
        if named.is_file():
            return named
        if explicit:
            return None
    ledgers = sorted(ledger_dir.glob("*.jsonl"))
    return ledgers[0] if len(ledgers) == 1 else None


# A `Slice-Id:`/`Step-Id:` commit trailer carrying a `slice-NN` identifier.
_SLICE_ID_TRAILER_RE = re.compile(r"^(?:Slice-Id|Step-Id):\s*(slice-\d+)\s*$")


def _shipped_slices(project_dir: Path) -> frozenset[str]:
    """The set of `slice-NN` carried by `Slice-Id:` trailers in the git history.

    DDD-10: a slice is "shipped" when at least one commit's message carries its
    `Slice-Id:`/`Step-Id:` trailer. Reads the whole history via `git log`. When
    `project_dir` is not a git repository the set is empty -- there is then
    nothing to reconcile and the caller falls through to the feature-end check.
    """
    try:
        output = subprocess.run(
            ["git", "log", "--format=%B%x1e"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return frozenset()
    shipped: set[str] = set()
    for message in output.split("\x1e"):
        for line in message.splitlines():
            match = _SLICE_ID_TRAILER_RE.match(line.strip())
            if match:
                shipped.add(match.group(1))
    return frozenset(shipped)


def _foreign_owned_slices(project_dir: Path, *, own_ledger: Path) -> frozenset[str]:
    """Slices POSITIVELY owned by OTHER features' AT-completion ledgers.

    F-DELIVER-INTEGRITY-LEDGER-TARGETING: a co-resident feature's slice lands
    in the shared git history (so it is in `shipped`) but is recorded in that
    other feature's ledger. Subtracting this set from `shipped - verified`
    removes the cross-feature false positive without dropping an own-feature
    slice that no other feature owns.

    Scans `.nwave/telemetry/atdd-pure/*.jsonl` EXCLUDING `own_ledger`; for each
    other ledger the owned set is `review_verdict_slices() | verified_slices()`
    (a slice reviewed OR verified by that feature). The union over every other
    ledger is foreign-owned. Computed from ledger FILES (filesystem), git-free.
    """
    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    own = own_ledger.resolve()
    foreign: set[str] = set()
    for ledger_file in sorted(ledger_dir.glob("*.jsonl")):
        if ledger_file.resolve() == own:
            continue
        other = AtCompletionLedger(ledger_file.stem, project_dir)
        try:
            foreign |= other.review_verdict_slices() | other.verified_slices()
        except LedgerIntegrityViolation:
            # A corrupt foreign ledger cannot positively own a slice -- treat
            # it as owning nothing rather than crashing this feature's verdict.
            continue
    return frozenset(foreign)


_COMMON_AUDIT_LOG_REL = Path(".nwave") / "audit" / "atdd-pure-events.jsonl"


def _verify_common_audit_log(project_dir: Path, feature_id: str | None) -> int | None:
    """Validate the common audit log substrate (slice-01 SSOT consolidation).

    Returns an exit code (0 or 1) when the common audit log exists and was
    validated; returns None when no common audit log is present and the caller
    should fall through to the legacy per-feature behavior.

    Surfaces a `LedgerIntegrityViolation` as a structured operator-readable
    diagnostic that carries the violation class, the offending line number, and
    a pointer to ``docs/operations/repair-instructions.md`` (AMEND #1: the
    operator-recoverable diagnostic surface).
    """
    common_log = project_dir / _COMMON_AUDIT_LOG_REL
    if not common_log.is_file():
        return None

    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    try:
        # Singleton-shape construction: project_root-only, no feature_id at
        # construction time. The integrity sweep runs over every record in the
        # common log regardless of any optional filter passed below.
        AtCompletionLedger(project_root=project_dir).read_records(feature_id=feature_id)
    except LedgerIntegrityViolation as exc:
        # Structured operator-recoverable diagnostic: violation class +
        # offending line number + repair-instructions pointer. AMEND #1.
        print(
            "LedgerIntegrityViolation: the common audit log failed its M7 "
            f"integrity contract.\n"
            f"  - violation class: {exc.detail}\n"
            f"  - offending line {exc.line_number} in {common_log}\n"
            f"  - see {exc.repair_instructions} for recovery steps\n"
            f"  - detail: {exc}"
        )
        return 1
    return 0


def _verify_atdd_pure(
    project_dir: Path, roadmap_path: Path, feature_id: str | None = None
) -> int:
    """Verify deliver integrity for an atdd_pure feature (ADR-028 D4.2).

    The atdd_pure spine is roadmap-free and execution-log-free. `--roadmap-only`
    and the execution-log cross-reference are no-ops here -- this branch never
    inspects either artifact for verdict purposes. The verifier validates the
    AT-completion ledger instead:

    - present ledger -> proceed to the feature-end cycle assertion;
    - absent ledger  -> structured integrity-violation diagnostic (exit 1),
      never a crash;
    - a leftover roadmap.json is the WRONG artifact for this spine, reported as
      a WARNING -- never an error.

    slice-05 revision (Finding 1): a present ledger is no longer sufficient.
    The feature-end cycle must have written an `EBatchRefactorCompleted` record
    AND a `FeatureEndReviewVerdict` record -- absent either, the cycle (batch
    refactor + deep review) never ran and integrity fails (exit 1). A corrupt
    ledger that breaks its M7 integrity contract is also exit 1, never a crash.

    SSOT consolidation (slice-01): when the common audit log
    ``.nwave/audit/atdd-pure-events.jsonl`` is present, the integrity check
    runs against it FIRST and surfaces a `LedgerIntegrityViolation` with the
    offending line number + a pointer to
    ``docs/operations/repair-instructions.md`` (AMEND #1 operator-readable
    diagnostic). With the common log present and integrity-clean OR absent,
    the verifier proceeds to the legacy per-feature feature-end cycle check.
    """
    # slice-01 SSOT consolidation: integrity-check the common audit log when
    # present. A corrupt common log is a verification failure (exit 1) carrying
    # the AMEND #1 operator-readable diagnostic; a clean (or absent) common log
    # falls through to the legacy per-feature feature-end-cycle assertion.
    common_verdict = _verify_common_audit_log(project_dir, feature_id)
    if common_verdict == 1:
        return 1

    explicit = feature_id is not None
    resolved_feature_id = feature_id or _derive_feature_id(project_dir)
    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    ledger_path = _find_at_completion_ledger(
        project_dir, resolved_feature_id, explicit=explicit
    )

    if ledger_path is None:
        if explicit:
            print(
                "INTEGRITY VIOLATION: the AT-completion ledger is missing for "
                f"feature '{resolved_feature_id}'.\n"
                f"  - expected the append-only JSONL ledger at "
                f"{ledger_dir / f'{resolved_feature_id}.jsonl'}\n"
                "  - the atdd_pure DELIVER spine records audit telemetry in the "
                "AT-completion ledger (ADR-028 D3); without it the feature has "
                "no verifiable integrity trace. The verifier targets THIS "
                "feature's ledger exactly -- an absent ledger is a verification "
                "failure, never a silent fall-through to another file."
            )
        else:
            print(
                "INTEGRITY VIOLATION: cannot determine which feature to verify.\n"
                f"  - the AT-completion telemetry directory {ledger_dir} holds "
                "more than one feature ledger (or none)\n"
                "  - pass --feature-id <id> so the verifier targets exactly "
                "that feature's ledger; it will NOT fall through to an "
                "unrelated feature's ledger (false-PASS protection)."
            )
        return 1

    # The ledger may have been resolved via the single-ledger fallback (no
    # explicit / no derived id). Bind the feature id to the located ledger so
    # the feature-end read below targets the file actually verified.
    resolved_feature_id = ledger_path.stem

    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    # DDD-10 feature-end reconciliation: every commit carrying a `Slice-Id:`
    # trailer must have a matching `SliceCommitVerified` ledger record. When
    # the M-2 commit-time backstop was bypassed (--no-verify, a foreign commit
    # path), an unrecorded slice is caught here -- the authoritative
    # feature-close sweep. Runs only when the history actually carries
    # `Slice-Id:` commits; with none there is nothing to reconcile and the
    # verdict falls through to the feature-end-cycle assertion below (the
    # classic-era roadmap-free check, unchanged).
    shipped = _shipped_slices(project_dir)
    if shipped:
        try:
            verified = AtCompletionLedger(
                resolved_feature_id, project_dir
            ).verified_slices()
        except LedgerIntegrityViolation as exc:
            print(
                json.dumps(
                    {
                        "event": "LedgerIntegrityViolation",
                        "error": (
                            "the AT-completion ledger failed its M7 integrity "
                            f"contract ({exc.detail}): {exc}"
                        ),
                    }
                )
            )
            return 1
        # F-DELIVER-INTEGRITY-LEDGER-TARGETING: start from the loud-safe
        # `shipped - verified` and SUBTRACT only slices POSITIVELY owned by
        # OTHER features' ledgers. A co-resident feature's slice shares this
        # repo's git history (so it is in `shipped`) but is recorded in that
        # other feature's ledger -- subtracting `foreign_owned` removes the
        # cross-feature false positive. An own-feature slice with the exit gate
        # skipped is in NEITHER this feature's verified/reviewed set NOR any
        # other feature's ledger, so it survives and is still reported (the
        # loud-safe done-gate). An isolated single-feature repo has an empty
        # `foreign_owned`, so the formula degenerates to `shipped - verified`.
        foreign_owned = _foreign_owned_slices(project_dir, own_ledger=ledger_path)
        unreconciled = sorted((shipped - verified) - foreign_owned)
        if unreconciled:
            print(
                json.dumps(
                    {
                        "event": "FeatureUnreconciled",
                        "feature_id": resolved_feature_id,
                        "unreconciled_slices": unreconciled,
                        "error": (
                            f"feature {resolved_feature_id!r} has Slice-Id "
                            f"commit(s) for {unreconciled} with no matching "
                            "SliceCommitVerified ledger record -- the slice "
                            "exit gate was skipped"
                        ),
                    }
                )
            )
            return 1
        # The sweep cleared -- but reconciliation and the feature-end-cycle
        # check COMPOSE: a feature with every slice reconciled while the batch
        # refactor + deep review never ran is NOT closeable. Fall through to
        # the feature-end-cycle check below rather than `return 0` here.

    if roadmap_path.exists():
        print(
            f"Warning: a leftover roadmap.json is present at {roadmap_path}. "
            "The atdd_pure spine is roadmap-free (ADR-028 D1); this stale "
            "artifact is ignored and may be removed."
        )

    # Finding 1: assert the feature-end cycle ran. The targeted feature id
    # (NOT the alphabetically-first glob match) drives the M7 fail-closed read.
    # fix-oss-environmental-e2e-gate slice-02: presence-of-proof done-gate
    # (principle 13) -- the env-e2e heartbeat MUST be present alongside the
    # E_BATCH_REFACTOR + deep-review records before the feature is closeable.
    # fix-walking-skeleton-feature-end-wiring slice-01: the walking-skeleton
    # heartbeat MUST also be present -- mirror of env-e2e slice-02, 5th sibling
    # of the pre-7af95a3d2 shipped-but-unread defect class.
    # fix-distill-signoff-feature-end-wiring slice-01: the two coverage-map
    # touchpoint heartbeats (`CoverageMapVerifiedAtDistillExit` +
    # `CoverageMapVerifiedAtDeliverExit`) emitted by the slice-06 gate are
    # also required -- closes the named residue F-SLICE-06-U4-CONSUMER-MISSING
    # from Gate D slice-06 commit `a8c9dc9d8`.
    required = {
        "CoverageMapVerifiedAtDeliverExit",
        "CoverageMapVerifiedAtDistillExit",
        "EBatchRefactorCompleted",
        "EnvironmentalE2eGateRan",
        "FeatureEndReviewVerdict",
        "WalkingSkeletonGateRan",
    }
    # fix-feature-end-ws-gate-applicability slice-04: each applicability-aware
    # required record is satisfied by itself OR its DISTINCT not-applicable
    # marker -- never a false `*Verified*`. The cycle mints the NA marker ONLY on
    # the un-gameable mechanical NA signal (WS-NA delta cross-check for env-e2e;
    # genuine-absence-under-repo-inactive-adoption for coverage). A leg with
    # NEITHER record is still caught (the silent-skip backstop is intact). The
    # `required` set is UNCHANGED (R3 sequencing caveat): it keeps demanding the
    # heartbeat / verified names so the done-gate contract for in-flight features
    # does not shift mid-stream; the NA marker merely reconciles the requirement.
    _NA_MARKER_RECONCILES = {
        "CoverageMapNotApplicableAtDistillExit": "CoverageMapVerifiedAtDistillExit",
        "CoverageMapNotApplicableAtDeliverExit": "CoverageMapVerifiedAtDeliverExit",
    }
    try:
        ledger = AtCompletionLedger(resolved_feature_id, project_dir)
        recorded = (
            ledger.feature_end_events()
            | ledger.environmental_e2e_events()
            | ledger.walking_skeleton_events()
            | ledger.coverage_map_touchpoint_events()
        )
    except LedgerIntegrityViolation as exc:
        print(
            "INTEGRITY VIOLATION: the AT-completion ledger failed its M7 "
            f"integrity contract ({exc.detail}): {exc}"
        )
        return 1

    reconciled = {
        required_name
        for na_marker, required_name in _NA_MARKER_RECONCILES.items()
        if na_marker in recorded
    }
    missing = sorted(required - recorded - reconciled)
    if missing:
        # The structured `FeatureEndCycleIncomplete` verdict (machine-readable
        # `missing_records`) is emitted on EVERY incomplete feature-end -- the
        # consolidated feature-end-cycle driving surface reads the missing set
        # off this JSON to pin partial-done honesty (slice-03 AT-4), and the
        # DDD-10 shipped-slice reconciliation path consumes it unchanged. When
        # `Slice-Id:` commits are present the message names the reconciliation
        # framing; otherwise it names the plain incomplete-cycle framing -- the
        # event + missing_records shape is identical so every consumer reads one
        # contract.
        if shipped:
            error = (
                f"feature {resolved_feature_id!r} reconciled every slice commit "
                "but the feature-end cycle is incomplete -- the ledger is "
                f"missing {missing}; the batch refactor + deep review never ran"
            )
        else:
            error = (
                f"feature {resolved_feature_id!r} has an incomplete feature-end "
                f"cycle -- the ledger is missing {missing}; the batch refactor, "
                "deep review, or a gate heartbeat never ran and was recorded"
            )
        print(
            json.dumps(
                {
                    "event": "FeatureEndCycleIncomplete",
                    "feature_id": resolved_feature_id,
                    "missing_records": missing,
                    "error": error,
                }
            )
        )
        return 1

    # Both checks cleared. With `Slice-Id:` commits this is the composed
    # reconciliation verdict (`FeatureReconciled`); otherwise the classic
    # plain-text trace verdict, unchanged.
    if shipped:
        print(
            json.dumps(
                {
                    "event": "FeatureReconciled",
                    "feature_id": resolved_feature_id,
                    "reconciled_slices": sorted(shipped),
                }
            )
        )
        return 0
    print(
        f"All slices have a complete AT-completion ledger trace: {ledger_path} "
        "and the feature-end cycle recorded its refactor + review verdict "
        "(atdd_pure: roadmap.json and execution-log.json cross-reference skipped)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    # F-2 (RC-B, ADR-025): argparse replaces hand-rolled args[0] loop. The
    # legacy loop silently swallowed `--roadmap-only` (treating it as the
    # positional path) which made the Phase 1 hard gate in
    # `nw-deliver/SKILL.md:153` non-functional. argparse natively raises
    # SystemExit on unknown flags with the usage banner.
    raw_args = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    args = parser.parse_args(raw_args)

    # `--repo` is the consolidated feature-end-cycle alias for the positional
    # project_dir; exactly one of the two locates the verification target.
    project_dir = args.project_dir if args.project_dir is not None else args.repo
    if project_dir is None:
        parser.error("a project_dir positional or --repo is required")
    roadmap_path = project_dir / "roadmap.json"

    # ADR-028 D4.2: resolve workflow mode BEFORE any roadmap.json access. Under
    # atdd_pure the spine is roadmap-free -- a missing roadmap is the expected
    # state, not exit 2 -- so the mode branch MUST run above the roadmap check.
    if resolve_workflow_mode(project_dir) == ATDD_PURE_MODE:
        return _verify_atdd_pure(project_dir, roadmap_path, args.feature_id)

    if not roadmap_path.exists():
        print(f"Error: roadmap.json not found at {roadmap_path}")
        return 2

    roadmap = json.loads(roadmap_path.read_text())

    # Structural pre-check: validate roadmap format. In --roadmap-only mode
    # this is the ONLY check; execution-log.json is never opened.
    try:
        roadmap_schema = RoadmapSchemaLoader().load()
        validator = RoadmapValidator(roadmap_schema)
        validation = validator.validate(roadmap)
        errors = [v for v in validation.violations if v.severity == "error"]
        if errors:
            print(f"ROADMAP FORMAT ERRORS ({len(errors)}):")
            for e in errors:
                print(f"  - [{e.rule}] {e.path}: {e.message}")
            print("Fix roadmap format before verifying deliver integrity.")
            return 1
    except Exception as e:
        print(f"Warning: roadmap format pre-check skipped: {e}")
        if args.roadmap_only:
            # In --roadmap-only mode the validator IS the verdict — surface
            # the failure rather than silently continuing past it.
            return 2

    if args.roadmap_only:
        print(
            f"Roadmap format OK: {roadmap_path} "
            f"(validator: no errors). --roadmap-only: execution-log skipped."
        )
        return 0

    exec_log_path = project_dir / "execution-log.json"
    if not exec_log_path.exists():
        print(f"Error: execution-log.json not found at {exec_log_path}")
        return 2

    exec_log = json.loads(exec_log_path.read_text())

    step_ids = _extract_step_ids(roadmap)
    entries = _parse_execution_log(exec_log)

    schema = TDDSchemaLoader().load()

    # F-3 (RC-C, ADR-025): the integrity verifier honours the rigor-profile
    # phase set declared in `.nwave/des-config.json`, intersected with the
    # canonical TDDSchema phase set. This lets 3-phase ADR-025 projects pass
    # integrity without spurious "missing PREPARE/RED_ACCEPTANCE/RED_UNIT"
    # errors, while legacy 5-phase projects continue to verify unchanged.
    #
    # ADR-025 dispatch (per-log auto-detect, 2026-05-18 hotfix): the CLI
    # uses the EXECUTION LOG to decide which canon applies. If ALL three
    # legacy-only phases (PREPARE, RED_ACCEPTANCE, RED_UNIT) appear in
    # ANY step's recorded events, treat the log as v4 legacy and validate
    # against the schema's `legacy_phases` tuple. Otherwise canonical.
    # Mirrors `validator._resolve_active_phases` for consistency with the
    # in-process step-completion validator.
    legacy_only = {"PREPARE", "RED_ACCEPTANCE", "RED_UNIT"}
    log_canon_is_legacy = any(
        legacy_only.issubset(set(phase_names)) for phase_names in entries.values()
    )
    active_phases = schema.legacy_phases if log_canon_is_legacy else schema.tdd_phases
    rigor_phases = DESConfig().rigor_tdd_phases
    # Empty rigor.tdd_phases is a config misconfiguration, not a degenerate
    # zero-overlap case — surface the diagnostic BEFORE the active-phases
    # fallback can mask it. The fallback (line below) is correct ONLY when
    # rigor declares non-empty phases that simply do not overlap with the
    # active canon (e.g. 3-phase rigor against a legacy v4 audit-replay).
    if not rigor_phases:
        print(
            f"ERROR: rigor.tdd_phases is empty in .nwave/des-config.json. "
            f"Configure rigor.tdd_phases with at least one of: "
            f"{list(schema.tdd_phases)!r} (canonical) or "
            f"{list(schema.legacy_phases)!r} (legacy).",
            file=sys.stderr,
        )
        return 2
    effective_phases = (
        tuple(p for p in active_phases if p in rigor_phases) or active_phases
    )
    if not effective_phases:
        print(
            f"ERROR: rigor.tdd_phases contains no phases recognised by the "
            f"canonical TDDSchema. Misconfigured rigor phases: "
            f"{list(rigor_phases)!r}; canonical phases: "
            f"{list(schema.tdd_phases)!r}.",
            file=sys.stderr,
        )
        return 2

    required_phases = list(effective_phases)
    verifier = DeliverIntegrityVerifier(required_phases=required_phases)
    result = verifier.verify(step_ids, entries)

    if result.is_valid:
        print(f"All {result.steps_verified} steps have complete DES traces")
        return 0
    else:
        print(f"INTEGRITY VIOLATIONS: {result.reason}")
        for v in result.violations:
            print(
                f"  - {v.step_id}: {v.phase_count}/{len(required_phases)} phases, "
                f"missing: {v.missing_phases}"
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
