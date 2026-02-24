# Functional Programming Principles and Thinking Patterns

**Source**: "Learn You a Haskell for Great Good" (learnyouahaskell.github.io)
**Purpose**: Language-agnostic FP principles extracted from LYAH. Concepts first, syntax second.
**Date**: 2026-02-15

---

## 1. Higher-Order Functions as a Thinking Tool

### The Principle

Stop thinking "loop through items, mutate state, collect results." Start thinking "what transformation applies to each element? what filter selects the right ones? what accumulation produces the result?"

Three operations replace most loops:

| Operation | What It Does | Imperative Equivalent |
|-----------|-------------|----------------------|
| **Map** | Transform each element, preserve structure | `for` loop building new array |
| **Filter** | Keep elements matching a predicate | `for` loop with `if` inside |
| **Fold** | Accumulate elements into a single result | `for` loop with running total |

### Map: Shape-Preserving Transformation

The input structure stays the same; only values change. Nested maps handle nested structures naturally.

```haskell
map (+3) [1,5,3]                    -- [4,8,6]
map (map (^2)) [[1,2],[3,4]]       -- [[1,4],[9,16]]
```

### Filter: Selection, Not Transformation

Remove noise by applying a boolean condition. Does not change values, only membership.

```haskell
filter even [1..10]                 -- [2,4,6,8,10]
filter (>3) [1,5,3,2,1,6]          -- [5,6]
```

### Fold: The Universal List Consumer

"Folds can be used to implement any function where you traverse a list once, element by element, and return something based on that."

The fold's binary function defines how each new element changes the accumulated state:

```haskell
-- Left fold: process left-to-right, strict accumulation
sum' = foldl (+) 0

-- Right fold: process right-to-left, can work on infinite lists
map' f xs = foldr (\x acc -> f x : acc) [] xs

-- Common operations are all folds
maximum' = foldr1 (\x acc -> if x > acc then x else acc)
reverse' = foldl (\acc x -> x : acc) []
```

**Key insight**: The accumulator IS your state. The binary function IS your state transition. Folds make the state machine explicit.

### Cross-Language Translation

| Haskell | F# | Scala | Kotlin | Python | TypeScript |
|---------|-----|-------|--------|--------|------------|
| `map f xs` | `List.map f xs` | `xs.map(f)` | `xs.map(f)` | `map(f, xs)` / `[f(x) for x in xs]` | `xs.map(f)` |
| `filter p xs` | `List.filter p xs` | `xs.filter(p)` | `xs.filter(p)` | `filter(p, xs)` / `[x for x in xs if p(x)]` | `xs.filter(p)` |
| `foldl f z xs` | `List.fold f z xs` | `xs.foldLeft(z)(f)` | `xs.fold(z, f)` | `functools.reduce(f, xs, z)` | `xs.reduce(f, z)` |

---

## 2. Type-Driven Design

### The Principle

Write the type signature BEFORE the implementation. The type tells you what the function can and cannot do. A function `[a] -> a` can only select from the list -- it cannot fabricate values. A function `(a -> b) -> [a] -> [b]` must apply the function to list elements -- there is essentially one correct implementation.

"It really helps to first think what the type declaration of a function should be before concerning ourselves with the implementation."

### Type Variables as Generalization

When a function uses no specific behavior of its type parameter, make it polymorphic. `head :: [a] -> a` works for any list, because it does not inspect the elements.

**Design heuristic**: Start concrete, then ask "which type-specific operations do I actually use?" Replace concrete types with type variables for everything else. The resulting type signature documents your minimal assumptions.

### Constraints as Requirements Documentation

```haskell
elem :: (Eq a) => a -> [a] -> Bool
```

This reads: "works for any type that supports equality." The constraint `Eq a` is a capability requirement, not an inheritance relationship.

**Design progression**: Concrete types -> type variables -> constrained type variables. Each step increases reuse while documenting exactly what is needed.

### Cross-Language Translation

| Haskell | F# | Scala | Kotlin | TypeScript |
|---------|-----|-------|--------|------------|
| Type variables `a`, `b` | `'a`, `'b` | `A`, `B` | `<T>`, `<U>` | `<T>`, `<U>` |
| Constraints `(Eq a) =>` | Structural | `[A : Eq]` context bounds | `where T : Comparable<T>` | No direct equivalent (use interfaces) |
| Type inference | Full inference | Full inference | Full inference | Partial inference |

---

## 3. Pattern Matching as Decision Decomposition

