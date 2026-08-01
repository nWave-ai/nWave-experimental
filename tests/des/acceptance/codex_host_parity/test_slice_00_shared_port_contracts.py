"""Active-RED acceptance contract for the sole slice-01 (S0 lane) driving port.

@feature-codex-host-parity
@slice-01
@contract-shape:in-memory

The tests use only the production composition root.  Five independent doubles
witness the five DESIGN ports; no test-owned façade reproduces the journey.
"""

from __future__ import annotations

from collections.abc import Mapping
from inspect import signature

import pytest

from .composition import CodexParityJourneyComposition, diagnostic_field, field
from .port_witnesses import FivePortWitnesses


pytestmark = [pytest.mark.acceptance]

# Independent oracle for sha256(canonical JSON of the three frozen build inputs).
_CANDIDATE_ID = "febc8331fdccf9913bfbcddece8df239a2af85dc353be1080dcd27d1f1ee1eac"


def _request(*, arms: list[Mapping[str, object]] | None = None) -> dict[str, object]:
    # These subjects are distinct values. Only the top-level selection is the
    # canonical carrier that the root must pass to acquire_lease.
    subject: dict[str, object] = {
        "composition_id": "codex-cli-linux-native",
        "candidate_id": _CANDIDATE_ID,
        "manifest_digest": "manifest-1",
        "requested_platform": "CODEX",
        "target_selection": {
            "requested_platform": "CODEX",
            "detected_capabilities": ["codex-installed"],
        },
    }
    plan_subject = dict(subject)
    plan_subject["target_selection"] = dict(subject["target_selection"])
    probe_subject = dict(subject)
    probe_subject["target_selection"] = dict(subject["target_selection"])
    return {
        "subject": subject,
        "build_inputs": {
            "distribution_digest": "distribution-1",
            "public_manifest_digest": "manifest-1",
            "build_recipe_version": "recipe-1",
        },
        "assembled_candidate": {
            "locator": "candidate-1.whl",
            "origin": "ASSEMBLED_DISTRIBUTION",
            "declared_digest": "distribution-1",
        },
        "treatment_plan": {
            "subject": plan_subject,
            "intents": [{"key": "nwave/role.toml"}],
        },
        "probe": {
            "subject": probe_subject,
            "workload_digest": "workload-1",
            "witnesses": [
                {
                    "id": "role-load",
                    "item": "role:specialist",
                    "suite": "role-load-suite",
                    "timeout": 30,
                }
            ],
            "arms": arms
            if arms is not None
            else [
                {
                    "kind": "CONTROL",
                    "nonce": "control-1",
                    "clean_absence": True,
                    "binary_digest": "binary-1",
                    "workload_digest": "workload-1",
                },
                {
                    "kind": "TREATMENT",
                    "nonce": "treatment-1",
                    "candidate_id": _CANDIDATE_ID,
                    "isolated_install": True,
                    "binary_digest": "binary-1",
                    "workload_digest": "workload-1",
                },
            ],
        },
        "expected_evidence": {"kind": "DOCUMENTED"},
    }


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "mutation",
    [
        lambda request: request.pop("build_inputs"),
        lambda request: request.update({"legacy_candidate": {}}),
    ],
)
def test_slice_00_request_schema_is_exactly_six_keys_before_effects(
    mutation: object,
) -> None:
    """Missing and additional carriers cannot widen the frozen public request."""
    ports = FivePortWitnesses()
    request = _request()
    assert set(request) == {
        "subject",
        "build_inputs",
        "assembled_candidate",
        "treatment_plan",
        "probe",
        "expected_evidence",
    }
    assert callable(mutation)
    mutation(request)

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED"
    assert field(result, "stage_error") == "REQUEST_INVALID"
    assert ports.trace.events == []


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "arms",
    [
        [],
        [{"kind": "CONTROL", "nonce": "control-1", "clean_absence": True}],
        [{"kind": "TREATMENT", "nonce": "treatment-1", "isolated_install": True}],
        [
            {"kind": "CONTROL", "nonce": "same", "clean_absence": True},
            {"kind": "TREATMENT", "nonce": "same", "isolated_install": True},
        ],
    ],
)
def test_slice_00_refuses_unclosed_pair_before_any_external_effect(
    arms: list[Mapping[str, object]],
) -> None:
    """Invalid A/B shape is a public refusal, never an exception or partial probe."""
    # covers: R-S00-09
    ports = FivePortWitnesses()

    result = CodexParityJourneyComposition().run(
        _request(arms=arms), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: an unclosed control/treatment pair was accepted. "
        "WHY: one-arm or duplicate-arm evidence can falsely prove parity. "
        "HOW: return REFUSED(REQUEST_INVALID) before lease, deployment, probe, or ledger work."
    )
    assert field(result, "stage_error") == "REQUEST_INVALID"
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events == []


