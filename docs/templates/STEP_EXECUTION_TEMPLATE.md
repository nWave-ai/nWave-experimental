# Step Execution Template (Parametric)

## Standard Workflow for Step Implementation

This template defines the standardized workflow for executing any step in the plugin-marketplace-migration roadmap following the implement → review → fix → refactor cycle.

---

## STEP {STEP_NUMBER}: {STEP_NAME}

**Context**: {BRIEF_CONTEXT_DESCRIPTION}

**Parameters**:
- AGENT: `@agent-{PRIMARY_AGENT}`
- REVIEWER: `@agent-{PRIMARY_AGENT}-reviewer`
- STEP_FILE: `docs/feature/plugin-marketplace-migration/steps/{STEP_FILE}.json`
- REFACTOR_LEVEL: `{REFACTOR_LEVEL}` (1-6, typically 4 for type-driven design with business language)

**Workflow Sequence**:

### 0. Initialize
- Tell user: "Starting Step {STEP_NUMBER}: {STEP_NAME}"
- Deliverables: {BRIEF_DELIVERABLES_LIST}

### 1. Implement ({ESTIMATED_HOURS_IMPLEMENT}h)
```
/nw:execute @agent-{PRIMARY_AGENT} implement docs/feature/plugin-marketplace-migration/steps/{STEP_FILE}.json
- Focus on deliverables only (no reports)
- Use business language and domain concepts throughout
- CRITICAL TDD CYCLE: Write test → Test FAILS for correct reason → Implement → Test PASSES
- DO NOT COMMIT before user approval
```

**TDD Requirements**:
- Write tests FIRST that fail for the correct reason
- Implement code to make tests pass
- Never skip the red phase (failing test)
- Verify tests pass for the right reason, not by accident

### 1.5 TDD Inner Loop (MANDATORY - 11 Phases)

