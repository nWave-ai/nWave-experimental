"""Acceptance: one manifest response survives every host and binds unchanged.

The generated law has the explicit preservation map:
independent ManifestCase -> actual installed/canonical/Codex admission -> JSON
stdin at the real dispatcher -> matching persisted public_oracle and restored
state. The single subprocess journey witnesses that same observation with real
terminal wiring. Examples retain existing constructor refusal/CAS selections;
the expanded verification recipe owns the already-established CAS fault tests.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import event, given, settings
from tests.des.acceptance.architect_manifest_binding.public_observation import (
    ArchitectObservation,
    explanation,
    schema_errors,
    schema_nodes,
)
from tests.des.acceptance.architect_manifest_binding.semantic_cases import (
    DIAGNOSTICS,
    ManifestCase,
    accepted,
    canonical_manifest,
    finite_manifests,
    manifest_cases,
)

from des.domain.design_document import DesignDocument


@pytest.fixture(scope="module")
def host(tmp_path_factory) -> ArchitectObservation:
    """Provision the real installation/base repo once; isolate cheap namespaces."""
    return ArchitectObservation(tmp_path_factory.mktemp("architect-manifest"))


def assert_projection_and_binding(
    host: ArchitectObservation, case: ManifestCase
) -> None:
    """One law through all declared projections and the same real public consumer."""
    response = accepted(case.manifest)
    host.validate_response(response)
    host.decode_response(response)
    with tempfile.TemporaryDirectory(dir=host.workspace, prefix="bind-") as directory:
        root = host.new_repository(Path(directory))
        host.bootstrap(root)
        host.bind(root, case)


def test_projected_manifest_binds_without_translation(
    host: ArchitectObservation,
) -> None:
    """@walking_skeleton @driving_port @contract-shape: real-io"""
    with tempfile.TemporaryDirectory(
        dir=host.workspace, prefix="journey-"
    ) as directory:
        root = host.new_repository(Path(directory))
        host.bootstrap(root, process=True)
        case = ManifestCase(canonical_manifest())
        # This first behavioral assertion is the reported installed-schema defect,
        # not collection/setup failure or the absence of future compiler methods.
        host.validate_response(accepted(case.manifest))
        host.decode_response(accepted(case.manifest))
        host.bind(root, case, process=True)
        host.assert_nonaccepting(root)


def test_schema_follows_the_design_contract(host: ArchitectObservation) -> None:
    """@contract-shape: real-io; whole current grammar, not copied source phrases."""
    host.validate_response(accepted(canonical_manifest()))
    compile_schema = getattr(DesignDocument, "input_schema", None)
    assert callable(compile_schema), explanation(
        "the DESIGN contract publishes no complete manifest schema",
        "The form owner, not a parallel provider definition, must own the language.",
        "Extend its existing compiler and expose DesignDocument.input_schema.",
    )
    domain = compile_schema()
    domain_properties = domain["properties"]
    for name in ("installed-omp", "canonical-claude"):
        projections = [
            node
            for node in schema_nodes(host.schemas[name])
            if set(node.get("properties", {})) == set(domain_properties)
        ]
        assert projections, explanation(
            f"{name} has no projection of the domain manifest population "
            f"{sorted(domain_properties)!r}",
            "New domain fields must flow to every canonical host without a second schema edit.",
            "Consume the complete domain-generated schema in the architect envelope.",
        )
        for projection in projections:
            assert projection["properties"] == domain_properties and (
                set(projection.get("required", ())) == set(domain["required"])
                and projection.get("additionalProperties") is False
            ), explanation(
                f"{name} diverges from the owning domain schema",
                "Required fields, nested forms and closure must come from the single form authority.",
                "Reuse the domain compiler output rather than maintaining a provider copy.",
            )
    for case in finite_manifests():
        assert not schema_errors(domain, case.manifest), explanation(
            f"domain projection refuses independently admitted input {case.manifest!r}",
            "Whole-manifest projection must carry tagged and typed nested alternatives.",
            "Compile all current DESIGN forms with their actual types and optional semantics.",
        )
        host.validate_response(accepted(case.manifest))
    # Mechanical population discovery, never a hard-coded optional-field list.
    optional = set(domain_properties) - set(domain["required"])
    for field in optional:
        if not schema_errors(domain_properties[field], None):
            continue
        invalid = canonical_manifest()
        invalid[field] = None
        host.validate_response(accepted(invalid), admitted=False)


def malformed_responses() -> list[dict]:
    valid = accepted(canonical_manifest())
    missing = {key: value for key, value in valid.items() if key != "manifest"}
    null = {**valid, "manifest": None}
    legacy = {
        "outcome": "accepted",
        "diagnostic": "Historical provider facts are not a constructor manifest.",
        "design_facts": {},
    }
    return [
        missing,
        null,
        legacy,
        {**valid, "design_facts": {}},
        *(
            {**valid, "outcome": outcome, "diagnostic": diagnostic}
            for outcome, diagnostic in DIAGNOSTICS.items()
        ),
    ]


def test_only_the_manifest_response_binds(host: ArchitectObservation) -> None:
    """@contract-shape: real-io; provider facts refusal != internal facts loss."""
    for response in malformed_responses():
        host.validate_response(response, admitted=False)
        host.decode_response(response, admitted=False)
    assert_projection_and_binding(host, ManifestCase(canonical_manifest()))


def test_installed_schema_preserves_outcome_meaning(host: ArchitectObservation) -> None:
    """@contract-shape: real-io; finite outcome/null/absence and opaque ownership."""
    with tempfile.TemporaryDirectory(
        dir=host.workspace, prefix="diagnostics-"
    ) as directory:
        root = host.new_repository(Path(directory))
        host.bootstrap(root)
        host.assert_nonaccepting(root)
    for outcome, diagnostic in DIAGNOSTICS.items():
        for bad_diagnostic in ("", None):
            invalid = {
                "outcome": outcome,
                "diagnostic": bad_diagnostic,
                "manifest": None,
            }
            host.validate_response(invalid, admitted=False)
        # Ownership is instruction semantics, never a regular-expression gate.
        opaque = {
            "outcome": outcome,
            "diagnostic": "Opaque assessment: λ / é / prose is not a routing instruction.",
            "manifest": None,
        }
        host.validate_response(opaque)
        host.decode_response(opaque)


def test_strict_projection_preserves_manifest_admission(
    host: ArchitectObservation,
) -> None:
    """@contract-shape: real-io; strict object branches, answer-only transport."""
    strict_nodes = [
        node
        for node in schema_nodes(host.schemas["codex"])
        if isinstance(node.get("properties"), dict)
    ]
    assert strict_nodes, explanation(
        "Codex emitted no strict object branch population",
        "An unexamined or empty projection cannot prove strict transport admission.",
        "Publish the architect response through the existing Codex answer schema.",
    )
    for node in strict_nodes:
        assert set(node.get("required", ())) == set(node["properties"]) and (
            node.get("additionalProperties") is False
        ), explanation(
            f"Codex object is not strict: {node!r}",
            "Optional absence must be represented by object alternatives, not relaxed strictness.",
            "Recursively derive closed presence/absence branches from the domain schema.",
        )
    for case in finite_manifests():
        assert_projection_and_binding(host, case)
        transported = json.loads(
            json.dumps({"answer": accepted(case.manifest)}, ensure_ascii=False)
        )
        assert transported["answer"]["manifest"] == case.manifest, explanation(
            "answer-wrapper removal changed the supplied manifest",
            "The host removes only the transport wrapper, not optional values or semantic fields.",
            "Submit the unwrapped manifest unchanged through stdin.",
        )


def invalid_manifest_cases() -> list[dict]:
    """Finite distinguishable structural and semantic schema-2 refusals."""
    base = canonical_manifest()
    cases = []
    for field, value in (
        ("schema_version", True),
        ("schema_version", 1),
        ("authority", {"heading": "# Not a plain heading"}),
        (
            "targets",
            [
                {
                    "path": "../escape.py",
                    "decision": "EXTEND",
                    "reason": base["targets"][0]["reason"],
                }
            ],
        ),
        ("constraints", [base["constraints"][0]] * 2),
        ("oracle_verification_index", -1),
        ("oracle_verification_index", 1),  # structurally allowed, semantically unlinked
        ("verification", [["python", "NUL\u0000argument"]]),
        ("acceptance_supports", ["tests/test_manifest.py"]),
        ("acceptance_supports", ["README.md"]),
        ("adr", None),
        ("architect_handoff", None),
    ):
        cases.append({**copy.deepcopy(base), field: value})
    extra = copy.deepcopy(base)
    extra["undeclared_carrier"] = {}
    cases.append(extra)
    missing = copy.deepcopy(base)
    missing.pop("purpose")
    cases.append(missing)
    missing_constraints = copy.deepcopy(base)
    missing_constraints.pop("constraints")
    cases.append(missing_constraints)
    decided = finite_manifests()[1].manifest
    for field, value in (
        (
            "impact_closure",
            {"applicability": "not_applicable", "reason": decided["purpose"]},
        ),
        (
            "agreement_analysis",
            {"applicability": "not_applicable", "reason": decided["purpose"]},
        ),
    ):
        cases.append({**copy.deepcopy(decided), field: value})
    duplicate_path = copy.deepcopy(base)
    duplicate_path["targets"].append(
        {**base["targets"][0], "reason": {"ref": "V1-duplicate-path"}}
    )
    duplicate_path["facts"].append(
        {
            "id": "V1-duplicate-path",
            "text": "Different record, same path.",
        }
    )
    cases.append(duplicate_path)
    return cases


def test_existing_manifest_refusals_preserve_public_state(
    host: ArchitectObservation,
) -> None:
    """@contract-shape: real-io; structural projection never replaces semantic admission."""
    with tempfile.TemporaryDirectory(
        dir=host.workspace, prefix="refusals-"
    ) as directory:
        root = host.new_repository(Path(directory))
        host.bootstrap(root)
        host.bind(root, ManifestCase(canonical_manifest()))
        for invalid in invalid_manifest_cases():
            host.assert_invalid_constructor(root, invalid)
            host.decode_response(accepted(invalid), admitted=False)
    # Explicit incapable/malformed vs genuinely valid discriminators: the same
    # consumer above successfully bound one admitted input before refusing these.


@settings(max_examples=24, deadline=None, print_blob=True)
@given(case=manifest_cases())
def test_manifest_meaning_survives_projection_and_direct_binding(
    host: ArchitectObservation, case: ManifestCase
) -> None:
    """@contract-shape: real-io; bounded search, native shrinking/database replay.

    The generated public_oracle is the independent expected value, not a
    schema-generated specimen or production serialization used as its own oracle.
    """
    event(f"paradigm={case.manifest['paradigm']}")
    event(f"adr={case.manifest.get('adr', {}).get('applicability', 'absent')}")
    event(f"typed-handoff={'architect_handoff' in case.manifest}")
    event(f"decisions={case.manifest['agreement_analysis']['applicability']}")
    assert_projection_and_binding(host, case)