### The Principle

Decompose decisions by DATA SHAPE, not by boolean conditions. Each pattern clause handles one concrete case. The compiler verifies exhaustiveness -- you cannot forget a case.

```haskell
factorial :: (Integral a) => a -> a
factorial 0 = 1                    -- base case: boundary
factorial n = n * factorial (n-1)  -- recursive case: structure
```

### Pattern Matching vs. Conditionals

- **Pattern matching** asks: "What shape is this data?"
- **Guards** ask: "What property does this value have?"
- **Where/let bindings** name intermediate results to avoid repetition

Combine them for clear, layered decisions:

```haskell
densityTell mass volume
    | density < air   = "Float in sky"
    | density <= water = "Float in water"
    | otherwise        = "Sink"
    where density = mass / volume
          air = 1.2
          water = 1000.0
```

### Design Heuristic

Prefer small extracted functions over giant match expressions. Each function should handle one level of decision. Pattern match on the top-level shape, then delegate to named functions for sub-decisions.

### Exhaustiveness as a Safety Net

When you add a new constructor to a sum type, the compiler flags every pattern match that does not handle it. This turns "did I update all the switch statements?" from a manual audit into a compiler error.

### Cross-Language Translation

| Haskell | F# | Scala | Kotlin | TypeScript |
|---------|-----|-------|--------|------------|
| Function-level patterns | `match...with` | `match` expression | `when` expression | Switch + type narrowing |
| Exhaustiveness checking | Yes (warnings) | Yes (warnings) | Yes (sealed) | Partial (discriminated unions) |
| Destructuring | Built-in | Built-in | Built-in (`case class`) | `val (a, b)` | Object destructuring |

---

## 4. Composition Patterns

### Currying and Partial Application

Every multi-argument function is a chain of single-argument functions. This is not just implementation detail -- it is a design tool.

```haskell
-- These are equivalent
multThree x y z = x * y * z
multThree = \x -> \y -> \z -> x * y * z

-- Partial application creates specialized functions
compareWithHundred = compare 100
isUpperCase = (`elem` ['A'..'Z'])
```

**Design pattern**: Instead of writing a new function, partially apply an existing one. `map (+3)` is clearer than `map (\x -> x + 3)`.

### Function Composition

The `.` operator chains functions into pipelines. Read right-to-left:

```haskell
-- Nested calls (hard to read)
fn x = ceiling (negate (tan (cos (max 50 x))))

-- Composition pipeline (reveals architecture)
fn = ceiling . negate . tan . cos . max 50
```

**The insight**: Composition reveals the ARCHITECTURE of computation -- what transforms feed into what. Each function in the chain has a single responsibility.

### Point-Free Style

Omit the explicit argument when the function is just a composition:

```haskell
sum' = foldl (+) 0       -- Instead of: sum' xs = foldl (+) 0 xs
```

Use point-free when it reveals intent. Avoid it when it obscures meaning.

### The `$` Operator

Low-precedence function application eliminates parentheses and enables treating application as data:

```haskell
map ($ 3) [(4+), (10*), (^2), sqrt]  -- [7.0, 30.0, 9.0, 1.732...]
```

### Cross-Language Translation

| Concept | F# | Scala | Kotlin | TypeScript |
|---------|-----|-------|--------|------------|
| Currying | Default for `let` functions | `.curried` | Manual or arrow-chain | Manual or arrow-chain |
| Partial application | Automatic | `f(_, 5)` placeholder | No built-in (use lambdas) | No built-in (use closures) |
| Composition | `>>` (left-to-right) `<<` (right-to-left) | `f.compose(g)` / `f.andThen(g)` | Extension functions | `flow()`/`pipe()` via libraries |
| Pipe operator | `\|>` | N/A | N/A | Proposed `\|>` (TC39 stage 2) |

---

## 5. Algebraic Data Types for Domain Modeling

### The Principle

Model your domain with two building blocks:

- **Choice types (sum types)**: "A value is ONE OF these alternatives" -- `data Shape = Circle Float | Rectangle Float Float`
- **Record types (product types)**: "A value has ALL OF these fields" -- `data Person = Person { name :: String, age :: Int }`

### Sum Types: Making Illegal States Unrepresentable

```haskell
data LockerState = Taken | Free
type Code = String

lockerLookup :: Int -> LockerMap -> Either String Code
lockerLookup n m = case Map.lookup n m of
    Nothing            -> Left "Locker doesn't exist!"
    Just (Taken, _)    -> Left "Locker is taken!"
    Just (Free, code)  -> Right code
```

