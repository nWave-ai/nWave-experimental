"""Domain types for des-spine-control-plane-ssot slice-05 (config-asset drift).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-05 .feature scenarios speak lives here as a typed enum or frozen
dataclass. Step methods + composition consume these typed parameters; raw `str`
parameters are avoided wherever a domain enum exists.

Slice-05 SUT = the HOOK ENTRYPOINT freshness gate (the SAME driving port as
slice-01), now interrogating the SHIPPED CONFIG ASSETS (`lib/nWave/`), not only
the `*.py` package. This is the SYS-4 / AD-27 fix — the freshness envelope
`canonical_tree_hash` globs ONLY `*.py`, so a drifted shipped config asset
(`flavors/atdd_pure.yaml`, `framework-catalog.yaml`) is invisible to the gate.

Vocabulary deliberately MIRRORS slice-01 (`HookVerdict`, `StructuredEventName`,
`CheckoutAdjacency`, `FreshnessOptOut`) — the freshness driving port is shared
across slices (Mandate-12 step-reuse). Slice-05 ADDS only the config-asset
nouns: the config-drift event name, the config-drift health-gate EventType, and
the `ConfigAssetDrift` precondition enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Re-export the shared slice-01 verdict/adjacency/opt-out vocabulary so the
# slice-05 steps speak ONE freshness language across the feature (Mandate-12).
from .domain_types import (
    CheckoutAdjacency,
    CheckoutProbe,
    FreshnessOptOut,
    HookVerdict,
)


class ConfigAssetDrift(str, Enum):
    """How the shipped `lib/nWave/` config assets relate to their install snapshot.

    DRIFTED is the AD-27 / SYS-4 condition — a shipped config asset (e.g. the
    gate-composition SSOT `flavors/atdd_pure.yaml`, made authoritative by
    slice-04) was edited in the installed copy after install, so the installed
    config no longer matches the manifest's `config_assets_tree_hash`. The hook
    must catch this and warn LOUD — today it CANNOT, because the freshness
    envelope hashes only `*.py`.

    MATCHES is the regression pin — installed config assets equal their install
    snapshot → no false config-drift warning (the gate must compare config
    CONTENT, not merely the presence of `lib/nWave/`).
    """

    DRIFTED = "shipped configuration has drifted from the install snapshot"
    MATCHES = "shipped configuration matches the install snapshot"


class StructuredConfigEventName(str, Enum):
    """The structured stderr event names the hook config-drift gate may emit.

    `install-freshness.config-drift` is the NEW LOUD warning this slice adds for
    the SYS-4 / AD-27 config-asset drift. It is DISTINCT from slice-01's
    `install-freshness.stale` (`*.py` drift) and the pre-existing
    `proceed`/`autoskipped`/`skipped` events — so post-hoc audit answers "why did
    the spine run on a stale CONFIG asset" (KPI 1/2). The `.value` is the full
    structured-event string the gate stamps on stderr.
    """

    CONFIG_DRIFT = "des.runtime.freshness.config-drift"  # NEW — the SYS-4 LOUD warning
    SKIPPED = "des.runtime.freshness.skipped"  # operator NWAVE_FRESHNESS=skip
    STALE = "des.runtime.freshness.stale"  # slice-01 `*.py` drift (NOT config)


# The persisted audit-log EventType name (DEVOPS DV-5) the config-drift warning
# writes to the JsonlAuditLogWriter SSOT (`audit-*.log` under the
# `AuditLogPathResolver` dir, serialized under the record's top-level `event`
# key). The hook freshness gate dual-emits: stderr (above) + this persisted
# record (the KPI-1 queryable sink read by JsonlAuditLogReader). NOT a separate
# `audit.jsonl` representation (RELOOP_A — same SSOT discipline as slice-01).
HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT = (
    "HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT"
)


# --- Frozen probe / outcome dataclasses ----------------------------------


@dataclass(frozen=True)
class InstalledConfigProbe:
    """A handle on a synthetic installed spine WITH shipped `lib/nWave/` config.

    Wraps a tmp_path-scoped install layout: the `des/` package under
    `lib/python/`, the shipped config assets under `lib/nWave/`
    (`flavors/atdd_pure.yaml`, `framework-catalog.yaml`), and a manifest whose
    `config_assets_tree_hash` (schema v2) snapshots the config assets at install
    time. `config_drift` records how the installed config content relates to that
    snapshot — the seam the SYS-4 config-asset envelope must interrogate.
    """

    installed_root: Path  # the `des/` package root inside lib/python/
    nwave_assets_root: Path  # the shipped `lib/nWave/` config-asset tree
    config_drift: ConfigAssetDrift


@dataclass(frozen=True)
class ConfigHookOutcome:
    """Observable outcome of one real hook subprocess fire on the hot path.

    Universe entries `assert_state_delta` tracks are built from THIS dataclass's
    port-exposed fields: `exit_code`, `verdict`, `stderr_event`, `audit_records`.
    Internal plumbing (Popen handle, env dict, stdin bytes, manifest dict) is
    NEVER in the universe (Mandate 8 — port-exposed observables only).
    """

    exit_code: int
    stderr_text: str
    stderr_event: str | None  # parsed `event` from the structured stderr line
    stderr_remediation: str | None  # the `remediation` field, when present
    verdict: HookVerdict
    audit_records: tuple[dict, ...]  # parsed records from the audit-*.log SSOT


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

CONFIG_DRIFT_BY_PHRASE: dict[str, ConfigAssetDrift] = {
    d.value: d for d in ConfigAssetDrift
}
# Shared `.git/`-adjacency phrase table (reuses the slice-01 `CheckoutAdjacency`
# vocabulary). Named `_05` so the slice-05 steps bind unambiguously without
# colliding with slice-01's `ADJACENCY_BY_PHRASE` under the same step namespace.
ADJACENCY_BY_PHRASE_05: dict[str, CheckoutAdjacency] = {
    a.value: a for a in CheckoutAdjacency
}


__all__ = [
    "ADJACENCY_BY_PHRASE_05",
    "CONFIG_DRIFT_BY_PHRASE",
    "HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT",
    "CheckoutAdjacency",
    "CheckoutProbe",
    "ConfigAssetDrift",
    "ConfigHookOutcome",
    "FreshnessOptOut",
    "HookVerdict",
    "InstalledConfigProbe",
    "StructuredConfigEventName",
]
