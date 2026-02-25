Feature: Rigor Profile Selection
  As a developer using nWave,
  I want to choose how much quality ceremony nWave applies to my session
  So that I can balance rigor against token cost and iteration speed

  Background:
    Given nWave is installed in the current project
    And .nwave/des-config.json exists and is writable

  # --- Happy Paths ---

  Scenario: First-time interactive profile selection (standard)
    Given Kai Nakamura has no rigor profile configured
    When Kai runs /nw:rigor
    Then nWave displays a comparison table of all 5 profiles
    And "standard" is marked as [recommended]
    And each profile shows: agent model, reviewer model, review, TDD phases, mutation, estimated cost, estimated time
    When Kai selects "standard"
    Then nWave shows the detail view for "standard"
    And the detail view lists what Kai gets and what Kai loses
    When Kai confirms the selection
    Then .nwave/des-config.json contains rigor.profile = "standard"
    And .nwave/des-config.json contains rigor.agent_model = "sonnet"
    And .nwave/des-config.json contains rigor.reviewer_model = "haiku"
    And .nwave/des-config.json contains rigor.tdd_phases = ["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN", "COMMIT"]
    And .nwave/des-config.json contains rigor.review_enabled = true
    And .nwave/des-config.json contains rigor.mutation_enabled = false
    And nWave displays a session confirmation summary

  Scenario: Selecting lean profile shows explicit losses
    Given Priya Sharma runs /nw:rigor
    When Priya selects "lean"
    Then the detail view shows "WHAT YOU LOSE" section containing:
      | loss                                    |
      | No peer review of your code             |
      | No PREPARE phase (test fixture setup)   |
      | No COMMIT phase (no refactoring gate)   |
      | No mutation testing                     |
      | No dedicated refactoring pass           |
    And the detail view shows "Estimated token savings: ~60% vs standard"
    When Priya confirms the selection
    Then .nwave/des-config.json contains rigor.profile = "lean"
    And .nwave/des-config.json contains rigor.agent_model = "haiku"
    And .nwave/des-config.json contains rigor.reviewer_model = "skip"
    And .nwave/des-config.json contains rigor.tdd_phases = ["RED_UNIT", "GREEN"]
    And .nwave/des-config.json contains rigor.review_enabled = false

  Scenario: Selecting thorough profile shows full ceremony and cost
    Given Kai runs /nw:rigor
    When Kai selects "thorough"
    Then the detail view shows "WHAT IT COSTS" section containing:
      | cost                                   |
      | ~180% token usage vs standard          |
      | ~20 minutes per step                   |
    And the detail view shows double peer review is included
    And the detail view does NOT show mutation testing
    When Kai confirms the selection
    Then .nwave/des-config.json contains rigor.profile = "thorough"
    And .nwave/des-config.json contains rigor.agent_model = "opus"
    And .nwave/des-config.json contains rigor.reviewer_model = "sonnet"
    And .nwave/des-config.json contains rigor.review_enabled = true
    And .nwave/des-config.json contains rigor.mutation_enabled = false

  Scenario: Selecting exhaustive profile shows mutation testing and opus reviewer
    Given Kai runs /nw:rigor
    When Kai selects "exhaustive"
    Then the detail view shows "WHAT IT COSTS" section containing:
      | cost                                         |
      | ~250% token usage vs standard                |
      | ~30 minutes per step                         |
      | Opus reviewer significantly increases review cost |
    And the detail view shows double peer review is included
    And the detail view shows mutation testing with >= 80% kill rate gate
    And the detail view shows opus model for both agents AND reviewers
    When Kai confirms the selection
    Then .nwave/des-config.json contains rigor.profile = "exhaustive"
    And .nwave/des-config.json contains rigor.agent_model = "opus"
    And .nwave/des-config.json contains rigor.reviewer_model = "opus"
    And .nwave/des-config.json contains rigor.review_enabled = true
    And .nwave/des-config.json contains rigor.mutation_enabled = true

  Scenario: Selecting inherit profile respects session model
    Given Tomasz Kowalski is running Claude Code with haiku model
    And Tomasz runs /nw:rigor
    When Tomasz selects "inherit"
    Then the detail view shows "Your current session model for agents (*currently: haiku*)"
    And the detail view explains quality checks stay at standard level
    When Tomasz confirms the selection
    Then .nwave/des-config.json contains rigor.profile = "inherit"
    And .nwave/des-config.json contains rigor.agent_model = "inherit"
    And .nwave/des-config.json contains rigor.reviewer_model = "haiku"
    And .nwave/des-config.json contains rigor.tdd_phases = ["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN", "COMMIT"]
    And .nwave/des-config.json contains rigor.review_enabled = true

  Scenario: Quick switch with direct profile argument
    Given Kai has rigor profile set to "standard"
    When Kai runs /nw:rigor lean
    Then nWave shows a diff of what changes from standard to lean
    And the diff highlights what Kai will LOSE
    When Kai confirms
    Then the profile switches to "lean"
    And nWave does not show the comparison table

  Scenario: Changing profile mid-session
    Given Priya has rigor profile set to "lean"
    And Priya has already run /nw:deliver for a config change
    When Priya runs /nw:rigor thorough
    And Priya confirms
    Then all subsequent /nw:* commands use the "thorough" profile
    And previously completed commands are not affected

  # --- Config Persistence ---

  Scenario: Profile persists in config alongside existing settings
    Given des-config.json already contains audit_logging_enabled = true
    And des-config.json already contains skill_tracking = "passive-logging"
    When Kai selects profile "standard" via /nw:rigor
    Then des-config.json still contains audit_logging_enabled = true
    And des-config.json still contains skill_tracking = "passive-logging"
    And des-config.json additionally contains rigor.profile = "standard"

  # --- Navigation ---

  Scenario: User goes back from detail view to comparison
    Given Kai is viewing the detail view for "lean"
    When Kai enters "back"
    Then nWave shows the comparison table again
    And no profile change is saved

  Scenario: User cancels confirmation
    Given Kai is viewing the detail view for "thorough"
    When Kai enters "n" at the confirm prompt
    Then no profile change is saved
    And the previous profile (if any) remains active

  # --- Error Paths ---

  Scenario: Invalid profile name shows available options
    Given Kai runs /nw:rigor
    When Kai enters "turbo" as profile selection
    Then nWave displays "Unknown profile 'turbo'. Available: lean, standard, thorough, exhaustive, inherit"
    And the comparison table is shown again

  Scenario: Missing nWave directory
    Given the .nwave/ directory does not exist
    When Kai runs /nw:rigor
    Then nWave displays "No nWave config directory found. Run nwave install first."
    And no config file is created

  Scenario: Corrupted config file is recovered
    Given des-config.json contains invalid JSON
    When Kai runs /nw:rigor
    Then nWave backs up the corrupted file as des-config.json.bak
    And nWave displays "Config file corrupted. Resetting to defaults."
    And Kai can proceed with profile selection normally

  Scenario: Inherit with undetectable session model falls back
    Given Tomasz selects "inherit" profile
    And the current session model cannot be determined
    Then nWave displays "Cannot detect current session model. Using 'sonnet' as fallback."
    And rigor.agent_model is set to "sonnet"

  # --- Wave Command Integration ---

  Scenario: /nw:deliver respects lean profile
    Given Kai has rigor profile set to "lean"
    When Kai runs /nw:deliver "fix typo in README"
    Then the deliver orchestrator uses haiku model for the crafter agent
    And the deliver orchestrator skips PREPARE phase
    And the deliver orchestrator skips COMMIT phase
    And the deliver orchestrator skips peer review (Phase 4)
    And the deliver orchestrator skips mutation testing (Phase 5)

  Scenario: /nw:deliver respects thorough profile
    Given Priya has rigor profile set to "thorough"
    When Priya runs /nw:deliver "implement rate limiting for API"
    Then the deliver orchestrator uses opus model for the crafter agent
    And the deliver orchestrator uses sonnet model for the reviewer
    And the deliver orchestrator runs all 5 TDD phases with extra pass
    And the deliver orchestrator runs double peer review (Phase 4)
    And the deliver orchestrator skips mutation testing (Phase 5)

  Scenario: /nw:deliver respects exhaustive profile
    Given Kai has rigor profile set to "exhaustive"
    When Kai runs /nw:deliver "implement token validation for auth"
    Then the deliver orchestrator uses opus model for the crafter agent
    And the deliver orchestrator uses opus model for the reviewer
    And the deliver orchestrator runs all 5 TDD phases with extra pass
    And the deliver orchestrator runs double peer review (Phase 4)
    And the deliver orchestrator runs mutation testing with >= 80% kill rate (Phase 5)
