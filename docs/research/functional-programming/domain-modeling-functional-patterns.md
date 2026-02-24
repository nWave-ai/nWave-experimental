# Domain Modeling Made Functional: Patterns and Concepts

Conceptual patterns for type-driven domain modeling, drawn from Scott Wlaschin's work and the broader functional DDD community.

---

## 1. How Types Model the Domain [STARTER]

### 1.1 The Two Building Blocks

All domain types are composed from smaller types using two operations:

- **AND (Record Types)**: Groups of data that must appear together. Example: an Order requires CustomerInfo AND ShippingAddress AND BillingAddress AND OrderLines.
- **OR (Choice Types)**: Data that represents a choice between alternatives. Example: a ProductCode is either a WidgetCode OR a GizmoCode.

These two operations, combined recursively, can express virtually any domain structure.

### 1.2 Domain Wrappers (Single-Case Unions)

Primitive values (strings, integers) are never used directly in the domain model. Each domain concept gets its own wrapper type:

- `CustomerId` wraps an `int`
- `WidgetCode` wraps a `string`
- `KilogramQuantity` wraps a `decimal`

**Benefits**:
- Prevents accidental mixing (compiler rejects comparing a `CustomerId` with an `OrderId`)
- Each wrapper carries its own validation rules
- The type name IS the documentation

### 1.3 Validated Construction (Smart Constructors)

Wrapper types use the "smart constructor" pattern: the raw constructor is private, and a `create` function validates input before construction. The `create` function returns a `Result` type, making validation failure explicit.

For example, a `UnitQuantity` must be between 1 and 1000. Its `create` function rejects values outside that range and returns `Error` rather than allowing invalid values to exist.

A companion `value` function provides read access to the inner primitive when needed.

### 1.4 Making Illegal States Unrepresentable

This is the central design guideline. Instead of flags and runtime checks, model the domain so that invalid states cannot be constructed:

**Pattern: Replace flags with distinct types**
- Instead of `{ EmailAddress; IsVerified: bool }`, create separate `VerifiedEmailAddress` and `UnverifiedEmailAddress` types
- Give `VerifiedEmailAddress` a private constructor so only the verification service can produce one
- Functions that require verification (e.g., `SendPasswordResetEmail`) take `VerifiedEmailAddress` as input, making misuse a compile error

**Pattern: Replace optional fields with choice types**
- Instead of `{ Email: option; Address: option }` (where both could be None), create a choice: `EmailOnly | AddressOnly | EmailAndAddress`
- The "at least one required" business rule becomes structurally enforced

**Pattern: NonEmptyList for "at least one" rules**
- Define `NonEmptyList<'a> = { First: 'a; Rest: 'a list }` to guarantee non-emptiness
- An Order with `OrderLines: NonEmptyList<OrderLine>` cannot have zero lines

### 1.5 Value Objects vs. Entities

- **Value Objects**: No identity; equal if all fields match. Most domain types are value objects (names, addresses, product codes). F# records provide structural equality by default.
- **Entities**: Have persistent identity via an identifier field. Two entities with the same ID are the same entity even if other fields differ.

### 1.6 Aggregates

An aggregate is a cluster of entities treated as a single unit:

- The top-level entity is the **aggregate root**
- All changes to child entities must go through the root (immutability makes this natural)
- The aggregate is the **consistency boundary**: rules like "order total = sum of line prices" are enforced at the aggregate level
- The aggregate is the **unit of persistence**: load/save whole aggregates atomically
- Reference other aggregates by ID only (store `CustomerId`, not the full `Customer` record)

---

## 2. Workflow Design [STARTER]

### 2.1 Workflows as Functions

Every business workflow is modeled as a single function:
- **Input**: A command containing the data needed to initiate the workflow
- **Output**: A list of domain events (things that happened as a result)

```
type PlaceOrderWorkflow = PlaceOrderCommand -> AsyncResult<PlaceOrderEvent list, PlaceOrderError>
```

