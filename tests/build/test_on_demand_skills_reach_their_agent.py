"""Every on-demand skill a role declares must reach that role's shipped spec.

Measured 2026-09-12 on the K4 quality axis. Six of six deliveries scored 0 on
"do property-based tests map generators to observations", and five of six on
"is a data invariant enforced BY CONSTRUCTION". Both disciplines ship as skills
and neither reached the point of use:

- `nw-property-based-testing` appeared ZERO times in `role-skill-loading.yaml`,
  so no role loaded it -- not the acceptance designer authoring the oracle.
- `nw-certainty-by-construction` was `catalog_only` for both crafters. That
  field is read by `agent_catalog.py` for build-time distribution and NEVER by
  the renderer that emits activation directives (`scripts/docgen.py:878-939`),
  so a catalogued skill produces no activation text at all.

Fixing the registry alone was not enough: the crafters' and acceptance
designer's specs carried no `GENERATED:role-skill-loading` region, so the
declaration had nowhere to land. Seven other agents had one; these three did
not, and nothing said so.

This pins the whole path in one assertion: a role that DECLARES an on-demand
skill must SHIP a directive naming it. The registry and the spec are two
halves of one fact, and a defect in either is invisible from the other.
"""

from __future__ import annotations

from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "nWave" / "data" / "role-skill-loading.yaml"
_AGENTS = _ROOT / "nWave" / "agents"


def test_every_on_demand_skill_reaches_its_agent_spec() -> None:
    registry = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    roles = registry["roles"]
    global_on_demand = registry.get("global_on_demand") or {}

    missing: list[str] = []
    for role, entry in roles.items():
        declared = entry.get("on_demand") or {}
        if not declared:
            continue
        spec = _AGENTS / f"{role}.md"
        if not spec.is_file():
            continue  # a role with no shipped spec of its own
        shipped = spec.read_text(encoding="utf-8")
        for skill in declared:
            if skill not in shipped:
                missing.append(f"{role} declares {skill}, its spec never names it")

    assert missing == [], (
        "WHAT: a role declares an on-demand skill that its shipped spec never "
        "names, so the agent is never told the skill exists:\n  "
        + "\n  ".join(missing)
        + "\n\nWHY: the declaration and the directive are two halves of one "
        "fact. A skill nobody is told to invoke is indistinguishable from a "
        "skill nobody wrote -- measured on K4, where two shipped disciplines "
        "were absent from every one of six deliveries.\n"
        "HOW: add the skill to that agent's GENERATED:role-skill-loading "
        "region, or remove the declaration from role-skill-loading.yaml if the "
        "role genuinely should not carry it."
    )

    global_missing = []
    for spec in sorted(_AGENTS.glob("nw-*.md")):
        role = spec.stem
        shipped = spec.read_text(encoding="utf-8")
        for skill in global_on_demand:
            if skill not in shipped:
                global_missing.append(
                    f"{role} must carry global on-demand skill {skill}"
                )
    assert global_missing == [], "\n".join(global_missing)
