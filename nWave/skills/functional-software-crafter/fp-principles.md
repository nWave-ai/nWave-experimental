# FP Principles

Core functional programming thinking patterns. Language-agnostic.

Cross-references: [fp-domain-modeling](./fp-domain-modeling.md), [fp-hexagonal-architecture](./fp-hexagonal-architecture.md), [fp-algebra-driven-design](./fp-algebra-driven-design.md)

---

## 1. Higher-Order Functions as Problem Decomposition

[STARTER]

Three operations replace most loops:

| Operation | Purpose | Replaces |
|-----------|---------|----------|
| **Map** | Transform each element, preserve structure | Loop building new collection |
| **Filter** | Keep elements matching a condition | Loop with conditional |
| **Fold** | Accumulate elements into a single result | Loop with running total |

**When to use Map**: You have a collection and want to transform every element without changing the collection's shape. Nested maps handle nested structures.

**When to use Filter**: You want to select elements without changing their values.

**When to use Fold**: You want to reduce a collection to a single value. The accumulator IS your state. The combining function IS your state transition. Folds make state machines explicit.

**Decision**: "Am I transforming, selecting, or accumulating?" Pick the matching operation. If none fit, compose two of them.

**Why it matters**: These operations communicate intent. A map says "same shape, different values." A fold says "many inputs, one output." Loops say nothing about intent until you read every line.

---

## 2. Type-Driven Design

[STARTER]

Write the type signature before the implementation. The type tells you what the function can and cannot do.

**Process**:
1. Declare what the function consumes and produces
2. Ask: "which type-specific operations do I actually use?"
3. Replace concrete types with type variables for everything you do not inspect
4. Add constraints only for capabilities you use (equality, ordering, display)

**Design progression**: Concrete types -> type variables -> constrained type variables. Each step increases reuse while documenting minimal assumptions.

**Why it matters**: A function's type signature is a contract. It tells callers what is required and what is guaranteed. Narrower types mean fewer possible implementations, which means fewer bugs.

---

## 3. Pattern Matching as Decision Decomposition

[STARTER]

Decompose decisions by data shape, not by boolean conditions. Each clause handles one concrete case. The compiler verifies exhaustiveness.

**When to use pattern matching**: "What shape is this data?"
**When to use guards/conditions**: "What property does this value have?"
**When to use named bindings**: Intermediate results need a name to avoid repetition.

**Design heuristic**: Prefer small extracted functions over giant match expressions. Pattern match on the top-level shape, delegate to named functions for sub-decisions.

**Exhaustiveness as safety net**: When you add a new variant to a choice type, the compiler flags every match that does not handle it. "Did I update all the switch statements?" becomes a compiler error.

---

## 4. Composition Patterns

[INTERMEDIATE]

### Partial Application

Fix some arguments of a general function to create a specialized version. Instead of writing a new function, partially apply an existing one.

**When to use**: A general function exists and you need a specialized version for a specific context. Eliminates throwaway helper functions.

### Function Composition (Pipelines)

Chain functions into pipelines where the output of one feeds into the next. Each function in the chain has a single responsibility.

**Why it matters**: Composition reveals the architecture of computation -- what transforms feed into what. Pipelines read as a sequence of steps, making the business process visible.

**When to use**: Building complex behavior from simple, tested pieces. The pipeline is the workflow.

### Point-Free Style

Omit the explicit argument when the function is just a composition. Use when it reveals intent. Avoid when it obscures meaning.

---

## 5. Container Abstractions

[INTERMEDIATE] -> [ADVANCED]

A progressive hierarchy for working with values inside containers (nullables, lists, futures, results).

### [INTERMEDIATE] Transformable Container (Functor)

**What**: Apply a function to values inside a container without changing the container's structure.

**Plain English**: "I have a value in a box. Transform the value without opening the box."

**When to use**: You have a nullable/optional/list/future and want to transform its contents. You do not need to inspect the container to decide what to do.

**Guarantees**: Transforming with identity does nothing. You can fuse or split transformations freely.

### [INTERMEDIATE] Combinable Containers (Applicative)

**What**: Apply a function that is also inside a container to values inside other containers. Handles multi-argument functions across containers.

**Plain English**: "I have a function in a box AND values in boxes. Combine them."

