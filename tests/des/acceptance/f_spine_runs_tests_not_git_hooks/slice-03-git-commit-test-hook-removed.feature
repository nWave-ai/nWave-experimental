@feature-f-spine-runs-tests-not-git-hooks
Feature: The git pre-commit test hook is removed; the safety net is kept and flagged
  As a developer relying on the commit/push gates
  I want the git pre-COMMIT test hook removed (the spine slice-AT gate is now the
    commit-time test authority), the FAST pre-commit hooks kept, and the pre-push
    full-suite net kept with an EXPLICIT interim marker naming its removal
    precondition
  So that commits are fast and no test authority silently vanishes -- the net can
    only be dropped once the feature-end certainty (CT-5/CT-6) is proven

  # slice-03 of f-spine-runs-tests-not-git-hooks. Implements the directive's
  # "REMOVE the FULL SUITE from commits; leave it on pre-push until certain".
  # Reuses `.pre-commit-config.yaml` structure. NEW: remove the `pytest-validation`
  # pre-commit hook entry; keep `pytest-fast-gate` at pre-commit; add a LOUD
  # interim-transition marker on the pre-push full-suite so the net cannot be
  # silently dropped before certainty (DDD-3 / DDD-4).
  #
  # DRIVING SURFACE (Mandate-13, @contract-shape:pure-function): the "port" IS the
  #   shipped `.pre-commit-config.yaml` read as DATA -- there is no subprocess /
  #   composition entry for a config-shape assertion. The AT reads the SAME real
  #   file shipped from the repo root (never an inline test string -- the
  #   protocol-driver prose-surface case: assert a shipped artifact, not a
  #   self-fulfilling fixture). observable = the presence/absence of named hook
  #   ids at each stage + the literal interim-marker phrase in the config text.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD `.pre-commit-config.yaml` STILL
  #   carries the `pytest-validation` pre-commit hook AND carries NO interim
  #   marker on the pre-push full-suite. Each scenario observes a semantic
  #   AssertionError against the expected post-removal / marked state. GREEN once
  #   DELIVER removes the `pytest-validation` entry and adds the interim marker.

  # ---- CT-5: the pre-commit test hook is gone; the fast gate stays ------------

  @slice-03 @driving_port @real-io @us-commit-hook-removed @contract-shape:pure-function
  Scenario: The pre-commit test-validation hook is removed
    Given the shipped pre-commit config
    When the commit-stage hooks are inspected
    Then the pre-commit "pytest-validation" test hook is absent
    And the fast pre-commit "pytest-fast-gate" hook is present

  # ---- CT-6: the pre-push net stays and carries the interim marker ------------

  @slice-03 @driving_port @real-io @us-interim-net @contract-shape:pure-function
  Scenario: The pre-push full-suite net is kept with an explicit interim marker
    Given the shipped pre-commit config
    When the push-stage hooks are inspected
    Then the pre-push "pytest-quick-tiers" full-suite hook is present
    And the pre-push full-suite carries the explicit interim removal marker
