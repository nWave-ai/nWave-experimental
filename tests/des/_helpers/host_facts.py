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
    """Produce a complete JSON-valued manifest from the internal fixture facts."""
    heading = (
        facts.get("authority_locator", "").partition("#")[2] or f"Value {position}"
    )
    not_applicable = {
        "applicability": "not_applicable",
        "reason": "The fixture has no affected boundary.",
    }
    targets = [
        dict(item, reason=item.get("reason", "Own the fixture's public behavior."))
        for item in facts["targets"]
    ]
    manifest = {
        "schema_version": 1,
        "authority": {"heading": heading},
        "purpose": observation,
        "constraints": ["Preserve unrelated repository bytes."],
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
        "boundaries": dict(not_applicable),
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
    return json.loads(json.dumps(manifest))


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
