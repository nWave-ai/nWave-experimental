# JTBD Analysis: Auto-Update Check

**Epic**: nw-update
**Date**: 2026-02-25
**Method**: Jobs-to-be-Done extraction from GitHub issue evidence + Four Forces analysis

---

## Evidence Sources

1. GitHub issue #11 (RTodorov): "what is the right way to keep my nWave setup up to date?"
2. Inferred from issue: no notification mechanism exists; users discover updates by chance
3. Persona synthesis: Priya Sharma (team lead, predictability), Kai Nakamura (daily user, breaking changes)

---

## Job Stories

### Job 1: Know when a new nWave version is available without actively checking

> **When** I open a new Claude Code session,
> **I want to** be told automatically if a newer version of nWave is available,
> **So that** I am never unknowingly running a stale framework that may be missing fixes or causing issues.

**Job type**: Core functional
**Frequency**: Every session start (passive) -- action taken only when update exists
**Satisfaction gap**: HIGH -- no mechanism exists; users file issues asking how to stay current

---

### Job 2: Understand what changed before deciding to update

> **When** I am notified that a new nWave version is available,
> **I want to** see a summary of what changed (especially breaking changes and new features),
> **So that** I can decide whether to update now, wait, or skip this version with confidence rather than anxiety.

**Job type**: Emotional (confidence, informed consent)
**Frequency**: Every time a notification is shown
**Satisfaction gap**: HIGH -- even if a notification existed, blind "update now?" without context would cause anxiety for Kai and Priya

---

### Job 3: Control how often update checks interrupt my session

> **When** I have set a preference for update check frequency,
> **I want to** nWave to respect it across sessions without asking again,
> **So that** I am not interrupted every session but also not forgotten about when updates accumulate.

**Job type**: Consumption chain (integration with existing workflow)
**Frequency**: Configuration set once, respected until changed
**Satisfaction gap**: MEDIUM -- users vary: RTodorov wants to know ASAP, Priya wants weekly digest, some users want silence

---

### Job 4: Update in one action from the notification

> **When** I decide I want to update after reading the changelog summary,
> **I want to** trigger the update without leaving Claude Code or remembering the pip command,
> **So that** the upgrade path is as simple as the awareness path.

**Job type**: Core functional (reduce friction to action)
**Frequency**: Every accepted update
**Satisfaction gap**: MEDIUM -- current workaround requires knowing `pip install --upgrade nwave-ai && nwave install`

---

## Four Forces Analysis

### Job 1: Know when a new version is available

| Force | Description |
|-------|-------------|
| **Push (current pain)** | "I had no idea there was a new version. I found out by accident when checking PyPI." (RTodorov) |
| **Pull (desired outcome)** | "The framework tells me when it has news for me -- like a good tool should." |
| **Habit (inertia)** | "I just use whatever version I installed and assume it is current." |
| **Anxiety (switching cost)** | "What if the check slows down my session start? What if it errors and blocks me?" |

### Job 2: Understand what changed

| Force | Description |
|-------|-------------|
| **Push** | "I updated once and something broke. Now I am scared to update without knowing what changed." (Kai) |
| **Pull** | "A one-paragraph summary of what is new is all I need to make a decision." |
| **Habit** | "I skip the changelog and just accept whatever the update brings." |
| **Anxiety** | "What if the changelog summary is misleading and I still get surprised by a breaking change?" |

### Job 3: Control check frequency

| Force | Description |
|-------|-------------|
| **Push** | "I do not want 'update available' noise every session. I check updates weekly." (Priya) |
| **Pull** | "One setting, set once, forgotten. The tool respects my rhythm." |
| **Habit** | "I ignore repeated notifications until they annoy me enough to act." |
| **Anxiety** | "If I set 'weekly', will I miss a critical security fix?" |

### Job 4: Update in one action

| Force | Description |
|-------|-------------|
| **Push** | "I have to remember the pip command AND run nwave install after. I always forget the second step." (RTodorov) |
| **Pull** | "One confirmation and the tool updates itself. Done." |
| **Habit** | "I copy the pip command from the readme and run it manually." |
| **Anxiety** | "What if the update breaks my current session or corrupts my config?" |

---

## Opportunity Scoring

| Job | Importance (1-10) | Satisfaction (1-10) | Opportunity Score |
|-----|-------------------|---------------------|-------------------|
| J1: Know when available | 9 | 1 | **17** (9 + (9 - 1)) |
| J2: Understand what changed | 8 | 2 | **14** (8 + (8 - 2)) |
| J3: Control frequency | 7 | 3 | **11** (7 + (7 - 3)) |
| J4: Update in one action | 7 | 2 | **12** (7 + (7 - 2)) |

**Priority**: J1 > J2 > J4 > J3
(J1 and J2 are tightly coupled -- notification without context creates anxiety; J4 closes the loop on J1+J2; J3 prevents J1 from becoming noise)

---

## Personas

### RTodorov -- The Curious Installer
- Developer who installed nWave and asked "how do I keep it updated?"
- Does not want to track a GitHub repo manually
- Values: automation, sensible defaults, zero ceremony
- Context: Solo developer, personal project use

### Kai Nakamura -- The Breaking-Change-Wary Daily User
- Uses nWave every working day
- Had a bad experience with a silent breaking change in another tool
- Reads changelogs before updating production tooling
- Values: transparency, control over when things change, predictability
- Context: Team of 3, shared workflow, cannot afford mid-sprint surprises

### Priya Sharma -- The Team Lead With Predictable Windows
- Manages a team of 4 using nWave
- Updates team tools on Fridays to avoid mid-week disruption
- Values: scheduled awareness, not per-session noise, team-wide consistency
- Context: Enterprise team, weekly tool-maintenance window

---

## Non-Jobs (Explicitly Out of Scope)

- "I want nWave to auto-update without asking me" -- Silent auto-update is too risky for a CLI framework with TDD enforcement. User consent is required.
- "I want a full changelog rendered in the terminal" -- Long changelogs create scrollback pollution. A salient summary linking to full notes is the right boundary.
- "I want update checks on resume/compact/clear" -- Only `SessionStart` with `source: startup` fires once per new session. Resume and compact are mid-session and would interrupt flow.
- "I want version pinning per project" -- Version pinning is a project-level concern handled by `pyproject.toml` or lockfiles, not the update notifier.
