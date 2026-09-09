"""Closed provider-free DISTILL acceptance authority input."""

from __future__ import annotations

import json
from dataclasses import dataclass

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.domain.discuss_document import _markdown_content, _table_content


class DistillDocumentInvalid(ValueError):
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


@dataclass(frozen=True, slots=True)
class DistillValue:
    observation: str
    obligations: tuple[AcceptanceObligation, ...]
    oracle: str
    supports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DistillDocument:
    values: tuple[DistillValue, ...]

    @classmethod
    def from_json(cls, raw: str) -> DistillDocument:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DistillDocumentInvalid(f"input is not JSON: {error}") from error
        if not isinstance(data, dict) or set(data) != {"schema_version", "values"}:
            raise DistillDocumentInvalid(
                "input must contain exactly schema_version and values"
            )
        if (
            not isinstance(data["schema_version"], int)
            or isinstance(data["schema_version"], bool)
            or data["schema_version"] != 1
        ):
            raise DistillDocumentInvalid("schema_version must be integer 1")
        if not isinstance(data["values"], list) or not data["values"]:
            raise DistillDocumentInvalid("values must be a non-empty array")
        values = []
        seen = set()
        for ix, value in enumerate(data["values"]):
            if not isinstance(value, dict) or set(value) != {
                "observation",
                "acceptance_obligations",
                "oracle",
                "acceptance_supports",
            }:
                raise DistillDocumentInvalid(f"values[{ix}] has invalid keys")
            observation = _text(value["observation"], f"values[{ix}].observation")
            if observation in seen:
                raise DistillDocumentInvalid("value observations must be unique")
            seen.add(observation)
            raw_obligations = value["acceptance_obligations"]
            if not isinstance(raw_obligations, list) or not raw_obligations:
                raise DistillDocumentInvalid(
                    f"values[{ix}].acceptance_obligations must be non-empty"
                )
            obligations = []
            ids = set()
            for j, item in enumerate(raw_obligations):
                if not isinstance(item, dict) or set(item) != {
                    "id",
                    "stimulus",
                    "expected",
                }:
                    raise DistillDocumentInvalid(
                        f"values[{ix}].acceptance_obligations[{j}] has invalid keys"
                    )
                fact = AcceptanceObligation(
                    _text(item["id"], "obligation.id"),
                    _text(item["stimulus"], "obligation.stimulus"),
                    _text(item["expected"], "obligation.expected"),
                )
                if fact.id in ids:
                    raise DistillDocumentInvalid(
                        "obligation ids must be unique within a value"
                    )
                ids.add(fact.id)
                obligations.append(fact)
            supports = value["acceptance_supports"]
            if not isinstance(supports, list):
                raise DistillDocumentInvalid("acceptance_supports must be an array")
            values.append(
                DistillValue(
                    observation,
                    tuple(obligations),
                    _oracle_locator(value["oracle"], "oracle"),
                    tuple(_support_locator(s, "acceptance_supports") for s in supports),
                )
            )
        return cls(tuple(values))

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
