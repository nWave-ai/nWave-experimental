"""Adversarial active-RED tests for the public shared parity journey.

No production domain, application helper, or driven-port type is imported here.
The single allowed system entry is the test protocol driver's composition root.
"""

from __future__ import annotations

from itertools import product
from types import SimpleNamespace

import pytest

from .composition import CodexParityJourneyComposition, diagnostic_field, field
from .port_witnesses import (
    FivePortWitnesses,
    GenuineIssuedRealHostProof,
    GenuineRealHostProofIssuerWitness,
)
from .test_slice_00_shared_port_contracts import _request


pytestmark = [pytest.mark.acceptance]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda request: request["probe"].update({"witnesses": []}),  # type: ignore[index,union-attr]
            "REQUEST_INVALID",
        ),
        (
            lambda request: request["probe"].update(  # type: ignore[index,union-attr]
                {
                    "arms": [
                        {
                            "kind": "CONTROL",
                            "nonce": "control-1",
                            "clean_absence": False,
                        },
                        {
                            "kind": "TREATMENT",
                            "nonce": "treatment-1",
                            "isolated_install": True,
                        },
                    ]
                }
            ),
            "CONTROL_BASELINE_UNPROVED",
        ),
        (
            lambda request: request["probe"].update(  # type: ignore[index,union-attr]
                {
                    "arms": [
                        {
                            "kind": "CONTROL",
                            "nonce": "control-1",
                            "clean_absence": True,
                        },
                        {
                            "kind": "TREATMENT",
                            "nonce": "treatment-1",
                            "candidate_id": "other-candidate",
                            "isolated_install": True,
                        },
                    ]
                }
            ),
            "TREATMENT_DEPLOYMENT_UNPROVED",
        ),
    ],
)
def test_slice_00_refuses_each_invalid_pair_without_claiming_proof(
    mutator: object, expected_error: str
) -> None:
    """Every malformed control/treatment precondition has a closed typed outcome."""
    # covers: R-S00-17
    ports = FivePortWitnesses()
    request = _request()
    assert callable(mutator)
    mutator(request)

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: an invalid A/B receipt pair proceeded as a usable witness. "
        "WHY: control absence and treatment lineage are independent proof prerequisites. "
        "HOW: preserve the matching closed stage error and prevent PROVED evidence."
    )
    assert field(result, "stage_error") == expected_error
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert "ledger.append" not in ports.trace.events


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("mode", "outcome", "stage_error"),
    [
        ("BOX_UNAVAILABLE", "INDETERMINATE", "BOX_UNAVAILABLE"),
        ("LEASE_LOST", "INDETERMINATE", "LEASE_LOST"),
        ("TARGET_UNAVAILABLE", "REFUSED", "TARGET_UNAVAILABLE"),
        ("TERMINATION_UNPROVED", "INDETERMINATE", "TERMINATION_UNPROVED"),
        ("NONCE_MISMATCH", "FAILED", "NONCE_MISMATCH"),
        ("OBSERVATION_DUPLICATE", "FAILED", "OBSERVATION_DUPLICATE"),
    ],
)
def test_slice_00_preserves_partial_or_contradictory_substrate_outcome(
    mode: str, outcome: str, stage_error: str
) -> None:
    """A real-host substrate failure cannot be relabelled as a green support result."""
    # covers: R-S00-18
    ports = (
        FivePortWitnesses(native_failure=mode)
        if mode == "TERMINATION_UNPROVED"
        else FivePortWitnesses(probe_failure=mode)
    )

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == outcome, (
        "WHAT: a substrate non-success changed disposition at the journey boundary. "
        "WHY: unavailable, unprovable, and contradictory facts have different remediation. "
        "HOW: preserve the closed port error and its REFUSED/INDETERMINATE/FAILED mapping."
    )
    assert field(result, "stage_error") == stage_error
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert "ledger.append" not in ports.trace.events


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "mutator",
    [
        lambda request: request["treatment_plan"].update({"intents": []}),  # type: ignore[index,union-attr]
        lambda request: request["treatment_plan"].update(  # type: ignore[index,union-attr]
            {"intents": [{"key": "nwave/role.toml"}, {"key": "nwave/role.toml"}]}
        ),
        lambda request: request["treatment_plan"].update(  # type: ignore[index,union-attr]
            {"intents": [{"key": "  "}]}
        ),
        lambda request: request["probe"]["witnesses"][0].update({"id": ""}),  # type: ignore[index,union-attr]
        lambda request: request["probe"]["witnesses"][0].update({"item": ""}),  # type: ignore[index,union-attr]
        lambda request: request["probe"]["witnesses"][0].update({"suite": ""}),  # type: ignore[index,union-attr]
        lambda request: request["probe"]["witnesses"][0].update({"timeout": 0}),  # type: ignore[index,union-attr]
    ],
)
def test_slice_00_refuses_empty_intent_or_incomplete_witness_before_effects(
    mutator: object,
) -> None:
    """Empty plans and incomplete witness descriptors never enter the transaction."""
    ports = FivePortWitnesses()
    request = _request()
    assert callable(mutator)
    mutator(request)

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: an empty mutation plan or incomplete witness reached an external port. "
        "WHY: evidence without a declared item, suite, bounded timeout, and owned delta is unrepeatable. "
        "HOW: return a closed validation refusal before digest, lease, deployment, execution, or ledger work."
    )
    assert field(result, "stage_error") in {"REQUEST_INVALID", "PLAN_INVALID"}
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events == []


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "mutator",
    [
        lambda request: request["probe"]["arms"][0].pop("binary_digest"),  # type: ignore[index,union-attr]
        lambda request: request["probe"]["arms"][1].update(  # type: ignore[index,union-attr]
            {"binary_digest": "other-binary"}
        ),
        lambda request: request["probe"]["arms"][0].pop("workload_digest"),  # type: ignore[index,union-attr]
        lambda request: request["probe"]["arms"][1].update(  # type: ignore[index,union-attr]
            {"workload_digest": "other-workload"}
        ),
    ],
)
def test_slice_00_refuses_unbound_arm_digests_before_effects(mutator: object) -> None:
    """Both arms bind the same non-empty binary and workload before any port call."""
    ports = FivePortWitnesses()
    request = _request()
    assert callable(mutator)
    mutator(request)

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED"
    assert field(result, "stage_error") == "REQUEST_INVALID"
    assert ports.trace.events == []


