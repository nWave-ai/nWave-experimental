"""GOLDEN FIXTURE (clean / fully-wired registry) — registration-contract.

This is NOT the live ``des`` registry; it is the precision-half corpus for the
slice-06 registration contract. Every row points at a leaf module that imports
cleanly AND exposes a callable ``main`` — exactly the contract the live
dispatcher rows satisfy.

The gate MUST clear every row (``check_registry(...).conformant is True``, zero
unresolved rows). A gate that flags this fully-wired registry is over-firing —
the precision failure the clean fixture exists to catch.

The row shape mirrors the live ``des.cli.__main__._SubcommandRow`` (name,
module_path, entry attribute) WITHOUT importing it — the fixture is a
self-contained corpus, so it never transcribes the live subcommand names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureRow:
    """A registry row in the shape the registration contract reads."""

    name: str
    module_path: str
    entry_attr: str = "main"


_PKG = (
    "tests.build.at_mandate_mechanical_enforcement.acceptance"
    ".fixtures.registration_contract.clean_subcommands"
)

# Every row resolves, imports, and exposes a callable ``main`` — the clean
# corpus. More than one row, so the gate is exercised over the whole set.
CLEAN_REGISTRY: tuple[FixtureRow, ...] = (
    FixtureRow("wired-alpha", f"{_PKG}.wired_alpha", "main"),
    FixtureRow("wired-beta", f"{_PKG}.wired_beta", "main"),
)
