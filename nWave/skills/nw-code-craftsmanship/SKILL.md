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

## FP-Specific Dependency Injection

In functional code, dependency injection is achieved through composition, not frameworks. Three idiomatic patterns:

- **Currying / partial application** — partially apply a dependency (e.g., a repository function) to produce a new function; the caller sees only the remaining arguments. Prefer this for single-dependency scenarios where the injected value is stable for a computation's lifetime.
- **Reader monad / environment record** — thread a shared read-only environment (config, clock, logger, repo) through a chain of functions via an explicit `env` parameter or a Reader-typed computation. Use when three or more functions in a pipeline need the same shared capabilities. Avoid implicit global singletons — they make units untestable.
- **Effect types as port abstractions** — in typed FP (Haskell, Scala ZIO, PureScript, F#, Kotlin with Arrow), represent side-effects as typed capabilities (`IO`, `ZIO[R,E,A]`, `Eff`). The port is the effect type signature; adapters swap the interpreter. This is the FP analogue of the driven-port/adapter split.

Choose the lightest-weight form that preserves testability: currying for a single collaborator, Reader/env record for a shared context, typed effects when the language supports it and the boundary is meaningful. Never impose a monad stack or effect library when the function takes a plain argument.

## FP-Specific Hexagonal Architecture

The same port/adapter principle applies in FP, but immutability changes the texture:

- **Driving ports** are pure functions or types expressing the public interface. A driving adapter converts external input (HTTP request, CLI arg) into the domain's algebraic types.
- **Driven ports** are functions passed as arguments (or captured in an environment record) rather than interface implementations. An in-memory adapter is a pure function; a real adapter runs in IO.
- **Immutability boundary** — domain logic is pure; the IO/effect boundary is the adapter. Do not let IO leak into domain functions. A function that produces a value from inputs is always testable without mocking.
- **Effect types as driven ports** — a `Clock`, `Logger`, or `Repo` capability injected as an effect type is the FP hexagonal pattern. Test with a pure interpreter; deploy with the real interpreter.

The boundary invariant: the domain module must compile and test without importing any adapter. If it imports an HTTP client or a DB driver, the boundary has leaked.

## Usable Design for Algebraic APIs

Algebraic APIs (typeclasses, monoidal structures, combinators) require extra naming and discoverability discipline because their power is non-obvious:

- **Operation naming** — prefer names from the problem domain (`merge`, `combine`, `validate`) over mathematical names (`mappend`, `fold`) unless the mathematical name is universally understood in the team's context. The first goal is legibility at the call site.
- **Discoverability** — group related combinators in one module with a clear module name. A `Parser` module that exports `map`, `flatMap`, `or`, `many`, `between` is navigable; scattering them across utils is not. Document the composition laws (associativity, identity) as property tests, not prose.
- **Composition laws as tests** — laws are executable contracts. A monoid must satisfy `combine(a, identity) == a` and `combine(combine(a,b),c) == combine(a,combine(b,c))`. Write these as parametric property tests; they double as usage examples.
- **Minimal footprint** — expose the smallest orthogonal set of primitives from which callers can derive everything else. A combinator expressible from existing primitives should not be a first-class API member unless it appears in three or more call sites (Rule of Three).

## Role Boundary

The LLM (orchestrating agent) chooses and orchestrates the design; the crafter respects the design already selected and implements within it. When implementation surfaces a new ownership conflict (two candidate owners for the same rule/fact), the crafter raises it to the architect rather than picking one silently. A reviewer judges semantic duplication as part of review. None of this is a runtime gate — it is authoring and review discipline, not an enforced check.
