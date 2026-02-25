# Component Boundaries: nw-rigor

## Component Map

```
nWave/tasks/nw/rigor.md          [NEW]  -- Interactive UI, profile persistence
nWave/tasks/nw/deliver.md        [MOD]  -- Rigor-aware orchestration
nWave/tasks/nw/execute.md        [MOD]  -- Rigor-aware single step dispatch
nWave/tasks/nw/design.md         [MOD]  -- Rigor-aware design dispatch
nWave/tasks/nw/review.md         [MOD]  -- Rigor-aware review dispatch
nWave/tasks/nw/distill.md        [MOD]  -- Rigor-aware distill dispatch
nWave/framework-catalog.yaml     [MOD]  -- Register /nw:rigor command
src/des/adapters/driven/config/des_config.py  [MOD]  -- Rigor properties
src/des/domain/step_completion_validator.py    [MOD]  -- Phase set parameter
```

## Boundary Rules

### rigor.md owns

- Profile comparison table (all 7 artifact mappings for all 5 profiles)
- Interactive selection flow (display, detail, confirm)
- Config write (read-modify-write to des-config.json)
- Profile-to-settings mapping (which profile maps to which concrete values)

### rigor.md does NOT own

- How wave commands use the settings (each command owns its own dispatch logic)
- DES hook validation behavior
- Config read (DESConfig owns that)

### DESConfig owns

- Reading `rigor` key from des-config.json
- Providing typed properties with standard defaults
- Handling missing/malformed rigor data gracefully

### DESConfig does NOT own

- Writing config (rigor.md does that)
- Deciding what to do with rigor values (commands/hooks decide)

### StepCompletionValidator owns

- Validating phase events against an expected phase set
- Classifying errors (abandoned, incomplete, invalid skip)

### StepCompletionValidator does NOT own

- Deciding which phases are expected (caller provides this)
- Reading config (caller reads DESConfig, passes phase tuple)

## Data Flow

```
User -> /nw:rigor -> des-config.json    (write path)

des-config.json -> DESConfig -> wave command -> Task(model=X)    (read path: commands)
des-config.json -> DESConfig -> hook adapter -> StepCompletionValidator(phases=Y)    (read path: hooks)
```

## Interface Contracts

### DESConfig new properties

| Property | Return Type | Default | Description |
|----------|-------------|---------|-------------|
| `rigor_profile` | `str` | `"standard"` | Active profile name |
| `rigor_settings` | `dict[str, Any]` | standard preset | Full rigor dict |
| `rigor_tdd_phases` | `tuple[str, ...]` | 5-phase tuple | Expected TDD phases |
| `rigor_agent_model` | `str` | `"sonnet"` | Model for agent dispatch |
| `rigor_reviewer_model` | `str` | `"haiku"` | Model for reviewer dispatch |
| `rigor_review_enabled` | `bool` | `True` | Whether review phase runs |
| `rigor_double_review` | `bool` | `False` | Whether review runs twice |
| `rigor_mutation_enabled` | `bool` | `False` | Whether mutation gate runs |
| `rigor_refactor_pass` | `bool` | `True` | Whether refactor phase runs |

### StepCompletionValidator.validate() change

Current: `validate(self, events: list[PhaseEvent]) -> CompletionResult`
New: `validate(self, events: list[PhaseEvent], expected_phases: tuple[str, ...] | None = None) -> CompletionResult`

When `expected_phases` is provided, use it instead of `self._schema.tdd_phases`. Backward compatible.

## Profile Defaults (Canonical Reference)

| Setting | lean | standard | thorough | exhaustive | inherit |
|---------|------|----------|----------|------------|---------|
| agent_model | haiku | sonnet | opus | opus | inherit |
| reviewer_model | skip | haiku | sonnet | opus | haiku |
| tdd_phases | [RED_UNIT, GREEN] | [PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT] | same | same | same |
| review_enabled | false | true | true | true | true |
| double_review | false | false | true | true | false |
| mutation_enabled | false | false | false | true | false |
| refactor_pass | false | true | true | true | true |

These defaults live in DESConfig as a static mapping. When the config file has explicit values, those take precedence.
