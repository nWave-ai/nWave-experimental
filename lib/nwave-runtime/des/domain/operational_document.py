"""Closed v1 operational-document input and its deterministic projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.input_defects import Defects, InputDefects


if TYPE_CHECKING:
    from collections.abc import Callable


class OperationalDocumentInvalid(InputDefects):
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


def _authority(value: object) -> str:
    authority = _object(value, "authority")
    defects = Defects(OperationalDocumentInvalid)
    defects.take(partial(_keys, authority, {"heading"}, "authority"))
    heading = (
        defects.take(
            partial(_text, authority["heading"], "authority.heading", single_line=True)
        )
        if "heading" in authority
        else None
    )
    defects.close()
    return heading  # type: ignore[return-value]


def _applicability(value: object, name: str) -> str:
    applicability = _text(value, f"{name}.applicability")
    if applicability not in {"applicable", "not_applicable"}:
        raise OperationalDocumentInvalid(f"{name}.applicability is not supported")
    return applicability


def _obligation(value: object, name: str) -> dict[str, str]:
    obligation = _object(value, name)
    keys = ("id", "requirement", "verification", "owner")
    defects = Defects(OperationalDocumentInvalid)
    defects.take(partial(_keys, obligation, set(keys), name))
    normalized = {
        key: defects.take(partial(_text, obligation[key], f"{name}.{key}"))
        for key in keys
        if key in obligation
    }
    defects.close()
    return normalized  # type: ignore[return-value]


def _obligations(value: object, name: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise OperationalDocumentInvalid(f"{name}.obligations must be an array")
    defects = Defects(OperationalDocumentInvalid)
    obligations = [
        defects.take(partial(_obligation, item, f"{name}.obligations[{index}]"))
        for index, item in enumerate(value)
    ]
    # Duplicate ids are judged only over wholly decoded obligations.
    defects.close()
    ids = [obligation["id"] for obligation in obligations]  # type: ignore[index]
    if len(set(ids)) != len(ids):
        raise OperationalDocumentInvalid(
            f"{name}.obligations must not contain duplicate id"
        )
    return obligations  # type: ignore[return-value]


def _section(value: object, name: str) -> dict[str, object]:
    section = _object(value, name)
    defects = Defects(OperationalDocumentInvalid)
    defects.take(
        partial(_keys, section, {"applicability", "reason", "obligations"}, name)
    )

    def member(key: str, decode: Callable[[object], object]) -> object:
        return defects.take(partial(decode, section[key])) if key in section else None

    applicability = member("applicability", partial(_applicability, name=name))
    reason = member("reason", partial(_text, name=f"{name}.reason"))
    obligations = member("obligations", partial(_obligations, name=name))
    raw_obligations = section.get("obligations")
    if (
        applicability is not None
        and isinstance(raw_obligations, list)
        and (applicability == "applicable") != bool(raw_obligations)
    ):
        defects.add(f"{name}.obligations must be non-empty exactly when applicable")
    defects.close()
    return {
        "applicability": applicability,
        "reason": reason,
        "obligations": obligations,
    }


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
        # An unsupported schema_version is the envelope: no section is judged
        # against a language the input does not claim.  An absent one is a
        # key-set defect, reported with the sections' own defects.
        version = root.get("schema_version")
        if "schema_version" in root and (
            not isinstance(version, int) or isinstance(version, bool) or version != 1
        ):
            raise OperationalDocumentInvalid("schema_version must be 1")
        defects = Defects(OperationalDocumentInvalid)
        defects.take(
            partial(
                _keys,
                root,
                {"schema_version", "authority", "purpose", *_SECTIONS},
                "input",
            )
        )
        heading = (
            defects.take(partial(_authority, root["authority"]))
            if "authority" in root
            else None
        )
        purpose = (
            defects.take(partial(_text, root["purpose"], "purpose"))
            if "purpose" in root
            else None
        )
        sections = tuple(
            (name, defects.take(partial(_section, root[name], name)))
            for name in _SECTIONS
            if name in root
        )
        defects.close()
        return cls(heading, purpose, sections)  # type: ignore[arg-type]

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
