"""The closed v1 DESIGN-document semantic value and its two projections."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import asdict, dataclass, replace
from functools import partial
from typing import TYPE_CHECKING, Generic, TypeVar

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
    target_acceptance_support_conflict,
    target_acceptance_support_conflict_text,
)
from des.domain.input_defects import Defects, InputDefects
from des.ports.driven_ports.task_invocation_port import (
    MUTABLE_TARGET_DECISIONS,
    AgreementParty,
    ApplicableADR,
    ApplicableAgreementAnalysis,
    ApplicableArchitecturalTests,
    ApplicableContractTests,
    ApplicableImpactClosure,
    ApplicablePrefactoring,
    ArchitecturalTestObligation,
    ContractTestObligation,
    DesignFacts,
    DesignTarget,
    ImpactItem,
    LegacyDesignFacts,
    NotApplicable,
    PublicOracle,
    ReuseAnalysis,
    ReuseCandidate,
    UnassessedDesignDecision,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence


class DesignDocumentInvalid(InputDefects):
    """The supplied document is not a member of the closed v1 language."""


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DesignDocumentInvalid(f"{name} must be an object")
    return value


def _keys(value: dict[str, object], keys: set[str], name: str) -> None:
    if set(value) != keys:
        raise DesignDocumentInvalid(f"{name} must contain exactly {sorted(keys)}")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise DesignDocumentInvalid(f"{name} must be a non-empty string")
    return normalized


def _duplicates(values: tuple[object, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise DesignDocumentInvalid(f"{name} must not contain duplicate entries")


def _path(value: object, name: str) -> str:
    path = _text(value, name)
    if not is_repository_relative_whole_file_locator(path):
        raise DesignDocumentInvalid(f"{name} must be a repository-relative path")
    return path


_ORACLE_SHAPE = (
    "a repository-relative DESIGN oracle locator: the whole file "
    "(`test/orders.ml`) or the file with an optional `::selector` "
    "(`tests/orders.rs::reject_cancelled`); native runner targets select that file; "
    "a `:line` suffix is not accepted"
)


def _oracle(value: object, name: str) -> str:
    locator = _text(value, name)
    if not is_design_oracle_locator(locator):
        raise DesignDocumentInvalid(f"{name} must be {_ORACLE_SHAPE}")
    return locator


def _reuse_locator(value: object, name: str) -> str:
    locator = _text(value, name)
    path, separator, line = locator.rpartition(":")
    if (
        not separator
        or not line.isdecimal()
        or int(line) < 1
        or not is_repository_relative_whole_file_locator(path)
    ):
        raise DesignDocumentInvalid(
            f"{name} must be a repository-relative path and positive line"
        )
    return locator


def _impact_locator(value: object, name: str) -> str:
    locator = _text(value, name)
    if is_repository_relative_whole_file_locator(locator):
        return locator
    try:
        return _reuse_locator(locator, name)
    except DesignDocumentInvalid:
        raise DesignDocumentInvalid(
            f"{name} must be a repository-relative path, optionally followed by :line"
        ) from None


T = TypeVar("T")


class _Form(Generic[T]):
    """One finite input form which can both decode and describe itself."""

    def decode(self, value: object, name: str) -> T:
        raise NotImplementedError

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class _Leaf(_Form[T]):
    """A scalar whose semantic predicate is already part of this language."""

    description: str
    decoder: Callable[[object, str], T]

    def decode(self, value: object, name: str) -> T:
        return self.decoder(value, name)

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        return (self.description,)


@dataclass(frozen=True, slots=True)
class _Field:
    name: str
    form: _Form[object]
    optional: bool = False
    #: A cross-field admission rule the decoder enforces on this field and the
    #: form alone cannot state, printed with the field so a producer learns it
    #: before submitting rather than from a refusal.
    note: str = ""

    def headline(self, described: str) -> str:
        """The form's first described line, followed by this field's note."""
        head = described.lstrip()
        if not self.note:
            return head
        return f"{head.rstrip('.')}; {self.note}."


@dataclass(frozen=True, slots=True)
class _Product(_Form[dict[str, object]]):
    """A closed object with ordered, named child forms."""

    fields: tuple[_Field, ...]

    def decode(self, value: object, name: str) -> dict[str, object]:
        decoded = _object(value, name)
        defects = Defects(DesignDocumentInvalid)
        fields = self.decode_into(decoded, name, defects)
        defects.close()
        return fields

    def decode_into(
        self, decoded: dict[str, object], name: str, defects: Defects
    ) -> dict[str, object]:
        """Decode every present field, recording the key-set and field defects.

        A refused or absent field is ``None``: a present field that decodes is
        never ``None``, so a caller can tell which cross-field rules may run.
        """
        required = {field.name for field in self.fields if not field.optional}
        allowed = {field.name for field in self.fields}
        if not required <= set(decoded) <= allowed:
            defects.add(
                f"{name} must contain {sorted(required)}; optional: {sorted(allowed - required)}"
            )
        return self.decode_fields(decoded, name, defects)

    def decode_fields(
        self, decoded: dict[str, object], name: str, defects: Defects
    ) -> dict[str, object]:
        return {
            field.name: defects.take(
                partial(field.form.decode, decoded[field.name], f"{name}.{field.name}")
            )
            if field.name in decoded
            else None
            for field in self.fields
        }

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        prefix = " " * indent
        lines: list[str] = [f"{prefix}object with exactly:"]
        for field in self.fields:
            child = field.form.describe(indent + 2)
            qualifier = " (optional)" if field.optional else ""
            lines.append(
                f"{prefix}- `{field.name}`{qualifier}: {field.headline(child[0])}"
            )
            lines.extend(child[1:])
        return tuple(lines)


def _frozen(value: object) -> object:
    if isinstance(value, dict):
        return tuple((key, _frozen(item)) for key, item in value.items())
    if isinstance(value, tuple):
        return tuple(_frozen(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class _ListOf(_Form[tuple[object, ...]]):
    """A list form that owns its element form and collection predicates."""

    item: _Form[object]
    non_empty: bool = True
    unique: bool = True
    collection: str = "list"
    identity: Callable[[object], object] = _frozen

    def decode(self, value: object, name: str) -> tuple[object, ...]:
        if not isinstance(value, list) or (self.non_empty and not value):
            qualifier = "non-empty " if self.non_empty else ""
            raise DesignDocumentInvalid(f"{name} must be a {qualifier}list")
        defects = Defects(DesignDocumentInvalid)
        decoded = tuple(
            defects.take(partial(self.item.decode, item, f"{name}[{index}]"))
            for index, item in enumerate(value)
        )
        # Duplicates are judged only over a wholly decoded list.
        defects.close()
        if self.unique:
            _duplicates(tuple(self.identity(item) for item in decoded), name)
        return decoded

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        qualifiers = []
        if self.non_empty:
            qualifiers.append("non-empty")
        if self.unique:
            qualifiers.append("unique")
        qualifier = " ".join(qualifiers)
        head = f"{qualifier} {self.collection}".strip()
        child = self.item.describe(indent + 2)
        return (f"{head} of {child[0].lstrip()}", *child[1:])


@dataclass(frozen=True, slots=True)
class _Choice(_Form[object]):
    """Either an enum leaf or a tagged set of closed product alternatives."""

    alternatives: tuple[str, ...] = ()
    tag: str | None = None
    products: tuple[tuple[str, _Product], ...] = ()

    def decode(self, value: object, name: str) -> object:
        if self.tag is None:
            decoded = _text(value, name)
            if decoded not in self.alternatives:
                correction = (
                    "; consultation belongs in reuse_analysis.candidates, not targets; "
                    "submit corrected declarations through des design --repo-root ROOT --value N --input -"
                    if self is _TARGET_DECISION or self is _PRODUCT_CHANGE
                    else ""
                )
                raise DesignDocumentInvalid(
                    f"WHAT: {name} is not supported; WHY: supplied {decoded!r}, "
                    f"expected {self.alternatives!r}; HOW: choose a supported alternative{correction}"
                )
            return decoded
        decoded = _object(value, name)
        selected = _text(decoded.get(self.tag), f"{name}.{self.tag}")
        for label, product in self.products:
            if selected == label:
                defects = Defects(DesignDocumentInvalid)
                defects.take(
                    partial(
                        _keys,
                        decoded,
                        {self.tag, *(field.name for field in product.fields)},
                        name,
                    )
                )
                fields = product.decode_fields(decoded, name, defects)
                defects.close()
                return {self.tag: label, **fields}
        raise DesignDocumentInvalid(f"{name}.{self.tag} is not supported")

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        if self.tag is None:
            return (" or ".join(f"`{item}`" for item in self.alternatives),)
        prefix = " " * indent
        lines = [f"{prefix}tagged object on `{self.tag}`:"]
        for label, product in self.products:
            lines.append(f"{prefix}- `{label}`:")
            lines.append(f"{' ' * (indent + 2)}object with exactly:")
            lines.append(f"{' ' * (indent + 2)}- `{self.tag}`: `{label}`")
            for field in product.fields:
                child = field.form.describe(indent + 4)
                lines.append(
                    f"{' ' * (indent + 2)}- `{field.name}`: {field.headline(child[0])}"
                )
                lines.extend(child[1:])
        return tuple(lines)


def _plain_heading(value: object, name: str) -> str:
    heading = _text(value, name)
    if "\n" in heading or "\r" in heading or heading.startswith("#"):
        raise DesignDocumentInvalid(
            f"{name} must be plain text, not a Markdown heading"
        )
    return heading


_TEXT = _Leaf("non-empty text.", _text)
_PATH = _Leaf("repository-relative file path.", _path)
_ORACLE = _Leaf(f"{_ORACLE_SHAPE}.", _oracle)
_REUSE_LOCATOR = _Leaf("repository-relative path and positive line.", _reuse_locator)
_SCHEMA_VERSION = _Leaf(
    "integer `1`.",
    lambda value, name: (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value == 1
        else (_ for _ in ()).throw(DesignDocumentInvalid(f"{name} must be 1"))
    ),
)
_PARADIGM = _Choice(("object_oriented", "functional", "procedural"))
_TARGET_DECISION = _Choice(MUTABLE_TARGET_DECISIONS)
_PRODUCT_CHANGE = _Choice(("required", "none"))
_REUSE_DECISION = _Choice(("REUSE", "EXTEND", "REPLACE", "CREATE_NEW"))
_FAILURE_OUTCOME = _Choice(("Refusal", "Retry", "Indeterminate"))

_TEXTS = _ListOf(_TEXT)
_PATHS = _ListOf(_PATH, non_empty=False)
#: Both rules are refused by `DesignDocument.from_json`; stated here so the
#: generated grammar teaches them before a submission (native architect runs
#: listed the oracle's own file as a support, and an EXTEND target as one).
_SUPPORTS_NOTE = (
    "only acceptance-owned fixtures the oracle needs before craft: never the "
    "`oracle`'s own file and never a `targets` path (a production module the "
    "oracle imports is a target)"
)


def _argv_token(value: object, name: str) -> str:
    text = _text(value, name)
    if "\x00" in text:
        raise DesignDocumentInvalid(
            f"{name} must not contain a NUL character: no process can receive it"
        )
    return text


_ARGV_TOKEN = _Leaf("non-empty text without NUL.", _argv_token)
#: One argv: tokens may repeat (`-q -q`, `-k a -k b` are real commands).
_ARGV = _ListOf(_ARGV_TOKEN, collection="argv list", unique=False)
#: The one public native argv contract: distinct whole argv lists.
NATIVE_VERIFICATION = _ListOf(_ARGV)
_VERIFICATION = NATIVE_VERIFICATION


def native_verification_defect(verification: object) -> str | None:
    """The WHAT/WHY/HOW defect of typed native argv lists, or None if valid."""
    try:
        NATIVE_VERIFICATION.decode(
            [list(argv) for argv in verification],  # type: ignore[attr-defined]
            "verification",
        )
    except DesignDocumentInvalid as error:
        return (
            f"{error}: every declared native command runs once as text tokens; "
            "remove the NUL character or the repeated whole argv"
        )
    except TypeError as error:
        return f"verification must be a list of argv lists: {error}"
    return None


_ORACLE_VERIFICATION_INDEX = _Leaf(
    "non-negative integer.",
    lambda value, name: (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else (_ for _ in ()).throw(
            DesignDocumentInvalid(f"{name} must be a non-negative integer")
        )
    ),
)
_TARGET = _Product(
    (
        _Field("path", _PATH),
        _Field("decision", _TARGET_DECISION),
        _Field("reason", _TEXT),
    )
)
_TARGETS = _ListOf(
    _TARGET,
    non_empty=False,
    collection="list with distinct paths",
    identity=lambda item: item["path"],  # type: ignore[index]
)
_REUSE_CANDIDATE = _Product(
    (
        _Field("symbol", _TEXT),
        _Field("locator", _REUSE_LOCATOR),
        _Field("decision", _REUSE_DECISION),
        _Field("reason", _TEXT),
    )
)
_REUSE_ANALYSIS = _Product(
    (
        _Field(
            "candidates",
            _ListOf(
                _REUSE_CANDIDATE,
                non_empty=False,
            ),
        ),
    )
)
_PREFACTORING = _Choice(
    tag="applicability",
    products=(
        (
            "applicable",
            _Product(
                (
                    _Field("existing_oracle", _ORACLE),
                    _Field("move", _TEXT),
                    _Field("preserved_observation", _TEXT),
                    _Field("verification", _VERIFICATION),
                    _Field(
                        "acceptance_supports",
                        _PATHS,
                        note="never `existing_oracle`'s own file",
                    ),
                )
            ),
        ),
        (
            "not_applicable",
            _Product((_Field("reason", _TEXT),)),
        ),
    ),
)
_AGREEMENT_ROLE = _Choice(("producer", "consumer"))
_AGREEMENT_DECISION = _Choice(("MIGRATED", "UNCHANGED_COMPATIBLE", "INCOMPATIBLE"))
_AGREEMENT_PARTY = _Product(
    (
        _Field("contract", _TEXT),
        _Field("role", _AGREEMENT_ROLE),
        _Field("locator", _REUSE_LOCATOR),
        _Field("decision", _AGREEMENT_DECISION),
        _Field("reason", _TEXT),
    )
)
_AGREEMENT_ANALYSIS = _Choice(
    tag="applicability",
    products=(
        (
            "applicable",
            _Product((_Field("parties", _ListOf(_AGREEMENT_PARTY)),)),
        ),
        (
            "not_applicable",
            _Product((_Field("reason", _TEXT),)),
        ),
    ),
)
_FAILURE = _Product(
    (
        _Field("condition", _TEXT),
        _Field("outcome", _FAILURE_OUTCOME),
        _Field("observation", _TEXT),
    )
)
_BOUNDARIES = _Choice(
    tag="applicability",
    products=(
        (
            "applicable",
            _Product(
                (
                    _Field("driving_port", _TEXT),
                    _Field("driven_ports", _TEXTS),
                    _Field("dependency_direction", _TEXT),
                    _Field("failures", _ListOf(_FAILURE)),
                )
            ),
        ),
        (
            "not_applicable",
            _Product((_Field("reason", _TEXT),)),
        ),
    ),
)
_PUBLIC_ORACLE = _Product(
    (
        _Field("observation", _TEXT),
        _Field("stimulus", _TEXT),
        _Field("expected", _TEXT),
        _Field("falsifier", _TEXT),
    )
)
_AUTHORITY = _Product(
    (
        _Field(
            "heading",
            _Leaf("plain non-empty text, not a Markdown heading.", _plain_heading),
        ),
    )
)


def _applicability(form: _Product) -> _Choice:
    return _Choice(
        tag="applicability",
        products=(
            ("applicable", form),
            ("not_applicable", _Product((_Field("reason", _TEXT),))),
        ),
    )


_ARCHITECTURAL_OBLIGATION = _Product(
    (
        _Field("obligation", _TEXT),
        _Field("oracle", _ORACLE),
        _Field("verification_index", _ORACLE_VERIFICATION_INDEX),
    )
)
_CONTRACT_OBLIGATION = _Product(
    (
        _Field("obligation", _TEXT),
        _Field("contract", _TEXT),
        _Field("producer", _REUSE_LOCATOR),
        _Field("consumer", _REUSE_LOCATOR),
        _Field("observation", _TEXT),
        _Field("oracle", _ORACLE),
        _Field("verification_index", _ORACLE_VERIFICATION_INDEX),
    )
)
_ARCHITECTURAL_TESTS = _applicability(
    _Product((_Field("obligations", _ListOf(_ARCHITECTURAL_OBLIGATION)),))
)
_CONTRACT_TESTS = _applicability(
    _Product((_Field("obligations", _ListOf(_CONTRACT_OBLIGATION)),))
)
_ADR = _applicability(
    _Product(
        (
            _Field("context", _TEXT),
            _Field("decision", _TEXT),
            _Field("alternatives", _TEXTS),
            _Field("consequences", _TEXTS),
            _Field(
                "status", _Choice(("proposed", "accepted", "superseded", "deprecated"))
            ),
        )
    )
)
#: Language-neutral roles a reached locator can play.  The software never maps
#: a file name to a role: the architect classifies, and the closure rule below
#: only demands that nothing the DESIGN names or reaches is left unclassified.
_IMPACT_KIND = _Choice(
    (
        "public_interface",
        "consumer",
        "test",
        "fixture",
        "export",
        "discovery",
        "build_metadata",
        "manifest",
        "lock",
        "runtime",
    )
)
_IMPACT_DECISION = _Choice(("CHANGED", "MIGRATED", "UNCHANGED_COMPATIBLE"))
_IMPACT_LOCATOR = _Leaf(
    "repository-relative path, optionally followed by `:line`.", _impact_locator
)
_IMPACT_ITEM = _Product(
    (
        _Field("kind", _IMPACT_KIND),
        _Field("locator", _IMPACT_LOCATOR),
        _Field("decision", _IMPACT_DECISION),
        _Field("reason", _TEXT),
    )
)
_IMPACT_CLOSURE = _applicability(
    _Product(
        (
            _Field(
                "items",
                _ListOf(
                    _IMPACT_ITEM,
                    collection="list with distinct locators",
                    identity=lambda item: item["locator"],  # type: ignore[index]
                ),
            ),
        )
    )
)
_DECISION_FIELDS = (
    _Field("architectural_tests", _ARCHITECTURAL_TESTS),
    _Field("contract_tests", _CONTRACT_TESTS),
    _Field("prefactoring", _PREFACTORING),
    _Field("agreement_analysis", _AGREEMENT_ANALYSIS),
    _Field("reuse_analysis", _REUSE_ANALYSIS),
    _Field("impact_closure", _IMPACT_CLOSURE),
    _Field("adr", _ADR, optional=True),
)
_DESIGN_DECISIONS = _Product(_DECISION_FIELDS)


def _architect_handoff_input(value: object, name: str) -> dict:
    from des.application.architect_handoff import decode, wire

    try:
        return wire(decode(value))
    except ValueError as error:
        raise DesignDocumentInvalid(f"{name}: {error}") from error


_ARCHITECT_HANDOFF = _Leaf(
    "typed architect sections from `des handoff describe`; raw model text is retained.",
    _architect_handoff_input,
)


_MANIFEST = _Product(
    (
        _Field("schema_version", _SCHEMA_VERSION),
        _Field("authority", _AUTHORITY),
        _Field("purpose", _TEXT),
        _Field("constraints", _TEXTS),
        _Field(
            "product_change",
            _PRODUCT_CHANGE,
            optional=True,
            note="omission means required with a mutable production target excluding the oracle; none requires targets=[]; consultation belongs in reuse_analysis.candidates",
        ),
        _Field("targets", _TARGETS),
        _Field("paradigm", _PARADIGM),
        _Field("decisions", _TEXTS),
        _Field("reuse_analysis", _REUSE_ANALYSIS),
        _Field("prefactoring", _PREFACTORING),
        _Field("agreement_analysis", _AGREEMENT_ANALYSIS),
        _Field("architectural_tests", _ARCHITECTURAL_TESTS),
        _Field("contract_tests", _CONTRACT_TESTS),
        _Field("adr", _ADR, optional=True),
        _Field("architect_handoff", _ARCHITECT_HANDOFF, optional=True),
        _Field("impact_closure", _IMPACT_CLOSURE),
        _Field("boundaries", _BOUNDARIES),
        _Field("public_oracle", _PUBLIC_ORACLE),
        _Field("oracle", _ORACLE),
        _Field(
            "acceptance_supports",
            _PATHS,
            note=_SUPPORTS_NOTE,
        ),
        _Field("verification", _VERIFICATION),
        _Field("oracle_verification_index", _ORACLE_VERIFICATION_INDEX),
    )
)


def design_decisions_wire(facts: DesignFacts) -> dict[str, object]:
    """Lossless JSON projection shared by every typed-fact transport."""

    def wire(value: object) -> object:
        if isinstance(value, dict):
            return {key: wire(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [wire(item) for item in value]
        return value

    projection = {
        field.name: wire(asdict(getattr(facts, field.name)))
        for field in _DECISION_FIELDS
        if getattr(facts, field.name) is not None
        and not isinstance(getattr(facts, field.name), UnassessedDesignDecision)
    }
    if facts.architect_handoff is not None:
        from des.application.architect_handoff import wire as handoff_wire

        projection["architect_handoff"] = handoff_wire(facts.architect_handoff)
    return projection


def _decode_architect_handoff(raw: object) -> dict:
    from des.application.architect_handoff import decode

    try:
        return decode(raw)
    except ValueError as error:
        raise DesignDocumentInvalid(str(error)) from error


def decode_design_decisions(
    raw: dict[str, object], *, historical: bool = False
) -> dict[str, object]:
    """Decode required decisions with the constructor's sole grammar."""
    selected = {
        field.name: raw[field.name] for field in _DECISION_FIELDS if field.name in raw
    }
    form = _DESIGN_DECISIONS
    if historical:
        form = _Product(
            tuple(replace(field, optional=True) for field in _DECISION_FIELDS)
        )
    decoded = form.decode(selected, "design")
    return {
        name: _decision_record(name, decision) for name, decision in decoded.items()
    }


