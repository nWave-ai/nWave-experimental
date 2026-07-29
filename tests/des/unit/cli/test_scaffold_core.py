"""Unit tests for `des.cli._scaffold_core` -- the shared exists-decision +
verdict-envelope primitives the scaffold family (charter-scaffold,
examine-fixture, feature-end-preconditions-scaffold, flavor-scaffold) now
imports instead of hand-rolling (D49, mikado 2026-07-29)."""

from __future__ import annotations

import json

import pytest

from des.cli._scaffold_core import (
    ScaffoldDegradeError,
    decide_on_exists,
    emit_scaffold_verdict,
)
from des.cli.validate_feature_delta import VERDICT_ACCEPTED


# --- decide_on_exists -------------------------------------------------------


def test_fresh_target_always_writes_regardless_of_policy():
    for policy in ("skip", "refuse", "rebuild"):
        assert (
            decide_on_exists(target_exists=False, policy=policy) == "write"  # type: ignore[arg-type]
        )


def test_existing_target_skip_policy_skips():
    assert decide_on_exists(target_exists=True, policy="skip") == "skip"


def test_existing_target_refuse_policy_refuses():
    assert decide_on_exists(target_exists=True, policy="refuse") == "refuse"


def test_existing_target_rebuild_policy_rebuilds():
    assert decide_on_exists(target_exists=True, policy="rebuild") == "rebuild"


def test_force_overrides_refuse_to_write():
    assert decide_on_exists(target_exists=True, policy="refuse", force=True) == "write"


def test_force_overrides_skip_to_write():
    """`force` is not `flavor-scaffold`-specific -- it overrides ANY declared
    policy, not just `"refuse"` (mutation-guard: a `policy == "refuse"` check
    gated on `force` would silently NOT override skip/rebuild)."""
    assert decide_on_exists(target_exists=True, policy="skip", force=True) == "write"


def test_force_is_a_no_op_on_a_fresh_target():
    assert decide_on_exists(target_exists=False, policy="refuse", force=True) == "write"


# --- emit_scaffold_verdict ---------------------------------------------------


def test_emit_scaffold_verdict_prints_the_payload_as_one_json_line(capsys):
    payload = {"feature_id": "demo", "verdict": VERDICT_ACCEPTED, "detail": "ok"}
    emit_scaffold_verdict(payload)
    out = capsys.readouterr().out
    assert out == json.dumps(payload) + "\n"


def test_emit_scaffold_verdict_returns_zero_on_accepted():
    exit_code = emit_scaffold_verdict({"verdict": VERDICT_ACCEPTED, "detail": "ok"})
    assert exit_code == 0


def test_emit_scaffold_verdict_returns_one_on_any_non_accepted_verdict():
    exit_code = emit_scaffold_verdict(
        {"verdict": "missing-feature-delta", "detail": "nope"}
    )
    assert exit_code == 1


def test_emit_scaffold_verdict_returns_one_when_verdict_key_is_absent():
    """Mutation-guard: `payload.get("verdict")` (not `payload["verdict"]`) --
    a malformed payload degrades LOUD (non-zero) rather than raising
    `KeyError`, matching every scaffold's own degrade-on-failure contract."""
    exit_code = emit_scaffold_verdict({"detail": "no verdict key at all"})
    assert exit_code == 1


def test_emit_scaffold_verdict_respects_a_custom_accepted_token():
    exit_code = emit_scaffold_verdict({"verdict": "custom-ok"}, accepted="custom-ok")
    assert exit_code == 0


# --- ScaffoldDegradeError ----------------------------------------------------


def test_scaffold_degrade_error_carries_verdict_and_detail():
    error = ScaffoldDegradeError("git-operation-failed", "git commit failed: boom")
    assert error.verdict == "git-operation-failed"
    assert error.detail == "git commit failed: boom"


def test_scaffold_degrade_error_is_raisable_and_catchable():
    with pytest.raises(ScaffoldDegradeError) as excinfo:
        raise ScaffoldDegradeError("x", "y")
    assert excinfo.value.verdict == "x"
    assert excinfo.value.detail == "y"


# --- no drift between this module's accepted-token literal and the SSOT ----


def test_scaffold_core_accepted_matches_validate_feature_delta():
    """`_scaffold_core`'s default `accepted` token is NOT imported from
    `validate_feature_delta.VERDICT_ACCEPTED` (this module stays free of a
    dependency on the feature-delta parser -- see module docstring); this
    test is the mechanical anti-drift guard for that choice, run every time
    either constant changes."""
    exit_code = emit_scaffold_verdict({"verdict": VERDICT_ACCEPTED})
    assert exit_code == 0
