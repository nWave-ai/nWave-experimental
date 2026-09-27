"""Grammar and admission of caller-supplied public observation packets.

The packet is intentionally evidence transport, not a DES execution plan.  Its
producer chooses observations; this module only makes the declared wire format,
candidate binding and known-path screen deterministic.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


MAX_PACKET_BYTES = 65_536
SCHEMA = "nwave.public_observations"
WITHHELD = {
    "withheld": True,
    "reason": "source-blind examiner: native verification detail may reveal oracle identifiers or source",
}
_STATE = re.compile(r"^S[1-9][0-9]{0,4}$")
_SCENARIO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Defect:
    pointer: str
    code: str
    detail: str


class ObservationPacketRefused(ValueError):
    def __init__(self, defects: list[Defect], stopped: bool = False) -> None:
        self.defects = sorted(defects, key=lambda item: (item.pointer, item.code))
        self.stopped = stopped
        super().__init__("observation packet refused")


def _pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _join(pointer: str, token: str | int) -> str:
    return f"{pointer}/{_pointer(str(token))}"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> object:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("byte-order mark")
    text = raw.decode("utf-8", errors="strict")
    decoder = json.JSONDecoder(
        object_pairs_hook=_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
    value, end = decoder.raw_decode(text)
    if text[end:].strip():
        raise ValueError("trailing data")
    return value


class _Validator:
    def __init__(self, candidate: str, tree: str, owned_paths: list[str]) -> None:
        self.candidate = candidate
        self.tree = tree
        self.owned_paths = owned_paths
        self.defects: list[Defect] = []
        self.missing: set[str] = set()

    def add(self, pointer: str, code: str, detail: str) -> None:
        if pointer in self.missing:
            return  # the missing_key defect already names it
        self.defects.append(Defect(pointer, code, detail))

    def exact(
        self, value: object, required: set[str], pointer: str
    ) -> dict[str, object] | None:
        """Report key defects; return the object with absent keys as None.

        Validation continues past key defects so independent defects are all
        collected; absent keys are silenced by their own missing_key defect.
        """
        if not isinstance(value, dict):
            self.add(pointer, "wrong_type", "must be an object")
            return None
        for key in sorted(required - set(value)):
            self.add(pointer, "missing_key", f"missing key {json.dumps(key)}")
            self.missing.add(_join(pointer, key))
        for key in sorted(set(value) - required):
            self.add(_join(pointer, key), "unknown_key", "key is not permitted")
        return {key: value.get(key) for key in required}

    def string(
        self,
        value: object,
        pointer: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
        pattern: re.Pattern[str] | None = None,
    ) -> bool:
        if not isinstance(value, str):
            self.add(pointer, "wrong_type", "must be a string")
            return False
        if "\x00" in value:
            self.add(pointer, "bad_value", "must not contain U+0000")
        if minimum is not None and len(value) < minimum:
            self.add(
                pointer, "bad_value", f"must contain at least {minimum} character(s)"
            )
        if maximum is not None and len(value) > maximum:
            self.add(
                pointer, "bad_value", f"must contain at most {maximum} character(s)"
            )
        if pattern is not None and not pattern.fullmatch(value):
            self.add(pointer, "bad_value", "has an invalid format")
        return True

    def any_strings(self, value: object, pointer: str) -> None:
        if isinstance(value, str):
            if "\x00" in value:
                self.add(pointer, "bad_value", "must not contain U+0000")
            for path in self.owned_paths:
                if path and path in value:
                    self.add(
                        pointer,
                        "path_bearing",
                        f"contains declared path {json.dumps(path)}",
                    )
                    break
        elif isinstance(value, dict):
            for key, child in value.items():
                self.any_strings(key, _join(pointer, key))
                self.any_strings(child, _join(pointer, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self.any_strings(child, _join(pointer, index))

    def reference(self, value: object, pointer: str, states: dict[str, object]) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            self.add(pointer, "wrong_type", "must be a state reference or null")
        elif value not in states:
            self.add(
                pointer, "unresolved_ref", f"does not name a state: {json.dumps(value)}"
            )

    def validate(self, packet: object) -> list[Defect]:
        required = {
            "schema",
            "version",
            "candidate_sha",
            "candidate_tree_sha",
            "producer",
            "states",
            "scenarios",
        }
        original = packet
        packet = self.exact(packet, required, "")
        if packet is None:
            self.any_strings(original, "")
            return self.defects
        self.string(packet["schema"], "/schema")
        if packet["schema"] != SCHEMA:
            self.add("/schema", "bad_value", f"must equal {json.dumps(SCHEMA)}")
        if not _is_int(packet["version"]):
            self.add("/version", "wrong_type", "must be JSON integer 1")
        elif packet["version"] != 1:
            self.add("/version", "bad_value", "must equal 1")
        for key, expected, stale in (
            ("candidate_sha", self.candidate, "stale_candidate"),
            ("candidate_tree_sha", self.tree, "stale_tree"),
        ):
            pointer = f"/{key}"
            value = packet[key]
            if self.string(value, pointer):
                if not _HEX.fullmatch(value):
                    self.add(
                        pointer,
                        "bad_value",
                        "must be lowercase 40-character hexadecimal",
                    )
                elif value != expected:
                    self.add(
                        pointer,
                        stale,
                        f"{json.dumps(value)} differs from {json.dumps(expected)}",
                    )
        producer = self.exact(packet["producer"], {"id", "version"}, "/producer")
        if producer is not None:
            self.string(producer["id"], "/producer/id", minimum=1, maximum=128)
            self.string(producer["version"], "/producer/version", minimum=1, maximum=64)
        states = packet["states"]
        if not isinstance(states, dict):
            self.add("/states", "wrong_type", "must be an object")
            states = {}
        else:
            for key in states:
                if not _STATE.fullmatch(key):
                    self.add(
                        _join("/states", key),
                        "bad_value",
                        "state key has an invalid format",
                    )
        scenarios = packet["scenarios"]
        if not isinstance(scenarios, list):
            self.add("/scenarios", "wrong_type", "must be an array")
        elif not scenarios:
            self.add("/scenarios", "bad_value", "must not be empty")
        else:
            seen: set[str] = set()
            for index, scenario in enumerate(scenarios):
                self.scenario(scenario, _join("/scenarios", index), states, seen)
        self.any_strings(original, "")
        return self.defects

    def scenario(
        self, value: object, pointer: str, states: dict[str, object], seen: set[str]
    ) -> None:
        value = self.exact(value, {"id", "substrate", "purpose", "events"}, pointer)
        if value is None:
            return
        ident = value["id"]
        if self.string(ident, _join(pointer, "id"), pattern=_SCENARIO) and isinstance(
            ident, str
        ):
            if ident in seen:
                self.add(
                    _join(pointer, "id"), "bad_value", "scenario id must be unique"
                )
            seen.add(ident)
        substrate = value["substrate"]
        if not isinstance(substrate, str):
            self.add(_join(pointer, "substrate"), "wrong_type", "must be a string")
        elif substrate not in {"installed_host", "source_tree", "mock_provider"}:
            self.add(
                _join(pointer, "substrate"), "bad_value", "is not a supported substrate"
            )
        self.string(value["purpose"], _join(pointer, "purpose"), minimum=1, maximum=512)
        events = value["events"]
        if not isinstance(events, list):
            self.add(_join(pointer, "events"), "wrong_type", "must be an array")
            return
        if not events:
            self.add(_join(pointer, "events"), "bad_value", "must not be empty")
            return
        previous = 0
        for index, event in enumerate(events):
            previous = self.event(
                event, _join(_join(pointer, "events"), index), states, previous
            )

    def event(
        self, value: object, pointer: str, states: dict[str, object], previous: int
    ) -> int:
        value = self.exact(
            value, {"seq", "stimulus", "response", "state", "counter"}, pointer
        )
        if value is None:
            return previous
        seq = value["seq"]
        if not _is_int(seq):
            self.add(_join(pointer, "seq"), "wrong_type", "must be an integer")
        elif seq < 1 or seq <= previous:
            self.add(
                _join(pointer, "seq"),
                "bad_value",
                "must be strictly increasing and at least 1",
            )
        else:
            previous = seq
        stimulus = self.exact(
            value["stimulus"], {"argv", "stdin"}, _join(pointer, "stimulus")
        )
        if stimulus is not None:
            argv = stimulus["argv"]
            argv_pointer = _join(_join(pointer, "stimulus"), "argv")
            if not isinstance(argv, list):
                self.add(argv_pointer, "wrong_type", "must be an array")
            elif not argv:
                self.add(argv_pointer, "bad_value", "must not be empty")
            else:
                for index, arg in enumerate(argv):
                    if not isinstance(arg, str):
                        self.add(
                            _join(argv_pointer, index), "wrong_type", "must be a string"
                        )
                    elif index == 0 and not arg:
                        self.add(
                            _join(argv_pointer, index), "bad_value", "must not be empty"
                        )
            self.reference(
                stimulus["stdin"], _join(_join(pointer, "stimulus"), "stdin"), states
            )
        response = self.exact(
            value["response"], {"exit", "stdout", "stderr"}, _join(pointer, "response")
        )
        if response is not None:
            if not _is_int(response["exit"]):
                self.add(
                    _join(_join(pointer, "response"), "exit"),
                    "wrong_type",
                    "must be an integer",
                )
            self.string(response["stdout"], _join(_join(pointer, "response"), "stdout"))
            self.string(response["stderr"], _join(_join(pointer, "response"), "stderr"))
        state = self.exact(value["state"], {"before", "after"}, _join(pointer, "state"))
        if state is not None:
            self.reference(
                state["before"], _join(_join(pointer, "state"), "before"), states
            )
            self.reference(
                state["after"], _join(_join(pointer, "state"), "after"), states
            )
        counter = value["counter"]
        if counter is not None:
            counter_pointer = _join(pointer, "counter")
            counter = self.exact(counter, {"before", "after"}, counter_pointer)
            if counter is not None:
                for key in ("before", "after"):
                    observed = counter[key]
                    target = _join(counter_pointer, key)
                    if not _is_int(observed):
                        self.add(target, "wrong_type", "must be a non-negative integer")
                    elif observed < 0:
                        self.add(target, "bad_value", "must be non-negative")
        return previous


def read_packet(
    path: Path, candidate: str, tree: str, owned_paths: list[str]
) -> tuple[dict[str, object], dict[str, object]]:
    """Read one packet once and return its parsed value plus DES provenance."""
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            raw = stream.read(MAX_PACKET_BYTES + 1)
    except OSError as error:
        raise ObservationPacketRefused(
            [Defect("", "unreadable", str(error))], True
        ) from error
    if size > MAX_PACKET_BYTES or len(raw) > MAX_PACKET_BYTES:
        size = max(size, len(raw))
        raise ObservationPacketRefused(
            [Defect("", "oversize", f"is {size} bytes; maximum is {MAX_PACKET_BYTES}")],
            True,
        )
    try:
        packet = _strict_json(raw)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        code = "not_utf8" if isinstance(error, UnicodeDecodeError) else "not_json"
        raise ObservationPacketRefused([Defect("", code, str(error))], True) from error
    defects = _Validator(candidate, tree, owned_paths).validate(packet)
    if defects:
        raise ObservationPacketRefused(defects)
    assert isinstance(packet, dict)
    return packet, {
        "origin": "caller_supplied",
        "measured_by_des": False,
        "packet_sha256": hashlib.sha256(raw).hexdigest(),
        "packet_bytes": len(raw),
        "checked": ["shape", "candidate_identity", "size", "known_path_strings"],
        "unverified": [
            "capture_authenticity",
            "declared_substrate",
            "copied_source_or_selectors",
        ],
    }