The implementation MUST follow the disciplined 11-phase TDD inner loop:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. PREPARE: Activate ONE acceptance test, [Ignore] others      │
│    GATE: Only ONE acceptance test active                        │
├─────────────────────────────────────────────────────────────────┤
│ 2. RED (Acceptance): Run test → MUST fail                       │
│    GATE: If passes immediately, test is invalid                 │
├─────────────────────────────────────────────────────────────────┤
│ 3. RED (Unit): Write unit test → MUST fail for correct reason   │
│    GATE: Fails on assertion, NOT compilation/setup              │
├─────────────────────────────────────────────────────────────────┤
│ 4. GREEN (Unit): Implement MINIMAL code (YAGNI)                 │
├─────────────────────────────────────────────────────────────────┤
│ 5. CHECK: Run acceptance test                                   │
│    IF FAILS → Return to phase 3                                 │
│    IF PASSES → Continue                                         │
├─────────────────────────────────────────────────────────────────┤
│ 6. GREEN (Acceptance): All tests pass                           │
├─────────────────────────────────────────────────────────────────┤
│ 7. REVIEW LOOP: Review + VALIDATE + Fix (max 2 iterations)      │
├─────────────────────────────────────────────────────────────────┤
│ 8. REFACTOR LOOP: L1 → L2 → L3 → L4 (validate each level)       │
├─────────────────────────────────────────────────────────────────┤
│ 9. POST-REFACTOR REVIEW: Review after refactoring               │
├─────────────────────────────────────────────────────────────────┤
│ 10. FINAL VALIDATE: 100% tests passing                          │
├─────────────────────────────────────────────────────────────────┤
│ 11. COMMIT: This step only (NO PUSH - push after finalize)      │
└─────────────────────────────────────────────────────────────────┘
```

#### Phase A: Prepare Acceptance Test
- Remove [Ignore] from ONE scenario only
- Verify all others have [Ignore]
- **GATE G1**: Exactly one acceptance test active

#### Phase B: RED - Acceptance Test
- Run test
- **MUST fail** for valid reason (missing business logic, not infrastructure)
- If passes immediately → test is invalid, investigate

#### Phase C: RED - Unit Test
- Write unit test for minimal behavior needed
- Naming: `{BusinessConcept}Should.{Behavior}_When{Condition}`
- **MUST fail with assertion error** (not compilation error)
- **FORBIDDEN**: Mocks of domain/application classes (only ports/adapters)

#### Phase D: GREEN - Unit Test
- Implement MINIMAL code
- YAGNI: no functionality beyond what test requires

#### Phase E: Check Acceptance
- Run acceptance test
- If fails → return to Phase C (more unit tests needed)
- If passes → continue to review

### Test Infrastructure Requirements

| Test Type | Allowed Test Doubles | Preferred Approach |
|-----------|---------------------|-------------------|
| Domain Unit | NONE | Real objects only |
| Application Unit | Ports only | In-memory adapters |
| Integration | External services | Testcontainers or fakes |
| Acceptance/E2E | External APIs only | Real system with fakes |

### Business Language Validation

**Test Class Names**: `{BusinessConcept}Should`
**Test Method Names**: `{Behavior}_When{Condition}`

**GOOD Examples**:
- `OrderServiceShould.RejectOrder_WhenInventoryInsufficient`
- `CustomerEmailShould.BeInvalid_WhenMissingAtSymbol`

**BAD Examples**:
- `TestClass.Test1`
- `HelperTests.TestMethod`

### 2. Review ({ESTIMATED_HOURS_REVIEW}h)
```
/nw:review @agent-{PRIMARY_AGENT}-reviewer review implementation of docs/feature/plugin-marketplace-migration/steps/{STEP_FILE}.json
- Embed critique in response (no separate reports)
- Verify business language is used consistently
- DO NOT COMMIT before user approval
```
- Tell user: "Review complete" + summary + "Applying fixes..."

### 3. Fix ({ESTIMATED_HOURS_FIX}h)
```
/nw:execute @agent-{PRIMARY_AGENT} implement fix for ALL issues found in review
- DO NOT COMMIT before user approval
```
- Tell user: "Fixes applied" + description

### 4. Refactor ({ESTIMATED_HOURS_REFACTOR}h)
```
/nw:refactor @agent-{PRIMARY_AGENT} refactor implementation and tests for docs/feature/plugin-marketplace-migration/steps/{STEP_FILE}.json from level 1 to level {REFACTOR_LEVEL}
- Use business language and domain definitions for:
  * Type discovery and implementation
  * Class and method names
  * Test names and test class names
