"""Domain types for the whole-tree resolution arch-net (ADR-FLOW-011 D7, Mandate-12 c1).

The net guards the runner-aware whole-tree routing: every whole-tree contract-gate
mode must route through a whole-tree runner RESOLVER before it reaches any
pytest-bound leg. TWO resolvers are valid (one per mode family) -- the RUN router
for the run-suite mode and the DIGEST router for the three digest modes; routing
via EITHER satisfies the invariant. The nouns below are the scan's typed vocabulary.

WHY this matters: the feature-scoped path is already runner-aware
(`_maybe_route_through_cargo`); the whole-tree modes were never wired to
resolution (#73). #73 DELIVER wired the RUN router into `_mode_run_suite`;
slice-02 wired the DIGEST router (`_maybe_route_digest_through_runner`) into the
three digest modes. This static rule prevents a NEW whole-tree mode from quietly
hardcoding pytest again -- it must route through ONE of the two resolvers first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NewType


# Repo root from THIS file: .../tests/des/acceptance/<dir>/steps/<this>.py -> 5 up.
REPO_ROOT: Path = Path(__file__).resolve().parents[5]

# The scanned subject: the whole-tree contract-gate module (the shipped source).
WHOLE_TREE_GATE_SOURCE: Path = (
    REPO_ROOT / "src" / "des" / "cli" / "run_contract_gate.py"
)

# The four whole-tree mode functions (no --feature-id) the gate dispatches to.
# Source: run_contract_gate.main (the four `args.*` branches that are NOT
# --feature-id / --inprocess-exemplar / --run-suite).
WHOLE_TREE_MODES: frozenset[str] = frozenset(
    {
        "_mode_run_suite",
        "_mode_print_digest",
        "_mode_committed_scope_digest",
        "_mode_verify_gate_scope",
    }
)

# The whole-tree runner RESOLVERS a mode preamble may wire to resolve the runner
# before any pytest leg (ADR-FLOW-011 D3, mirrors `_maybe_route_through_cargo`).
# TWO equally-valid routers exist, one per mode family:
#   * the RUN router (`_maybe_route_through_runner_whole_tree`) for the run-suite
#     mode -- wired by #73 DELIVER;
#   * the DIGEST router (`_maybe_route_digest_through_runner`) added by slice-02
#     for the three digest modes (print-digest / committed-scope / verify-gate-scope).
# BOTH call `resolve_runner` and route/degrade for a non-Python target, so a mode
# preceding its pytest leg with EITHER is correctly runner-routed. The net must
# recognize both, else it false-positives the digest modes as "unrouted".
WHOLE_TREE_RUN_RESOLVER: str = "_maybe_route_through_runner_whole_tree"
WHOLE_TREE_DIGEST_RESOLVER: str = "_maybe_route_digest_through_runner"
WHOLE_TREE_RESOLVERS: frozenset[str] = frozenset(
    {WHOLE_TREE_RUN_RESOLVER, WHOLE_TREE_DIGEST_RESOLVER}
)

# Back-compat alias: the RUN router name retained for the human-readable reason
# strings on UnroutedMode (the canonical preamble call DELIVER first wired).
WHOLE_TREE_RESOLVER: str = WHOLE_TREE_RUN_RESOLVER

# The pytest-bound legs a whole-tree mode reaches. A call to ANY of these in a
# mode body, with no preceding resolver call, is the leak the net catches.
# Source: tsunami `callers_of pytest_interpreter` + the digest helpers the modes
# invoke (run_contract_gate.py:{231,687} + the committed-scope digest workers).
PYTEST_BOUND_LEGS: frozenset[str] = frozenset(
    {
        "_collect_scope",
        "_run_contract_suite",
        "_committed_scope_digest_quiet",
        "_committed_scope_digest_value",
        "_committed_scope_digest",
        "pytest_interpreter",
    }
)

# A "<mode>:<line>" coordinate naming where a whole-tree mode reached a pytest leg
# without a preceding runner resolution (the human-readable leak site).
UnroutedSite = NewType("UnroutedSite", str)


@dataclass(frozen=True)
class UnroutedMode:
    """One whole-tree mode that reaches a pytest-bound leg with no preceding resolver.

    The keystone observable: ``mode`` reaches ``leg`` at ``leg_line`` but the
    whole-tree resolver is absent from the body (``resolver_line is None``) or
    appears only AFTER the leg (``resolver_line > leg_line``).
    """

    mode: str
    leg: str
    leg_line: int
    resolver_line: int | None

    @property
    def site(self) -> UnroutedSite:
        """The ``<mode>:<leg-line>`` coordinate (stable across machines)."""
        return UnroutedSite(f"{self.mode}:{self.leg_line}")

    @property
    def reason(self) -> str:
        resolvers = " / ".join(f"`{r}(`" for r in sorted(WHOLE_TREE_RESOLVERS))
        if self.resolver_line is None:
            return f"no whole-tree runner resolver ({resolvers}) call in `{self.mode}` body"
        return (
            f"a whole-tree runner resolver ({resolvers}) at line {self.resolver_line} "
            f"appears AFTER the pytest-bound `{self.leg}(` at line {self.leg_line}"
        )
