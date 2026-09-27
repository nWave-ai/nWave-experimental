"""Read native D0 producer-to-delivery attribution evidence.

V1 receipt files were caller assembled and remain fail-closed. V2 retains the
reserved native records under content-addressed paths, then joins their typed
crafter transitions to a strict final delivery projection and a closed D0
ledger. No model prose or caller-supplied diff is used for this decision.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.adapters.driven.task_invocation.model_envelope import is_crafter_role
from des.adapters.driven.task_invocation.turn_recorder import TURN_LOG_RELATIVE_DIR
from des.domain.filesystem_projection import (
    FileState,
    FilesystemProjectionError,
    GitPath,
    PathTransition,
    projection_from_bytes,
    projection_to_bytes,
)
from scripts.analysis.k4 import intervention_ledger


if TYPE_CHECKING:
    from des.adapters.driven.task_invocation.turn_recorder import RecorderReservation
    from scripts.analysis.blind_review import DeliveryCapture


PRODUCER_RECEIPT_SCHEMA = "ProducerReceiptV1"
DELIVERY_ATTRIBUTION_SCHEMA = "DeliveryAttributionV1"
ATTRIBUTION_FILE_NAME = "delivery-attribution-v1.json"
DELIVERY_ATTRIBUTION_V2_SCHEMA = "DeliveryAttributionV2"
ATTRIBUTION_V2_FILE_NAME = "delivery-attribution-v2.json"
ATTRIBUTED = "ATTRIBUTED"
NOT_RETAINED = "NOT_RETAINED"
INDETERMINATE = "INDETERMINATE"


_NATIVE_ATTRIBUTION_BLOCKER = (
    "native attribution is unavailable: TurnRecorder does not system-record a "
    "producer projection binding. The minimal native path is a "
    "TurnRecorder-created immutable projection record containing the producer "
    "artifact path and SHA-256, followed by a closed, verified D0 ledger "
    "delivery_captured event containing the exact final DELIVERY.patch path and "
    "SHA-256 plus its packet identity. Attribution must verify those native "
    "records before it can return ATTRIBUTED."
)


class AttributionError(ValueError):
    """Evidence cannot prove producer-to-delivery attribution."""


_SEQUENCE = re.compile(
    r"^(?P<sequence>[0-9]{2,})-(?P<role>[^/\\]+)\.(?P<kind>json|projection)$"
)
_MARKER = re.compile(r"^[0-9]{2,}\.sequence$")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise AttributionError(f"retained evidence directory is missing: {root.name}")
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AttributionError(f"{name} is missing or empty")
    return value


def _evidence_path(root: Path, relative: str, name: str) -> Path:
    """Resolve an artifact only inside its attribution packet."""
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise AttributionError(f"{name} escapes the attribution packet")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved_root not in (resolved, *resolved.parents):
        raise AttributionError(f"{name} escapes the attribution packet")
    return resolved


def _provider_result(turn: dict[str, Any]) -> tuple[str, str]:
    """Read the fields the current native ``TurnRecorder`` actually writes."""
    raw = _require_text(turn.get("provider_stdout"), "native provider_stdout")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AttributionError("native provider_stdout is not JSON") from exc
    if not isinstance(envelope, dict):
        raise AttributionError("native provider_stdout is not an object")
    session = _require_text(envelope.get("session_id"), "native provider session_id")
    if (
        envelope.get("terminal_reason") != "completed"
        or envelope.get("is_error") is not False
    ):
        raise AttributionError("native producer turn did not complete successfully")
    result = _require_text(envelope.get("result"), "native provider result")
    return session, result


@dataclass(frozen=True)
class ProducerReceiptV1:
    """Untrusted legacy receipt, retained only so old evidence can be read."""

    schema: str
    root_delivery_session: str
    des_step: str
    role_id: str
    run_id: str
    turn: int
    producer_session_id: str
    input_base_tree: str
    result_patch_path: str
    result_patch_sha256: str
    result_tree_sha256: str | None
    native_turn_receipt_path: str
    native_turn_receipt_sha256: str
    native_result_sha256: str
    native_handover_path: str | None
    native_handover_sha256: str | None
    completion: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryAttributionV1:
    """Untrusted legacy delivery join, retained only for fail-closed reading."""

    schema: str
    root_delivery_session: str
    root_delivery_session_path: str
    root_delivery_session_receipt_sha256: str
    producer: ProducerReceiptV1
    final_delivery_patch_path: str
    final_delivery_patch_sha256: str

    def to_json(self) -> dict[str, object]:
        result = asdict(self)
        result["producer"] = self.producer.to_json()
        return result


@dataclass(frozen=True)
class AttributionAssessment:
    status: str
    why: str
    producer_role: str | None = None


def construct_producer_receipt(
    native_turn_path: Path,
    *,
    root_delivery_session: str,
    des_step: str,
    input_base_tree: str,
    native_turn_receipt_path: str,
    result_patch_path: str,
    result_patch: Path,
    result_tree_sha256: str | None = None,
    native_handover_path: str | None = None,
    native_handover: Path | None = None,
) -> ProducerReceiptV1:
    """Refuse caller-created producer projections.

    Parameters remain temporarily for an explicit refusal at the old API
    boundary.  They are intentionally not read: a matching caller-provided
    patch, including one with a correct hash, is not a native producer record.
    """
    raise AttributionError(_NATIVE_ATTRIBUTION_BLOCKER)


def construct_delivery_attribution(
    producer: ProducerReceiptV1,
    *,
    root_delivery_session_path: str,
    root_delivery_session_receipt: Path,
    final_delivery_patch_path: str,
    final_delivery_patch: Path,
) -> DeliveryAttributionV1:
    """Bind one producer receipt to the root session and captured delivery.

    The current campaign envelope writes its root ``session_id`` at top level.
    It is not a DES turn receipt, so it remains a separate artifact and both
    its bytes and session id are bound here.
    """
    _require_text(root_delivery_session_path, "root_delivery_session_path")
    _require_text(final_delivery_patch_path, "final_delivery_patch_path")
    try:
        root_bytes = root_delivery_session_receipt.read_bytes()
        root_result = json.loads(root_bytes)
        final_hash = _sha256_file(final_delivery_patch)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttributionError(f"root delivery evidence is unavailable: {exc}") from exc
    if not isinstance(root_result, dict):
        raise AttributionError("root delivery evidence is not an object")
    root_session = _require_text(
        root_result.get("session_id"), "root delivery session_id"
    )
    if root_session != producer.root_delivery_session:
        raise AttributionError(
            "root delivery session does not join the producer receipt"
        )
    return DeliveryAttributionV1(
        schema=DELIVERY_ATTRIBUTION_SCHEMA,
        root_delivery_session=producer.root_delivery_session,
        root_delivery_session_path=root_delivery_session_path,
        root_delivery_session_receipt_sha256=_sha256_bytes(root_bytes),
        producer=producer,
        final_delivery_patch_path=final_delivery_patch_path,
        final_delivery_patch_sha256=final_hash,
    )


def write_attribution(path: Path, attribution: DeliveryAttributionV1) -> None:
    """Publish a new receipt. Existing evidence is never overwritten."""
    if path.exists() or path.is_symlink():
        raise AttributionError(f"attribution destination already exists: {path}")
    _publish_no_replace(
        path,
        (json.dumps(attribution.to_json(), indent=1, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )


def _read_producer(value: object) -> ProducerReceiptV1:
    if not isinstance(value, dict):
        raise AttributionError("producer receipt is missing")
    required = {
        "schema",
        "root_delivery_session",
        "des_step",
        "role_id",
        "run_id",
        "turn",
        "producer_session_id",
        "input_base_tree",
        "result_patch_path",
        "result_patch_sha256",
        "result_tree_sha256",
        "native_turn_receipt_path",
        "native_turn_receipt_sha256",
        "native_result_sha256",
        "native_handover_path",
        "native_handover_sha256",
        "completion",
    }
    if set(value) != required:
        raise AttributionError("producer receipt has an unsupported shape")
    try:
        producer = ProducerReceiptV1(**value)
    except TypeError as exc:
        raise AttributionError("producer receipt cannot be read") from exc
    if producer.schema != PRODUCER_RECEIPT_SCHEMA:
        raise AttributionError("producer receipt schema is unsupported")
    for field in (
        "root_delivery_session",
        "des_step",
        "role_id",
        "run_id",
        "producer_session_id",
        "input_base_tree",
        "result_patch_path",
        "result_patch_sha256",
        "native_turn_receipt_path",
        "native_turn_receipt_sha256",
        "native_result_sha256",
    ):
        _require_text(getattr(producer, field), field)
    if not isinstance(producer.turn, int) or producer.turn < 1:
        raise AttributionError("producer turn is missing or invalid")
    if producer.completion != "completed":
        raise AttributionError("producer completion is not completed")
    if (producer.native_handover_path is None) != (
        producer.native_handover_sha256 is None
    ):
        raise AttributionError("native handover path and hash do not join")
    return producer


def _read_attribution(path: Path) -> DeliveryAttributionV1:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttributionError(f"attribution record is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise AttributionError("attribution record is not an object")
    required = {
        "schema",
        "root_delivery_session",
        "root_delivery_session_path",
        "root_delivery_session_receipt_sha256",
        "producer",
        "final_delivery_patch_path",
        "final_delivery_patch_sha256",
    }
    if set(value) != required:
        raise AttributionError("attribution record has an unsupported shape")
    producer = _read_producer(value["producer"])
    attribution = DeliveryAttributionV1(
        schema=value["schema"],
        root_delivery_session=value["root_delivery_session"],
        root_delivery_session_path=value["root_delivery_session_path"],
        root_delivery_session_receipt_sha256=value[
            "root_delivery_session_receipt_sha256"
        ],
        producer=producer,
        final_delivery_patch_path=value["final_delivery_patch_path"],
        final_delivery_patch_sha256=value["final_delivery_patch_sha256"],
    )
    if attribution.schema != DELIVERY_ATTRIBUTION_SCHEMA:
        raise AttributionError("attribution schema is unsupported")
    _require_text(attribution.root_delivery_session, "root_delivery_session")
    _require_text(attribution.root_delivery_session_path, "root_delivery_session_path")
    _require_text(
        attribution.root_delivery_session_receipt_sha256,
        "root_delivery_session_receipt_sha256",
    )
    _require_text(attribution.final_delivery_patch_path, "final_delivery_patch_path")
    _require_text(
        attribution.final_delivery_patch_sha256, "final_delivery_patch_sha256"
    )
    if attribution.root_delivery_session != producer.root_delivery_session:
        raise AttributionError(
            "root delivery session does not join the producer receipt"
        )
    return attribution


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        + b"\n"
    )


def _canonical_object(raw: bytes, subject: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttributionError(f"{subject} is not JSON") from exc
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise AttributionError(f"{subject} is not canonical")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hex(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AttributionError(f"{name} is not a lowercase SHA-256")
    return value


def _state(value: object) -> FileState:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise AttributionError("native projection state is malformed")
    try:
        if value == {"kind": "absent"}:
            return FileState.absent()
        if set(value) != {"kind", "mode", "sha256", "size"}:
            raise AttributionError("native projection state has invalid fields")
        kind, mode = value["kind"], value["mode"]
        if not isinstance(mode, str):
            raise AttributionError("native projection mode is invalid")
        if kind == "regular":
            return FileState.regular(int(mode, 8), value["size"], value["sha256"])
        if kind == "symlink" and mode == "120000":
            return FileState.symlink(value["size"], value["sha256"])
    except (FilesystemProjectionError, TypeError, ValueError) as exc:
        raise AttributionError("native projection state is invalid") from exc
    raise AttributionError("native projection state has an unknown kind")


def _projection_transitions(
    raw: bytes, run_id: str, sequence: int, role: str
) -> tuple[PathTransition, ...]:
    value = _canonical_object(raw, "native producer projection")
    required = {
        "after_sha256",
        "before_sha256",
        "role_id",
        "run_id",
        "schema_version",
        "sequence",
        "transitions",
    }
    if (
        set(value) != required
        or value["run_id"] != run_id
        or value["role_id"] != role
        or type(value["sequence"]) is not int
        or value["sequence"] != sequence
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or not isinstance(value["transitions"], list)
    ):
        raise AttributionError("native producer projection has an invalid schema")
    _hex(value["before_sha256"], "native projection before hash")
    _hex(value["after_sha256"], "native projection after hash")
    transitions: list[PathTransition] = []
    for item in value["transitions"]:
        if not isinstance(item, dict) or set(item) != {"after", "before", "path"}:
            raise AttributionError("native producer projection transition is malformed")
        try:
            transitions.append(
                PathTransition.changed(
                    GitPath.from_base64(item["path"]),
                    _state(item["before"]),
                    _state(item["after"]),
                )
            )
        except (FilesystemProjectionError, TypeError) as exc:
            raise AttributionError(
                "native producer projection transition is invalid"
            ) from exc
    if [item.path.raw for item in transitions] != sorted(
        item.path.raw for item in transitions
    ):
        raise AttributionError(
            "native producer projection transitions are not canonical"
        )
    if len({item.path for item in transitions}) != len(transitions):
        raise AttributionError("native producer projection has duplicate paths")
    return tuple(transitions)


def _transition_state(state: FileState) -> dict[str, object]:
    if state.kind == "absent":
        return {"kind": "absent"}
    assert (
        state.mode is not None and state.size is not None and state.sha256 is not None
    )
    return {
        "kind": state.kind,
        "mode": format(state.mode, "06o"),
        "sha256": state.sha256,
        "size": state.size,
    }


def _retained_transition_values(
    transitions: tuple[PathTransition, ...],
) -> list[dict[str, object]]:
    if [item.path.raw for item in transitions] != sorted(
        item.path.raw for item in transitions
    ):
        raise AttributionError("strict capture transitions are not canonically sorted")
    if len({item.path for item in transitions}) != len(transitions):
        raise AttributionError("strict capture transitions have duplicate paths")
    values = [
        {
            "after": _transition_state(item.after),
            "before": _transition_state(item.before),
            "path": item.path.base64,
        }
        for item in transitions
    ]
    return values


def _retained_intersection(
    producer_transitions: tuple[PathTransition, ...],
    strict_transitions: tuple[PathTransition, ...],
) -> tuple[PathTransition, ...]:
    """Keep only producer effects that survive as strict capture transitions."""
    strict_by_path = {item.path: item for item in strict_transitions}
    retained = {
        item.path: item
        for item in producer_transitions
        if (strict := strict_by_path.get(item.path)) is not None
        and strict.after == item.after
    }
    return tuple(retained[path] for path in sorted(retained))


def capture_evidence(
    capture: DeliveryCapture, producer_transitions: tuple[PathTransition, ...]
) -> dict[str, object]:
    """The strict facts and surviving producer effects the ledger must bind."""
    if capture.projection is None:
        raise AttributionError("strict delivery capture has no typed projection")
    retained = _retained_intersection(producer_transitions, capture.transitions)
    if not retained:
        raise AttributionError(
            "NOT_RETAINED: no native crafter transition survives the strict capture"
        )
    transitions = _retained_transition_values(retained)
    return {
        "strict_projection_sha256": _sha256(projection_to_bytes(capture.projection)),
        "retained_transitions": transitions,
        "retained_transitions_sha256": _sha256(_canonical_json(transitions)),
    }


def capture_binding(attribution_path: Path) -> dict[str, object]:
    """Read the exact strict facts that ``delivery_captured`` must bind.

    Construction writes this immutable V2 record before its ledger event.  The
    runner deliberately reads these values back instead of rebuilding a second
    interpretation of the native records.
    """
    value = _canonical_object(attribution_path.read_bytes(), "V2 attribution")
    required = {
        "strict_projection_sha256",
        "retained_transitions",
        "retained_transitions_sha256",
    }
    if not required <= set(value):
        raise AttributionError("V2 attribution lacks strict capture binding")
    return {key: value[key] for key in sorted(required)}


_TURN_KEYS = {
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


def _turn_projection(
    raw: bytes, *, run_id: str, sequence: int, role: str, projection_raw: bytes | None
) -> tuple[dict[str, object], tuple[PathTransition, ...] | None]:
    """Validate the recorder's complete turn grammar and optional projection pair."""
    turn = _canonical_object(raw, "native turn")
    if set(turn) != _TURN_KEYS:
        raise AttributionError("native turn has an invalid schema")
    if (
        turn["run_id"] != run_id
        or type(turn["sequence"]) is not int
        or turn["sequence"] != sequence
        or turn["role_id"] != role
        or not isinstance(turn["prompt"], str)
        or not isinstance(turn["diagnostic"], str)
        or not isinstance(turn["outcome"], str)
        or type(turn["exit_status"]) is not int
        or type(turn["retry_safe"]) is not bool
        or not isinstance(turn["started_at"], str)
        or not isinstance(turn["ended_at"], str)
        or isinstance(turn["duration_seconds"], bool)
        or not isinstance(turn["duration_seconds"], (int, float))
        or not (
            turn["argv"] is None
            or (
                isinstance(turn["argv"], list)
                and all(isinstance(token, str) for token in turn["argv"])
            )
        )
        or not (
            turn["provider_stdout"] is None or isinstance(turn["provider_stdout"], str)
        )
        or not (
            turn["provider_stderr"] is None or isinstance(turn["provider_stderr"], str)
        )
        or not (turn["raised"] is None or isinstance(turn["raised"], str))
        or not isinstance(turn["producer_projection"], dict)
    ):
        raise AttributionError("native turn has invalid field types")
    reference = turn["producer_projection"]
    if reference == {"state": "not_applicable"}:
        if projection_raw is not None:
            raise AttributionError("non-producer turn has an orphan projection")
        return turn, None
    if reference.get("state") == "indeterminate":
        if (
            set(reference) != {"how", "state", "what", "why"}
            or not all(
                isinstance(reference[key], str) and reference[key]
                for key in ("how", "what", "why")
            )
            or projection_raw is not None
        ):
            raise AttributionError(
                "indeterminate native turn has an invalid projection"
            )
        return turn, None
    name = f"{sequence:02d}-{role}.projection"
    if (
        set(reference) != {"path", "sha256", "state", "transition_count"}
        or reference.get("state") != "captured"
        or reference.get("path") != name
        or type(reference.get("transition_count")) is not int
        or projection_raw is None
        or reference.get("sha256") != _sha256(projection_raw)
    ):
        raise AttributionError("native turn does not bind its projection")
    transitions = _projection_transitions(projection_raw, run_id, sequence, role)
    if reference["transition_count"] != len(transitions):
        raise AttributionError("native turn projection transition count differs")
    return turn, transitions


