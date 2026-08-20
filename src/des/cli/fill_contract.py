"""Fill exactly one semantic field of an existing DeliveryContract skeleton.

``des fill-contract`` is the ONLY route to a filled DeliveryContract: ATD
passes one value per call (``--target``, ``--field`` from a closed set, the
value on stdin between quoted heredoc markers); this CLI is the sole
writer of the contract file (single-writer discipline, mirroring ``des
compile-contract``'s own). A mechanical field (``declared-imports``,
``decision``, ``candidate``, ``verification-scope``, ``obligations``, ...)
has no ``--field`` choice naming it at all -- an attempt to fill one is an
argparse error at authoring time, never a runtime refusal to detect after
the fact. See ``des.application.fill_contract`` module docstring for the
full rationale (Ale's construction-over-file correction, 2026-08-20).
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

from des.application.fill_contract import (
    ALL_FIELDS,
    Blocked,
    FillContractInputs,
    Filled,
    fill_contract_field,
)
from des.application.ordinary_request import contract_locator_for
from des.domain.contract_placeholder_resolver import find_unfilled_placeholders


_EXIT_BLOCKED = 2
_DELIVERY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing -- mirrors ``des compile-contract``'s own.
    An unrecognized ``--field`` value (a mechanical field, a typo) is one
    of these: a WHAT/WHY/HOW line, at authoring time, never a written
    byte."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed, and only the compiler's own closed "
            "semantic-field vocabulary is a valid --field value. "
            "HOW: pass every required --flag with a value from its own "
            "closed vocabulary; see `des fill-contract --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des fill-contract",
        description=(
            "Fill exactly one semantic field of a compiled DeliveryContract "
            "skeleton, or report which fields remain unfilled. The value "
            "for --field arrives on stdin, between quoted heredoc markers."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument(
        "--target",
        default=None,
        help="Required for a target-level field, forbidden for a contract-level one.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--field",
        choices=sorted(ALL_FIELDS),
        help="The one semantic field this call fills; its value arrives on stdin.",
    )
    mode.add_argument(
        "--status",
        action="store_true",
        help="Report which fields remain unfilled without writing anything.",
    )
    return parser


def _report_status(contract: dict) -> None:
    remaining = find_unfilled_placeholders(contract)
    if remaining:
        print("CONTRACT-FILL-STATUS: INCOMPLETE")
        for field_path in remaining:
            print(f"UNFILLED: {field_path}")
    else:
        print("CONTRACT-FILL-STATUS: COMPLETE")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    repo_root: Path = args.repo_root
    try:
        root_stat = repo_root.lstat()
    except OSError as exc:
        return _blocked(
            what=f"--repo-root cannot be read ({exc})",
            why="contract filling requires a real repository root",
            how="pass an existing absolute repository directory",
        )
    if (
        not repo_root.is_absolute()
        or not stat.S_ISDIR(root_stat.st_mode)
        or repo_root.is_symlink()
    ):
        return _blocked(
            what="--repo-root is not an absolute real directory",
            why="contract identity must not depend on the invoking cwd, and "
            "a symlink root makes it ambiguous",
            how="pass the absolute physical repository directory",
        )

    if not _DELIVERY_ID_RE.match(args.delivery_id):
        return _blocked(
            what=f"--delivery-id {args.delivery_id!r} is not schema-shaped",
            why="delivery-id must match thin-delivery-contract.schema.json's "
            "$defs/id pattern",
            how="pass the exact lowercase-kebab id `des compile-contract` already used",
        )

    contract_locator = contract_locator_for(args.delivery_id)
    destination = repo_root / contract_locator
    try:
        file_stat = destination.lstat()
    except OSError as exc:
        return _blocked(
            what=f"no contract exists at {contract_locator} ({exc})",
            why="fill-contract mutates an existing compiled skeleton, never "
            "invents one",
            how="run `des compile-contract` first",
        )
    if not stat.S_ISREG(file_stat.st_mode):
        return _blocked(
            what=f"the contract path {contract_locator} is not a regular file",
            why="a symlink, directory or fifo is not a stable contract identity",
            how="pass a locator resolving to a regular JSON file",
        )
    try:
        contract = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _blocked(
            what=f"the contract at {contract_locator} cannot be read as JSON ({exc})",
            why="fill-contract requires a well-formed JSON object to mutate",
            how="fix the contract's encoding/JSON and rerun",
        )

    if args.status:
        _report_status(contract)
        return 0

    value = sys.stdin.read()
    result = fill_contract_field(
        FillContractInputs(
            contract=contract, field=args.field, value=value, target=args.target
        )
    )
    if isinstance(result, Blocked):
        return _blocked(what=result.what, why=result.why, how=result.how)
    assert isinstance(result, Filled)

    destination.write_text(
        json.dumps(result.contract, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    target_suffix = f" ({args.target})" if args.target else ""
    print(f"DELIVERY-CONTRACT-FILLED: {args.field}{target_suffix}")
    _report_status(result.contract)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