- Introduce new types or move responsibilities to types (Level 4+)
- Use type system as protection layer against non-representable state
- All tests must pass before refactoring
```

**CRITICAL REFACTORING RULES**:
- ❌ **DO NOT DELETE TESTS** - Tests are the safety net for refactoring
- ❌ **DO NOT MODIFY TEST LOGIC** - Only change test structure/organization
- ✅ **Tests must remain unchanged** unless type signatures change fundamentally
- ✅ **All tests must pass DURING and AFTER refactoring**
- ✅ **Exception**: Test updates allowed ONLY when introducing new domain types that change method signatures
- ✅ **TDD cycle maintained**: If changing types, write new test → fail → refactor → pass

**Acceptable Test Changes During Refactoring**:
- Renaming test classes/methods for business language (Level 1)
- Extracting test fixtures/helpers (Level 2)
- Organizing tests into domain-based classes (Level 3)
- Updating test data to use domain types (Level 4+) - BUT assertions stay the same

**Unacceptable Test Changes**:
- Deleting tests to make refactoring easier
- Changing test assertions to match new behavior
- Removing edge case tests
- Weakening test coverage

- Tell user: "Refactoring complete. Ready for commit after your approval."

### Critical Rules
- ✅ Follow sequence strictly (implement → review → fix → refactor)
- ✅ **TDD CYCLE MANDATORY**: Write test → Test fails correctly → Implement → Test passes
- ✅ Use business language and domain concepts everywhere (types, classes, methods, tests)
- ✅ **Tests are sacred during refactoring** - preserve all tests, only change structure
- ✅ All tests must pass at EVERY stage (after implement, after fix, after refactor)
- ✅ Escalate if unexpected issues occur
- ✅ Wait for user approval before commit
- ❌ No extra reports or documentation
- ❌ **NEVER delete tests** to make refactoring easier
- ❌ **NEVER modify test assertions** unless type signatures fundamentally change

---

## Parameter Reference Table

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| `{STEP_NUMBER}` | Step identifier (e.g., 01-02) | `01-02` |
| `{STEP_NAME}` | Human-readable step name | `Create Agent Jinja2 Template` |
| `{BRIEF_CONTEXT_DESCRIPTION}` | 1-2 sentence context | `Enhance existing agent.md.j2 template with YAML escaping` |
| `{PRIMARY_AGENT}` | Agent responsible for implementation | `software-crafter` |
| `{STEP_FILE}` | JSON step file name without extension | `01-02` |
| `{REFACTOR_LEVEL}` | Target refactoring level (1-6) | `4` |
| `{BRIEF_DELIVERABLES_LIST}` | Key deliverables summary | `Enhanced template, unit tests, E2E tests` |
| `{ESTIMATED_HOURS_IMPLEMENT}` | Implementation time estimate | `3-4` |
| `{ESTIMATED_HOURS_REVIEW}` | Review time estimate | `0.5-0.75` |
| `{ESTIMATED_HOURS_FIX}` | Fix time estimate | `1-2` |
| `{ESTIMATED_HOURS_REFACTOR}` | Refactoring time estimate | `1-2` |

---

## Progressive Refactoring Levels (1-6)

**CRITICAL**: Use business language and domain definitions at ALL levels for type names, class names, method names, test names, and test class names.

### Level 1: Naming and Simple Extractions
**Focus**: Clear, intention-revealing names using business language

**Techniques**:
- Rename variables, methods, classes to reflect domain concepts
- Extract magic numbers to named constants with business meaning
- Remove code duplication through simple extractions

**Example**:
```python
# Before (technical names)
def proc(d): return d * 0.15

# After (business language)
def calculate_vat_amount(net_price: Money) -> Money:
    VAT_RATE = 0.15
    return net_price * VAT_RATE
```

**Test naming**: `test_vat_calculation_applies_fifteen_percent_rate()`

---

### Level 2: Method and Function Extraction
**Focus**: Single responsibility at method level using domain operations

**Techniques**:
- Extract long methods into smaller, focused methods with business names
- Group related operations into cohesive units
- Introduce explaining variables with domain terminology

**Example**:
```python
# Before
def process_order(order):
    total = sum(item.price for item in order.items)
    discount = total * 0.1 if len(order.items) > 5 else 0
    final = total - discount
    # ...payment processing...

# After (business operations)
def process_order(order: Order) -> ProcessedOrder:
    subtotal = calculate_order_subtotal(order)
    discount = apply_bulk_purchase_discount(order, subtotal)
    final_amount = calculate_final_amount(subtotal, discount)
    payment_result = process_payment(final_amount)
    return ProcessedOrder(payment_result, final_amount)
```

**Test naming**: `test_bulk_purchase_discount_applies_when_order_exceeds_five_items()`

---

### Level 3: Class Extraction and Responsibility Organization
**Focus**: Single Responsibility Principle at class level with domain boundaries

**Techniques**:
- Extract classes for distinct business concepts
- Move methods to appropriate classes based on domain responsibilities
- Organize code around business entities and operations

**Example**:
```python
# Before (God class)
class OrderManager:
    def calculate_total(self, items): ...
    def apply_discount(self, total): ...
    def process_payment(self, amount): ...
    def send_email(self, order): ...

# After (domain-driven classes)
class OrderPricing:
    def calculate_subtotal(self, items: list[OrderItem]) -> Money: ...
    def apply_bulk_discount(self, subtotal: Money, item_count: int) -> Money: ...

class PaymentProcessor:
    def charge_customer(self, amount: Money, payment_method: PaymentMethod) -> PaymentResult: ...

class OrderNotifier:
    def send_confirmation_email(self, order: Order, customer: Customer) -> None: ...
