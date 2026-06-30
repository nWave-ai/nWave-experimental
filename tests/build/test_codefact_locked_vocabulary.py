"""Cross-tier Published-Language byte-lock guard (ADR-CA-001 D2, ADR-LA-001 §7 analogue).

The arch-tier conformance guard that mechanically protects the cross-tier byte-lock
ratified with the SF team 2026-06-14. It asserts the token set the OSS production
code SERIALIZES — the 5 capability ids + the ``{provider, confidence, reason_code}``
value vocabularies — is **byte-identical** to the committed
``tests/build/fixtures/locked-vocabulary.json`` fixture.

An OSS edit that renames ``binding-resolved -> precise``, adds a 6th ``confidence``
label, or drifts a capability id makes the guard RED — so a future OSS edit cannot
silently erode the SF-shared vocabulary (R2, Critical/cross-tier).

Auto-discovered by the existing ``run_contract_gate._arch_invariant_paths`` glob
(it returns the ``tests/build/`` directory; a new file here is picked up
automatically — no change to ``_arch_invariant_paths`` itself).

Earned-Trust self-application (Principle 13): the guard is itself probed — the
``test_byte_lock_guard_*`` meta-tests below prove the pristine vocabulary PASSES
and a planted-drift variant makes the guard RED. AT-4 of the slice-01 acceptance
suite drives the SAME ``assert_locked_vocabulary_unchanged`` callable.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.ports.code_fact_port import (
    STABLE_CORE_CAPABILITY_IDS,
    Confidence,
    Provider,
    ReasonCode,
)


# tests/build/<this file> -> parents[2] = REPO_ROOT
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED_FIXTURE = (
    _REPO_ROOT / "tests" / "build" / "fixtures" / "locked-vocabulary.json"
)


def serialize_locked_vocabulary() -> dict[str, list[str]]:
    """The OSS-serialized LOCKED token set, derived from the PRODUCTION port enums.

    This is the single source the guard compares the committed fixture against —
    the production capability ids + the ``{provider, confidence, reason_code}``
    value vocabularies (ADR-LA-001 §2/§5a), kebab-lowercase, sorted for a stable,
    byte-comparable serialization.
    """
    return {
        "capability_ids": sorted(STABLE_CORE_CAPABILITY_IDS),
        "providers": sorted(member.value for member in Provider),
        "confidences": sorted(member.value for member in Confidence),
        "reason_codes": sorted(member.value for member in ReasonCode),
    }


def assert_locked_vocabulary_unchanged(
    *, fixture_path: Path | str | None = None
) -> None:
    """Assert the committed fixture is byte-identical to the production token set.

    Raises ``AssertionError`` (the guard goes RED) when the ``fixture_path`` token
    set diverges from the production serialization — a renamed / added / dropped
    LOCKED token. ``fixture_path`` defaults to the committed
    ``tests/build/fixtures/locked-vocabulary.json``; AT-4's self-probe passes a
    planted-drift variant to prove the guard catches drift.
    """
    fixture = Path(fixture_path) if fixture_path is not None else _COMMITTED_FIXTURE
    committed = json.loads(fixture.read_text(encoding="utf-8"))
    produced = serialize_locked_vocabulary()
    if committed != produced:
        raise AssertionError(
            "the cross-tier-LOCKED Published Language (ADR-LA-001 §2/§5a, ratified "
            "with SF 2026-06-14) has DRIFTED: the committed locked-vocabulary fixture "
            f"{fixture} is no longer byte-identical to the OSS-serialized token set. "
            f"committed={committed!r} produced={produced!r}. A rename / addition / "
            "drop of a LOCKED capability id / provider / confidence / reason_code "
            "breaks the byte-lock with the SF tier (C1, R2). Revert the drift or "
            "re-ratify the Published Language cross-tier before editing the fixture."
        )


# ---------------------------------------------------------------------------
# Earned-Trust self-probe (Principle 13): the guard is itself tested.
# ---------------------------------------------------------------------------


def test_byte_lock_guard_passes_on_pristine_vocabulary() -> None:
    """The committed fixture is byte-identical to the production tokens -> PASS."""
    assert_locked_vocabulary_unchanged()


def test_committed_fixture_matches_production_serialization() -> None:
    """The committed fixture content equals the production serialization exactly."""
    committed = json.loads(_COMMITTED_FIXTURE.read_text(encoding="utf-8"))
    assert committed == serialize_locked_vocabulary()


def test_byte_lock_guard_catches_planted_drift(tmp_path: Path) -> None:
    """A planted-drift variant (binding-resolved -> precise) MUST make the guard RED."""
    drifted = serialize_locked_vocabulary()
    drifted["confidences"] = sorted(
        "precise" if token == "binding-resolved" else token
        for token in drifted["confidences"]
    )
    drifted_path = tmp_path / "drifted-locked-vocabulary.json"
    drifted_path.write_text(json.dumps(drifted, indent=2), encoding="utf-8")

    raised = False
    try:
        assert_locked_vocabulary_unchanged(fixture_path=drifted_path)
    except AssertionError:
        raised = True
    assert raised, (
        "the byte-lock guard must go RED on a planted-drift vocabulary variant"
    )