@pytest.mark.negative_at
def test_slice_00_test_double_provenance_cannot_mint_proved() -> None:
    """A substituted probe may exercise orchestration but cannot establish host proof."""
    ports = FivePortWitnesses()
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "COMPLETED"
    assert field(result, "stage_error") == "EXECUTION_UNPROVED"
    assert not ports.ledger_commits


@pytest.mark.negative_at
def test_slice_00_forged_real_host_provenance_string_cannot_mint_proved() -> None:
    """A string is not the opaque production proof for persisted observables."""
    ports = FivePortWitnesses(probe_reported_provenance="REAL_HOST_PERSISTED")
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "COMPLETED"
    assert field(result, "stage_error") == "EXECUTION_UNPROVED"
    assert not ports.ledger_commits


def test_slice_00_genuine_issued_proof_with_matching_observables_can_prove() -> None:
    """A genuine proof is issued only after lease and probe facts are available."""
    request = _request()
    issuer = GenuineRealHostProofIssuerWitness()
    ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED",
        proof_issuer=issuer,
    )
    request["expected_evidence"] = {"kind": "PROVED"}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "COMPLETED"
    assert field(result, "evidence").state == "PROVED"
    assert len(issuer.issued) == 1
    assert len(ports.persisted_probe_records) == 1
    proof = issuer.issued[0]
    durable_record = ports.persisted_probe_records[0]
    assert issuer.verifies(proof)
    assert proof.subject == ports.acquired_subjects[0]
    assert proof.lease_id == "box-1"
    assert proof.candidate_id == request["subject"]["candidate_id"]  # type: ignore[index]
    assert proof.binary_digest == "binary-1"
    assert proof.workload_digest == request["probe"]["workload_digest"]  # type: ignore[index]
    assert proof.ordered_observations == field(
        field(result, "attestation"), "observations"
    )
    assert proof.ordered_observations == field(
        durable_record, "ordered_observations"
    )
    assert proof.durable_record_id == field(durable_record, "record_id")
    assert proof.persisted_record_bytes == field(durable_record, "persisted_bytes")


