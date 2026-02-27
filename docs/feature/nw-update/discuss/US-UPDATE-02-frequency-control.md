# US-UPDATE-02: User-Controlled Update Check Frequency

## Problem
Priya Sharma is a tech lead who leads a team of 4 developers. She wants to hear about nWave updates on her own schedule -- Friday afternoons during her team's tool-maintenance window -- not every time she opens Claude Code. She has no way to configure this. The only option today is either "update check exists" or "it does not", with no middle ground. If the check fires every session, she will start ignoring it or find it disruptive mid-sprint. If it fires silently every time, she learns nothing.

## Who
- Tech Lead | Opens Claude Code multiple times per day | Wants one notification per week, not per session
- Daily power user | Values low interruption | Wants to set check frequency once and forget it
- Developer | Wants to disable checks entirely for air-gapped or offline environments | Needs a "never" option

## Solution
The first time a user sees an update notification, a frequency-control prompt is appended asking how often they want to be checked. Their answer is persisted to `.nwave/des-config.json` under `update_check.frequency`. On subsequent sessions, the check only fires when the configured frequency allows. The user can also state frequency intent at any time conversationally and Claude will update the setting.

## Domain Examples

### 1: Priya sets weekly frequency at first notification
Priya sees her first nWave update notification. At the bottom it reads:

```
How often should I check for updates? (every session / daily / weekly / never) [daily]
```

She tells Claude "weekly". Claude writes `update_check.frequency = "weekly"` to `.nwave/des-config.json`. Next Monday she opens Claude Code on Tuesday, Wednesday, Thursday -- no notification. On Friday (8 days after the last check), she opens Claude Code and sees the weekly digest of what accumulated.

### 2: Kai changes frequency mid-session
Kai is annoyed that he has seen the same "update available" notification three sessions in a row (he keeps saying "later"). He tells Claude: "Stop checking for nWave updates every day, switch to weekly." Claude writes `frequency = "weekly"` to `.nwave/des-config.json`. Starting next session, checks only happen weekly.

### 3: Air-gapped environment, frequency set to never
An enterprise developer works in a network-isolated environment. During onboarding, they set `frequency = "never"` when they see the first notification. From that point on, the hook fires, reads `frequency = "never"`, and immediately returns without any network call or output. The session has zero overhead from update checking.

### 4: Corrupted config resets to daily default
The `update_check` block in `des-config.json` is corrupted (truncated write). The hook reads the file, detects invalid JSON, and treats it as first-run with `frequency = "daily"`. The user's other config keys in the file (rigor settings, audit logging) are preserved if the top-level JSON is intact; only the corrupted `update_check` value is reset.

## UAT Scenarios (BDD)

### Scenario 1: First notification includes frequency prompt
Given .nwave/des-config.json has no "update_check" key
And an update is available (1.2.65 -> 1.2.68)
When the SessionStart hook fires with source "startup"
Then the notification includes a frequency prompt at the bottom
And the prompt offers options: every session, daily, weekly, never
And the prompt shows "daily" as the default in brackets

### Scenario 2: User sets frequency to weekly -- persisted immediately
Given Priya Sharma has seen her first update notification with frequency prompt
When Priya tells Claude "check weekly"
Then .nwave/des-config.json update_check.frequency is set to "weekly"
And other config keys (rigor, audit_logging_enabled) are unchanged
And no frequency prompt is shown in subsequent notifications

### Scenario 3: Weekly frequency suppresses check within 7-day window
Given Priya has update_check.frequency = "weekly"
And update_check.last_checked = "2026-02-20T09:00:00Z"
And today is 2026-02-25 (5 days later)
When the SessionStart hook fires with source "startup"
Then no version check is performed
And no notification is shown
And last_checked remains "2026-02-20T09:00:00Z"

### Scenario 4: Weekly frequency fires after 7-day window
Given Priya has update_check.frequency = "weekly"
And update_check.last_checked = "2026-02-18T09:00:00Z"
And today is 2026-02-25 (7 days later)
And an update is available
When the SessionStart hook fires with source "startup"
Then the version check is performed
And the notification is shown
And last_checked is updated to today's timestamp

### Scenario 5: Frequency set to never -- no network call
Given a developer has update_check.frequency = "never"
When the SessionStart hook fires with source "startup"
Then no HTTP request is made to PyPI or GitHub
And no notification is shown
And last_checked is not updated

### Scenario 6: Daily frequency fires on new day
Given Kai has update_check.frequency = "daily"
And update_check.last_checked = "2026-02-24T23:30:00Z"
And the current time is "2026-02-25T08:00:00Z" (25.5 hours later, new calendar day)
And an update is available
When the SessionStart hook fires with source "startup"
Then the version check is performed
And the notification is shown

### Scenario 7: Missing config defaults to daily behavior
Given .nwave/des-config.json exists but has no "update_check" key
When the SessionStart hook fires with source "startup"
Then the hook behaves as if frequency = "daily" and last_checked is epoch (never checked)
And a version check is performed
And if an update exists, the notification includes the frequency prompt

## Acceptance Criteria
- [ ] Valid frequency values are: every_session, daily, weekly, never
- [ ] First-run (no update_check config) defaults to daily and appends frequency prompt to the first notification
- [ ] Frequency prompt is shown exactly once (first notification); omitted from all subsequent notifications
- [ ] User-stated frequency preference is persisted to .nwave/des-config.json under update_check.frequency using read-modify-write
- [ ] "never" frequency causes the hook to exit before any network call
- [ ] "daily" frequency: check fires if last_checked is more than 24 hours in the past
- [ ] "weekly" frequency: check fires if last_checked is more than 168 hours (7 days) in the past
- [ ] "every_session" frequency: check fires every time source == "startup", regardless of last_checked
- [ ] last_checked is updated after every check attempt regardless of whether an update was found
- [ ] Corrupted update_check config reverts to daily default without touching other config keys

## Technical Notes
- Config storage: `.nwave/des-config.json` under `update_check` key, alongside `rigor` and other existing keys
- Frequency gate must read and compare timestamps using UTC (not local time)
- last_checked format: ISO 8601 UTC string ("2026-02-25T10:00:00Z")
- Read-modify-write: existing keys (rigor, audit_logging_enabled, skill_tracking) must be preserved
- Frequency prompt text is rendered as part of the notification stdout; no separate user input mechanism needed (user responds conversationally via Claude)
- Dependency: US-UPDATE-01 (version check) -- frequency-gate is a pre-condition of the version fetch step
- Dependency: US-RIGOR-03 config persistence patterns apply here (backup on corruption, read-modify-write)

## Traceability
- **Job 3**: Control how often update checks interrupt my session
