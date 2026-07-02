@feature-opt-in-per-step-double-review
Feature: Priya's opted-in review step is actually dispatched twice and a disagreement is never silently overruled
  As Priya, an nWave operator reading the DISTILL Final Wave Review Gate guide
  I want the dispatch procedure to consult the shipped requires_agreement(step_id)
    decision and apply the DD-3 agreement predicate
  So that a step she opts into require_agreement (slice-01) is not just resolvable
    in isolation but ACTUALLY dispatched twice, with disagreement or dispatch
    failure surfaced loudly instead of silently resolved

  # slice-02 (wiring-completion, DD-6/DD-7): slice-01 proved
  # ResolvedReviewStepSet.requires_agreement(step_id) resolves correctly via DIRECT
  # DESConfig calls, but the actual consumer -- nw-distill/SKILL.md's Final Wave
  # Review Gate dispatch prose (the SAME surface the sibling rigor-review-step-toggles
  # feature's own slice-07 wired to consult resolve_review_steps().active()/.model_for())
  # -- does not yet mention requires_agreement, double-dispatch, or the DD-3 agreement
  # predicate at all. ADR-RST-002 decision 4 is the wiring specification this slice
  # scaffolds against.
  #
  # This is a methodology-SKILL.md (LLM-consumed prose) change, not testable Python --
  # same artifact class as the sibling's own slice-07 (test pattern mirrored, not
  # cross-imported, per this feature's established per-feature self-containment
  # convention). Driving surface (real, in-process, hermetic -- no interpreter fork,
  # no ~/.claude path): a REAL file read of the shipped
  # nWave/skills/nw-distill/SKILL.md, scoped to the "## Final Wave Review Gate"
  # section (bounded by the next "## " heading).
  #
  # Domain Example coverage: #1 (agreement/happy-path capability) -> scenario 1;
  # #2 (disagreement escalation) -> scenario 3; #4 (dispatch failure, distinct
  # escalation class) -> scenario 4. #3 (untouched step, no regression) is
  # explicitly NOT re-scaffolded as its own scenario here -- slice-01 already
  # proves the resolver-level regression lock (requires_agreement resolves False
  # for every non-opted-in step); at THIS dispatch-prose layer, scenario 1's own
  # conditional-language check (the double-dispatch instruction is gated on
  # requires_agreement(step_id) being True, not unconditional) is the same
  # regression proof the sibling's slice-07 scenario #2 used for `.active()`
  # conditional dispatch -- a step Priya never opts in reads the SAME "for each
  # active step where ... is True" clause and is excluded by construction, so a
  # dedicated fifth Domain-Example-3 scenario would test the identical text
  # scenario 1 already inspects. Contract-shape induction (DD-3's outcome-class
  # predicate): scenario 2 proves the predicate classifies the FULL
  # {approved, conditionally_approved} vs {needs_revision, rejected} vocabulary,
  # not just the two example rows -- prose-testing's example-only analogue of a
  # property test (Mandate 9, layer-3+).

  @slice-02 @infrastructure @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: The dispatch procedure conditions double-dispatch on the opted-in accessor
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for double-dispatch conditioning
    Then the dispatch procedure dispatches an opted-in step's reviewer twice on the identical scope, conditioned on requires_agreement

  @slice-02 @infrastructure @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: The dispatch procedure encodes the full pass-class and fail-class vocabulary
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for the agreement predicate
    Then the dispatch procedure classifies every approval_status value into the correct pass-class or fail-class

  @slice-02 @infrastructure @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: A disagreement escalates and blocks the pass-and-move-on path instead of being silently resolved
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for disagreement handling
    Then the dispatch procedure surfaces both verdicts side by side and blocks the gate until a human resolves the disagreement

  @slice-02 @infrastructure @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: A dispatch failure escalates as a distinct unresolved class instead of falling back to the one completed verdict
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for dispatch-failure handling
    Then the dispatch procedure surfaces a missing or failed dispatch as an unresolved escalation distinct from a disagreement

  @slice-02 @infrastructure @driving_port @real-io @JOB-028 @contract-shape:pure-function @regression-lock
  Scenario: The Sentinel always-dispatches guarantee survives the double-dispatch rewrite
    Given the shipped nw-distill review-dispatch guide
    When the Final Wave Review Gate dispatch procedure is inspected for the Sentinel hard-pin guarantee
    Then the dispatch procedure still guarantees Sentinel always dispatches regardless of any per-step agreement opt-in