@pytest.mark.negative_at
def test_slice_00_same_shaped_real_host_proof_without_issuer_capability_is_rejected() -> None:
    """Copying every public binding cannot counterfeit the opaque issuer capability."""
    issuer = GenuineRealHostProofIssuerWitness()
    seed_request = _request()
    seed_request["expected_evidence"] = {"kind": "PROVED"}
    seed_ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED", proof_issuer=issuer
    )
    seed_result = CodexParityJourneyComposition().run(
        seed_request, external_ports=seed_ports.external_ports()
    )
    assert field(seed_result, "outcome") == "COMPLETED"
    genuine = issuer.issued[0]
    forged = SimpleNamespace(
        subject=genuine.subject,
        lease_id=genuine.lease_id,
        candidate_id=genuine.candidate_id,
        binary_digest=genuine.binary_digest,
        workload_digest=genuine.workload_digest,
        ordered_observations=genuine.ordered_observations,
        durable_record_id=genuine.durable_record_id,
        persisted_record_bytes=genuine.persisted_record_bytes,
    )
    assert not issuer.verifies(forged)
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}
    ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED",
        probe_reported_proof=forged,
    )

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert (field(result, "outcome"), field(result, "stage_error")) == (
        "INDETERMINATE",
        "EXECUTION_UNPROVED",
    )
    assert not ports.ledger_commits


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "mutation",
    [
        "subject",
        "lease",
        "candidate",
        "binary",
        "workload",
        "ordered_observations",
        "durable_record",
        "persisted_bytes",
    ],
)
def test_slice_00_each_mutated_binding_on_issued_proof_is_rejected(
    mutation: str,
) -> None:
    """Each signed fact independently invalidates an otherwise genuine capability."""
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}
    issuer = GenuineRealHostProofIssuerWitness()
    seed_ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED", proof_issuer=issuer
    )
    seed_result = CodexParityJourneyComposition().run(
        request, external_ports=seed_ports.external_ports()
    )
    assert field(seed_result, "outcome") == "COMPLETED"
    proof = issuer.issued[0]
    assert isinstance(proof, GenuineIssuedRealHostProof)
    assert issuer.verifies(proof)
    canonical_proof_subject = proof.subject
    capability_before = proof._capability_for_verification()
    replacements = {
        "subject": ("subject", {"subject": "other"}),
        "lease": ("lease_id", "other-lease"),
        "candidate": ("candidate_id", "other-candidate"),
        "binary": ("binary_digest", "other-binary"),
        "workload": ("workload_digest", "other-workload"),
        "ordered_observations": (
            "ordered_observations",
            tuple(reversed(proof.ordered_observations)),
        ),
        "durable_record": ("durable_record_id", "other-record"),
        "persisted_bytes": ("persisted_record_bytes", b"mutated-record"),
    }
    field_name, replacement = replacements[mutation]
    setattr(proof, field_name, replacement)
    assert isinstance(proof, GenuineIssuedRealHostProof)
    if mutation != "subject":
        assert proof.subject is canonical_proof_subject
    assert proof._capability_for_verification() == capability_before
    assert not issuer.verifies(proof), (
        f"{mutation} is not covered by the issuer HMAC binding"
    )
    ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED",
        probe_reported_proof=proof,
    )

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "INDETERMINATE"
    assert field(result, "stage_error") == "EXECUTION_UNPROVED"


