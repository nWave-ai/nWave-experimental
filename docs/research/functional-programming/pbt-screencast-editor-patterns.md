# Property-Based Testing Patterns

Patterns for using property-based testing (PBT) effectively, extracted from real-world application to a screencast editor with a hierarchical timeline.

---

## How to Find Properties

Finding properties is hard because it forces you to understand a system's general behavior, not just specific examples. Four strategies:

1. **Start from invariants**: What must always be true regardless of input? (e.g., transforming a timeline must preserve total duration and clip identity)
2. **Think about equivalences**: Different paths that should produce the same result (e.g., processing a whole collection vs. processing each part separately and combining)
3. **Identify conservation rules**: What is preserved through a transformation? What may be added but never lost?
4. **Consider inverse operations**: If action A transforms state S to S', does undo(A) return to S?

---

## Patterns

### [STARTER] Round-Trip Properties

**When**: You have operations that should cancel each other out (serialize/deserialize, encode/decode, undo/redo).

**What**: Generate random inputs, apply operation A then its inverse, assert you get back the original.

**Why**: Tests the entire operation pipeline without reimplementing any logic in the test. The undo/redo version of this pattern survived a two-week refactoring from stack-based to inverse-action-based undo without any test modification.

### [STARTER] Conservation Properties

**When**: A transformation should preserve some measurable quantity (total count, total duration, set membership).

**What**: Measure the quantity before and after the transformation; assert equality.

**Why**: Catches a wide class of bugs (off-by-one, dropped items, duplicate items) with a single property.

### [INTERMEDIATE] Smart Generators (Constraint-Encoding)

**When**: Valid inputs have structural constraints that random generation rarely satisfies.

**What**: Build generators that only produce valid inputs by construction, rather than generating arbitrary data and filtering. Compose generators by passing them as arguments to other generators.

**Why**: Filtering-based generation is exponentially inefficient for constrained domains. Smart generators also serve as executable documentation of domain constraints.

Rules for smart generators:
- Simpler is better -- early generators that were "too clever" (random pixel colors) had subtle bugs; deterministic, obvious generators were more reliable
- Generators are first-class values; compose them like any other abstraction
- When a generator bug is found through shrinking, it reveals a domain constraint you missed

### [INTERMEDIATE] Output-First Generators (Oracle Generators)

**When**: You cannot easily describe correctness as a function from input to expected output (e.g., the "oracle problem" -- verifying output would require reimplementing the algorithm).

**What**: Generate the expected output first, then derive valid input from it. Assertions become simple equality checks.

**Why**: Eliminates the need for a test oracle entirely. Example: for a video classifier, generate sequences of "moving" and "still" segments (the expected output), then derive pixel frames from those segments (alternating gray/white for moving, all-black for still).

### [INTERMEDIATE] Stubbed Integration Testing

**When**: You want to test interactions between subsystems without real side effects (GUI, network, disk).

**What**: Run the full application control flow with side effects stubbed out. Represent user actions abstractly; generate random sequences of actions to drive the system through realistic state transitions.

**Why**: Finds bugs that unit tests miss: off-by-one index errors, inconsistent state after sequences of operations, incorrectly constructed inverse actions. Integration-level properties describe outcomes rather than implementation details, making them resilient to refactoring.

### [ADVANCED] Shrinking as a Diagnostic Tool

**When**: A property test fails and you need to understand the root cause.

**What**: Let the PBT framework shrink the failing input to a minimal counterexample. Interpret the minimal case as a diagnostic clue.

**Why**: Shrinking reveals structure in failures:
- A minimal timeline isolating one branch of a fold points to that branch's logic
- Consistent shrunk values (e.g., always 0.6s instead of expected 1.0s) point to hardcoded constants or off-by-one errors
- When shrinking causes test setup to break (e.g., color values shrink to 0, colliding with the "still frame" encoding), it reveals generator flaws -- the generator did not properly separate its concerns

### [ADVANCED] Stateful Sequence Testing

**When**: Your system has mutable state and a command vocabulary (user actions, API calls).

**What**: Generate random sequences of commands, execute them against the system, check invariants after each step or at the end.

**Why**: Explores state spaces that manual test design cannot cover. Combined with round-trip properties (execute N commands, then N undos, assert initial state), this tests the entire command pipeline.

---

## When to Use PBT

PBT works for effectful and stateful code, not just pure functions. Three integration modes:

| Mode | When | Example |
|---|---|---|
| **After-the-fact testing** | Existing code you want to verify | Found three simultaneous bugs in 30 lines of a video classifier |
| **Test-first development** | New functionality where you can state properties before implementing | Write conservation and round-trip properties, then implement |
| **Refactoring safety net** | Major restructuring of existing code | Integration properties written against the old implementation stay green through the refactoring |

The iterative PBT cycle -- specify behavior as properties, build generators encoding domain constraints, run many tests, use shrunk failures to diagnose bugs, repeat -- parallels TDD.

---

## Combining Patterns

PBT patterns combine powerfully with patterns from Algebra-Driven Design and Usable Software Design:

- **Output-First Generators + Algebraic Rules**: When your API is specified as algebraic equations (from ADD), generate random expressions using the algebraic constructors. The equations themselves become the properties. The generator produces expressions; the property checks the equation holds.

- **Conservation Properties + Design Element Constraints**: Each design element (from USD) has defined responsibilities. Conservation properties can verify those constraints automatically: "a Controller never writes to the database" becomes a property over generated request sequences.

- **Stubbed Integration Testing + Feature-Oriented Organization**: Organize property tests by feature (from USD), with each feature's tests using stubbed integration to verify cross-component behavior within that feature boundary.

- **Smart Generators + Compositional APIs**: If your API is compositional (from ADD), your generators should mirror that composition -- build complex test inputs by combining simple generators that match the API's algebraic constructors.
