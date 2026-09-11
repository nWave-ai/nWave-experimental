"""Candidate-bound host role artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.task_invocation.model_envelope import decode_model_run
from des.application.delivery_continuation import DeliveryContinuationRunner
from des.application.delivery_steps import _prepared
from des.application.handover import stored_handover


if TYPE_CHECKING:
    from des.ports.driven_ports.task_invocation_port import ModelRun


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("conflicting bytes for existing role artifact")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError("conflicting bytes for existing role artifact")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def _sealed(payload: dict[str, object], kind: str) -> bytes:
    """Canonical artifact bytes with a digest of the payload excluding itself."""
    payload = {**payload, "kind": kind}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return json.dumps(
        {**payload, "payload_sha256": hashlib.sha256(canonical).hexdigest()},
        sort_keys=True,
        ensure_ascii=False,
    ).encode()


def load_prepared(
    root: Path, role: str, candidate: str
) -> tuple[Path, dict[str, object], bytes]:
    """Load one sealed input and rebind it to current request/native authority."""
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-input.json"
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("prepared role input is unavailable") from error
    digest = payload.pop("payload_sha256", None)
    if payload.get("kind") != "role_input" or payload.get("role") != role:
        raise ValueError("prepared role input kind or role differs")
    if (
        not isinstance(digest, str)
        or hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        != digest
    ):
        raise ValueError("prepared role input digest differs")
    stored = stored_handover(root)
    runner = DeliveryContinuationRunner()
    tree = runner._git(root, "rev-parse", f"{candidate}^{{tree}}")
    if (
        stored is None
        or not hasattr(stored, "raw")
        or runner.verified_candidate(root, stored) != candidate
        or not runner.load_native_evidence_identity(root, candidate)
        or payload.get("candidate_sha") != candidate
        or payload.get("request_digest") != hashlib.sha256(stored.raw).hexdigest()
        or tree.returncode
        or payload.get("candidate_tree_sha") != tree.stdout.strip()
        or payload.get("native_evidence_sha256") != runner.native_evidence_sha256
    ):
        raise ValueError("prepared role input authority binding differs")
    payload["payload_sha256"] = digest
    return path, payload, raw


def prepare(root: Path, role: str, candidate: str) -> tuple[str, str]:
    stored = stored_handover(root)
    if stored is None or not hasattr(stored, "request"):
        raise ValueError("handover unavailable")
    runner = DeliveryContinuationRunner()
    if runner.verified_candidate(
        root, stored
    ) != candidate or not runner.load_native_evidence_identity(root, candidate):
        raise ValueError("candidate has no bound native evidence")
    native_path = root / runner.native_evidence_locator
    native = json.loads(native_path.read_bytes())
    request_digest = hashlib.sha256(stored.raw).hexdigest()
    tree = runner._git(root, "rev-parse", f"{candidate}^{{tree}}")
    if tree.returncode:
        raise ValueError("candidate tree is unavailable")
    common = {
        "schema_version": 1,
        "role": role,
        "request_digest": request_digest,
        "candidate_sha": candidate,
        "candidate_tree_sha": tree.stdout.strip(),
        "native_evidence_sha256": runner.native_evidence_sha256,
    }
    changed = runner._changed_paths(root, f"{candidate}^", candidate)
    if changed is None:
        raise ValueError("candidate changed paths are unavailable")
    try:
        radius_record = json.loads(
            (root / ".nwave/des/logs/radius" / f"{candidate}.json").read_bytes()
        )
        if not isinstance(radius_record, dict):
            raise ValueError("radius record is not an object")
        seal = radius_record.pop("payload_sha256", None)
        if (
            seal
            != hashlib.sha256(
                json.dumps(radius_record, sort_keys=True).encode()
            ).hexdigest()
        ):
            raise ValueError("radius seal differs")
        if (
            radius_record.get("candidate_sha") != candidate
            or radius_record.get("native_evidence_sha256")
            != runner.native_evidence_sha256
            or not isinstance(radius_record.get("radius"), str)
        ):
            raise ValueError("radius binding differs")
        radius = radius_record["radius"]
    except (OSError, json.JSONDecodeError, ValueError):
        raise ValueError("candidate-bound native radius is unavailable")
    prepared = _prepared(runner, root, stored)
    if not isinstance(prepared, list):
        raise ValueError("authority facts unavailable")
    if role == "examiner":
        projected = [
            {
                k: item.get(k)
                for k in (
                    "exit",
                    "stdout",
                    "stderr",
                    "origin",
                    "incomplete",
                    "incomplete_what",
                    "incomplete_why",
                    "incomplete_how",
                    "duration_seconds",
                )
            }
            for item in native
        ]
        payload = {
            **common,
            "outcomes": [value for value, _ in prepared],
            "native_evidence": projected,
            "radius": radius,
        }
    elif role == "reviewer":
        diff = runner._git(
            root, "diff", "--no-color", f"{candidate}^", candidate
        ).stdout
        approved = []
        for _, design in prepared:
            for path in design.acceptance_paths:
                observed = runner._git(root, "show", f"{candidate}:{path}")
                if observed.returncode:
                    raise ValueError(f"candidate oracle {path} is unavailable")
                approved.append([path, observed.stdout])
        payload = {
            **common,
            "diff": diff,
            "values": runner._prepared_facts(prepared),
            "owned_paths": runner._request_owned_paths(prepared),
            "approved_oracles": approved,
            "native_evidence": native,
            "radius": radius,
        }
    else:
        raise ValueError("role must be reviewer or examiner")
    raw = _sealed(payload, "role_input")
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-input.json"
    return path.relative_to(root).as_posix(), _write(path, raw)


def record(
    root: Path,
    role: str,
    candidate: str,
    provider: str,
    model: str | None,
    session: str | None,
    raw: bytes,
) -> tuple[str, str, str]:
    _input_path, prepared, input_raw = load_prepared(root, role, candidate)
    structured = json.loads(raw)["structured_output"]
    decode_model_run(
        structured,
        role_id="nw-software-crafter-reviewer"
        if role == "reviewer"
        else "nw-user-examiner",
    )
    outcome = structured["outcome"]
    payload = {
        "schema_version": 1,
        "role": role,
        "candidate_sha": candidate,
        "candidate_tree_sha": prepared.get("candidate_tree_sha"),
        "request_digest": prepared.get("request_digest"),
        "native_evidence_sha256": prepared.get("native_evidence_sha256"),
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "declared_provider": provider,
        "result": structured,
    }
    if model is not None:
        payload["declared_model"] = model
    if session is not None:
        payload["declared_session_id"] = session
    encoded = _sealed(payload, "role_result")
    identity = hashlib.sha256((session or "adapter").encode()).hexdigest()
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-{identity}-result.json"
    return outcome, path.relative_to(root).as_posix(), _write(path, encoded)


def record_model(
    root: Path, role: str, candidate: str, provider: str, model: str, run: ModelRun
) -> tuple[str, str, str]:
    """Persist the adapter's typed result without reconstructing an envelope."""
    _input_path, prepared, input_raw = load_prepared(root, role, candidate)
    payload = {
        "schema_version": 1,
        "role": role,
        "candidate_sha": candidate,
        "input_sha256": hashlib.sha256(input_raw).hexdigest(),
        "candidate_tree_sha": prepared.get("candidate_tree_sha"),
        "request_digest": prepared.get("request_digest"),
        "native_evidence_sha256": prepared.get("native_evidence_sha256"),
        "actual_provider": provider,
        "actual_model": model,
        "outcome": run.outcome.value,
        "diagnostic": run.diagnostic,
        "issued": run.issued,
        "exit_status": run.exit_status,
        "retry_safe": run.retry_safe,
    }
    if run.accounting is not None:
        payload["accounting"] = {
            "total_cost_usd": run.accounting.total_cost_usd,
            "num_turns": run.accounting.num_turns,
            "input_tokens": run.accounting.input_tokens,
            "output_tokens": run.accounting.output_tokens,
            "cache_creation_input_tokens": run.accounting.cache_creation_input_tokens,
            "cache_read_input_tokens": run.accounting.cache_read_input_tokens,
            "session_id": run.accounting.session_id,
        }
    if run.review_defect is not None:
        payload["review_defect"] = {
            "owner": run.review_defect.owner.value,
            "value": run.review_defect.value,
        }
    raw = _sealed(payload, "role_result")
    identity = hashlib.sha256(raw).hexdigest()
    path = root / ".nwave/des/logs/roles" / f"{candidate}-{role}-{identity}-result.json"
    return run.outcome.value, path.relative_to(root).as_posix(), _write(path, raw)
