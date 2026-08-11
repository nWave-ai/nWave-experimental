"""Regression: a dispatch owes ITS OWN wave's ceremony, not DELIVER's.

Measured defect (2026-07-18): the atdd_pure section validator keyed only on
DES-PHASE and DES-LANE. An AUTHORING wave (DISCUSS/DESIGN/DEVOPS/DISTILL)
declares neither, so every such dispatch fell to the fail-closed DELIVER
default and was held to the 12 implementation sections -- ``DESIGN_CONTEXT``
among them. DISCUSS runs BEFORE DESIGN, so satisfying that demand means
injecting design context into the one wave whose job is to derive value
before any design exists. The guard did not merely miss that inversion; it
produced it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)
from des.cli import dispatch as dispatch_cli
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES
from tests.common.delivery_contract_fixture import contract_args


# tests/des/unit/cli/<this file> -> parents[4] == checkout root.
_REPO_ROOT = Path(__file__).resolve().parents[4]

AUTHORING_WAVES = ("discuss", "design", "devops", "distill")


def _generate(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    exit_code = dispatch_cli.main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            "wave-ceremony-probe",
            "--slice",
            "slice-01",
            "--intent",
            "Probe the wave ceremony profile.",
            *argv,
        ]
    )
    assert exit_code == 0, "the generator must render a dispatch for this wave"
    return capsys.readouterr().out


@pytest.mark.parametrize("wave", AUTHORING_WAVES)
def test_authoring_wave_dispatch_passes_the_guard_without_a_phase(
    wave: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The generated dispatch for each authoring wave is gate-valid.

    An authoring wave runs none of the 3 canonical DELIVER phases, so
    ``--phase`` must not be required -- demanding one forces the operator to
    borrow an unrelated DELIVER phase word, writing a false step into the
    audit trail purely to satisfy a flag.
    """
    result = AtddPurePromptValidator().validate_prompt(
        _generate(capsys, "--wave", wave)
    )

    assert result.status == "PASSED", result.errors
    assert result.task_invocation_allowed is True


def test_discuss_dispatch_does_not_demand_a_design_it_cannot_have(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """DISCUSS precedes DESIGN -- neither the profile nor the prompt cites one."""
    assert "DESIGN_CONTEXT" not in WAVE_DISPATCH_PROFILES["discuss"].required_sections
    assert "# DESIGN_CONTEXT" not in _generate(capsys, "--wave", "discuss")


@pytest.mark.parametrize("wave", ("design", "devops", "distill"))
def test_authoring_waves_downstream_of_design_still_cite_it(
    wave: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dropping DESIGN_CONTEXT is scoped to DISCUSS, never a blanket removal."""
    assert "# DESIGN_CONTEXT" in _generate(capsys, "--wave", wave)


@pytest.mark.parametrize(
    ("wave", "expected_agent"),
    (
        ("discuss", "nw-product-owner"),
        ("design", "nw-solution-architect"),
        ("devops", "nw-platform-architect"),
        ("distill", "nw-acceptance-designer"),
    ),
)
def test_authoring_wave_names_its_own_agent_not_the_crafter(
    wave: str, expected_agent: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a wave axis a phaseless dispatch resolved to the crafter --
    naming the implementer as the recipient of a wave that writes a document.
    """
    assert f"Agent: {expected_agent}" in _generate(capsys, "--wave", wave)


def test_deliver_still_owes_the_full_implementation_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The lighter profiles are ADDITIVE -- DELIVER's ceremony is untouched."""
    prompt = _generate(
        capsys,
        "--wave",
        "deliver",
        "--phase",
        "A_GREEN",
        *contract_args(_REPO_ROOT, seed=False),
    )

    for section in ATDD_PURE_MANDATORY_SECTIONS:
        assert f"# {section}" in prompt
    assert AtddPurePromptValidator().validate_prompt(prompt).status == "PASSED"


def test_an_incomplete_deliver_dispatch_is_still_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The guard is RELOCATED per wave, never weakened: DELIVER still fails
    closed when a mandatory implementation section is absent."""
    prompt = _generate(
        capsys,
        "--wave",
        "deliver",
        "--phase",
        "A_GREEN",
        *contract_args(_REPO_ROOT, seed=False),
    )

    mutilated = prompt.replace("# TERMINATING_RUN", "# NOT_A_SECTION")

    assert AtddPurePromptValidator().validate_prompt(mutilated).status == "FAILED"


def test_an_unrecognised_wave_falls_back_to_the_full_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail-closed: an unknown wave is treated as implementation, never
    silently downgraded to a lighter profile."""
    lean = _generate(capsys, "--wave", "discuss").replace(
        "DES-WAVE : discuss", "DES-WAVE : not-a-wave"
    )

    assert AtddPurePromptValidator().validate_prompt(lean).status == "FAILED"


def test_a_lean_profile_mislabelled_as_deliver_is_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The profile is chosen by the DECLARED wave, so a lean prompt claiming
    to be DELIVER is caught rather than passed on its lean merits."""
    mislabelled = _generate(capsys, "--wave", "discuss").replace(
        "DES-WAVE : discuss", "DES-WAVE : deliver"
    )

    assert AtddPurePromptValidator().validate_prompt(mislabelled).status == "FAILED"


def test_the_deliver_profile_datum_matches_the_exported_ssot() -> None:
    """The domain datum spells its DELIVER row literally (it must not import
    the application layer) -- this is what keeps the two from drifting."""
    assert (
        WAVE_DISPATCH_PROFILES["deliver"].required_sections
        == ATDD_PURE_MANDATORY_SECTIONS
    )


def _phase_action_help(parser: object) -> str:
    for action in parser._actions:  # type: ignore[attr-defined]
        if "--phase" in getattr(action, "option_strings", ()):
            return action.help or ""
    raise AssertionError("--phase action not found in parser")


def test_phase_help_names_the_authoring_wave_exemption_too() -> None:
    """The `--phase` help STRING ITSELF must name BOTH exemptions.

    The runtime error message (main(), on a missing --phase) already names
    two exemptions -- a phaseless lane OR an authoring --wave. Regression:
    the --help text for --phase named only the lane exemption, so a reader
    of `des dispatch --help` (never hitting the runtime error) would wrongly
    conclude --phase is mandatory for e.g. `--wave discuss`. Asserting
    against the FULL parser help is too weak -- `--wave`'s own choices list
    already prints every wave name, which would make this pass for the
    wrong reason; the property under test is that the `--phase` HELP STRING
    names the exemption, not that the wave name appears somewhere on the
    page.
    """
    phase_help = _phase_action_help(dispatch_cli._build_parser())
    authoring_waves = sorted(
        w for w, p in WAVE_DISPATCH_PROFILES.items() if not p.runs_tests
    )
    assert authoring_waves, "fixture sanity: at least one authoring wave exists"
    assert "authoring wave" in phase_help, (
        "--phase help must name the authoring-wave exemption, not just the "
        "phaseless-lane one"
    )
    for wave in authoring_waves:
        assert wave in phase_help, (
            f"--phase help must name the authoring-wave exemption ({wave})"
        )
