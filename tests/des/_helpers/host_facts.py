"""Test-host fixture facts submitted to DES's deterministic public constructors."""

from __future__ import annotations

import copy
import json

from des.domain.discuss_contract import MINIMAL_EXAMPLE


def product_manifest(request: str, observations: list[str]) -> dict:
    manifest = copy.deepcopy(MINIMAL_EXAMPLE)
    manifest.update(
        request=request,
        outcomes=observations,
        decisions=["Exercise the selected public fixture behavior."],
        values=[
            {"observation": text, "dependencies": observations[:index]}
            for index, text in enumerate(observations)
        ],
    )
    manifest["scope"]["in_scope"] = observations
    return manifest


def _closure(facts: dict, targets: list[dict]) -> dict:
    """The fixture's closure: every target and agreement consumer, or none needed."""
    agreement = facts["agreement_analysis"]
    consumers = [
        party["locator"]
        for party in agreement.get("parties", ())
        if party["role"] == "consumer"
    ]
    if not consumers:
        return {
            "applicability": "not_applicable",
            "reason": "The fixture reaches no public surface, consumer or build metadata.",
        }
    return {
        "applicability": "applicable",
        "items": [
            *(
                {
                    "kind": "runtime",
                    "locator": item["path"],
                    "decision": "CHANGED",
                    "reason": item["reason"],
                }
                for item in targets
            ),
            *(
                {
                    "kind": "consumer",
                    "locator": locator,
                    "decision": "UNCHANGED_COMPATIBLE",
                    "reason": "The fixture consumer reads the unchanged contract.",
                }
                for locator in dict.fromkeys(consumers)
            ),
        ],
    }


def design_manifest(facts: dict, observation: str, position: int) -> dict:
    """Construct schema-2 input from this test host's explicit fixture fields."""
    not_applicable = {
        "applicability": "not_applicable",
        "reason": "The fixture has no affected boundary.",
    }
    targets = [
        dict(item, reason=item.get("reason", "Own the fixture's public behavior."))
        for item in facts["targets"]
    ]
    manifest = {
        "schema_version": 2,
        "purpose": facts.get("purpose", observation),
        "constraints": facts.get(
            "constraints", ["Preserve unrelated repository bytes."]
        ),
        "targets": targets,
        "paradigm": facts["paradigm"],
        "decisions": facts["decisions"],
        "reuse_analysis": facts.get("reuse_analysis")
        or {
            "candidates": [
                {
                    "symbol": item["path"],
                    "locator": item["path"] + ":1",
                    "decision": item["decision"],
                    "reason": item["reason"],
                }
                for item in targets
            ]
        },
        "architectural_tests": facts["architectural_tests"],
        "contract_tests": facts["contract_tests"],
        "prefactoring": facts["prefactoring"],
        "agreement_analysis": facts["agreement_analysis"],
        "impact_closure": facts.get("impact_closure") or _closure(facts, targets),
        **({"adr": facts["adr"]} if facts.get("adr") is not None else {}),
        **(
            {"product_change": facts["product_change"]}
            if "product_change" in facts
            else {}
        ),
        **(
            {"architect_handoff": facts["architect_handoff"]}
            if "architect_handoff" in facts
            else {}
        ),
        **({"inherits": facts["inherits"]} if "inherits" in facts else {}),
        "boundaries": facts.get("boundaries", dict(not_applicable)),
        "public_oracle": facts.get("public_oracle")
        or {
            "observation": observation,
            "stimulus": "Execute the public fixture oracle.",
            "expected": observation,
            "falsifier": "The public assertion contradicts the expected observation.",
        },
        "oracle": facts["oracle"],
        "acceptance_supports": facts.get("acceptance_supports", []),
        "verification": facts["verification"],
        "oracle_verification_index": facts.get("oracle_verification_index", 0),
    }
    manifest = copy.deepcopy(manifest)
    definitions = copy.deepcopy(facts.get("facts", []))
    ids_by_text = {
        " ".join(record["text"].split()).casefold(): record["id"]
        for record in definitions
    }
    occupied_ids = {record["id"] for record in definitions}

    def reference(text):
        if isinstance(text, dict):
            return copy.deepcopy(text)
        key = " ".join(text.split()).casefold()
        identifier = ids_by_text.get(key)
        if identifier is None:
            number = len(definitions) + 1
            identifier = f"V{position}-F{number}"
            while identifier in occupied_ids:
                number += 1
                identifier = f"V{position}-F{number}"
            occupied_ids.add(identifier)
            ids_by_text[key] = identifier
            definitions.append({"id": identifier, "text": text})
        return {"ref": identifier}

    for name in ("purpose",):
        manifest[name] = reference(manifest[name])
    for name in ("constraints", "decisions"):
        manifest[name] = [reference(text) for text in manifest[name]]
    for target in manifest["targets"]:
        target["reason"] = reference(target["reason"])
    for candidate in manifest["reuse_analysis"]["candidates"]:
        candidate["reason"] = reference(candidate["reason"])
    for name in (
        "architectural_tests",
        "contract_tests",
        "prefactoring",
        "agreement_analysis",
        "impact_closure",
        "boundaries",
        "adr",
    ):
        section = manifest.get(name)
        if section is None:
            continue
        if section["applicability"] == "not_applicable":
            section["reason"] = reference(section["reason"])
            continue
        if name == "prefactoring":
            for field in ("move", "preserved_observation"):
                section[field] = reference(section[field])
        elif name == "adr":
            for field in ("context", "decision"):
                section[field] = reference(section[field])
            for field in ("alternatives", "consequences"):
                section[field] = [reference(text) for text in section[field]]
        elif name == "boundaries":
            for field in ("driving_port", "dependency_direction"):
                section[field] = reference(section[field])
            section["driven_ports"] = [
                reference(text) for text in section["driven_ports"]
            ]
            for failure in section["failures"]:
                for field in ("condition", "observation"):
                    failure[field] = reference(failure[field])
        else:
            collection = (
                "parties"
                if name == "agreement_analysis"
                else "items"
                if name == "impact_closure"
                else "obligations"
            )
            for index, record in enumerate(section[collection], 1):
                if collection != "items":
                    record.setdefault("id", f"V{position}-{name}-{index}")
                for field in ("reason", "obligation", "observation"):
                    if field in record:
                        record[field] = reference(record[field])
    for field, text in manifest["public_oracle"].items():
        manifest["public_oracle"][field] = reference(text)
    manifest["facts"] = definitions
    return json.loads(json.dumps(manifest))


