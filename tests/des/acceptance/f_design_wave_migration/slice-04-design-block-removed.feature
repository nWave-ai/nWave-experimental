@feature-f-design-wave-migration @slice-04
Feature: The DESIGN-absence BLOCK and hard MANDATORY-read are reconciled away (AT-8)
  As an operator running a feature that skipped the DESIGN wave
  I want every DESIGN-absence-keyed BLOCK veto and unconditional MANDATORY-read of
    the DESIGN artifact reconciled to an advisory / read-if-present across all four
    loci in the shipped skills
  So that the never-blocks invariant holds end-to-end and no surviving veto or
    hard-require silently re-blocks a DESIGN-skipped feature

  # slice-04 (@infrastructure, removal-only) of f-design-wave-migration. AT AT-8.
  #
  # TEST-FORMAT CONVERSION: Gherkin form of the passing plain-pytest
  # test_slice04_design_block_removed.py (6 tests -> 4 scenarios; each nw-distill
  # matrix's row + carve-out witness folded into one scenario per matrix, all
  # coverage retained, carpaccio ceiling <=5). The PRODUCTION reconciliation already
  # ships GREEN across all four loci, so these are GREEN-not-active-RED — the
  # expected state for a format conversion of passing behaviour. Each scenario stays
  # GENUINE (mutation-verifiable): re-inserting BLOCK into a matrix row, or MANDATORY
  # into the nw-deliver DESIGN step, reds the scenario.
  #
  # DRIVING SURFACE (Mandate-13, prose-surface case): the filesystem read of the
  # REAL shipped nw-distill + nw-deliver skills via the shared _skill_source helper.
  # Each oracle is DISCRIMINATING (both halves): ABSENCE — the BLOCK/MANDATORY token
  # is gone from the locus's OWN window; PRESENCE — an advisory / read-if-present
  # replacement is in the SAME window (reconciled, not merely deleted, so a no-op
  # deletion that also strips the advisory cannot false-green).
  #
  # THE FOUR LOCI: R-4 nw-distill 1st matrix ("warn vs block"); R-3 nw-distill 2nd
  # matrix ("Missing Upstream Artifacts"); R-1 nw-deliver DESIGN read MANDATORY
  # declass; R-2 nw-deliver READING ENFORCEMENT brief.md hard-require.

  @slice-04 @driving_port @real-io @us-distill-matrix @contract-shape:unbounded-preservation
  Scenario Outline: Each nw-distill matrix reconciles its DESIGN-absent BLOCK to an advisory
    When the shipped nw-distill skill is read
    Then the "<matrix>" matrix reconciles its DESIGN-absent block to an advisory

    Examples:
      | matrix          |
      | WARN_VS_BLOCK   |
      | MISSING_UPSTREAM |

  @slice-04 @driving_port @real-io @us-deliver-design-read @contract-shape:unbounded-preservation
  Scenario: The nw-deliver DESIGN read is declassed from mandatory to read-if-present
    When the shipped nw-deliver skill is read
    Then the nw-deliver DESIGN read is no longer mandatory and reads the artifact if present

  @slice-04 @driving_port @real-io @us-deliver-enforcement @contract-shape:unbounded-preservation
  Scenario: The nw-deliver reading-enforcement drops the brief.md hard-require but keeps the rest
    When the shipped nw-deliver skill is read
    Then the nw-deliver reading-enforcement no longer hard-requires brief.md but still requires the surviving reads
