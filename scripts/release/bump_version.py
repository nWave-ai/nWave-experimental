"""Bump version strings in pyproject.toml and/or framework-catalog.yaml.

Replaces fragile inline heredoc Python blocks in release-prod.yml with
a proper, testable CLI script.

CLI:
    python -m scripts.release.bump_version \\
        --version VERSION \\
        --pyproject PATH \\
        --catalog PATH

At least one of --pyproject or --catalog must be provided.

Exit codes:
    0 = success
    1 = error (file not found, validation failure)
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for version bumping."""
    parser = argparse.ArgumentParser(
        description="Bump version in pyproject.toml and/or framework-catalog.yaml"
    )
    parser.add_argument(
        "--version", required=True, help="New version string (e.g. 1.1.23)"
    )
    parser.add_argument(
        "--pyproject", default=None, help="Path to pyproject.toml to bump"
    )
    parser.add_argument(
        "--catalog", default=None, help="Path to framework-catalog.yaml to bump"
    )
    args = parser.parse_args(argv)

    if args.pyproject is None and args.catalog is None:
        parser.error("At least one of --pyproject or --catalog must be provided")

    return args


def _bump_pyproject(path: str, version: str) -> None:
    """Read pyproject.toml, replace first version = "..." occurrence, write back."""
    if not os.path.isfile(path):
        msg = f"pyproject.toml not found: {path}"
        raise FileNotFoundError(msg)

    content = open(path).read()
    updated = re.sub(
        r'version = "[^"]+"',
        f'version = "{version}"',
        content,
        count=1,
    )
    with open(path, "w") as f:
        f.write(updated)


def _bump_catalog(path: str, version: str) -> None:
    """Read YAML catalog, set version key, write back preserving order."""
    import yaml

    if not os.path.isfile(path):
        msg = f"Catalog file not found: {path}"
        raise FileNotFoundError(msg)

    with open(path) as f:
        catalog = yaml.safe_load(f)

    catalog["version"] = version

    with open(path, "w") as f:
        yaml.dump(catalog, f, default_flow_style=False, sort_keys=False)


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse args, bump requested files, report results."""
    args = parse_args(argv)

    try:
        if args.pyproject is not None:
            _bump_pyproject(args.pyproject, args.version)
            print(f"Bumped pyproject.toml to version {args.version}: {args.pyproject}")

        if args.catalog is not None:
            _bump_catalog(args.catalog, args.version)
            print(f"Bumped catalog to version {args.version}: {args.catalog}")

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
