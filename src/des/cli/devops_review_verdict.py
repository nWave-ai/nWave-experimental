"""DEVOPS review verdict PRODUCER -- ``des record-devops-review`` (slice-02).

After the platform-architect-reviewer judges the DEVOPS artefact, this producer
RECORDS the outcome as a ``DevopsReviewVerdict`` record on the per-feature
AT-completion ledger. The DEVOPS gate-OUT consumer (``des
verify-devops-review``) reads it back -- the agent NEVER hands the gate a
verdict, it only triggers the RECORDING (§22.7).

The recording itself is the shared ``_wave_review_cli.producer_main``; this
module is the DEVOPS spec bound to it.
"""

from __future__ import annotations

from des.cli._wave_review_cli import producer_main
from des.domain.wave_review_spec import DEVOPS_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Record a DEVOPS review verdict from the command line."""
    return producer_main(DEVOPS_REVIEW_SPEC, argv)


if __name__ == "__main__":
    raise SystemExit(main())