@pytest.mark.negative_at
def test_slice_00_issued_proof_replay_with_same_canonical_subject_is_rejected() -> None:
    """A valid consumed capability cannot prove a second run of the same subject."""
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}
    canonical_subject = request["subject"]
    issuer = GenuineRealHostProofIssuerWitness()
    seed_ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED", proof_issuer=issuer
    )
    seed_result = CodexParityJourneyComposition().run(
        request, external_ports=seed_ports.external_ports()
    )
    assert field(seed_result, "outcome") == "COMPLETED"
    proof = issuer.issued[0]
    assert issuer.verifies(proof)
    replay_request = request
    assert replay_request["subject"] is canonical_subject
    ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED",
        probe_reported_proof=proof,
    )

    result = CodexParityJourneyComposition().run(
        replay_request, external_ports=ports.external_ports()
    )

    assert (field(result, "outcome"), field(result, "stage_error")) == (
        "INDETERMINATE",
        "EXECUTION_UNPROVED",
    )
    assert not ports.ledger_commits


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "counterfeit",
    [
        {"subject": "forged"},
        "replayed-proof-token",
        object(),
        {"persisted_observable_digest": "mutated"},
    ],
    ids=["dict", "replay-string", "duck-object", "mutated-observable"],
)
def test_slice_00_counterfeit_or_replayed_proof_carrier_cannot_mint_proved(
    counterfeit: object,
) -> None:
    """Only the production issuer/verifier can admit a proof carrier."""
    ports = FivePortWitnesses(
        probe_reported_provenance="REAL_HOST_PERSISTED",
        probe_reported_proof=counterfeit,
    )
    request = _request()
    request["expected_evidence"] = {"kind": "PROVED"}

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "INDETERMINATE"
    assert field(result, "stage_error") == "EXECUTION_UNPROVED"
    assert not ports.ledger_commits


@pytest.mark.negative_at
@pytest.mark.parametrize("hostile_kind", ["legacy_alias", "dict_receipt"])
def test_slice_00_hostile_digest_adapter_never_uses_alias_or_mapping_receipt(
    hostile_kind: str,
) -> None:
    """Only `digest` returning a typed observation can enter the lineage verifier."""
    ports = FivePortWitnesses()
    external_ports = ports.external_ports()

    class LegacyOnlyDigest:
        def verify_candidate_material(self, locator: object) -> object:
            return {"state": "SUCCEEDED", "digest": "distribution-1"}

    class DictDigest:
        def digest(self, locator: object) -> object:
            return {"state": "SUCCEEDED", "digest": "distribution-1"}

    external_ports["candidate_material_digest"] = (
        LegacyOnlyDigest() if hostile_kind == "legacy_alias" else DictDigest()
    )
    result = CodexParityJourneyComposition().run(
        _request(), external_ports=external_ports
    )

    assert field(result, "outcome") == "INDETERMINATE"
    assert field(result, "stage_error") == "ADAPTER_UNAVAILABLE"
    assert ports.trace.events == []