`Either` carries failure information that `Maybe` loses. Choose the type that captures exactly your domain's possibilities.

### Type Parameters: Generic When Structure Is Universal

```haskell
data Maybe a = Nothing | Just a    -- The 'a' could be anything
data Tree a = EmptyTree | Node a (Tree a) (Tree a)
```

**Heuristic**: Parameterize when the container's behavior does not depend on what it holds. Keep concrete when domain semantics matter.

### Record Syntax for Clarity

```haskell
data Person = Person
    { firstName :: String
    , lastName  :: String
    , age       :: Int
    } deriving (Show)
```

Record syntax auto-generates accessor functions and enables field-based construction.

### Type Synonyms for Documentation

```haskell
type PhoneNumber = String
type PhoneBook = [(Name, PhoneNumber)]
```

Zero runtime cost, maximum readability.

### Design Rules from LYAH

1. **Do not put type constraints in data declarations.** Constraints belong in function signatures where they are actually used.
2. **Value constructors are functions.** `Just` has type `a -> Maybe a`. You can map, filter, and compose with them.
3. **Recursive types model recursive structures.** Trees, lists, and expressions are naturally recursive ADTs.

### Cross-Language Translation

| Concept | F# | Scala | Kotlin | TypeScript | Python |
|---------|-----|-------|--------|------------|--------|
| Sum type | Discriminated union | `sealed trait` + `case class` | `sealed class` | Discriminated union (`type A = B \| C`) | `@dataclass` + Union types |
| Product type | Record | `case class` | `data class` | Interface / type literal | `@dataclass` |
| Maybe/Option | `Option<'a>` | `Option[A]` | `T?` (nullable) | `T \| undefined` | `Optional[T]` |
| Either | `Result<'a,'b>` | `Either[A,B]` | `Result<T>` (Kotlin Result) | Custom / `fp-ts Either` | Custom / `returns` library |

---

## 6. Type Classes as Capability Contracts

### The Principle

Type classes define "what a thing can do" without inheritance hierarchies. They are interfaces that can be added to types after the fact, without modifying the type definition.

```haskell
class YesNo a where
    yesno :: a -> Bool

instance YesNo Int where
    yesno 0 = False
    yesno _ = True
```

### Key Properties

1. **Retroactive conformance**: You can make existing types implement new type classes without changing the type.
2. **Constraint composition**: Functions can require multiple capabilities: `(Eq a, Show a) => a -> String`
3. **Conditional instances**: `instance (Eq m) => Eq (Maybe m)` -- "Maybe is equatable when its contents are equatable."
4. **Laws, not just signatures**: `Eq` must be reflexive, symmetric, transitive. The compiler does not check laws, but violating them breaks downstream code.

### Deriving: Automatic Implementation

```haskell
data Day = Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday
    deriving (Eq, Ord, Show, Read, Bounded, Enum)
```

For simple types, the compiler can generate sensible implementations of standard type classes.

### Cross-Language Translation

| Haskell Type Class | F# | Scala | Kotlin | TypeScript | Python |
|--------------------|-----|-------|--------|------------|--------|
| Type class | SRTP / interfaces | `trait` + `given`/`using` (Scala 3) | Interface | Interface (structural) | Protocol (PEP 544) |
| Retroactive conformance | Extension members | Extension methods + givens | Extension functions | Declaration merging (limited) | Not built-in |
| `Eq` | `(=)` operator | `equals` / `==` | `equals()` / `==` | `===` | `__eq__` |
| `Ord` | `IComparable` | `Ordered` trait | `Comparable` | Custom | `__lt__`, `__gt__`, etc. |
| `Show` | `sprintf "%A"` | `toString` | `toString()` | `toString()` | `__str__` / `__repr__` |

---

## 7. Lazy Evaluation as a Design Pattern

### The Principle

Separate WHAT you want to compute from WHEN it gets computed. Define potentially infinite data structures and let the consumer determine how much to evaluate.

```haskell
-- Define an infinite sequence
naturals = [1..]
evens = [2,4..]
fibs = 0 : 1 : zipWith (+) fibs (tail fibs)

-- Consume only what you need
take 10 fibs           -- [0,1,1,2,3,5,8,13,21,34]
takeWhile (<100) fibs  -- [0,1,1,2,3,5,8,13,21,34,55,89]
```

### When Deferred Computation Is Useful Beyond Haskell

