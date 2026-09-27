"""Construct or reuse one selected value's independent expectation charter.

The whole namespace assigned to the selected scope is classified before the
selected member is touched (Missing/Empty/Valid/Invalid): an invalid sibling
blocks construction of the selected value, and a valid sibling is preserved
untouched. A valid selected member is reused byte-for-byte with zero new
Product Owner turns and without ever opening `--input`.
"""

from __future__ import annotations

import hashlib
import json
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.application.handover import Blocked
from des.application.whole_file_document_publisher import (
    PublishRefusalVocabulary,
    publish_whole_file,
)
from des.domain.expectation_charter import (
    ExpectationCharter,
    ExpectationCharterInvalid,
    canonical_bytes,
    member_path,
    member_value,
    namespace_directory,
    parse_canonical,
    source_fingerprint_sha256,
)
from des.ports.driven_ports.task_invocation_port import (
    MalformedModelEnvelope,
    ModelOutcome,
    TaskInvocationPort,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.domain.document_scope import DocumentScope


_SEMANTIC_TASK = "expectation-charter"
_ROLE = "nw-product-owner"
_ADMITTED_KEYS = frozenset(
    {"schema_version", "intent", "observation", "public_start_recipe"}
)
_SEMANTIC_FIELDS = ("intent", "observation", "public_start_recipe")


@dataclass(frozen=True, slots=True)
class CharterOutcome:
    """One closed result of a charter construction/reuse attempt."""

    kind: str  # reused | constructed | clarification | refusal | retry | indeterminate
    what: str = ""
    why: str = ""
    how: str = ""
    path: str | None = None
    turns_bought: int = 0
    diagnostic: str | None = None


class _DuplicateKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen[key] = value
    return seen


def _decode_input(
    raw: str | None,
) -> tuple[dict[str, object] | None, CharterOutcome | None]:
    """Parse `--input` bytes into the three admitted semantic keys, or refuse.

    Returns ``(document, None)`` on a syntactically admissible object, or
    ``(None, outcome)`` naming a malformed-input refusal. Absent semantic
    facts are reported by the caller, which also has stored-value context.
    """
    if raw is None:
        return {}, None
    try:
        document = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except _DuplicateKey as duplicate:
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            f"--input carries a duplicate JSON key: {duplicate.key}",
            "supply --input JSON with each key exactly once",
        )
    except json.JSONDecodeError as error:
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            f"--input is not one strict UTF-8 JSON object: {error}",
            "supply a single JSON object with schema_version, intent, observation, "
            "and public_start_recipe",
        )
    if not isinstance(document, dict):
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            "--input top-level JSON value is not an object",
            "supply a single JSON object with schema_version, intent, observation, "
            "and public_start_recipe",
        )
    extra = sorted(set(document) - _ADMITTED_KEYS)
    if extra:
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            f"--input carries unadmitted field(s): {', '.join(extra)}",
            "supply exactly schema_version, intent, observation, and public_start_recipe",
        )
    if "schema_version" not in document:
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            "--input is missing the required schema_version",
            "set schema_version to the integer 1",
        )
    version = document["schema_version"]
    if type(version) is not int or version != 1:
        return None, CharterOutcome(
            "refusal",
            "CharterInputMalformed",
            "--input schema_version must be the integer 1",
            "set schema_version to the integer 1",
        )
    for field in _SEMANTIC_FIELDS:
        if field in document and not isinstance(document[field], str):
            return None, CharterOutcome(
                "refusal",
                "CharterInputMalformed",
                f"--input field {field} must be a string",
                f"supply {field} as a nonblank string",
            )
    return document, None


def _missing_semantic_fields(document: dict[str, object]) -> tuple[str, ...]:
    missing = []
    for field in _SEMANTIC_FIELDS:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return tuple(missing)


@dataclass(frozen=True, slots=True)
class _NamespaceState:
    kind: str
    charters: dict[int, ExpectationCharter]
    invalid_path: str | None = None
    invalid_reason: str | None = None
    observations: tuple[tuple[str, str], ...] = ()


