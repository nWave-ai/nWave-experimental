"""Construct and publish the canonical DesignClosureV1 authority region."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from des.application.architecture_projection import (
    PARADIGMS,
    DesignClosureV1,
    canonical_payload,
    design_closure_marker_count,
    design_projection_digest,
    is_canonical_repository_path,
    is_structurally_valid_design_closure_payload,
    sole_design_closure_region,
)
from des.domain.verification_authority_resolver import (
    AmbiguousAuthorityReference,
    LiteralScriptBlock,
    ResolvedAuthoritySection,
    UnresolvedAuthorityReference,
    resolve_authority_section,
    resolve_verification_authority,
)
from des.ports.driven_ports.filesystem_port import FileSystemPort


_SHAPES = {"pure-function", "bounded-change", "unbounded-preservation"}
_OBLIGATIONS = {
    "ARCHITECTURE_BOUNDARY_CHANGE",
    "BROAD_INPUT_DOMAIN",
    "CONTESTED_LAW",
    "INVALID_STATE",
    "PRESERVATION",
    "REPRESENTATION_CHANGE",
}


def _refuse(problems: list[str]) -> int:
    print(
        "WHAT: " + "; ".join(problems) + "\n"
        "WHY: a design closure is published only from a complete, valid semantic input\n"
        "HOW: correct every named argv or authority fact and retry",
        file=sys.stderr,
    )
    return 2


def _relative(value: str) -> bool:
    return is_canonical_repository_path(value)


def _parse(argv: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    values: dict[str, Any] = {
        "targets": [],
        "obligations": [],
        "skills": [],
        "dependencies": [],
        "verification_commands": [],
    }
    current: dict[str, Any] | None = None
    index = 0
    single = {
        "--repo-root": "repo_root",
        "--authority": "authority",
        "--paradigm": "paradigm",
    }
    while index < len(argv):
        flag = argv[index]
        if flag in single or flag in {"--oracle", "--verification-authority"}:
            if index + 1 >= len(argv):
                return None, [f"{flag} needs a value"]
            if flag == "--oracle":
                if index + 2 >= len(argv):
                    return None, ["--oracle needs kind and locator"]
                values["oracle"] = {"kind": argv[index + 1], "locator": argv[index + 2]}
                index += 3
                continue
            key = single.get(flag, flag[2:].replace("-", "_"))
            values[key] = argv[index + 1]
            index += 2
            continue
        if flag == "--verification-executable":
            if index + 1 >= len(argv):
                return None, ["--verification-executable needs a value"]
            values["verification_commands"].append([argv[index + 1]])
            index += 2
            continue
        if flag == "--target":
            if index + 1 >= len(argv):
                return None, ["--target needs a path"]
            current = {
                "path": argv[index + 1],
                "declared_imports": [],
                "boundary": {},
                "extends": [],
                "creates": [],
            }
            values["targets"].append(current)
            index += 2
            continue
        if flag in {
            "--purpose",
            "--shape",
            "--extend",
            "--import",
            "--failure-behavior",
            "--substrate-lie",
            "--substrate-probe",
            "--double-blind-spot",
        }:
            if current is None or index + 1 >= len(argv):
                return None, [f"{flag} must follow a target and have a value"]
            value = argv[index + 1]
            if flag == "--purpose":
                current["purpose"] = value
            elif flag == "--shape":
                current["shape"] = value
            elif flag == "--extend":
                current["extends"].append(value)
            elif flag == "--import":
                current["declared_imports"].append(value)
            else:
                current["boundary"][flag[2:]] = value
            index += 2
            continue
        if flag == "--create-new":
            if current is None or index + 3 >= len(argv):
                return None, ["--create-new needs candidate, symbol and reason"]
            current["creates"].append(
                [argv[index + 1], argv[index + 2], argv[index + 3]]
            )
            index += 4
            continue
        if flag == "--verification-arg":
            if index + 1 >= len(argv):
                return None, [f"{flag} needs a value"]
            if not values["verification_commands"]:
                return None, [
                    "--verification-arg must follow --verification-executable"
                ]
            values["verification_commands"][-1].append(argv[index + 1])
            index += 2
            continue
        if flag in {"--obligation", "--skill", "--test-dependency"}:
            if index + 1 >= len(argv):
                return None, [f"{flag} needs a value"]
            key = {
                "--obligation": "obligations",
                "--skill": "skills",
                "--test-dependency": "dependencies",
            }[flag]
            values[key].append(argv[index + 1])
            index += 2
            continue
        return None, [f"unsupported argument {flag}"]
    return values, []


def main(argv: list[str] | None = None) -> int:
    values, errors = _parse(list(argv or []))
    if errors or values is None:
        return _refuse(errors)
    root = Path(values.get("repo_root", ""))
    authority = values.get("authority", "")
    problems: list[str] = []
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        problems.append("repo-root must be an absolute real directory")
    if values.get("paradigm") not in PARADIGMS:
        problems.append("paradigm must be a closed variant")
    document, separator, anchor = authority.partition("#")
    if not separator or not _relative(document):
        problems.append("authority must be a repository-relative document#heading")
    oracle = values.get("oracle", {})
    if oracle.get("kind") not in {"new", "existing"} or not _relative(
        oracle.get("locator", "")
    ):
        problems.append(
            "oracle must select new or existing repository-relative locator"
        )
    if not values["obligations"] or not set(values["obligations"]).issubset(
        _OBLIGATIONS
    ):
        problems.append("obligations must be nonempty closed variants")
    if not values["targets"]:
        problems.append("target set must be nonempty")
    targets: dict[str, dict[str, Any]] = {}
    for target in values["targets"]:
        path = target["path"]
        if not _relative(path):
            problems.append("target path must be repository-relative")
        if path in targets:
            problems.append(f"duplicate target {path}")
        if not target.get("purpose") or target.get("shape") not in _SHAPES:
            problems.append(f"target {path} needs purpose and closed shape")
        for member in {
            "failure-behavior",
            "substrate-lie",
            "substrate-probe",
            "double-blind-spot",
        } - set(target["boundary"]):
            problems.append(f"target {path} misses {member}")
        for member, text in target["boundary"].items():
            if not text:
                problems.append(f"target {path} has empty {member}")
        if bool(target["extends"]) == bool(target["creates"]):
            problems.append(
                f"target {path} must choose exactly one --extend or --create-new decision"
            )
        if target["extends"]:
            decision = {"variant": "EXTEND", "evidence": sorted(target["extends"])}
        else:
            decision = {"variant": "CREATE_NEW", "evidence": sorted(target["creates"])}
        targets[path] = {
            "purpose": target.get("purpose", ""),
            "shape": target.get("shape", ""),
            "declared_imports": sorted(target["declared_imports"]),
            "boundary": target["boundary"],
            "decision": decision,
        }
    if values["verification_commands"] and "verification_authority" in values:
        problems.append("verification commands and authority delegation conflict")
    verification: dict[str, Any]
    if "verification_authority" in values:
        resolved = resolve_verification_authority(
            root, values["verification_authority"]
        )
        if not isinstance(resolved, LiteralScriptBlock):
            problems.append("verification authority cannot be resolved")
            verification = {}
        else:
            verification = {
                "kind": "delegated",
                "literal-script-block": {
                    "locator": resolved.locator,
                    "content-digest": resolved.content_digest,
                    "lines": list(resolved.lines),
                },
            }
    elif values["verification_commands"]:
        for command in values["verification_commands"]:
            if not command or not all(
                isinstance(token, str) and token for token in command
            ):
                problems.append("verification argv must be nonempty strings")
            elif not _relative(command[0]):
                problems.append("verification executable must be repository-relative")
        verification = {
            "kind": "commands",
            "argvs": values["verification_commands"],
        }
    else:
        problems.append("verification authority or executable is required")
        verification = {}
    if problems:
        return _refuse(problems)
    authority_path = root / document
    try:
        resolved_root = root.resolve(strict=True)
        resolved_authority = authority_path.resolve(strict=True)
    except OSError as exc:
        return _refuse([f"authority cannot be resolved: {exc}"])
    if not resolved_authority.is_relative_to(resolved_root):
        return _refuse(["authority resolves outside the repository root"])
    try:
        text = authority_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _refuse([f"authority cannot be read: {exc}"])
    section_result = resolve_authority_section(
        text, anchor, locator=authority, doc_part=document
    )
    if isinstance(section_result, UnresolvedAuthorityReference):
        return _refuse(
            [f"authority heading cannot be resolved: {section_result.reason}"]
        )
    if isinstance(section_result, AmbiguousAuthorityReference):
        return _refuse([f"authority heading is ambiguous: {section_result.reason}"])
    assert isinstance(section_result, ResolvedAuthoritySection)
    payload = canonical_payload(
        authority=authority,
        paradigm=values["paradigm"],
        oracle=oracle,
        verification=verification,
        targets=targets,
        obligations=values["obligations"],
        skills=values["skills"],
        test_dependencies=values["dependencies"],
    )
    rendered = DesignClosureV1(payload).render().decode("utf-8")
    start, end = section_result.start, section_result.insertion_end
    section = text[start:end]
    all_markers = design_closure_marker_count(text)
    existing_region = sole_design_closure_region(text)
    if all_markers:
        if (
            all_markers != 2
            or existing_region is None
            or existing_region.start < start
            or existing_region.end > end
        ):
            return _refuse(
                [
                    "authority design-closure markers are absent, one-sided, duplicate, cross-heading or wrong-owner"
                ]
            )
        first = existing_region.start - start
        last = existing_region.end - start
        existing = existing_region.text
        try:
            body = existing.split("```json\n", 1)[1].rsplit("\n```\n", 1)[0]
            envelope = json.loads(body)
            if not is_structurally_valid_design_closure_payload(
                envelope.get("payload")
            ):
                raise ValueError("structurally malformed payload")
            canonical = DesignClosureV1(envelope["payload"]).render().decode("utf-8")
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return _refuse(["authority design-closure region has malformed JSON"])
        if (
            set(envelope) != {"format", "design-projection-digest", "payload"}
            or envelope.get("format") != "DesignClosureV1"
            or envelope.get("design-projection-digest")
            != design_projection_digest(envelope["payload"])
            or existing != canonical
        ):
            return _refuse(
                [
                    "authority design-closure region is noncanonical, unsupported or has wrong digest"
                ]
            )
    else:
        first = last = -1
    if first < 0 and last < 0:
        replacement = section + ("" if section.endswith("\n") else "\n") + rendered
    elif first >= 0 and last >= first:
        replacement = section[:first] + rendered + section[last:]
    else:
        return _refuse(
            [
                "authority design-closure markers are absent, one-sided, duplicate or malformed"
            ]
        )
    expected = (text[:start] + replacement + text[end:]).encode("utf-8")
    try:
        FileSystemPort.replace_text_atomically(
            object(),
            authority_path,
            expected,
        )
        observed = FileSystemPort.read_bytes(object(), authority_path)
    except OSError as exc:
        return _refuse([f"authority replacement failed: {exc}"])
    if observed != expected:
        return _refuse(
            ["authority publication readback differs from the canonical closure"]
        )
    print(f"DESIGN-CLOSURE-WRITTEN: {authority}")
    return 0