_APPLICABLE_LISTS = {
    "architectural_tests": (
        ApplicableArchitecturalTests,
        "obligations",
        ArchitecturalTestObligation,
    ),
    "contract_tests": (ApplicableContractTests, "obligations", ContractTestObligation),
    "agreement_analysis": (ApplicableAgreementAnalysis, "parties", AgreementParty),
    "impact_closure": (ApplicableImpactClosure, "items", ImpactItem),
}


def _decision_record(name: str, decision: object) -> object:
    """The domain record of one decoded decision; ``None`` is an absent one."""
    if decision is None:
        return None if name == "adr" else UnassessedDesignDecision()
    if name == "reuse_analysis":
        return ReuseAnalysis(
            tuple(ReuseCandidate(**item) for item in decision["candidates"])  # type: ignore[index]
        )
    if decision["applicability"] == "not_applicable":  # type: ignore[index]
        return NotApplicable(decision["reason"])  # type: ignore[index]
    if name in _APPLICABLE_LISTS:
        record_type, member, item_type = _APPLICABLE_LISTS[name]
        return record_type(tuple(item_type(**item) for item in decision[member]))  # type: ignore[index]
    record_type = ApplicablePrefactoring if name == "prefactoring" else ApplicableADR
    return record_type(
        **{
            key: item
            for key, item in decision.items()  # type: ignore[attr-defined]
            if key != "applicability"
        }
    )