def test_slice_00_probe_factory_receives_one_native_executor_once() -> None:
    """The root creates one probe arbiter from the one supplied native port."""
    ports = FivePortWitnesses()
    external_ports = ports.external_ports()
    native = external_ports["native_execution"]

    CodexParityJourneyComposition().run(_request(), external_ports=external_ports)

    assert ports.factory_calls == 1
    assert ports.factory_native_inputs == [native]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "receipt_mode",
    ["FAILED", "INDETERMINATE", "none", "malformed"],
)
def test_slice_00_non_success_or_malformed_receipt_never_succeeds_without_error(
    receipt_mode: str,
) -> None:
    """Receipt state closes independently of optional stage_error text."""
    ports = FivePortWitnesses(receipt_mode=receipt_mode)

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "COMPLETED"
    assert field(result, "stage_error") == "ADAPTER_UNAVAILABLE"
    assert field(result, "stage_state") == "INDETERMINATE"
    assert ports.trace.events[-2:] == ["deployment.rollback", "probe.lease.release"]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("ports", "expected_error"),
    [
        (
            FivePortWitnesses(release_failure="LEASE_RELEASE_UNPROVED"),
            "LEASE_RELEASE_UNPROVED",
        ),
        (
            FivePortWitnesses(
                deployment_failure="ROLLBACK_FAILED",
                recovery_failure="RECOVERY_RECORD_UNAVAILABLE",
            ),
            "ROLLBACK_FAILED",
        ),
    ],
)
def test_slice_00_cleanup_failure_receipts_remain_visible(
    ports: FivePortWitnesses, expected_error: str
) -> None:
    """Recovery and release failures cannot be overwritten by apparent completion."""
    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "COMPLETED"
    assert field(result, "stage_error") == expected_error
    assert ports.trace.events[-1] == "probe.lease.release"


@pytest.mark.negative_at
def test_slice_00_recovery_unavailable_preserves_rollback_failure_and_operator_owner() -> None:
    """A failed recovery record cannot replace the original cleanup contradiction."""
    ports = FivePortWitnesses(
        deployment_failure="ROLLBACK_FAILED",
        recovery_failure="RECOVERY_RECORD_UNAVAILABLE",
    )

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "FAILED"
    assert field(result, "stage_error") == "ROLLBACK_FAILED"
    assert field(result, "retry_owner") == "OPERATOR"
    assert "RECOVERY_RECORD_UNAVAILABLE" in diagnostic_field(result, "what")
    assert ports.trace.events[-1] == "probe.lease.release"


@pytest.mark.negative_at
def test_slice_00_rollback_failure_outranks_ledger_unavailability() -> None:
    """Cleanup contradiction has fixed precedence over final-evidence availability."""
    ports = FivePortWitnesses(
        deployment_failure="ROLLBACK_FAILED",
        ledger_failure="PERSISTENCE_UNAVAILABLE",
    )

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "FAILED"
    assert field(result, "stage_error") == "ROLLBACK_FAILED"
    assert field(result, "retry_owner") == "OPERATOR"
    assert "PERSISTENCE_UNAVAILABLE" in diagnostic_field(result, "what")
    assert ports.trace.events[-1] == "probe.lease.release"


@pytest.mark.negative_at
def test_slice_00_ledger_refusal_cannot_complete_and_always_cleans_up() -> None:
    """Durability refusal is non-green while rollback and lease release remain mandatory."""
    ports = FivePortWitnesses(ledger_failure="PERSISTENCE_UNAVAILABLE")

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "INDETERMINATE", (
        "WHAT: a rejected evidence append was reported as complete. "
        "WHY: an undurable paired observation cannot support a parity claim. "
        "HOW: preserve the ledger error, roll back the treatment, then release the lease."
    )
    assert field(result, "stage_error") == "PERSISTENCE_UNAVAILABLE"
    assert ports.trace.events[-3:] == [
        "deployment.rollback",
        "ledger.append",
        "probe.lease.release",
    ], (
        "WHAT: final evidence durability was attempted outside the cleaned lease. "
        "WHY: PROVED can be attempted only after successful rollback, and an append "
        "refusal cannot authorize a success-only readback. "
        "HOW: roll back, attempt the final append once, skip readback on refusal, then release."
    )
    assert "ledger.read" not in ports.trace.events


