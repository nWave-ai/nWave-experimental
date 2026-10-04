"""Lossless, bounded reading views of an already sealed role input.

Views project only their supplied input. They cannot widen a role's evidence
boundary and never replace the immutable input used for recording a result.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_PART_NAME = re.compile(r"field-[0-9]{6}-part-[0-9]{6}\.json\Z")
_MAX_PART_BYTES = 8192
_STRING_PART_CHARACTERS = 1024


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _write_once(path: Path, raw: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError(f"role input view conflicts at {path}") from None


def write_views(source: Path, raw: bytes) -> Path:
    """Construct reading projections after the original input has been sealed."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or _canonical(payload) != raw:
        raise ValueError("role input must be a canonical JSON object")
    directory = source.with_name(source.name + ".views")
    if directory.is_symlink():
        raise ValueError("role input views must use a real directory")
    directory.mkdir(exist_ok=True)
    fields: list[dict[str, object]] = []

    def emit(value: object, path: list[str | int]) -> None:
        if isinstance(value, dict) and value:
            for key in sorted(value):
                emit(value[key], [*path, key])
            return
        if isinstance(value, list) and value:
            for index, child in enumerate(value):
                emit(child, [*path, index])
            return
        if isinstance(value, str):
            values = [
                value[offset : offset + _STRING_PART_CHARACTERS]
                for offset in range(0, len(value), _STRING_PART_CHARACTERS)
            ] or [""]
            kind = "string"
        else:
            values = [value]
            kind = "value"
        parts = []
        for index, part in enumerate(values, start=1):
            name = f"field-{len(fields) + 1:06d}-part-{index:06d}.json"
            data = _canonical({"value": part})
            if len(data) > _MAX_PART_BYTES:
                raise ValueError("role input view scalar exceeds the reading ceiling")
            _write_once(directory / name, data)
            parts.append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})
        fields.append({"path": path, "kind": kind, "parts": parts})

    emit(payload, [])
    manifest = directory / "manifest.json"
    _write_once(
        manifest,
        json.dumps(
            {
                "schema": "nwave.role_input_views.v1",
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "fields": fields,
            },
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
    )
    return manifest


def read_views(manifest: Path, *, expected_input_sha256: str) -> bytes:
    """Authenticate against the independently retained INPUT-SHA256, not the index."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_input_sha256):
        raise ValueError("trusted role input digest is malformed")
    if manifest.is_symlink() or any(parent.is_symlink() for parent in manifest.parents):
        raise ValueError("role input view manifest is not confined")
    try:
        index = json.loads(manifest.read_bytes())
    except (OSError, ValueError) as error:
        raise ValueError("role input view manifest is unavailable") from error
    if (
        not isinstance(index, dict)
        or set(index) != {"schema", "input_sha256", "fields"}
        or index["schema"] != "nwave.role_input_views.v1"
        or not isinstance(index["fields"], list)
    ):
        raise ValueError("role input view manifest is malformed")
    if index["input_sha256"] != expected_input_sha256:
        raise ValueError("role input view manifest digest differs from trusted INPUT")
    recovered: object = {}
    seen: set[tuple[str | int, ...]] = set()
    ancestors: set[tuple[str | int, ...]] = set()
    for field in index["fields"]:
        if not isinstance(field, dict) or set(field) != {"path", "kind", "parts"}:
            raise ValueError("role input view field is malformed")
        path, parts = field["path"], field["parts"]
        if (
            not isinstance(path, list)
            or not all(
                isinstance(p, str)
                or (isinstance(p, int) and not isinstance(p, bool) and p >= 0)
                for p in path
            )
            or not isinstance(parts, list)
            or not parts
        ):
            raise ValueError("role input view field path or parts are malformed")
        key = tuple(path)
        if (
            key in seen
            or key in ancestors
            or any(key[:n] in seen for n in range(len(key)))
        ):
            raise ValueError("role input view fields overlap")
        seen.add(key)
        ancestors.update(key[:n] for n in range(len(key)))
        values = []
        for part in parts:
            if (
                not isinstance(part, dict)
                or set(part) != {"file", "sha256"}
                or not isinstance(part["file"], str)
                or not _PART_NAME.fullmatch(part["file"])
            ):
                raise ValueError("role input view part is not confined")
            target = manifest.parent / part["file"]
            if target.is_symlink():
                raise ValueError("role input view part is not confined")
            try:
                raw = target.read_bytes()
            except OSError as error:
                raise ValueError("role input view part is unavailable") from error
            if (
                len(raw) > _MAX_PART_BYTES
                or hashlib.sha256(raw).hexdigest() != part["sha256"]
            ):
                raise ValueError("role input view part digest differs")
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {"value"}:
                raise ValueError("role input view part is malformed")
            values.append(value["value"])
        if field["kind"] == "string" and all(isinstance(v, str) for v in values):
            value = "".join(values)
        elif (
            field["kind"] == "value"
            and len(values) == 1
            and not isinstance(values[0], str)
        ):
            value = values[0]
        else:
            raise ValueError("role input view field kind differs")
        if not path:
            recovered = value
            continue
        node = recovered
        for position, token in enumerate(path):
            last = position == len(path) - 1
            if isinstance(node, dict) and isinstance(token, str):
                if last:
                    node[token] = value
                else:
                    node = node.setdefault(
                        token, [] if isinstance(path[position + 1], int) else {}
                    )
            elif isinstance(node, list) and isinstance(token, int):
                if token > len(node):
                    raise ValueError("role input view array has a missing element")
                if token == len(node):
                    node.append(
                        value
                        if last
                        else ([] if isinstance(path[position + 1], int) else {})
                    )
                if not last:
                    node = node[token]
                else:
                    node[token] = value
            else:
                raise ValueError("role input view field container differs")
    raw = _canonical(recovered)
    if hashlib.sha256(raw).hexdigest() != expected_input_sha256:
        raise ValueError("reconstructed role input digest differs")
    return raw
