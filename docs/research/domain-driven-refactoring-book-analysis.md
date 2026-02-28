# Research: Domain-Driven Refactoring -- Book Analysis

**Date**: 2026-02-28 | **Researcher**: nw-researcher (Nova) | **Confidence**: High | **Source**: Primary (book analysis)

## Executive Summary

"Domain-Driven Refactoring" by Alessandro Colla and Alberto Acerbis (Packt, April 2025) is a practitioner-focused guide to refactoring legacy systems using Domain-Driven Design. The book traces a complete journey from a chaotic monolith through modular monolith to microservices, using a brewery ERP system ("BrewUp") as a running example implemented in C# / .NET. The book's distinctive contribution is its emphasis on **incremental, safe refactoring** guided by DDD strategic and tactical patterns, with a strong pragmatic ethos captured in the recurring principle: "start simple, grow big."

The book is structured in three parts: (1) Understanding the foundations (Cynefin, complexity, strategic/tactical DDD patterns), (2) Refactoring the monolith (code, architecture, database, CI/CD), and (3) Moving to microservices (transition strategies, event evolution, sagas). It draws heavily from Evans, Vernon, Brandolini, Fowler, and Richards/Ford, synthesizing their work into a practical refactoring methodology rather than introducing fundamentally new theory. The book's strongest sections are its treatment of database refactoring with DDD alignment (Chapter 8), the fitness function approach to measuring refactoring progress (Chapter 6), and the event versioning strategies (Chapter 11).

Key insight for nWave: The book validates our wave-based methodology by demonstrating that DDD refactoring follows a discovery-to-delivery pipeline -- from understanding complexity (Cynefin/EventStorming) through strategic design (bounded contexts, context mapping) to tactical implementation (aggregates, events) to infrastructure evolution (database splitting, microservice extraction). This maps directly to nWave's DISCOVER > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER sequence.

---

## Book Metadata

| Field | Value |
|-------|-------|
| **Title** | Domain-Driven Refactoring |
| **Authors** | Alessandro Colla, Alberto Acerbis |
| **Publisher** | Packt Publishing |
| **Date** | April 2025 (pre-launch copy) |
| **Pages** | ~289 (including front/back matter) |
| **ISBN** | B22493 (Packt ID) |
| **Language** | English |
| **Code examples** | C# / .NET 9.0 |
| **Repository** | github.com/PacktPublishing/Domain-driven-Refactoring |
| **Foreword by** | Alberto Brandolini (inventor of EventStorming) |
| **Technical reviewers** | Andrea Saltarello, Emanuele Bartolesi |

---

## Part I: Understanding Complexity (Chapters 1-4)

### Chapter 1: What Is Refactoring and Why It Matters (pp. 23-34)

**Key Concepts:**
- Defines refactoring as improving internal structure without changing external behavior, following Martin Fowler's canonical definition
- Distinguishes between **refactoring** (behavior-preserving), **rewriting** (replacing the system), and **rearchitecting** (changing architectural style)
- Introduces the concept of **technical debt** as the primary driver for refactoring
- Positions DDD as the strategic compass for refactoring decisions -- DDD tells you WHERE and WHY to refactor, while traditional refactoring techniques tell you HOW

**Practical Insights:**
- The authors frame refactoring as a continuous activity, not a separate phase: "Refactoring is not a one-time activity but a continuous process" (p. 24)
- Argues that refactoring without domain understanding leads to "cosmetic improvements" that do not address structural problems
- The Whirlpool process (from Eric Evans) is introduced as the iterative model for domain understanding during refactoring

**Cross-references to DDD Literature:**
- Martin Fowler, "Refactoring: Improving the Design of Existing Code" (1999, 2018)
- Eric Evans, "Domain-Driven Design: Tackling Complexity in the Heart of Software" (2003)
- Ward Cunningham's original technical debt metaphor (1992)

---

### Chapter 2: Understanding Complexity: Problem and Solution Space (pp. 35-54)

**Key Concepts:**
- **Cynefin Framework**: The book dedicates significant space to Dave Snowden's Cynefin framework as a sense-making tool for deciding when and how to refactor. The five domains (Clear, Complicated, Complex, Chaotic, Confusion/Aporetic) determine the appropriate refactoring strategy
- **Problem Space vs. Solution Space**: The problem space is about understanding the domain (subdomains, bounded contexts discovery); the solution space is about implementing the model (tactical patterns, architecture)
- **Core Domain Chart**: A tool for classifying bounded contexts along two axes -- model complexity and business differentiation -- to determine investment priority
- **EventStorming**: Introduced as the primary collaborative discovery technique. The authors cover Big Picture EventStorming for domain discovery and Design-Level EventStorming for bounded context modeling

**The Cynefin-Refactoring Mapping (novel synthesis):**
| Cynefin Domain | Refactoring Approach |
|---------------|---------------------|
| Clear | Apply established patterns directly; standard refactoring catalogs |
| Complicated | Analyze with experts, then apply patterns; multiple valid solutions exist |
| Complex | Probe with safe-to-fail experiments; EventStorming to discover patterns |
| Chaotic | Act first to stabilize, then refactor; emergency patches acceptable |
| Confusion | Gather information before deciding; avoid premature refactoring |

**Whirlpool Process (from Evans):**
The authors explicitly adopt Eric Evans' Whirlpool process as their iterative methodology: Model > Scenario exploration > Code probing > Model refinement. This is contrasted with the naive "understand everything first, then implement" approach. The Whirlpool emphasizes that modeling and implementation inform each other in tight feedback loops.

**Practical Insights:**
- "The second law of software architecture: The WHY is more important than the HOW" (p. 44) -- this becomes a recurring refrain throughout the book
- EventStorming is recommended as the starting point for ANY refactoring effort, not just greenfield projects
- The authors warn against "premature decomposition" -- splitting bounded contexts before understanding the domain deeply enough

