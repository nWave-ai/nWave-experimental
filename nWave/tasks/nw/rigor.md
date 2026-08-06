---
description: "Selects a quality-vs-token-consumption profile (lean, standard, thorough, exhaustive, custom, inherit) and persists it globally (~/.nwave/global-config.json) or per-project (.nwave/des-config.json). Use when tuning how much rigor wave commands apply."
disable-model-invocation: true
argument-hint: '[profile] - Optional: lean, standard, thorough, exhaustive, custom, inherit. Omit for interactive selection.'
---

# NW-RIGOR: Quality Profile Selection

**Wave**: CROSS_WAVE | **Agent**: Main Instance (self) | **Command**: `/nw-rigor [profile]`

## Overview

Select a quality-vs-token-consumption profile and persist it under the `rigor` key in `~/.nwave/global-config.json` (global) or `.nwave/des-config.json` (project). All wave commands read it to set agent models, review policy, examination depth, and refactoring effort. The executable-AT delivery floor is fixed, not a profile choice. You (the main Claude instance) run this directly — no subagent delegation.

## Methodology — Load the Skill (SSOT)

The full methodology — the Profile Mappings table (Single Source of Truth), the three-mode behavior flow, scope selection, save semantics, error handling, and examples — lives in the `nw-rigor` skill. Load it before acting; do not re-derive any of it here.

**Load**: `~/.claude/skills/nw-rigor/SKILL.md`

## Invocation Contract

- `/nw-rigor` — Mode 1 (Interactive Selection): welcome → scope → comparison table → select → detail → confirm → save → summary.
- `/nw-rigor <preset>` — Mode 2 (Quick Switch). `<preset>` ∈ {lean, standard, thorough, exhaustive, inherit}: validate → scope → diff → confirm → save.
- `/nw-rigor custom` — Mode 3 (Custom Builder): scope → per-setting questions → summary → confirm → save as `profile: custom`.
- Profiles: **lean, standard [recommended], thorough, exhaustive, custom, inherit** (semantics in the skill's Profile Mappings table).
- Scope: **global** (`~/.nwave/global-config.json`) or **project** (`.nwave/des-config.json`) — asked in every mode.
- Save is read-modify-write: set `config["rigor"]`, preserve all other top-level keys; auto-create `~/.nwave/` on first global save.

## Progress Tracking

Create a task list from the skill's mode steps at the start using TaskCreate. Each step is a task with its gate as the completion criterion; mark in_progress on entry, completed on gate pass.

## Success Criteria

- [ ] `nw-rigor` skill loaded before acting (methodology read, not re-derived)
- [ ] Current profile displayed (or "none set")
- [ ] Scope question asked (global vs project) in all 3 modes
- [ ] Comparison table shown with all 5 profiles
- [ ] User selected and confirmed a profile
- [ ] Config written to the chosen target file (read-modify-write, other keys preserved)
- [ ] `~/.nwave/` directory auto-created on first global save
- [ ] Summary of all resolved settings displayed (including scope and target file path)
