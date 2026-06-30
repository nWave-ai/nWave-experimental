@feature-f-nonbypassable-attestation @slice-03
Feature: A truncated feature with pending slices cannot be declared done
  As a developer declaring a feature done
  I want the done-gate to refuse when any Slice-Plan row is not shipped
  So that a feature whose slices were never delivered cannot be declared done
    even though every committed slice reconciled (backlog residual (b))

  # slice-03 of f-nonbypassable-attestation (KPI-1 residual (b), DDD-5). The
  # done-gate parses the feature-delta Slice Plan and vetoes on any Status that is
  # not `shipped`. Reuses the canonical Slice-Plan `Status` column the plan itself
  # declares. Also carries CT-7: the git-absent / non-Python degrade-LOUD path
  # (C7 environment taxonomy) -- same done-gate driving surface, INDETERMINATE.
  #
  # DRIVING SURFACE (Mandate-13, Layer-3 composition): verify_deliver_integrity.main
  #   observable = exit code (FAIL=1 on a pending slice; INDETERMINATE=4 git-absent).
  #
  # DISTINCT FIXTURE PER VERDICT: all-shipped (clears) vs one-pending (refuses) vs
  #   git-absent (cannot-certify) are three different project states.
  #
  # CAUSE-DISCRIMINATOR: the git-absent INDETERMINATE names the git/work-tree
  #   cause, distinguishing it from slice-02's bypass-debt INDETERMINATE.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the done-gate does NOT parse the
  #   Slice Plan, so a one-pending-row plan currently CLEARS where a REFUSAL is
  #   expected -- a semantic AssertionError. GREEN once DELIVER folds the
  #   all-shipped assertion into verify_deliver_integrity.

  @slice-03 @walking_skeleton @driving_port @real-io @us-no-truncated-done @error @contract-shape:unbounded-preservation
  Scenario: A feature with a pending slice is refused though every commit reconciled
    Given a complete feature whose slice plan has a pending slice
    When the developer declares the feature done
    Then the done-gate refuses with a definite failure
    And the refusal names the pending slice

  @slice-03 @driving_port @real-io @us-no-truncated-done @contract-shape:unbounded-preservation
  Scenario: A feature whose every slice is shipped clears
    Given a complete feature whose slice plan is entirely shipped
    When the developer declares the feature done
    Then the done-gate clears the feature

  # C3-ZERO obligation (Grenning ZOMBIES — the empty iterative surface). The
  # slice-plan assertion iterates plan rows; the zero-rows case is the terminal
  # branch the loop body never exercises. A feature with no plan rows MUST NOT be
  # falsely refused — the assertion never manufactures a refusal where no plan
  # declares work. GREEN at HEAD: the shipped `_undelivered_slice_plan_slices`
  # returns [] on an absent/header-only Slice Plan, so the done-gate clears. This
  # AT pins that contract (regression guard against a future change that flags
  # an empty plan as truncated).
  @slice-03 @driving_port @real-io @us-no-truncated-done @contract-shape:unbounded-preservation
  Scenario: A complete feature that declares no slice plan is not falsely refused
    Given a complete feature whose slice plan declares no slices
    When the developer declares the feature done
    Then the done-gate clears the feature

  @slice-03 @driving_port @real-io @us-no-truncated-done @error @contract-shape:unbounded-preservation
  Scenario: Declaring done where the work-tree is unreadable cannot be certified
    Given a complete feature on a target that is not a git work-tree
    When the developer declares the feature done
    Then the done-gate cannot certify the feature
    And the refusal names the unreadable work-tree
