Feature: CI/CD Slack Notifications with Alarm Fatigue Prevention

  As a developer on a high-urgency team
  I want to receive actionable pipeline notifications with clear ownership
  So that I can fix failures quickly without experiencing alarm fatigue

  Background:
    Given the #cicd Slack channel exists
    And Dakota's notification service is running
    And author mapping is configured:
      | git_username     | slack_user_id | email                             |
      | undeadgrishnackh | U01234ABCD    | michele.brissoni@brix.consulting  |
      | 11PJ11           | U56789EFGH    | alessandro.digioia@brix.consulting |
    And branch filter includes ["master", "develop", "installer"]

  # ==========================================================================
  # SCENARIO A: Developer breaks build and fixes it (Happy Path)
  # ==========================================================================

  @horizontal @e2e @critical
  Scenario: Developer breaks build and fixes it within 20 minutes
    Given the "installer" branch last build was successful (run_id: 122)
    And the current time is "2026-01-31 14:34:00"

    # RED NOTIFICATION
    When Michele pushes commit "a1b2c3d" with message "Fix authentication bug"
    And the "CI Pipeline" workflow completes with status "failure" (run_id: 123)
    And the failed jobs are:
      | job_name | exit_code | error_summary               |
      | test     | 1         | AssertionError: Expected 200, got 401 |
      | lint     | 1         | ruff formatting             |

    Then a Slack message is posted to #cicd channel
    And the message header is "🔴 Pipeline Failed: CI Pipeline"
    And the message contains:
      | field          | value                        |
      | Branch         | installer                    |
      | Author         | <@U01234ABCD>                |
      | Commit Message | Fix authentication bug       |
      | Commit SHA     | a1b2c3d                      |
      | Failed Jobs    | test (exit code 1)           |
      | Failed Jobs    | lint (ruff formatting)       |
    And the message has a "danger" style [View Run] button linking to run 123
    And the message has a [View Commit] button linking to commit a1b2c3d
    And the message context shows "⏱️ Failed at: 2:34 PM"
    And Michele receives a Slack notification ping (due to @mention)

    # DEVELOPER INVESTIGATION & FIX
    When Michele clicks the [View Run] button
    Then Michele sees the GitHub Actions log for run 123
    And Michele identifies the auth mock issue

    When Michele fixes the code locally
    And Michele runs tests locally (all pass)
    And Michele commits "b2c3d4e" with message "Fix auth mock in tests"
    And Michele pushes to "installer" branch at "2026-01-31 14:52:00"

    # GREEN NOTIFICATION
    When the "CI Pipeline" workflow completes with status "success" (run_id: 124)
    And the current time is "2026-01-31 14:52:00"

    Then a Slack message is posted to #cicd channel
    And the message header is "✅ Pipeline Recovered: CI Pipeline"
    And the message contains:
      | field             | value                       |
      | Branch            | installer                   |
      | Fixed by          | <@U01234ABCD>               |
      | Commit Message    | Fix auth mock in tests      |
      | Commit SHA        | b2c3d4e                     |
      | Recovery Time     | 18 minutes                  |
      | Recovery Commits  | 1                           |
      | Previously Failed | test ✅ now passing          |
      | Previously Failed | lint ✅ now passing          |
    And the message has a "primary" style [View Run] button linking to run 124
    And the message has a [View Commit] button linking to commit b2c3d4e
    And the message context shows "🟢 All systems healthy"
    And Michele receives a Slack notification ping (due to @mention)

    # EMOTIONAL VALIDATION
    And Michele feels "Relief + Celebration" (validated via user survey)
    And the team sees "All clear" signal (no stress)

  # ==========================================================================
  # SCENARIO B: Teammate fixes developer's broken build
  # ==========================================================================

  @horizontal @e2e
  Scenario: Developer away, teammate fixes the build
    Given the "installer" branch last build was successful (run_id: 122)
    And the current time is "2026-01-31 12:00:00"

    # RED NOTIFICATION (Michele away)
    When Michele pushes commit "a1b2c3d" with message "Quick auth refactor"
    And the "CI Pipeline" workflow completes with status "failure" (run_id: 123)
    Then a RED notification is posted mentioning @michele.brissoni
    And Michele is away at lunch (does not see notification)

    # TEAMMATE INTERVENTION
    When Alessandro sees the RED notification at "2026-01-31 12:30:00"
    And Alessandro investigates the failure
    And Alessandro pushes 3 commits to fix the issue:
      | commit_sha | commit_message           | timestamp          |
      | b2c3d4e    | Start fixing auth issue  | 2026-01-31 13:00:00 |
      | c3d4e5f    | Fix Mike's auth issue    | 2026-01-31 14:00:00 |
      | d4e5f6g    | Add missing test         | 2026-01-31 14:30:00 |
    And the "CI Pipeline" workflow completes with status "success" (run_id: 126)
    And the current time is "2026-01-31 14:34:00"

    # GREEN NOTIFICATION
    Then a Slack message is posted to #cicd channel
    And the message header is "✅ Pipeline Recovered: CI Pipeline"
    And the message contains:
      | field             | value                     |
      | Branch            | installer                 |
      | Fixed by          | <@U56789EFGH>             |
      | Commit Message    | Add missing test          |
      | Commit SHA        | d4e5f6g                   |
      | Recovery Time     | 2h 34m                    |
      | Recovery Commits  | 3                         |
    And Alessandro receives a Slack notification ping (credit for fix)

    # MICHELE RETURNS
    When Michele returns from lunch at "2026-01-31 15:00:00"
    And Michele opens Slack
    Then Michele sees the GREEN notification
    And Michele feels "Relief + Gratitude" (teammate helped)
    And Michele sends "Thanks Alessandro, I owe you coffee ☕" in thread

  # ==========================================================================
  # SCENARIO C: Build stays green (No Spam)
  # ==========================================================================

  @horizontal @noise_reduction
  Scenario: Build stays green should not generate notification
    Given the "installer" branch last build was successful (run_id: 122)

    When Michele pushes commit "x1y2z3a" with message "Add new feature"
    And the "CI Pipeline" workflow completes with status "success" (run_id: 123)

    Then NO Slack message is posted to #cicd
    And the #cicd channel remains silent
    And alarm fatigue is prevented (no green spam)

  # ==========================================================================
  # INTEGRATION TESTS: Shared Artifact Validation
  # ==========================================================================

  @integration @critical
  Scenario: Author mapping (git username → Slack user ID)
    Given git username "undeadgrishnackh" maps to Slack user "U01234ABCD"

    When a pipeline failure occurs with git author "undeadgrishnackh"
    Then the RED notification must contain "<@U01234ABCD>"
    And the RED notification must NOT contain plaintext "undeadgrishnackh"

    When the pipeline recovers
    Then the GREEN notification must contain "<@U01234ABCD>"

  @integration @critical
  Scenario: Failed jobs persistence (RED → GREEN proof)
    Given a pipeline fails with jobs:
      | job_name | status  |
      | test     | failed  |
      | lint     | failed  |
      | build    | success |

    When the RED notification is posted
    Then the failed jobs shown are "test, lint" (not build)

    When the pipeline recovers
    And all jobs now pass
    Then the GREEN notification shows:
      """
      Previously failed:
      • test ✅ now passing
      • lint ✅ now passing
      """
    And the job names match exactly (integration validated)

  @integration
  Scenario: State transition tracking (previous_run_id → current_run_id)
    Given run_id 122 completed with status "success"
    And run_id 123 completed with status "failure"

    When Dakota receives workflow_run webhook for run_id 123
    Then Dakota retrieves previous_run_id 122 from state storage
    And Dakota compares status: success → failure
    And Dakota determines notification_type: "failure"

    When run_id 124 completes with status "success"
    Then Dakota retrieves previous_run_id 123 from state storage
    And Dakota compares status: failure → success
    And Dakota determines notification_type: "back_to_green"
    And Dakota calculates time_since_failure from run_id 123 timestamp

  @integration
  Scenario: Time-since-failure calculation
    Given run_id 123 failed at "2026-01-31 14:34:00"
    And run_id 124 succeeded at "2026-01-31 14:52:00"

    When Dakota generates GREEN notification
    Then time_since_failure is calculated as 18 minutes
    And the GREEN notification shows "Back to green after 18 minutes"

  @integration
  Scenario: Recovery commit count
    Given run_id 123 failed at commit "a1b2c3d"
    And commits between failure and recovery are:
      | commit_sha | commit_message           |
      | b2c3d4e    | Fix auth mock in tests   |

    When run_id 124 succeeds at commit "b2c3d4e"
    Then Dakota calculates recovery_commit_count as 1
    And the GREEN notification shows "Recovery commits: 1"

  # ==========================================================================
  # EDGE CASES & ERROR HANDLING
  # ==========================================================================

  @edge_case
  Scenario: Unknown git author (mapping not found)
    Given git username "external_contributor" has NO Slack mapping

    When a pipeline fails with author "external_contributor"
    Then the RED notification contains plaintext "external_contributor"
    And Dakota logs warning: "Author mapping missing for external_contributor"
    And the notification is still posted (degraded gracefully)

  @edge_case
  Scenario: Long commit message truncation
    Given Michele pushes commit with message:
      """
      This is a very long commit message that exceeds the 100 character limit and needs to be truncated to prevent Slack block overflow
      """

    When a notification is generated
    Then the displayed commit message is:
      """
      This is a very long commit message that exceeds the 100 character limit and needs to be truncat...
      """
    And the message length is exactly 100 characters

  @edge_case
  Scenario: Multiple jobs failed with different error types
    Given a pipeline fails with jobs:
      | job_name | exit_code | error_summary                          |
      | test     | 1         | 5 tests failed                         |
      | lint     | 1         | ruff formatting issues                 |
      | type     | 1         | mypy type errors                       |
      | security | 1         | bandit found 2 vulnerabilities         |

    When the RED notification is generated
    Then the failed jobs section shows:
      """
      ❌ Failed Jobs:
      • test (5 tests failed)
      • lint (ruff formatting issues)
      • type (mypy type errors)
      • security (bandit found 2 vulnerabilities)
      """

  @edge_case
  Scenario: Branch not in filter (should not notify)
    Given branch filter includes ["master", "develop", "installer"]

    When a pipeline fails on branch "feature/experimental"
    Then NO Slack notification is posted
    And the #cicd channel remains silent

  @edge_case
  Scenario: Recovery after multiple failures (flapping)
    Given the pipeline fails at run_id 123 (commit a1b2c3d)
    And Michele pushes fix commit b2c3d4e → fails again at run_id 124
    And Michele pushes another fix c3d4e5f → succeeds at run_id 125

    When the GREEN notification is generated for run_id 125
    Then time_since_failure is calculated from run_id 123 (first failure)
    And recovery_commit_count is 2 (both fix attempts)
    And the GREEN notification shows "Back to green after 45 minutes"

  # ==========================================================================
  # ANTI-ALARM-FATIGUE VALIDATION
  # ==========================================================================

  @alarm_fatigue @validation
  Scenario: Ownership prevents diffusion of responsibility
    Given a pipeline fails
    Then exactly ONE developer is @mentioned in RED notification
    And that developer is the git commit author
    And there is NO "someone should fix this" ambiguity

  @alarm_fatigue @validation
  Scenario: Closure prevents despair (RED graveyard)
    Given the #cicd channel has 5 RED notifications from yesterday
    When all pipelines recover today
    Then the #cicd channel shows 5 GREEN notifications
    And developers see "resolution happened" (not abandoned failures)
    And the channel feels "responsive" not "despairing"

  @alarm_fatigue @validation
  Scenario: Actionability enables immediate investigation
    Given a RED notification is posted
    Then the notification shows:
      | actionable_element | value                              |
      | Failed Jobs        | test, lint (specific job names)    |
      | Error Summary      | exit code 1, ruff formatting       |
      | View Run Button    | Direct link to GitHub Actions log  |
      | View Commit Button | Direct link to commit diff         |
    And the developer can investigate WITHOUT leaving Slack first
    And the developer knows WHAT failed (not just "it failed")

  @alarm_fatigue @validation
  Scenario: Celebration creates positive feedback loop
    Given a RED notification created anxiety
    When the GREEN notification appears
    Then the message tone is "celebratory" (🎉 emoji)
    And the message validates effort ("Back to green after 18 minutes")
    And the developer feels "pride" not "relief only"
    And the team culture reinforces "fixing issues is valued"

  @alarm_fatigue @validation
  Scenario: Noise reduction maintains signal quality
    Given the team has 10 active feature branches
    And only ["master", "develop", "installer"] are critical
    When feature branch "my-experiment" fails
    Then NO notification is posted to #cicd
    And the #cicd channel maintains high signal-to-noise ratio
    And developers trust that #cicd alerts are ALWAYS important

  # ==========================================================================
  # SLACK BLOCK KIT TECHNICAL VALIDATION
  # ==========================================================================

  @technical @slack_api
  Scenario: RED notification block structure validation
    Given a pipeline failure occurs
    When the RED notification is generated
    Then the Slack message has blocks:
      | block_type | content                              |
      | header     | 🔴 Pipeline Failed: CI Pipeline      |
      | section    | Branch: installer, Author: <@USER>   |
      | section    | Commit message + SHA                 |
      | section    | Failed jobs list                     |
      | actions    | [View Run] [View Commit] buttons     |
      | context    | ⏱️ Failed at: timestamp              |
    And the total block count is ≤ 50 (Slack limit)
    And the message character count is ≤ 3000 (Slack limit)

  @technical @slack_api
  Scenario: GREEN notification block structure validation
    Given a pipeline recovery occurs
    When the GREEN notification is generated
    Then the Slack message has blocks:
      | block_type | content                              |
      | header     | ✅ Pipeline Recovered: CI Pipeline   |
      | section    | Branch: installer, Fixed by: <@USER> |
      | section    | Commit message + SHA                 |
      | section    | Recovery time + commit count         |
      | section    | Previously failed jobs (now passing) |
      | actions    | [View Run] [View Commit] buttons     |
      | context    | 🟢 All systems healthy               |
    And the total block count is ≤ 50 (Slack limit)
    And the message character count is ≤ 3000 (Slack limit)

  # ==========================================================================
  # PERFORMANCE & RELIABILITY
  # ==========================================================================

  @performance
  Scenario: Notification latency (webhook → Slack post)
    Given a GitHub Actions workflow completes
    When Dakota receives the workflow_run webhook
    Then the Slack notification is posted within 5 seconds
    And developers see results in near-real-time

  @reliability
  Scenario: Slack API failure handling
    Given a pipeline fails
    When Dakota attempts to post to Slack
    And the Slack API returns 500 Internal Server Error
    Then Dakota retries up to 3 times with exponential backoff
    And if all retries fail, Dakota logs the error
    And the notification data is persisted for manual recovery