def design_decisions_defect(
    facts: DesignFacts, *, historical: bool = False
) -> str | None:
    """Validate shape and declared linkage, not whether a check is sufficient."""
    defects = design_decisions_defects(facts, historical=historical)
    return str(DesignDocumentInvalid(*defects)) if defects else None


def design_decisions_defects(
    facts: DesignFacts, *, historical: bool = False
) -> tuple[str, ...]:
    """Every shape and declared-linkage defect of ``facts``, found in one pass."""
    if isinstance(facts, LegacyDesignFacts) and not historical:
        return (
            f"historical DESIGN decisions are unassessed: {', '.join(facts.missing_decisions)}; "
            "reconstruct complete DESIGN with --replace-current --input - before reusing delivery proof",
        )
    try:
        decisions = decode_design_decisions(
            design_decisions_wire(facts), historical=historical
        )
    except DesignDocumentInvalid as error:
        return error.defects
    except (TypeError, AttributeError) as error:
        return (str(error),)
    found: list[str] = []
    try:
        for defect in _decision_rule_defects(
            decisions, facts.targets, facts.verification
        ):
            found.append(defect)
    except (TypeError, AttributeError) as error:
        found.append(str(error))
    return tuple(found)


def _unlinked_party_defect(
    role: str,
    obligation: ContractTestObligation,
    parties: tuple[AgreementParty, ...],
) -> str:
    """The unlinked contract party, with the parties the analysis does declare."""
    defect = (
        f"contract_tests.{role} must name an agreement party for {obligation.contract}"
    )
    declared = tuple(
        f"`{party.locator}`"
        for party in parties
        if party.contract == obligation.contract and party.role == role
    )
    if declared:
        return (
            f"{defect}: agreement_analysis declares {role} {', '.join(declared)} "
            f"for that contract, not `{getattr(obligation, role)}`"
        )
    elsewhere = tuple(
        f"`{party.locator}` for `{party.contract}`"
        for party in parties
        if party.role == role
    )
    return f"{defect}: agreement_analysis declares no {role} for that contract" + (
        f"; its {role} parties are {', '.join(elsewhere)}" if elsewhere else ""
    )