def _classify_namespace(root: Path, scope: DocumentScope, stored) -> _NamespaceState:
    namespace = namespace_directory(scope)
    directory = root
    for part in Path(namespace).parts:
        directory = directory / part
        try:
            mode = directory.lstat().st_mode
        except FileNotFoundError:
            if directory.exists() or directory.is_symlink():
                return _NamespaceState(
                    "invalid", {}, str(directory), "unreadable namespace parent"
                )
            return _NamespaceState("missing", {})
        except OSError as error:
            return _NamespaceState(
                "invalid", {}, str(directory), f"namespace parent unavailable: {error}"
            )
        if not stat.S_ISDIR(mode):
            return _NamespaceState(
                "invalid",
                {},
                str(directory),
                "namespace parent is not a real directory",
            )
        if not mode & 0o444 or not mode & 0o111:
            return _NamespaceState(
                "invalid", {}, str(directory), "namespace parent is unreadable"
            )
    try:
        entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
    except OSError as error:
        return _NamespaceState(
            "invalid", {}, namespace, f"namespace cannot be enumerated: {error}"
        )
    if not entries:
        return _NamespaceState("empty", {})
    charters: dict[int, ExpectationCharter] = {}
    observations: list[tuple[str, str]] = []
    for entry in entries:
        relative = f"{namespace}/{entry.name}"
        value = member_value(entry.name)
        try:
            mode = entry.lstat().st_mode
        except OSError as error:
            return _NamespaceState(
                "invalid", {}, relative, f"entry unavailable: {error}"
            )
        if value is None or not stat.S_ISREG(mode):
            return _NamespaceState(
                "invalid", {}, relative, "not a canonical direct value-N.md member"
            )
        if not mode & 0o444:
            return _NamespaceState("invalid", {}, relative, "entry is unreadable")
        if not 1 <= value <= len(stored.values):
            return _NamespaceState(
                "invalid",
                {},
                relative,
                "value position is absent from the stored handover",
            )
        if value in charters:
            return _NamespaceState("invalid", {}, relative, "duplicate value position")
        try:
            data = entry.read_bytes()
        except OSError:
            return _NamespaceState("invalid", {}, relative, "unreadable")
        try:
            charter = parse_canonical(data)
        except ExpectationCharterInvalid as error:
            return _NamespaceState("invalid", {}, relative, str(error))
        if charter.value != value:
            return _NamespaceState("invalid", {}, relative, "value position mismatch")
        if charter.source_sha256 != source_fingerprint_sha256(
            stored.values[value - 1].observation, scope, value
        ):
            return _NamespaceState(
                "invalid", {}, relative, "source fingerprint is stale"
            )
        charters[value] = charter
        observations.append((relative, hashlib.sha256(data).hexdigest()))
    return _NamespaceState("valid", charters, observations=tuple(observations))


def _stored_observation(stored, value: int) -> str | None:
    if not 1 <= value <= len(stored.values):
        return None
    return stored.values[value - 1].observation


