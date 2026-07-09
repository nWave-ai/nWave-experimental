"""
Regression tests: show_installation_summary must state the install target path.

Bug (Vera examine finding, 2026-07-08): the installer's success summary reports
"nWave vX installed and healthy!" but never states WHERE it installed. A user
(especially one sandboxing/testing with a redirected HOME) sees success with no
path and cannot tell where the install landed -- Vera pointed HOME at a temp
dir, the installer ignored it (installs to CLAUDE_CONFIG_DIR / ~/.claude) and
reported success with no path, so she could not tell the install landed
elsewhere.

Fix locus: scripts/install/install_nwave.py show_installation_summary(logger)
(~line 901) must thread the install target directory in and print it. The
sole caller is main() at scripts/install/install_nwave.py:1125, which has
`installer.claude_config_dir` (set in NWaveInstaller.__init__ from
PathUtils.get_claude_config_dir()) available to pass through.

These ATs drive the REAL show_installation_summary. They call it with the
anticipated install-target argument and fall back to the current logger-only
signature if that argument does not exist yet (TypeError) -- so the AT is RED
today for the right reason (the target path is absent from the summary
output; a real AssertionError), never because of a signature mismatch.
"""

from pathlib import Path


def _show_summary_for_target(logger, target_dir: Path) -> None:
    """Call show_installation_summary, driving the anticipated install-target arg.

    Falls back to the current (logger-only) signature so the call itself
    never breaks the test at collection or execution time for a reason
    unrelated to the bug -- only the observable output is asserted on.
    """
    from scripts.install.install_nwave import show_installation_summary

    try:
        show_installation_summary(logger, target_dir)
    except TypeError:
        show_installation_summary(logger)


def test_installation_summary_states_install_target_path(tmp_path, capsys):
    """
    GIVEN: nWave was installed into a specific target directory
    WHEN: show_installation_summary is called for that install
    THEN: the emitted summary states the install target path, so the user
          can see exactly where nWave landed.
    """
    from scripts.install.install_utils import Logger

    target_dir = tmp_path / "sandboxed-claude-config"
    logger = Logger(log_file=None)

    _show_summary_for_target(logger, target_dir)

    captured = capsys.readouterr()
    assert str(target_dir) in captured.out, (
        "Installation summary should state the install target path so the "
        f"user knows where nWave landed. Expected to find {target_dir!s} in "
        f"the output. Actual output:\n{captured.out}"
    )


def test_installation_summary_never_claims_healthy_without_stating_target_path(
    tmp_path, capsys
):
    """
    GIVEN: nWave was installed into a specific target directory
    WHEN: show_installation_summary reports the install as healthy
    THEN: it must NOT do so while omitting the install target path -- the
          exact bug: success claimed, location silent (a user with a
          redirected HOME cannot tell where the install landed).
    """
    from scripts.install.install_utils import Logger

    target_dir = tmp_path / "sandboxed-claude-config"
    logger = Logger(log_file=None)

    _show_summary_for_target(logger, target_dir)

    captured = capsys.readouterr()
    claims_healthy = "installed and healthy" in captured.out.lower()
    states_target_path = str(target_dir) in captured.out

    assert not (claims_healthy and not states_target_path), (
        "Installation summary must not claim success ('installed and "
        "healthy') while the install target path is absent from the "
        f"output. claims_healthy={claims_healthy} "
        f"states_target_path={states_target_path}. Actual output:\n"
        f"{captured.out}"
    )
