"""One minimal, software-owned restart handover and shared delivery lock."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
    new_target_acceptance_support_conflict,
)
from des.domain.design_authority_locator import is_design_authority_locator
from des.domain.design_document import native_verification_defect
from des.domain.distill_document import AcceptanceObligation
from des.domain.document_scope import (
    DocumentScope,
    Feature,
    Project,
    legacy_scope,
    parse_scope,
    scope_json,
)
from des.domain.feature_documents import FeatureDocumentsInvalid, valid_feature_id
from des.ports.driven_ports.task_invocation_port import (
    DesignFacts,
    DesignTarget,
    PublicOracle,
)


_MISSING = object()


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
    #: Ordered native argvs of a complete (schema_version 2) selection; ``None``
    #: on a persisted v1 selection, which is legacy partial and never completed
    #: from DESIGN.
    acceptance_verification: tuple[tuple[str, ...], ...] | None = None
    acceptance_oracle_verification_index: int | None = None
    #: The design basis the complete selection was made over (see
    #: :func:`design_basis_sha256`); written only by the DISTILL writer.
    acceptance_design_basis_sha256: str | None = None
    #: Identity of the complete normalized DESIGN input bound to this value;
    #: written only by :func:`bind_design_facts`.
    design_semantic_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SharedDesign:
    """The one DESIGN section shared by every value of a Request.

    ``section_sha256`` identifies the rendered section bytes; ``semantic_sha256``
    identifies the complete normalized constructor input.  They are separate
    facts: rendering is lossy, so equal sections may hide different input.
    """

    authority_locator: str
    section_sha256: str
    semantic_sha256: str
    design: DesignFacts


@dataclass(frozen=True, slots=True)
class StoredHandover:
    request: str
    values: tuple[HandoverValue, ...]
    raw: bytes
    scope: DocumentScope
    shared_design: SharedDesign | None = None

    @property
    def has_explicit_scope(self) -> bool:
        """Whether the persisted bytes carry a typed scope key (not legacy)."""
        return "scope" in json.loads(self.raw.decode("utf-8"))

    @property
    def feature_id(self) -> str | None:
        from des.domain.document_scope import Slice

        return (
            self.scope.feature_id if isinstance(self.scope, (Feature, Slice)) else None
        )


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
_JSON_NESTING_LIMIT = 4096


def _shown(value: object) -> str:
    """One rejected value, quoted and bounded, safe to put in a message."""
    text = value if isinstance(value, str) else repr(value)
    if len(text) > _QUOTED_VALUE_BUDGET:
        text = text[:_QUOTED_VALUE_BUDGET] + "..."
    return '"' + text.replace("\n", "\\n").replace("\r", "\\r") + '"'


def _not_a_locator(field: str, value: object) -> str:
    return f"{field} is not a repository-relative file locator: {_shown(value)}"


def _is_section_locator(locator: str) -> bool:
    """The repository-relative DESIGN section locator grammar (path#heading)."""
    document, separator, heading = locator.partition("#")
    return bool(
        separator
        and document
        and is_repository_relative_whole_file_locator(document)
        and heading
        and heading == heading.strip()
        and "#" not in heading
        and "\n" not in heading
        and "\r" not in heading
    )


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
    conflict = new_target_acceptance_support_conflict(
        facts.oracle,
        ((target.path, target.decision) for target in facts.targets),
        facts.acceptance_supports,
    )
    if conflict is not None:
        return (
            "a non-oracle CREATE_NEW target is also a required acceptance support: "
            f"{_shown(conflict)}; the acceptance designer must create supports "
            "before craft: declare an oracle fixture only as acceptance_supports, "
            "or remove a craft-created target from acceptance_supports; "
            "do not label a new file EXTEND"
        )
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
    native = native_verification_defect(facts.verification)
    if native is not None:
        return native
    if (
        not isinstance(facts.oracle_verification_index, int)
        or isinstance(facts.oracle_verification_index, bool)
        or not 0 <= facts.oracle_verification_index < len(facts.verification)
    ):
        return (
            "oracle_verification_index must name one declared verification command: "
            f"{_shown(facts.oracle_verification_index)}"
        )
    if not isinstance(facts.authority_locator, str):
        return f"authority_locator is not a string: {_shown(facts.authority_locator)}"
    if facts.authority_locator:
        heading = facts.authority_locator.partition("#")[2]
        # The five shared clauses are asked of the ONE table that also publishes
        # them to the architect (`design_authority_locator`); only this guard's
        # ADDITIONAL canonical clause is spelled here, because bytes restored
        # from disk must also be the exact bytes a constructor would write.  It
        # stays strictly stricter than the decoder, so nothing this refuses today
        # becomes admissible.
        if (
            not is_design_authority_locator(facts.authority_locator)
            or heading != heading.strip()
        ):
            return (
                "authority_locator is not a repository-relative DESIGN section "
                f"locator: {_shown(facts.authority_locator)}"
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


def _bound_feature(raw: bytes) -> str | None:
    """The durable feature scope carried by existing handover bytes, if any.

    Every rewrite re-encodes from these bytes, so no writer can drop it.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if "scope" in payload:
        scope = parse_scope(payload["scope"])
        return (
            scope.feature_id
            if isinstance(scope, Feature)
            else None
            if isinstance(scope, Project)
            else scope
        )
    value = payload.get("feature_id")
    return value if valid_feature_id(value) else None


def handover_path(root: Path) -> Path:
    return root / ".nwave" / "des" / "handover.json"


def candidate_handover_path(root: Path, candidate: str) -> Path | None:
    """The immutable graph snapshot belonging to one verified Git candidate."""
    if re.fullmatch(r"[0-9a-f]{40}", candidate) is None:
        return None
    return root / ".nwave" / "des" / "candidates" / candidate / "handover.json"


def retain_candidate_handover(
    root: Path, candidate: str, expected: bytes
) -> Blocked | None:
    """Persist exact active handover bytes for a verified candidate once.

    The active handover must disappear after integration so a new Request starts
    cleanly. Role evidence, however, remains meaningful for the integrated
    candidate. This separate, candidate-addressed snapshot preserves the one
    graph that produced it without reviving it as current delivery state.
    """
    path = candidate_handover_path(root, candidate)
    if path is None:
        return Blocked(
            "CandidateHandoverUnavailable",
            "candidate is not a full lowercase Git object id",
            "retain a candidate printed by des verify",
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return Blocked(
            "CandidateHandoverUnavailable", str(error), "restore handover storage"
        )
    created = _create_if_absent(path, expected)
    if isinstance(created, Blocked):
        return Blocked(
            "CandidateHandoverUnavailable", created.why, "restore handover storage"
        )
    try:
        actual = path.read_bytes()
    except OSError as error:
        return Blocked(
            "CandidateHandoverUnavailable", str(error), "restore handover storage"
        )
    if actual != expected:
        return Blocked(
            "CandidateHandoverConflict",
            "candidate handover bytes differ from the verified active handover",
            "start from a new verified candidate",
            refusal=True,
        )
    synced = _fsync_directory(
        path.parent,
        unavailable="CandidateHandoverUnavailable",
        repair="restore handover storage",
    )
    if synced is not None:
        return Blocked(
            "CandidateHandoverUnavailable", synced.why, "restore handover storage"
        )
    return None


def stored_candidate_handover(
    root: Path, candidate: str
) -> StoredHandover | Blocked | None:
    """Read only the immutable graph snapshot bound to ``candidate``."""
    path = candidate_handover_path(root, candidate)
    return None if path is None else _existing_handover(path)


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


def _facts_wire(
    value: DesignFacts,
    *,
    include_obligations: bool = True,
    include_authority_locator: bool = True,
    include_public_oracle: bool = True,
) -> dict[str, object]:
    facts: dict[str, object] = {
        "targets": [
            {"path": target.path, "decision": target.decision}
            for target in value.targets
        ],
        "paradigm": value.paradigm,
        "decisions": list(value.decisions),
        "oracle": value.oracle,
        "acceptance_supports": list(value.acceptance_supports),
        "verification": [list(argv) for argv in value.verification],
        "oracle_verification_index": value.oracle_verification_index,
    }
    if include_obligations:
        facts["obligations"] = list(value.obligations)
    if include_authority_locator:
        facts["authority_locator"] = value.authority_locator
    if include_public_oracle and value.public_oracle is not None:
        facts["public_oracle"] = {
            "observation": value.public_oracle.observation,
            "stimulus": value.public_oracle.stimulus,
            "expected": value.public_oracle.expected,
            "falsifier": value.public_oracle.falsifier,
        }
    return facts


def _shared_wire(shared: SharedDesign) -> dict[str, object]:
    return {
        "authority_locator": shared.authority_locator,
        "section_sha256": shared.section_sha256,
        "semantic_sha256": shared.semantic_sha256,
        "design": _facts_wire(shared.design),
    }


def _complete_selection_wire(value: HandoverValue) -> dict[str, object]:
    """The optional complete-revision keys, serialized only when present."""
    if value.acceptance_verification is None:
        return {}
    wire: dict[str, object] = {
        "acceptance_verification": [
            list(argv) for argv in value.acceptance_verification
        ],
        "acceptance_oracle_verification_index": value.acceptance_oracle_verification_index,
    }
    if value.acceptance_design_basis_sha256 is not None:
        wire["acceptance_design_basis_sha256"] = value.acceptance_design_basis_sha256
    return wire


def design_basis_sha256(shared: SharedDesign | None, value: HandoverValue) -> str:
    """Digest of the DESIGN identities a selection is made over.

    The single definition of the basis: the DISTILL writer stores it with every
    complete write and the one selected-authority reader compares against it.
    Unknown legacy identities contribute ``null``.  The value authority is
    included exactly as the handover wire encodes it, so a provider change of
    the bound facts is a different basis even when no full-input identity is
    known.  The public_oracle is excluded from the basis: it is included in
    the value's design_semantic_sha256, and a binding that closes the semantic
    always also binds that sha256.
    """
    authority = value.authority
    return hashlib.sha256(
        json.dumps(
            {
                "authority": (
                    _facts_wire(authority, include_public_oracle=False)
                    if isinstance(authority, DesignFacts)
                    else authority
                ),
                "shared": None if shared is None else shared.semantic_sha256,
                "value": value.design_semantic_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _canonical_bytes(
    request: str,
    values: tuple[HandoverValue, ...],
    *,
    include_obligations: bool = True,
    include_acceptance: bool | None = None,
    include_authority_locator: bool = True,
    feature_id: str | None = None,
    include_scope: bool = True,
    shared: SharedDesign | None = None,
) -> bytes:
    def authority(value: str | DesignFacts | None) -> object:
        if isinstance(value, DesignFacts):
            return _facts_wire(
                value,
                include_obligations=include_obligations,
                include_authority_locator=include_authority_locator,
            )
        return value

    return json.dumps(
        {
            "request": request,
            **(
                {"scope": scope_json(legacy_scope(feature_id))}
                if include_scope
                else ({"feature_id": feature_id} if isinstance(feature_id, str) else {})
            ),
            "values": [
                (
                    {
                        "observation": value.observation,
                        "dependencies": list(value.dependencies),
                        "authority": authority(value.authority),
                        **(
                            {"design_semantic_sha256": value.design_semantic_sha256}
                            if value.design_semantic_sha256 is not None
                            else {}
                        ),
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
                        **(
                            _complete_selection_wire(value)
                            if include_acceptance is True
                            or (include_acceptance is None and bool(value.acceptance))
                            else {}
                        ),
                    }
                )
                for value in values
            ],
            **({"shared_design": _shared_wire(shared)} if shared is not None else {}),
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


_SHARED_KEYS = {"authority_locator", "section_sha256", "semantic_sha256", "design"}
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def _shared_malformed(why: str) -> Blocked:
    return Blocked(
        "HandoverMalformed",
        f"shared_design is invalid: {why}",
        "restore the handover, or rebind with `des design --shared --replace-current`",
    )


def _decode_shared(raw: object) -> SharedDesign | Blocked:
    """Restore the shared binding strictly; every departure is refused."""
    if not isinstance(raw, dict) or set(raw) != _SHARED_KEYS:
        return _shared_malformed(
            f"it must be an object with exactly {sorted(_SHARED_KEYS)}"
        )
    for name in ("section_sha256", "semantic_sha256"):
        digest = raw[name]
        if not isinstance(digest, str) or _SHA256_HEX.fullmatch(digest) is None:
            return _shared_malformed(f"{name} is not 64 lowercase hex characters")
    design_raw = raw["design"]
    if not isinstance(design_raw, dict):
        return _shared_malformed("design is not an object")
    design = _restore_facts(design_raw)
    if isinstance(design, Blocked):
        return design
    defect = design_facts_defect(design)
    if defect is not None:
        return _shared_malformed(f"design is inadmissible: {defect}")
    locator = raw["authority_locator"]
    if (
        not isinstance(locator, str)
        or not locator
        or locator != design.authority_locator
    ):
        return _shared_malformed(
            "authority_locator must be the design's own non-empty locator"
        )
    return SharedDesign(locator, raw["section_sha256"], raw["semantic_sha256"], design)


def _bound_shared(raw: bytes) -> SharedDesign | None:
    """The shared binding carried by existing handover bytes, if any.

    Every writer re-encodes from these bytes, so none can drop it.  The bytes
    were admitted by :func:`read_handover`, so a malformed binding is absent.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or "shared_design" not in payload:
        return None
    decoded = _decode_shared(payload["shared_design"])
    return None if isinstance(decoded, Blocked) else decoded


def _restore_facts(authority: dict) -> DesignFacts | Blocked:
    """Rebuild persisted design facts, or say why they are not restorable."""
    if "oracle_verification_index" not in authority:
        return Blocked(
            "HandoverMalformed",
            "design facts omit the required oracle_verification_index binding",
            _HANDOVER_REPAIR,
        )
    legacy_keys = {
        "targets",
        "paradigm",
        "decisions",
        "oracle",
        "acceptance_supports",
        "verification",
        "oracle_verification_index",
    }
    keys = {
        *legacy_keys,
        "obligations",
    }
    locator_keys = {*keys, "authority_locator"}
    legacy_locator_keys = {*legacy_keys, "authority_locator"}
    # Extract public_oracle if present and validate the remaining keys
    public_oracle = None
    authority_keys = set(authority)
    if "public_oracle" in authority_keys:
        authority_keys = authority_keys - {"public_oracle"}
    if authority_keys not in (
        legacy_keys,
        keys,
        legacy_locator_keys,
        locator_keys,
    ):
        return Blocked(
            "HandoverMalformed",
            "design facts are invalid",
            "restore the handover",
        )
    try:
        if "public_oracle" in authority:
            po = authority["public_oracle"]
            if not isinstance(po, dict):
                raise TypeError("public_oracle must be an object")
            po_keys = {"observation", "stimulus", "expected", "falsifier"}
            if set(po) != po_keys:
                raise TypeError(f"public_oracle must contain exactly {sorted(po_keys)}")
            for key in po_keys:
                if not isinstance(po[key], str) or not po[key].strip():
                    raise TypeError(f"public_oracle.{key} must be a non-empty string")
            public_oracle = PublicOracle(
                observation=po["observation"],
                stimulus=po["stimulus"],
                expected=po["expected"],
                falsifier=po["falsifier"],
            )
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
            authority["oracle_verification_index"],
            _obligations(authority["obligations"])
            if "obligations" in authority
            else (),
            authority.get("authority_locator", ""),
            public_oracle=public_oracle,
        )
    except (KeyError, TypeError) as error:
        return Blocked(
            "HandoverMalformed",
            f"design facts cannot be reconstructed: {_shown(str(error))}",
            _HANDOVER_REPAIR,
        )
    return facts


_ACCEPTANCE_TRIO = {"acceptance", "acceptance_oracle", "acceptance_supports"}
_COMPLETE_PAIR = {"acceptance_verification", "acceptance_oracle_verification_index"}
_BASIS_KEY = "acceptance_design_basis_sha256"
_SEMANTIC_KEY = "design_semantic_sha256"


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256_HEX.fullmatch(value) is not None


def _value_keys_admissible(keys: set[str]) -> bool:
    """Closed value encoding: the trio all-or-none, the pair both-or-neither,
    the basis only beside the pair, the pair only beside the trio."""
    base = {"observation", "dependencies", "authority"}
    if not base <= keys:
        return False
    rest = keys - base - {_SEMANTIC_KEY}
    has_trio = rest >= _ACCEPTANCE_TRIO
    if rest & _ACCEPTANCE_TRIO and not has_trio:
        return False
    rest -= _ACCEPTANCE_TRIO
    has_pair = rest >= _COMPLETE_PAIR
    if rest & _COMPLETE_PAIR and not has_pair:
        return False
    rest -= _COMPLETE_PAIR
    has_basis = _BASIS_KEY in rest
    rest -= {_BASIS_KEY}
    return not rest and (not has_pair or has_trio) and (not has_basis or has_pair)


def _malformed_selection(why: str) -> Blocked:
    return Blocked(
        "HandoverMalformed",
        f"acceptance selection is invalid: {why}",
        "restore the handover, or replace the selection with `des distill "
        "--replace-current --input -` using complete schema_version 2",
    )


def _restore_selection(
    item: dict,
) -> tuple[tuple[tuple[str, ...], ...] | None, int | None, str | None] | Blocked:
    """Validate the closed optional complete-revision keys of one value."""
    if "acceptance_verification" not in item:
        return None, None, None
    raw, index = (
        item["acceptance_verification"],
        item["acceptance_oracle_verification_index"],
    )
    if (
        not isinstance(raw, list)
        or not raw
        or any(
            not isinstance(argv, list)
            or not argv
            or any(
                not isinstance(part, str) or not part or "\x00" in part for part in argv
            )
            for argv in raw
        )
    ):
        return _malformed_selection(
            "acceptance_verification is not a non-empty list of argv lists"
        )
    verification = tuple(tuple(argv) for argv in raw)
    if len(set(verification)) != len(verification):
        return _malformed_selection("acceptance_verification repeats an argv")
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or not 0 <= index < len(raw)
    ):
        return _malformed_selection(
            "acceptance_oracle_verification_index is outside the argv list"
        )
    basis = item.get(_BASIS_KEY)
    if _BASIS_KEY in item and not _is_digest(basis):
        return _malformed_selection(f"{_BASIS_KEY} is not 64 lowercase hex characters")
    return verification, index, basis


