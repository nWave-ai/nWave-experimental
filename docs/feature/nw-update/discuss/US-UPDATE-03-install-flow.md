# US-UPDATE-03: One-Action Update from Notification

## Problem
RTodorov is a developer who sees the nWave update notification and wants to update. He does not know the full update command sequence. The correct sequence is `pip install --upgrade nwave-ai && nwave install` -- two steps, where the second step is easy to forget. When he forgets `nwave install`, the Python package updates but the Claude Code agents, hooks, and skills remain at the old version. His nWave installation is then split-brain: PyPI package is new, framework files are old. He only discovers this when something breaks.

## Who
- Developer | Sees "update now" option in notification | Wants the tool to handle the upgrade sequence, not remember commands
- Daily user | Wants to get back to work within 30 seconds | Values "done" confirmation over watching pip output scroll
- Tech lead | Sometimes wants to defer until Friday | Needs "remind me later" and "skip this version" to feel genuinely respected

## Solution
When the user responds to an update notification with "update now", Claude executes `pip install --upgrade nwave-ai && nwave install`, reports success or failure, and confirms the new version. When the user responds "skip this version", the skipped version is recorded in `.nwave/des-config.json` so it is never shown again (but future higher versions will still notify). When the user responds "remind me later", no state is written and the next eligible session will show the notification again.

## Domain Examples

### 1: RTodorov updates from 1.2.65 to 1.2.68 in one step
RTodorov sees the notification. He says "update now". Claude runs:

```
Running: pip install --upgrade nwave-ai && nwave install
```

The pip output scrolls. nwave install completes. Claude confirms:

```
nWave updated: 1.2.65 -> 1.2.68
Framework files (agents, skills, hooks) refreshed.
Restart Claude Code or start a new session to activate the updated hooks.
```

RTodorov starts a new session. Done.

### 2: Priya skips version 1.2.68 (her team is mid-sprint)
Priya sees the notification for 1.2.68. Her team is mid-sprint and she does not want to update until Friday. But she is tired of seeing this notification every day. She says "skip this version". Claude writes `"1.2.68"` to `update_check.skipped_versions` in `.nwave/des-config.json`. She will not see a notification for 1.2.68 again. When 1.2.69 is released on Friday, she will see a notification again (1.2.69 is not in skipped_versions).

### 3: Kai says "remind me later" and continues working
Kai sees the notification for 1.2.68. He is mid-flow on a complex feature. He says "remind me later". No state is written. Claude proceeds with the session. Tomorrow morning, the frequency gate fires (he is daily), checks PyPI, finds 1.2.68 is still available, and shows the notification again.

### 4: pip install fails -- old version preserved
RTodorov says "update now". The pip install fails because his virtual environment is read-only (permissions issue). Claude shows:

```
Update failed:
  ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied

Your current installation (1.2.65) is unchanged. No framework files were modified.
To update manually: pip install --upgrade nwave-ai && nwave install
```

RTodorov's nWave installation is fully intact. He can fix permissions and retry.

### 5: Kai skips 1.2.68, then 1.2.70 is released
Kai previously skipped 1.2.68. When 1.2.70 is released, the version check finds local = 1.2.65, latest = 1.2.70. It checks skipped_versions: ["1.2.68"]. Since 1.2.70 is not in skipped_versions, the notification fires for 1.2.70. The notification says "1.2.65 -> 1.2.70 (5 releases)" -- all releases since his installed version, not just since the skipped one.

## UAT Scenarios (BDD)

### Scenario 1: User chooses "update now" -- success
Given RTodorov has nwave-ai 1.2.65 installed
And the update notification for 1.2.68 is shown in the session
When RTodorov tells Claude "update now"
Then Claude runs pip install --upgrade nwave-ai followed by nwave install
And on success Claude displays the old version (1.2.65) and new version (1.2.68)
And Claude displays "Restart Claude Code or start a new session to activate the updated hooks"
And update_check.last_checked is updated in .nwave/des-config.json
And update_check.skipped_versions is not modified

