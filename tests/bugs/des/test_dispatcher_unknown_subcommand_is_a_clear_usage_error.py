"""Regression: unknown `des <subcommand>` must be a clear usage error, never
a bare StopIteration.

techdebt.md row `main-dispatcher-silent-stopiteration-on-unknown-subcommand`
claimed ``src/des/cli/__main__.py``'s dispatcher used ``next()`` without a
default on the registry lookup, so an unknown subcommand would raise an
unguarded ``StopIteration`` instead of a self-explaining error (GDP-3).

VERIFIED (2026-07-27) against the current dispatcher: this does NOT
reproduce. ``_build_parser`` registers subparsers via
``parser.add_subparsers(dest="subcommand", required=True)`` (one
``add_parser(row.name)`` per registry row), which gives argparse itself a
closed choice-set for the ``subcommand`` positional. An unrecognised
subcommand is rejected by argparse's own choice validation -- inside
``parser.parse_known_args`` -- before dispatch ever reaches the
``next(r for r in _REGISTRY if ...)`` lookup the row's `defect=` describes.
This test pins that behaviour so a future refactor of ``_build_parser``
cannot silently reopen the gap.
"""

from __future__ import annotations

import pytest

from des.cli.__main__ import main


def test_unknown_subcommand_exits_cleanly_with_usage_message(
    capsys: pytest.CaptureFixture,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["totally-bogus-subcommand-xyz"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err
    assert "totally-bogus-subcommand-xyz" in captured.err


def test_unknown_subcommand_never_raises_stopiteration() -> None:
    """The specific failure mode the pile row named must not occur."""
    try:
        main(["totally-bogus-subcommand-xyz"])
    except StopIteration:
        pytest.fail(
            "dispatcher raised bare StopIteration on an unknown subcommand "
            "instead of a self-explaining usage error"
        )
    except SystemExit:
        pass  # expected: argparse's own choice-validation usage error
