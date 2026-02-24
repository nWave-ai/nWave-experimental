# FP Usable Design

Making functional code usable. The developer is the user of your design. Apply usability thinking to code organization, naming, and architecture.

Cross-references: [fp-domain-modeling](./fp-domain-modeling.md), [fp-hexagonal-architecture](./fp-hexagonal-architecture.md), [fp-algebra-driven-design](./fp-algebra-driven-design.md)

---

## 1. Core Insight

[STARTER]

The user of software design is the developer, not the end user of the product. When developers struggle, blame the design, not the people. Pressure, team churn, unclear specs, and noisy environments produce unusable designs. The response is to improve the design.

---

## 2. Five Evaluation Goals

[STARTER]

Use these to assess any codebase or API:

| Goal | What It Means | How to Assess |
|---|---|---|
| **Learnability** | How quickly a new developer becomes productive | Timed tasks for unfamiliar developers |
| **Efficiency** | How fast common tasks are performed | Count unnecessary navigation and decisions |
| **Memorability** | How easily proficiency returns after time away | What do returning developers re-learn? |
| **Error resistance** | How many bugs the design induces | Track bug locations; ask "what design change prevents this category?" |
| **Satisfaction** | How pleasant it is to work in the codebase | Developer interviews, retrospectives |

---

## 3. Naming Conventions

[STARTER]

### Domain Language in Function Names

Use the domain expert's vocabulary, not mathematical conventions or technical jargon. No `OrderFactory`, `OrderManager`, `OrderHelper`. A domain expert would not know what these mean.

### Verb-Noun for Transformations (Pipeline-Friendly)

Functions that transform data use verb-noun naming. This reads naturally in pipelines:

```
rawOrder
  |> validateOrderFields
  |> enrichWithCustomerData
  |> calculateOrderTotal
  |> applyDiscountRules
  |> generateOrderConfirmation
```

### Predicate Functions Use Question-Style Names

```
isActiveCustomer     -- not: checkActive, activeP
hasShippingAddress   -- not: shippingAddr, addrCheck
canPlaceOrder        -- not: orderOk, validateOrderBool
```

### When Short Names Are Acceptable

Single-letter names are appropriate only in:
- Library internals and generic utility functions
- Lambda parameters in trivial operations (domain names still preferred)
- Type variables
- Mathematical domains where the convention IS the domain language

### Lifecycle Prefixes

Types at different workflow stages get prefixed: `UnvalidatedOrder`, `ValidatedOrder`, `PricedOrder`. The stage is immediately visible in any type signature.

### Error Type Naming

Named after what went wrong, scoped to context: `ValidationError`, `PricingError`. Pipeline-level: `PlaceOrderError` (choice type unifying step errors).

---

## 4. Feature-Oriented Organization

[STARTER]

Organize code by feature domain rather than technical layer.

**Instead of** (technical layers):
```
controllers/
services/
models/
```

**Use** (feature domains):
```
auth/
speakers/
speakers/profile/
order/
```

**When to use**: When developers frequently need to find and modify all code related to a specific feature.
**Why it matters**: When something changes in "call for speakers," it is obvious where to look. Technical layering scatters related code across the entire codebase.

### Module Organization Within a Feature

- Simple types at the top (no dependencies)
- Compound domain types in the middle
- Aggregates and workflow types at the bottom
- Types and functions in the same file or types-first, functions-second

---

## 5. Navigability as First-Class Concern

[STARTER]

The typical developer workflow (find, navigate, read, write, test) executes hundreds of times per day. Small improvements compound.

**Eliminate**: Long methods requiring scrolling. Unclear method names that force reading implementations. Tests that cannot be related to features. Inconsistent placement of similar logic.

**Naming as navigation**: Establish consistent patterns where suffix/prefix indicates design role. Names precise enough that search yields 3-4 results at most. IDE-friendly casing enables fast jump-to.

**Why it matters**: Navigability is a quasi-ignored dimension with enormous cumulative impact.

---

## 6. Design Elements (Constrained Roles)

[INTERMEDIATE]

Define a set of constrained roles for your codebase. Each role specifies: what it is responsible for, what it can collaborate with, and how to test it.

| Role | Responsibilities | Can Call | Test With |
|---|---|---|---|
| Controller | Delegates operations, renders views | Services, Command Objects | Component tests |
| Command Object | Validates input, delegates writes | Database services, queries | Unit tests |
| Application Service | Orchestrates business logic | Commands, other services | Integration tests |
| Database Query | Read-only data access | Database only | Unit tests |
| View Model | Shapes data for presentation | Nothing | Unit tests |

