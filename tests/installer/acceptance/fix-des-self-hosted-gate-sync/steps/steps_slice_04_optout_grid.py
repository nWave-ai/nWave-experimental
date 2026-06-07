"""Step bodies for slice-04 NWAVE_FRESHNESS opt-out grid ATs.

Layer: 3 (subprocess + real install plugin against tmp_path) — per Mandate 11
this layer is example-only / parametrize-collapse; the opt-out grid is a
Scenario Outline (6 rows) + one named unknown-value sad path. PBT machinery
is intentionally NOT imported. ADR-028 D2-bis coupled justification recorded
in the slice-plan §5 row for slice-04.

Mandate-12: every step body is ≤2 statements, ends in
`freshness_probe.<method>(...)` or the SSOT-narrowed snapshot helper, and
contains no control flow. Business logic lives in `FreshnessProbeFixture`
(conftest.py) which delegates to the real production composition root
(`des.runtime.freshness.assert_fresh_or_explain` via subprocess).

Mandate 8: assertions go through `assert_state_delta(before, after, universe,
expected)` from `tests.common.state_delta`. The narrowed VERDICT_UNIVERSE
(`outcome.exit_code` + `outcome.verdict`) is the SSOT registered by
`steps_slice_01_walking_skeleton.py` for the PROCEED / REFUSE Gherkin
phrases; this module ADDS its own parameterized assertion vocabulary on top.

Reused step decorators (no shadowing, per Mandate-12 cross-slice SSOT):

* "a synthetic installed DES tree at the standard install path"        — slice-01
* "the operator imports `des.cli` against that installed tree"          — slice-01
* "the gate reports state {state_letter}"                              — slice-02
* "the freshness gate REFUSES the invocation with exit code 78"         — slice-01
* "the gate reports state DEGRADED"                                     — slice-02
  (slice-02's parameterized step subsumes the slice-01-deleted literal)

NEW step decorators introduced here:

* @given(parsers.parse("the installed tree is in install state {state}"))
* @given(parsers.parse("the environment variable NWAVE_FRESHNESS is set to {token}"))
* @then(parsers.parse("the freshness gate verdict is {verdict}"))
* @then("the refusal reason cites the unrecognised opt-out value")
"""

from __future__ import annotations

import sys
from pathlib import Path


# Match the kebab-case workaround in the sibling conftest.py — inject the
# feature root so `from steps.domain_types import ...` and
# `from conftest import ...` resolve against THIS feature's local modules.
_FEATURE_ROOT = Path(__file__).resolve().parent.parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from pytest_bdd import given, parsers, then  # noqa: E402
from steps.domain_types import (  # noqa: E402
    FreshnessOptOut,
    GateVerdict,
)

from tests.common.state_delta import (  # noqa: E402
    assert_state_delta,
    set_to,
)


# --- Universe (Mandate 8): port-exposed observables only -----------------
#
# Narrowed to the verdict pair: the trailing And-steps assert state/event
# stderr facets via the slice-02 parameterized step (`the gate reports
# state {state_letter}`) and the slice-04 unknown-value reason step below.

VERDICT_UNIVERSE = frozenset(
    {
        "outcome.exit_code",
        "outcome.verdict",
    }
)


def _verdict_snapshot(state: dict) -> dict:
    """Build a dict snapshot of the verdict universe from scenario state.

    Pure function. Returns sentinels (None) for unobserved keys so the
    before-snapshot is well-defined before any outcome is captured.
    """
    outcome = state.get("outcome")
    return {
        "outcome.exit_code": getattr(outcome, "exit_code", None),
        "outcome.verdict": getattr(outcome, "verdict", None),
    }


# --- Given ----------------------------------------------------------------


@given(parsers.parse("the installed tree is in install state {install_state}"))
def given_installed_tree_in_state(
    freshness_probe, state, tmp_path, install_state
) -> None:
    state["installed"] = freshness_probe.build_optout_grid_install(
        tmp_path, install_state=install_state
    )


@given(parsers.parse("the environment variable NWAVE_FRESHNESS is set to {token}"))
def given_environment_variable_nwave_freshness_is_set_to(state, token) -> None:
    state["opt_out"] = freshness_optout_from_token(token)


# --- When -----------------------------------------------------------------
#
# The "When the operator imports `des.cli` against that installed tree" step
# is registered by slice-01 and resolves against the SAME `state["installed"]`
# + `state.get("opt_out", FreshnessOptOut.UNSET)` keys this module populates.
# No new @when decorator needed (Mandate-12 SSOT — reuse).


# --- Then -----------------------------------------------------------------


@then(parsers.parse("the freshness gate verdict is {verdict_token}"))
def then_freshness_gate_verdict_is(state, verdict_token) -> None:
    expected_verdict = GateVerdict(verdict_token)
    expected_exit_code = 0 if expected_verdict is GateVerdict.PROCEED else 78
    after = _verdict_snapshot(state)
    assert_state_delta(
        before={k: state["before"][k] for k in VERDICT_UNIVERSE},
        after={k: after[k] for k in VERDICT_UNIVERSE},
        universe=VERDICT_UNIVERSE,
        expected={
            "outcome.exit_code": set_to(expected_exit_code),
            "outcome.verdict": set_to(expected_verdict),
        },
    )


@then("the refusal reason cites the unrecognised opt-out value")
def then_refusal_reason_cites_unrecognised_opt_out_value(state) -> None:
    _assert_stderr_cites_unrecognised(state)


# --- Internal helpers (pure, no business logic) --------------------------


# Token → enum map. Kept here (not in domain_types.py) because this mapping
# is purely a Gherkin Examples-cell convention — the production code never
# sees these tokens, only the env-var value the fixture sets. `empty` is the
# Gherkin convention for "the empty string" (pytest-bdd table cells cannot
# carry an explicit empty value unambiguously through `parsers.parse`).
_OPT_OUT_TOKEN_TO_ENUM = {
    "enforce": FreshnessOptOut.ENFORCE,
    "verbose": FreshnessOptOut.VERBOSE,
    "empty": FreshnessOptOut.EMPTY,
    "skip": FreshnessOptOut.SKIP,
    "garbage": FreshnessOptOut.UNKNOWN,
}


def freshness_optout_from_token(token: str) -> FreshnessOptOut:
    """Resolve an Examples-cell token to a FreshnessOptOut.

    Pure function — no I/O, no side effects. Raises KeyError on an
    unrecognised token so a typo in the Examples table fails loudly at
    Given-time rather than producing a silently-wrong env var.
    """
    return _OPT_OUT_TOKEN_TO_ENUM[token]


def _assert_stderr_cites_unrecognised(state) -> None:
    """Assert the refusal reason on stderr mentions the unrecognised opt-out.

    Sibling of slice-02's `_then_refusal_reason_cites_diverged_file_hash`:
    both inspect the stderr text for a domain-readable explanation. Kept as
    a traditional assertion (universe-guard at layer 3 is OPTIONAL per the
    `Layered Test Discipline` matrix; the verdict pair is already universe-
    bound by `then_freshness_gate_verdict_is`).
    """
    stderr = getattr(state.get("outcome"), "stderr_text", "") or ""
    lowered = stderr.lower()
    assert (
        "unrecognised" in lowered or "unrecognized" in lowered or "unknown" in lowered
    ), (
        f"expected refusal reason on stderr to cite the unrecognised opt-out value; "
        f"got stderr={stderr!r}"
    )
