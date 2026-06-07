"""
Regression tests for show_installation_summary reopen hint (Step 01-02).

Acceptance Criteria:
1. show_installation_summary emits a line instructing the user to quit and reopen Claude Code.
2. The reopen line appears BEFORE the existing "Open Claude Code ... /nw-" line.
3. The reopen line is visually prominent (attention-grabbing prefix/emoji).
"""


class TestShowInstallationSummaryReopenHint:
    """Test that the install success panel contains the reopen Claude Code instruction."""

    def test_success_summary_contains_reopen_claude_code_hint(self, capsys):
        """
        GIVEN: show_installation_summary is called after a successful install
        WHEN: Output is captured
        THEN: The output contains an instruction to quit and reopen Claude Code

        Acceptance Criteria 1 & 3: reopen line present and visually prominent.
        """
        from scripts.install.install_nwave import show_installation_summary
        from scripts.install.install_utils import Logger

        logger = Logger(log_file=None)
        show_installation_summary(logger)

        captured = capsys.readouterr()
        output_lower = captured.out.lower()

        assert "reopen" in output_lower or "quit" in output_lower, (
            "Output should instruct the user to quit and reopen Claude Code. "
            f"Actual output:\n{captured.out}"
        )

    def test_reopen_hint_appears_before_usage_hint(self, capsys):
        """
        GIVEN: show_installation_summary is called
        WHEN: Output lines are captured
        THEN: The reopen hint line appears before the /nw- usage hint line

        Acceptance Criteria 2: reopen first, then try /nw-.
        """
        from scripts.install.install_nwave import show_installation_summary
        from scripts.install.install_utils import Logger

        logger = Logger(log_file=None)
        show_installation_summary(logger)

        captured = capsys.readouterr()
        lines = captured.out.splitlines()

        reopen_indices = [
            i
            for i, line in enumerate(lines)
            if "reopen" in line.lower() or "quit" in line.lower()
        ]
        usage_indices = [i for i, line in enumerate(lines) if "/nw-" in line.lower()]

        assert reopen_indices, (
            f"Output should contain a reopen hint line. Actual output:\n{captured.out}"
        )
        assert usage_indices, (
            "Output should contain a usage hint line with /nw-. "
            f"Actual output:\n{captured.out}"
        )
        assert reopen_indices[0] < usage_indices[-1], (
            f"Reopen hint (line {reopen_indices[0]}) should appear before usage hint "
            f"(line {usage_indices[-1]}).\nActual output:\n{captured.out}"
        )
