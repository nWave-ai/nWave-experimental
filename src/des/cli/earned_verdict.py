"""des.cli.earned_verdict -- the ``earned-verdict`` CLI composition root.

The driving port of the earned-verdict gate (ADR-042, OSS hook tier). The
``main`` entry point is invoked as a subprocess with two
``nwave.test_result.v1`` JSON files (baseline + perturbed) and the opaque
``--seam-id`` / ``--at-id`` the verdict is being asked about. It reads the two
RUN envelopes, calls the
target-blind CORE (``des.domain.earned_verdict.compute_verdict``), and writes
the emitted ``nwave.earned_verdict.v1`` JSON to ``--out``.

Hexagonal: a thin argparse driving adapter over the pure CORE. ALL business
logic -- the deterministic verdict rule -- lives in the CORE. This module only
transports envelopes across the process boundary; it never re-computes the
verdict (no shadow oracle) and never branches on the runner.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.domain.earned_verdict import (
    EarnedVerdict,
    compute_verdict,
    earned_verdict_envelope,
    test_run_from_envelope,
)


def main(argv: list[str] | None = None) -> int:
    """Compute one earned verdict over two RUN envelopes. Returns an exit code."""
    args = _parse_args(argv)
    _write_verdict(args.out, _compute_from_files(args))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--baseline --perturbed --seam-id --at-id --out`` argv contract."""
    parser = argparse.ArgumentParser(prog="earned-verdict")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--perturbed", required=True, type=Path)
    parser.add_argument("--seam-id", required=True)
    parser.add_argument("--at-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def _compute_from_files(args: argparse.Namespace) -> EarnedVerdict:
    """Read the two RUN envelopes and rule the verdict through the CORE."""
    return compute_verdict(
        test_run_from_envelope(_read_json(args.baseline)),
        test_run_from_envelope(_read_json(args.perturbed)),
        seam_id=args.seam_id,
        at_id=args.at_id,
    )


def _read_json(path: Path) -> dict[str, object]:
    """Read and parse a JSON envelope file."""
    parsed: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _write_verdict(out: Path, verdict: EarnedVerdict) -> None:
    """Write the emitted ``nwave.earned_verdict.v1`` JSON to ``out``."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(earned_verdict_envelope(verdict), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))
