"""RepoSourceProbe — production FreshnessProbe adapter (§1.5).

Reads ``_install_manifest.json`` colocated with the installed ``des/`` package
and returns a :class:`FreshnessVerdict` per the §1.3 four-state truth table.

Slice-02 adds state C / D discrimination via the canonical tree-hash (§1.6):

* manifest absent → state ``DEGRADED`` (REFUSE)
* manifest present, ``source_tree`` not reachable on this host → state ``A``
  (customer install, PROCEED silently)
* manifest present, ``source_tree`` reachable, installed tree-hash equals
  ``manifest.tree_hash`` → state ``C`` (developer fresh install, PROCEED)
* manifest present, ``source_tree`` reachable, installed tree-hash diverges
  from ``manifest.tree_hash`` → state ``D`` (developer stale install, REFUSE
  with reason citing the tree-hash component)

State ``B`` (manifest present, source_tree reachable but commit mismatch
suggesting accidental customer proximity) is not exercised by slice-02 ATs
and remains a non-load-bearing branch reachable in slice-03.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.ports.driven_ports.freshness_port import FreshnessVerdict
from des.runtime.tree_hash import (
    canonical_config_assets_hash,
    canonical_tree_hash,
)


# The installed package root the gate inspects. Resolved from this module's
# location at import time: ``…/lib/python/des/adapters/driven/freshness/`` →
# the installed ``des/`` package root is four parents up.
_INSTALLED_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_FILENAME = "_install_manifest.json"
# Known manifest schema versions. v1 = the §1.4 eight-field shape. v2 = the
# SYS-4 / AD-27 shape that ADDS ``config_assets_tree_hash`` (the install-time
# snapshot of the shipped ``lib/nWave/`` config assets). Any other value →
# DEGRADED (the installer slice-05 corruption AT pins ``999`` → REFUSE).
_KNOWN_SCHEMA_VERSIONS = frozenset({1, 2})
_CONFIG_ASSETS_SCHEMA_VERSION = 2
_CONFIG_ASSETS_FIELD = "config_assets_tree_hash"
# §1.4 install manifest schema — the 8 required fields. Missing any of these
# yields a DEGRADED verdict citing the missing field(s).
_REQUIRED_FIELDS = (
    "schema_version",
    "installed_version",
    "installed_at_iso",
    "source_tree",
    "source_commit",
    "source_dirty",
    "source_kind",
    "tree_hash",
)

# The DEGRADED "no manifest" reason text + its cause-appropriate remediation
# (RCA fix-des-silent-config-failure, root cause B): the dev-editable-binary-
# from-a-non-project-cwd topology has nothing to reinstall — the fix is
# running from a project/source checkout. Exported (not `_`-prefixed) so
# `des.runtime.freshness` can key its reason->remediation fallback map off
# the same SSOT text, keeping a directly-constructed `FreshnessVerdict` (e.g.
# in tests, or another `FreshnessProbe` adapter) correctly differentiated
# even without going through this probe.
NO_MANIFEST_REASON = "no install manifest — reinstall required"
NO_MANIFEST_REMEDIATION = "run from a project directory or the nWave source checkout"


class RepoSourceProbe:
    """Production FreshnessProbe — reads ``_install_manifest.json``."""

    def __init__(self, installed_root: Path | None = None) -> None:
        # Default to the installed package this module was loaded from. Tests
        # may inject a tmp_path-scoped root; the acceptance tests do not (they
        # rely on PYTHONPATH pointing at the synthetic installed tree, so
        # ``__file__`` resolves there naturally).
        self._installed_root = installed_root or _INSTALLED_PACKAGE_ROOT

    def probe(self) -> FreshnessVerdict:
        manifest_path = self._installed_root / _MANIFEST_FILENAME
        loaded = self._load_and_validate_manifest(manifest_path)
        if isinstance(loaded, FreshnessVerdict):
            return loaded
        return self._classify_state(loaded)

    def _load_and_validate_manifest(
        self, manifest_path: Path
    ) -> FreshnessVerdict | dict:
        """Read + parse + schema-validate the manifest file.

        Returns a DEGRADED ``FreshnessVerdict`` when the file is absent,
        empty, non-JSON, has an unknown ``schema_version``, or omits one of
        the §1.4 required fields. Returns the parsed manifest dict when the
        load + validation succeeded.
        """
        if not manifest_path.exists():
            return FreshnessVerdict(
                state="DEGRADED",
                reason=NO_MANIFEST_REASON,
                remediation=NO_MANIFEST_REMEDIATION,
            )
        raw_text = manifest_path.read_text(encoding="utf-8")
        if not raw_text:
            return FreshnessVerdict(
                state="DEGRADED",
                reason="cannot parse install manifest: file is empty",
            )
        try:
            manifest = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return FreshnessVerdict(
                state="DEGRADED",
                reason=f"cannot parse install manifest: {exc.msg}",
            )
        if manifest.get("schema_version") not in _KNOWN_SCHEMA_VERSIONS:
            return FreshnessVerdict(
                state="DEGRADED",
                reason=(
                    f"unknown manifest schema_version="
                    f"{manifest.get('schema_version')!r}"
                ),
            )
        missing = [field for field in _REQUIRED_FIELDS if field not in manifest]
        if missing:
            return FreshnessVerdict(
                state="DEGRADED",
                reason=f"missing required field(s) in install manifest: {missing}",
            )
        return manifest

    def _classify_state(self, manifest: dict) -> FreshnessVerdict:
        """Discriminate state A / C / D / STALE from a validated manifest.

        Installed-side first (states A/C/D, unchanged): a divergence between the
        installed tree and the manifest snapshot is state D (someone edited the
        installed copy → REFUSE).

        Gap B (#58 repo-moved-on) then refines state C: even when the installed
        tree matches the manifest, the dev may have edited the REPO ``src/des``
        after install. Re-hashing ``source_tree`` (rewrite-aware, so the
        pre-rewrite repo tree compares symmetrically to the post-rewrite manifest
        snapshot) detects that content divergence → state STALE (degrade-loud).
        This makes the gate compare CONTENT, not the coarse ``.git/`` presence.
        """
        source_tree = manifest.get("source_tree", "")
        if not source_tree or not Path(source_tree).exists():
            return FreshnessVerdict(
                state="A",
                reason="customer install — source tree not reachable",
            )
        manifest_tree_hash = manifest.get("tree_hash", "")
        installed_tree_hash = canonical_tree_hash(self._installed_root)
        if installed_tree_hash != manifest_tree_hash:
            return FreshnessVerdict(
                state="D",
                reason=(
                    f"installed tree_hash={installed_tree_hash} "
                    f"!= manifest tree_hash={manifest_tree_hash}"
                ),
            )
        source_tree_hash = canonical_tree_hash(Path(source_tree), rewrite_imports=True)
        if source_tree_hash != manifest_tree_hash:
            return FreshnessVerdict(
                state="STALE",
                reason=(
                    f"installed spine is stale: repo source_tree_hash="
                    f"{source_tree_hash} != installed manifest tree_hash="
                    f"{manifest_tree_hash}"
                ),
            )
        config_drift = self._classify_config_assets(manifest)
        if config_drift is not None:
            return config_drift
        return FreshnessVerdict(state="C", reason="developer install — fresh")

    def _classify_config_assets(self, manifest: dict) -> FreshnessVerdict | None:
        """Detect SYS-4 / AD-27 shipped config-asset drift (schema v2 only).

        v1 manifests carry no ``config_assets_tree_hash`` snapshot → no
        config-asset envelope (returns ``None``, the caller proceeds to state C).

        v2 manifests snapshot the shipped ``lib/nWave/`` config assets at install
        time. Re-hash the installed config tree and compare: a divergence means a
        maintainer edited a shipped config asset (``flavors/atdd_pure.yaml``, the
        gate-composition SSOT, or ``framework-catalog.yaml``) after install → a
        CONFIG_DRIFT verdict the hook names LOUD + degrades-loud on. The config
        tree sits beside ``lib/python`` as ``lib/nWave`` (``installed_root`` is
        ``lib/python/des``), exactly where the installer ships it.
        """
        if manifest.get("schema_version") != _CONFIG_ASSETS_SCHEMA_VERSION:
            return None
        snapshot = manifest.get(_CONFIG_ASSETS_FIELD, "")
        assets_root = self._installed_root.parent.parent / "nWave"
        if not snapshot or not assets_root.exists():
            return None
        installed_config_hash = canonical_config_assets_hash(assets_root)
        if installed_config_hash != snapshot:
            return FreshnessVerdict(
                state="CONFIG_DRIFT",
                reason=(
                    f"shipped config asset is stale: installed "
                    f"config_assets_tree_hash={installed_config_hash} "
                    f"!= manifest config_assets_tree_hash={snapshot}"
                ),
            )
        return None


__all__ = ["NO_MANIFEST_REASON", "NO_MANIFEST_REMEDIATION", "RepoSourceProbe"]
