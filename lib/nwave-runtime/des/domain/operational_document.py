"""Closed v1 operational-document input and its deterministic projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class OperationalDocumentInvalid(ValueError):
    """The supplied value is outside the OperationalDocumentInput v1 grammar."""


_SECTIONS = ("environment", "deployment", "recovery", "observability")


def _markdown_content(value: str) -> str:
    """Keep permitted multiline semantic text inside its declared Markdown field."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(f"    {line}" for line in normalized.split("\n"))


def _table_content(value: str) -> str:
    """One obligation value must remain one table cell."""
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OperationalDocumentInvalid(f"{name} must be an object")
    return value


def _keys(value: dict[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise OperationalDocumentInvalid(
            f"{name} must contain exactly {sorted(expected)}"
        )


def _text(value: object, name: str, *, single_line: bool = False) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise OperationalDocumentInvalid(f"{name} must be a non-empty string")
    # ``sys.stdin`` can be configured with ``surrogateescape``.  In that mode a
    # malformed UTF-8 byte is represented by a lone surrogate rather than
    # raising while the stream is read.  Reject it at the closed-input boundary
    # instead of allowing rendering or facts serialization to fail after the
    # producer has acquired its lock.
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as error:
        raise OperationalDocumentInvalid(f"{name} must be valid UTF-8 text") from error
    if single_line and ("\n" in normalized or "\r" in normalized):
        raise OperationalDocumentInvalid(
            f"{name} must be a non-empty single-line string"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class OperationalDocument:
    heading: str
    purpose: str
    sections: tuple[tuple[str, dict[str, object]], ...]

    @classmethod
    def from_json(cls, raw: str) -> OperationalDocument:
        try:
            root = _object(json.loads(raw), "input")
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OperationalDocumentInvalid(f"input is not JSON: {error}") from error
        _keys(root, {"schema_version", "authority", "purpose", *_SECTIONS}, "input")
        if (
            not isinstance(root["schema_version"], int)
            or isinstance(root["schema_version"], bool)
            or root["schema_version"] != 1
        ):
            raise OperationalDocumentInvalid("schema_version must be 1")
        authority = _object(root["authority"], "authority")
        _keys(authority, {"heading"}, "authority")
        heading = _text(authority["heading"], "authority.heading", single_line=True)
        purpose = _text(root["purpose"], "purpose")
        sections: list[tuple[str, dict[str, object]]] = []
        for name in _SECTIONS:
            section = _object(root[name], name)
            _keys(section, {"applicability", "reason", "obligations"}, name)
            applicability = _text(section["applicability"], f"{name}.applicability")
            if applicability not in {"applicable", "not_applicable"}:
                raise OperationalDocumentInvalid(
                    f"{name}.applicability is not supported"
                )
            reason = _text(section["reason"], f"{name}.reason")
            raw_obligations = section["obligations"]
            if not isinstance(raw_obligations, list):
                raise OperationalDocumentInvalid(f"{name}.obligations must be an array")
            if (applicability == "applicable") != bool(raw_obligations):
                raise OperationalDocumentInvalid(
                    f"{name}.obligations must be non-empty exactly when applicable"
                )
            obligations: list[dict[str, str]] = []
            ids: set[str] = set()
            for index, raw_obligation in enumerate(raw_obligations):
                obligation = _object(raw_obligation, f"{name}.obligations[{index}]")
                _keys(
                    obligation,
                    {"id", "requirement", "verification", "owner"},
                    f"{name}.obligations[{index}]",
                )
                normalized = {
                    key: _text(obligation[key], f"{name}.obligations[{index}].{key}")
                    for key in ("id", "requirement", "verification", "owner")
                }
                if normalized["id"] in ids:
                    raise OperationalDocumentInvalid(
                        f"{name}.obligations must not contain duplicate id"
                    )
                ids.add(normalized["id"])
                obligations.append(normalized)
            sections.append(
                (
                    name,
                    {
                        "applicability": applicability,
                        "reason": reason,
                        "obligations": obligations,
                    },
                )
            )
        return cls(heading, purpose, tuple(sections))

    def facts(self, destination: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "authority": {"destination": destination, "heading": self.heading},
            "purpose": self.purpose,
            **dict(self.sections),
        }

    def facts_bytes(self, destination: str) -> bytes:
        return json.dumps(
            self.facts(destination), ensure_ascii=False, separators=(",", ":")
        ).encode()

    def markdown(self) -> str:
        lines = [
            f"## {self.heading}",
            "",
            "### Purpose",
            _markdown_content(self.purpose),
        ]
        for name, section in self.sections:
            lines += [
                "",
                f"### {name.capitalize()}",
                f"Applicability: {section['applicability']}",
                "",
                f"Reason: {_markdown_content(section['reason'])}",
            ]
            obligations = section["obligations"]
            if obligations:
                lines += [
                    "",
                    "| ID | Requirement | Verification | Owner |",
                    "|---|---|---|---|",
                ]
                lines.extend(
                    f"| {_table_content(item['id'])} | {_table_content(item['requirement'])} | {_table_content(item['verification'])} | {_table_content(item['owner'])} |"
                    for item in obligations
                )  # type: ignore[index]
        return "\n".join(lines) + "\n"


def operational_facts_from_json(raw: str) -> dict[str, object]:
    """Deserialize only a canonical OperationalFacts v1 sidecar."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise OperationalDocumentInvalid(
            f"operational facts are not JSON: {error}"
        ) from error
    root = _object(value, "operational facts")
    _keys(
        root,
        {"schema_version", "authority", "purpose", *_SECTIONS},
        "operational facts",
    )
    authority = _object(root["authority"], "operational facts.authority")
    _keys(authority, {"destination", "heading"}, "operational facts.authority")
    destination = _text(
        authority["destination"], "operational facts.authority.destination"
    )
    destination_path = Path(destination)
    if (
        destination_path.is_absolute()
        or ".." in destination_path.parts
        or not destination_path.parts
        or destination_path.suffix != ".md"
    ):
        raise OperationalDocumentInvalid(
            "operational facts.authority.destination must be a repository-relative .md path"
        )
    # Reuse the input grammar after converting the selection-only authority.
    input_value = dict(root)
    input_value["authority"] = {"heading": authority["heading"]}
    parsed = OperationalDocument.from_json(json.dumps(input_value))
    facts = parsed.facts(destination)
    canonical = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
    if raw != canonical:
        raise OperationalDocumentInvalid("operational facts are not canonical")
    return facts
