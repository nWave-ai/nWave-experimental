"""Validate one DeliveryContract through the installed runtime schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.cli._placeholder_refusal import (
    first_unfilled_placeholder_finding as _first_unfilled_placeholder_finding,
)
from des.cli.dispatch import (
    _load_delivery_contract,
    _resolve_oracle,
    _resolve_supporting_files,
    closure_digest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des validate-delivery-contract",
        description=(
            "Validate one repository-root-relative DeliveryContract with the "
            "same installed schema used by des dispatch."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-contract", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Print one stable validated identity or return the loader's refusal."""
    args = _parser().parse_args(argv)
    try:
        root_stat = args.repo_root.lstat()
    except OSError as error:
        print(
            f"WHAT: --repo-root cannot be read ({error}) "
            "WHY: contract resolution requires an explicit real repository root "
            "HOW: pass an existing absolute repository directory",
            file=sys.stderr,
        )
        return 2
    if (
        not args.repo_root.is_absolute()
        or not args.repo_root.is_dir()
        or args.repo_root.is_symlink()
    ):
        print(
            "WHAT: --repo-root is not an absolute real directory "
            "WHY: relative, non-directory or symlink roots make contract identity ambiguous "
            "HOW: pass the absolute physical repository directory",
            file=sys.stderr,
        )
        return 2
    del root_stat

    loaded = _load_delivery_contract(args.repo_root, args.delivery_contract)
    if loaded is None:
        return 2

    contract, locator, contract_bytes = loaded

    unfilled = _first_unfilled_placeholder_finding(contract)
    if unfilled is not None:
        what, why, how = unfilled
        print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
        return 2

    # Ale's construction-over-file correction (2026-08-20, "the contract
    # has one writer -- `des fill-contract` is the constructor", Agda
    # vacuity report ~/nwave-formal/2026-08-19-gates/report/2026-08-19-
    # gate-analysis.md): declared-imports resolution and verification-
    # scope path existence used to be re-checked HERE too -- DELETED, not
    # merely reordered. `des fill-contract` has no batch entry naming
    # a mechanical field at all, so a contract reaching this crafter-
    # BASELINE call already has them correct by construction.

    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_bytes = _resolve_oracle(args.repo_root, oracle_locator)
    if oracle_bytes is None:
        return 2
    supporting_files = _resolve_supporting_files(
        args.repo_root,
        list(contract["acceptance-tests"].get("supporting-locators", [])),
    )
    if supporting_files is None:
        return 2

    digest = closure_digest(
        contract_bytes,
        oracle_bytes,
        oracle_locator=oracle_locator,
        supporting_files=supporting_files,
    )
    print(
        json.dumps(
            {
                "contract": locator,
                "digest": f"sha256:{digest}",
                "verdict": "VALID",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