### 2.2 Pipeline Composition

Workflows are decomposed into a series of smaller steps, each modeled as a function that transforms one document type into another:

```
UnvalidatedOrder -> ValidatedOrder -> PricedOrder -> Events
```

Each step:
- Is stateless and side-effect free (in the core domain)
- Has a single input type and single output type
- Can be tested independently

The workflow is assembled by piping the output of one step to the input of the next.

### 2.3 Modeling Dependencies as Function Parameters

Instead of injecting heavyweight interfaces (e.g., `IProductCatalog`), each step declares exactly the functions it needs:

- `CheckProductCodeExists: ProductCode -> bool`
- `GetProductPrice: ProductCode -> Price`
- `CheckAddressExists: UnvalidatedAddress -> AsyncResult<CheckedAddress, AddressValidationError>`

**Dependency placement convention**: Dependencies come first in the parameter list, the primary input comes last. This enables partial application (the functional equivalent of dependency injection).

**Public vs. internal**: The top-level workflow function hides its dependencies from callers. Internal steps make their dependencies explicit.

### 2.4 Composition Root

At the application's entry point, all services are instantiated and partially applied to the workflow functions. The fully-assembled workflow is then a simple one-parameter function matching the public API type.

### 2.5 Commands and Events

- **Commands**: Requests to do something, written in imperative ("Place order"). A generic `Command<'data>` type holds the workflow-specific data plus common metadata (timestamp, userId).
- **Events**: Records of what happened, written in past tense ("Order placed"). Events are the output of workflows and the trigger for downstream workflows.
- **Event choice type**: If a workflow produces multiple event types, define a choice type: `OrderPlaced | BillableOrderPlaced | AcknowledgmentSent`. Return a `list` of this choice type for extensibility.

### 2.6 Document Lifecycle as State Types

Rather than one `Order` type with flags, create separate types for each lifecycle stage:

- `UnvalidatedOrder` (raw input, all fields are strings)
- `ValidatedOrder` (all fields have been checked)
- `PricedOrder` (prices calculated, amount to bill computed)

A top-level `Order` choice type unifies all states:

```
type Order = Unvalidated of UnvalidatedOrder | Validated of ValidatedOrder | Priced of PricedOrder
```

New states can be added (e.g., `Refunded`) without breaking existing code.

### 2.7 Documenting Effects in Type Signatures

Function signatures make side effects visible:
- `Result<success, failure>` -- may fail with a domain error
- `Async<T>` -- performs I/O, does not return immediately
- `Async<Result<success, failure>>` (aliased as `AsyncResult`) -- both async and fallible
- `unit` in a signature signals a side effect

Effects propagate upward: if a dependency returns `AsyncResult`, the step that uses it must also return `AsyncResult`.

---

## 3. Error Handling [INTERMEDIATE]

For the full error-track pipeline pattern (Railway-Oriented Programming), see [Functional Hexagonal Architecture](./functional-hexagonal-architecture-comprehensive-research.md) section 3.

### 3.1 Error Classification

Three categories, each handled differently:

| Category | Examples | Handling Strategy |
|---|---|---|
| **Domain Errors** | Validation failure, product out of stock | Model as types, return via `Result` |
| **Panics** | Out of memory, null reference, divide by zero | Throw exceptions, catch at top level |
| **Infrastructure Errors** | Network timeout, auth failure | Case-by-case: model as domain errors when business cares, otherwise throw |

### 3.2 Unifying Error Types

Each step may have its own error type (`ValidationError`, `PricingError`). To compose steps, define a common error type as a choice:

```
type PlaceOrderError = Validation of ValidationError | Pricing of PricingError
```

Use `mapError` to lift each step's error into the common type before composing with `bind`.

### 3.3 Collecting All Errors (Validation)

Standard `bind` short-circuits on the first error. For validation (where you want all errors), use **applicative** composition (parallel combination) instead of sequential composition. This collects errors from independent validations into a list.

---

