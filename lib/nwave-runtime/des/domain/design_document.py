"""The closed v1 DESIGN-document semantic value and its two projections."""

from __future__ import annotations

import json
from dataclasses import dataclass

from des.domain.architecture_brief_resolver import (
    is_design_oracle_locator,
    is_repository_relative_whole_file_locator,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


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


def _texts(value: object, name: str, *, non_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (non_empty and not value):
        raise DesignDocumentInvalid(f"{name} must be a list of non-empty strings")
    texts = tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))
    _duplicates(texts, name)
    return texts


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
    boundaries: tuple[str, ...]
    public_oracle: tuple[str, str, str, str]
    facts: DesignFacts

    @classmethod
    def from_json(cls, raw: str) -> DesignDocument:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DesignDocumentInvalid(f"input is not JSON: {error}") from error
        root = _object(value, "manifest")
        _keys(
            root,
            {
                "schema_version",
                "authority",
                "purpose",
                "constraints",
                "targets",
                "paradigm",
                "decisions",
                "reuse_analysis",
                "prefactoring",
                "boundaries",
                "public_oracle",
                "oracle",
                "acceptance_supports",
                "verification",
            },
            "manifest",
        )
        if (
            not isinstance(root["schema_version"], int)
            or isinstance(root["schema_version"], bool)
            or root["schema_version"] != 1
        ):
            raise DesignDocumentInvalid("schema_version must be 1")
        authority = _object(root["authority"], "authority")
        _keys(authority, {"heading"}, "authority")
        heading, purpose = (
            _text(authority["heading"], "authority.heading"),
            _text(root["purpose"], "purpose"),
        )
        if "\n" in heading or "\r" in heading or heading.startswith("#"):
            raise DesignDocumentInvalid(
                "authority.heading must be plain text, not a Markdown heading"
            )
        constraints, decisions = (
            _texts(root["constraints"], "constraints"),
            _texts(root["decisions"], "decisions"),
        )
        paradigm, oracle = (
            _text(root["paradigm"], "paradigm"),
            _text(root["oracle"], "oracle"),
        )
        if paradigm not in {"object_oriented", "functional"}:
            raise DesignDocumentInvalid("paradigm is not supported")
        targets_raw = root["targets"]
        if not isinstance(targets_raw, list) or not targets_raw:
            raise DesignDocumentInvalid("targets must be a non-empty list")
        targets: list[tuple[str, str, str]] = []
        for index, item in enumerate(targets_raw):
            item = _object(item, f"targets[{index}]")
            _keys(item, {"path", "decision", "reason"}, f"targets[{index}]")
            path, decision, reason = (
                _path(item["path"], "target.path"),
                _text(item["decision"], "target.decision"),
                _text(item["reason"], "target.reason"),
            )
            if decision not in {"EXTEND", "CREATE_NEW"}:
                raise DesignDocumentInvalid("target.decision is not supported")
            targets.append((path, decision, reason))
        _duplicates(tuple(targets), "targets")
        _duplicates(tuple(path for path, _, _ in targets), "targets paths")
        reuse_root = _object(root["reuse_analysis"], "reuse_analysis")
        _keys(reuse_root, {"candidates"}, "reuse_analysis")
        candidates = reuse_root["candidates"]
        if not isinstance(candidates, list):
            raise DesignDocumentInvalid("reuse_analysis.candidates must be a list")
        reuse: list[tuple[str, str, str, str]] = []
        for index, item in enumerate(candidates):
            item = _object(item, f"reuse candidate {index}")
            _keys(
                item,
                {"symbol", "locator", "decision", "reason"},
                f"reuse candidate {index}",
            )
            symbol, locator, decision, reason = (
                _text(item["symbol"], "reuse candidate symbol"),
                _reuse_locator(item["locator"], "reuse candidate locator"),
                _text(item["decision"], "reuse candidate decision"),
                _text(item["reason"], "reuse candidate reason"),
            )
            if decision not in {"REUSE", "EXTEND", "REPLACE", "CREATE_NEW"}:
                raise DesignDocumentInvalid("reuse candidate decision is not supported")
            reuse.append((symbol, locator, decision, reason))
        _duplicates(tuple(reuse), "reuse_analysis.candidates")
        pre = _object(root["prefactoring"], "prefactoring")
        applicability = _text(pre.get("applicability"), "prefactoring.applicability")
        if applicability == "applicable":
            _keys(
                pre,
                {"applicability", "existing_oracle", "move", "preserved_observation"},
                "prefactoring",
            )
            prefactoring = (
                applicability,
                _oracle(pre["existing_oracle"], "prefactoring.existing_oracle"),
                _text(pre["move"], "prefactoring.move"),
                _text(
                    pre["preserved_observation"], "prefactoring.preserved_observation"
                ),
            )
        elif applicability == "not_applicable":
            _keys(pre, {"applicability", "reason"}, "prefactoring")
            prefactoring = (applicability, _text(pre["reason"], "prefactoring.reason"))
        else:
            raise DesignDocumentInvalid("prefactoring.applicability is not supported")
        boundaries_root = _object(root["boundaries"], "boundaries")
        applicability = _text(
            boundaries_root.get("applicability"), "boundaries.applicability"
        )
        if applicability == "not_applicable":
            _keys(boundaries_root, {"applicability", "reason"}, "boundaries")
            boundaries = (
                applicability,
                _text(boundaries_root["reason"], "boundaries.reason"),
            )
        elif applicability == "applicable":
            _keys(
                boundaries_root,
                {
                    "applicability",
                    "driving_port",
                    "driven_ports",
                    "dependency_direction",
                    "failures",
                },
                "boundaries",
            )
            driven = _texts(boundaries_root["driven_ports"], "boundaries.driven_ports")
            failures_raw = boundaries_root["failures"]
            if not isinstance(failures_raw, list) or not failures_raw:
                raise DesignDocumentInvalid(
                    "boundaries.failures must be a non-empty list"
                )
            failures: list[tuple[str, str, str]] = []
            for index, failure in enumerate(failures_raw):
                failure = _object(failure, f"boundaries.failures[{index}]")
                _keys(
                    failure,
                    {"condition", "outcome", "observation"},
                    f"boundaries.failures[{index}]",
                )
                condition, outcome, observation = (
                    _text(failure["condition"], "boundaries.failure.condition"),
                    _text(failure["outcome"], "boundaries.failure.outcome"),
                    _text(failure["observation"], "boundaries.failure.observation"),
                )
                if outcome not in {"Refusal", "Retry", "Indeterminate"}:
                    raise DesignDocumentInvalid(
                        "boundaries.failure.outcome is not supported"
                    )
                failures.append((condition, outcome, observation))
            _duplicates(tuple(failures), "boundaries.failures")
            boundaries = (
                applicability,
                f"Driving port: {_text(boundaries_root['driving_port'], 'boundaries.driving_port')}",
                *(f"Driven port: {port}" for port in driven),
                "Dependency direction: "
                + _text(
                    boundaries_root["dependency_direction"],
                    "boundaries.dependency_direction",
                ),
                *(
                    "Failure: "
                    f"Condition: {condition} | Outcome: {outcome} | Observation: {observation}"
                    for condition, outcome, observation in failures
                ),
            )
        else:
            raise DesignDocumentInvalid("boundaries.applicability is not supported")
        public = _object(root["public_oracle"], "public_oracle")
        _keys(
            public,
            {"observation", "stimulus", "expected", "falsifier"},
            "public_oracle",
        )
        public_oracle = tuple(
            _text(public[key], f"public_oracle.{key}")
            for key in ("observation", "stimulus", "expected", "falsifier")
        )
        supports = tuple(
            _path(item, f"acceptance_supports[{index}]")
            for index, item in enumerate(
                _texts(
                    root["acceptance_supports"], "acceptance_supports", non_empty=False
                )
            )
        )
        verification_raw = root["verification"]
        if not isinstance(verification_raw, list) or not verification_raw:
            raise DesignDocumentInvalid("verification must be a non-empty list")
        verification = tuple(
            _texts(argv, f"verification[{index}]")
            for index, argv in enumerate(verification_raw)
        )
        _duplicates(verification, "verification")
        facts = DesignFacts(
            tuple(DesignTarget(path, decision) for path, decision, _ in targets),
            paradigm,
            decisions,
            _oracle(oracle, "oracle"),
            supports,
            verification,
            constraints,
        )
        return cls(
            heading,
            purpose,
            constraints,
            tuple(targets),
            paradigm,
            decisions,
            tuple(reuse),
            prefactoring,
            boundaries,
            public_oracle,
            facts,
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

    def facts_json(self) -> str:
        return json.dumps(
            {
                "targets": [
                    {"path": target.path, "decision": target.decision}
                    for target in self.facts.targets
                ],
                "paradigm": self.facts.paradigm,
                "decisions": list(self.facts.decisions),
                "oracle": self.facts.oracle,
                "acceptance_supports": list(self.facts.acceptance_supports),
                "verification": [list(argv) for argv in self.facts.verification],
                "obligations": list(self.facts.obligations),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
