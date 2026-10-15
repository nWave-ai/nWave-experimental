"""Closed semantic input for the provider-free DISCUSS constructor."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING

from des.domain.discuss_contract import (
    CURRENT_VERSION,
    LEGACY_VERSIONS,
    SECTION_NAMES,
)
from des.domain.discuss_sections import DiscussSections
from des.domain.input_defects import Defects, InputDefects
from des.domain.integration_commit_message import ChangeIntent


if TYPE_CHECKING:
    from collections.abc import Callable


class DiscussDocumentInvalid(InputDefects):
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
    defects = Defects(DiscussDocumentInvalid)
    texts = tuple(
        defects.take(partial(_text, item, f"{name}[{index}]"))
        for index, item in enumerate(value)
    )
    defects.close()
    return texts  # type: ignore[return-value]


def _out_of_scope(out: object) -> tuple[str, str, tuple[str, ...]]:
    keys = "scope.out_of_scope must contain exactly applicability, reason, items"
    if not isinstance(out, dict):
        raise DiscussDocumentInvalid(keys)
    defects = Defects(DiscussDocumentInvalid)
    if set(out) != {"applicability", "reason", "items"}:
        defects.add(keys)
    applicability = (
        defects.take(
            partial(_text, out["applicability"], "scope.out_of_scope.applicability")
        )
        if "applicability" in out
        else None
    )
    reason = (
        defects.take(partial(_text, out["reason"], "scope.out_of_scope.reason"))
        if "reason" in out
        else None
    )
    items = out.get("items")
    supported = applicability in {"applicable", "not_applicable"}
    if (applicability is not None and not supported) or (
        "items" in out and not isinstance(items, list)
    ):
        defects.add("scope.out_of_scope has unsupported applicability or items")
    out_items: tuple[str | None, ...] = ()
    if isinstance(items, list):
        out_items = tuple(
            defects.take(partial(_text, item, f"scope.out_of_scope.items[{index}]"))
            for index, item in enumerate(items)
        )
        if supported and (applicability == "applicable") != bool(items):
            defects.add(
                "scope.out_of_scope.items must be non-empty exactly when applicable"
            )
    defects.close()
    return applicability, reason, out_items  # type: ignore[return-value]


def _scope(scope: object) -> tuple[tuple[str, ...], tuple[str, str, tuple[str, ...]]]:
    keys = "scope must contain exactly in_scope and out_of_scope"
    if not isinstance(scope, dict):
        raise DiscussDocumentInvalid(keys)
    defects = Defects(DiscussDocumentInvalid)
    if set(scope) != {"in_scope", "out_of_scope"}:
        defects.add(keys)
    in_scope = (
        defects.take(partial(_texts, scope["in_scope"], "scope.in_scope"))
        if "in_scope" in scope
        else None
    )
    out_of_scope = (
        defects.take(partial(_out_of_scope, scope["out_of_scope"]))
        if "out_of_scope" in scope
        else None
    )
    defects.close()
    return in_scope, out_of_scope  # type: ignore[return-value]


def _dependencies(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DiscussDocumentInvalid(f"{name}.dependencies must be an array")
    defects = Defects(DiscussDocumentInvalid)
    dependencies = tuple(
        defects.take(partial(_text, dependency, f"{name}.dependencies[{position}]"))
        for position, dependency in enumerate(value)
    )
    defects.close()
    return dependencies  # type: ignore[return-value]


def _values(raw_values: object) -> tuple[DiscussValue, ...]:
    if not isinstance(raw_values, list) or not raw_values:
        raise DiscussDocumentInvalid("values must be a non-empty array")
    defects = Defects(DiscussDocumentInvalid)
    declared_observations = {
        raw.strip()
        for item in raw_values
        if isinstance(item, dict)
        and isinstance(raw := item.get("observation"), str)
        and raw.strip()
    }
    values: list[DiscussValue] = []
    # Every earlier observation as compared; ``None`` where it cannot be known.
    # A refused observation whose raw value is text still counts as seen, so
    # a later dependency on it is not refused only because its text failed.
    seen: list[str | None] = []
    for index, item in enumerate(raw_values):
        name = f"values[{index}]"
        required = {"observation", "dependencies"}
        if not isinstance(item, dict) or not required <= set(item) <= required | {
            "change"
        }:
            defects.add(
                f"{name} must contain exactly observation, dependencies "
                "and optionally change"
            )
        if not isinstance(item, dict):
            seen.append(None)
            continue
        raw_observation = item.get("observation")
        observation = (
            defects.take(partial(_text, raw_observation, f"{name}.observation"))
            if "observation" in item
            else None
        )
        dependencies = (
            defects.take(partial(_dependencies, item["dependencies"], name))
            if "dependencies" in item
            else None
        )
        change = (
            defects.take(
                partial(ChangeIntent.from_payload, item["change"], f"{name}.change")
            )
            if "change" in item
            else None
        )
        if (observation is not None and observation in seen) or (
            dependencies is not None and len(set(dependencies)) != len(dependencies)
        ):
            defects.add(f"{name}.dependencies must be unique earlier observations")
        if dependencies is not None:
            # Unknown earlier text could resolve an unknown dependency when
            # repaired. But a known current/later value cannot become an earlier
            # value too without violating uniqueness; report that defect now.
            unresolved = any(
                dep not in seen and (None not in seen or dep in declared_observations)
                for dep in dependencies
            )
            positions = [seen.index(dep) for dep in dependencies if dep in seen]
            if unresolved or positions != sorted(positions):
                defects.add(
                    f"{name}.dependencies must be ordered preceding observations"
                )
        if observation is not None and dependencies is not None:
            values.append(DiscussValue(observation, dependencies, change))
        seen.append(
            observation
            if observation is not None
            else raw_observation.strip()
            if isinstance(raw_observation, str)
            else None
        )
    defects.close()
    return tuple(values)


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
    change: ChangeIntent | None = None


@dataclass(frozen=True, slots=True)
class DiscussDocument:
    request: str
    outcomes: tuple[str, ...]
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, str, tuple[str, ...]]
    decisions: tuple[str, ...]
    values: tuple[DiscussValue, ...]
    sections: DiscussSections = field(default_factory=DiscussSections)

    @classmethod
    def from_json(cls, raw: str) -> DiscussDocument:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise DiscussDocumentInvalid(f"input is not JSON: {error}") from error
        if not isinstance(payload, dict):
            raise DiscussDocumentInvalid("input must be a JSON object")
        version = payload.get("schema_version")
        supported = (CURRENT_VERSION, *LEGACY_VERSIONS)
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version not in supported
        ):
            raise DiscussDocumentInvalid(
                f"schema_version must be integer {CURRENT_VERSION} (current) "
                f"or legacy {LEGACY_VERSIONS[0]}"
            )
        core = {"schema_version", "request", "outcomes", "scope", "decisions", "values"}
        sections = set(SECTION_NAMES)
        allowed = core | sections
        required = core | (sections if version == CURRENT_VERSION else set())
        defects = Defects(DiscussDocumentInvalid)
        if not required <= set(payload) <= allowed:
            defects.add(
                f"schema_version {version} input must contain {sorted(required)}"
                f" and no key outside {sorted(allowed)}"
            )

        def member(key: str, decode: Callable[[object], object]) -> object:
            return (
                defects.take(partial(decode, payload[key])) if key in payload else None
            )

        parsed_sections = defects.take(
            partial(DiscussSections.from_payload, payload, version)
        )
        scope = member("scope", _scope)
        values = member("values", _values)
        request = member("request", partial(_text, name="request"))
        outcomes = member("outcomes", partial(_texts, name="outcomes"))
        decisions = member("decisions", partial(_texts, name="decisions"))
        defects.close()
        in_scope, out_of_scope = scope  # type: ignore[misc]
        return cls(
            request,  # type: ignore[arg-type]
            outcomes,  # type: ignore[arg-type]
            in_scope,
            out_of_scope,
            decisions,  # type: ignore[arg-type]
            values,  # type: ignore[arg-type]
            parsed_sections,  # type: ignore[arg-type]
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
            *self.sections.markdown(),
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
        if any(value.change is not None for value in self.values):
            lines.extend(
                [
                    "",
                    "## Change intent",
                    "| Observation | Type | Description |",
                    "| --- | --- | --- |",
                ]
            )
            lines.extend(
                f"| {_table_content(value.observation)} | "
                f"{value.change.type if value.change is not None else 'unrecorded'} | "
                f"{_table_content(value.change.description) if value.change is not None else 'unrecorded'} |"
                for value in self.values
            )
        return "\n".join(lines) + "\n"
