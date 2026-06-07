"""Composition root for des-spine-control-plane-ssot slice-05 (config-asset drift).

Pillar 3 (App as in production): the SUT is the REAL installed HOOK ENTRYPOINT —
`python -c "import des.adapters.drivers.hooks.claude_code_hook_adapter"` —
exactly as Claude Code invokes it at hook process startup, against a synthetic
install layout under tmp_path that includes BOTH the `des/` package
(`lib/python/des/`) AND the shipped config assets (`lib/nWave/`). The freshness
gate fires at the hook adapter import site (slice-01 Gap-A wiring); slice-05
extends its envelope to the config assets (SYS-4 / AD-27). The AT observes the
gate's decision via the process exit code + the structured stderr event + the
persisted audit-log record.

Mandate-13 (invariant 1+2): the driving port is the hook subprocess. This module
NEVER does `from des.runtime.freshness import ...` to invoke the gate at the test
boundary — the only production import is the subprocess module-path string. The
config-drift is a genuine filesystem-content divergence between the installed
`lib/nWave/` tree and the manifest's `config_assets_tree_hash` snapshot.

Mandate-12 criterion 2/3: `ConfigDriftFixture` is the single source of truth for
ALL business logic the step methods need. Step bodies in `steps_slice_05_*.py`
delegate here — each body is ≤2 statements ending in one `fixture.<method>(...)`
call, no control flow inline.

DISTILL-authored RED scaffold (ADR-025): the freshness subsystem EXISTS
(slice-01 shipped the hook wiring + the `*.py` envelope), but slice-05's NEW
behavior does NOT:
  * SYS-4 / AD-27 — `canonical_tree_hash` (`runtime/tree_hash.py:61`) globs ONLY
    `*.py`. The shipped `*.yaml`/`*.json` config assets are OUTSIDE the envelope,
    so a drifted `flavors/atdd_pure.yaml` is structurally invisible.
  * the manifest is schema v1 with NO `config_assets_tree_hash` field
    (`des_plugin.py:668`, `repo_source_probe.py:36` `_SCHEMA_VERSION = 1`).
  * `FreshnessStateLabel` (`freshness_port.py:24`) has NO config-drift state and
    `RepoSourceProbe._classify_state` never re-hashes `lib/nWave/`.
  * there is NO `des.runtime.freshness.config-drift` event nor a
    `HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT` audit record.
So AT-01 (config-drift LOUD) + AT-03 (audit sink) RED-fail with assertion
mismatch — the LOUD `install-freshness.config-drift` warning + audit record are
absent today (the probe sees a MATCHES `*.py` tree → state C → SILENT PROCEED).
NOT import error (Mandate-7 RED-vs-BROKEN preserved). AT-02 (fresh-config
silent) GREEN-passes today as a regression pin (the config envelope must not
regress silence when the config matches).

Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io
because the driven set includes a real filesystem adapter). No PBT machinery.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .domain_types_slice_05 import (
    HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT,
    CheckoutProbe,
    ConfigAssetDrift,
    ConfigHookOutcome,
    FreshnessOptOut,
    HookVerdict,
    InstalledConfigProbe,
    StructuredConfigEventName,
)


# Repo root = .../nWave-dev (this file lives 5 dirs deep under tests/des/...).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REAL_DES_SRC = _REPO_ROOT / "src" / "des"
_REAL_NWAVE = _REPO_ROOT / "nWave"

# The load-bearing config-SSOT set the freshness envelope must cover (DV-3 /
# DESIGN OQ#3 MINIMAL boundary): the gate-composition SSOT flavor YAML +
# the framework catalog. `data/`/`templates/`/`schemas/` are OUT of the minimal
# envelope (envelope-width call, recommended MINIMAL to bound the hash input).
_CONFIG_ASSET_FLAVOR = ("flavors", "atdd_pure.yaml")
_CONFIG_ASSET_CATALOG = ("framework-catalog.yaml",)


def _parse_structured_event_line(stderr_text: str) -> tuple[str | None, str | None]:
    """Extract (`event`, `remediation`) from the first freshness JSON line on stderr.

    The gate emits one JSON-per-line; finds the first parseable line whose `event`
    starts with `des.runtime.freshness.` and returns its event + remediation.
    Returns (None, None) when no such line is present. Pure function.
    """
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = payload.get("event")
        if isinstance(event, str) and event.startswith("des.runtime.freshness."):
            return event, payload.get("remediation")
    return None, None


def _read_audit_records(audit_log_dir: Path) -> tuple[dict, ...]:
    """Parse every JSON line from the `JsonlAuditLogWriter` SSOT log files.

    Globs `audit-*.log` under the `AuditLogPathResolver`-resolved dir (the SAME
    single SSOT sink slice-01 reads — NOT a separate `audit.jsonl` orphan).
    Returns an empty tuple when no log file exists.
    """
    records: list[dict] = []
    for log_file in sorted(audit_log_dir.glob("audit-*.log")):
        for raw_line in log_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tuple(records)


class ConfigDriftFixture:
    """Composition-root service for des-spine-control-plane-ssot slice-05 ATs.

    Pillar 3: invokes the SAME hook entrypoint Claude Code invokes, against a
    synthetic install layout under tmp_path whose `_install_manifest.json`
    (schema v2) snapshots both the `*.py` tree-hash AND the shipped config-asset
    tree-hash. The SYS-4 config drift, the customer/fresh baseline, and the
    operator opt-out are all expressed as filesystem topology. The AT observes
    the gate's decision via exit code + structured stderr event + persisted
    audit record.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    # --- installed-spine + config-asset construction (the SYS-4 seam) -------

    def build_installed_spine(
        self, *, config_drift: ConfigAssetDrift
    ) -> InstalledConfigProbe:
        """Lay out a synthetic install (des package + lib/nWave config) + manifest.

        The `*.py` tree always MATCHES its source snapshot (slice-05 isolates the
        CONFIG-asset envelope, not the `*.py` envelope slice-01 covers). The
        config drift is the variable:

        DRIFTED → the installed `lib/nWave/flavors/atdd_pure.yaml` content
                  DIVERGES from the manifest's `config_assets_tree_hash` snapshot
                  (the AD-27 condition: a maintainer edited the installed config
                  asset after install). Today this is invisible (`*.py`-only
                  envelope) → the LOUD config-drift warning is absent (RED).
        MATCHES → the installed config assets EQUAL their install snapshot
                  (a fresh reinstall) → no false config-drift warning.
        """
        lib_python = self._tmp_path / "lib" / "python"
        des_root = lib_python / "des"
        # Install-fidelity copy: the SUT is the REAL hook entrypoint whose import
        # closure spans the whole `des/` package — mirror the production installer
        # (copytree + `from src.des`→`from des` rewrite) so the synthetic tree is
        # importable without a ModuleNotFoundError (BROKEN, not RED).
        self._copytree_with_rewrite(_REAL_DES_SRC, des_root)

        nwave_assets_root = self._build_nwave_assets(config_drift=config_drift)
        self._write_manifest(
            des_root,
            nwave_assets_root=nwave_assets_root,
            config_drift=config_drift,
        )
        return InstalledConfigProbe(
            installed_root=des_root,
            nwave_assets_root=nwave_assets_root,
            config_drift=config_drift,
        )

    @staticmethod
    def _copytree_with_rewrite(src_des: Path, dst_des: Path) -> None:
        """Copy `src/des` → synthetic `des/`, applying the installer import rewrite.

        Mirrors `des_plugin._rewrite_import_paths`: `from src.des`→`from des` etc.
        `__pycache__`/`*.pyc` skipped (they pollute the tree-hash). GIT-FREE.
        """
        from_pat = re.compile(r"\bfrom\s+src\.des\b")
        import_pat = re.compile(r"\bimport\s+src\.des\b")
        general_pat = re.compile(r"\bsrc\.des\.")
        for path in src_des.rglob("*"):
            if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            rel = path.relative_to(src_des)
            target = dst_des / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".py":
                content = path.read_text(encoding="utf-8")
                content = from_pat.sub("from des", content)
                content = import_pat.sub("import des", content)
                content = general_pat.sub("des.", content)
                target.write_text(content, encoding="utf-8")
            else:
                shutil.copyfile(path, target)

    def _build_nwave_assets(self, *, config_drift: ConfigAssetDrift) -> Path:
        """Ship the load-bearing `lib/nWave/` config assets, then optionally drift.

        Copies the real `flavors/atdd_pure.yaml` + `framework-catalog.yaml` to the
        synthetic `lib/nWave/` (mirroring `_install_nwave_runtime_assets`). For
        DRIFTED, appends a byte to the installed flavor AFTER the snapshot is
        taken (the manifest hash is computed in `_write_manifest` from the
        post-copy / pre-drift content), so the installed content != the snapshot.
        """
        nwave_root = self._tmp_path / "lib" / "nWave"
        flavor_dst = nwave_root / _CONFIG_ASSET_FLAVOR[0] / _CONFIG_ASSET_FLAVOR[1]
        flavor_dst.parent.mkdir(parents=True, exist_ok=True)
        flavor_src = _REAL_NWAVE / _CONFIG_ASSET_FLAVOR[0] / _CONFIG_ASSET_FLAVOR[1]
        shutil.copyfile(flavor_src, flavor_dst)
        catalog_dst = nwave_root / _CONFIG_ASSET_CATALOG[0]
        catalog_src = _REAL_NWAVE / _CONFIG_ASSET_CATALOG[0]
        shutil.copyfile(catalog_src, catalog_dst)
        return nwave_root

    @staticmethod
    def _config_assets_tree_hash(nwave_root: Path) -> str:
        """Canonical content hash over the load-bearing `lib/nWave/` config assets.

        The SYS-4 envelope variant of `canonical_tree_hash`: same algorithm shape
        (sorted rel-path + md5-of-bytes → sha256) but over the config-asset glob
        (`*.yaml`/`*.json`) instead of `*.py`. Reimplemented here (NOT imported
        from production — production does NOT yet hash config assets; that IS the
        slice-05 deliverable) so the manifest snapshot is well-defined for the AT.
        GIT-FREE, pure function.
        """
        sha = hashlib.sha256()
        assets = sorted(
            [
                p
                for p in nwave_root.rglob("*")
                if p.is_file() and p.suffix in (".yaml", ".yml", ".json")
            ],
            key=lambda p: p.relative_to(nwave_root).as_posix(),
        )
        for asset in assets:
            rel = asset.relative_to(nwave_root).as_posix()
            digest = hashlib.md5(asset.read_bytes()).hexdigest()
            sha.update(f"{rel}\0{digest}\n".encode())
        return f"sha256:{sha.hexdigest()}"

    @staticmethod
    def _canonical_py_hash(tree_root: Path) -> str:
        """Canonical `*.py` content hash — mirrors `des.runtime.tree_hash` §1.6.

        Reimplemented here (NOT imported at the test boundary, Mandate-13). The
        sibling parity test catches algorithm drift against production.
        """
        sha = hashlib.sha256()
        py_files = sorted(
            tree_root.rglob("*.py"), key=lambda p: p.relative_to(tree_root)
        )
        for py_file in py_files:
            rel = py_file.relative_to(tree_root).as_posix()
            digest = hashlib.md5(py_file.read_bytes()).hexdigest()
            sha.update(f"{rel}\0{digest}\n".encode())
        return f"sha256:{sha.hexdigest()}"

    def _write_manifest(
        self,
        installed_des_root: Path,
        *,
        nwave_assets_root: Path,
        config_drift: ConfigAssetDrift,
    ) -> None:
        """Write the `_install_manifest.json` colocated with the package.

        Schema choice ISOLATES the config-envelope assertion from the schema-bump:

        * DRIFTED → schema v2 (the SYS-4 post-fix manifest shape: the 8 v1 fields
          PLUS `config_assets_tree_hash`, the canonical hash of the shipped
          `lib/nWave/` config assets at install time). The snapshot is taken from
          the post-copy / PRE-drift config; the installed flavor is mutated AFTER
          the snapshot, so installed config-hash != snapshot. TODAY the v1 probe
          (`repo_source_probe.py:36` `_SCHEMA_VERSION = 1`) does NOT read this
          field — that IS the SYS-4 gap: the config drift is invisible. (Today's
          v1 probe rejects the v2 schema_version → DEGRADED → a `stale` event, NOT
          the `config-drift` event AT-01/AT-03 assert → RED-for-right-reason: the
          config-asset envelope, v2 manifest support, and the config-drift state
          do not exist yet — ONE coherent SYS-4 deliverable.)

        * MATCHES → schema v1 (TODAY's accepted manifest shape, no config hash).
          The current v1 probe accepts it, resolves the fresh `*.py` tree → state
          C → SILENT. This is the GREEN regression pin: a fresh install must stay
          silent, and the widened config envelope must NOT over-fire on matching
          config once v2 lands. Isolating MATCHES at v1 keeps AT-02 a clean
          fresh-config-silence assertion, uncoupled from the schema migration.

        The `*.py` tree always MATCHES its `source_tree` snapshot (slice-05
        isolates the CONFIG envelope; the `*.py` envelope is slice-01's concern).
        """
        installed_py_hash = self._canonical_py_hash(installed_des_root)
        config_snapshot_hash = self._config_assets_tree_hash(nwave_assets_root)
        # Apply the config drift AFTER snapshotting (so installed != snapshot).
        if config_drift is ConfigAssetDrift.DRIFTED:
            drifted = (
                nwave_assets_root / _CONFIG_ASSET_FLAVOR[0] / _CONFIG_ASSET_FLAVOR[1]
            )
            drifted.write_text(
                drifted.read_text(encoding="utf-8")
                + "\n# maintainer edit after install — config asset drifted (AD-27)\n",
                encoding="utf-8",
            )
        # `source_tree` = a verbatim copy of the installed `*.py` so the slice-01
        # `*.py` envelope resolves MATCHES (state C). Only the config envelope is
        # exercised by slice-05.
        source_root = self._tmp_path / "repo" / "src" / "des"
        source_root.mkdir(parents=True, exist_ok=True)
        for py_file in installed_des_root.rglob("*.py"):
            rel = py_file.relative_to(installed_des_root)
            dst = source_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(py_file, dst)
        manifest = {
            "schema_version": 1,
            "installed_version": "0.0.0-test",
            "installed_at_iso": "2026-06-02T00:00:00Z",
            "source_tree": str(source_root.resolve()),
            "source_commit": "",
            "source_dirty": False,
            "source_kind": "dev-checkout",
            "tree_hash": installed_py_hash,
        }
        if config_drift is ConfigAssetDrift.DRIFTED:
            manifest["schema_version"] = 2
            manifest["config_assets_tree_hash"] = config_snapshot_hash
        (installed_des_root / "_install_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    # --- audit-record observers (DV-5 KPI-1 sink) --------------------------

    @staticmethod
    def config_drift_audit_records(outcome: ConfigHookOutcome) -> tuple[dict, ...]:
        """Filter the SSOT audit records to the config-drift freshness ones.

        SSOT for the DV-5 record-matching logic so the step body stays a thin
        delegate. The `JsonlAuditLogWriter` serializes the event_type into the
        top-level `event` key; a config-drift record is recognised by its `event`
        being the structured event name (`des.runtime.freshness.config-drift`) OR
        the `EventType` member name the DELIVER wave wires
        (`HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT`, DV-5).
        """
        return tuple(
            r
            for r in outcome.audit_records
            if r.get("event")
            in (
                StructuredConfigEventName.CONFIG_DRIFT.value,
                HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT,
            )
        )

    @staticmethod
    def record_has_remediation(records: tuple[dict, ...]) -> bool:
        """True iff every record carries a non-empty top-level remediation (KPI-2)."""
        return all(bool(r.get("remediation")) for r in records)

    # --- checkout-adjacency construction (reused from slice-01 semantics) ---

    def build_checkout(self, *, adjacency) -> CheckoutProbe:
        """Lay out a synthetic CWD with the requested `.git/` adjacency. GIT-FREE.

        DEV_CHECKOUT → `cwd/.git/` present (the autoskip trap the hook suppresses).
        """
        from .domain_types_slice_05 import CheckoutAdjacency

        cwd = self._tmp_path / "operator-cwd"
        cwd.mkdir(parents=True, exist_ok=True)
        if adjacency is CheckoutAdjacency.DEV_CHECKOUT:
            (cwd / ".git").mkdir(parents=True, exist_ok=True)
        return CheckoutProbe(cwd=cwd, adjacency=adjacency)

    # --- the driving-port fire (real hook subprocess) ----------------------

    def fire_hook(
        self,
        installed: InstalledConfigProbe,
        checkout: CheckoutProbe,
        *,
        opt_out: FreshnessOptOut = FreshnessOptOut.UNSET,
    ) -> ConfigHookOutcome:
        """Fire the REAL installed hook entrypoint on the hot path.

        The freshness gate fires at the hook adapter's IMPORT TIME (slice-01 Gap-A
        wiring). The driving port is IMPORTING the hook adapter module exactly as
        the installed hook process does at startup:

            python -c "import des.adapters.drivers.hooks.claude_code_hook_adapter"

        PYTHONPATH points at the synthetic installed `lib/python` tree (so the
        `lib/nWave/` config assets resolve as siblings, exactly as in a real
        install); CWD is the checkout (so the autoskip probe sees the `.git/`
        marker — the hook site suppresses it via DV-2 so the content probe runs).
        The audit sink is redirected to a tmp_path dir via `DES_AUDIT_LOG_DIR`.

        Returns a ConfigHookOutcome capturing the port-exposed observables.
        """
        lib_python = installed.installed_root.parent  # …/lib/python
        audit_log_dir = self._tmp_path / ".nwave" / "des" / "logs"
        audit_log_dir.mkdir(parents=True, exist_ok=True)

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(lib_python),
            "DES_AUDIT_LOG_DIR": str(audit_log_dir),
        }
        for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
            if var in os.environ:
                env[var] = os.environ[var]
        if opt_out is FreshnessOptOut.SKIP:
            env["NWAVE_FRESHNESS"] = "skip"

        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import des.adapters.drivers.hooks.claude_code_hook_adapter",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(checkout.cwd),
            timeout=30,
        )
        event, remediation = _parse_structured_event_line(completed.stderr)
        verdict = (
            HookVerdict.REFUSE if completed.returncode != 0 else HookVerdict.PROCEED
        )
        return ConfigHookOutcome(
            exit_code=completed.returncode,
            stderr_text=completed.stderr,
            stderr_event=event,
            stderr_remediation=remediation,
            verdict=verdict,
            audit_records=_read_audit_records(audit_log_dir),
        )


__all__ = ["ConfigDriftFixture"]
