# @feature-certified-capture
# @slice-02
# @real-io @adapter-integration @driving_port @contract-shape:bounded-change
"""Public-port acceptance contract for retained local evidence."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from types import ModuleType
from typing import Any, cast
from uuid import UUID

import pytest
from nwave_ai.state_delta import assert_state_delta, set_to


pytestmark = pytest.mark.acceptance

_PRIMARY_HEADER = re.compile(rb"[0-9A-F]{8}")
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}")
_HEALTH_KEYS = {
    "kind",
    "manifest_digest",
    "partition_id",
    "payload",
    "run_id",
    "schema",
    "writer_id",
}


def _assert_contract(
    condition: bool,
    *,
    invariant: str,
    observed: object,
    expected: object,
    repair: str,
) -> None:
    assert condition, (
        f"WHAT: {invariant}; expected {expected!r}, observed {observed!r}. "
        "WHY: retained bytes and public actions are the certified-capture evidence "
        "boundary, so divergence can falsely certify or reject a local bundle. "
        f"HOW: DELIVER must {repair}."
    )


def _assert_exact_contract(
    actual: object,
    expected: object,
    *,
    invariant: str,
    repair: str,
) -> None:
    _assert_contract(
        actual == expected,
        invariant=invariant,
        observed=actual,
        expected=expected,
        repair=repair,
    )


def _capture_public_port() -> ModuleType:
    capture = importlib.import_module("nwave_capture")
    required = (
        "AtomicHealthReceiptStore",
        "CaptureStorageError",
        "CaptureVerifier",
        "EvidenceRecord",
        "ExpectedPartition",
        "ExpectedPopulation",
        "FramedPartitionStore",
        "HealthReceiptUnavailableError",
        "LocalEvidenceIncomplete",
        "LocalEvidenceIndeterminate",
        "LocalEvidenceVerified",
        "PartitionStateError",
        "PartitionTerminal",
        "PartitionWriterConflictError",
        "ReceiptConflictError",
        "TerminalReason",
    )
    missing = tuple(name for name in required if not hasattr(capture, name))
    assert not missing, (
        "WHAT: the public capture boundary is incomplete. WHY: a release operator "
        "cannot retain or verify local evidence through an internal module. HOW: export "
        f"the ratified slice-02 public names at nwave_capture root; missing {missing}."
    )
    return capture


def _manifest(capture: ModuleType, root: Path):
    digest = "a" * 64
    run_id = UUID("12345678-1234-5678-1234-567812345678")
    now = datetime(2026, 8, 5, tzinfo=UTC)
    study = capture.StudyRef("study-1", digest, "current-des")
    run = capture.RunRef(run_id, 1, study)
    partition = capture.PartitionRef("root", run_id, "harness-1", "harness")
    return capture.RunManifest(
        "v1",
        run,
        digest,
        ("tokens",),
        (
            capture.UsageObservationSemantics(
                "provider",
                "v1",
                capture.UsageObservationMode.CUMULATIVE_SNAPSHOT,
                "max-v1",
            ),
        ),
        partition,
        now,
        now + timedelta(minutes=1),
        now + timedelta(minutes=6),
        root,
        digest,
        digest,
        digest,
        digest,
        "writer-v1",
        "metadata-only",
        now + timedelta(days=30),
        capture.RepositoryRef(digest, digest, "f" * 40),
        ("provider:v1",),
        digest,
    )


def _expected_partitions(capture: ModuleType, manifest, count: int) -> tuple:
    if count == 0:
        return ()
    declared_at = manifest.interval_start
    expected = [
        capture.ExpectedPartition(manifest.root_partition, "writer-root", declared_at)
    ]
    for index in range(1, count):
        child = capture.PartitionRef(
            f"child-{index}",
            manifest.run.run_id,
            f"worker-{index}",
            "worker",
            manifest.root_partition.partition_id,
        )
        expected.append(
            capture.ExpectedPartition(child, f"writer-child-{index}", declared_at)
        )
    return tuple(expected)


def _population(capture: ModuleType, manifest, expected: tuple):
    return capture.ExpectedPopulation(
        manifest.run.run_id, manifest.manifest_digest, expected
    )


def _public_boundaries(capture: ModuleType, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(capture, root)
    health = capture.AtomicHealthReceiptStore(root, manifest)
    verifier = capture.CaptureVerifier(root, manifest)
    health.probe()
    verifier.probe()
    return health, verifier, manifest


def _writer(capture: ModuleType, root: Path, manifest, expected):
    primary = capture.FramedPartitionStore(root, manifest, expected)
    primary.probe()
    return primary


def _attempt_synchronized_open(
    root: Path,
    manifest: object,
    expected: object,
    acquisition_barrier: Any,
    outcomes: Any,
) -> None:
    capture = _capture_public_port()
    primary = _writer(capture, root, manifest, expected)
    acquisition_barrier.wait(timeout=10)
    try:
        primary.open()
    except capture.PartitionStateError as error:
        outcomes.put(("conflict", type(error).__name__))
    except Exception as error:
        outcomes.put(("unexpected", type(error).__name__))
    else:
        outcomes.put(("owner", ""))


def _close_partition(
    capture: ModuleType,
    root: Path,
    manifest,
    expected,
    records: tuple[str, ...],
    reason: str,
):
    primary = _writer(capture, root, manifest, expected)
    primary.open()
    for sequence, payload_json in enumerate(records, start=1):
        primary.append(capture.EvidenceRecord(sequence, "usage", payload_json))
    return primary.close(getattr(capture.TerminalReason, reason))


def _receipt_map(health, expected) -> dict[str, bytes]:
    return {json.loads(receipt)["kind"]: receipt for receipt in health.read(expected)}


def _primary_file(root: Path, terminal_receipt: bytes) -> Path:
    primary_digest = json.loads(terminal_receipt)["payload"]["primary_digest"]
    return next(
        path
        for path in (root / "primary").rglob("*.jsonl")
        if hashlib.sha256(path.read_bytes()).hexdigest() == primary_digest
    )


def _canonical_json_value(retained: bytes, *, permits_trailing_newline: bool) -> object:
    if permits_trailing_newline:
        payload = retained[:-1]
        _assert_contract(
            retained.endswith(b"\n") and not payload.endswith(b"\n"),
            invariant="a primary frame does not end in exactly one newline",
            observed=retained[-2:],
            expected=b"<payload>\\n with no second newline",
            repair="emit one newline after each exact-length primary envelope",
        )
    else:
        payload = retained
        _assert_contract(
            not retained.endswith(b"\n"),
            invariant="a health receipt has a trailing newline",
            observed=retained[-1:],
            expected=b"canonical JSON final byte, not newline",
            repair="atomically retain canonical health JSON without a trailing newline",
        )
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssertionError(
            "WHAT: retained evidence is not a UTF-8 JSON value. "
            "WHY: certified-capture consumers derive schema and digests from canonical "
            "retained JSON bytes. HOW: DELIVER must serialize the ratified value as "
            f"canonical UTF-8 JSON; decoder said {error}."
        ) from error
    canonical = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _assert_exact_contract(
        payload,
        canonical,
        invariant="retained JSON bytes are not the canonical serialization",
        repair="serialize with ensure_ascii, sorted keys, finite values, and compact separators",
    )
    return value


def _assert_primary_frames(
    retained: bytes,
    expected_records: tuple[tuple[int, str, dict[str, object]], ...] | None = None,
) -> tuple[dict[str, object], ...]:
    _assert_contract(
        bool(retained) and retained.endswith(b"\n"),
        invariant="the retained primary stream is empty or lacks its frame newline",
        observed=retained[-1:] if retained else b"",
        expected=b"non-empty framed bytes ending in newline",
        repair="retain at least one complete primary frame ending in one newline",
    )
    offset = 0
    envelopes: list[dict[str, object]] = []
    while offset < len(retained):
        header = retained[offset : offset + 8]
        _assert_contract(
            _PRIMARY_HEADER.fullmatch(header) is not None,
            invariant="a primary frame header is not eight uppercase hexadecimal bytes",
            observed=header,
            expected=b"00000000 through FFFFFFFF",
            repair="prefix every envelope with its eight-digit uppercase hexadecimal byte length",
        )
        _assert_exact_contract(
            retained[offset + 8 : offset + 9],
            b":",
            invariant="a primary frame omits the colon after its length header",
            repair="place one colon between the eight-byte header and envelope",
        )
        payload_length = int(header, 16)
        payload_start = offset + 9
        payload_end = payload_start + payload_length
        payload = retained[payload_start:payload_end]
        _assert_exact_contract(
            len(payload),
            payload_length,
            invariant="the primary header length does not match its UTF-8 envelope bytes",
            repair="compute the header from the complete canonical envelope byte length",
        )
        _assert_exact_contract(
            retained[payload_end : payload_end + 1],
            b"\n",
            invariant="a primary frame lacks the newline at its declared payload boundary",
            repair="write one newline immediately after the exact-length envelope",
        )
        envelope = _canonical_json_value(payload + b"\n", permits_trailing_newline=True)
        _assert_contract(
            isinstance(envelope, dict),
            invariant="a primary envelope is not a JSON object",
            observed=type(envelope).__name__,
            expected="dict",
            repair="emit the ratified primary envelope object",
        )
        envelope = cast("dict[str, object]", envelope)
        _assert_exact_contract(
            set(envelope),
            {"kind", "payload", "schema", "sequence"},
            invariant="a primary envelope has missing or additional keys",
            repair="emit exactly kind, payload, schema, and sequence",
        )
        _assert_exact_contract(
            envelope["schema"],
            "nwave_capture.primary.v1",
            invariant="a primary envelope uses an unratified schema",
            repair="emit schema nwave_capture.primary.v1",
        )
        _assert_contract(
            isinstance(envelope["kind"], str)
            and envelope["kind"]
            and envelope["kind"].strip() == envelope["kind"],
            invariant="a primary record kind is not a trimmed non-empty string",
            observed=envelope["kind"],
            expected="trimmed non-empty str",
            repair="validate and retain the EvidenceRecord kind unchanged",
        )
        _assert_contract(
            isinstance(envelope["payload"], dict),
            invariant="a primary payload is not a JSON object",
            observed=type(envelope["payload"]).__name__,
            expected="dict",
            repair="retain the parsed canonical EvidenceRecord payload object",
        )
        _assert_contract(
            isinstance(envelope["sequence"], int)
            and not isinstance(envelope["sequence"], bool),
            invariant="a primary sequence is not an integer",
            observed=envelope["sequence"],
            expected="int but not bool",
            repair="retain the validated integer EvidenceRecord sequence",
        )
        _assert_contract(
            envelope["sequence"] > 0,
            invariant="a primary sequence is not positive",
            observed=envelope["sequence"],
            expected="integer greater than zero",
            repair="reject non-positive sequences before primary mutation",
        )
        envelopes.append(envelope)
        offset = payload_end + 1
    _assert_exact_contract(
        offset,
        len(retained),
        invariant="bytes remain after the final complete primary frame",
        repair="retain only a concatenation of complete length-delimited frames",
    )
    if expected_records is not None:
        actual_records = tuple(
            (envelope["sequence"], envelope["kind"], envelope["payload"])
            for envelope in envelopes
        )
        _assert_exact_contract(
            actual_records,
            expected_records,
            invariant="retained primary records differ from the public records appended",
            repair="frame each validated EvidenceRecord exactly once and in sequence order",
        )
    return tuple(envelopes)


def _assert_health_receipt(
    capture: ModuleType,
    retained: bytes,
    *,
    manifest,
    expected,
    receipt_kind: str,
) -> dict[str, object]:
    envelope = _canonical_json_value(retained, permits_trailing_newline=False)
    _assert_contract(
        isinstance(envelope, dict),
        invariant="a health receipt is not a JSON object",
        observed=type(envelope).__name__,
        expected="dict",
        repair="emit the ratified health receipt envelope object",
    )
    envelope = cast("dict[str, object]", envelope)
    _assert_exact_contract(
        set(envelope),
        _HEALTH_KEYS,
        invariant="a health receipt has missing or additional envelope keys",
        repair="emit exactly kind, manifest_digest, partition_id, payload, run_id, schema, and writer_id",
    )
    non_payload_types = {
        name: type(envelope[name]).__name__ for name in _HEALTH_KEYS - {"payload"}
    }
    _assert_contract(
        all(name == "str" for name in non_payload_types.values()),
        invariant="a non-payload health field is not a JSON string",
        observed=non_payload_types,
        expected="str for every non-payload field",
        repair="serialize every non-payload health field as its canonical string",
    )
    _assert_exact_contract(
        envelope["kind"],
        receipt_kind,
        invariant="a retained health receipt kind differs from its observation slot",
        repair="publish the expected, started, terminal, or failure kind consistently",
    )
    _assert_exact_contract(
        envelope["schema"],
        "nwave_capture.health.v1",
        invariant="a health receipt uses an unratified schema",
        repair="emit schema nwave_capture.health.v1",
    )
    _assert_exact_contract(
        envelope["manifest_digest"],
        manifest.manifest_digest,
        invariant="a health receipt does not bind the active manifest",
        repair="copy the manifest digest from the probed RunManifest",
    )
    _assert_contract(
        isinstance(envelope["manifest_digest"], str)
        and _LOWER_SHA256.fullmatch(envelope["manifest_digest"]) is not None,
        invariant="a health manifest digest is not lowercase SHA-256",
        observed=envelope["manifest_digest"],
        expected="64 lowercase hexadecimal characters",
        repair="validate and retain the canonical lowercase manifest digest",
    )
    _assert_exact_contract(
        envelope["partition_id"],
        expected.partition.partition_id,
        invariant="a health receipt names the wrong partition",
        repair="bind the receipt to the declared ExpectedPartition",
    )
    _assert_exact_contract(
        envelope["run_id"],
        str(manifest.run.run_id),
        invariant="a health receipt names the wrong run",
        repair="bind the receipt to the manifest run UUID",
    )
    try:
        canonical_run_id = str(UUID(cast("str", envelope["run_id"])))
    except (TypeError, ValueError, AttributeError) as error:
        raise AssertionError(
            "WHAT: a health run_id is not canonical UUID text. WHY: receipts join to "
            "the declared certified-capture run by this value. HOW: DELIVER must emit "
            f"the lowercase canonical UUID string; parser said {error}."
        ) from error
    _assert_exact_contract(
        envelope["run_id"],
        canonical_run_id,
        invariant="a health run_id is not canonical lowercase UUID text",
        repair="serialize the run UUID with its canonical lowercase string form",
    )
    _assert_exact_contract(
        envelope["writer_id"],
        expected.writer_id,
        invariant="a health receipt names the wrong declared writer",
        repair="bind the receipt to the immutable ExpectedPartition writer",
    )
    payload = envelope["payload"]
    _assert_contract(
        isinstance(payload, dict),
        invariant="a health payload is not a JSON object",
        observed=type(payload).__name__,
        expected="dict",
        repair="emit the exact per-kind payload object",
    )
    payload = cast("dict[str, object]", payload)
    if receipt_kind == "expected":
        _assert_exact_contract(
            set(payload),
            {"declared_at"},
            invariant="an expected receipt payload has the wrong keys",
            repair="emit only declared_at for expected evidence",
        )
        _assert_exact_contract(
            payload["declared_at"],
            expected.declared_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            invariant="an expected receipt has a non-canonical declaration time",
            repair="serialize declared_at as fixed-microsecond UTC text ending in Z",
        )
    elif receipt_kind == "started":
        _assert_exact_contract(
            payload,
            {},
            invariant="a started receipt payload is not empty",
            repair="emit the ratified empty started payload",
        )
    elif receipt_kind == "terminal":
        _assert_exact_contract(
            set(payload),
            {
                "first_sequence",
                "last_sequence",
                "primary_digest",
                "reason",
                "record_count",
            },
            invariant="a terminal receipt payload has missing or additional keys",
            repair="emit exactly digest, count, bounds, and terminal reason",
        )
        _assert_contract(
            isinstance(payload["primary_digest"], str)
            and _LOWER_SHA256.fullmatch(payload["primary_digest"]) is not None,
            invariant="a terminal primary digest is not lowercase SHA-256",
            observed=payload["primary_digest"],
            expected="64 lowercase hexadecimal characters",
            repair="digest the complete retained primary bytes with SHA-256",
        )
        _assert_contract(
            isinstance(payload["record_count"], int)
            and not isinstance(payload["record_count"], bool),
            invariant="a terminal record_count is not an integer",
            observed=payload["record_count"],
            expected="int but not bool",
            repair="retain the exact integer primary record count",
        )
        _assert_contract(
            cast("int", payload["record_count"]) >= 0,
            invariant="a terminal record_count is negative",
            observed=payload["record_count"],
            expected="integer greater than or equal to zero",
            repair="reject negative counts before terminal publication",
        )
        for name in ("first_sequence", "last_sequence"):
            _assert_contract(
                payload[name] is None
                or (
                    isinstance(payload[name], int)
                    and not isinstance(payload[name], bool)
                ),
                invariant=f"terminal {name} is neither null nor an integer",
                observed=payload[name],
                expected="None or int but not bool",
                repair="retain canonical nullable integer sequence bounds",
            )
        allowed_reasons = {reason.value for reason in capture.TerminalReason}
        _assert_contract(
            payload["reason"] in allowed_reasons,
            invariant="a terminal receipt uses an unratified reason",
            observed=payload["reason"],
            expected=allowed_reasons,
            repair="emit only a TerminalReason value",
        )
    elif receipt_kind == "failure":
        _assert_exact_contract(
            set(payload),
            {"code"},
            invariant="a failure receipt payload has the wrong keys",
            repair="emit only the failure code",
        )
        _assert_contract(
            isinstance(payload["code"], str)
            and bool(payload["code"])
            and cast("str", payload["code"]).strip() == payload["code"],
            invariant="a failure code is not a trimmed non-empty string",
            observed=payload["code"],
            expected="trimmed non-empty str",
            repair="validate the failure code before retaining it",
        )
    else:
        raise AssertionError(f"unratified health receipt kind: {receipt_kind}")
    return envelope


def _derive_bundle_digest(
    capture: ModuleType,
    root: Path,
    manifest,
    health,
    expected: tuple,
) -> str:
    partitions = []
    for item in sorted(expected, key=lambda value: value.partition.partition_id):
        receipts = _receipt_map(health, item)
        _assert_exact_contract(
            set(receipts),
            {"expected", "started", "terminal"},
            invariant="a verified partition lacks the exact digest-bearing receipt set",
            repair="retain expected and started, then terminal only through close",
        )
        for receipt_kind in ("expected", "started", "terminal"):
            _assert_health_receipt(
                capture,
                receipts[receipt_kind],
                manifest=manifest,
                expected=item,
                receipt_kind=receipt_kind,
            )
        primary = _primary_file(root, receipts["terminal"])
        _assert_primary_frames(primary.read_bytes())
        partitions.append(
            {
                "expected_receipt_digest": hashlib.sha256(
                    receipts["expected"]
                ).hexdigest(),
                "partition_id": item.partition.partition_id,
                "primary_digest": hashlib.sha256(primary.read_bytes()).hexdigest(),
                "started_receipt_digest": hashlib.sha256(
                    receipts["started"]
                ).hexdigest(),
                "terminal_receipt_digest": hashlib.sha256(
                    receipts["terminal"]
                ).hexdigest(),
                "writer_id": item.writer_id,
            }
        )
    descriptor = {
        "manifest_digest": manifest.manifest_digest,
        "partitions": partitions,
        "run_id": str(manifest.run.run_id),
        "schema": "nwave_capture.bundle.v1",
    }
    canonical = json.dumps(
        descriptor,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"nwave-capture:bundle:v1\x00" + canonical).hexdigest()


def _bundle_state(health, expected, result: object | None = None) -> dict[str, object]:
    return {
        "health.receipt-kinds": tuple(
            json.loads(receipt)["kind"] for receipt in health.read(expected)
        ),
        "verifier.local-result": type(result).__name__ if result is not None else None,
    }


def test_release_operator_sees_only_ratified_actions_and_close_retains_terminal(
    tmp_path: Path,
) -> None:
    # covers: R10
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "public-actions"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    primary = _writer(capture, root, manifest, expected)
    boundaries = {
        "observer": health,
        "writer": primary,
        "verifier": verifier,
    }
    actual_methods = {
        name: {
            method
            for method in dir(boundary)
            if not method.startswith("_") and callable(getattr(boundary, method))
        }
        for name, boundary in boundaries.items()
    }
    forbidden_aliases = {
        "declare",
        "start",
        "latch_failure",
        "publish_terminal",
    }

    _assert_exact_contract(
        actual_methods,
        {
            "observer": {"probe", "read"},
            "writer": {"probe", "open", "append", "close", "abort"},
            "verifier": {"probe", "verify"},
        },
        invariant="the observer, writer, or verifier public action set diverges",
        repair="expose only the exact role methods ratified by CC-S02-1",
    )
    exposed_aliases = {
        name: tuple(
            sorted(alias for alias in forbidden_aliases if hasattr(boundary, alias))
        )
        for name, boundary in boundaries.items()
    }
    _assert_exact_contract(
        exposed_aliases,
        {"observer": (), "writer": (), "verifier": ()},
        invariant="a public boundary exposes a forbidden lifecycle alias",
        repair="remove declare/start/latch_failure/publish_terminal from public boundaries",
    )

    primary.open()
    primary.append(capture.EvidenceRecord(1, "usage", '{"tokens":1}'))
    _assert_exact_contract(
        tuple(_receipt_map(health, expected)),
        ("expected", "started"),
        invariant="terminal evidence exists before writer.close",
        repair="keep terminal publication private until close succeeds",
    )
    primary.close(capture.TerminalReason.CAPTURED)
    _assert_exact_contract(
        tuple(_receipt_map(health, expected)),
        ("expected", "started", "terminal"),
        invariant="writer.close does not produce the sole terminal observation",
        repair="publish exactly one terminal receipt from close after expected/started",
    )


def test_retained_bundle_bytes_match_ratified_primary_and_health_forms(
    tmp_path: Path,
) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "canonical-bundle"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    _close_partition(
        capture,
        root,
        manifest,
        expected,
        ('{"tokens":1}',),
        "CAPTURED",
    )
    receipts = _receipt_map(health, expected)
    _assert_exact_contract(
        tuple(receipts),
        ("expected", "started", "terminal"),
        invariant="the successful retained journey has the wrong health history",
        repair="retain expected, started, and terminal in canonical observation order",
    )
    for receipt_kind in ("expected", "started", "terminal"):
        _assert_health_receipt(
            capture,
            receipts[receipt_kind],
            manifest=manifest,
            expected=expected,
            receipt_kind=receipt_kind,
        )
    primary = _primary_file(root, receipts["terminal"])
    _assert_primary_frames(
        primary.read_bytes(),
        expected_records=((1, "usage", {"tokens": 1}),),
    )

    failure_root = tmp_path / "canonical-failure"
    failure_health, _failure_verifier, failure_manifest = _public_boundaries(
        capture, failure_root
    )
    failure_expected = _expected_partitions(capture, failure_manifest, 1)[0]
    failure_primary = _writer(capture, failure_root, failure_manifest, failure_expected)
    failure_primary.abort("operator-refused")
    failure_receipts = _receipt_map(failure_health, failure_expected)
    _assert_exact_contract(
        tuple(failure_receipts),
        ("expected", "failure"),
        invariant="the refused retained journey has the wrong health history",
        repair="retain expected followed by exactly one canonical failure receipt",
    )
    for receipt_kind in ("expected", "failure"):
        _assert_health_receipt(
            capture,
            failure_receipts[receipt_kind],
            manifest=failure_manifest,
            expected=failure_expected,
            receipt_kind=receipt_kind,
        )

    result = verifier.verify(population)
    independently_derived = _derive_bundle_digest(
        capture, root, manifest, health, (expected,)
    )
    _assert_contract(
        isinstance(result, capture.LocalEvidenceVerified),
        invariant="canonical retained bytes do not produce LocalEvidenceVerified",
        observed=type(result).__name__,
        expected="LocalEvidenceVerified",
        repair="verify only after every retained primary and health byte passes CC-S02-3",
    )
    _assert_exact_contract(
        getattr(result, "bundle_digest", None),
        independently_derived,
        invariant="the verifier digest differs from the independent retained-byte digest",
        repair="derive the bundle digest from the exact validated retained bytes",
    )


@pytest.mark.parametrize(
    ("records", "reason", "expected_first", "expected_last", "expected_result"),
    (
        ((), "NO_ELIGIBLE_EVENT", None, None, "LocalEvidenceVerified"),
        ((), "REFUSED_BEFORE_WORK", None, None, "LocalEvidenceIncomplete"),
        (('{"tokens":1}',), "CAPTURED", 1, 1, "LocalEvidenceVerified"),
        (
            ('{"tokens":1}', '{"tokens":2}'),
            "CAPTURED",
            1,
            2,
            "LocalEvidenceVerified",
        ),
    ),
    ids=("verified-zero", "refused-zero", "one-record", "many-records"),
)
def test_retained_record_cardinality_preserves_terminal_reason_and_local_result(
    tmp_path: Path,
    records: tuple[str, ...],
    reason: str,
    expected_first: int | None,
    expected_last: int | None,
    expected_result: str,
) -> None:
    # covers: R11
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    before = _bundle_state(health, expected)

    terminal = _close_partition(capture, root, manifest, expected, records, reason)
    result = verifier.verify(population)
    after = _bundle_state(health, expected, result)

    assert_state_delta(
        before,
        after,
        universe={"health.receipt-kinds", "verifier.local-result"},
        expected={
            "health.receipt-kinds": set_to(("expected", "started", "terminal")),
            "verifier.local-result": set_to(expected_result),
        },
        strict=True,
    )
    assert (
        terminal.record_count,
        terminal.first_sequence,
        terminal.last_sequence,
        terminal.reason,
    ) == (
        len(records),
        expected_first,
        expected_last,
        getattr(capture.TerminalReason, reason),
    )
    terminal_payload = json.loads(_receipt_map(health, expected)["terminal"])["payload"]
    assert terminal_payload["reason"] == getattr(capture.TerminalReason, reason).value
    assert type(result).__name__ == expected_result
    if expected_result == "LocalEvidenceVerified":
        assert result.bundle_digest == _derive_bundle_digest(
            capture, root, manifest, health, (expected,)
        )
    else:
        assert isinstance(result, capture.LocalEvidenceIncomplete)


def test_refused_zero_never_collapses_into_verified_known_zero(tmp_path: Path) -> None:
    # covers: R11
    # covers: R12
    capture = _capture_public_port()
    observed: dict[str, tuple[bytes, object]] = {}

    for reason in ("NO_ELIGIBLE_EVENT", "REFUSED_BEFORE_WORK"):
        root = tmp_path / reason.lower()
        health, verifier, manifest = _public_boundaries(capture, root)
        expected = _expected_partitions(capture, manifest, 1)[0]
        population = _population(capture, manifest, (expected,))
        _close_partition(capture, root, manifest, expected, (), reason)
        observed[reason] = (
            _receipt_map(health, expected)["terminal"],
            verifier.verify(population),
        )

    known_zero_receipt, known_zero_result = observed["NO_ELIGIBLE_EVENT"]
    refused_receipt, refused_result = observed["REFUSED_BEFORE_WORK"]

    known_zero_reason = (
        f'"reason":"{capture.TerminalReason.NO_ELIGIBLE_EVENT.value}"'.encode()
    )
    refused_reason = (
        f'"reason":"{capture.TerminalReason.REFUSED_BEFORE_WORK.value}"'.encode()
    )
    assert known_zero_reason in known_zero_receipt
    assert refused_reason in refused_receipt
    assert known_zero_receipt != refused_receipt
    assert isinstance(known_zero_result, capture.LocalEvidenceVerified)
    assert isinstance(refused_result, capture.LocalEvidenceIncomplete)
    assert not isinstance(refused_result, capture.LocalEvidenceVerified)


@pytest.mark.parametrize(
    ("partition_count", "expected_result"),
    (
        (0, "LocalEvidenceIncomplete"),
        (1, "LocalEvidenceVerified"),
        (3, "LocalEvidenceVerified"),
    ),
    ids=("zero-partitions", "one-partition", "many-parent-closed-partitions"),
)
def test_expected_population_preserves_zero_one_and_many_partitions(
    tmp_path: Path,
    partition_count: int,
    expected_result: str,
) -> None:
    # covers: R11
    # covers: R15
    capture = _capture_public_port()
    root = tmp_path / "population"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, partition_count)
    population = _population(capture, manifest, expected)
    for item in expected:
        _close_partition(capture, root, manifest, item, ('{"tokens":1}',), "CAPTURED")

    result = verifier.verify(population)

    assert type(result).__name__ == expected_result
    if partition_count == 0:
        assert "MISSING_ROOT_EXPECTATION" in result.known_failures
    else:
        assert result.bundle_digest == _derive_bundle_digest(
            capture, root, manifest, health, expected
        )


def test_primary_writer_fault_is_actionable_incomplete_and_never_verified(
    tmp_path: Path,
) -> None:
    # covers: R13
    # covers: R14
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    primary = _writer(capture, root, manifest, expected)
    (root / "primary").write_text("not a directory", encoding="utf-8")
    before = _bundle_state(health, expected)

    with pytest.raises(capture.CaptureStorageError) as raised:
        primary.open()
    result = verifier.verify(population)
    after = _bundle_state(health, expected, result)

    assert_state_delta(
        before,
        after,
        universe={"health.receipt-kinds", "verifier.local-result"},
        expected={
            "health.receipt-kinds": set_to(("expected", "failure")),
            "verifier.local-result": set_to("LocalEvidenceIncomplete"),
        },
        strict=True,
    )
    assert all(
        getattr(raised.value, name, "")
        for name in ("operation", "partition_id", "reason", "remediation")
    )
    assert isinstance(result, capture.LocalEvidenceIncomplete)
    assert not isinstance(result, capture.LocalEvidenceVerified)


def test_duplicate_evidence_replay_preserves_retained_count_and_digest(
    tmp_path: Path,
) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    _health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    primary = _writer(capture, root, manifest, expected)
    record = capture.EvidenceRecord(1, "usage", '{"tokens":1}')
    primary.open()
    primary.append(record)
    retained = next((root / "primary").rglob("*.jsonl"))
    before_bytes = retained.read_bytes()
    before_digest = hashlib.sha256(before_bytes).hexdigest()

    primary.append(record)
    after_bytes = retained.read_bytes()
    terminal = primary.close(capture.TerminalReason.CAPTURED)
    result = verifier.verify(population)

    assert after_bytes == before_bytes
    assert after_bytes.count(b"\n") == 1
    assert hashlib.sha256(after_bytes).hexdigest() == before_digest
    assert terminal.record_count == 1
    assert isinstance(result, capture.LocalEvidenceVerified)


def test_second_declared_writer_is_refused_with_actionable_conflict(
    tmp_path: Path,
) -> None:
    # covers: R13
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    _health, _verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    primary = _writer(capture, root, manifest, expected)
    replacement = capture.ExpectedPartition(
        expected.partition, "writer-2", expected.declared_at
    )
    competing = _writer(capture, root, manifest, replacement)
    primary.open()

    with pytest.raises(capture.PartitionWriterConflictError) as raised:
        competing.open()

    assert all(
        getattr(raised.value, name, "")
        for name in ("operation", "partition_id", "reason", "remediation")
    )


@pytest.mark.negative_at
def test_simultaneous_same_writer_opens_never_grant_shared_ownership(
    tmp_path: Path,
) -> None:
    # covers: R13
    capture = _capture_public_port()
    root = tmp_path / "contended-bundle"
    _health, _verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    process_context = get_context("spawn")
    acquisition_barrier = process_context.Barrier(2)
    outcomes = process_context.Queue()
    processes = tuple(
        process_context.Process(
            target=_attempt_synchronized_open,
            args=(root, manifest, expected, acquisition_barrier, outcomes),
        )
        for _ in range(2)
    )

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    still_running = tuple(process for process in processes if process.is_alive())
    for process in still_running:
        process.terminate()
        process.join(timeout=2)

    observed_outcomes = []
    for _process in processes:
        try:
            observed_outcomes.append(outcomes.get(timeout=2))
        except Empty:
            break
    outcomes.close()
    outcomes.join_thread()

    temporary_residue = tuple(
        sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.name.endswith(".tmp")
        )
    )
    _assert_contract(
        not still_running
        and all(process.exitcode == 0 for process in processes)
        and sorted(observed_outcomes)
        == [("conflict", "PartitionStateError"), ("owner", "")]
        and not temporary_residue,
        invariant="simultaneous same-writer opens did not preserve exclusive ownership",
        observed={
            "exitcodes": tuple(process.exitcode for process in processes),
            "outcomes": tuple(observed_outcomes),
            "temporary_residue": temporary_residue,
        },
        expected={
            "exitcodes": (0, 0),
            "outcomes": (("conflict", "PartitionStateError"), ("owner", "")),
            "temporary_residue": (),
        },
        repair=(
            "acquire same-writer ownership atomically and use per-attempt temporary "
            "publication paths that are removed after success or conflict"
        ),
    )


def test_caller_created_terminal_cannot_replace_retained_terminal_authority(
    tmp_path: Path,
) -> None:
    # covers: R12
    # covers: R13
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    _close_partition(capture, root, manifest, expected, ('{"tokens":1}',), "CAPTURED")
    forged = capture.PartitionTerminal(
        "f" * 64, 1, 1, 1, capture.TerminalReason.CAPTURED
    )

    retained = json.loads(_receipt_map(health, expected)["terminal"])
    result = verifier.verify(population)

    assert retained["payload"]["primary_digest"] != forged.primary_digest
    assert isinstance(result, capture.LocalEvidenceVerified)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("receipt_kind", "field_path", "forged_value"),
    (
        pytest.param(
            "expected", ("schema",), "nwave_capture.health.v2", id="expected-schema"
        ),
        pytest.param(
            "started", ("payload",), {"forged": True}, id="started-payload-schema"
        ),
        pytest.param(
            "expected", ("manifest_digest",), "f" * 64, id="expected-manifest"
        ),
        pytest.param(
            "started",
            ("run_id",),
            "87654321-4321-8765-4321-876543218765",
            id="started-run",
        ),
        pytest.param(
            "expected", ("partition_id",), "forged-root", id="expected-partition"
        ),
        pytest.param(
            "expected", ("payload", "declared_at"), 7, id="expected-declared-at-type"
        ),
    ),
)
def test_verifier_never_accepts_canonical_forged_expected_or_started_receipt(
    tmp_path: Path,
    receipt_kind: str,
    field_path: tuple[str, ...],
    forged_value: object,
) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / f"forged-{receipt_kind}-{'-'.join(field_path)}"
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    _close_partition(capture, root, manifest, expected, ('{"tokens":1}',), "CAPTURED")
    retained = _receipt_map(health, expected)[receipt_kind]
    envelope = cast(
        "dict[str, Any]",
        _canonical_json_value(retained, permits_trailing_newline=False),
    )
    target = envelope
    for field in field_path[:-1]:
        target = cast("dict[str, Any]", target[field])
    target[field_path[-1]] = forged_value

    forged = json.dumps(
        envelope,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    receipt_file = next(
        path
        for path in (root / "health").rglob("*.json")
        if path.read_bytes() == retained
    )
    receipt_file.write_bytes(forged)

    _canonical_json_value(forged, permits_trailing_newline=False)
    _assert_exact_contract(
        (envelope["kind"], envelope["writer_id"]),
        (receipt_kind, expected.writer_id),
        invariant="the forged receipt changed its kind or declared writer",
        repair="hold kind and writer constant while probing the remaining receipt contract",
    )
    result = verifier.verify(population)

    _assert_contract(
        isinstance(result, capture.LocalEvidenceIndeterminate)
        and not isinstance(result, capture.LocalEvidenceVerified),
        invariant=(
            f"the verifier accepted a canonical forged {receipt_kind} receipt "
            f"with invalid {'.'.join(field_path)}"
        ),
        observed=type(result).__name__,
        expected="LocalEvidenceIndeterminate",
        repair=(
            "validate the exact envelope, per-kind payload types, manifest, run, and "
            "partition bindings before deriving any local bundle digest"
        ),
    )


@pytest.mark.negative_at
def test_receipt_kind_must_match_its_physical_slot(tmp_path: Path) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "swapped-receipt-slots"
    _health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    _close_partition(capture, root, manifest, expected, ('{"tokens":1}',), "CAPTURED")
    expected_slot = next((root / "health").rglob("expected.json"))
    started_slot = next((root / "health").rglob("started.json"))
    expected_bytes = expected_slot.read_bytes()
    started_bytes = started_slot.read_bytes()

    expected_slot.write_bytes(started_bytes)
    started_slot.write_bytes(expected_bytes)
    _assert_exact_contract(
        (expected_slot.read_bytes(), started_slot.read_bytes()),
        (started_bytes, expected_bytes),
        invariant="the hostile probe did not exchange the complete receipt bytes",
        repair="swap the retained receipts intact without changing either envelope",
    )
    result = verifier.verify(population)

    _assert_contract(
        isinstance(result, capture.LocalEvidenceIndeterminate)
        and not isinstance(result, capture.LocalEvidenceVerified),
        invariant="the verifier accepted receipt kinds retained in the wrong physical slots",
        observed=type(result).__name__,
        expected="LocalEvidenceIndeterminate",
        repair=(
            "require each physical receipt slot to contain its matching closed receipt "
            "kind before certifying the bundle"
        ),
    )


def test_illegal_lifecycle_transitions_are_refused_without_rewriting_history(
    tmp_path: Path,
) -> None:
    # covers: R12
    # covers: R13
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    health, _verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    primary = _writer(capture, root, manifest, expected)
    record = capture.EvidenceRecord(1, "usage", '{"tokens":1}')

    with pytest.raises(capture.PartitionStateError):
        primary.append(record)
    with pytest.raises(capture.PartitionStateError):
        primary.close(capture.TerminalReason.CAPTURED)
    primary.open()
    with pytest.raises(capture.PartitionStateError):
        primary.open()
    with pytest.raises(ValueError):
        primary.close(capture.TerminalReason.CAPTURED)
    primary.abort("interrupted")
    primary.abort("interrupted")
    with pytest.raises(capture.ReceiptConflictError):
        primary.abort("changed-code")
    assert tuple(json.loads(receipt)["kind"] for receipt in health.read(expected)) == (
        "expected",
        "started",
        "failure",
    )


def test_repeated_close_is_idempotent_but_terminal_history_is_immutable(
    tmp_path: Path,
) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    _health, _verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    primary = _writer(capture, root, manifest, expected)
    primary.open()
    primary.append(capture.EvidenceRecord(1, "usage", '{"tokens":1}'))

    first = primary.close(capture.TerminalReason.CAPTURED)
    repeated = primary.close(capture.TerminalReason.CAPTURED)

    assert repeated == first
    with pytest.raises(capture.ReceiptConflictError):
        primary.close(capture.TerminalReason.NO_ELIGIBLE_EVENT)
    with pytest.raises(capture.PartitionStateError):
        primary.abort("late-abort")


@pytest.mark.parametrize(
    "target", ("primary", "health-digest"), ids=("primary-byte", "health-digest")
)
def test_corrupted_retained_evidence_is_never_locally_verified(
    tmp_path: Path,
    target: str,
) -> None:
    # covers: R12
    # covers: R13
    capture = _capture_public_port()
    root = tmp_path / target
    health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    _close_partition(capture, root, manifest, expected, ('{"tokens":1}',), "CAPTURED")
    terminal_bytes = _receipt_map(health, expected)["terminal"]
    if target == "primary":
        primary = _primary_file(root, terminal_bytes)
        primary.write_bytes(primary.read_bytes() + b"corrupt")
    else:
        envelope = json.loads(terminal_bytes)
        envelope["payload"]["primary_digest"] = "f" * 64
        corrupted = json.dumps(
            envelope,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        terminal_file = next(
            path
            for path in (root / "health").rglob("*.json")
            if path.read_bytes() == terminal_bytes
        )
        terminal_file.write_bytes(corrupted)

    result = verifier.verify(population)

    assert not isinstance(result, capture.LocalEvidenceVerified)
    assert isinstance(result, capture.LocalEvidenceIndeterminate)


@pytest.mark.parametrize(
    "invalid_case",
    (
        "noncanonical-record",
        "wrong-sequence-type",
        "padded-writer",
        "duplicate-population",
    ),
    ids=(
        "noncanonical-record",
        "wrong-sequence-type",
        "padded-writer",
        "duplicate-population",
    ),
)
def test_malformed_public_values_raise_only_the_closed_validation_errors(
    tmp_path: Path,
    invalid_case: str,
) -> None:
    # covers: R12
    capture = _capture_public_port()
    root = tmp_path / "malformed"
    _health, _verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]

    if invalid_case == "noncanonical-record":
        with pytest.raises(ValueError):
            capture.EvidenceRecord(1, "usage", '{"tokens": 1}')
    elif invalid_case == "wrong-sequence-type":
        with pytest.raises(TypeError):
            capture.EvidenceRecord("1", "usage", '{"tokens":1}')
    elif invalid_case == "padded-writer":
        with pytest.raises(ValueError):
            capture.ExpectedPartition(
                expected.partition, " writer ", expected.declared_at
            )
    else:
        with pytest.raises(ValueError):
            _population(capture, manifest, (expected, expected))


def test_lost_health_provenance_is_indeterminate_and_never_a_clean_bundle(
    tmp_path: Path,
) -> None:
    # covers: R14
    capture = _capture_public_port()
    root = tmp_path / "bundle"
    _health, verifier, manifest = _public_boundaries(capture, root)
    expected = _expected_partitions(capture, manifest, 1)[0]
    population = _population(capture, manifest, (expected,))
    primary = _writer(capture, root, manifest, expected)
    (root / "health").write_text("not a directory", encoding="utf-8")

    with pytest.raises(capture.HealthReceiptUnavailableError) as raised:
        primary.open()
    result = verifier.verify(population)

    assert all(
        getattr(raised.value, name, "")
        for name in ("operation", "partition_id", "reason", "remediation")
    )
    assert isinstance(result, capture.LocalEvidenceIndeterminate)
    assert not isinstance(result, capture.LocalEvidenceVerified)
