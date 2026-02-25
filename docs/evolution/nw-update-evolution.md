# Evolution: nw-update — SessionStart Hook for Automatic Version Check Notifications

**Project**: nWave DES (Deterministic Execution System)
**Feature**: nw-update — automatic update check on session start
**Branch**: `feat/nwave-update-command`
**Wave**: DELIVER (completed)
**Date**: 2026-02-25
**Status**: Complete — adversarial review passed, mutation testing >= 80% kill rate

---

## Executive Summary

**Feature Delivered**: SessionStart hook integration that automatically checks for nwave-ai updates on each Claude Code session start. When a newer version is available on PyPI, users receive an `additionalContext` notification in their session containing the version delta and GitHub release changelog.

**Implementation Scope**: 12 commits, 4 new source files, 3 extended source files, 65 tests across unit, acceptance, and integration layers — all passing.

**Quality Achievement**: L1-L4 refactoring applied, adversarial review passed (4 findings addressed), mutation kill rate >= 80%.

---

## Motivation

nwave-ai is distributed via PyPI. Users installing via `pip install nwave-ai` would not receive automatic update notifications — they could run stale versions of the framework indefinitely without knowing. The SessionStart hook in Claude Code provides a clean injection point: before any session activity, silently check whether a newer version is published, and surface actionable context when it is.

Design constraints driving the implementation:
- **Zero session-blocking**: a failed update check must never prevent Claude Code from starting.
- **Frequency control**: checking PyPI on every session for users with long-running projects adds latency for negligible value. The frequency gate (every_session/daily/weekly/never) gives users control.
- **Minimal footprint**: no new runtime dependencies, no background processes, no cron jobs. Pure stdlib (urllib, importlib.metadata).

---

## Architecture Decisions

### ADR-1: SessionStart hook over periodic background check

**Decision**: Implement update checks as a Claude Code `SessionStart` hook, not as a scheduled background process or pre-command hook.

**Rationale**: The SessionStart hook fires exactly once per Claude Code session, before any user interaction. This matches the mental model users have for "is my tooling up to date?" — a question asked at the start of a work session, not mid-command. PreToolUse hooks fire per tool invocation (too frequent); scheduled jobs require OS-level setup (too heavy); PostToolUse hooks fire after the fact (too late for session context).

**Rejected alternatives**:
1. OS-level cron job — requires OS-specific installation complexity, outside Claude Code lifecycle.
2. PreToolUse on every Task invocation — check would fire dozens of times per session.

### ADR-2: PyPI as version detection source, GitHub for changelog

**Decision**: Fetch version from `https://pypi.org/pypi/nwave-ai/json` (authoritative release registry), then fetch changelog from GitHub Releases API only when an update is detected.

**Rationale**: PyPI is the source of truth for installed package versions — it is the same registry users install from. GitHub Releases provides structured release notes that add value to the notification. The two-step design avoids GitHub API calls when no update is available (common case).

**Design details**:
- PyPI response parsed for `info.version` — no version pinning or range logic needed.
- GitHub tag normalisation: strips leading `v` (`v2.0.0` matches `2.0.0`) to handle both tagging conventions.
- Changelog capped at 2000 characters before `additionalContext` injection — protects token budget against large release bodies.

### ADR-3: Fail-open architecture

**Decision**: Every error path in the SessionStart handler returns exit code 0 and emits no output. The outer `try/except Exception` in `handle_session_start()` is intentional.

**Rationale**: The adversarial principle here is inverted: the threat is blocking the user's session, not missing an update notification. PyPI being unreachable (network partitioned, CI sandbox, air-gapped environment) must not stop work. A missed update notification is recoverable; a blocked session is not.

**Exceptions silently swallowed**:
- Network failures (urllib errors, timeouts)
- JSON parse failures (malformed PyPI response)
- DESConfig IO errors (state persistence is best-effort)
- Any unexpected exception in the service or handler

### ADR-4: Frequency gate in domain layer via UpdateCheckPolicy

**Decision**: Frequency evaluation lives in `UpdateCheckPolicy` (domain), not in the service or handler.

