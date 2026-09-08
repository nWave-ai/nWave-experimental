"""The algebra obligation says what it rests on, in both directions.

ADR-SSOT-002 Section 1a item 6 asks for algebra-driven design. Naming the
observations, the laws and the preservation maps is the architect's work.
CHECKING them mechanically needs Agda or TLA+, and neither ships here.

Discord feedback, 2026-09-05: a tool absent without a warning. An obligation
nobody could mechanically check, reported as silence, reads as an obligation
met. Both branches are asserted here for exactly that reason -- a line printed
only on the unmet side would teach the reader that silence means met.
"""

from __future__ import annotations

import shutil

from des.domain.algebraic_modelling_tools import (
    ALGEBRAIC_CHECKERS,
    algebra_line,
    reachable_checkers,
)


def test_an_environment_without_a_checker_says_indeterminate_and_names_both(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    line = algebra_line()
    assert line.startswith("ALGEBRA: INDETERMINATE")
    for name in ALGEBRAIC_CHECKERS:
        assert name in line
    assert "Section 1a item 6" in line
    assert "install one of them" in line
    assert reachable_checkers() == ()


def test_an_environment_with_a_checker_says_so_rather_than_staying_silent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/agda" if name == "agda" else None
    )
    line = algebra_line()
    assert not line.startswith("ALGEBRA: INDETERMINATE")
    assert "agda" in line
    # It reports what it MEASURED -- a name on PATH -- and claims no more.
    # `shutil.which` finding a file called `tlc` is a designation; that the
    # file is a model checker is derived, and a derived claim can be wrong.
    assert "on PATH" in line
    assert "reachable" in line
    assert "checked mechanically" not in line
    assert reachable_checkers() == ("agda",)
