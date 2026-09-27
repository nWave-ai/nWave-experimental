#!/usr/bin/env python3
"""Run one declared arm as a D0 diagnostic and preserve its evidence.

This runner intentionally has no comparison math.  A single execution is a
diagnostic specimen only, even when its delivery itself succeeds.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


# Allow the executable form (`python scripts/analysis/single_arm_campaign.py`)
# as well as the package form used by tests and automation.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from des.adapters.driven.task_invocation.turn_recorder import reserve_d0
from des.domain.filesystem_projection import STRICT_DELIVERY_POLICY
from scripts.analysis import blind_review, paired_campaign
from scripts.analysis.k4 import delivery_attribution, intervention_ledger
from scripts.analysis.k4.preflight import TREATMENT_INSTALL_STEP


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_tree(root: Path) -> dict[str, str]:
    """Return deterministic hashes for a captured packet or copied payload."""
    return {
        str(path.relative_to(root)): intervention_ledger.sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _capture_transcripts(
    environment: dict[str, str], specimen: Path
) -> list[dict[str, str]]:
    """Copy transcript bytes under content-addressed, specimen-relative paths."""
    config = environment.get("CLAUDE_CONFIG_DIR")
    if not config:
        raise RuntimeError("selected treatment has no transcript CLAUDE_CONFIG_DIR")
    root = Path(config) / "projects"
    if not root.is_dir():
        raise RuntimeError("selected treatment has no transcript projects directory")
    transcripts = specimen / "transcripts"
    transcripts.mkdir()
    references: list[dict[str, str]] = []
    for transcript in sorted(root.rglob("*.jsonl")):
        payload = transcript.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        destination = transcripts / f"{digest}.jsonl"
        if destination.exists():
            if destination.read_bytes() != payload:
                raise RuntimeError(
                    "content-addressed transcript path has different bytes"
                )
        else:
            with destination.open("xb") as copied:
                copied.write(payload)
        references.append(
            {
                "source": transcript.relative_to(root).as_posix(),
                "sha256": digest,
                "specimen_path": destination.relative_to(specimen).as_posix(),
            }
        )
    if not references:
        raise RuntimeError("selected treatment produced no JSONL transcript")
    return references


def _write_specimen_metadata(
    *, arm: paired_campaign.ArmSpec, task: str, workspace: Path, run_dir: Path
) -> dict[str, object]:
    """Copy payload and make the environment/transcript evidence durable."""
    specimen = run_dir / "specimen"
    specimen.mkdir(exist_ok=True)
    payload = run_dir / f"{arm.name}.json"
    stderr = run_dir / f"{arm.name}.err"
    copied: dict[str, str] = {}
    for source, name in ((payload, "delivery.json"), (stderr, "delivery.stderr")):
        if source.is_file():
            destination = specimen / name
            shutil.copy2(source, destination)
            copied[name] = intervention_ledger.sha256_file(destination)
    environment = arm.rendered_env(workspace)
    environment_evidence = {
        name: {"sha256": _sha256_text(value)}
        for name, value in sorted(environment.items())
    }
    request_dir = specimen / "request"
    request_dir.mkdir()
    request_artifacts = {
        "task.txt": task,
        "task-prefix.txt": arm.task_prefix,
        "effective-request.txt": arm.task_prefix + task,
    }
    for name, value in request_artifacts.items():
        (request_dir / name).write_text(value, encoding="utf-8")
    metadata = {
        "task_sha256": _sha256_text(task),
        "task_prefix_sha256": _sha256_text(arm.task_prefix),
        "effective_request_sha256": _sha256_text(arm.task_prefix + task),
        "argv": arm.rendered(workspace),
        "environment": environment_evidence,
        "transcripts": _capture_transcripts(environment, specimen),
        "payload_sha256": copied,
    }
    metadata_path = specimen / "references.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"specimen_hashes": _hash_tree(specimen)}


def _diagnostic_treatment(arm: paired_campaign.ArmSpec) -> bool:
    """Recognise only the canonical installed-nWave intervention."""
    return any(
        len(step) == len(TREATMENT_INSTALL_STEP)
        and Path(step[0]).name == "nwave-ai"
        and step[1:] == TREATMENT_INSTALL_STEP[1:]
        for step in arm.setup
    )


def _problem(message: str) -> int:
    sys.stderr.write(
        f"WHAT: {message}\n"
        "WHY:  a D0 diagnostic must preserve one declared execution and its evidence.\n"
        "HOW:  correct the declaration or use a new empty output directory.\n"
    )
    print("CLASSIFICATION: INDETERMINATE", flush=True)
    return 2


def _evidence_problem(message: str) -> None:
    sys.stderr.write(
        f"WHAT: {message}\n"
        "WHY:  this diagnostic lacks a complete, durable evidence chain.\n"
        "HOW:  preserve the declared instruments and capture a new diagnostic run.\n"
    )


@dataclass(frozen=True)
class _CampaignDeclaration:
    """Which campaign ran: the declared arm, task, and run parameters."""

    arm: paired_campaign.ArmSpec
    task: str
    runs: int
    timeout: int


@dataclass(frozen=True)
class _CampaignOutcome:
    """How the campaign ended."""

    state: str
    classification: str
    failure: str | None = None


def _campaign_record(
    *, declaration: _CampaignDeclaration, outcome: _CampaignOutcome
) -> dict[str, object]:
    """Construct the campaign state; callers never mutate a prior record."""
    arm, task = declaration.arm, declaration.task
    record: dict[str, object] = {
        "state": outcome.state,
        "classification": outcome.classification,
        "task_sha256": _sha256_text(task),
        "task_prefix_sha256": _sha256_text(arm.task_prefix),
        "effective_request_sha256": _sha256_text(arm.task_prefix + task),
        "arm": arm.name,
        "runs": declaration.runs,
        "delivery_timeout_s": declaration.timeout,
        "declaration": {
            "setup": [list(step) for step in arm.setup],
            "argv": list(arm.argv),
            "env": dict(arm.env),
            "task_prefix": arm.task_prefix,
        },
    }
    if outcome.failure is not None:
        record["failure"] = outcome.failure
    return record


def _write_campaign(path: Path, record: dict[str, object]) -> None:
    """Publish the whole campaign state in one atomic replacement."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            destination.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
        temporary.replace(path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class _RunOutcome:
    complete: bool
    reason: str | None = None


def _run_one(
    *,
    arm: paired_campaign.ArmSpec,
    task: str,
    run_dir: Path,
    timeout: int,
    instruments: dict[str, Path],
) -> _RunOutcome:
    treatment = _diagnostic_treatment(arm)
    targets = paired_campaign.git_checkout_targets(arm.setup)
    baseline = targets[-1] if targets else None
    ledger: intervention_ledger.InterventionLedger | None = None
    reservation = None
    evidence_failure: str | None = None

    def before_delivery(workspace: Path) -> dict[str, str] | None:
        nonlocal ledger, reservation
        if not treatment:
            return None
        reservation = reserve_d0(workspace, STRICT_DELIVERY_POLICY)
        ledger = intervention_ledger.open_ledger(
            run_dir / "ledger", bound_instruments=instruments
        )
        ledger.event(
            "delivery_started",
            arm=arm.name,
            baseline=baseline,
            run_id=reservation.run_id,
            reservation_sha256=reservation.reservation_sha256,
            policy_sha256=reservation.policy_sha256,
            high_water_mark=0,
        )
        return reservation.environment_delta

    def after_delivery(workspace: Path, delivery_ok: bool) -> None:
        nonlocal evidence_failure
        if ledger is None:
            return
        classification = "DIAGNOSTIC"
        try:
            if baseline is None:
                raise RuntimeError("no declared checkout baseline")
            evidence = _write_specimen_metadata(
                arm=arm, task=task, workspace=workspace, run_dir=run_dir
            )
            specimen = run_dir / "specimen"
            packet = specimen / "delivery-packet"
            captured = blind_review.capture_delivery_packet(
                workspace, packet, baseline=baseline
            )
            if captured.target != packet or captured.baseline != baseline:
                raise RuntimeError(
                    "strict capture did not preserve the requested packet baseline"
                )
            if reservation is None:
                raise RuntimeError("D0 did not retain its native reservation")
            attribution_path = delivery_attribution.construct_d0_attribution(
                workspace=workspace,
                specimen=specimen,
                reservation=reservation,
                capture=captured,
            )
            strict_capture = delivery_attribution.capture_binding(attribution_path)
            evidence["delivery_ok"] = delivery_ok
            evidence["packet_hashes"] = _hash_tree(packet)
            evidence["request_hashes"] = _hash_tree(specimen / "request")
            evidence["transcript_hashes"] = _hash_tree(specimen / "transcripts")
            evidence["attribution_hashes"] = {
                attribution_path.name: intervention_ledger.sha256_file(attribution_path)
            }
            evidence["native_artifact_hashes"] = _hash_tree(
                specimen / "native-artifacts"
            )
            evidence["capture"] = {
                "baseline": captured.baseline,
                "target": str(captured.target),
                "paths": list(captured.paths),
                "transition_count": len(captured.transitions),
            }
            evidence.update(strict_capture)
            ledger.event("delivery_captured", **evidence)
            preliminary = delivery_attribution.assess(
                attribution_path, require_closed=False
            )
            classification = (
                "DIAGNOSTIC"
                if delivery_ok and preliminary.status == delivery_attribution.ATTRIBUTED
                else "INDETERMINATE"
            )
        except (AttributeError, OSError, RuntimeError, ValueError) as exc:
            classification = "INDETERMINATE"
            evidence_failure = (
                f"strict delivery capture failed: {type(exc).__name__}: {exc}"
            )
            try:
                ledger.event("capture_failed", reason=evidence_failure)
            except (OSError, RuntimeError, ValueError) as event_exc:
                evidence_failure = (
                    f"{evidence_failure}; failure event was not recorded: "
                    f"{type(event_exc).__name__}: {event_exc}"
                )
        finally:
            try:
                verification = ledger.close(classification=classification)
            except (OSError, RuntimeError, ValueError) as exc:
                evidence_failure = (
                    f"ledger could not close: {type(exc).__name__}: {exc}"
                )
            else:
                if verification.is_indeterminate and evidence_failure is None:
                    evidence_failure = "ledger close verification failed: " + "; ".join(
                        verification.problems
                    )
                elif evidence_failure is None:
                    assessment = delivery_attribution.assess(
                        run_dir
                        / "specimen"
                        / delivery_attribution.ATTRIBUTION_V2_FILE_NAME
                    )
                    if assessment.status != delivery_attribution.ATTRIBUTED:
                        evidence_failure = (
                            "closed D0 attribution failed: " + assessment.why
                        )

    try:
        result = paired_campaign.execute_declared_arm_once(
            arm,
            task=task,
            run_dir=run_dir,
            timeout=timeout,
            before_delivery=before_delivery,
            after_delivery=after_delivery,
        )
    except (KeyboardInterrupt, SystemExit) as exc:
        # Delivery can unwind before its observation callback.  Preserve the
        # interruption for the campaign owner, but first close evidence that
        # was opened after the treatment reservation.
        cleanup_failures: list[str] = []
        if ledger is not None:
            try:
                ledger.event("delivery_interrupted", interrupt=type(exc).__name__)
            except (OSError, RuntimeError, ValueError) as cleanup_exc:
                cleanup_failures.append(
                    "ledger interruption event failed: "
                    f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )
            try:
                ledger.close(classification="INDETERMINATE")
            except (OSError, RuntimeError, ValueError) as cleanup_exc:
                cleanup_failures.append(
                    "ledger interruption close failed: "
                    f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )
        if cleanup_failures:
            exc._nwave_ledger_cleanup_failures = tuple(cleanup_failures)
        raise
    if not result.setup_ok:
        return _RunOutcome(False, "the selected arm setup failed")
    if evidence_failure is not None:
        return _RunOutcome(False, evidence_failure)
    if ledger is not None:
        verification = intervention_ledger.verify(ledger.root)
        if verification.is_indeterminate:
            return _RunOutcome(
                False, "ledger verification failed: " + "; ".join(verification.problems)
            )
    if not result.delivery_ok:
        return _RunOutcome(False, "the selected arm delivery record was invalid")
    return _RunOutcome(True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arms", required=True, type=Path)
    parser.add_argument("--arm", required=True, help="the one declared arm to execute")
    parser.add_argument("--intent", required=True)
    parser.add_argument("--runs", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--timeout", type=int, default=paired_campaign.DELIVERY_TIMEOUT_S
    )
    args = parser.parse_args(argv)
    if args.intent != "diagnostic":
        return _problem("D0 accepts only `--intent diagnostic`")
    if args.runs < 1:
        return _problem("--runs must be at least one")
    if args.out.exists():
        return _problem(f"output directory already exists: {args.out}")
    try:
        spec = json.loads(args.arms.read_text(encoding="utf-8"))
        declared_arms = spec["arms"]
        declared = declared_arms[args.arm]
        arm = paired_campaign.parse_arm(args.arm, declared)
        task = spec["task"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return _problem(f"cannot read the selected arm: {exc}")
    if not isinstance(task, str):
        return _problem("the declared task is not a string")
    if not _diagnostic_treatment(arm):
        return _problem(
            f"selected arm '{arm.name}' is not the declared treatment for a D0 diagnostic"
        )

    declaration = _CampaignDeclaration(
        arm=arm, task=task, runs=args.runs, timeout=args.timeout
    )

    # A whole one-arm diagnostic owns this host-local lock.  It is taken before
    # setup can spawn and held through every delivery, so a second local D0
    # run cannot add provider load between two declared runs.
    lock_path = Path(tempfile.gettempdir()) / "nwave-single-arm-campaign.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _problem("another local single-arm diagnostic holds the load lock")
        args.out.mkdir(parents=True)
        campaign_path = args.out / "campaign.json"
        _write_campaign(
            campaign_path,
            _campaign_record(
                declaration=declaration,
                outcome=_CampaignOutcome(state="OPEN", classification="UNCLASSIFIED"),
            ),
        )
        instruments = {
            "arms": args.arms,
            "paired_runner": Path(paired_campaign.__file__).resolve(),
            "capture": Path(blind_review.__file__).resolve(),
            "single_arm_runner": Path(__file__).resolve(),
            "intervention_ledger": Path(intervention_ledger.__file__).resolve(),
            "exercise_precondition": Path(__file__).parent
            / "k4"
            / "exercise_precondition.py",
            "delivery_attribution": Path(__file__).parent
            / "k4"
            / "delivery_attribution.py",
        }
        try:
            for index in range(1, args.runs + 1):
                run_dir = args.out / f"run-{index}"
                run_dir.mkdir()
                try:
                    outcome = _run_one(
                        arm=arm,
                        task=task,
                        run_dir=run_dir,
                        timeout=args.timeout,
                        instruments=instruments,
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    outcome = _RunOutcome(
                        False,
                        f"D0 runner could not preserve evidence: {type(exc).__name__}: {exc}",
                    )
                if not outcome.complete:
                    _evidence_problem(
                        outcome.reason or "the selected run was incomplete"
                    )
                    _write_campaign(
                        campaign_path,
                        _campaign_record(
                            declaration=declaration,
                            outcome=_CampaignOutcome(
                                state="CLOSED",
                                classification="INDETERMINATE",
                                failure=outcome.reason
                                or "the selected run was incomplete",
                            ),
                        ),
                    )
                    print(f"diagnostic run {index}: incomplete", flush=True)
                    print("CLASSIFICATION: INDETERMINATE", flush=True)
                    return 1
                print(f"diagnostic run {index}: captured", flush=True)
        except (KeyboardInterrupt, SystemExit) as exc:
            failure = f"D0 runner interrupted: {type(exc).__name__}: {exc}"
            cleanup_failures = getattr(exc, "_nwave_ledger_cleanup_failures", ())
            if cleanup_failures:
                failure += "; " + "; ".join(cleanup_failures)
            _evidence_problem(failure)
            _write_campaign(
                campaign_path,
                _campaign_record(
                    declaration=declaration,
                    outcome=_CampaignOutcome(
                        state="CLOSED",
                        classification="INDETERMINATE",
                        failure=failure,
                    ),
                ),
            )
            print("CLASSIFICATION: INDETERMINATE", flush=True)
            return 1
        _write_campaign(
            campaign_path,
            _campaign_record(
                declaration=declaration,
                outcome=_CampaignOutcome(state="CLOSED", classification="DIAGNOSTIC"),
            ),
        )
    print("CLASSIFICATION: DIAGNOSTIC", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
