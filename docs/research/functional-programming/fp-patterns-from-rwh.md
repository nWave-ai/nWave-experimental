# Functional Programming Patterns from Real World Haskell

**Source**: [Real World Haskell](https://book.realworldhaskell.org/read/) by Bryan O'Sullivan, Don Stewart, and John Goerzen
**Research date**: 2026-02-15
**Scope**: Language-agnostic FP patterns extracted from practical Haskell, with cross-language translations

---

## 1. Error Handling Patterns

### 1.1 Optional Value (Maybe/Option)

**Principle**: Represent the possible absence of a value in the type system instead of using null, sentinel values, or exceptions. Forces callers to handle both cases.

**When to use**: Simple success/failure where the caller does not need to know *why* it failed. Lookups, parsing single values, optional fields.

**Haskell**:
```haskell
safeTail :: [a] -> Maybe [a]
safeTail [] = Nothing
safeTail (_:xs) = Just xs
```

**Cross-language**:
| Language | Type | Empty | Present |
|----------|------|-------|---------|
| F# | `'a option` | `None` | `Some x` |
| Scala | `Option[A]` | `None` | `Some(x)` |
| Kotlin | `T?` | `null` | value |
| Python | `Optional[T]` | `None` | value |
| TypeScript | `T \| undefined` | `undefined` | value |

### 1.2 Result with Error Context (Either/Result)

**Principle**: When failure needs explanation, return a value that carries either a success or a typed error. The error branch is a first-class value you can pattern match, log, or transform.

**When to use**: Validation, API calls, any operation where callers need to distinguish between failure modes.

**Haskell**:
```haskell
divBy :: Integral a => a -> [a] -> Either String [a]
divBy _ [] = Right []
divBy _ (0:_) = Left "division by zero"
divBy n (d:xs) = case divBy n xs of
  Left err -> Left err
  Right results -> Right ((n `div` d) : results)
```

**Cross-language**:
| Language | Type | Error | Success |
|----------|------|-------|---------|
| F# | `Result<'T,'E>` | `Error e` | `Ok v` |
| Scala | `Either[E, A]` | `Left(e)` | `Right(v)` |
| Kotlin | `Result<T>` | `failure` | `success` |
| Python | (no stdlib; use `returns` lib) | -- | -- |
| TypeScript | discriminated union | `{ok: false, error}` | `{ok: true, value}` |

### 1.3 Error Short-Circuiting (Monadic Error Propagation)

**Principle**: Chain operations that might fail so that the first failure stops the chain. No nested if/else or try/catch required.

**Haskell**:
```haskell
findAddress person phoneMap carrierMap addressMap = do
  number  <- M.lookup person phoneMap     -- fails here? whole thing is Nothing
  carrier <- M.lookup number carrierMap
  M.lookup carrier addressMap
```

**Cross-language**:
- **F#**: `result { }` computation expression
- **Scala**: `for` comprehension on `Option`/`Either`
- **Kotlin**: `?.let { }` chaining, or Arrow's `either { }`
- **Python**: Early return pattern or `returns` library `flow`
- **TypeScript**: `fp-ts` `pipe` + `chain`, or manual early-return

### 1.4 Per-Element vs All-or-Nothing Errors

**Principle**: Choose between `List<Result<T>>` (each element may fail independently) and `Result<List<T>>` (one failure kills the batch). This affects laziness, streaming, and partial results.

**Haskell**:
```haskell
-- Per-element: caller gets partial results
divBy :: Integral a => a -> [a] -> [Maybe a]
divBy n = map (\d -> if d == 0 then Nothing else Just (n `div` d))

-- All-or-nothing: first zero kills everything
divBy :: Integral a => a -> [a] -> Maybe [a]
```

**General rule**: Use per-element when partial results are useful (data pipelines, batch processing). Use all-or-nothing for transactions.

### 1.5 Custom Error Types

**Principle**: Define domain-specific error types rather than using strings. Enables exhaustive pattern matching and programmatic error handling.

```haskell
data DivByError a = DivBy0 | ForbiddenDenominator a
  deriving (Eq, Show)
```

This pattern applies universally. Every language benefits from typed/structured errors over string messages.

---

## 2. Data Processing Pipelines

### 2.1 The Sandwich Pattern (IO-Pure-IO)

**Principle**: Structure programs as: read input (impure) -> transform (pure) -> write output (impure). The pure middle is testable, composable, and parallelizable.

**Haskell**:
```haskell
interactWith f inputFile outputFile = do
  input <- readFile inputFile
  writeFile outputFile (f input)
```

**Universal pattern**:
```
readData() |> pureTransform |> writeResult()
```

### 2.2 Fold as Universal Accumulator

**Principle**: Most data processing reduces to a fold: walk a collection, accumulate a result. Prefer library fold functions over hand-written recursion -- they are well-tested, optimized, and communicate intent.

**Haskell**:
```haskell
sum     = foldl' (+) 0
length  = foldl' (\n _ -> n + 1) 0
reverse = foldl' (flip (:)) []
```

**Cross-language**: `reduce` (Python, JS/TS), `fold`/`foldLeft` (Scala, Kotlin, F#), `Aggregate` (C#/LINQ).

**Hierarchy of preference** (from RWH): Library combinators > fold > hand-written recursion.

### 2.3 Function Composition as Pipeline

**Principle**: Chain small, focused transformations. Each function does one thing. The pipeline reads as a sequence of steps.

**Haskell**:
```haskell
suffixes = init . tails
process = unlines . filter (elem 'a') . lines
```

**Cross-language**:
- **F#**: `|>` pipe operator
- **Scala**: method chaining or `andThen`
- **Kotlin**: `.let { }` chains, extension functions
- **Python**: Nested calls (no pipe), or `toolz.pipe`
- **TypeScript**: `fp-ts` `pipe`, or proposed pipeline operator

### 2.4 Partial Application for Specialization

**Principle**: Fix some arguments of a general function to create a specialized version. Eliminates throwaway helper functions.

**Haskell**:
```haskell
dropWhile isSpace        -- specialized "strip leading whitespace"
any (isInfixOf needle)   -- specialized "contains substring"
```

**Cross-language**: Lambdas serve this purpose everywhere, but F#, Scala, and Haskell support true partial application natively.

---

## 3. Parsing as a Pattern

### 3.1 Parser Combinators: Build Complex from Simple

**Principle**: Define small parsers for atomic elements (a character, a number, a keyword). Combine them with operators for sequencing, choice, and repetition. The result is a grammar expressed in code.

This is not limited to text. It applies to: binary protocols, configuration formats, API responses, command-line arguments, any structured input.

**Haskell (Parsec)**:
```haskell
csvFile = endBy line eol
line    = sepBy cell (char ',')
cell    = quotedCell <|> many (noneOf ",\n")
```

**Core combinators** (language-agnostic concepts):
| Combinator | Meaning |
|-----------|---------|
| `sequence` (do/for) | Parse A then B |
| `choice` (<\|>) | Try A, if it fails try B |
| `many` / `some` | Zero-or-more / one-or-more |
| `sepBy` | Items separated by delimiter |
| `optional` | Parse or skip |
| `try` / `attempt` | Backtrack on failure |

**Cross-language**:
- **F#**: FParsec
- **Scala**: scala-parser-combinators, fastparse
- **Kotlin**: better-parse
- **Python**: parsy, pyparsing
- **TypeScript**: parsimmon, arcsecond

### 3.2 Custom Error Messages in Parsers

**Principle**: Attach human-readable context to parser failures. When parsing fails deep in a combinator tree, the user needs to know *what* was expected, not *which combinator* failed.

```haskell
eol = try (string "\n\r") <|> string "\n" <?> "end of line"
```

### 3.3 Implicit State Threading in Parsers

**Principle**: Wrap parsing state (remaining input, position, offset) in an opaque type. Parser functions access state through controlled operations, not by passing tuples everywhere.

```haskell
newtype Parse a = Parse {
  runParse :: ParseState -> Either String (a, ParseState)
}
```

This is the State monad pattern applied to parsing. Adding new state fields (line numbers, error context) requires changes only in accessor functions.

---

## 4. Testing Practices

### 4.1 Property-Based Testing

**Principle**: Instead of testing specific input/output pairs, define *properties* that must hold for all valid inputs. The framework generates random inputs and finds counterexamples.

**Key property types**:

| Strategy | Example |
|----------|---------|
| **Idempotency** | `sort(sort(xs)) == sort(xs)` |
| **Round-trip** | `decode(encode(x)) == x` |
| **Model comparison** | `mySort(xs) == stdlib.sort(xs)` |
| **Invariant preservation** | `isSorted(sort(xs))` |
| **Conditional** | `if xs not empty then head(sort(xs)) == min(xs)` |

**Haskell (QuickCheck)**:
```haskell
prop_idempotent xs = qsort (qsort xs) == qsort xs
prop_minimum xs = not (null xs) ==> head (qsort xs) == minimum xs
prop_model xs = sort xs == qsort xs
```

**Cross-language**:
- **F#**: FsCheck
- **Scala**: ScalaCheck
- **Kotlin**: Kotest property testing
- **Python**: Hypothesis
- **TypeScript**: fast-check

### 4.2 Custom Data Generators

**Principle**: For domain types, define how to generate random instances. Use combinators to build complex generators from simple ones.

```haskell
instance Arbitrary Doc where
  arbitrary = oneof
    [ return Empty
    , Char <$> arbitrary
    , Text <$> arbitrary
    , return Line
    , Concat <$> arbitrary <*> arbitrary
    ]
```

Generator combinators: `oneof` (pick random alternative), `elements` (pick from list), `choose` (range), `frequency` (weighted choice).

### 4.3 Coverage-Driven Testing

**Principle**: Use code coverage tools to find untested paths. Property-based testing generates many cases but may miss specific branches (error paths, edge cases). Coverage reports guide where to add targeted properties.

### 4.4 Pure Functions Are Trivially Testable

**Principle**: Functions without side effects need no mocking, no setup, no teardown. They take input and produce output. This is the strongest practical argument for maximizing pure code.

---

## 5. IO and Side Effects Management

### 5.1 IO Actions as Values

**Principle**: Side effects are values that describe actions, not actions themselves. They can be stored in data structures, passed as arguments, composed -- and only execute when the runtime reaches them.

**Haskell**:
```haskell
actions :: [IO ()]
actions = map putStrLn ["hello", "world"]
-- Nothing has been printed yet. These are descriptions.
sequence_ actions  -- Now they execute.
```

**Cross-language equivalent**: Thunks/lambdas (`() => effect()`), or effect types in libraries like ZIO (Scala), Arrow (Kotlin), Effect (TypeScript).

### 5.2 Type-Level Effect Tracking

**Principle**: If a function's return type includes `IO`, it may have side effects. If it does not, it is guaranteed pure. The type signature is documentation and enforcement in one.

This is Haskell-specific in its enforcement, but the *discipline* applies everywhere: mark impure functions clearly (naming convention, return type, annotation).

### 5.3 Lazy IO for Streaming

**Principle**: Process large inputs without loading everything into memory by reading data on demand. The input appears as a regular value but is materialized lazily.

```haskell
main = do
  input <- readFile "huge.txt"       -- lazy: doesn't read yet
  writeFile "out.txt" (map toUpper input)  -- reads as it writes
```

**Caution**: Lazy IO has edge cases (resource management, error timing). Modern Haskell prefers streaming libraries (conduit, pipes). The general principle -- process data incrementally -- is universal.

### 5.4 Resource Safety Pattern

**Principle**: Acquire a resource, use it, release it -- guaranteed, even on exceptions. Use bracket/try-finally/using patterns.

```haskell
withTempFile pattern func =
  bracket (openTempFile dir pattern)
          (\(path, h) -> hClose h >> removeFile path)
          (\(path, h) -> func path h)
```

**Cross-language**: `using`/`IDisposable` (C#/F#), `try-with-resources` (Kotlin/Scala), context managers (Python), no built-in (TS -- manual try/finally).

---

## 6. Performance Patterns

### 6.1 The Space Leak

**Principle**: Deferred computation builds up chains of "I'll compute this later" (thunks) that consume memory. In eager languages, this manifests as holding references to intermediate collections.

**Fix**: Force evaluation of accumulators in tight loops.

**Haskell**:
```haskell
-- BAD: foldl builds thunk chain
mean xs = foldl (+) 0 xs / fromIntegral (length xs)

-- GOOD: foldl' forces each step
mean xs = let (sum, len) = foldl' (\(!s, !n) x -> (s+x, n+1)) (0, 0) xs
          in sum / fromIntegral len
```

**Cross-language**: In eager languages, the equivalent is avoiding unnecessary intermediate collections (use `Seq` in Scala, generators in Python, `Sequence` in Kotlin, iterators in Rust).

### 6.2 Strict vs Lazy: Decision Framework

| Choose Strict When | Choose Lazy When |
|-------------------|-----------------|
| Accumulating a numeric result | Building data structures consumed partially |
| Tight inner loops | Infinite sequences |
| Known-size data | Conditional/short-circuit evaluation |
| Performance-critical paths | Decoupling producer from consumer |

### 6.3 Profiling-Driven Optimization

**Principle**: Never optimize without profiling data. The workflow:
1. Write correct code first
2. Profile (time + allocation)
3. Identify hot spots (often: one function accounts for 80%+ of time)
4. Apply targeted fixes (strictness, unboxing, algorithm change)
5. Re-profile to verify improvement

### 6.4 Unboxing for Numeric Performance

**Principle**: Wrap primitive numeric types in structs/value types to eliminate heap allocation overhead. Strict fields with simple types let the compiler store values directly in registers.

```haskell
data Pair = Pair !Int !Double  -- unboxed with -funbox-strict-fields
```

**Cross-language**: Value types (C#/F#), `@specialized` (Scala), inline classes (Kotlin), not applicable (Python/TS -- JIT handles this).

### 6.5 Stream Fusion / Deforestation

**Principle**: Fuse multiple traversals into a single pass that allocates no intermediate collections. Libraries can achieve this via compiler rewrite rules or explicit stream types.

**Cross-language**: Kotlin `Sequence`, Java `Stream`, Scala `LazyList`/`Iterator`, Python generators, C# LINQ (deferred), Rust iterator chains.

---

## 7. Concurrency Patterns

### 7.1 Shared Mutable Variable (MVar)

**Principle**: A thread-safe container that holds zero or one value. Taking from an empty container blocks; putting into a full container blocks. Simplest synchronization primitive.

**Use for**: One-time thread coordination, simple producer/consumer, mutex-like protection.

```haskell
communicate = do
  m <- newEmptyMVar
  forkIO $ do
    v <- takeMVar m
    putStrLn ("received " ++ show v)
  putMVar m "wake up!"
```

**Cross-language**: `Channel(1)` (Kotlin), `BlockingQueue(1)` (Java/Scala), `asyncio.Queue(1)` (Python), `Promise`/`Deferred` (TS/JS for one-shot).

### 7.2 Channels for Message Passing

**Principle**: Unbounded FIFO queue between threads. Writers never block; readers block when empty. Good for decoupling producers from consumers.

**Caution**: Unbounded channels can grow without limit if consumers are slower than producers. Use bounded variants in production.

**Cross-language**: `Channel` (Kotlin coroutines, Go), `Queue` (Python), `BlockingQueue` (Java), various async queue libraries (TS).

### 7.3 Software Transactional Memory (STM)

**Principle**: Declare blocks of shared-state operations as atomic transactions. The runtime ensures isolation -- no other thread sees intermediate states. If a conflict is detected, the transaction retries automatically.

**Key advantage over locks**: Composability. Two correct STM functions combined produce a correct composed function. Two correct lock-based functions combined may deadlock.

```haskell
transfer qty fromBal toBal = atomically $ do
  from <- readTVar fromBal
  when (qty > from) retry        -- blocks until balance changes
  writeTVar fromBal (from - qty)
  readTVar toBal >>= writeTVar toBal . (+ qty)
```

**STM-specific patterns**:
- `retry`: Block until relevant state changes (no busy-waiting, no condition variables)
- `orElse`: Try transaction A; if it retries, try B instead (composable fallback)
- Keep transactions short to minimize conflicts

**Cross-language**: Clojure (built-in STM), Scala (scala-stm), Kotlin/Java (no mainstream STM -- use coroutines/locks), Python/TS (no STM).

### 7.4 Parallel Pure Computation

**Principle**: Pure functions can be evaluated in parallel without synchronization. Annotate expressions as "evaluate this in parallel" and the runtime handles scheduling.

```haskell
parSort (x:xs) = force greater `par` (force lesser `pseq` (lesser ++ x:greater))
```

**Cross-language**: Parallel streams (Java/Scala), `parallelStream` (Kotlin), `multiprocessing` (Python), Web Workers (TS/JS). Note: only safe for pure/immutable data.

---

## 8. Library Design

### 8.1 Progressive API Layers

**Principle**: Offer multiple abstraction levels. Casual users get a simple, opinionated API. Power users get low-level control. Both share the same internals.

From the Bloom filter library:
- **High-level**: `easyList 0.01 items` (just works)
- **Mid-level**: `fromList hashFns size items` (control hash functions)
- **Low-level**: Mutable operations in `ST` monad (full control)

### 8.2 Hide Internals, Export Interfaces

**Principle**: Export only the minimum API surface. Use opaque types (newtype/newtype wrappers) so users cannot depend on implementation details.

```haskell
module Supply (Supply, next, runSupply) where
-- Supply type is exported, but its constructor S is not
```

**Cross-language**: Private constructors (Kotlin, Scala), internal modules (F#), `_` prefix convention (Python), not-exported symbols (TS).

### 8.3 Type-Safe Boundaries

**Principle**: Use the type system to prevent misuse. Define typeclasses/interfaces for capabilities (like `Hashable`) rather than accepting raw functions.

### 8.4 Test Before Optimize

**Principle**: Establish correctness with property-based tests first. Optimize second. Tests protect against regressions during optimization.

---

## 9. JSON / Data Serialization Patterns

### 9.1 Algebraic Data Types for Data Models

**Principle**: Model the structure of the data format as a sum type (tagged union). Each variant represents one possible shape of the data.

```haskell
data JValue = JString String
            | JNumber Double
            | JBool Bool
            | JNull
            | JObject [(String, JValue)]
            | JArray [JValue]
```

**Cross-language**: Discriminated unions (F#, TS), sealed classes/interfaces (Kotlin, Scala), `@dataclass` + Union (Python).

### 9.2 Separate Rendering from IO

**Principle**: Build an intermediate representation (like a `Doc` type) rather than producing strings directly. This enables different output strategies (compact, pretty-printed, streaming) from the same data.

```haskell
renderJValue :: JValue -> Doc   -- pure: builds structure
putJValue :: JValue -> IO ()    -- impure: writes to handle
```

### 9.3 Accessor Functions with Optional Results

**Principle**: Provide typed accessors that return `Maybe`/`Option` rather than throwing on type mismatch.

```haskell
getString :: JValue -> Maybe String
getString (JString s) = Just s
getString _           = Nothing
```

---

## 10. Monadic Patterns for Real Work

Readable names for the three core monadic patterns that appear in every non-trivial FP application.

### 10.1 Stateful Computation (State Monad)

**What it does**: Threads a mutable value through a sequence of operations without passing it explicitly.

**When to use**: Counters, random number generators, accumulators, in-progress parse state -- anything that transforms step by step.

```haskell
type App a = State AppState a

increment :: App ()
increment = modify (\s -> s { count = count s + 1 })
```

**Cross-language**: Mutable variable in a closure (all languages), or explicit state-passing (functional style). F# has computation expressions; Scala has `State` from Cats; Kotlin/Arrow has `StateT`.

### 10.2 Environment Access (Reader Monad)

**What it does**: Makes shared, read-only configuration available to any function in a computation chain without passing it as a parameter.

**When to use**: Database connections, app config, feature flags, dependency injection.

```haskell
type App a = Reader Config a

getDbUrl :: App String
getDbUrl = asks dbConnectionUrl
```

**Cross-language**: Constructor injection (OOP), implicit parameters (Scala), context receivers (Kotlin), module-level config (Python/TS). Reader is the FP equivalent of dependency injection.

### 10.3 Logging Accumulator (Writer Monad)

**What it does**: Accumulates a side-channel value (logs, metrics, validation errors) alongside the main computation.

**When to use**: Audit trails, collecting validation errors, accumulating SQL fragments.

**Caution**: Use efficient append structures (not lists). Difference lists or sequences prevent O(n^2) concatenation.

```haskell
type Validated a = Writer [ValidationError] a

validateAge :: Int -> Validated Int
validateAge n
  | n < 0     = tell [NegativeAge] >> return 0
  | n > 150   = tell [UnrealisticAge] >> return n
  | otherwise  = return n
```

### 10.4 Stacking Effects (Monad Transformers)

**Principle**: Real applications need multiple effects simultaneously (config + state + error handling + IO). Stack them using transformers. The order matters.

```haskell
type App a = ReaderT Config (StateT AppState (ExceptT AppError IO)) a
```

**Ordering rule**: Effects you want to survive failure go *outside* the error transformer. If `WriterT` is outside `MaybeT`, logs are preserved on failure. If inside, they are lost.

**Cross-language**:
- **F#**: Computation expressions compose naturally
- **Scala**: Cats `EitherT`, `ReaderT`, `StateT` or ZIO (all-in-one)
- **Kotlin**: Arrow Fx, context receivers
- **Python**: Not idiomatic -- use classes with explicit state
- **TypeScript**: fp-ts `ReaderTaskEither` (pre-composed stack)

### 10.5 Testable Effects via Interfaces

**Principle**: Define effects as typeclasses/interfaces. Write production and test implementations. Functions polymorphic over the effect type work in both contexts without modification.

```haskell
class Monad m => MonadHandle m where
  openFile :: FilePath -> IOMode -> m Handle
  hClose   :: Handle -> m ()

-- Production: real IO
-- Test: logs operations to a Writer
```

This is the FP equivalent of mocking, but type-safe and composable.

---

## Summary: The 10 Patterns at a Glance

| # | Pattern | One-Line Summary |
|---|---------|-----------------|
| 1 | Error Handling | Use types (Option/Result) not exceptions for expected failures |
| 2 | Data Pipelines | IO-Pure-IO sandwich; fold over hand-written loops |
| 3 | Parser Combinators | Build complex parsers from tiny composable pieces |
| 4 | Property Testing | Define invariants, generate random inputs, find counterexamples |
| 5 | Effect Management | Separate pure logic from IO at the type level |
| 6 | Performance | Profile first; strict accumulators; fuse traversals |
| 7 | Concurrency | STM for composable atomicity; channels for message passing |
| 8 | Library Design | Progressive API layers; hide internals; test before optimize |
| 9 | Serialization | Sum types for data models; separate structure from rendering |
| 10 | Monadic Patterns | State, Reader, Writer as practical tools; stack with transformers |

---

## Knowledge Gaps

- **RWH is from 2008**: Some Haskell-specific advice (lazy IO, String vs Text) is outdated. Modern Haskell prefers streaming libraries and `Text`/`ByteString`.
- **No Applicative coverage**: The book predates the Applicative-Monad proposal. Modern FP heavily uses Applicative for independent effects.
- **Limited async patterns**: The concurrency chapters cover threads and STM but not modern async/await patterns now common in all languages.
- **No effect system coverage**: Modern approaches (ZIO, Polysemy, Eff) supersede monad transformers for large applications.
