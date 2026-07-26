---
name: nw-tdd-methodology-paradigm
description: The default test-writing paradigm for unit + acceptance tests - property-based + state-delta mandate, the applicability matrix, the debt-payoff efficacy curve, and the delta-first trigger/bypass rules for state-mutating code
user-invocable: false
disable-model-invocation: true
---

# Test-Writing Paradigm — Property-Based + State-Delta

**Trigger**: writing a unit or acceptance test — deciding the test-writing paradigm (PBT-by-default, state-delta over single-assert) and whether delta-first applies to a state-mutating test.

## Paradigm Mandate — Property-Based + State-Delta (STANDING, 2026-05-05)

**Default test-writing paradigm for UNIT + ACCEPTANCE tests — not optional, not "when applicable".**

### Test-level applicability matrix

| Level | Default paradigm | Rationale |
|---|---|---|
| **Unit** | Property-based + state-delta — single-example is FALLBACK only | Property tests cover equivalence classes; the state-delta universe forbids hidden mutations on adjacent slots |
| **Integration** | UNCHANGED — single-example test verifies WIRING | The contract is "wires connect correctly", not "all input shapes succeed". One representative call suffices |
| **E2E** | UNCHANGED — single-example end-to-end happy path | The contract is "complete flow connects", not "all flows are equivalent". One golden walkthrough suffices |

### Mandate (unit + acceptance levels)

Every unit and acceptance test you write MUST be:

1. **Property-based by default** — use Hypothesis `@given` strategies to explore equivalence classes, NOT single-fixture examples. A property test asserting an invariant over N generated inputs replaces N example tests with stronger semantic coverage.

2. **State-delta over single-property assertion** — capture the FULL observable state surface (universe), declare the expected delta with predicates (`prepended_with`, `set_to`, `unchanged`, `containing`, `idempotent_after`, `legacy_healed`, `normalized_to`, `appended_with`), and call `assert_state_delta(before, after, universe, expected, strict=True)`. `strict=True` forbids hidden mutations on adjacent slots — this is what catches bugs that pinned-fixture asserts miss.

```python
from hypothesis import given, settings, strategies as st
from nwave_ai.state_delta import assert_state_delta, set_to, unchanged

@given(domain_input=domain_specific_strategy())
@settings(max_examples=100, deadline=None)
def test_pbt_invariant(domain_input):
    before = capture_full_state()
    perform_action(domain_input)
    after = capture_full_state()
    assert_state_delta(
        before, after,
        universe={"slot.a", "slot.b", "slot.c", "slot.d"},
        expected={"slot.a": set_to(expected_from(domain_input)), "slot.b": unchanged()},
        strict=True,
    )
```

3. **Acceptance tests express PROPERTIES of the system** — Gherkin scenarios should be framed as `Property: <invariant statement>` with quantified preconditions ("a set of N tasks with arbitrary timestamps") and invariant outcomes ("monotonically descending by timestamp"), instead of single-example `Scenario:` blocks. Step definitions internally use `@given` strategies + state-delta assertions.

**OLD pattern (banned by default)**:
```gherkin
Scenario: Operator sees three tasks ordered by recency
  Given tasks A, B, C with timestamps T1 < T2 < T3
  When the operator runs `prism board`
  Then the board shows: B (T2), C (T3), A (T1) — wait, ordered descending: C, B, A
```

**NEW pattern (required default)**:
```gherkin
Property: Board column order reflects recency
  Given a set of N tasks with arbitrary timestamps
  When the operator runs `prism board`
  Then the column order is monotonically descending by timestamp
  And no task appears twice in the column
  And every input task appears exactly once in the output
```

**Fallback** — when property-framing genuinely cannot express the contract (e.g., flow-specific UI tests with puntual outcomes, golden-file diffs, error messages with exact strings):
- Document WHY property-framing failed in a one-line `# bypass:` comment
- Compensate by adding stronger PBT at unit/integration level

**Forbidden bypass paths** (insufficient justification):
- "Single-property is enough" — NO. Always declare the universe, even if only one slot is checked. `unchanged()` predicate covers the rest.
- "Mock-based interaction test" — NO. Mocks are still observable state; their call-recording surface is part of the universe (`mock.call_count`, `mock.last_call_args`).

**Exempt categories** (still apply paradigm where it adds value, but not mandatory):
- Pure-function tests with single output and no side effects
- Schema/AST validators with single output
- Smoke imports

### Goals

| Goal | Old paradigm | New paradigm |
|---|---|---|
| Number of tests | N example-tests per contract | 1 PBT covers N+ examples |
| Token consumption | High (N test bodies, N test names) | Low (one body, one strategy) |
| Coverage | Pinned by chosen examples | Discovered via Hypothesis shrinking |
| Bug-finding | Limited to imagined cases | Includes edge cases author didn't think of |
| Documentation value | Examples may diverge from spec | Property = invariant = living spec |
| Speed | Slower (more tests to run) | Faster (fewer tests, same coverage) |

### Empirical efficacy framework — debt-payoff curve (NOT instantaneous hit rate)

**Reframing (Ale 2026-05-05)**: paradigm efficacy is measured via the **debt-payoff curve over a surface's lifetime**, not via instantaneous hit rate snapshots.

#### Three stages

