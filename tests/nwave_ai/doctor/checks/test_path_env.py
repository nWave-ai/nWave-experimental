"""Acceptance tests for PathEnvCheck.

Tests enter through the check's run() driving port.

The question the check answers is: "will a Claude Code session resolve the DES
shims in <claude_dir>/bin?" (issue nWave-ai/nWave-experimental#5). A session
gets its PATH from settings.json env.PATH when that key is present (Claude
Code REPLACES the inherited PATH with it), otherwise from the PATH inherited
from the user's shell. So:

- env.PATH absent  -> the inherited process PATH decides.
- env.PATH present -> env.PATH alone decides; it must contain the bin
  directory, split on the platform separator and compared after
  normalization, and must not be a PATH frozen on another machine.

Seams assumed by these tests (the crafter implements them):

- The inherited PATH is read from ``os.environ["PATH"]`` at call time.
- ``path_env`` reaches the platform through its module-global name ``os``
  at call time: ``os.pathsep`` for splitting, ``os.path.normpath`` and
  ``os.path.normcase`` for comparison, ``os.path.isdir`` for the
  foreign-home probe. Windows-shaped tests replace that module global with
  a proxy whose ``pathsep`` is ``";"`` and whose ``path`` is ``ntpath``,
  so they run on any host without patching the real ``os`` module.
"""

from __future__ import annotations

import json
import ntpath
import os
import re
from typing import TYPE_CHECKING, Any

import pytest
from nwave_ai.doctor.checks.path_env import PathEnvCheck
from nwave_ai.doctor.context import DoctorContext

from nwave_ai.doctor.checks import path_env as path_env_module


if TYPE_CHECKING:
    from pathlib import Path


_SHELL_PROFILE_HINT = re.compile(
    r"shell profile|\.zshenv|\.zprofile|\.zshrc|\.bashrc|\.bash_profile|\.profile"
    r"|PowerShell \$PROFILE|user environment variables",
    re.IGNORECASE,
)


class _WindowsShapedOs:
    """Proxy for the ``os`` module: Windows separator and path rules, real rest."""

    pathsep = ";"
    sep = "\\"
    path = ntpath

    def __getattr__(self, name: str) -> Any:
        return getattr(os, name)


@pytest.fixture()
def context(tmp_path: Path) -> DoctorContext:
    return DoctorContext(home_dir=tmp_path)


@pytest.fixture()
def windows_shaped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run path_env as if on native Windows (``;`` separator, ntpath rules)."""
    monkeypatch.setattr(path_env_module, "os", _WindowsShapedOs(), raising=False)


def _write_settings(context: DoctorContext, settings: dict[str, Any]) -> None:
    context.claude_dir.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(json.dumps(settings))


def _write_settings_with_path(context: DoctorContext, path_value: str) -> None:
    _write_settings(context, {"env": {"PATH": path_value}})


def _bin(context: DoctorContext) -> str:
    return str(context.claude_dir / "bin")


# ---------------------------------------------------------------------------
# env.PATH present, host separator
# ---------------------------------------------------------------------------


def test_passes_when_claude_bin_in_path(context: DoctorContext) -> None:
    """BEHAVIOUR: a session whose env.PATH lists the bin dir resolves the shims."""
    _write_settings_with_path(
        context, os.pathsep.join(["/usr/bin", _bin(context), "/usr/local/bin"])
    )

    result = PathEnvCheck().run(context)

    assert result.passed is True


def test_fails_when_claude_bin_not_in_path(context: DoctorContext) -> None:
    """BEHAVIOUR: a session whose env.PATH omits the bin dir cannot resolve the shims."""
    _write_settings_with_path(context, os.pathsep.join(["/usr/bin", "/usr/local/bin"]))

    result = PathEnvCheck().run(context)

    assert result.passed is False
    assert result.remediation is not None


def test_env_path_without_bin_fails_even_when_inherited_path_has_it(
    context: DoctorContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BEHAVIOUR (issue #5, case 3): env.PATH REPLACES the inherited PATH, so a
    bin dir reachable only through the shell does not reach the session."""
    monkeypatch.setenv("PATH", os.pathsep.join([_bin(context), "/usr/bin"]))
    _write_settings_with_path(context, os.pathsep.join(["/usr/bin", "/bin"]))

    result = PathEnvCheck().run(context)

    assert result.passed is False


# ---------------------------------------------------------------------------
# env.PATH absent: the inherited PATH decides (issue #5, cases 1 and 2)
# ---------------------------------------------------------------------------


