"""Domain types for fix-des-self-hosted-gate-sync acceptance tests (Mandate-12).

Per nw-distill § DSL Emergence + SSOT via Types + Services + DSL:

Typed enums + dataclasses for every domain noun the .feature scenarios speak.
Composition-root services (FreshnessProbeFixture below) consume these typed
parameters; step methods invoke services with typed args and never inline
business logic.

The vocabulary is shared across slice-01/02/03 step modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


# --- Four-state truth table (§1.3) ---------------------------------------


class FreshnessState(str, Enum):
    """The four states the gate distinguishes + the degraded sentinel.

    Mirrors `des.runtime.freshness.FreshnessVerdict.state` Literal one-for-one.
    The .value strings are what stderr JSON carries.
    """

    CUSTOMER_PYPI = "A"
    CUSTOMER_REPO_NEARBY = "B"
    DEVELOPER_FRESH = "C"
    DEVELOPER_STALE = "D"
    DEGRADED = "DEGRADED"


class FreshnessOptOut(str, Enum):
    """Legal values of NWAVE_FRESHNESS env var (§1.8 + DDD-10)."""

    ENFORCE = "enforce"
    SKIP = "skip"
    VERBOSE = "verbose"
    UNSET = "__unset__"  # sentinel meaning: do not set the env var at all
    EMPTY = ""  # explicit empty string (treated as ENFORCE per §1.8)
    UNKNOWN = "garbage"  # canonical "unrecognised value" representative


class GateVerdict(str, Enum):
    """What the gate decided to do — observable at the process boundary."""

    PROCEED = "proceed"
    REFUSE = "refuse"


# --- Source-tree shape (§1.4 install manifest input) ---------------------


class SourceTreeKind(str, Enum):
    """`source_kind` field in `_install_manifest.json` (§1.4)."""

    DEV_CHECKOUT = "dev-checkout"
    PRE_BUILT = "pre-built"
    WHEEL = "wheel"


# --- Slice-05: manifest corruption kinds (§1.3 DEGRADED row) -------------


class CorruptionKind(str, Enum):
    """Enumerable shapes of `_install_manifest.json` corruption (slice-05).

    Each kind maps to a stderr `reason` substring the gate cites when it
    REFUSES with state DEGRADED. The mapping is the SUT contract under test;
    the test fixture writes the named corruption shape, the production code
    must classify + emit the matching substring.

    The four kinds form a closed enumerable set (Mandate 11: layer-3 sad
    paths are example-based, not PBT-generated).
    """

    UNKNOWN_SCHEMA_VERSION = "unknown_schema_version"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    NON_JSON_CONTENT = "non_json_content"
    EMPTY_FILE = "empty_file"


# --- Frozen probe dataclasses --------------------------------------------


@dataclass(frozen=True)
class InstalledPathProbe:
    """A handle on a synthetic installed `~/.claude/lib/python/des/` tree.

    Wraps a tmp_path-scoped directory laid out like the real installed
    package. Tests build one of these via `installed_tree_factory`.
    """

    root: Path  # the `des/` package root inside lib/python/
    has_manifest: bool
    manifest_path: Path  # may not exist when has_manifest is False


@dataclass(frozen=True)
class RepoPathProbe:
    """A handle on the `src/des/` source tree the gate compares against.

    May be `present=False` to model the customer scenario (no repo on host).
    """

    source_tree: Path | None
    present: bool


@dataclass(frozen=True)
class GateInvocationOutcome:
    """Observable outcome of one `python -c 'import des.cli'` (or CLI) spawn.

    The universe `assert_state_delta` tests assert against is built from this
    dataclass's port-exposed fields: exit_code, stderr_event, stderr_state.
    Internal subprocess plumbing (Popen handle, stdin file) is NEVER in the
    universe.
    """

    exit_code: int
    stderr_text: str
    stderr_event: str | None  # parsed `event` field from structured line
    stderr_state: str | None  # parsed `state` field, when present
    verdict: GateVerdict


# --- Install manifest (§1.4 schema, slice-02) ----------------------------


@dataclass(frozen=True)
class InstallManifest:
    """Parsed contents of `~/.claude/lib/python/des/_install_manifest.json`.

    Mirrors §1.4 schema (8 fields). All fields port-exposed observables —
    nothing internal to the install plugin appears here. The manifest is
    written by `DESPlugin._install_des_module` (slice-02 extension) and read
    by `RepoSourceProbe` at runtime.

    `tree_hash` is the SHA-256 prefix-tagged form ("sha256:...") computed via
    §1.6 canonical normalisation against the post-import-rewrite content.
    """

    schema_version: int
    installed_version: str
    installed_at_iso: str
    source_tree: str
    source_commit: str
    source_dirty: bool
    source_kind: str  # SourceTreeKind.value — kept as str for raw JSON shape
    tree_hash: str


@dataclass(frozen=True)
class InstalledTree:
    """A real `lib/python/des/` tree just laid down by the install plugin.

    Wraps the post-install directory plus its parsed manifest. Tests built
    against this dataclass observe both the on-disk shape AND the manifest
    schema. The manifest is parsed at construction time (eager — a missing
    or malformed manifest is itself the failure mode under test, captured
    by `manifest=None`).
    """

    package_root: Path  # the `des/` package root inside the install prefix
    manifest_path: Path  # `<package_root>/_install_manifest.json`
    manifest: InstallManifest | None  # None when the file is absent / malformed


__all__ = [
    "CorruptionKind",
    "FreshnessOptOut",
    "FreshnessState",
    "GateInvocationOutcome",
    "GateVerdict",
    "InstallManifest",
    "InstalledPathProbe",
    "InstalledTree",
    "RepoPathProbe",
    "SourceTreeKind",
]
