Feature: Documentation Accuracy
  As a new nWave user
  I want the installation documentation to be accurate
  So that I can successfully install nWave on a fresh machine

  Background:
    Given the installation guide exists at docs/installation/installation-guide.md

  # ==========================================================================
  # AC-10: Documentation Accuracy
  # ==========================================================================

  @ac10 @manual
  Scenario: Quick start commands work on virgin machine
    Given I have a fresh machine with Python installed
    And pipenv is installed via "pip install pipenv"
    When I follow the quick start instructions:
      | step | command                                              |
      | 1    | pipenv install --dev                                 |
      | 2    | pipenv run python scripts/install/install_nwave.py  |
    Then each command should succeed
    And nWave should be installed successfully

  @ac10
  Scenario: Prerequisites are correctly stated
    Given I read the installation guide prerequisites
    Then the prerequisites should include "Python 3.8 or higher"
    And the prerequisites should include "pipenv"
    And the prerequisites should NOT state "Python 3.11" as minimum

  @ac10
  Scenario: Quick start section includes virtual environment setup
    Given I read the quick start section
    Then the quick start should include "pipenv install"
    And the quick start should include "pipenv run" or "pipenv shell"
    And the quick start should NOT show bare "python3 scripts/install/install_nwave.py"

  @ac10
  Scenario: Documentation mentions pipenv requirement
    Given I read the installation guide
    Then the guide should mention pipenv is required
    And the guide should explain how to install pipenv
    And the guide should show pipenv commands for installation

  @ac10
  Scenario: Troubleshooting section addresses common errors
    Given I read the troubleshooting section
    Then the section should address "ModuleNotFoundError"
    And the section should address "not in virtual environment"
    And each error should have a solution with pipenv commands