**When to use**: Validation is the primary use case. Check multiple fields independently, combine results only if all succeed. Unlike chaining, this does not short-circuit -- it collects all errors.

### [INTERMEDIATE] Combinable Values (Monoid)

**What**: Combine two values of the same type into one, with a default element that changes nothing.

**Plain English**: "I have many values. Smash them together into one."

**When to use**: Folding/reducing collections. The combining operation must be associative (grouping does not matter), which enables parallelism.

**Examples**: String concatenation with empty string. Addition with zero. List append with empty list.

### [ADVANCED] Chainable Operations (Monad)

**What**: Chain operations where each step produces a wrapped value, and the next step depends on the previous result.

**Plain English**: "Step 1's output determines what step 2 does. Each step might fail/branch/have effects."

**When to use**: Sequential dependent operations where each step can fail, branch, or produce effects. Error propagation, database lookups, stateful computations.

### Decision Tree: Which Abstraction Do I Need?

```
Do I need to transform values inside a container?
  YES, one function, one container --> Transformable (Functor)
  YES, combine multiple independent containers --> Combinable Containers (Applicative)
  YES, chain dependent operations sequentially --> Chainable Operations (Monad)
Do I need to combine values of the same type?
  YES --> Combinable Values (Monoid)
```

### Progression Summary

Each level adds a new kind of combination:
- **Transformable**: one function, one container
- **Combinable Containers**: one function, multiple containers (independent)
- **Chainable**: sequential dependent operations, each producing a container
- **Combinable Values**: same-type values collapsed into one

### Runnable Example: Map, Filter, Fold on Domain Objects

```
orders = [Order(100, "pending"), Order(250, "shipped"), Order(50, "pending")]

pendingTotals = orders
  |> filter (o -> o.status == "pending")    -- [Order(100, "pending"), Order(50, "pending")]
  |> map (o -> o.amount)                    -- [100, 50]
  |> fold 0 (acc, x -> acc + x)            -- 150
```

---

## 6. Specialized Chainable Patterns

[ADVANCED]

| Pattern | What It Manages | When to Use |
|---------|----------------|-------------|
| **Optional** (Maybe/Option) | Possible absence | Operations that can fail without explanation |
| **Result** (Either) | Failure with context | Operations that fail with error details |
| **Environment** (Reader) | Shared read-only config | Dependency injection, configuration threading |
| **Accumulator** (Writer) | Side-channel output | Logging, auditing, collecting metadata |
| **Stateful** (State) | Sequential state changes | Counters, parsers, accumulators |

These compose: real applications stack multiple patterns. See [fp-hexagonal-architecture](./fp-hexagonal-architecture.md) for dependency injection patterns.

---

## 7. Lazy Evaluation as Design Pattern

[INTERMEDIATE]

Separate WHAT you want to compute from WHEN it gets computed. Define potentially infinite sequences and let the consumer determine how much to evaluate.

**When to use**: Generating candidates then selecting results. Pagination and streaming. Decoupling producers from consumers. Build systems that only rebuild what changed.

**The separation principle**: Generate all possibilities, then filter. This declarative style says WHAT you want, not HOW to search for it.

---

## 8. The FP Problem-Solving Method

[STARTER]

1. **Start with the type signature**: What does this function consume and produce?
2. **Identify the traversal pattern**: Map, filter, fold, or search?
3. **Recognize the accumulator**: If folding, what is the state and how does each element change it?
4. **Decompose by data shape**: Pattern match on constructors, handle each case independently
5. **Compose small functions**: Build complex behavior from simple, tested pieces

**The mindset shift**: Describe WHAT to compute (transformations, compositions, constraints) rather than HOW to compute it (loops, mutations, control flow).

| Imperative Thinking | Functional Thinking |
|---------------------|---------------------|
| Loop through items | Map/filter/fold over collections |
| Mutate variables | Transform immutable values |
| Check conditions with if/else | Pattern match on data shapes |
| Inherit from base class | Satisfy capability constraints |
| Call methods on objects | Compose functions into pipelines |
| Handle errors with try/catch | Use Optional/Result to make failure explicit in types |
| Pass dependencies explicitly | Use Environment pattern for implicit config |
