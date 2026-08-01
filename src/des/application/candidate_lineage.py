"""Candidate byte-lineage verifier shared by build, deployment and probes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.codex_parity import (
    CandidateBuildReceipt,
    CandidateDeploymentReceipt,
    CandidateInputs,
    CandidateLocator,
    CandidateOrigin,
    CandidateProbeReceipt,
    Digest,
    ReceiptState,
    WhatWhyHow,
    mint_candidate_id,
)


if TYPE_CHECKING:
    from des.ports.driven_ports.candidate_material_digest_port import (
        CandidateMaterialDigestPort,
    )


class CandidateLineageVerifier:
    def __init__(self, digests: CandidateMaterialDigestPort) -> None:
        self._digests = digests

    def record_build(
        self, inputs: CandidateInputs, artifact: CandidateLocator
    ) -> CandidateBuildReceipt:
        if artifact.origin is not CandidateOrigin.ASSEMBLED_DISTRIBUTION:
            return CandidateBuildReceipt(
                state=ReceiptState.REFUSED,
                candidate_id=None,
                candidate_inputs=inputs,
                artifact_digest=None,
                artifact=artifact,
                diagnostic=_diagnostic(
                    "build receipt source is not an assembled distribution",
                    "source paths and ambient installations are not candidate bytes",
                    "supply the exact built distribution artifact",
                ),
            )
        observed = self._digests.digest(artifact)
        if observed.state is not ReceiptState.SUCCEEDED or observed.digest is None:
            return CandidateBuildReceipt(
                state=_observation_state(observed.state, observed.digest),
                candidate_id=None,
                candidate_inputs=inputs,
                artifact_digest=observed.digest,
                artifact=artifact,
                diagnostic=observed.diagnostic or _unreadable("built artifact"),
            )
        if observed.digest != inputs.distribution_digest:
            return CandidateBuildReceipt(
                state=ReceiptState.FAILED,
                candidate_id=None,
                candidate_inputs=inputs,
                artifact_digest=observed.digest,
                artifact=artifact,
                diagnostic=_mismatch("built artifact"),
            )
        return CandidateBuildReceipt(
            state=ReceiptState.SUCCEEDED,
            candidate_id=mint_candidate_id(inputs),
            candidate_inputs=inputs,
            artifact_digest=observed.digest,
            artifact=artifact,
        )

    def verify_deployment(
        self,
        build: CandidateBuildReceipt,
        installed_tree: CandidateLocator,
    ) -> CandidateDeploymentReceipt:
        if (
            build.state is not ReceiptState.SUCCEEDED
            or build.candidate_id is None
            or build.candidate_inputs is None
            or build.artifact_digest is None
        ):
            return CandidateDeploymentReceipt(
                ReceiptState.REFUSED,
                build.candidate_id,
                None,
                None,
                installed_tree,
                _diagnostic(
                    "deployment lacks a successful build receipt",
                    "candidate identity has not been established",
                    "repair and re-record the assembled build first",
                ),
            )
        expected_id = mint_candidate_id(build.candidate_inputs)
        if (
            build.candidate_id != expected_id
            or build.artifact_digest != build.candidate_inputs.distribution_digest
        ):
            return CandidateDeploymentReceipt(
                ReceiptState.REFUSED,
                build.candidate_id,
                None,
                None,
                installed_tree,
                _diagnostic(
                    "build receipt candidate identity is not derivable",
                    "the receipt fields do not reproduce the sealed candidate subject",
                    "use the receipt returned by record_build without reconstruction",
                ),
            )
        artifact_observation = self._digests.digest(build.artifact)
        if (
            artifact_observation.state is not ReceiptState.SUCCEEDED
            or artifact_observation.digest is None
        ):
            return CandidateDeploymentReceipt(
                _observation_state(
                    artifact_observation.state, artifact_observation.digest
                ),
                build.candidate_id,
                artifact_observation.digest,
                None,
                installed_tree,
                artifact_observation.diagnostic or _unreadable("deployment artifact"),
            )
        if artifact_observation.digest != build.artifact_digest:
            return CandidateDeploymentReceipt(
                ReceiptState.FAILED,
                build.candidate_id,
                artifact_observation.digest,
                None,
                installed_tree,
                _mismatch("deployment artifact"),
            )
        if installed_tree.origin is not CandidateOrigin.ISOLATED_INSTALL:
            return CandidateDeploymentReceipt(
                ReceiptState.REFUSED,
                build.candidate_id,
                artifact_observation.digest,
                None,
                installed_tree,
                _ambient_fallback(installed_tree.origin),
            )
        tree_observation = self._digests.digest(installed_tree)
        if (
            tree_observation.state is not ReceiptState.SUCCEEDED
            or tree_observation.digest is None
        ):
            return CandidateDeploymentReceipt(
                _observation_state(tree_observation.state, tree_observation.digest),
                build.candidate_id,
                artifact_observation.digest,
                tree_observation.digest,
                installed_tree,
                tree_observation.diagnostic or _unreadable("installed tree"),
            )
        return CandidateDeploymentReceipt(
            ReceiptState.SUCCEEDED,
            build.candidate_id,
            artifact_observation.digest,
            tree_observation.digest,
            installed_tree,
        )

    def verify_probe(
        self,
        deployment: CandidateDeploymentReceipt,
        observed_binary_digest: Digest,
    ) -> CandidateProbeReceipt:
        origin = deployment.isolated_prefix.origin
        if (
            deployment.state is not ReceiptState.SUCCEEDED
            or deployment.candidate_id is None
            or deployment.installed_tree_digest is None
        ):
            return CandidateProbeReceipt(
                ReceiptState.REFUSED,
                deployment.candidate_id,
                None,
                None,
                origin,
                _diagnostic(
                    "probe lacks a successful deployment receipt",
                    "the isolated installed candidate is not established",
                    "repair and verify deployment before probing",
                ),
            )
        if origin is not CandidateOrigin.ISOLATED_INSTALL:
            return CandidateProbeReceipt(
                ReceiptState.REFUSED,
                deployment.candidate_id,
                None,
                None,
                origin,
                _ambient_fallback(origin),
            )
        observed = self._digests.digest(deployment.isolated_prefix)
        if observed.state is not ReceiptState.SUCCEEDED or observed.digest is None:
            return CandidateProbeReceipt(
                _observation_state(observed.state, observed.digest),
                deployment.candidate_id,
                observed.digest,
                None,
                origin,
                observed.diagnostic or _unreadable("probe installed tree"),
            )
        if observed.digest != deployment.installed_tree_digest:
            return CandidateProbeReceipt(
                ReceiptState.FAILED,
                deployment.candidate_id,
                observed.digest,
                None,
                origin,
                _mismatch("probe installed tree"),
            )
        return CandidateProbeReceipt(
            ReceiptState.SUCCEEDED,
            deployment.candidate_id,
            observed.digest,
            observed_binary_digest,
            origin,
        )


def _diagnostic(what: str, why: str, how: str) -> WhatWhyHow:
    return WhatWhyHow(what=what, why=why, how=how)


def _observation_state(state: ReceiptState, digest: Digest | None) -> ReceiptState:
    if state is ReceiptState.SUCCEEDED and digest is None:
        return ReceiptState.INDETERMINATE
    return state


def _mismatch(material: str) -> WhatWhyHow:
    return _diagnostic(
        f"{material} digest changed",
        "the consumed bytes differ from the immutable candidate receipt",
        "rebuild once and pass that exact candidate through every downstream stage",
    )


def _unreadable(material: str) -> WhatWhyHow:
    return _diagnostic(
        f"{material} could not be read",
        "lineage cannot distinguish absence from an unavailable observation",
        "restore readable isolated candidate bytes and repeat verification",
    )


def _ambient_fallback(origin: CandidateOrigin) -> WhatWhyHow:
    return _diagnostic(
        f"candidate material came from forbidden origin {origin.value}",
        "source, developer HOME and global installs can borrow undeclared behavior",
        "install and probe only the receipt-scoped candidate in an isolated prefix",
    )


__all__ = ["CandidateLineageVerifier"]