def test_slice_00_runs_one_lease_enclosed_paired_journey_and_persists_the_pair() -> (
    None
):
    """One root owns control → treatment → cleanup → durable final evidence sequence."""
    # covers: R-S00-10
    ports = FivePortWitnesses()

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "COMPLETED", (
        "WHAT: the complete paired journey did not finish. "
        "WHY: a parity proof requires one lease-enclosed clean control and receipt-scoped treatment. "
        "HOW: drive the whole transaction through CodexParityJourneyPort, clean treatment, then persist."
    )
    attestation = field(result, "attestation")
    observations = field(attestation, "observations")
    assert len(observations) == 2, (
        "WHAT: the paired witness population is incomplete. "
        "WHY: one witness requires one CONTROL and one TREATMENT observation. "
        "HOW: emit exactly 2 × witness-count nonce-correlated observations."
    )
    assert ports.trace.events == [
        "digest.verify",
        "probe.lease.acquire",
        "deployment.deploy",
        "digest.verify",
        "digest.verify",
        "native.control",
        "native.treatment",
        "probe.pair",
        "digest.verify",
        "deployment.rollback",
        "ledger.append",
        "ledger.read",
        "probe.lease.release",
    ]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("DEGRADED", {}),
        ("INDETERMINATE", {"reason": "missing remediation"}),
        ("FAILED", {"remediation": "missing reason"}),
        ("NOT_A_CLOSED_EVIDENCE_STATE", {}),
    ],
)
def test_slice_00_refuses_invalid_expected_evidence_before_any_effect(
    kind: str, payload: Mapping[str, object]
) -> None:
    """The closed evidence payload is validated before even digesting candidate bytes."""
    # covers: R-S00-09
    ports = FivePortWitnesses()
    request = _request()
    request["expected_evidence"] = {"kind": kind, **payload}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED"
    assert field(result, "stage_error") == "REQUEST_INVALID"
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events == [], (
        "WHAT: an invalid expected_evidence payload started external work. "
        "WHY: evidence disposition is a closed pre-effect authority input. "
        "HOW: reject absent required policy/reason/remediation or unknown state before digest."
    )


def test_slice_00_never_records_proved_when_the_real_probe_is_partial() -> None:
    """A missing paired observation stays a typed non-green result."""
    # covers: R-S00-11
    ports = FivePortWitnesses(probe_failure="OBSERVATION_MISSING")

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "INDETERMINATE", (
        "WHAT: a partial host observation was promoted to success. "
        "WHY: absence of an observation is not evidence of parity. "
        "HOW: preserve OBSERVATION_MISSING as INDETERMINATE and write no PROVED evidence."
    )
    assert field(result, "stage_error") == "OBSERVATION_MISSING"
    assert "ledger.append" not in ports.trace.events
    assert ports.trace.events[-1] == "probe.lease.release"


