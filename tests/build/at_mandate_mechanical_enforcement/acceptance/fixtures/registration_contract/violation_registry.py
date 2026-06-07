"""GOLDEN FIXTURE (planted-violation / dropped-or-broken registry) —
registration-contract.

This is NOT the live ``des`` registry; it is the recall-half corpus for the
slice-06 registration contract. It carries a fully-wired row (so the gate is not
trivially flagging everything) PLUS two planted breaches that a dropped or
half-wired registration produces:

  * UNIMPORTABLE_ROW   — a row whose ``module_path`` resolves to no module
                         (the module was dropped / renamed). ``import_module``
                         raises ``ModuleNotFoundError``.
  * MAIN_MISSING_ROW   — a row whose module imports cleanly but exposes no
                         callable ``main`` entry (the entry attribute was
                         dropped / the module was never wired as a subcommand).

The gate MUST flag the registry non-conformant and MUST name BOTH offending
rows so a regression that drops a registration cannot pass green. A gate that
cannot catch the importability gap of a dropped row is itself testing-theater
(ADR-TEST-002 D-E golden-fixture-AT meta-rule; the slice-06 learning hypothesis
is disproved if it cannot).

The row shape mirrors the live ``des.cli.__main__._SubcommandRow`` WITHOUT
importing it — the fixture never transcribes the live subcommand names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureRow:
    """A registry row in the shape the registration contract reads."""

    name: str
    module_path: str
    entry_attr: str = "main"


_CLEAN_PKG = (
    "tests.build.at_mandate_mechanical_enforcement.acceptance"
    ".fixtures.registration_contract.clean_subcommands"
)
_BROKEN_PKG = (
    "tests.build.at_mandate_mechanical_enforcement.acceptance"
    ".fixtures.registration_contract.broken_subcommands"
)

# The name of the row whose module cannot be imported (dropped module path).
UNIMPORTABLE_ROW_NAME = "dropped-module"

# The name of the row whose module imports but exposes no callable ``main``.
MAIN_MISSING_ROW_NAME = "main-missing"

# A well-formed row + two planted breaches. The gate clears the wired row and
# names both broken rows.
VIOLATION_REGISTRY: tuple[FixtureRow, ...] = (
    FixtureRow("wired-alpha", f"{_CLEAN_PKG}.wired_alpha", "main"),
    FixtureRow(
        UNIMPORTABLE_ROW_NAME,
        f"{_BROKEN_PKG}.this_module_was_dropped",
        "main",
    ),
    FixtureRow(
        MAIN_MISSING_ROW_NAME,
        f"{_BROKEN_PKG}.main_missing",
        "main",
    ),
)
