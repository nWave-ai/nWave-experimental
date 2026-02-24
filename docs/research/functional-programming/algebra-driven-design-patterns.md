# Algebra-Driven Design Patterns

Patterns for designing software by specifying rules (equations) that operations must satisfy, then deriving implementations from those rules.

---

## Why Algebraic Thinking Matters

Code is the wrong level of abstraction for design work. When you start with data structures and algorithms, you inherit unnecessary constraints that limit composability. Instead:

- **Specify rules first, implement second.** State what equations must hold between operations. The implementation is a solution to that system of equations.
- **Rules generate tests automatically.** Every rule is directly a property test. One rule generates thousands of test cases.
- **Rules reveal missing features.** Algebraic analysis of your rules often exposes operations you need but have not designed yet.
- **Rules catch contradictions early.** A contradiction found during design costs minutes; the same contradiction found in production costs days.

---

## The Design Process

1. **Start with scope, not implementation.** Know what problem you are solving. Do not decide on data structures upfront.

2. **Define observations first.** How do users extract information from the system? Observations define equality: two values are equal if no observation can distinguish them. This gives enormous implementation freedom.

3. **Add operations incrementally.** For each new operation, immediately write rules connecting it to existing operations. This web of rules IS the design.

4. **Let messy rules signal problems.** When rules become complex, your building blocks are too coarse-grained. Decompose until each rule is nearly trivial. Simple rules = good decomposition.

5. **Generalize aggressively.** Remove unnecessary type constraints. If most operations do not inspect contained values, parameterize over them.

---

## Algebraic Structures (Simplest to Most Powerful)

These are recurring patterns in software. Recognizing them unlocks known rules and capabilities.

### [STARTER] Combinable Values (Semigroup)

A type with one merge operation where grouping does not matter: `(a merge b) merge c = a merge (b merge c)`.

**When it matters**: Whenever you combine things and parenthesization should not matter.
**Examples**: String concatenation, config merging, min/max.

### [STARTER] Combinable Values with a Default (Monoid)

A Combinable Value that also has an "empty" or "default" element that is inert under combination.

**When it matters**: Whenever you need safe defaults, fold operations, or "nothing happened yet" values.
**Examples**: `(+, 0)`, `(*, 1)`, `(concat, [])`, `(and, true)`.
**Design signal**: If you find an associative operation, look for a default element. Finding one enables fold/reduce over collections.

### [INTERMEDIATE] Merge-and-Forget Values (Semilattice)

A Combinable Value where merging is also order-independent and merging the same thing twice changes nothing.

**When it matters**: Conflict resolution, eventually-consistent systems, CRDTs.
**Design signal**: When combining the same evidence twice should not change anything, and order of evidence should not matter.
**Example**: A status tracker with ordering `seen < failed < completed` uses `max` as the merge operation.

### [INTERMEDIATE] Structure-Preserving Transformations (Functor)

A container type where you can transform the contents without changing the structure. The transformation must preserve identity and composition.

**When it matters**: When operations work on the shape of data rather than the values inside.
**Design signal**: If most of your operations are agnostic to the contained type, you likely have one of these.

### [ADVANCED] Combinable Containers (Applicative Functor)

A container where you can combine contents element-wise and fill containers with uniform values.

**When it matters**: When you need to combine containers that hold different types of content.
**Design signal**: If your observation maps to a type that supports this pattern, your type likely does too ("the instance's observation follows the observation's instance").

### [ADVANCED] Reversible Operations (Group)

A Combinable Value with Default where every element has an inverse that cancels it out.

**When it matters**: Undo operations, spatial transformations.
**Example**: Clockwise and counter-clockwise rotation are inverses; horizontal flip is its own inverse.

---

## Properties of a Well-Designed API

These eight properties group into three categories:

### Clarity (the API communicates well)
- **Compositional**: Complex values built from simpler ones; understanding small pieces gives understanding of the whole
- **Task-relevant**: Operations provide high-level functionality useful to actual users
- **Interrelated**: Rules connect every operation to others in the API

### Economy (the API has no waste)
- **Parsimonious**: Each operation does one thing well; minimal redundancy
- **Orthogonal**: No half-baked concept shared across multiple operations
- **Generalized**: Unnecessary type constraints removed; polymorphic where possible

### Safety (the API prevents mistakes)
- **Closed**: Every syntactically valid construction is semantically valid; no error conditions
- **Complete**: Maximum algebraic structure discovered for every concept (e.g., finding default elements)

