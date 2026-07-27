"""The installer must not die on a legacy Windows console encoding.

``print_logo`` emits block-drawing glyphs and wave emoji. On a cp1252 console
-- still the default on a non-UTF-8 Windows box -- writing any of them raises
UnicodeEncodeError, and because the logo prints before any real work, the
install fails at the very first line of output.
"""

from __future__ import annotations

import io
import sys

import pytest

from scripts.install.install_nwave import _force_utf8_console, print_logo


#: Every character the logo emits that cp1252 cannot represent.
CP1252_HOSTILE = ["▀", "▁", "▂", "▄", "█", "\U0001f30a"]


def _cp1252_console() -> io.TextIOWrapper:
    """A stream that behaves like a strict cp1252 Windows console."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")


@pytest.mark.parametrize("glyph", CP1252_HOSTILE)
def test_the_glyph_really_is_hostile_to_cp1252(glyph: str) -> None:
    """Guards the premise: if these ever became encodable the test is moot."""
    with pytest.raises(UnicodeEncodeError):
        glyph.encode("cp1252")


def test_forcing_utf8_lets_the_logo_print_on_a_cp1252_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = _cp1252_console()
    monkeypatch.setattr(sys, "stdout", console)

    _force_utf8_console()
    print_logo()

    console.flush()
    rendered = console.buffer.getvalue().decode("utf-8")  # type: ignore[attr-defined]
    assert "\U0001f30a" in rendered


def test_force_utf8_console_is_safe_when_the_stream_cannot_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stream without ``reconfigure`` must not turn a cosmetic call into a crash."""

    class _Bare(io.StringIO):
        reconfigure = None  # type: ignore[assignment]

    monkeypatch.setattr(sys, "stdout", _Bare())
    monkeypatch.setattr(sys, "stderr", _Bare())

    _force_utf8_console()
