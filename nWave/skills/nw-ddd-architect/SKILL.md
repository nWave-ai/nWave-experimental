---
name: nw-ddd-architect
description: DDD architect design-time mandates — the Fixture-Fanout Enumeration Mandate for shared-substrate per-caller migration (enumerate production callers plus fixture sites plus atomic bundle scope, mechanically enforced) that both the ddd-architect and its reviewer load by name
user-invocable: false
disable-model-invocation: true
---

# DDD Architect — design-time mandates

The `nw-ddd-architect` agent and `nw-ddd-architect-reviewer` both instruct loading this file
by name (`~/.claude/skills/nw-ddd-architect/SKILL.md`) at DESIGN entry, before any DESIGN row
is authored. It carries the design-time mandates that must be in context BEFORE the domain
model is authored. Strategic/tactical/event-modeling knowledge lives in the sibling skills
(`nw-ddd-strategic`, `nw-ddd-tactical`, `nw-ddd-event-modeling`, `nw-ddd-eventsourcing`); this
core holds the cross-cutting enforcement mandates the agent spec references.

## Fixture-Fanout Enumeration Mandate

`F-DDD-ARCHITECT-SKILL-FIXTURE-FANOUT-GATE` (M51 R-M51-B closure, 2026-05-25) — a
mechanically-enforced design-time gate.

**When it fires.** A DESIGN row that migrates a **shared substrate per-caller** — an adapter /
ledger / plugin whose construction or seed surface is shared between production and test
composition. Trigger by either signal:
- the row's `Decision = PER_CALLER_MIGRATION`, OR
- the substrate type matches the pattern `[A-Z]\w+Ledger | [A-Z]\w+Adapter | [A-Z]\w+Plugin`
  AND is constructed in BOTH `src/` and `tests/` (e.g. `AtCompletionLedger`).

**What the row MUST enumerate (with grep evidence).** Three cells, all mandatory:
- **(a) Production Callers** — every production callsite, `file:line` for each.
- **(b) Fixture Sites** — every test-composition / helper / `conftest` entry that CONSTRUCTS or
  SEEDS the same substrate. This is the cell that is silently omitted — and its omission is the
  M50 defect class: the substrate ships GREEN against its own ATs and breaks sibling consumers
  at the crafter's empirical run.
- **(c) Atomic Bundle Scope** — the row explicitly states `production sites {N} + fixture sites
  {M} ship together in slice {S}`. Production sites + fixture sites that read/write the SAME
  substrate path MUST ship in ONE slice; splitting them across slices is the violation.

**Why (empirical anchors).** friction #42 `F-M40-SLICE-02C-N1-PRODUCTION-FIXTURE-NOT-ATOMIC`
(M50 crafter — 3 production callsites declared, 5+ fixture sites silently excluded → 12 sibling
regressions, REVERTED). A 5-instance META-pattern (#33 M34 + #38 M42 + #40 M45 + #42 M50 + #43
M49) all surfaced ONLY at the crafter's empirical execution despite architect residuality
passes — the Streetlight bias: M50 declared 7 sites where empirical run found 18 (2.5× undercount).
The eye does not see the fixture fanout; the mechanical grep does.

**Mechanical procedure + rejection rule (self-execution; the reviewer runs the same).**
1. grep the DESIGN section for rows matching the substrate-migration trigger above.
2. For each, extract the `Production Callers:` count + `Fixture Sites:` count + `Atomic Bundle:`
   cell.
3. Run INDEPENDENT grep counts against the real tree:
   - production: `grep -rn '<substrate_pattern>' src/des/ | wc -l`
   - fixtures: `grep -rln '<substrate_pattern>' tests/ | xargs grep -c '<substrate_pattern>' | awk -F: '{s+=$2} END {print s}'`
4. **REJECT (critical BLOCKER)** on ANY of: a missing cell (Production Callers / Fixture Sites /
   Atomic Bundle Scope), a declared-vs-empirical count mismatch (off-by-N% for any N > 0), or an
   Atomic Bundle that splits production from fixtures across slices. A row that lists production
   callers but omits the fixture-sites enumeration is the silent-fixture-fanout defect — block it.

**Defense-in-depth.** Complements F-D-09 (Forbidden-Import-Roots) + the runtime cascade-detector
arch test (registry-vs-frozenset symmetry). The architect declares the enumeration (principle 9);
the reviewer re-runs the greps and blocks on mismatch (principle 6); neither trusts the other's
count — the grep is the arbiter.
