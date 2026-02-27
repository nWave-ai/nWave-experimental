# US-RIGOR-02: Wave Commands Honor Rigor Profile

## Problem
Kai Nakamura is a senior developer who selected "lean" profile via `/nw:rigor` to quickly fix a README typo. But when he runs `/nw:deliver`, it still dispatches opus agents, runs full 5-phase TDD, and triggers peer review -- because wave commands do not read the rigor configuration. His profile selection was meaningless, and he burned the same tokens he was trying to save.

## Who
- Developer | Has set a rigor profile | Expects all wave commands to respect that choice consistently
- Tech Lead | Set team default to standard | Expects predictable behavior across all team members' sessions

## Solution
All wave commands (`/nw:deliver`, `/nw:design`, `/nw:execute`, `/nw:review`, `/nw:distill`) read the rigor profile from `.nwave/des-config.json` at invocation time and adjust their behavior: model selection for agents and reviewers, TDD phase set, review gating, mutation testing gating, and refactoring pass.

## Domain Examples

### 1: Lean deliver skips review and mutation
Kai Nakamura has profile "lean" active. He runs `/nw:deliver "fix typo in README"`. The deliver orchestrator reads rigor config, dispatches a haiku crafter, runs only RED_UNIT and GREEN phases, skips peer review (Phase 4), skips mutation testing (Phase 5), and skips the dedicated refactoring pass (Phase 3). Total time: ~3 minutes, ~70K tokens.

### 2: Thorough deliver activates all gates
Priya Sharma has profile "thorough" active for her rate-limiting feature. She runs `/nw:deliver "implement rate limiting"`. The deliver orchestrator dispatches an opus crafter, runs all 5 TDD phases, runs double peer review with sonnet reviewer (Phase 4 runs twice), runs mutation testing requiring 80% kill rate (Phase 5), and includes a refactoring pass (Phase 3). Total time: ~20 minutes, ~450K tokens.

### 3: Inherit profile resolves model at execution time
Tomasz Kowalski has profile "inherit" active. He started his Claude Code session with haiku. When he runs `/nw:design "plan caching layer"`, the design command detects agent_model = "inherit", resolves it to "haiku" (current session model), and dispatches the solution-architect with haiku. Later, Tomasz switches to opus in Claude Code and runs `/nw:deliver`. Now the crafter runs with opus -- no need to re-run `/nw:rigor`.

### 4: No profile defaults to standard behavior
Maria Santos just installed nWave and has never run `/nw:rigor`. She runs `/nw:deliver "add logging"`. The deliver orchestrator finds no rigor key in des-config.json, defaults to standard behavior (sonnet agent, haiku reviewer, full TDD, single review, no mutation), and proceeds normally. Maria sees no prompt or warning about missing profile.

## UAT Scenarios (BDD)

### Scenario 1: Lean profile reduces deliver ceremony
Given Kai Nakamura has rigor profile "lean" in .nwave/des-config.json
When Kai runs /nw:deliver "fix typo in README"
Then the deliver orchestrator dispatches the crafter agent with model "haiku"
And the TDD cycle includes only RED_UNIT and GREEN phases
And Phase 3 (refactoring pass) is skipped
And Phase 4 (peer review) is skipped
And Phase 5 (mutation testing) is skipped

### Scenario 2: Thorough profile activates all quality gates
Given Priya Sharma has rigor profile "thorough" in .nwave/des-config.json
When Priya runs /nw:deliver "implement rate limiting for API"
Then the deliver orchestrator dispatches the crafter agent with model "opus"
And the TDD cycle includes all 5 phases: PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT
And Phase 3 (refactoring pass) runs with L1-L4 levels
And Phase 4 (peer review) runs twice with model "sonnet" for the reviewer
And Phase 5 (mutation testing) runs with minimum 80% kill rate gate

### Scenario 3: Inherit profile resolves to session model
Given Tomasz Kowalski has rigor profile "inherit" in .nwave/des-config.json
And Tomasz is running Claude Code with opus as the current model
When Tomasz runs /nw:execute "project-id" "01-01"
Then the execute command resolves agent_model "inherit" to "opus"
And the crafter agent is dispatched with model "opus"
And TDD runs full 5-phase cycle (standard-level checks)
And peer review uses haiku reviewer

### Scenario 4: Missing profile defaults to standard
Given Maria Santos has .nwave/des-config.json with no "rigor" key
When Maria runs /nw:deliver "add structured logging"
Then the deliver orchestrator uses sonnet for the crafter agent
And the deliver orchestrator uses haiku for the reviewer
And TDD runs full 5-phase cycle
And peer review runs once
And mutation testing is skipped
And no warning or prompt about missing rigor profile is shown

### Scenario 5: Design command respects rigor model
Given Kai has rigor profile "lean" active
When Kai runs /nw:design "plan caching layer"
Then the design command dispatches solution-architect with model "haiku"
And review of the design uses the rigor reviewer_model setting

### Scenario 6: Profile change mid-session affects subsequent commands
Given Priya starts with rigor profile "lean"
And Priya completes /nw:deliver "fix config" with lean settings
When Priya runs /nw:rigor thorough and confirms
And Priya runs /nw:deliver "implement authentication"
Then the second deliver uses opus crafter, sonnet reviewer, double review, mutation testing
And the first deliver's results are unchanged

## Acceptance Criteria
- [ ] /nw:deliver reads rigor config and adjusts: agent model, reviewer model, TDD phases, review gating (single/double/skip), mutation gating, refactoring pass
- [ ] /nw:design reads rigor config and adjusts: agent model, reviewer model
- [ ] /nw:execute reads rigor config and adjusts: agent model, TDD phases
- [ ] /nw:review reads rigor config and adjusts: reviewer model; skip entirely when review_enabled = false
- [ ] "inherit" model is resolved to current session model at command execution time, not at config save time
- [ ] Missing rigor config defaults to standard behavior silently (no prompt, no warning)
- [ ] Lean profile TDD cycle enforces RED_UNIT and GREEN only (tests are still mandatory)
- [ ] Thorough profile double review dispatches the reviewer agent twice with separate review scopes

## Technical Notes
- DESConfig needs a `rigor` property exposing all sub-fields with defaults matching "standard"
- Wave command files (`nWave/tasks/nw/*.md`) need instructions to read rigor config
- DES orchestrator needs to pass model parameter through to Task tool invocations
- "inherit" resolution mechanism: read current model from Claude Code session context
- TDD phase enforcement: DES hooks must respect the reduced phase set for lean profile
- Lean profile still requires tests to pass -- RED/GREEN is minimum, not zero tests

## Traceability
- **Job 1**: Calibrate quality investment to match the stakes
- **Job 3**: Preserve my model choice without fighting the framework
