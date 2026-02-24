# Property-Based Testing Frameworks by Language

**Date:** 2026-02-15
**Researcher:** Nova (nw-researcher)
**Confidence:** High (3+ independent sources for most frameworks; Medium for less-documented ones)
**Purpose:** Language-specific skill creation for AI agents

---

## Table of Contents

1. [Python: Hypothesis](#1-python-hypothesis)
2. [TypeScript/JavaScript: fast-check](#2-typescriptjavascript-fast-check)
3. [Erlang/Elixir: PropEr, PropCheck, StreamData](#3-erlangelixir-proper-propcheck-streamdata)
4. [Haskell: QuickCheck, Hedgehog](#4-haskell-quickcheck-hedgehog)
5. [Rust: proptest, quickcheck, bolero](#5-rust-proptest-quickcheck-bolero)
6. [Go: gopter, rapid](#6-go-gopter-rapid)
7. [Java/Kotlin: jqwik, junit-quickcheck](#7-javakotlin-jqwik-junit-quickcheck)
8. [Scala: ScalaCheck, ZIO Test](#8-scala-scalacheck-zio-test)
9. [C#/.NET: FsCheck, CsCheck](#9-cnet-fscheck-cscheck)
10. [Clojure: test.check](#10-clojure-testcheck)
11. [Swift: SwiftCheck](#11-swift-swiftcheck)
12. [F#: FsCheck, Hedgehog.Fsharp](#12-f-fscheck-hedgehogfsharp)
13. [Comparison Matrix](#13-comparison-matrix)
14. [Sources](#14-sources)
15. [Knowledge Gaps](#15-knowledge-gaps)

---

## 1. Python: Hypothesis

### Primary Framework

**Hypothesis** -- the dominant PBT framework for Python. Created by David R. MacIver, actively maintained, used by PyTorch, NumPy, pandas, and dozens of major projects [S1][S2].

- **GitHub:** github.com/HypothesisWorks/hypothesis (~8k stars)
- **Maturity:** 10+ years (first release 2013)
- **Community:** Large -- used across the scientific Python ecosystem

### API Style

Properties are defined as test functions decorated with `@given()`. Data generators are called "strategies" and live in `hypothesis.strategies` (aliased as `st`). Strategies compose via `.map()`, `.filter()`, `.flatmap()`, and the `@st.composite` decorator.

```python
from hypothesis import given, assume, settings
from hypothesis import strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs):
    once = sorted(xs)
    twice = sorted(once)
    assert once == twice

# Custom composite strategy
@st.composite
def sorted_lists(draw, min_size=0):
    xs = draw(st.lists(st.integers(), min_size=min_size))
    return sorted(xs)
```

Integration with **pytest** is seamless -- Hypothesis tests are regular pytest functions. No special plugin required; `@given` works with `@pytest.mark.parametrize` and fixtures.

### Shrinking Approach: Internal Shrinking

Hypothesis uses a unique **internal shrinking** approach. Instead of shrinking generated values, it shrinks the underlying byte stream (choice sequence) that produced those values, then replays the strategies against the simplified stream [S2][S3].

- Two simplicity rules: shorter byte arrays are simpler; lexicographically earlier arrays are simpler
- Users rarely need to write custom shrinkers
- Works correctly across monadic bind (unlike integrated shrinking)
- Generation and shrinking cannot get out of sync

### Stateful Testing: Yes

Hypothesis provides `RuleBasedStateMachine` for stateful testing [S4]:
- `@rule()` decorators define operations
- `@initialize()` for setup
- `@invariant()` for global assertions checked after every step
- `Bundle` objects track values across rules (e.g., created resource IDs)
- `@precondition()` guards rules based on model state

**Limitation:** No parallel/linearizability testing support [S5].

### Unique Features

- **Database of examples:** Hypothesis persists failing examples to a local database and replays them in future runs
- **Coverage-guided generation:** Can use coverage information to guide exploration
- **Ghostwriter:** Automatically generates property tests from type annotations (`hypothesis write module.function`)
- **Health checks:** Warns when strategies are too slow or filter too aggressively
- **Deadline enforcement:** Fails tests that take too long per example
- **Profiles:** Named settings profiles for CI vs local development

### Quick Example

```python
import json
from hypothesis import given
from hypothesis import strategies as st

@given(st.dictionaries(
    keys=st.text(min_size=1),
    values=st.one_of(st.integers(), st.text(), st.booleans(), st.none())
))
def test_json_roundtrip(d):
    assert json.loads(json.dumps(d)) == d
```

Sources: [S1][S2][S3][S4][S5]

---

## 2. TypeScript/JavaScript: fast-check

### Primary Framework

**fast-check** -- the dominant PBT framework for the JS/TS ecosystem. Created by Nicolas Dubien, written in TypeScript with first-class type support [S6][S7].

- **GitHub:** github.com/dubzzz/fast-check (~4.5k stars)
- **Maturity:** 8+ years (first release 2017)
- **Community:** Large -- used by jest, jasmine, fp-ts, ramda, js-yaml

### API Style

Properties are defined using `fc.assert(fc.property(...))`. Generators are called "arbitraries." The API is fluent and type-safe.

```typescript
import fc from 'fast-check';

// Basic property
fc.assert(
  fc.property(fc.array(fc.integer()), (arr) => {
    const sorted = [...arr].sort((a, b) => a - b);
    expect(sorted.length).toBe(arr.length);
  })
);

// Custom arbitrary with map
const evenInteger = fc.integer().map(n => n * 2);

// Record-based generation
const userArb = fc.record({
  name: fc.string({ minLength: 1 }),
  age: fc.integer({ min: 0, max: 150 }),
  active: fc.boolean(),
});

// Recursive structures with letrec
const jsonArb = fc.letrec(tie => ({
  value: fc.oneof(
    fc.constant(null), fc.boolean(), fc.integer(), fc.string(),
    fc.array(tie('value')), fc.dictionary(fc.string(), tie('value'))
  ),
})).value;
```

Integrates with **jest**, **vitest**, and **ava** via official plugins providing enhanced `test` and `it` functions with automatic timeout synchronization.

### Shrinking Approach: Integrated Shrinking

fast-check uses **integrated shrinking** -- generators produce shrink trees (rose trees) where the root is the generated value and children are progressively simpler alternatives [S6][S7][S8].

- Composing generators automatically composes shrinking
- Works well for independent (applicative) composition
- Dependent (monadic/chain) generators may produce suboptimal shrinks
- Custom shrinking can be specified via the `Arbitrary` class

### Stateful Testing: Yes

fast-check provides model-based testing via `fc.commands` and `fc.modelRun` [S7][S9]:

```typescript
class PushCommand implements fc.Command<Model, RealStack> {
  constructor(readonly value: number) {}
  check = (m: Readonly<Model>) => true;
  run(m: Model, r: RealStack): void {
    r.push(this.value);
    m.items.push(this.value);
  }
  toString = () => `push(${this.value})`;
}
```

- `fc.asyncModelRun` for async operations
- `fc.scheduledModelRun` with `fc.scheduler()` for race condition detection
- The scheduler wraps promises and controls resolution order

### Unique Features

- **Race condition detection:** `fc.scheduler()` arbitrary controls async interleaving order -- unique among PBT frameworks outside Erlang
- **Replay system:** Failing tests produce a `seed` and `replayPath` for deterministic reproduction
- **Bias mode:** Generates edge cases (0, -1, MAX_INT, empty strings) more frequently than pure random
- **Verbose mode:** Detailed output showing all generated values and shrink steps
- **No dependencies:** Zero runtime dependencies

### Quick Example

```typescript
import fc from 'fast-check';

test('JSON roundtrip', () => {
  fc.assert(
    fc.property(
      fc.dictionary(fc.string(), fc.oneof(fc.integer(), fc.string())),
      (obj) => {
        expect(JSON.parse(JSON.stringify(obj))).toEqual(obj);
      }
    ),
    { numRuns: 1000 }
  );
});
```

Sources: [S6][S7][S8][S9]

---

## 3. Erlang/Elixir: PropEr, PropCheck, StreamData

### PropEr (Erlang)

The primary open-source PBT framework for Erlang, inspired by QuickCheck. Deeply integrated with the BEAM ecosystem [S10][S11].

- **GitHub:** github.com/proper-testing/proper (~900 stars)
- **Maturity:** 15+ years
- **Community:** Core Erlang testing tool

**API Style:** Uses macros (`?FORALL`, `?LET`, `?SUCHTHAT`, `?LAZY`, `?SHRINK`).

```erlang
prop_sort_preserves_length() ->
    ?FORALL(List, list(integer()),
        length(lists:sort(List)) =:= length(List)).

%% Custom generator with ?LET
sorted_list() ->
    ?LET(L, list(integer()), lists:sort(L)).
```

**Shrinking:** Type-based (manual). Generators and shrinkers are separate. `?SHRINK` and `?LETSHRINK` macros provide explicit control. Numbers shrink toward 0, lists toward `[]` [S10][S11].

**Stateful Testing:** Yes -- `proper_statem` module with full state machine support:
- `initial_state/0`, `command/1`, `precondition/2`, `postcondition/3`, `next_state/3` callbacks
- Symbolic references during generation, concrete values during execution
- Two-phase execution model (abstract + real)
- `parallel_commands/1` for linearizability testing [S10][S11][S12]

**Unique:** `proper_fsm` module for finite state machine testing (distinct from generic state machines). PULSE integration for controlled scheduling in parallel tests.

### PropCheck (Elixir)

An Elixir wrapper around PropEr providing idiomatic Elixir syntax [S13].

- **GitHub:** github.com/alfert/propcheck (~400 stars)
- Same capabilities as PropEr (stateful testing, parallel testing)
- Elixir-idiomatic API using macros like `forall`, `let_shrink`

```elixir
property "list reversal is involutory" do
  forall l <- list(integer()) do
    l == Enum.reverse(Enum.reverse(l))
  end
end
```

### StreamData (Elixir)

Native Elixir PBT library, written entirely in Elixir [S14].

- **GitHub:** github.com/whatyouhide/stream_data (~800 stars)
- Idiomatic Elixir API using `ExUnitProperties`
- **No stateful testing support** -- the major gap vs PropCheck
- Simpler API, better Elixir integration

```elixir
use ExUnitProperties

property "bin roundtrip" do
  check all bin <- binary() do
    assert bin == :erlang.iolist_to_binary([bin])
  end
end
```

Sources: [S10][S11][S12][S13][S14]

---

## 4. Haskell: QuickCheck, Hedgehog

### QuickCheck (The Original)

The framework that started it all. Created by Koen Claessen and John Hughes in 2000 [S15].

- **Hackage:** Test.QuickCheck
- **Maturity:** 25+ years -- the grandfather of all PBT
- **Community:** Universal in Haskell

**API Style:** Uses the `Arbitrary` type class. One generator per type. Properties are functions returning `Bool` or `Property`.

```haskell
import Test.QuickCheck

prop_reverse_involutory :: [Int] -> Bool
prop_reverse_involutory xs = reverse (reverse xs) == xs

-- Custom Arbitrary instance
data Color = Red | Green | Blue deriving (Show, Eq)

instance Arbitrary Color where
  arbitrary = elements [Red, Green, Blue]
  shrink Red = []
  shrink _   = [Red]
```

**Shrinking:** Type-based (manual). The `shrink` function in `Arbitrary` returns a list of simpler candidates. Composing shrinkers for complex types requires manual effort [S8][S15].

**Stateful Testing:** Yes (via Quviq's commercial QuickCheck). The open-source version has limited stateful support; `quickcheck-state-machine` package adds it.

**Unique:** The original academic paper. The `Arbitrary` type class approach. Commercial Quviq QuickCheck (Erlang) is the most complete PBT implementation in existence, finding bugs in Ericsson, Volvo, and AUTOSAR systems [S16].

### Hedgehog

Modern alternative using integrated shrinking [S17][S18].

- **GitHub:** github.com/hedgehogqa/haskell-hedgehog (~700 stars)
- **Maturity:** 8+ years

**API Style:** No type classes for generators. Every generator is an explicit value. Uses `Gen` and `Range` combinators.

```haskell
import Hedgehog
import qualified Hedgehog.Gen as Gen
import qualified Hedgehog.Range as Range

prop_reverse :: Property
prop_reverse = property $ do
  xs <- forAll $ Gen.list (Range.linear 0 100) Gen.alpha
  reverse (reverse xs) === xs
```

**Shrinking:** Integrated. Generators produce rose trees of values. Shrinking composes automatically through applicative interface [S8][S17].

**Trade-off vs QuickCheck:** No orphan instance problems, better shrinking composition, but generators require more code and shrinking can be significantly slower [S17][S18].

**Stateful Testing:** Yes -- via `Hedgehog.Gen` command sequences. Supports parallel state machine testing.

Sources: [S8][S15][S16][S17][S18]

---

## 5. Rust: proptest, quickcheck, bolero

### proptest

The most popular Rust PBT framework, inspired by Hypothesis [S19][S20].

- **GitHub:** github.com/proptest-rs/proptest (~1.7k stars)
- **Maturity:** 7+ years

**API Style:** Uses `Strategy` objects (not type-based). The `proptest!` macro provides concise syntax.

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn sort_preserves_length(ref v in prop::collection::vec(any::<i32>(), 0..100)) {
        let mut sorted = v.clone();
        sorted.sort();
        prop_assert_eq!(sorted.len(), v.len());
    }
}

// Custom strategy
fn even_integers() -> impl Strategy<Value = i32> {
    any::<i32>().prop_map(|x| x * 2)
}
```

**Shrinking:** Integrated (Hypothesis-inspired). Strategies are constraint-aware and avoid generating invalid values. Maintains intermediate states for richer shrinking. Trade-off: up to 10x slower generation than quickcheck for complex types [S20].

**Stateful Testing:** No built-in support.

**Unique:** Multiple strategies per type without newtype wrappers. Direct range specification (`0..100i32`). Regex-based string generation (`"[a-z]{1,10}"`). Persistence of failing cases to files.

### quickcheck (quickcheck-rs)

Rust port of Haskell's QuickCheck [S21].

- **GitHub:** github.com/BurntSushi/quickcheck (~2.4k stars)
- **Maturity:** 10+ years (by Andrew Gallant / BurntSushi)

**API Style:** Type-based via the `Arbitrary` trait. One generator per type.

```rust
use quickcheck::quickcheck;

quickcheck! {
    fn prop_reverse_involutory(xs: Vec<i32>) -> bool {
        let rev: Vec<_> = xs.iter().rev().rev().cloned().collect();
        rev == xs
    }
}
```

**Shrinking:** Type-based (manual). Stateless, fast, but limited composability. Cannot express constraints; relies on `TestResult::discard()` for filtering [S20].

**Stateful Testing:** No.

### bolero

A fuzz-testing and PBT frontend that unifies multiple engines [S22].

- **GitHub:** github.com/camshaft/bolero (~300 stars)

**API Style:** Uses the `bolero::check!` macro.

```rust
use bolero::check;

#[test]
fn sort_test() {
    check!().with_type::<Vec<i32>>().for_each(|v| {
        let mut sorted = v.clone();
        sorted.sort();
        assert_eq!(sorted.len(), v.len());
    });
}
```

**Unique:** Pluggable engines -- can run the same test with libfuzzer, honggfuzz, AFL, or even the Kani formal verifier. Bridges the gap between property testing and fuzzing/verification.

**Shrinking:** Depends on the engine. **Stateful Testing:** No.

Sources: [S19][S20][S21][S22]

---

## 6. Go: gopter, rapid

### gopter

The more established Go PBT library, inspired by QuickCheck and ScalaCheck [S23].

- **GitHub:** github.com/leanovate/gopter (~600 stars)

**API Style:** Explicit generator construction with separate packages for `gen`, `prop`, `arbitrary`, and `commands`.

```go
import (
    "github.com/leanovate/gopter"
    "github.com/leanovate/gopter/gen"
    "github.com/leanovate/gopter/prop"
)

func TestSortLength(t *testing.T) {
    properties := gopter.NewProperties(nil)
    properties.Property("sort preserves length", prop.ForAll(
        func(xs []int) bool {
            sort.Ints(xs)
            return len(xs) == len(xs) // simplified
        },
        gen.SliceOf(gen.Int()),
    ))
    properties.TestingRun(t)
}
```

**Shrinking:** Type-based. **Stateful Testing:** Yes -- via `commands` package. **Maturity:** More features, more verbose API.

### rapid

Modern Go PBT library with a simpler API [S24].

- **GitHub:** github.com/flyingmutant/rapid (~600 stars)

**API Style:** Uses `*rapid.T` parameter (similar to Go's `*testing.T`). Generators are functions that take `*rapid.T`.

```go
import "pgregory.net/rapid"

func TestSortLength(t *testing.T) {
    rapid.Check(t, func(t *rapid.T) {
        xs := rapid.SliceOf(rapid.Int()).Draw(t, "xs")
        sorted := make([]int, len(xs))
        copy(sorted, xs)
        sort.Ints(sorted)
        if len(sorted) != len(xs) {
            t.Fatalf("length changed: %d -> %d", len(xs), len(sorted))
        }
    })
}
```

**Shrinking:** Internal (Hypothesis-inspired). Fully automatic, no user code needed. Understands value structure for intelligent minimization [S24].

**Stateful Testing:** Yes -- via `rapid.StateMachine`. **Unique:** The most Hypothesis-like Go library. Simpler API than gopter with better automatic shrinking.

Sources: [S23][S24]

---

## 7. Java/Kotlin: jqwik, junit-quickcheck

### jqwik

The primary PBT framework for Java, built as a JUnit 5 test engine [S25][S26].

- **GitHub:** github.com/jqwik-dev/jqwik (~600 stars)
- **Maturity:** 7+ years, actively maintained by Johannes Link

**API Style:** Annotation-driven. `@Property` instead of `@Test`, `@ForAll` on parameters.

```java
import net.jqwik.api.*;

class SortProperties {
    @Property
    void sortPreservesLength(@ForAll List<Integer> list) {
        List<Integer> sorted = new ArrayList<>(list);
        Collections.sort(sorted);
        Assertions.assertEquals(list.size(), sorted.size());
    }

    @Property
    void sortIsIdempotent(@ForAll List<Integer> list) {
        List<Integer> once = new ArrayList<>(list);
        Collections.sort(once);
        List<Integer> twice = new ArrayList<>(once);
        Collections.sort(twice);
        Assertions.assertEquals(once, twice);
    }

    // Custom provider
    @Provide
    Arbitrary<String> emails() {
        return Arbitraries.strings()
            .alpha().ofMinLength(1).ofMaxLength(10)
            .map(name -> name + "@example.com");
    }
}
```

**Shrinking:** Integrated. Automatic for built-in types. When a failure is found, jqwik tries to simplify to the minimal reproducing case [S25].

**Stateful Testing:** Yes -- via action sequences. Actions are generated and executed sequentially against a model [S26].

**Unique Features:**
- **Edge cases:** Automatically tests boundary values (0, MIN/MAX, empty collections)
- **Statistics:** `@StatisticsReport` annotation shows distribution of generated values
- **Domains:** Group related arbitraries into reusable domain contexts
- **Kotlin support:** Works natively with Kotlin via JUnit 5

### junit-quickcheck

Older alternative, less actively maintained [S27].

- **GitHub:** github.com/pholser/junit-quickcheck (~950 stars)
- Uses JUnit 4 `@RunWith` approach
- Less feature-rich than jqwik; **no stateful testing**
- Largely superseded by jqwik for new projects

Sources: [S25][S26][S27]

---

## 8. Scala: ScalaCheck, ZIO Test

### ScalaCheck

The established PBT library for Scala, inspired by Haskell's QuickCheck [S28].

- **GitHub:** github.com/typelevel/scalacheck (~1.9k stars)
- **Maturity:** 15+ years
- **Community:** Used by Cats, Akka, Spark

**API Style:** `Prop.forAll` with implicit `Arbitrary` instances (type-class based, like Haskell QuickCheck). `Gen` combinators for custom generators.

```scala
import org.scalacheck.Prop.forAll
import org.scalacheck.{Gen, Arbitrary}

val propSortLength = forAll { (xs: List[Int]) =>
  xs.sorted.length == xs.length
}

// Custom generator
val genEven: Gen[Int] = Gen.choose(-1000, 1000).map(_ * 2)

// With ScalaTest integration
class SortSpec extends AnyFunSuite with ScalaCheckPropertyChecks {
  test("sort is idempotent") {
    forAll { (xs: List[Int]) =>
      xs.sorted.sorted shouldBe xs.sorted
    }
  }
}
```

**Shrinking:** Type-based (manual). `Shrink[T]` type class. Known to be problematic -- can shrink to values that violate generator constraints [S28].

**Stateful Testing:** Yes -- via `Commands` trait (sequential and parallel). Less commonly used than the stateless API.

**Integration:** ScalaTest, specs2, LambdaTest. No external dependencies beyond Scala runtime.

### ZIO Test

Property testing built into the ZIO effect system [S29].

```scala
import zio.test._

test("sort preserves length") {
  check(Gen.listOf(Gen.int)) { xs =>
    assertTrue(xs.sorted.length == xs.length)
  }
}
```

**Shrinking:** Integrated (built into ZIO generators). **Stateful Testing:** Through ZIO's effect system. **Unique:** Tight integration with ZIO effects; can test effectful properties natively. Provides adapters to use ScalaCheck generators.

Sources: [S28][S29]

---

## 9. C#/.NET: FsCheck, CsCheck

### FsCheck

F# implementation of QuickCheck with C# API [S30].

- **GitHub:** github.com/fscheck/FsCheck (~1.1k stars)
- **Maturity:** 15+ years
- **NuGet:** FsCheck, FsCheck.Xunit, FsCheck.NUnit

**API Style (C#):**

```csharp
using FsCheck;
using FsCheck.Xunit;

public class SortProperties
{
    [Property]
    public bool SortPreservesLength(List<int> xs)
    {
        xs.Sort();
        return xs.Count == xs.Count; // simplified
    }

    [Property]
    public Property SortIsIdempotent()
    {
        return Prop.ForAll<List<int>>(xs =>
        {
            var once = xs.OrderBy(x => x).ToList();
            var twice = once.OrderBy(x => x).ToList();
            return once.SequenceEqual(twice);
        });
    }
}
```

**Shrinking:** Type-based (manual). `Arb<T>` provides generation and shrinking. **Stateful Testing:** Limited -- no built-in state machine module. **Unique:** Works from F#, C#, and VB.NET. FsCheck v3 is the current stable version.

### CsCheck

Modern C# PBT library with unique parallel testing capabilities [S31][S32].

- **GitHub:** github.com/AnthonyLloyd/CsCheck (~300 stars)
- **NuGet:** CsCheck

**API Style:**

```csharp
using CsCheck;

[Fact]
public void Sort_Preserves_Length()
{
    Gen.Int.Array
       .Sample(arr =>
       {
           var sorted = arr.OrderBy(x => x).ToArray();
           return sorted.Length == arr.Length;
       });
}
```

**Shrinking:** PCG-based random shrinking. Both generation and shrinking use the PCG random number generator, making shrinking parallelizable and fast [S31].

**Stateful Testing:** Yes. **Parallel/Linearizability Testing:** Yes -- `Check.SampleConcurrent` runs operations sequentially then in parallel and checks against all possible linearizations. This is rare among PBT frameworks [S31][S32].

**Unique:** One of the few frameworks (alongside PropEr and Hedgehog) that supports parallel linearizability testing. Shrinking works even for parallel test failures. Very fast due to PCG-based approach.

Sources: [S30][S31][S32]

---

## 10. Clojure: test.check

**test.check** -- the standard PBT library for Clojure, inspired by QuickCheck [S33].

- **GitHub:** github.com/clojure/test.check (~1.2k stars)
- **Maturity:** 10+ years
- Official Clojure contrib library

**API Style:** Functional. Uses `gen/` namespace for generators, `prop/for-all` for properties, `tc/quick-check` for execution.

```clojure
(require '[clojure.test.check :as tc])
(require '[clojure.test.check.generators :as gen])
(require '[clojure.test.check.properties :as prop])

(def prop-sort-idempotent
  (prop/for-all [v (gen/vector gen/small-integer)]
    (= (sort v) (sort (sort v)))))

(tc/quick-check 1000 prop-sort-idempotent)

;; Custom generator
(def gen-even
  (gen/fmap #(* 2 %) gen/small-integer))
```

Integration with `clojure.test` via `defspec` macro. Deep integration with **clojure.spec** -- specs can automatically generate test data.

**Shrinking:** Integrated. Generators produce shrink trees. Automatic composition through `gen/fmap` and `gen/bind` [S33].

**Stateful Testing:** No built-in support.

**Unique:** Integration with clojure.spec for automatic generator derivation from data specifications. Size-based generation that starts small and grows.

Sources: [S33]

---

## 11. Swift: SwiftCheck

**SwiftCheck** -- QuickCheck for Swift [S34].

- **GitHub:** github.com/typelift/SwiftCheck (~1.4k stars)
- **Maturity:** 8+ years (maintenance mode)

**API Style:** Uses `Arbitrary` protocol (like Haskell's type class). `forAll` quantifier.

```swift
import SwiftCheck

func testSortPreservesLength() {
    property("sort preserves length") <- forAll { (xs: [Int]) in
        return xs.sorted().count == xs.count
    }
}

// Custom Arbitrary
extension Color: Arbitrary {
    static var arbitrary: Gen<Color> {
        return Gen<Color>.fromElements(of: [.red, .green, .blue])
    }
}
```

**Shrinking:** Type-based (manual). Minimal counterexample search via `shrink` method on `Arbitrary` [S34].

**Stateful Testing:** No.

**Unique Features:**
- `^&&^` conjunction operator for composing properties
- `<?>` labelling operator for sub-property identification
- `==>` implication operator for preconditions
- **Note:** A newer Swift Testing-native property testing library is under development as a potential successor [S34].

Sources: [S34]

---

## 12. F#: FsCheck, Hedgehog.Fsharp

### FsCheck (F# API)

The same FsCheck library as in the C# section, but with its native F# API which is more idiomatic [S30].

```fsharp
open FsCheck

let propSortIdempotent (xs: int list) =
    let once = List.sort xs
    let twice = List.sort once
    once = twice

Check.Quick propSortIdempotent

// Generator combinators
let genEven = Gen.choose (-100, 100) |> Gen.map (fun x -> x * 2)
```

**Shrinking:** Type-based. **Stateful Testing:** Limited.

### Hedgehog (fsharp-hedgehog)

State-of-the-art PBT for .NET with integrated shrinking [S35].

- **GitHub:** github.com/hedgehogqa/fsharp-hedgehog (~500 stars)

**API Style:** Uses F# computation expressions (`gen { }`, `property { }`).

```fsharp
open Hedgehog

let propReverse = property {
    let! xs = Gen.list (Range.linear 0 100) Gen.alpha
    return List.rev (List.rev xs) = xs
}

Property.check propReverse
```

**Shrinking:** Integrated. Generators produce shrink trees automatically. Better composition than FsCheck's type-based approach [S35].

**Stateful Testing:** No built-in module (unlike Haskell Hedgehog).

**Unique:** `Hedgehog.Xunit` for xUnit integration. `Hedgehog.Experimental` for auto-generators (AutoFixture-like). Computation expression syntax is the most readable F# PBT API.

Sources: [S30][S35]

---

## 13. Comparison Matrix

| Language | Framework | Shrinking | Stateful | Parallel Testing | Active Maintenance |
|----------|-----------|-----------|----------|------------------|--------------------|
| Python | Hypothesis | Internal | Yes (RuleBasedStateMachine) | No | Yes (very active) |
| TS/JS | fast-check | Integrated | Yes (fc.commands) | Yes (scheduler) | Yes (very active) |
| Erlang | PropEr | Type-based | Yes (proper_statem) | Yes (linearizability) | Yes |
| Elixir | PropCheck | Type-based (PropEr) | Yes (via PropEr) | Yes (via PropEr) | Yes |
| Elixir | StreamData | Integrated | No | No | Yes |
| Haskell | QuickCheck | Type-based | Limited (open-source) | Via packages | Yes |
| Haskell | Hedgehog | Integrated | Yes | Yes | Yes |
| Rust | proptest | Integrated | No | No | Yes |
| Rust | quickcheck | Type-based | No | No | Maintenance mode |
| Rust | bolero | Engine-dependent | No | No | Yes |
| Go | gopter | Type-based | Yes (commands) | No | Low activity |
| Go | rapid | Internal | Yes (StateMachine) | No | Yes |
| Java | jqwik | Integrated | Yes (actions) | No | Yes (active) |
| Java | junit-quickcheck | Type-based | No | No | Low activity |
| Scala | ScalaCheck | Type-based | Yes (Commands) | Yes (parallel) | Yes |
| Scala | ZIO Test | Integrated | Via ZIO effects | Via ZIO effects | Yes |
| C# | FsCheck | Type-based | Limited | No | Yes |
| C# | CsCheck | PCG-based | Yes | Yes (linearizability) | Yes |
| Clojure | test.check | Integrated | No | No | Yes (stable) |
| Swift | SwiftCheck | Type-based | No | No | Maintenance mode |
| F# | FsCheck | Type-based | Limited | No | Yes |
| F# | fsharp-hedgehog | Integrated | No | No | Yes |

### Shrinking Strategy Summary

| Strategy | Frameworks | Pros | Cons |
|----------|-----------|------|------|
| **Type-based** | QuickCheck, PropEr, quickcheck-rs, FsCheck, SwiftCheck | Fast, explicit control | Manual composition, can desync with generators |
| **Integrated** | Hedgehog, fast-check, ScalaCheck, test.check, proptest, jqwik | Automatic composition | Poor with monadic/dependent generators |
| **Internal** | Hypothesis, rapid | Fully automatic, works with monadic bind | Less direct control |
| **PCG-based** | CsCheck | Parallelizable, fast | Newer approach, less proven |

### Parallel/Linearizability Testing Support

Only a handful of frameworks support this advanced feature [S5]:

| Framework | Mechanism |
|-----------|-----------|
| PropEr/PropCheck | `parallel_commands/1` -- generates sequential prefix + parallel branches, checks all linearizations |
| CsCheck | `Check.SampleConcurrent` -- PCG-based parallel shrinking |
| Hedgehog (Haskell) | Parallel state machine commands |
| fast-check | `fc.scheduler()` -- controls promise resolution order (async-specific) |
| ScalaCheck | `Commands` with parallel execution |

Sources: [S5][S36]

---

## 14. Sources

| ID | Source | Type | Reputation |
|----|--------|------|------------|
| S1 | [HypothesisWorks/hypothesis - GitHub](https://github.com/HypothesisWorks/hypothesis) | Repository | High |
| S2 | [Hypothesis Documentation](https://hypothesis.readthedocs.io/) | Official docs | High |
| S3 | [How Hypothesis Works - hypothesis.works](https://hypothesis.works/articles/how-hypothesis-works/) | Official blog | High |
| S4 | [Hypothesis Stateful Testing Docs](https://hypothesis.readthedocs.io/en/latest/stateful.html) | Official docs | High |
| S5 | [Stevana - The Sad State of PBT Libraries (2024)](https://stevana.github.io/the_sad_state_of_property-based_testing_libraries.html) | Analysis | Medium-High |
| S6 | [dubzzz/fast-check - GitHub](https://github.com/dubzzz/fast-check) | Repository | High |
| S7 | [fast-check Documentation](https://fast-check.dev/) | Official docs | High |
| S8 | [Well-Typed: Integrated vs Manual Shrinking](https://www.well-typed.com/blog/2019/05/integrated-shrinking/) | Technical blog | High |
| S9 | [fast-check Model-Based Testing](https://fast-check.dev/docs/advanced/model-based-testing/) | Official docs | High |
| S10 | [propertesting.com - Fred Hebert](https://propertesting.com/) | Book/guide | High |
| S11 | [PropEr API Docs](https://proper-testing.github.io/apidocs/) | Official docs | High |
| S12 | [Claessen et al. - Finding Race Conditions in Erlang (ICFP 2009)](https://dl.acm.org/doi/10.1145/1596550.1596574) | Academic paper | High |
| S13 | [PropCheck - Hex docs](https://hexdocs.pm/propcheck/index.html) | Official docs | High |
| S14 | [whatyouhide/stream_data - GitHub](https://github.com/whatyouhide/stream_data) | Repository | High |
| S15 | [Claessen & Hughes - QuickCheck (ICFP 2000)](https://dl.acm.org/doi/10.1145/351240.351266) | Academic paper | High |
| S16 | [Hughes - Testing the Hard Stuff and Staying Sane](https://www.cs.tufts.edu/~nr/cs257/archive/john-hughes/quviq-testing.pdf) | Academic paper | High |
| S17 | [hedgehogqa/haskell-hedgehog - GitHub](https://github.com/hedgehogqa/haskell-hedgehog) | Repository | High |
| S18 | [Migrating from QuickCheck to Hedgehog](https://frasertweedale.github.io/blog-fp/posts/2020-03-31-quickcheck-hedgehog.html) | Technical blog | Medium-High |
| S19 | [proptest-rs/proptest - GitHub](https://github.com/proptest-rs/proptest) | Repository | High |
| S20 | [Proptest vs QuickCheck](https://proptest-rs.github.io/proptest/proptest/vs-quickcheck.html) | Official docs | High |
| S21 | [BurntSushi/quickcheck - GitHub](https://github.com/BurntSushi/quickcheck) | Repository | High |
| S22 | [camshaft/bolero - GitHub](https://github.com/camshaft/bolero) | Repository | High |
| S23 | [leanovate/gopter - GitHub](https://github.com/leanovate/gopter) | Repository | High |
| S24 | [flyingmutant/rapid - GitHub](https://github.com/flyingmutant/rapid) | Repository | High |
| S25 | [jqwik.net](https://jqwik.net/) | Official docs | High |
| S26 | [Docker Blog - Model-Based Testing with jqwik](https://www.docker.com/blog/model-based-testing-testcontainers-jqwik/) | Technical blog | Medium-High |
| S27 | [pholser/junit-quickcheck - GitHub](https://github.com/pholser/junit-quickcheck) | Repository | High |
| S28 | [scalacheck.org](https://scalacheck.org/) | Official docs | High |
| S29 | [ZIO Test - scala.monster](https://scala.monster/zio-test/) | Technical blog | Medium-High |
| S30 | [FsCheck Documentation](https://fscheck.github.io/FsCheck/) | Official docs | High |
| S31 | [AnthonyLloyd/CsCheck - GitHub](https://github.com/AnthonyLloyd/CsCheck) | Repository | High |
| S32 | [The Happy State of PBT in C# - Anthony Lloyd](http://anthonylloyd.github.io/blog/2024/07/07/cscheck-happy-state) | Technical blog | Medium-High |
| S33 | [Clojure test.check Guide](https://clojure.org/guides/test_check_beginner) | Official docs | High |
| S34 | [typelift/SwiftCheck - GitHub](https://github.com/typelift/SwiftCheck) | Repository | High |
| S35 | [hedgehogqa/fsharp-hedgehog - GitHub](https://github.com/hedgehogqa/fsharp-hedgehog) | Repository | High |
| S36 | [jmid/pbt-frameworks - GitHub](https://github.com/jmid/pbt-frameworks) | Community resource | Medium-High |

---

## 15. Knowledge Gaps

| Gap | What Was Searched | Finding |
|-----|-------------------|---------|
| **GitHub star counts** | Searched GitHub repos for all frameworks | Approximate counts provided from search results; exact current numbers require live API queries. Counts are directionally accurate but may be off by hundreds. |
| **junit-quickcheck current status** | Searched for recent activity | Limited recent information. Appears to be in maintenance mode, largely superseded by jqwik. Confidence: Medium. |
| **bolero stateful testing** | Searched bolero docs and GitHub | No evidence of stateful testing support. Documentation focuses on fuzzing integration. |
| **SwiftCheck successor** | Searched for new Swift Testing PBT library | References to a new "QuickCheck for Swift Testing" exist on Swift forums but no stable release found. |
| **rapid parallel testing** | Searched rapid docs | No evidence of parallel/linearizability testing in rapid. Only sequential state machine testing confirmed. |
| **ScalaCheck parallel testing details** | Searched ScalaCheck docs | `Commands` trait supports parallel execution but documentation is sparse. Confidence: Medium. |
| **ZIO Test stateful testing details** | Searched ZIO Test docs | Stateful testing is possible through ZIO's effect system but no dedicated state machine module like PropEr's `statem`. Confidence: Medium. |
| **Hedgehog.Fsharp stateful testing** | Searched fsharp-hedgehog GitHub | No state machine module found, unlike the Haskell Hedgehog which has one. |
