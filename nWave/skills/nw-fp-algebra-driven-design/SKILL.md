---
name: nw-fp-algebra-driven-design
agent: nw-functional-software-crafter
description: Algebra-driven API design with monoids, semigroups, and interpreters via algebraic equations
user-invocable: false
---

# FP Algebra-Driven Design

Algebraic thinking for API design. Discover the right API before implementing by specifying rules (equations) that operations must satisfy.

**Thin FP projection (ADR-SSOT-002 §6a).** The design METHOD — how to find
observations, add constructors, and follow a contradiction to its carrier —
lives once in `nw-algebraic-design-protocol` and applies at every layer, not
just FP data types. This file's own contribution is narrower: the catalogue
of recurring FP structures (Section 2) and how they compose. Load the
protocol skill for the method; load this one for the structure catalogue.

Cross-references: [fp-principles](../nw-fp-principles/SKILL.md) | [fp-domain-modeling](../nw-fp-domain-modeling/SKILL.md) | [fp-usable-design](../nw-fp-usable-design/SKILL.md)

---

## 1. Common Algebraic Structures

[STARTER] -> [ADVANCED]

Recurring patterns in software. Recognizing them unlocks known rules and capabilities.

### [STARTER] Combinable Values (Semigroup)

**What**: Type with one merge operation where grouping doesn't matter.
**Rule**: `(a merge b) merge c = a merge (b merge c)` (associativity)
**When**: Combining things where parenthesization shouldn't matter.
**Examples**: String concatenation | config merging | min/max.

### [STARTER] Combinable Values with Default (Monoid)

**What**: Combinable Value with a default element inert under combination.
**Rules**: Associativity + `default merge x = x` and `x merge default = x`
**When**: Safe defaults | fold operations | "nothing happened yet" values.
**Examples**: `(+, 0)` | `(*, 1)` | `(concat, [])` | `(and, true)`.
**Design signal**: If you find an associative operation, look for a default element. Finding one enables fold/reduce over collections.

### [INTERMEDIATE] Merge-and-Forget Values (Semilattice)

**What**: Combinable Value where merging is also order-independent and idempotent.
**When**: Conflict resolution | eventually-consistent systems | CRDTs.
**Example**: Status tracker with `seen < failed < completed` uses `max` as merge.

### [INTERMEDIATE] Structure-Preserving Transformations (Functor)

**What**: Container type where you can transform contents without changing structure. Preserves identity and composition.
**When**: Operations that work on data shape rather than values inside.
**Design signal**: If most operations are agnostic to contained type, you likely have this.

### [ADVANCED] Combinable Containers (Applicative)

**What**: Container where you can combine contents element-wise and fill with uniform values.
**When**: Combining containers holding different content types.

### [ADVANCED] Reversible Operations (Group)

**What**: Combinable Value with Default where every element has an inverse that cancels it.
**When**: Undo operations | spatial transformations.
**Example**: Clockwise/counter-clockwise rotation are inverses; horizontal flip is its own inverse.

---

## 2. When Is Algebraic Thinking Worth It?

[INTERMEDIATE]

```
Is your domain about COMBINING things?
  YES --> Algebraic thinking helps significantly
    Do combinations have rules (order irrelevant, defaults, inverses)?
      YES --> Known algebraic structures; use their rules directly
      NO --> Rules still help, but structures are not standard
  NO --> Is your domain about TRANSFORMING things?
    YES --> Look for Structure-Preserving Transformation patterns
    NO --> Is your API surface small and well-understood?
      YES --> Algebraic thinking adds overhead; use conventional design
      NO --> Rules can still clarify, even without standard structures
```

---

## 3. Integration with Other FP Lenses

**Rules + Property-Based Testing**: Rules ARE property tests. Algebraic constructors become PBT generators. See `nw-property-based-testing` for semantic PBT and test authoring ownership.

**Rules + Domain Modeling** (see [fp-domain-modeling](../nw-fp-domain-modeling/SKILL.md)): Domain wrappers with smart constructors are algebraic rules. State machine transitions are rules about valid sequences.

**Rules + Usable Design** (see [fp-usable-design](../nw-fp-usable-design/SKILL.md)): Simple algebraic rules map to simple, searchable, nameable operations — improving navigability and learnability.

**Decomposition + Feature Organization**: When algebraic decomposition splits a monolithic operation into orthogonal pieces, organize by feature domain.

See `nw-algebraic-design-protocol` for the complete design method and `nw-certainty-by-construction` for encoding claims at any layer the architecture touches.
