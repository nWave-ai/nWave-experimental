"""DESIGN review verdict PRODUCER -- ``des record-design-review`` (slice-01).

After the solution-architect-reviewer judges the DESIGN artefact, this producer
RECORDS the outcome as a ``DesignReviewVerdict`` record on the per-feature
AT-completion ledger. The DESIGN gate-OUT consumer (``des
verify-design-review``) reads it back -- the agent NEVER hands the gate a
verdict, it only triggers the RECORDING (§22.7).

The recording itself is the shared ``_wave_review_cli.producer_main``; this
module is the DESIGN spec bound to it.
"""

from __future__ import annotations

from des.cli._wave_review_cli import producer_main
from des.domain.wave_review_spec import DESIGN_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Record a DESIGN review verdict from the command line."""
    return producer_main(DESIGN_REVIEW_SPEC, argv)


if __name__ == "__main__":
    raise SystemExit(main())
