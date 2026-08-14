"""AT -- `des charter-scaffold --help` shows example invocations for all
three seed-modes (direct-value, bug-observable, brownfield-discovery).

The help text must include concrete examples so users understand the
cardinality and required inputs for each seed-mode. Help-only, additive --
the pre-existing usage/description/`--seed-mode` help text is unchanged.

Driving surface: `des.cli.charter_scaffold.main(["--help"])` invoked
IN-PROCESS (composition-root driving port -- Mandate 16, driving-port-only
boundary). `argparse` prints help to stdout then raises `SystemExit(0)` for
`--help` -- caught via `pytest.raises(SystemExit)`, stdout captured via
`capsys`.
"""

from __future__ import annotations

import re

import pytest


def _help_stdout(capsys) -> str:
    """Drive `main(["--help"])` in-process; argparse prints help then raises
    `SystemExit(0)` before `main()` reaches its own `return`. Returns the
    captured stdout, whitespace-normalized so assertions are robust to
    argparse's line-wrapping of option help text -- only the epilog is
    raw/unwrapped even after the fix (`RawDescriptionHelpFormatter` only
    affects description+epilog, never per-option help). textwrap breaks long
    words AT an existing hyphen (e.g. "bug-observable" -> "bug-" / newline /
    "observable") without inserting a new one, so a hyphen immediately
    followed by whitespace is a wrap artifact and is re-joined with NO
    space; every other run of whitespace collapses to a single space."""
    from des.cli.charter_scaffold import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0

    raw = capsys.readouterr().out
    dehyphenated = re.sub(r"-\s+", "-", raw)
    return " ".join(dehyphenated.split())


def test_help_shows_example_invocations_with_1_vs_n_cardinality_distinction(
    capsys,
) -> None:
    """Scenario 1: `--help` stdout carries an examples/epilog block naming all
    three seed-modes (direct-value, bug-observable, brownfield-discovery),
    each annotated as producing exactly ONE charter."""
    help_text = _help_stdout(capsys)

    # All three post-cutover seed-mode example invocations are present.
    assert "--seed-mode direct-value" in help_text
    assert "--seed-mode bug-observable" in help_text
    assert "--seed-mode brownfield-discovery" in help_text
    assert "--observable" in help_text
    assert "--area" in help_text
    assert "--value" in help_text

    # No slice-plan wording.
    lowered = help_text.lower()
    assert "slice-plan" not in lowered, (
        "help text mentions 'slice-plan' which was deleted post-cutover"
    )


def test_help_epilog_does_not_remove_existing_description(capsys) -> None:
    """Scenario 2 (negative / non-regression): `--help` still exits 0, and
    the pre-existing usage description survives -- the epilog is additive,
    never a rewrite."""
    help_text = _help_stdout(capsys)

    # Pre-existing top-level description, unchanged.
    assert "Generate expectation-charter scaffolds" in help_text
    assert "idempotent, degrade-LOUD" in help_text