def _validated_native_turns(
    names: dict[str, dict[str, object]], specimen: Path, run_id: str
) -> dict[
    tuple[int, str],
    tuple[dict[str, object], bytes, bytes | None, tuple[PathTransition, ...] | None],
]:
    """Require the recorder's contiguous marker/turn/projection membership."""
    markers: set[int] = set()
    turns: dict[tuple[int, str], dict[str, object]] = {}
    projections: dict[tuple[int, str], dict[str, object]] = {}
    for name, item in names.items():
        if name in {"reservation", "policy"}:
            continue
        if _MARKER.fullmatch(name):
            sequence = int(name.removesuffix(".sequence"))
            marker = _evidence_path(
                specimen, str(item["specimen_path"]), "sequence marker"
            )
            if marker.read_bytes() != b"":
                raise AttributionError("native sequence marker is not empty")
            markers.add(sequence)
            continue
        matched = _SEQUENCE.fullmatch(name)
        if matched is None:
            raise AttributionError("reserved native run has a foreign artifact")
        key = (int(matched.group("sequence")), matched.group("role"))
        bucket = turns if matched.group("kind") == "json" else projections
        if key in bucket:
            raise AttributionError("native run has duplicate sequence members")
        bucket[key] = item
    sequences = {sequence for sequence, _ in turns} | {
        sequence for sequence, _ in projections
    }
    if (
        not sequences
        or markers != sequences
        or sequences != set(range(1, max(sequences) + 1))
    ):
        raise AttributionError(
            "native run has missing, extra, or non-contiguous sequence markers"
        )
    if set(projections) - set(turns):
        raise AttributionError("native run has an orphan projection")
    if len(turns) != len(sequences):
        raise AttributionError("native run has multiple turns for one sequence marker")
    validated: dict[
        tuple[int, str],
        tuple[
            dict[str, object], bytes, bytes | None, tuple[PathTransition, ...] | None
        ],
    ] = {}
    for key, item in turns.items():
        sequence, role = key
        turn_raw = _evidence_path(
            specimen, str(item["specimen_path"]), "native turn"
        ).read_bytes()
        projection_item = projections.get(key)
        projection_raw = (
            _evidence_path(
                specimen, str(projection_item["specimen_path"]), "native projection"
            ).read_bytes()
            if projection_item is not None
            else None
        )
        turn, transitions = _turn_projection(
            turn_raw,
            run_id=run_id,
            sequence=sequence,
            role=role,
            projection_raw=projection_raw,
        )
        validated[key] = (turn, turn_raw, projection_raw, transitions)
    return validated


