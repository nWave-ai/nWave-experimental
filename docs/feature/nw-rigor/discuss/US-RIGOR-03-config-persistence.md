# US-RIGOR-03: Rigor Config Persistence and Recovery

## Problem
Priya Sharma is a tech lead who set her team's rigor profile to "standard" yesterday. Today she opens a new Claude Code session and runs `/nw:deliver`, expecting standard behavior. But if the config was not properly persisted -- or was corrupted by a concurrent write -- her profile is lost and she gets unpredictable behavior without knowing it. She needs config persistence to be reliable, with clear recovery when things go wrong.

## Who
- Tech Lead | Sets profile once, expects it to persist across sessions | Needs reliability
- Developer | Runs concurrent Claude Code sessions | Needs config to survive race conditions

## Solution
Rigor profile is persisted in `.nwave/des-config.json` using read-modify-write pattern with backup on corruption detection. The config is the single source of truth -- no caching, no environment variables, no shadow state.

## Domain Examples

### 1: Config survives session restart
Kai Nakamura sets profile to "lean" via `/nw:rigor`. He closes Claude Code, opens a new session, and runs `/nw:deliver`. The deliver command reads des-config.json, finds rigor.profile = "lean", and proceeds with lean settings. No prompt, no re-selection required.

### 2: Corrupted config triggers safe recovery
Priya Sharma's des-config.json was truncated by a disk-full error: `{"audit_logging_enabled": true, "rigor": {"prof`. When she runs `/nw:rigor`, nWave detects invalid JSON, backs up the file as `des-config.json.bak`, creates a fresh config with defaults, and shows "Config file corrupted. Resetting to defaults (backup saved)." Priya proceeds with selection.

### 3: Merge preserves unrelated config keys
Tomasz Kowalski's des-config.json contains `{"audit_logging_enabled": true, "skill_tracking": "passive-logging"}`. When he runs `/nw:rigor` and selects "inherit", the write adds the rigor block without touching audit_logging_enabled or skill_tracking. The final JSON contains all three top-level keys.

## UAT Scenarios (BDD)

### Scenario 1: Profile persists across sessions
Given Kai Nakamura set rigor profile to "lean" in a previous Claude Code session
And .nwave/des-config.json contains rigor.profile = "lean"
When Kai opens a new Claude Code session
And Kai runs /nw:deliver "update version number"
Then the deliver orchestrator reads rigor.profile = "lean" from des-config.json
And proceeds with lean settings (haiku agent, no review, RED/GREEN only)

### Scenario 2: Read-modify-write preserves other config
Given .nwave/des-config.json contains:
  | key                     | value            |
  | audit_logging_enabled   | true             |
  | skill_tracking          | passive-logging  |
When Kai runs /nw:rigor and selects "standard"
Then .nwave/des-config.json contains audit_logging_enabled = true
And .nwave/des-config.json contains skill_tracking = "passive-logging"
And .nwave/des-config.json contains rigor.profile = "standard"

### Scenario 3: Corrupted JSON triggers backup and reset
Given .nwave/des-config.json contains truncated invalid JSON
When Priya runs /nw:rigor
Then nWave creates .nwave/des-config.json.bak with the corrupted content
And nWave displays "Config file corrupted. Resetting to defaults (backup saved as des-config.json.bak)."
And Priya can proceed with profile selection normally
And the new des-config.json is valid JSON

### Scenario 4: Missing .nwave directory blocks with clear message
Given the .nwave/ directory does not exist in the project root
When Kai runs /nw:rigor
Then nWave displays "No nWave config directory found. Run nwave install first."
And no files are created

### Scenario 5: Profile update overwrites only rigor block
Given .nwave/des-config.json contains rigor.profile = "lean"
When Kai runs /nw:rigor standard and confirms
Then rigor.profile is updated to "standard"
And all rigor sub-fields are updated to match the standard profile
And no other top-level config keys are modified

## Acceptance Criteria
- [ ] Rigor config is written to .nwave/des-config.json under "rigor" key using read-modify-write pattern
- [ ] Existing config keys (audit_logging_enabled, skill_tracking, etc.) are preserved during rigor writes
- [ ] Corrupted JSON is detected, backed up as .bak, and replaced with valid defaults
- [ ] Missing .nwave/ directory produces a clear error message directing user to install
- [ ] Config is the single source of truth -- no environment variable overrides for rigor profile
- [ ] Profile persists across Claude Code sessions (file-based, no in-memory-only state)

## Technical Notes
- DESConfig (`src/des/adapters/driven/config/des_config.py`) already handles missing/corrupted JSON gracefully -- extend this for rigor
- Read-modify-write must handle the case where another process writes concurrently (last-write-wins is acceptable for MVP)
- Backup file should use `.bak` extension (single backup, overwritten on subsequent corruptions)
- No environment variable override for rigor (unlike audit_logging which has DES_AUDIT_LOGGING_ENABLED) -- rigor is always from config file

## Traceability
- **Job 2**: Understand what I am giving up before I choose (config reliability is prerequisite for trust)
