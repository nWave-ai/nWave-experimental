# @feature-des-refactor-fixer-swarm
"""Regression AT -- `des refactor --help` must TEACH, not just enumerate.

RCA (refactor-ux drain, 2026-07-29, incident 1 of the two-incident report):
a real operator, working from an INSTALLED nWave in her own project repo,
looked for `scripts/refactor_agent.py` inside her PROJECT and did not find
it -- the actuator lives in the nWave INSTALLATION, resolved via
`des.runtime.interpreter.resolve_installed_actuator`, never inside a
consumer's project. She concluded "no actuator here" and dispatched an
expensive background agent instead of ever running `des refactor`. Before
this fix, `des refactor --help` printed five bare options with ZERO
descriptions (verified empirically: every `argparse.add_argument` call in
`_parse_args` omitted `help=`) and never mentioned the actuator, where it
lives, or that the shipped default cannot reach a merge on its own
(`_verdict_fix_line`'s own honesty clause, `src/des/cli/refactor.py`). The
well-written runtime refusals (`_actuator_not_found_refusal`,
`_entry_gate_verdict_missing_refusal`) never had a chance to fire, because
she never ran the command at all -- `--help` is read BEFORE any of that, and
it taught nothing.

Property tests only (per the design's own instruction): assert the FACTS a
user needs are present, never pin exact wording -- the same discipline this
tree already applies to every other WHAT/WHY/HOW refusal.

Driving surface: in-process, the REAL `des.cli.refactor._build_parser()` /
`_parse_args`, no subprocess -- `--help` is argparse's own synchronous
`format_help`/`SystemExit(0)` path, nothing to fork.
"""

from __future__ import annotations

import pytest

from des.cli.refactor import _build_parser, _parse_args


pytestmark = pytest.mark.acceptance

_DOCUMENTED_OPTIONS = (
    "--pile",
    "--agent-cmd",
    "--max-parallel",
    "--driver",
    "--prompt-template",
)


def test_every_cli_option_carries_a_non_blank_help_description():
    """Given the real `des refactor` argument parser, Then every operator-
    facing option has a non-blank `help=` string -- never the bare
    `--option OPTION` argparse renders when `help` is omitted.
    """
    parser = _build_parser()
    documented = {
        action.option_strings[0]: action.help
        for action in parser._actions
        if action.option_strings and action.option_strings[0] != "-h"
    }
    assert set(documented) == set(_DOCUMENTED_OPTIONS), (
        f"expected help text for exactly {_DOCUMENTED_OPTIONS}, got {sorted(documented)}"
    )
    for option, help_text in documented.items():
        assert help_text and help_text.strip(), f"{option} has no help= description"


def test_help_states_the_default_actuator_lives_in_the_installation_not_the_project():
    """Given `des refactor --help`, Then the rendered help states plainly
    that the actuator it resolves by default lives in the nWave
    INSTALLATION, not inside the operator's own project -- the one fact
    that would have stopped incident 1 before any command ran.
    """
    full_help = _build_parser().format_help().lower()
    assert "installation" in full_help, (
        f"help text never says the default actuator lives in the installation: {full_help!r}"
    )
    assert "project" in full_help, (
        f"help text never contrasts installation-relative with the operator's own project: "
        f"{full_help!r}"
    )


def test_help_declares_the_default_actuator_cannot_reach_a_merge_alone():
    """Given `des refactor --help`, Then the rendered help states honestly
    that the default (no `--agent-cmd`) actuator does not print an
    entry-gate verdict, so it cannot complete a drain on its own -- the same
    honesty clause `_verdict_fix_line` already gives a reader who first hits
    the runtime refusal, surfaced instead at the point BEFORE any command
    ran, where incident 1's operator actually was.
    """
    full_help = _build_parser().format_help().lower()
    assert "verdict" in full_help, (
        f"help text never mentions the entry-gate verdict requirement: {full_help!r}"
    )
    assert "cannot" in full_help or "does not" in full_help or "doesn't" in full_help, (
        f"help text never states the default path cannot complete on its own: {full_help!r}"
    )


def test_help_flag_still_exits_zero_and_parses_via_the_real_entry_point():
    """Negative-safety companion: the help-text additions must not perturb
    `--help`'s own argparse contract (exit 0, `SystemExit`) or break normal
    argument parsing for a real invocation.
    """
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(["--help"])
    assert excinfo.value.code == 0
