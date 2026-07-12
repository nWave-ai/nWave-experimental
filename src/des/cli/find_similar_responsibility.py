"""des find-similar-responsibility -- the observable CLI over the additive
``query.similar-responsibility`` ``CodeFactPort`` capability (WS-9b, the
reuse-first keystone, ``codefact-similar-responsibility`` feature slice-01).

Given a proposed NEW symbol name and a scope directory, shows an operator
(and a crafter's Phase-A step 3.5 reuse-before-create check) the RANKED
existing module-level ``def``/``class`` symbols whose structural fingerprint
(name-token Jaccard + parameter arity) overlaps the proposed name -- before
the operator writes a parallel implementation.

Advisory, GDP-6-safe: this command ALWAYS exits 0 -- it informs, it never
blocks. The signal distinguishing "I looked and found nothing" from "I could
not look" is the ``reason_code`` field on the JSON payload, mirroring the
LOCKED ``CodeFactResult.reason_code`` vocabulary (``des.ports.code_fact_port
.ReasonCode``): ``"live-non-callable"`` (a real, parseable scope was
searched) vs ``"absent"`` (the scope could not be searched at all --
nonexistent path / empty directory / nothing parseable). An ``"absent"``
reason_code always reports an empty candidate list -- but never the reverse
confusion (a genuine empty search must never read as ``"absent"``).

CLI contract:
    des find-similar-responsibility --name <symbol> --scope <path> [--format json]

stdout token (JSON):
    {candidates:[{symbol, file, line, overlap}], reason_code, detail,
     unparsed_count}

``unparsed_count`` (F-fix-find-similar-declares-unparseable-coverage) is the
coverage-gap signal: the count of candidate files under ``--scope`` the AST
adapter could not parse during the SAME ranking pass -- so an operator can
tell "searched everything and found nothing" apart from "searched what
parsed". A fully-parseable corpus reports zero and is otherwise unchanged.

Exit code is ALWAYS 0 (advisory, GDP-6 -- never blocks).

Thin shell: builds an ``AstAdapter`` scoped to ``--scope``, queries the
``query.similar-responsibility`` capability, and renders the ``CodeFactResult``
envelope as the CLI's JSON contract -- no parallel fingerprint logic here (the
adapter owns the structural computation).
"""

from __future__ import annotations

import argparse
import json
import sys

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.ports.code_fact_port import (
    CAPABILITY_SIMILAR_RESPONSIBILITY,
    CapabilityDescriptor,
    ReasonCode,
)


_ABSENT_DETAIL = (
    "the scope could not be searched (nonexistent path, empty directory, or "
    "nothing parseable) -- no similar-responsibility fact available"
)


def _detail_for(reason_code: str | None, candidate_count: int) -> str:
    """The self-explaining ``detail`` line for the JSON contract. Pure.

    ``absent`` always reports the fixed "could not look" explanation; a live
    search reports how many candidates were ranked (including zero -- a
    genuine "looked and found nothing" answer, distinct from ``absent``).
    """
    if reason_code == ReasonCode.ABSENT.value:
        return _ABSENT_DETAIL
    return f"{candidate_count} candidate(s) ranked above the overlap threshold"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="find-similar-responsibility",
        description=(
            "Show the ranked EXISTING module-level def/class symbols whose "
            "structural fingerprint (name-token Jaccard + arity) overlaps a "
            "proposed NEW symbol name -- advisory, never blocks."
        ),
    )
    parser.add_argument("--name", required=True, help="The proposed new symbol's name.")
    parser.add_argument(
        "--scope", required=True, help="Directory to search for existing symbols."
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only 'json' is supported).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Query ``query.similar-responsibility`` and print the JSON contract.

    ALWAYS returns 0 -- advisory (GDP-6), it informs and never blocks.
    """
    args = _build_parser().parse_args(argv)

    adapter = AstAdapter(root=args.scope)
    descriptor = CapabilityDescriptor(
        id=CAPABILITY_SIMILAR_RESPONSIBILITY,
        stability="stable",
        contract_version="1.0.0",
        io_schema="similar-responsibility.v1",
        providing_adapter="ast",
    )
    result = adapter.query(descriptor, {"name": args.name})
    payload = result.payload if isinstance(result.payload, dict) else {}
    candidates = payload.get("candidates", [])
    unparsed_count = payload.get("unparsed_count", 0)

    print(
        json.dumps(
            {
                "candidates": candidates,
                "reason_code": result.reason_code,
                "detail": _detail_for(result.reason_code, len(candidates)),
                "unparsed_count": unparsed_count,
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
