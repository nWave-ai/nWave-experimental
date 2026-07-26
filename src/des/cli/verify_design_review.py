"""DESIGN review CONSUMER veto gate -- ``des verify-design-review`` (slice-01).

The DESIGN gate-OUT CONSUMER veto, wired into the DESIGN gate-out stack
(``nWave/waves/design.yaml``) so a DESIGN return is REFUSED unless an
artefact-current approved verdict exists.

THIN WRAPPER -- zero correctness logic of its own. The read-seal-decide-project
sequence is the shared ``_wave_review_cli.verify_main``, and the decision inside
it is ``ReviewVerdictGate.evaluate``; this module is the DESIGN spec plus its
ledger reader.
"""

from __future__ import annotations

from des.adapters.driven.logging.design_review_ledger_reader import (
    DesignReviewLedgerReader,
)
from des.cli._wave_review_cli import verify_main
from des.domain.wave_review_spec import DESIGN_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Verify the DESIGN architect-review consumer veto from the command line."""
    return verify_main(DESIGN_REVIEW_SPEC, DesignReviewLedgerReader(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
