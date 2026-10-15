"""Independent semantic inputs, not schema-derived answers or legacy facts bridges.

Bounds below limit counterexample search only, never the admitted DESIGN language.
The complete baseline follows the incumbent public DESIGN constructor fixture.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from hypothesis import strategies as st
from tests.des._helpers.host_facts import design_manifest
from tests.des.architect_handoff.tests.test_g10 import fixture_context


VALUE = (
    "A host binds the architect's accepted manifest unchanged through the public "
    "DESIGN constructor and retains diagnostic-only nonaccepting responses."
)
DIAGNOSTICS = {
    "rejected": (
        "BLOCKED-BY: Missing product authority. WHAT: the selected value is absent. "
        "WHY: DESIGN cannot infer product intent. HOW: ask the product owner to "
        "supply the value. DEFECT-OWNER: product_owner."
    ),
    "indeterminate": (
        "BLOCKED-BY: Schema projection evidence unavailable. WHAT: installed "
        "contract cannot be observed. WHY: admission is unverified. HOW: restore "
        "the installer observation. DEFECT-OWNER: solution_architect."
    ),
}


def not_applicable(reason: str) -> dict:
    return {"applicability": "not_applicable", "reason": reason}


def _canonical_input() -> dict:
    """Complete source-specific semantic input, before catalog construction."""
    return {
        "schema_version": 2,
        "purpose": "Bind the architect response without translating its input.",
        "constraints": ["Preserve the selected product observation."],
        "targets": [
            {
                "path": "README.md",
                "decision": "EXTEND",
                "reason": "The existing document owns the public example.",
            }
        ],
        "paradigm": "object_oriented",
        "decisions": ["Submit the accepted manifest unchanged on stdin."],
        "reuse_analysis": {"candidates": []},
        "prefactoring": not_applicable("No preceding preserving move is required."),
        "agreement_analysis": not_applicable("No independent wire consumer changes."),
        "architectural_tests": not_applicable("No dependency boundary changes."),
        "contract_tests": not_applicable("No independently released contract changes."),
        "impact_closure": not_applicable("The fixture reaches no declared consumer."),
        "boundaries": not_applicable("The fixture introduces no new port."),
        "public_oracle": {
            "observation": VALUE,
            "stimulus": "Submit the architect's accepted manifest alone on stdin.",
            "expected": "DESIGN reports Success and persists the supplied observation.",
            "falsifier": "A translated input, refusal or missing bound observation.",
        },
        "oracle": "tests/test_manifest.py::test_accepted_manifest",
        "acceptance_supports": [],
        "verification": [["python", "-m", "pytest", "-q", "tests/test_manifest.py"]],
        "oracle_verification_index": 0,
    }


def canonical_manifest() -> dict:
    return design_manifest(_canonical_input(), VALUE, 1)


def product_manifest() -> dict:
    """The public PO constructor prerequisite, without a model or facts helper."""
    return {
        "schema_version": 2,
        "request": "Bind one accepted architect manifest directly through DESIGN.",
        "outcomes": [VALUE],
        "scope": {
            "in_scope": [VALUE],
            "out_of_scope": {
                "applicability": "not_applicable",
                "reason": "This isolated fixture has only the one stated observation.",
                "items": [],
            },
        },
        "decisions": ["Use the native stdin constructors without a provider turn."],
        "values": [{"observation": VALUE, "dependencies": []}],
        "jtbd": {"status": "not_explored"},
        "journey": {"status": "not_explored"},
        "gherkin": {"status": "not_explored"},
        "quint_scenarios": {"status": "not_run"},
    }


def accepted(manifest: dict) -> dict:
    return {
        "outcome": "accepted",
        "diagnostic": "The complete selected manifest is ready for host submission.",
        "manifest": copy.deepcopy(manifest),
    }


def decided_manifest() -> dict:
    """Constructively reachable applicable alternatives with valid linkages."""
    manifest = _canonical_input()
    manifest["reuse_analysis"]["candidates"] = [
        {
            "symbol": "Public example",
            "locator": "README.md:1",
            "decision": "REUSE",
            "reason": "The current document supplies the existing public example.",
        }
    ]
    manifest["prefactoring"] = {
        "applicability": "applicable",
        "existing_oracle": "tests/test_previous.py::test_previous_observation",
        "move": "Move the existing example without changing its observation.",
        "preserved_observation": "The existing example remains visible.",
        "verification": [["python", "-m", "pytest", "tests/test_previous.py"]],
        "acceptance_supports": [],
    }
    manifest["agreement_analysis"] = {
        "applicability": "applicable",
        "parties": [
            {
                "contract": "Public example",
                "role": role,
                "locator": locator,
                "decision": "UNCHANGED_COMPATIBLE",
                "reason": "The party retains the same public example.",
            }
            for role, locator in (
                ("producer", "README.md:1"),
                ("consumer", "tests/test_manifest.py:1"),
            )
        ],
    }
    obligation = {
        "obligation": "The public example preserves the selected observation.",
        "oracle": manifest["oracle"],
        "verification_index": 0,
    }
    manifest["architectural_tests"] = {
        "applicability": "applicable",
        "obligations": [copy.deepcopy(obligation)],
    }
    manifest["contract_tests"] = {
        "applicability": "applicable",
        "obligations": [
            {
                **obligation,
                "contract": "Public example",
                "producer": "README.md:1",
                "consumer": "tests/test_manifest.py:1",
                "observation": VALUE,
            }
        ],
    }
    manifest["impact_closure"] = {
        "applicability": "applicable",
        "items": [
            {
                "kind": kind,
                "locator": locator,
                "decision": "UNCHANGED_COMPATIBLE",
                "reason": "The existing example and consumer remain compatible.",
            }
            for kind, locator in (
                ("runtime", "README.md"),
                ("consumer", "tests/test_manifest.py:1"),
            )
        ],
    }
    manifest["boundaries"] = {
        "applicability": "applicable",
        "driving_port": "des design --input -",
        "driven_ports": ["Architecture document", "Persisted handover"],
        "dependency_direction": "The public constructor consumes the manifest.",
        "failures": [
            {
                "condition": "The submitted manifest violates the v1 contract.",
                "outcome": "Refusal",
                "observation": "InvalidDesignDocument without authority mutation.",
            }
        ],
    }
    return manifest


def typed_handoff() -> tuple[dict, list[dict]]:
    """Construct the current typed fixture with its explicit catalog."""
    path = (
        Path(__file__).resolve().parents[2] / "architect_handoff/fixtures/oo.g10.json"
    )
    normalized, catalog, _driven = fixture_context(
        json.loads(path.read_text(encoding="utf-8"))
    )
    for section in normalized["sections"]:
        section["scope"] = "value:1"
    return normalized, [
        {"id": record.id, "text": record.text} for record in catalog.records
    ]


@dataclass(frozen=True)
class ManifestCase:
    """Independent expectations for the observation that survives transport."""

    manifest: dict

    @property
    def public_observation(self) -> dict:
        return self.manifest["public_oracle"]


def finite_manifests() -> list[ManifestCase]:
    plain = _canonical_input()
    adr = decided_manifest()
    adr["adr"] = {
        "applicability": "applicable",
        "context": "The host consumes the architect response.",
        "decision": "Submit the accepted manifest unchanged.",
        "alternatives": ["Translate provider facts into another carrier."],
        "consequences": ["The constructor consumes exactly the supplied input."],
        "status": "accepted",
    }
    handoff = _canonical_input()
    handoff["architect_handoff"], handoff["facts"] = typed_handoff()
    # Intrinsically nullable typed fields are not the nonnullable manifest optionals.
    handoff["architect_handoff"]["sections"][0]["status"]["payload"]["generators"][0][
        "depth_bound"
    ] = None
    unbounded_contract = _canonical_input()
    unbounded_contract["purpose"] = "x" * 256
    unbounded_contract["constraints"] = [
        f"Distinct admitted constraint {index}" for index in range(5)
    ]
    empty_constraints = _canonical_input()
    empty_constraints["constraints"] = []
    return [
        ManifestCase(design_manifest(plain, VALUE, 1)),
        ManifestCase(design_manifest(adr, VALUE, 1)),
        ManifestCase(design_manifest(handoff, VALUE, 1)),
        ManifestCase(design_manifest(unbounded_contract, VALUE, 1)),
        ManifestCase(design_manifest(empty_constraints, VALUE, 1)),
    ]


@st.composite
def manifest_cases(draw):
    """One preservation law: independent semantic input -> projection -> binding.

    Generate the alternative first. No filtering or production admission oracle.
    Hypothesis retains normal shrinking and example-database replay.
    """
    alternative = draw(st.sampled_from(("plain", "decided", "typed")))
    manifest = decided_manifest() if alternative == "decided" else _canonical_input()
    text = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789éλ",
        min_size=1,
        max_size=64,
    )
    distinct_texts = st.lists(
        text,
        min_size=1,
        max_size=4,
        unique_by=str.casefold,
    )
    manifest["purpose"] = draw(text)
    manifest["constraints"] = draw(distinct_texts)
    manifest["decisions"] = draw(distinct_texts)
    manifest["paradigm"] = draw(
        st.sampled_from(("object_oriented", "functional", "procedural"))
    )
    manifest["targets"][0]["decision"] = draw(st.sampled_from(("EXTEND", "CREATE_NEW")))
    manifest["targets"][0]["reason"] = draw(text)
    manifest["acceptance_supports"] = [
        f"tests/support/input_{index}.py" for index in range(draw(st.integers(0, 4)))
    ]
    for name in manifest["public_oracle"]:
        manifest["public_oracle"][name] = draw(text)
    adr = draw(st.sampled_from(("absent", "not_applicable", "applicable")))
    if adr == "not_applicable":
        manifest["adr"] = not_applicable(draw(text))
    if adr == "applicable":
        manifest["adr"] = {
            "applicability": adr,
            "context": draw(text),
            "decision": draw(text),
            "alternatives": draw(distinct_texts),
            "consequences": draw(distinct_texts),
            "status": draw(st.sampled_from(("proposed", "accepted"))),
        }
    if alternative == "typed":
        manifest["architect_handoff"], manifest["facts"] = typed_handoff()
        manifest["architect_handoff"]["sections"][0]["status"]["payload"]["generators"][
            0
        ]["depth_bound"] = draw(st.one_of(st.none(), st.integers(1, 4)))
    return ManifestCase(design_manifest(manifest, VALUE, 1))
