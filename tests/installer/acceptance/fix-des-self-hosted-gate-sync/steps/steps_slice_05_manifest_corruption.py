"""Step bodies for slice-05 manifest-corruption-DEGRADED ATs.

Layer: 3 (subprocess against tmp_path-installed `des/` tree with a malformed
`_install_manifest.json`) — per Mandate 11 layer-3 sad paths are enumerated
examples, NEVER PBT-generated. The four corruption kinds form a closed set
captured as Scenario Outline rows (ADR-028 D2-bis coupled by single SUT
classifier method per row).

Mandate-12: every step body is ≤2 statements, ends in
`freshness_probe.<method>(...)` or a sibling SSOT helper, contains no
control flow. Business logic lives in `FreshnessProbeFixture.corrupt_manifest`
(conftest.py) which writes the named corruption shape; the gate's classifier
under test lives in production code (`RepoSourceProbe._read_install_manifest`).

Mandate 8: the verdict-pair assertion (exit_code, verdict) is delegated to
slice-01's SSOT `@then("the freshness gate REFUSES the invocation with exit
code 78")` step body — narrowed VERDICT_UNIVERSE shared across slices. The
slice-02 `@then(parsers.parse("the gate reports state {state_letter}"))` SSOT
handles the DEGRADED stderr state assertion. This module adds ONE new
@given (corruption kind selector) and ONE new @then (reason substring
assertion) — minimum surface to express the new behavioural contract.

Reused step decorators (no shadowing, per Mandate-12 cross-slice SSOT):

* "a synthetic installed DES tree at the standard install path"        — slice-01
* "the operator imports `des.cli` against that installed tree"          — slice-01
* "the freshness gate REFUSES the invocation with exit code 78"         — slice-01
* "the gate reports state {state_letter}"                              — slice-02
  (slice-02's parametrized step handles DEGRADED uniformly via FreshnessState)

NEW step decorators introduced here:

* @given(parsers.parse("the installed tree has a malformed manifest of kind {kind}"))
* @then(parsers.parse("the refusal reason includes the substring {substring}"))
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

from pytest_bdd import given, parsers, then
from steps.domain_types import CorruptionKind


# --- Given ----------------------------------------------------------------


@given(parsers.parse("the installed tree has a malformed manifest of kind {kind}"))
def given_installed_tree_has_malformed_manifest(
    freshness_probe, state, tmp_path, kind
) -> None:
    # Two statements — first builds the synthetic tree (no manifest yet);
    # second overwrites with the requested corruption shape. Both delegate
    # to FreshnessProbeFixture services; no business logic in the step.
    state["installed"] = freshness_probe.build_installed_tree(
        state.get("installed_tmp_root", tmp_path), with_manifest=False
    )
    state["installed"] = freshness_probe.corrupt_manifest(
        state["installed"], kind=CorruptionKind(kind)
    )


# --- When -----------------------------------------------------------------
#
# The "When the operator imports `des.cli` against that installed tree" step
# is registered by slice-01 and resolves against the SAME `state["installed"]`
# this module populates. No new @when decorator needed (Mandate-12 SSOT —
# reuse).


# --- Then -----------------------------------------------------------------


@then(parsers.parse("the refusal reason includes the substring {substring}"))
def then_refusal_reason_includes_substring(state, substring) -> None:
    _assert_stderr_contains_substring(state, expected=substring)


# --- Internal helpers (pure, no business logic) --------------------------


def _assert_stderr_contains_substring(state, *, expected: str) -> None:
    """Assert the refusal reason on stderr contains the expected substring.

    Sibling of slice-04's `_assert_stderr_cites_unrecognised`: both inspect
    the stderr text for a domain-readable explanation. Kept as a traditional
    assertion (universe-guard at layer 3 is OPTIONAL per the
    `Layered Test Discipline` matrix; the verdict pair is already universe-
    bound by slice-01's SSOT `then_gate_refuses_exit_78`).

    The match is case-insensitive on the haystack to absorb capitalisation
    drift across production reason strings ("Schema_version mismatch" vs
    "schema_version mismatch"). The needle is lower-cased before comparison.
    """
    stderr = getattr(state.get("outcome"), "stderr_text", "") or ""
    needle = expected.lower()
    assert needle in stderr.lower(), (
        f"expected refusal reason on stderr to include substring "
        f"{expected!r}; got stderr={stderr!r}"
    )