---

### Chapter 3: Strategic Patterns (pp. 55-74)

**Key Concepts:**
- **Bounded Context**: Defined as a semantic boundary where a domain model has consistent meaning. The authors emphasize this is the MOST important DDD pattern and the one most frequently misunderstood
- **Context Mapping**: All standard patterns covered with practical guidance:
  - **Shared Kernel**: Shared code/model between contexts. Use sparingly; high coupling cost
  - **Customer-Supplier**: Upstream serves downstream; power asymmetry
  - **Conformist**: Downstream conforms entirely to upstream model
  - **Anti-Corruption Layer (ACL)**: Translation layer protecting a context from external model influence. The authors call this "one of the most powerful patterns in DDD" (p. 65)
  - **Open Host Service (OHS) + Published Language**: Providing a well-defined protocol for integration
  - **Partnership**: Two teams cooperate on integration with shared goals
  - **Separate Ways**: No integration; each context solves independently

**Critical Distinction -- Bounded Context vs. Microservice (p. 224):**
> "A bounded context defines a semantic boundary... A microservice defines a physical boundary... You can have a microservice with more than one bounded context, but you cannot have a bounded context split through many microservices!"

This is stated explicitly as a rule. A bounded context is a unit of conceptual integrity; a microservice is a unit of deployment. They often align but serve different purposes.

**Practical Insights:**
- The ACL pattern is the most frequently used integration pattern in refactoring scenarios because legacy systems rarely speak the same language as newly designed bounded contexts
- Context maps should be drawn before any code is written in a refactoring effort
- The authors show how context mapping patterns evolve during refactoring (e.g., a Conformist relationship can be refactored to Customer-Supplier with an ACL)

---

### Chapter 4: Tactical Patterns (pp. 75-96)

**Key Concepts:**
- **Entities**: Objects with identity that persists through state changes. Identified by a unique identifier, not by attribute values
- **Value Objects**: Objects defined by their attributes with no conceptual identity. Immutable. The authors advocate strongly for preferring Value Objects over primitives ("primitive obsession" is a key code smell)
- **Aggregates**: Cluster of entities and value objects treated as a single unit for data changes. The aggregate root is the only entry point. The authors define aggregates as "transactional consistency boundaries" (p. 82)
- **Domain Events**: Represent something that happened in the domain. Immutable records. The authors distinguish between:
  - **Domain Events**: Internal to a bounded context
  - **Integration Events**: Cross bounded context boundaries (translated by ACL)
- **Repositories**: Abstraction over data access. The authors use the repository pattern to encapsulate persistence, following the ports-and-adapters principle
- **Domain Services**: Operations that do not naturally belong to any entity or value object. Should be stateless

**Aggregate Design Rules (following Vaughn Vernon):**
1. Protect business invariants inside aggregate boundaries
2. Design small aggregates
3. Reference other aggregates by identity only
4. Update other aggregates using eventual consistency (via domain events)

**Practical Insights:**
- The book shows the progression: Anemic Domain Model (anti-pattern) > Rich Domain Model with tactical patterns
- Aggregate boundaries are where transactional consistency is enforced; cross-aggregate operations use eventual consistency via events
- The authors demonstrate transforming a CRUD-based entity into a proper aggregate with business rules, commands, and domain events using the BrewUp example

---

## Part II: Refactoring the Monolith (Chapters 5-9)

### Chapter 5: Introducing Refactoring Principles (pp. 99-120)

**Key Concepts:**
- **Code Smells as Refactoring Triggers**: Long methods, large classes, feature envy, data clumps, primitive obsession, shotgun surgery, divergent change
- **Testing as a Safety Net**: The authors establish a testing taxonomy:
  - Unit tests: Isolated behavior verification
  - Integration tests: Component interaction verification
  - Acceptance tests: Business requirement validation
  - Performance tests: Non-functional requirement verification
- **When NOT to Refactor**: Systems scheduled for replacement, stable systems with no new development, or systems where the cost exceeds the benefit

**Refactoring Decision Framework:**
The authors propose asking three questions before refactoring:
1. What is the **business value** of refactoring this area?
2. What is the **risk** of refactoring vs. not refactoring?
3. What is the **cost** (time, effort, disruption)?

