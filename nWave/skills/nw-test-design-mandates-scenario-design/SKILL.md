---
name: nw-test-design-mandates-scenario-design
description: "Scenario-design mandates for acceptance tests — Hexagonal Boundary Enforcement (drive through driving ports, never internals), Business Language Abstraction (three abstraction layers), User Journey Completeness, Pure Function Extraction Before Fixtures, Algebraic Analysis Before the Scenario (name the law, find its narrowest surface, declare every gated input, prove the scenario can fail), the 3 Pillars style backbone, and Walking Skeleton Strategy. Consult while shaping or judging a scenario's boundary, language, journey completeness, and fixture strategy. Canonical definitions; SSOT for these mandates."
user-invocable: false
disable-model-invocation: true
---

# Test-Design Mandates — Scenario Design

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are shaping or judging a scenario's SHAPE — what to drive (boundary), what language to use, whether it is a complete user journey, and whether fixtures are parametrized correctly. Mandates 1-4 + the 3 Pillars + Walking Skeleton Strategy.

Numbering is an SSOT-internal index defined in the recomposing core `nw-test-design-mandates`; refer to mandates by descriptive name externally. Language-convention frame (non-Python target adaptation) lives in the core — read it before applying any code example below.

## Mandate 1: Hexagonal Boundary Enforcement

Tests invoke through driving ports (entry points), never internal components.

### Driving Ports (Test Through These)
Application services/orchestrators | API controllers/CLI handlers | Message consumers/event handlers | Public API facade classes

### Not Entry Points (Never Test Directly)
Internal validators, parsers, formatters | Domain entities/value objects | Repository implementations | Internal service components

### Correct Pattern

```python
# Invoke through system entry point (driving port)
from myapp.orchestrator import AppOrchestrator

def when_user_performs_action(self):
    orchestrator = AppOrchestrator()
    self.result = orchestrator.perform_action(
        context=self.context
    )
```

### Violation Pattern

```python
# Invoking internal component directly
from myapp.validator import InputValidator  # INTERNAL

def when_user_validates_input(self):
    validator = InputValidator()  # WRONG BOUNDARY
    self.result = validator.validate(self.input)
```

Testing internal components creates Testing Theater: tests pass but users cannot access feature through actual entry point. Integration wiring bugs remain hidden.

## Mandate 2: Business Language Abstraction

Step methods speak business language, abstract all technical details.

### Three Abstraction Layers

**Layer 1 - Gherkin**: Pure business language, all stakeholders. Domain terms from ubiquitous language | Zero technical jargon | Describe WHAT user does, not HOW system does it

```gherkin
Scenario: Customer places order for available product
  Given customer has items in shopping cart
  When customer submits order
  Then order is confirmed
  And customer receives confirmation email
```

**Layer 2 - Step Methods**: Business service delegation. Method names use domain terms | Delegate to business service layer (OrderService, not HTTP client) | Assert business outcomes (order.is_confirmed()), not technical state (status_code == 201)

```python
def when_customer_submits_order(self):
    self.result = self.order_service.place_order(
        customer=self.customer, items=self.cart_items
    )

def then_order_is_confirmed(self):
    assert self.result.is_confirmed()
    assert self.result.has_order_number()
```

**Layer 3 - Business Services**: Production services handle technical implementation. HTTP calls, DB transactions, SMTP hidden inside service layer.

### Test Smell Indicators
`requests.post()` in step method | `db.execute()` in step method | `assert response.status_code` | Technical terms in Gherkin

## Mandate 3: User Journey Completeness

Tests validate complete user journeys with business value, not isolated technical operations.

### Complete Journey Structure
Every scenario includes: **User trigger** (Given/When) | **Business logic** (When - system processes rules) | **Observable outcome** (Then - user sees result) | **Business value** (Then - value delivered)

### Correct Example

```gherkin
Scenario: Customer successfully completes purchase
  Given customer has selected products worth $150
  And customer has valid payment method
  When customer submits order
  Then order is confirmed with order number
  And customer receives email confirmation
  And order appears in customer's order history
```

### Violation Example

```gherkin
Scenario: Order validator accepts valid order data
  Given valid order JSON exists
  When validator.validate() is called
  Then validation passes
# Tests isolated validation, not user journey
```