| Stage | Surface state | Expected hit rate | Meaning |
|---|---|---|---|
| **Stage 0** | New code, paradigm-from-day-zero | N/A — debt never accumulates | **Healthy by construction**. Tests catch hidden mutations as they emerge |
| **Stage 1** | Bug-prone, debt-accumulated, never-cured | 33–75% (state-delta migration) | **Debt-payoff phase**. High yield = years of single-property-asserts being unmasked |
| **Stage 2a** | Stage-1-completed surface, PBT amplification | ~0% by design | **Maintenance mode**. Debt is paid; PBT now catches in-flight regressions, not retroactive ones |
| **Stage 2b** | Bug-prone, never-migrated, PBT amplification | ~75% (per hardening empirical) | Same as Stage 1 — surface still has accumulated assumptions |

#### Empirical evidence (2026-05-05 pilot, 2 instances)

| Pilot | Stage | Surface | Hit rate | Source |
|---|---|---|---|---|
| Stage 1 state-delta migration | Stage 1 | installer plugin tests, never cured | 4/9 = 44% |
| Stage 2a PBT amplification | Stage 2a | plugin code post Stage 1 | 0/3 = 0% (post commit `29daeb102`) |

**Reading the data correctly**: the master 0% is NOT failure — it's confirmation that Stage 1 already extracted the debt. Stage 2a on a cured surface validates the surface stays healthy. Stage 2b on an uncured surface re-confirms paradigm yield on debt-accumulated code.

#### Implication for AI delegation (the deeper point)

Humans accumulate test debt (single-property-asserts, missed-universe-keys, post-state-only). Machines applying the paradigm **from day zero** (Stage 0) do NOT accumulate debt by construction. Therefore: **AI-written code under paradigm enforcement has lower debt-rate than human-written code**, given equivalent specification quality.

This is why paradigm-as-default for NEW unit tests (the mandate above) matters more than migration: migrations are one-time cleanup; the long-term value is **never accumulating debt to migrate**.

**The paradigm is the environment modification that lets machines build software with lower debt over time** (Ale 2026-05-05).

## Delta-First Test Paradigm (state-mutating code)

**Scope**: ~28% of the test suite (419 test files audited). Applies to installer-class, sync-class, and hook-registration code that mutates user-observable state. NOT universal. Pure-function tests, schema validators, and interaction tests retain standard assertion style.

### Trigger — apply delta-first when ALL of these hold

1. The test mutates user-observable state in **2 or more** distinct slots (e.g. filesystem path + config key + env setting).
2. OR the test implicitly asserts "preserve X" semantics — i.e., the correctness claim is partly about what did NOT change.
3. The code under test is in `scripts/install/`, `scripts/sync/`, or any hook-registration path.

### Bypass — do NOT apply delta-first when

- Pure-function tests with a single return value (no side effects).
- Single-property assertion (`assert result.returncode == 0`).
- `validate_prerequisites()` failure paths (returncode / boolean / exception only).
- Interaction tests (`mock.assert_called_with(...)`) — no universe to declare.
- AST / schema / YAML validators.
- Adding 3-5× ceremony for zero additional detection gain vs. a direct `assert`.

### Pattern

```python
from nwave_ai.state_delta import (
    assert_state_delta,
    prepended_with,
    unchanged,
    set_to,
    containing,
)

def test_des_plugin_installs_hook(tmp_path):
    before = capture_state(tmp_path)   # snapshot before action

    plugin.install(context_for(tmp_path))

    after = capture_state(tmp_path)    # snapshot after action

    assert_state_delta(
        before,
        after,
        universe={
            "hooks.pre_tool_use",      # every slot that COULD change
            "hooks.post_tool_use",
            "config.rigor",
        },
        expected={
            "hooks.pre_tool_use": prepended_with("des_hook.py"),
            "hooks.post_tool_use": unchanged(),
            "config.rigor": set_to("standard"),
        },
        # implicit-unchanged: any universe slot NOT in expected must be identical
    )
```

Full API: `assert_state_delta(before, after, universe, expected, *, strict=False)`.

Available predicate factories: `prepended_with`, `appended_with`, `unchanged`, `set_to`, `containing`, `normalized_to`, `idempotent_after`, `legacy_healed`.

Import: `from nwave_ai.state_delta import assert_state_delta, <predicates>`.

### Empirical justification

Migration of 7 installer test files: **4/7 (57%) exposed previously-untracked mutations** that post-state-property assertions had missed.

Hidden mutations caught:
- `attribution.trailer` written silently (`test_attribution_plugin`) — post-state test only checked `returncode`.
- `content.full` transitioned `None → str` (`test_opencode_des_plugin`) — old assertion never declared `content.full` in universe.

### Reusable helpers that emerged from migration

- `_flatten_config(path)` — flattens a JSON/YAML config into dotted key paths.
- `_skill_filesystem_state(target_dir, track=)` — snapshots skills directory into slot dict.
- `_*_content_state(target_dir, name)` — snapshots a named agent/command content file.

### References

- Source: `nwave_ai/state_delta/matcher.py`
- Canonical migrated example: `tests/installer/unit/plugins/test_attribution_plugin.py`
- D-12 hard gate examples: `tests/state_delta/integration/test_pilot_bug48.py`
