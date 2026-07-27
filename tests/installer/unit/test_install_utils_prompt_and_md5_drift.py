"""Verification tests for two techdebt.md closures (no code change needed --
both rows described a hypothetical risk that the actual, sole call site does
not exhibit).

D6-install-utils-silent-prompt-return: scripts/install/install_utils.py's
``confirm_action`` collapses "user typed no" and "Ctrl-C/EOF" into the same
``False``. The row worried a caller might let a destructive action proceed on
the silent False. The ONLY caller (scripts/install/uninstall_nwave.py:238,
the uninstall confirmation gate) treats every non-True outcome as "abort" --
the collapse is safe there because both causes must produce the same action.

D7-return-none-on-error-file-md5: scripts/install/install_nwave.py's
``_file_md5`` returns None on OSError, and ``_files_content_equal`` treats an
unreadable file as content-different. The row worried this masks read
failures as false 'drift'. The sole caller (the templates-verify step in
``NWaveInstaller.verify_installation``) already reports every non-matching
file by NAME under 'Content drift: ...' -- loud, not silent -- exactly as
``_file_md5``'s own docstring documents.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts.install.install_nwave import _file_md5, _files_content_equal
from scripts.install.install_utils import confirm_action


class TestConfirmActionCancellationIsAlwaysAbort:
    """confirm_action must return False -- never True -- for every non-yes path."""

    def test_explicit_no_returns_false(self):
        with patch("builtins.input", return_value="n"):
            assert confirm_action("proceed?") is False

    def test_keyboard_interrupt_returns_false_not_raises(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            assert confirm_action("proceed?") is False

    def test_eof_returns_false_not_raises(self):
        with patch("builtins.input", side_effect=EOFError):
            assert confirm_action("proceed?") is False


class TestFilesContentEqualDriftReporting:
    """An unreadable file must be reported as drift, never crash the verifier."""

    def test_file_md5_returns_none_on_missing_file(self, tmp_path: Path):
        missing = tmp_path / "does-not-exist.md"
        assert _file_md5(missing) is None

    def test_files_content_equal_is_false_when_source_unreadable(self, tmp_path: Path):
        source = tmp_path / "unreadable-source.md"
        # never created -> _file_md5(source) is None
        target = tmp_path / "target.md"
        target.write_text("content", encoding="utf-8")

        # False (not a crash) is exactly what lets the caller report a named
        # 'Content drift' line instead of aborting the whole verify walk.
        assert _files_content_equal(source, target) is False