def referencing_manifest(
    facts: dict, observation: str, position: int, shared: dict
) -> dict:
    """A value DESIGN whose meaning already in ``shared`` references it once.

    Sibling values never repeat a fact: every sentence the bound shared DESIGN
    defines becomes a reference, and only the value's own new sentences stay
    defined in the value manifest.
    """
    manifest = design_manifest(
        {**facts, "facts": shared["facts"]}, observation, position
    )
    defined = {record["id"] for record in shared["facts"]}
    manifest["facts"] = [
        record for record in manifest["facts"] if record["id"] not in defined
    ]
    return manifest


def supplied_arguments(root, argv, answers, stdin):
    """Materialize the explicitly selected test-host action before invoking DES."""
    command = list(argv)
    if not command or "--input" in command or "--charter" in command:
        return command, stdin
    action = command[0]
    if action not in {"po", "design", "oracle", "craft"}:
        return command, stdin
    answer = answers[0] if answers else {}
    for name, body in answer.get("writes", {}).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    for name in answer.get("deletes", []):
        (root / name).unlink(missing_ok=True)
    payload = answer.get("structured_output", {"outcome": "accepted", "diagnostic": ""})
    if action == "po":
        if "values" not in payload:
            return command, stdin
        manifest = product_manifest(
            stdin, [item["observation"] for item in payload["values"]]
        )
        if not any(
            flag in command for flag in ("--feature", "--project", "--epic", "--slice")
        ):
            command.extend(("--feature", "fixture"))
    elif action == "design":
        if payload.get("outcome") != "accepted" or not isinstance(
            payload.get("manifest"), dict
        ):
            return command, stdin
        manifest = payload["manifest"]
    else:
        if action == "craft":
            payload = {**payload, "blocked_by": payload.get("blocked_by")}
        manifest = {"structured_output": payload}
    command.extend(("--input", "-"))
    return command, json.dumps(manifest)
