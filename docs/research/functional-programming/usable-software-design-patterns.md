# Usable Software Design Patterns

Patterns for treating developers as the users of software design, applying usability thinking to code organization, naming, and architecture.

---

## Core Insight

The user of software design is the developer, not the end user of the product. When developers struggle, blame the design, not the people. Pressure, team churn, unclear specs, and noisy environments produce unusable designs -- the response is to improve the design.

---

## Five Evaluation Goals

Use these to assess any codebase or API. They are goals to optimize for, not patterns to apply.

| Goal | What It Means | How to Measure |
|---|---|---|
| **Learnability** | How quickly a new developer becomes productive | Give unfamiliar developer timed tasks; observe where they get stuck |
| **Efficiency** | How fast common (not trivial) tasks are performed | Map developer workflow steps; count unnecessary navigation and decisions |
| **Memorability** | How easily a developer regains proficiency after time away | Ask returning developers what they remember and what they have to re-learn |
| **Error resistance** | How many bugs the design induces and how easily they are caught | Track bug locations; ask "what design change prevents this category?" |
| **Satisfaction** | How pleasant and motivating it is to work in the codebase | Developer interviews, retrospectives |

---

## Patterns

### [STARTER] Naming Conventions as Navigation

**When**: Developers frequently search for code by name, and search results return too many false positives.

**What**: Establish consistent naming patterns where the suffix or prefix indicates the design role (e.g., all write operations end in `Command`: `SaveUserCommand`, `CreateEventCommand`). Names should be precise enough that searching yields 3-4 results at most. Use IDE-friendly casing (e.g., uppercase initials enable fast jump-to: "CPC" for `ChangePasswordCommand`).

**Why**: Naming conventions are memorized once and applied everywhere, reducing cognitive load from hundreds of individual names to a handful of rules. Developers can predict where code lives without reading documentation.

### [STARTER] Feature-Oriented Organization

**When**: Developers frequently need to find and modify all code related to a specific feature.

**What**: Organize code by feature domain rather than technical layer.

Instead of `controllers/`, `services/`, `models/` (technical layers), use `auth/`, `speakers/`, `speakers/profile/` (feature domains).

**Why**: When something changes in "call for speakers," it is obvious where to look. Technical layering scatters related code across the entire codebase.

### [STARTER] Navigability as a Design Concern

**When**: The typical developer workflow (find what to change, navigate there, read, write, test) is executed hundreds of times per day.

**What**: Actively reduce navigation friction. Eliminate: long methods requiring scrolling, unclear method names that force reading implementations, tests that cannot be related to features, inconsistent placement of similar logic.

**Why**: Small navigability improvements compound across hundreds of daily developer actions. This is a quasi-ignored dimension with enormous cumulative impact.

### [INTERMEDIATE] Design Elements (Constrained Roles)

**When**: Developers ask "where does this logic go?" or bugs recur because responsibilities are unclear.

**What**: Define a set of constrained roles for your codebase. Each role specifies: what it is responsible for, what it can collaborate with, and how to test it. Examples:

| Role | Responsibilities | Can Call | Test With |
|---|---|---|---|
| Controller | Delegates operations, renders views | Services, Command Objects | Component tests |
| Command Object | Validates input, delegates writes | Database services, queries | Unit tests |
| Application Service | Orchestrates business logic | Commands, other services | Integration tests |
| Database Query | Read-only data access | Database only | Unit tests |
| View Model | Shapes data for presentation | Nothing | Unit tests |

**Why**: Makes the design "easy to use correctly and hard to use incorrectly." Developers know exactly where each type of logic belongs. A Controller cannot write to the database, so database bugs cannot originate in Controllers.

Rules for design elements:
- Derive them after building 10+ features, not upfront
- Cover 80% of cases; handle exceptions case-by-case
- Review periodically as the product evolves
- Make compliance easier than deviation (provide samples, generators, testing support)

### [INTERMEDIATE] Constraints as Clarity

**When**: A part of the codebase is confusing because too many things are possible.

**What**: Deliberately restrict what each component can do. Constrain both behavior (what a thing does) and collaboration (what it can call). When a use case does not fit existing roles, extract it into a separate module with its own consistency rules rather than polluting the main design.

