"""Regression tests: the installer's env.PATH write is platform-portable.

Issue nWave-ai/nWave-experimental#5. ``DESPlugin._update_path_in_settings``
splits and joins PATH with a hardcoded ``":"``. On native Windows the PATH
separator is ``";"`` and every entry carries a drive colon (``C:\\``), so the
installer wrote ``C:\\Users\\u\\.claude\\bin:C:\\Windows\\system32;...``, whose
first entry is not a directory.

Bucket-(ii) behaviour (the installer still WRITES env.PATH, the provenance
receipt, fresh-install seeding) is deliberately NOT re-specified here; these
tests only pin the separator and the normalized idempotency.

Seam assumed by these tests (the crafter implements it):

- ``des_plugin`` reaches the platform through its module-global name ``os``
  at call time: ``os.pathsep`` for split/join, ``os.path.normpath`` and
  ``os.path.normcase`` for the "already present" comparison, ``os.environ``
  for the live PATH. Windows-shaped tests replace that module global with a
  proxy whose ``pathsep`` is ``";"`` and whose ``path`` is ``ntpath``.
"""

from __future__ import annotations

import json
import ntpath
import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from nwave_ai.state_delta import assert_state_delta, set_to

from scripts.install.plugins import des_plugin as des_plugin_module
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


_WINDOWS_DES_BIN = r"C:\Users\u\.claude\bin"
_WINDOWS_LIVE_ENTRIES = [
    r"C:\Windows\system32",
    r"C:\Windows",
    r"C:\Program Files\Git\cmd",
    r"C:\Users\u\AppData\Local\Programs\Python\Python312",
]


class _WindowsShapedOs:
    """Proxy for the ``os`` module: Windows separator and path rules, real rest."""

    pathsep = ";"
    sep = "\\"
    path = ntpath

    def __getattr__(self, name: str) -> Any:
        return getattr(os, name)


@pytest.fixture()
def windows_shaped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run des_plugin as if on native Windows (``;`` separator, ntpath rules)."""
    monkeypatch.setattr(des_plugin_module, "os", _WindowsShapedOs())


def _context(tmp_path: Path) -> InstallContext:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=tmp_path / "templates",
        logger=MagicMock(),
        project_root=tmp_path / "project",
    )


def _settings_state(settings_file: Path) -> dict[str, object]:
    """Port-exposed universe of settings.json: env.PATH, permissions, hooks."""
    config = (
        json.loads(settings_file.read_text(encoding="utf-8"))
        if settings_file.exists()
        else {}
    )
    return {
        "env.PATH": config.get("env", {}).get("PATH", ""),
        "permissions": json.dumps(config.get("permissions", {}), sort_keys=True),
        "hooks": json.dumps(config.get("hooks", {}), sort_keys=True),
    }


def _bin_appears_once(
    des_bin: str, sep: str, normalize: Callable[[str], str]
) -> Callable[[Any, Any], bool]:
    """Predicate: ``new`` keeps every entry of ``old`` and names des_bin once."""

    def _predicate(old: Any, new: Any) -> bool:
        target = normalize(des_bin)
        hits = [e for e in new.split(sep) if e and normalize(e) == target]
        return len(hits) == 1 and new.split(sep)[-len(old.split(sep)) :] == old.split(
            sep
        )

    _predicate.__name__ = f"bin_appears_once({des_bin!r}, sep={sep!r})"
    return _predicate


@pytest.mark.usefixtures("windows_shaped")
def test_windows_live_path_is_seeded_with_semicolon_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BEHAVIOUR (issue #5, case 6): on Windows, a fresh install seeds env.PATH
    from the live ``;``-separated PATH. Split on ``;``, the bin dir is its own
    first entry and every original entry follows intact, so Windows can
    resolve both the shims and the user's own tools."""
    context = _context(tmp_path)
    settings_file = context.claude_dir / "settings.json"
    monkeypatch.setenv("PATH", ";".join(_WINDOWS_LIVE_ENTRIES))

    before = _settings_state(settings_file)
    DESPlugin()._update_path_in_settings(context, _WINDOWS_DES_BIN)
    after = _settings_state(settings_file)

    assert_state_delta(
        before=before,
        after=after,
        universe={"env.PATH", "permissions", "hooks"},
        expected={
            "env.PATH": set_to(";".join([_WINDOWS_DES_BIN, *_WINDOWS_LIVE_ENTRIES]))
        },
    )