def _decision_rule_defects(
    decisions: Mapping[str, object],
    targets: Iterable[DesignTarget] | None,
    verification: Sequence[object] | None,
) -> Iterator[str]:
    """Each declared-linkage defect among the decided ``decisions``.

    A decision missing from ``decisions``, or ``None`` targets or verification,
    was itself refused: a rule needing it does not run, so no defect is
    reported only because another field failed.
    """
    agreement = decisions.get("agreement_analysis")
    for name in ("architectural_tests", "contract_tests"):
        decision = decisions.get(name)
        if decision is None or isinstance(
            decision, (NotApplicable, UnassessedDesignDecision)
        ):
            continue
        contract = name == "contract_tests"
        if contract and isinstance(
            agreement, (NotApplicable, UnassessedDesignDecision)
        ):
            yield "contract_tests requires applicable agreement_analysis"
        for obligation in decision.obligations:  # type: ignore[attr-defined]
            if verification is not None and obligation.verification_index >= len(
                verification
            ):
                yield f"{name}.verification_index must name one declared verification command"
            if not contract or not isinstance(agreement, ApplicableAgreementAnalysis):
                continue
            for role in ("producer", "consumer"):
                locator = getattr(obligation, role)
                if not any(
                    party.contract == obligation.contract
                    and party.role == role
                    and party.locator == locator
                    for party in agreement.parties
                ):
                    yield _unlinked_party_defect(role, obligation, agreement.parties)
    prefactoring = decisions.get("prefactoring")
    if (
        isinstance(prefactoring, ApplicablePrefactoring)
        and prefactoring.existing_oracle.partition("::")[0]
        in prefactoring.acceptance_supports
    ):
        yield "prefactoring.acceptance_supports cannot include its own oracle"
    consumers = (
        tuple(
            dict.fromkeys(
                party.locator for party in agreement.parties if party.role == "consumer"
            )
        )
        if isinstance(agreement, ApplicableAgreementAnalysis)
        else ()
    )
    closure = decisions.get("impact_closure")
    if isinstance(closure, NotApplicable) and consumers:
        yield (
            "impact_closure is not_applicable while agreement_analysis declares "
            f"consumers {', '.join(consumers)}: a consumer is reached by the "
            "change, so its disposition cannot be waived; declare impact_closure "
            "applicable with one item per consumer locator (kind, decision, reason)"
        )
    if isinstance(closure, ApplicableImpactClosure):
        dispositions = {item.locator for item in closure.items}
        missing = tuple(
            dict.fromkeys(
                (
                    *(
                        target.path
                        for target in targets or ()
                        if target.path not in dispositions
                    ),
                    *(locator for locator in consumers if locator not in dispositions),
                )
            )
        )
        if missing:
            yield (
                "impact_closure is not closed: no disposition for "
                f"{', '.join(missing)}; a target or consumer without a CHANGED, "
                "MIGRATED or UNCHANGED_COMPATIBLE disposition leaves its "
                "downstream impact unproven before craft; add one "
                "impact_closure item per listed locator naming its kind, "
                "decision and reason"
            )