---

## Refactoring Techniques

### Decompose Large Operations

When rules become complex, the building blocks are too coarse. Split operations that take many parameters into smaller, orthogonal ones. If a rule ignores some parameters of an operation, those parameters should be separate operations.

### Find Contradictions in Rules

Algebraic manipulation reveals contradictions before code is written. Example: requiring a merge operation to be order-independent while returning an ordered list creates a contradiction. Fix: use an unordered collection. Choose data structures that satisfy your rules, not the other way around.

### Unify Observations

When multiple observations share traversal logic, find a single observation from which all others can be derived. This simplifies the entire rule set because traversal logic is written once, and often reveals hidden structure.

### Use Symmetry to Discover Missing Features

When you have a "both" operation (parallel composition), look for its symmetric counterpart ("either"). Symmetry arguments are excellent inspiration for discovering functionality that has not been explicitly requested but will inevitably be needed.

---

## Three-Phase Testing Strategy

1. **Build a naive implementation**: Implement each operation as a direct data constructor (the "interpreter pattern"). Naive but obviously correct because it mirrors the specification exactly.

2. **Discover all rules automatically**: Feed the naive implementation to a tool that enumerates all well-typed expressions up to a maximum size and finds which ones are observationally equal. This discovers rules you specified AND emergent rules you missed.

3. **Freeze as regression tests**: Convert discovered rules into executable property tests. These form the regression suite for any future optimized implementation.

Two values are equal if no observation can distinguish them. Testing equality through observations rather than structural comparison allows completely different implementations to pass the same test suite.

---

## Decision Tree: When Is Algebraic Thinking Worth It?

```
Is your domain about COMBINING things?
  YES --> Algebraic thinking will help significantly
    Do combinations have rules (order doesn't matter, defaults exist, inverses)?
      YES --> You have known algebraic structures; use their rules directly
      NO --> You may still benefit from writing rules, but the structures won't be standard
  NO --> Is your domain about TRANSFORMING things?
    YES --> Look for structure-preserving transformation patterns (Functor/Applicative)
    NO --> Is your API surface small and well-understood?
      YES --> Algebraic thinking adds overhead with little benefit; use conventional design
      NO --> Writing rules can still clarify the design, even without standard algebraic structures
```

---

## Design Heuristics

1. **Do not start with an implementation.** Work out the rules first; derive the implementation from them.
2. **Simple rules indicate good decomposition.** Complex rules mean coarse building blocks.
3. **Every new operation needs rules connecting it to existing ones.** Isolated operations indicate missing relationships.
4. **Look for algebraic structures.** Associative operation? Look for a default (Monoid). Monoid? Check for commutativity or inverses. Each upgrade brings new rules and capabilities.
5. **Structure-preserving transformations prove correctness.** When your observation maps algebraic operations to well-known operations on the output type, the design is sound.
6. **Generalize by removing type constraints.** If your rules do not mention a specific type, parameterize over it.
7. **Unified observations simplify everything.** Find one observation from which all others derive.
8. **Build naive first, optimize second.** Generate a comprehensive test suite from the naive implementation, then build the optimized one against those tests.
9. **Invariants belong in the types, not in business logic.** When your rules require commutativity but your data structure is ordered, change the data structure.

---

## Combining Patterns

Algebra-Driven Design combines with PBT and Usable Software Design patterns:

- **Algebraic Rules + PBT Generators**: Rules ARE property tests. Use algebraic constructors as the basis for PBT generators. The rules generate the properties; the generators generate the test inputs; the framework generates thousands of test cases.

- **Algebraic Rules + Output-First Generators (from PBT)**: When testing complex transformations, generate the expected algebraic result first, derive inputs from it, then verify the implementation matches.

- **Compositional APIs + Design Elements (from USD)**: Each design element constrains what operations are allowed. Algebraic rules formalize those constraints as equations. A "Controller" that cannot write to the database is an algebraic rule: `observe_writes(controller(x)) = empty`.

- **Decompose Large Operations + Feature-Oriented Organization (from USD)**: When algebraic decomposition splits a monolithic operation into orthogonal pieces, organize those pieces by feature domain rather than technical layer.

- **Rule Simplicity + Navigability (from USD)**: Simple algebraic rules map to simple, searchable, nameable operations -- improving the navigability and learnability that USD cares about.
