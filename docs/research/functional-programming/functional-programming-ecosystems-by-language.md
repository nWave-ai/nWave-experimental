# Functional Programming Ecosystems by Language

Language-specific guidance for developers building functional applications. Covers F#, Haskell, Scala, Kotlin, and Clojure.

**Related**:
- [Domain Modeling Functional Patterns](./domain-modeling-functional-patterns.md)
- [Functional Hexagonal Architecture](./functional-hexagonal-architecture-comprehensive-research.md)
- [Property-Based Testing Frameworks by Language](./property-based-testing-frameworks-by-language.md)

---

## Table of Contents

1. [Language Decision Guide](#1-language-decision-guide)
2. [Cross-Language Comparison](#2-cross-language-comparison)
3. [F#](#3-f)
4. [Haskell](#4-haskell)
5. [Scala](#5-scala)
6. [Kotlin](#6-kotlin)
7. [Clojure](#7-clojure)

---

## 1. Language Decision Guide

### When to Choose Each Language

Pick based on your primary constraint:

```
What is your platform?
|
+-- .NET required? --> F#
|
+-- JVM required?
|   |
|   +-- Team knows Java? --> Kotlin (gentle onboarding) or Scala (full FP)
|   |
|   +-- Data-centric / REPL-driven? --> Clojure
|   |
|   +-- Need typed effect systems? --> Scala (ZIO or Cats Effect)
|
+-- Maximum type safety / correctness-critical? --> Haskell
|
+-- Rapid prototyping / data exploration? --> Clojure
```

### Decision Matrix

| Choose... | When you need... | Accept this trade-off... |
|-----------|-----------------|--------------------------|
| **F#** | Domain modeling on .NET; DDD focus; pragmatic FP | No higher-kinded types; smaller community; file-order dependency |
| **Haskell** | Maximum type safety; compiler-enforced purity | Steep learning curve; smaller talent pool; lazy evaluation surprises |
| **Scala** | JVM with full FP power; large-scale systems; data engineering | Complexity from OO+FP duality; slow compilation; ecosystem fragmentation (ZIO vs Cats Effect) |
| **Kotlin** | JVM with pragmatic FP; Android; team familiarity with Java | FP depends on Arrow library (see maturity caveat below); no higher-kinded types |
| **Clojure** | Data-centric domains; REPL-driven exploration; rapid prototyping | No compile-time type safety; runtime errors; smaller talent pool |

### Unique Strengths for Domain Modeling

| Language | What it does best that others do not |
|----------|--------------------------------------|
| **F#** | Error-track pipelines (Railway-Oriented Programming) originated here; computation expressions for custom monadic syntax; strongest DDD community resources |
| **Haskell** | Compiler prevents mixing pure and impure code; zero-cost domain wrappers; GADTs for precise state machines |
| **Scala** | Opaque types + Iron for refined types with compile-time validation; gradual OO-to-FP migration path |
| **Kotlin** | Value classes for zero-cost wrappers; `Raise` DSL for direct-style typed errors; best IDE/tooling support |
| **Clojure** | Spec-generated test data from domain descriptions; REPL-driven domain exploration; data-first philosophy |

### Kotlin Arrow Maturity Caveat

Arrow is a capable library with active development, but it carries risks worth acknowledging:
- **Context receivers/parameters** (which Arrow 2.0's `Raise` DSL relies on) are still experimental in Kotlin. The feature has been renamed and redesigned multiple times.
- Arrow's API has changed significantly between major versions. Migration from Arrow 1.x to 2.x required substantial rewrites.
- The library has a smaller contributor base than ZIO or Cats Effect.
- For teams that need stable, production-grade FP: evaluate whether Arrow's current API surface will remain stable for your project's lifetime. For teams comfortable with some API churn: Arrow provides genuinely useful abstractions.

---

## 2. Cross-Language Comparison

### Naming Conventions (All Languages)

| Element | F# | Haskell | Scala 3 | Kotlin | Clojure |
|---------|-----|---------|---------|--------|---------|
| Functions | `camelCase` | `camelCase` | `camelCase` | `camelCase` | `kebab-case` |
| Types | `PascalCase` | `PascalCase` | `PascalCase` | `PascalCase` | N/A (maps) |
| Constructors | `PascalCase` | `PascalCase` | `PascalCase` | `PascalCase` | `kebab-case` |
| Constants | `PascalCase` | `camelCase` | `PascalCase` | `UPPER_SNAKE` | `kebab-case` |
| Type params | `'a`, `'b` | `a`, `b` | `A`, `B` | `T`, `E` | N/A |
| Packages/NS | `PascalCase.Dot` | `PascalCase.Dot` | `lower.dot` | `lower.dot` | `kebab.dot` |
| Modules | `PascalCase` | `PascalCase` | `PascalCase` | N/A | `kebab-case` |
| Predicates | `isActive` | `isActive` | `isActive` | `isActive` | `active?` |
| Side effects | convention | `IO` in type | convention | `suspend` | `!` suffix |
| Smart ctors | `create` | `mk` prefix | `apply`/`from` | `invoke`/`of` | `make-` prefix |
| Acronyms | `HttpClient` | `HttpServer` | `HttpClient` | `HttpClient` | `http-client` |

### Type System Comparison

| Feature | F# | Haskell | Scala 3 | Kotlin | Clojure |
|---------|----|---------|---------|--------|---------|
| Choice types | DU (native) | `data` (native) | `enum`/`sealed` | `sealed` | Convention |
| Record types | Record (native) | Record (native) | `case class` | `data class` | Map/Record |
| Pattern matching | Native + active patterns | Native + guards | Native | `when` + smart casts | Library |
| Type inference | Hindley-Milner | Hindley-Milner (extended) | Local/bidirectional | Local | N/A |
| Higher-kinded types | No | Yes | Yes | No | N/A |
| Type classes | No (SRTP partial) | Yes (defining feature) | Yes (`given`/`using`) | No (interfaces) | Protocols |
| Zero-cost wrappers | Single-case DU (small cost) | `newtype` (zero-cost) | `opaque type` | `value class` | N/A |

### Effect Management Comparison

| Approach | F# | Haskell | Scala 3 | Kotlin | Clojure |
|----------|-----|---------|---------|--------|---------|
| Purity enforcement | Convention | Compiler (`IO`) | Convention or library | Convention | Convention |
| Primary mechanism | Computation expressions | IO / effect systems | ZIO / Cats Effect | Coroutines + Arrow | Atoms/Refs |
| Typed errors | `Result<'S,'F>` | `Either e a` | `ZIO[R,E,A]` / `Either` | Arrow `Raise<E>` | Convention (maps) |
| Async | `async { }` / `task { }` | `IO`, `Async` | ZIO fibers / CE `IO` | `suspend` + coroutines | `core.async` |

### Testing Comparison

| Aspect | F# | Haskell | Scala 3 | Kotlin | Clojure |
|--------|-----|---------|---------|--------|---------|
| Primary PBT | FsCheck | QuickCheck | ScalaCheck | Kotest | test.check |
| Modern PBT | fsharp-hedgehog | Hedgehog | ZIO Test | Kotest | test.check |
| Unit framework | Expecto/xUnit | Hspec/tasty | ScalaTest/MUnit | Kotest/JUnit5 | clojure.test |
| Spec-generated tests | No | No | No | No | Yes (spec + stest/check) |

### Composition Style Comparison

| Feature | F# | Haskell | Scala 3 | Kotlin | Clojure |
|---------|-----|---------|---------|--------|---------|
| Pipeline | `\|>` (native) | None (`.` or `&`) | `.pipe` (extension) | `.let {}` / Arrow | `->`, `->>` |
| Function composition | `>>` | `.` | `andThen`/`compose` | Manual | `comp` |
| Monadic syntax | CEs: `result { }` | `do`-notation | `for { } yield` | Arrow `either { }` | N/A |
| Error chaining | `Result.bind` | `>>=` on `Either` | `flatMap` / `for` | `Raise` context | `some->` |

---

## 3. F\#

**Ecosystem**: .NET / ML family | **Maturity**: High (2005, actively developed) | **Community**: Medium (strong in DDD/finance niches)

### 3.1 Type System

F#'s type system is optimized for domain modeling rather than abstract category theory. Discriminated unions + records + single-case unions provide the core toolkit. The lack of higher-kinded types is a deliberate trade-off for .NET interop and simplicity.

**Active Patterns**: F#'s unique feature for extensible pattern matching:

```
let (|Even|Odd|) n = if n % 2 = 0 then Even else Odd
```

### 3.2 Effect Management

F# is **impure by default**. Effect management is by convention and computation expressions.

**Computation Expressions (CEs)**: Monadic syntax sugar with `let!`, `do!`, `return`, `return!`:

| Builder | Purpose |
|---------|---------|
| `async { }` | Asynchronous I/O |
| `task { }` | .NET Task interop (preferred for .NET libs) |
| `result { }` | Error-track error handling |
| `option { }` | Optional chaining |

**AsyncResult pattern**: Combining `async` and `result` CEs for effectful, fallible workflows. Libraries like FsToolkit.ErrorHandling provide `asyncResult { }` builder.

Unlike Haskell, F# does not separate pure/impure at the type level. Purity is maintained by architectural convention (see [Pure Core / Imperative Shell](./functional-hexagonal-architecture-comprehensive-research.md#41-pure-core--imperative-shell)).

### 3.3 Architecture Patterns

F# naturally implements Ports and Adapters through:

1. **Ports as function types**: `type FindOrder = OrderId -> Async<Order option>`
2. **Adapters as concrete implementations**: `let findOrderInDb connStr orderId = ...`
3. **Dependency injection via partial application**: Dependencies first, primary input last. Partially apply at composition root.
4. **Pure core / imperative shell**: Domain logic as pure functions, I/O at edges.

**Pipeline Architecture** (Wlaschin): `UnvalidatedOrder -> ValidatedOrder -> PricedOrder -> Events`. Each transformation is a small, pure, testable function assembled via `|>`.

See: [Functional Hexagonal Architecture](./functional-hexagonal-architecture-comprehensive-research.md) sections 1, 4, 5

### 3.4 Domain Modeling Idioms

F# is the gold standard for functional domain modeling, largely due to Scott Wlaschin's work.

| Technique | F# Implementation |
|-----------|-------------------|
| Domain wrappers | Single-case DU: `type EmailAddress = EmailAddress of string` |
| Validated construction | Private DU + `create` function returning `Result<T, Error>` |
| Opaque types | Single-case DU with private constructor |
| Making illegal states unrepresentable | Choice types for state machines; `NonEmptyList` for "at least one" |
| Value objects | Records with structural equality (default) |
| Entities | Records with `[<NoEquality; NoComparison>]`, compare by ID |
| Document lifecycle | Separate types per stage: `UnvalidatedOrder`, `ValidatedOrder`, `PricedOrder` |

See: [Domain Modeling Functional Patterns](./domain-modeling-functional-patterns.md)

### 3.5 Composition Style

| Operator | Syntax | Usage |
|----------|--------|-------|
| Pipeline forward | `\|>` | `input \|> step1 \|> step2 \|> step3` |
| Function composition | `>>` | `let processAndConfirm = validate >> price >> confirm` |
| Monadic bind | `Result.bind`, `Async.bind` | `\|> Result.bind calculateTotal` |
| Map | `Result.map`, `Option.map` | `\|> Result.map generateReceipt` |

**Pipeline-first design**: F# functions use the "data last" convention so they work naturally with `|>`. This is the defining ergonomic feature of F#.

### 3.6 Error Handling

F# is the origin of Railway-Oriented Programming (Scott Wlaschin, 2014).

- **Result<'Success, 'Failure>**: Built into FSharp.Core since F# 4.1.
- **Railway pattern**: `Result.bind` for sequential composition; `Result.map` for transformations; `Result.mapError` for error type unification.
- **Collect-all-errors validation**: Libraries like FsToolkit.ErrorHandling provide `validation { }` CE.

See: [Error-Track Pipelines](./functional-hexagonal-architecture-comprehensive-research.md#33-error-track-pipelines-railway-oriented-programming)

### 3.7 Testing Ecosystem

| Tool | Purpose | Notes |
|------|---------|-------|
| **FsCheck** | Property-based testing | QuickCheck port; type-based shrinking |
| **fsharp-hedgehog** | PBT (modern) | Integrated shrinking; `property { }` CE syntax |
| **Expecto** | Test framework | F#-native; tests as values; parallel by default |
| **Unquote** | Assertions | Quotation-based assertions with clear failure messages |

### 3.8 Build Tools and Project Structure

**Build tool**: `dotnet` CLI. **Project file**: `.fsproj` (MSBuild XML).

**F#-specific constraint**: File order matters. Files are compiled top-to-bottom in the order listed in `.fsproj`.

```
MyProject/
  src/
    MyProject.Domain/         # Pure domain logic
      Types.fs                # Domain types (simple types first, aggregates last)
      OrderWorkflow.fs
    MyProject.Infrastructure/ # Adapters
      Database.fs
      HttpApi.fs
    MyProject.App/            # Composition root
      CompositionRoot.fs
      Program.fs
  tests/
    MyProject.Domain.Tests/
      OrderWorkflowTests.fs
```

---

## 4. Haskell

**Ecosystem**: GHC / Hackage | **Maturity**: Very High (1990, production-ready) | **Community**: Medium (strong in FP theory, compilers, finance)

### 4.1 Type System

Haskell has the most expressive type system of any mainstream language: GADTs, type families, phantom types, existential types, rank-N types, DataKinds.

**Trade-off**: The power comes with complexity. Type-level programming can be extremely sophisticated but also extremely difficult to learn and debug.

### 4.2 Effect Management

Haskell is **pure by default**. Side effects are tracked in the type system via the `IO` type.

```haskell
-- Pure: no IO in the type
calculateTotal :: Order -> Money

-- Impure: IO in the return type
saveOrder :: Order -> IO ()

-- calculateTotal CANNOT call saveOrder -- compiler error
```

**Effect System Landscape** (2025-2026):

| Library | Approach | Performance | When to Use |
|---------|----------|-------------|-------------|
| **mtl** | Monad transformer stacks | Good | Existing codebases; well-understood |
| **Effectful** | ReaderT over IO | Excellent | Recommended starting point; best performance |
| **Polysemy** | Algebraic effects | Poor to moderate | When algebraic effect semantics matter |
| **fused-effects** | Fusion-based | Good | Balance of performance and elegance |
| **Heftia** | Higher-order algebraic effects | Near-Effectful | Higher-order effects (new, 2024-2025) |

### 4.3 Architecture Patterns

Haskell's type system **enforces** hexagonal architecture at compile time. See [Compiler-Enforced Architecture](./functional-hexagonal-architecture-comprehensive-research.md#compiler-enforced-architecture-haskell).

**Three Layers Pattern** (common in production):

```haskell
-- Layer 1: Pure domain (no IO, no effects)
module Domain where
  calculateDiscount :: Order -> Discount

-- Layer 2: Effect interfaces (type classes or effect types)
module Effects where
  class Monad m => OrderRepo m where
    findOrder :: OrderId -> m (Maybe Order)

-- Layer 3: IO implementations
module Adapters.Postgres where
  instance OrderRepo IO where
    findOrder oid = ... -- actual database call
```

### 4.4 Domain Modeling Idioms

| Technique | Haskell Implementation |
|-----------|----------------------|
| Domain wrappers | `newtype EmailAddress = EmailAddress String` (zero-cost) |
| Validated construction | Export type but not constructor; export `mkEmailAddress :: String -> Either ValidationError EmailAddress` |
| Phantom types | `data Token (a :: TokenState) = Token String` -- encode state at type level |
| Making illegal states unrepresentable | GADTs for state-dependent types |
| NonEmpty lists | `Data.List.NonEmpty` (base library) |

### 4.5 Composition Style

| Operator | Syntax | Usage |
|----------|--------|-------|
| Function composition | `.` | `processAndConfirm = confirm . price . validate` (right-to-left) |
| Application | `$` | `print $ calculate order` (avoids parentheses) |
| Monadic bind | `>>=` | `findOrder oid >>= validateOrder >>= priceOrder` |
| Functor map | `<$>` | `calculateTotal <$> findOrder oid` |
| Applicative apply | `<*>` | `mkOrder <$> validateName name <*> validateEmail email` |
| do-notation | `do` block | Syntactic sugar for `>>=` chains |

### 4.6 Error Handling

| Type | Purpose |
|------|---------|
| `Maybe a` | Missing values |
| `Either e a` | Errors with context (right-biased: `Right` = success) |
| `ExceptT e m a` | Errors in monadic context |
| `Validation e a` | Accumulating errors (applicative) |

### 4.7 Testing Ecosystem

| Tool | Purpose |
|------|---------|
| **QuickCheck** | The original PBT framework (2000) |
| **Hedgehog** | PBT with integrated shrinking |
| **Hspec** | BDD-style test framework |
| **tasty** | Composable test tree with multiple providers |

### 4.8 Build Tools

| Tool | Config | Notes |
|------|--------|-------|
| **Cabal** | `project.cabal` | Official; `cabal-install` for deps |
| **Stack** | `stack.yaml` + `package.yaml` | Reproducible builds via curated snapshots |

---

## 5. Scala

**Ecosystem**: JVM / Scala 3 | **Maturity**: Very High (2004, Scala 3 since 2021) | **Community**: Large (enterprise, data engineering, FP)

### 5.1 Type System

Scala 3 significantly narrows the gap with Haskell: union types (`A | B`), intersection types (`A & B`), opaque types, match types, dependent function types.

Scala is the only language here that combines OO and FP with equal weight, enabling gradual adoption.

### 5.2 Effect Management

Two dominant effect libraries:

| Library | Type Signature | Philosophy | Error Model | DI |
|---------|---------------|-----------|-------------|-----|
| **ZIO** | `ZIO[R, E, A]` | Batteries-included | Typed errors (`E`) | ZLayer |
| **Cats Effect** | `IO[A]` | Minimal; type-class-based | Throwable (or EitherT) | Tagless final |

**Recommendation**: ZIO for greenfield projects wanting typed errors and integrated DI. Cats Effect for integration with the Typelevel ecosystem (http4s, FS2, Doobie).

### 5.3 Architecture Patterns

**ZIO approach**:
```scala
trait OrderRepository:
  def findOrder(id: OrderId): Task[Option[Order]]

def placeOrder(raw: RawOrder): ZIO[OrderRepository & EmailService, OrderError, Confirmation] = ...
```

**Tagless final approach** (Cats Effect):
```scala
trait OrderRepository[F[_]]:
  def findOrder(id: OrderId): F[Option[Order]]

def placeOrder[F[_]: Monad: OrderRepository](raw: RawOrder): F[Either[OrderError, Confirmation]] = ...
```

### 5.4 Domain Modeling Idioms

| Technique | Scala 3 Implementation |
|-----------|----------------------|
| Domain wrappers | **Opaque types**: `opaque type EmailAddress = String` (zero-cost) |
| Validated construction | Companion object with `apply` or `from` returning `Either` |
| Refined types | **Iron** library for compile-time and runtime validation |
| Making illegal states unrepresentable | `enum`/`sealed trait` for state machines |
| NonEmpty lists | `cats.data.NonEmptyList` or `zio.NonEmptyChunk` |

**Opaque types**: Inside the defining scope, the alias is transparent. Outside, only operations you define are available:

```scala
object Email:
  opaque type EmailAddress = String
  def apply(raw: String): Either[ValidationError, EmailAddress] =
    if raw.contains("@") then Right(raw) else Left(InvalidEmail(raw))
  extension (e: EmailAddress) def domain: String = e.split("@")(1)
```

### 5.5 Composition Style

Dominant style: for-comprehensions for monadic chains; method chaining for collection operations. Scala 3's `pipe` and `tap` from `scala.util.chaining` fill the pipeline gap.

### 5.6 Error Handling

| Type | Purpose | Source |
|------|---------|--------|
| `Option[A]` | Missing values | stdlib |
| `Either[E, A]` | Typed errors | stdlib |
| `Validated[E, A]` | Accumulating errors | Cats |
| `ZIO[R, E, A]` | Typed errors + effects | ZIO |

### 5.7 Testing Ecosystem

| Tool | Purpose |
|------|---------|
| **ScalaCheck** | Property-based testing |
| **ZIO Test** | PBT + unit testing integrated with ZIO |
| **ScalaTest** | BDD/FunSpec styles |
| **MUnit** | Lightweight; Typelevel ecosystem |

### 5.8 Build Tools

**Primary**: sbt. **Alternative**: Mill (simpler, growing adoption).

Standard layout follows Maven convention: `src/main/scala/`, `src/test/scala/`.

---

## 6. Kotlin

**Ecosystem**: JVM / Multiplatform | **Maturity**: High (2016, rapidly growing) | **Community**: Very Large (Android + server-side)

### 6.1 Type System

Sealed hierarchies are Kotlin's primary choice type mechanism:

```kotlin
sealed interface PaymentResult {
    data class Success(val transactionId: String) : PaymentResult
    data class Declined(val reason: String) : PaymentResult
    data object NetworkError : PaymentResult
}
```

KotlinConf 2025 showcased progress toward **union types** and **rich errors** as native language features, which would reduce the need for Arrow's Either.

### 6.2 Effect Management

Kotlin is **impure by default** with **coroutines** as the primary async mechanism.

**Arrow Fx**: Functional effect management built on coroutines -- `suspend` functions as the effect type, structured concurrency, `parZip`/`parTraverse` for parallel execution.

**Arrow Raise DSL**: Modern typed errors as effects:

```kotlin
context(Raise<OrderError>)
suspend fun placeOrder(raw: RawOrder): Confirmation {
    val validated = validate(raw)
    val priced = price(validated)
    return confirm(priced)
}
```

### 6.3 Architecture Patterns

Kotlin typically uses **interface-based ports** (dominant, OO style) or **function types** (FP style):

```kotlin
// Interface-based
interface OrderRepository {
    suspend fun findOrder(id: OrderId): Order?
}

// Function-type-based
typealias FindOrder = suspend (OrderId) -> Order?
```

DI: Kotlin ecosystem favors constructor injection (Koin, Dagger/Hilt). Arrow's `context` parameters may bridge to FP-style DI.

### 6.4 Domain Modeling Idioms

| Technique | Kotlin Implementation |
|-----------|----------------------|
| Domain wrappers | `@JvmInline value class EmailAddress(val value: String)` (zero-cost) |
| Validated construction | `companion object` with `invoke` returning `Either` or `Raise` context |
| State machines | `sealed interface OrderState` with data class/object variants |
| NonEmpty lists | Arrow `NonEmptyList<A>` |

### 6.5 Composition Style

Extension functions and scope functions (`let`, `run`, `also`) serve as lightweight composition. Arrow's `Raise` DSL enables direct-style code that looks imperative but is functionally pure in error handling.

**Accumulating errors**:
```kotlin
either {
    zipOrAccumulate(
        { validateName(raw.name) },
        { validateEmail(raw.email) },
        { validateAddress(raw.address) }
    ) { name, email, address -> ValidatedOrder(name, email, address) }
}
```

### 6.6 Testing Ecosystem

| Tool | Purpose |
|------|---------|
| **Kotest** | Test framework + property testing; multiplatform |
| **jqwik** | PBT on JUnit 5 engine |
| **MockK** | Kotlin-native mocking (coroutine-aware) |

### 6.7 Build Tools

**Primary**: Gradle (Kotlin DSL preferred). Standard layout follows Maven convention.

---

## 7. Clojure

**Ecosystem**: JVM / ClojureScript | **Maturity**: High (2007, stable) | **Community**: Medium (strong in data-centric domains)

### 7.1 Type System (Runtime Validation)

Clojure is **dynamically typed**. The community uses runtime validation and specification instead of compile-time types.

**clojure.spec**: Describes data shapes, validates at runtime, generates test data:

```clojure
(s/def ::email (s/and string? #(re-matches #".+@.+\..+" %)))
(s/def ::customer (s/keys :req [::name ::email]))

;; Validate at runtime
(s/valid? ::customer {:name "Alice" :email "alice@example.com"})

;; Generate test data automatically
(gen/sample (s/gen ::customer))
```

**Malli**: A newer alternative with schema-first approach, JSON Schema output, and better error messages. Growing in adoption.

### 7.2 Effect Management

Side effects are managed by **convention and architecture**, not the type system. Rich Hickey's position: "State is a succession of values over time."

- **Atoms** for managed mutable state (thread-safe via CAS)
- **Refs** + STM for coordinated state changes
- **core.async** channels for CSP-style concurrency

**Component/Integrant/Mount**: Library-level dependency injection and lifecycle management.

### 7.3 Architecture Patterns

Hexagonal architecture in Clojure:

1. **Ports as protocols**: `(defprotocol OrderRepository (find-order [this id]))`
2. **Ports as function arguments**: Pass functions directly (more idiomatic)
3. **Pure core**: Namespaces of pure functions operating on plain maps/records

**Idiomatic preference**: Functions over protocols. Pass `find-order` as a function argument rather than bundling in a protocol.

### 7.4 Domain Modeling Idioms

| Technique | Clojure Implementation |
|-----------|----------------------|
| Domain wrappers | Qualified keywords: `::order/id` instead of `OrderId` |
| Validated construction | Functions that validate and return maps |
| Making illegal states unrepresentable | **Not possible at compile time**; use spec + generative testing |
| State machines | Multimethods dispatching on `:status` key |

**Philosophy**: "Data is better than types." Domain models are plain maps with qualified keywords. Validation happens at boundaries.

### 7.5 Composition Style

Threading macros are the defining ergonomic feature:

| Pattern | Syntax | Usage |
|---------|--------|-------|
| Thread first | `->` | `(-> raw validate price confirm)` |
| Thread last | `->>` | `(->> orders (filter active?) (map :name))` |
| Some-thread | `some->` | `(some-> order validate price)` (short-circuits on nil) |
| Function composition | `comp` | `(def process (comp confirm price validate))` (right-to-left) |

### 7.6 Error Handling

Clojure has no stdlib Result/Either types:

| Approach | When |
|----------|------|
| Exceptions (`try`/`catch`, `ex-info`) | Infrastructure errors, panics |
| Return maps (`{:ok value}` / `{:error reason}`) | Domain errors (convention) |
| `some->` threading | "Not found" cases (nil short-circuit) |

### 7.7 Testing Ecosystem

| Tool | Purpose |
|------|---------|
| **clojure.test** | Built-in unit testing |
| **test.check** | Property-based testing; integrates with spec for auto-generation |
| **Kaocha** | Comprehensive test runner |

**Spec + test.check integration** is the standout feature: define specs, get generators for free, auto-check functions against their specs.

### 7.8 Build Tools

| Tool | Config | Status |
|------|--------|--------|
| **Clojure CLI** | `deps.edn` | Recommended for new projects |
| **Leiningen** | `project.clj` | Established; richer plugin ecosystem |

Note: Clojure namespaces use `-` but filenames use `_` (JVM requirement).

---

## Summary

1. **F# is the gold standard for domain modeling** -- Wlaschin's work, error-track pipelines, pipeline-first design. Choose for .NET teams doing DDD.

2. **Haskell provides the strongest guarantees** -- compiler-enforced purity, zero-cost domain wrappers, most expressive type system. Choose for correctness-critical systems where the learning curve is acceptable.

3. **Scala offers the richest effect ecosystem** -- ZIO and Cats Effect are the most mature FP effect systems on the JVM. Choose for large JVM teams wanting full FP with gradual adoption.

4. **Kotlin provides the gentlest onboarding** -- Arrow's Raise DSL brings modern typed error handling to familiar syntax. Choose for teams coming from Java/Android wanting practical FP. Be aware of Arrow's evolving API surface.

5. **Clojure trades compile-time safety for simplicity** -- spec + test.check compensates with runtime validation and generated tests. Choose for data-centric domains and REPL-driven development.

6. **All five languages implement ports and adapters naturally** -- through function types, effect environments, or interfaces. The pattern is universal; only the mechanism differs.

7. **Property-based testing is available in all five** -- Clojure's spec integration is unique in auto-generating tests from domain specs.
