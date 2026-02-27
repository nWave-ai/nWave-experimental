# US-RIGOR-01: Interactive Rigor Profile Selection

## Problem
Kai Nakamura is a senior developer who uses nWave daily for both critical features and routine maintenance. He finds it wasteful to wait 8 minutes and burn 180K tokens for a one-line README fix because nWave applies the same full ceremony (5-phase TDD, peer review, refactoring pass) to every change regardless of stakes. His workaround is skipping nWave entirely for small changes, which means those changes get zero quality checks.

## Who
- Developer | Daily nWave user working on mixed-stakes changes | Wants to match quality investment to risk level
- Tech Lead | Managing team token budget | Wants predictable cost per quality level
- Model-opinionated developer | Already chose their model in Claude Code | Wants nWave to respect that choice

## Solution
An interactive `/nw:rigor` command that guides the user through selecting one of five quality profiles (lean, standard, thorough, exhaustive, inherit), showing a comparison table, detailed gains/losses for the selected profile, and persisting the choice to `.nwave/des-config.json` for all subsequent wave commands.

## Domain Examples

### 1: Kai selects standard for feature work
Kai Nakamura is starting a new feature (rate limiting for the API). He runs `/nw:rigor`, sees the comparison table with standard marked as [recommended], selects "2" (standard), reviews the detail view showing sonnet agents + haiku reviewers + full TDD + single review, confirms, and sees the session summary. His subsequent `/nw:deliver` uses sonnet for the crafter and haiku for the reviewer.

### 2: Priya quick-switches to lean for a config fix
Priya Sharma has been working in standard profile all morning. She needs to fix a typo in `pyproject.toml`. She runs `/nw:rigor lean` (quick switch), sees the diff showing she will lose peer review and PREPARE/COMMIT phases, confirms, fixes the typo via `/nw:deliver`, then runs `/nw:rigor standard` to switch back for her next feature.

### 3: Tomasz selects inherit to keep his haiku session
Tomasz Kowalski launched Claude Code with haiku for rapid prototyping. He runs `/nw:rigor`, selects "inherit", and the detail view shows "Your current session model: haiku" with standard-level quality checks. When he later switches to opus in Claude Code for complex work, nWave automatically uses opus for subsequent commands without Tomasz re-running `/nw:rigor`.

### 4: Kai tries thorough for a security-critical change
Kai is implementing authentication token validation. He runs `/nw:rigor thorough`, sees the cost warning (~180% tokens, ~20 min per step), confirms because this code is security-sensitive. His `/nw:deliver` runs opus agents, sonnet reviewers, double review, full TDD, and mutation testing with 80% kill rate gate.

### 5: Priya encounters corrupted config
Priya runs `/nw:rigor` but des-config.json was corrupted by a failed write. nWave displays "Config file corrupted. Resetting to defaults." and backs up the old file. Priya proceeds with profile selection as normal, and her audit_logging setting is preserved from the backup where possible.

## UAT Scenarios (BDD)

### Scenario 1: Happy path -- interactive selection of standard profile
Given Kai Nakamura has no rigor profile configured in .nwave/des-config.json
When Kai runs /nw:rigor
Then nWave displays a comparison table showing lean, standard, thorough, inherit side by side
And "standard" is marked as [recommended]
And each profile shows agent model, reviewer model, review policy, TDD phases, mutation, estimated cost percentage, and estimated time
When Kai enters "2" to select standard
Then nWave shows the detail view for standard listing what Kai gets and what is not included
When Kai enters "Y" to confirm
Then .nwave/des-config.json contains a "rigor" key with profile "standard", agent_model "sonnet", reviewer_model "haiku", review_enabled true, mutation_enabled false
And nWave displays a session confirmation showing all resolved settings

### Scenario 2: Quick switch skips comparison table
Given Priya Sharma has rigor profile set to "standard" in .nwave/des-config.json
When Priya runs /nw:rigor lean
Then nWave shows a diff of what changes: agent sonnet->haiku, reviewer haiku->skip, review yes->no, TDD 5-phase->RED/GREEN
And the diff highlights what Priya will LOSE (peer review, PREPARE phase, COMMIT phase)
When Priya enters "Y" to confirm
Then .nwave/des-config.json rigor.profile is updated to "lean"

### Scenario 3: Lean profile detail shows explicit losses
Given Kai runs /nw:rigor and selects "lean"
Then the detail view contains a "WHAT YOU LOSE" section listing: no peer review, no PREPARE phase, no COMMIT phase, no mutation testing, no refactoring pass
And the detail view shows estimated token savings of ~60% vs standard
And the detail view shows "Haiku may struggle with complex architectural decisions"

### Scenario 4: Inherit resolves to current session model
Given Tomasz Kowalski is running Claude Code with haiku as the session model
When Tomasz runs /nw:rigor and selects "inherit"
Then the detail view shows "Your current session model: haiku"
And quality checks (TDD phases, review) are at standard level
When Tomasz confirms
Then .nwave/des-config.json contains rigor.agent_model = "inherit"

### Scenario 5: Config merge preserves existing settings
Given .nwave/des-config.json contains {"audit_logging_enabled": true, "skill_tracking": "passive-logging"}
When Kai runs /nw:rigor and selects "standard"
Then .nwave/des-config.json still contains audit_logging_enabled = true
And .nwave/des-config.json still contains skill_tracking = "passive-logging"
And .nwave/des-config.json additionally contains the rigor configuration block

### Scenario 6: Invalid profile name shows helpful error
Given Kai runs /nw:rigor
When Kai enters "turbo" as the profile selection
Then nWave displays "Unknown profile 'turbo'. Available: lean, standard, thorough, inherit"
And the comparison table is shown again for re-selection

### Scenario 7: Back navigation from detail view
Given Kai is viewing the detail view for "lean" after selecting it
When Kai enters "back"
Then nWave returns to the comparison table
And no profile change has been saved

## Acceptance Criteria
- [ ] Comparison table displays all 4 profiles with: agent model, reviewer model, review policy, TDD phases, mutation testing, estimated cost (% of standard), estimated time per step
- [ ] "standard" is visually marked as [recommended] in the comparison table
- [ ] Detail view for every profile contains both a "gains" section and a "losses" section (or "costs" for thorough)
- [ ] Quick switch syntax `/nw:rigor {name}` bypasses comparison table and shows diff + confirmation
- [ ] Profile selection persists to .nwave/des-config.json under "rigor" key without overwriting other config keys
- [ ] Invalid input at any step shows a helpful message and allows retry without restarting
- [ ] "back" from detail view returns to comparison table; "n" at confirmation cancels without saving
- [ ] Session confirmation summary shows all resolved settings (model, reviewer, TDD phases, review, mutation)

## Technical Notes
- Config storage: `.nwave/des-config.json` under `"rigor"` key (see shared-artifacts-registry.md for schema)
- Must merge into existing config -- read-modify-write, never overwrite entire file
- `inherit` model resolution happens at command execution time, not at `/nw:rigor` time
- Default when no profile set: behave as `standard` (no prompt, no blocking)
- Dependency: DESConfig class (`src/des/adapters/driven/config/des_config.py`) needs a `rigor` property
- Dependency: All wave command files need to read rigor config (cross-cutting change)

## Traceability
- **Job 1**: Calibrate quality investment to match the stakes
- **Job 2**: Understand what I am giving up before I choose
- **Job 3**: Preserve my model choice without fighting the framework
