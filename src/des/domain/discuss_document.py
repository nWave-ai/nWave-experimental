"""Closed semantic input for the provider-free DISCUSS constructor."""

from __future__ import annotations

import json
from dataclasses import dataclass


class DiscussDocumentInvalid(ValueError):
    pass


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise DiscussDocumentInvalid(f"{name} must be a non-empty string")
    try:
        normalized = value.strip()
        normalized.encode("utf-8")
    except UnicodeEncodeError as error:
        raise DiscussDocumentInvalid(f"{name} must be valid UTF-8 text") from error
    if not normalized:
        raise DiscussDocumentInvalid(f"{name} must be a non-empty string")
    return normalized


def _texts(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DiscussDocumentInvalid(f"{name} must be a non-empty array")
    return tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))


def _markdown_content(value: str) -> str:
    """Keep semantic multiline text inside the Markdown field that owns it."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(f"    {line}" for line in normalized.split("\n"))


def _table_content(value: str) -> str:
    """Keep one semantic value in one Markdown table cell."""
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "")
        .replace("\n", "<br>")
    )


@dataclass(frozen=True, slots=True)
class DiscussValue:
    observation: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscussDocument:
    request: str
    outcomes: tuple[str, ...]
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, str, tuple[str, ...]]
    decisions: tuple[str, ...]
    values: tuple[DiscussValue, ...]

    @classmethod
    def from_json(cls, raw: str) -> DiscussDocument:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise DiscussDocumentInvalid(f"input is not JSON: {error}") from error
        expected = {
            "schema_version",
            "request",
            "outcomes",
            "scope",
            "decisions",
            "values",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise DiscussDocumentInvalid(
                f"input must contain exactly {sorted(expected)}"
            )
        version = payload["schema_version"]
        if not isinstance(version, int) or isinstance(version, bool) or version != 1:
            raise DiscussDocumentInvalid("schema_version must be integer 1")
        scope = payload["scope"]
        if not isinstance(scope, dict) or set(scope) != {"in_scope", "out_of_scope"}:
            raise DiscussDocumentInvalid(
                "scope must contain exactly in_scope and out_of_scope"
            )
        out = scope["out_of_scope"]
        if not isinstance(out, dict) or set(out) != {
            "applicability",
            "reason",
            "items",
        }:
            raise DiscussDocumentInvalid(
                "scope.out_of_scope must contain exactly applicability, reason, items"
            )
        applicability = _text(out["applicability"], "scope.out_of_scope.applicability")
        reason = _text(out["reason"], "scope.out_of_scope.reason")
        if applicability not in {"applicable", "not_applicable"} or not isinstance(
            out["items"], list
        ):
            raise DiscussDocumentInvalid(
                "scope.out_of_scope has unsupported applicability or items"
            )
        out_items = tuple(
            _text(item, f"scope.out_of_scope.items[{index}]")
            for index, item in enumerate(out["items"])
        )
        if (applicability == "applicable") != bool(out_items):
            raise DiscussDocumentInvalid(
                "scope.out_of_scope.items must be non-empty exactly when applicable"
            )
        raw_values = payload["values"]
        if not isinstance(raw_values, list) or not raw_values:
            raise DiscussDocumentInvalid("values must be a non-empty array")
        values: list[DiscussValue] = []
        seen: list[str] = []
        for index, item in enumerate(raw_values):
            if not isinstance(item, dict) or set(item) != {
                "observation",
                "dependencies",
            }:
                raise DiscussDocumentInvalid(
                    f"values[{index}] must contain exactly observation, dependencies"
                )
            observation = _text(item["observation"], f"values[{index}].observation")
            dependencies = item["dependencies"]
            if not isinstance(dependencies, list):
                raise DiscussDocumentInvalid(
                    f"values[{index}].dependencies must be an array"
                )
            normalized_dependencies = tuple(
                _text(dep, f"values[{index}].dependencies[{position}]")
                for position, dep in enumerate(dependencies)
            )
            positions = [
                seen.index(dep) if dep in seen else -1
                for dep in normalized_dependencies
            ]
            if observation in seen or len(set(normalized_dependencies)) != len(
                normalized_dependencies
            ):
                raise DiscussDocumentInvalid(
                    f"values[{index}].dependencies must be unique earlier observations"
                )
            if -1 in positions or positions != sorted(positions):
                raise DiscussDocumentInvalid(
                    f"values[{index}].dependencies must be ordered preceding observations"
                )
            values.append(DiscussValue(observation, normalized_dependencies))
            seen.append(observation)
        return cls(
            _text(payload["request"], "request"),
            _texts(payload["outcomes"], "outcomes"),
            _texts(scope["in_scope"], "scope.in_scope"),
            (applicability, reason, out_items),
            _texts(payload["decisions"], "decisions"),
            tuple(values),
        )

    def markdown(self) -> str:
        applicability, reason, items = self.out_of_scope
        lines = [
            "# Product brief",
            "",
            "## Request",
            _markdown_content(self.request),
            "",
            "## Outcomes",
            *[f"- {_markdown_content(item)}" for item in self.outcomes],
            "",
            "## Scope",
            "",
            "### In scope",
            *[f"- {_markdown_content(item)}" for item in self.in_scope],
            "",
            "### Out of scope",
            f"Applicability: {applicability}",
            f"Reason: {_markdown_content(reason)}",
            *[f"- {_markdown_content(item)}" for item in items],
            "",
            "## Observations",
            *[f"- {_markdown_content(value.observation)}" for value in self.values],
            "",
            "## Decisions",
            *[f"- {_markdown_content(item)}" for item in self.decisions],
            "",
            "## Values",
            "| Observation | Dependencies |",
            "| --- | --- |",
        ]
        lines.extend(
            f"| {_table_content(value.observation)} | {_table_content(', '.join(value.dependencies))} |"
            for value in self.values
        )
        return "\n".join(lines) + "\n"