def test_passes_when_env_path_absent_and_bin_on_inherited_path(
    context: DoctorContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BEHAVIOUR (issue #5, case 1): with no env.PATH in settings.json the
    session inherits the shell PATH; the bin dir is on it, so the shims
    resolve and the doctor must pass."""
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", _bin(context), "/bin"]))
    _write_settings(context, {"hooks": {}})

    result = PathEnvCheck().run(context)

    assert result.passed is True, (
        "env.PATH is absent and the bin dir is on the inherited PATH, so a "
        f"session resolves the shims; doctor said: {result.message!r}"
    )


def test_fails_when_env_path_absent_and_bin_not_on_inherited_path(
    context: DoctorContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BEHAVIOUR (issue #5, case 2): with no env.PATH and the bin dir missing
    from the inherited PATH the shims do not resolve. The remediation names
    the bin dir and a shell-profile entry, and never steers the user into
    rewriting env.PATH (which re-introduces the synced-settings bug)."""
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin"]))
    _write_settings(context, {"hooks": {}})

    result = PathEnvCheck().run(context)

    assert result.passed is False
    assert result.remediation is not None
    assert _bin(context) in result.remediation
    assert _SHELL_PROFILE_HINT.search(result.remediation), (
        f"remediation must point at a shell-profile entry: {result.remediation!r}"
    )
    assert "nwave-ai install" not in result.remediation, (
        "remediation must not tell the user to run `nwave-ai install`: "
        f"{result.remediation!r}"
    )
    assert "env.PATH" not in result.remediation, (
        f"remediation must not tell the user to add env.PATH: {result.remediation!r}"
    )


# ---------------------------------------------------------------------------
# Normalized comparison (issue #5, case 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param("{bin}/", id="trailing-slash"),
        pytest.param("{claude}/./bin", id="dot-segment"),
        pytest.param("{claude}//bin", id="doubled-separator"),
        pytest.param("{claude}/bin/../bin", id="parent-segment"),
    ],
)
def test_env_path_bin_entry_matches_after_normalization(
    context: DoctorContext, spelling: str
) -> None:
    """BEHAVIOUR (issue #5, case 4): an env.PATH entry that names the bin dir
    with redundant segments, followed by a trailing PATH separator, is the
    same directory and the doctor must accept it."""
    entry = spelling.format(bin=_bin(context), claude=str(context.claude_dir))
    _write_settings_with_path(
        context, os.pathsep.join(["/usr/bin", entry]) + os.pathsep
    )

    result = PathEnvCheck().run(context)

    assert result.passed is True, f"{entry!r} names the bin dir: {result.message!r}"


# ---------------------------------------------------------------------------
# Windows-shaped env.PATH (issue #5, cases 3 and 4)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("windows_shaped")
def test_windows_env_path_with_bin_passes(context: DoctorContext) -> None:
    """BEHAVIOUR (issue #5, case 3): on Windows env.PATH is ``;``-separated and
    entries carry a drive colon; the bin dir as its own entry passes."""
    _write_settings_with_path(
        context,
        ";".join([r"C:\Windows\system32", _bin(context), r"C:\Windows"]),
    )

    result = PathEnvCheck().run(context)

    assert result.passed is True, result.message


@pytest.mark.usefixtures("windows_shaped")
def test_windows_env_path_without_bin_fails(context: DoctorContext) -> None:
    """BEHAVIOUR (issue #5, case 3): a ``;``-separated env.PATH lacking the bin
    dir fails."""
    _write_settings_with_path(
        context,
        ";".join([r"C:\Windows\system32", r"C:\Windows", r"C:\Program Files\Git\cmd"]),
    )

    result = PathEnvCheck().run(context)

    assert result.passed is False


@pytest.mark.usefixtures("windows_shaped")
def test_windows_env_path_bin_matches_case_insensitively(
    context: DoctorContext,
) -> None:
    """BEHAVIOUR (issue #5, case 4): Windows paths are case-insensitive, so the
    bin dir spelt in a different case, with a trailing slash and a trailing
    PATH separator, still matches."""
    _write_settings_with_path(
        context,
        ";".join([r"C:\Windows\system32", _bin(context).upper() + "\\"]) + ";",
    )

    result = PathEnvCheck().run(context)

    assert result.passed is True, result.message


# ---------------------------------------------------------------------------
# env.PATH frozen on another machine (issue #5, case 5)
# ---------------------------------------------------------------------------


def test_env_path_from_another_machine_is_reported(context: DoctorContext) -> None:
    """BEHAVIOUR (issue #5, case 5): a synced settings.json carries another
    machine's absolute PATH. Its ``.claude/bin`` entry points at a home that
    does not exist here, so the doctor must not pass, and must say the
    env.PATH looks like it came from another machine."""
    foreign_home = "/Users/nwave-foreign-user-does-not-exist"
    _write_settings_with_path(
        context,
        os.pathsep.join(
            [
                f"{foreign_home}/.claude/bin",
                f"{foreign_home}/.nvm/versions/node/v20.11.0/bin",
                "/usr/bin",
                "/bin",
            ]
        ),
    )

    result = PathEnvCheck().run(context)

    assert result.passed is False
    assert re.search(r"another machine", result.message, re.IGNORECASE), (
        "message must say env.PATH looks like it came from another machine: "
        f"{result.message!r}"
    )


def test_fails_gracefully_when_settings_absent(context: DoctorContext) -> None:
    """BEHAVIOUR: no settings.json -> passed=False with a remediation, no exception."""
    result = PathEnvCheck().run(context)

    assert result.passed is False
    assert result.remediation is not None