def _copy_exclusive(source: Path, target: Path) -> str:
    return _copy_raw_exclusive(source.read_bytes(), target)


def _copy_raw_exclusive(raw: bytes, target: Path) -> str:
    digest = _sha256(raw)
    target.mkdir(parents=True, exist_ok=True)
    destination = target / digest
    try:
        _publish_no_replace(destination, raw)
    except FileExistsError:
        if destination.read_bytes() != raw:
            raise AttributionError("content-addressed native artifact differs")
    return digest


def _write_all(descriptor: int, raw: bytes) -> None:
    written = 0
    while written < len(raw):
        count = os.write(descriptor, raw[written:])
        if count <= 0:
            raise OSError("could not write complete attribution evidence")
        written += count


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
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
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _native_artifacts(
    workspace: Path, reservation: RecorderReservation, specimen: Path
) -> list[dict[str, object]]:
    expected = Path(workspace).absolute() / TURN_LOG_RELATIVE_DIR / reservation.run_id
    directory = Path(reservation.directory).absolute()
    if (
        directory != expected
        or directory.is_symlink()
        or directory.resolve(strict=False) != expected.resolve(strict=False)
        or not directory.is_dir()
    ):
        raise AttributionError("reserved native turn directory is unavailable")
    lock = directory / ".sequence.lock"
    try:
        lock_mode = lock.lstat().st_mode
    except FileNotFoundError as exc:
        raise AttributionError(
            "reserved native turn directory lacks sequence lock"
        ) from exc
    if lock.is_symlink() or not stat.S_ISREG(lock_mode):
        raise AttributionError("reserved native sequence lock is unsafe")
    expected_lock_bytes = b"0" if os.name == "nt" else b""
    if lock.read_bytes() != expected_lock_bytes:
        raise AttributionError(
            "reserved native sequence lock has invalid lifecycle bytes"
        )
    artifacts: list[dict[str, object]] = []
    for source in sorted(directory.iterdir()):
        if source.name == ".sequence.lock":
            continue
        if source.is_symlink() or not source.is_file():
            raise AttributionError(
                "reserved native turn directory has an unsafe member"
            )
        if (
            source.name not in {"reservation", "policy"}
            and not _MARKER.fullmatch(source.name)
            and not _SEQUENCE.fullmatch(source.name)
        ):
            raise AttributionError(
                "reserved native turn directory has a foreign member"
            )
        digest = _copy_exclusive(source, specimen / "native-artifacts")
        artifacts.append(
            {
                "source_name": source.name,
                "specimen_path": f"native-artifacts/{digest}",
                "sha256": digest,
            }
        )
    return artifacts


