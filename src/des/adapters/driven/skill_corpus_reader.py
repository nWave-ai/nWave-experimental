"""Driven adapter: read the normative-clause manifest + skill assets.

Feature: skill-normative-content-gate (DESIGN §5, component `SkillCorpusReader`).
Layer: Driven adapter — the ONLY filesystem surface in the feature.

Contract (DESIGN §5, ADR-SNCG-001 §Consequences):
  - `read_manifest(path)` → parse JSON via stdlib `json.loads`.
  - `read_asset(path)`    → `read_text(encoding="utf-8")`; reads-and-catches
    (no TOCTOU): `FileNotFoundError` → `ManifestAssetAbsent`,
    `UnicodeDecodeError` → `ManifestAssetUndecodable` (the two typed errors the
    service maps to INDETERMINATE — AC-06, AC-10).

Status: the plain reads are implemented (slice-01 walking skeleton). The typed
error mapping `FileNotFoundError`/`UnicodeDecodeError` →
`ManifestAssetAbsent`/`ManifestAssetUndecodable` arrives in slice-03 (AC-06,
AC-10); until then a read failure propagates uncaught — keeping the slice-03
INDETERMINATE ATs semantically RED.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from des.domain.skill_normative_clause import (
    ManifestAssetAbsent,
    ManifestAssetUndecodable,
)


if TYPE_CHECKING:
    from pathlib import Path


__all__ = ["ManifestAssetAbsent", "ManifestAssetUndecodable", "SkillCorpusReader"]


class SkillCorpusReader:
    """Reads the JSON manifest and the text skill assets it references."""

    def read_manifest(self, manifest_path: Path) -> dict[str, Any]:
        """Parse the manifest JSON (stdlib `json.loads`)."""
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cast("dict[str, Any]", parsed)

    def read_asset(self, asset_path: Path) -> str:
        """Read a skill asset as UTF-8 text; map read failures to typed errors.

        Reads-and-catches (no TOCTOU): a missing path raises `ManifestAssetAbsent`,
        a non-UTF-8 file raises `ManifestAssetUndecodable` — the two typed errors
        the service maps to INDETERMINATE (AC-06, AC-10).
        """
        try:
            return asset_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ManifestAssetAbsent(f"asset not found: {asset_path}") from exc
        except UnicodeDecodeError as exc:
            raise ManifestAssetUndecodable(
                f"asset is not valid UTF-8 text: {asset_path}"
            ) from exc
