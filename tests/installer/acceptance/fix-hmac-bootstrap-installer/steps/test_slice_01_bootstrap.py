"""Step definitions — slice-01: HMAC reviewer signing key bootstrap.

F-HMAC-BOOTSTRAP-INSTALLER slice-01. Layer 3 (subprocess / FS acceptance):
the production install pipeline is the driving port; the only driven ports
are the real filesystem (tmp_path target) and the NWAVE_REVIEWER_SIGNING_KEY
environment variable. Example-based walking-skeleton (Mandate 11) — 3 ATs
covering the credibility-blocker contract (fresh-install / idempotent-reinstall
/ env-var-override).

Step bodies delegate to `HmacBootstrapFixture` — a tmp_path-bound composition
root that exercises the production `ReviewerSigningPlugin` against an isolated
InstallContext (Mandate-12 criterion 3, ≤2 statements per body).

PROVENANCE NOTE — RED-status escalation. The orchestrator brief framed this
slice as RED because "the installer doesn't auto-provision yet". The
production `ReviewerSigningPlugin` is ALREADY shipped at
`scripts/install/plugins/reviewer_signing_plugin.py` and registered in
`scripts/install/install_nwave.py:393`. These ATs exercise the production
seam through the plugin's driving port; they will GREEN against current
master. They function as REGRESSION PINS on the credibility-blocker
acquirer-demo contract — preventing future drift, not driving DELIVER
implementation. See the dispatch escalation in the agent reply for the
recommended orchestrator action.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.common.state_delta import (
    assert_state_delta,
    set_to,
    unchanged,
)

from .composition import HmacBootstrapFixture, InstallObservation


scenarios("../slice-01-bootstrap-walking-skeleton.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HmacBootstrapFixture:
    """Production-wired bootstrap fixture rooted at an isolated tmp target."""
    monkeypatch.delenv("NWAVE_REVIEWER_SIGNING_KEY", raising=False)
    return HmacBootstrapFixture(target_root=tmp_path / "target")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured operator-observable surfaces across steps."""
    return {}


# --- AT1 Given -------------------------------------------------------------


@given("the operator has a fresh target directory with no nWave installation")
def given_fresh_target(fixture: HmacBootstrapFixture) -> None:
    # A no-op composition method — the tmp_path target is already empty by
    # construction. The step exists so the Gherkin reads as a business
    # precondition (Pillar 1).
    fixture.capture_surface()


@given("no signing key environment variable is set in the operator environment")
def given_no_env_key(fixture: HmacBootstrapFixture) -> None:
    fixture.clear_env_signing_key()


# --- AT2 Given (chained narrative — Pillar 2) ------------------------------


@given("the operator has a target with a previously provisioned reviewer signing key")
def given_previously_provisioned(
    fixture: HmacBootstrapFixture, result_box: dict[str, object]
) -> None:
    fixture.run_install_plugin_only()
    result_box["before"] = fixture.capture_surface()


# --- AT3 Given -------------------------------------------------------------


@given("the operator has set the signing key environment variable to an override value")
def given_env_key_set(fixture: HmacBootstrapFixture) -> None:
    fixture.set_env_signing_key("operator-supplied-override-value")


# --- When ------------------------------------------------------------------


@when("the operator runs the nWave install pipeline against the target")
def when_install(fixture: HmacBootstrapFixture, result_box: dict[str, object]) -> None:
    fixture.run_install_plugin_only()
    result_box["after"] = fixture.capture_surface()


@when("the operator re-runs the nWave install pipeline against the target")
def when_reinstall(
    fixture: HmacBootstrapFixture, result_box: dict[str, object]
) -> None:
    fixture.run_install_plugin_only()
    result_box["after"] = fixture.capture_surface()


# --- AT1 Then --------------------------------------------------------------


@then(
    "the target carries a reviewer signing key file with 64 hex characters of randomness"
)
def then_key_provisioned(
    fixture: HmacBootstrapFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_provisioned_surface(result_box["after"])  # type: ignore[arg-type]


@then(
    "the install verification reports the reviewer signing key as present at its path"
)
def then_verify_reports_present(result_box: dict[str, object]) -> None:
    observation: InstallObservation = result_box["after"]  # type: ignore[assignment]
    assert "reviewer signing key present" in observation.verify_message.lower()


@then("on POSIX the reviewer signing key file mode is restricted to the operator")
def then_posix_mode_restricted(result_box: dict[str, object]) -> None:
    observation: InstallObservation = result_box["after"]  # type: ignore[assignment]
    import os as _os

    if _os.name == "posix":
        assert observation.key_file_mode_bits == 0o600


# --- AT2 Then (state-delta over universe — Mandate 8) ----------------------


@then(
    "the reviewer signing key file is byte-identical to the previously provisioned key"
)
def then_key_byte_identical(
    fixture: HmacBootstrapFixture, result_box: dict[str, object]
) -> None:
    before: InstallObservation = result_box["before"]  # type: ignore[assignment]
    after: InstallObservation = result_box["after"]  # type: ignore[assignment]
    assert_state_delta(
        {
            "key_file.exists": before.key_file_exists,
            "key_file.bytes": before.key_file_bytes,
            "key_file.mode_bits": before.key_file_mode_bits,
        },
        {
            "key_file.exists": after.key_file_exists,
            "key_file.bytes": after.key_file_bytes,
            "key_file.mode_bits": after.key_file_mode_bits,
        },
        universe={"key_file.exists", "key_file.bytes", "key_file.mode_bits"},
        expected={
            "key_file.exists": set_to(True),
            "key_file.bytes": unchanged(),
            "key_file.mode_bits": unchanged(),
        },
        strict=True,
    )


@then("the reviewer signing key file mode bits are unchanged")
def then_mode_unchanged(result_box: dict[str, object]) -> None:
    before: InstallObservation = result_box["before"]  # type: ignore[assignment]
    after: InstallObservation = result_box["after"]  # type: ignore[assignment]
    assert before.key_file_mode_bits == after.key_file_mode_bits


# --- AT3 Then --------------------------------------------------------------


@then("the target carries no reviewer signing key file")
def then_no_key_file(
    fixture: HmacBootstrapFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_env_override_surface(result_box["after"])  # type: ignore[arg-type]


@then(
    "the install verification names the signing key environment variable as the key source"
)
def then_verify_names_env(result_box: dict[str, object]) -> None:
    observation: InstallObservation = result_box["after"]  # type: ignore[assignment]
    assert "NWAVE_REVIEWER_SIGNING_KEY" in observation.verify_message
