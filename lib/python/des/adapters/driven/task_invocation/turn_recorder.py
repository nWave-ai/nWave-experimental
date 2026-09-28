"""Write immutable diagnostic records for model turns.

The records never participate in DES control flow. Their producer projection is
evidence only: a failed reservation, observation, or publication is reported
on stderr after the model terminal has already been determined.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.adapters.driven.task_invocation.model_envelope import is_crafter_role
from des.domain.filesystem_projection import (
    FileState,
    FilesystemProjectionError,
    GitPath,
    PathTransition,
    ProjectionIndeterminate,
    ProjectionPolicy,
    WorkspaceProjection,
    observe_workspace,
    projection_to_bytes,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


TURN_LOG_RELATIVE_DIR = ".nwave/des/logs/turns"
RESERVED_RUN_ID_ENV = "NWAVE_DES_RESERVED_RUN_ID"
_RESERVATION_NAME = "reservation"
_POLICY_NAME = "policy"
_LOCK_NAME = ".sequence.lock"


def _new_run_id() -> str:
    return str(uuid.uuid4())


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        + b"\n"
    )


def _policy_bytes(policy: ProjectionPolicy) -> bytes:
    return _canonical_json(
        {
            "excluded_basename_prefixes": [
                base64.b64encode(prefix).decode("ascii")
                for prefix in policy.excluded_basename_prefixes
            ],
            "excluded_basenames": [
                base64.b64encode(basename).decode("ascii")
                for basename in policy.excluded_basenames
            ],
            "excluded_roots": [root.base64 for root in policy.excluded_roots],
            "schema_version": 1,
        }
    )


def _reservation_bytes(run_id: str, policy_sha256: str) -> bytes:
    return _canonical_json(
        {
            "high_water_mark": 0,
            "policy_sha256": policy_sha256,
            "run_id": run_id,
            "schema_version": 1,
        }
    )


def _state_json(state: FileState) -> dict[str, object]:
    if state.kind == "absent":
        return {"kind": "absent"}
    assert (
        state.mode is not None and state.size is not None and state.sha256 is not None
    )
    return {
        "kind": state.kind,
        "mode": format(state.mode, "o"),
        "sha256": state.sha256,
        "size": state.size,
    }


def _transition_json(transition: PathTransition) -> dict[str, object]:
    return {
        "after": _state_json(transition.after),
        "before": _state_json(transition.before),
        "path": transition.path.base64,
    }


@dataclass(frozen=True)
class _TurnStart:
    workspace: Path
    before: WorkspaceProjection | None
    problem: str | None


# The records below carry one turn document's fields, split the way a reader asks
# about a turn: what was issued, what came back, when, and which turn of the run
# a producer projection belongs to.  Every one of them is keyword-only because
# every one has at least two fields of the same type -- two strings, or two
# floats -- and nothing here checks an annotation at runtime, so a positional
# construction could transpose a pair and no gate would see it.


@dataclass(frozen=True, kw_only=True)
class IssuedTurn:
    """The turn as issued: its record root, its role, its prompt, its argv.

    ``argv`` is the provider command line that was actually spawned, and is
    ``None`` for a turn refused before any provider existed.
    """

    root: Path
    role_id: str
    prompt: str
    argv: list[str] | None


@dataclass(frozen=True, kw_only=True)
class TurnResult:
    """What the turn returned, and how it ended.

    ``raised`` names the exception type for a turn that left by raising rather
    than by answering; a turn that answered carries ``None``.
    """

    outcome: str
    diagnostic: str
    exit_status: int
    retry_safe: bool
    provider_stdout: str | None
    provider_stderr: str | None
    raised: str | None = None


@dataclass(frozen=True, kw_only=True)
class TurnTiming:
    """The turn's two wall-clock instants; the record derives its duration."""

    started_at: float
    ended_at: float


@dataclass(frozen=True, kw_only=True)
class _TurnIdentity:
    """Which turn of which run a producer projection belongs to."""

    run_id: str
    sequence: int
    role_id: str


@dataclass(frozen=True)
class RecorderReservation:
    """The immutable native run reservation bound into a delivery child env."""

    run_id: str
    directory: Path
    policy_sha256: str
    reservation_sha256: str

    @property
    def environment_delta(self) -> dict[str, str]:
        return {RESERVED_RUN_ID_ENV: self.run_id}


def reserve_d0(workspace: Path, policy: ProjectionPolicy) -> RecorderReservation:
    """Reserve one empty UUIDv4 record directory before delivery starts."""
    return _reserve(workspace, policy)