def _json_nesting_exceeds_limit(raw: bytes) -> bool:
    """Bound parser depth independently of the interpreter recursion setting."""
    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue
        if byte == ord('"'):
            in_string = True
        elif byte in (ord("["), ord("{")):
            depth += 1
            if depth > _JSON_NESTING_LIMIT:
                return True
        elif byte in (ord("]"), ord("}")):
            depth = max(depth - 1, 0)
    return False


def read_handover(raw: bytes) -> StoredHandover | Blocked:
    if _json_nesting_exceeds_limit(raw):
        return Blocked(
            "HandoverMalformed",
            ".nwave/des/handover.json is malformed: JSON nesting is too deep to parse",
            _HANDOVER_REPAIR,
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return Blocked("HandoverMalformed", str(error), "restore the handover")
    except RecursionError:
        return Blocked(
            "HandoverMalformed",
            ".nwave/des/handover.json is malformed: JSON nesting is too deep to parse",
            _HANDOVER_REPAIR,
        )
    if not isinstance(payload, dict) or set(payload) not in (
        {"request", "values"},  # legacy project handover
        {"request", "values", "feature_id"},  # legacy feature handover
        {"request", "values", "scope"},
        {"request", "values", "scope", "shared_design"},
    ):
        return Blocked(
            "HandoverMalformed",
            "root must contain request, explicit scope, and values",
            "restore the handover",
        )
    request, items = payload["request"], payload["values"]
    feature_id = payload.get("feature_id")
    if "scope" in payload:
        try:
            scope = parse_scope(payload["scope"])
            feature_id = (
                scope.feature_id
                if isinstance(scope, Feature)
                else None
                if isinstance(scope, Project)
                else scope
            )
        except (ValueError, FeatureDocumentsInvalid) as error:
            return Blocked(
                "HandoverMalformed", str(error), "supply an explicit valid scope"
            )
    elif "feature_id" in payload and not valid_feature_id(feature_id):
        return Blocked(
            "HandoverMalformed",
            "feature_id is not a canonical feature id",
            "restore the handover",
        )
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
        if not isinstance(item, dict) or not _value_keys_admissible(set(item)):
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
        selection = _restore_selection(item)
        if isinstance(selection, Blocked):
            return selection
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
            restored = _restore_facts(authority)
            if isinstance(restored, Blocked):
                return restored
            facts = restored
        else:
            facts = authority
            if isinstance(facts, str) and facts and not _is_section_locator(facts):
                return Blocked(
                    "HandoverMalformed",
                    f"value {len(values) + 1} authority is invalid: it is not a "
                    "repository-relative DESIGN section locator (path#heading): "
                    f"{_shown(facts)}",
                    _HANDOVER_REPAIR,
                )
        if isinstance(facts, DesignFacts):
            defect = design_facts_defect(facts)
            if defect is not None:
                return Blocked(
                    "HandoverMalformed",
                    f"restored design facts are inadmissible: {defect}",
                    _HANDOVER_REPAIR,
                )
        semantic = item.get("design_semantic_sha256")
        if "design_semantic_sha256" in item and (
            not _is_digest(semantic)
            or not isinstance(facts, DesignFacts)
            or not facts.authority_locator
        ):
            return Blocked(
                "HandoverMalformed",
                "design_semantic_sha256 must be 64 lowercase hex characters and "
                "belongs only to a value bound to typed DESIGN facts with an "
                "authority locator",
                "restore the handover",
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
                *selection,
                semantic,
            )
        )
        observations.append(observation)
    stored = tuple(values)
    shared: SharedDesign | None = None
    if "shared_design" in payload:
        decoded = _decode_shared(payload["shared_design"])
        if isinstance(decoded, Blocked):
            return decoded
        bound_headings = {
            value.authority.authority_locator
            for value in stored
            if isinstance(value.authority, DesignFacts)
        } | {value.authority for value in stored if isinstance(value.authority, str)}
        if decoded.authority_locator in bound_headings:
            return _shared_malformed("its locator is owned by a bound value")
        shared = decoded
    # Persisted bytes must BE the canonical encoding, not merely parse to it:
    # pretty printing or reordered keys would break byte compare-and-swap.
    comparison_raw = raw
    if "scope" not in payload:
        expected_keys = (
            ["request", "values"]
            if "feature_id" not in payload
            else ["request", "feature_id", "values"]
        )
        compact = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        if list(payload) != expected_keys or raw != compact:
            return Blocked(
                "HandoverMalformed",
                "legacy handover bytes are not canonical",
                "restore the handover",
            )
        comparison_raw = json.dumps(
            {
                "request": request,
                "scope": scope_json(legacy_scope(feature_id)),
                "values": items,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    if shared is not None and comparison_raw != _canonical_bytes(
        feature_id=feature_id, request=request, values=stored, shared=shared
    ):
        # A bound shared design admits only the current encoding: a legacy
        # value encoding could hide a heading collision.
        return Blocked(
            "HandoverMalformed",
            "handover bytes are not canonical",
            "restore the handover",
        )
    if comparison_raw not in (
        # Exact legacy encoding remains readable; every subsequent rewrite
        # migrates it to the explicit tagged scope above.
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_scope=False,
        ),
        _canonical_bytes(
            feature_id=feature_id, request=request, values=stored, shared=shared
        ),
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_obligations=False,
        ),
        # Typed handovers from before the section-identity migration have no
        # authority_locator member.  They remain readable as external legacy
        # bytes, while every newly constructed serialization includes it.
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_authority_locator=False,
        ),
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_obligations=False,
            include_authority_locator=False,
        ),
        # Legacy handovers did not carry acceptance facts; their DESIGN facts
        # also predate the optional obligations member.
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_acceptance=False,
        ),
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_obligations=False,
            include_acceptance=False,
            include_authority_locator=False,
        ),
        # Accept an early optional-field encoding so it can be changed by a
        # real fact update, but never force it onto an idempotent legacy retry.
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_acceptance=True,
        ),
        _canonical_bytes(
            feature_id=feature_id,
            request=request,
            values=stored,
            shared=shared,
            include_acceptance=True,
            include_authority_locator=False,
        ),
    ):
        return Blocked(
            "HandoverMalformed",
            "handover bytes are not canonical",
            "restore the handover",
        )
    return StoredHandover(request, stored, raw, legacy_scope(feature_id), shared)


