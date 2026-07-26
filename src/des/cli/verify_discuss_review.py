"""DISCUSS PO-review CONSUMER veto gate -- ``des verify-discuss-review`` (OB-2).

The PO-review CONSUMER veto promoted to its own catalog ``gate_id`` so the
DISCUSS gate-OUT stack is the readable 2-row declared list
``[validate-feature-delta, verify-discuss-review]`` (OB-2).

THIN WRAPPER -- zero correctness logic of its own. The read-seal-decide-project
sequence is the shared ``_wave_review_cli.verify_main``, and the decision inside
it is ``ReviewVerdictGate.evaluate`` (which ``DiscussReviewGate.evaluate``
already delegated to); this module is the DISCUSS spec plus its ledger reader.
"""

from __future__ import annotations

from des.adapters.driven.logging.discuss_review_ledger_reader import (
    DiscussReviewLedgerReader,
)
from des.cli._wave_review_cli import verify_main
from des.domain.wave_review_spec import DISCUSS_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Verify the DISCUSS PO-review consumer veto from the command line."""
    return verify_main(DISCUSS_REVIEW_SPEC, DiscussReviewLedgerReader(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
