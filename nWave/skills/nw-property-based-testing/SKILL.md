---
name: nw-property-based-testing
description: Property-based testing strategies (PBT — ACTIVE, authored by the acceptance-designer during DISTILL), shrinking, PBT+TDD integration.
user-invocable: false
---

# Property-Based Testing (ACTIVE)

> **PBT IS ACTIVE — NOT deprecated.** Property-based testing remains a first-class technique: the
> **acceptance-designer authors PBT during DISTILL** (max PBT + parametrize density is a standing
> mandate). Everything below is CURRENT.

## Property-Based Testing (PBT)

Instead of examples ("given X, expect Y"), write properties ("for all valid inputs, condition Z holds").
Framework samples generated inputs against a stated observation. It is
counterexample search, not universal proof or a substitute for real-boundary
integration evidence.

Evidence is sampled and case-bounded; retain the generator, observation and
falsifier boundary rather than claiming universal proof or causal effect.

## Property Patterns
1. **Invariants**: "for all inputs, condition holds" (sorted list is ordered, balance >= 0)
2. **Roundtrip**: "encode then decode = original" (serialize/deserialize, compress/decompress)
3. **Oracle**: "compare against reference implementation" (optimized vs correct-but-slow)
4. **Metamorphic**: "different operations, same result" (add(a,b)==add(b,a), filter can't increase size)

## Non-vacuous generator construction

Compile the declared law before choosing framework syntax:

```text
SemanticCase -> ConcreteInput -> SUT -> Observation
SemanticCase --------------------------> IndependentOracle
```

The map is total: every generated component must influence `ConcreteInput`,
the SUT invocation, or the independent oracle, directly or through a named
derivation. An unused generated component invalidates the property; delete it
or make its semantic effect observable. The oracle must not copy the
production algorithm it judges.

For a branching or biconditional law, model the alternatives as a closed sum
(`CaseA | CaseB`), generate the case tag first, and derive concrete inputs that
satisfy that case by construction. Hoping random inputs reach a rare branch,
filtering/assuming away a branch, or raising the example count does not prove
reachability. Classification, labels and coverage events are diagnostics only;
they never substitute for constructive reachability.

The observation must distinguish the promised law. Assertions such as
"returns a collection", "has the expected type", or "never raises" are
proxies unless that is the declared law itself. On `RED_TO_GREEN`, run a
property claimed as the RED oracle for a newly promised law against base
behavior: it must fail because the promised observation is missing or wrong.
If it passes, it does not discharge `BROAD_INPUT_DOMAIN`; correct or remove it
before `RedConfirmed`. Keep one property per distinct law, combining laws only
when one generated observation honestly falsifies every combined law.

## Shrinking

When a framework supports shrinking, it may reduce a failing input to a smaller
counterexample; retain the case and inspect generator validity before blaming
the SUT.
Algorithm: find failing input -> try simpler variants -> if still fails, use as new candidate -> repeat.

## Cross-layer properties (ADR-SSOT-002 §6a)

PBT is one projection of the same per-layer observations/laws Section 6a
names — pick the property PATTERN (above) that matches the layer the target's
`boundary`/`contract-shape` says applies; do not author a property for a
layer with no declared law:

| Layer | Property pattern | What it checks |
|---|---|---|
| Domain | Invariant | a stable state/transition law holds for all generated inputs |
| Application/ports | Roundtrip/Oracle | the outcome type is total — every declared success/failure alternative is reachable and handled |
| Adapter/integration | Metamorphic | under a controlled, test-injected fault model, translation maps each simulated fault to its declared failure without losing causal identity |
| Infrastructure/recovery | Invariant | retry/idempotency/timeout/compensation laws hold under repeated or reordered application, against the declared deterministic recovery model |

A layer with no declared failure-mapping or recovery law has no corresponding
property to author for that target — this is a derivation, not an invitation
to invent coverage.

Adapter/recovery properties use injected deterministic faults; they do not
predict a live vendor or replace real-boundary integration evidence.

## When PBT Adds Value
HIGH value: algorithms | data structures | serialization | business rules (validation, calculations) | protocols/state machines | **unbounded input domain** with universal invariant | deterministic adapter failure-translation and recovery-model properties under a controlled fault model (see Cross-layer properties above).
LOW value: simple CRUD | UI logic | probing live external API/vendor behavior | **closed-world finite domain** (use parametrize instead — see falsifier-gate below).
PBT complements example-based testing, doesn't replace it, and never substitutes for real-boundary integration tests against the actual external system.

### Falsifier-gate: closed-world finite → parametrize, NOT PBT

For a finite enumerable domain, use parametrize/dict iteration: shrinking and
example budgets add no coverage. Reserve PBT for a broad domain and a stated
universal law; see `nw-test-optimization` for the paradigm match.

## PBT + TDD Integration

Examples establish specific behaviour; properties generalize a selected law
and preserve it through refactoring. A failure reopens generator, observation
and implementation rather than assigning blame by default.

## State-Delta + Hypothesis Integration

Combines the delta-first paradigm (see `nw-tdd-methodology::Delta-First Test
Paradigm`) with Hypothesis shrinking for production code branching on input
shape.

### `path_strategy()` — composite Hypothesis strategy

Location: `nwave_ai/state_delta/strategies/path_strategy.py`

Generates four production branches:

1. Empty string (no PATH set).
2. `$HOME/bin` literal (unexpanded shell variable).
3. Legacy fallback (`/usr/local/bin` only).
4. Idempotent target-already-present case.

**Lazy-import boundary**: `hypothesis` is NOT imported at
`import nwave_ai.state_delta.matcher` time. It loads only when `path_strategy()`
is called; `tests/state_delta/unit/test_lazy_import.py` verifies a
hypothesis-free matcher import does not raise `ImportError`.

### Integration pattern

```python
from hypothesis import given, settings
from nwave_ai.state_delta.strategies.path_strategy import path_strategy
from nwave_ai.state_delta import assert_state_delta, prepended_with, unchanged

@given(path_strategy())
@settings(max_examples=500)
def test_path_injection_all_shapes(initial_path):
    before = {"env.PATH": initial_path, "env.OTHER": "x"}
    after = {"env.PATH": inject_nwave_bin(initial_path), "env.OTHER": "x"}
    assert_state_delta(
        before, after, universe={"env.PATH", "env.OTHER"},
        expected={"env.PATH": prepended_with("/home/user/.nwave/bin"),
                  "env.OTHER": unchanged()},
    )
```

### When to use this combination

- Production code has multiple branches over input shape.
- Shrinking and surrounding-state verification are both needed.
- One `@given` honestly replaces the matching parametrized cases.

### Reference

`tests/state_delta/integration/test_pilot_bug48.py::test_pilot_bug48_post_fix_validated`
is D-12 Part B hard-gate evidence: 500 examples, GREEN in 0.88s.
