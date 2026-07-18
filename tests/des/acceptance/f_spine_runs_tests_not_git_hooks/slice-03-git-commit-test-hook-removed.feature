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

  # ---- CT-6: the interim net is RETIRED, and the retirement is LOUD -----------
  #
  # UPDATED 2026-07-18 (Ale-ratified): the interim net's own exit precondition --
  # "dropped once the feature-end certainty is proven" -- is now SATISFIED: the
  # feature-end cycle runs the full suite itself, so the pre-push duplicate was
  # paying the same cost twice on every push. The hook moved to `stages: [manual]`.
  #
  # The INVARIANT is unchanged and still enforced here: no test authority may
  # vanish SILENTLY. What the scenario asserts flips from "the net is present"
  # to "the net is retired AND the retirement names its consequences in the
  # config text" -- a bare `stages: [manual]` with no explanation would be the
  # silent drop this feature exists to forbid.

  @slice-03 @driving_port @real-io @us-interim-net @contract-shape:pure-function
  Scenario: The retired pre-push net names what replaced it and what it cost
    Given the shipped pre-commit config
    When the push-stage hooks are inspected
    Then the "pytest-quick-tiers" full-suite hook no longer fires at pre-push
    And the retirement of the pre-push full-suite is explained in the config text
