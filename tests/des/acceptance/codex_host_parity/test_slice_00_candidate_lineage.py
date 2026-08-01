"""Active-RED public-journey checks for immutable assembled candidate lineage."""

from __future__ import annotations

import pytest

from .composition import CodexParityJourneyComposition, diagnostic_field, field
from .port_witnesses import FivePortWitnesses
from .test_slice_00_shared_port_contracts import _request


@pytest.mark.acceptance
@pytest.mark.negative_at
@pytest.mark.parametrize(
    "origin",
    ["SOURCE_TREE", "DEVELOPER_HOME", "GLOBAL_INSTALL"],
    ids=["source-tree-pre-effect", "developer-home-pre-effect", "global-install-pre-effect"],
)
def test_slice_00_refuses_ambient_candidate_origin_without_reading_or_substituting_it(
    origin: str,
) -> None:
    """The composed journey admits only its assembled distribution and isolated install."""
    # covers: R-S00-12
    ports = FivePortWitnesses()
    request = _request()
    assembled_candidate = request["assembled_candidate"]
    assert isinstance(assembled_candidate, dict)
    assembled_candidate["origin"] = origin

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "REFUSED", (
        "WHAT: an ambient source, home, or global installation satisfied candidate lineage. "
        "WHY: ambient bytes can borrow undeclared behavior from the developer machine. "
        "HOW: refuse the origin before deployment or probe and require the receipt-scoped isolated install."
    )
    assert field(result, "stage_error") == "ORIGIN_FORBIDDEN"
    assert origin.lower().replace("_", "-") in diagnostic_field(result, "what").lower()
    assert ports.trace.events == []


@pytest.mark.acceptance
def test_slice_00_keeps_the_candidate_identity_from_assembled_material_to_probe_attestation() -> (
    None
):
    """A successful public result exposes one unchanged CandidateId across the journey."""
    # covers: R-S00-13
    ports = FivePortWitnesses()
    request = _request()

    result = CodexParityJourneyComposition().run(
        request, external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "COMPLETED"
    candidate_id = field(result, "candidate_id")
    assert candidate_id == "febc8331fdccf9913bfbcddece8df239a2af85dc353be1080dcd27d1f1ee1eac", (
        "WHAT: the public journey did not expose the canonical builder-minted identity. "
        "WHY: a caller-supplied label cannot substitute for the content identity of the "
        "distribution, public manifest and build recipe. "
        "HOW: mint once from canonical build inputs and carry those exact bytes forward."
    )
    assert candidate_id == request["subject"]["candidate_id"]  # type: ignore[index]
    assert candidate_id == field(field(result, "deployment_receipt"), "candidate_id"), (
        "WHAT: deployment changed the candidate identity. "
        "WHY: evidence from different bytes must never be combined. "
        "HOW: carry the builder-minted CandidateId unchanged through deployment."
    )
    assert candidate_id == field(field(result, "attestation"), "candidate_id"), (
        "WHAT: the host attestation lost candidate lineage. "
        "WHY: a real-host observation proves only the bytes it consumed. "
        "HOW: bind the same CandidateId to every paired observation and attestation."
    )
    assert ports.trace.events[0] == "digest.verify"
    assert len(ports.digest_calls) >= 4, (
        "WHAT: candidate lineage was accepted after a single build-time digest. "
        "WHY: deployment and probe can consume bytes different from the assembled wheel. "
        "HOW: use the real CandidateLineageVerifier to re-digest assembled material, "
        "deployment material, isolated install, and probe-consumed install."
    )


@pytest.mark.acceptance
@pytest.mark.negative_at
def test_slice_00_refuses_a_candidate_identity_that_changes_on_any_lineage_redigest() -> (
    None
):
    """A later consumed-byte mismatch is a typed FAILED lineage result, never completion."""
    # covers: R-S00-13
    ports = FivePortWitnesses(
        digest_sequence=(
            "distribution-1",
            "distribution-1",
            "isolated-1",
            "tampered-probe-install",
        )
    )

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") == "FAILED"
    assert field(result, "stage_error") == "DIGEST_MISMATCH"
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert "ledger.append" not in ports.trace.events


@pytest.mark.acceptance
@pytest.mark.negative_at
@pytest.mark.parametrize(
    "stage_error",
    [
        "MATERIAL_MISSING",
        "MATERIAL_UNREADABLE",
        "DIGEST_UNSTABLE",
        "DIGEST_MISMATCH",
    ],
)
def test_slice_00_lineage_failure_from_digest_port_never_reaches_mutation(
    stage_error: str,
) -> None:
    """The root verifies assembled bytes through the digest port before effects."""
    ports = FivePortWitnesses(digest_failure=stage_error)

    result = CodexParityJourneyComposition().run(
        _request(), external_ports=ports.external_ports()
    )

    assert field(result, "outcome") != "COMPLETED", (
        "WHAT: missing, unreadable, unstable, or mismatched material completed. "
        "WHY: candidate identity is valid only for repeatably digested assembled bytes. "
        "HOW: preserve the digest-port failure before lease, deployment, execution, or ledger work."
    )
    assert field(result, "stage_error") == stage_error
    assert all(diagnostic_field(result, name) for name in ("what", "why", "how"))
    assert ports.trace.events == ["digest.verify"]
