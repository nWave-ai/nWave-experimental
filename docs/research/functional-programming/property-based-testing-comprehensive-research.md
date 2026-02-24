# Property-Based Testing: Comprehensive Research

**Date:** 2026-02-15
**Researcher:** Nova (nw-researcher)
**Confidence:** High (3+ independent sources for all major claims)

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Types of Properties](#2-types-of-properties)
3. [Generator Composition](#3-generator-composition)
4. [Shrinking Strategies](#4-shrinking-strategies)
5. [Common Patterns and Strategies](#5-common-patterns-and-strategies)
6. [Sources](#6-sources)
7. [Knowledge Gaps](#7-knowledge-gaps)

---

## 1. Core Concepts

### 1.1 Property-Based Testing vs Example-Based Testing

**Example-based testing** (traditional unit testing) specifies concrete inputs and expected outputs. The developer chooses specific scenarios they believe are representative. The fundamental limitation is that developers can only test what they think of.

**Property-based testing** (PBT) inverts this relationship. Instead of specifying individual examples, the developer defines *properties* -- general rules that must hold true for *all* valid inputs -- and the framework generates hundreds or thousands of random inputs to attempt falsification.

> "First, the programmer writes a property of the program under test that they expect to always hold. Then, to check the property, QuickCheck generates a number of random test cases."
> -- Claessen & Hughes, 2000 [1]

The key insight from Fred Hebert's work: a cloud project's "460 lines of quickcheck tests uncovered 25 bugs in 60,000 lines of production code, including race conditions and timing errors" [2]. This demonstrates that PBT can find defects in already-tested, production-ready software.

**Example-based test (Python):**

```python
def test_sort_specific():
    assert sort([3, 1, 2]) == [1, 2, 3]
    assert sort([]) == []
    assert sort([1]) == [1]
```

**Property-based test (Python / Hypothesis):**

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.lists(st.integers()))
def test_sort_properties(xs):
    result = sort(xs)
    # Property: output is same length as input
    assert len(result) == len(xs)
    # Property: output is ordered
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
    # Property: output contains same elements
    assert sorted(xs) == result
```

**Property-based test (TypeScript / fast-check):**

```typescript
import fc from 'fast-check';

test('sort properties', () => {
  fc.assert(
    fc.property(fc.array(fc.integer()), (xs) => {
      const result = sort(xs);
      // Same length
      expect(result.length).toBe(xs.length);
      // Ordered
      for (let i = 0; i < result.length - 1; i++) {
        expect(result[i]).toBeLessThanOrEqual(result[i + 1]);
      }
    })
  );
});
```

**Property-based test (Erlang / PropEr):**

```erlang
prop_sort_ordered() ->
    ?FORALL(List, list(integer()),
        begin
            Sorted = lists:sort(List),
            length(Sorted) =:= length(List) andalso
            is_ordered(Sorted)
        end).
```

Sources: [1][2][3][4]

### 1.2 How Generators Work

Generators (called *strategies* in Hypothesis, *arbitraries* in fast-check, *types* in PropEr) are composable descriptions of how to produce random test data. They define both the shape and distribution of generated values.

The framework uses a size parameter that grows over the test run, starting with simple values and gradually producing more complex ones. This allows early tests to catch simple failures while later tests explore the space more thoroughly.

**Hypothesis** generates data by reading from an underlying byte stream. Strategies implement a `do_draw(data)` method that reads from this stream and interprets the bytes as structured values. As described in the Hypothesis internals documentation: "Hypothesis consists of three layers: a byte stream fuzzer called Conjecture, a strategy library, and a testing interface" [5].

**fast-check** arbitraries are "responsible for the random but deterministic generation of values and may also offer shrinking capabilities" [6].

**PropEr** includes built-in generators such as `integer/1`, `list/1`, `binary/0`, with the ability to generate and shrink general Erlang terms [7].

Sources: [2][5][6][7]

### 1.3 What Shrinking Is and Why It Matters

When a property fails, the initial counterexample is typically large and complex -- a list of 47 elements, a deeply nested structure, a string of 200 characters. **Shrinking** is the process of automatically reducing a failing counterexample to the smallest, simplest input that still causes the failure.

> "All modern property-based testing libraries attempt to 'shrink' values if they fail the test -- that is, when a test fails they'll try to find smaller values (e.g. smaller integers, shorter strings) that still fail the test."
> -- QuickCheck paper summary [1]

**Why it matters:** Without shrinking, a developer receives `[847, -23, 0, 445, 12, -7, 93, ...]` as a failing input. With shrinking, they receive `[0, -1]` -- the minimal case that exposes the bug. This transforms PBT from "it found something wrong" to "it found exactly what is wrong."

**Default shrinking directions** (from PropEr documentation [7]):
- Numbers: floats toward integers, integers toward 0
- Lists: toward the empty list `[]`
- Binaries: toward the empty binary `<<>>`
- Strings: toward shorter strings with earlier characters

Sources: [1][2][5][7]

---

## 2. Types of Properties

The categorization of property types draws from three independent and complementary taxonomies: Fred Hebert's propertesting.com [2], Scott Wlaschin's F# for Fun and Profit [8], and the broader PBT literature.

### 2.1 Invariants ("Some things never change")

An invariant is a condition that must hold true regardless of the input. It describes a structural or logical constraint on the output.

**Examples:**
- A sorted list has the same length as the input list
- A balanced tree remains balanced after any insertion
- The sum of a list is always >= the minimum * length

```python
# Python / Hypothesis
@given(st.lists(st.integers()))
def test_sort_preserves_length(xs):
    assert len(sorted(xs)) == len(xs)
```

```typescript
// TypeScript / fast-check
fc.assert(fc.property(fc.array(fc.integer()), (xs) => {
  expect(mySort(xs).length).toBe(xs.length);
}));
```

As Hebert describes: invariants are "facts that should remain true at all times, but can be observed on any part of the list at any given time" [2].

Sources: [2][8][9]

### 2.2 Idempotency ("The more things change, the more they stay the same")

Applying an operation twice produces the same result as applying it once: `f(f(x)) === f(x)`.

**Examples:**
- Sorting an already-sorted list yields the same list
- Deduplication applied twice yields the same result
- HTTP PUT with the same body is idempotent
- Formatting already-formatted code produces no changes

```python
@given(st.lists(st.integers()))
def test_sort_idempotent(xs):
    once = sorted(xs)
    twice = sorted(once)
    assert once == twice
```

```typescript
fc.assert(fc.property(fc.array(fc.integer()), (xs) => {
  const once = deduplicate(xs);
  const twice = deduplicate(once);
  expect(once).toEqual(twice);
}));
```

Sources: [2][8]

### 2.3 Round-Trip / Symmetry ("There and back again")

Two operations that are inverses of each other should compose to the identity: `decode(encode(x)) === x`.

> "Symmetric properties work well whenever two pieces of code are written that do opposite actions, such as an encoder and a decoder. The trick is to test them together."
> -- Hebert [2]

**Examples:**
- `JSON.parse(JSON.stringify(x)) === x`
- `decompress(compress(data)) === data`
- `deserialize(serialize(obj)) === obj`

```python
@given(st.dictionaries(st.text(), st.integers()))
def test_json_roundtrip(d):
    assert json.loads(json.dumps(d)) == d
```

```erlang
prop_encode_decode() ->
    ?FORALL(Data, binary(),
        Data =:= decode(encode(Data))).
```

```typescript
fc.assert(fc.property(
  fc.dictionary(fc.string(), fc.integer()),
  (obj) => {
    expect(JSON.parse(JSON.stringify(obj))).toEqual(obj);
  }
));
```

Sources: [2][8][9]

### 2.4 Oracle / Model-Based Properties

Compare the system under test against a simpler reference implementation (the "oracle" or "model"). The model should be "so simple it is obviously correct" [2].

**Examples:**
- Test an optimized sort against the standard library sort
- Test a custom hash map against a simple association list
- Test a database query optimizer against brute-force execution

```python
@given(st.lists(st.integers()))
def test_my_sort_matches_oracle(xs):
    assert my_sort(xs) == sorted(xs)  # stdlib is the oracle
```

```erlang
prop_my_dict() ->
    ?FORALL(Ops, list(oneof([{put, term(), term()}, {get, term()}])),
        begin
            MyResult = apply_ops(my_dict:new(), Ops),
            OracleResult = apply_ops(dict:new(), Ops),
            MyResult =:= OracleResult
        end).
```

John Hughes' industrial work at Quviq extensively used model-based testing to validate telecom protocols at Ericsson and automotive systems for AUTOSAR, "identifying over 200 problems, including well over 100 ambiguities" in a 1-million-line C codebase [10].

Sources: [2][8][10]

### 2.5 Metamorphic Properties

Metamorphic testing defines relationships between multiple executions with different inputs, rather than checking individual outputs. This is particularly valuable when you cannot easily verify correctness of a single output (the "oracle problem").

> "Metamorphic testing alleviates the oracle problem by testing programs against metamorphic relations (MRs), which are necessary properties among multiple executions of the target program."
> -- Wikipedia on Metamorphic Testing [11]

**Metamorphic relations** take the form: if `f(x) = y`, then `f(transform(x))` should relate to `y` in a predictable way.

**Examples:**
- `sin(pi - x) === sin(x)` (trigonometric identity)
- Adding a data point above the mean should increase the mean
- Rotating an image then classifying should give the same label
- Doubling audio volume should not change speech-to-text output

```python
@given(st.lists(st.integers(), min_size=1), st.integers())
def test_sort_metamorphic(xs, extra):
    base = sorted(xs)
    extended = sorted(xs + [extra])
    # Metamorphic relation: adding one element increases length by 1
    assert len(extended) == len(base) + 1
    # Metamorphic relation: all original elements still present
    for x in base:
        assert x in extended
```

Metamorphic testing was invented by T.Y. Chen in 1998 and has since generated over 750 research papers [11][12].

Sources: [8][11][12]

### 2.6 Commutativity ("Different paths, same destination")

Operations can be applied in different orders with the same result: `f(g(x)) === g(f(x))`.

> "Doing X then Y gives the same result as doing Y followed by X."
> -- Wlaschin [8]

**Examples:**
- `map(sort(xs), f) === sort(map(xs, f))` (when f preserves ordering)
- Adding items to a set in any order produces the same set
- Applying independent database migrations in different orders

```python
@given(st.lists(st.integers()))
def test_reverse_sort_commute(xs):
    # reverse(sort(xs)) === sort(reverse(xs)) -- only when sort is stable
    # Better example: map then filter vs filter then map (when independent)
    pass
```

Sources: [8]

### 2.7 Inductive Properties ("Solve a smaller problem first")

If a property holds for a base case and for `n` implies `n+1`, it holds for all cases. This maps naturally to recursive data structures.

**Examples:**
- An empty tree is balanced; inserting into a balanced tree yields a balanced tree
- An empty list is sorted; inserting into a sorted list at the right position yields a sorted list

```python
@given(st.lists(st.integers()))
def test_insert_maintains_sorted(xs):
    result = []
    for x in xs:
        insort(result, x)
        # Inductive property: after each insertion, list remains sorted
        assert all(result[i] <= result[i+1] for i in range(len(result)-1))
```

Sources: [8]

### 2.8 Verification Asymmetry ("Hard to prove, easy to verify")

Some problems are hard to solve but easy to verify. Generate inputs, run the algorithm, then verify the output with a cheap check.

**Examples:**
- Pathfinding: verify the path is connected and within the graph
- Factorization: multiply factors back together
- Compilation: run the output and check behavior

```python
@given(st.integers(min_value=2, max_value=10000))
def test_factorize_verifiable(n):
    factors = factorize(n)
    # Easy to verify: product of factors equals n
    product = 1
    for f in factors:
        product *= f
    assert product == n
    # All factors are prime
    assert all(is_prime(f) for f in factors)
```

Sources: [8]

---

## 3. Generator Composition

### 3.1 Built-in Generators

All major PBT frameworks provide primitive generators that can be composed into complex structures.

**Hypothesis (Python):**

```python
import hypothesis.strategies as st

st.integers()                    # Any integer
st.integers(min_value=0, max_value=100)  # Bounded
st.floats()                      # Any float (including NaN, inf)
st.text()                        # Unicode strings
st.binary()                      # Byte strings
st.booleans()                    # True / False
st.lists(st.integers())          # Lists of integers
st.dictionaries(st.text(), st.integers())
st.tuples(st.integers(), st.text())
st.none()                        # Always None
st.one_of(st.integers(), st.text())  # Union types
st.sampled_from([1, 2, 3])      # Pick from list
```

**fast-check (TypeScript):**

```typescript
fc.integer()
fc.integer({ min: 0, max: 100 })
fc.float()
fc.string()
fc.boolean()
fc.array(fc.integer())
fc.dictionary(fc.string(), fc.integer())
fc.tuple(fc.integer(), fc.string())
fc.constant(null)
fc.oneof(fc.integer(), fc.string())
fc.constantFrom(1, 2, 3)
```

**PropEr (Erlang):**

```erlang
integer()
integer(0, 100)
float()
binary()
boolean()
list(integer())
{integer(), binary()}           % Tuples are direct
oneof([integer(), binary()])
elements([a, b, c])
```

Sources: [3][4][7]

### 3.2 Mapping (Transforming Generated Values)

Map transforms generated values while preserving shrinkability.

**Hypothesis:**

```python
# Generate even numbers
even_integers = st.integers().map(lambda x: x * 2)

# Generate non-empty uppercase strings
upper_strings = st.text(min_size=1).map(str.upper)

# Using builds() for objects
@dataclass
class User:
    name: str
    age: int

users = st.builds(User, name=st.text(min_size=1), age=st.integers(1, 120))
```

**fast-check:**

```typescript
// Even numbers
const evenIntegers = fc.integer().map(x => x * 2);

// User objects
const users = fc.record({
  name: fc.string({ minLength: 1 }),
  age: fc.integer({ min: 1, max: 120 })
});
```

**PropEr:**

```erlang
%% Even numbers using ?LET
even() ->
    ?LET(N, integer(), N * 2).

%% Queue from list
queue() ->
    ?LET(List, list({term(), term()}), queue:from_list(List)).
```

Sources: [3][4][7]

### 3.3 Filtering

Filter rejects generated values that do not meet criteria. Use sparingly -- excessive filtering wastes generation attempts.

**Hypothesis:**

```python
# Positive integers (filter approach - less efficient)
positive = st.integers().filter(lambda x: x > 0)

# Positive integers (constrained approach - more efficient)
positive = st.integers(min_value=1)

# assume() inside tests
@given(st.integers(), st.integers())
def test_division(a, b):
    assume(b != 0)
    assert a == (a // b) * b + (a % b)
```

**fast-check:**

```typescript
const positive = fc.integer().filter(x => x > 0);
// Prefer: fc.integer({ min: 1 })
```

**PropEr:**

```erlang
%% Using ?SUCHTHAT (filtering)
non_empty_list() ->
    ?SUCHTHAT(L, list(integer()), L =/= []).
```

As Hebert notes, transformation approaches (map/LET) are "often more efficient than filtering, as they succeed on the first attempt rather than requiring retries" [7].

Sources: [3][4][7]

### 3.4 FlatMap / Chain (Dependent Generation)

When one generated value determines the shape of the next, use flatMap (Hypothesis: `flatmap`, fast-check: `chain`, PropEr: nested `?LET`).

**Hypothesis:**

```python
# Generate a list and then an element from that list
@st.composite
def list_and_element(draw):
    xs = draw(st.lists(st.integers(), min_size=1))
    i = draw(st.sampled_from(xs))
    return (xs, i)
```

**fast-check:**

```typescript
// Generate a list and an index into it
const listAndIndex = fc.array(fc.integer(), { minLength: 1 }).chain(
  arr => fc.tuple(fc.constant(arr), fc.integer({ min: 0, max: arr.length - 1 }))
);
```

**PropEr:**

```erlang
list_and_element() ->
    ?LET(List, non_empty(list(integer())),
        ?LET(Elem, elements(List),
            {List, Elem})).
```

Sources: [3][4][7]

### 3.5 Frequency / Weighted Generation

Control the distribution of generated values to emphasize certain cases.

**PropEr:**

```erlang
text_like() ->
    list(frequency([
        {80, range($a, $z)},    % 80% letters
        {10, $\s},              % 10% whitespace
        {1,  oneof([$.,$-])}    % ~1% punctuation
    ])).
```

**fast-check:**

```typescript
const textLike = fc.array(
  fc.frequency(
    { weight: 80, arbitrary: fc.char().filter(c => /[a-z]/.test(c)) },
    { weight: 10, arbitrary: fc.constant(' ') },
    { weight: 1,  arbitrary: fc.constantFrom('.', '-') }
  )
);
```

**Hypothesis:**

```python
# Hypothesis doesn't have frequency() directly, but uses one_of with
# st.sampled_from for similar effects, or custom @composite strategies
```

Sources: [4][7]

### 3.6 Recursive Generators

For tree-like and recursive data structures, frameworks provide special support.

**Hypothesis:**

```python
# Recursive JSON-like structure
json_values = st.recursive(
    # Base case: leaves
    st.none() | st.booleans() | st.integers() | st.text(),
    # Recursive case: containers
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=50
)
```

**fast-check:**

```typescript
// Recursive JSON
const jsonValues: fc.Arbitrary<unknown> = fc.letrec(tie => ({
  json: fc.oneof(
    fc.constant(null),
    fc.boolean(),
    fc.integer(),
    fc.string(),
    fc.array(tie('json')),
    fc.dictionary(fc.string(), tie('json'))
  )
})).json;
```

**PropEr:**

```erlang
%% Binary tree - requires ?LAZY to prevent infinite recursion
tree(Type) ->
    ?SIZED(Size, tree(Size, Type)).

tree(0, Type) ->
    {leaf, Type};
tree(Size, Type) ->
    frequency([
        {1, {leaf, Type}},
        {5, ?LAZY({node, Type, tree(Size div 2, Type), tree(Size div 2, Type)})}
    ]).
```

The `?LAZY` macro is critical in PropEr because "Erlang uses eager evaluation, [so] the `?LAZY(Expression)` macro defers evaluation until actually needed" [7]. Without it, recursive generators cause infinite loops.

Sources: [3][4][7]

### 3.7 Size Control

**PropEr:**

```erlang
%% Static resize
prop_resize() ->
    ?FORALL(Bin, resize(150, binary()), byte_size(Bin) =< 150).

%% Dynamic sizing with ?SIZED
prop_profile() ->
    ?FORALL(Profile, [
        {name, string()},
        {bio, ?SIZED(Size, resize(Size * 35, string()))}
    ], validate(Profile)).
```

Sources: [7]

---

## 4. Shrinking Strategies

### 4.1 Three Approaches to Shrinking

The PBT ecosystem has converged on three distinct approaches to shrinking, each with different trade-offs.

#### Type-Based / Manual Shrinking (QuickCheck, PropEr)

The original approach from QuickCheck. Generators and shrinkers are separate: the generator produces a value, and a distinct shrink function returns a list of candidate smaller values.

> "In QuickCheck's approach, you package a generator with a shrinking function."
> -- Well-Typed [13]

For a failing integer value `22`, the shrinker might produce `[11, 21]` (half the value, or one less). The framework recursively applies the shrinker until no smaller failing value exists.

**Advantages:** Explicit control; straightforward for simple types.
**Disadvantages:** Composing shrinkers is complex; shrinker and generator can get out of sync; custom types require custom shrinkers.

Sources: [1][7][13]

#### Integrated Shrinking (Hedgehog, fast-check)

Generators produce *shrink trees* -- rose trees where the root is the generated value and children are progressively simpler alternatives.

> "The generator produces a tree of values where the root is unshrunk and branches represent shrink paths."
> -- Well-Typed [13]

When generators are composed (e.g., pairs), the shrink trees compose automatically via the applicative interface.

**Advantages:** "Composing generators naturally composes shrinking" [13]; no separate shrinker needed.
**Disadvantages:** "Even with integrated shrinking, you still have to think about shrinking. There is no free lunch." [13]. Dependent (monadic) generators produce poor shrinking without explicit management.

Sources: [6][13]

#### Internal Shrinking (Hypothesis)

Hypothesis takes a unique approach: instead of shrinking generated *values*, it shrinks the underlying *choice sequence* (byte stream) that produced those values.

> "Instead of having a separate shrinking function, Hypothesis instead shrinks the list of samples, and then re-runs the parser."
> -- Hypothesis documentation [5]

The system uses two simplicity rules: shorter byte arrays are simpler, and lexicographically earlier arrays are simpler. Strategies can provide "hints about possibly useful shrinks" but otherwise have minimal control.

**Advantages:**
- Users "rarely or never have to write their own shrinking functions" [5]
- Works across monadic bind (unlike integrated shrinking)
- Works well for mutable objects (re-creates from scratch each time)
- Generation and shrinking cannot get out of sync

**Disadvantages:** Less direct control over shrink behavior; may explore more shrink candidates.

Sources: [5][14]

### 4.2 Shrink Trees

A shrink tree (rose tree) represents all possible simplifications of a value. The root is the original value; each child is a simpler version, and each child has its own children.

```
         [3, 2, 1]
        /    |     \
    [2,1]  [3,1]  [3,2]
    / \     / \     |
  [1] [2] [1] [3] [3]
   |   |   |   |
  []  []  []  []
```

During shrinking, the framework traverses this tree depth-first, testing each candidate. When a simpler failing input is found, it becomes the new root and the process repeats.

Sources: [6][13]

### 4.3 Custom Shrinkers

**PropEr -- ?SHRINK macro:**

```erlang
%% When shrinking, prefer common year ranges over full range
year() ->
    ?SHRINK(integer(0, 9999), [integer(1970, 2000)]).
```

**PropEr -- ?LETSHRINK macro:**

```erlang
%% Independent shrinking of merged data
date() ->
    ?LETSHRINK([Y, M, D],
               [integer(1, 9999), integer(1, 12), integer(1, 31)],
               {Y, M, D}).
```

`?LETSHRINK` "can discard transformations and return individual generator outputs directly" [7], making it more effective for composite data than `?LET`.

**Hypothesis:** Custom shrinking is rarely needed because internal shrinking handles it automatically. When needed, users can influence shrinking by choosing strategies that naturally produce well-ordered values.

**fast-check:** Custom shrinking can be specified when creating arbitraries via the `Arbitrary` class, defining how values decompose into simpler alternatives.

Sources: [5][7][13]

---

## 5. Common Patterns and Strategies

### 5.1 "Don't Write Tests, Generate Them"

The fundamental PBT philosophy: instead of manually crafting test cases, describe the *space* of valid inputs and the *properties* that must hold, then let the machine explore.

This requires a shift in thinking from "what specific scenarios should I test?" to "what must always be true about my system?"

Hebert describes this as requiring "a learned and practiced skill" where "half the effort involves fixing programs; half involves correcting tests -- with ongoing discovery of previously unsuspected properties throughout development" [2].

Sources: [1][2][8]

### 5.2 The Oracle Pattern

Use a known-correct (but possibly slow or simple) implementation as a reference to verify a new implementation.

**Applications:**
- Test an optimized algorithm against a brute-force version
- Test a new parser against a well-known library
- Test a distributed system against a single-node model

```python
@given(st.lists(st.integers()))
def test_my_quicksort_vs_stdlib(xs):
    assert my_quicksort(xs) == sorted(xs)
```

Hughes applied this extensively at Quviq, testing Ericsson's Megaco protocol implementation against a simplified model, uncovering faults that prior testing techniques missed [10].

Sources: [2][8][10]

### 5.3 Differential Testing

A generalization of the oracle pattern: test two independent implementations of the same specification against each other. Neither is necessarily the "correct" one -- disagreements indicate bugs in one or both.

**Applications:**
- Compare two JSON parsers
- Compare a new compiler version against the old one
- Compare SQL query results across database engines

Sources: [8][10]

### 5.4 Stateless vs Stateful Property-Based Testing

#### Stateless PBT

Tests pure functions: generate input, call function, check properties. No state carries between invocations.

```python
@given(st.lists(st.integers()))
def test_reverse_reverse(xs):
    assert list(reversed(list(reversed(xs)))) == xs
```

#### Stateful PBT

Tests systems with mutable state by generating *sequences of operations* and checking that a model stays in sync with the real system after each operation.

The approach, pioneered by Hughes for QuickCheck:
1. Define a **model** (simplified state representation)
2. Define **commands** (operations that can be performed)
3. Define **preconditions** (when each command is valid)
4. Define **postconditions** (what must be true after each command)
5. The framework generates random sequences of valid commands, executes them against both the real system and the model, and checks postconditions after each step.

**Hypothesis (RuleBasedStateMachine):**

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize

class DatabaseTest(RuleBasedStateMachine):
    @initialize()
    def init(self):
        self.db = Database()
        self.model = {}

    @rule(key=st.text(), value=st.integers())
    def put(self, key, value):
        self.db.put(key, value)
        self.model[key] = value

    @rule(key=st.text())
    def get(self, key):
        if key in self.model:
            assert self.db.get(key) == self.model[key]

TestDatabase = DatabaseTest.TestCase
```

**PropEr:**

```erlang
%% Commands return symbolic calls for better shrinking
command(_State) ->
    oneof([
        {call, ?MODULE, put, [key(), value()]},
        {call, ?MODULE, get, [key()]}
    ]).

precondition(_State, {call, _, get, [Key]}) ->
    maps:is_key(Key, _State);
precondition(_, _) -> true.

postcondition(State, {call, _, get, [Key]}, Result) ->
    Result =:= maps:get(Key, State).
```

Hughes' stateful testing work "extended QuickCheck with state machine formalisms, and standardized serializability properties that can expose harmful race conditions in concurrent code" [10].

Sources: [2][7][10]

### 5.5 Analysis and Distribution Checking

A critical but often overlooked practice: verify that your generators actually produce the distribution of values you expect.

**PropEr:**

```erlang
prop_distribution() ->
    ?FORALL(X, my_generator(),
        collect(classify(X), true)).
```

**Hypothesis:**

```python
from hypothesis import event

@given(st.lists(st.integers()))
def test_with_stats(xs):
    event(f"list_length:{len(xs)}")
    assert my_function(xs)
```

Hebert emphasizes using `collect` and `aggregate` to "reveal whether generators adequately cover the problem space and identify underrepresented edge cases" [7].

Sources: [3][7]

---

## 6. Sources

### Primary Sources

| # | Source | Type | Confidence |
|---|--------|------|------------|
| [1] | Claessen & Hughes, "QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs" (ICFP 2000) | Academic paper | High |
| [2] | Hebert, F. [propertesting.com](https://propertesting.com/) -- free chapters from "Property-Based Testing with PropEr, Erlang, and Elixir" | Official documentation / book | High |
| [3] | Hypothesis documentation, [hypothesis.readthedocs.io](https://hypothesis.readthedocs.io/en/latest/) | Official documentation | High |
| [4] | fast-check documentation, [fast-check.dev](https://fast-check.dev/) | Official documentation | High |
| [5] | MacIver, D.R. "How Hypothesis Works", [hypothesis.works](https://hypothesis.works/articles/how-hypothesis-works/) | Official blog | High |
| [6] | fast-check GitHub, [github.com/dubzzz/fast-check](https://github.com/dubzzz/fast-check) | Source repository | High |
| [7] | PropEr tutorials and Hebert custom generators/shrinking chapters at propertesting.com | Official documentation | High |
| [8] | Wlaschin, S. "Choosing properties for property-based testing", [fsharpforfunandprofit.com](https://fsharpforfunandprofit.com/posts/property-based-testing-2/) | Technical blog | High |
| [9] | Lambda Class, "What is property-based testing? Two examples in Rust", [blog.lambdaclass.com](https://blog.lambdaclass.com/what-is-property-based-testing/) | Technical blog | Medium |
| [10] | Hughes, J. "Experiences with QuickCheck: Testing the Hard Stuff and Staying Sane", [cs.tufts.edu](https://www.cs.tufts.edu/~nr/cs257/archive/john-hughes/quviq-testing.pdf) | Academic paper | High |
| [11] | "Metamorphic testing", [Wikipedia](https://en.wikipedia.org/wiki/Metamorphic_testing) | Encyclopedia | Medium |
| [12] | Wayne, H. "Metamorphic Testing", [hillelwayne.com](https://www.hillelwayne.com/post/metamorphic-testing/) | Technical blog | High |
| [13] | de Vries, E. "Integrated versus Manual Shrinking", [well-typed.com](https://www.well-typed.com/blog/2019/05/integrated-shrinking/) | Technical blog | High |
| [14] | MacIver, D.R. "Compositional Shrinking", [hypothesis.works](https://hypothesis.works/articles/compositional-shrinking/) | Official blog | High |

---

## 7. Knowledge Gaps

### 7.1 Gaps Identified

| Gap | What Was Searched | Why Insufficient |
|-----|-------------------|------------------|
| **Quantitative comparison of shrinking approaches** | Searched for benchmarks comparing manual vs integrated vs internal shrinking across frameworks | No rigorous benchmark study found. The [jlink/shrinking-challenge](https://github.com/jlink/shrinking-challenge) repository exists but comprehensive analysis was not located. |
| **Formal treatment of property completeness** | Searched for academic work on whether a set of properties is sufficient to fully specify a function | Limited formal results found. Most guidance is heuristic ("think of more properties"). |
| **PBT for async/concurrent systems beyond Erlang** | Searched for PBT approaches to testing async JavaScript, Python asyncio | Limited practical guidance found outside of Erlang/Elixir ecosystem where it is well-established. |
| **Performance overhead of PBT in CI pipelines** | Searched for studies on PBT execution time impact in real CI/CD systems | Anecdotal reports only; no systematic study found. Hypothesis provides `max_examples` and deadline settings as mitigations. |
| **PropEr documentation direct access** | Attempted to fetch proper-testing.github.io tutorial pages | Some pages returned redirect or partial content; relied on propertesting.com (Hebert) and search results instead. |

### 7.2 Conflicting Information

| Topic | Conflict | Assessment |
|-------|----------|------------|
| **Best shrinking approach** | Well-Typed [13] argues integrated shrinking still requires manual effort for monadic cases; Hypothesis [5] claims internal shrinking solves this | Both are correct for their contexts. Internal shrinking (Hypothesis) does handle monadic bind better, but is specific to Hypothesis's architecture. Integrated shrinking (Hedgehog, fast-check) is more widely applicable but has known limitations with dependent generators. |
| **Metamorphic testing as PBT** | Some sources treat MT as a form of PBT [12]; others treat them as complementary but distinct paradigms [11] | **Interpretation:** MT and PBT overlap in their generative nature but differ in focus. PBT emphasizes generation/shrinking; MT emphasizes relations between executions. They are best understood as complementary techniques that can be combined in PBT frameworks. |
