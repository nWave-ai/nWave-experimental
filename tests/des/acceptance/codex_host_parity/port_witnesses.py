"""Independent external witnesses for the five slice-00 DESIGN ports.

These doubles record only effects at their own boundary.  They deliberately
do not offer a façade that can reproduce the journey orchestration in test
code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import json
from types import SimpleNamespace


_CANDIDATE_ID = "febc8331fdccf9913bfbcddece8df239a2af85dc353be1080dcd27d1f1ee1eac"


def _receipt(**fields: object) -> SimpleNamespace:
    """Return a structural receipt object, never a mapping compatibility shim."""
    return SimpleNamespace(**fields)


def _public_field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


class GenuineIssuedRealHostProof:
    """Constructor-guarded capability; only the issuer can create this carrier."""

    __slots__ = (
        "subject",
        "lease_id",
        "candidate_id",
        "binary_digest",
        "workload_digest",
        "ordered_observations",
        "durable_record_id",
        "persisted_record_bytes",
        "__issuer_capability",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("RealHostProof is issuable only by the real-host proof issuer")

    def _capability_for_verification(self) -> bytes:
        return self.__issuer_capability


class GenuineRealHostProofIssuerWitness:
    """Issues and verifies a persisted-byte-bound real-host capability."""

    _SIGNING_KEY = hashlib.sha256(
        b"acceptance-real-host-proof-issuer-signing-key"
    ).digest()

    def __init__(self) -> None:
        self.issued: list[GenuineIssuedRealHostProof] = []

    def issue_after_probe(
        self,
        *,
        subject: object,
        lease: object,
        candidate_id: str,
        binary_digest: str,
        workload_digest: str,
        observations: tuple[object, ...],
        durable_record_id: str,
        persisted_record_bytes: bytes,
    ) -> GenuineIssuedRealHostProof:
        capability = self._sign(
            subject=subject,
            lease_id=str(getattr(lease, "lease_id")),
            candidate_id=candidate_id,
            binary_digest=binary_digest,
            workload_digest=workload_digest,
            observations=observations,
            durable_record_id=durable_record_id,
            persisted_record_bytes=persisted_record_bytes,
        )
        proof = object.__new__(GenuineIssuedRealHostProof)
        proof.subject = subject
        proof.lease_id = str(getattr(lease, "lease_id"))
        proof.candidate_id = candidate_id
        proof.binary_digest = binary_digest
        proof.workload_digest = workload_digest
        proof.ordered_observations = observations
        proof.durable_record_id = durable_record_id
        proof.persisted_record_bytes = persisted_record_bytes
        proof._GenuineIssuedRealHostProof__issuer_capability = capability
        self.issued.append(proof)
        return proof

    def verifies(self, candidate: object) -> bool:
        if not isinstance(candidate, GenuineIssuedRealHostProof):
            return False
        expected = self._sign(
            subject=candidate.subject,
            lease_id=candidate.lease_id,
            candidate_id=candidate.candidate_id,
            binary_digest=candidate.binary_digest,
            workload_digest=candidate.workload_digest,
            observations=candidate.ordered_observations,
            durable_record_id=candidate.durable_record_id,
            persisted_record_bytes=candidate.persisted_record_bytes,
        )
        return hmac.compare_digest(
            candidate._capability_for_verification(), expected
        )

    @classmethod
    def _sign(
        cls,
        *,
        subject: object,
        lease_id: str,
        candidate_id: str,
        binary_digest: str,
        workload_digest: str,
        observations: tuple[object, ...],
        durable_record_id: str,
        persisted_record_bytes: bytes,
    ) -> bytes:
        bindings = _canonical_bytes(
            {
                "subject": subject,
                "lease_id": lease_id,
                "candidate_id": candidate_id,
                "binary_digest": binary_digest,
                "workload_digest": workload_digest,
                "ordered_observations": observations,
                "durable_record_id": durable_record_id,
                "persisted_record_sha256": hashlib.sha256(
                    persisted_record_bytes
                ).hexdigest(),
            }
        )
        return hmac.new(cls._SIGNING_KEY, bindings, hashlib.sha256).digest()


def _canonical_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_value(item) for item in value)
    if hasattr(value, "__dict__"):
        return {
            str(key): _canonical_value(item)
            for key, item in vars(value).items()
        }
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _canonical_value(value), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


@dataclass
class PortTrace:
    events: list[str] = field(default_factory=list)


@dataclass
class CandidateMaterialDigestWitness:
    trace: PortTrace
    failure: str | None = None
    calls: list[object] = field(default_factory=list)
    digest_sequence: tuple[str, ...] = ()

    def digest(self, locator: object) -> object:
        self.calls.append(locator)
        self.trace.events.append("digest.verify")
        if self.failure and self.failure != "ROLLBACK_FAILED":
            return _receipt(state="INDETERMINATE", stage_error=self.failure)
        digest = (
            self.digest_sequence[len(self.calls) - 1]
            if len(self.digest_sequence) >= len(self.calls)
            else "distribution-1"
        )
        return _receipt(
            state="SUCCEEDED",
            candidate_id=_CANDIDATE_ID,
            digest=digest,
            locator=locator,
        )


@dataclass
class OwnedArtifactDeploymentWitness:
    trace: PortTrace
    failure: str | None = None
    raise_on_deploy: bool = False
    plans: list[object] = field(default_factory=list)
    issued_deployments: list[object] = field(default_factory=list)
    issued_rollbacks: list[object] = field(default_factory=list)

    def deploy(self, plan: object) -> object:
        self.trace.events.append("deployment.deploy")
        self.plans.append(plan)
        if self.raise_on_deploy:
            raise RuntimeError("deployment adapter exploded")
        # ROLLBACK_FAILED describes the cleanup receipt, not deployment.  The
        # journey can only prove (and recover from) a failed rollback after a
        # concrete treatment receipt has been issued.
        if self.failure and self.failure != "ROLLBACK_FAILED":
            return _receipt(state="FAILED", stage_error=self.failure)
        receipt = _receipt(
            state="SUCCEEDED",
            receipt_id="deploy-1",
            candidate_id=_CANDIDATE_ID,
            mutations=(_receipt(key="nwave/role.toml"),),
            plan=plan,
        )
        self.issued_deployments.append(receipt)
        return receipt

    def rollback(self, receipt: object) -> object:
        self.trace.events.append("deployment.rollback")
        if self.failure == "ROLLBACK_FAILED":
            rollback = _receipt(
                state="FAILED",
                stage_error="ROLLBACK_FAILED",
                deployment_receipt=receipt,
            )
        else:
            rollback = _receipt(state="SUCCEEDED", receipt=receipt)
        self.issued_rollbacks.append(rollback)
        return rollback


@dataclass
class NativeExecutionWitness:
    trace: PortTrace
    failure: str | None = None
    calls: int = 0

    def execute(self, command: object) -> object:
        self.calls += 1
        arm = "control" if self.calls == 1 else "treatment"
        self.trace.events.append(f"native.{arm}")
        if self.failure:
            return _receipt(state="INDETERMINATE", stage_error=self.failure)
        return _receipt(
            state="SUCCEEDED",
            receipt_id=f"native-{arm}",
            command_digest=f"command-{arm}",
            observable_digest=f"observable-{arm}",
            command=command,
        )


@dataclass
class RealHostProbeWitness:
    trace: PortTrace
    failure: str | None = None
    attestation_mode: str = "exact"
    recovery_failure: str | None = None
    release_failure: str | None = None
    receipt_mode: str = "exact"
    reported_provenance: str = "EXTERNAL_DOUBLE"
    reported_proof: object | None = None
    proof_issuer: GenuineRealHostProofIssuerWitness | None = None
    recovery_payloads: list[object] = field(default_factory=list)
    recovery_calls: list[tuple[object, object, object, object]] = field(
        default_factory=list
    )
    acquired_subjects: list[object] = field(default_factory=list)
    rechecked_target_selections: list[object] = field(default_factory=list)
    issued_leases: list[object] = field(default_factory=list)
    persisted_probe_records: list[object] = field(default_factory=list)

    def acquire_lease(self, subject: object) -> object:
        self.trace.events.append("probe.lease.acquire")
        self.acquired_subjects.append(subject)
        self.rechecked_target_selections.append(
            getattr(subject, "target_selection", None)
        )
        if self.failure == "BOX_UNAVAILABLE":
            return _receipt(state="INDETERMINATE", stage_error=self.failure)
        if self.failure == "TARGET_UNAVAILABLE":
            return _receipt(state="REFUSED", stage_error=self.failure)
        lease = _receipt(
            state="SUCCEEDED",
            lease_id="box-1",
            subject=subject,
            target_binary_digest="binary-1",
        )
        self.issued_leases.append(lease)
        return lease

    def probe(self, lease: object, request: object) -> object:
        self.trace.events.append("probe.pair")
        if self.receipt_mode == "none":
            return None  # type: ignore[return-value]
        if self.receipt_mode == "malformed":
            return "not-a-receipt"  # type: ignore[return-value]
        if self.receipt_mode in {"FAILED", "INDETERMINATE"}:
            return _receipt(state=self.receipt_mode)
        if self.failure:
            state = (
                "FAILED"
                if self.failure in {"NONCE_MISMATCH", "OBSERVATION_DUPLICATE"}
                else "INDETERMINATE"
            )
            return _receipt(state=state, stage_error=self.failure)
        witnesses = tuple(getattr(request, "witnesses", ()))
        arms = tuple(getattr(request, "arms", ()))
        subject = getattr(request, "subject", None)
        workload_digest = getattr(request, "workload_digest", None)
        observations = [
            _receipt(
                witness_id=getattr(witness, "witness_id"),
                item_id=getattr(witness, "item_id"),
                suite_id=getattr(witness, "suite_id"),
                arm=getattr(arm, "kind"),
                echoed_nonce=getattr(arm, "nonce"),
                subject=subject,
                binary_digest="binary-1",
                workload_digest=workload_digest,
                native_receipt=f"native-{getattr(getattr(arm, 'kind'), 'value', getattr(arm, 'kind')).lower()}",
                arm_receipt_id=(
                    "baseline-1"
                    if getattr(getattr(arm, "kind"), "value", getattr(arm, "kind"))
                    == "control"
                    else "treatment-1"
                ),
                observable_digest=(
                    f"observable-{getattr(witness, 'witness_id')}-"
                    f"{getattr(getattr(arm, 'kind'), 'value', getattr(arm, 'kind')).lower()}"
                ),
            )
            for witness in witnesses
            for arm in arms
        ]
        if self.attestation_mode == "missing_native_receipt":
            del observations[0].native_receipt
        elif self.attestation_mode == "wrong_nonce":
            observations[0].echoed_nonce = "foreign-nonce"
        elif self.attestation_mode == "duplicate_pair":
            observations[1] = _receipt(**vars(observations[0]))
        elif self.attestation_mode == "wrong_arm":
            observations[0].arm = "OTHER"
        elif self.attestation_mode == "wrong_subject":
            observations[0].subject = _receipt(composition_id="other")
        elif self.attestation_mode == "wrong_binary":
            observations[0].binary_digest = "other-binary"
        elif self.attestation_mode == "wrong_workload":
            observations[0].workload_digest = "other-workload"
        elif self.attestation_mode == "wrong_arm_receipt":
            observations[0].arm_receipt_id = "other-arm-receipt"
        control_receipt: object = _receipt(
            state="SUCCEEDED",
            receipt_id="baseline-1",
            clean_absence=True,
            subject=subject,
        )
        treatment_receipt: object = _receipt(
            state="SUCCEEDED",
            receipt_id="treatment-1",
            candidate_id=_CANDIDATE_ID,
            deployment_receipt_id="deploy-1",
        )
        if self.attestation_mode == "missing_control_receipt":
            control_receipt = _receipt()
        elif self.attestation_mode == "missing_treatment_receipt":
            treatment_receipt = _receipt()
        durable_record = _receipt(
            record_id="real-host-record-1",
            binary_digest="binary-1",
            workload_digest=workload_digest,
            ordered_observations=tuple(observations),
        )
        durable_record.persisted_bytes = _canonical_bytes(durable_record)
        self.persisted_probe_records.append(durable_record)
        real_host_proof = self.reported_proof
        if self.proof_issuer is not None:
            real_host_proof = self.proof_issuer.issue_after_probe(
                subject=subject,
                lease=lease,
                candidate_id=str(_public_field(subject, "candidate_id", "")),
                binary_digest="binary-1",
                workload_digest=str(workload_digest),
                observations=tuple(observations),
                durable_record_id=durable_record.record_id,
                persisted_record_bytes=durable_record.persisted_bytes,
            )
        return _receipt(
            state="SUCCEEDED",
            provenance=self.reported_provenance,
            real_host_proof=real_host_proof,
            # The issuer is the capability authority.  Production receives the
            # verifier with the probe receipt instead of treating a provenance
            # string (or a proof-shaped object) as authenticity.
            verify_real_host_proof=(
                self.proof_issuer.verifies if self.proof_issuer is not None else None
            ),
            control_receipt=control_receipt,
            treatment_receipt=treatment_receipt,
            observations=tuple(observations),
        )

    def record_cleanup_recovery(
        self,
        lease: object,
        deployment: object,
        rollback: object,
        attestation: object,
    ) -> object:
        self.trace.events.append("probe.recovery.record")
        self.recovery_calls.append((lease, deployment, rollback, attestation))
        payload = _receipt(
            subject=getattr(lease, "subject", None),
            lease=lease,
            plan_key="plan-1",
            deployment=deployment,
            rollback=rollback,
            provisional_attestation=attestation,
            attestation_digest="attestation-1",
            changed_artifact_ids=("nwave/role.toml",),
            rollback_token="rollback-1",
            attempt_count=1,
            failed_rollback_receipt=rollback,
            retry_owner="OPERATOR",
        )
        self.recovery_payloads.append(payload)
        if self.recovery_failure:
            return _receipt(state="INDETERMINATE", stage_error=self.recovery_failure)
        return _receipt(
            state="SUCCEEDED",
            recovery_key="subject+box-1+plan-1",
            payload=payload,
        )

    def release_lease(
        self, lease: object, recovery_key: object | None = None
    ) -> object:
        self.trace.events.append("probe.lease.release")
        if self.release_failure:
            return _receipt(state="INDETERMINATE", stage_error=self.release_failure)
        return _receipt(state="SUCCEEDED", lease=lease, recovery_key=recovery_key)


@dataclass
class ParityEvidenceLedgerWitness:
    trace: PortTrace
    failure: str | None = None
    raise_on_append: bool = False
    seeded_records: tuple[object, ...] = ()
    committed_records: list[object] = field(default_factory=list)
    read_mode: str = "exact"

    def append(self, envelope: object) -> object:
        self.trace.events.append("ledger.append")
        if self.raise_on_append:
            raise RuntimeError("ledger adapter exploded")
        if self.failure:
            state = (
                "INDETERMINATE"
                if self.failure == "PERSISTENCE_UNAVAILABLE"
                else "REFUSED"
            )
            return _receipt(state=state, stage_error=self.failure)
        self.committed_records.append(envelope)
        return _receipt(state="SUCCEEDED", record_id="record-1", envelope=envelope)

    def records_for(
        self, subject: object
    ) -> tuple[object, ...]:
        self.trace.events.append("ledger.read")
        if self.read_mode == "empty":
            return ()
        if self.read_mode == "wrong_subject":
            return (_receipt(subject=_receipt(composition_id="other")),)
        if self.read_mode == "tampered":
            return (*self.seeded_records, _receipt(attestation="tampered"))
        return (*self.seeded_records, *self.committed_records)


@dataclass
class FivePortWitnesses:
    trace: PortTrace = field(default_factory=PortTrace)
    digest_failure: str | None = None
    deployment_failure: str | None = None
    native_failure: str | None = None
    probe_failure: str | None = None
    ledger_failure: str | None = None
    ledger_exception: bool = False
    ledger_records: tuple[object, ...] = ()
    ledger_commits: list[object] = field(default_factory=list)
    ledger_read_mode: str = "exact"
    attestation_mode: str = "exact"
    recovery_failure: str | None = None
    release_failure: str | None = None
    receipt_mode: str = "exact"
    probe_reported_provenance: str = "EXTERNAL_DOUBLE"
    probe_reported_proof: object | None = None
    proof_issuer: GenuineRealHostProofIssuerWitness | None = None
    digest_calls: list[object] = field(default_factory=list)
    digest_sequence: tuple[str, ...] = ()
    recovery_payloads: list[object] = field(default_factory=list)
    recovery_calls: list[tuple[object, object, object, object]] = field(
        default_factory=list
    )
    deployment_plans: list[object] = field(default_factory=list)
    issued_deployment_receipts: list[object] = field(default_factory=list)
    issued_rollback_receipts: list[object] = field(default_factory=list)
    issued_leases: list[object] = field(default_factory=list)
    persisted_probe_records: list[object] = field(default_factory=list)
    factory_calls: int = 0
    factory_native_inputs: list[object] = field(default_factory=list)
    acquired_subjects: list[object] = field(default_factory=list)
    rechecked_target_selections: list[object] = field(default_factory=list)

    def _probe_factory(self) -> Callable[[object], RealHostProbeWitness]:
        probe = RealHostProbeWitness(
            self.trace,
            self.probe_failure,
            self.attestation_mode,
            self.recovery_failure,
            self.release_failure,
            self.receipt_mode,
            self.probe_reported_provenance,
            self.probe_reported_proof,
            self.proof_issuer,
            self.recovery_payloads,
            self.recovery_calls,
            self.acquired_subjects,
            self.rechecked_target_selections,
            self.issued_leases,
            self.persisted_probe_records,
        )

        def factory(native_execution: object) -> RealHostProbeWitness:
            # The sole runner is supplied once at composition time. The fixture
            # never creates a second native-execution seam.
            assert native_execution is not None
            self.factory_calls += 1
            self.factory_native_inputs.append(native_execution)
            return probe

        return factory

    def external_ports(self) -> dict[str, object]:
        return {
            "candidate_material_digest": CandidateMaterialDigestWitness(
                self.trace,
                self.digest_failure,
                self.digest_calls,
                self.digest_sequence,
            ),
            "owned_artifact_deployment": OwnedArtifactDeploymentWitness(
                self.trace,
                self.deployment_failure,
                False,
                self.deployment_plans,
                self.issued_deployment_receipts,
                self.issued_rollback_receipts,
            ),
            "native_execution": NativeExecutionWitness(self.trace, self.native_failure),
            "real_host_probe": self._probe_factory(),
            "parity_evidence_ledger": ParityEvidenceLedgerWitness(
                self.trace,
                self.ledger_failure,
                self.ledger_exception,
                self.ledger_records,
                self.ledger_commits,
                self.ledger_read_mode,
            ),
        }
