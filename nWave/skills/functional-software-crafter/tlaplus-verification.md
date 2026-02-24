# TLA+ / Formal Verification

When and how to use TLA+ for design verification. Complements PBT (which verifies implementation).

## Decision Tree: When to Use TLA+ vs PBT vs Both

```
Is the risk in the DESIGN or the IMPLEMENTATION?
  |
  +-- Design risk (protocol correctness, distributed coordination, concurrency)
  |     -> Does the system involve concurrent or distributed state?
  |       Yes -> Use TLA+ for design verification
  |              Then use PBT to verify implementation matches design
  |       No  -> PBT alone is likely sufficient
  |
  +-- Implementation risk (edge cases, serialization, data transforms)
  |     -> Use PBT alone
  |
  +-- Both
        -> TLA+ validates design, PBT validates implementation
```

### Use TLA+ When:

- A design bug would cause data loss or significant customer impact
- The system involves concurrent or distributed state manipulation
- Subtle interactions between components are hard to reason about informally
- Informal reasoning or testing has already failed to prevent bugs

### Skip TLA+ When:

- Simple CRUD with straightforward business logic
- UI/UX behavior
- Performance optimization (TLA+ models correctness, not performance)
- Design is well-understood; risk is only in implementation bugs
- Rapid prototyping where design changes frequently

## TLA+ in 60 Seconds

TLA+ describes **what** a system should do, not how to implement it. A specification consists of:

- **Variables**: State components
- **Init**: Valid starting states
- **Next**: How the system transitions between states
- **Invariants**: Conditions that must hold in every reachable state

The TLC model checker exhaustively explores all reachable states within a bounded model. If an invariant is violated, TLC provides a counterexample trace -- the shortest path from initial state to the violation.

## PlusCal as Entry Point

PlusCal is an imperative-looking language that transpiles to TLA+. Most programmers find it easier to learn first.

```
(* --algorithm Transfer
variables accounts = [a |-> 100, b |-> 100];

process Transfer \in 1..2
variables from, to, amount;
begin
  Pick:
    from := "a"; to := "b"; amount := 50;
  Check:
    if accounts[from] >= amount then
      Debit:
        accounts[from] := accounts[from] - amount;
      Credit:
        accounts[to] := accounts[to] + amount;
    end if;
end process;
end algorithm; *)

\* Invariant: total money is conserved
MoneyConserved == accounts["a"] + accounts["b"] = 200
```

**Labels** define atomicity boundaries. Everything between two labels executes atomically. Concurrency interleavings happen at label boundaries.

PlusCal limitation: cannot express all TLA+ patterns (complex fairness, some non-determinism forms). Start with PlusCal, switch to raw TLA+ when needed.

## TLC Model Checker Workflow

1. Write spec in PlusCal or TLA+
2. Configure model: concrete values for constants, invariants to check
3. Run TLC: exhaustive breadth-first exploration of all reachable states
4. If violation found: TLC provides counterexample trace (shortest path to violation)
5. Fix design, re-check
6. Gradually increase model parameters (more nodes, more messages)

### Model Configuration (.cfg file)

```
SPECIFICATION Spec
CONSTANT
  Nodes = {n1, n2, n3}
  MaxMessages = 4
INVARIANT
  MoneyConserved
  NoDoubleDelivery
```

### Managing State Space Explosion

State space grows as O(constants^variables). 3 nodes = ~1,000 states; 4 nodes = ~100,000 states. Most bugs manifest with 2-3 nodes.

Mitigation strategies:
- Start with 2-3 nodes, low bounds (most bugs manifest with small configs)
- Use symmetry reduction for interchangeable elements
- Use state constraints to limit exploration
- Use simulation mode (`-simulate`) for large models (random sampling instead of exhaustive)

## Common Modeling Patterns

### Message Passing
Network as a set of in-flight messages. Send adds to set, receive removes. Unreliable network: messages can be removed without receipt (loss) or kept after receipt (duplication).

### Shared Memory
Variables represent memory locations. Locks modeled as variables indicating the holding process.

### Failures
Node crash: non-deterministic removal from active set. Volatile state lost, persistent state retained. Restart: rejoin active set with fresh volatile state.

### Leader Election
Nodes propose, vote, and become leader when majority achieved. Safety invariant: at most one leader per term.

### Transactions
Two-phase commit: resource managers prepare, transaction manager commits when all prepared. Safety: no partial commits.

## Safety and Liveness

**Safety** ("nothing bad happens"): Expressed as invariants. Violated by a finite counterexample trace. Example: "Two processes never hold the same lock."

**Liveness** ("something good eventually happens"): Requires fairness assumptions. Cannot be violated by a finite prefix. Example: "Every request eventually gets a response."

Start with safety properties. Add liveness after safety is established.

## The TLA+ to PBT Pipeline

This is the key integration point between formal verification and testing:

1. **TLA+ specification phase**: Identify invariants, safety properties, state machine transitions
2. **Model check with TLC**: Verify design correctness
3. **Implementation phase**: Code the verified design
4. **PBT phase**: Translate TLA+ invariants into PBT properties

The properties discovered during TLA+ specification become PBT test oracles:
- TLA+ invariant "total money conserved" becomes `assert sum(all_accounts) == initial_total`
- TLA+ safety property "no double-delivery" becomes a stateful PBT postcondition
- TLA+ state machine transitions map to stateful PBT commands

TLA+ invariants are exhaustive. PBT properties sample. If TLA+ proves A and B and C, your PBT must check all three -- checking only A creates false confidence.

### What Each Catches

| TLA+ Catches (Design) | PBT Catches (Implementation) |
|----------------------|----------------------------|
| Protocol deadlocks | Off-by-one errors |
| Consistency violations under failure | Incorrect serialization |
| Missing error handling paths | Memory management issues |
| Race conditions in algorithms | Edge cases in data transforms |

Neither catches: performance bugs, usability issues, integration with external systems.

## Tooling

- **VS Code extension** (`alygin.vscode-tlaplus`): Primary IDE. Syntax highlighting, model checking, counterexample visualization. Requires Java 11+.
- **TLA+ Toolbox**: Original Eclipse-based IDE. Still functional but VS Code is now preferred.
- **Command-line TLC**: `java -jar tla2tools.jar -config Spec.cfg Spec.tla`
- **Apalache**: Symbolic model checker using SMT (Z3). Use Apalache when TLC hits state explosion (>10M states). Most designs use TLC.
- **Community Modules**: Reusable TLA+ modules (FinSets, Sequences, Bags, Json, TLCExt).

## Real-World Adoption

- **AWS**: DynamoDB, S3, EBS -- found subtle bugs in every system, including potential data loss. Engineers learned TLA+ in 2-3 weeks.
- **Azure Cosmos DB**: All five consistency levels formally specified. Specs open-sourced.
- **Elasticsearch**: Replication, cluster coordination, shard allocation. Models open-sourced.
- **MongoDB, CockroachDB, Kafka**: Protocol verification.

## Iterative Development Approach

1. Start with 2 processes, 1 message type
2. Add failure modes (crash, restart, message loss)
3. Add more processes (verify N-participant scaling)
4. Add liveness properties (verify progress under fairness)
5. Add optimizations (verify optimized paths maintain correctness)
