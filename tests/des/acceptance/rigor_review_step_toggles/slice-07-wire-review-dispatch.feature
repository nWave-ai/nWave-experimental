@feature-rigor-review-step-toggles
Feature: Priya's disabled review step actually does not run in a real DISTILL dispatch
  As Priya, an nWave operator reading the DISTILL Final Wave Review Gate guide
  I want the dispatch procedure to consult the review-step registry
  So that a step she disables under rigor (slices 01-06) is not just resolvable
     in isolation but ACTUALLY skipped by the real review dispatch

  # slice-07 (wiring-completion, Ale-ratified 2026-06-30 post feature-end deep-review
  # gap): slices 01-06 proved DESConfig.resolve_review_steps() resolves correctly via
  # DIRECT calls, but NONE of them wired the resolver into the actual consumer --
  # nw-distill/SKILL.md's Final Wave Review Gate dispatch prose, which today
  # unconditionally instructs "Dispatch four reviewers in parallel" naming all four by
  # name, regardless of any config. DESIGN's own Reuse Analysis (feature-delta.md:217)
  # already specified this EXTEND row ("the registry generalizes the existing
  # skip/always-on logic to per-step; prose is regenerated to cite
  # resolve_review_steps()"); no prior slice executed it.
  #
  # This is a methodology-SKILL.md (LLM-consumed prose) change, not testable Python --
  # same artifact class as nw-rigor/SKILL.md (slice-05 precedent). The test pattern
  # mirrors slice-05 exactly: a real file read of the shipped, repo-tracked
  # nWave/skills/nw-distill/SKILL.md (NOT the installed ~/.claude/skills/ copy --
  # confirmed byte-identical at HEAD via diff, but nWave/skills/ is the canonical
  # install SOURCE per scripts/install/plugins/skills_plugin.py's OLD_HIERARCHICAL
  # fallback `project_root / "nWave" / "skills"`, and is the only copy portable/
  # testable in CI).
  #
  # Driving surface (real, in-process, hermetic -- no interpreter fork, no
  # ~/.claude path): a REAL file read of the shipped nWave/skills/nw-distill/SKILL.md,
  # scoped to the "## Final Wave Review Gate" section (bounded by the next "## "
  # heading) -- the SAME real-file-read pattern slice-05 drives against nw-rigor.
  #
  # RED today (#1/#2/#4) because the numbered dispatch procedure (step 1, lines
  # ~272-277) unconditionally lists all four reviewers with no resolver reference,
  # no `.active()` conditional-dispatch language, and a stale flat "4 Haiku reviewers"
  # cost line predating slice-02's per-step model resolution. GREEN today (#3,
  # regression-lock) because the Sentinel hard-pin guarantee ("ALWAYS dispatches")
  # already exists in the section's background prose (slice-04-era language) and MUST
  # survive the slice-07 rewrite.

  @slice-07 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: The dispatch procedure cites the review-step resolver as the dispatch mechanism
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for its dispatch mechanism
    Then the dispatch procedure cites the review-step resolver as the mechanism deciding which reviewers run

  @slice-07 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: The dispatch procedure makes dispatch conditional on active-step membership
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for conditional dispatch language
    Then the dispatch procedure states reviewers are dispatched only when active, not unconditionally

  @slice-07 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function @regression-lock
  Scenario: The Sentinel always-dispatches guarantee survives the dispatch-procedure rewrite
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for the Sentinel hard-pin guarantee
    Then the dispatch procedure still guarantees Sentinel always dispatches

  @slice-07 @infrastructure @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: The dispatch procedure describes per-step model resolution instead of a flat cost line
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for its cost-and-model description
    Then the dispatch procedure describes per-step model resolution instead of a flat four-Haiku assumption