1. **Generators/iterators**: Python's `yield`, C# `IEnumerable`, JavaScript generators -- all defer computation.
2. **Streams**: Java Streams, Kotlin Sequences, F# `seq {}` -- lazy collections that process on demand.
3. **Short-circuit evaluation**: `&&` and `||` in every language are lazy. This principle generalizes.
4. **Pagination/streaming APIs**: Fetch data only as needed, not all at once.
5. **Build systems**: Make/Gradle only rebuild what changed -- laziness as architecture.

### The Separation Principle

Lazy evaluation lets you separate "generating candidates" from "selecting results":

```haskell
-- Generate ALL right triangles, then filter
[(a,b,c) | c <- [1..10], b <- [1..c], a <- [1..b],
           a^2 + b^2 == c^2, a+b+c == 24]
```

This declarative style says WHAT you want, not HOW to search for it.

### Cross-Language Translation

| Concept | F# | Scala | Kotlin | Python | TypeScript |
|---------|-----|-------|--------|--------|------------|
| Lazy sequences | `seq { }` | `LazyList` | `sequence { }` | Generators (`yield`) | Generator functions (`function*`) |
| Infinite streams | `Seq.initInfinite` | `LazyList.from(1)` | `generateSequence(1) { it + 1 }` | `itertools.count(1)` | Custom generators |
| Take N | `Seq.take n` | `.take(n)` | `.take(n)` | `itertools.islice` | Manual or library |

---

## 8. The Container Abstraction Progression

### Transformable Container (Functor)

**What it does**: Apply a function to the value(s) inside a container, without changing the container's structure.

**The pattern**: "I have a value in a box. I want to transform the value without opening the box."

```haskell
fmap :: (a -> b) -> f a -> f b

fmap (+1) (Just 3)        -- Just 4
fmap (+1) Nothing         -- Nothing
fmap (+1) [1,2,3]         -- [2,3,4]
fmap reverse getLine       -- IO action that reverses input
```

**Laws** (guarantees for safe refactoring):
- `fmap id = id` -- mapping identity does nothing
- `fmap (f . g) = fmap f . fmap g` -- you can fuse or split maps freely

**Practical meaning**: Any time you have a value "inside" something (a nullable, a list, a future, an either) and want to transform it without manually unwrapping, you want a Functor.

### Combinable Containers (Applicative Functor)

**What it does**: Apply a function that is ALSO inside a container to values inside containers. Handles multi-argument functions across containers.

**The pattern**: "I have a function in a box AND values in boxes. Combine them."

```haskell
pure :: a -> f a
(<*>) :: f (a -> b) -> f a -> f b

-- Multi-argument functions across containers
(+) <$> Just 3 <*> Just 5              -- Just 8
(+) <$> Just 3 <*> Nothing             -- Nothing
(++) <$> getLine <*> getLine            -- IO: concatenates two input lines
(*) <$> [1,2,3] <*> [10,100]           -- [10,100,20,200,30,300]
```

**Practical meaning**: Validation is the killer use case. Check multiple fields independently, combine results only if all succeed. Unlike monads, applicatives do not short-circuit -- they can collect ALL errors.

### Combinable Values (Monoid)

**What it does**: Combine two values of the same type into one, with an identity element that does not change anything.

**The pattern**: "I have many values. Smash them together into one."

```haskell
mempty  :: m              -- The identity ([], 0, "")
mappend :: m -> m -> m    -- The combining operation
mconcat :: [m] -> m       -- Reduce a list

[1,2] `mappend` [3,4]    -- [1,2,3,4]
Sum 3 `mappend` Sum 5     -- Sum 8
All True `mappend` All False -- All False
```

**Practical meaning**: Any time you fold/reduce a collection, there is a monoid hiding underneath. Monoids enable parallelism -- since `mappend` is associative, you can split work across threads and combine results in any order.

**Laws**:
- `mempty <> x = x` and `x <> mempty = x` (identity)
- `(x <> y) <> z = x <> (y <> z)` (associativity -- enables parallelism)

### Chainable Operations (Monad)

**What it does**: Chain operations where each step produces a wrapped value, and the next step depends on the previous result.

**The pattern**: "The output of step 1 determines what step 2 does. Each step might fail/branch/have effects."