def _write_temporary(
    path: Path,
    raw: bytes,
    *,
    unavailable: str = "HandoverUnavailable",
    repair: str = "restore handover storage",
) -> Path | Blocked:
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
        return Blocked(unavailable, str(error), repair)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def _fsync_directory(
    path: Path,
    *,
    unavailable: str = "HandoverUnavailable",
    repair: str = "restore handover storage",
) -> Blocked | None:
    try:
        descriptor = os.open(path, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        return Blocked(unavailable, str(error), repair)
    return None


def replace_exact_bytes(
    path: Path,
    expected: bytes | None,
    raw: bytes,
    *,
    unavailable: str,
    repair: str,
    drift: str,
    drift_subject: str = "stored bytes",
) -> Blocked | None:
    """Atomically replace ``path`` only when it still holds ``expected``.

    The temporary is fully fsynced before rename, so an interruption cannot
    expose a truncated target.  A directory fsync failure follows a successful
    rename; callers receive an indeterminate result because the complete new
    bytes may already be visible.  This is deliberately one-file atomicity:
    callers that update a second projection must report a mixed outcome rather
    than claim a transaction they do not own.
    """
    temporary = _write_temporary(path, raw, unavailable=unavailable, repair=repair)
    if isinstance(temporary, Blocked):
        return temporary
    try:
        try:
            actual = path.read_bytes()
        except FileNotFoundError:
            actual = None
        if actual != expected:
            return Blocked(
                drift,
                f"{drift_subject} changed before atomic replace",
                f"inspect {drift_subject} before restart",
                refusal=True,
            )
        temporary.replace(path)
        synced = _fsync_directory(path.parent, unavailable=unavailable, repair=repair)
        if synced is not None:
            return Blocked(
                unavailable,
                "the complete replacement may now be visible but its directory "
                f"could not be synced: {synced.why}",
                repair,
            )
        return None
    except OSError as error:
        return Blocked(unavailable, str(error), repair)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


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


def _file_kind(mode: int) -> str:
    """The name of a non-regular file type, for the refusal's WHY."""
    if stat.S_ISFIFO(mode):
        return "FIFO"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symbolic link"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISBLK(mode):
        return "block device"
    return "non-regular file"


def _not_regular(kind: str) -> Blocked:
    return Blocked(
        "HandoverUnavailable",
        f".nwave/des/handover.json is not a regular file: it is a {kind}",
        _HANDOVER_REPAIR,
    )


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _existing_handover(path: Path) -> StoredHandover | Blocked | None:
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return None
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore the handover")
    if not stat.S_ISREG(mode):
        return _not_regular(_file_kind(mode))
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            return _not_regular("symbolic link")
        return Blocked("HandoverUnavailable", str(error), "restore the handover")
    try:
        opened = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(opened):
            return _not_regular(_file_kind(opened))
        raw = _read_descriptor(descriptor)
    except OSError as error:
        return Blocked("HandoverUnavailable", str(error), "restore the handover")
    finally:
        os.close(descriptor)
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
        replace(
            by_observation[observation],
            dependencies=tuple(
                sorted(dependencies[observation], key=canonical_positions.__getitem__)
            ),
        )
        for observation in ordered
    )


