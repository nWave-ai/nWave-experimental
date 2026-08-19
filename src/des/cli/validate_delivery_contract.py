"""Validate one DeliveryContract through the installed runtime schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.cli._declared_import_refusal import (
    first_missing_declared_import as _first_missing_declared_import,
)
from des.cli._declared_import_refusal import (
    unresolved_declared_import_how as _unresolved_declared_import_how,
)
from des.cli._oracle_structure_refusal import (
    all_oracle_structure_findings as _all_oracle_structure_findings,
)
from des.cli._verification_command_refusal import (
    first_missing_verification_path as _first_missing_verification_path,
)
from des.cli._verification_command_refusal import (
    missing_verification_path_finding as _missing_verification_path_finding,
)
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

    missing = _first_missing_declared_import(args.repo_root, contract)
    if missing is not None:
        target_path, reference = missing
        print(
            f"WHAT: target {target_path!r} declares import {reference!r}, "
            "which does not resolve to a base-tree module or symbol "
            "WHY: a DeliveryContract citing an invented symbol reintroduces "
            "ATD-invented substrate (K4 failure-to-design matrix row 12) "
            f"HOW: {_unresolved_declared_import_how(args.repo_root, contract, reference)}",
            file=sys.stderr,
        )
        return 2

    missing_verification = _first_missing_verification_path(args.repo_root, contract)
    if missing_verification is not None:
        what, why, how = _missing_verification_path_finding(missing_verification)
        print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
        return 2

    structure_findings = _all_oracle_structure_findings(args.repo_root, contract)
    if structure_findings:
        what, why, how = structure_findings[0]
        print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
        return 2

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
