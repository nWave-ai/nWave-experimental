"""The dispatcher registration-contract gate (slice-06).

slice-06 (created by DISTILL, implemented by DELIVER). The RULE: *every row of a
subcommand registry must RESOLVE, IMPORT, and expose a CALLABLE entry attribute*
(the dispatcher's wiring contract — ``des.cli.__main__._REGISTRY`` per
F-DES-SINGLE-ENTRY-POINT-CONSOLIDATION). A dropped or half-wired row — its
module unimportable, or its ``main`` missing / non-callable — is a registration
breach the gate MUST catch so a dropped-registration regression cannot pass
green.

Unlike the AST-source gates in this family (M1/M8/M9/CM-I), this gate is
IMPORT-RESOLUTION, not AST. It runs IN-PROCESS via ``importlib`` only — NO
``ast``, NO ``git``, NO subprocess, NO real I/O beyond importing the registered
modules. The gate is count-agnostic by construction: it iterates whatever rows
the registry exposes, so a newly-added valid subcommand row is auto-covered with
zero per-subcommand authoring.

The registry is read LIVE (the caller passes ``des.cli.__main__._REGISTRY`` or a
golden-fixture registry). The gate reads each row's ``name``, ``module_path``,
and entry-attribute name structurally (duck-typed over the row's attributes), so
it works against both the live ``_SubcommandRow`` (whose entry attr field is
``function_name``) and the fixtures (``entry_attr``) without coupling to either.

RED scaffold (Mandate 7): ``check_registry`` raises ``AssertionError`` (DELIVER
implements the resolution). The gate is therefore RED (implementation missing),
not BROKEN.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from collections.abc import Iterable


class RegistryRow(Protocol):
    """The structural shape the gate reads off each registry row (duck-typed).

    Every row exposes the operator-visible ``name`` and the dotted
    ``module_path``. The entry-attribute name lives under whichever field the
    row's source uses — ``function_name`` on the live ``_SubcommandRow``,
    ``entry_attr`` on the golden fixtures — so both are declared optional and
    read structurally (never coupling to one source).
    """

    name: str
    module_path: str
    function_name: str | None
    entry_attr: str | None


# The entry-attribute field name varies by registry source: the live
# ``_SubcommandRow`` exposes it as ``function_name``; the golden fixtures expose
# it as ``entry_attr``. The gate reads whichever the row carries (duck-typed),
# never coupling to one source.
_ENTRY_ATTR_FIELDS = ("function_name", "entry_attr")


class RegistrationBreachKind(Enum):
    """The kind of registration breach a row carries (port-exposed).

    UNIMPORTABLE_MODULE — the row's ``module_path`` resolves to no importable
                          module (the module was dropped / renamed).
    ENTRY_NOT_CALLABLE  — the module imports but its declared entry attribute is
                          missing or is not callable (the ``main`` was dropped /
                          the module was never wired as a subcommand).
    """

    UNIMPORTABLE_MODULE = "unimportable_module"
    ENTRY_NOT_CALLABLE = "entry_not_callable"


@dataclass(frozen=True)
class RegistrationBreach:
    """A flagged registration breach (port-exposed observable).

    ``row_name``    — the operator-visible subcommand name of the offending row.
    ``module_path`` — the dotted module path the row points at.
    ``kind``        — which half of the contract the row fails.
    """

    row_name: str
    module_path: str
    kind: RegistrationBreachKind


@dataclass(frozen=True)
class RegistrationVerdict:
    """The port-exposed result of checking a registry against the contract.

    ``breaches``   — the offending rows (empty == conformant). Names each dropped
                     or half-wired row so a regression is pinpointed.
    ``conformant`` (derived) — True iff ``breaches`` is empty, i.e. every row
                     resolves, imports, and exposes a callable entry.
    ``row_count``  — how many rows the gate checked (port-observable; proves the
                     gate is count-agnostic — it scaled to the live registry's
                     size without per-row authoring).
    """

    breaches: tuple[RegistrationBreach, ...]
    row_count: int

    @property
    def conformant(self) -> bool:
        return not self.breaches


def check_registry(registry: Iterable[RegistryRow]) -> RegistrationVerdict:
    """Verify every row of ``registry`` resolves, imports, and exposes a
    callable entry attribute.

    Iterates the rows the registry exposes (count-agnostic), imports each row's
    module via ``importlib.import_module``, and confirms the row's entry
    attribute is present and callable. Returns a ``RegistrationVerdict`` naming
    any dropped or half-wired rows.

    RED scaffold (Mandate 7): DELIVER implements the import-resolution walk.
    """
    breaches: list[RegistrationBreach] = []
    row_count = 0
    for row in registry:
        row_count += 1
        entry_name = _entry_attr_name(row)
        try:
            module = importlib.import_module(row.module_path)
        except ImportError:
            breaches.append(
                RegistrationBreach(
                    row.name,
                    row.module_path,
                    RegistrationBreachKind.UNIMPORTABLE_MODULE,
                )
            )
            continue
        entry = getattr(module, entry_name, None)
        if not callable(entry):
            breaches.append(
                RegistrationBreach(
                    row.name,
                    row.module_path,
                    RegistrationBreachKind.ENTRY_NOT_CALLABLE,
                )
            )
    return RegistrationVerdict(breaches=tuple(breaches), row_count=row_count)


def _entry_attr_name(row: RegistryRow) -> str:
    """Read the name of the row's entry attribute, duck-typed over the field
    name the row's source uses (``function_name`` live, ``entry_attr`` fixture).
    """
    name: str = next(
        getattr(row, field)
        for field in _ENTRY_ATTR_FIELDS
        if getattr(row, field, None) is not None
    )
    return name
