"""Closed provider-free DISTILL acceptance authority input."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.domain.design_document import (
    _ORACLE_VERIFICATION_INDEX,
    NATIVE_VERIFICATION,
    DesignDocumentInvalid,
    native_verification_defect,
)
from des.domain.discuss_document import _markdown_content, _table_content
from des.domain.input_defects import Defects, InputDefects


if TYPE_CHECKING:
    from collections.abc import Callable


class DistillDocumentInvalid(InputDefects):
    pass


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DistillDocumentInvalid(f"{name} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise DistillDocumentInvalid(f"{name} must be valid UTF-8 text") from error
    return value.strip()


def _oracle_locator(value: object, name: str) -> str:
    text = _text(value, name)
    if not is_design_oracle_locator(text):
        raise DistillDocumentInvalid(
            f"{name} must be a safe repository-relative oracle locator"
        )
    return text


def _support_locator(value: object, name: str) -> str:
    text = _text(value, name)
    if not is_repository_relative_whole_file_locator(text):
        raise DistillDocumentInvalid(
            f"{name} must be a safe repository-relative whole-file locator"
        )
    return text


@dataclass(frozen=True, slots=True)
class AcceptanceObligation:
    """One typed public acceptance obligation, owned by the domain."""

    id: str
    stimulus: str
    expected: str


def selected_revision_sha256(
    obligations: tuple[AcceptanceObligation, ...] | None,
    oracle: str,
    supports: tuple[str, ...],
    verification: tuple[tuple[str, ...], ...],
    oracle_verification_index: int,
) -> str:
    """The one semantic identity of a selected revision (total, no validation).

    ``None`` obligations (DESIGN-sourced) and any DISTILL selection never share
    an identity.  Both consumers -- the typed revision and the runner's
    projection -- delegate here.
    """
    return hashlib.sha256(
        json.dumps(
            {
                "obligations": None
                if obligations is None
                else [
                    {"expected": o.expected, "id": o.id, "stimulus": o.stimulus}
                    for o in obligations
                ],
                "oracle": oracle,
                "oracle_verification_index": oracle_verification_index,
                "supports": list(supports),
                "verification": [list(argv) for argv in verification],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SelectedAcceptanceRevision:
    """One immutable selected acceptance revision: the complete tuple.

    Two constructible sources and no third state: a complete DISTILL
    schema_version 2 value (``obligations`` a non-empty tuple) or DESIGN facts
    via :meth:`from_design` (``obligations`` is ``None``: the criteria are
    absent, never invented as empty).  Any member change is a new revision.
    """

    obligations: tuple[AcceptanceObligation, ...] | None
    oracle: str
    supports: tuple[str, ...]
    verification: tuple[tuple[str, ...], ...]
    oracle_verification_index: int

    @classmethod
    def from_design(
        cls,
        oracle: str,
        supports: tuple[str, ...],
        verification: tuple[tuple[str, ...], ...],
        oracle_verification_index: int,
    ) -> SelectedAcceptanceRevision:
        return cls(None, oracle, supports, verification, oracle_verification_index)

    def __post_init__(self) -> None:
        if self.obligations is not None and not self.obligations:
            raise DistillDocumentInvalid(
                "obligations must be None (DESIGN-sourced) or non-empty: an empty "
                "criteria tuple is no revision; supply at least one obligation "
                "or build the revision from DESIGN"
            )
        defect = native_verification_defect(self.verification)
        if defect is not None:
            raise DistillDocumentInvalid(defect)
        defect = _oracle_index_defect(self.oracle_verification_index, self.verification)
        if defect is not None:
            raise DistillDocumentInvalid(defect)

    @property
    def identity_sha256(self) -> str:
        return selected_revision_sha256(
            self.obligations,
            self.oracle,
            self.supports,
            self.verification,
            self.oracle_verification_index,
        )


@dataclass(frozen=True, slots=True)
class DistillValue:
    observation: str
    revision: SelectedAcceptanceRevision

    @property
    def obligations(self) -> tuple[AcceptanceObligation, ...]:
        return self.revision.obligations

    @property
    def oracle(self) -> str:
        return self.revision.oracle

    @property
    def supports(self) -> tuple[str, ...]:
        return self.revision.supports


_VALUE_KEYS = {
    "observation",
    "acceptance_obligations",
    "oracle",
    "acceptance_supports",
    "verification",
    "oracle_verification_index",
}

V2_HOW = (
    "provide the complete closed DISTILL JSON with schema_version 2: every "
    "value carries observation, acceptance_obligations, oracle, "
    "acceptance_supports, verification (ordered native argv lists) and "
    "oracle_verification_index"
)


def _decoded(form: object, value: object, name: str) -> object:
    try:
        return form.decode(value, name)  # type: ignore[attr-defined]
    except DesignDocumentInvalid as error:
        raise DistillDocumentInvalid(*error.defects) from error


def _oracle_index_defect(
    index: int, verification: tuple[tuple[str, ...], ...]
) -> str | None:
    if 0 <= index < len(verification):
        return None
    return (
        "oracle_verification_index must name one declared verification "
        f"command: {index} is outside "
        f"0..{len(verification) - 1}; use an index of the verification list"
    )


def _obligation(value: object, name: str) -> AcceptanceObligation:
    keys = ("id", "stimulus", "expected")
    if not isinstance(value, dict):
        raise DistillDocumentInvalid(f"{name} has invalid keys")
    defects = Defects(DistillDocumentInvalid)
    if set(value) != set(keys):
        defects.add(f"{name} has invalid keys")
    fields = {
        key: defects.take(partial(_text, value[key], f"obligation.{key}"))
        for key in keys
        if key in value
    }
    defects.close()
    return AcceptanceObligation(**fields)  # type: ignore[arg-type]


def _obligations(value: object, ix: int) -> tuple[AcceptanceObligation, ...]:
    if not isinstance(value, list) or not value:
        raise DistillDocumentInvalid(
            f"values[{ix}].acceptance_obligations must be non-empty"
        )
    defects = Defects(DistillDocumentInvalid)
    obligations = tuple(
        defects.take(
            partial(_obligation, item, f"values[{ix}].acceptance_obligations[{j}]")
        )
        for j, item in enumerate(value)
    )
    # Id uniqueness is judged only over wholly decoded obligations.
    defects.close()
    if len({o.id for o in obligations}) != len(obligations):  # type: ignore[union-attr]
        raise DistillDocumentInvalid("obligation ids must be unique within a value")
    return obligations  # type: ignore[return-value]


def _supports(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DistillDocumentInvalid("acceptance_supports must be an array")
    defects = Defects(DistillDocumentInvalid)
    supports = tuple(
        defects.take(partial(_support_locator, item, "acceptance_supports"))
        for item in value
    )
    defects.close()
    return supports  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class DistillDocument:
    values: tuple[DistillValue, ...]

    def canonical_json(self) -> str:
        """Return the one stable wire representation of this validated input."""
        return json.dumps(
            {
                "schema_version": 2,
                "values": [
                    {
                        "observation": value.observation,
                        "acceptance_obligations": [
                            {
                                "id": obligation.id,
                                "stimulus": obligation.stimulus,
                                "expected": obligation.expected,
                            }
                            for obligation in value.obligations
                        ],
                        "oracle": value.oracle,
                        "acceptance_supports": list(value.supports),
                        "verification": [
                            list(argv) for argv in value.revision.verification
                        ],
                        "oracle_verification_index": value.revision.oracle_verification_index,
                    }
                    for value in self.values
                ],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def input_description(cls) -> str:
        """The one public description of the accepted input, for `--help`."""
        return "\n".join(
            (
                "Closed DISTILL JSON on stdin (`--input -`), schema_version 2:",
                '{"schema_version": 2, "values": [VALUE, ...]}',
                "VALUE is an object with exactly:",
                "- observation: a stored graph observation (unique).",
                "- acceptance_obligations: non-empty list of {id, stimulus, expected}.",
                "- oracle: repository-relative oracle locator.",
                "- acceptance_supports: list of repository-relative whole-file paths; "
                "only acceptance-owned fixtures, never a DESIGN target of this value.",
                "- verification: non-empty ordered list of native argv lists, no repeated "
                "whole argv; run without a shell at the repository root.",
                "- oracle_verification_index: integer index into verification.",
                "schema_version 1 input is refused. DES derives the design basis; "
                "never supply it.",
            )
        )

    @classmethod
    def from_json(cls, raw: str) -> DistillDocument:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DistillDocumentInvalid(f"input is not JSON: {error}") from error
        keys = "input must contain exactly schema_version and values"
        if not isinstance(data, dict):
            raise DistillDocumentInvalid(keys)
        # An unsupported schema_version is the envelope: no value is judged
        # against a language the input does not claim.  An absent one is a
        # key-set defect, reported with the values' own defects.
        version = data.get("schema_version")
        if "schema_version" in data and (
            not isinstance(version, int) or isinstance(version, bool) or version != 2
        ):
            raise DistillDocumentInvalid(
                "schema_version must be integer 2: a schema_version 1 selection "
                "is incomplete without verification and oracle_verification_index; "
                + V2_HOW
            )
        defects = Defects(DistillDocumentInvalid)
        if set(data) != {"schema_version", "values"}:
            defects.add(keys)
        values = (
            defects.take(partial(cls._values, data["values"]))
            if "values" in data
            else None
        )
        defects.close()
        return cls(values)  # type: ignore[arg-type]

    @classmethod
    def _values(cls, raw_values: object) -> tuple[DistillValue, ...]:
        if not isinstance(raw_values, list) or not raw_values:
            raise DistillDocumentInvalid("values must be a non-empty array")
        defects = Defects(DistillDocumentInvalid)
        values: list[DistillValue] = []
        observations: list[str | None] = []
        for ix, value in enumerate(raw_values):
            if not isinstance(value, dict) or set(value) != _VALUE_KEYS:
                defects.add(f"values[{ix}] has invalid keys; " + V2_HOW)
            if not isinstance(value, dict):
                observations.append(None)
                continue
            observation = (
                defects.take(
                    partial(_text, value["observation"], f"values[{ix}].observation")
                )
                if "observation" in value
                else None
            )
            observations.append(observation)
            revision = defects.take(partial(cls._revision, value, ix))
            if observation is not None and revision is not None:
                values.append(DistillValue(observation, revision))
        # Observation uniqueness is judged only over wholly decoded observations.
        if None not in observations and len(set(observations)) != len(observations):
            defects.add("value observations must be unique")
        defects.close()
        return tuple(values)

    @staticmethod
    def _revision(value: dict, ix: int) -> SelectedAcceptanceRevision | None:
        """The value's revision, or ``None`` when one of its members is absent.

        An absent member is the value's key-set defect, which the caller
        reports; every present member is decoded and its defects collected.
        """
        defects = Defects(DistillDocumentInvalid)

        def member(key: str, decode: Callable[[object], object]) -> object:
            return defects.take(partial(decode, value[key])) if key in value else None

        obligations = member(
            "acceptance_obligations", lambda raw: _obligations(raw, ix)
        )
        oracle = member("oracle", lambda raw: _oracle_locator(raw, "oracle"))
        supports = member("acceptance_supports", _supports)
        verification = member(
            "verification",
            lambda raw: _decoded(
                NATIVE_VERIFICATION, raw, f"values[{ix}].verification"
            ),
        )
        index = member(
            "oracle_verification_index",
            lambda raw: _decoded(
                _ORACLE_VERIFICATION_INDEX,
                raw,
                f"values[{ix}].oracle_verification_index",
            ),
        )
        if index is not None and verification is not None:
            defect = _oracle_index_defect(index, verification)  # type: ignore[arg-type]
            if defect is not None:
                defects.add(defect)
        defects.close()
        members = (obligations, oracle, supports, verification, index)
        if any(member is None for member in members):
            return None
        return SelectedAcceptanceRevision(*members)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class PublishedAcceptance:
    """What the acceptance brief shows of one value: never the native argv."""

    observation: str
    obligations: tuple[AcceptanceObligation, ...]
    oracle: str
    supports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceBrief:
    """The published DISTILL projection, which legacy selections can also fill."""

    values: tuple[PublishedAcceptance, ...]

    def markdown(self, request: str) -> str:
        lines = [
            "# Acceptance brief",
            "",
            "## Request",
            _markdown_content(request),
            "",
            "## Value Observations",
        ]
        for value in self.values:
            lines += [
                f"### {_markdown_content(value.observation)}",
                "",
                "## Acceptance Obligations",
                "| ID | Stimulus | Expected result |",
                "| --- | --- | --- |",
                *[
                    f"| {_table_content(o.id)} | {_table_content(o.stimulus)} | {_table_content(o.expected)} |"
                    for o in value.obligations
                ],
                "",
                "## Oracle",
                f"`{_table_content(value.oracle)}`",
                "",
                "## Supports",
                *([f"- `{_table_content(s)}`" for s in value.supports] or ["- None"]),
            ]
        return "\n".join(lines) + "\n"
