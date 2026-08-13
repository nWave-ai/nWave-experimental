---
name: nw-property-based-testing
description: Property-based testing strategies (PBT — ACTIVE, authored by the acceptance-designer during DISTILL), shrinking, PBT+TDD integration.
user-invocable: false
disable-model-invocation: true
---

# Property-Based Testing (ACTIVE)

> **PBT IS ACTIVE — NOT deprecated.** Property-based testing remains a first-class technique: the
> **acceptance-designer authors PBT during DISTILL** (max PBT + parametrize density is a standing
> mandate). Everything below is CURRENT.

## Property-Based Testing (PBT)

Instead of examples ("given X, expect Y"), write properties ("for all valid inputs, condition Z holds").
Framework generates hundreds/thousands of inputs checking property. Dramatically expands test coverage.

## Property Patterns
1. **Invariants**: "for all inputs, condition holds" (sorted list is ordered, balance >= 0)
2. **Roundtrip**: "encode then decode = original" (serialize/deserialize, compress/decompress)
3. **Oracle**: "compare against reference implementation" (optimized vs correct-but-slow)
4. **Metamorphic**: "different operations, same result" (add(a,b)==add(b,a), filter can't increase size)

## Shrinking

When property fails, framework auto-finds minimal failing input. Dramatically accelerates debugging.
Algorithm: find failing input -> try simpler variants -> if still fails, use as new candidate -> repeat.

## PBT Tools by Language

| Language | Framework |
|----------|-----------|
| Python | Hypothesis |
| JavaScript/TypeScript | fast-check |
| Haskell | QuickCheck |
| Rust | quickcheck |
| Java | jqwik |
| C# | FsCheck |

Adopted by Amazon, Volvo, Stripe, Jane Street (ICSE 2024 study).

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

**Scope of the adapter/infrastructure rows.** These properties exercise
deterministic failure translation and the declared recovery model under a
fault the test itself injects (timeout, malformed response, simulated
partition) — they show the adapter and recovery logic behave correctly given
a fault, not that the property has discovered or predicted a real vendor's
actual behavior. They do not substitute for real-boundary integration tests,
which exercise the actual external system (or its recorded contract) and are
the only class that shows whether the substrate genuinely delivers what it
claims. The "external API integrations" LOW-value entry below refers to
using PBT to probe live vendor behavior — it does not apply to the bounded,
HIGH-value adapter/infrastructure translation and recovery properties above.

## When PBT Adds Value
HIGH value: algorithms | data structures | serialization | business rules (validation, calculations) | protocols/state machines | **unbounded input domain** with universal invariant | deterministic adapter failure-translation and recovery-model properties under a controlled fault model (see Cross-layer properties above).
LOW value: simple CRUD | UI logic | probing live external API/vendor behavior | **closed-world finite domain** (use parametrize instead — see falsifier-gate below).
PBT complements example-based testing, doesn't replace it, and never substitutes for real-boundary integration tests against the actual external system.

### Falsifier-gate: closed-world finite → parametrize, NOT PBT

If the input domain is **finite + enumerable** (N known files, M known event types, K known skill names, fixed Python versions), PBT is the wrong tool:

- `Hypothesis` import (~457ms) + per-example bookkeeping > `@pytest.mark.parametrize` overhead
- Shrinking is irrelevant — the failing input is already a known list member, no minimization needed
- Coverage is bounded by the parameter list, not the example budget — fewer assertions, same coverage

**Decision rule**: enumerate the domain. If listable (`[a, b, c, ...]`), use parametrize-collapse or dict-iteration (see `nw-test-optimization` §3.1, §3.2). Reserve PBT for "for all X in DOMAIN, P(X) holds" where DOMAIN is infinite (all strings, all integers, all valid JSON, all sorted lists).

**Empirical anchor 2026-05-18**: 155-file closed-world skill registry PBT migration was correctly aborted at recon stage by the falsifier-gate. Solution: set-difference parametrize-collapse (commit `c2637f6c8`), 5.42s → 0.71s (8.9× faster). Mass-migrating closed-world tests to PBT would have made the suite **slower**, not faster.

See `nw-test-optimization` §4-bis Paradigm-Match Decision Rule for the full shape-to-paradigm table.

## PBT + TDD Integration
1. Start with example-based TDD for specific cases (drives detailed design)
2. Once basic implementation works, write properties to generalize
3. If property fails: found bug or need refined implementation
4. Refactor freely - properties verify behavior preservation

Properties = higher-level spec that survives refactoring better than examples.

## PBT Performance Guidance
- Fast feedback: ~100 examples | CI/CD: ~1000 examples | Nightly builds: ~10000+ examples

Modern frameworks allow configuring example count per context.

## State-Delta + Hypothesis Integration

Combines the delta-first paradigm (see `nw-tdd-methodology::Delta-First Test Paradigm`) with Hypothesis shrinking to cover production code that branches on input shape.

### `path_strategy()` — composite Hypothesis strategy

Location: `nwave_ai/state_delta/strategies/path_strategy.py`

Generates realistic PATH string shapes covering 4 production branches:
1. Empty string (no PATH set)
2. `$HOME/bin` literal (unexpanded shell variable)
3. Legacy fallback path (`/usr/local/bin` only)
4. Idempotent case (target already present in PATH)

**Lazy-import boundary**: `hypothesis` is NOT imported at `import nwave_ai.state_delta.matcher` time. It is loaded only when `path_strategy()` is called. This is verified by a subprocess-isolated test at `tests/state_delta/unit/test_lazy_import.py` — importing the matcher in a hypothesis-free environment must not raise `ImportError`.

### Integration pattern

```python
from hypothesis import given, settings
from nwave_ai.state_delta.strategies.path_strategy import path_strategy
from nwave_ai.state_delta import assert_state_delta, prepended_with, unchanged

@given(path_strategy())
@settings(max_examples=500)
def test_path_injection_all_shapes(initial_path):
    before = {"env.PATH": initial_path, "env.OTHER": "x"}

    result_path = inject_nwave_bin(initial_path)

    after = {"env.PATH": result_path, "env.OTHER": "x"}

    assert_state_delta(
        before,
        after,
        universe={"env.PATH", "env.OTHER"},
        expected={"env.PATH": prepended_with("/home/user/.nwave/bin"),
                  "env.OTHER": unchanged()},
    )
```

Hypothesis shrinking finds the minimal failing PATH shape automatically when a branch is broken.

### When to use this combination

- Production code has **multiple branches over input shape** (empty vs. populated, legacy vs. current format).
- You want both shrinking (Hypothesis strength) and surrounding-state verification (delta-first strength).
- Single `@given` replaces N parametrized example tests covering the same branches.

### Reference

- D-12 Part B hard gate: `tests/state_delta/integration/test_pilot_bug48.py::test_pilot_bug48_post_fix_validated` — 500 examples, GREEN in 0.88s.