## 4. Bounded Contexts [INTERMEDIATE]

### 4.1 Problem Space vs. Solution Space

- **Problem space**: Domains and subdomains (areas of business knowledge)
- **Solution space**: Bounded contexts (subsystems in the implementation)

The mapping is not always 1:1. Multiple domains may map to one bounded context (especially with legacy systems), or one domain may be split across multiple contexts.

### 4.2 Bounded Context Principles

- Each context has its own dialect of the Ubiquitous Language (the word "order" may mean different things in order-taking vs. billing)
- Contexts communicate only through events and DTOs
- Design for autonomy: each context should be able to evolve independently
- Design for friction-free workflows: refactor boundaries to reduce blocking between contexts
- Boundaries should correspond to team boundaries (inverse Conway maneuver)

### 4.3 Inter-Context Relationships

| Relationship | Description |
|---|---|
| **Shared Kernel** | Two contexts share some common design; changes require consultation |
| **Customer/Supplier** | Downstream context defines the contract; upstream provides it |
| **Conformist** | Downstream context accepts upstream's contract as-is |
| **Anti-Corruption Layer** | A translator component that prevents an external model from corrupting the internal domain model |

### 4.4 Trust Boundaries

The perimeter of a bounded context is a trust boundary:
- **Input gate**: Validates and converts incoming DTOs to domain types
- **Output gate**: Converts domain types to DTOs, deliberately dropping private information
- Anything inside the boundary is trusted; anything outside is untrusted

---

## 5. Persistence Ignorance [INTERMEDIATE]

### 5.1 The Principle

The domain model must not contain any awareness of databases or persistence mechanisms. Domain types are designed purely from business concepts. Persistence is an infrastructure concern pushed to the edges.

### 5.2 Domain Types vs. DTO Types

Two distinct type hierarchies exist:

- **Domain types**: Rich, nested, use choice types, validated values, domain-specific wrappers. Not serialization-friendly.
- **DTO types**: Flat, use primitives (string, int, nullable), arrays instead of lists, enums instead of choice types. Designed for easy serialization.

### 5.3 Conversion Pattern

Every DTO type has a pair of conversion functions:
- **`fromDomain`**: Domain -> DTO. Always succeeds (a valid domain type can always produce a DTO).
- **`toDomain`**: DTO -> Result<Domain, Error>. May fail because the DTO may contain invalid data. Validation happens here, inside the bounded context.

### 5.4 Serialization as Pipeline Steps

Serialization and deserialization are added as steps at the edges of the workflow pipeline:

```
JSON -> deserialize -> DTO -> toDomain -> [WORKFLOW] -> fromDomain -> DTO -> serialize -> JSON
```

The domain workflow never sees JSON or DTOs directly.

### 5.5 DTO Translation Rules

| Domain Type | DTO Representation |
|---|---|
| Domain wrapper (`ProductCode of string`) | Underlying primitive (`string`) |
| Option | Nullable (value types) or null (reference types) |
| Records | Records with primitive fields |
| Lists, Sets | Arrays |
| Choice types (enum-like) | .NET enums or strings |
| Choice types (with data) | Tagged objects or flattened records with a discriminator field |
| Maps | Array of key-value pair records |

### 5.6 I/O at the Edges

Following the Pure Core / Imperative Shell pattern (see [Functional Hexagonal Architecture](./functional-hexagonal-architecture-comprehensive-research.md) section 4), I/O happens only at the start and end of a workflow, not inside the core domain logic.

---

## 6. State Machines with Types [INTERMEDIATE]

### 6.1 The Pattern

When a domain entity has distinct states with different data and different allowed operations, model each state as a separate type and the entity as a choice type over all states:

```
type ShoppingCart = EmptyCart | ActiveCart of ActiveCartData | PaidCart of PaidCartData
```

### 6.2 State Transition Functions

Each command handler takes the full state machine (the choice type), pattern-matches on the current state, and returns a new state:

- `addItem`: EmptyCart -> ActiveCart (create new); ActiveCart -> ActiveCart (add item); PaidCart -> PaidCart (ignore)
- `makePayment`: ActiveCart -> PaidCart; others -> unchanged

### 6.3 Benefits

- **All states are explicit**: No hidden states from flag combinations
- **Each state has its own data**: No optional fields that are "sometimes present"
- **Invalid transitions are prevented**: The type system ensures you handle every state
- **Forces completeness**: Pattern matching warnings reveal unhandled edge cases
- **Extensible**: New states can be added without modifying existing state types

### 6.4 Long-Running Workflows (Sagas)

When workflow steps involve slow external services or human interaction:
- Save state to storage before calling the service
- Wait for a completion event
- Load state and continue

The workflow becomes a series of mini-workflows connected by events, with the state machine representing the persisted state between steps.

---

## 7. Naming Patterns [STARTER]

### 7.1 Core Naming Principles

- **Use the Ubiquitous Language**: Type and function names come from the domain expert's vocabulary, not technical jargon
- **No technical noise**: No `OrderFactory`, `OrderManager`, `OrderHelper`, `OrderBase`. A domain expert would not know what these mean.
- **Types named as nouns**: `Order`, `ProductCode`, `CustomerInfo`, `BillingAmount`
- **Workflows named as verbs/commands**: `ValidateOrder`, `PriceOrder`, `PlaceOrder`
- **Events in past tense**: `OrderPlaced`, `OrderShipped`, `AcknowledgmentSent`
- **Commands in imperative**: `PlaceOrder`, `ShipOrder`, `CancelOrder`

### 7.2 Lifecycle Prefixes

Types at different stages of a workflow get prefixed with their state:
- `UnvalidatedOrder`, `UnvalidatedAddress`, `UnvalidatedOrderLine`
- `ValidatedOrder`, `ValidatedAddress`, `ValidatedOrderLine`
- `PricedOrder`, `PricedOrderLine`

This makes the stage of processing immediately visible in any type signature.

### 7.3 Dependency Naming

Dependencies (service functions) are named by what they do, not what they are:
- `CheckProductCodeExists: ProductCode -> bool`
- `GetProductPrice: ProductCode -> Price`
- `CheckAddressExists: UnvalidatedAddress -> Result<CheckedAddress, AddressValidationError>`

### 7.4 Error Type Naming

Error types are named after what went wrong, scoped to their context:
- Step-level: `ValidationError`, `PricingError`, `AddressValidationError`
- Pipeline-level: `PlaceOrderError` (a choice type unifying all step errors)

### 7.5 Module Organization

- Simple types at the top of the file (they have no dependencies)
- Compound domain types in the middle
- Top-level aggregates and workflow types at the bottom
- Types in one file, functions in a separate file (or lower in the same file)
- Namespaces correspond to bounded contexts

---

## 8. Key Design Heuristics [STARTER]

1. **Start from events and workflows, not data structures.** The event storming process surfaces events, which trigger workflows, which produce more events.

2. **Let the domain expert drive naming.** If they call it an "order quantity," that is the type name. If they say "it depends," model the conditional as a choice type.

3. **Avoid database-driven and class-driven design.** No entity-relationship diagrams, no class hierarchies during requirements gathering.

4. **Model each workflow as an input-output pipeline.** Pure functions in the middle, I/O at the edges.

5. **Use types to enforce business rules at compile time.** Every rule captured in the type system is a rule that never needs a unit test.

6. **Document effects in signatures.** Result for errors, Async for I/O, Option for missing data.

7. **Keep bounded contexts autonomous.** Communicate through events and DTOs. Each context owns its language and data.

8. **Design for consistency at the aggregate level.** Eventual consistency between aggregates and between contexts.

9. **Separate domain types from serialization types.** The domain model is pure; serialization is an infrastructure concern at the edges.

10. **Prefer explicit over implicit.** No global event managers, no hidden mutable state, no implicit dependencies. Every input and dependency is a function parameter.