def construct_d0_attribution(
    *,
    workspace: Path,
    specimen: Path,
    reservation: RecorderReservation,
    capture: DeliveryCapture,
) -> Path:
    """Retain and bind one reserved native run to one strict delivery capture."""
    if capture.projection is None:
        raise AttributionError("strict delivery capture has no typed projection")
    artifacts = _native_artifacts(workspace, reservation, specimen)
    by_name = {item["source_name"]: item for item in artifacts}
    if set(by_name) < {"reservation", "policy"}:
        raise AttributionError("reserved native run lacks reservation or policy")
    reservation_raw = _evidence_path(
        specimen, str(by_name["reservation"]["specimen_path"]), "reservation"
    ).read_bytes()
    reservation_value = _canonical_object(reservation_raw, "native reservation")
    if (
        set(reservation_value)
        != {"high_water_mark", "policy_sha256", "run_id", "schema_version"}
        or reservation_value["run_id"] != reservation.run_id
        or reservation_value["high_water_mark"] != 0
        or reservation_value["policy_sha256"] != reservation.policy_sha256
        or reservation_value["schema_version"] != 1
        or _sha256(reservation_raw) != reservation.reservation_sha256
    ):
        raise AttributionError("native reservation does not bind the D0 run")
    policy = _evidence_path(specimen, str(by_name["policy"]["specimen_path"]), "policy")
    if _sha256_file(policy) != reservation.policy_sha256:
        raise AttributionError("native policy hash differs from the reservation")

    candidates: list[dict[str, object]] = []
    producer_transitions: list[PathTransition] = []
    native_turns = _validated_native_turns(by_name, specimen, reservation.run_id)
    for (sequence, role), (
        turn,
        _turn_raw,
        projection_raw,
        transitions,
    ) in native_turns.items():
        if not is_crafter_role(role):
            continue
        if (
            turn.get("run_id") != reservation.run_id
            or turn.get("sequence") != sequence
            or turn.get("role_id") != role
            or turn.get("outcome") != "accepted"
            or turn.get("exit_status") != 0
            or turn.get("raised") is not None
        ):
            continue
        if projection_raw is None or not transitions:
            continue
        producer_transitions.extend(transitions)
        candidates.append(
            {
                "role_id": role,
                "sequence": sequence,
                "turn_path": by_name[f"{sequence:02d}-{role}.json"]["specimen_path"],
                "turn_sha256": by_name[f"{sequence:02d}-{role}.json"]["sha256"],
                "projection_path": by_name[f"{sequence:02d}-{role}.projection"][
                    "specimen_path"
                ],
                "projection_sha256": by_name[f"{sequence:02d}-{role}.projection"][
                    "sha256"
                ],
                "transition_count": len(transitions),
            }
        )
    if not candidates:
        raise AttributionError(
            "NOT_RETAINED: no accepted exit-zero native crafter transition reaches the strict final projection"
        )
    captured_evidence = capture_evidence(capture, tuple(producer_transitions))
    packet = capture.target / "DELIVERY.patch"
    if not packet.is_file():
        raise AttributionError("strict delivery packet lacks DELIVERY.patch")
    path = specimen / ATTRIBUTION_V2_FILE_NAME
    if path.exists() or path.is_symlink():
        raise AttributionError("D0 attribution destination already exists")
    projection_raw = projection_to_bytes(capture.projection)
    projection_hash = _copy_raw_exclusive(
        projection_raw, specimen / "strict-projection"
    )
    value = {
        "schema": DELIVERY_ATTRIBUTION_V2_SCHEMA,
        "run_id": reservation.run_id,
        "reservation_sha256": reservation.reservation_sha256,
        "policy_sha256": reservation.policy_sha256,
        "native_artifacts": artifacts,
        "crafters": candidates,
        "packet_path": "delivery-packet/DELIVERY.patch",
        "packet_sha256": _sha256_file(packet),
        "strict_projection_path": f"strict-projection/{projection_hash}",
        "strict_projection_sha256": projection_hash,
        "strict_transitions": _retained_transition_values(capture.transitions),
        "strict_transitions_sha256": _sha256(
            _canonical_json(_retained_transition_values(capture.transitions))
        ),
        "retained_transitions": captured_evidence["retained_transitions"],
        "retained_transitions_sha256": captured_evidence["retained_transitions_sha256"],
        "capture_baseline": capture.baseline,
        "ledger_path": "../ledger",
    }
    _publish_no_replace(path, _canonical_json(value))
    return path