def create_handover(
    root: Path,
    request: str,
    values: tuple[HandoverValue, ...],
    feature_id: str | None = None,
) -> StoredHandover | Blocked:
    normalized = _normalize_values(values)
    if isinstance(normalized, Blocked):
        return normalized
    path = handover_path(root)
    raw = _canonical_bytes(request, normalized, feature_id=feature_id)
    validated = read_handover(raw)
    if isinstance(validated, Blocked):
        return validated
    created = _create_if_absent(path, raw)
    if isinstance(created, Blocked):
        return created
    if created:
        return StoredHandover(request, normalized, raw, legacy_scope(feature_id))
    winner = load_handover(root, request)
    if winner is None:
        return Blocked(
            "HandoverUnavailable",
            "handover disappeared after create race",
            "inspect handover storage",
        )
    return winner


def create_constructed_handover(
    root: Path,
    request: str,
    values: tuple[HandoverValue, ...],
    feature_id: str | None = None,
) -> StoredHandover | Blocked:
    """Write an already-validated ordered graph without decoding its own bytes.

    The DISCUSS boundary constructs this graph under its stricter semantic
    contract. Persisted files still enter only through :func:`read_handover`.
    """
    path = handover_path(root)
    raw = _canonical_bytes(request, values, feature_id=feature_id)
    created = _create_if_absent(path, raw)
    if isinstance(created, Blocked):
        return created
    if created:
        return StoredHandover(request, values, raw, legacy_scope(feature_id))
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
    root: Path,
    expected: bytes,
    request: str,
    values: tuple[HandoverValue, ...],
    *,
    feature_id: str | object | None = _MISSING,
) -> StoredHandover | Blocked:
    normalized = _normalize_values(values)
    if isinstance(normalized, Blocked):
        return normalized
    resolved_feature_id = (
        _bound_feature(expected) if feature_id is _MISSING else feature_id
    )
    legacy_scope(resolved_feature_id)
    shared = _bound_shared(expected)
    raw = _canonical_bytes(
        request, normalized, feature_id=resolved_feature_id, shared=shared
    )
    validated = read_handover(raw)
    if isinstance(validated, Blocked):
        return validated
    replaced = replace_exact_bytes(
        handover_path(root),
        expected,
        raw,
        unavailable="HandoverUnavailable",
        repair="restore handover storage",
        drift="HandoverDrift",
        drift_subject="handover",
    )
    if replaced is not None:
        return replaced
    return StoredHandover(
        request, normalized, raw, legacy_scope(resolved_feature_id), shared
    )


