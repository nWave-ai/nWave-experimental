"""Outcome value object — immutable record of a shipped capability.

Frozen dataclass with tuple-typed collections (Object Calisthenics
Rule 4: first-class collections, immutable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


OutcomeKind = Literal["specification", "operation", "invariant"]


@dataclass(frozen=True)
class InputShape:
    """One input shape (name + canonical type expression)."""

    shape: str


@dataclass(frozen=True)
class OutputShape:
    """The output shape (canonical type expression)."""

    shape: str


@dataclass(frozen=True)
class Outcome:
    """A registered outcome — one shipped capability, identified by id.

    Tuples (not lists) for collections — value objects are immutable.
    """

    id: str
    kind: OutcomeKind
    summary: str
    feature: str
    inputs: tuple[InputShape, ...]
    output: OutputShape
    keywords: tuple[str, ...]
    artifact: str
    related: tuple[str, ...]
    superseded_by: str | None
