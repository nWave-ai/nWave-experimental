# US-DEV-001: Developer Contribution Guide - Environment Setup for CI Parity

## Problem (The Pain)

Marco Rossi is a backend developer who just joined the nWave project team. He cloned the repository, made several code changes, and committed locally without issues. When he pushed to the remote, CI failed with 83 ruff lint errors. He spent 45 minutes debugging why his local environment didn't catch what CI enforces.

The root cause: `.git/hooks/pre-commit` was MISSING because he never ran `pre-commit install`. The `.pre-commit-config.yaml` exists with correct configuration, but nothing told him activation was required.

## Who (The User)

- **New contributors** joining the nWave project (internal team or external)
- **Occasional contributors** who clone fresh copies for specific work
- **Developers switching machines** who need to re-setup their environment
- Key motivation: Avoid wasted time from CI failures that local setup would have caught

## Solution (What We Build)

A comprehensive Developer Contribution Guide that ensures local environment matches CI quality gates, including:

1. **CONTRIBUTING.md** file at repository root with prominent setup instructions
2. **Verification command** to confirm hooks are active
3. **README.md enhancement** with more prominent "First Time Setup" section
4. **Optional automation** via Makefile target or setup script

## Domain Examples

### Example 1: Marco's First Contribution (Happy Path)
Marco Rossi clones the nWave repository on his MacBook. He reads the README, sees the prominent "First Time Setup" callout, follows the 3-step instructions, and runs the verification command showing "pre-commit hooks: ACTIVE". His first commit triggers ruff auto-fix, and his push passes CI on first attempt.

### Example 2: Sarah's Machine Migration (Environment Reset)
Sarah Chen switches to a new development laptop. She clones her existing fork of nWave. The CONTRIBUTING.md reminds her about hook installation. She runs `make setup` which handles pre-commit installation automatically. Verification shows all hooks active including version-bump and pytest-validation.

### Example 3: Alex's Forgotten Setup (Error Recovery)
Alex Kim contributed 6 months ago and cloned fresh for a new feature. He forgets about pre-commit setup and commits code with trailing whitespace. The commit succeeds locally (no hooks), but he notices the README mentions verification. He runs the check, sees "hooks: INACTIVE", installs them, and amends his commit before pushing.

### Example 4: CI Failure Diagnosis (Troubleshooting)
Jordan Lee's push fails CI with ruff errors. The troubleshooting guide in CONTRIBUTING.md says "If CI fails but local commit succeeded, verify hooks are active." Jordan runs the verification, sees hooks were inactive, installs them, runs `pre-commit run --all-files`, fixes the issues, and successfully pushes.

## UAT Scenarios (BDD)

### Scenario: New contributor follows setup guide successfully
```gherkin
Given Marco Rossi has cloned the nWave repository
And he has never contributed before
When Marco opens the README.md
Then Marco sees a prominent "First Time Setup" section within the first 50 lines
And the section includes the command "pre-commit install"
And the section includes a verification command to confirm hooks are active
```

### Scenario: Developer verifies pre-commit hooks are active
```gherkin
Given Sarah Chen has cloned the nWave repository
And she has run "pre-commit install"
When Sarah runs the hook verification command
Then she sees confirmation that pre-commit hooks are ACTIVE
And she sees the list of installed hooks including "ruff" and "nwave-version-bump"
```

### Scenario: Developer discovers inactive hooks before push
```gherkin
Given Alex Kim has a local clone without pre-commit hooks installed
When Alex runs the hook verification command
Then he sees a warning that pre-commit hooks are INACTIVE
And he sees the exact command to install hooks
And he sees a recommendation to run "pre-commit run --all-files" after installation
```

### Scenario: CONTRIBUTING.md exists with required sections
```gherkin
Given the nWave repository exists
When a developer opens CONTRIBUTING.md at repository root
Then the document includes a "Development Environment Setup" section
And the section includes pre-commit installation instructions
And the section includes verification steps
And the section includes troubleshooting for CI failures
```

### Scenario: Makefile provides automation target (optional enhancement)
```gherkin
Given the nWave repository has a Makefile
When a developer runs "make setup" or "make dev-setup"
Then pre-commit is installed if not present
And pre-commit hooks are installed in the repository
And verification output confirms successful setup
```

### Scenario: CI failure troubleshooting guide exists
```gherkin
Given Jordan Lee's push has failed CI with lint errors
When Jordan consults the CONTRIBUTING.md troubleshooting section
Then Jordan finds guidance for "CI fails but local commit succeeded"
And the guidance directs Jordan to verify hook installation
And the guidance provides commands to fix the issue
```

### Scenario: README cross-references CONTRIBUTING.md
```gherkin
Given a developer is reading the nWave README.md
When they look at the "Contributing" section
Then they see a link to CONTRIBUTING.md
And they see "IMPORTANT: Run pre-commit install before your first commit"
```

## Acceptance Criteria

- [ ] CONTRIBUTING.md file exists at repository root with "Development Environment Setup" section
- [ ] Setup section includes: `pip install pre-commit && pre-commit install` command
- [ ] Setup section includes verification command (e.g., `ls -la .git/hooks/pre-commit` or custom script)
- [ ] Setup section includes explanation of what hooks enforce (ruff, yaml validation, version bump)
- [ ] Troubleshooting section addresses "CI fails but local commit succeeded" scenario
- [ ] README.md "First Time Setup" or "Contributing" section prominently mentions hook installation
- [ ] README.md links to CONTRIBUTING.md for full details
- [ ] (Optional) Makefile target `make setup` or `make dev-setup` automates the process

## Technical Notes

- Pre-commit config already exists: `.pre-commit-config.yaml` with 13 hooks across 3 repos
- Hooks include: ruff lint/format, YAML validation, version-bump, pytest-validation, docs-freshness
- Some hooks run at different stages: pre-commit, post-commit, pre-push
- Verification should check `.git/hooks/pre-commit` file existence and content
- Consider a simple Python script for cross-platform verification: `scripts/verify-dev-setup.py`

## Dependencies

- **Depends on**: None (standalone documentation task)
- **Enables**: Better contributor experience, reduced CI failures, faster onboarding

## Story Sizing Assessment

- **Effort**: 1-2 days (documentation + optional script)
- **Scenarios**: 7 UAT scenarios
- **Value**: HIGH - affects all contributors, prevents recurring CI failures
- **Complexity**: LOW - primarily documentation with optional simple scripting

## Priority Recommendation

**HIGH** - This is a developer experience improvement that:
1. Prevents recurring CI failures (time waste)
2. Improves onboarding for new contributors
3. Has minimal implementation risk
4. Provides immediate value upon completion

---

*Story ID: US-DEV-001*
*Wave: DISCUSS*
*Status: DRAFT*
*Created: 2026-01-29*
*Author: Riley (Requirements Analyst)*