### Scenario Name Test
Does name express user value or technical operation? "Customer completes purchase" = correct. "Validator accepts JSON" = violation.

## Walking Skeleton Strategy

Balance user-centric E2E integration tests with focused boundary tests.

### Walking Skeletons (2-5 per feature)
Trace thin vertical slice delivering observable user value E2E | Each answers: "Can a user accomplish this goal and see the result?" | Express simplest complete user journey | Validate system delivers demo-able stakeholder value | Touch all layers as consequence of journey, not as design goal

### Walking Skeleton Litmus Test
1. Title describes user goal ("Customer purchases a product") not technical flow ("Order passes through all layers")
2. Given/When describe user actions/context, not system state setup
3. Then describe user observations (confirmation, email, receipt), not internal side effects (DB row, message queued)
4. Non-technical stakeholder can confirm "yes, that is what users need"

### Focused Scenarios (15-20 per feature, majority)
Test specific business rules at driving port boundary | Test doubles for external dependencies (faster, isolated) | Cover business rule variations and edge cases | Invoke through entry point (OrderService, Orchestrator)

### Recommended Ratio
For typical feature with 20 scenarios: 2-3 walking skeletons (user value E2E) | 17-18 focused scenarios (boundary tests with test doubles). Walking skeletons prove users achieve goals. Focused scenarios run fast, cover breadth. Both use business language and invoke through entry points.

## Mandate 4: Pure Function Extraction Before Fixtures

BEFORE parametrizing any test fixture with environment variants:

1. Identify ALL business logic in the code under test
2. Extract every piece of business logic into a pure function:
   - Pure function: takes inputs, returns outputs, no side effects
   - Impure code: subprocess calls, file I/O, network, environment variables
3. Test pure functions directly — no fixtures, no mocks, no environment setup needed
4. Test impure code (subprocess, file I/O) through adapter interfaces:
   - Define a port (interface) for each impure operation
   - Create a test adapter (in-memory, fake) for each port
   - Acceptance tests use real adapters; unit tests use fakes
5. Parametrize fixtures ONLY for the thin adapter layer that connects to real environments

**Rationale**: Parametrizing fixtures across environments is expensive. Pure functions need zero environment setup. Extract first, parametrize the minimum.

### Violation Pattern

```python
# WRONG: parametrizing entire test across environments
@pytest.fixture(params=["clean", "with-pre-commit", "with-stale-config"])
def environment(request):
    return setup_environment(request.param)

def test_install_detects_conflicts(environment):
    result = full_install_pipeline(environment)  # Impure: touches filesystem
    assert result.conflicts == []
```

### Correct Pattern

```python
# Step 1: Extract pure logic
def detect_conflicts(config: Config, existing: list[str]) -> list[Conflict]:
    """Pure function — no I/O, no environment dependency."""
    return [Conflict(k) for k in existing if k in config.keys]

# Step 2: Test pure function directly (no fixture needed)
def test_detect_conflicts_with_overlapping_keys():
    conflicts = detect_conflicts(Config(keys=["a", "b"]), existing=["b", "c"])
    assert conflicts == [Conflict("b")]

# Step 3: Parametrize ONLY the adapter layer
@pytest.fixture(params=["clean", "with-pre-commit"])
def fs_adapter(request):
    return create_real_fs_adapter(request.param)

def test_adapter_reads_config_from_environment(fs_adapter):
    config = fs_adapter.read_config()  # Only I/O is parametrized
    assert config is not None
```

### Mandate Compliance (CM-D)

- **CM-D**: Business logic extracted to pure functions. Impure code isolated behind adapters. Fixture parametrization applies only to adapter layer.

## The 3 Pillars (style backbone for acceptance tests)

These three pillars are the lens used during writing and review. They sit above Mandates 1-4: every scenario MUST embody all three before mandate compliance is even considered.

### Pillar 1 — Domain language with specific actions

Scenarios speak the domain, not the code. A domain expert reads them without seeing a single line of implementation. Step names are semantic (`User_signs_up`, NOT `Call_signup_endpoint`). Technical jargon (HTTP, JSON, schema, endpoint, database) is forbidden in scenario titles, Gherkin steps, and step-method names. Technical detail lives inside step bodies only.

