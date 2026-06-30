"""Step definitions -- S5: keyless installer + preserve-by-default.

oss-review-verdict-demotion slice-05. Layer 3 (subprocess / FS acceptance +
composition root): the production install surface is the driving port. Two
composition-root driving ports (Mandate 13):

  * `NWaveInstaller._create_plugin_registry(...)` -- the registered-plugin set
    + count (registry surface);
  * `scripts/install/install_nwave.py` as a real subprocess -- the full
    install pipeline (keyless install + preserve-by-default).

Step bodies delegate to `InstallerDemotionFixture` -- a tmp_path-bound
composition root -- and never inline logic (Mandate-12 criterion 3, <=2
statements ending in a composition call).

RED-for-the-right-reason (at tip, before S5 lands): the production registry
still carries `reviewer_signing` (count 8) and a fresh install still
provisions a key file. The walking-skeleton scenario binds the
preserve-by-default observation to the demoted-registry observation, so it too
fails at tip (the registry still registers the signing plugin) -- it is NOT an
always-green guard. Classification recorded in
docs/feature/oss-review-verdict-demotion/distill/red-classification-slice-05.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import InstallerDemotionFixture


scenarios("../slice-05-keyless-installer.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> InstallerDemotionFixture:
    """Production-wired demotion fixture rooted at an isolated tmp target."""
    monkeypatch.delenv("NWAVE_REVIEWER_SIGNING_KEY", raising=False)
    return InstallerDemotionFixture(target_root=tmp_path / "target")


@pytest.fixture
def box() -> dict[str, object]:
    """Carrier for captured surfaces across When/Then steps."""
    return {}


# --- Given -----------------------------------------------------------------

_PREEXISTING_KEY = b"a" * 64  # 64 hex chars; an operator's own provisioned key


@given("an install target that already carries the operator's own signing key")
def given_target_with_user_key(
    fixture: InstallerDemotionFixture, box: dict[str, object]
) -> None:
    fixture.provision_preexisting_user_key(_PREEXISTING_KEY)
    box["before"] = fixture.capture_key_slot()


@given("no signing key override is set in the operator environment")
def given_no_env_override(fixture: InstallerDemotionFixture) -> None:
    fixture.clear_signing_key_env()


@given("the production nWave installer for the default platform")
def given_production_installer(fixture: InstallerDemotionFixture) -> None:
    fixture.clear_signing_key_env()


@given("a fresh install target with no signing key anywhere")
def given_fresh_keyless_target(fixture: InstallerDemotionFixture) -> None:
    fixture.clear_signing_key_env()


# --- When ------------------------------------------------------------------


@when("the operator runs the nWave install pipeline against the target")
def when_run_install(fixture: InstallerDemotionFixture, box: dict[str, object]) -> None:
    box["result"] = fixture.run_registry_install_against_target()


@when("the install plugins are wired into the registry")
def when_wire_registry(
    fixture: InstallerDemotionFixture, box: dict[str, object]
) -> None:
    box["registry"] = fixture.capture_production_registry()


# --- Then ------------------------------------------------------------------


@then("the operator's signing key file is byte-identical to the one they had")
def then_user_key_preserved(
    fixture: InstallerDemotionFixture, box: dict[str, object]
) -> None:
    after = fixture.capture_key_slot()
    fixture.assert_user_key_preserved(
        before=box["before"],  # type: ignore[arg-type]
        after=after,
    )


@then("the production install registry no longer registers the signing plugin")
def then_registry_demoted_after_install(
    fixture: InstallerDemotionFixture,
) -> None:
    fixture.assert_registry_demoted(fixture.capture_production_registry())


@then("the registry registers exactly seven plugins")
def then_registry_seven(box: dict[str, object]) -> None:
    InstallerDemotionFixture.assert_registry_demoted(box["registry"])  # type: ignore[arg-type]


@then("none of the registered plugins is the reviewer signing plugin")
def then_no_signing_plugin(box: dict[str, object]) -> None:
    InstallerDemotionFixture.assert_registry_demoted(box["registry"])  # type: ignore[arg-type]


@then("the install completes cleanly")
def then_install_clean(
    fixture: InstallerDemotionFixture, box: dict[str, object]
) -> None:
    fixture.assert_install_clean_and_keyless(
        result=box["result"],  # type: ignore[arg-type]
        key_slot=fixture.capture_key_slot(),
    )


@then("no signing key file is provisioned on the target")
def then_no_key_provisioned(
    fixture: InstallerDemotionFixture, box: dict[str, object]
) -> None:
    fixture.assert_install_clean_and_keyless(
        result=box["result"],  # type: ignore[arg-type]
        key_slot=fixture.capture_key_slot(),
    )