def _reserve(
    workspace: Path, policy: ProjectionPolicy, run_id: str | None = None
) -> RecorderReservation:
    if not isinstance(policy, ProjectionPolicy):
        raise TypeError("reserve_d0 requires a ProjectionPolicy")
    root = Path(workspace)
    policy_raw = _policy_bytes(policy)
    policy_sha256 = hashlib.sha256(policy_raw).hexdigest()
    parent = root / TURN_LOG_RELATIVE_DIR
    parent.mkdir(parents=True, exist_ok=True)
    while True:
        candidate = run_id or _new_run_id()
        directory = parent / candidate
        try:
            directory.mkdir()
        except FileExistsError:
            if run_id is not None:
                raise RuntimeError(
                    "run directory already exists; refusing UUID collision"
                )
            continue
        break
    reservation_raw = _reservation_bytes(candidate, policy_sha256)
    try:
        _write_exclusive(directory / _POLICY_NAME, policy_raw)
        _write_exclusive(directory / _RESERVATION_NAME, reservation_raw)
        _sync_directory(directory)
    except BaseException:
        # Leave evidence of a failed exclusive reservation; never re-use it.
        raise
    return RecorderReservation(
        candidate,
        directory,
        policy_sha256,
        hashlib.sha256(reservation_raw).hexdigest(),
    )


