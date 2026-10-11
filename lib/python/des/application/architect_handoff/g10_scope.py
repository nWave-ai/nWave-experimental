"""What a section may cite. A section at `shared` cites shared entries only; a section at `value:N`
cites shared entries and entries of the same value. This is the locality of the projection, applied to
the joins: a reference that the projection of value N would cut is a defect, not a silent dangling id."""

from __future__ import annotations

import dataclasses as dc

from . import g10_types as T
from .g10_codec import canon


@dc.dataclass(frozen=True)
class Visible:
    runs: dict[str, T.Run]
    models: dict[str, T.Model]
    laws: frozenset[str]
    observations: frozenset[str]
    constructors: frozenset[str]
    generators: frozenset[str]
    constructions: frozenset[str]


def scopes_for(scope: str) -> tuple[str, ...]:
    return ("shared",) if scope == "shared" else ("shared", scope)


def visible(h: T.Handoff, scope: str) -> Visible:
    runs: dict[str, T.Run] = {}
    models: dict[str, T.Model] = {}
    laws: set[str] = set()
    obs: set[str] = set()
    ctors: set[str] = set()
    gens: set[str] = set()
    cons: set[str] = set()
    for (kind, sc), e in sorted(h.items()):
        if sc not in scopes_for(scope) or not isinstance(e.status, T.Applicable):
            continue
        p = e.status.payload
        if kind == "receipts":
            runs.update(
                {r.id: r for r in sorted(p.runs, key=canon)}
            )  # a repeated id must not make the result depend on list order
        elif kind == "model":
            models.update({m.id: m for m in sorted(p.models, key=canon)})
        elif kind == "laws":
            laws.update(x.id for x in p.laws)
            obs.update(x.id for x in p.observations)
            ctors.update(x.id for x in p.constructors)
            gens.update(x.id for x in p.generators)
        elif kind == "construction":
            cons.update(c.id for c in p.claims)
    return Visible(
        runs,
        models,
        frozenset(laws),
        frozenset(obs),
        frozenset(ctors),
        frozenset(gens),
        frozenset(cons),
    )
