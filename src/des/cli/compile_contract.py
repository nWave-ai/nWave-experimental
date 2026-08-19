"""Compile one DeliveryContract SKELETON from a DESIGN architecture brief.

``des compile-contract`` mechanically derives every fact a ``des dispatch``
validator already knows how to CHECK (target candidate/decision/declared-
imports, verification-scope commands, the acceptance locator by convention,
the schema-closed obligation vocabulary) by calling the same resolver in
GENERATION mode. What remains is written as the literal ``<ATD: fill>``
placeholder (``des.domain.contract_placeholder_resolver``) for ATD to
author -- never a guess. See ``des.application.compile_contract`` module
docstring for the full rationale (ADR-SSOT-002 Section 4/4b item 1).
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

from des.application.compile_contract import (
    Blocked,
    CompileContractInputs,
    Compiled,
    compile_delivery_contract,
)
from des.application.ordinary_request import (
    ARCH_HEADER_PREFIXES,
    BUDGET_TABLE,
    contract_locator_for,
    is_valid_arch_header_line,
)


_EXIT_BLOCKED = 2
_DELIVERY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing: one concise WHAT/WHY/HOW line on stderr,
    nonzero exit -- mirrors ``des prepare-ordinary-request``'s own parser."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed. "
            "HOW: pass every required --flag; see "
            "`des compile-contract --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des compile-contract",
        description=(
            "Compile one DeliveryContract SKELETON from a DESIGN architecture "
            "brief's own citations; leaves every semantic field as an "
            "explicit <ATD: fill> placeholder for the acceptance designer "
            "to author."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument(
        "--architecture-authority",
        required=True,
        help="The exact 'ARCHITECTURE-COVERED: <path>.md#<anchor>' line -- "
        "the SAME shape/value des prepare-ordinary-request already "
        "validates and ATD's own envelope carries.",
    )
    parser.add_argument(
        "--route",
        dest="delivery_route",
        default="RED_TO_GREEN",
        choices=("RED_TO_GREEN", "GREEN_TO_GREEN"),
    )
    parser.add_argument(
        "--paradigm",
        default="object_oriented",
        choices=("functional", "object_oriented"),
    )
    parser.add_argument("--examine", default="true", choices=("true", "false"))
    parser.add_argument(
        "--independent-review",
        default=None,
        choices=("true", "false"),
        help="The caller's own already-resolved Seeded value (ADR-SSOT-002 "
        "Section 4c) -- omit only for a standalone/manual run with no "
        "better source, which falls back to this compiler's own "
        "obligations-based proxy.",
    )
    parser.add_argument("--size", default="M", choices=("M", "L"))
    parser.add_argument("--budget-token-limit", type=int, default=None)
    parser.add_argument("--budget-wall-clock-minutes", type=int, default=None)
    return parser


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
            why="contract compilation requires a real repository root",
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
            how="pass a lowercase-kebab id starting with a letter or digit",
        )

    if not is_valid_arch_header_line(args.architecture_authority):
        return _blocked(
            what=(
                f"--architecture-authority {args.architecture_authority!r} "
                "is not a well-formed ARCHITECTURE-COVERED <path>.md#<anchor> "
                "line"
            ),
            why="the architecture authority is a citation, not free text -- "
            "the same shape des prepare-ordinary-request already requires",
            how="pass the architect's exact 'ARCHITECTURE-COVERED: "
            "<repo-relative-path>.md#<anchor>' line verbatim",
        )
    prefix = next(
        p for p in ARCH_HEADER_PREFIXES if args.architecture_authority.startswith(p)
    )
    reference = args.architecture_authority[len(prefix) :]
    brief_relative_path, _separator, _anchor = reference.partition("#")
    brief_path = repo_root / brief_relative_path
    try:
        brief_text = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _blocked(
            what=f"the architecture brief cannot be read at {brief_path} ({exc})",
            why="compile-contract derives every fact from the brief's own citations",
            how="pass an --architecture-authority path readable under --repo-root",
        )

    table_tokens, table_minutes = BUDGET_TABLE[args.size]
    budget_token_limit = (
        args.budget_token_limit if args.budget_token_limit is not None else table_tokens
    )
    budget_wall_clock_minutes = (
        args.budget_wall_clock_minutes
        if args.budget_wall_clock_minutes is not None
        else table_minutes
    )

    inputs = CompileContractInputs(
        repo_root=repo_root,
        delivery_id=args.delivery_id,
        brief_text=brief_text,
        delivery_route=args.delivery_route,
        paradigm=args.paradigm,
        examine=args.examine == "true",
        budget_token_limit=budget_token_limit,
        budget_wall_clock_minutes=budget_wall_clock_minutes,
        independent_review=(
            None
            if args.independent_review is None
            else args.independent_review == "true"
        ),
    )
    result = compile_delivery_contract(inputs)
    if isinstance(result, Blocked):
        return _blocked(what=result.what, why=result.why, how=result.how)
    assert isinstance(result, Compiled)

    contract_locator = contract_locator_for(args.delivery_id)
    destination = repo_root / contract_locator
    if destination.exists():
        return _blocked(
            what=f"a contract already exists at {contract_locator}",
            why="one contract is written once; compiling over an existing "
            "skeleton would silently discard ATD's in-progress fills",
            how="delete the existing file first if truly starting over, or "
            "edit it directly instead of recompiling",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.contract, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"DELIVERY-CONTRACT-SKELETON: {contract_locator}")
    print(f"ORACLE-LOCATOR: {result.contract['acceptance-tests']['locator']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