def _read_v2(path: Path, *, require_closed: bool) -> AttributionAssessment:
    specimen = path.parent.resolve()
    if specimen.name != "specimen" or path.name != ATTRIBUTION_V2_FILE_NAME:
        raise AttributionError("V2 attribution is outside the D0 specimen layout")
    value = _canonical_object(path.read_bytes(), "V2 attribution")
    required = {
        "schema",
        "run_id",
        "reservation_sha256",
        "policy_sha256",
        "native_artifacts",
        "crafters",
        "packet_path",
        "packet_sha256",
        "strict_projection_path",
        "strict_projection_sha256",
        "strict_transitions",
        "strict_transitions_sha256",
        "retained_transitions",
        "retained_transitions_sha256",
        "capture_baseline",
        "ledger_path",
    }
    if set(value) != required or value["schema"] != DELIVERY_ATTRIBUTION_V2_SCHEMA:
        raise AttributionError("V2 attribution has an unsupported shape")
    run_id = _require_text(value["run_id"], "V2 run_id")
    _hex(value["reservation_sha256"], "V2 reservation hash")
    _hex(value["policy_sha256"], "V2 policy hash")
    artifacts = value["native_artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise AttributionError("V2 native artifacts are missing")
    names: dict[str, dict[str, object]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {
            "source_name",
            "specimen_path",
            "sha256",
        }:
            raise AttributionError("V2 native artifact has an invalid shape")
        name = _require_text(item["source_name"], "native artifact name")
        evidence = _evidence_path(
            specimen,
            _require_text(item["specimen_path"], "native artifact path"),
            "native artifact",
        )
        digest = _hex(item["sha256"], "native artifact hash")
        if evidence.name != digest or _sha256_file(evidence) != digest or name in names:
            raise AttributionError("V2 native artifact bytes do not join")
        names[name] = item
    reservation = names.get("reservation")
    policy = names.get("policy")
    if reservation is None or policy is None:
        raise AttributionError("V2 native reservation or policy is missing")
    reservation_raw = _evidence_path(
        specimen, str(reservation["specimen_path"]), "reservation"
    ).read_bytes()
    record = _canonical_object(reservation_raw, "V2 native reservation")
    if (
        set(record) != {"high_water_mark", "policy_sha256", "run_id", "schema_version"}
        or record.get("run_id") != run_id
        or record.get("high_water_mark") != 0
        or record.get("policy_sha256") != value["policy_sha256"]
        or _sha256(reservation_raw) != value["reservation_sha256"]
        or _sha256_file(
            _evidence_path(specimen, str(policy["specimen_path"]), "policy")
        )
        != value["policy_sha256"]
    ):
        raise AttributionError("V2 reservation/policy binding differs")
    packet = _evidence_path(
        specimen, _require_text(value["packet_path"], "packet path"), "packet"
    )
    if packet.name != "DELIVERY.patch" or _sha256_file(packet) != _hex(
        value["packet_sha256"], "packet hash"
    ):
        raise AttributionError("V2 strict packet differs")
    strict_projection_path = _evidence_path(
        specimen,
        _require_text(value["strict_projection_path"], "strict projection path"),
        "strict projection",
    )
    strict_projection_raw = strict_projection_path.read_bytes()
    strict_projection_hash = _hex(
        value["strict_projection_sha256"], "strict projection hash"
    )
    if (
        strict_projection_path.name != strict_projection_hash
        or _sha256(strict_projection_raw) != strict_projection_hash
    ):
        raise AttributionError("V2 strict projection bytes differ")
    try:
        strict_projection = projection_from_bytes(strict_projection_raw)
    except FilesystemProjectionError as exc:
        raise AttributionError("V2 strict projection is malformed") from exc

    def transition_values(raw: object, subject: str) -> tuple[PathTransition, ...]:
        if not isinstance(raw, list):
            raise AttributionError(f"V2 {subject} transitions are missing")
        if any(
            not isinstance(item, dict) or set(item) != {"after", "before", "path"}
            for item in raw
        ):
            raise AttributionError(f"V2 {subject} transition is malformed")
        try:
            transitions = tuple(
                PathTransition.changed(
                    GitPath.from_base64(item["path"]),
                    _state(item["before"]),
                    _state(item["after"]),
                )
                for item in raw
            )
        except (FilesystemProjectionError, KeyError, TypeError) as exc:
            raise AttributionError(f"V2 {subject} transition is malformed") from exc
        canonical = _retained_transition_values(transitions)
        if raw != canonical:
            raise AttributionError(f"V2 {subject} transitions are not canonical")
        return transitions

    strict_transitions = transition_values(value["strict_transitions"], "strict")
    strict_values = _retained_transition_values(strict_transitions)
    strict_hash = _hex(value["strict_transitions_sha256"], "V2 strict transition hash")
    if strict_hash != _sha256(_canonical_json(strict_values)):
        raise AttributionError("V2 strict transition hash differs")
    if any(
        strict_projection.state_at(item.path) != item.after
        for item in strict_transitions
    ):
        raise AttributionError("V2 strict transition differs from final projection")

    retained = value["retained_transitions"]
    retained_transitions = transition_values(retained, "retained")
    recomputed_retained = _retained_transition_values(retained_transitions)
    retained_hash = _hex(
        value["retained_transitions_sha256"], "V2 retained transition hash"
    )
    if retained_hash != _sha256(_canonical_json(recomputed_retained)):
        raise AttributionError("V2 retained transitions are not canonical")
    crafters = value["crafters"]
    if not isinstance(crafters, list) or not crafters:
        return AttributionAssessment(NOT_RETAINED, "no retained accepted crafter")
    native_turns = _validated_native_turns(names, specimen, run_id)
    roles: list[str] = []
    producer_transitions: list[PathTransition] = []
    for candidate in crafters:
        if not isinstance(candidate, dict) or set(candidate) != {
            "role_id",
            "sequence",
            "turn_path",
            "turn_sha256",
            "projection_path",
            "projection_sha256",
            "transition_count",
        }:
            raise AttributionError("V2 crafter binding has an invalid shape")
        role, sequence = candidate["role_id"], candidate["sequence"]
        if (
            not isinstance(role, str)
            or not is_crafter_role(role)
            or type(sequence) is not int
            or sequence < 1
        ):
            raise AttributionError("V2 crafter identity is invalid")
        member = native_turns.get((sequence, role))
        turn_item = names.get(f"{sequence:02d}-{role}.json")
        projection_item = names.get(f"{sequence:02d}-{role}.projection")
        if (
            member is None
            or turn_item is None
            or projection_item is None
            or candidate["turn_path"] != turn_item["specimen_path"]
            or candidate["projection_path"] != projection_item["specimen_path"]
            or candidate["turn_sha256"] != turn_item["sha256"]
            or candidate["projection_sha256"] != projection_item["sha256"]
        ):
            raise AttributionError("V2 crafter does not name its native record pair")
        turn, turn_raw, projection_raw, transitions = member
        if projection_raw is None or transitions is None:
            raise AttributionError("V2 crafter lacks a captured native projection")
        if _sha256(turn_raw) != _hex(candidate["turn_sha256"], "turn hash") or _sha256(
            projection_raw
        ) != _hex(candidate["projection_sha256"], "projection hash"):
            raise AttributionError("V2 crafter artifact hash differs")
        if (
            (
                turn.get("run_id"),
                turn.get("sequence"),
                turn.get("role_id"),
                turn.get("outcome"),
                turn.get("exit_status"),
                turn.get("raised"),
            )
            != (run_id, sequence, role, "accepted", 0, None)
            or candidate["transition_count"] != len(transitions)
            or not transitions
        ):
            raise AttributionError(
                "V2 crafter is not accepted exit-zero with transitions"
            )
        producer_transitions.extend(transitions)
        roles.append(role)
    expected_retained = _retained_intersection(
        tuple(producer_transitions), strict_transitions
    )
    if not expected_retained:
        raise AttributionError(
            "NOT_RETAINED: no native crafter transition survives the strict capture"
        )
    expected_retained_values = _retained_transition_values(expected_retained)
    if recomputed_retained != expected_retained_values:
        raise AttributionError(
            "V2 retained transitions differ from the native/strict intersection"
        )
    ledger_relative = value["ledger_path"]
    if (
        ledger_relative != "../ledger"
        or (specimen.parent / "ledger").resolve()
        != specimen.parent.resolve() / "ledger"
    ):
        raise AttributionError("V2 ledger path is not the D0 sibling ledger")
    ledger = specimen.parent / "ledger"
    records = intervention_ledger.read_closed_records(
        ledger, require_closed=require_closed
    )
    started = next(
        (event for event in records if event.get("kind") == "delivery_started"), None
    )
    captured = next(
        (event for event in records if event.get("kind") == "delivery_captured"), None
    )
    if started is None or captured is None:
        raise AttributionError("D0 ledger lacks delivery_started or delivery_captured")
    started_payload = started.get("payload")
    if (
        not isinstance(started_payload, dict)
        or any(
            started_payload.get(key) != value[key]
            for key in ("run_id", "reservation_sha256", "policy_sha256")
        )
        or started_payload.get("high_water_mark") != 0
    ):
        raise AttributionError("D0 delivery_started does not bind the reservation")
    captured_payload = captured.get("payload")
    if not isinstance(captured_payload, dict):
        raise AttributionError("D0 delivery_captured is malformed")
    attribution_hashes = captured_payload.get("attribution_hashes")
    if not isinstance(attribution_hashes, dict) or attribution_hashes.get(
        ATTRIBUTION_V2_FILE_NAME
    ) != _sha256_file(path):
        raise AttributionError("D0 delivery_captured does not bind V2 attribution")
    if captured_payload.get("packet_hashes") != {
        "DELIVERY.patch": _sha256_file(packet),
        "DELIVERY-CHANGES.txt": _sha256_file(
            specimen / "delivery-packet" / "DELIVERY-CHANGES.txt"
        ),
    }:
        raise AttributionError("D0 delivery_captured does not bind the exact packet")
    if captured_payload.get("request_hashes") != _tree_hashes(specimen / "request"):
        raise AttributionError("D0 delivery_captured does not bind request bytes")
    if captured_payload.get("transcript_hashes") != _tree_hashes(
        specimen / "transcripts"
    ):
        raise AttributionError("D0 delivery_captured does not bind transcript bytes")
    if captured_payload.get("native_artifact_hashes") != _tree_hashes(
        specimen / "native-artifacts"
    ):
        raise AttributionError("D0 delivery_captured does not bind native artifacts")
    if (
        captured_payload.get("strict_projection_sha256")
        != value["strict_projection_sha256"]
        or captured_payload.get("retained_transitions") != expected_retained_values
        or captured_payload.get("retained_transitions_sha256") != retained_hash
    ):
        raise AttributionError(
            "D0 delivery_captured does not bind strict capture values"
        )
    capture_record = captured_payload.get("capture")
    if (
        not isinstance(capture_record, dict)
        or capture_record.get("baseline") != value["capture_baseline"]
        or started_payload.get("baseline") != value["capture_baseline"]
        or captured_payload.get("delivery_ok") is not True
    ):
        raise AttributionError(
            "D0 capture does not bind a successful declared baseline"
        )
    if (
        require_closed
        and intervention_ledger.verify(ledger).classification != "DIAGNOSTIC"
    ):
        raise AttributionError("D0 ledger is not closed DIAGNOSTIC")
    return AttributionAssessment(
        ATTRIBUTED,
        "native accepted crafter transition joins the strict D0 delivery",
        roles[0],
    )


def assess(path: Path, *, require_closed: bool = True) -> AttributionAssessment:
    """Return ATTRIBUTED only for the closed, native D0 V2 chain; V1 fails closed."""
    try:
        if path.name == ATTRIBUTION_V2_FILE_NAME:
            return _read_v2(path, require_closed=require_closed)
        _read_attribution(path)
        raise AttributionError(_NATIVE_ATTRIBUTION_BLOCKER)
    except (AttributionError, OSError, UnicodeDecodeError, ValueError) as exc:
        return AttributionAssessment(INDETERMINATE, str(exc))
