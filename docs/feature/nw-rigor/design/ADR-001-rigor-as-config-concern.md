# ADR-001: Rigor as Configuration Concern, Not Domain Concept

## Status

Accepted

## Context

Rigor profiles control agent model selection, TDD phase depth, review gating, and mutation testing. The question: should rigor be a first-class domain concept (new domain entity, port interface, dedicated service) or a configuration concern (properties on DESConfig, instructions in command files)?

The existing DES architecture has a clear separation:
- **Domain layer**: Phase events, turn counter, timeout, TDD schema -- pure business rules
- **Config adapter**: DESConfig loads settings, exposes typed properties
- **Command files**: Markdown instructions that tell the orchestrating Claude instance what to do

Rigor affects HOW commands invoke agents (model parameter, phase selection) but does not introduce new business rules. The profile mappings are static lookups, not domain logic.

## Decision

Rigor is a **configuration concern**. Implementation:
- DESConfig gets rigor properties (read-only, with standard defaults)
- Command files get rigor-reading instructions (markdown-level integration)
- StepCompletionValidator accepts configurable phase set (parameterization, not new logic)
- No new domain entities, ports, or services

## Alternatives Considered

### Alternative A: Full Domain Model

New `RigorProfile` domain entity, `RigorPort` driven port, `RigorService` application service, `RigorAdapter` driven adapter.

**Rejected because**:
- Over-engineers a static lookup table into a domain model
- Adds 4+ new files for what is essentially 5 named config presets
- Profile resolution has no complex business rules (no validation beyond "is it one of 5 strings?")
- Violates simplest-solution-first principle

### Alternative B: Rigor as TDD Schema Extension

Extend `TDDSchema` with multiple phase sets, one per rigor profile. Schema loader picks the right set based on config.

**Rejected because**:
- TDD schema is loaded from `step-tdd-cycle-schema.json` (single source of truth for phase definitions)
- Mixing profile-specific phase subsets into the schema conflates "what phases exist" with "which phases to enforce"
- Schema is immutable and process-cached; rigor can change per command invocation

### Alternative C: Config Concern (Selected)

DESConfig exposes rigor properties. Command files read config and adjust behavior.

**Selected because**:
- Minimal code changes (3 properties on DESConfig, 1 parameter on validator)
- Aligns with existing patterns (skill_tracking, audit_logging follow same approach)
- Command files already control agent dispatch -- adding rigor instructions is natural
- No new abstractions to maintain

## Consequences

- **Positive**: Minimal blast radius; follows established DESConfig patterns; no new modules
- **Positive**: Profile mappings live in `/nw:rigor` command (single source); DESConfig just reads what was written
- **Negative**: Profile-to-settings mapping logic lives in markdown (rigor.md), not in Python -- not unit-testable
- **Mitigation**: DESConfig properties are unit-testable; command file behavior is acceptance-testable via BDD scenarios
