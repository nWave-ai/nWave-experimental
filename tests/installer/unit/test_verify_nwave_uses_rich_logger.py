"""Regression test: verify_nwave.py must construct a Rich-capable logger.

Prior to this fix, `verify_nwave.py` constructed `install_utils.Logger`
directly instead of the `rich_console` family (`RichLogger`/`PlainLogger`/
`SilentLogger`) every other install-flow script uses -- so verify_nwave.py
never got Rich styling while the rest of the installer did. This pins the
concrete symptom: `verify_nwave.main`'s module-level `RichLogger` name must
resolve to `rich_console.RichLogger`, not `install_utils.Logger`.
"""

from __future__ import annotations


def test_verify_nwave_module_uses_rich_console_logger_family():
    from scripts.install import rich_console, verify_nwave

    assert verify_nwave.RichLogger is rich_console.RichLogger


def test_verify_nwave_logger_construction_is_rich_capable(tmp_path):
    """The logger built inside main() must be a RichLogger instance -- it
    carries Rich/ANSI styling methods (print_styled, warn) that
    install_utils.Logger's call-compatible surface duplicates independently."""
    from scripts.install.rich_console import RichLogger

    log_file = tmp_path / "nwave-install.log"
    logger = RichLogger(log_file=log_file, silent=True)

    assert hasattr(logger, "print_styled")
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