```

**Test classes**: `OrderPricingTest`, `PaymentProcessorTest`, `OrderNotifierTest`
**Test naming**: `test_order_pricing_calculates_subtotal_from_item_prices()`

---

### Level 4: Type-Driven Design with Business Types
**Focus**: Introduce domain-specific types, move responsibilities to types, use type system to make wrong state non-representable

**Techniques**:
- Create value objects for business concepts (Money, Email, OrderStatus)
- Replace primitive obsession with rich domain types
- Use type system to enforce business invariants
- Move validation and business logic into type constructors
- Use frozen dataclasses, TypedDict with Required/NotRequired
- Create union types for explicit state representation

**Example**:
```python
# Before (primitive obsession, invalid states possible)
def create_order(customer_email: str, items: list[dict], status: str) -> dict:
    if not items:
        raise ValueError("Empty order")
    return {"email": customer_email, "items": items, "status": status}

# After (business types, invalid states non-representable)
@dataclass(frozen=True)
class CustomerEmail:
    value: str
    def __post_init__(self):
        if "@" not in self.value:
            raise ValueError(f"Invalid email: {self.value}")

@dataclass(frozen=True)
class OrderItem:
    product_name: str
    quantity: int  # Type ensures >= 0
    unit_price: Money

@dataclass(frozen=True)
class NonEmptyOrderItems:
    """Type ensures at least one item exists"""
    items: list[OrderItem]
    def __post_init__(self):
        if not self.items:
            raise ValueError("Order must have at least one item")

class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"

@dataclass(frozen=True)
class Order:
    customer_email: CustomerEmail  # Type ensures valid email
    items: NonEmptyOrderItems      # Type ensures non-empty
    status: OrderStatus            # Type ensures valid status
```

**Test naming**: `test_customer_email_rejects_invalid_format()`
**Test class naming**: `CustomerEmailValidationTest`, `NonEmptyOrderItemsTest`

---

### Level 5: Interface Segregation and Dependency Inversion
**Focus**: Decouple through domain-aligned abstractions

**Techniques**:
- Extract interfaces for business capabilities
- Depend on abstractions (protocols) not implementations
- Use dependency injection with domain-named dependencies
- Apply Interface Segregation Principle with business boundaries

**Example**:
```python
# Before (concrete dependency)
class OrderProcessor:
    def __init__(self):
        self.email_service = SmtpEmailService()  # Concrete dependency

# After (business abstraction)
class OrderNotificationService(Protocol):
    """Domain capability: notify customer about order events"""
    def notify_order_confirmed(self, order: Order, customer: Customer) -> None: ...

class OrderProcessor:
    def __init__(self, notifier: OrderNotificationService):
        self._notifier = notifier  # Depends on business capability
```

**Test naming**: `test_order_processor_notifies_customer_when_order_confirmed()`

---

### Level 6: Domain-Driven Design Patterns
**Focus**: Strategic design with bounded contexts and domain patterns

**Techniques**:
- Identify and implement domain patterns (Repository, Factory, Aggregate)
- Define bounded contexts with ubiquitous language
- Implement domain events for business state changes
- Apply hexagonal/clean architecture with domain at core

**Example**:
```python
# Domain layer (business logic)
class Order(AggregateRoot):
    """Aggregate root for order lifecycle"""
    def confirm(self) -> OrderConfirmed:
        if self.status != OrderStatus.PENDING:
            raise InvalidOrderStateTransition()
        self._status = OrderStatus.CONFIRMED
        return OrderConfirmed(order_id=self.id, confirmed_at=now())

# Repository (business collection)
class OrderRepository(Protocol):
    def find_pending_orders_for_customer(self, customer_id: CustomerId) -> list[Order]: ...
    def save(self, order: Order) -> None: ...

# Domain event (business occurrence)
@dataclass(frozen=True)
class OrderConfirmed:
    order_id: OrderId
    confirmed_at: datetime
