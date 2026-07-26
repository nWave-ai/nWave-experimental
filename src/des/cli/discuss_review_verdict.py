"""DISCUSS PO-review verdict PRODUCER -- ``des record-discuss-review`` (slice-07b).

After the product-owner reviewer judges the DISCUSS artefact, this producer
RECORDS the outcome as a ``DiscussReviewVerdict`` record on the per-feature
AT-completion ledger. The DISCUSS gate-OUT consumer reads it back -- the agent
NEVER hands the gate a verdict, it only triggers the RECORDING (§22.7).

O-4 (intentional + isolated divergence from ``at_review_verdict``): this
producer writes a record for BOTH ``approved`` AND ``needs-revision``.
``at_review_verdict.record_review_outcome`` (which skips NEEDS_REVISION for its
loop-back) is NOT affected.

The recording itself is the shared ``_wave_review_cli.producer_main``; this
module is the DISCUSS spec bound to it.
"""

from __future__ import annotations

from des.cli._wave_review_cli import producer_main
from des.domain.wave_review_spec import DISCUSS_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Record a DISCUSS PO-review verdict from the command line."""
    return producer_main(DISCUSS_REVIEW_SPEC, argv)


if __name__ == "__main__":
    raise SystemExit(main())
