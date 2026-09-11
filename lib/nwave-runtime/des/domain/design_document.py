"""The closed v1 DESIGN-document semantic value and its two projections."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Generic, TypeVar

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


if TYPE_CHECKING:
    from collections.abc import Callable


class DesignDocumentInvalid(ValueError):
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


def _oracle(value: object, name: str) -> str:
    locator = _text(value, name)
    if not is_design_oracle_locator(locator):
        raise DesignDocumentInvalid(f"{name} must be a DESIGN oracle locator")
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


@dataclass(frozen=True, slots=True)
class _Product(_Form[dict[str, object]]):
    """A closed object with ordered, named child forms."""

    fields: tuple[_Field, ...]

    def decode(self, value: object, name: str) -> dict[str, object]:
        decoded = _object(value, name)
        _keys(decoded, {field.name for field in self.fields}, name)
        return self.decode_fields(decoded, name)

    def decode_fields(self, decoded: dict[str, object], name: str) -> dict[str, object]:
        return {
            field.name: field.form.decode(decoded[field.name], f"{name}.{field.name}")
            for field in self.fields
        }

    def describe(self, indent: int = 0) -> tuple[str, ...]:
        prefix = " " * indent
        lines: list[str] = [f"{prefix}object with exactly:"]
        for field in self.fields:
            child = field.form.describe(indent + 2)
            lines.append(f"{prefix}- `{field.name}`: {child[0].lstrip()}")
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
        decoded = tuple(
            self.item.decode(item, f"{name}[{index}]")
            for index, item in enumerate(value)
        )
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
                raise DesignDocumentInvalid(f"{name} is not supported")
            return decoded
        decoded = _object(value, name)
        selected = _text(decoded.get(self.tag), f"{name}.{self.tag}")
        for label, product in self.products:
            if selected == label:
                _keys(
                    decoded,
                    {self.tag, *(field.name for field in product.fields)},
                    name,
                )
                return {self.tag: label, **product.decode_fields(decoded, name)}
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
                    f"{' ' * (indent + 2)}- `{field.name}`: {child[0].lstrip()}"
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
_ORACLE = _Leaf("repository-relative DESIGN oracle locator.", _oracle)
_REUSE_LOCATOR = _Leaf("repository-relative path and positive line.", _reuse_locator)
_SCHEMA_VERSION = _Leaf(
    "integer `1`.",
    lambda value, name: (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value == 1
        else (_ for _ in ()).throw(DesignDocumentInvalid(f"{name} must be 1"))
    ),
)
_PARADIGM = _Choice(("object_oriented", "functional"))
_TARGET_DECISION = _Choice(("EXTEND", "CREATE_NEW"))
_REUSE_DECISION = _Choice(("REUSE", "EXTEND", "REPLACE", "CREATE_NEW"))
_FAILURE_OUTCOME = _Choice(("Refusal", "Retry", "Indeterminate"))

_TEXTS = _ListOf(_TEXT)
_PATHS = _ListOf(_PATH, non_empty=False)
_ARGV = _ListOf(_TEXT, collection="argv list")
_VERIFICATION = _ListOf(_ARGV)
_TARGET = _Product(
    (
        _Field("path", _PATH),
        _Field("decision", _TARGET_DECISION),
        _Field("reason", _TEXT),
    )
)
_TARGETS = _ListOf(
    _TARGET,
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
_MANIFEST = _Product(
    (
        _Field("schema_version", _SCHEMA_VERSION),
        _Field("authority", _AUTHORITY),
        _Field("purpose", _TEXT),
        _Field("constraints", _TEXTS),
        _Field("targets", _TARGETS),
        _Field("paradigm", _PARADIGM),
        _Field("decisions", _TEXTS),
        _Field("reuse_analysis", _REUSE_ANALYSIS),
        _Field("prefactoring", _PREFACTORING),
        _Field("agreement_analysis", _AGREEMENT_ANALYSIS),
        _Field("boundaries", _BOUNDARIES),
        _Field("public_oracle", _PUBLIC_ORACLE),
        _Field("oracle", _ORACLE),
        _Field("acceptance_supports", _PATHS),
        _Field("verification", _VERIFICATION),
    )
)


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
    public_oracle: tuple[str, str, str, str]
    facts: DesignFacts

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
        root = _MANIFEST.decode(value, "manifest")
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
        public_oracle = tuple(
            root["public_oracle"][key]  # type: ignore[index]
            for key in ("observation", "stimulus", "expected", "falsifier")
        )
        supports = root["acceptance_supports"]
        verification = root["verification"]
        facts = DesignFacts(
            tuple(DesignTarget(path, decision) for path, decision, _ in targets),
            paradigm,
            decisions,
            oracle,
            supports,
            verification,
            constraints,
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
        )

    @classmethod
    def input_description(cls) -> str:
        """The closed v1 input language for the CLI and installed author guidance."""
        return "\n".join(
            (
                "DESIGN constructor input is one strict UTF-8 JSON manifest:",
                *_MANIFEST.describe(),
            )
        )

    def markdown(self) -> str:
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
            f"Observation: {self.public_oracle[0]}",
            "",
            f"Stimulus: {self.public_oracle[1]}",
            "",
            f"Expected: {self.public_oracle[2]}",
            "",
            f"Falsifier: {self.public_oracle[3]}",
            "",
            "### Oracle and verification",
            f"Oracle target locator: `{self.facts.oracle}`",
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
            "obligations": list(facts.obligations),
        }
        if facts.authority_locator:
            projection["authority_locator"] = facts.authority_locator
        return json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
        )