class TurnRecorder:
    """One recorder per invocation with UUIDv4 reservation and locked sequence."""

    def __init__(self, run_id: str | None = None, root: Path | None = None) -> None:
        supplied = os.environ.get(RESERVED_RUN_ID_ENV)
        if run_id is not None and supplied is not None and run_id != supplied:
            self._run_id, self._reservation_problem = (
                run_id,
                "configured run id disagrees with reserved run id",
            )
        else:
            self._run_id, self._reservation_problem = (
                supplied or run_id or _new_run_id(),
                None,
            )
        self._root = root
        self._sequence = 0
        self._prepared_anchor: Path | None = None
        self._prepared_policy: ProjectionPolicy | None = None

    @property
    def run_id(self) -> str:
        return self._run_id

    def begin(self, *, root: Path, role_id: str) -> _TurnStart:
        """Capture a crafter's before projection before provider invocation."""
        anchor = self._anchor(root)
        problem = self._prepare(anchor)
        if not is_crafter_role(role_id):
            return _TurnStart(Path(root), None, problem)
        if problem is not None:
            return _TurnStart(Path(root), None, problem)
        assert self._prepared_policy is not None
        try:
            return _TurnStart(
                Path(root),
                observe_workspace(Path(root), self._prepared_policy),
                None,
            )
        except (OSError, ProjectionIndeterminate) as error:
            return _TurnStart(Path(root), None, str(error))

    def finish(self, *, started: _TurnStart, role_id: str) -> dict[str, object]:
        """Publish a crafter projection before its turn document."""
        if not is_crafter_role(role_id):
            return {"state": "not_applicable"}
        if started.problem is not None or started.before is None:
            return _indeterminate(started.problem or "before projection is unavailable")
        if self._prepared_policy is None:
            return _indeterminate("reserved projection policy is unavailable")
        try:
            after = observe_workspace(started.workspace, self._prepared_policy)
            transitions = started.before.transitions_to(after)
            anchor = self._anchor(started.workspace)
            problem = self._prepare(anchor)
            if problem is not None:
                return _indeterminate(problem)
            published: dict[str, bytes] = {}

            def publish(sequence: int) -> None:
                raw = _producer_projection_bytes(
                    started.before,
                    after,
                    transitions,
                    _TurnIdentity(
                        run_id=self._run_id, sequence=sequence, role_id=role_id
                    ),
                )
                _publish_no_replace(
                    self._directory(anchor) / f"{sequence:02d}-{role_id}.projection",
                    raw,
                )
                published["raw"] = raw

            sequence = self._publish_new(
                anchor,
                publish,
            )
            path = self._directory(anchor) / f"{sequence:02d}-{role_id}.projection"
            raw = published["raw"]
            return {
                "path": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "state": "captured",
                "transition_count": len(transitions),
            }
        except (OSError, ProjectionIndeterminate, RuntimeError) as error:
            return _indeterminate(str(error))

    def record(
        self,
        *,
        turn: IssuedTurn,
        result: TurnResult,
        timing: TurnTiming,
        producer_projection: dict[str, object] | None = None,
    ) -> Path | None:
        """Write one immutable turn document; errors stay diagnostic-only."""
        role_id = turn.role_id
        anchor = self._anchor(turn.root)
        problem = self._prepare(anchor)
        if problem is not None:
            self._report(role_id, problem)
            return None
        try:

            def publish(sequence: int) -> None:
                document: dict[str, Any] = {
                    "run_id": self._run_id,
                    "sequence": sequence,
                    "role_id": role_id,
                    "prompt": turn.prompt,
                    "argv": turn.argv,
                    "outcome": result.outcome,
                    "diagnostic": result.diagnostic,
                    "exit_status": result.exit_status,
                    "retry_safe": result.retry_safe,
                    "provider_stdout": result.provider_stdout,
                    "provider_stderr": result.provider_stderr,
                    "raised": result.raised,
                    "started_at": _utc(timing.started_at),
                    "ended_at": _utc(timing.ended_at),
                    "duration_seconds": round(timing.ended_at - timing.started_at, 6),
                    "producer_projection": producer_projection
                    or {"state": "not_applicable"},
                }
                _publish_no_replace(
                    self._directory(anchor) / f"{sequence:02d}-{role_id}.json",
                    _canonical_json(document),
                )

            if (
                producer_projection is not None
                and producer_projection.get("state") == "captured"
            ):
                projection_name = producer_projection.get("path")
                if not isinstance(projection_name, str):
                    raise RuntimeError("captured producer projection has no path")
                sequence_text, separator, _ = projection_name.partition("-")
                if not separator or not sequence_text.isdecimal():
                    raise RuntimeError(
                        "captured producer projection has an invalid path"
                    )
                sequence = int(sequence_text)
                _validate_producer_reference(
                    producer_projection,
                    self._directory(anchor),
                    self._run_id,
                    sequence,
                    role_id,
                )
                self._publish_existing(anchor, sequence, publish)
            else:
                sequence = self._publish_new(anchor, publish)
            self._sequence = max(self._sequence, sequence)
            return self._directory(anchor) / f"{sequence:02d}-{role_id}.json"
        except (OSError, RuntimeError) as error:
            self._report(role_id, str(error))
            return None

    def _anchor(self, root: Path) -> Path:
        return Path(self._root) if self._root is not None else Path(root)

    def _directory(self, anchor: Path) -> Path:
        return anchor / TURN_LOG_RELATIVE_DIR / self._run_id

    def _prepare(self, anchor: Path) -> str | None:
        if self._reservation_problem is not None:
            return self._reservation_problem
        if not _is_uuid4(self._run_id):
            return "run id is not a canonical UUIDv4"
        if self._prepared_anchor is not None:
            return (
                None
                if self._prepared_anchor == anchor
                else "one recorder cannot publish into two record roots"
            )
        directory = self._directory(anchor)
        inherited = os.environ.get(RESERVED_RUN_ID_ENV) is not None
        try:
            if inherited:
                policy = _read_reserved_policy(directory)
                _validate_reservation(directory, self._run_id, policy)
            else:
                policy = ProjectionPolicy.native_capture()
                _reserve(anchor, policy, self._run_id)
        except (OSError, RuntimeError, ValueError) as error:
            return f"could not reserve run: {error}"
        self._prepared_anchor = anchor
        self._prepared_policy = policy
        return None

    def _publish_new(self, anchor: Path, publish: Callable[[int], None]) -> int:
        directory = self._directory(anchor)
        with _sequence_lock(directory / _LOCK_NAME):
            sequences = self._validated_sequences(directory)
            sequence = max(sequences, default=0) + 1
            _write_exclusive(directory / f"{sequence:02d}.sequence", b"")
            publish(sequence)
            return sequence

    def _publish_existing(
        self, anchor: Path, sequence: int, publish: Callable[[int], None]
    ) -> None:
        directory = self._directory(anchor)
        with _sequence_lock(directory / _LOCK_NAME):
            self._validated_sequences(directory, pending_sequence=sequence)
            marker = directory / f"{sequence:02d}.sequence"
            projection = (
                directory
                / f"{sequence:02d}-{self._role_from_projection(sequence, directory)}.projection"
            )
            if not marker.is_file() or not projection.is_file():
                raise RuntimeError(
                    "captured producer projection reservation is orphaned"
                )
            publish(sequence)

    def _validated_sequences(
        self, directory: Path, pending_sequence: int | None = None
    ) -> set[int]:
        """Validate every existing member before it can advance high water."""
        if self._prepared_policy is None:
            raise RuntimeError("reserved projection policy is unavailable")
        _validate_reservation(directory, self._run_id, self._prepared_policy)
        entries: dict[int, dict[str, Path]] = {}
        ignored = {_RESERVATION_NAME, _POLICY_NAME, _LOCK_NAME}
        for child in directory.iterdir():
            if child.name in ignored:
                continue
            sequence, kind = _sequence_member(child.name)
            if sequence is None or kind is None:
                raise RuntimeError("run directory contains a foreign record")
            bucket = entries.setdefault(sequence, {})
            if kind in bucket:
                raise RuntimeError("run directory has duplicate sequence members")
            bucket[kind] = child
        sequences = set(entries)
        if sequences and sequences != set(range(1, max(sequences) + 1)):
            raise RuntimeError("turn sequence has a gap")
        for sequence, members in entries.items():
            marker = members.get("marker")
            if marker is None or _read_exact(marker) != b"":
                raise RuntimeError("turn sequence has no empty exclusive reservation")
            turn, projection = members.get("turn"), members.get("projection")
            if turn is None:
                if sequence == pending_sequence and projection is not None:
                    _validate_projection(
                        _read_exact(projection),
                        self._run_id,
                        sequence,
                        _role_from_name(projection.name, sequence, ".projection"),
                    )
                    continue
                raise RuntimeError("turn sequence reservation has no published record")
            role_id = _validate_turn(_read_exact(turn), self._run_id, sequence)
            if _role_from_name(turn.name, sequence, ".json") != role_id:
                raise RuntimeError("turn record filename role differs from its content")
            if projection is not None:
                if _role_from_name(projection.name, sequence, ".projection") != role_id:
                    raise RuntimeError(
                        "producer projection filename role differs from its turn"
                    )
                _validate_projection(
                    _read_exact(projection), self._run_id, sequence, role_id
                )
            _validate_producer_reference(
                _canonical_object(_read_exact(turn), "turn record")[
                    "producer_projection"
                ],
                directory,
                self._run_id,
                sequence,
                role_id,
            )
        return sequences

    def _role_from_projection(self, sequence: int, directory: Path) -> str:
        for child in directory.iterdir():
            parsed, kind = _sequence_member(child.name)
            if parsed == sequence and kind == "projection":
                return _role_from_name(child.name, sequence, ".projection")
        raise RuntimeError("captured producer projection reservation is orphaned")

    def _report(self, role_id: str, problem: str) -> None:
        print(
            f"des: could not record turn {self._sequence + 1} for {role_id}: {problem}",
            file=sys.stderr,
        )


