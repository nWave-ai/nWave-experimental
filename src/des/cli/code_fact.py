"""Public read-only CLI over the vendor-neutral ``CodeFactChain``.

The OSS baseline assumes no paid or external analyzer.  The chain degrades
from the bundled AST tier to the zero-dependency textual floor.  This module
adds no analysis logic and owns no state; it only parses a bounded request and
renders the resolved envelope + its bounded ``Resolution`` trace as JSON.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.ports.code_fact_port import (
    CAPABILITY_ADR_SECTION,
    CAPABILITY_ATOMS_IN_FILE,
    STABLE_CORE_CAPABILITY_IDS,
    Answered,
    CapabilityDescriptor,
)


_SUBJECT_FREE = frozenset({CAPABILITY_ATOMS_IN_FILE})

_UNRECOGNIZED_ARGUMENTS_MARKER = "unrecognized arguments"
_UNRECOGNIZED_ARGUMENTS_HOW = (
    " HOW: put `subject` BEFORE `--root`, e.g. `des code-fact "
    "query.callers-of SYMBOL --root ROOT` (or `--root ROOT query.callers-of "
    "SYMBOL`, --root first) -- a bare positional trailing an "
    "already-satisfied `--root` is unrecognized under this parser; "
    "`query.atoms-in-file` never takes a `subject` at all, pass the target "
    "through `--root` instead."
)


class _CodeFactArgumentParser(argparse.ArgumentParser):
    """Argparse keeps its own standard error text (so a caller or the
    build-time executable-example guard can still recognize the exact
    failure class by its fixed vocabulary) with one HOW line appended for
    the specific class root actually hit. Run 6 evidence: a bare
    "unrecognized arguments" message with no example sent root into 3
    failed retries of a mis-ordered `--root`/`subject` invocation, then a
    19-file source-Read fallback this CLI's own error message could have
    prevented outright."""

    def error(self, message: str) -> None:
        hint = (
            _UNRECOGNIZED_ARGUMENTS_HOW
            if _UNRECOGNIZED_ARGUMENTS_MARKER in message
            else ""
        )
        super().error(message + hint)


def _parser() -> argparse.ArgumentParser:
    parser = _CodeFactArgumentParser(
        prog="des code-fact",
        description=(
            "Query a bundled vendor-neutral code fact and emit its provider, "
            "confidence and payload as JSON."
        ),
    )
    parser.add_argument("capability", choices=sorted(STABLE_CORE_CAPABILITY_IDS))
    parser.add_argument(
        "subject",
        nargs="?",
        help="Symbol or prose anchor; omitted only for query.atoms-in-file.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Target tree (default: current working directory).",
    )
    return parser


def _request(capability: str, subject: str | None) -> dict[str, object]:
    if capability not in _SUBJECT_FREE and not subject:
        raise ValueError("subject is required for this capability")
    if capability == CAPABILITY_ADR_SECTION:
        return {"anchor": subject or ""}
    if capability == CAPABILITY_ATOMS_IN_FILE:
        return {}
    return {"symbol": subject or ""}


def main(argv: list[str] | None = None) -> int:
    """Resolve one stable code fact and print the honest result envelope."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        request = _request(args.capability, args.subject)
    except ValueError as error:
        parser.error(str(error))

    chain = CodeFactChain(root=Path(args.root))
    descriptor = CapabilityDescriptor(
        id=args.capability,
        stability="stable",
        contract_version="1.0.0",
        io_schema="code-fact.v1",
        providing_adapter="negotiated",
    )
    resolution = chain.resolve(descriptor, request)
    if not isinstance(resolution, Answered):
        # Stable-core invariant; kept honest if the registry drifts.
        parser.error(f"no provider covers stable capability {args.capability!r}")

    output = asdict(resolution.payload)
    output["trace"] = [asdict(entry) for entry in resolution.trace]
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
