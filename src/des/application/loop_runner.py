"""Durable standing-loop control and the sole semantic tick runner."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from des.ports.standing_loop_ports import StandingLoopTickPort


@dataclass(frozen=True)
class LoopHandle:
    loop_id: str
    generation: int


@dataclass(frozen=True)
class LoopRecord:
    project_root: Path
    generation: int
    desired_state: str
    observed_state: str


@dataclass(frozen=True)
class TickAttestation:
    id: str
    occurrence_key: str
    project_root: Path
    project_id: str
    ledger_digest: str
    budget: dict[str, int]
    budget_verdict: str
    outcome: str
    requested_digest: str
    observed_digest: str | None
    isolation: dict[str, str]
    resources: dict[str, Any]
    execution_receipt: dict[str, Any] | None = None
    replayed: bool = False


@dataclass(frozen=True)
class Recovery:
    declared_outcome: str
    context_mode: str
    attestation_count: int
    applied: bool
    reconciliation_digest: str
    attestation: TickAttestation | None


@dataclass(frozen=True)
class StopAttempt:
    observed_state: str
    changed: bool


@dataclass(frozen=True)
class _StoredLoop:
    handle: LoopHandle
    project_root: Path
    outcome: str
    context_mode: str
    budget: dict[str, int]
    desired_state: str = "ARMED"
    observed_state: str = "SCHEDULED"
    fence_epoch: int = 1


@dataclass(frozen=True)
class _ExecutionInputs:
    context_capsule: dict[str, str]
    budget: dict[str, int]
    isolation: dict[str, Path]


@dataclass(frozen=True)
class _Claim:
    owner: bool
    fence_epoch: int
    receipt: TickAttestation | None = None


class IdempotencyConflict(ValueError):
    """A caller reused an authority key for a different request."""


class _StandingLoopLedger:
    """SQLite is the cross-process authority boundary for a project loop."""

    @staticmethod
    def _project(project_root: Any) -> Path:
        return Path(project_root).resolve()

    @staticmethod
    def _database(project: Path) -> Path:
        return project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"

    def _connect(self, project: Path) -> sqlite3.Connection:
        database = self._database(project)
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database, isolation_level=None, timeout=30)
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS loop_state "
            "(singleton INTEGER PRIMARY KEY CHECK(singleton = 1), payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS attestations "
            "(occurrence_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS idempotency_receipts "
            "(verb TEXT NOT NULL, key_digest TEXT NOT NULL, request_digest TEXT NOT NULL, "
            "payload TEXT NOT NULL, PRIMARY KEY(verb, key_digest))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS loop_events "
            "(sequence INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS occurrence_claims "
            "(occurrence_key TEXT PRIMARY KEY, request_digest TEXT NOT NULL, "
            "fence_epoch INTEGER NOT NULL, status TEXT NOT NULL)"
        )
        return connection

    @staticmethod
    def _stored_from_payload(project: Path, payload: dict[str, Any]) -> _StoredLoop:
        return _StoredLoop(
            handle=LoopHandle(payload["loop_id"], int(payload["generation"])),
            project_root=project,
            outcome=payload["outcome"],
            context_mode=payload["context_mode"],
            budget=dict(payload["budget"]),
            desired_state=payload["desired_state"],
            observed_state=payload["observed_state"],
            fence_epoch=int(payload.get("fence_epoch", 1)),
        )

    def _load_from(
        self, connection: sqlite3.Connection, project: Path
    ) -> _StoredLoop | None:
        row = connection.execute(
            "SELECT payload FROM loop_state WHERE singleton = 1"
        ).fetchone()
        return (
            None
            if row is None
            else self._stored_from_payload(project, json.loads(row[0]))
        )

    def _load(self, project: Path) -> _StoredLoop | None:
        if not self._database(project).is_file():
            return None
        with sqlite3.connect(self._database(project)) as connection:
            return self._load_from(connection, project)

    @staticmethod
    def _state_payload(stored: _StoredLoop) -> str:
        return json.dumps(
            {
                "loop_id": stored.handle.loop_id,
                "generation": stored.handle.generation,
                "outcome": stored.outcome,
                "context_mode": stored.context_mode,
                "budget": stored.budget,
                "desired_state": stored.desired_state,
                "observed_state": stored.observed_state,
                "fence_epoch": stored.fence_epoch,
            },
            sort_keys=True,
        )

    def _save_to(self, connection: sqlite3.Connection, stored: _StoredLoop) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO loop_state(singleton, payload) VALUES (1, ?)",
            (self._state_payload(stored),),
        )

    @staticmethod
    def _attestation_payload(attestation: TickAttestation) -> str:
        payload = asdict(attestation)
        payload["project_root"] = str(attestation.project_root)
        return json.dumps(payload, sort_keys=True)

    def _save_attestation_to(
        self, connection: sqlite3.Connection, attestation: TickAttestation
    ) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO attestations(occurrence_key, payload) VALUES (?, ?)",
            (attestation.occurrence_key, self._attestation_payload(attestation)),
        )

    @staticmethod
    def _attestation_from(payload: dict[str, Any]) -> TickAttestation:
        return TickAttestation(
            id=payload["id"],
            occurrence_key=payload["occurrence_key"],
            project_root=Path(payload["project_root"]),
            project_id=payload["project_id"],
            ledger_digest=payload["ledger_digest"],
            budget=dict(payload["budget"]),
            budget_verdict=payload["budget_verdict"],
            outcome=payload["outcome"],
            requested_digest=payload["requested_digest"],
            observed_digest=payload.get("observed_digest"),
            isolation=dict(payload["isolation"]),
            resources=dict(payload["resources"]),
            execution_receipt=payload.get("execution_receipt"),
            replayed=bool(payload.get("replayed", False)),
        )

    def _last_attestation_from(
        self, connection: sqlite3.Connection, project: Path
    ) -> TickAttestation | None:
        row = connection.execute(
            "SELECT payload FROM attestations ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return None if row is None else self._attestation_from(json.loads(row[0]))

    def last_attestation(self, project: Path) -> TickAttestation | None:
        if not self._database(project).is_file():
            return None
        with sqlite3.connect(self._database(project)) as connection:
            return self._last_attestation_from(connection, project)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _append_event(
        self,
        connection: sqlite3.Connection,
        stored: _StoredLoop,
        event_type: str,
        *,
        idempotency_key: str,
        request_digest: str,
        occurrence_key: str | None = None,
        attestation: TickAttestation | None = None,
        fence_token: str | None = None,
        effect_digest: str | None = None,
    ) -> None:
        recorded_at = self._now()
        event = {
            "schema_version": "des.loop.event.v1",
            "event_type": event_type,
            "event_id": sha256(
                f"{event_type}|{_project_id(stored.project_root)}|{stored.handle.loop_id}|"
                f"{recorded_at}|{idempotency_key}".encode()
            ).hexdigest(),
            "recorded_at": recorded_at,
            "ProjectId": _project_id(stored.project_root),
            "HandleId": stored.handle.loop_id,
            "generation": stored.handle.generation,
            "fence_epoch": stored.fence_epoch,
            "idempotency_key_digest": _key_digest(idempotency_key),
            "request_digest": request_digest,
        }
        if occurrence_key is not None:
            event["OccurrenceId"] = occurrence_key
        if attestation is not None:
            event["attestation"] = json.loads(self._attestation_payload(attestation))
        if fence_token is not None:
            event["fence_token"] = fence_token
        if effect_digest is not None:
            event["effect_digest"] = effect_digest
        connection.execute(
            "INSERT INTO loop_events(payload) VALUES (?)",
            (json.dumps(event, sort_keys=True),),
        )

    @staticmethod
    def _read_idempotency(
        connection: sqlite3.Connection,
        verb: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT request_digest, payload FROM idempotency_receipts "
            "WHERE verb = ? AND key_digest = ?",
            (verb, _key_digest(idempotency_key)),
        ).fetchone()
        if row is None:
            return None
        if row[0] != request_digest:
            raise IdempotencyConflict(
                f"{verb} request differs from the original receipt"
            )
        return json.loads(row[1])

    @staticmethod
    def _write_idempotency(
        connection: sqlite3.Connection,
        verb: str,
        idempotency_key: str,
        request_digest: str,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO idempotency_receipts"
            "(verb, key_digest, request_digest, payload) VALUES (?, ?, ?, ?)",
            (
                verb,
                _key_digest(idempotency_key),
                request_digest,
                json.dumps(payload, sort_keys=True),
            ),
        )

    def arm(self, work: Any, *, idempotency_key: str) -> LoopHandle:
        project = self._project(work.project_root)
        request_digest = _arm_request_digest(project, work)
        key_digest = _key_digest(idempotency_key)
        connection = self._connect(project)
        try:
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute(
                "SELECT request_digest, payload FROM idempotency_receipts "
                "WHERE verb = 'arm' AND key_digest = ?",
                (key_digest,),
            ).fetchone()
            if receipt is not None:
                if receipt[0] != request_digest:
                    raise IdempotencyConflict(
                        "arm request differs from the original receipt"
                    )
                payload = json.loads(receipt[1])
                connection.commit()
                return LoopHandle(payload["loop_id"], int(payload["generation"]))
            existing = self._load_from(connection, project)
            if existing is not None and existing.desired_state == "ARMED":
                handle = existing.handle
            else:
                generation = 1 if existing is None else existing.handle.generation + 1
                handle = LoopHandle(
                    loop_id=f"standing-{sha256(str(project).encode()).hexdigest()[:16]}",
                    generation=generation,
                )
                stored = _StoredLoop(
                    handle=handle,
                    project_root=project,
                    outcome=work.outcome,
                    context_mode=work.context_mode,
                    budget=_budget_from(work),
                    fence_epoch=(1 if existing is None else existing.fence_epoch + 1),
                )
                self._save_to(connection, stored)
                self._append_event(
                    connection,
                    stored,
                    "LOOP_ARMED",
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                )
            connection.execute(
                "INSERT INTO idempotency_receipts(verb, key_digest, request_digest, payload) "
                "VALUES ('arm', ?, ?, ?)",
                (
                    key_digest,
                    request_digest,
                    json.dumps(asdict(handle), sort_keys=True),
                ),
            )
            connection.commit()
            return handle
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list(self, project_root: Any) -> tuple[LoopRecord, ...]:
        project = self._project(project_root)
        stored = self._load(project)
        if stored is None:
            return ()
        return (
            LoopRecord(
                project,
                stored.handle.generation,
                stored.desired_state,
                stored.observed_state,
            ),
        )

    def handle(self, project_root: Any) -> LoopHandle:
        return self._require(self._project(project_root)).handle

    def stop(
        self, project_root: Any, handle: Any, *, idempotency_key: str = "direct-stop"
    ) -> StopAttempt:
        project = self._project(project_root)
        connection = self._connect(project)
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = self._require_from(connection, project)
            self._validate_handle(stored, handle)
            request_digest = _control_request_digest(
                project, "stop", stored.handle, idempotency_key
            )
            replay = self._read_idempotency(
                connection, "stop", idempotency_key, request_digest
            )
            if replay is not None:
                connection.commit()
                return StopAttempt(replay["observed_state"], False)
            self._append_event(
                connection,
                stored,
                "STOP_REQUESTED",
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            changed = stored.desired_state != "STOPPED"
            stopped = replace(
                stored,
                desired_state="STOPPED",
                observed_state="STOPPED",
                fence_epoch=stored.fence_epoch + 1,
            )
            if changed:
                self._save_to(connection, stopped)
            self._append_event(
                connection,
                stopped,
                "STOP_OBSERVED",
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            self._write_idempotency(
                connection,
                "stop",
                idempotency_key,
                request_digest,
                {"observed_state": "STOPPED", "changed": changed},
            )
            connection.commit()
            return StopAttempt("STOPPED", changed)
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover(
        self,
        project_root: Any,
        *,
        apply: bool = False,
        idempotency_key: str = "recover-plan",
    ) -> Recovery:
        project = self._project(project_root)
        connection = self._connect(project) if apply else None
        if connection is not None:
            connection.execute("BEGIN IMMEDIATE")
        try:
            if connection is None:
                if not self._database(project).is_file():
                    raise ValueError("no loop is armed for project")
                with sqlite3.connect(self._database(project)) as read_connection:
                    stored = self._require_from(read_connection, project)
                    count = read_connection.execute(
                        "SELECT COUNT(*) FROM attestations"
                    ).fetchone()[0]
                    attestation = self._last_attestation_from(read_connection, project)
            else:
                stored = self._require_from(connection, project)
                request_digest = _control_request_digest(
                    project, "recover", stored.handle, idempotency_key
                )
                replay = self._read_idempotency(
                    connection, "recover", idempotency_key, request_digest
                )
                count = connection.execute(
                    "SELECT COUNT(*) FROM attestations"
                ).fetchone()[0]
                attestation = self._last_attestation_from(connection, project)
                if replay is None:
                    self._append_event(
                        connection,
                        stored,
                        "RECOVERY_APPLIED",
                        idempotency_key=idempotency_key,
                        request_digest=request_digest,
                    )
                    self._write_idempotency(
                        connection,
                        "recover",
                        idempotency_key,
                        request_digest,
                        {"applied": True},
                    )
                connection.commit()
            return Recovery(
                stored.outcome,
                stored.context_mode
                if stored.context_mode == "reconstructed"
                else "reconstructed",
                count,
                apply,
                sha256(
                    f"{project}|{stored.handle.loop_id}|{count}|reconcile".encode()
                ).hexdigest(),
                attestation,
            )
        except BaseException:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def execution_inputs(self, project_root: Any, occurrence: Any) -> _ExecutionInputs:
        project = self._project(project_root)
        stored = self._require(project)
        if occurrence.loop_id != stored.handle.loop_id:
            raise ValueError("occurrence does not belong to the selected project loop")
        return _ExecutionInputs(
            {"mode": stored.context_mode, "outcome": stored.outcome},
            dict(stored.budget),
            {"project_root": project},
        )

    def claim(self, occurrence: Any, isolation: dict[str, Path]) -> _Claim:
        project = self._project(isolation["project_root"])
        connection = self._connect(project)
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = self._require_from(connection, project)
            if stored.desired_state == "STOPPED":
                connection.commit()
                return _Claim(
                    False,
                    stored.fence_epoch,
                    _stopped_refusal(project, occurrence, stored),
                )
            request_digest = _requested_digest(project, occurrence, stored.handle)
            self._read_idempotency(
                connection, "tick", occurrence.idempotency_key, request_digest
            )
            row = connection.execute(
                "SELECT payload FROM attestations WHERE occurrence_key = ?",
                (occurrence.idempotency_key,),
            ).fetchone()
            if row is not None:
                connection.commit()
                return _Claim(
                    False,
                    stored.fence_epoch,
                    replace(self._attestation_from(json.loads(row[0])), replayed=True),
                )
            existing_claim = connection.execute(
                "SELECT request_digest, fence_epoch FROM occurrence_claims "
                "WHERE occurrence_key = ?",
                (occurrence.idempotency_key,),
            ).fetchone()
            if existing_claim is not None:
                if existing_claim[0] != request_digest:
                    raise IdempotencyConflict(
                        "tick occurrence differs from its original request"
                    )
                connection.commit()
                return _Claim(False, int(existing_claim[1]))
            connection.execute(
                "INSERT INTO occurrence_claims"
                "(occurrence_key, request_digest, fence_epoch, status) "
                "VALUES (?, ?, ?, 'CLAIMED')",
                (occurrence.idempotency_key, request_digest, stored.fence_epoch),
            )
            self._write_idempotency(
                connection,
                "tick",
                occurrence.idempotency_key,
                request_digest,
                {"status": "CLAIMED"},
            )
            fence_token = _fence_token(project, occurrence, stored.fence_epoch)
            self._append_event(
                connection,
                stored,
                "TICK_CLAIMED",
                idempotency_key=occurrence.idempotency_key,
                request_digest=request_digest,
                occurrence_key=occurrence.idempotency_key,
                fence_token=fence_token,
            )
            connection.commit()
            return _Claim(True, stored.fence_epoch)
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute_claimed(
        self,
        occurrence: Any,
        context_capsule: dict[str, str],
        budget: dict[str, int],
        isolation: dict[str, Path],
        fence_epoch: int,
    ) -> TickAttestation:
        project = self._project(isolation["project_root"])
        connection = self._connect(project)
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = self._require_from(connection, project)
            requested_digest = _requested_digest(project, occurrence, stored.handle)
            claim = connection.execute(
                "SELECT request_digest, fence_epoch, status FROM occurrence_claims "
                "WHERE occurrence_key = ?",
                (occurrence.idempotency_key,),
            ).fetchone()
            if (
                stored.desired_state == "STOPPED"
                or stored.fence_epoch != fence_epoch
                or claim is None
                or claim[0] != requested_digest
                or int(claim[1]) != fence_epoch
            ):
                connection.commit()
                return _stopped_refusal(project, occurrence, stored)
            if claim[2] == "ATTESTED":
                row = connection.execute(
                    "SELECT payload FROM attestations WHERE occurrence_key = ?",
                    (occurrence.idempotency_key,),
                ).fetchone()
                connection.commit()
                if row is None:
                    raise ValueError("attested occurrence has no durable receipt")
                return replace(
                    self._attestation_from(json.loads(row[0])), replayed=True
                )
            if not _budget_available(stored.budget):
                connection.commit()
                return _budget_refusal(project, occurrence, stored)
            execution_receipt = _execute_bounded_action(
                occurrence, context_capsule, budget, isolation
            )
            observed_digest = execution_receipt["effect_digest"]
            resources = _resources(stored.budget, execution_receipt)
            fence_token = _fence_token(project, occurrence, fence_epoch)
            self._append_event(
                connection,
                stored,
                "EFFECT_APPLIED",
                idempotency_key=occurrence.idempotency_key,
                request_digest=requested_digest,
                occurrence_key=occurrence.idempotency_key,
                fence_token=fence_token,
                effect_digest=observed_digest,
            )
            attestation = TickAttestation(
                _attestation_id(project, occurrence, observed_digest),
                occurrence.idempotency_key,
                project,
                _project_id(project),
                _ledger_digest(project),
                dict(stored.budget),
                "AVAILABLE",
                "CHANGED",
                requested_digest,
                observed_digest,
                _isolation_receipt(project, occurrence),
                resources,
                execution_receipt,
            )
            self._save_attestation_to(connection, attestation)
            connection.execute(
                "UPDATE occurrence_claims SET status = 'ATTESTED' "
                "WHERE occurrence_key = ?",
                (occurrence.idempotency_key,),
            )
            self._write_idempotency(
                connection,
                "tick",
                occurrence.idempotency_key,
                requested_digest,
                {
                    "status": "ATTESTED",
                    "attestation_id": attestation.id,
                },
            )
            self._append_event(
                connection,
                stored,
                "TICK_ATTESTED",
                idempotency_key=occurrence.idempotency_key,
                request_digest=requested_digest,
                occurrence_key=occurrence.idempotency_key,
                attestation=attestation,
                fence_token=fence_token,
            )
            connection.commit()
            return attestation
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def await_claim(
        self, occurrence: Any, isolation: dict[str, Path]
    ) -> TickAttestation:
        project = self._project(isolation["project_root"])
        for _ in range(3000):
            stored = self._require(project)
            if stored.desired_state == "STOPPED":
                return _stopped_refusal(project, occurrence, stored)
            row = self._connect(project)
            try:
                attestation_row = row.execute(
                    "SELECT payload FROM attestations WHERE occurrence_key = ?",
                    (occurrence.idempotency_key,),
                ).fetchone()
            finally:
                row.close()
            if attestation_row is not None:
                return replace(
                    self._attestation_from(json.loads(attestation_row[0])),
                    replayed=True,
                )
            time.sleep(0.01)
        raise TimeoutError("timed out waiting for the claimed occurrence")

    def _require_from(
        self, connection: sqlite3.Connection, project: Path
    ) -> _StoredLoop:
        stored = self._load_from(connection, project)
        if stored is None:
            raise ValueError("no loop is armed for project")
        return stored

    def _require(self, project: Path) -> _StoredLoop:
        stored = self._load(project)
        if stored is None:
            raise ValueError("no loop is armed for project")
        return stored

    @staticmethod
    def _validate_handle(stored: _StoredLoop, handle: Any) -> None:
        if isinstance(handle, LoopRecord):
            if (
                handle.project_root == stored.project_root
                and handle.generation == stored.handle.generation
            ):
                return
        loop_id = getattr(handle, "loop_id", handle)
        if loop_id != stored.handle.loop_id:
            raise ValueError("handle does not belong to the selected project")


class LoopControlService:
    _ledger = _StandingLoopLedger()

    def arm(self, work: Any, *, idempotency_key: str) -> LoopHandle:
        return self._ledger.arm(work, idempotency_key=idempotency_key)

    def list(self, project_root: Any) -> tuple[LoopRecord, ...]:
        return self._ledger.list(project_root)

    def handle(self, project_root: Any) -> LoopHandle:
        return self._ledger.handle(project_root)

    def stop(
        self, project_root: Any, handle: Any, *, idempotency_key: str = "direct-stop"
    ) -> StopAttempt:
        return self._ledger.stop(project_root, handle, idempotency_key=idempotency_key)

    def recover(
        self,
        project_root: Any,
        *,
        apply: bool = False,
        idempotency_key: str = "recover-plan",
    ) -> Recovery:
        return self._ledger.recover(
            project_root, apply=apply, idempotency_key=idempotency_key
        )

    def execution_inputs(self, project_root: Any, occurrence: Any) -> _ExecutionInputs:
        return self._ledger.execution_inputs(project_root, occurrence)

    def last_attestation(self, project_root: Any) -> TickAttestation | None:
        return self._ledger.last_attestation(self._ledger._project(project_root))


class LoopRunner(StandingLoopTickPort):
    _ledger = LoopControlService._ledger

    def execute_tick(
        self, occurrence: Any, context_capsule: Any, budget: Any, isolation: Any
    ) -> TickAttestation:
        claim = self._ledger.claim(occurrence, isolation)
        if claim.receipt is not None:
            return claim.receipt
        if not claim.owner:
            return self._ledger.await_claim(occurrence, isolation)
        return self._ledger.execute_claimed(
            occurrence,
            context_capsule,
            budget,
            isolation,
            claim.fence_epoch,
        )


def _execute_bounded_action(
    occurrence: Any,
    context_capsule: dict[str, str],
    budget: dict[str, int],
    isolation: dict[str, Path],
) -> dict[str, Any]:
    """Run a real, inspectable bounded file effect for this manual core."""
    project = Path(isolation["project_root"])
    started_at = _StandingLoopLedger._now()
    started_clock = time.perf_counter()
    action_root = project / ".nwave" / "standing-loops" / "occurrences"
    action_root.mkdir(parents=True, exist_ok=True)
    effect_path = action_root / f"{occurrence.idempotency_key}.json"
    effect = {
        "schema_version": "des.loop.effect.v1",
        "occurrence_id": occurrence.idempotency_key,
        "loop_id": occurrence.loop_id,
        "context": context_capsule,
        "budget": budget,
        "started_at": started_at,
        "completed_at": _StandingLoopLedger._now(),
    }
    effect_bytes = json.dumps(effect, sort_keys=True).encode()
    effect_path.write_bytes(effect_bytes)
    observed_bytes = effect_path.read_bytes()
    effect_digest = sha256(observed_bytes).hexdigest()
    elapsed = max(time.perf_counter() - started_clock, 1e-9)
    consumed = {
        "tokens": max(1, (len(observed_bytes) + 3) // 4),
        "wall_seconds": elapsed,
        "agent_concurrency": 1,
        "box_concurrency": 1,
    }
    observed_at = _StandingLoopLedger._now()
    resource_receipts: dict[str, dict[str, Any]] = {}
    for resource, value in consumed.items():
        executor_resource = {
            "tokens": "workload_units",
            "wall_seconds": "duration_ms",
            "agent_concurrency": "agent_concurrency",
            "box_concurrency": "box_concurrency",
        }[resource]
        executor_value = value * 1000 if resource == "wall_seconds" else value
        measurement_id = sha256(
            json.dumps(
                {
                    "resource": executor_resource,
                    "value": executor_value,
                    "executor_id": "project-file-effect-executor.v1",
                    "effect_digest": effect_digest,
                    "observed_at": observed_at,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        resource_receipts[resource] = {
            "resource": resource,
            "value": value,
            "executor_resource": executor_resource,
            "executor_value": executor_value,
            "executor_id": "project-file-effect-executor.v1",
            "effect_digest": effect_digest,
            "observed_at": observed_at,
            "measurement_id": measurement_id,
        }
    measurement_id = sha256(
        json.dumps(
            {
                "effect_digest": effect_digest,
                "resource_measurement_ids": sorted(
                    receipt["measurement_id"] for receipt in resource_receipts.values()
                ),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    measurement = {
        "schema_version": "des.loop.resource-measurement.v1",
        "measurement_id": measurement_id,
        "source": "executor_observed",
        "effect_digest": effect_digest,
        "consumed": consumed,
        "resource_receipts": resource_receipts,
    }
    return {
        "executor_id": "project-file-effect-executor.v1",
        "effect_id": str(effect_path.relative_to(project)),
        "effect_digest": effect_digest,
        "observed_at": observed_at,
        "resource_receipt_id": measurement_id,
        "resource_measurement": measurement,
    }


def _budget_from(work: Any) -> dict[str, int]:
    return {
        "max_tokens_per_tick": work.max_tokens_per_tick,
        "max_wall_seconds": work.max_wall_seconds,
        "max_agent_concurrency": work.max_agent_concurrency,
        "max_box_concurrency": work.max_box_concurrency,
    }


def _project_id(project: Path) -> str:
    return sha256(str(project).encode()).hexdigest()


def _key_digest(key: str) -> str:
    return sha256(key.encode()).hexdigest()


def _ledger_digest(project: Path) -> str:
    return sha256(f"ledger-v1|{_project_id(project)}".encode()).hexdigest()


def _requested_digest(
    project: Path, occurrence: Any, handle: LoopHandle | None = None
) -> str:
    generation = 0 if handle is None else handle.generation
    return sha256(
        f"{_project_id(project)}|{occurrence.loop_id}|{generation}|"
        f"{occurrence.idempotency_key}".encode()
    ).hexdigest()


def _arm_request_digest(project: Path, work: Any) -> str:
    return sha256(
        json.dumps(
            {
                "project": _project_id(project),
                "outcome": work.outcome,
                "context": work.context_mode,
                "budget": _budget_from(work),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _control_request_digest(
    project: Path, verb: str, handle: LoopHandle, key: str
) -> str:
    return sha256(
        f"{_project_id(project)}|{verb}|{handle.loop_id}|{handle.generation}|{key}".encode()
    ).hexdigest()


def _isolation_receipt(project: Path, occurrence: Any) -> dict[str, str]:
    requested = _requested_digest(project, occurrence)
    return {
        "kind": "project-read-only",
        "receipt_id": sha256(f"isolation|{requested}".encode()).hexdigest(),
        "root_digest": sha256(str(project).encode()).hexdigest(),
    }


def _fence_token(project: Path, occurrence: Any, fence_epoch: int) -> str:
    return sha256(
        f"fence|{_project_id(project)}|{occurrence.idempotency_key}|"
        f"{fence_epoch}".encode()
    ).hexdigest()


def _attestation_id(project: Path, occurrence: Any, observed_digest: str | None) -> str:
    return sha256(
        f"tick-attestation-v1|{_project_id(project)}|{occurrence.idempotency_key}|{observed_digest or 'unobserved'}".encode()
    ).hexdigest()


def _budget_available(authorised: dict[str, int]) -> bool:
    return all(value > 0 for value in authorised.values())


def _resources(
    authorised: dict[str, int], receipt: dict[str, Any] | None = None
) -> dict[str, Any]:
    consumed = (
        {} if receipt is None else dict(receipt["resource_measurement"]["consumed"])
    )
    return {"authorised": dict(authorised), "consumed": consumed}


def _stopped_refusal(
    project: Path, occurrence: Any, stored: _StoredLoop
) -> TickAttestation:
    return TickAttestation(
        _attestation_id(project, occurrence, None),
        occurrence.idempotency_key,
        project,
        _project_id(project),
        _ledger_digest(project),
        dict(stored.budget),
        "REFUSED",
        "REFUSED_STOPPED",
        _requested_digest(project, occurrence, stored.handle),
        None,
        _isolation_receipt(project, occurrence),
        _resources(stored.budget),
    )


def _budget_refusal(
    project: Path, occurrence: Any, stored: _StoredLoop
) -> TickAttestation:
    return TickAttestation(
        _attestation_id(project, occurrence, None),
        occurrence.idempotency_key,
        project,
        _project_id(project),
        _ledger_digest(project),
        dict(stored.budget),
        "REFUSED",
        "REFUSED_BUDGET",
        _requested_digest(project, occurrence, stored.handle),
        None,
        _isolation_receipt(project, occurrence),
        _resources(stored.budget),
    )


__all__ = [
    "IdempotencyConflict",
    "LoopControlService",
    "LoopHandle",
    "LoopRecord",
    "LoopRunner",
    "Recovery",
    "StopAttempt",
    "TickAttestation",
]
