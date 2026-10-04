---
name: nw-code-craftsmanship
description: Universal OO/FP craftsmanship foundation — domain-language naming, small cohesive units, semantic DRY/SSOT, reuse-before-new, one owner per rule/config/fact, prefactoring before new behavior, ports/adapters for testability. Consult before writing or reviewing any unit of code, either paradigm.
user-invocable: false
disable-model-invocation: true
---

# Code Craftsmanship — Universal Foundation

**Kind**: KNOWLEDGE (reference). No forced sequence — consult while writing or reviewing a unit.
**Trigger**: authoring, extending, or reviewing code in either paradigm.

## Naming and Shape

Names come from the domain language, not implementation mechanics. Units (functions, classes, modules) stay small and cohesive — one reason to change, one responsibility observable from the name.

## Semantic DRY / Single Source of Truth

Duplication is a SEMANTIC question, not a textual one. Before writing new logic, run reuse analysis: does an existing symbol already own this responsibility? One business rule, one config value, one fact has exactly ONE owner. Two algorithms independently deciding the same fact is a defect even when their code looks nothing alike — the risk is divergence, not the copy-paste.

Distinguish **coincidental similarity** (two units that happen to look alike but answer different questions, change for different reasons, owned by different authorities) from **shared responsibility** (two units answering the same question). Only the second is a DRY violation. Collapsing coincidental similarity into a shared abstraction creates a false dependency — the two callers now change together for no domain reason.

Search by responsibility, invariant and real consumers, not only matching names. For each relevant existing owner, explain whether it can be reused or extended; `CREATE_NEW` needs a concrete incompatibility or absent responsibility, not a preference for a fresh abstraction. A rule change must reach every known consumer through its one owner. Atomically derived projections or denormalized storage are not competing authorities when the owning rule and update invariant remain single.

Keep business decisions readable apart from SQL, transport and filesystem plumbing. Use precise native records, unions or result types at deliberate boundaries; document any generic payload boundary. Prefer the smallest representation that excludes a demonstrated invalid state. Do not impose a hierarchy, smart constructor, primitive wrapper or extra allocation when a native type and existing invariant owner suffice. Judge cohesion and consumer behavior, not file/class counts.

## Prefactoring Before New Behavior

The architect owns the applicability and selected preservation recipe in the canonical DESIGN grammar (`nw-design`). For an applicable move, the host observes a trustworthy existing GREEN baseline, then the same oracle/support content and argv/runtime on the intermediate state after only the declared movement, before feature behavior changes. Keep distinct production identities and before-move/after-move-before-behavior evidence; two finite GREEN runs support only those observations. A failing feature oracle is not the preservation baseline. No autonomous commit, extra review cycle or unrelated cleanup is implied.

## Ports and Adapters

Ports/adapters exist to make testing easy without leaking implementation details across the boundary. A driving port is a clean seam to test through; a driven port isolates an external dependency behind a swappable adapter. Neither port exposes internal types or private structure to its caller.

## SOLID and Object Calisthenics

For OO application/domain code, use SOLID (single responsibility, open/closed, Liskov substitution, interface segregation and dependency inversion). `nw-code-design-oo` owns the scoped calisthenics as design heuristics, not compulsory syntax, wrappers, size gates or allocation. Do not repeat its table here.

## Both Paradigms, No Forced Framework

The shared readability, ownership, reuse and boundary principles apply in both paradigms; OO-specific constraints above stay scoped to OO application/domain code. A unit can be a function or module as much as a class. Never impose a generalized framework, abstraction layer, or plugin mechanism the current requirement does not need. Generalize only when a second real caller demands it.

## Role Boundary

The LLM (orchestrating agent) chooses and orchestrates the design; the crafter respects the design already selected and implements within it. When implementation surfaces a new ownership conflict (two candidate owners for the same rule/fact), the crafter raises it to the architect rather than picking one silently. A reviewer judges semantic duplication as part of review. None of this is a runtime gate — it is authoring and review discipline, not an enforced check.
