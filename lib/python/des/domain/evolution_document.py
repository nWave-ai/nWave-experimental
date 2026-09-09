"""Closed, deterministic feature-evolution document input."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date as calendar_date
from urllib.parse import quote, urlparse


class EvolutionDocumentInvalid(ValueError):
    pass


_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (value := value.strip()):
        raise EvolutionDocumentInvalid(f"{name} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise EvolutionDocumentInvalid(f"{name} must be valid UTF-8 text") from error
    return value


def _texts(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise EvolutionDocumentInvalid(f"{name} must be a non-empty array")
    return tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))


def _escape(value: str) -> str:
    return "\n".join(
        f"    {line}"
        for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    )


@dataclass(frozen=True, slots=True)
class EvolutionDocument:
    date: str
    feature_id: str
    purpose: str
    key_decisions: tuple[str, ...]
    delivered_work: tuple[str, ...]
    verification_results: tuple[str, ...]
    problems: tuple[str, str, tuple[str, ...]]
    lessons: tuple[str, str, tuple[str, ...]]
    durable_artifacts: tuple[tuple[str, str], ...]

    @classmethod
    def from_json(cls, raw: str) -> EvolutionDocument:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise EvolutionDocumentInvalid(f"input is not JSON: {error}") from error
        expected = {
            "schema_version",
            "date",
            "feature_id",
            "purpose",
            "key_decisions",
            "delivered_work",
            "verification_results",
            "problems",
            "lessons",
            "durable_artifacts",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise EvolutionDocumentInvalid(
                f"input must contain exactly {sorted(expected)}"
            )
        if (
            not isinstance(value["schema_version"], int)
            or isinstance(value["schema_version"], bool)
            or value["schema_version"] != 1
        ):
            raise EvolutionDocumentInvalid("schema_version must be 1")
        date = _text(value["date"], "date")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise EvolutionDocumentInvalid("date must be YYYY-MM-DD")
        try:
            calendar_date.fromisoformat(date)
        except ValueError as error:
            raise EvolutionDocumentInvalid("date must be a calendar date") from error
        feature_id = _text(value["feature_id"], "feature_id")
        if not _ID.fullmatch(feature_id):
            raise EvolutionDocumentInvalid(
                "feature_id must be a lowercase hyphenated identifier"
            )

        def retrospective(name: str) -> tuple[str, str, tuple[str, ...]]:
            item = value[name]
            if not isinstance(item, dict) or set(item) != {
                "applicability",
                "reason",
                "items",
            }:
                raise EvolutionDocumentInvalid(
                    f"{name} must contain exactly applicability, reason, items"
                )
            applicability, reason = (
                _text(item["applicability"], f"{name}.applicability"),
                _text(item["reason"], f"{name}.reason"),
            )
            if applicability not in {"applicable", "not_applicable"} or not isinstance(
                item["items"], list
            ):
                raise EvolutionDocumentInvalid(
                    f"{name} has unsupported applicability or items"
                )
            items = tuple(
                _text(x, f"{name}.items[{i}]") for i, x in enumerate(item["items"])
            )
            if (applicability == "applicable") != bool(items):
                raise EvolutionDocumentInvalid(
                    f"{name}.items must be non-empty exactly when applicable"
                )
            return applicability, reason, items

        artifacts: list[tuple[str, str]] = []
        if (
            not isinstance(value["durable_artifacts"], list)
            or not value["durable_artifacts"]
        ):
            raise EvolutionDocumentInvalid(
                "durable_artifacts must be a non-empty array"
            )
        for i, item in enumerate(value["durable_artifacts"]):
            if not isinstance(item, dict) or set(item) != {"label", "path"}:
                raise EvolutionDocumentInvalid(
                    f"durable_artifacts[{i}] must contain exactly label, path"
                )
            path = _text(item["path"], f"durable_artifacts[{i}].path")
            parsed = urlparse(path)
            if (parsed.scheme and (parsed.scheme != "https" or not parsed.netloc)) or (
                not parsed.scheme and (path.startswith("/") or ".." in path.split("/"))
            ):
                raise EvolutionDocumentInvalid(
                    f"durable_artifacts[{i}].path must be repository-relative or HTTPS"
                )
            label = _text(item["label"], f"durable_artifacts[{i}].label")
            if any(character in label for character in "\r\n[]") or any(
                character in path for character in "\r\n()"
            ):
                raise EvolutionDocumentInvalid(
                    f"durable_artifacts[{i}] must not inject Markdown structure"
                )
            artifacts.append((label, path))
        return cls(
            date,
            feature_id,
            _text(value["purpose"], "purpose"),
            _texts(value["key_decisions"], "key_decisions"),
            _texts(value["delivered_work"], "delivered_work"),
            _texts(value["verification_results"], "verification_results"),
            retrospective("problems"),
            retrospective("lessons"),
            tuple(artifacts),
        )

    def markdown(self) -> str:
        lines = [
            f"# Evolution: {self.feature_id}",
            "",
            f"Date: {self.date}",
            "",
            "## Purpose",
            _escape(self.purpose),
        ]
        for title, values in (
            ("Key decisions", self.key_decisions),
            ("Delivered work", self.delivered_work),
            ("Verification results", self.verification_results),
        ):
            lines += ["", f"## {title}", *[f"- {_escape(item)}" for item in values]]
        for title, section in (("Problems", self.problems), ("Lessons", self.lessons)):
            applicability, reason, items = section
            lines += [
                "",
                f"## {title}",
                f"Applicability: {applicability}",
                f"Reason: {_escape(reason)}",
                *[f"- {_escape(item)}" for item in items],
            ]
        lines += [
            "",
            "## Durable artifacts",
            *[
                f"- [{label}]({quote(path, safe=':/?&=#%')})"
                for label, path in self.durable_artifacts
            ],
        ]
        return "\n".join(lines) + "\n"
