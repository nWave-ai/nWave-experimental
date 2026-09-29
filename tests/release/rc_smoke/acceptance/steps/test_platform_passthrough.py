"""Tier A step definitions — `--platform` contract (US-5).

Driving port: the published console script's install handler
(``nwave_ai.cli._handle_install``) and its usage text. Layer 4 (real CLI
arg-handling) -> example-based, no PBT machinery (Mandate 9 / 11).

The passthrough is pinned by spying on the single seam through which install
args leave the CLI (``_run_script``): the chosen ``--platform <tool>`` must
arrive there unchanged, so a refactor cannot silently break the matrix entry
point. Step bodies delegate to the CLI; no business logic inlined
(Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from nwave_ai import cli


scenarios("../platform-contract.feature")


@pytest.fixture
def run_state(monkeypatch, tmp_path: Path) -> dict:
    """Run the public CLI seam from an isolated consumer project."""
    monkeypatch.chdir(tmp_path)
    state: dict = {"forwarded": None}

    def _spy_run_script(
        script: str, args: list[str], *, user_project_root: Path | None = None
    ) -> int:
        state["forwarded"] = list(args)
        state["user_project_root"] = user_project_root
        return 0

    # Capture the script args without launching the installer.
    monkeypatch.setattr(cli, "_run_script", _spy_run_script)
    state["monkeypatch"] = monkeypatch
    return state


# --- Given -----------------------------------------------------------------


@given("the published installer usage text")
def given_usage_text(run_state):
    # _handle_install docstring is the in-code usage contract for the flag set.
    run_state["usage"] = (cli._handle_install.__doc__ or "") + (cli.__doc__ or "")


@given(parsers.parse('the release engineer chooses platform "{tool}"'))
def given_chosen_platform(run_state, tool):
    run_state["argv"] = ["--platform", tool, "--yes"]


# --- When ------------------------------------------------------------------


@when("the release engineer reads the install command help")
def when_read_help(run_state):
    # No-op: usage captured in Given; the assertion reads it in Then.
    run_state["read"] = True


@when("the install command forwards its arguments")
def when_forward_args(run_state):
    cli._handle_install(run_state["argv"])


# --- Then ------------------------------------------------------------------


@then("the platform selector is documented")
def then_platform_documented(run_state):
    # US-5: --platform must be a documented contract. This scenario stays RED
    # until DELIVER adds the flag to the usage text.
    assert "--platform" in run_state["usage"], (
        "--platform is not documented in the install usage text"
    )


@then(parsers.parse('the installer receives platform "{tool}" unchanged'))
def then_platform_forwarded(run_state, tool):
    forwarded = run_state["forwarded"]
    assert forwarded is not None, "install did not reach the forward seam"
    assert "--platform" in forwarded, forwarded
    idx = forwarded.index("--platform")
    assert forwarded[idx + 1] == tool, f"platform mangled: {forwarded}"
    assert run_state["user_project_root"] == Path.cwd().resolve()
