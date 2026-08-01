"""Public composition root for the shared Codex host-parity journey."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace

from des.application.candidate_lineage import CandidateLineageVerifier
from des.domain.codex_parity import (
    CandidateInputs,
    CandidateLocator,
    CandidateOrigin,
    Digest,
    MaterialDigestObservation,
    ReceiptState,
    WhatWhyHow,
    mint_candidate_id,
)
from des.ports.driven_ports.real_host_probe_port import ProbeArmKind


class JourneyOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    INDETERMINATE = "INDETERMINATE"
    FAILED = "FAILED"


class JourneyStageError(str, Enum):
    REQUEST_INVALID = "REQUEST_INVALID"
    PLAN_INVALID = "PLAN_INVALID"
    CONTROL_BASELINE_UNPROVED = "CONTROL_BASELINE_UNPROVED"
    TREATMENT_DEPLOYMENT_UNPROVED = "TREATMENT_DEPLOYMENT_UNPROVED"
    ORIGIN_FORBIDDEN = "ORIGIN_FORBIDDEN"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
    BOX_UNAVAILABLE = "BOX_UNAVAILABLE"
    LEASE_LOST = "LEASE_LOST"
    TERMINATION_UNPROVED = "TERMINATION_UNPROVED"
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    NONCE_MISMATCH = "NONCE_MISMATCH"
    OBSERVATION_DUPLICATE = "OBSERVATION_DUPLICATE"
    EXECUTION_UNPROVED = "EXECUTION_UNPROVED"
    ATTESTATION_SUBJECT_MISMATCH = "ATTESTATION_SUBJECT_MISMATCH"
    BINARY_IDENTITY_MISMATCH = "BINARY_IDENTITY_MISMATCH"
    MATERIAL_MISSING = "MATERIAL_MISSING"
    MATERIAL_UNREADABLE = "MATERIAL_UNREADABLE"
    DIGEST_UNSTABLE = "DIGEST_UNSTABLE"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"
    LEDGER_REJECTED = "LEDGER_REJECTED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    RECOVERY_RECORD_UNAVAILABLE = "RECOVERY_RECORD_UNAVAILABLE"
    LEASE_RELEASE_UNPROVED = "LEASE_RELEASE_UNPROVED"
    READ_UNAVAILABLE = "READ_UNAVAILABLE"
    RECORD_TAMPERED = "RECORD_TAMPERED"
    ADAPTER_UNAVAILABLE = "ADAPTER_UNAVAILABLE"


_REFUSED = frozenset(
    {
        "REQUEST_INVALID",
        "PLAN_INVALID",
        "CONTROL_BASELINE_UNPROVED",
        "TREATMENT_DEPLOYMENT_UNPROVED",
        "ORIGIN_FORBIDDEN",
        "SUBJECT_MISMATCH",
        "TARGET_UNAVAILABLE",
        "LEDGER_REJECTED",
        "ENVELOPE_INVALID",
        "ITEM_UNDECLARED",
        "WITNESS_UNDECLARED",
        "DUPLICATE_EVIDENCE",
        "OBSERVABLE_MISSING",
    }
)
_INDETERMINATE = frozenset(
    {
        "MATERIAL_MISSING",
        "MATERIAL_UNREADABLE",
        "ALGORITHM_UNSUPPORTED",
        "EXECUTABLE_NOT_FOUND",
        "TIMED_OUT_TREE_TERMINATED",
        "TERMINATION_UNPROVED",
        "BOX_UNAVAILABLE",
        "LEASE_LOST",
        "OBSERVATION_MISSING",
        "WITNESS_TIMED_OUT",
        "EXECUTION_UNPROVED",
        "PERSISTENCE_UNAVAILABLE",
        "READ_UNAVAILABLE",
        "RECOVERY_RECORD_UNAVAILABLE",
        "LEASE_RELEASE_UNPROVED",
        "ADAPTER_UNAVAILABLE",
    }
)


@dataclass(frozen=True)
class JourneyDiagnostic:
    what: str
    why: str
    how: str


@dataclass(frozen=True)
class PublicDeploymentReceipt:
    candidate_id: str
    receipt_id: str


@dataclass(frozen=True)
class PublicAttestation:
    candidate_id: str
    observations: tuple[object, ...]


@dataclass(frozen=True)
class PublicEvidence:
    state: str
    contributes_to_full_parity: bool
    policy_id: str | None = None
    reason: str | None = None
    remediation: str | None = None


@dataclass(frozen=True)
class ParityJourneyResult:
    outcome: JourneyOutcome
    stage_error: JourneyStageError | None = None
    stage_state: str | None = None
    diagnostic: JourneyDiagnostic | None = None
    candidate_id: str | None = None
    deployment_receipt: PublicDeploymentReceipt | None = None
    attestation: PublicAttestation | None = None
    evidence: PublicEvidence | None = None
    retry_owner: str | None = None


_REQUEST_KEYS = frozenset(
    {
        "subject",
        "build_inputs",
        "assembled_candidate",
        "treatment_plan",
        "probe",
        "expected_evidence",
    }
)
_EVIDENCE_STATES = frozenset(
    {
        "PROVED",
        "DOCUMENTED",
        "UNVERIFIED",
        "UNSUPPORTED",
        "DEGRADED",
        "INDETERMINATE",
        "FAILED",
    }
)


class _JourneyAbort(Exception):
    def __init__(self, result: ParityJourneyResult) -> None:
        self.result = result


class _UnavailableProbe:
    """A factory was callable but could not yield the declared probe protocol.

    This is deliberately distinct from a malformed *composition*: the five-port
    closure is still rejected at compose time.  A callable factory which raises
    or returns a receipt/value instead of its probe is a runtime adapter failure
    and must cross the public journey boundary as a typed result, never leak an
    implementation exception.
    """


class _SubjectCarrier(dict[str, object]):
    """One canonical subject usable by mapping and typed driven-port callers."""

    def __getattr__(self, name: str) -> object:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class _PublicDigestBridge:
    """Translate the frozen public digest adapter into the lineage port type."""

    def __init__(self, port: object) -> None:
        self._port = port

    def digest(self, locator: CandidateLocator) -> MaterialDigestObservation:
        operation = getattr(self._port, "digest", None)
        if not callable(operation):
            return MaterialDigestObservation(
                ReceiptState.INDETERMINATE,
                None,
                WhatWhyHow(
                    "ADAPTER_UNAVAILABLE: digest adapter unavailable",
                    "candidate bytes cannot be observed",
                    "restore the declared digest adapter",
                ),
            )
        try:
            value = operation(locator)
        except Exception:
            return MaterialDigestObservation(
                ReceiptState.INDETERMINATE,
                None,
                WhatWhyHow(
                    "ADAPTER_UNAVAILABLE: digest adapter failed",
                    "candidate bytes cannot be observed",
                    "restore the declared digest adapter",
                ),
            )
        if isinstance(value, Mapping):
            return MaterialDigestObservation(
                ReceiptState.INDETERMINATE,
                None,
                WhatWhyHow(
                    "ADAPTER_UNAVAILABLE: digest adapter returned a mapping receipt",
                    "candidate lineage requires the declared typed digest observation",
                    "restore the declared digest adapter",
                ),
            )
        fields = getattr(value, "__dict__", None)
        if not isinstance(fields, Mapping):
            return MaterialDigestObservation(
                ReceiptState.INDETERMINATE,
                None,
                WhatWhyHow(
                    "ADAPTER_UNAVAILABLE: digest adapter returned no receipt",
                    "candidate bytes cannot be observed",
                    "restore the declared digest adapter",
                ),
            )
        value = dict(fields)
        try:
            state = ReceiptState(str(value.get("state", "INDETERMINATE")).lower())
        except ValueError:
            state = ReceiptState.INDETERMINATE
        digest = value.get("digest")
        if state is ReceiptState.SUCCEEDED and isinstance(digest, str) and digest:
            return MaterialDigestObservation(state, Digest(digest))
        error = str(value.get("stage_error", "ADAPTER_UNAVAILABLE"))
        return MaterialDigestObservation(
            state
            if state is not ReceiptState.SUCCEEDED
            else ReceiptState.INDETERMINATE,
            None,
            WhatWhyHow(
                f"{error}: material digest is unavailable",
                "candidate lineage cannot be established",
                "restore readable candidate material",
            ),
        )


class CodexParityComposition:
    """The sole production factory for the five-port parity transaction."""

    def __init__(
        self, ports: Mapping[str, object], probe: object | None = None
    ) -> None:
        self._ports = dict(ports)
        self._probe = probe

    @classmethod
    def compose(
        cls,
        *,
        candidate_material_digest: object,
        owned_artifact_deployment: object,
        native_execution: object,
        real_host_probe: Callable[[object], object] | object,
        parity_evidence_ledger: object,
    ) -> CodexParityComposition:
        ports = {
            "candidate_material_digest": candidate_material_digest,
            "owned_artifact_deployment": owned_artifact_deployment,
            "native_execution": native_execution,
            "real_host_probe": real_host_probe,
            "parity_evidence_ledger": parity_evidence_ledger,
        }
        probe = cls._validate_ports(ports)
        return cls(ports, probe)

    @staticmethod
    def _validate_ports(ports: Mapping[str, object]) -> object:
        required = frozenset(
            {
                "candidate_material_digest",
                "owned_artifact_deployment",
                "native_execution",
                "real_host_probe",
                "parity_evidence_ledger",
            }
        )
        if frozenset(ports) != required:
            raise ValueError(
                "Codex parity composition requires exactly its five declared ports"
            )
        digest_port = ports["candidate_material_digest"]
        if not callable(getattr(digest_port, "digest", None)) and not callable(
            getattr(digest_port, "verify_candidate_material", None)
        ):
            raise TypeError("candidate_material_digest must expose digest")
        deployment = ports["owned_artifact_deployment"]
        if not all(
            callable(getattr(deployment, name, None)) for name in ("deploy", "rollback")
        ):
            raise TypeError("owned_artifact_deployment must expose deploy and rollback")
        if not callable(getattr(ports["native_execution"], "execute", None)):
            raise TypeError("native_execution must expose execute")
        factory = ports["real_host_probe"]
        if not callable(factory):
            raise TypeError("real_host_probe must be a factory")
        try:
            probe = factory(ports["native_execution"])
        except Exception:
            return _UnavailableProbe()
        if isinstance(probe, (Mapping, str, bytes)):
            return _UnavailableProbe()
        if not all(
            callable(getattr(probe, name, None))
            for name in (
                "acquire_lease",
                "probe",
                "record_cleanup_recovery",
                "release_lease",
            )
        ):
            raise TypeError("real_host_probe factory returned an incomplete probe")
        ledger = ports["parity_evidence_ledger"]
        if not all(
            callable(getattr(ledger, name, None)) for name in ("append", "records_for")
        ):
            raise TypeError("parity_evidence_ledger must expose append and records_for")
        return probe

    def journey_port(self) -> CodexParityJourneyPort:
        return CodexParityJourneyPort(self._ports, self._probe)


class CodexParityJourneyPort:
    """Own the serial candidate → probe → rollback → durable-evidence transaction."""

    def __init__(
        self, ports: Mapping[str, object], probe: object | None = None
    ) -> None:
        self._ports = ports
        self._probe = probe

    def run(self, request: Mapping[str, object]) -> ParityJourneyResult:
        invalid = self._validate(request)
        if invalid:
            return self._non_success(*invalid)
        subject = self._mapping(request["subject"])
        lease_subject = _SubjectCarrier(subject)
        candidate = self._mapping(request["assembled_candidate"])
        inputs = CandidateInputs(
            Digest(str(self._mapping(request["build_inputs"])["distribution_digest"])),
            Digest(
                str(self._mapping(request["build_inputs"])["public_manifest_digest"])
            ),
            str(self._mapping(request["build_inputs"])["build_recipe_version"]),
        )
        assembled = CandidateLocator(
            str(candidate["locator"]), CandidateOrigin.ASSEMBLED_DISTRIBUTION
        )
        lineage = CandidateLineageVerifier(
            _PublicDigestBridge(self._ports["candidate_material_digest"])
        )
        build = lineage.record_build(inputs, assembled)
        if build.state is not ReceiptState.SUCCEEDED:
            return self._lineage_non_success(build.state, build.diagnostic)
        candidate_id = (
            build.candidate_id.value if build.candidate_id is not None else ""
        )
        if subject.get("candidate_id") != candidate_id:
            return self._non_success(
                "REQUEST_INVALID",
                "subject candidate identity differs from canonical build receipt",
            )

        probe = self._probe_port()
        lease: Mapping[str, object] | None = None
        lease_receipt: object | None = None
        lease_acquired = False
        deployment: Mapping[str, object] | None = None
        deployment_receipt: object | None = None
        provisional: PublicAttestation | None = None
        completed: ParityJourneyResult | None = None
        try:
            lease, lease_receipt = self._call_with_raw(
                probe,
                ("acquire_box_lease", "acquire_lease"),
                lease_subject,
            )
            self._abort_if_non_success(lease)
            lease_acquired = True
            # Lease acquisition is the frozen target-authority boundary.  Do
            # not probe a legacy second target-verifier: the lease receipt is
            # the proof for the exact canonical selection it accepted.
            target = {
                "state": lease.get("state"),
                "binary_digest": lease.get("target_binary_digest"),
            }
            deployment, deployment_receipt = self._call_with_raw(
                self._ports["owned_artifact_deployment"],
                ("deploy_treatment", "deploy"),
                self._mapping(request["treatment_plan"]),
            )
            self._abort_if_non_success(deployment)
            if str(deployment.get("candidate_id", "")) != candidate_id:
                raise _JourneyAbort(self._non_success("TREATMENT_DEPLOYMENT_UNPROVED"))
            installed_locator = CandidateLocator(
                str(deployment.get("receipt_id", "")), CandidateOrigin.ISOLATED_INSTALL
            )
            deployed = lineage.verify_deployment(build, installed_locator)
            if deployed.state is not ReceiptState.SUCCEEDED:
                raise _JourneyAbort(
                    self._lineage_non_success(deployed.state, deployed.diagnostic)
                )
            probe_request = self._mapping(request["probe"])
            native_receipts: dict[str, Mapping[str, object]] = {}
            for arm in ("CONTROL", "TREATMENT"):
                native = self._call(
                    self._ports["native_execution"],
                    ("run_native", "execute"),
                    {"arm": arm, "subject": subject, "probe": probe_request},
                )
                self._abort_if_non_success(native)
                native_receipts[arm] = native
            paired = self._paired_probe(
                probe,
                lease_receipt if lease_receipt is not None else lease,
                self._typed_probe_request(lease_subject, probe_request),
            )
            self._abort_if_non_success(paired)
            raw_observations = tuple(self._sequence(paired.get("observations")))
            observations = tuple(
                item
                for item in (
                    self._normalise_observation(value) for value in raw_observations
                )
                if item
            )
            attestation_error = self._attestation_error(
                subject,
                probe_request,
                observations,
                target,
                deployment,
                paired,
                native_receipts,
            )
            if attestation_error:
                raise _JourneyAbort(self._non_success(attestation_error))
            if not self._proved_host_evidence_is_authentic(request, paired):
                raise _JourneyAbort(
                    self._non_success(
                        "EXECUTION_UNPROVED",
                        "PROVED evidence lacks a verified persisted real-host capability",
                    )
                )
            consumed = lineage.verify_probe(
                deployed, Digest(str(target.get("binary_digest", "unknown")))
            )
            if consumed.state is not ReceiptState.SUCCEEDED:
                raise _JourneyAbort(
                    self._lineage_non_success(consumed.state, consumed.diagnostic)
                )
            provisional = PublicAttestation(candidate_id, raw_observations)
        except _JourneyAbort as abort:
            completed = abort.result
        except Exception:
            completed = self._non_success("ADAPTER_UNAVAILABLE")
        finally:
            if deployment is not None:
                rollback, rollback_receipt = self._call_safely_with_raw(
                    self._ports["owned_artifact_deployment"],
                    ("rollback_treatment", "rollback"),
                    deployment_receipt
                    if deployment_receipt is not None
                    else deployment,
                )
                if not self._is_success(rollback):
                    rollback_error = self._receipt_error(rollback)
                    if rollback_error == "ADAPTER_UNAVAILABLE":
                        completed = self._non_success(
                            rollback_error,
                            "rollback adapter returned no closed receipt",
                        )
                    else:
                        recovery = self._record_recovery(
                            probe,
                            lease_receipt if lease_receipt is not None else lease,
                            deployment_receipt
                            if deployment_receipt is not None
                            else deployment,
                            rollback_receipt,
                            provisional,
                        )
                        evidence = PublicEvidence(
                            "FAILED",
                            False,
                            reason="rollback failed",
                            remediation="box arbiter recovery required",
                        )
                        envelope: Mapping[str, object] = {
                            "subject": subject,
                            "candidate_id": candidate_id,
                            "attestation": provisional,
                            "evidence": evidence,
                            "recovery_key": recovery.get("recovery_key"),
                        }
                        recovery_error = self._receipt_error(recovery)
                        durability_error = self._append_and_read(
                            subject, envelope, read_after_rejection=True
                        )
                        if recovery_error:
                            completed = self._non_success(
                                "ROLLBACK_FAILED",
                                f"rollback recovery did not become durable: {recovery_error}",
                                "FAILED",
                                retry_owner="OPERATOR",
                            )
                        elif durability_error:
                            completed = self._non_success(
                                "ROLLBACK_FAILED",
                                f"rollback failure evidence did not become durable: {durability_error}",
                                "FAILED",
                                retry_owner="OPERATOR",
                            )
                        else:
                            completed = self._non_success(
                                "ROLLBACK_FAILED",
                                receipt_state="FAILED",
                                retry_owner="OPERATOR",
                            )
                elif provisional is not None:
                    evidence = self._evidence(request)
                    envelope = {
                        "subject": subject,
                        "candidate_id": candidate_id,
                        "attestation": provisional,
                        "evidence": evidence,
                    }
                    durable_error = self._append_and_read(subject, envelope)
                    if durable_error:
                        completed = self._non_success(durable_error)
                    else:
                        completed = ParityJourneyResult(
                            JourneyOutcome.COMPLETED,
                            candidate_id=candidate_id,
                            deployment_receipt=PublicDeploymentReceipt(
                                candidate_id, str(deployment.get("receipt_id", ""))
                            ),
                            attestation=provisional,
                            evidence=evidence,
                        )
            if lease_acquired and lease is not None:
                release = self._call_safely(
                    probe,
                    ("release_box_lease", "release_lease"),
                    lease_receipt if lease_receipt is not None else lease,
                )
                if not self._is_success(release) and not (
                    completed is not None
                    and completed.stage_error is JourneyStageError.ROLLBACK_FAILED
                ):
                    completed = self._non_success(
                        self._receipt_error(release) or "LEASE_RELEASE_UNPROVED",
                        "box lease release receipt is not successful",
                        self._receipt_state(release),
                    )
        return completed or self._non_success("ADAPTER_UNAVAILABLE")

    def _probe_port(self) -> object:
        if self._probe is not None:
            return self._probe
        port = self._ports["real_host_probe"]
        return port(self._ports["native_execution"]) if callable(port) else port

    @staticmethod
    def _typed_probe_request(
        subject: Mapping[str, object], probe: Mapping[str, object]
    ) -> object:
        """Build the declared probe carrier at the public-to-driven boundary."""
        witnesses = tuple(
            SimpleNamespace(
                witness_id=str(item.get("id", "")),
                item_id=str(item.get("item", "")),
                suite_id=str(item.get("suite", "")),
                timeout_seconds=float(item.get("timeout", 0)),
            )
            for item in CodexParityJourneyPort._sequence(probe.get("witnesses"))
            if isinstance(item, Mapping)
        )
        arms = tuple(
            SimpleNamespace(
                kind=ProbeArmKind(str(item.get("kind", "")).lower()),
                nonce=str(item.get("nonce", "")),
            )
            for item in CodexParityJourneyPort._sequence(probe.get("arms"))
            if isinstance(item, Mapping)
        )
        return SimpleNamespace(
            subject=subject,
            workload_digest=probe.get("workload_digest"),
            witnesses=witnesses,
            arms=arms,
        )

    def _paired_probe(
        self, probe: object, lease: object, request: object
    ) -> Mapping[str, object]:
        operation = getattr(probe, "probe", None)
        if not callable(operation):
            return {"state": "INDETERMINATE", "stage_error": "ADAPTER_UNAVAILABLE"}
        try:
            value = operation(lease, request)
        except Exception:
            return {"state": "INDETERMINATE", "stage_error": "ADAPTER_UNAVAILABLE"}
        return self._normalise_receipt(value)

    @staticmethod
    def _normalise_observation(value: object) -> Mapping[str, object]:
        observation = dict(CodexParityJourneyPort._mapping(value))
        arm = observation.get("arm")
        arm_value = getattr(arm, "value", arm)
        if arm_value is not None:
            observation["arm"] = str(arm_value).upper()
        if "echoed_nonce" in observation:
            observation["nonce"] = observation["echoed_nonce"]
        return observation

    @staticmethod
    def _proved_host_evidence_is_authentic(
        request: Mapping[str, object], paired: Mapping[str, object]
    ) -> bool:
        """Admit PROVED only through the probe authority's opaque verifier.

        A provenance label is descriptive data and can be forged.  The probe
        that persisted the observations must instead return a capability and
        the verifier authority for that capability.  Non-PROVED evidence is a
        documented disposition, not a claim that needs this authority.
        """
        expected = CodexParityJourneyPort._mapping(request.get("expected_evidence"))
        if expected.get("kind") != "PROVED":
            return True
        if paired.get("provenance") != "REAL_HOST_PERSISTED":
            return False
        verifier = paired.get("verify_real_host_proof")
        proof = paired.get("real_host_proof")
        if not callable(verifier) or proof is None:
            return False
        try:
            return verifier(proof) is True
        except Exception:
            return False

    @staticmethod
    def _lineage_non_success(
        state: ReceiptState, diagnostic: WhatWhyHow | None
    ) -> ParityJourneyResult:
        error = diagnostic.what.partition(":")[0] if diagnostic is not None else ""
        if error in {
            "MATERIAL_MISSING",
            "MATERIAL_UNREADABLE",
            "DIGEST_UNSTABLE",
            "DIGEST_MISMATCH",
            "ADAPTER_UNAVAILABLE",
        }:
            return CodexParityJourneyPort._non_success(
                error, diagnostic.what if diagnostic else ""
            )
        if diagnostic is not None and "digest changed" in diagnostic.what:
            return CodexParityJourneyPort._non_success(
                "DIGEST_MISMATCH", diagnostic.what
            )
        if state is ReceiptState.REFUSED:
            return CodexParityJourneyPort._non_success(
                "ORIGIN_FORBIDDEN", diagnostic.what if diagnostic else ""
            )
        if state is ReceiptState.INDETERMINATE:
            return CodexParityJourneyPort._non_success(
                "MATERIAL_UNREADABLE", diagnostic.what if diagnostic else ""
            )
        return CodexParityJourneyPort._non_success(
            "DIGEST_MISMATCH", diagnostic.what if diagnostic else ""
        )

    def _append_and_read(
        self,
        subject: Mapping[str, object],
        envelope: Mapping[str, object],
        *,
        read_after_rejection: bool = False,
    ) -> str | None:
        appended = self._call_safely(
            self._ports["parity_evidence_ledger"],
            ("append_evidence", "append"),
            envelope,
        )
        if not self._is_success(appended):
            if read_after_rejection:
                reader = getattr(
                    self._ports["parity_evidence_ledger"], "records_for", None
                )
                if callable(reader):
                    try:
                        reader(subject)
                    except Exception:
                        pass
            return self._receipt_error(appended)
        # ``records_for`` returns a sequence, rather than a receipt mapping.  Read it
        # directly so exact persisted-envelope identity survives the boundary.
        reader = getattr(self._ports["parity_evidence_ledger"], "records_for", None)
        try:
            population = reader(subject) if callable(reader) else ()
        except Exception:
            return "ADAPTER_UNAVAILABLE"
        if not isinstance(population, Sequence) or isinstance(
            population, (str, bytes, Mapping)
        ):
            return "ADAPTER_UNAVAILABLE"
        if not population:
            return "READ_UNAVAILABLE"
        if any(
            not isinstance(record, Mapping) or record.get("subject") != subject
            for record in population
        ):
            # A read outside the requested subject is a corrupted readback, not
            # an authority request made by this journey.
            return "RECORD_TAMPERED"
        if not any(record == envelope for record in population):
            return "RECORD_TAMPERED"
        return None

    def _record_recovery(
        self,
        probe: object,
        lease: object | None,
        deployment: object,
        rollback: object,
        provisional: PublicAttestation | None,
    ) -> Mapping[str, object]:
        if lease is None:
            return {}
        operation = getattr(probe, "record_cleanup_recovery", None)
        if not callable(operation):
            return {"state": "FAILED", "stage_error": "ADAPTER_UNAVAILABLE"}
        try:
            return self._normalise_receipt(
                operation(lease, deployment, rollback, provisional)
            )
        except Exception:
            return {"state": "FAILED", "stage_error": "ADAPTER_UNAVAILABLE"}

    def _abort_if_non_success(self, receipt: Mapping[str, object]) -> None:
        if not self._is_success(receipt):
            error = self._receipt_error(receipt) or "ADAPTER_UNAVAILABLE"
            raise _JourneyAbort(
                self._non_success(
                    error,
                    "port receipt is not successful",
                    self._receipt_state(receipt)
                    if self._error(receipt)
                    else "INDETERMINATE",
                )
            )

    def _validate(self, request: Mapping[str, object]) -> tuple[str, str] | None:
        if frozenset(request) != _REQUEST_KEYS:
            return "REQUEST_INVALID", "public request keys are not closed"
        subject, build, candidate, plan, probe = (
            self._mapping(request[k])
            for k in (
                "subject",
                "build_inputs",
                "assembled_candidate",
                "treatment_plan",
                "probe",
            )
        )
        if any(
            not subject.get(k)
            for k in (
                "composition_id",
                "candidate_id",
                "manifest_digest",
                "requested_platform",
            )
        ):
            return "REQUEST_INVALID", "subject identity is incomplete"
        selection = self._mapping(subject.get("target_selection"))
        caps = self._sequence(selection.get("detected_capabilities"))
        if (
            subject.get("requested_platform") == "CODEX"
            and "claude-installed" in caps
            and not any(x in {"codex", "codex-installed"} for x in caps)
        ):
            return "TARGET_UNAVAILABLE", "requested Codex is unavailable"
        plan_selection = self._mapping(
            self._mapping(plan.get("subject")).get("target_selection")
        )
        probe_selection = self._mapping(
            self._mapping(probe.get("subject")).get("target_selection")
        )
        if not selection or selection != plan_selection or selection != probe_selection:
            return "REQUEST_INVALID", "target selection carriers do not agree"
        if not all(
            build.get(key)
            for key in (
                "distribution_digest",
                "public_manifest_digest",
                "build_recipe_version",
            )
        ):
            return "REQUEST_INVALID", "build candidate inputs are incomplete"
        expected = mint_candidate_id(
            CandidateInputs(
                Digest(str(build.get("distribution_digest", ""))),
                Digest(str(build.get("public_manifest_digest", ""))),
                str(build.get("build_recipe_version", "")),
            )
        ).value
        if (
            not expected
            or subject.get("candidate_id") != expected
            or candidate.get("origin") != "ASSEMBLED_DISTRIBUTION"
        ):
            return (
                (
                    "ORIGIN_FORBIDDEN",
                    str(candidate.get("origin", "")).lower().replace("_", "-"),
                )
                if candidate.get("origin") != "ASSEMBLED_DISTRIBUTION"
                else (
                    "REQUEST_INVALID",
                    "subject candidate identity is not builder-minted",
                )
            )
        intents = plan.get("intents")
        if (
            plan.get("subject") != subject
            or not isinstance(intents, list)
            or not intents
            or any(
                not isinstance(intent, Mapping)
                or not isinstance(intent.get("key"), str)
                or not str(intent["key"]).strip()
                for intent in intents
            )
            or len(
                {
                    str(intent["key"])
                    for intent in intents
                    if isinstance(intent, Mapping)
                }
            )
            != len(intents)
        ):
            return (
                "PLAN_INVALID",
                "treatment plan is empty or scoped to another subject",
            )
        if probe.get("subject") != subject:
            return "REQUEST_INVALID", "probe subject differs from journey subject"
        witnesses = probe.get("witnesses")
        if (
            not isinstance(witnesses, list)
            or not witnesses
            or any(
                not isinstance(w, Mapping)
                or not all(w.get(k) for k in ("id", "item", "suite"))
                or not isinstance(w.get("timeout"), (int, float))
                or w["timeout"] <= 0
                for w in witnesses
            )
        ):
            return "REQUEST_INVALID", "witness population is incomplete"
        arms = probe.get("arms")
        if not isinstance(arms, list) or len(arms) != 2:
            return "REQUEST_INVALID", "A/B pair must contain exactly two arms"
        arm_map = {
            str(self._mapping(arm).get("kind")): self._mapping(arm) for arm in arms
        }
        if (
            set(arm_map) != {"CONTROL", "TREATMENT"}
            or len({a.get("nonce") for a in arm_map.values()}) != 2
            or any(not a.get("nonce") for a in arm_map.values())
        ):
            return "REQUEST_INVALID", "A/B kinds or nonces are not closed"
        if arm_map["CONTROL"].get("clean_absence") is not True:
            return "CONTROL_BASELINE_UNPROVED", "control absence is unproved"
        if (
            arm_map["TREATMENT"].get("isolated_install") is not True
            or arm_map["TREATMENT"].get("candidate_id", subject["candidate_id"])
            != subject["candidate_id"]
        ):
            return (
                "TREATMENT_DEPLOYMENT_UNPROVED",
                "treatment candidate lineage is unproved",
            )
        if (
            arm_map["CONTROL"].get("binary_digest")
            != arm_map["TREATMENT"].get("binary_digest")
            or arm_map["CONTROL"].get("workload_digest")
            != arm_map["TREATMENT"].get("workload_digest")
            or arm_map["CONTROL"].get("workload_digest") != probe.get("workload_digest")
        ):
            return (
                "REQUEST_INVALID",
                "control and treatment must bind one binary and workload",
            )
        evidence = self._mapping(request["expected_evidence"])
        state = evidence.get("kind")
        if state not in _EVIDENCE_STATES:
            return "REQUEST_INVALID", "expected evidence state is not closed"
        if state == "DEGRADED" and (
            not evidence.get("policy_id") or len(evidence) != 2
        ):
            return "REQUEST_INVALID", "degraded evidence requires only policy_id"
        if state in {"INDETERMINATE", "FAILED"} and (
            not evidence.get("reason")
            or not evidence.get("remediation")
            or len(evidence) != 3
        ):
            return (
                "REQUEST_INVALID",
                "non-success evidence requires reason and remediation",
            )
        if (
            state in {"PROVED", "DOCUMENTED", "UNVERIFIED", "UNSUPPORTED"}
            and len(evidence) != 1
        ):
            return "REQUEST_INVALID", "evidence state does not accept payload fields"
        return None

    @staticmethod
    def _attestation_error(
        subject: Mapping[str, object],
        probe: Mapping[str, object],
        observations: tuple[Mapping[str, object], ...],
        target: Mapping[str, object],
        deployment: Mapping[str, object],
        paired: Mapping[str, object],
        native_receipts: Mapping[str, Mapping[str, object]],
    ) -> str | None:
        witnesses = CodexParityJourneyPort._sequence(probe.get("witnesses"))
        arms = CodexParityJourneyPort._sequence(probe.get("arms"))
        expected = {
            (str(w.get("id")), str(a.get("kind")))
            for w in witnesses
            if isinstance(w, Mapping)
            for a in arms
            if isinstance(a, Mapping)
        }
        pairs: set[tuple[str, str]] = set()
        nonces = {
            str(a.get("kind")): a.get("nonce") for a in arms if isinstance(a, Mapping)
        }
        binary_digest = target.get("binary_digest")
        workload_digest = probe.get("workload_digest")
        control = CodexParityJourneyPort._mapping(paired.get("control_receipt"))
        treatment = CodexParityJourneyPort._mapping(paired.get("treatment_receipt"))
        if not binary_digest or not workload_digest:
            return "BINARY_IDENTITY_MISMATCH"
        if (
            control.get("state") != "SUCCEEDED"
            or control.get("clean_absence") is not True
            or control.get("subject") != subject
        ):
            return "CONTROL_BASELINE_UNPROVED"
        if (
            treatment.get("state") != "SUCCEEDED"
            or treatment.get("candidate_id") != subject.get("candidate_id")
            or treatment.get("deployment_receipt_id") != deployment.get("receipt_id")
        ):
            return "TREATMENT_DEPLOYMENT_UNPROVED"
        if len(observations) != len(expected):
            return "OBSERVATION_MISSING"
        for observation in observations:
            if observation.get("subject") != subject:
                return "ATTESTATION_SUBJECT_MISMATCH"
            arm, witness = (
                str(observation.get("arm")),
                str(observation.get("witness_id")),
            )
            if (
                (witness, arm) not in expected
                or arm not in nonces
                or observation.get("nonce") != nonces[arm]
            ):
                return "NONCE_MISMATCH"
            native = native_receipts.get(arm, {})
            native_receipt = native.get("receipt_id")
            if (
                not native_receipt
                or observation.get("native_receipt") != native_receipt
            ):
                return "EXECUTION_UNPROVED"
            if (
                observation.get("binary_digest") != binary_digest
                or observation.get("workload_digest") != workload_digest
            ):
                return "BINARY_IDENTITY_MISMATCH"
            if arm == "CONTROL" and observation.get("arm_receipt_id") != control.get(
                "receipt_id"
            ):
                return "CONTROL_BASELINE_UNPROVED"
            if arm == "TREATMENT" and observation.get(
                "arm_receipt_id"
            ) != treatment.get("receipt_id"):
                return "TREATMENT_DEPLOYMENT_UNPROVED"
            if (witness, arm) in pairs:
                return "OBSERVATION_DUPLICATE"
            pairs.add((witness, arm))
        return None if pairs == expected else "OBSERVATION_MISSING"

    @staticmethod
    def _mapping(value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return value
        fields = getattr(value, "__dict__", None)
        return dict(fields) if isinstance(fields, Mapping) else {}

    @staticmethod
    def _sequence(value: object) -> Sequence[object]:
        return (
            value if isinstance(value, Sequence) and not isinstance(value, str) else ()
        )

    @staticmethod
    def _call(
        port: object, names: tuple[str, ...], argument: object
    ) -> Mapping[str, object]:
        for name in names:
            operation = getattr(port, name, None)
            if callable(operation):
                value = operation(argument)
                return CodexParityJourneyPort._normalise_receipt(value)
        return {"state": "INDETERMINATE", "stage_error": "ADAPTER_UNAVAILABLE"}

    @staticmethod
    def _normalise_receipt(value: object) -> Mapping[str, object]:
        receipt = CodexParityJourneyPort._mapping(value)
        if not receipt or (
            str(receipt.get("state", "")).upper() == "SUCCEEDED" and len(receipt) == 1
        ):
            return {"state": "INDETERMINATE", "stage_error": "ADAPTER_UNAVAILABLE"}
        return receipt

    @staticmethod
    def _call_with_raw(
        port: object, names: tuple[str, ...], argument: object
    ) -> tuple[Mapping[str, object], object]:
        for name in names:
            operation = getattr(port, name, None)
            if callable(operation):
                raw = operation(argument)
                return CodexParityJourneyPort._normalise_receipt(raw), raw
        unavailable = {
            "state": "INDETERMINATE",
            "stage_error": "ADAPTER_UNAVAILABLE",
        }
        return unavailable, unavailable

    @staticmethod
    def _call_safely_with_raw(
        port: object, names: tuple[str, ...], argument: object
    ) -> tuple[Mapping[str, object], object]:
        try:
            return CodexParityJourneyPort._call_with_raw(port, names, argument)
        except Exception:
            unavailable = {"state": "FAILED", "stage_error": "ADAPTER_UNAVAILABLE"}
            return unavailable, unavailable

    def _call_safely(
        self, port: object, names: tuple[str, ...], argument: object
    ) -> Mapping[str, object]:
        try:
            return self._call(port, names, argument)
        except Exception:
            return {"state": "FAILED", "stage_error": "ADAPTER_UNAVAILABLE"}

    @staticmethod
    def _error(receipt: Mapping[str, object] | None) -> str | None:
        return (
            str(receipt["stage_error"])
            if receipt and receipt.get("stage_error")
            else None
        )

    @staticmethod
    def _receipt_state(receipt: Mapping[str, object] | None) -> str:
        state = (
            str(receipt.get("state", "INDETERMINATE")).upper()
            if receipt
            else "INDETERMINATE"
        )
        return (
            state
            if state in {"SUCCEEDED", "REFUSED", "INDETERMINATE", "FAILED"}
            else "INDETERMINATE"
        )

    @staticmethod
    def _is_success(receipt: Mapping[str, object] | None) -> bool:
        return (
            CodexParityJourneyPort._receipt_state(receipt) == "SUCCEEDED"
            and CodexParityJourneyPort._error(receipt) is None
        )

    @staticmethod
    def _receipt_error(receipt: Mapping[str, object] | None) -> str | None:
        if CodexParityJourneyPort._is_success(receipt):
            return None
        if error := CodexParityJourneyPort._error(receipt):
            return error
        return "ADAPTER_UNAVAILABLE"

    @staticmethod
    def _evidence(request: Mapping[str, object]) -> PublicEvidence:
        value = CodexParityJourneyPort._mapping(request["expected_evidence"])
        state = str(value["kind"])
        return PublicEvidence(
            state,
            state == "PROVED",
            str(value["policy_id"]) if value.get("policy_id") else None,
            str(value["reason"]) if value.get("reason") else None,
            str(value["remediation"]) if value.get("remediation") else None,
        )

    @staticmethod
    def _non_success(
        error: str,
        detail: str = "",
        receipt_state: str | None = None,
        *,
        retry_owner: str | None = None,
    ) -> ParityJourneyResult:
        outcome = (
            JourneyOutcome.REFUSED
            if error in _REFUSED
            else JourneyOutcome.INDETERMINATE
            if error in _INDETERMINATE
            else JourneyOutcome.FAILED
        )
        state = receipt_state or (
            "REFUSED"
            if outcome is JourneyOutcome.REFUSED
            else "INDETERMINATE"
            if outcome is JourneyOutcome.INDETERMINATE
            else "FAILED"
        )
        try:
            stage_error = JourneyStageError(error)
        except ValueError:
            stage_error = JourneyStageError.ADAPTER_UNAVAILABLE
        return ParityJourneyResult(
            outcome,
            stage_error,
            state,
            JourneyDiagnostic(
                f"{error}: {detail or 'journey stage did not satisfy its closed contract'}",
                "the paired parity claim lacks a required closed receipt",
                "repair the named prerequisite without substituting subject, candidate, target, or evidence, then retry.",
            ),
            retry_owner=retry_owner,
        )


__all__ = ["CodexParityComposition", "CodexParityJourneyPort", "ParityJourneyResult"]