@pytest.mark.negative_at
def test_slice_00_adapter_exception_is_typed_and_releases_the_lease() -> None:
    """Operational exceptions do not escape or strand a leased mutated box."""
    ports = FivePortWitnesses(ledger_exception=True)

    try:
        result = CodexParityJourneyComposition().run(
            _request(), external_ports=ports.external_ports()
        )
    except (RuntimeError, ValueError) as error:
        pytest.fail(
            "WHAT: an external adapter exception crossed the public driving boundary. "
            "WHY: callers then lose the typed outcome and cleanup evidence. "
            f"HOW: translate the exception, roll back, and release the lease; got {error!r}."
        )

    assert field(result, "outcome") != "COMPLETED"
    assert field(result, "stage_error") == "ADAPTER_UNAVAILABLE"
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events[-3:] == [
        "deployment.rollback",
        "ledger.append",
        "probe.lease.release",
    ], (
        "WHAT: an exceptional final append escaped the cleaned-then-durable ordering. "
        "WHY: an unavailable ledger cannot support readback, but cleanup and lease release remain mandatory. "
        "HOW: translate the exception, omit success-only readback, and release after the append attempt."
    )
    assert "ledger.read" not in ports.trace.events


@pytest.mark.negative_at
def test_slice_00_rollback_failure_never_completes_and_still_releases_lease() -> None:
    """A failed rollback persists recovery plus FAILED evidence before lease release."""
    ports = FivePortWitnesses(deployment_failure="ROLLBACK_FAILED")

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "FAILED", (
        "WHAT: failed restoration was hidden behind a completed journey. "
        "WHY: the box is not proven clean after ROLLBACK_FAILED. "
        "HOW: return a typed non-success and release the serialization lease."
    )
    assert field(result, "stage_error") == "ROLLBACK_FAILED"
    assert field(result, "stage_state") == "FAILED", (
        "WHAT: rollback failure lost its typed receipt state at the public boundary. "
        "WHY: callers must distinguish a contradiction from a refusal or unavailable observation. "
        "HOW: retain the closed FAILED ReceiptState alongside the originating stage error."
    )
    assert field(result, "retry_owner") == "OPERATOR"
    assert ports.trace.events[-5:] == [
        "deployment.rollback",
        "probe.recovery.record",
        "ledger.append",
        "ledger.read",
        "probe.lease.release",
    ], (
        "WHAT: rollback failure did not durably preserve recovery and FAILED evidence. "
        "WHY: a later cleanup retry must not erase the contradiction or strand ownership. "
        "HOW: record subject/lease/plan recovery, append+read exact FAILED evidence, then release."
    )
    assert ports.trace.events[-1] == "probe.lease.release"
    assert len(ports.recovery_payloads) == 1
    assert len(ports.recovery_calls) == 1
    assert len(ports.issued_leases) == 1
    assert len(ports.deployment_plans) == 1
    assert len(ports.issued_deployment_receipts) == 1
    assert len(ports.issued_rollback_receipts) == 1
    recovery = ports.recovery_payloads[0]
    expected_lease = ports.issued_leases[0]
    expected_plan = ports.deployment_plans[0]
    expected_deployment = ports.issued_deployment_receipts[0]
    expected_rollback = ports.issued_rollback_receipts[0]
    actual_lease, actual_deployment, actual_rollback, actual_attestation = (
        ports.recovery_calls[0]
    )
    assert actual_lease == expected_lease
    assert actual_deployment == expected_deployment
    assert actual_rollback == expected_rollback
    assert field(expected_deployment, "plan") == expected_plan
    assert field(expected_rollback, "deployment_receipt") == expected_deployment
    assert field(actual_attestation, "candidate_id") == field(
        expected_deployment, "candidate_id"
    )
    assert field(actual_attestation, "observations") == field(
        ports.persisted_probe_records[0], "ordered_observations"
    )
    assert vars(recovery) == {
        "subject": field(expected_lease, "subject"),
        "lease": expected_lease,
        "plan_key": "plan-1",
        "deployment": expected_deployment,
        "rollback": expected_rollback,
        "provisional_attestation": actual_attestation,
        "attestation_digest": "attestation-1",
        "changed_artifact_ids": ("nwave/role.toml",),
        "rollback_token": "rollback-1",
        "attempt_count": 1,
        "failed_rollback_receipt": expected_rollback,
        "retry_owner": "OPERATOR",
    }, (
        "WHAT: recovery omitted or substituted a cleanup fact. "
        "WHY: a retry needs one exact subject/lease/plan/deployment/rollback record. "
        "HOW: persist the distinctive recovery record with no optional or inferred fields."
    )
    assert len(ports.ledger_commits) == 1
    assert "ledger.append" in ports.trace.events
    failed_envelope = ports.ledger_commits[0]
    assert field(field(failed_envelope, "evidence"), "state") == "FAILED"
    assert field(failed_envelope, "recovery_key")