def construct_or_reuse(
    root: Path,
    port: TaskInvocationPort | Callable[[], TaskInvocationPort | object],
    stored,
    value: int,
    raw_input: str | Callable[[], str | CharterOutcome | None] | None,
) -> CharterOutcome:
    scope = stored.scope
    if not 1 <= value <= len(stored.values):
        return CharterOutcome(
            "refusal",
            "ValueOutOfRange",
            f"this Request carries {len(stored.values)} value(s), numbered 1 to "
            f"{len(stored.values)}, and {value} is outside that range",
            "read `des state --repo-root <root>` for the ordered values",
        )
    namespace = _classify_namespace(root, scope, stored)
    if namespace.kind == "invalid":
        return CharterOutcome(
            "refusal",
            "ExpectationCharterNamespaceInvalid",
            f"{namespace.invalid_path} is not a valid canonical charter: "
            f"{namespace.invalid_reason}",
            "repair or remove the offending namespace member before selecting "
            "this value's charter",
        )
    stored_observation = _stored_observation(stored, value)
    existing = namespace.charters.get(value)
    if existing is not None:
        expected_source = source_fingerprint_sha256(stored_observation, scope, value)
        if existing.source_sha256 != expected_source:
            return CharterOutcome(
                "refusal",
                "ExpectationCharterStale",
                f"{member_path(scope, value)} is stale: it embeds a source "
                "fingerprint that no longer matches the persisted value it claims "
                "to bind, because the value's "
                "observation drifted after the charter was minted",
                "reconstruct the charter over the current persisted value, or "
                "restore the persisted observation the charter was minted against",
            )
        return CharterOutcome("reused", path=member_path(scope, value))
    if callable(raw_input):
        try:
            raw_input = raw_input()
        except (OSError, UnicodeError) as error:
            return CharterOutcome(
                "refusal",
                "CharterInputUnavailable",
                str(error),
                "supply a regular readable UTF-8 --input file",
            )
    if isinstance(raw_input, CharterOutcome):
        return raw_input
    document, refusal = _decode_input(raw_input)
    if refusal is not None:
        return refusal
    missing = _missing_semantic_fields(document)
    if missing:
        return CharterOutcome(
            "clarification",
            "CLARIFICATION_NEEDED",
            "the supplied --input is missing: " + ", ".join(missing),
            "supply --input JSON with schema_version 1 and nonblank intent, "
            "observation, and public_start_recipe fields",
        )
    supplied_observation = document["observation"]
    if supplied_observation != stored_observation:
        return CharterOutcome(
            "refusal",
            "CharterObservationMismatch",
            "the supplied --input observation does not equal the selected "
            "persisted value's observation",
            "supply --input whose observation field is byte-identical to the "
            "selected value's persisted observation",
        )
    intent = document["intent"]
    recipe = document["public_start_recipe"]
    prompt = "\n".join(
        f"{key}: {json.dumps(text, ensure_ascii=False)}"
        for key, text in (
            ("observation", stored_observation),
            ("intent", intent),
            ("public_start_recipe", recipe),
        )
    )
    if callable(port):
        port = port()
    if not hasattr(port, "invoke"):
        failure = getattr(port, "failure", None)
        return CharterOutcome(
            "indeterminate",
            "CharterProviderUnavailable",
            getattr(failure, "why", "selected Product Owner provider is unavailable"),
            getattr(
                failure, "how", "restore the selected role runtime before invoking"
            ),
        )
    with tempfile.TemporaryDirectory(prefix="nwave-charter-po-") as private_cwd:
        try:
            run = port.invoke(
                role_id=_ROLE,
                prompt=prompt,
                cwd=Path(private_cwd),
                semantic_task=_SEMANTIC_TASK,
            )
        except MalformedModelEnvelope as error:
            return CharterOutcome(
                "indeterminate",
                "ModelEnvelopeUnavailable",
                str(error),
                "observe the provider result",
                turns_bought=1,
            )
    if not run.issued:
        return CharterOutcome(
            "indeterminate",
            "ModelNotIssued",
            run.diagnostic,
            "repair the selected role runtime or its capability profile and retry",
        )
    turns_bought = 1
    if run.exit_status:
        return CharterOutcome(
            "retry" if run.retry_safe else "indeterminate",
            "ProviderTurnFailed",
            run.diagnostic or "provider did not complete cleanly",
            "inspect the measured provider effects before retrying",
            turns_bought=turns_bought,
        )
    if run.outcome is ModelOutcome.Rejected:
        return CharterOutcome(
            "clarification",
            "CLARIFICATION_NEEDED",
            run.diagnostic,
            "supply clarified value facts and exact public start recipe through --input",
            turns_bought=turns_bought,
        )
    if run.outcome is not ModelOutcome.Accepted or run.charter is None:
        return CharterOutcome(
            "indeterminate",
            "ExpectationCharterIndeterminate",
            run.diagnostic,
            "inspect the Product Owner result before retrying",
            turns_bought=turns_bought,
        )
    charter = run.charter
    source_sha256 = source_fingerprint_sha256(stored_observation, scope, value)
    data = canonical_bytes(
        ExpectationCharter(
            value=value,
            source_sha256=source_sha256,
            intent=charter.intent,
            public_start_recipe=recipe,
            exploration=charter.exploration,
            positive_observations=charter.positive_observations,
            negative_observation=charter.negative_observation,
        )
    )
    try:
        parsed = parse_canonical(data)
        if (
            parsed.public_start_recipe != recipe
            or parsed.intent != charter.intent
            or parsed.exploration != charter.exploration
            or parsed.positive_observations != charter.positive_observations
            or parsed.negative_observation != charter.negative_observation
        ):
            raise ExpectationCharterInvalid(
                "generated charter facts do not round-trip exactly"
            )
    except ExpectationCharterInvalid as error:
        return CharterOutcome(
            "indeterminate",
            "CharterConstructionInvalid",
            str(error),
            "repair the constructor or clarify ambiguous charter facts",
            turns_bought=turns_bought,
        )
    current = _classify_namespace(root, scope, stored)
    if current.kind == "invalid" or current.observations != namespace.observations:
        return CharterOutcome(
            "refusal",
            "ExpectationCharterNamespaceChanged",
            "the charter namespace changed or became invalid during the Product Owner turn",
            "reclassify the namespace and retry",
            turns_bought=turns_bought,
        )
    published = publish_whole_file(
        root,
        member_path(scope, value),
        data,
        refusals=PublishRefusalVocabulary(
            unsafe="ExpectationCharterPathUnsafe",
            drift="ExpectationCharterConflict",
            unavailable="ExpectationCharterPublishUnavailable",
        ),
    )
    if isinstance(published, Blocked):
        return CharterOutcome(
            "refusal" if published.refusal else "indeterminate",
            published.what,
            published.why,
            published.how,
            turns_bought=turns_bought,
        )
    return CharterOutcome(
        "constructed",
        path=member_path(scope, value),
        turns_bought=turns_bought,
        diagnostic=run.diagnostic,
    )
