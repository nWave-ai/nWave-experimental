"""One minimal, software-owned restart handover and shared delivery lock."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.domain.distill_document import AcceptanceObligation
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


@dataclass(frozen=True, slots=True)
class Blocked:
    what: str
    why: str
    how: str
    refusal: bool = False
    retry: bool = False


@dataclass(frozen=True, slots=True)
class HandoverValue:
    observation: str
    dependencies: tuple[str, ...]
    authority: str | DesignFacts | None
    acceptance: tuple[AcceptanceObligation, ...] = ()
    acceptance_oracle: str | None = None
    acceptance_supports: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredHandover:
    request: str
    values: tuple[HandoverValue, ...]
    raw: bytes


#: The ONE repair a restored-handover refusal names.  The path it quotes is
#: asserted against :func:`handover_path` in the tests: a HOW naming a file
#: the software does not write is a rejection that lies.
_HANDOVER_REPAIR = (
    "delete .nwave/des/handover.json to re-elicit this Request from its "
    "durable authorities; the generated artifacts themselves are never removed"
)

_PARADIGMS = ("object_oriented", "functional")
_DECISIONS = ("EXTEND", "CREATE_NEW")
_QUOTED_VALUE_BUDGET = 120


def _shown(value: object) -> str:
    """One rejected value, quoted and bounded, safe to put in a message."""
    text = value if isinstance(value, str) else repr(value)
    if len(text) > _QUOTED_VALUE_BUDGET:
        text = text[:_QUOTED_VALUE_BUDGET] + "..."
    return '"' + text.replace("\n", "\\n").replace("\r", "\\r") + '"'


def _not_a_locator(field: str, value: object) -> str:
    return f"{field} is not a repository-relative file locator: {_shown(value)}"


def design_facts_defect(facts: DesignFacts) -> str | None:
    """The FIRST contract clause ``facts`` violates, or ``None`` when valid.

    Every caller used to print "incomplete facts" for ANY violation.  Measured
    on 2026-09-05 (run 20260905T002110Z-3913588, turn 04) that message was
    false: the architect returned facts that were COMPLETE and of the wrong
    TYPE -- six prose sentences where ``acceptance_supports`` requires
    repository-relative file locators -- and the run was told to "return
    complete typed design facts", which names the wrong repair.  A rejection
    that misnames its own cause is worse than a bare traceback.

    The clause order mirrors the original conjunction exactly, because later
    clauses are only well-defined once earlier ones hold: an unhashable path
    must never reach the duplicate check, and a non-string oracle must never
    reach ``partition``.
    """
    if not facts.targets:
        return "targets is empty"
    if facts.paradigm not in _PARADIGMS:
        return f"paradigm is not one of {' or '.join(_PARADIGMS)}: {_shown(facts.paradigm)}"
    if not facts.decisions:
        return "decisions is empty"
    for index, item in enumerate(facts.decisions):
        if not isinstance(item, str) or not item:
            return f"decisions[{index}] is not a non-empty string: {_shown(item)}"
    if not isinstance(facts.oracle, str):
        return f"oracle is not a string: {_shown(facts.oracle)}"
    if not is_design_oracle_locator(facts.oracle):
        return _not_a_locator("oracle", facts.oracle)
    oracle_path = facts.oracle.partition("::")[0]
    for index, target in enumerate(facts.targets):
        if not isinstance(target.path, str) or (
            not is_repository_relative_whole_file_locator(target.path)
        ):
            return _not_a_locator(f"targets[{index}].path", target.path)
        if target.decision not in _DECISIONS:
            return (
                f"targets[{index}].decision is not one of "
                f"{' or '.join(_DECISIONS)}: {_shown(target.decision)}"
            )
    seen_paths: set[str] = set()
    for index, target in enumerate(facts.targets):
        if target.path in seen_paths:
            return f"targets[{index}].path repeats an earlier target: {_shown(target.path)}"
        seen_paths.add(target.path)
    seen_supports: set[str] = set()
    for index, path in enumerate(facts.acceptance_supports):
        if not isinstance(path, str) or (
            not is_repository_relative_whole_file_locator(path)
        ):
            return _not_a_locator(f"acceptance_supports[{index}]", path)
        if path == oracle_path:
            return (
                f"acceptance_supports[{index}] repeats the oracle, which is "
                f"never its own support: {_shown(path)}"
            )
        if path in seen_supports:
            return f"acceptance_supports[{index}] repeats an earlier support: {_shown(path)}"
        seen_supports.add(path)
    if not facts.verification:
        return "verification is empty"
    for index, argv in enumerate(facts.verification):
        if not argv:
            return f"verification[{index}] is an empty argv"
        for position, part in enumerate(argv):
            if not isinstance(part, str) or not part:
                return (
                    f"verification[{index}][{position}] is not a non-empty "
                    f"string: {_shown(part)}"
                )
    return None


def valid_design_facts(facts: DesignFacts) -> bool:
    """Kept as the boolean face of :func:`design_facts_defect`.

    The provider now refuses these shapes inside the architect's own turn: the
    schema it enforces carries the same locator grammar, the same enums and the
    same lower bounds (``_SOLUTION_ARCHITECT_SCHEMA``).  This guard is NOT that
    constraint restated for the model -- it is the integrity check for the
    OTHER consumer, ``read_handover``, which reconstructs design facts from
    ``.nwave/des/handover.json``: bytes on disk that no provider validator ever
    saw and that a hand edit or a partial write can corrupt.  Removing it would
    leave that path deciding on a DESIGNATION.
    """
    return design_facts_defect(facts) is None


def handover_path(root: Path) -> Path:
    return root / ".nwave" / "des" / "handover.json"


def _obligations(raw: object) -> tuple[str, ...]:
    """Restore the optional persisted constraint projection without coercion."""
    if not isinstance(raw, list):
        raise TypeError("obligations is not a list")
    if any(
        not isinstance(item, str) or not item or item != item.strip() for item in raw
    ):
        raise TypeError("obligations contains a normalized non-empty string violation")
    if len(set(raw)) != len(raw):
        raise TypeError("obligations contains a duplicate")
    return tuple(raw)


def _canonical_bytes(
    request: str,
    values: tuple[HandoverValue, ...],
    *,
    include_obligations: bool = True,
    include_acceptance: bool | None = None,
) -> bytes:
    def authority(value: str | DesignFacts | None) -> object:
        if isinstance(value, DesignFacts):
            facts = {
                "targets": [
                    {"path": target.path, "decision": target.decision}
                    for target in value.targets
                ],
                "paradigm": value.paradigm,
                "decisions": list(value.decisions),
                "oracle": value.oracle,
                "acceptance_supports": list(value.acceptance_supports),
                "verification": [list(argv) for argv in value.verification],
            }
            if include_obligations:
                facts["obligations"] = list(value.obligations)
            return facts
        return value

    return json.dumps(
        {
            "request": request,
            "values": [
                (
                    {
                        "observation": value.observation,
                        "dependencies": list(value.dependencies),
                        "authority": authority(value.authority),
                        **(
                            {
                                "acceptance": [
                                    {
                                        "id": item.id,
                                        "stimulus": item.stimulus,
                                        "expected": item.expected,
                                    }
                                    for item in value.acceptance
                                ]
                            }
                            if include_acceptance is True
                            or (include_acceptance is None and bool(value.acceptance))
                            else {}
                        ),
                        **(
                            {
                                "acceptance_oracle": value.acceptance_oracle,
                                "acceptance_supports": list(value.acceptance_supports),
                            }
                            if include_acceptance is True
                            or (include_acceptance is None and bool(value.acceptance))
                            else {}
                        ),
                    }
                )
                for value in values
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def read_handover(raw: bytes) -> StoredHandover | Blocked:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return Blocked("HandoverMalformed", str(error), "restore the handover")
    if not isinstance(payload, dict) or set(payload) != {"request", "values"}:
        return Blocked(
            "HandoverMalformed",
            "root must contain only request and values",
            "restore the handover",
        )
    request, items = payload["request"], payload["values"]
    if (
        not isinstance(request, str)
        or not request
        or not isinstance(items, list)
        or not items
    ):
        return Blocked(
            "HandoverMalformed",
            "request and values are invalid",
            "restore the handover",
        )
    values: list[HandoverValue] = []
    observations: list[str] = []
    for item in items:
        if not isinstance(item, dict) or set(item) not in (
            {
                "observation",
                "dependencies",
                "authority",
            },
            {
                "observation",
                "dependencies",
                "authority",
                "acceptance",
                "acceptance_oracle",
                "acceptance_supports",
            },
        ):
            return Blocked(
                "HandoverMalformed", "value fields are invalid", "restore the handover"
            )
        observation, dependencies, authority = (
            item["observation"],
            item["dependencies"],
            item["authority"],
        )
        try:
            acceptance = tuple(
                AcceptanceObligation(entry["id"], entry["stimulus"], entry["expected"])
                for entry in item.get("acceptance", [])
            )
            acceptance_oracle = item.get("acceptance_oracle")
            acceptance_supports = tuple(item.get("acceptance_supports", []))
        except (KeyError, TypeError):
            return Blocked(
                "HandoverMalformed",
                "acceptance facts are invalid",
                "restore the handover",
            )
        acceptance_is_present = "acceptance" in item
        if (
            (acceptance_is_present and (not acceptance or acceptance_oracle is None))
            or (
                acceptance_oracle is not None
                and (
                    not isinstance(acceptance_oracle, str)
                    or not acceptance_oracle
                    or not is_design_oracle_locator(acceptance_oracle)
                )
            )
            or not all(
                isinstance(s, str)
                and s
                and is_repository_relative_whole_file_locator(s)
                for s in acceptance_supports
            )
            or any(
                not isinstance(part, str) or not part
                for fact in acceptance
                for part in (fact.id, fact.stimulus, fact.expected)
            )
            or len({fact.id for fact in acceptance}) != len(acceptance)
        ):
            return Blocked(
                "HandoverMalformed",
                "acceptance facts are invalid",
                "restore the handover",
            )
        facts: str | DesignFacts | None
        if isinstance(authority, dict):
            legacy_keys = {
                "targets",
                "paradigm",
                "decisions",
                "oracle",
                "acceptance_supports",
                "verification",
            }
            keys = {
                *legacy_keys,
                "obligations",
            }
            if set(authority) != legacy_keys and set(authority) != keys:
                return Blocked(
                    "HandoverMalformed",
                    "design facts are invalid",
                    "restore the handover",
                )
            try:
                targets = tuple(
                    DesignTarget(item["path"], item["decision"])
                    for item in authority["targets"]
                )
                facts = DesignFacts(
                    targets,
                    authority["paradigm"],
                    tuple(authority["decisions"]),
                    authority["oracle"],
                    tuple(authority["acceptance_supports"]),
                    tuple(tuple(argv) for argv in authority["verification"]),
                    _obligations(authority["obligations"])
                    if "obligations" in authority
                    else (),
                )
            except (KeyError, TypeError) as error:
                return Blocked(
                    "HandoverMalformed",
                    f"design facts cannot be reconstructed: {_shown(str(error))}",
                    _HANDOVER_REPAIR,
                )
        else:
            facts = authority
        if isinstance(facts, DesignFacts):
            defect = design_facts_defect(facts)
            if defect is not None:
                return Blocked(
                    "HandoverMalformed",
                    f"restored design facts are inadmissible: {defect}",
                    _HANDOVER_REPAIR,
                )
        if (
            not isinstance(observation, str)
            or not observation
            or observation in observations
            or not isinstance(dependencies, list)
            or not all(isinstance(dep, str) for dep in dependencies)
            or (
                facts is not None
                and (
                    not isinstance(facts, (str, DesignFacts))
                    or (isinstance(facts, str) and not facts)
                )
            )
        ):
            return Blocked(
                "HandoverMalformed", "value fields are invalid", "restore the handover"
            )
        positions = [
            observations.index(dep) if dep in observations else -1
            for dep in dependencies
        ]
        if (
            len(set(dependencies)) != len(dependencies)
            or positions != sorted(positions)
            or -1 in positions
        ):
            return Blocked(
                "HandoverMalformed",
                "dependencies must be ordered preceding observations",
                "restore the handover",
            )
        values.append(
            HandoverValue(
                observation,
                tuple(dependencies),
                facts,
                acceptance,
                acceptance_oracle,
                acceptance_supports,
            )
        )
        observations.append(observation)
    stored = tuple(values)
    # Persisted bytes must BE the canonical encoding, not merely parse to it:
    # pretty printing or reordered keys would break byte compare-and-swap.
    if raw not in (
        _canonical_bytes(request, stored),
        _canonical_bytes(request, stored, include_obligations=False),
        # Legacy handovers did not carry acceptance facts; their DESIGN facts
        # also predate the optional obligations member.
        _canonical_bytes(request, stored, include_acceptance=False),
        _canonical_bytes(
            request,
            stored,
            include_obligations=False,
            include_acceptance=False,
        ),
        # Accept an early optional-field encoding so it can be changed by a
        # real fact update, but never force it onto an idempotent legacy retry.
        _canonical_bytes(request, stored, include_acceptance=True),
    ):
        return Blocked(
            "HandoverMalformed",
            "handover bytes are not canonical",
            "restore the handover",
        )
    return StoredHandover(request, stored, raw)


def _write_temporary(path: Path, raw: bytes) -> Path | Blocked:
    descriptor: int | None = None
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".handover-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        completed, temporary = temporary, None
        return completed
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore handover storage")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def _fsync_directory(path: Path) -> Blocked | None:
    try:
        descriptor = os.open(path, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore handover storage")
    return None


def _create_if_absent(path: Path, raw: bytes) -> bool | Blocked:
    temporary = _write_temporary(path, raw)
    if isinstance(temporary, Blocked):
        return temporary
    try:
        path.hardlink_to(temporary)
        return True
    except FileExistsError:
        return False
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore handover storage")
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _existing_handover(path: Path) -> StoredHandover | Blocked | None:
    if path.is_symlink():
        return Blocked(
            "HandoverUnavailable",
            "handover must be a regular file",
            "restore the handover",
        )
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore the handover")
    return read_handover(raw)


def stored_handover(root: Path) -> StoredHandover | Blocked | None:
    """The persisted graph as it stands, for a caller that holds no Request.

    A step invoked ALONE takes `--repo-root` and a value position; the Request
    is IN the handover, so demanding it back on the command line would ask the
    orchestrator to retype the key the software already owns -- and a single
    mistyped character would refuse the graph as another Request's.
    """
    return _existing_handover(handover_path(root))


def load_handover(root: Path, request: str) -> StoredHandover | Blocked | None:
    existing = _existing_handover(handover_path(root))
    if isinstance(existing, StoredHandover) and existing.request != request:
        return Blocked(
            "HandoverRequestMismatch",
            "handover belongs to a different Request",
            "resume the owning Request without overwriting it",
            refusal=True,
        )
    return existing


def _normalize_values(
    values: tuple[HandoverValue, ...],
) -> tuple[HandoverValue, ...] | Blocked:
    """Canonicalize a semantic PO graph before its first durable write."""
    observations = [value.observation for value in values]
    if (
        not values
        or any(
            not isinstance(observation, str) or not observation
            for observation in observations
        )
        or len(set(observations)) != len(observations)
    ):
        return Blocked(
            "HandoverMalformed", "value observations are invalid", "repair values"
        )
    positions = {observation: index for index, observation in enumerate(observations)}
    dependencies: dict[str, tuple[str, ...]] = {}
    for value in values:
        if not isinstance(value.dependencies, tuple) or not all(
            isinstance(dependency, str) for dependency in value.dependencies
        ):
            return Blocked(
                "HandoverMalformed", "value dependencies are invalid", "repair values"
            )
        deduplicated = tuple(dict.fromkeys(value.dependencies))
        if any(dependency not in positions for dependency in deduplicated):
            return Blocked(
                "HandoverMalformed", "value dependencies are invalid", "repair values"
            )
        dependencies[value.observation] = deduplicated

    remaining = set(observations)
    ordered: list[str] = []
    while remaining:
        ready = [
            observation
            for observation in remaining
            if set(dependencies[observation]) <= set(ordered)
        ]
        if not ready:
            return Blocked(
                "HandoverMalformed",
                "value dependencies contain a cycle",
                "repair values",
            )
        next_observation = min(ready, key=positions.__getitem__)
        ordered.append(next_observation)
        remaining.remove(next_observation)

    canonical_positions = {
        observation: index for index, observation in enumerate(ordered)
    }
    by_observation = {value.observation: value for value in values}
    return tuple(
        HandoverValue(
            observation,
            tuple(
                sorted(dependencies[observation], key=canonical_positions.__getitem__)
            ),
            by_observation[observation].authority,
            by_observation[observation].acceptance,
            by_observation[observation].acceptance_oracle,
            by_observation[observation].acceptance_supports,
        )
        for observation in ordered
    )


def create_handover(
    root: Path, request: str, values: tuple[HandoverValue, ...]
) -> StoredHandover | Blocked:
    normalized = _normalize_values(values)
    if isinstance(normalized, Blocked):
        return normalized
    path, raw = handover_path(root), _canonical_bytes(request, normalized)
    validated = read_handover(raw)
    if isinstance(validated, Blocked):
        return validated
    created = _create_if_absent(path, raw)
    if isinstance(created, Blocked):
        return created
    if created:
        return StoredHandover(request, normalized, raw)
    winner = load_handover(root, request)
    if winner is None:
        return Blocked(
            "HandoverUnavailable",
            "handover disappeared after create race",
            "inspect handover storage",
        )
    return winner


def create_constructed_handover(
    root: Path, request: str, values: tuple[HandoverValue, ...]
) -> StoredHandover | Blocked:
    """Write an already-validated ordered graph without decoding its own bytes.

    The DISCUSS boundary constructs this graph under its stricter semantic
    contract. Persisted files still enter only through :func:`read_handover`.
    """
    path, raw = handover_path(root), _canonical_bytes(request, values)
    created = _create_if_absent(path, raw)
    if isinstance(created, Blocked):
        return created
    if created:
        return StoredHandover(request, values, raw)
    winner = load_handover(root, request)
    if winner is None:
        return Blocked(
            "HandoverUnavailable",
            "handover disappeared after create race",
            "inspect handover storage",
        )
    if isinstance(winner, StoredHandover) and tuple(
        (value.observation, value.dependencies) for value in winner.values
    ) != tuple((value.observation, value.dependencies) for value in values):
        return Blocked(
            "HandoverGraphMismatch",
            "handover winner has a different ordered observation/dependency graph",
            "inspect the winning handover and reconcile the DISCUSS authority",
            refusal=True,
        )
    return winner


def rewrite_handover(
    root: Path, expected: bytes, request: str, values: tuple[HandoverValue, ...]
) -> StoredHandover | Blocked:
    path = handover_path(root)
    try:
        actual = path.read_bytes()
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore handover storage")
    if actual != expected:
        return Blocked(
            "HandoverDrift",
            "handover changed before compare-and-swap",
            "inspect handover before restart",
            refusal=True,
        )
    normalized = _normalize_values(values)
    if isinstance(normalized, Blocked):
        return normalized
    raw = _canonical_bytes(request, normalized)
    validated = read_handover(raw)
    if isinstance(validated, Blocked):
        return validated
    temporary = _write_temporary(path, raw)
    if isinstance(temporary, Blocked):
        return temporary
    try:
        if path.read_bytes() != expected:
            return Blocked(
                "HandoverDrift",
                "handover changed before replace",
                "inspect handover before restart",
                refusal=True,
            )
        temporary.replace(path)
        synced = _fsync_directory(path.parent)
        if synced is not None:
            return synced
        return StoredHandover(request, normalized, raw)
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore handover storage")
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def bind_design_facts(
    root: Path,
    stored: StoredHandover,
    position: int,
    facts: DesignFacts,
    *,
    authority_persisted: bool = False,
) -> StoredHandover | Blocked:
    """CAS the one facts projection after its authority section was persisted."""
    if not 1 <= position <= len(stored.values):
        return Blocked(
            "ValueOutOfRange",
            "the value position is outside the stored handover",
            "read des state and retry with a valid value",
            refusal=True,
        )
    values = list(stored.values)
    current = values[position - 1]
    if current.authority == facts:
        return stored
    values[position - 1] = HandoverValue(
        current.observation,
        current.dependencies,
        facts,
        current.acceptance,
        current.acceptance_oracle,
        current.acceptance_supports,
    )
    bound = rewrite_handover(root, stored.raw, stored.request, tuple(values))
    if (
        authority_persisted
        and isinstance(bound, Blocked)
        and bound.what == "HandoverDrift"
    ):
        return Blocked(bound.what, bound.why, bound.how)
    return bound


def handover_unchanged(root: Path, expected: bytes) -> Blocked | None:
    try:
        actual = handover_path(root).read_bytes()
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore the handover")
    if actual != expected:
        return Blocked(
            "HandoverDrift",
            "a model or external process changed the frozen handover",
            "inspect handover before restart",
            refusal=True,
        )
    return None


def finalize_handover(root: Path, expected: bytes) -> Blocked | None:
    path = handover_path(root)
    unchanged = handover_unchanged(root, expected)
    if unchanged is not None:
        return unchanged
    try:
        path.unlink()
        synced = _fsync_directory(path.parent)
        if synced is not None:
            restored = _create_if_absent(path, expected)
            if isinstance(restored, Blocked):
                return Blocked(
                    "HandoverCleanupUnproven",
                    restored.why,
                    "inspect handover residue",
                )
            return Blocked(
                "HandoverCleanupUnproven",
                synced.why,
                "inspect handover residue",
            )
    except OSError as error:
        return Blocked(
            "HandoverCleanupUnproven", str(error), "inspect handover residue"
        )
    return None


@dataclass(slots=True)
class DeliveryLock:
    handle: object
    kind: str

    def release(self) -> None:
        try:
            if self.kind == "fcntl":
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            else:
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close()


def acquire_delivery_lock(root: Path) -> DeliveryLock | Blocked:
    path = root / ".nwave" / "des" / "commit.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
    except OSError as error:
        return Blocked("DeliveryLockUnavailable", str(error), "restore delivery lock")
    try:
        try:
            import fcntl
        except ImportError:
            fcntl = None
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return DeliveryLock(handle, "fcntl")
        try:
            import msvcrt
        except ImportError:
            handle.close()
            return Blocked(
                "DeliveryLockUnavailable",
                "no supported lock primitive",
                "restore delivery lock",
            )
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return DeliveryLock(handle, "msvcrt")
    except (BlockingIOError, OSError):
        handle.close()
        return Blocked(
            "DeliveryBusy",
            "another delivery owns the shared checkout",
            "retry when the current delivery completes",
            retry=True,
        )