_SECONDARY_FAILURE_MATRIX = [
    values for values in product((False, True), repeat=4) if any(values)
]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("recovery_unavailable", "ledger_unavailable", "read_unavailable", "release_unproved"),
    _SECONDARY_FAILURE_MATRIX,
)
def test_slice_00_rollback_failed_outranks_every_combination_of_secondary_failure(
    recovery_unavailable: bool,
    ledger_unavailable: bool,
    read_unavailable: bool,
    release_unproved: bool,
) -> None:
    """ROLLBACK_FAILED is invariant under all non-empty secondary failure combinations."""
    ports = FivePortWitnesses(
        deployment_failure="ROLLBACK_FAILED",
        recovery_failure=("RECOVERY_RECORD_UNAVAILABLE" if recovery_unavailable else None),
        ledger_failure=("PERSISTENCE_UNAVAILABLE" if ledger_unavailable else None),
        ledger_read_mode=("empty" if read_unavailable else "exact"),
        release_failure=("LEASE_RELEASE_UNPROVED" if release_unproved else None),
    )

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert (field(result, "outcome"), field(result, "stage_error")) == (
        "FAILED",
        "ROLLBACK_FAILED",
    )
    assert ports.trace.events[-5:] == [
        "deployment.rollback",
        "probe.recovery.record",
        "ledger.append",
        "ledger.read",
        "probe.lease.release",
    ]


@pytest.mark.negative_at
@pytest.mark.parametrize("read_mode", ["empty", "wrong_subject", "tampered"])
def test_slice_00_refuses_non_exact_post_rollback_ledger_readback(read_mode: str) -> None:
    """A write receipt alone is insufficient: the exact persisted envelope must read back."""
    # covers: R-S00-20
    ports = FivePortWitnesses(ledger_read_mode=read_mode)

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") in {"INDETERMINATE", "FAILED"}
    assert field(result, "stage_error") in {
        "READ_UNAVAILABLE",
        "RECORD_TAMPERED",
        "SUBJECT_MISMATCH",
    }
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events[-4:] == [
        "deployment.rollback",
        "ledger.append",
        "ledger.read",
        "probe.lease.release",
    ]


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "attestation_mode",
    [
        "missing_native_receipt",
        "wrong_nonce",
        "duplicate_pair",
        "wrong_arm",
        "wrong_subject",
        "wrong_binary",
        "wrong_workload",
        "wrong_arm_receipt",
        "missing_control_receipt",
        "missing_treatment_receipt",
    ],
)
def test_slice_00_refuses_incomplete_or_non_unique_attestation_before_cleanup(
    attestation_mode: str,
) -> None:
    """Every paired fact is exact: subject, arm, nonce, uniqueness and native receipt."""
    # covers: R-S00-10
    ports = FivePortWitnesses(attestation_mode=attestation_mode)

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") in {"REFUSED", "INDETERMINATE", "FAILED"}
    assert field(result, "stage_error") in {
        "ATTESTATION_SUBJECT_MISMATCH",
        "NONCE_MISMATCH",
        "OBSERVATION_DUPLICATE",
        "OBSERVATION_MISSING",
        "EXECUTION_UNPROVED",
        "BINARY_IDENTITY_MISMATCH",
        "CONTROL_BASELINE_UNPROVED",
        "TREATMENT_DEPLOYMENT_UNPROVED",
    }
    assert "ledger.append" not in ports.trace.events
    assert ports.trace.events[-2:] == ["deployment.rollback", "probe.lease.release"]
