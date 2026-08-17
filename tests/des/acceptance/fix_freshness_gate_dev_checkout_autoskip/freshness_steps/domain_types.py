"""Domain types for fix-freshness-gate-dev-checkout-autoskip acceptance tests.

Mandate-12 (SSOT via Types + Services + DSL): every domain noun the slice-01
.feature scenarios speak lives here as a typed enum or frozen dataclass. Step
methods and composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Reuses semantics from `tests/installer/acceptance/fix-des-self-hosted-gate-sync/
steps/domain_types.py` (the sibling freshness-gate suite) to keep the
cross-feature vocabulary aligned, but lives independently so this feature's
slice can DELIVER + COMMIT without dragging the sibling tree's 5-slice
substrate into pre-commit scope (friction #15 mitigation).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CheckoutAdjacency(str, Enum):
    """Whether the operator's CWD looks like a developer git checkout.

    This is the structural detector THIS BUGFIX introduces — fired BEFORE the
    four-state classification in `assert_fresh_or_explain`. The .value strings
    are the human-readable Gherkin phrases the step decorators parse.
    """

    DEV_CHECKOUT = "developer checkout with a `.git` directory present"
    CUSTOMER_HOST = "customer host with no checkout adjacency"


class GateVerdict(str, Enum):
    """What the gate decided at the process boundary — observable via exit code."""

    PROCEED = "proceed"
    REFUSE = "refuse"


class StructuredEventName(str, Enum):
    """The structured stderr event names the gate emits at distinct outcomes.

    `autoskipped` is the opt-in diagnostic this bugfix adds. It is
    DISTINCT from the pre-existing `skipped` (operator-set `NWAVE_FRESHNESS=
    skip`) so an operator can ask why the gate did not refuse without adding
    noise to every successful machine-readable command.
    """

    REFUSED = "des.runtime.freshness.refused"
    SKIPPED = "des.runtime.freshness.skipped"  # operator-set, pre-existing
    AUTOSKIPPED = "des.runtime.freshness.autoskipped"  # structural, NEW
    PROCEED = "des.runtime.freshness.proceed"  # state C, pre-existing


# --- Frozen probe dataclasses --------------------------------------------


@dataclass(frozen=True)
class InstalledTreeProbe:
    """A handle on a synthetic installed `~/.claude/lib/python/des/` tree.

    Wraps a tmp_path-scoped directory laid out like the real installed
    package. The freshness chain's production files are copied from `src/des/`
    so the gate's import-time wiring runs against the SAME bytes as production.
    """

    root: Path  # the `des/` package root inside lib/python/
    has_manifest: bool


@dataclass(frozen=True)
class CheckoutProbe:
    """A handle on a synthetic developer checkout (or absence thereof).

    `cwd` is the directory the subprocess will set as its current working
    directory. When `adjacency` is DEV_CHECKOUT, `cwd` contains a `.git/`
    subdirectory (the structural marker the bugfix detects). When CUSTOMER_HOST,
    `cwd` is a plain directory with no `.git/` adjacency.
    """

    cwd: Path
    adjacency: CheckoutAdjacency


@dataclass(frozen=True)
class GateInvocationOutcome:
    """Observable outcome of one `python -c 'import des.cli'` subprocess spawn.

    Universe entries that `assert_state_delta` tracks are built from THIS
    dataclass's port-exposed fields: `exit_code`, `verdict`, `stderr_event`.
    Internal subprocess plumbing (Popen handle, env dict, stdin file) is
    NEVER in the universe (Mandate 8 — port-exposed observables only).
    """

    exit_code: int
    stderr_text: str
    stderr_event: str | None  # parsed `event` field from the structured line
    verdict: GateVerdict


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

ADJACENCY_BY_PHRASE: dict[str, CheckoutAdjacency] = {
    a.value: a for a in CheckoutAdjacency
}


__all__ = [
    "ADJACENCY_BY_PHRASE",
    "CheckoutAdjacency",
    "CheckoutProbe",
    "GateInvocationOutcome",
    "GateVerdict",
    "InstalledTreeProbe",
    "StructuredEventName",
]