def rewrite_constructed_handover(
    root: Path, expected: bytes, request: str, values: tuple[HandoverValue, ...]
) -> StoredHandover | Blocked:
    """CAS already-constructed values without decoding their canonical bytes.

    Domain constructors have already established the typed values.  Re-reading
    the bytes here would validate the same values a second time; only later
    process boundaries use :func:`read_handover` for external persisted bytes.
    """
    feature_id = _bound_feature(expected)
    shared = _bound_shared(expected)
    raw = _canonical_bytes(request, values, feature_id=feature_id, shared=shared)
    replaced = replace_exact_bytes(
        handover_path(root),
        expected,
        raw,
        unavailable="HandoverUnavailable",
        repair="restore handover storage",
        drift="HandoverDrift",
        drift_subject="handover",
    )
    if replaced is not None:
        return replaced
    return StoredHandover(request, values, raw, legacy_scope(feature_id), shared)


def bind_design_facts(
    root: Path,
    stored: StoredHandover,
    position: int,
    facts: DesignFacts,
    *,
    authority_persisted: bool = False,
    semantic_sha256: str | None = None,
) -> StoredHandover | Blocked:
    """CAS the one facts projection after its authority section was persisted.

    A no-op only when the facts AND the full-input identity are both equal
    (``None`` means the caller cannot name the identity, keeping the facts-only
    comparison).  Otherwise both are rebound: differing facts bound without
    naming their full input clear the identity, never keep a stale one.  Acceptance keys, including the
    complete selection and its basis, are carried untouched: a changed DESIGN
    never rewrites a selection, it only makes the basis differ on read.
    """
    if not 1 <= position <= len(stored.values):
        return Blocked(
            "ValueOutOfRange",
            "the value position is outside the stored handover",
            "read des state and retry with a valid value",
            refusal=True,
        )
    values = list(stored.values)
    current = values[position - 1]
    if current.authority == facts and (
        semantic_sha256 is None or current.design_semantic_sha256 == semantic_sha256
    ):
        return stored
    values[position - 1] = replace(
        current,
        authority=facts,
        design_semantic_sha256=semantic_sha256,
    )
    bound = rewrite_constructed_handover(
        root, stored.raw, stored.request, tuple(values)
    )
    if (
        authority_persisted
        and isinstance(bound, Blocked)
        and bound.what == "HandoverDrift"
    ):
        return Blocked(bound.what, bound.why, bound.how)
    return bound


def bind_shared_design(
    root: Path,
    stored: StoredHandover,
    shared: SharedDesign,
    *,
    scope: DocumentScope,
) -> StoredHandover | Blocked:
    """CAS the shared binding, and the scope when it is first constructed.

    The only writer that changes ``shared_design``; values, design facts,
    acceptance and selections are re-encoded from ``stored`` untouched.
    """
    if stored.shared_design == shared and stored.scope == scope:
        return stored
    feature_id = (
        scope.feature_id
        if isinstance(scope, Feature)
        else None
        if isinstance(scope, Project)
        else scope
    )
    raw = _canonical_bytes(
        stored.request, stored.values, feature_id=feature_id, shared=shared
    )
    validated = read_handover(raw)
    if isinstance(validated, Blocked):
        return validated
    replaced = replace_exact_bytes(
        handover_path(root),
        stored.raw,
        raw,
        unavailable="HandoverUnavailable",
        repair="restore handover storage",
        drift="HandoverDrift",
        drift_subject="handover",
    )
    if replaced is not None:
        return replaced
    return StoredHandover(stored.request, stored.values, raw, scope, shared)


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