**Why it matters**: Makes the design "easy to use correctly and hard to use incorrectly." A Controller cannot write to the database, so database bugs cannot originate in Controllers.

**Rules for design elements**:
- Derive them after building 10+ features, not upfront
- Cover 80% of cases; handle exceptions case-by-case
- Review periodically as the product evolves
- Make compliance easier than deviation (provide samples, generators, testing support)

---

## 7. Constraints as Clarity

[INTERMEDIATE]

Deliberately restrict what each component can do. Constrain both behavior (what a thing does) and collaboration (what it can call).

**Why it matters**: Unconstrained components can express too much. Good abstractions restrict what is possible to make the remaining possibilities clearer. Immutability is a prime example: constraining mutation improves usability.

**When a use case does not fit**: Extract it into a separate module with its own consistency rules rather than polluting the main design.

---

## 8. Root-Cause Bugs in the Design

[INTERMEDIATE]

Ask "what design change would prevent this category of bug?" rather than fixing individual instances. Track which code areas are most bug-prone and redesign those areas.

**Fear of making changes signals a design problem**: unclear side effects, missing tests, tangled responsibilities. Fixing individual bugs without addressing the design guarantees recurrence.

See [fp-algebra-driven-design](./fp-algebra-driven-design.md) section 5 for using algebraic contradiction analysis to find structural root causes.

---

## 9. Prescribed Testing Strategy

[INTERMEDIATE]

Assign a testing approach to each design element role. Controllers get component tests. Command objects get unit tests. This removes the "how should I test this?" decision entirely.

**Why it matters**: Reduces decision fatigue. Tests also document and enforce what each role should do.

---

## 10. Usability Testing the Design

[ADVANCED]

Apply UX research techniques to your codebase:

| Technique | Application |
|---|---|
| Developer interviews | What was hard? Confusing? Risky? |
| Personas | Developer profiles (skill level, domain knowledge, tool familiarity) |
| Flow analysis | Map steps for common tasks; identify bottlenecks |
| Timed tasks | Give unfamiliar developers specific tasks; observe friction |
| Continuous feedback | Retrospectives and root-cause analysis as ongoing design feedback |

---

## Decision Tree: How to Organize This Module?

```
Does this module represent a feature domain?
  YES --> Feature-oriented folder (auth/, order/, speakers/)
    Does the feature have sub-features?
      YES --> Nested feature folders (speakers/profile/)
      NO --> Single feature folder
  NO --> Is it shared infrastructure?
    YES --> Infrastructure folder, organized by capability
    NO --> Is it a cross-cutting concern?
      YES --> Shared module, referenced by feature modules
      NO --> Evaluate whether it belongs in an existing feature
```

---

## 11. Design Heuristics

1. **Blame the design, not the people** -- the foundational heuristic
2. **No best practices, only contextual practices** -- SOLID helps when you need low cost of change; skip it otherwise
3. **Constraints enable creativity** -- limiting what a component can do leads to more focused solutions
4. **Improve incrementally** -- use the imperfect name now, improve it next time you cannot find it
5. **Action over analysis** -- make things work first, then refine structure
6. **Consistency at module level** -- system-wide conceptual integrity is hard; module-level consistency is practical and valuable

---

## 12. Combining with Other Patterns

**Design Elements + Algebraic Rules**: Each element's constraints ("a Controller can only call Services") are formalizable as algebraic rules, making constraints machine-checkable. See [fp-algebra-driven-design](./fp-algebra-driven-design.md). Example: an architecture test asserts `imports(controllerModule) intersect dbModules == empty`.

**Navigability + Simple Rules**: Algebraic decomposition produces small, orthogonal operations with simple rules. Small operations are easy to name well. Good names improve navigability. Example: `applyDiscount` and `calculateTax` are instantly searchable; `processOrder` is not.

**Feature Organization + Domain Modeling**: Feature folders align with bounded contexts. Each feature owns its domain types and workflows. See [fp-domain-modeling](./fp-domain-modeling.md). Example: `order/types.fs`, `order/validate.fs`, `order/price.fs` -- all order logic in one place.

**Prescribed Testing + Property-Based Testing**: Design elements prescribe WHAT kind of test. PBT patterns prescribe HOW to write those tests as properties. Example: Command objects get conservation properties (`forAll(order -> totalOf(applyDiscount(order)) <= totalOf(order))`). Controllers get round-trip properties.