def _producer_projection_bytes(
    before: WorkspaceProjection,
    after: WorkspaceProjection,
    transitions: tuple[PathTransition, ...],
    identity: _TurnIdentity,
) -> bytes:
    return _canonical_json(
        {
            "after_sha256": hashlib.sha256(projection_to_bytes(after)).hexdigest(),
            "before_sha256": hashlib.sha256(projection_to_bytes(before)).hexdigest(),
            "role_id": identity.role_id,
            "run_id": identity.run_id,
            "schema_version": 1,
            "sequence": identity.sequence,
            "transitions": [_transition_json(transition) for transition in transitions],
        }
    )


def _indeterminate(problem: str) -> dict[str, object]:
    return {
        "how": "inspect the recorder diagnostic and repair the filesystem observation",
        "state": "indeterminate",
        "what": "native producer projection was not captured",
        "why": problem,
    }


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError):
        return False
    return parsed.version == 4 and str(parsed) == value


def _read_exact(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65536):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _canonical_object(raw: bytes, subject: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{subject} is not JSON") from error
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise RuntimeError(f"{subject} is not canonical")
    return value


def _hash(value: object, subject: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(f"{subject} is not a lowercase SHA-256")
    return value


def _validate_reservation(
    directory: Path, run_id: str, policy: ProjectionPolicy
) -> None:
    if not directory.is_dir():
        raise RuntimeError("reserved run directory does not exist under record root")
    policy_raw = _policy_bytes(policy)
    if _read_exact(directory / _POLICY_NAME) != policy_raw:
        raise RuntimeError("reserved projection policy is missing or differs")
    reservation_raw = _read_exact(directory / _RESERVATION_NAME)
    reservation = _canonical_object(reservation_raw, "run reservation")
    if set(reservation) != {
        "high_water_mark",
        "policy_sha256",
        "run_id",
        "schema_version",
    }:
        raise RuntimeError("run reservation has an invalid schema")
    if (
        type(reservation["schema_version"]) is not int
        or reservation["schema_version"] != 1
        or reservation["run_id"] != run_id
        or type(reservation["high_water_mark"]) is not int
        or reservation["high_water_mark"] != 0
        or _hash(reservation["policy_sha256"], "reservation policy hash")
        != hashlib.sha256(policy_raw).hexdigest()
    ):
        raise RuntimeError("run reservation does not bind this policy and UUID")


def _read_reserved_policy(directory: Path) -> ProjectionPolicy:
    """Read one exact reservation policy; malformed or altered bytes fail closed."""
    raw = _read_exact(directory / _POLICY_NAME)
    policy = _canonical_object(raw, "reserved projection policy")
    if set(policy) != {
        "excluded_basename_prefixes",
        "excluded_basenames",
        "excluded_roots",
        "schema_version",
    }:
        raise RuntimeError("reserved projection policy has an invalid schema")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise RuntimeError("reserved projection policy has an invalid schema")
    roots = policy["excluded_roots"]
    basenames = policy["excluded_basenames"]
    prefixes = policy["excluded_basename_prefixes"]
    if not all(isinstance(value, list) for value in (roots, basenames, prefixes)):
        raise RuntimeError("reserved projection policy rules are invalid")
    try:
        value = ProjectionPolicy.from_rules(
            excluded_roots=(GitPath.from_base64(root) for root in roots),
            excluded_basenames=(_decode_basename(value) for value in basenames),
            excluded_basename_prefixes=(_decode_basename(value) for value in prefixes),
        )
    except (FilesystemProjectionError, TypeError) as error:
        raise RuntimeError("reserved projection policy rules are invalid") from error
    if _policy_bytes(value) != raw:
        raise RuntimeError("reserved projection policy is not canonical")
    return value


def _decode_basename(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise FilesystemProjectionError("reserved basename rule is invalid")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise FilesystemProjectionError("reserved basename rule is invalid") from error
    if base64.b64encode(decoded).decode("ascii") != value:
        raise FilesystemProjectionError("reserved basename rule is not canonical")
    return decoded


def _state_from_json(value: object) -> FileState:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise RuntimeError("producer projection state is malformed")
    try:
        if set(value) == {"kind"} and value["kind"] == "absent":
            return FileState.absent()
        if set(value) != {"kind", "mode", "sha256", "size"}:
            raise RuntimeError("producer projection state has invalid fields")
        mode = int(str(value["mode"]), 8)
        if value["kind"] == "regular":
            return FileState.regular(mode, value["size"], value["sha256"])
        if value["kind"] == "symlink":
            if value["mode"] != "120000":
                raise RuntimeError("symlink projection mode is not 120000")
            return FileState.symlink(value["size"], value["sha256"])
    except (FilesystemProjectionError, TypeError, ValueError) as error:
        raise RuntimeError("producer projection state is invalid") from error
    raise RuntimeError("producer projection state has an unknown kind")


def _validate_projection(
    raw: bytes, expected_run_id: str, expected_sequence: int, expected_role: str
) -> int:
    projection = _canonical_object(raw, "producer projection")
    if (
        set(projection)
        != {
            "after_sha256",
            "before_sha256",
            "role_id",
            "run_id",
            "schema_version",
            "sequence",
            "transitions",
        }
        or type(projection["schema_version"]) is not int
        or projection["schema_version"] != 1
        or projection["run_id"] != expected_run_id
        or type(projection["sequence"]) is not int
        or projection["sequence"] != expected_sequence
        or projection["role_id"] != expected_role
    ):
        raise RuntimeError("producer projection has an invalid schema")
    _hash(projection["before_sha256"], "producer before hash")
    _hash(projection["after_sha256"], "producer after hash")
    transitions = projection["transitions"]
    if not isinstance(transitions, list):
        raise RuntimeError("producer projection transitions are not an array")
    paths: list[bytes] = []
    for transition in transitions:
        if not isinstance(transition, dict) or set(transition) != {
            "after",
            "before",
            "path",
        }:
            raise RuntimeError("producer projection transition is malformed")
        try:
            path = GitPath.from_base64(transition["path"])
        except (FilesystemProjectionError, TypeError) as error:
            raise RuntimeError("producer projection path is invalid") from error
        before, after = (
            _state_from_json(transition["before"]),
            _state_from_json(transition["after"]),
        )
        if before == after:
            raise RuntimeError("producer projection contains a no-op transition")
        paths.append(path.raw)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise RuntimeError("producer projection transitions are not canonical")
    return len(transitions)


def _validate_producer_reference(
    value: object, directory: Path, run_id: str, sequence: int, role_id: str
) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("state"), str):
        raise RuntimeError("turn producer projection is malformed")
    state = value["state"]
    if state == "not_applicable" and set(value) == {"state"}:
        return
    if state == "indeterminate" and set(value) == {"how", "state", "what", "why"}:
        if all(
            isinstance(value[key], str) and value[key] for key in ("how", "what", "why")
        ):
            return
    if state != "captured" or set(value) != {
        "path",
        "sha256",
        "state",
        "transition_count",
    }:
        raise RuntimeError("turn producer projection has an invalid state")
    name = f"{sequence:02d}-{role_id}.projection"
    if value["path"] != name or type(value["transition_count"]) is not int:
        raise RuntimeError("turn producer projection does not name this sequence")
    expected_hash = _hash(value["sha256"], "turn producer projection hash")
    raw = _read_exact(directory / name)
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise RuntimeError("turn producer projection hash differs from its artifact")
    if (
        _validate_projection(raw, run_id, sequence, role_id)
        != value["transition_count"]
    ):
        raise RuntimeError("turn producer projection transition count differs")


def _sequence_member(name: str) -> tuple[int | None, str | None]:
    stem, separator, suffix = name.partition(".")
    if separator and suffix == "sequence" and stem.isdecimal():
        sequence = int(stem)
        return (
            (sequence, "marker")
            if sequence > 0 and f"{sequence:02d}" == stem
            else (None, None)
        )
    stem, separator, suffix = name.partition("-")
    if not separator or not stem.isdecimal() or not suffix:
        return None, None
    sequence = int(stem)
    if sequence <= 0 or f"{sequence:02d}" != stem:
        return None, None
    if suffix.endswith(".json"):
        return sequence, "turn"
    if suffix.endswith(".projection"):
        return sequence, "projection"
    return None, None


def _role_from_name(name: str, sequence: int, suffix: str) -> str:
    prefix = f"{sequence:02d}-"
    if not name.startswith(prefix) or not name.endswith(suffix):
        raise RuntimeError("record filename does not match its sequence")
    role_id = name[len(prefix) : -len(suffix)]
    if not role_id or "/" in role_id or "\\" in role_id:
        raise RuntimeError("record filename has an unsafe role id")
    return role_id


def _validate_turn(raw: bytes, run_id: str, sequence: int) -> str:
    turn = _canonical_object(raw, "turn record")
    required = {
        "argv",
        "diagnostic",
        "duration_seconds",
        "ended_at",
        "exit_status",
        "outcome",
        "producer_projection",
        "prompt",
        "provider_stderr",
        "provider_stdout",
        "raised",
        "retry_safe",
        "role_id",
        "run_id",
        "sequence",
        "started_at",
    }
    if set(turn) != required:
        raise RuntimeError("turn record has an invalid schema")
    if (
        turn["run_id"] != run_id
        or type(turn["sequence"]) is not int
        or turn["sequence"] != sequence
    ):
        raise RuntimeError("turn record does not bind this run and sequence")
    if not isinstance(turn["role_id"], str) or not turn["role_id"]:
        raise RuntimeError("turn record role id is invalid")
    if not isinstance(turn["producer_projection"], dict):
        raise RuntimeError("turn record producer projection is invalid")
    return turn["role_id"]


def _write_exclusive(path: Path, raw: bytes) -> None:
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600
    )
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_no_replace(path: Path, raw: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, path)
        _sync_directory(path.parent)
    except FileExistsError as error:
        raise RuntimeError(
            f"refusing to overwrite existing record {path.name}"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _sequence_lock(path: Path) -> Iterator[None]:
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600
    )
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                _write_all(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, raw: bytes) -> None:
    """Handle valid short writes; a zero write cannot publish complete bytes."""
    written = 0
    while written < len(raw):
        count = os.write(descriptor, raw[written:])
        if count <= 0:
            raise OSError("could not write complete diagnostic record")
        written += count


def _utc(instant: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(instant))


__all__ = [
    "RESERVED_RUN_ID_ENV",
    "TURN_LOG_RELATIVE_DIR",
    "IssuedTurn",
    "RecorderReservation",
    "TurnRecorder",
    "TurnResult",
    "TurnTiming",
    "reserve_d0",
]