### Pillar 2 — Chained narrative

Within a story line, scenarios read as a sequence of state transitions: **the `Given` of scenario N equals the `Given + When` of scenario N-1**. Read in order, the tests tell the feature. The `Given` of scenario N never duplicates the setup of N-1: it reuses already-defined step methods (step composition, not copy-pasted fixtures).

### Pillar 3 — App as in production

The SUT is built via the production composition root (style `WebApplicationFactory` or equivalent). Only **external / non-deterministic ports** (clock, email, SMS, push, payment, LLM, third-party APIs) are substituted by fakes/stubs. The app is never rebuilt by hand replicating the wiring. Tier B (state-machine PBT, Mandate 10) uses an `InMemoryComposition` root that honors the same interfaces — same vocabulary, different composition root.

## Mandate 16: Algebraic Analysis Before the Scenario

Do the analysis that a good bugfix would eventually force, at the moment the
scenario is authored. It is the same analysis either way; only its price
changes. Four questions, each paired with the imperative for its honest-no.

**1. What law does this scenario protect?**

> Name the property in one sentence — conservation, decomposition, a state
> transition, an oracle, a metamorphic relation. If the honest answer is "it
> checks that the feature works", **stop and name the law**: an unnamed law
> cannot tell you which observations are missing, and the scenario will drift
> into asserting whatever the implementation happens to do.

**2. What is the narrowest surface that carries that law?**

> Ask what the scenario must set up to observe it. If the answer is a whole
> subsystem — every sibling component satisfied, the unrelated ones patched out —
> **the law is being observed at the wrong altitude.** Push it down to the unit
> that owns it (a pure function over declared inputs, property-tested), and keep
> ONE example at the composition surface for the reporting/wiring claim. A
> scenario that fabricates a world to observe a small law has a failure surface
> as large as that world, and will break for reasons that have nothing to do with
> the law.

**3. Which inputs is the behaviour gated on — and does the scenario DECLARE
every one of them?**

> Walk the path from the driving port to the assertion and check it against the
> gate list in `contract:declared-inputs-not-ambient-reads`
> (`nw-cross-cutting-invariants` — one list, so it cannot drift between copies).
> For each gate, ask whether the scenario states it or inherits it. Answering
> "the fixture uses `tmp_path`, so it is hermetic" is the wrong answer:
> isolating the filesystem is not isolating the environment. **If it inherits,
> state it explicitly.**

**4. How would you know this scenario can fail?**

> Answering "it is green and the code is correct, so it is covered" is the wrong
> answer — a scenario that cannot fail is green for free, and green-for-free is
> indistinguishable from green-for-the-right-reason at the moment you read it.
> **Watch it go red for the reason it exists.** Authoring RED-first, the initial
> failure IS that evidence, provided you read WHY it failed: a collection or
> import error is not the law failing. Once it has gone green — after a refactor,
> or when the scenario predates the defect it now guards — re-inject the defect
> and watch it go red again. **Record which observations died and which
> survived**: laws that constrain shape correctly survive a content defect, and
> a suite where everything dies to everything is as uninformative as one where
> nothing does.
>
> This is a single deliberate check per scenario, at authoring time, on the
> defect the scenario names. It is NOT mutation testing, which this project
> disables as a routine gate (`CLAUDE.md` § Mutation Testing Strategy) — no
> generated mutants, no kill-rate, no scheduled run.

**Order-independence is part of the contract.** Before calling a scenario done,
run it ALONE in a fresh process. Passing only in file order is a defect of the
scenario, not a quirk of the runner: CI shards and parallel workers redistribute
tests, so a sibling's side effect is not a dependency you may rely on.

Design-time twins: the same two questions are stated for the architect and the
crafter in `nw-code-design-oo` and `nw-code-design-fp` (declared inputs at the
boundary; enumerate the outcomes before choosing the return type). Reaching
this mandate first, read those next.

Empirical anchor, 2026-08-06: three CI-only failures, three different suites, one
class — each scenario inherited host/platform state instead of declaring it, and
one of them additionally drove an entire installer to observe a single
byte-comparison. Fixing them by declaring the input took minutes; finding them
cost four refuted hypotheses each, because a scenario that reads ambient state
gives no signal about WHICH state it read.