```haskell
(>>=) :: m a -> (a -> m b) -> m b

-- Maybe: automatic failure propagation
Just 3 >>= (\x -> Just (x + 1)) >>= (\y -> Just (y * 2))  -- Just 8
Nothing >>= (\x -> Just (x + 1))                            -- Nothing

-- List: explore all possibilities
[1,2] >>= (\n -> ['a','b'] >>= \ch -> return (n,ch))
-- [(1,'a'),(1,'b'),(2,'a'),(2,'b')]
```

**do-notation** makes chains readable:
```haskell
routine = do
    start <- return (0,0)
    first <- landLeft 2 start
    second <- landRight 2 first
    landLeft 1 second
```

**Laws** (ensure chaining is predictable):
- `return x >>= f = f x` (left identity)
- `m >>= return = m` (right identity)
- `(m >>= f) >>= g = m >>= (\x -> f x >>= g)` (associativity)

### Specialized Monads as Design Patterns

| Pattern | What It Manages | Use When |
|---------|----------------|----------|
| **Maybe/Option** | Possible absence | Operations that can fail without explanation |
| **Either/Result** | Failure with information | Operations that fail with error details |
| **List** | Multiple possibilities | Non-deterministic computation, search |
| **Writer** | Accumulated output | Logging, auditing, collecting metadata alongside results |
| **Reader** | Shared environment | Dependency injection, configuration threading |
| **State** | Mutable state | Sequential stateful algorithms in pure code |

### The Progression Summarized

```
Functor       : fmap  f  container     -- transform inside
Applicative   : pure f <*> c1 <*> c2  -- combine independent containers
Monad         : c1 >>= f >>= g        -- chain dependent operations
Monoid        : x <> y <> z           -- smash values together
```

Each level adds power by adding a new kind of combination:
- **Functor**: one function, one container
- **Applicative**: one function, MULTIPLE containers (independent)
- **Monad**: SEQUENTIAL dependent operations, each producing a container
- **Monoid**: SAME-TYPE values collapsed into one

### Cross-Language Translation

| Abstraction | F# | Scala | Kotlin | TypeScript | Python |
|-------------|-----|-------|--------|------------|--------|
| Functor (map) | `Option.map`, `List.map` | `.map` | `.map`, `?.let{}` | `.map`, `?.` optional chain | `fmap` via `returns` lib |
| Applicative | Computation expressions | `Applicative` from cats | Arrow library | `fp-ts` Apply | `returns` library |
| Monad (bind/flatMap) | `Option.bind`, computation expressions | `.flatMap` | `.flatMap`, `?.let{}` | `.flatMap`, `fp-ts chain` | `returns` library |
| Monoid | Custom via operators | `Monoid` from cats | Custom | `fp-ts Monoid` | Custom `__add__` |
| do-notation | `let!` in computation expressions | `for` comprehension | coroutines (Arrow) | `Do` notation (`fp-ts`) | Not built-in |

---

## 9. Functional Problem-Solving Method

### The LYAH Approach

1. **Start with the type signature**: What does this function consume and produce?
2. **Identify the traversal pattern**: Are you mapping, filtering, folding, or searching?
3. **Recognize the accumulator**: If folding, what is the state and how does each element change it?
4. **Decompose by data shape**: Pattern match on constructors, handle each case independently.
5. **Compose small functions**: Build complex behavior from simple, tested pieces.

### The RPN Calculator Pattern

When you recognize "process a sequence while maintaining state":
1. Identify the state (a stack)
2. Identify the input stream (tokens)
3. Write a fold where the accumulator IS the state
4. Pattern match on each input to determine the state transition

### The Optimization Pattern (Heathrow)

When you recognize "find optimal path through sequential decisions":
1. Solve by hand to find the repeating structure
2. Represent state minimally (only what is needed for the next decision)
3. Fold over sections, carrying only the optimal-so-far state
4. Extract the answer from the final state

---

## Summary: The FP Mindset Shift

| Imperative Thinking | Functional Thinking |
|---------------------|---------------------|
| Loop through items | Map/filter/fold over collections |
| Mutate variables | Transform immutable values |
| Check conditions with if/else | Pattern match on data shapes |
| Inherit from base class | Satisfy type class constraints |
| Call methods on objects | Compose functions into pipelines |
| Handle errors with try/catch | Use Maybe/Either to make failure explicit in types |
| Pass dependencies explicitly | Use Reader pattern for implicit environment |
| Log with side effects | Use Writer pattern for pure logging |
| Manage state with mutation | Use State pattern for explicit state threading |

The core shift: **describe WHAT to compute (transformations, compositions, constraints) rather than HOW to compute it (loops, mutations, control flow).**