def test_slice_00_fixture_exposes_only_the_frozen_five_port_operations() -> None:
    """A green result cannot depend on a compatibility alias or second runner."""
    # covers: R-S00-23; adversarial contract guard for the fixture itself.
    ports = FivePortWitnesses().external_ports()
    digest = ports["candidate_material_digest"]
    deployment = ports["owned_artifact_deployment"]
    execution = ports["native_execution"]
    ledger = ports["parity_evidence_ledger"]
    factory = ports["real_host_probe"]

    assert callable(factory)
    probe = factory(execution)  # type: ignore[operator]
    assert all(
        callable(getattr(candidate, operation, None))
        for candidate, operation in (
            (digest, "digest"),
            (deployment, "deploy"),
            (deployment, "rollback"),
            (execution, "execute"),
            (ledger, "append"),
            (ledger, "records_for"),
            (probe, "acquire_lease"),
            (probe, "probe"),
            (probe, "record_cleanup_recovery"),
            (probe, "release_lease"),
        )
    )
    assert list(signature(factory).parameters) == ["native_execution"]
    assert list(signature(digest.digest).parameters) == ["locator"]
    assert list(signature(deployment.deploy).parameters) == ["plan"]
    assert list(signature(deployment.rollback).parameters) == ["receipt"]
    assert list(signature(execution.execute).parameters) == ["command"]
    assert list(signature(ledger.append).parameters) == ["envelope"]
    assert list(signature(ledger.records_for).parameters) == ["subject"]
    assert list(signature(probe.acquire_lease).parameters) == ["subject"]
    assert list(signature(probe.probe).parameters) == ["lease", "request"]
    assert list(signature(probe.record_cleanup_recovery).parameters) == [
        "lease",
        "deployment",
        "rollback",
        "attestation",
    ]
    assert list(signature(probe.release_lease).parameters) == [
        "lease",
        "recovery_key",
    ]
    assert not any(
        hasattr(candidate, alias)
        for candidate, alias in (
            (digest, "verify_candidate_material"),
            (deployment, "deploy_treatment"),
            (deployment, "rollback_treatment"),
            (execution, "run_native"),
            (probe, "acquire_box_lease"),
            (probe, "verify_requested_target"),
            (probe, "run_paired_probe"),
            (probe, "record_recovery"),
            (probe, "release_box_lease"),
            (ledger, "append_evidence"),
            (ledger, "read_records"),
        )
    ), (
        "WHAT: a fixture still offers a legacy port alias. "
        "WHY: alias probing would let production silently change the frozen contract. "
        "HOW: expose only the typed Slice-00 operation names and one probe factory."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("mutation", ["missing", "extra", "aggregate"])
def test_slice_00_production_factory_owns_five_port_closure(mutation: str) -> None:
    """The test driver forwards hostile adapter sets; compose rejects them itself."""
    ports = FivePortWitnesses().external_ports()
    if mutation == "missing":
        ports.pop("native_execution")
    elif mutation == "extra":
        ports["unexpected"] = object()
    else:
        ports["parity"] = object()

    with pytest.raises((TypeError, ValueError)):
        CodexParityJourneyComposition().compose_only(external_ports=ports)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "port_key",
    [
        "candidate_material_digest",
        "owned_artifact_deployment",
        "native_execution",
        "real_host_probe",
        "parity_evidence_ledger",
    ],
)
def test_slice_00_production_factory_rejects_each_nonconforming_port(
    port_key: str,
) -> None:
    """Closure checks the structural protocol of every named adapter at compose time."""
    ports = FivePortWitnesses().external_ports()
    ports[port_key] = object()

    with pytest.raises((TypeError, ValueError)):
        CodexParityJourneyComposition().compose_only(external_ports=ports)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("operation", "port_key"),
    [
        ("digest", "candidate_material_digest"),
        ("deploy", "owned_artifact_deployment"),
        ("rollback", "owned_artifact_deployment"),
        ("execute", "native_execution"),
        ("factory", "real_host_probe"),
        ("acquire_lease", "real_host_probe"),
        ("probe", "real_host_probe"),
        ("record_cleanup_recovery", "real_host_probe"),
        ("release_lease", "real_host_probe"),
        ("append", "parity_evidence_ledger"),
        ("records_for", "parity_evidence_ledger"),
    ],
)
def test_slice_00_production_closure_rejects_every_operation_mutant(
    operation: str, port_key: str
) -> None:
    """One missing operation is rejected while every sibling stays canonical."""
    ports = FivePortWitnesses().external_ports()

    class OmitOneOperation:
        def __init__(self, delegate: object, omitted: str) -> None:
            self._delegate = delegate
            self._omitted = omitted

        def __getattr__(self, name: str) -> object:
            if name == self._omitted:
                raise AttributeError(name)
            return getattr(self._delegate, name)

    if operation == "factory":
        ports[port_key] = object()
    elif port_key == "real_host_probe":
        canonical_factory = ports[port_key]
        assert callable(canonical_factory)

        def factory(native_execution: object) -> object:
            return OmitOneOperation(canonical_factory(native_execution), operation)

        ports[port_key] = factory
    else:
        ports[port_key] = OmitOneOperation(ports[port_key], operation)

    with pytest.raises((TypeError, ValueError)):
        CodexParityJourneyComposition().compose_only(external_ports=ports)