**Rationale**: Frequency windows (daily=24h, weekly=168h) are pure business rules with no I/O dependencies. Placing them in the domain layer allows exhaustive unit testing without any mocking, consistent with the `MaxTurnsPolicy` pattern already established in DES. The service layer (`UpdateCheckService`) calls the policy and owns I/O coordination.

**First-run detection**: When `update_check` config key is entirely absent (fresh install), `frequency=None` and `last_checked=None` are passed to the policy. Rule 3 triggers a CHECK — ensuring the user receives their first notification immediately.

### ADR-5: update_check_frequency returns str|None to enable first-run Rule 3

**Decision**: `DESConfig.update_check_frequency` returns `None` (not `'daily'`) when the `update_check` key is absent from the config file.

**Rationale**: Returning `'daily'` as a default would suppress the first-run check if the user's config predates nw-update (no `update_check` section written yet). Returning `None` threads the "absent config = first run" signal through to the policy without requiring the service to special-case it. `save_update_check_state()` bootstraps `'daily'` as the default on first write, ensuring subsequent sessions use a sensible default.

---

## Files Modified and What Changed

### New source files

| File | Purpose |
|------|---------|
| `src/des/domain/update_check_policy.py` | `UpdateCheckPolicy` — pure domain rule evaluating frequency windows, skipped-version lists, first-run detection. Returns `CheckDecision` enum. |
| `src/des/application/update_check_service.py` | `UpdateCheckService` — fetches PyPI version and GitHub changelog, applies frequency gate, persists `last_checked`. Fail-open on all network/parse errors. |
| `src/des/adapters/drivers/hooks/session_start_handler.py` | `handle_session_start()` — Claude Code hook entry point. Reads stdin, invokes service, writes `additionalContext` JSON to stdout when `UPDATE_AVAILABLE`. |

### Extended source files

| File | Change |
|------|--------|
| `src/des/adapters/driven/config/des_config.py` | Added `update_check_frequency`, `update_check_last_checked`, `update_check_skipped_versions` properties; added `save_update_check_state()`. Frequency returns `None` when key absent (first-run detection). |
| `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py` | Added `session-start` entry to dispatch table, routing to `handle_session_start()`. |
| `scripts/install/plugins/des_plugin.py` | Registered `SessionStart` hook in Claude Code hook configuration; bootstrapped `update_check` defaults into DES config on install. |

### New test files (65 tests total across feature)

| File | Layer | Tests |
|------|-------|-------|
| `tests/des/unit/domain/test_update_check_policy.py` | Unit | Policy rules: never, skipped versions, first-run, every_session, daily/weekly windows |
| `tests/des/unit/application/test_update_check_service.py` | Unit | Version comparison, UP_TO_DATE, UPDATE_AVAILABLE, PyPI fetch failure |
| `tests/des/unit/application/test_update_check_service_changelog.py` | Unit | GitHub changelog fetch, tag normalisation, 2000-char cap, missing changelog |
| `tests/des/unit/application/test_update_check_service_frequency.py` | Unit | Frequency gate integration with DESConfig, first-run default, last_checked persistence |
| `tests/des/unit/adapters/driven/config/test_des_config_update_check.py` | Unit | DESConfig update_check properties, None-for-absent contract, save/load round-trip |
| `tests/des/unit/adapters/drivers/hooks/test_session_start_handler.py` | Unit | Handler output format, fail-open on service exception, SKIP produces no output |
| `tests/des/unit/adapters/drivers/hooks/test_session_start_routing.py` | Unit | Dispatch table routing for `session-start` command |
| `tests/des/acceptance/test_session_start_handler_acceptance.py` | Acceptance | BDD: update available → additionalContext; no update → no output; network failure → exit 0 |
| `tests/des/acceptance/test_session_start_routing_acceptance.py` | Acceptance | BDD: session-start dispatches to SessionStart handler |
| `tests/des/integration/test_session_start_handler.py` | Integration | End-to-end: mocked PyPI + GitHub → handler stdout/exit code validation |

---

## Quality Gates Passed

| Gate | Target | Result |
|------|--------|--------|
| Unit tests | All pass | 52 unit tests — PASS |
| Acceptance tests | All pass | 7 acceptance tests — PASS |
| Integration tests | All pass | 6 integration tests — PASS |
| Total test count | — | 65 tests, 0 failures |
| L1-L4 refactoring | Applied | All 4 levels applied to session_start_handler |
| Adversarial review | Pass | 4 findings addressed (C1, C2, H1, H2) |
| Mutation kill rate | >= 80% | Achieved |
| Fail-open contract | No exceptions propagate | Verified by acceptance tests |

