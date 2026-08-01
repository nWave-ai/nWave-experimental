@feature-unified-event-store
Feature: One feature's events, merged into a single chronological timeline

  Charter: docs/product/expectations/unified-event-store/
           as-an-orchestrator-i-can-see-one-features-slice-commits-examine-review-verdicts-on-one-timeline.md

  An orchestrator needs one feature's slice-commit, examine-verdict, and
  review-verdict events readable as a single chronologically-ordered view,
  without naming a directory, a family, or how many ledgers exist (DD-13).
  Today the caller must know three separate paths and interleave them by
  hand; the `des event-store-query` default (no `--family`) mode replaces
  that with one command.

  # Driving surface (Owns-row correction, feature-delta.md [REF] Staging
  # Plan, human-authorized by Ale 2026-07-31): every scenario below drives
  # `des.cli.event_store_query.main(argv, output=)` IN-PROCESS with NO
  # `--family` -- the subcommand's own default cross-domain mode -- never
  # `CrossDomainReader.read_across()` directly. The correction explicitly
  # requires the AT to drive "the subcommand itself, not the internal
  # composition helper"; driving the internal reader class would bypass the
  # composition-root driving port (Mandate-16). The subcommand's default
  # mode is itself a thin scaffold: it constructs `CrossDomainReader` and
  # calls `read_across()` uncaught, so the scaffold's `AssertionError`
  # still bubbles all the way to this AT's composition -- the RED reason is
  # unchanged in substance from the earlier direct-call shape, only the
  # driving surface moved up to the real composition root.
  #
  # Contract shape (Mandate 14): bounded-change -- read_across merges a
  # known, bounded set of per-family JSONL files for one partition key,
  # never an unbounded scan.
  #
  # RED at HEAD (unified-event-store slice-04): CrossDomainReader is a
  # DISTILL-authored scaffold whose read_across() raises a bare
  # AssertionError. Every scenario below fails for that reason today -- a
  # semantic AssertionError, never a collection/import or CLI-argument
  # error (the composition catches it narrowly and records it on the
  # observable, mirroring slice-03's QueryObservable).

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R46 @covers-R47
  Scenario: An orchestrator sees a slice-commit, an examine verdict, and a review verdict as one chronological timeline
    Given a fixture feature with a slice-commit, an examine verdict, and a review verdict recorded across the three ledgers, in that chronological order
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains all three events in ascending chronological order
    And each row names which ledger family it came from

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R48
  Scenario: No event silently vanishes, and a re-recorded event still counts once, when several events share a ledger
    Given a fixture feature with 2 slice-commit events, 1 examine verdict, 1 review verdict, and 1 further review verdict re-recorded twice under one reduction key
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains exactly 5 records, none of the 5 distinct events dropped, and the re-recorded review verdict counted once, not twice

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R49
  Scenario: Rows sharing one reduction key still count once in the merged timeline
    Given a fixture feature with 4 derived events sharing one reduction key recorded in the review ledger
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains exactly 1 record for that reduction key, not 4

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R50
  Scenario: The merged result always carries an arity-safe could-not-verify count
    Given a fixture feature with a slice-commit, an examine verdict, and a review verdict recorded across the three ledgers, in that chronological order
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the result carries a could-not-verify count of zero, present rather than omitted

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R51
  Scenario: A could-not-verify count from one family is never reset by reading the next
    Given a fixture feature with one wrong-typed row in the atdd-pure ledger and a different wrong-typed row in the review ledger
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the result's could-not-verify count is 2
    And the result names 2 distinct could-not-verify reasons, one per family

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R52
  Scenario: One family's ledger being unreadable does not silence the other families
    Given a fixture feature with events in all three ledgers, but the review ledger file is unreadable
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline still contains the atdd-pure and examine events
    And the result's could-not-verify count names the review family's read failure

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R53
  Scenario: One family's ledger holding a wrong-typed row does not exclude its well-formed siblings
    Given a fixture feature with a well-formed slice-commit event and, in the same ledger, one event whose agent id is a list instead of text
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline still contains the well-formed slice-commit event
    And the result's could-not-verify count names the wrong-typed row

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R54
  Scenario: A family with no ledger file contributes nothing, not a could-not-verify
    Given a fixture feature with events in the atdd-pure and examine ledgers only, and no review ledger file at all
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains only the atdd-pure and examine events
    And the result carries a could-not-verify count of zero, present rather than omitted

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R55
  Scenario: Two events from different families sharing the same timestamp are both retained
    Given a fixture feature with an examine verdict and a review verdict recorded at the identical timestamp
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains both events, neither dropped as a duplicate

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R56
  Scenario: An event with no timestamp is could-not-verify, never silently ordered
    Given a fixture feature with a review verdict recorded with no timestamp field
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the result's could-not-verify count names the missing timestamp

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R57
  Scenario: An event whose timestamp is a number, not text, is could-not-verify with a distinct reason
    Given a fixture feature with a review verdict recorded with a numeric timestamp
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the result's could-not-verify count names the wrong-typed timestamp
    And that reason is distinguishable from a missing-timestamp reason

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R58
  Scenario: Two events tied on timestamp with mismatched seq types degrade one, not crash the merge
    Given a fixture feature with two events sharing one timestamp, one recorded with an integer seq and one recorded with a string seq
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the query does not crash and the exit code is 0
    And the result's could-not-verify count names the seq field and its wrong type, distinguishable from the timestamp reasons
    And the merged timeline still contains the well-formed sibling event, counted in the measured count

  @slice-04 @driving_port @real-io @contract-shape:bounded-change @covers-R59
  Scenario: An event with no seq is a legitimate measured record, and the absent seq sorts as zero
    Given a fixture feature with three events at the identical timestamp: seq -1, no seq field at all, and seq 1
    When the orchestrator reads across the atdd-pure, examine, and review families for that feature
    Then the merged timeline contains all three events, each counted as measured
    And the merged order is seq -1, then the no-seq event, then seq 1, pinning the absent seq to sort as zero