def product_change_defect(
    product_change: object, targets: tuple[DesignTarget, ...], oracle: str
) -> str | None:
    correction = (
        "HOW: submit product_change=none with targets=[] and consultation in "
        "reuse_analysis.candidates, or required with real EXTEND/CREATE_NEW "
        "production targets through des design --repo-root ROOT --value N --input -"
    )
    if product_change not in ("required", "none"):
        return f"WHAT: product_change is invalid; WHY: supplied {product_change!r}; {correction}"
    invalid = tuple(
        target for target in targets if target.decision not in MUTABLE_TARGET_DECISIONS
    )
    if invalid:
        return (
            "WHAT: targets[].decision is invalid; WHY: "
            + ", ".join(f"{target.path} ({target.decision})" for target in invalid)
            + "; "
            + correction
        )
    if product_change == "none" and targets:
        return (
            "WHAT: product_change/targets conflict; WHY: none declares mutation paths "
            + ", ".join(target.path for target in targets)
            + "; "
            + correction
        )
    if product_change == "required" and not any(
        target.path != oracle.partition("::")[0] for target in targets
    ):
        return (
            "WHAT: product_change/targets lack a mutable production target; "
            f"WHY: required declares {[target.path for target in targets]!r}, "
            f"excluding immutable oracle {oracle}; {correction}"
        )
    return None


def _manifest_rule_defects(root: Mapping[str, object]) -> Iterator[str]:
    """Each cross-field defect of a manifest whose own fields decoded.

    ``root`` maps a refused or absent field to ``None``; a rule whose inputs
    include one does not run.
    """
    oracle = root["oracle"]
    supports = root["acceptance_supports"]
    targets = root["targets"]
    verification = root["verification"]
    index = root["oracle_verification_index"]
    if targets is not None and oracle is not None:
        defect = product_change_defect(
            root.get("product_change") or "required",
            tuple(DesignTarget(item["path"], item["decision"]) for item in targets),
            oracle,
        )
        if defect is not None:
            yield defect
    if index is not None and verification is not None and index >= len(verification):  # type: ignore[operator, arg-type]
        yield "manifest.oracle_verification_index must name one declared verification command"
    if oracle is not None and supports is not None:
        oracle_file = oracle.partition("::")[0]  # type: ignore[attr-defined]
        if oracle_file in supports:  # type: ignore[operator]
            yield (
                "manifest.acceptance_supports must not list the oracle's own "
                f"file, which is never its own support: {oracle_file}"
            )
        for target in targets or ():  # type: ignore[attr-defined]
            conflict = target_acceptance_support_conflict(
                oracle,  # type: ignore[arg-type]
                (target["path"],),
                supports,  # type: ignore[arg-type]
            )
            if conflict is not None:
                yield (
                    "manifest.acceptance_supports: "
                    + target_acceptance_support_conflict_text(conflict)
                )
    yield from _decision_rule_defects(
        {
            field.name: _decision_record(field.name, root[field.name])
            for field in _DECISION_FIELDS
            if root[field.name] is not None
        },
        None
        if targets is None
        else tuple(
            DesignTarget(item["path"], item["decision"])  # type: ignore[index]
            for item in targets  # type: ignore[attr-defined]
        ),
        verification,  # type: ignore[arg-type]
    )


def _form_schema(form: _Form[object]) -> dict[str, object]:
    """Compile a descriptor without changing its constructor admission."""
    if isinstance(form, _Product):
        return {
            "type": "object",
            "properties": {
                field.name: {
                    **_form_schema(field.form),
                    **({"description": field.note} if field.note else {}),
                }
                for field in form.fields
            },
            "required": [field.name for field in form.fields if not field.optional],
            "additionalProperties": False,
        }
    if isinstance(form, _ListOf):
        return {
            "type": "array",
            "items": _form_schema(form.item),
            "minItems": int(form.non_empty),
            "uniqueItems": form.unique,
        }
    if isinstance(form, _Choice):
        if form.tag is None:
            return {"type": "string", "enum": list(form.alternatives)}
        alternatives = []
        for label, product in form.products:
            compiled = _form_schema(product)
            alternatives.append(
                {
                    **compiled,
                    "properties": {
                        form.tag: {"type": "string", "const": label},
                        **compiled["properties"],
                    },
                    "required": [form.tag, *compiled["required"]],
                }
            )
        return {"anyOf": alternatives}
    if form is _SCHEMA_VERSION:
        return {"type": "integer", "const": 1}
    if form is _ORACLE_VERIFICATION_INDEX:
        return {"type": "integer", "minimum": 0}
    if form is _ARCHITECT_HANDOFF:
        from des.application.architect_handoff import input_schema

        return input_schema()
    if form in (_ORACLE, _PATH, _REUSE_LOCATOR, _IMPACT_LOCATOR):
        from des.domain.architecture_brief_resolver import (
            DESIGN_ORACLE_LOCATOR_PATTERN,
            REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN,
        )

        pattern = REPOSITORY_RELATIVE_WHOLE_FILE_PATTERN
        if form is _ORACLE:
            pattern = DESIGN_ORACLE_LOCATOR_PATTERN
        if form is _REUSE_LOCATOR:
            pattern = pattern[:-1] + r":[1-9][0-9]*$"
        if form is _IMPACT_LOCATOR:
            pattern = pattern[:-1] + r"(?::[1-9][0-9]*)?$"
        return {"type": "string", "pattern": pattern}
    if form is _ARGV_TOKEN:
        return {
            "type": "string",
            "minLength": 1,
            "pattern": r"^[^\u0000]*[^\s\u0000][^\u0000]*$",
        }
    if isinstance(form, _Leaf) and form.decoder is _plain_heading:
        return {
            "type": "string",
            "pattern": r"^(?!\s*#)[^\r\n]*\S[^\r\n]*$",
        }
    if form is not _TEXT:
        raise TypeError(f"Unsupported DESIGN scalar form: {form!r}")
    return {"type": "string", "minLength": 1, "pattern": r"\S"}


_WRAP_WIDTH = 80

#: A word that CommonMark could read as a block start when it opens a line:
#: a bullet, an ATX heading, a block quote, an ordered-list marker, a fence,
#: or a setext underline / thematic break made of one repeated character.
_BLOCK_START = re.compile(
    r"[-+*]$|#{1,6}$|>|\d{1,9}[.)]$|`{3}|~{3}|=+$|-+$|\*{3,}$|_{3,}$"
)
_ORDERED_MARKER = re.compile(r"\d{1,9}(?=[.)]$)")
_FENCE_RUN = re.compile(r"`{3,}|~{3,}")
_LINE_BREAKS = re.compile(r"\r\n|\r|\n")
_WHITESPACE = re.compile(r"\s+")


def _code_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Half-open index ranges of CommonMark backtick code spans in ``text``.

    A backtick run opens a span only when a later run of the same length
    closes it; an unmatched run is literal.  A backslash outside a span
    escapes the next character, so an escaped backtick opens nothing.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] != "`":
            index += 1
            continue
        run_end = index
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        closer = None
        cursor = run_end
        while cursor < len(text):
            if text[cursor] != "`":
                cursor += 1
                continue
            candidate = cursor
            while candidate < len(text) and text[candidate] == "`":
                candidate += 1
            if candidate - cursor == run_end - index:
                closer = candidate
                break
            cursor = candidate
        if closer is None:
            index = run_end
        else:
            spans.append((index, closer))
            index = closer
    return tuple(spans)


