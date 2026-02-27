# Opportunity Scoring: Multi-Platform nWave Support

**Date**: 2026-02-27 (updated 2026-02-27 — added outcomes #13-15: Plugin Marketplace)
**Scoring method**: Ulwick's ODI — Opportunity = Importance + max(0, Importance - Satisfaction)
**Data source**: Team estimate based on persona analysis and research findings (not user survey)
**Confidence**: Medium (team estimate, no direct user data)

---

## Outcome Statements and Scores

Importance and Satisfaction rated as estimated % of target users who would rate 4+ on a 5-point scale.

| # | Outcome Statement | Imp. (%) | Sat. (%) | Score | Priority |
|---|-------------------|----------|----------|-------|----------|
| 1 | Minimize the likelihood of losing TDD discipline when switching AI platforms | 85 | 10 | 16.0 | Extremely Underserved |
| 2 | Minimize the time to share methodology knowledge across team members using different tools | 80 | 15 | 14.5 | Underserved |
| 3 | Minimize the likelihood of vendor lock-in blocking enterprise adoption evaluation | 75 | 5 | 14.5 | Underserved |
| 4 | Minimize the cost per development session while maintaining methodology discipline | 70 | 20 | 12.0 | Underserved |
| 5 | Minimize the number of platform-specific adaptations needed for skill files | 70 | 60 | 8.0 | Overserved |
| 6 | Minimize the time to access specialized agent expertise from any coding platform | 75 | 15 | 13.5 | Underserved |
| 7 | Minimize the likelihood of inconsistent code quality across a team using mixed tools | 80 | 10 | 15.0 | Extremely Underserved |
| 8 | Maximize the likelihood that DES enforcement works identically on all platforms | 65 | 0 | 13.0 | Underserved |
| 9 | Minimize the time to resume work on an alternative platform during outages | 60 | 5 | 11.5 | Appropriately Served |
| 10 | Minimize the likelihood that multi-platform support degrades Claude Code experience | 90 | 80 | 10.0 | Appropriately Served |
| 11 | Minimize the maintenance burden of supporting multiple platform adapters | 55 | 20 | 9.0 | Overserved |
| 12 | Maximize the number of AI platforms where nWave methodology is available | 50 | 5 | 9.5 | Overserved |
| 13 | Minimize the time to install nWave and start using structured TDD | 90 | 30 | 15.0 | Extremely Underserved |
| 14 | Minimize the effort to keep nWave agents and skills up to date | 75 | 20 | 13.0 | Underserved |
| 15 | Minimize the effort to deploy nWave across an engineering team | 80 | 10 | 15.0 | Extremely Underserved |

---

## Interpretation

### Top Opportunities (Score >= 12) — Invest

| Rank | # | Outcome | Score | Implication |
|------|---|---------|-------|-------------|
| 1 | 1 | TDD discipline across platforms | 16.0 | Core value proposition. DES portability is the most important AND least satisfied outcome. |
| 2 | 13 | **Time to install and start** | **15.0** | **Plugin marketplace collapses install from 30min to 1 command. Highest-ROI intervention.** |
| 3 | 15 | **Team-wide deployment effort** | **15.0** | **Enterprise managed plugins (`extraKnownMarketplaces`) = zero per-developer install.** |
| 4 | 7 | Team code quality consistency | 15.0 | Team leads care deeply about this. Skills + agents partially address it; DES fully addresses it. |
| 5 | 2 | Knowledge sharing across tools | 14.5 | Cross-platform skills are the lowest-cost, highest-impact intervention. |
| 6 | 3 | Vendor lock-in for enterprise | 14.5 | Even architectural proof (not full parity) unlocks enterprise conversations. |
| 7 | 6 | Agent expertise access | 13.5 | Agent catalog portability — moderate effort, high perceived value. |
| 8 | 14 | **Auto-update agents/skills** | **13.0** | **Plugin auto-update eliminates manual reinstall. Free with plugin packaging.** |
| 9 | 8 | DES parity across platforms | 13.0 | Users want identical enforcement. Partial enforcement may frustrate more than none. |
| 10 | 4 | Cost optimization | 12.0 | Model-agnostic support enables significant cost savings for budget-conscious users. |

### Appropriately Served (Score 10-12) — Maintain

| # | Outcome | Score | Note |
|---|---------|-------|------|
| 9 | Resume on alt platform during outage | 11.5 | Nice-to-have, not a primary driver |
| 10 | Do not degrade Claude Code experience | 10.0 | Critical constraint (protect existing users), but currently well-satisfied |

### Overserved (Score < 10) — Simplify or Deprioritize

| # | Outcome | Score | Note |
|---|---------|-------|------|
| 5 | Skill format adaptation | 8.0 | Already nearly solved — SKILL.md standard works across platforms |
| 11 | Maintenance burden | 9.0 | Internal concern, not user-facing — manage via architecture |
| 12 | Number of platforms | 9.5 | Users want depth (quality on 2 platforms) over breadth (presence on 4) |

---

## Opportunity Map

```
                    HIGH IMPORTANCE
                         |
    [1] TDD Discipline   |   [10] No Claude Degradation
         (16.0)          |        (10.0)
  ★ [13] Install Time    |
         (15.0)          |
  ★ [15] Team Deploy     |
         (15.0)          |
    [7] Team Quality     |
         (15.0)          |
    [3] Vendor Lock-in   |
         (14.5)          |
    [2] Knowledge Share  |
         (14.5)          |
    [6] Agent Access     |
         (13.5)          |
  ★ [14] Auto-Update     |
         (13.0)          |
    [8] DES Parity       |
         (13.0)          |
    [4] Cost Optimize    |
         (12.0)          |
    [9] Outage Resume    |
         (11.5)          |   [5] Skill Format (8.0)
                         |
  -------UNDERSERVED-----|----OVERSERVED---------
                         |
                         |   [12] Platform Count (9.5)
                         |   [11] Maintenance (9.0)
                         |
                    LOW IMPORTANCE

★ = Plugin marketplace outcomes (NEW)
```

---

## Strategic Implications

### 1. Skills portability is the "free" win

Outcome #5 (skill format adaptation) scores 8.0 — overserved. This means the open agent skills standard (SKILL.md) already solves cross-platform skill portability. The investment needed is minimal (installer path changes). Ship this immediately.

### 2. DES portability is the high-risk, high-reward bet

Outcomes #1 (16.0) and #8 (13.0) are the top opportunity AND the hardest technical challenge. The research shows DES enforcement requires:
- **Claude Code**: Full support today (baseline)
- **OpenCode**: Partial (tool.execute.before exists but subagent bypass bug blocks enforcement)
- **Copilot CLI**: Partial (hooks exist but cwd-scoped, not global)
- **Codex CLI**: Impossible (no PreToolUse hook exists)

The MCP server approach could bypass platform-specific hook limitations by running DES as a tool that agents must call — but this changes the enforcement model from "system intercepts" to "agent cooperates."

### 3. Agent catalog has moderate opportunity

Outcome #6 (13.5) is underserved. Agent format compatibility:
- **OpenCode**: Compatible (MD + YAML frontmatter)
- **Copilot CLI**: Compatible (.agent.md + YAML frontmatter)
- **Codex CLI**: Incompatible (TOML sections, no per-file agents)

Three of four platforms can host nWave agents. Worth investing.

### 4. Protect the Claude Code experience

Outcome #10 (10.0) is critical as a constraint, not an opportunity. Any multi-platform work must not regress the Claude Code experience. This means platform abstraction must be additive, not refactoring the existing Claude Code path.

### 5. Depth over breadth

Outcome #12 (9.5) confirms users want quality on fewer platforms, not presence on all four. Focus on Claude Code (existing) + ONE additional platform done well, rather than spreading thin across all three.

### 6. Plugin marketplace is the highest-ROI investment (NEW)

Outcomes #13 (15.0), #15 (15.0), and #14 (13.0) are all Extremely Underserved or Underserved. Combined, they represent the single largest cluster of unmet need — and they are the **cheapest to address**.

Why cheapest: nWave's component model (agents, skills, commands, hooks, MCP servers) maps 1:1 to the Claude Code plugin spec. Packaging nWave as a plugin is primarily a structural reorganization, not feature development. The plugin system provides auto-updates, version management, enterprise distribution (`extraKnownMarketplaces`), and project-scoped install for free.

**Cost-benefit comparison**:
- Plugin packaging: ~2-3 weeks effort, addresses outcomes #13/#14/#15 (combined score: 43.0)
- Cross-platform Phase 1: ~6-8 weeks effort, addresses outcomes #2/#3/#6 (combined score: 42.5)
- DES MCP Server: ~8-10 weeks effort, addresses outcomes #1/#8 (combined score: 29.0)

The plugin marketplace delivers nearly equivalent opportunity score to Phase 1 at **one-third the cost**. It should be the immediate priority — before any cross-platform work.

### 7. Plugin marketplace + cross-platform are complementary, not competing

The plugin marketplace addresses Claude Code users' adoption friction (Persona G). Cross-platform addresses non-Claude-Code users' platform needs (Personas B, E, F). These are different user segments with different jobs. The optimal sequence is: plugin first (maximize Claude Code adoption) → cross-platform second (expand TAM).
