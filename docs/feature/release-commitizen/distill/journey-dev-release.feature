Feature: CZ-Driven Dev Release Version Calculation
  As Mike, the release engineer for nwave-dev,
  I want dev release versions to reflect conventional commit types
  So that feat: commits produce a minor bump (1.2.0.dev1) instead of always patch (1.1.23.dev1)

  Background:
    Given the nwave-dev repo is on branch master
    And the current version in pyproject.toml is "1.1.22"
    And pyproject.toml contains a [tool.commitizen] section with version_scheme = "pep440"
    And all CI checks on HEAD are green

  # --- US-CZ-01: CZ-driven version bump replaces hardcoded patch ---

  Scenario: feat commits produce minor bump via Commitizen
    Given Mike has pushed 4 "feat:" commits since the last stable tag v1.1.22
    And no existing dev tags for version "1.2.0"
    When the pipeline runs "cz bump --get-next"
    Then Commitizen outputs "1.2.0"
    When the pipeline runs next_version.py with --base-version "1.2.0"
    Then the dev version is "1.2.0.dev1"
    And the version follows PEP 440 format

  Scenario: fix-only commits produce patch bump via Commitizen
    Given Mike has pushed 3 "fix:" commits since v1.1.22
    And no existing dev tags for version "1.1.23"
    When the pipeline runs "cz bump --get-next"
    Then Commitizen outputs "1.1.23"
    When the pipeline runs next_version.py with --base-version "1.1.23"
    Then the dev version is "1.1.23.dev1"

  Scenario: breaking change produces major bump via Commitizen
    Given Mike has pushed a "feat!:" commit since v1.1.22
    And no existing dev tags for version "2.0.0"
    When the pipeline runs "cz bump --get-next"
    Then Commitizen outputs "2.0.0"
    When the pipeline runs next_version.py with --base-version "2.0.0"
    Then the dev version is "2.0.0.dev1"

  Scenario: Sequential counter with CZ base version
    Given Commitizen determined the base version as "1.2.0"
    And a dev tag "v1.2.0.dev1" already exists
    When the pipeline runs next_version.py with --base-version "1.2.0"
    Then the dev version is "1.2.0.dev2"

  Scenario: Empty base-version falls back to patch bump
    Given the --base-version argument is empty
    And the current version in pyproject.toml is "1.1.22"
    And no existing dev tags for version "1.1.23"
    When the pipeline runs next_version.py with --base-version ""
    Then next_version.py calculates the fallback version by bumping the patch component
    And the dev version is "1.1.23.dev1"

  # --- US-CZ-01b: Mid-cycle bump level escalation ---

  Scenario: Patch-to-minor escalation resets dev counter mid-cycle
    Given the current version in pyproject.toml is "1.1.25"
    And Mike and Ale have pushed "ci:" and "fix:" commits since v1.1.25
    And 8 dev releases have been tagged: v1.1.26.dev1 through v1.1.26.dev8
    And Ale then pushes a "feat:" commit adding a new agent
    When the pipeline runs "cz bump --get-next"
    Then Commitizen re-scans ALL commits since v1.1.25
    And feat: is the highest bump level
    And Commitizen outputs "1.2.0"
    When the pipeline runs next_version.py with --base-version "1.2.0"
    Then no existing dev tags match the escalated base version "1.2.0"
    And the dev version is "1.2.0.dev1"

  Scenario: Patch-to-major escalation resets dev counter mid-cycle
    Given the current version in pyproject.toml is "1.1.25"
    And Mike has pushed 3 "fix:" commits since v1.1.25
    And 3 dev releases have been tagged: v1.1.26.dev1 through v1.1.26.dev3
    And Ale then pushes a "feat!: redesign plugin API" commit
    When the pipeline runs "cz bump --get-next"
    Then Commitizen re-scans ALL commits since v1.1.25
    And "feat!:" is the highest bump level (BREAKING CHANGE)
    And Commitizen outputs "2.0.0"
    When the pipeline runs next_version.py with --base-version "2.0.0"
    Then _highest_counter finds NO v2.0.0.dev* tags
    And the dev version is "2.0.0.dev1"

  Scenario: Minor-to-major escalation resets dev counter mid-cycle
    Given the current version in pyproject.toml is "1.1.25"
    And Mike has pushed 2 "feat:" commits since v1.1.25
    And 4 dev releases have been tagged: v1.2.0.dev1 through v1.2.0.dev4
    And Ale then pushes a commit with "BREAKING CHANGE:" in the body
    When the pipeline runs "cz bump --get-next"
    Then Commitizen re-scans ALL commits since v1.1.25
    And BREAKING CHANGE is the highest bump level
    And Commitizen outputs "2.0.0"
    When the pipeline runs next_version.py with --base-version "2.0.0"
    Then _highest_counter finds NO v2.0.0.dev* tags (old v1.2.0.dev* are invisible)
    And the dev version is "2.0.0.dev1"

  Scenario: Reverted feat commit does not de-escalate (CZ scans all commits including revert)
    Given the current version in pyproject.toml is "1.1.25"
    And Mike pushed a "feat:" commit and then a "revert:" commit reverting it
    And only "fix:" commits remain as net-effective changes
    When the pipeline runs "cz bump --get-next"
    Then Commitizen scans ALL commits since v1.1.25 including the revert
    And the original "feat:" commit is still in the history
    And Commitizen outputs "1.2.0" (feat: still the highest bump type seen)

  Scenario: Multiple base versions coexist in tags after escalation
    Given the current version in pyproject.toml is "1.1.25"
    And existing tags include v1.1.26.dev1 through v1.1.26.dev8
    And existing tags include v1.2.0.dev1
    And Commitizen now outputs "1.2.0" (feat: commits present)
    When the pipeline runs next_version.py with --base-version "1.2.0"
    Then only dev tags for the new base version "1.2.0" are considered
    And finds highest counter is 1 (from v1.2.0.dev1)
    And the dev version is "1.2.0.dev2"
    And v1.1.26.dev* tags are ignored (different base)

  Scenario: RC promotion after mid-cycle escalation uses highest base
    Given the current version in pyproject.toml is "1.1.25"
    And existing tags include v1.1.26.dev1 through v1.1.26.dev8
    And existing tags include v1.2.0.dev1 and v1.2.0.dev2
    When the team promotes the latest dev tag to RC
    Then the RC candidate is v1.2.0.dev2 (highest base version, highest counter)
    And the RC version is "1.2.0rc1"
    And the stable promotion path is v1.2.0.dev2 -> v1.2.0rc1 -> v1.2.0

  # --- US-CZ-02: Version floor override from pyproject.toml ---

  Scenario: Floor overrides CZ when floor is higher
    Given Commitizen determined the base version as "1.2.0"
    And [tool.nwave].public_version is set to "1.3.0"
    And no existing dev tags for version "1.3.0"
    When the pipeline runs next_version.py with --base-version "1.2.0" and --version-floor "1.3.0"
    Then the floor "1.3.0" is higher than the CZ base "1.2.0"
    And the dev version is "1.3.0.dev1"

  Scenario: Floor is ignored when lower than CZ base
    Given Commitizen determined the base version as "1.2.0"
    And [tool.nwave].public_version is set to "1.1.0"
    And no existing dev tags for version "1.2.0"
    When the pipeline runs next_version.py with --base-version "1.2.0" and --version-floor "1.1.0"
    Then the floor "1.1.0" is lower than the CZ base "1.2.0"
    And the dev version is "1.2.0.dev1"

  Scenario: Floor overrides fallback when CZ fails
    Given the --base-version argument is empty (CZ failed)
    And [tool.nwave].public_version is set to "2.0.0"
    And the current version in pyproject.toml is "1.1.22"
    And no existing dev tags for version "2.0.0"
    When the pipeline runs next_version.py with --base-version "" and --version-floor "2.0.0"
    Then next_version.py calculates the fallback version by bumping the patch component: "1.1.23"
    And the floor "2.0.0" is higher than the fallback "1.1.23"
    And the dev version is "2.0.0.dev1"

  Scenario: Floor and CZ base with existing tags combine correctly
    Given Commitizen determined the base version as "1.2.0"
    And [tool.nwave].public_version is set to "1.3.0"
    And a dev tag "v1.3.0.dev1" already exists
    When the pipeline runs next_version.py with --base-version "1.2.0" and --version-floor "1.3.0"
    Then the floor wins: base is "1.3.0"
    And the dev version is "1.3.0.dev2"

  # --- US-CZ-03: Graceful fallback when CZ fails ---

  Scenario: CZ not installed falls back gracefully
    Given commitizen is not installed in the CI environment
    When the pipeline runs "cz bump --get-next"
    Then the CZ step outputs an empty string (not a pipeline failure)
    When the pipeline passes --base-version "" to next_version.py
    Then next_version.py calculates the fallback version by bumping the patch component
    And the dev version is "1.1.23.dev1"
    And the pipeline completes successfully

  Scenario: CZ config missing falls back gracefully
    Given pyproject.toml does not contain a [tool.commitizen] section
    When the pipeline runs "cz bump --get-next"
    Then the CZ step outputs an empty string
    When the pipeline passes --base-version "" to next_version.py
    Then next_version.py calculates the fallback version by bumping the patch component
    And the dev version is "1.1.23.dev1"

  Scenario: Invalid base-version is rejected
    Given the --base-version argument is "not-a-version"
    When the pipeline runs next_version.py with --base-version "not-a-version"
    Then next_version.py exits with code 2
    And the error message contains "Invalid base-version"

  Scenario: Invalid version-floor is rejected
    Given the --version-floor argument is "abc"
    When the pipeline runs next_version.py with --version-floor "abc"
    Then next_version.py exits with code 2
    And the error message contains "Invalid version-floor"

  # --- US-CZ-04: Full Promotion Chain (Dev -> RC -> Stable) ---

  Scenario: Dev to RC promotion after mid-cycle escalation uses highest dev tag
    Given the current version in pyproject.toml is "1.1.25"
    And existing tags include v1.1.26.dev1 through v1.1.26.dev8 (patch-bump base)
    And existing tags include v1.2.0.dev1 and v1.2.0.dev2 (minor-bump base after feat: escalation)
    When Mike clicks "Promote to RC" in release-rc.yml and leaves the tag field empty
    Then discover_tag.py --pattern dev sorts all dev tags by packaging.Version
    And v1.2.0.dev2 is the highest (not v1.1.26.dev8, which is higher by string sort)
    And calculate_rc receives "v1.2.0.dev2" as current_version
    And calculate_rc strips to base "1.2.0" and creates "1.2.0rc1"
    And the orphaned v1.1.26.dev1 through v1.1.26.dev8 tags remain as historical artifacts

  Scenario: Orphaned dev tags from pre-escalation base are ignored by discover_tag
    Given existing tags include v1.1.26.dev1 through v1.1.26.dev8 (from fix-only period)
    And existing tags include v1.2.0.dev1 and v1.2.0.dev2 (from feat: escalation)
    When discover_tag.py runs with --pattern dev
    Then discover_tag.py filters all tags matching dev pattern
    And sorts by packaging.Version (not lexicographic)
    And v1.2.0.dev2 sorts higher than v1.1.26.dev8
    And the result is v1.2.0.dev2
    And v1.1.26.dev* tags are never promoted (dead-end artifacts)

  Scenario: Sequential RC counter increments on repeated promotion
    Given v1.2.0rc1 already exists from a first RC promotion
    And a bug was found in RC, the fix was merged, and a new dev release v1.2.0.dev3 was created
    When Mike clicks "Promote to RC" again with the tag field empty
    Then discover_tag.py --pattern dev finds v1.2.0.dev3
    And calculate_rc receives "v1.2.0.dev3", strips to base "1.2.0"
    And _highest_counter finds existing v1.2.0rc1 (counter = 1)
    And the RC version is "1.2.0rc2"

  Scenario: RC to stable promotion strips RC suffix
    Given existing RC tags include v1.2.0rc1 and v1.2.0rc2
    When Mike clicks "Promote to Stable" in release-prod.yml and leaves the tag field empty
    Then discover_tag.py --pattern rc sorts all RC tags by packaging.Version
    And v1.2.0rc2 is the highest RC tag
    And calculate_stable receives "v1.2.0rc2"
    And calculate_stable strips to base "1.2.0"
    And the stable version is "1.2.0"
    And pyproject.toml is updated to version "1.2.0"
    And the stable tag v1.2.0 is created

  Scenario: Accidental wrong-tag RC promotion self-heals at stable stage
    Given someone manually entered "v1.1.26.dev8" in the RC workflow tag field
    And discover_tag.py --validate "v1.1.26.dev8" confirms it exists
    And calculate_rc created v1.1.26rc1 from that tag
    And later the correct RC promotion created v1.2.0rc1
    When Mike clicks "Promote to Stable" with the tag field empty
    Then discover_tag.py --pattern rc finds both v1.1.26rc1 and v1.2.0rc1
    And v1.2.0rc1 sorts higher by packaging.Version
    And the stable version is "1.2.0" (the correct version)
    And v1.1.26rc1 remains as a historical artifact (never promoted to stable)

  Scenario: Floor override does not affect RC or stable stages
    Given [tool.nwave].public_version is set to "2.0.0" in pyproject.toml
    And the latest dev tag is v1.2.0.dev2 (floor was applied at dev stage)
    When Mike promotes to RC via release-rc.yml
    Then calculate_rc receives "v1.2.0.dev2" and creates "1.2.0rc1"
    And the floor value "2.0.0" is NOT consulted during RC calculation
    When Mike then promotes to stable via release-prod.yml
    Then calculate_stable receives "v1.2.0rc1" and creates "1.2.0"
    And the floor value "2.0.0" is NOT consulted during stable calculation
    And floor override applies exclusively to the dev stage

  Scenario: Full three-stage promotion chain with one-click UX
    Given the current version in pyproject.toml is "1.1.25"
    And Ale pushed feat: commits causing escalation to base "1.2.0"
    And the latest dev tag is v1.2.0.dev2
    When Mike clicks "Promote to RC" in release-rc.yml with tag field empty
    Then discover_tag.py auto-discovers v1.2.0.dev2
    And the pipeline creates tag v1.2.0rc1
    When Mike clicks "Promote to Stable" in release-prod.yml with tag field empty
    Then discover_tag.py auto-discovers v1.2.0rc1
    And the pipeline creates tag v1.2.0
    And pyproject.toml is updated to "1.2.0"
    And the full chain is: v1.2.0.dev2 -> v1.2.0rc1 -> v1.2.0
    And each stage required exactly one click with no manual tag entry

  # --- US-CZ-05: PSR-to-CZ Migration (consolidate versioning tools) ---

  Scenario: CZ config includes version_files for all PSR-managed files
    Given the [tool.commitizen] section exists in pyproject.toml
    When Mike reviews the CZ config after PSR migration
    Then version_files includes "nWave/VERSION"
    And version_files includes "nWave/framework-catalog.yaml:version"
    And changelog_file is set to "CHANGELOG.md"
    And CZ handles all file updates that PSR previously handled via .releaserc

  Scenario: .releaserc file is removed from the repository
    Given the .releaserc file currently exists at the repo root
    And it contains Node.js semantic-release plugin configuration
    When the PSR migration is complete
    Then .releaserc no longer exists in the repository
    And the rsync exclude lists in release workflows no longer reference .releaserc

  Scenario: PSR config sections removed from pyproject.toml
    Given pyproject.toml contains [tool.semantic_release] with version_toml and version_variables
    And pyproject.toml contains [tool.semantic_release.branches.main] with match = "master"
    And pyproject.toml contains [tool.semantic_release.changelog] with exclude patterns
    When the PSR migration is complete
    Then none of the [tool.semantic_release] sections exist in pyproject.toml
    And [tool.commitizen] is the sole version management config

  Scenario: python-semantic-release removed from dev dependencies
    Given pyproject.toml lists "python-semantic-release>=9.0.0" in dev dependencies
    And requirements.lock contains "python-semantic-release==10.5.3"
    When the PSR migration is complete
    Then python-semantic-release does not appear in pyproject.toml dependencies
    And python-semantic-release does not appear in requirements.lock
    And commitizen remains as the version management dependency

  Scenario: Legacy release.yml uses CZ instead of PSR for version bump
    Given release.yml version-bump job runs "pip install python-semantic-release"
    And the job calls "semantic-release version" to calculate and bump versions
    When the PSR migration is complete
    Then the version-bump job uses "cz bump" instead of "semantic-release version"
    And dry-run mode uses "cz bump --dry-run" instead of "semantic-release version --print"
    And force-bump mode uses "cz bump --increment {level}" instead of "semantic-release version --{level}"

  Scenario: CZ generates changelog during stable release
    Given the [tool.commitizen] config has changelog_file = "CHANGELOG.md"
    And .gitignore already ignores CHANGELOG.md
    When Mike triggers a stable release via legacy release.yml
    Then CZ generates CHANGELOG.md from conventional commits
    And the changelog groups entries by type: Features, Bug Fixes, etc.
    And the changelog is committed alongside the version bump

  Scenario: CI and documentation references updated from PSR to CZ
    Given ci.yml prints "python-semantic-release keeps framework-catalog.yaml in sync"
    And .github/workflows/README.md describes PSR as the version management tool
    When the PSR migration is complete
    Then ci.yml references "commitizen" instead of "python-semantic-release"
    And the workflows README describes CZ as the version management tool