def _inside(spans: tuple[tuple[int, int], ...], index: int) -> bool:
    return any(start <= index < end for start, end in spans)


def _escape_outside_code(text: str, specials: str) -> str:
    """Backslash-escape ``specials`` everywhere except inside code spans."""
    spans = _code_spans(text)
    return "".join(
        f"\\{char}" if char in specials and not _inside(spans, index) else char
        for index, char in enumerate(text)
    )


def _table_cell(text: str) -> str:
    """One unwrapped table cell: one line, no inline HTML, no cell split.

    GFM splits cells on every unescaped pipe, code spans included, and drops
    the backslash of an escaped one before inline parsing, so a pipe is
    escaped everywhere while ``<`` is escaped only outside code spans.
    """
    return _escape_outside_code(_LINE_BREAKS.sub(" ", text), "<").replace("|", "\\|")


def _neutralized(word: str) -> str:
    """The same rendered text, escaped so it cannot open a block at line start."""
    if not _BLOCK_START.match(word):
        return word
    if marker := _ORDERED_MARKER.match(word):
        return f"{marker.group()}\\{word[marker.end() :]}"
    if fence := _FENCE_RUN.match(word):
        return "".join(f"\\{char}" for char in fence.group()) + word[fence.end() :]
    return f"\\{word}"


def _wrap(text: str, first: str = "", continuation: str = "") -> list[str]:
    """Hard-wrap one prose block at whitespace to at most 80 columns.

    Pure and deterministic.  It never breaks inside a word and never
    hyphenates; a word longer than the width stands alone on its line.  It
    escapes ``<`` outside code spans and never lets a continuation line open
    block markup: outside a code span the opening word is escaped, and inside
    one (where a backslash would be literal) no break is taken there.
    """
    escaped = _escape_outside_code(text.strip(), "<")
    spans = _code_spans(escaped)
    chunks: list[str] = []
    cursor = 0
    for separator in _WHITESPACE.finditer(escaped):
        word = escaped[cursor : separator.start()]
        following = _WHITESPACE.split(escaped[separator.end() :], maxsplit=1)[0]
        cursor = separator.end()
        in_code = _inside(spans, separator.start())
        breakable = (
            separator.group() == " " and not _BLOCK_START.match(following)
            if in_code
            else (len(word) - len(word.rstrip("\\"))) % 2 == 0
        )
        joint = _LINE_BREAKS.sub(" ", separator.group()) if in_code else " "
        if not chunks:
            chunks.append(word)
        else:
            chunks[-1] += word
        if breakable:
            chunks.append("")
        else:
            chunks[-1] += joint
    if chunks:
        chunks[-1] += escaped[cursor:]
    else:
        chunks.append(escaped[cursor:])
    lines = [first + chunks[0]]
    for chunk in chunks[1:]:
        candidate = f"{lines[-1]} {chunk}"
        if len(candidate) <= _WRAP_WIDTH:
            lines[-1] = candidate
        else:
            lines.append(continuation + _neutralized(chunk))
    return lines


def _bullets(items: tuple[str, ...]) -> list[str]:
    """One tight list; continuation lines are indented under the item text."""
    return [line for item in items for line in _wrap(item, "- ", "  ")]


def _fenced(language: str, content: str) -> list[str]:
    """A fence longer than any backtick run inside, so content never closes it."""
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{language}", content, fence]


def _assurance_blocks(facts: DesignFacts, suffix: str = "") -> list[list[str]]:
    blocks: list[list[str]] = []
    for title, decision in (
        ("Architectural tests", facts.architectural_tests),
        ("Contract tests", facts.contract_tests),
    ):
        blocks.append([f"### {title}{suffix}"])
        if isinstance(decision, NotApplicable):
            blocks.append(_wrap(f"Not applicable: {decision.reason}"))
            continue
        blocks.append(
            _wrap(
                "The following checks falsify the declared obligations using the linked native verification command."
            )
        )
        for check in decision.obligations:
            blocks += [
                _wrap(f"Obligation: {check.obligation}"),
                _wrap(f"Test locator: `{check.oracle}`"),
                _wrap(f"Verification command index: `{check.verification_index}`"),
            ]
            if isinstance(check, ContractTestObligation):
                blocks += [
                    _wrap(f"Contract: {check.contract}"),
                    _wrap(
                        f"Producer: `{check.producer}`; consumer: `{check.consumer}`"
                    ),
                    _wrap(f"Observation: {check.observation}"),
                ]
    if facts.adr is not None:
        blocks.append([f"### Architecture decision record{suffix}"])
        if isinstance(facts.adr, NotApplicable):
            blocks.append(_wrap(f"Not applicable: {facts.adr.reason}"))
        else:
            adr = facts.adr
            blocks += [
                _wrap(f"Context: {adr.context}"),
                _wrap(f"Decision: {adr.decision}"),
                _wrap(f"Status: {adr.status}"),
                _wrap("Alternatives considered:"),
                _bullets(adr.alternatives),
                _wrap("Consequences of this decision:"),
                _bullets(adr.consequences),
            ]
    return blocks


def _impact_closure_blocks(facts: DesignFacts, suffix: str = "") -> list[list[str]]:
    closure = facts.impact_closure
    if isinstance(closure, UnassessedDesignDecision):
        return []
    blocks: list[list[str]] = [[f"### Impact closure{suffix}"]]
    if isinstance(closure, NotApplicable):
        blocks.append(_wrap(f"Not applicable: {closure.reason}"))
    else:
        blocks.append(
            _bullets(
                tuple(
                    f"{item.kind}: `{item.locator}`; {item.decision}: {item.reason}"
                    for item in closure.items
                )
            )
        )
    return blocks


def _reuse_blocks(facts: DesignFacts) -> list[list[str]]:
    reuse = facts.reuse_analysis
    if isinstance(reuse, UnassessedDesignDecision):
        return []
    blocks: list[list[str]] = [["### Reuse analysis"]]
    blocks.append(
        _bullets(
            tuple(
                f"{item.symbol}: `{item.locator}`; {item.decision}: {item.reason}"
                for item in reuse.candidates
            )
        )
        or _wrap("No reuse candidates were found.")
    )
    return blocks


def _preservation_commands(facts: DesignFacts) -> list[list[str]]:
    if not isinstance(facts.prefactoring, ApplicablePrefactoring):
        return []
    blocks = [
        _wrap(
            "Preservation uses the same existing test and support content before and after the move, before behavior changes."
        )
    ]
    if facts.prefactoring.acceptance_supports:
        blocks.append(
            _bullets(
                tuple(
                    f"Preservation support: `{path}`"
                    for path in facts.prefactoring.acceptance_supports
                )
            )
        )
    for argv in facts.prefactoring.verification:
        blocks += [
            _wrap("Preservation verification command:"),
            _fenced("sh", shlex.join(argv)),
        ]
    return blocks


