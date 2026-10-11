"""Target-native terminal evidence; external reporter truth remains a trust boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class OracleObservationKind(Enum):
    Missing = "missing"
    Passed = "passed"
    AssertionFailed = "assertion-failed"
    SetupFailed = "setup-failed"
    Unavailable = "unavailable"


@dataclass(frozen=True, slots=True)
class OracleObservation:
    kind: OracleObservationKind
    source: str
    observed: int = 0
    assertions_failed: int = 0
    setup_failed: int = 0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ObservationUnavailable:
    source: str
    reason: str
    kind: OracleObservationKind = field(
        default=OracleObservationKind.Unavailable, init=False
    )


def observation_from_counts(
    observed: int, assertions_failed: int, setup_failed: int, *, source: str
) -> OracleObservation | ObservationUnavailable:
    """Centralize count coherence at the controlled native/report boundary."""
    counts = (observed, assertions_failed, setup_failed)
    if any(type(count) is not int or count < 0 for count in counts):
        return ObservationUnavailable(
            source, "counts must be nonnegative integers, not Booleans"
        )
    if assertions_failed > observed:
        return ObservationUnavailable(source, "assertions_failed exceeds observed")
    kind = OracleObservationKind.Missing
    if setup_failed:
        kind = OracleObservationKind.SetupFailed
    elif assertions_failed:
        kind = OracleObservationKind.AssertionFailed
    elif observed:
        kind = OracleObservationKind.Passed
    return OracleObservation(kind, source, observed, assertions_failed, setup_failed)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate JSON key {name!r}")
        result[name] = value
    return result


def decode_native_observation(
    stdout: str, completed: bool
) -> OracleObservation | ObservationUnavailable:
    """Decode only completed, strict terminal evidence, never human diagnostics."""
    source = "native-observation"
    marker = "DES-ORACLE-OBSERVATION: "
    records = [
        line
        for line in stdout.splitlines(keepends=True)
        if line.startswith("DES-ORACLE-OBSERVATION:")
    ]
    if not completed:
        return ObservationUnavailable(source, "native execution did not complete")
    if not records:
        return OracleObservation(OracleObservationKind.Missing, source)
    if len(records) != 1:
        return ObservationUnavailable(source, "multiple terminal observation records")
    record = records[0]
    if not record.startswith(marker) or not record.endswith("\n"):
        return ObservationUnavailable(
            source, "terminal observation is truncated or has an invalid delimiter"
        )
    try:
        payload = json.loads(record[len(marker) :], object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError) as error:
        return ObservationUnavailable(source, f"invalid terminal JSON: {error}")
    fields = {"version", "observed", "assertions_failed", "setup_failed"}
    if not isinstance(payload, dict) or payload.keys() != fields:
        return ObservationUnavailable(
            source,
            "terminal observation must contain exactly version, observed, assertions_failed and setup_failed",
        )
    if type(payload["version"]) is not int or payload["version"] != 1:
        return ObservationUnavailable(
            source, "terminal observation version must be integer 1"
        )
    return observation_from_counts(
        payload["observed"],
        payload["assertions_failed"],
        payload["setup_failed"],
        source=source,
    )
