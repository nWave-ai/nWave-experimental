"""des CLI dispatcher — single entry point for the nWave runtime.

Implements DDD-1..DDD-11 of fix-des-single-entry-point-consolidation feature.

The dispatcher is a pure-function fan-out over the subcommand registry
(_REGISTRY below — the same SSOT mirrored in tests/des/acceptance/
single_entry_point/steps/domain_types.py:SUBCOMMAND_TABLE). Each row maps
the operator-visible kebab-case name to its importable module path. argparse
discovers subcommands from the registry; ``des --help`` advertises every
name without per-subcommand prose duplication (each module owns its own
help via per-subcommand ``des <sub> --help``).

Stdlib-only at import time (bundle-scan compliant per DDD-2). Subcommand
modules load via ``importlib.import_module`` only on dispatch — startup
cost stays constant regardless of registry size.

Exit-code passthrough is verbatim (DDD-6): whatever ``<sub>.main(argv[2:])``
returns becomes this process's exit code.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class _SubcommandRow:
    """One row of the dispatcher's subcommand registry."""

    name: str
    module_path: str
    function_name: str


# The subcommand registry — SSOT for the dispatcher. Mirrors
# tests/des/acceptance/single_entry_point/steps/domain_types.py SUBCOMMAND_TABLE
# (the executable test mirror). Filesystem-grounded against src/des/cli/*.py
# (excluding __init__.py and __main__.py) as of 2026-05-23.
_REGISTRY: tuple[_SubcommandRow, ...] = (
    _SubcommandRow("log-phase", "des.cli.log_phase", "main"),
    _SubcommandRow("init-log", "des.cli.init_log", "main"),
    _SubcommandRow("verify-integrity", "des.cli.verify_deliver_integrity", "main"),
    _SubcommandRow("roadmap", "des.cli.roadmap", "main"),
    _SubcommandRow("health-check", "des.cli.health_check", "main"),
    _SubcommandRow("verify-commit-trailers", "des.cli.verify_commit_trailers", "main"),
    _SubcommandRow(
        "verify-slice-commit",
        "des.cli.verify_slice_commit_completeness",
        "main",
    ),
    _SubcommandRow("walking-skeleton-gate", "des.cli.walking_skeleton_gate", "main"),
    _SubcommandRow(
        "walking-skeleton-done-gate",
        "des.cli.walking_skeleton_done_gate",
        "main",
    ),
    _SubcommandRow("carpaccio-slice-gate", "des.cli.carpaccio_slice_gate", "main"),
    _SubcommandRow("classify-features", "des.cli.classify_features", "main"),
    _SubcommandRow("convert-to-atdd-pure", "des.cli.convert_to_atdd_pure", "main"),
    _SubcommandRow("reverify-slice-commit", "des.cli.reverify_slice_commit", "main"),
    _SubcommandRow(
        "verify-environmental-e2e",
        "des.cli.verify_environmental_e2e",
        "main",
    ),
    _SubcommandRow("run-contract-gate", "des.cli.run_contract_gate", "main"),
    _SubcommandRow("commit-slice", "des.cli.commit_slice", "main"),
    _SubcommandRow("emit-feature-end", "des.cli.emit_feature_end", "main"),
    _SubcommandRow("feature-end", "des.cli.feature_end", "main"),
    _SubcommandRow(
        "check-slice-at-completeness",
        "des.cli.check_slice_at_completeness",
        "main",
    ),
    _SubcommandRow("doctor", "des.cli.doctor", "main"),
    _SubcommandRow(
        "verify-readiness-pre-dispatch",
        "des.cli.verify_readiness_pre_dispatch",
        "main",
    ),
    _SubcommandRow(
        "verify-slice-ledger-evidence",
        "des.cli.verify_slice_ledger_evidence",
        "main",
    ),
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per registry row.

    Subparsers are registered with ``add_help=False`` so per-subcommand
    ``--help`` flows to the underlying module's argparse instead of being
    intercepted here (DDD-5). The dispatcher's own ``--help`` lists every
    registered subcommand name (DDD-4).
    """
    parser = argparse.ArgumentParser(
        prog="des",
        description="nWave deterministic execution system — single CLI entry point.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for row in _REGISTRY:
        subparsers.add_parser(row.name, add_help=False, help=row.name)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatcher entry point — parse subcommand, delegate, passthrough exit.

    Parses the first positional argument as the subcommand name, resolves
    its registry row, lazily imports the module, and delegates the
    remaining ``argv`` to that module's ``main`` function. The subcommand's
    return value becomes this process's exit code unchanged (DDD-6).
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    parser = _build_parser()
    parsed, remaining = parser.parse_known_args(raw_argv)
    row = next(r for r in _REGISTRY if r.name == parsed.subcommand)
    module = importlib.import_module(row.module_path)
    subcommand_main = getattr(module, row.function_name)
    return subcommand_main(remaining)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
