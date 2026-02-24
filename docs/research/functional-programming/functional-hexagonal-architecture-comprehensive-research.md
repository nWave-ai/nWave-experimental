# Functional Hexagonal Architecture

Foundational patterns for building well-structured functional applications using hexagonal architecture (ports and adapters).

---

## Table of Contents

1. [Ports and Adapters in FP](#1-ports-and-adapters-in-fp)
2. [Domain Modeling with Types](#2-domain-modeling-with-types)
3. [Functional Composition Patterns](#3-functional-composition-patterns)
4. [Side Effect Management](#4-side-effect-management)
5. [Dependency Injection in FP](#5-dependency-injection-in-fp)
6. [Testing in Functional Architecture](#6-testing-in-functional-architecture)
7. [Naming Conventions and Readability](#7-naming-conventions-and-readability)
8. [Function Size and Decomposition](#8-function-size-and-decomposition)
9. [Combining Patterns](#9-combining-patterns)

---

## 1. Ports and Adapters in FP

### Core Finding

Functional architecture naturally implements the Ports and Adapters pattern without requiring the deliberate effort needed in object-oriented programming. In OOP, developers must intentionally structure their code to achieve hexagonal architecture; in FP, the separation emerges from the paradigm itself.

### How the Translation Works

| OOP Concept | FP Equivalent | Rationale |
|---|---|---|
| Port (interface) | Function type signature / type alias | A port defines a contract; in FP, a function signature `OrderId -> Async<Order option>` is that contract |
| Adapter (class implementing interface) | Concrete function implementation | An adapter fulfills the contract; in FP, a specific function with the matching signature does the same |
| Dependency Injection container | Function parameters / partial application / Environment pattern | Dependencies are passed as function arguments, no container needed |
| Domain service class | Module of pure functions | A group of related pure functions replaces a stateful service object |
| Entity with behavior | Immutable data type + functions operating on it | Data and behavior are separated; functions transform immutable values |

### Compiler-Enforced Architecture (Haskell)

Haskell enforces this architecture through its type system. Pure functions have types that never mention `IO`, while impure functions must declare `IO` in their return type. A pure function cannot call an impure function -- the compiler prevents it. This creates an automatic architectural boundary:

- **Pure core**: All business logic lives in functions without `IO` in their types
- **Impure shell**: All side effects (database, network, file system) live in `IO`-annotated functions
- **The boundary is enforced at compile time**, not by convention

In languages without this enforcement (F#, Scala, TypeScript), the discipline must be maintained by convention, but the pattern remains the same.

### Practical Port Definition (Multi-Language)

```
-- Haskell: Port as a type alias
type FindOrder = OrderId -> IO (Maybe Order)
type SaveOrder = Order -> IO ()

-- F#: Port as a function type
type FindOrder = OrderId -> Async<Order option>
type SaveOrder = Order -> Async<unit>

-- TypeScript: Port as a type alias
type FindOrder = (orderId: OrderId) => Promise<Order | null>
type SaveOrder = (order: Order) => Promise<void>

-- Scala (ZIO): Port as a trait with effect type
trait OrderRepository:
  def findOrder(id: OrderId): Task[Option[Order]]
  def saveOrder(order: Order): Task[Unit]
```

---

## 2. Domain Modeling with Types

### Core Finding

The type system is the primary tool for domain modeling in functional programming. By encoding business rules in types, illegal states become unrepresentable -- the compiler rejects invalid domain states before the code runs.

### Key Techniques

#### 2.1 Choice Types (Sum Types / Discriminated Unions) for State Machines

Choice types model "OR" relationships -- a value is one of several variants. This replaces boolean flags, string enums, and nullable fields.

```
-- Instead of: { status: string, shippedDate?: Date, cancelReason?: string }
-- Which allows impossible states like { status: "pending", shippedDate: today }

type OrderStatus =
  | Pending of { createdAt: DateTime }
  | Confirmed of { confirmedAt: DateTime; estimatedDelivery: DateTime }
  | Shipped of { shippedAt: DateTime; trackingNumber: TrackingNumber }
  | Delivered of { deliveredAt: DateTime; signature: Signature }
  | Cancelled of { cancelledAt: DateTime; reason: CancellationReason }
```

Each state carries only the data relevant to that state. Pattern matching forces handling of every case.

#### 2.2 Record Types (Product Types) for Entities

Record types model "AND" relationships -- a value contains all of several fields. Combined with smart constructors, they enforce rules at creation time.

```
type ValidatedOrder = {
    orderId: OrderId
    customer: ValidatedCustomer
    items: NonEmptyList<OrderItem>   -- Cannot be empty
    shippingAddress: ValidatedAddress
}
```

#### 2.3 Domain Wrappers (Newtypes / Branded Types)

Wrap primitive types to prevent accidental misuse. An `EmailAddress` is not a `String`; an `OrderId` is not an `Int`.

```
-- Haskell: newtype
newtype EmailAddress = EmailAddress String
newtype OrderId = OrderId UUID

-- TypeScript: branded type
type EmailAddress = string & { readonly __brand: 'EmailAddress' }
type OrderId = string & { readonly __brand: 'OrderId' }

-- F#: single-case union
type EmailAddress = EmailAddress of string
type OrderId = OrderId of Guid
```

#### 2.4 Smart Constructors

Smart constructors validate rules at creation time, returning a `Result` type on failure:

```
let createEmailAddress (rawInput: string) : Result<EmailAddress, ValidationError> =
    if isValidEmailFormat rawInput then
        Ok (EmailAddress rawInput)
    else
        Error (InvalidEmail rawInput)
```

The internal constructor is not exported. The only way to create an `EmailAddress` is through `createEmailAddress`, which validates.

For comprehensive domain modeling patterns, see [Domain Modeling Functional Patterns](./domain-modeling-functional-patterns.md).

---

## 3. Functional Composition Patterns

### Core Finding

Functional composition is the primary mechanism for building complex behavior from simple, well-named functions. Three key patterns dominate: pipeline composition, function composition, and error-track pipelines.

### 3.1 Pipeline Operator

The pipeline operator (`|>` in F#/Elixir, `|` in shell) passes the result of one function as the last argument to the next. It reads top-to-bottom, like a recipe:

```
let processOrder rawOrder =
    rawOrder
    |> validateOrderFields
    |> enrichWithCustomerData customerRepository
    |> calculateOrderTotal taxCalculator
    |> applyDiscountRules activePromotions
    |> generateOrderConfirmation
```

Each step is a small, named, independently testable function. The pipeline makes the business process visible.

### 3.2 Function Composition

The composition operator (`>>` in F#, `.` in Haskell) creates a new function from two existing ones. The output type of the first must match the input type of the second.

```
-- F#: compose two functions into one
let processAndConfirm = validateOrder >> calculateTotal >> generateConfirmation

-- Haskell: function composition with (.)
processAndConfirm = generateConfirmation . calculateTotal . validateOrder
```

### 3.3 Error-Track Pipelines (Railway-Oriented Programming)

Each function returns `Result<Success, Failure>`. The "bind" operation chains them so that once any step fails, subsequent steps are skipped and the error propagates to the end:

- **Happy path**: Each function receives the success value and processes it
- **Error path**: Once any function fails, subsequent functions are bypassed

```
let placeOrder rawInput =
    rawInput
    |> validateOrder         // Result<ValidOrder, OrderError>
    |> Result.bind calculateTotal    // Result<PricedOrder, OrderError>
    |> Result.bind checkInventory    // Result<ConfirmedOrder, OrderError>
    |> Result.bind chargePayment     // Result<PaidOrder, OrderError>
    |> Result.map generateReceipt    // Result<Receipt, OrderError>
```

Key combinators:
- **map**: Transform the success value (one-track function into two-track)
- **bind**: Chain a function that itself returns a Result
- **mapError**: Transform the error value
- **tee**: Perform a side effect without changing the value (logging)

### 3.4 Collect-All-Errors Validation (Applicative Style)

When you need to collect ALL errors (not short-circuit on the first), applicative style runs all validations and accumulates errors:

```
let validateOrder rawOrder =
    createValidatedOrder
    <!> validateCustomerName rawOrder.name      // Result<Name, Error list>
    <*> validateEmail rawOrder.email             // Result<Email, Error list>
    <*> validateAddress rawOrder.address         // Result<Address, Error list>
    // If any fail, ALL errors are collected
```

---

## 4. Side Effect Management

### Core Finding

The dominant pattern is "Pure Core, Imperative Shell" (coined by Gary Bernhardt). All business logic is pure; all side effects live at the system's edges. Multiple mechanisms exist to enforce this boundary.

### 4.1 Pure Core / Imperative Shell

**Architecture**:
```
+--------------------------------------------------+
|  Imperative Shell (thin)                         |
|  - HTTP handlers, CLI, message consumers         |
|  - Database access, file I/O, network calls      |
|  - Reads data, calls core, writes results        |
|                                                  |
|  +--------------------------------------------+ |
|  |  Functional Core (large)                    | |
|  |  - Pure functions only                      | |
|  |  - Domain logic, validation, calculation    | |
|  |  - No IO, no side effects                   | |
|  |  - Immutable data transformations           | |
|  +--------------------------------------------+ |
+--------------------------------------------------+
```

**The Dependency Rule**: The shell may call the core. The core never calls the shell. The core is unaware of the shell's existence.

**The "Sandwich" Pattern**: Impure (read) -> Pure (decide) -> Impure (write)

```
// Imperative shell
let handlePlaceOrder (request: HttpRequest) =
    // 1. IMPURE: Read from the world
    let rawOrder = parseRequest request
    let existingCustomer = database.findCustomer rawOrder.customerId
    let inventory = database.getInventory rawOrder.items

    // 2. PURE: Make decisions (call the core)
    let orderResult = DomainLogic.placeOrder existingCustomer inventory rawOrder

    // 3. IMPURE: Write to the world
    match orderResult with
    | Ok confirmedOrder ->
        database.saveOrder confirmedOrder
        emailService.sendConfirmation confirmedOrder
        HttpResponse.ok (serialize confirmedOrder)
    | Error validationErrors ->
        HttpResponse.badRequest (serialize validationErrors)
```

### 4.2 IO Type (Haskell)

Haskell uses the `IO` type to tag impure computations. The type system prevents mixing pure and impure code:

- `calculateTotal :: Order -> Money` -- pure, no IO
- `saveOrder :: Order -> IO ()` -- impure, tagged with IO
- `calculateTotal` cannot call `saveOrder` -- compiler error

### 4.3 Effect Systems (ZIO, Cats Effect, Koka)

Effect systems provide fine-grained control over which effects a function can perform:

```scala
// ZIO: the type signature declares EXACTLY which effects are needed
def placeOrder(order: Order): ZIO[Database & EmailService & Clock, OrderError, Confirmation]
// This function needs Database, EmailService, and Clock
// It can fail with OrderError
// It produces a Confirmation
```

Effect systems offer advantages over the IO type: effects are specific (not just "IO"), they compose well, and they support structured concurrency.

### 4.4 Comparison of Approaches

| Approach | Enforcement | Granularity | Learning Curve | Best For |
|---|---|---|---|---|
| Convention (discipline) | None -- developer choice | N/A | Low | Any language, small teams |
| IO Type | Compile-time | Binary (pure/impure) | High | Haskell |
| Effect Systems (ZIO) | Compile-time | Fine-grained per effect | High | Scala, large systems |
| Effect Systems (Koka) | Compile-time | Fine-grained, inferred | Medium | Research, new projects |
| Pure Core / Imperative Shell | Architectural convention | Module-level | Low | Any language, pragmatic |

---

## 5. Dependency Injection in FP

### Core Finding

There is no single consensus approach to DI in FP. The community is split across multiple strategies with different trade-offs. The simplest and most widely recommended starting point is "functions as parameters."

### 5.1 [STARTER] Functions as Parameters (Partial Application)

The simplest approach: pass dependencies as function parameters. Use partial application to "bake in" dependencies at the composition root.

```
// Domain function accepts dependencies as parameters
let placeOrder (findCustomer: CustomerId -> Async<Customer option>)
               (saveOrder: Order -> Async<unit>)
               (sendEmail: Email -> Async<unit>)
               (rawOrder: RawOrder) : Async<Result<Confirmation, OrderError>> =
    // Pure logic using the injected functions
    ...

// Composition root: partially apply concrete implementations
let placeOrderHandler =
    placeOrder
        Database.findCustomer      // concrete adapter
        Database.saveOrder         // concrete adapter
        EmailService.sendEmail     // concrete adapter
// placeOrderHandler : RawOrder -> Async<Result<Confirmation, OrderError>>
```

**Pros**: Simple, no abstractions, works in every language
**Cons**: Parameter lists grow; deeply nested calls require threading parameters

### 5.2 [INTERMEDIATE] Environment Pattern (Reader)

Wraps a computation in a function that accepts an environment. Dependencies are provided later.

```
// Define a Reader that needs an environment
let placeOrder (rawOrder: RawOrder) : Reader<AppEnvironment, Result<Confirmation, OrderError>> =
    reader {
        let! env = Reader.ask
        let! customer = env.findCustomer rawOrder.customerId
        ...
    }

// Run it by providing the environment
placeOrder rawOrder |> Reader.run productionEnvironment
```

**Pros**: Eliminates explicit parameter threading; composable
**Cons**: Hard to mix with Result/Async (type tetris); adds abstraction overhead

The Environment pattern "eliminates the ugly dependency parameters" but struggles when combined with other wrapper types.

### 5.3 [ADVANCED] Capability Interfaces (Tagless Final)

Abstracts over the effect type using type classes / interfaces. Popular in Scala (Cats Effect).

```scala
// Define capabilities as type classes
trait OrderRepository[F[_]]:
  def findOrder(id: OrderId): F[Option[Order]]
  def saveOrder(order: Order): F[Unit]

// Business logic is polymorphic over the effect type
def placeOrder[F[_]: Monad: OrderRepository: EmailService](
  rawOrder: RawOrder
): F[Either[OrderError, Confirmation]] = ...

// At the edge, provide concrete implementations
given OrderRepository[IO] = PostgresOrderRepository()
```

**Pros**: Maximum flexibility; testable with pure interpreters; type-safe
**Cons**: High learning curve; verbose; poor IDE support in some languages

### 5.4 [ADVANCED] Instruction Trees (Free Monad)

Builds an abstract syntax tree (AST) of operations that is interpreted later.

**Pros**: Full inspection of the computation before execution; can optimize, batch, or reinterpret
**Cons**: Performance overhead; very high complexity; rarely justified outside library/framework code

### 5.5 Recommended Approach by Context

| Context | Recommended Approach | Rationale |
|---|---|---|
| Small/medium codebase | Functions as parameters | Simplest; sufficient for most needs |
| Large codebase, many effects | Capability interfaces or effect system | Scales better; explicit capabilities |
| Haskell specifically | Type classes (capability interfaces) | Idiomatic; well-supported |
| Scala with ZIO | ZIO environment (ZLayer) | Built-in; ergonomic; effect-based |
| TypeScript/F# pragmatic | Functions as parameters + modules | Best balance of simplicity and structure |
| Library/framework code | Instruction trees (rare) | When you need to inspect/optimize the AST |

---

## 6. Testing in Functional Architecture

### Core Finding

Functional architecture makes testing dramatically simpler. Pure functions are trivially testable (no mocks, no setup, no teardown). Integration tests focus on the thin adapter layer. Property-based testing is the natural companion to domain modeling with types.

### 6.1 Testing the Pure Core

Pure functions require only input and expected output. No test doubles, no dependency injection, no setup/teardown:

```
// Unit test for a pure domain function
test "calculateOrderTotal applies tax correctly" =
    let order = { items = [{ price = 100.0; quantity = 2 }]; taxRate = 0.1 }
    let result = calculateOrderTotal order
    assertEqual 220.0 result.total
```

This is the primary benefit of the functional core pattern: the majority of business logic is pure and trivially testable.

### 6.2 Property-Based Testing for Domain Logic

Property-based testing generates random inputs and verifies that rules hold for all of them. This is especially powerful with domain types:

```
// Rule: validated orders always have at least one item
property "validated orders have non-empty items" =
    forAll generateRawOrder (fun rawOrder ->
        match validateOrder rawOrder with
        | Ok validOrder -> NonEmptyList.length validOrder.items > 0
        | Error _ -> true  // invalid orders are fine
    )

// Rule: order total is always non-negative
property "order total is non-negative" =
    forAll generateValidOrder (fun order ->
        let result = calculateOrderTotal order
        result.total >= 0.0
    )
```

Key rule categories for domain logic:
- **Invariant preservation**: Domain rules hold for all valid inputs
- **Round-trip**: Serialize then deserialize produces the same value
- **Idempotency**: Applying an operation twice equals applying it once
- **Commutativity**: Order of independent operations does not matter

### 6.3 Integration Testing at Adapter Boundaries

Adapters (database, HTTP, file system) require integration tests. These are fewer in number because adapters are thin:

```
// Integration test for the database adapter
test "PostgresOrderRepository saves and retrieves orders" =
    use testDb = createTestDatabase()
    let repository = PostgresOrderRepository(testDb.connectionString)
    let order = createSampleOrder()

    repository.saveOrder order |> Async.RunSynchronously
    let retrieved = repository.findOrder order.id |> Async.RunSynchronously

    assertEqual (Some order) retrieved
```

### 6.4 Testing Strategy Summary

| Layer | Test Type | Volume | Speed | Mocks Needed |
|---|---|---|---|---|
| Pure core (domain) | Unit + Property-based | Many | Fast (ms) | None |
| Composition root | Integration (wiring) | Few | Medium | None |
| Adapters | Integration | Few per adapter | Slow (requires infra) | None (real dependencies) |
| End-to-end | System tests | Very few | Slowest | None |

---

## 7. Naming Conventions and Readability

**Scope**: These guidelines apply to **application code** -- domain logic, workflows, adapters. Library internals and generic utility code follow different conventions (see "When Short Names Are Acceptable" below).

### Core Finding

Functional programming communities historically favor terse, mathematical naming (`f`, `g`, `xs`, `fmap`). This research explicitly rejects that convention for application code. Domain-oriented, intention-revealing names produce more maintainable code.

### 7.1 Naming Guidelines

#### Domain Language in Function Names

```
-- BAD: Mathematical convention
let f customers = filter (\cust -> cust.balance > 0) customers |> map (\cust -> cust.email)

-- GOOD: Domain language
let activeCustomerEmails customers =
    customers
    |> filter isActiveCustomer
    |> map customerEmail
```

#### Verb-Noun for Transformations (Pipeline-Friendly)

Functions that transform data should use verb-noun naming. This reads naturally in pipelines:

```
rawOrder
|> validateOrderFields        -- verb-noun
|> enrichWithCustomerData     -- verb-preposition-noun
|> calculateOrderTotal        -- verb-noun
|> applyDiscountRules         -- verb-noun
|> generateOrderConfirmation  -- verb-noun
```

#### Predicate Functions Use Question-Style Names

```
isActiveCustomer    -- not: checkActive, activeP, pred
hasShippingAddress  -- not: shippingAddr, addrCheck
canPlaceOrder       -- not: orderOk, validateOrderBool
```

#### When Short Names Are Acceptable

Single-letter names are appropriate ONLY in:
- **Library internals and generic utility functions**: `map transform items`, `fold combine initial items`
- Lambda parameters in trivial operations: `|> filter (fun count -> count > 0)` (domain names still preferred)
- Type variables: `'a`, `'b`, `F[_]`
- Mathematical domains where the convention IS the domain language

### 7.2 Module and File Organization

```
Domain/
  Order.fs              -- Order type + pure functions operating on orders
  Customer.fs           -- Customer type + pure functions
  OrderWorkflow.fs      -- Composition of Order + Customer logic
Adapters/
  PostgresOrderRepo.fs  -- Database adapter implementing FindOrder, SaveOrder
  HttpOrderApi.fs       -- HTTP adapter
  SmtpEmailSender.fs    -- Email adapter
App/
  CompositionRoot.fs    -- Wires adapters to domain, creates the "sandwich"
  Program.fs            -- Entry point
```

---

## 8. Function Size and Decomposition

### Core Finding

Small, composable functions are preferable to large pattern-match blocks. Each function should do one thing, be independently testable, and compose with others via pipelines or function composition.

### 8.1 When to Extract a Function

Extract when you can name what it does. More specifically:

- A block of code has a distinct purpose you can describe in a verb-noun phrase
- The same logic appears (or could appear) in more than one place
- A pattern match case body exceeds a few lines
- You need to test a specific piece of logic independently

```
-- BAD: Large pattern match with inline logic
let processCommand command =
    match command with
    | PlaceOrder order ->
        let validated = ... 20 lines of validation ...
        let priced = ... 10 lines of pricing ...
        let confirmed = ... 15 lines of confirmation ...
        Ok confirmed
    | CancelOrder orderId ->
        let found = ... 10 lines of lookup ...
        let cancelled = ... 10 lines of cancellation ...
        Ok cancelled

-- GOOD: Small, named, composable functions
let processCommand command =
    match command with
    | PlaceOrder order ->
        order
        |> validateOrderFields
        |> Result.bind calculateOrderPricing
        |> Result.bind confirmOrder
    | CancelOrder orderId ->
        orderId
        |> findExistingOrder
        |> Result.bind cancelOrder
```

### 8.2 Complexity Guidance

- **Pure functions**: Target cyclomatic complexity of 1-4. Most pure functions should have a single code path or a simple pattern match.
- **Adapter functions**: Slightly higher is acceptable (error handling branches), target 1-6.
- **Composition root**: Can be higher (wiring logic), but should still be linear.

### 8.3 Composition Over Nesting

```
-- BAD: Deeply nested
let result =
    match validate order with
    | Ok validated ->
        match price validated with
        | Ok priced ->
            match confirm priced with
            | Ok confirmed -> Ok confirmed
            | Error err -> Error err
        | Error err -> Error err
    | Error err -> Error err

-- GOOD: Flat pipeline using bind
let result =
    order
    |> validate
    |> Result.bind price
    |> Result.bind confirm
```

---

## 9. Combining Patterns

These patterns are not independent -- they form a layered system where each pattern enables the next.

### Pattern Dependencies

```
Domain Wrappers + Smart Constructors
        |
        v
Choice Types for State Machines -----> Error-Track Pipelines
        |                                       |
        v                                       v
Pure Core / Imperative Shell ---------> Functions as Parameters (DI)
        |                                       |
        v                                       v
Pipeline Composition <-----------------  Property-Based Testing
```

### Recommended Learning Sequence

**[STARTER] -- Start here for any functional codebase:**
1. **Pure Core / Imperative Shell** -- Separate decisions from actions. This is the foundation.
2. **Domain Wrappers** -- Stop passing raw strings and ints. Wrap them.
3. **Smart Constructors** -- Validate at the boundary, trust inside.
4. **Pipeline Composition** -- Chain small functions with `|>` or `>>`.

**[INTERMEDIATE] -- Add when the codebase grows:**
5. **Choice Types for State Machines** -- Model business states explicitly.
6. **Error-Track Pipelines** -- Handle failures without nesting.
7. **Functions as Parameters** -- Inject dependencies via partial application.
8. **Property-Based Testing** -- Write rules, not example lists.

**[ADVANCED] -- Add when you have specific scaling needs:**
9. **Capability Interfaces / Effect Systems** -- When parameter lists get unwieldy.
10. **Collect-All-Errors Validation** -- When users need all errors at once.

### Which Patterns Work Together

| Starting Pattern | Naturally Leads To | Why |
|---|---|---|
| Pure Core / Imperative Shell | Pipeline Composition | Pure functions compose naturally |
| Domain Wrappers | Smart Constructors | Wrappers need validation at creation |
| Smart Constructors | Error-Track Pipelines | Constructors return Results that chain |
| Choice Types | Pattern Matching + Exhaustiveness | Compiler catches missing cases |
| Error-Track Pipelines | Collect-All-Errors Validation | Same `Result` type, different combinator |
| Functions as Parameters | Property-Based Testing | Pure functions with injected deps are trivially testable |

---

## Summary

1. **Functional architecture IS ports and adapters** -- the paradigm naturally creates the separation that OOP must deliberately engineer
2. **Types are the primary modeling tool** -- choice types, record types, domain wrappers, and smart constructors replace defensive programming
3. **Pipelines and error-track composition** replace nested conditionals and try/catch
4. **Pure core / imperative shell** is the universal pattern -- works in every language, enforceable by convention or type system
5. **Functions as parameters** is the simplest and most recommended DI approach for most codebases
6. **Pure functions eliminate the need for mocks** -- property-based testing is the natural companion
7. **Descriptive, domain-oriented naming** over mathematical conventions in application code
8. **Small, composable functions** over large pattern-match blocks -- composition over nesting
