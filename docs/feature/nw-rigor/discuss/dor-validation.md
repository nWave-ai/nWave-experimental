# Definition of Ready Validation: nw-rigor Epic

**Date**: 2026-02-25
**Validator**: Luna (nw-product-owner)

---

## US-RIGOR-01: Interactive Rigor Profile Selection

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "wasteful to wait 8 minutes and burn 180K tokens for a one-line README fix" -- specific pain, domain terms |
| 2 | User/persona with specific characteristics | PASS | Kai (senior dev, daily nWave, mixed stakes), Priya (tech lead, budget tracking), Tomasz (model-opinionated, haiku preference) |
| 3 | 3+ domain examples with real data | PASS | 5 examples: Kai/standard, Priya/quick-switch-lean, Tomasz/inherit-haiku, Kai/thorough-security, Priya/corrupted-config |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 7 scenarios covering happy path, quick switch, loss display, inherit, config merge, invalid input, back navigation |
| 5 | AC derived from UAT | PASS | 8 AC items, each traceable to one or more scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 7 scenarios, ~2-3 days effort (interactive TUI + config write + comparison table) |
| 7 | Technical notes: constraints/dependencies | PASS | DESConfig extension, config schema, inherit resolution timing, wave command cross-cut noted |
| 8 | Dependencies resolved or tracked | PASS | DESConfig dependency tracked, wave command integration tracked as US-RIGOR-02 |

**Result: PASS (8/8)**

---

## US-RIGOR-02: Wave Commands Honor Rigor Profile

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "wave commands do not read the rigor configuration" -- profile selection was meaningless |
| 2 | User/persona with specific characteristics | PASS | Kai (lean for README fix), Priya (thorough for rate limiting), Tomasz (inherit with session model), Maria (new user, no profile) |
| 3 | 3+ domain examples with real data | PASS | 4 examples: lean deliver, thorough deliver, inherit design, missing profile default |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 6 scenarios covering lean, thorough, inherit, missing, design, mid-session change |
| 5 | AC derived from UAT | PASS | 8 AC items covering all wave commands and edge cases |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 6 scenarios, ~2-3 days (cross-cutting change to multiple command files + DES config) |
| 7 | Technical notes: constraints/dependencies | PASS | DESConfig property, wave command files, DES hooks, inherit resolution mechanism, lean TDD enforcement |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RIGOR-01 (config must exist), US-RIGOR-03 (config persistence) |

**Result: PASS (8/8)**

---

## US-RIGOR-03: Rigor Config Persistence and Recovery

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "config was corrupted... profile is lost and she gets unpredictable behavior without knowing it" |
| 2 | User/persona with specific characteristics | PASS | Priya (sets profile once, expects persistence), Kai (cross-session persistence), Tomasz (merge preservation) |
| 3 | 3+ domain examples with real data | PASS | 3 examples: session restart, corrupted config, merge preservation |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 5 scenarios covering persistence, merge, corruption, missing dir, update |
| 5 | AC derived from UAT | PASS | 6 AC items each traceable to scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 5 scenarios, ~1-2 days (extend DESConfig, add backup logic) |
| 7 | Technical notes: constraints/dependencies | PASS | DESConfig extension, read-modify-write, .bak backup, no env var override |
| 8 | Dependencies resolved or tracked | PASS | DESConfig class identified, concurrency model noted (last-write-wins for MVP) |

**Result: PASS (8/8)**

---

## Epic Summary

| Story | DoR | Scenarios | Effort Est. | Priority |
|-------|-----|-----------|-------------|----------|
| US-RIGOR-01 | 8/8 PASS | 7 | 2-3 days | P1 (enables all others) |
| US-RIGOR-03 | 8/8 PASS | 5 | 1-2 days | P1 (foundation) |
| US-RIGOR-02 | 8/8 PASS | 6 | 2-3 days | P2 (depends on 01 + 03) |

**Recommended implementation order**: US-RIGOR-03 (config) -> US-RIGOR-01 (interactive command) -> US-RIGOR-02 (wave integration)

**Total estimated effort**: 5-8 days
**Total scenarios**: 18