@dataclass(frozen=True, slots=True)
class DesignDocument:
    heading: str
    purpose: str
    constraints: tuple[str, ...]
    targets: tuple[tuple[str, str, str], ...]
    paradigm: str
    decisions: tuple[str, ...]
    reuse: tuple[tuple[str, str, str, str], ...]
    prefactoring: tuple[str, ...]
    agreement_analysis: tuple[object, ...]
    boundaries: tuple[str, ...]
    public_oracle: PublicOracle
    facts: DesignFacts
    #: SHA-256 of the complete normalized constructor input, distinct from any
    #: digest of the rendered Markdown, which is lossy (argv boundaries vanish).
    semantic_sha256: str = ""

    def facts_at(self, authority_locator: str) -> DesignFacts:
        """Return this closed document's facts bound to its durable section.

        The configured destination is resolved at the application boundary,
        after this document has validated but before either projection writes.
        It must therefore be carried as data, rather than reconstructed from a
        heading by a later reader.
        """
        return replace(self.facts, authority_locator=authority_locator)

    @classmethod
    def from_json(cls, raw: str) -> DesignDocument:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DesignDocumentInvalid(f"input is not JSON: {error}") from error
        manifest = _object(value, "manifest")
        # An unsupported schema_version is the envelope: no other field is
        # judged against a language the input does not claim.
        if "schema_version" in manifest:
            _SCHEMA_VERSION.decode(
                manifest["schema_version"], "manifest.schema_version"
            )
        defects = Defects(DesignDocumentInvalid)
        root = _MANIFEST.decode_into(manifest, "manifest", defects)
        for defect in _manifest_rule_defects(root):
            defects.add(defect)
        defects.close()
        # An absent new carrier must not invalidate already-bound legacy DESIGN identities.
        identity = {
            key: value
            for key, value in root.items()
            if (key != "architect_handoff" or value is not None)
            and (key != "product_change" or value == "none")
        }
        semantic_sha256 = hashlib.sha256(
            json.dumps(
                identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        # Decoding above is the only validation pass.  Everything below is a
        # projection of normalized descriptor values into domain records.
        authority = root["authority"]  # type: ignore[assignment]
        heading = authority["heading"]  # type: ignore[index]
        purpose = root["purpose"]
        constraints = root["constraints"]
        paradigm = root["paradigm"]
        decisions = root["decisions"]
        oracle = root["oracle"]
        targets = tuple(
            (item["path"], item["decision"], item["reason"])  # type: ignore[index]
            for item in root["targets"]  # type: ignore[union-attr]
        )
        reuse = tuple(
            (item["symbol"], item["locator"], item["decision"], item["reason"])  # type: ignore[index]
            for item in root["reuse_analysis"]["candidates"]  # type: ignore[index]
        )
        prefactoring_root = root["prefactoring"]  # type: ignore[assignment]
        prefactoring = tuple(
            prefactoring_root[key]  # type: ignore[index]
            for key in (
                ("applicability", "existing_oracle", "move", "preserved_observation")
                if prefactoring_root["applicability"] == "applicable"  # type: ignore[index]
                else ("applicability", "reason")
            )
        )
        agreement_root = root["agreement_analysis"]  # type: ignore[assignment]
        if agreement_root["applicability"] == "applicable":  # type: ignore[index]
            agreement_analysis = (
                agreement_root["applicability"],  # type: ignore[index]
                tuple(
                    (
                        party["contract"],  # type: ignore[index]
                        party["role"],  # type: ignore[index]
                        party["locator"],  # type: ignore[index]
                        party["decision"],  # type: ignore[index]
                        party["reason"],  # type: ignore[index]
                    )
                    for party in agreement_root["parties"]  # type: ignore[index]
                ),
            )
        else:
            agreement_analysis = (
                agreement_root["applicability"],  # type: ignore[index]
                agreement_root["reason"],  # type: ignore[index]
            )
        boundaries_root = root["boundaries"]  # type: ignore[assignment]
        if boundaries_root["applicability"] == "applicable":  # type: ignore[index]
            boundaries = (
                boundaries_root["applicability"],  # type: ignore[index]
                f"Driving port: {boundaries_root['driving_port']}",  # type: ignore[index]
                *(f"Driven port: {port}" for port in boundaries_root["driven_ports"]),  # type: ignore[index]
                f"Dependency direction: {boundaries_root['dependency_direction']}",  # type: ignore[index]
                *(
                    "Failure: "
                    f"Condition: {failure['condition']} | Outcome: {failure['outcome']} | "
                    f"Observation: {failure['observation']}"
                    for failure in boundaries_root["failures"]  # type: ignore[index]
                ),
            )
        else:
            boundaries = (
                boundaries_root["applicability"],  # type: ignore[index]
                boundaries_root["reason"],  # type: ignore[index]
            )
        public_oracle_tuple = tuple(
            root["public_oracle"][key]  # type: ignore[index]
            for key in ("observation", "stimulus", "expected", "falsifier")
        )
        public_oracle = PublicOracle(*public_oracle_tuple)
        supports = root["acceptance_supports"]
        verification = root["verification"]
        oracle_verification_index = root["oracle_verification_index"]
        facts = DesignFacts(
            tuple(DesignTarget(path, decision) for path, decision, _ in targets),
            paradigm,
            decisions,
            oracle,
            supports,
            verification,
            oracle_verification_index,
            constraints,
            public_oracle=public_oracle,
            product_change=root.get("product_change") or "required",
            architect_handoff=(
                _decode_architect_handoff(root["architect_handoff"])
                if root.get("architect_handoff") is not None
                else None
            ),
            **{
                field.name: _decision_record(field.name, root[field.name])
                for field in _DECISION_FIELDS
            },
        )
        return cls(
            heading,
            purpose,
            constraints,
            targets,
            paradigm,
            decisions,
            reuse,
            prefactoring,
            agreement_analysis,
            boundaries,
            public_oracle,
            facts,
            semantic_sha256,
        )

    @classmethod
    def input_schema(cls) -> dict[str, object]:
        """The complete closed manifest projected from the constructor forms."""
        return _form_schema(_MANIFEST)

    @classmethod
    def input_description(cls) -> str:
        """The closed v1 input language for the CLI and installed author guidance."""
        return "\n".join(
            (
                "DESIGN constructor input is one strict UTF-8 JSON manifest:",
                *_MANIFEST.describe(),
                "",
                "Impact closure rule: an applicable `impact_closure` must hold one "
                "item for every `targets` path and for every `agreement_analysis` "
                "consumer locator, each with its kind, decision and reason; "
                "`not_applicable` is refused while `agreement_analysis` declares a "
                "consumer.  A manifest with any locator undisposed is refused "
                "before craft, naming every missing locator at once.",
            )
        )

    def markdown(self) -> str:
        """Render the owned section as Markdown a default markdownlint accepts.

        Every block is separated by exactly one blank line, sub-headings carry
        the section heading so several sections in one file stay unique, prose
        is wrapped at 80 columns, and tables and fences are never wrapped.
        """

        def heading(title: str) -> list[str]:
            return [f"### {title} ({self.heading})"]

        def table(header: tuple[str, ...], rows: object) -> list[str]:
            return [
                "| " + " | ".join(header) + " |",
                "|" + "---|" * len(header),
                *(
                    "| " + " | ".join(_table_cell(cell) for cell in row) + " |"
                    for row in rows  # type: ignore[attr-defined]
                ),
            ]

        product_change_blocks = (
            [["Product change: none"], ["No product changes authorized."]]
            if self.facts.product_change == "none"
            else []
        )
        blocks: list[list[str]] = [
            [f"## {self.heading}"],
            *product_change_blocks,
            heading("Purpose"),
            _wrap(self.purpose),
            heading("Constraints"),
            _bullets(self.constraints),
            heading("Targets"),
            table(
                ("Path", "Decision", "Reason"),
                (
                    (f"`{path}`", decision, reason)
                    for path, decision, reason in self.targets
                ),
            ),
            heading("Paradigm"),
            _wrap(self.paradigm),
            heading("Decisions"),
            _bullets(self.decisions),
            heading("Reuse analysis"),
            table(
                ("Symbol", "Locator", "Decision", "Reason"),
                (
                    (symbol, f"`{locator}`", decision, reason)
                    for symbol, locator, decision, reason in self.reuse
                ),
            ),
            heading("Prefactoring"),
        ]
        if self.prefactoring[0] == "not_applicable":
            blocks.append(_wrap(f"Not applicable: {self.prefactoring[1]}"))
        else:
            blocks += [
                _wrap(f"Existing oracle: `{self.prefactoring[1]}`"),
                _wrap(f"Move: {self.prefactoring[2]}"),
                _wrap(f"Preserved observation: {self.prefactoring[3]}"),
            ]
            blocks += _preservation_commands(self.facts)
        blocks.append(heading("Agreement analysis"))
        if self.agreement_analysis[0] == "not_applicable":
            blocks.append(_wrap(f"Not applicable: {self.agreement_analysis[1]}"))
        else:
            blocks.append(
                table(
                    ("Contract", "Role", "Locator", "Decision", "Reason"),
                    (
                        (contract, role, f"`{locator}`", decision, reason)
                        for contract, role, locator, decision, reason in self.agreement_analysis[  # type: ignore[misc]
                            1
                        ]
                    ),
                )
            )
        blocks += _impact_closure_blocks(self.facts, f" ({self.heading})")
        blocks += _assurance_blocks(self.facts, f" ({self.heading})")
        blocks.append(heading("Boundaries"))
        blocks.append(
            _wrap(f"Not applicable: {self.boundaries[1]}")
            if self.boundaries[0] == "not_applicable"
            else _bullets(self.boundaries[1:])
        )
        if self.facts.acceptance_supports:
            blocks += [
                heading("Acceptance supports"),
                _bullets(
                    tuple(f"`{support}`" for support in self.facts.acceptance_supports)
                ),
            ]
        blocks += [
            heading("Public oracle"),
            _wrap(f"Observation: {self.public_oracle.observation}"),
            _wrap(f"Stimulus: {self.public_oracle.stimulus}"),
            _wrap(f"Expected: {self.public_oracle.expected}"),
            _wrap(f"Falsifier: {self.public_oracle.falsifier}"),
            heading("Oracle and verification"),
            [
                *_wrap(f"Oracle target locator: `{self.facts.oracle}`"),
                f"Oracle verification command index: "
                f"`{self.facts.oracle_verification_index}`",
            ],
        ]
        for argv in self.facts.verification:
            blocks += [_wrap("Verification command:"), _fenced("sh", shlex.join(argv))]
        if self.facts.architect_handoff is not None:
            from des.application.architect_handoff import wire

            blocks += [
                heading("Typed architect handoff"),
                _fenced(
                    "json",
                    json.dumps(
                        wire(self.facts.architect_handoff), ensure_ascii=False, indent=2
                    ),
                ),
            ]
        return "\n\n".join("\n".join(block) for block in blocks) + "\n"

    def legacy_markdown_v1(self) -> str:
        """Return the frozen pre-lint projection for exact migration proof.

        This is deliberately a historical compatibility projection, not an
        alternative authoring format.  A migration admits it only when the
        complete owned section on disk equals these bytes exactly.
        """
        lines = [
            f"## {self.heading}",
            "",
            "### Purpose",
            self.purpose,
            "",
            "### Constraints",
            *(f"- {item}" for item in self.constraints),
            "",
            "### Targets",
            "| Path | Decision | Reason |",
            "|---|---|---|",
            *(
                f"| `{path}` | {decision} | {reason} |"
                for path, decision, reason in self.targets
            ),
            "",
            "### Paradigm",
            self.paradigm,
            "",
            "### Decisions",
            *(f"- {item}" for item in self.decisions),
            "",
            "### Reuse analysis",
            "| Symbol | Locator | Decision | Reason |",
            "|---|---|---|---|",
            *(
                f"| {symbol} | `{locator}` | {decision} | {reason} |"
                for symbol, locator, decision, reason in self.reuse
            ),
            "",
            "### Prefactoring",
            *(
                [f"Not applicable: {self.prefactoring[1]}"]
                if self.prefactoring[0] == "not_applicable"
                else [
                    f"Existing oracle: `{self.prefactoring[1]}`",
                    "",
                    f"Move: {self.prefactoring[2]}",
                    "",
                    f"Preserved observation: {self.prefactoring[3]}",
                ]
            ),
            "",
            "### Agreement analysis",
            *(
                [f"Not applicable: {self.agreement_analysis[1]}"]
                if self.agreement_analysis[0] == "not_applicable"
                else [
                    "| Contract | Role | Locator | Decision | Reason |",
                    "|---|---|---|---|---|",
                    *(
                        f"| {contract} | {role} | `{locator}` | {decision} | {reason} |"
                        for contract, role, locator, decision, reason in self.agreement_analysis[
                            1
                        ]
                    ),
                ]
            ),
            "",
            "### Boundaries",
        ]
        lines += (
            [f"Not applicable: {self.boundaries[1]}"]
            if self.boundaries[0] == "not_applicable"
            else [f"- {boundary}" for boundary in self.boundaries[1:]]
        )
        if self.facts.acceptance_supports:
            lines += [
                "",
                "### Acceptance supports",
                *(f"- `{support}`" for support in self.facts.acceptance_supports),
            ]
        lines += [
            "",
            "### Public oracle",
            f"Observation: {self.public_oracle.observation}",
            "",
            f"Stimulus: {self.public_oracle.stimulus}",
            "",
            f"Expected: {self.public_oracle.expected}",
            "",
            f"Falsifier: {self.public_oracle.falsifier}",
            "",
            "### Oracle and verification",
            f"Oracle target locator: `{self.facts.oracle}`",
            f"Oracle verification command index: `{self.facts.oracle_verification_index}`",
            "",
        ]
        lines.extend(
            f"Verification command: `{' '.join(argv)}`"
            for argv in self.facts.verification
        )
        return "\n".join(lines) + "\n"

    def facts_json(self, facts: DesignFacts | None = None) -> str:
        facts = self.facts if facts is None else facts
        projection: dict[str, object] = {
            "targets": [
                {"path": target.path, "decision": target.decision}
                for target in facts.targets
            ],
            "paradigm": facts.paradigm,
            "decisions": list(facts.decisions),
            "oracle": facts.oracle,
            "acceptance_supports": list(facts.acceptance_supports),
            "verification": [list(argv) for argv in facts.verification],
            "oracle_verification_index": facts.oracle_verification_index,
            "obligations": list(facts.obligations),
            **design_decisions_wire(facts),
            **({"product_change": "none"} if facts.product_change == "none" else {}),
        }
        if facts.authority_locator:
            projection["authority_locator"] = facts.authority_locator
        return json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
        )
