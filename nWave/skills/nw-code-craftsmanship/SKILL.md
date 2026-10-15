---
name: nw-code-craftsmanship
description: Universal OO/FP craftsmanship foundation — domain-language naming, small cohesive units, semantic DRY/SSOT, reuse-before-new, one owner per rule/config/fact, prefactoring before new behavior, ports/adapters for testability. Consult before writing or reviewing any unit of code, either paradigm.
user-invocable: false
disable-model-invocation: true
---

# Code Craftsmanship — Universal Foundation

**Kind**: KNOWLEDGE (reference). No forced sequence — consult while writing or reviewing a unit.
**Trigger**: authoring, extending, or reviewing code in either paradigm.

## Quality Axes

The crafter writes, and the reviewer judges, every changed unit on nine axes:

| Axis | The code shows it when |
|---|---|
| Readable | names come from the domain language and each unit reads as one intention |
| Encapsulated | state is private and changed only through the owner's behaviour; no internal type leaks across a boundary |
| Declarative | it states what the domain decides (expressions, pipelines, polymorphism) rather than step-by-step bookkeeping |
| Modular | each module has one reason to change and a narrow public surface |
| Performant | no avoidable allocation, copying, repeated I/O or quadratic work on a hot path |
| Maintainable | a requirement change touches one owner; no duplication of a rule |
| Decoupled | dependencies point inward through ports; collaborators are injected; connascence stays weak and local |
| Cohesive | data and the behaviour that uses it live together |
| Secure | inputs are parsed and validated at the boundary; paths are normalized and confined to their root; commands run as argv without shell interpolation; secrets never reach logs |

Tests are not the crafter's: the acceptance designer authors the oracle and its
supports, and those tests specify the behaviour. The crafter adds no unit tests;
design quality comes from the code, not from a growing suite of tests around it.

## Simple Design

Judge in this order: the behaviour is demonstrated by the tests; no semantic
duplication; maximal clarity; then the fewest elements. Removing a type or a
collaborator is an improvement only when the first three still hold.

## Coupling and Connascence

Checkable on the diff:

- Two units that must agree on a position, a literal value, the meaning of a
  value, an algorithm or a call order share a hidden agreement: replace it with
  a named type, a named constant or one owner that both call. Agreements on a
  name or a type are the acceptable ones.
- A unit reads another's data to decide (control flag, branch on its state,
  reach into its fields): move the decision to the data's owner and send it a
  message.
- A method groups steps only because they run in sequence, at the same time or
  on the same data: split it by responsibility.

## Naming and Shape

Names come from the domain language, not implementation mechanics. Units (functions, classes, modules) stay small and cohesive — one reason to change, one responsibility observable from the name.

## Semantic DRY / Single Source of Truth

Duplication is a SEMANTIC question, not a textual one. Before writing new logic, run reuse analysis: does an existing symbol already own this responsibility? One business rule, one config value, one fact has exactly ONE owner. Two algorithms independently deciding the same fact is a defect even when their code looks nothing alike — the risk is divergence, not the copy-paste.

Distinguish **coincidental similarity** (two units that happen to look alike but answer different questions, change for different reasons, owned by different authorities) from **shared responsibility** (two units answering the same question). Only the second is a DRY violation. Collapsing coincidental similarity into a shared abstraction creates a false dependency — the two callers now change together for no domain reason.

Search by responsibility, invariant and real consumers, not only matching names. For each relevant existing owner, explain whether it can be reused or extended; `CREATE_NEW` needs a concrete incompatibility or absent responsibility, not a preference for a fresh abstraction. A rule change must reach every known consumer through its one owner. Atomically derived projections or denormalized storage are not competing authorities when the owning rule and update invariant remain single.

Keep business decisions readable apart from SQL, transport and filesystem plumbing. Make wrong state unrepresentable with the type system: give a concept its own type (value object, record, choice type) when it can be confused with another concept, when its type can exclude invalid states, or when it owns a rule; its constructor refuses the invalid value. A native type that already says all of this stays native. Use precise native records, unions or result types at deliberate boundaries; document any generic payload boundary. Judge cohesion and consumer behavior, not file/class counts.

## Prefactoring Before New Behavior

The architect owns the applicability and selected preservation recipe in the canonical DESIGN grammar (`nw-design`). For an applicable move, the host observes a trustworthy existing GREEN baseline, then the same oracle/support content and argv/runtime on the intermediate state after only the declared movement, before feature behavior changes. Keep distinct production identities and before-move/after-move-before-behavior evidence; two finite GREEN runs support only those observations. A failing feature oracle is not the preservation baseline. No autonomous commit, extra review cycle or unrelated cleanup is implied.

## Ports and Adapters

Ports/adapters exist to make testing easy without leaking implementation details across the boundary. A driving port is a clean seam to test through; a driven port isolates an external dependency behind a swappable adapter. Neither port exposes internal types or private structure to its caller.

## SOLID and Object Calisthenics

For OO application/domain code, use SOLID (single responsibility, open/closed, Liskov substitution, interface segregation and dependency inversion) and the ten Object Calisthenics in `nw-code-design-oo`, strictly inside the hexagon. That skill also owns the rich domain model, the code smells hierarchy and the Refactoring Priority Premise order applied within each delta. Domain identity, lifecycle, aggregate consistency, repositories and domain events follow `nw-ddd-tactical` (OO) or `nw-fp-domain-modeling` (FP). Do not repeat their tables here.

## Both Paradigms, No Forced Framework

The shared readability, ownership, reuse and boundary principles apply in both paradigms; OO-specific constraints above stay scoped to OO application/domain code. A unit can be a function or module as much as a class. Never impose a generalized framework, abstraction layer, or plugin mechanism the current requirement does not need. Generalize only when a second real caller demands it.

## Role Boundary

The LLM (orchestrating agent) chooses and orchestrates the design; the crafter respects the design already selected and implements within it. When implementation surfaces a new ownership conflict (two candidate owners for the same rule/fact), the crafter raises it to the architect rather than picking one silently. A reviewer judges semantic duplication as part of review. None of this is a runtime gate — it is authoring and review discipline, not an enforced check.
