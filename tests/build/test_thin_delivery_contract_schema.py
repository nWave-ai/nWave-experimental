"""Executable boundary for the host-neutral thin DeliveryContract schema.

The schema proves the shape of declared authority only.  Admission remains
responsible for comparing those declarations with the host diff, commands, and
evidence; JSON Schema does not establish that cross-document conformance.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError


SCHEMA_PATH = Path("nWave/schemas/thin-delivery-contract.schema.json")
TARGET_PATH = "nWave/schemas/thin-delivery-contract.schema.json"
CHECKED_IN_CONTRACTS = Path("docs/delivery-contracts")

ALL_OBLIGATION_KINDS = (
    "CONTESTED_LAW",
    "REPRESENTATION_CHANGE",
    "INVALID_STATE",
    "PRESERVATION",
    "BROAD_INPUT_DOMAIN",
    "REUSE_CANDIDATE",
    "ARCHITECTURE_BOUNDARY_CHANGE",
)


def _target_plan() -> dict[str, Any]:
    return {
        "candidate": "nWave/schemas/component-manifest.schema.json",
        "overlap": "Draft 2020-12 identity and closed-object vocabulary.",
        "decision": "CREATE_NEW",
        "justification": "The component manifest is feature-component-specific.",
        "declared-imports": [],
        "contract-shape": "bounded-change",
        "boundary": {
            "failure-behavior": "Reject malformed declared authority before routing.",
            "substrate-lie": "Schema validity does not prove a host route exists.",
            "substrate-probe": "Validate the declared contract with Draft 2020-12.",
            "double-blind-spot": "A schema cannot observe the repository diff.",
        },
    }


def _repository_executable_command(path: str, *arguments: str) -> dict[str, Any]:
    return {
        "executable": {"kind": "repository", "path": path},
        "arguments": list(arguments),
    }


def _toolchain_executable_command(name: str, *arguments: str) -> dict[str, Any]:
    return {
        "executable": {"kind": "toolchain", "name": name},
        "arguments": list(arguments),
    }


def _contract(paradigm: str) -> dict[str, Any]:
    return {
        "schema-version": "1.2",
        "delivery-id": "thin-delivery-contract-schema",
        "repository": {
            "worktree": ".",
            "base-revision": f"git-sha1:{'a' * 40}",
        },
        "outcome": "Validate one immutable delivery contract before direct role routing.",
        "targets": {TARGET_PATH: _target_plan()},
        "paradigm": paradigm,
        "delivery-route": "RED_TO_GREEN",
        "obligations": ["REUSE_CANDIDATE"],
        "acceptance-tests": {
            "locator": "tests/build/test_thin_delivery_contract_schema.py",
            "digest": f"sha256:{'b' * 64}",
        },
        "verification-scope": {
            "commands": [
                _toolchain_executable_command(
                    "uv",
                    "run",
                    "pytest",
                    "tests/build/test_thin_delivery_contract_schema.py",
                    "-q",
                )
            ]
        },
        "applicability": {
            "independent-review": True,
            "examine": False,
        },
        "budget": {
            "token-limit": 12000,
            "wall-clock-minutes": 30,
        },
    }


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _errors(contract: dict[str, Any]) -> list[ValidationError]:
    return list(_validator().iter_errors(contract))


def _resolve_local_ref(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in node:
        return node
    assert node["$ref"].startswith("#/$defs/")
    return schema["$defs"][node["$ref"].removeprefix("#/$defs/")]


def test_thin_delivery_contract_schema_identity_and_draft_are_valid() -> None:
    schema = _schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        schema["$id"] == "https://nwave.ai/schemas/thin-delivery-contract.schema.json"
    )
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("paradigm", ["object_oriented", "functional"])
def test_complete_thin_delivery_contract_validates(paradigm: str) -> None:
    assert _errors(_contract(paradigm)) == []


@pytest.mark.parametrize(
    "contract_path",
    sorted(CHECKED_IN_CONTRACTS.glob("*.json")),
    ids=lambda path: path.name,
)
def test_every_checked_in_delivery_contract_uses_the_current_schema(
    contract_path: Path,
) -> None:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert _errors(contract) == [], (
        "WHAT: a checked-in DeliveryContract no longer validates against the sole "
        "current schema. "
        "WHY: changing canonical authority without migrating its live instances "
        "creates two effective contract versions. "
        f"HOW: migrate {contract_path} in the same vertical as the schema change."
    )


Mutation = Callable[[dict[str, Any]], None]


def _remove_paradigm(contract: dict[str, Any]) -> None:
    del contract["paradigm"]


def _remove_evidence_locator(contract: dict[str, Any]) -> None:
    del contract["acceptance-tests"]["locator"]


def _remove_obligations(contract: dict[str, Any]) -> None:
    del contract["obligations"]


@pytest.mark.parametrize(
    ("mutate", "expected_path"),
    [
        (_remove_paradigm, ()),
        (_remove_evidence_locator, ("acceptance-tests",)),
        (_remove_obligations, ()),
    ],
)
def test_contract_rejects_missing_required_authority(
    mutate: Mutation,
    expected_path: tuple[str, ...],
) -> None:
    contract = copy.deepcopy(_contract("object_oriented"))
    mutate(contract)

    assert any(
        tuple(error.absolute_path) == expected_path and error.validator == "required"
        for error in _errors(contract)
    )


@pytest.mark.parametrize("kind", ALL_OBLIGATION_KINDS)
def test_every_closed_obligation_kind_validates_alone(kind: str) -> None:
    contract = _contract("object_oriented")
    contract["obligations"] = [kind]

    assert _errors(contract) == []


def _empty_obligations(contract: dict[str, Any]) -> None:
    contract["obligations"] = []


def _duplicate_obligations(contract: dict[str, Any]) -> None:
    contract["obligations"] = ["REUSE_CANDIDATE", "REUSE_CANDIDATE"]


def _unknown_obligation(contract: dict[str, Any]) -> None:
    contract["obligations"] = ["NOT_A_CLOSED_ENUM_KIND"]


@pytest.mark.parametrize(
    ("mutate", "expected_validator"),
    [
        (_empty_obligations, "minItems"),
        (_duplicate_obligations, "uniqueItems"),
        (_unknown_obligation, "enum"),
    ],
)
def test_contract_rejects_empty_duplicate_or_unknown_obligations(
    mutate: Mutation,
    expected_validator: str,
) -> None:
    contract = copy.deepcopy(_contract("object_oriented"))
    mutate(contract)

    assert any(
        tuple(error.absolute_path)[:1] == ("obligations",)
        and error.validator == expected_validator
        for error in _errors(contract)
    ), (
        "WHAT: an empty, duplicate, or unknown-kind obligations array was accepted. "
        "WHY: obligations is a non-vacuous, duplicate-free, closed-world set. "
        "HOW: reject empty arrays (minItems), duplicate kinds (uniqueItems), and "
        "any kind outside the closed enum."
    )


def test_schema_has_no_finalize_property() -> None:
    schema = _schema()

    assert "finalize" not in schema["properties"]
    assert "finalize" not in schema["$defs"], (
        "WHAT: the schema defines a finalize shape. "
        "WHY: finalize is end-of-delivery promotion and filesystem cleanup, not "
        "per-slice DeliveryContract data. "
        "HOW: keep finalize outside this schema and run it once after the whole "
        "delivery completes."
    )


@pytest.mark.parametrize(
    "invalid_target",
    [
        "/tmp/absolute-target.py",
        "../traversal.py",
        "src/des/../outside-target.py",
        "src//empty-segment.py",
        r"src\backslash-escape.py",
        "tests/build/test_*.py",
    ],
)
def test_contract_rejects_non_relative_or_pattern_target_keys(
    invalid_target: str,
) -> None:
    contract = _contract("object_oriented")
    contract["targets"] = {invalid_target: _target_plan()}

    assert any(
        tuple(error.absolute_path) == ("targets",) and error.validator == "pattern"
        for error in _errors(contract)
    )


@pytest.mark.parametrize(
    "repository_relative_path",
    [
        "__main__.py",
        "_catalog.yaml",
        ".github/workflows/ci.yml",
        "crates/engine/src/main.rs",
    ],
)
def test_contract_accepts_safe_language_agnostic_targets_and_candidates(
    repository_relative_path: str,
) -> None:
    contract = _contract("object_oriented")
    target_plan = _target_plan()
    target_plan["candidate"] = repository_relative_path
    contract["targets"] = {repository_relative_path: target_plan}

    assert _errors(contract) == [], (
        "WHAT: a safe repository-relative path was rejected. "
        "WHY: repositoryRelativePath is coupled to Python-like segments. "
        "HOW: accept safe dot/underscore and language-neutral segments while retaining "
        "absolute, traversal, empty-segment, and backslash rejection."
    )


@pytest.mark.parametrize("declared_import", ["@scope/pkg", "crate::module", "My.App"])
def test_contract_accepts_language_agnostic_declared_import_references(
    declared_import: str,
) -> None:
    contract = _contract("functional")
    contract["targets"][TARGET_PATH]["declared-imports"] = [declared_import]

    assert _errors(contract) == [], (
        "WHAT: a valid non-Python declared import was rejected. "
        "WHY: declared-imports is constrained to Python module notation. "
        "HOW: accept language-neutral references without weakening path validation."
    )


@pytest.mark.parametrize(
    "declared_import",
    [
        "/absolute/import",
        "../traversal",
        "package..empty_segment",
        r"package\\backslash_escape",
        "package.*",
    ],
)
def test_contract_rejects_unsafe_declared_import_references(
    declared_import: str,
) -> None:
    contract = _contract("functional")
    contract["targets"][TARGET_PATH]["declared-imports"] = [declared_import]

    assert any(
        tuple(error.absolute_path) == ("targets", TARGET_PATH, "declared-imports", 0)
        and error.validator == "pattern"
        for error in _errors(contract)
    ), (
        "WHAT: an unsafe declared import reference was accepted. "
        "WHY: imports must not escape or expand outside their declared reference. "
        "HOW: reject absolute, traversal, empty-segment, backslash, and glob references."
    )


def _remove_target_overlap(contract: dict[str, Any]) -> None:
    del contract["targets"][TARGET_PATH]["overlap"]


def _invalidate_target_decision(contract: dict[str, Any]) -> None:
    contract["targets"][TARGET_PATH]["decision"] = "create-new"


def _remove_target_contract_shape(contract: dict[str, Any]) -> None:
    del contract["targets"][TARGET_PATH]["contract-shape"]


@pytest.mark.parametrize(
    ("mutate", "expected_path", "expected_validator"),
    [
        (_remove_target_overlap, ("targets", TARGET_PATH), "required"),
        (_invalidate_target_decision, ("targets", TARGET_PATH, "decision"), "enum"),
        (_remove_target_contract_shape, ("targets", TARGET_PATH), "required"),
    ],
)
def test_contract_rejects_incomplete_or_invalid_target_plan(
    mutate: Mutation,
    expected_path: tuple[str, ...],
    expected_validator: str,
) -> None:
    contract = copy.deepcopy(_contract("functional"))
    mutate(contract)

    assert any(
        tuple(error.absolute_path) == expected_path
        and error.validator == expected_validator
        for error in _errors(contract)
    )


@pytest.mark.parametrize(
    ("legacy_property", "container"),
    [
        ("allowed-paths", None),
        ("reuse-decisions", None),
        ("architecture-boundaries", None),
        ("contract-shapes", None),
        ("substrate-lies", None),
        ("targets", "verification-scope"),
    ],
)
def test_contract_rejects_parallel_target_authority(
    legacy_property: str,
    container: str | None,
) -> None:
    contract = _contract("object_oriented")
    target = contract if container is None else contract[container]
    target[legacy_property] = []
    expected_path = () if container is None else (container,)

    assert any(
        tuple(error.absolute_path) == expected_path
        and error.validator == "additionalProperties"
        for error in _errors(contract)
    )


@pytest.mark.parametrize(
    "shell_string_command",
    [
        "uv run pytest tests/build/test_thin_delivery_contract_schema.py -q",
        "pytest 'tests/path with spaces/test_x.py'",
        "make test && make lint",
    ],
)
def test_contract_rejects_a_shell_string_verification_command(
    shell_string_command: str,
) -> None:
    contract = _contract("object_oriented")
    contract["verification-scope"]["commands"] = [shell_string_command]

    assert any(
        tuple(error.absolute_path) == ("verification-scope", "commands", 0)
        and error.validator == "type"
        for error in _errors(contract)
    ), (
        "WHAT: a verification command was accepted as a single shell string. "
        "WHY: a string leaves word-splitting, quoting, and metacharacter handling "
        "to whoever executes it, so the same declaration means different things. "
        "HOW: declare each command as an argv vector, e.g. "
        '["uv", "run", "pytest", "tests/path with spaces/test_x.py", "-q"].'
    )


@pytest.mark.parametrize(
    ("commands", "expected_path", "expected_validator"),
    [
        (
            [{"executable": {"kind": "toolchain", "name": ""}, "arguments": []}],
            ("verification-scope", "commands", 0, "executable", "name"),
            "minLength",
        ),
        (
            [_toolchain_executable_command("uv", "")],
            ("verification-scope", "commands", 0, "arguments", 0),
            "minLength",
        ),
        ([], ("verification-scope", "commands"), "minItems"),
    ],
)
def test_contract_rejects_empty_verification_argv(
    commands: list[Any],
    expected_path: tuple[str | int, ...],
    expected_validator: str,
) -> None:
    contract = _contract("functional")
    contract["verification-scope"]["commands"] = commands

    def _flatten(errors: list[ValidationError]) -> list[ValidationError]:
        flattened = []
        for error in errors:
            flattened.append(error)
            flattened.extend(_flatten(list(error.context or [])))
        return flattened

    assert any(
        tuple(error.absolute_path) == expected_path
        and error.validator == expected_validator
        for error in _flatten(_errors(contract))
    ), (
        "WHAT: an empty toolchain name, an empty argument token, or an empty "
        "commands array was accepted. "
        "WHY: none of these name a runnable executable, so verification would "
        "report success without executing anything. "
        "HOW: every toolchain name and every argument token needs at least one "
        "character; the commands array itself needs at least one entry."
    )


@pytest.mark.parametrize(
    "literal_token",
    [
        "tests/path with spaces/test_x.py",
        "-k=name and other",
        "$HOME/not-expanded",
        "a;b|c>d",
        "*.py",
    ],
)
def test_contract_accepts_a_literal_token_without_splitting_it(
    literal_token: str,
) -> None:
    """A token stays one token.

    The schema proves the DECLARATION is unambiguous: a path with spaces or a
    metacharacter occupies exactly one argv slot and cannot be re-read as shell
    syntax.  It does not prove the executor passes it through unchanged -- that
    is an execution property and belongs to whoever runs the vector.
    """
    contract = _contract("object_oriented")
    contract["verification-scope"]["commands"] = [
        _toolchain_executable_command("uv", "run", "pytest", literal_token)
    ]

    assert _errors(contract) == []
    assert (
        contract["verification-scope"]["commands"][0]["arguments"][2] == literal_token
    )


@pytest.mark.parametrize(
    ("command", "expect_valid"),
    [
        (["python3", "manage.py", "test"], False),
        (
            _repository_executable_command(
                "k4-fixture-venv/bin/python", "manage.py", "test"
            ),
            True,
        ),
        (_toolchain_executable_command("uv", "run", "pytest", "-q"), True),
        (
            {
                "executable": {
                    "kind": "repository",
                    "path": "k4-fixture-venv/bin/python",
                    "name": "python",
                },
                "arguments": ["manage.py", "test"],
            },
            False,
        ),
        (
            {
                "executable": {"kind": "system", "path": "python3"},
                "arguments": ["manage.py", "test"],
            },
            False,
        ),
    ],
    ids=[
        "bare-argv-ambiguous-interpreter",
        "repository-executable-identity",
        "toolchain-executable-identity",
        "executable-both-path-and-name",
        "executable-unknown-kind",
    ],
)
def test_verification_command_is_a_tagged_executable_identity_not_bare_argv(
    command: object,
    expect_valid: bool,
) -> None:
    """CONTRACT_SHAPE: a verification-scope.commands element is the executable-
    identity sum type -- {kind: repository, path} | {kind: toolchain, name} --
    paired with a literal `arguments` array, not a raw argv vector.
    """
    # A bare argv vector lets the producer's PATH pick which `python3` (or `uv`)
    # actually runs, so the declared command silently changes meaning downstream.
    contract = _contract("object_oriented")
    contract["verification-scope"]["commands"] = [command]

    errors = _errors(contract)

    if expect_valid:
        assert errors == []
    else:
        assert errors != []


def test_targets_are_path_keyed_without_a_second_target_designation() -> None:
    schema = _schema()
    targets = _resolve_local_ref(schema, schema["properties"]["targets"])
    target_plan = _resolve_local_ref(schema, targets["additionalProperties"])

    assert "propertyNames" in targets
    assert "target" not in target_plan["properties"]
    assert "target" not in target_plan["required"]


DELIVERY_ROUTE_VALUES = ("RED_TO_GREEN", "GREEN_TO_GREEN")


@pytest.mark.parametrize("delivery_route", DELIVERY_ROUTE_VALUES)
@pytest.mark.parametrize("examine", [True, False])
def test_every_delivery_route_validates_crossed_with_examine(
    delivery_route: str,
    examine: bool,
) -> None:
    contract = _contract("object_oriented")
    contract["delivery-route"] = delivery_route
    contract["applicability"]["examine"] = examine

    assert _errors(contract) == []


def test_contract_rejects_missing_delivery_route() -> None:
    contract = _contract("object_oriented")
    del contract["delivery-route"]

    assert any(
        tuple(error.absolute_path) == () and error.validator == "required"
        for error in _errors(contract)
    ), (
        "WHAT: a DeliveryContract without a top-level delivery-route was accepted. "
        "WHY: the execution route (RED_TO_GREEN vs GREEN_TO_GREEN) is declared "
        "authority the host must know before routing, not an inferred default. "
        "HOW: require delivery-route as a top-level property of every contract."
    )


@pytest.mark.parametrize(
    "invalid_delivery_route",
    [
        "RED-TO-GREEN",
        "NOT_A_ROUTE",
        "red_to_green",
        "",
    ],
    ids=["near-miss-hyphenated", "unknown-value", "wrong-case", "empty-string"],
)
def test_contract_rejects_non_enum_delivery_route(
    invalid_delivery_route: str,
) -> None:
    contract = _contract("object_oriented")
    contract["delivery-route"] = invalid_delivery_route

    assert any(
        tuple(error.absolute_path) == ("delivery-route",) and error.validator == "enum"
        for error in _errors(contract)
    ), (
        "WHAT: a delivery-route value outside the closed two-value enum was accepted. "
        "WHY: delivery-route is a closed-world switch -- RED_TO_GREEN or "
        "GREEN_TO_GREEN, exactly -- not a free string a near-miss spelling can "
        "silently slip past. "
        f"HOW: reject {invalid_delivery_route!r} and every value that is not "
        "exactly one of the two closed enum members."
    )


def test_schema_acceptance_does_not_claim_host_conformance() -> None:
    contract = _contract("object_oriented")
    contract["targets"] = {"src/declared-but-unobserved.py": _target_plan()}
    contract["acceptance-tests"]["locator"] = "tests/declared-but-unobserved.py"

    # Admission, not JSON Schema, must compare these declarations with the host.
    assert _errors(contract) == []
