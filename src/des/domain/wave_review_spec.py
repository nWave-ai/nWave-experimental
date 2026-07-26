"""The per-wave binding of the wave-parametric review-verdict gate.

``ReviewVerdictGate`` (``review_verdict_gate``) already holds the ONE verdict
decision shared by DISCUSS / DESIGN / DEVOPS. What stayed copied three times was
everything AROUND that decision: the record-family event name, the ledger
probe directory, the catalog ``gate_id``, the producer subcommand, and the
per-token recovery prose. Every one of those is the SAME sentence with the wave
and the reviewer's role substituted in -- an accident of writing, not a
requirement.

``WaveReviewSpec`` is that substitution made explicit. Three literals per wave
(the wave id + how the reviewer is named) generate the rest, so a fourth wave is
one spec, not a fourth copy of the reader + producer + consumer triple.

The two literals that genuinely differ per wave and CANNOT be derived:

* ``reviewer_role`` -- how the recovery prose names the review ("PO-review",
  "architect-review", "platform-architect-review"). It is the operator-facing
  HOW; naming the wrong reviewer sends the operator to the wrong agent.
* ``reviewer_title`` -- the agent role in ``--help`` ("product-owner",
  "solution-architect", "platform-architect").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaveReviewSpec:
    """What ONE wave contributes to the shared review-verdict gate.

    INVARIANT: nothing here decides a verdict. The PASS / VETOED /
    INDETERMINATE decision lives once in ``ReviewVerdictGate.evaluate``; this
    VO only names the record family the reader selects on and the prose the
    consumer projects. A spec can change what the operator READS, never what
    the gate DECIDES.
    """

    wave: str
    """Lowercase wave id -- ``discuss`` | ``design`` | ``devops``."""

    reviewer_role: str
    """How the recovery prose names the review (e.g. ``architect-review``)."""

    reviewer_title: str
    """The reviewing agent's role, for ``--help`` (e.g. ``solution-architect``)."""

    @property
    def wave_upper(self) -> str:
        """The wave as the recovery prose spells it (``DESIGN``)."""
        return self.wave.upper()

    @property
    def wave_camel(self) -> str:
        """The wave as the ledger event names spell it (``Design``)."""
        return self.wave.capitalize()

    @property
    def event(self) -> str:
        """The ledger record-family discriminant (``DesignReviewVerdict``)."""
        return f"{self.wave_camel}ReviewVerdict"

    @property
    def consumer_event(self) -> str:
        """The consumer veto's stdout event (``DesignReviewConsumerVeto``)."""
        return f"{self.wave_camel}ReviewConsumerVeto"

    @property
    def producer_event(self) -> str:
        """The producer's stdout event (``DesignReviewVerdictCLI``)."""
        return f"{self.wave_camel}ReviewVerdictCLI"

    @property
    def verify_gate_id(self) -> str:
        """The catalog gate id of the consumer veto (``verify-design-review``)."""
        return f"verify-{self.wave}-review"

    @property
    def producer_command(self) -> str:
        """The producer subcommand the recovery routes to (GDP-4)."""
        return f"record-{self.wave}-review"

    @property
    def probe_gate_dir(self) -> str:
        """The startup-probe scratch directory name (``design-gate``)."""
        return f"{self.wave}-gate"

    @property
    def vetoed_recovery(self) -> tuple[str, ...]:
        """The reviewer said NEEDS_REVISION -- how the operator clears the veto."""
        return (
            f"The {self.wave_upper} {self.reviewer_role} returned NEEDS_REVISION "
            "-- address the reviewer's findings in "
            "docs/feature/<id>/feature-delta.md, then record a fresh APPROVED "
            f"{self.reviewer_role} verdict whose artefact hash matches the "
            "updated feature-delta before retrying the return.",
            "If the verdict is stale (its sealed hash no longer matches the "
            f"current feature-delta), re-run the {self.reviewer_role} against "
            "the latest feature-delta so the artefact-currency seal is current.",
        )

    @property
    def indeterminate_recovery(self) -> tuple[str, ...]:
        """The mechanism could not run -- how the operator makes it able to (GDP-4)."""
        return (
            f"The {self.wave_upper} {self.reviewer_role} verdict mechanism could "
            "not run (no APPROVED verdict recorded for this feature, or the "
            "recorded verdict is stale / of an unknown schema) -- record a "
            f"current APPROVED {self.reviewer_role} verdict via "
            f"`des {self.producer_command}` whose artefact hash matches the "
            f"feature-delta, then retry the {self.wave} return.",
        )


# The three shipped waves. DISCUSS came first (slice-07b); DESIGN and DEVOPS
# were literal lifts of it (f-design-devops-review-gate slice-01 / slice-02).
DISCUSS_REVIEW_SPEC = WaveReviewSpec(
    wave="discuss",
    reviewer_role="PO-review",
    reviewer_title="product-owner",
)

DESIGN_REVIEW_SPEC = WaveReviewSpec(
    wave="design",
    reviewer_role="architect-review",
    reviewer_title="solution-architect",
)

DEVOPS_REVIEW_SPEC = WaveReviewSpec(
    wave="devops",
    reviewer_role="platform-architect-review",
    reviewer_title="platform-architect",
)
