"""Read-only point-of-use projection of the Discover/Resolve charter algebra.

Thin argv/JSON shell over ``des.cli._charter_resolution``.  No writes, no
workflow state -- one JSON line describing the closed EXAMINE/charter
precondition for a given ``--delivery-id``.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    resolve_delivery_contract_schema_path,
)
from des._internal.json_schema_subset import JsonSchemaSubsetError
from des._internal.json_schema_subset import validate as _validate_contract_schema
from des.cli._charter_resolution import (
    _assert_never,
    _Author,
    _Block,
    _discover_charter_namespace,
    _resolve_charter_namespace,
    _Reuse,
)


_EXIT_USAGE_ERROR = 2


class _ArgumentRefusal(Exception):
    """One malformed argv fact, rendered by ``main`` as JSON BLOCK."""


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Keep malformed argv inside the command's one-JSON-line algebra."""

    def error(self, message: str) -> None:
        raise _ArgumentRefusal(message)


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True))


def _refuse(what: str, why: str, how: str) -> int:
    _emit({"status": "BLOCK", "what": what, "why": why, "how": how})
    return _EXIT_USAGE_ERROR


def _build_parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des resolve-charters",
        description=(
            "Resolve the EXAMINE/charter precondition for one delivery-id and "
            "print exactly one JSON line."
        ),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        type=Path,
        help="Absolute physical repository root used to resolve the namespace.",
    )
    parser.add_argument(
        "--delivery-id",
        required=True,
        help="Producer delivery-id whose expectation-charter namespace is resolved.",
    )
    parser.add_argument(
        "--examine",
        required=True,
        choices=["true", "false"],
        help="applicability.examine as carried by the immutable DeliveryContract.",
    )
    return parser


def _delivery_id_schema_refusal(delivery_id: str) -> tuple[str, str, str] | None:
    """Validate raw argv against the canonical shipped ``$defs/id`` schema."""
    schema_path = resolve_delivery_contract_schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        delivery_id_schema = schema["$defs"]["id"]
        if not isinstance(delivery_id_schema, dict):
            raise TypeError("$defs/id is not an object")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return (
            f"the DeliveryContract id schema cannot be read at {schema_path} ({exc})",
            "charter discovery cannot trust a delivery-id without its canonical schema",
            "reinstall nWave with its thin-delivery-contract schema",
        )
    try:
        _validate_contract_schema(delivery_id_schema, delivery_id)
    except JsonSchemaSubsetError as exc:
        return (
            f"--delivery-id {delivery_id!r} is not schema-valid ({exc.message})",
            "the namespace path is derived from delivery-id; an unsafe id could escape the expectations root",
            f"pass a delivery-id satisfying $defs/id in {schema_path.name}",
        )
    return None


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    except _ArgumentRefusal as exc:
        return _refuse(
            f"the resolve-charters argv is malformed ({exc})",
            "every discovery input must be explicit and closed before filesystem access",
            "pass --repo-root, --delivery-id and --examine true|false exactly once",
        )
    repo_root: Path = args.repo_root
    examine = args.examine == "true"

    if not repo_root.is_absolute():
        return _refuse(
            "--repo-root is relative",
            "namespace identity must not depend on the invoking cwd",
            "pass the absolute physical repository root",
        )
    try:
        root_stat = repo_root.lstat()
    except OSError as exc:
        return _refuse(
            f"--repo-root cannot be read ({exc})",
            "namespace resolution requires a real repository root",
            "pass an existing absolute repository directory",
        )
    if not stat.S_ISDIR(root_stat.st_mode) or repo_root.is_symlink():
        return _refuse(
            "--repo-root is not a real directory",
            "a symlink or non-directory makes namespace identity ambiguous",
            "pass the absolute physical repository directory",
        )

    if refusal := _delivery_id_schema_refusal(args.delivery_id):
        return _refuse(*refusal)

    if not examine:
        _emit({"status": "SKIP"})
        return 0

    discovered = _discover_charter_namespace(repo_root, args.delivery_id)
    resolution = _resolve_charter_namespace(examine=examine, discovered=discovered)

    if isinstance(resolution, _Author):
        _emit(
            {
                "status": "AUTHOR",
                "namespace": resolution.namespace.relative_to(
                    repo_root.resolve()
                ).as_posix(),
            }
        )
        return 0
    if isinstance(resolution, _Reuse):
        _emit(
            {
                "status": "REUSE",
                "charter-paths": [
                    path.resolve().relative_to(repo_root.resolve()).as_posix()
                    for path in sorted(resolution.charter_paths)
                ],
            }
        )
        return 0
    if isinstance(resolution, _Block):
        return _refuse(resolution.what, resolution.why, resolution.how)
    _assert_never(resolution)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