### Scenario 2: User chooses "skip this version"
Given Priya has nwave-ai 1.2.65 installed
And the update notification for 1.2.68 is shown
When Priya tells Claude "skip this version"
Then .nwave/des-config.json update_check.skipped_versions contains "1.2.68"
And all other config keys are unchanged
And no pip or nwave commands are executed

### Scenario 3: Skipped version does not notify again
Given Priya's .nwave/des-config.json has skipped_versions = ["1.2.68"]
And nwave-ai 1.2.65 is installed
And PyPI reports latest version is 1.2.68
When the SessionStart hook fires with source "startup"
Then no notification is shown
And last_checked is updated

### Scenario 4: Future version above skipped still notifies
Given Priya's .nwave/des-config.json has skipped_versions = ["1.2.68"]
And nwave-ai 1.2.65 is installed
And PyPI reports latest version is 1.2.70
When the SessionStart hook fires with source "startup"
Then the notification is shown for 1.2.70 (not 1.2.68)
And the notification shows "1.2.65 -> 1.2.70"

### Scenario 5: User chooses "remind me later" -- no state written
Given Kai has nwave-ai 1.2.65 installed
And the update notification for 1.2.68 is shown
When Kai tells Claude "remind me later"
Then .nwave/des-config.json skipped_versions is not modified
And the session continues without any update action
And the next eligible session (per frequency setting) will show the notification again

### Scenario 6: pip install fails -- old installation preserved
Given RTodorov has nwave-ai 1.2.65 installed
And Claude runs pip install --upgrade nwave-ai but the command exits with a non-zero status
When the install command fails
Then Claude displays the error output from pip
And Claude confirms "Your current installation (1.2.65) is unchanged"
And Claude shows the manual update command for RTodorov to run himself
And .nwave/ framework files are unchanged
And last_checked is not updated (so the notification will appear next session)

### Scenario 7: Successful install clears skipped versions
Given RTodorov has skipped_versions = ["1.2.66", "1.2.67"] and installs 1.2.68
When pip install --upgrade nwave-ai && nwave install completes successfully
Then update_check.skipped_versions is cleared (empty array) in .nwave/des-config.json
And update_check.last_checked is updated to the current timestamp

## Acceptance Criteria
- [ ] "update now" response causes Claude to run `pip install --upgrade nwave-ai && nwave install` as a two-step sequence
- [ ] Success confirmation shows old version, new version, and instruction to restart Claude Code
- [ ] Failed install displays pip error output, confirms old installation is unchanged, and shows manual command
- [ ] Failed install does not update last_checked (so notification reappears next eligible session)
- [ ] "skip this version" writes the latest version string to update_check.skipped_versions using read-modify-write
- [ ] Skipped version is never shown again in notifications; versions above the skipped one still notify
- [ ] "remind me later" writes no state -- next eligible session will show the notification again
- [ ] Successful install clears skipped_versions and updates last_checked
- [ ] All three actions (install, skip, later) preserve all other .nwave/des-config.json keys (rigor, audit_logging_enabled, etc.)

## Technical Notes
- Install sequence is two commands: `pip install --upgrade nwave-ai` then `nwave install`
- Both commands must succeed for a clean install; if `pip install` fails, `nwave install` must not run
- `nwave install` re-runs the full installation plugin pipeline (agents, hooks, skills, templates)
- Hook re-registration after `nwave install` requires Claude Code session restart to take effect
- skipped_versions is an array of semver strings; comparison is exact string match (not range)
- On successful install: `skipped_versions` is reset to `[]` (fresh start for the new baseline)
- Claude interprets user intent from natural language: "update it", "do it", "yes" -> install_now; "skip", "ignore this version" -> skip_version; "later", "not now", "maybe tomorrow" -> remind_later
- Dependency: US-UPDATE-01 (notification must be shown before this story's actions are reachable)
- Dependency: US-UPDATE-02 (skipped_versions written using same read-modify-write pattern as frequency)

## Traceability
- **Job 4**: Update in one action from the notification
- **Job 1**: Know when a new nWave version is available without actively checking (closing the loop)
