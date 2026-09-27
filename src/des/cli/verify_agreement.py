"""Execute one declared agreement and report whether its consumer accepts it."""

# The public driving port of the executable-agreement crossing, and this
# slice's WHOLE public surface: one registered subcommand, added as a single
# row to `des.cli.__main__._REGISTRY`. No second surface advertises it.
#
# The module docstring above is deliberately ONE line: `scripts/docgen.py`'s
# `_command_catalog_body` renders this command's catalog row from it, so a
# multi-paragraph docstring here would land in a generated document. The WHY of
# the crossing itself lives with the code that performs it
# (`des.application.agreement_crossing`) rather than being duplicated here.
#
# This module offers no size, tier or profile option: the registry-wide guard
# `test_no_public_command_offers_a_size_on_its_own_surface` derives its corpus
# from `_REGISTRY`, and a public command that lets an operator dial its own
# scope is exactly what that guard forbids. It likewise imports neither
# `DeliveryContinuationRunner` nor `des.application.delivery_continuation`,
# which the two registry-wide unit guards forbid.

from __future__ import annotations

import argparse
from pathlib import Path

from des.application.agreement_crossing import cross_agreement
from des.cli._emit_json import emit_json_line


def main(argv: list[str] | None = None) -> int:
    """Cross one declared agreement; return 0 crossed, 1 refused, 2 indeterminate.

    Emits exactly one single-line JSON object on stdout (the machine surface)
    beside one human line naming the same agreement, so the two halves of the
    terminal cannot drift into disagreeing about what happened.
    """
    args = _parse_args(argv)
    outcome = cross_agreement(Path(args.repo_root), args.declaration)
    emit_json_line(outcome.payload)
    print(outcome.human)
    return outcome.exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des verify-agreement",
        description=(
            "Execute a declared producer, carry its artifact to the declared "
            "consumer, and report whether that consumer accepts it."
        ),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="the repository the declaration and both parties are resolved in",
    )
    parser.add_argument(
        "--declaration",
        required=True,
        metavar="REPOSITORY_RELATIVE_JSON",
        help="repository-relative path of the agreement declaration to execute",
    )
    return parser.parse_args(argv)