@pytest.mark.usefixtures("windows_shaped")
def test_windows_existing_env_path_is_prepended_with_semicolon_separator(
    tmp_path: Path,
) -> None:
    """BEHAVIOUR (issue #5, case 6): an existing ``;``-separated env.PATH gets
    the bin dir as a new first ``;`` entry, original entries untouched."""
    context = _context(tmp_path)
    settings_file = context.claude_dir / "settings.json"
    existing = ";".join(_WINDOWS_LIVE_ENTRIES)
    settings_file.write_text(json.dumps({"env": {"PATH": existing}}))

    before = _settings_state(settings_file)
    DESPlugin()._update_path_in_settings(context, _WINDOWS_DES_BIN)
    after = _settings_state(settings_file)

    assert_state_delta(
        before=before,
        after=after,
        universe={"env.PATH", "permissions", "hooks"},
        expected={"env.PATH": set_to(f"{_WINDOWS_DES_BIN};{existing}")},
    )


@pytest.mark.usefixtures("windows_shaped")
@pytest.mark.parametrize(
    "present_spelling",
    [
        pytest.param(_WINDOWS_DES_BIN, id="exact"),
        pytest.param(_WINDOWS_DES_BIN.lower(), id="different-case"),
        pytest.param(_WINDOWS_DES_BIN + "\\", id="trailing-backslash"),
    ],
)
def test_windows_reinstall_does_not_prepend_bin_twice(
    tmp_path: Path, present_spelling: str
) -> None:
    """BEHAVIOUR (issue #5, case 7): re-running install on Windows when env.PATH
    already names the bin dir (same directory, any case, trailing backslash)
    does not add a second bin entry and keeps every original entry."""
    context = _context(tmp_path)
    settings_file = context.claude_dir / "settings.json"
    existing = ";".join([present_spelling, *_WINDOWS_LIVE_ENTRIES])
    settings_file.write_text(json.dumps({"env": {"PATH": existing}}))

    before = _settings_state(settings_file)
    DESPlugin()._update_path_in_settings(context, _WINDOWS_DES_BIN)
    after = _settings_state(settings_file)

    assert_state_delta(
        before=before,
        after=after,
        universe={"env.PATH", "permissions", "hooks"},
        expected={
            "env.PATH": _bin_appears_once(
                _WINDOWS_DES_BIN,
                ";",
                lambda e: ntpath.normcase(ntpath.normpath(e)),
            )
        },
    )


@pytest.mark.parametrize(
    "present_suffix",
    [
        pytest.param("/", id="trailing-slash"),
        pytest.param("/.", id="dot-segment"),
    ],
)
def test_reinstall_does_not_prepend_bin_twice_when_spelt_differently(
    tmp_path: Path, present_suffix: str
) -> None:
    """BEHAVIOUR (issue #5, case 7): on the host platform, re-running install
    when env.PATH names the bin dir with a redundant trailing segment does not
    prepend a second copy of the same directory."""
    context = _context(tmp_path)
    settings_file = context.claude_dir / "settings.json"
    des_bin = str(context.claude_dir / "bin")
    existing = os.pathsep.join([des_bin + present_suffix, "/usr/local/bin", "/usr/bin"])
    settings_file.write_text(json.dumps({"env": {"PATH": existing}}))

    before = _settings_state(settings_file)
    DESPlugin()._update_path_in_settings(context, des_bin)
    after = _settings_state(settings_file)

    assert_state_delta(
        before=before,
        after=after,
        universe={"env.PATH", "permissions", "hooks"},
        expected={
            "env.PATH": _bin_appears_once(
                des_bin, os.pathsep, lambda e: os.path.normcase(os.path.normpath(e))
            )
        },
    )
