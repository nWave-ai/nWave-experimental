"""Validate one DeliveryContract through the installed runtime schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.cli.dispatch import _load_delivery_contract, _resolve_oracle, closure_digest


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
    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_bytes = _resolve_oracle(args.repo_root, oracle_locator)
    if oracle_bytes is None:
        return 2

    digest = closure_digest(contract_bytes, oracle_bytes)
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
