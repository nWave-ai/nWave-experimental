"""DEVOPS review CONSUMER veto gate -- ``des verify-devops-review`` (slice-02).

The DEVOPS gate-OUT CONSUMER veto, wired into the DEVOPS gate-out stack
(``nWave/waves/devops.yaml``) so a DEVOPS return is REFUSED unless an
artefact-current approved verdict exists.

THIN WRAPPER -- zero correctness logic of its own. The read-seal-decide-project
sequence is the shared ``_wave_review_cli.verify_main``, and the decision inside
it is ``ReviewVerdictGate.evaluate``; this module is the DEVOPS spec plus its
ledger reader.
"""

from __future__ import annotations

from des.adapters.driven.logging.devops_review_ledger_reader import (
    DevopsReviewLedgerReader,
)
from des.cli._wave_review_cli import verify_main
from des.domain.wave_review_spec import DEVOPS_REVIEW_SPEC


def main(argv: list[str] | None = None) -> int:
    """Verify the DEVOPS platform-architect-review consumer veto from the CLI."""
    return verify_main(DEVOPS_REVIEW_SPEC, DevopsReviewLedgerReader(), argv)


if __name__ == "__main__":
    raise SystemExit(main())
