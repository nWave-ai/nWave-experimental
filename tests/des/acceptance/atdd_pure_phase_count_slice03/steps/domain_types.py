"""Typed domain concepts for the skill-prose-to-runtime parity slice (Mandate-12).

Slice-03 of fix-atdd-pure-spine-phase-count-reduction. The domain nouns:

* the *documented phase model* — the phase set a human reads in the nw-deliver
  skill prose;
* the *runtime phase model* — the canonical phase set the live runtime projects
  through the shipped ``des.cli.phases`` driving port;
* the *parity verdict* — whether the documentation agrees with the runtime.

All logic that derives the runtime set lives in the composition-root service
(``composition.py``). These types only NAME the concepts; they hold no business
logic beyond typed construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PhaseFormat(Enum):
    """Output format accepted by the phases driving port."""

    JSON = "json"
    TEXT = "text"


class DeliverySkill(Enum):
    """A skill artifact whose prose documents a phase model."""

    NW_DELIVER = "nw-deliver"


@dataclass(frozen=True)
class RuntimePhaseModel:
    """The canonical phase model as projected by the live runtime CLI.

    Derived from the shipped ``des.cli.phases --format json`` driving port so
    the parity check cannot drift from the runtime: the expected set IS the
    runtime set, never a hand-restated literal.
    """

    canonical_names: frozenset[str]
    count: int

    @classmethod
    def from_cli_json(cls, stdout: str) -> RuntimePhaseModel:
        import json

        payload = json.loads(stdout)
        names = frozenset(payload["phases"])
        return cls(canonical_names=names, count=payload["count"])


@dataclass(frozen=True)
class DocumentedPhaseModel:
    """The phase model a reader extracts from a skill's prose artifact."""

    prose: str
