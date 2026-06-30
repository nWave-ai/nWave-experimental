"""des.runtime.tree_hash — canonical tree-hash normalisation (§1.6).

Two files compared on two hosts MUST hash identically when their *content*
matches, irrespective of mtime, file-mode noise, or ``__pycache__``. Algorithm:

1. ``rglob("*.py")`` over the tree (only ``.py``; install plugin already
   excludes ``__pycache__``, ``*.pyc``, ``*.pyo``).
2. Sort by path relative to the tree root.
3. For each file, compute md5 of the bytes.
4. Concatenate ``<rel_path>\\0<md5>\\n`` lines.
5. SHA-256 of the concatenated stream.

Returns the prefix-tagged form ``"sha256:<hex>"``.

The installed tree is already post-import-rewrite, so its on-disk content can
be hashed directly. The repo ``src/des/`` tree is pre-rewrite — comparing it
symmetrically requires applying the install-time rewrite in-memory while
hashing. Slice-02 ships the installed-tree hash only; the repo-side symmetric
hash lands in slice-03 alongside DDD-13 (A-2) shared-rewrite extraction.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


# The install-time import rewrite (mirrors des_plugin._rewrite_import_paths):
# the repo `src/des/` is pre-rewrite (`from src.des ...`), the installed `des/`
# is post-rewrite (`from des ...`). To compare the two symmetrically by content,
# the repo side is hashed AFTER applying this rewrite in-memory (§1.6 note).
_REWRITE_FROM = re.compile(r"\bfrom\s+src\.des\b")
_REWRITE_IMPORT = re.compile(r"\bimport\s+src\.des\b")
_REWRITE_GENERAL = re.compile(r"\bsrc\.des\.")


def _rewrite_source_bytes(raw: bytes) -> bytes:
    """Apply the install-time `src.des`→`des` rewrite to one `.py` file's bytes."""
    text = raw.decode("utf-8")
    text = _REWRITE_FROM.sub("from des", text)
    text = _REWRITE_IMPORT.sub("import des", text)
    text = _REWRITE_GENERAL.sub("des.", text)
    return text.encode("utf-8")


# Config-asset envelope (SYS-4 / AD-27): the freshness gate hashed ONLY `*.py`,
# so a drifted shipped config asset (`lib/nWave/flavors/atdd_pure.yaml`, the
# gate-composition SSOT, or `framework-catalog.yaml`) drifted SILENTLY. The
# config-asset hash covers the shipped declarative config siblings of the `des`
# package under `lib/nWave/`.
_CONFIG_ASSET_SUFFIXES = (".yaml", ".yml", ".json")


def canonical_config_assets_hash(assets_root: Path) -> str:
    """Return ``"sha256:<hex>"`` for the canonical hash of the config assets.

    The SYS-4 config-asset envelope variant of :func:`canonical_tree_hash`: same
    algorithm shape (sorted POSIX rel-path + md5-of-bytes → sha256) but over the
    shipped declarative config glob (``*.yaml`` / ``*.yml`` / ``*.json``) under
    ``assets_root`` instead of ``*.py``. Pure function, GIT-FREE, cross-OS.

    A drifted shipped config asset (a maintainer edited the installed copy after
    install) makes this hash diverge from the manifest snapshot — the AD-27
    condition the runtime gate names LOUD.
    """
    sha = hashlib.sha256()
    assets = sorted(
        (
            p
            for p in assets_root.rglob("*")
            if p.is_file() and p.suffix in _CONFIG_ASSET_SUFFIXES
        ),
        key=lambda p: p.relative_to(assets_root).as_posix(),
    )
    for asset in assets:
        rel = asset.relative_to(assets_root).as_posix()
        digest = hashlib.md5(asset.read_bytes()).hexdigest()
        sha.update(f"{rel}\0{digest}\n".encode())
    return f"sha256:{sha.hexdigest()}"


def canonical_tree_hash(tree_root: Path, *, rewrite_imports: bool = False) -> str:
    """Return ``"sha256:<hex>"`` for the canonical hash of ``tree_root``.

    Pure function — reads ``*.py`` files under ``tree_root`` once each. The
    algorithm matches §1.6 of fix-des-self-hosted-gate-sync feature-delta.

    ``rewrite_imports`` (Gap B): when True, each ``.py`` file's bytes are passed
    through the install-time ``src.des``→``des`` rewrite before hashing, so a
    pre-rewrite repo ``src/des`` tree hashes identically to the post-rewrite
    installed ``des`` tree it was installed from. This is what lets the repo-side
    re-hash compare symmetrically against ``manifest.tree_hash`` to detect the
    #58 repo-moved-on drift.
    """
    sha = hashlib.sha256()
    py_files = sorted(tree_root.rglob("*.py"), key=lambda p: p.relative_to(tree_root))
    for py_file in py_files:
        rel = py_file.relative_to(tree_root).as_posix()
        raw = py_file.read_bytes()
        if rewrite_imports:
            raw = _rewrite_source_bytes(raw)
        digest = hashlib.md5(raw).hexdigest()
        sha.update(f"{rel}\0{digest}\n".encode())
    return f"sha256:{sha.hexdigest()}"


__all__ = ["canonical_config_assets_hash", "canonical_tree_hash"]
