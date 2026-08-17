"""ADR-SSOT-002 Section 4b Discover/Resolve charter-namespace algebra.

The total `Discover(root, delivery-id)` / `Resolve(examine, Discover)`
functions over the schema-validated `delivery-id` charter namespace, shared
by `des dispatch` (which already holds a schema-validated `delivery-id` from
an immutable DeliveryContract) and `des resolve-charters` (the read-only
point-of-use projection over a raw `--delivery-id` argv fact, which must
additionally gate that fact against schema `$defs/id` before Discover runs).
Review-time computation only -- no persisted artifact, ledger or second
carrier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.cli.verify_charter_filled import charter_missing_sections


if TYPE_CHECKING:
    from pathlib import Path
    from typing import NoReturn


@dataclass(frozen=True, slots=True)
class _Missing:
    namespace: Path


@dataclass(frozen=True, slots=True)
class _Empty:
    namespace: Path


@dataclass(frozen=True, slots=True)
class _Valid:
    charter_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.charter_paths:
            raise ValueError("_Valid requires a non-empty charter sequence")


@dataclass(frozen=True, slots=True)
class _Invalid:
    what: str
    why: str
    how: str

    def __post_init__(self) -> None:
        if not self.what.strip() or not self.why.strip() or not self.how.strip():
            raise ValueError("_Invalid requires WHAT/WHY/HOW")


_Discover = _Missing | _Empty | _Valid | _Invalid


@dataclass(frozen=True, slots=True)
class _Skip:
    pass


@dataclass(frozen=True, slots=True)
class _Author:
    namespace: Path


@dataclass(frozen=True, slots=True)
class _Reuse:
    charter_paths: tuple[Path, ...]

    def __post_init__(self) -> None:
        if not self.charter_paths:
            raise ValueError("_Reuse requires a non-empty charter sequence")


@dataclass(frozen=True, slots=True)
class _Block:
    what: str
    why: str
    how: str

    def __post_init__(self) -> None:
        if not self.what.strip() or not self.why.strip() or not self.how.strip():
            raise ValueError("_Block requires WHAT/WHY/HOW")


_Resolve = _Skip | _Author | _Reuse | _Block


def _assert_never(value: object) -> NoReturn:
    raise AssertionError(f"unhandled algebra variant: {value!r}")


_INVALID_WHY = (
    "Discover validates every direct charter member without filtering; one "
    "invalid member blocks the namespace"
)
_INVALID_HOW = (
    "fix or remove the invalid member; every member must be a filled regular "
    "Markdown charter below the exact namespace"
)


def _invalid_member_detail(entry: Path, namespace: Path) -> str | None:
    if entry.is_symlink():
        return f"{entry} is a symlink"
    if entry.is_dir():
        return f"{entry} is a directory"
    if entry.suffix != ".md":
        return f"{entry} is not Markdown"
    try:
        resolved = entry.resolve()
        resolved.relative_to(namespace)
        content = entry.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return f"{entry} is not a readable in-namespace file ({exc})"
    missing = charter_missing_sections(content)
    return f"{entry} is unfilled ({'; '.join(missing)})" if missing else None


def _discover_charter_namespace(repo_root: Path, delivery_id: str) -> _Discover:
    """Discover every member of the exact delivery-id charter namespace."""
    base = (repo_root / "docs" / "product" / "expectations").resolve()
    namespace = base / delivery_id

    def invalid(detail: str) -> _Invalid:
        return _Invalid(
            what=f"the expectation-charter namespace is invalid: {detail}",
            why=_INVALID_WHY,
            how=_INVALID_HOW,
        )

    if namespace.is_symlink():
        return invalid(f"{namespace} is a symlink")
    if not namespace.exists():
        return _Missing(namespace)
    if not namespace.is_dir():
        return invalid(f"{namespace} is not a directory")
    try:
        resolved_namespace = namespace.resolve()
        resolved_namespace.relative_to(repo_root.resolve())
        resolved_namespace.relative_to(base)
        entries = sorted(namespace.iterdir(), key=lambda entry: entry.name)
    except (OSError, ValueError) as exc:
        return invalid(f"the namespace escapes or cannot be read ({exc})")
    if not entries:
        return _Empty(namespace)

    valid: list[Path] = []
    for entry in entries:
        detail = _invalid_member_detail(entry, resolved_namespace)
        if detail is not None:
            return invalid(detail)
        valid.append(entry)
    return _Valid(tuple(valid))


def _resolve_charter_namespace(
    *, examine: bool, discovered: _Discover | None
) -> _Resolve:
    """Total Resolve(examine, Discover) algebra from ADR-SSOT-002 Section 4b."""
    if not examine:
        return _Skip()
    assert discovered is not None
    match discovered:
        case _Missing(namespace) | _Empty(namespace):
            return _Author(namespace)
        case _Valid(paths):
            return _Reuse(paths)
        case _Invalid(what, why, how):
            return _Block(what, why, how)
        case _:
            _assert_never(discovered)