**Why**: Unconstrained classes can express too much -- like raw steel versus a purpose-built tool. Good abstractions restrict what is possible to make the remaining possibilities clearer. Immutability is a prime example: constraining mutation improves usability.

### [INTERMEDIATE] Root-Cause Bugs in the Design

**When**: A bug recurs or developers express fear that their changes could be wrong.

**What**: Ask "what design change would prevent this category of bug?" rather than fixing the instance. Track which parts of the code are most bug-prone and redesign those parts.

**Why**: Fear of making changes signals a design problem (unclear side effects, missing tests, tangled responsibilities). Fixing individual bugs without addressing the design guarantees recurrence.

### [ADVANCED] Usability Testing the Design Itself

**When**: You want to evaluate whether your design actually works for developers, not just in theory.

**What**: Apply UX research techniques to your codebase:

| Technique | Application |
|---|---|
| Developer interviews | Ask: what was hard? what was confusing? what felt risky? |
| Personas | Define developer profiles (skill level, domain knowledge, tool familiarity) |
| Flow analysis | Map steps developers take for common tasks; identify bottlenecks |
| Timed tasks | Give developers unfamiliar with the code specific tasks; observe friction |
| Team agreement | Collaboratively define what "usable design" means for your context |
| Continuous feedback | Retrospectives and root-cause analysis as ongoing design feedback |

**Why**: Design decisions made in isolation accumulate friction. Regular usability evaluation catches problems before they calcify.

### [ADVANCED] Prescribed Testing Strategy

**When**: Developers waste time deciding how to test each component.

**What**: Assign a testing approach to each design element role. Controllers get component tests, command objects get unit tests, etc. This removes the "how should I test this?" decision entirely.

**Why**: Reduces decision fatigue. Tests also serve as design constraints -- they document and enforce what each role should do.

---

## Decision Tree: Classifying Code into Design Elements

```
Does this code handle an incoming request?
  YES --> Controller (delegates only, renders response)
  NO -->
    Does it orchestrate multiple operations?
      YES --> Application Service
      NO -->
        Does it write data?
          YES --> Command Object (validates, then delegates write)
          NO -->
            Does it read data?
              YES --> Database Query (read-only)
              NO -->
                Does it shape data for display?
                  YES --> View Model
                  NO --> Evaluate whether a new design element role is needed
```

---

## Design Heuristics

1. **Blame the design, not the people** -- the foundational heuristic
2. **No best practices, only contextual practices** -- SOLID helps when you need low cost of change; if you do not, skip it
3. **Constraints enable creativity** -- limiting what a component can do leads to more focused solutions
4. **Improve incrementally** -- use the imperfect name now, improve it next time you cannot find it
5. **Action over analysis** -- make things work first, then refine structure
6. **Consistency at module level** -- system-wide conceptual integrity is hard; module-level consistency is practical and valuable

---

## Combining Patterns

Usable Software Design patterns combine with PBT and Algebra-Driven Design:

- **Design Elements + Algebraic Rules (from ADD)**: Each design element's constraints ("a Controller can only call Services") are formalizable as algebraic rules. This makes the constraints machine-checkable rather than convention-dependent.

- **Navigability + Simple Rules (from ADD)**: Algebraic decomposition produces small, orthogonal operations with simple rules. Small operations are easy to name well. Good names improve navigability. Simple rules improve learnability. This is a virtuous cycle.

- **Feature-Oriented Organization + PBT Integration Tests (from PBT)**: Organize property-based tests by feature domain. Each feature's integration properties use stubbed testing to verify cross-component behavior within that feature's boundary.

- **Prescribed Testing + PBT Patterns (from PBT)**: Design elements prescribe WHAT kind of test; PBT patterns prescribe HOW to write those tests as properties. Controllers get component-level round-trip properties. Command objects get conservation properties on their validation logic. Services get stateful sequence tests.

- **Root-Cause in Design + Algebraic Contradictions (from ADD)**: When a recurring bug points to a design flaw, algebraic analysis can reveal whether the flaw is a contradiction in your rules (e.g., requiring order-independence but using an ordered data structure). The fix is structural, not behavioral.

- **Usability Testing + Property Discovery (from PBT)**: The "where did the developer get stuck?" observations from usability testing often reveal missing properties. If a developer cannot predict what an operation does, that operation likely lacks clear algebraic rules or naming conventions.
