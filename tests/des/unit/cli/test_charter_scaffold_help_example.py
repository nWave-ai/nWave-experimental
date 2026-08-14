"""AT -- `des charter-scaffold --help` shows the 1-vs-N charter cardinality
example (charter-scaffold-help-example feature, #54, slice-01).

Vera (charter-scaffold slice-03 examine) noted the shipped `--help` describes
the `--seed-mode` values in prose but gives NO concrete example distinguishing
the cardinality: a `slice-plan` run scaffolds N charters (one per observable
Slice Plan row) while `bug-observable` / `brownfield-discovery` scaffold
exactly ONE. A new user cannot tell from the current help how many files a
given invocation produces.

Fix (crafter, NOT this file): add an argparse `epilog=` (with
`formatter_class=argparse.RawDescriptionHelpFormatter`) to the
`_build_parser()` `ArgumentParser` in `src/des/cli/charter_scaffold.py`,
carrying example invocations for all three seed-modes that make the 1-vs-N
distinction explicit. Help-only, additive -- the pre-existing
usage/description/`--seed-mode` help text is byte-unchanged, `--help` still
exits 0.

covers: slice-01 of docs/feature/charter-scaffold-help-example/feature-delta.md

Driving surface: `des.cli.charter_scaffold.main(["--help"])` invoked
IN-PROCESS (composition-root driving port -- Mandate 16, driving-port-only
boundary). `argparse` prints help to stdout then raises `SystemExit(0)` for
`--help` -- caught via `pytest.raises(SystemExit)`, stdout captured via
`capsys` (extends the `_invoke()` in-process pattern from
`tests/des/unit/cli/test_charter_scaffold.py`, adapted for the `--help`
early-exit path that never reaches `main()`'s `return`).

RED reason: `_build_parser()` has no `epilog=` today, so scenario 1 fails
with a real `AssertionError` (the examples/cardinality text is absent from
stdout) -- not an import/collection error, since `des.cli.charter_scaffold`
already ships.
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
    three seed-modes, with the slice-plan example annotated as producing
    one-per-row / N charters and the bug-observable example annotated as
    producing exactly ONE."""
    help_text = _help_stdout(capsys)

    # All four seed-mode example invocations are present.
    assert "--seed-mode slice-plan" in help_text
    assert "--seed-mode bug-observable" in help_text
    assert "--seed-mode brownfield-discovery" in help_text
    assert "--seed-mode direct-value" in help_text
    assert "--observable" in help_text
    assert "--area" in help_text
    assert "--value" in help_text

    # The 1-vs-N cardinality distinction is spelled out, not merely implied.
    lowered = help_text.lower()
    slice_plan_says_many = any(
        phrase in lowered
        for phrase in ("one per", "one-per", "n charters", "n scaffolds")
    )
    bug_observable_says_one = any(
        phrase in lowered for phrase in ("exactly one", "exactly 1", "a single")
    )
    assert slice_plan_says_many, (
        "help text does not annotate the slice-plan example as producing "
        f"one-charter-per-observable-row (N charters); stdout:\n{help_text}"
    )
    assert bug_observable_says_one, (
        "help text does not annotate the bug-observable example as producing "
        f"exactly ONE charter; stdout:\n{help_text}"
    )


def test_help_epilog_does_not_remove_existing_description(capsys) -> None:
    """Scenario 2 (negative / non-regression): `--help` still exits 0, and
    the pre-existing usage description + `--seed-mode` help text survive
    byte-identifiable -- the epilog is additive, never a rewrite."""
    help_text = _help_stdout(capsys)

    # Pre-existing top-level description, unchanged.
    assert "Generate expectation-charter scaffolds" in help_text
    assert "OBSERVABLE Slice Plan rows" in help_text
    assert "idempotent, degrade-LOUD" in help_text

    # Pre-existing --seed-mode help text, unchanged.
    assert (
        "'slice-plan' (default) scaffolds every observable Slice Plan row" in help_text
    )
    assert "'bug-observable' scaffolds ONE charter straight from" in help_text
    assert "'brownfield-discovery' scaffolds ONE discovery-framed charter" in help_text