```

**Test naming**: `test_order_confirmation_emits_order_confirmed_event()`
**Test class naming**: `OrderAggregateTest`, `OrderRepositoryContractTest`

---

## Business Language Examples

### Type Names (Domain Concepts)
- ✅ `CustomerEmail`, `Money`, `OrderStatus`, `PaymentMethod`
- ❌ `StringValidator`, `DataHolder`, `ProcessResult`

### Class Names (Business Entities/Operations)
- ✅ `OrderPricing`, `PaymentProcessor`, `InventoryChecker`
- ❌ `DataManager`, `Helper`, `Util`

### Method Names (Business Actions)
- ✅ `calculate_vat_amount()`, `apply_bulk_discount()`, `confirm_order()`
- ❌ `process()`, `handle()`, `do_work()`

### Test Names (Business Scenarios)
- ✅ `test_bulk_discount_applies_when_cart_exceeds_minimum_items()`
- ✅ `test_order_confirmation_fails_when_stock_insufficient()`
- ❌ `test_function_1()`, `test_edge_case()`

### Test Class Names (Business Components)
- ✅ `OrderPricingTest`, `BulkDiscountPolicyTest`, `CustomerEmailValidationTest`
- ❌ `TestSuite1`, `UnitTests`, `Helpers`

---

## Common Agent Mappings

| Step Phase | Primary Agent | Typical Steps |
|------------|---------------|---------------|
| TOON Infrastructure | `software-crafter` | 01-01 to 01-06 |
| Archive & Documentation | `software-crafter` | 02-01 to 02-04 |
| Agent Migration | `software-crafter` | 03-01 to 03-03 |
| Command Migration | `software-crafter` | 04-01 to 04-06 |
| Skill Migration | `software-crafter` | 05-01 to 05-04 |
| Quality Validation | `software-crafter` | 06-01 to 06-03 |
| Plugin Configuration | `software-crafter` | 07-01 to 07-03 |
| Integration & Validation | `devop` or `software-crafter` | 08-01 to 08-04 |

---

## Usage Examples

### Example 1: Step 01-02 (Agent Template)
```
STEP 01-02: Create Agent Jinja2 Template (Complete)
- AGENT: @agent-software-crafter
- STEP_FILE: docs/feature/plugin-marketplace-migration/steps/01-02.json
- REFACTOR_LEVEL: 4
- DELIVERABLES: Enhanced template with YAML escaping, embedded knowledge, multiline support
```

### Example 2: Step 08-01 (Release Integration)
```
STEP 08-01: Update Release System
- AGENT: @agent-devop
- STEP_FILE: docs/feature/plugin-marketplace-migration/steps/08-01.json
- REFACTOR_LEVEL: 3
- DELIVERABLES: Release packaging integration in create_release_packages.py
```

### Example 3: Step 08-02 (Plugin Installation - BLOCKER #3)
```
STEP 08-02: Plugin Installation Test
- AGENT: @agent-devop
- STEP_FILE: docs/feature/plugin-marketplace-migration/steps/08-02.json
- REFACTOR_LEVEL: 4
- DELIVERABLES: Installation mechanism (fallback or /plugin install), validation tests
```

---

## Quick Reference: Fill Template for Any Step

**Step to execute**: ________________

**Parameters**:
- STEP_NUMBER: ________________
- STEP_NAME: ________________
- BRIEF_CONTEXT: ________________
- PRIMARY_AGENT: ________________
- REFACTOR_LEVEL: ________________
- DELIVERABLES: ________________

**Execution command**:
```
Lyra, please execute step {STEP_NUMBER} using the STEP_EXECUTION_TEMPLATE with the parameters above.
```

---

## Notes

- **Business Language Everywhere**:
  - Discover domain concepts first, then create types
  - Use ubiquitous language from business domain
  - Tests should read like business specifications
  - Avoid technical jargon in favor of domain terminology

- **Type-Driven Design (Level 4) Key Principle**:
  - Make invalid states unrepresentable through type constraints
  - Move validation from runtime checks to compile-time type checking
  - Use rich domain types instead of primitive obsession

- **Time Estimates**:
  - Implementation: 60-80% of total step hours
  - Review: 10-15% of total
  - Fix: 10-20% of total
  - Refactor: 15-25% of total

- **Agent Selection**:
  - Use `software-crafter` for code/infrastructure work
  - Use `devop` for deployment/integration work
  - Use `researcher` for investigation/analysis work
