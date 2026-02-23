"""Read a single field from a TOML file by dotted key path.

Replaces fragile inline regex/line-parsing Python blocks in release-prod.yml
with proper TOML parsing via tomllib (Python 3.11+) or tomli fallback.

CLI:
    python -m scripts.release.read_toml_field \\
        --file PATH \\
        --key DOTTED.KEY.PATH

Examples:
    python -m scripts.release.read_toml_field \\
        --file pyproject.toml --key project.version

    python -m scripts.release.read_toml_field \\
        --file pyproject.toml --key tool.nwave.public_version

Exit codes:
    0 = success (value printed to stdout)
    1 = error (file not found, key not found)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for TOML field reading."""
    parser = argparse.ArgumentParser(
        description="Read a field from a TOML file by dotted key path"
    )
    parser.add_argument("--file", required=True, help="Path to the TOML file")
    parser.add_argument(
        "--key", required=True, help="Dotted key path (e.g. project.version)"
    )
    return parser.parse_args(argv)


def _read_toml(path: str) -> dict:
    """Parse a TOML file and return the data as a dict."""
    toml_path = Path(path)
    if not toml_path.is_file():
        msg = f"File not found: {path}"
        raise FileNotFoundError(msg)
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def _resolve_key(data: dict, dotted_key: str) -> object | None:
    """Navigate a nested dict using a dotted key path.

    Returns the value if found, or None if any segment is missing
    or a non-dict intermediate is encountered.
    """
    current: object = data
    for segment in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
        if current is None:
            return None
    return current


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse args, read TOML, resolve key, print value."""
    args = parse_args(argv)

    try:
        data = _read_toml(args.file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    value = _resolve_key(data, args.key)
    if value is None:
        print(f"Error: key '{args.key}' not found in {args.file}", file=sys.stderr)
        sys.exit(1)

    print(value)


if __name__ == "__main__":
    main()
