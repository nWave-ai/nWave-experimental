"""Step definitions -- slice-01: Copilot CLI DES hook install contract.

copilot-cli-integration slice-01. Layer 3 (subprocess + FS acceptance): the
production installer/uninstaller CLI invoked as a real Python subprocess is the
driving port. Copilot presence is simulated for the installer's detector via a
tmp COPILOT_HOME tree + COPILOT_CLI=1 env (spike-validated detection signals) --
NO live `copilot` binary is ever invoked.

The only driven ports are:
  - the real filesystem (tmp COPILOT_HOME tree + tmp Claude config dir),
  - the real environment (COPILOT_HOME / HOME / COPILOT_CLI / CLAUDE_CONFIG_DIR,
    isolated to the tmp tree so the real ~/.copilot and ~/.claude are untouched),
  - the real subprocess (`python <install_nwave.py|uninstall_nwave.py>`).

Example-based (Mandate 11 -- layer 3 sad/preservation paths enumerated
explicitly; NO PBT machinery at layer 3 per Mandate 9). Three ATs cover the
slice-01 install-contract: walking-skeleton install-writes-file (FM-1) +
schema-double-nested (FS-1) + uninstall-round-trip-preserves-foreign (idempotent
inverse / preservation).

Step bodies delegate to `CopilotInstallFixture` (Mandate-12 criterion 3:
<=2 statements per body, final statement is a composition method call, zero
control flow in step bodies).

ADR-028 + friction #26 skip-marker: `pytestmark = pytest.mark.skip(...)` at the
file head keeps the whole slice RED-but-skipped until the DELIVER crafter unskips
one scenario at a time (Outside-In TDD outer-loop discipline). The crafter
removes the marker (or narrows it) when enabling each scenario in Phase A_GREEN_ATS.

RED-for-the-right-reason: the slice-01 production `copilot_des_plugin.py` and the
`TargetPlatform.COPILOT_CLI` enum do NOT exist yet (DELIVER lands them). When the
composition fixture runs the installer subprocess, the plugin registry has no
Copilot plugin, so NO `<COPILOT_HOME>/hooks/nwave-des.json` is written; the AT
then fires AssertionError on the first `Then` step (`assert_hook_file_present`).
That is the correct RED: the assertion fires because the install-time behavior is
unimplemented, not because of an import error or fixture setup bug.

Mandate-13 (driving-port-only): every step delegates to the composition fixture,
which drives the SUT via real installer subprocess + filesystem reads. ZERO direct
production import of the Copilot plugin; ZERO live `copilot` binary invocation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition import CopilotHookObservation, CopilotInstallFixture


# ADR-028 + friction #26: slice-01 skip marker removed in DELIVER Phase A_GREEN_ATS
# now that copilot_des_plugin.py + TargetPlatform.COPILOT_CLI exist.


scenarios("../slice-01-copilot-des-install.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> CopilotInstallFixture:
    """Production-wired Copilot install fixture rooted at an isolated tmp tree."""
    return CopilotInstallFixture(tmp_root=tmp_path)


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the captured operator-observable surface across steps."""
    return {}


# --- AT-1 + AT-2 Given (shared precondition) -------------------------------


@given("an operator whose Copilot runtime is present but carries no nWave hook")
def given_clean_copilot_runtime(fixture: CopilotInstallFixture) -> None:
    fixture.stage_copilot_runtime_without_nwave_hook()


# --- AT-3 Given ------------------------------------------------------------


@given(
    "an operator whose Copilot runtime already carries a hook they authored themselves"
)
def given_operator_authored_hook(fixture: CopilotInstallFixture) -> None:
    fixture.stage_operator_authored_copilot_hook()


# --- AT-2 + AT-3 Given (chained narrative -- Pillar 2: reuses AT-1's When) --


@given("the operator has installed nWave for their Copilot runtime")
def given_already_installed(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    result_box["after"] = fixture.run_install()


# --- When ------------------------------------------------------------------


@when("the operator installs nWave for their Copilot runtime")
def when_install(fixture: CopilotInstallFixture, result_box: dict[str, object]) -> None:
    result_box["after"] = fixture.run_install()


@when("the operator inspects the installed nWave DES hook config")
def when_inspect(result_box: dict[str, object]) -> None:
    # The chained `Given the operator has installed nWave...` already captured
    # the surface into result_box["after"]; inspection is a read of that surface.
    result_box.setdefault("after", result_box.get("after"))


@when("the operator uninstalls nWave from their Copilot runtime")
def when_uninstall(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    result_box["after"] = fixture.run_uninstall()


# --- AT-1 Then -------------------------------------------------------------


@then("the Copilot hooks directory carries an nWave DES hook config file")
def then_hook_file_present(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_hook_file_present(_obs(result_box))


@then("the nWave DES hook config invokes the shared DES adapter")
def then_hook_invokes_adapter(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_hook_invokes_des_adapter(_obs(result_box))


@then("no inline hook block is written into the Copilot settings file")
def then_no_inline_block(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_no_inline_settings_block(_obs(result_box))


# --- AT-2 Then -------------------------------------------------------------


@then("each hook entry groups its handlers under a nested handler list")
def then_double_nested(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_schema_double_nested(_obs(result_box))


@then("each handler names its kind and the command Copilot runs")
def then_handler_named(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_each_handler_named(_obs(result_box))


@then("the hook config is not written in the flat single-handler shape")
def then_not_flat(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_not_flat_shape(_obs(result_box))


# --- AT-3 Then -------------------------------------------------------------


@then("the nWave DES hook config is gone from the Copilot hooks directory")
def then_hook_removed(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_hook_file_removed(_obs(result_box))


@then("no orphan nWave hook artifact is left behind")
def then_no_orphan(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_no_orphan_artifact(_obs(result_box))


@then("the operator's own Copilot hook is preserved unchanged")
def then_foreign_preserved(
    fixture: CopilotInstallFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_foreign_hook_preserved(_obs(result_box))


# --- internal: typed accessor for the captured surface ---------------------


def _obs(result_box: dict[str, object]) -> CopilotHookObservation:
    """Return the captured observation; a helper so step bodies stay <=2 stmts."""
    return result_box["after"]  # type: ignore[return-value]
