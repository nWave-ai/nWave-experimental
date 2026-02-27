# JTBD Analysis: /nw:rigor

**Epic**: nw-rigor
**Date**: 2026-02-25
**Method**: Jobs-to-be-Done extraction from stakeholder evidence + Four Forces analysis

---

## Evidence Sources

1. User reports: "quality checks take time" (multiple users)
2. User reports: "token burn rate is too high" (multiple users)
3. Andrea Laforgia (team member): proposed low-to-high consumption tiers
4. Alessandro Di Gioia (product owner): endorsed lower models, rejected weakening TDD/discussion

---

## Job Stories

### Job 1: Calibrate quality investment to match the stakes

> **When** I am working on a low-stakes change (docs fix, config tweak, experimental spike),
> **I want to** reduce the ceremony nWave applies so I do not wait 15 minutes and burn 200K tokens for a one-line change,
> **So that** I can ship proportionally to the risk without abandoning the nWave workflow entirely.

**Job type**: Core functional
**Frequency**: Multiple times per day (experienced users)
**Satisfaction gap**: HIGH -- users currently have no way to reduce ceremony; all-or-nothing

### Job 2: Understand what I am giving up before I choose

> **When** I am choosing a quality profile for my session,
> **I want to** see exactly what each level includes and excludes, with honest token and time estimates,
> **So that** I make an informed tradeoff rather than discovering surprises mid-delivery.

**Job type**: Emotional (confidence, informed consent)
**Frequency**: Once per session or project setup
**Satisfaction gap**: HIGH -- currently no visibility into what quality checks cost

### Job 3: Preserve my model choice without fighting the framework

> **When** I have already selected a specific model in Claude Code (for cost, speed, or capability reasons),
> **I want to** nWave to respect that choice rather than overriding it,
> **So that** my session model preference and nWave's quality checks work together instead of conflicting.

**Job type**: Consumption chain (integration with existing workflow)
**Frequency**: Every session for users who set model preferences
**Satisfaction gap**: MEDIUM -- workaround is ignoring nWave's model recommendations

---

## Four Forces Analysis

### Job 1: Calibrate quality investment

| Force | Description |
|-------|-------------|
| **Push (current pain)** | "I waited 8 minutes for a config change because nWave ran full TDD + review + mutation" |
| **Pull (desired outcome)** | "Quick changes should feel quick. Serious changes should feel serious." |
| **Habit (inertia)** | "I just skip nWave for small changes and use raw Claude Code" |
| **Anxiety (switching cost)** | "If I lower quality, will I miss a real bug? Will my team judge me?" |

### Job 2: Understand the tradeoff

| Force | Description |
|-------|-------------|
| **Push** | "I have no idea how many tokens a review costs or whether mutation testing is worth it" |
| **Pull** | "I want to see a clear comparison table before committing" |
| **Habit** | "I just accept whatever nWave does and complain about cost later" |
| **Anxiety** | "What if the estimates are wrong and I blow my budget anyway?" |

### Job 3: Preserve model choice

| Force | Description |
|-------|-------------|
| **Push** | "I set Haiku in Claude Code for speed, but nWave ignores it" |
| **Pull** | "nWave should be a collaborator, not an overrider" |
| **Habit** | "I just let nWave do whatever it wants with models" |
| **Anxiety** | "If I use inherit, do I lose quality checks?" |

---

## Opportunity Scoring

| Job | Importance (1-10) | Satisfaction (1-10) | Opportunity Score |
|-----|-------------------|---------------------|-------------------|
| J1: Calibrate quality | 9 | 2 | **16** (9 + (9 - 2)) |
| J2: Understand tradeoff | 8 | 1 | **15** (8 + (8 - 1)) |
| J3: Preserve model choice | 6 | 3 | **9** (6 + (6 - 3)) |

**Priority**: J1 > J2 > J3 (but J2 is integral to J1's delivery -- you cannot calibrate without understanding)

---

## Personas

### Kai Nakamura -- The Pragmatic Crafter
- Senior developer, daily nWave user
- Works on mix of critical features and routine maintenance
- Frustrated by uniform ceremony: "I spent 180K tokens on a README fix"
- Values: speed for low-stakes, rigor for high-stakes
- Context: 3-person team, shared Anthropic API budget of $500/month

### Priya Sharma -- The Budget-Conscious Tech Lead
- Manages a team of 4 using nWave
- Tracks monthly token spend in a spreadsheet
- Needs to justify AI tooling cost to management
- Values: predictability, cost visibility, team-wide defaults
- Context: Enterprise team, quarterly budget reviews

### Tomasz Kowalski -- The Model-Opinionated Developer
- Runs Claude Code with Haiku for rapid prototyping
- Switches to Opus only for complex architectural work
- Wants nWave to respect his explicit model choice
- Values: control, no surprises, integration harmony
- Context: Solo developer, personal API key

---

## Non-Jobs (Explicitly Out of Scope)

- "I want to disable all quality checks" -- This is not compatible with nWave's philosophy. `/nw:rigor lean` still enforces RED/GREEN TDD.
- "I want per-command rigor" -- Session-level is the right granularity. Per-command creates decision fatigue.
- "I want to define custom profiles" -- The four profiles cover the spectrum. Custom profiles add complexity without proportional value.
