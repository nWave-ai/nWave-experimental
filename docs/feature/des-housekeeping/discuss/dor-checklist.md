# Definition of Ready: DES Housekeeping

Validation date: 2026-02-26

---

## US-HK-01: Audit Log Retention

| DoR Item | Status | Evidence |
|----------|--------|----------|
| Problem statement clear | PASS | "Kenji's .nwave/des/logs/ contains 30+ audit log files totaling 60MB after six weeks of daily usage" -- specific persona, measurable accumulation, concrete impact |
| User/persona identified | PASS | Kenji Nakamura, full-stack developer, daily nWave user across 3 projects; Sofia Reyes, team with 30-day compliance requirement |
| 3+ domain examples | PASS | 4 examples: standard cleanup (21-day span), custom retention (30-day), empty directory, permission error |
| UAT scenarios (3-7) | PASS | 6 scenarios: happy path, custom config, empty state, permission error, performance, today's log safety |
| AC derived from UAT | PASS | 5 acceptance criteria directly traceable to scenarios |
| Right-sized (1-3 days) | PASS | 1 day estimate. Single concern: date-based file deletion with glob pattern. 6 scenarios. |
| Technical notes | PASS | Filename parsing (not mtime), integration point (session_start_handler.py), fail-open pattern, today's log protection |
| Dependencies tracked | PASS | Depends on US-HK-04 for integration, or can be built standalone and integrated later. No external dependencies. |

**DoR Status: PASSED**

---

## US-HK-02: Orphaned Signal File Cleanup

| DoR Item | Status | Evidence |
|----------|--------|----------|
| Problem statement clear | PASS | "Stale des-task-active-* signal file from dead session causes DES to behave as if a subagent is already running" -- specific failure mode, user-observable impact |
| User/persona identified | PASS | Priya Sharma (crash recovery), Tomasz (concurrent sessions), Elena (stale deliver session), Carlos (multiple orphans) |
| 3+ domain examples | PASS | 4 examples: crash recovery, concurrent session safety, stale deliver session, multiple orphans |
| UAT scenarios (3-7) | PASS | 7 scenarios: orphan removal, concurrent safety, deliver-session removal, deliver-session preservation, multiple orphans, empty state, custom threshold |
| AC derived from UAT | PASS | 5 acceptance criteria covering signal files, deliver-session.json, concurrent safety, configuration, missing directory |
| Right-sized (1-3 days) | PASS | 1 day estimate. Single concern: mtime-based staleness check on glob pattern. 7 scenarios. |
| Technical notes | PASS | Mtime-based staleness, glob pattern for signal files, 4-hour default rationale, secondary created_at check option |
| Dependencies tracked | PASS | Depends on US-HK-04 for integration. Uses existing signal file patterns from claude_code_hook_adapter.py (no new deps). |

**DoR Status: PASSED**

---

## US-HK-03: Skill Tracking Log Rotation

| DoR Item | Status | Evidence |
|----------|--------|----------|
| Problem statement clear | PASS | "skill-loading-log.jsonl has grown to 15MB with thousands of entries; old entries have no diagnostic value but nothing trims it" -- measurable growth, clear waste |
| User/persona identified | PASS | Kenji (15MB log, active tracking), Sofia (400KB normal log), Amir (tracking disabled) |
| 3+ domain examples | PASS | 3 examples: oversized truncation, normal-sized skip, tracking disabled |
| UAT scenarios (3-7) | PASS | 5 scenarios: truncation, skip, missing file, locked file error, custom threshold |
| AC derived from UAT | PASS | 5 acceptance criteria covering truncation, threshold skip, missing file, failure isolation, configuration |
| Right-sized (1-3 days) | PASS | 1 day estimate. Single concern: size-check then tail-truncate a JSONL file. 5 scenarios. |
| Technical notes | PASS | Tail-based truncation, JSONL line independence, size check as first gate, file path from JsonlSkillTracker constant |
| Dependencies tracked | PASS | Depends on US-HK-04 for integration. Uses .nwave/skill-loading-log.jsonl path from JsonlSkillTracker. |

**DoR Status: PASSED**

---

## US-HK-04: Housekeeping Orchestration and Configuration

| DoR Item | Status | Evidence |
|----------|--------|----------|
| Problem statement clear | PASS | "Three housekeeping tasks need to run as a coordinated unit at session start; must never block or delay the session" -- clear orchestration problem |
| User/persona identified | PASS | Kenji (defaults), Sofia (custom config), Tomasz (disabled), plus integration with existing session_start_handler |
| 3+ domain examples | PASS | 4 examples: default config, custom overrides, disabled, partial failure |
| UAT scenarios (3-7) | PASS | 6 scenarios: all defaults, partial failure, disabled, no .nwave, performance, update check coexistence |
| AC derived from UAT | PASS | 8 acceptance criteria covering integration, isolation, performance, output, config, defaults, disable, missing directory |
| Right-sized (1-3 days) | PASS | 1-2 day estimate. Orchestration shell + DESConfig extension + session_start_handler integration. 6 scenarios. |
| Technical notes | PASS | Integration into session_start_handler.py, DESConfig extension pattern, separate service module, try/except per task, 500ms budget |
| Dependencies tracked | PASS | Depends on US-HK-01/02/03 being implemented (or stubbed for Outside-In TDD). Extends DESConfig (existing, no external deps). |

**DoR Status: PASSED**

---

## Summary

| Story | DoR Status | Estimated Effort | Scenarios |
|-------|-----------|-----------------|-----------|
| US-HK-01: Audit Log Retention | PASSED | 1 day | 6 |
| US-HK-02: Signal File Cleanup | PASSED | 1 day | 7 |
| US-HK-03: Skill Log Rotation | PASSED | 1 day | 5 |
| US-HK-04: Orchestration | PASSED | 1-2 days | 6 |

**All 4 stories pass Definition of Ready.** Ready for handoff to DESIGN wave.

### Recommended Build Order (Outside-In TDD)

1. **US-HK-04** first — build the orchestration shell with the DESConfig extension and session_start_handler integration, calling stub/interface methods for each task
2. **US-HK-01, US-HK-02, US-HK-03** in parallel — fill in the concrete implementations behind the interfaces

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Housekeeping exceeds 500ms budget on slow filesystems | Low | Low | Network FS users can increase threshold via config; local FS ops are fast |
| Concurrent session signal file incorrectly deleted | Low | Medium | 4-hour threshold is generous (typical tasks < 30 min); configurable for safety |
| File permission issues on cleanup | Low | Low | Fail-open per-file; skip and continue pattern |
