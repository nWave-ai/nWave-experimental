"""PATH test support is separator-parametric (issue nWave-ai/nWave-experimental#5).

The state-delta PATH predicates, the ``path_strategy`` generator and the
faithful installer simulator hardcode ``":"``. That makes it impossible to
write property tests for Windows-shaped PATHs (``;`` separator, drive-colon
entries such as ``C:\\Windows``), which is exactly the shape the installer and
the doctor got wrong.

Seams assumed by these tests (the crafter implements them):

- ``prepended_with``, ``appended_with`` and ``idempotent_after`` resolve their
  default separator from ``os.pathsep`` at CALL time (``sep=None`` default),
  not at import time.
- ``path_strategy(..., sep=...)`` accepts a ``sep`` keyword (default
  ``os.pathsep``); with ``sep=";"`` it generates Windows-shaped entries
  (drive-letter absolute paths, including its "DES bin first" branch).
- ``update_path_in_settings_faithful(..., sep=...)`` accepts a ``sep``
  keyword (default ``os.pathsep``) and splits/joins with it.
"""

from __future__ import annotations

import inspect
import os
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from nwave_ai.state_delta import appended_with, idempotent_after, prepended_with
from nwave_ai.state_delta.strategies import (
    path_strategy,
    update_path_in_settings_faithful,
)


_WINDOWS_ENTRY = re.compile(r"^[A-Za-z]:\\")
_WINDOWS_DES_BIN = r"C:\Users\u\.claude\bin"

windows_entries = st.lists(
    st.sampled_from(
        [
            r"C:\Windows\system32",
            r"C:\Windows",
            r"C:\Program Files\Git\cmd",
            r"C:\Users\u\AppData\Local\Programs\Python\Python312",
            r"D:\tools\bin",
        ]
    ),
    min_size=1,
    max_size=5,
)


def _assert_accepts_sep(fn: object) -> None:
    assert "sep" in inspect.signature(fn).parameters, (  # type: ignore[arg-type]
        f"{getattr(fn, '__name__', fn)} must accept a `sep` keyword so tests can "
        "generate Windows-shaped PATHs (issue #5)"
    )


@pytest.mark.parametrize(
    ("factory", "old", "new"),
    [
        pytest.param(
            prepended_with,
            r"C:\Windows",
            rf"{_WINDOWS_DES_BIN};C:\Windows",
            id="prepended_with",
        ),
        pytest.param(
            appended_with,
            r"C:\Windows",
            rf"C:\Windows;{_WINDOWS_DES_BIN}",
            id="appended_with",
        ),
        pytest.param(
            idempotent_after,
            "",
            rf"{_WINDOWS_DES_BIN};C:\Windows",
            id="idempotent_after",
        ),
    ],
)
def test_path_predicates_default_to_platform_separator(
    monkeypatch: pytest.MonkeyPatch, factory: object, old: str, new: str
) -> None:
    """BEHAVIOUR (issue #5, case 8): with no explicit separator, the PATH
    predicates use the platform separator, so on Windows a ``;``-joined
    PATH satisfies them."""
    monkeypatch.setattr(os, "pathsep", ";")

    predicate = factory(_WINDOWS_DES_BIN)  # type: ignore[operator]

    assert predicate(old, new) is True, (
        f"{predicate.__name__} must split on os.pathsep (';' here): {new!r}"
    )


@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_path_strategy_generates_windows_shaped_paths(data: st.DataObject) -> None:
    """BEHAVIOUR (issue #5, case 8) — property: ``path_strategy(sep=";")``
    produces PATHs whose every ``;`` entry is a drive-letter Windows path."""
    _assert_accepts_sep(path_strategy)
    generated = data.draw(
        path_strategy(
            sep=";",
            include_home_literal=False,
            include_empty=False,
            include_legacy_fallback=False,
        )
    )

    entries = generated.split(";")
    assert all(_WINDOWS_ENTRY.match(e) for e in entries), (
        f"every ';' entry must be a Windows path: {generated!r}"
    )


@settings(max_examples=100, deadline=None)
@given(existing=windows_entries, live=windows_entries)
def test_faithful_simulator_prepends_with_semicolon_on_windows(
    existing: list[str], live: list[str]
) -> None:
    """BEHAVIOUR (issue #5, cases 6 and 8) — property: for any Windows-shaped
    env.PATH, the simulated install puts the bin dir as its own first ``;``
    entry and keeps every original entry intact, in order; with no prior
    env.PATH it seeds from the live ``;`` PATH the same way."""
    _assert_accepts_sep(update_path_in_settings_faithful)
    existing_path = ";".join(existing)
    live_path = ";".join(live)

    written = update_path_in_settings_faithful(
        existing_path, _WINDOWS_DES_BIN, r"C:\Users\u", live_path, sep=";"
    )
    seeded = update_path_in_settings_faithful(
        "", _WINDOWS_DES_BIN, r"C:\Users\u", live_path, sep=";"
    )

    assert written.split(";") == [_WINDOWS_DES_BIN, *existing]
    assert seeded.split(";") == [_WINDOWS_DES_BIN, *live]