def _malformed_return(kind: str) -> object:
    if kind == "dict":
        return {"state": "SUCCEEDED"}
    if kind == "nonreceipt":
        return "not-a-typed-receipt"
    if kind == "exception":
        raise RuntimeError("hostile adapter return path")
    raise AssertionError(f"unknown malformed return kind: {kind}")


class _OneMalformedPortOperation:
    """Preserve every real operation except the one public-port mutant under test."""

    def __init__(self, delegate: object, operation: str, malformed_return: str) -> None:
        self._delegate = delegate
        self._operation = operation
        self._malformed_return = malformed_return

    def __getattr__(self, name: str) -> object:
        if name == self._operation:
            return lambda *_args, **_kwargs: _malformed_return(self._malformed_return)
        return getattr(self._delegate, name)


def _ports_with_one_malformed_operation(
    operation: str, malformed_return: str
) -> dict[str, object]:
    """Mutate exactly one frozen port operation; do not recreate the journey."""
    ports = FivePortWitnesses(
        deployment_failure=(
            "ROLLBACK_FAILED" if operation == "record_cleanup_recovery" else None
        )
    ).external_ports()
    port_key = {
        "digest": "candidate_material_digest",
        "deploy": "owned_artifact_deployment",
        "rollback": "owned_artifact_deployment",
        "execute": "native_execution",
        "acquire_lease": "real_host_probe",
        "probe": "real_host_probe",
        "record_cleanup_recovery": "real_host_probe",
        "release_lease": "real_host_probe",
        "append": "parity_evidence_ledger",
        "records_for": "parity_evidence_ledger",
    }.get(operation)
    if operation == "factory":
        ports["real_host_probe"] = lambda _native: _malformed_return(malformed_return)
    else:
        assert port_key is not None
        if port_key == "real_host_probe":
            factory = ports[port_key]
            assert callable(factory)
            ports[port_key] = lambda native: _OneMalformedPortOperation(
                factory(native), operation, malformed_return
            )
        else:
            ports[port_key] = _OneMalformedPortOperation(
                ports[port_key], operation, malformed_return
            )
    return ports


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("operation", "expected_outcome", "expected_error"),
    [
        ("digest", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("deploy", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("rollback", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("execute", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("factory", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("acquire_lease", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("probe", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("record_cleanup_recovery", "FAILED", "ROLLBACK_FAILED"),
        ("release_lease", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("append", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
        ("records_for", "INDETERMINATE", "ADAPTER_UNAVAILABLE"),
    ],
)
@pytest.mark.parametrize("malformed_return", ["dict", "nonreceipt", "exception"])
def test_slice_00_malformed_return_taxonomy_is_exact_for_every_operation(
    operation: str,
    expected_outcome: str,
    expected_error: str,
    malformed_return: str,
) -> None:
    """All 11×3 mutants traverse composition → public journey.run exactly once."""
    result = CodexParityJourneyComposition().run(
        _request(),
        external_ports=_ports_with_one_malformed_operation(operation, malformed_return),
    )

    assert field(result, "outcome") == expected_outcome
    assert field(result, "stage_error") == expected_error


@pytest.mark.negative_at
def test_slice_00_target_selection_carrier_mismatch_refuses_before_effects() -> None:
    """Requested authority and its immutable selection carrier must agree."""
    ports = FivePortWitnesses()
    request = _request()
    subject = request["subject"]
    assert isinstance(subject, dict)
    plan_subject = request["treatment_plan"]["subject"]  # type: ignore[index]
    probe_subject = request["probe"]["subject"]  # type: ignore[index]
    assert plan_subject is not subject
    assert probe_subject is not subject
    selection = subject["target_selection"]
    assert isinstance(selection, dict)
    assert isinstance(plan_subject, dict)
    plan_selection = plan_subject["target_selection"]
    assert isinstance(plan_selection, dict)
    assert plan_selection == selection and plan_selection is not selection
    plan_selection["requested_platform"] = "CLAUDE"

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED"
    assert field(result, "stage_error") == "REQUEST_INVALID"
    assert ports.trace.events == []


@pytest.mark.parametrize(
    "different_value", [False, True], ids=["same-value", "different-value"]
)
def test_slice_00_target_selection_carriers_are_distinct_and_only_canonical_reaches_acquire(
    different_value: bool,
) -> None:
    """Three distinct TargetSelection carriers must agree before the canonical one is leased."""
    ports = FivePortWitnesses(probe_failure="TARGET_UNAVAILABLE")
    request = _request()
    subject = request["subject"]
    plan_subject = request["treatment_plan"]["subject"]  # type: ignore[index]
    probe_subject = request["probe"]["subject"]  # type: ignore[index]
    assert isinstance(subject, dict)
    assert isinstance(plan_subject, dict)
    assert isinstance(probe_subject, dict)
    canonical = subject["target_selection"]
    plan_selection = plan_subject["target_selection"]
    probe_selection = probe_subject["target_selection"]
    assert isinstance(canonical, dict)
    assert isinstance(plan_selection, dict)
    assert isinstance(probe_selection, dict)
    assert len({id(canonical), id(plan_selection), id(probe_selection)}) == 3
    if different_value:
        probe_selection["detected_capabilities"] = ["claude-installed"]
    else:
        assert canonical == plan_selection == probe_selection

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    if different_value:
        assert (field(result, "outcome"), field(result, "stage_error")) == (
            "REFUSED",
            "REQUEST_INVALID",
        )
        assert ports.trace.events == []
        return

    assert (field(result, "outcome"), field(result, "stage_error")) == (
        "REFUSED",
        "TARGET_UNAVAILABLE",
    )
    assert ports.trace.events == ["digest.verify", "probe.lease.acquire"]
    assert ports.rechecked_target_selections == [canonical]
    assert ports.rechecked_target_selections[0] is canonical


@pytest.mark.negative_at
def test_slice_00_lease_rechecks_the_same_target_selection_atomically() -> None:
    """A target lost after prevalidation yields no lease or downstream effect."""
    ports = FivePortWitnesses(probe_failure="TARGET_UNAVAILABLE")

    request = _request()
    subject = request["subject"]
    assert isinstance(subject, dict)
    assert request["treatment_plan"]["subject"] is not subject  # type: ignore[index]
    assert request["probe"]["subject"] is not subject  # type: ignore[index]
    selection = subject["target_selection"]
    assert isinstance(selection, dict)

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED"
    assert field(result, "stage_error") == "TARGET_UNAVAILABLE"
    assert ports.trace.events == ["digest.verify", "probe.lease.acquire"]
    assert ports.factory_calls == 1
    assert len(ports.acquired_subjects) == 1
    assert len(ports.rechecked_target_selections) == 1
    assert ports.rechecked_target_selections[0] is selection
    assert ports.rechecked_target_selections[0] == selection
    assert not ports.ledger_commits
