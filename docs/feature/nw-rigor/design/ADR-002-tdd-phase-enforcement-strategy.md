# ADR-002: TDD Phase Enforcement Strategy for Rigor Profiles

## Status

Accepted

## Context

The lean profile reduces TDD to 2 phases (RED_UNIT, GREEN). The DES hook system validates step completion via `StepCompletionValidator`, which currently requires all 5 TDD phases. When a lean-mode agent completes only RED_UNIT and GREEN, the validator would flag PREPARE, RED_ACCEPTANCE, and COMMIT as abandoned -- a false positive.

Two enforcement levels exist:
1. **Command-level** (markdown): deliver.md tells the orchestrator which phases to include in the DES template
2. **Hook-level** (Python): StepCompletionValidator checks execution-log.yaml after agent returns

Both must agree on which phases are expected.

## Decision

**Parameterize StepCompletionValidator** to accept a phase override. The caller (hook adapter) reads rigor config via DESConfig and passes the expected phase tuple. Validator uses this override instead of TDDSchema.tdd_phases when provided.

Flow:
1. Hook adapter loads DESConfig at validation time
2. Reads `rigor_tdd_phases` property
3. Passes phase tuple to StepCompletionValidator
4. Validator checks events against the provided phases only

The `TDDSchema` remains unchanged (always defines all 5 canonical phases). Rigor narrows the enforcement window, not the schema.

## Alternatives Considered

### Alternative A: Command-Level Only (No Hook Changes)

Trust the command file to send the right phases. Don't validate at hook level. Let the agent complete whatever phases the command tells it.

**Rejected because**:
- DES hooks exist specifically to catch agents that skip phases
- Without hook enforcement, a lean agent that fails to complete even RED_UNIT goes undetected
- Breaks the DES integrity guarantee

### Alternative B: Multiple TDDSchema Instances

Create per-profile TDDSchema objects with different tdd_phases tuples. Schema loader picks one based on rigor config.

**Rejected because**:
- TDDSchema is an immutable singleton loaded from the canonical JSON file
- Creating profile-specific schemas duplicates phase definitions across config layers
- Over-complicates the cache-once-per-process design

### Alternative C: Parameterized Validator (Selected)

StepCompletionValidator.validate() accepts optional `expected_phases` parameter. When provided, overrides `self._schema.tdd_phases` for that validation call.

**Selected because**:
- Single-line change to validator interface (optional parameter with default)
- No changes to TDDSchema
- Hook adapter already has access to DESConfig
- Easy to test: pass different phase sets, verify different validation results

## Consequences

- **Positive**: Clean separation -- schema defines canonical phases, rigor narrows enforcement
- **Positive**: Backward compatible -- omitting the parameter uses schema defaults (standard behavior)
- **Negative**: Hook adapter gains a dependency on DESConfig for rigor reading
- **Mitigation**: DESConfig is already available in the adapter layer; no new wiring needed
