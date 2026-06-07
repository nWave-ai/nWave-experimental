"""Domain types for oss-spine-watchdog slice-01 (collection-health precheck).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-01 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-01 SUT = the COLLECTION-HEALTH PRECHECK driving port — the contract gate's
`--collect-only` collection probe (DESIGN OQ-1 RESOLVED: EXTEND
`run_contract_gate --collect-only`). Before the G_COMMIT exit gate can `block` on
E2 (which, on a collection crash, makes the harness re-fire the agent forever —
the 68-min stale-loop root, RCA #68), the precheck verifies the whole-tree
contract suite COLLECTS cleanly. A collection crash → a LOUD SINGLE failure that
NAMES the broken module (KPI-3), not a silent opaque re-fire.

Vocabulary mirrors the sibling control-plane slice-01
(`tests/des/acceptance/des_spine_control_plane_ssot/steps/domain_types.py`) —
same Verdict / probe-outcome shape — but lives independently so this feature's
slice DELIVER+COMMITs without dragging the sibling tree into pre-commit scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SuiteCollectability(str, Enum):
    """Whether the synthetic project's contract suite collects cleanly.

    CLEANLY is the discriminator / no-false-positive case — a suite whose
    contract-marked tests all import fine. The precheck must PASS it (no spurious
    loud failure), so the gate proceeds normally.

    COLLECTION_CRASHES is the #68 root condition — a contract test module with an
    import-time crash (a broken import). pytest collection aborts (exit 2), NOT a
    normal red test (exit 1). The precheck must turn this into a LOUD SINGLE
    failure NAMING the crashing module (KPI-3), terminating — never the silent
    opaque re-fire that kept E2 failing for 68 minutes.

    The `.value` strings are the human-readable Gherkin phrases the decorators
    parse (Mandate-12 DSL emergence).
    """

    CLEANLY = "collects cleanly"
    COLLECTION_CRASHES = "fails to collect because a test module has a broken import"


class FreshnessOptOut(str, Enum):
    """The `NWAVE_FRESHNESS` env state the precheck subprocess inherits.

    The precheck's whole point (DISCUSS D-7 / DESIGN OQ-1 / DEVOPS DV-4) is
    ENV-PARITY: it runs the whole-tree contract-suite collection WITHOUT the
    `NWAVE_FRESHNESS=skip` mask, so an import-time hook regression cannot hide
    under the operator's pipenv `.env` (the masked-collection was RCA #68 P1-B —
    the spine's first unmasked run was the bug-finder).

    UNSET   → the operator did not set the skip (the plain case).
    SKIP    → the operator's env carries `NWAVE_FRESHNESS=skip` (the pipenv `.env`
              topology). A collection CRASH is a pytest-collection failure, which
              is independent of the freshness gate — the precheck must STILL detect
              and name it even with skip set. This is the env-parity earned-trust
              probe that reproduces the RCA #68 P1-B masked-collection shape.
    """

    UNSET = "no freshness opt-out"
    SKIP = "the freshness opt-out set in the environment"


class PrecheckVerdict(str, Enum):
    """What the collection-health precheck decided — observable via exit code.

    PROCEED is the clean-collection outcome: the suite collects, the precheck
    passes (exit 0), the gate proceeds normally — NO loud failure.

    LOUD_NAMED is the collection-crash outcome: the precheck emits a single LOUD
    failure (exit 2) that NAMES the crashing module — the slice-01 walking-skeleton
    outcome + the KPI-3 assertion. It is NOT the silent re-fire loop.

    Note: slice-01 is the PROBE, not the terminal emission. The terminal
    (`SliceCommitBlockedTerminal` / non-block return) is slice-02/03 territory.
    Slice-01's observable is the precheck's verdict (exit 2 + named module vs
    exit 0 + digest) on its real driving-port surface — the contract-gate
    `--collect-only` CLI.
    """

    PROCEED = "proceed"  # exit 0 — suite collects, no loud failure
    LOUD_NAMED = "loud_named"  # exit 2 — collection crash, crashing module named


# --- Frozen probe / outcome dataclasses ----------------------------------


@dataclass(frozen=True)
class ContractSuiteProbe:
    """A handle on a synthetic project whose contract suite the precheck collects.

    Wraps a tmp_path-scoped project root laid out like a real DES project: a
    `conftest.py` that marks every collected item with the contract marker
    (`unit`), plus one or more contract-marked test modules under `tests/`. The
    `collectability` records whether those modules import cleanly or carry an
    import-time crash — the seam the collection precheck interrogates.

    `crashing_module_rel` is the POSIX-relative path of the module whose import
    crashes (None for a clean suite). It is the identifier KPI-3 demands the
    precheck name in its loud failure.
    """

    project_root: Path
    collectability: SuiteCollectability
    crashing_module_rel: str | None


@dataclass(frozen=True)
class PrecheckOutcome:
    """Observable outcome of ONE real collection-health precheck invocation.

    The driving port is the contract-gate `--collect-only` CLI subprocess
    (Layer-3). The universe entries `assert_state_delta` tracks are built from
    THIS dataclass's port-exposed fields: `exit_code`, `crash_named`,
    `named_module`. Internal plumbing (Popen handle, env dict, raw stderr chatter,
    worker marker bytes) is NEVER in the universe (Mandate 8 — port-exposed
    observables only).

    - `exit_code`      — the precheck process exit code (0 = collects, 2 =
                         collection crash, 1 = a normal red test which is NOT a
                         collection crash and must not be conflated).
    - `crash_named`    — True iff the precheck's failure payload carries a
                         non-empty crashing-module identifier (the KPI-3 signal).
    - `named_module`   — the crashing-module identifier the payload named (None
                         when no collection crash / not named).
    - `verdict`        — the typed PrecheckVerdict derived from the exit code.
    - `stdout_payload` — the parsed single-line JSON event the gate emits on a
                         collection crash (`MalformedInput`), or None on success.
    - `digest`         — the bare gate-scope digest printed on a clean collection
                         (None on crash). Proves the clean precheck PROCEEDs.
    """

    exit_code: int
    crash_named: bool
    named_module: str | None
    verdict: PrecheckVerdict
    stdout_payload: dict | None
    digest: str | None


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

COLLECTABILITY_BY_PHRASE: dict[str, SuiteCollectability] = {
    c.value: c for c in SuiteCollectability
}
OPT_OUT_BY_PHRASE: dict[str, FreshnessOptOut] = {o.value: o for o in FreshnessOptOut}


__all__ = [
    "COLLECTABILITY_BY_PHRASE",
    "OPT_OUT_BY_PHRASE",
    "ContractSuiteProbe",
    "FreshnessOptOut",
    "PrecheckOutcome",
    "PrecheckVerdict",
    "SuiteCollectability",
]