### Adversarial review findings addressed

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| C1 | Critical | `update_check_frequency` defaulting to `'daily'` suppressed first-run Rule 3 | Changed property to return `None` when key absent; `save_update_check_state()` bootstraps `'daily'` on first write |
| C2 | Critical | `TestInstallDESHooks` tested legacy `install_des_hooks.py` script with stale count assertions | Removed class; coverage provided by `TestSessionStartHookRegistration` and `TestBootstrapUpdateCheckConfig` against `DESPlugin` directly |
| H1 | High | Pre-release version strings (e.g. `2.0.0rc1`) caused `_parse_version` to raise `ValueError` with no test coverage | Added test documenting silent fallback to `False` from `_is_newer` — user shown UP_TO_DATE, no exception |
| H2 | High | Unbounded changelog injection from large or adversarial GitHub release body | Added 2000-character cap in `_fetch_changelog`; added `test_changelog_is_capped_at_2000_chars` |

---

## Retrospective Notes

### What worked well

**Domain/application separation**: Placing frequency evaluation in `UpdateCheckPolicy` (domain) and network I/O in `UpdateCheckService` (application) produced clean seams. The policy tests ran in microseconds with no mocking; the service tests mocked only the HTTP layer. This separation made the adversarial finding C1 trivial to fix — the policy's `None` handling was already a first-class rule, just not threaded through correctly from the config adapter.

**Fail-open as a first-class design constraint**: Naming the constraint explicitly ("session must never be blocked") before writing any code prevented the temptation to surface errors for debugging convenience. The outer `except Exception: return 0` in `handle_session_start()` was placed intentionally from step 1, not added as an afterthought.

**Two-step policy evaluation in the service**: Re-evaluating the policy after fetching the PyPI version (with the actual `latest_version` for skipped-versions Rule 2) required careful thought. The test for "user skipped 2.0.0, PyPI returns 2.0.0, no notification" would have caught this regression immediately if the double-evaluation had been missed.

### What could be improved

**Test count drift**: The feature task brief stated 42 tests; the final count is 65. The discrepancy reflects test growth during adversarial review (H1, H2 each added tests) and the integration test suite added in a dedicated step. Future briefs should treat the test count as a floor, not a fixed target.

**Changelog cap is a best-effort mitigation, not a security guarantee**: The 2000-character cap protects the common case of large release bodies. A genuinely adversarial PyPI/GitHub endpoint could still inject structured text within the cap. The mitigation is proportionate for the threat model (misconfigured mirror, not active attacker), but worth revisiting if nwave-ai expands to enterprise environments with stricter injection requirements.

**`DESConfig.update_check_frequency` None-for-absent semantics**: The `None` return for absent config key is correct but counter-intuitive — callers expecting a string must handle `None`. This is documented in the docstring and covered by tests, but a future refactor could use a more explicit `Optional[str]` return type annotation to surface this at the type-checker level (it is already typed as `str | None`, just the semantic meaning of `None` warrants stronger documentation at the call site).

---

## Commit History

| Commit | Type | Description |
|--------|------|-------------|
| `55b83738` | fix | Correct execution-log outcomes for step 01-01 |
| `430507c3` | feat | Add DESConfig update_check properties and save method |
| `68c11913` | chore | Log step 01-02 phases to execution-log.yaml |
| `659bb22c` | feat | Add UpdateCheckService version comparison |
| `a1e041d0` | feat | Add UpdateCheckService changelog fetch |
| `d49566f0` | feat | Add UpdateCheckService frequency gate and state persistence |
| `1359190c` | feat | Add SessionStart hook handler |
| `960e6121` | feat | Route session-start command in hook adapter |
| `1845c5cd` | feat | Register SessionStart hook and bootstrap update_check config in DES plugin |
| `d6ccae70` | test | Add integration tests for session-start handler flow |
| `2f21e69c` | refactor | Apply L1-L4 refactoring to session-start handler |
| `a2161639` | fix | Address adversarial review findings (C1, C2, H1, H2) |
