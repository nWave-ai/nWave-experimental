# Stateful Property-Based Testing: Comprehensive Research

**Date**: 2026-02-15
**Researcher**: Nova (nw-researcher)
**Confidence**: High (8+ verified sources across multiple independent authorities)

---

## Table of Contents

1. [Overview and Motivation](#1-overview-and-motivation)
2. [State Machine Testing](#2-state-machine-testing)
3. [Command Generation](#3-command-generation)
4. [Linearizability Testing](#4-linearizability-testing)
5. [Real-World Examples](#5-real-world-examples)
6. [Framework Deep Dives](#6-framework-deep-dives)
7. [Anti-Patterns and Common Mistakes](#7-anti-patterns-and-common-mistakes)
8. [Knowledge Gaps](#8-knowledge-gaps)
9. [Sources](#9-sources)

---

## 1. Overview and Motivation

Stateful property-based testing (PBT) extends traditional PBT from testing pure functions to testing systems with mutable state -- databases, APIs, state machines, protocols, and concurrent systems. Instead of generating individual inputs, stateful PBT generates **sequences of operations** and validates that the system behaves correctly across all reachable states.

**Core insight**: Stateful property tests excel when "what the code should do" (the user-visible behavior) is simple, but "how the code does it" (the implementation) is complex. They function as "a non-formal variation on model checking" [S1, S2, S8].

**The approach**: Define a simplified **model** of the system, generate random sequences of **commands** that operate on both the model and the real system, and assert that the real system's behavior matches the model at every step [S1, S2, S3, S4].

### Why Stateful PBT Matters

Traditional example-based tests cover specific scenarios. Stateful PBT explores the combinatorial space of operation sequences, finding edge cases that developers would never write manually:

- Operations that interact in unexpected ways
- State-dependent bugs that only manifest after specific sequences
- Race conditions in concurrent systems
- Resource leaks from specific allocation/deallocation patterns

---

## 2. State Machine Testing

### 2.1 The Model

The model consists of two parts [S1, S2]:

1. **A data structure** representing the expected system state (simplified, not a copy of the real implementation)
2. **Transition functions** that update the model when commands execute

**Critical principle**: The model is the source of authority that drives test execution, not the system [S1]. The model should be simpler than the system under test -- if implementing a model is as complicated as the target implementation, it may not be worth it [S8].

### 2.2 Commands and Actions

Each command encapsulates:

| Component | Purpose |
|-----------|---------|
| **Precondition** | Can this command execute in the current state? |
| **Execution** | Run the command on the real system |
| **State transition** | Update the model to reflect the command |
| **Postcondition** | Does the real result match the model's expectation? |

### 2.3 Preconditions

Preconditions are "the stateful equivalent to SUCHTHAT macros in stateless properties" [S1]. They prevent invalid operation sequences -- for example, you cannot dequeue from an empty queue or delete a nonexistent key.

Preconditions serve a dual purpose [S1, S2, S5]:
1. **During generation**: Filter out commands that don't make sense in the current model state
2. **During shrinking**: Ensure that minimized failing sequences remain valid

### 2.4 Postconditions

Postconditions verify that the real system's response matches the model's prediction. They run after each command executes against the real system [S1, S2, S5].

### 2.5 State Transitions (next_state)

The `next_state` function updates the model after a command executes. It runs during both the abstract phase (with symbolic values) and the real phase (with concrete values) [S1, S5].

### 2.6 Invariants

Invariants are assertions that must hold after every single step, regardless of which command executed. They validate global consistency properties rather than command-specific outcomes [S3].

### 2.7 Two-Phase Execution Model

PropEr/QuickCheck frameworks divide execution into two phases [S1, S2, S5]:

**Abstract Phase** (generation, no real system code runs):
1. Start from initial model state
2. Generate a candidate command
3. Check precondition against model
4. Apply state transition to model (using symbolic/placeholder values for results)
5. Repeat until sequence is long enough

**Real Phase** (execution against the actual system):
1. Re-evaluate preconditions (for shrinking correctness)
2. Execute command on real system
3. Capture result
4. Validate postcondition
5. Apply state transition (now with real values)
6. Check invariants

---

## 3. Command Generation

### 3.1 Generating Command Sequences

Frameworks generate sequences by repeatedly:
1. Consulting the model's current state
2. Selecting an applicable command (one whose precondition passes)
3. Generating arguments for that command using strategies/generators
4. Applying the state transition to the model
5. Repeating until a target sequence length is reached

### 3.2 Symbolic vs. Concrete References

This is one of the most important and subtle concepts in stateful PBT [S1, S5].

**Problem**: During the abstract/generation phase, the real system isn't running. Commands that return values (like "insert a row and get back its ID") produce results that don't exist yet.

**Solution**: Frameworks use **symbolic variables** as placeholders.

```
# During generation (symbolic):
var1 = insert("Alice")    # var1 is a symbolic reference, not a real ID
update(var1, "Bob")       # var1 is used symbolically

# During execution (concrete):
var1 = insert("Alice")    # var1 = 42 (actual database ID)
update(42, "Bob")         # symbolic var1 replaced with concrete 42
```

**Critical rule**: "Any value coming from the actual system that gets transferred to the model should be treated as an opaque blob that cannot be inspected, matched against, or used in a function call that aims to transform it" [S1]. This is because during generation, these values are just placeholders.

### 3.3 Handling Dependencies Between Commands

Commands often depend on results of previous commands. Three approaches:

**Approach 1: Symbolic references (PropEr/QuickCheck style)**
The framework tracks symbolic variables and resolves them at execution time [S1, S5].

**Approach 2: Bundles (Hypothesis style)**
Bundles are named pools of values. Rules can deposit values into bundles and later rules can draw from them [S3]:

```python
class MyStateMachine(RuleBasedStateMachine):
    keys = Bundle("keys")

    @rule(target=keys, k=st.text())
    def create_key(self, k):
        # Return value goes into the "keys" bundle
        return k

    @rule(k=keys)
    def use_key(self, k):
        # k is drawn from previously created keys
        ...
```

**Approach 3: Model tracking (fast-check style)**
The model itself tracks created resources, and commands reference them via the model [S4]:

```typescript
class CreateUserCommand implements fc.Command<Model, RealSystem> {
  constructor(readonly name: string) {}
  check = (m: Readonly<Model>) => true;
  run(m: Model, r: RealSystem): void {
    const id = r.createUser(this.name);
    m.users.push({ id, name: this.name });
  }
}
```

### 3.4 Weighting Command Selection

Not all commands should be equally likely. Weight functions control transition probabilities to ensure adequate coverage of underexplored states [S2, S8]:

- Without weighting, common operations dominate and rare states are undertested
- PropEr provides a `weight/3` callback for explicit control
- Hypothesis handles this implicitly through its coverage-guided engine

---

## 4. Linearizability Testing

### 4.1 Concept

Linearizability is a correctness condition for concurrent systems: every concurrent execution must be equivalent to some valid sequential execution [S6, S7, S9].

### 4.2 How It Works with PBT

The approach, pioneered by Claessen et al. (2009) [S6]:

1. Define a sequential state machine model (same as for sequential testing)
2. Generate a **sequential prefix** to put the system in a random state
3. Generate **parallel suffixes** -- multiple command sequences to run concurrently
4. Execute the parallel commands simultaneously
5. Check if the observed results are consistent with **any** valid sequential interleaving

If no valid linearization exists, a race condition has been detected.

### 4.3 PropEr/QuickCheck Parallel Testing

PropEr transforms the same sequential state machine into parallel tests [S1, S5]:

```
Sequential prefix:  A -> B
Parallel branch 1:  C -> E -> G
Parallel branch 2:  D -> F
```

The framework checks all possible interleavings of the parallel branches to determine if the observed results could have occurred under sequential execution.

**Usage is minimal** -- swap `commands()` for `parallel_commands()` and `run_commands()` for `run_parallel_commands()` [S1, S5].

**Limitation**: Standard Erlang scheduling may not explore enough interleavings. The PULSE tool adds controlled scheduling with explicit `erlang:yield()` calls for better race detection [S1, S6].

### 4.4 fast-check Scheduler Approach

fast-check takes a different approach using its `scheduler` arbitrary [S4, S10]:

```typescript
fc.assert(
  fc.property(
    fc.scheduler(),
    fc.commands(allCommands),
    async (scheduler, cmds) => {
      const setup = () => ({
        model: initialModel(),
        real: new RealSystem(scheduler),
      });
      await fc.scheduledModelRun(setup, cmds);
    }
  )
);
```

The scheduler wraps promises and controls their resolution order, enabling deterministic exploration of async interleavings [S10].

**Constraint**: Neither `check` nor `run` should rely on the completion of other scheduled tasks [S10].

### 4.5 Hypothesis Limitation

Hypothesis does not currently support parallel/linearizability testing. This is a known gap in the framework [S9].

---

## 5. Real-World Examples

### 5.1 Key-Value Store (Python / Hypothesis)

```python
from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine, Bundle, rule, invariant, precondition, initialize
)
import hypothesis.strategies as st


class KeyValueStoreTest(RuleBasedStateMachine):
    """Test a key-value store against a dict model."""

    def __init__(self):
        super().__init__()
        self.model: dict[str, str] = {}
        self.store = KeyValueStore()  # System under test

    keys = Bundle("keys")

    @initialize()
    def init_store(self):
        self.model = {}
        self.store = KeyValueStore()

    @rule(target=keys, k=st.text(min_size=1, max_size=10))
    def create_key(self, k):
        return k

    @rule(k=keys, v=st.text(max_size=100))
    def put(self, k, v):
        self.store.put(k, v)
        self.model[k] = v

    @rule(k=keys)
    def get_existing(self, k):
        expected = self.model.get(k)
        actual = self.store.get(k)
        assert actual == expected, f"get({k!r}): expected {expected!r}, got {actual!r}"

    @rule(k=keys)
    def delete(self, k):
        self.store.delete(k)
        self.model.pop(k, None)

    @rule(k=st.text(min_size=1, max_size=10))
    def get_missing(self, k):
        if k not in self.model:
            assert self.store.get(k) is None

    @invariant()
    def size_matches(self):
        assert self.store.size() == len(self.model)


# Run as a unittest
TestKeyValueStore = KeyValueStoreTest.TestCase
TestKeyValueStore.settings = settings(max_examples=100, stateful_step_count=50)
```

### 5.2 Queue with Enqueue/Dequeue (TypeScript / fast-check)

```typescript
import fc from "fast-check";
import assert from "node:assert";

// System under test
class Queue<T> {
  private data: T[] = [];
  enqueue(v: T): void { this.data.push(v); }
  dequeue(): T | undefined { return this.data.shift(); }
  size(): number { return this.data.length; }
  peek(): T | undefined { return this.data[0]; }
}

// Model
type QueueModel = { items: number[] };

// Commands
class EnqueueCommand implements fc.Command<QueueModel, Queue<number>> {
  constructor(readonly value: number) {}
  check = (_m: Readonly<QueueModel>) => true; // always valid
  run(m: QueueModel, r: Queue<number>): void {
    r.enqueue(this.value);
    m.items.push(this.value);
  }
  toString = () => `enqueue(${this.value})`;
}

class DequeueCommand implements fc.Command<QueueModel, Queue<number>> {
  check(m: Readonly<QueueModel>): boolean {
    return m.items.length > 0; // only valid when non-empty
  }
  run(m: QueueModel, r: Queue<number>): void {
    const expected = m.items.shift();
    const actual = r.dequeue();
    assert.strictEqual(actual, expected);
  }
  toString = () => "dequeue";
}

class SizeCommand implements fc.Command<QueueModel, Queue<number>> {
  check = (_m: Readonly<QueueModel>) => true;
  run(m: QueueModel, r: Queue<number>): void {
    assert.strictEqual(r.size(), m.items.length);
  }
  toString = () => "size";
}

class PeekCommand implements fc.Command<QueueModel, Queue<number>> {
  check(m: Readonly<QueueModel>): boolean {
    return m.items.length > 0;
  }
  run(m: QueueModel, r: Queue<number>): void {
    assert.strictEqual(r.peek(), m.items[0]);
  }
  toString = () => "peek";
}

// Test
const allCommands = [
  fc.integer().map((v) => new EnqueueCommand(v)),
  fc.constant(new DequeueCommand()),
  fc.constant(new SizeCommand()),
  fc.constant(new PeekCommand()),
];

describe("Queue", () => {
  it("matches model behavior for all command sequences", () => {
    fc.assert(
      fc.property(fc.commands(allCommands, { size: "+1" }), (cmds) => {
        const setup = () => ({
          model: { items: [] } as QueueModel,
          real: new Queue<number>(),
        });
        fc.modelRun(setup, cmds);
      }),
      { numRuns: 1000 }
    );
  });
});
```

### 5.3 REST API with CRUD Operations (Python / Hypothesis)

```python
import requests
from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine, Bundle, rule, initialize, invariant, precondition
)
import hypothesis.strategies as st


class RestApiTest(RuleBasedStateMachine):
    """Test a REST API for a user management service."""

    BASE_URL = "http://localhost:8080/api/users"

    def __init__(self):
        super().__init__()
        self.model: dict[int, dict] = {}  # id -> user data

    user_ids = Bundle("user_ids")

    @initialize()
    def reset_api(self):
        requests.post(f"{self.BASE_URL}/reset")  # test-only endpoint
        self.model = {}

    @rule(
        target=user_ids,
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "Z")
        )),
        email=st.emails(),
    )
    def create_user(self, name, email):
        resp = requests.post(self.BASE_URL, json={"name": name, "email": email})
        assert resp.status_code == 201
        user_id = resp.json()["id"]
        self.model[user_id] = {"name": name, "email": email}
        return user_id

    @rule(user_id=user_ids)
    def read_user(self, user_id):
        resp = requests.get(f"{self.BASE_URL}/{user_id}")
        if user_id in self.model:
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == self.model[user_id]["name"]
            assert data["email"] == self.model[user_id]["email"]
        else:
            assert resp.status_code == 404

    @rule(
        user_id=user_ids,
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "Z")
        )),
    )
    def update_user(self, user_id, name):
        if user_id not in self.model:
            return
        resp = requests.put(
            f"{self.BASE_URL}/{user_id}", json={"name": name}
        )
        assert resp.status_code == 200
        self.model[user_id]["name"] = name

    @rule(user_id=user_ids)
    def delete_user(self, user_id):
        resp = requests.delete(f"{self.BASE_URL}/{user_id}")
        if user_id in self.model:
            assert resp.status_code == 204
            del self.model[user_id]
        else:
            assert resp.status_code == 404

    @invariant()
    def list_count_matches(self):
        resp = requests.get(self.BASE_URL)
        assert resp.status_code == 200
        assert len(resp.json()) == len(self.model)


TestRestApi = RestApiTest.TestCase
TestRestApi.settings = settings(max_examples=50, stateful_step_count=30)
```

### 5.4 Database with Transactions (Python / Hypothesis)

```python
import sqlite3
from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine, Bundle, rule, initialize, invariant, precondition
)
import hypothesis.strategies as st


class TransactionalDatabaseTest(RuleBasedStateMachine):
    """Test transactional semantics: commit persists, rollback reverts."""

    def __init__(self):
        super().__init__()
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.execute("PRAGMA journal_mode=WAL")
        # Model tracks committed state and pending (uncommitted) state
        self.committed: dict[str, str] = {}
        self.pending: dict[str, str] = {}
        self.in_transaction = False

    keys = Bundle("keys")

    @rule(target=keys, k=st.text(min_size=1, max_size=10, alphabet="abcdefgh"))
    def gen_key(self, k):
        return k

    @precondition(lambda self: not self.in_transaction)
    @rule()
    def begin_transaction(self):
        self.conn.execute("BEGIN")
        self.pending = dict(self.committed)
        self.in_transaction = True

    @precondition(lambda self: self.in_transaction)
    @rule(k=keys, v=st.text(max_size=20))
    def insert_or_replace(self, k, v):
        self.conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (k, v)
        )
        self.pending[k] = v

    @precondition(lambda self: self.in_transaction)
    @rule(k=keys)
    def delete_in_txn(self, k):
        self.conn.execute("DELETE FROM kv WHERE key = ?", (k,))
        self.pending.pop(k, None)

    @precondition(lambda self: self.in_transaction)
    @rule()
    def commit(self):
        self.conn.execute("COMMIT")
        self.committed = dict(self.pending)
        self.in_transaction = False

    @precondition(lambda self: self.in_transaction)
    @rule()
    def rollback(self):
        self.conn.execute("ROLLBACK")
        self.pending = {}
        self.in_transaction = False

    @precondition(lambda self: not self.in_transaction)
    @rule(k=keys)
    def read_after_commit(self, k):
        cursor = self.conn.execute("SELECT value FROM kv WHERE key = ?", (k,))
        row = cursor.fetchone()
        expected = self.committed.get(k)
        if expected is None:
            assert row is None, f"Key {k!r} should not exist but got {row}"
        else:
            assert row is not None, f"Key {k!r} should exist with value {expected!r}"
            assert row[0] == expected

    @invariant()
    def committed_state_consistent(self):
        if not self.in_transaction:
            cursor = self.conn.execute("SELECT COUNT(*) FROM kv")
            assert cursor.fetchone()[0] == len(self.committed)

    def teardown(self):
        self.conn.close()


TestTransactionalDB = TransactionalDatabaseTest.TestCase
TestTransactionalDB.settings = settings(max_examples=100, stateful_step_count=40)
```

### 5.5 John Hughes' War Stories

Hughes' "Testing the Hard Stuff and Staying Sane" (2014/2016) describes several landmark case studies [S7]:

- **Bounded FIFO queue in C**: A simple stateful model (a list) found bugs in a circular buffer implementation that hand-written tests missed
- **AUTOSAR automotive software (Volvo Cars)**: The largest QuickCheck project at that time, using stateful PBT for acceptance testing of C code for automotive control units
- **Klarna database (dets)**: Parallel stateful testing found a notorious race condition in Erlang's built-in disk-based term storage that had plagued Klarna for years. The bug only manifested under specific concurrent access patterns

---

## 6. Framework Deep Dives

### 6.1 PropEr/PropCheck statem

**Language**: Erlang / Elixir
**Module**: `proper_statem` [S5]

The statem module requires five callbacks:

| Callback | Signature | Purpose |
|----------|-----------|---------|
| `initial_state/0` | `-> symbolic_state()` | Starting model state |
| `command/1` | `(state) -> type()` | Generate a command given current state |
| `precondition/2` | `(state, call) -> boolean()` | Is this command valid now? |
| `postcondition/3` | `(state, call, result) -> boolean()` | Did the result match expectations? |
| `next_state/3` | `(state, call, result) -> state()` | Update model after command |

**Symbolic vs. Dynamic state**: During generation, `next_state` receives symbolic variables like `{var, 2}`. During execution, these become real values like `42` [S5].

**Parallel testing**: Replace `commands/1` with `parallel_commands/1` and `run_commands/2` with `run_parallel_commands/2`. The framework generates a sequential prefix followed by parallel branches and checks linearizability [S1, S5].

### 6.2 Hypothesis RuleBasedStateMachine

**Language**: Python
**Class**: `hypothesis.stateful.RuleBasedStateMachine` [S3]

Key API elements:

```python
from hypothesis.stateful import (
    RuleBasedStateMachine,
    Bundle,          # Named pool of values for cross-rule data flow
    rule,            # Decorator: defines a testable action
    initialize,      # Decorator: runs once before all rules
    invariant,       # Decorator: checked after every step
    precondition,    # Decorator: guards a rule based on state
    consumes,        # Strategy wrapper: removes value from bundle after use
)
```

**Bundles** are the key differentiator. Unlike PropEr's symbolic references, bundles are named collections that rules populate and consume [S3]:

```python
keys = Bundle("keys")

@rule(target=keys, k=st.text())  # deposits into "keys" bundle
def create(self, k): return k

@rule(k=keys)                     # draws from "keys" bundle
def use(self, k): ...

@rule(k=consumes(keys))           # draws AND removes from bundle
def destroy(self, k): ...
```

**Configuration**:
- `max_examples`: Number of state machine runs
- `stateful_step_count`: Maximum steps per run (default 50)

**Limitation**: No parallel/linearizability testing support [S9].

### 6.3 fast-check Model-Based Testing

**Language**: TypeScript / JavaScript
**API**: `fc.commands`, `fc.modelRun`, `fc.asyncModelRun`, `fc.scheduledModelRun` [S4]

Commands implement the `fc.Command<Model, Real>` interface:

```typescript
interface Command<Model, Real> {
  check(m: Readonly<Model>): boolean;       // precondition
  run(m: Model, r: Real): void | Promise<void>;  // execute + assert
  toString(): string;                        // for error reporting
}
```

**Key design decisions**:
- Model and real system are separate parameters to `run()`
- `check()` receives a readonly model (precondition cannot mutate state)
- Model mutations happen inside `run()` alongside real system operations
- The `commands` arbitrary handles shrinking efficiently [S4]

**Race condition testing** via `scheduledModelRun`:

```typescript
fc.assert(
  fc.property(fc.scheduler(), fc.commands(allCmds), async (s, cmds) => {
    const setup = () => ({ model: initModel(), real: new System(s) });
    await fc.scheduledModelRun(setup, cmds);
  })
);
```

**Replay**: On failure, fast-check provides `seed` and `replayPath` to reproduce exact failing scenarios [S4].

### 6.4 Framework Comparison

| Feature | PropEr/QuickCheck | Hypothesis | fast-check |
|---------|-------------------|------------|------------|
| Language | Erlang/Elixir | Python | TypeScript/JS |
| Symbolic references | Yes (first-class) | Via Bundles | Via model tracking |
| Preconditions | Callback | Decorator | `check()` method |
| Postconditions | Callback | Assertions in rules | Assertions in `run()` |
| Invariants | Via postcondition | `@invariant()` decorator | Manual in commands |
| Parallel testing | Yes (linearizability) | No | Via scheduler |
| Shrinking | Integrated | Integrated | Integrated |
| State machine FSM | `proper_fsm` module | No | No |
| Maturity | 15+ years | 10+ years | 8+ years |

---

## 7. Anti-Patterns and Common Mistakes

### 7.1 Model Too Complex

**Anti-pattern**: Making the model as complex as the system under test.

**Why it's wrong**: If the model reimplements the system, you're testing code against itself. Bugs in the model mirror bugs in the system [S8].

**Fix**: The model should capture the *what* (expected behavior) in the simplest possible way. A key-value store model is just a dictionary. A queue model is just a list.

### 7.2 Insufficient Action Coverage

**Anti-pattern**: Not monitoring which commands actually execute during test runs [S8].

**Why it's wrong**: Without statistics, tests may "pass" while never exercising critical scenarios. If your delete command has a precondition requiring existing keys, but create commands are rare, deletions may barely execute.

**Fix**: Collect and review action distribution statistics. In Hypothesis, use `@settings(stateful_step_count=N)` and monitor logs. In fast-check, check the verbose output. Weight commands to ensure critical paths are covered.

### 7.3 Weak Preconditions

**Anti-pattern**: Missing preconditions that allow invalid commands, causing spurious failures [S8].

**Example**: A "transfer funds" command without a precondition checking sufficient balance produces failures that are valid rejections, not bugs.

**Fix**: Preconditions should precisely capture the system's documented contract. Invalid inputs should be tested separately with dedicated properties.

### 7.4 State Explosion

**Anti-pattern**: Adding too many state variables or commands without considering the combinatorial explosion [S8, S11].

**Why it's wrong**: With N boolean state variables, you have 2^N possible states. Adding more variables multiplies the state space quadratically in terms of edges (transitions) [S11].

**Fix**:
- Start with a minimal model and add complexity incrementally
- Use preconditions to prune unreachable states
- Focus on the most important state dimensions first
- Increase `stateful_step_count` / sequence length to explore deeper states

### 7.5 Side Effects in Model Code

**Anti-pattern**: Performing side effects (I/O, mutations of external state) in preconditions or state transition functions [S1].

**Why it's wrong**: These functions execute during both generation and execution phases. Side effects during generation corrupt the test setup.

**Fix**: Model code must be pure. Only the command execution step should interact with the real system.

### 7.6 Inspecting Opaque Values During Generation

**Anti-pattern**: Pattern-matching or transforming symbolic/placeholder values in the model during the abstract phase [S1].

**Why it's wrong**: During generation, return values are symbolic placeholders (not real data). Inspecting them fails or produces nonsense.

**Fix**: Treat all values from the real system as opaque in model code. Store them, pass them around, but never inspect their contents in `next_state`.

### 7.7 Not Shrinking-Aware

**Anti-pattern**: Writing commands that work during generation but break during shrinking because preconditions are incomplete.

**Why it's wrong**: During shrinking, the framework removes commands from the sequence. If a later command depends on an earlier one (e.g., using a created resource), removing the creation without a precondition check produces invalid sequences.

**Fix**: Every command that uses a resource must have a precondition verifying that resource exists in the model. The model, not the system, is the authority during shrinking [S1, S5].

### 7.8 Testing Implementation Details Instead of Behavior

**Anti-pattern**: Making the model track internal implementation details (e.g., internal tree structure of a balanced BST).

**Fix**: Model the *observable behavior* -- the interface contract. For a sorted set, the model is a sorted list. You don't need to model red-black tree rotations.

---

## 8. Knowledge Gaps

### 8.1 Documented Gaps

| Gap | What Was Searched | Finding |
|-----|-------------------|---------|
| Andrea Leopardi ElixirConf talks | Searched for "Andrea Leopardi ElixirConf stateful testing property-based" | Could not find freely accessible transcripts or detailed summaries of the specific talk content. Conference talks exist but detailed technical content is behind video paywalls. |
| Hypothesis parallel testing | Searched Hypothesis docs and GitHub | Confirmed: Hypothesis does **not** support parallel/linearizability testing as of 2026. No roadmap items found. |
| fast-check scheduledModelRun examples | Searched fast-check docs for detailed examples | The official documentation provides the API but **no complete code examples** of scheduledModelRun with model-based testing. Only the constraint about not depending on other scheduled tasks is documented. |
| Comparative benchmarks | Searched for "stateful PBT framework benchmark comparison" | No systematic benchmarks comparing bug-finding effectiveness across frameworks exist in the public literature. |

### 8.2 Landscape Gap

As documented by Stevana (2024), most PBT libraries do not implement state-of-the-art stateful testing features. Parallel testing via linearizability checking is "almost entirely absent from open-source implementations" -- only PropEr, CsCheck, Hedgehog, and quickcheck-state-machine support it, and even these have documented issues [S9]. The closed-source Quviq QuickCheck remains the most complete implementation, creating a gap between academic capabilities and open-source availability.

---

## 9. Sources

| ID | Source | Type | Used For |
|----|--------|------|----------|
| S1 | [propertesting.com - Stateful Properties](https://propertesting.com/book_stateful_properties.html) | Guide | Model concept, two-phase execution, symbolic values, preconditions |
| S2 | [propertesting.com - State Machine Properties](https://propertesting.com/book_state_machine_properties.html) | Guide | FSM-specific testing, weight functions, circuit breaker example |
| S3 | [Hypothesis - Stateful Testing Docs](https://hypothesis.readthedocs.io/en/latest/stateful.html) | Official docs | RuleBasedStateMachine API, bundles, initialize, invariants |
| S4 | [fast-check - Model Based Testing](https://fast-check.dev/docs/advanced/model-based-testing/) | Official docs | ICommand interface, modelRun, commands arbitrary |
| S5 | [PropEr - proper_statem API](https://proper-testing.github.io/apidocs/proper_statem.html) | Official docs | Callback API, symbolic/dynamic state, parallel_commands |
| S6 | [Claessen et al. - Finding Race Conditions in Erlang with QuickCheck and PULSE (ICFP 2009)](https://dl.acm.org/doi/10.1145/1596550.1596574) | Academic paper | PULSE tool, linearizability checking, race condition methodology |
| S7 | [Hughes - Experiences with QuickCheck: Testing the Hard Stuff and Staying Sane (2016)](https://link.springer.com/chapter/10.1007/978-3-319-30936-1_9) | Academic paper / talk | War stories: Volvo, Klarna, FIFO queue |
| S8 | [Johannes Link - Model-Based Testing](https://johanneslink.net/model-based-testing/) | Blog / guide | Anti-patterns, action coverage, model design best practices |
| S9 | [Stevana - The Sad State of Property-Based Testing Libraries (2024)](https://stevana.github.io/the_sad_state_of_property-based_testing_libraries.html) | Analysis | Framework landscape gaps, missing parallel testing, library comparison |
| S10 | [fast-check - Race Conditions](https://fast-check.dev/docs/advanced/race-conditions/) | Official docs | scheduledModelRun, scheduler arbitrary |
| S11 | [Concerning Quality - State Space Explosion](https://concerningquality.com/state-explosion/) | Blog | State space explosion problem in testing |

### Source Independence Verification

- S1/S2 (propertesting.com) and S5 (PropEr docs) cover the same framework but are written by different authors for different purposes (tutorial vs. API reference)
- S3 (Hypothesis), S4/S10 (fast-check), S5 (PropEr) are independent frameworks with independent documentation teams
- S6 and S7 share co-author (John Hughes) but are different papers addressing different aspects (PULSE/race detection vs. industrial experience)
- S8 (Johannes Link) and S9 (Stevana) are independent authors analyzing the field from different perspectives
