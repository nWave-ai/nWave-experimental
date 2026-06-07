"""des.cli.inject_seam -- the SeamInjectionPort CLI composition root (GAP-2).

The driving port of the per-language seam-injection adapter. Invoked as a
subprocess (``--scaffold <manifest> --out <path>``) it reads ``NWAVE_PERTURB``
from the environment, perturbs the named seam declared in the
``nwave.seam_manifest.v1`` scaffold manifest, and emits a small JSON envelope
reporting which locator the seam resolves to AFTER the call (and whether it
abstained):

    { "outcome": "perturbed" | "abstain",
      "resolved_impl": <opaque locator> | null,
      "reason": "no-nameable-seam" | null }

The perturbation is a bounded-change factory-lookup-by-name (NO monkeypatch):
the only effect is which locator the named seam resolves to. A nameable seam ->
PERTURBED, the seam now resolves to its ``fault`` locator. A seam name the
manifest does not declare -> fail-safe ABSTAIN(no-nameable-seam), the real
dependency left untouched. The business logic lives in
``des.domain.seam_injection``; this module only parses argv, reads the manifest +
the ``NWAVE_PERTURB`` selector, and serialises the port's result.

LANGUAGE_BOUND adapter (catalog #25): the ``real`` / ``fault`` locator
interpretation is Python-specific. The neutral manifest declaration + the
``NWAVE_PERTURB`` channel are language-neutral; the target-blind verdict CORE
never imports this module.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from des.domain.seam_injection import (
    PERTURB_ENV,
    InjectionResult,
    manifest_from_payload,
    perturb,
)


def main(argv: list[str] | None = None) -> int:
    """Perturb the named seam through the port and emit the result JSON."""
    args = _parse_args(argv)
    payload = json.loads(args.scaffold.read_text(encoding="utf-8"))
    manifest = manifest_from_payload(payload)
    selector = os.environ.get(PERTURB_ENV)
    seam_id = selector if selector is not None else ""
    result = perturb(seam_id, manifest, selector)
    _write_envelope(args.out, _envelope(result))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the ``--scaffold --out`` argv contract."""
    parser = argparse.ArgumentParser(prog="inject-seam")
    parser.add_argument("--scaffold", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def _envelope(result: InjectionResult) -> dict[str, object]:
    """Serialise the port-exposed result into the emitted JSON envelope."""
    return {
        "outcome": result.outcome.value,
        "resolved_impl": result.resolved_impl,
        "reason": result.reason.value if result.reason is not None else None,
    }


def _write_envelope(out: Path, envelope: dict[str, object]) -> None:
    """Write the emitted envelope as JSON to ``out``."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))
