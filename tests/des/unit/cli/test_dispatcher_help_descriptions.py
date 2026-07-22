"""Regression: `des --help` shows real per-subcommand descriptions.

Pins the fix in `src/des/cli/__main__.py` (`_describe` + `with_descriptions`):
before this fix every subparser was registered with ``help=row.name`` (its
own name repeated), making the top-level listing useless for discovery.
`_describe(row)` now imports the subcommand's module and returns the first
line of its docstring, but ONLY when the top-level `des --help`/`-h` is the
actual invocation — normal subcommand dispatch must not pay the per-module
import cost for a help string nobody renders on that call.
"""

from __future__ import annotations

import re
import sys

import pytest

from des.cli.__main__ import main


def _normalize_whitespace(text: str) -> str:
    """Collapse argparse's help-formatter line-wrapping into one line."""
    return re.sub(r"\s+", " ", text)


def test_top_level_help_shows_real_descriptions_not_bare_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0

    stdout = _normalize_whitespace(capsys.readouterr().out)

    assert "per-target-language language-adapter gap report" in stdout, (
        f"des --help did not show doctor's real description. stdout:\n{stdout}"
    )
    assert "Verify nWave installation health with 7 diagnostic checks" in stdout, (
        f"des --help did not show health-check's real description. stdout:\n{stdout}"
    )


def test_normal_dispatch_imports_only_the_dispatched_subcommand_module() -> None:
    baseline = frozenset(name for name in sys.modules if name.startswith("des.cli."))

    exit_code = main(["doctor", "--target-language", "python"])

    assert exit_code == 0
    after = frozenset(name for name in sys.modules if name.startswith("des.cli."))
    newly_imported = after - baseline
    assert newly_imported <= {"des.cli.doctor"}, (
        "normal subcommand dispatch imported extra des.cli.* modules beyond "
        f"the one dispatched: {sorted(newly_imported - {'des.cli.doctor'})}. "
        "The top-level --help description path must not run on normal dispatch."
    )


def test_subcommand_help_still_delegates_to_its_own_argparse(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["doctor", "--help"])
    assert exc_info.value.code == 0

    stdout = capsys.readouterr().out
    assert "des doctor" in stdout
    assert "--target-language" in stdout