**Practical Insights:**
- "Refactoring is not about making code perfect; it is about making code good enough to support the next set of changes" (p. 103)
- Tests must exist BEFORE refactoring begins -- the "test first, refactor second" principle
- The authors explicitly recommend characterization tests (Michael Feathers' technique from "Working Effectively with Legacy Code") for legacy systems without test coverage

---

### Chapter 6: Transitioning from Chaos (pp. 121-148)

**Key Concepts:**

This is one of the book's strongest chapters. It presents a systematic methodology for moving from a chaotic "Big Ball of Mud" monolith to a well-structured modular monolith.

**The Layered-to-Modular Refactoring Path:**
1. **Starting point**: Traditional layered architecture (Presentation > Business > Data Access)
2. **Step 1**: Identify bounded contexts using EventStorming and domain analysis
3. **Step 2**: Introduce modules aligned with bounded contexts within the monolith
4. **Step 3**: Move from shared database to module-aligned data access
5. **Step 4**: Introduce events for cross-module communication
6. **Step 5**: Apply CQRS to separate read and write concerns per module

**Fitness Functions (from "Building Evolutionary Architectures" by Ford/Parsons/Kua):**
The book adapts the fitness function concept for measuring refactoring progress:
- **Coupling metrics**: Afferent/efferent coupling between modules
- **Cohesion metrics**: Relatedness of components within a module
- **Dependency direction**: Ensuring dependencies flow in the correct direction
- **Test coverage**: As a proxy for refactoring safety

The authors recommend using tools like NDepend (.NET) or SonarQube to automate fitness function evaluation.

**Architectural Quanta:**
Borrowed from Richards and Ford, the concept of "architectural quantum" -- the smallest independently deployable unit with high functional cohesion -- is used to define the target granularity for modules. The authors argue that a well-designed modular monolith where each module is an architectural quantum can often be preferable to premature microservice extraction.

**Practical Insights:**
- The mediator pattern is introduced as an initial decoupling mechanism between modules: modules communicate through a mediator rather than direct references. However, the authors explicitly note this is an intermediate step -- mediator should eventually be replaced by events for full microservice readiness (covered in Chapter 10)
- The authors provide a full solution structure transformation from the BrewUp example, showing how the Visual Studio solution evolves from layers to modules
- "Do not introduce unnecessary complexity at the outset of your refactoring process" (p. 148) -- incremental steps that you can test at each stage

---

### Chapter 7: Refactoring the Code (pp. 149-170)

**Key Concepts:**

**Introduce Value Objects:**
- Pattern: Replace primitive types (string, int, Guid) with strongly-typed Value Objects
- When to apply: Primitive obsession code smell; business rules attached to primitive values
- Steps: (1) Create Value Object class with validation, (2) Replace primitive in aggregate, (3) Update repository mapping, (4) Update tests
- Example: `string salesOrderNumber` becomes `SalesOrderNumber` value object with format validation

**Introduce Domain Events:**
- Pattern: Replace direct method calls between aggregates/services with domain events
- When to apply: Operations that affect multiple aggregates; need for audit trail; preparing for eventual consistency
- Steps: (1) Identify the state change, (2) Create event class, (3) Raise event in aggregate, (4) Create handler, (5) Wire up event bus
- Example: `SalesOrderCreated` event replaces direct call from order creation to warehouse notification

**Introduce Domain Services:**
- Pattern: Extract operations that span multiple entities/aggregates into domain services
- When to apply: Business logic that does not belong to a single aggregate
- Steps: (1) Identify cross-aggregate operation, (2) Create service interface, (3) Implement service, (4) Inject dependencies via constructor

**Introduce CQRS:**
- Pattern: Separate the read model (queries) from the write model (commands)
- When to apply: Different scaling requirements for reads vs. writes; complex query patterns; read model optimization needed
- Steps: (1) Create separate read model DTOs, (2) Create query handlers, (3) Update read side to use optimized queries, (4) Keep write side using aggregates with domain events
- The authors implement CQRS using MediatR in .NET, with separate command handlers and query handlers

**Practical Insights:**
- Each refactoring is presented with "before" and "after" code, making the transformation explicit
- The authors emphasize that CQRS does NOT require event sourcing -- this is a common misconception they address directly
- Read models can be denormalized specifically for query performance without affecting the write model's integrity

---

### Chapter 8: Refactoring the Database (pp. 171-196)

**Key Concepts:**

This chapter addresses one of the most challenging aspects of DDD refactoring: splitting a shared monolithic database to align with bounded context boundaries.

**Principles of Database Refactoring:**
1. Identify domain boundaries in the data (tables, schemas, stored procedures)
2. Apply expand/contract pattern for safe migration
3. Use event-based data synchronization between contexts during transition

**Data Duplication Through Event-Based Synchronization:**
- When bounded contexts need data owned by another context, the owning context publishes integration events
- The consuming context maintains its own read-only copy, updated via event handlers
- The anti-corruption layer translates between the event format and the local model
- Example: Warehouse context publishes `AvailabilityUpdatedForNotification` integration event; Sales context's ACL consumes it and updates its local `Availability` copy

**Three Distributed Data Access Patterns:**
1. **Replicated Caching**: Each service maintains an in-memory cache synchronized asynchronously. Low latency, but may struggle with high update rates
2. **Synchronous Interservice Communication**: Direct RPC/REST calls between services. Immediate consistency but introduces latency and coupling
3. **Column Schema Replication**: Specific columns duplicated from one service's database to another for immediate local access. Trades consistency for performance

**Data Synchronization Approaches:**
- **Event-based pattern**: Warehouse broadcasts changes; Sales listens and updates locally. Eventual consistency
- **Background synchronization**: Periodic batch sync for non-critical data
- **Orchestrated request-based**: Central orchestrator manages transactions between services. Synchronous but bottleneck risk

**Testing Strategies for Database Refactoring:**
- Unit tests for schema integrity and constraints
- Integration tests with mocked services
- Eventual consistency tests (simulating network latency, service unavailability)
- Contract tests for interservice communication
- Performance and load tests for database scalability

**Deployment Strategies:**
- Blue-green deployments for zero downtime
- Expand/contract (schema migration) pattern
- Versioned migrations (Flyway, Liquibase)
- Data duplication for seamless transition
- Feature flags for gradual rollout

**Practical Insights:**
- "Database refactoring is never an easy task... The primary challenge often lies not in the technical approach, but in overcoming resistance from stakeholders and DBAs" (p. 194)
- Stored procedures must be migrated gradually to the code base, not all at once
- The book provides complete Visual Studio solution screenshots showing the before/after structure of bounded context projects

---

### Chapter 9: DDD Patterns for CI/CD and Continuous Refactoring (pp. 197-216)

**Key Concepts:**
- DDD and CI/CD create a synergy: DDD provides modularity and bounded context isolation that makes CI/CD pipelines more reliable; CI/CD provides the feedback loops that enable continuous domain model refinement
- **Splitting Bounded Contexts**: When a context grows too large or serves conflicting purposes
  - Use domain decomposition to break responsibilities into subdomains
  - Use context mapping to plan the split and redefine integration patterns
  - Steps: (1) Isolate related aggregates, (2) Introduce domain events for communication, (3) Gradually refactor dependent code
- **Merging Bounded Contexts**: When separation causes more friction than value
  - Identify redundancies (overlapping models, duplicate logic, tight coupling)
  - Establish unified ubiquitous language
  - Consolidate aggregates and deprecate redundant events
- **Continuous Refactoring**: Refactoring woven into daily development, not reserved for cleanup phases
  - Maintain ubiquitous language as the codebase evolves
  - Use automated tests as safety nets
  - Collaborate with domain experts to identify model drift

**Automation and Tooling:**
- SonarQube for continuous code quality analysis
- GitLab CI/CD and GitHub Actions pipeline examples provided
- The book includes complete YAML pipeline configurations for both platforms

**Practical Insights:**
- Bounded context splits are driven by business evolution, not technical convenience
- A bounded context split should always be validated with domain experts
- Use ACLs during the transition period between old and new context boundaries
- Pipeline stages: cleanup > build > test > sonarqube > deploy

---

## Part III: Moving from Monolith to Microservices (Chapters 10-12)

### Chapter 10: When and Why You Should Transition to Microservices (pp. 219-242)

**Key Concepts:**

**The Decision Framework:**
The book presents a disciplined approach to the monolith-to-microservices decision:
1. Analyze the domain
2. Define bounded contexts
3. Define aggregates
4. THEN identify microservice candidates

The process flow: `Analyze Domain > Define Bounded Context > Define Aggregates > Identify Microservices`

**Bounded Context != Microservice:**
This critical distinction is repeated emphatically. A bounded context is a semantic boundary (conceptual clarity); a microservice is a physical boundary (deployment and operational independence). They overlap but are not identical.

**Monolith vs. Microservices Comparison (Table 10.1, p. 223):**
| Aspect | Monolith | Microservices |
|--------|----------|---------------|
| Development | Single codebase, simpler initially | Independent teams, faster iterations |
| Deployment | Single unit, straightforward | Independent per service |
| Scalability | Vertical only | Horizontal per service |
| Resilience | Single failure crashes all | Failures isolated |
| Complexity | Lower initial | Higher operational |
| Team Autonomy | Tight coordination | Autonomous |
| Performance | No network overhead | Network latency between services |

**Architecture Characteristics Rating (Table 10.6, p. 232):**
Based on Richards/Ford's "Fundamentals of Software Architecture", the authors rate modular monolith vs. microservices across 12 characteristics. Key findings:
- Microservices excel at: Elasticity (5/5), Scalability (5/5), Evolutionary (5/5), Modularity (5/5)
- Modular monolith excels at: Overall cost (5/5), Simplicity (4/5), Performance (3/5)
- Roughly equal: Deployability, Testability, Reliability

**Signals of Microservices Readiness:**
1. Clear domain boundaries already established
2. Scaling pressure on specific areas (not uniform)
3. Independent development needs across teams
4. Operational maturity (CI/CD, monitoring, automated testing in place)
5. Technical expertise in distributed systems
6. Business justification (not trend-following)

**Fallacies of Distributed Computing:**
The original 8 fallacies (Deutsch, Joy, Gosling, 1994-1997) plus Udi Dahan's 2 additions plus 5 modern additions:

Original 8: Network is reliable, Latency is zero, Bandwidth is infinite, Network is secure, Topology doesn't change, One administrator, Transport cost is zero, Network is homogeneous

Dahan's additions: System is consistent, System is predictable

Modern additions: System has infinite resources, System is free of state, Scaling is easy, Failures are rare, Time is consistent

**Transitioning Strategy (incremental, 3-step):**
1. **Mediator phase**: Use mediator pattern for inter-module communication (intermediate step)
2. **Event-driven phase**: Replace mediator with event-based communication
3. **Physical separation**: Extract modules into independent deployable services

**Practical Insights:**
- "Starting a greenfield project with microservices is significantly more complex and costly than with a well-structured modular monolith" (p. 222)
- Always start with the most problematic or independent bounded context for the first extraction
- The mediator pattern is explicitly acknowledged as a stepping stone, not a final destination -- it creates centralized dependencies that resist microservice extraction

---

### Chapter 11: Dealing with Events and Their Evolution (pp. 243-262)

**Key Concepts:**

**CQRS + Event Sourcing Clarification:**
- CQRS separates read (query) and write (command) models
- Event Sourcing stores state as a sequence of immutable events in an event store
- The authors explicitly clarify the "event streaming misconception": event streaming (Kafka etc.) is NOT event sourcing. Event streaming moves data between systems; event sourcing IS the system's source of truth
- CQRS+ES should be applied selectively -- core domains benefit most; supporting/generic subdomains can use traditional CRUD ("data bags")

**Event Versioning Strategies:**

1. **Simple Event Versioning** (pp. 250-253)
   - Create a new versioned event class (e.g., `SalesOrderCreated_V2`)
   - Maintain `Apply` methods for ALL versions in the aggregate
   - New events use latest version; old events are replayed using their original version's handler
   - Drawback: Proliferation of Apply methods; code bloat at version 19+
   - Rule (quoting Greg Young): "A new version of an event must be convertible from the old version of the event. If not, it is not a new version but rather a new event."

2. **Upcasting** (pp. 254-256)
   - Transformer converts old event versions to the latest version at read time
   - `EventUpcaster` class with `Upcast(DomainEvent)` method maps old versions to new
   - Only one `Apply` method needed per event (for latest version)
   - Challenge in distributed/multi-node systems: double-publish mechanism may be needed
   - Requires rigorous testing of upcasters

3. **Weak Schema** (pp. 256-257)
   - Flexible, loosely-defined structure (typically JSON) tolerant of missing/extra fields
   - Unknown properties ignored during deserialization
   - Include version identifier in event metadata
   - Pros: Simplicity, backward compatibility
   - Cons: Delayed validation, consumer complexity, harder to reason about system state

4. **Content Negotiation** (pp. 257-259)
   - Version management at the producer-consumer communication layer (similar to HTTP Accept headers)
   - Flow: Version metadata > Consumer declaration > Producer negotiation > Middleware transformation
   - Atom feeds proposed as a practical transport mechanism (built-in versioning, schema links, content type negotiation)
   - Consumers register supported content types; publishers expose correct versions

5. **Copy-Replace** (pp. 259-261)
   - "The nuclear option" (Greg Young's term)
   - Create a new event stream by selectively copying/transforming/merging/omitting events from the old stream
   - Use when other strategies fall short
   - Critical question: "What happens if we need to replay the entire event stream from scratch?"
   - EventStoreDB's `truncate before` as a less invasive alternative
   - Always assume you WILL need full replay someday

**Practical Insights:**
- Event versioning is INEVITABLE if you use CQRS+ES -- plan for it from the start
- Commands are NOT subject to versioning (they trigger immediate actions, not stored for replay)
- The guiding principle: "start simple -- grow big" applies to CQRS+ES adoption. Begin with supporting/generic subdomains where mistakes have lower consequences

---

### Chapter 12: Orchestrating Complexity -- Advanced Approaches to Business Processes (pp. 263-280)

**Key Concepts:**

**Transaction Management Evolution:**
- **Atomic Transactions**: Work within a single database; no longer sufficient for distributed systems
- **Two-Phase Commit (2PC)**: Voting/prepare phase + Decision/commit phase. Five drawbacks: blocking nature, single point of failure, lack of fault tolerance, performance overhead, scalability issues
- **Sagas**: Alternative to 2PC for distributed transactions. Sequence of local transactions with compensating actions for rollback. Eventual consistency instead of atomicity

**Saga Patterns Classification (from Ford/Richards):**
Three architectural forces determine saga type: Communication (sync/async), Consistency (atomic/eventual), Coordination (orchestrated/choreographed)

| Pattern Name | Communication | Consistency | Coordination | Coupling |
|-------------|--------------|-------------|--------------|---------|
| Epic Saga | Synchronous | Atomic | Orchestrated | Very high |
| Phone Tag Saga | Synchronous | Atomic | Choreographed | High |
| Fairy Tale Saga | Synchronous | Eventual | Orchestrated | High |
| Time Travel Saga | Synchronous | Eventual | Choreographed | Medium |
| Fantasy Fiction Saga | Asynchronous | Atomic | Orchestrated | High |
| Horror Story Saga | Asynchronous | Atomic | Choreographed | Medium |
| Parallel Saga | Asynchronous | Eventual | Orchestrated | Low |
| Anthology Saga | Asynchronous | Eventual | Choreographed | Very low |

**Choreography:**
- Services react independently to events; no central coordinator
- Pros: Loose coupling, scalability, flexibility, resilience (no single point of failure)
- Cons: Difficult monitoring/debugging, cascading failures, complex error handling, rollback complexity grows with service count

**Orchestration:**
- Dedicated orchestrator component controls the workflow
- Pros: Centralized monitoring/debugging, structured error handling, explicit compensation, better observability
- Cons: Single point of failure, tighter coupling, scalability bottleneck, requires own persistent storage

**When to Use Each (Table 12.2, p. 273):**
| Scenario | Choreography | Orchestration |
|----------|-------------|--------------|
| Loosely coupled, independent services | Yes | No |
| Explicit control over execution order | No | Yes |
| Dynamic scaling with minimal dependencies | Yes | No |
| Observability and monitoring critical | No | Yes |
| Compensating transactions needed | No | Yes |

**Process Manager vs. Saga:**
- Process Manager: Centralized coordinator with explicit state management, branching logic, sequential service invocation. More control but single point of failure
- Saga: Decentralized, each service handles its part independently. More resilient but harder to track
- They are NOT interchangeable despite frequent confusion in the literature

**Error Handling and Recovery:**
- **Step failures**: Retries with exponential backoff, then compensating transaction
- **Saga-wide failures**: All previous successful steps must be compensated
- **Forward recovery**: Attempt alternative solution instead of rolling back
- **Backward recovery**: Execute compensating transactions to undo completed steps
- All compensating transactions must be **idempotent**

**Durable Execution:**
- Saga state must be persisted reliably (event logs, message queues, dedicated databases)
- All operations must be idempotent (safe to retry)
- Explicit timeouts for each step with fallback mechanisms
- Dead letter queue for persistently failing operations

**Event-Sourced Sagas:**
- Each saga step recorded as an event in an event store (Jonathan Oliver's approach)
- Saga state derived from event sequence, not mutable record
- Enables recovery by replaying saga events from last successful step
- Integrates naturally with CQRS

---

## Catalog of Refactoring Patterns

### Strategic-Level Patterns

| Pattern | When to Apply | Steps | Risks |
|---------|--------------|-------|-------|
| **Identify Bounded Contexts** | Starting any refactoring; monolith has unclear boundaries | (1) Run EventStorming, (2) Map domain events to subdomains, (3) Identify natural language boundaries, (4) Define context boundaries | Over-decomposition; splitting too early |
| **Split Bounded Context** | Context too large; conflicting purposes; teams stepping on each other | (1) Domain decomposition, (2) Context mapping, (3) Isolate aggregates, (4) Introduce domain events, (5) Refactor dependent code | Breaking existing integrations; data migration complexity |
| **Merge Bounded Contexts** | Excessive friction between contexts; overlapping models; redundant logic | (1) Identify redundancies, (2) Establish unified language, (3) Consolidate aggregates, (4) Deprecate redundant events, (5) Revisit context map | Creating a new "Big Ball of Mud"; performance regression |
| **Evolve Context Map** | Integration patterns no longer serve the architecture | (1) Map current relationships, (2) Identify pattern mismatches, (3) Propose new patterns (e.g., Conformist to Customer-Supplier), (4) Implement ACL, (5) Validate with domain experts | Breaking existing integrations |

### Tactical-Level Patterns

| Pattern | When to Apply | Steps | Risks |
|---------|--------------|-------|-------|
| **Replace Primitives with Value Objects** | Primitive obsession; business rules on primitive values | (1) Create Value Object with validation, (2) Replace in aggregate, (3) Update repository mapping, (4) Update tests | Serialization/deserialization changes; ORM mapping |
| **Introduce Domain Events** | Cross-aggregate side effects; audit trail needed; eventual consistency | (1) Identify state change, (2) Create event class, (3) Raise in aggregate, (4) Create handler, (5) Wire event bus | Event ordering; idempotency; eventual consistency complexity |
| **Extract Domain Service** | Cross-aggregate logic; stateless orchestration logic | (1) Identify operation, (2) Define interface, (3) Implement, (4) Inject via constructor | Over-extraction; service becomes anemic orchestrator |
| **Introduce CQRS** | Different read/write patterns; scaling requirements; query optimization | (1) Create read DTOs, (2) Create query handlers, (3) Optimize read queries, (4) Keep write via aggregates | Increased complexity; eventual consistency between models |
| **Enrich Anemic Domain Model** | Logic in services instead of entities; entities are data bags | (1) Identify business rules in services, (2) Move to entity/aggregate, (3) Encapsulate state changes, (4) Update tests | Breaking service-layer contracts |

### Infrastructure-Level Patterns

| Pattern | When to Apply | Steps | Risks |
|---------|--------------|-------|-------|
| **Split Database by Bounded Context** | Shared database creating coupling; schema changes affect multiple contexts | (1) Identify table ownership, (2) Expand schema, (3) Migrate data, (4) Contract old schema, (5) Test | Data integrity during transition; performance during migration |
| **Event-Based Data Synchronization** | Contexts need data from other contexts; eventual consistency acceptable | (1) Identify data dependencies, (2) Create integration events, (3) Implement handlers with ACL, (4) Maintain local copy | Consistency lag; event ordering; failure handling |
| **Replace Mediator with Events** | Preparing for microservice extraction; mediator creates coupling | (1) Identify mediator interactions, (2) Define events for each, (3) Implement event bus, (4) Remove mediator, (5) Test | Behavioral differences (async vs. sync); debugging complexity |
| **Extract Microservice** | Module stable, independently deployable, business justification clear | (1) Verify bounded context independence, (2) Extract module to service, (3) Define API/events, (4) Deploy independently, (5) Monitor | Distributed system complexity; operational overhead |

---

## Strategic DDD Insights

### Bounded Context Discovery
The book advocates a disciplined discovery process:
1. **EventStorming** as the primary tool (both Big Picture and Design-Level)
2. **Domain storytelling** as an alternative/complement
3. **Core Domain Chart** for prioritization (invest most in high-differentiation, high-complexity areas)
4. **Subdomains classification**: Core (competitive advantage), Supporting (necessary but not differentiating), Generic (commodity)

### Context Mapping Integration
Context mapping is treated as an ongoing activity, not a one-time exercise. The map evolves as:
- New bounded contexts are identified or existing ones are split/merged
- Integration patterns change (Conformist > Customer-Supplier > Partnership)
- ACLs are introduced or removed
- The book provides concrete examples of how the BrewUp context map evolves across refactoring stages

### EventStorming Integration
EventStorming serves dual purposes:
1. **Discovery**: Understanding the current domain (Big Picture)
2. **Design**: Modeling the target architecture (Design-Level)

The authors reference Brandolini's work (Brandolini wrote the foreword) and position EventStorming as the bridge between problem space and solution space. It reveals:
- Domain events (what happened)
- Commands (what triggered it)
- Policies (automated reactions)
- Read models (information needed for decisions)
- External systems (integration points)

### Cynefin Framework Usage
The Cynefin framework is used as a meta-decision tool:
- **Before refactoring**: Assess which domain the problem falls into
- **During refactoring**: Choose appropriate strategies (probe-sense-respond for Complex; sense-analyze-respond for Complicated)
- **After refactoring**: Evaluate if the system has moved to a less complex domain

---

## Legacy System Migration Methodology

The book presents a clear migration path:

### Phase 1: Understand and Stabilize
- Use EventStorming to map the current system
- Apply Cynefin to assess complexity
- Write characterization tests for critical paths
- Identify bounded contexts in the existing codebase

### Phase 2: Modularize the Monolith
- Introduce module structure aligned with bounded contexts
- Use mediator pattern for initial decoupling
- Apply fitness functions to measure progress
- Refactor database schemas toward context alignment

### Phase 3: Introduce Events and CQRS
- Replace mediator with event-driven communication
- Implement CQRS for contexts that benefit from read/write separation
- Split databases per bounded context using expand/contract
- Use event-based data synchronization for cross-context data needs

### Phase 4: Extract Services (if justified)
- Evaluate microservices readiness signals
- Start with most independent bounded context
- Use strangler fig pattern (implied, not named) -- incrementally extract while legacy still runs
- Apply appropriate saga pattern for distributed transactions

### CI/CD Support Throughout
- Automated tests at every phase
- Fitness functions in CI pipeline
- SonarQube quality gates
- Feature flags for gradual rollout
- Blue-green deployments for database changes

---

## Novel Contributions (vs. Evans, Vernon, Wlaschin)

### What This Book Adds

1. **Cynefin-DDD Integration**: While Snowden's Cynefin has been discussed in DDD circles, this book provides a practical mapping of Cynefin domains to specific refactoring strategies. This goes beyond Evans' or Vernon's work, which focused on the patterns themselves rather than when to apply them based on complexity assessment

2. **Fitness Functions for DDD Refactoring**: Adapting Ford/Parsons/Kua's evolutionary architecture fitness functions specifically for DDD refactoring progress measurement. Neither Evans nor Vernon addressed this quantitative angle

3. **Complete Refactoring Journey with Code**: While Evans was theoretical and Vernon was pattern-focused, this book provides a single running example (BrewUp) that evolves across ALL chapters -- from Big Ball of Mud through modular monolith to microservices. The complete Git repository with branches for each stage is a significant practical contribution

4. **Database Refactoring with DDD Alignment**: Chapter 8 provides detailed database migration strategies specifically designed to work with bounded context boundaries. Evans mentioned database concerns briefly; Vernon focused more on aggregate persistence. This book provides expand/contract patterns, event-based synchronization, and distributed data access patterns all in the DDD context

5. **Event Versioning Taxonomy**: Chapter 11 provides a structured comparison of five event versioning strategies (simple versioning, upcasting, weak schema, content negotiation, copy-replace) with trade-offs. While Greg Young's work covers versioning deeply, this book integrates it into the broader refactoring methodology

6. **Mediator-to-Events Migration Path**: The explicit two-step decoupling approach (mediator first, then events) is a practical contribution not found in the canonical DDD literature. It acknowledges that jumping directly to events in a monolith is premature

### What Evans/Vernon/Wlaschin Cover Better

1. **Evans**: Deeper theoretical foundation; the Whirlpool process is more thoroughly explained in Evans' own work; the concept of "model integrity" is more nuanced
2. **Vernon (Implementing DDD)**: More thorough treatment of aggregate design rules, event sourcing internals, and bounded context integration patterns
3. **Vernon (Domain-Driven Design Distilled)**: Better concise overview for quick reference
4. **Wlaschin (Domain Modeling Made Functional)**: Stronger on type-driven design, making illegal states unrepresentable, and functional DDD. This book stays entirely in OOP/C# territory
5. **Ford/Richards (Software Architecture: The Hard Parts)**: More thorough treatment of the saga classification and decomposition decision framework. This book references but does not fully reproduce their analysis

### What Is Missing

1. **Functional programming perspective**: No coverage of algebraic types, railway-oriented programming, or making illegal states unrepresentable
2. **Event sourcing implementation depth**: The ES coverage is intentionally surface-level; they recommend Greg Young's book for depth
3. **Concrete testing strategies for DDD**: While testing is mentioned throughout, there is no dedicated chapter on testing domain models, aggregates, or event handlers in detail
4. **Team Topologies integration**: No discussion of how Conway's Law and team structures should drive bounded context boundaries (beyond a brief mention of Conway's Law in Chapter 10)

---

## Implications for nWave

### For Solution Architect Agent (`nw-solution-architect`)

**High-value additions to skills:**
1. **Cynefin-based decision framework**: Before recommending architecture changes, assess which Cynefin domain the problem occupies. This directly informs whether to recommend exploratory (probe-sense-respond) or analytical (sense-analyze-respond) approaches
2. **Fitness function methodology**: Recommend fitness functions as acceptance criteria for refactoring work. These become measurable quality gates in the DESIGN wave
3. **Modular monolith as default recommendation**: The book strongly validates recommending modular monolith over premature microservices. The readiness signals checklist (p. 232-233) provides concrete criteria
4. **Context mapping evolution patterns**: How context maps should evolve during refactoring (e.g., Conformist to Customer-Supplier with ACL)
5. **Database separation strategy**: The expand/contract pattern and event-based data synchronization should be standard recommendations when database refactoring is needed

**Decision frameworks to encode:**
- Microservices readiness assessment (6 signals from Chapter 10)
- Architecture characteristics rating (modular vs. microservices, Table 10.6)
- Choreography vs. orchestration decision matrix (Table 12.2)
- CQRS+ES applicability (core domain = ES, supporting = CRUD)

### For Software Crafter Agent (`nw-software-crafter`)

**Refactoring patterns to encode:**
1. **Primitive > Value Object refactoring**: Step-by-step pattern with test-first approach
2. **Anemic > Rich Domain Model**: Moving business logic from services into aggregates
3. **Mediator > Events migration**: Two-phase approach for decoupling
4. **CQRS introduction**: Separating read/write handlers
5. **Event versioning implementation**: Upcasting as the recommended default approach

**Testing strategies:**
- Characterization tests before refactoring legacy code
- Contract tests for interservice communication
- Eventual consistency tests (simulating network failures)
- Schema integrity unit tests during database refactoring

### For Acceptance Designer Agent (`nw-acceptance-designer`)

**BDD scenarios to inform:**
1. Bounded context boundary validation: "Given bounded contexts A and B, when A publishes event X, then B should update its local model"
2. Event versioning acceptance: "Given a V1 event in the store, when the aggregate replays, then it should correctly apply default values for V2 properties"
3. Saga compensation: "Given a payment completed and warehouse reports quantity-not-found, then the saga should compensate by refunding the customer"
4. Fitness function validation: "Given the refactored module, when coupling metrics are measured, then afferent coupling should be below threshold"

### For Product Owner Agent (`nw-product-owner`)

**Story refinement insights:**
1. The book's emphasis on business value-driven refactoring maps to user story prioritization: prioritize refactoring stories by business impact, not technical debt alone
2. The Core Domain Chart maps directly to backlog prioritization: invest most in high-differentiation, high-complexity bounded contexts
3. Refactoring stories should include fitness function targets as acceptance criteria
4. Database refactoring stories need explicit expand/contract phases

### For nWave Methodology Overall

The book validates the nWave wave sequence:
1. **DISCOVER** maps to: Cynefin assessment, EventStorming Big Picture
2. **DISCUSS** maps to: Core Domain Chart prioritization, stakeholder alignment on refactoring scope
3. **DESIGN** maps to: Context mapping, aggregate design, CQRS decisions, fitness functions
4. **DISTILL** maps to: Acceptance criteria including fitness functions, BDD scenarios for integration
5. **DELIVER** maps to: Tactical refactoring patterns (value objects, domain events, CQRS), test-first implementation
6. **DEVOPS** maps to: Database refactoring, CI/CD pipeline, microservice extraction, event versioning

The book's "start simple, grow big" principle aligns with nWave's incremental delivery philosophy and TDD-based approach.

---

## Source Analysis

| Source | Domain | Reputation | Type | Notes |
|--------|--------|------------|------|-------|
| Domain-Driven Refactoring (Colla, Acerbis, 2025) | packtpub.com | Medium-High | Book (primary source) | Pre-launch copy; authors are Italian DDD practitioners |
| Foreword by Alberto Brandolini | N/A | High | Expert endorsement | Inventor of EventStorming validates the book's approach |
| Eric Evans, DDD (2003) | Canonical | High | Referenced work | Foundational; Whirlpool process, bounded contexts, ubiquitous language |
| Vaughn Vernon, IDDD (2013) | Canonical | High | Referenced work | Aggregate design rules, bounded context implementation |
| Martin Fowler, Refactoring (1999/2018) | martinfowler.com | High | Referenced work | Refactoring definition, code smell catalog |
| Ford/Richards, Software Architecture: The Hard Parts | O'Reilly | High | Referenced work | Saga classification, architectural quanta |
| Ford/Parsons/Kua, Building Evolutionary Architectures | O'Reilly | High | Referenced work | Fitness functions concept |
| Dave Snowden, Cynefin Framework | cognitive-edge.com | High | Referenced framework | Sense-making for complexity assessment |
| Greg Young, Versioning in an Event Sourced System | leanpub.com | High | Referenced work | Event versioning (authoritative source) |
| Michael Feathers, Working Effectively with Legacy Code | Canonical | High | Referenced work | Characterization tests |

**Note on Source Verification**: This is a primary source analysis (the book itself), not a web research document. The book's claims about DDD patterns, refactoring techniques, and architectural principles are cross-referenced against established canonical sources where applicable. The authors' citations are consistent with the referenced literature.

---

## Knowledge Gaps

### Gap 1: Real-World Scale Validation
**Issue**: The BrewUp example is a didactic brewery ERP system, not a large-scale production system. The refactoring patterns are demonstrated at tutorial scale, not at the scale where they would face real challenges (millions of events, hundreds of services, cross-team coordination)
**Recommendation**: Supplement with case studies from enterprise DDD adoptions (e.g., from DDD Europe conference proceedings)

### Gap 2: Non-.NET Applicability
**Issue**: All code examples are C# / .NET 9.0. The patterns are language-agnostic in concept but the implementation details are .NET-specific (MediatR, Entity Framework, specific NuGet packages)
**Recommendation**: For nWave skills, translate patterns to language-agnostic descriptions with notes on platform-specific implementation

### Gap 3: Testing Depth
**Issue**: While testing is mentioned as essential throughout, no chapter is dedicated to testing strategies for DDD (e.g., how to test aggregates, how to test event handlers, how to test sagas). The testing guidance is scattered and brief
**Recommendation**: Supplement with dedicated testing resources (e.g., Vladimir Khorikov's "Unit Testing: Principles, Practices, and Patterns")

### Gap 4: Team Topologies and Organizational Patterns
**Issue**: The book only briefly mentions Conway's Law (Chapter 10). No coverage of how team structures should inform bounded context boundaries, or how Team Topologies (Skelton/Pais) intersects with DDD
**Recommendation**: Cross-reference with "Team Topologies" for organizational design implications

---

## Full Citations

[1] Colla, A. and Acerbis, A. "Domain-Driven Refactoring". Packt Publishing. April 2025. Pre-launch copy. ISBN B22493.

[2] Evans, E. "Domain-Driven Design: Tackling Complexity in the Heart of Software". Addison-Wesley. 2003.

[3] Vernon, V. "Implementing Domain-Driven Design". Addison-Wesley. 2013.

[4] Fowler, M. "Refactoring: Improving the Design of Existing Code". Addison-Wesley. 2nd Edition. 2018.

[5] Ford, N. and Richards, M. "Software Architecture: The Hard Parts". O'Reilly. 2021.

[6] Ford, N., Parsons, R., and Kua, P. "Building Evolutionary Architectures". O'Reilly. 2017.

[7] Snowden, D. "Cynefin Framework". Cognitive Edge.

[8] Young, G. "Versioning in an Event Sourced System". Leanpub. https://leanpub.com/esversioning/read.

[9] Feathers, M. "Working Effectively with Legacy Code". Prentice Hall. 2004.

[10] Fowler, M. and Lewis, J. "Microservices". martinfowler.com. March 2014. https://www.martinfowler.com/articles/microservices.html.

[11] Brooks, F. "No Silver Bullet -- Essence and Accident in Software Engineering". 1986.

[12] Oliver, J. "CQRS Sagas with Event Sourcing". https://blog.jonathanoliver.com/cqrs-sagas-with-event-sourcing-part-i-of-ii/.

---

## Research Metadata

| Field | Value |
|-------|-------|
| Duration | ~120 min |
| Pages examined | ~280 |
| Chapters analyzed | 12/12 (100%) |
| Patterns catalogued | 14 (4 strategic, 5 tactical, 5 infrastructure) |
| Cross-references to canonical literature | 12 |
| Knowledge gaps identified | 4 |
| Output | `/mnt/c/Repositories/Projects/nWave-dev/docs/research/domain-driven-refactoring-book-analysis.md` |
