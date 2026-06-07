"""Domain types for des-spine-control-plane-ssot slice-01 acceptance tests.

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-01 .feature scenarios speak lives here as a typed enum or frozen
dataclass. Step methods + composition consume these typed parameters; raw `str`
parameters are avoided wherever a domain enum exists.

Slice-01 SUT = the HOOK ENTRYPOINT (Gap A wiring + DV-2 suppress_git_autoskip).
Vocabulary is aligned with the sibling
`tests/des/acceptance/fix_freshness_gate_dev_checkout_autoskip/freshness_steps/
domain_types.py` (the autoskip suite) — same GateVerdict / event-name semantics —
but lives independently so this feature's slice DELIVER+COMMITs without dragging
the sibling tree into pre-commit scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class InstallDrift(str, Enum):
    """Whether the installed `des/` tree matches the repo source it was built from.

    DRIFTED is the #58 condition — the dev edited `src/des/` after install, so the
    installed copy enforces stale code. MATCHES is a fresh reinstall (the positive
    discriminator that proves the gate compares CONTENT, not `.git/` presence).
    CUSTOMER is the install-fidelity baseline — manifest `source_tree` unreachable,
    state A, silent PROCEED (no drift comparison possible nor wanted).
    """

    DRIFTED = "code has drifted from the repository source"
    MATCHES = "code matches the repository source"
    CUSTOMER = "customer host with the source tree not reachable"


class CheckoutAdjacency(str, Enum):
    """Whether the operator's CWD looks like a developer git checkout.

    DEV_CHECKOUT is the #58 topology trap: the `.git/`-adjacency autoskip
    (`freshness.py:122`) short-circuits the gate here UNLESS the hook site passes
    `suppress_git_autoskip=True` (DV-2). CUSTOMER_HOST has no `.git/` adjacency.
    The `.value` strings are the human-readable Gherkin phrases the decorators
    parse. GIT-FREE: a `.git/` directory is constructed as a filesystem fixture,
    never via a `git` subprocess (Mandate-13 invariant 5).
    """

    DEV_CHECKOUT = "developer checkout with a `.git` directory present"
    CUSTOMER_HOST = "customer host with no checkout adjacency"


class FreshnessOptOut(str, Enum):
    """The `NWAVE_FRESHNESS` operator opt-out state for one hook invocation."""

    UNSET = "unset"  # default — the gate runs
    SKIP = "skip"  # NWAVE_FRESHNESS=skip — short-circuit ahead of everything


class HookVerdict(str, Enum):
    """What the hook decided at the process boundary — observable via exit code.

    Slice-01 is DEGRADE-LOUD (DISCUSS D1): the hook ALWAYS PROCEEDs (exit 0) on a
    freshness verdict — it never hard-blocks the session. A stale install yields
    PROCEED + a LOUD warning; a fresh/customer install yields PROCEED + silence.
    REFUSE is NOT a slice-01 hook outcome (the CLI keeps exit-78; the hook does
    not) — it exists in the enum only to make the "no REFUSE on the hook path"
    invariant nameable.
    """

    PROCEED = "proceed"
    REFUSE = "refuse"  # CLI-only; asserted ABSENT on the slice-01 hook path


class StructuredEventName(str, Enum):
    """The structured stderr event names the hook freshness gate may emit.

    `install-freshness.stale` is the NEW LOUD warning this slice adds for the #58
    repo-moved-on (Gap B) drift. It is DISTINCT from the pre-existing operator-set
    `skipped` and the coarse `autoskipped` — so post-hoc audit answers "why did the
    spine run stale" (KPI 1/2). `proceed`/`autoskipped` are pre-existing.
    """

    STALE = "des.runtime.freshness.stale"  # NEW — the #58 LOUD warning (Gap B)
    SKIPPED = "des.runtime.freshness.skipped"  # operator NWAVE_FRESHNESS=skip
    AUTOSKIPPED = "des.runtime.freshness.autoskipped"  # `.git/` coarse (pre-existing)
    PROCEED = "des.runtime.freshness.proceed"  # state C dev-fresh (pre-existing)
    REFUSED = "des.runtime.freshness.refused"  # CLI REFUSE (NOT on the hook path)


# The persisted audit-log EventType name (DEVOPS DV-5) the stale warning writes to
# the JsonlAuditLogWriter SSOT (`audit-*.log` under the `AuditLogPathResolver` dir,
# serialized under the record's top-level `event` key). The hook freshness gate
# dual-emits: stderr (above) + this persisted record (the KPI-1 queryable sink read
# by JsonlAuditLogReader). NOT a separate `audit.jsonl` file (RELOOP_A).
HEALTH_GATE_INSTALL_FRESHNESS_STALE = "HEALTH_GATE_INSTALL_FRESHNESS_STALE"


# --- Frozen probe / outcome dataclasses ----------------------------------


@dataclass(frozen=True)
class InstalledSpineProbe:
    """A handle on a synthetic installed `~/.claude/lib/python/des/` spine tree.

    Wraps a tmp_path-scoped directory laid out like the real installed package,
    with a `_install_manifest.json` whose `source_tree` points at the synthetic
    repo-source tree. `drift` records how the installed content relates to that
    source — the seam the freshness probe interrogates.
    """

    installed_root: Path  # the `des/` package root inside lib/python/
    source_root: Path | None  # the synthetic repo `src/des` (None for CUSTOMER)
    drift: InstallDrift


@dataclass(frozen=True)
class CheckoutProbe:
    """A handle on a synthetic developer checkout (or absence thereof).

    `cwd` is the directory the hook subprocess sets as its working directory. When
    `adjacency` is DEV_CHECKOUT, `cwd` contains a `.git/` subdirectory (the #58
    autoskip trap the hook must suppress). GIT-FREE filesystem construction.
    """

    cwd: Path
    adjacency: CheckoutAdjacency


@dataclass(frozen=True)
class HookInvocationOutcome:
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

DRIFT_BY_PHRASE: dict[str, InstallDrift] = {d.value: d for d in InstallDrift}
ADJACENCY_BY_PHRASE: dict[str, CheckoutAdjacency] = {
    a.value: a for a in CheckoutAdjacency
}


__all__ = [
    "ADJACENCY_BY_PHRASE",
    "DRIFT_BY_PHRASE",
    "HEALTH_GATE_INSTALL_FRESHNESS_STALE",
    "CheckoutAdjacency",
    "CheckoutProbe",
    "FreshnessOptOut",
    "HookInvocationOutcome",
    "HookVerdict",
    "InstallDrift",
    "InstalledSpineProbe",
    "StructuredEventName",
]
