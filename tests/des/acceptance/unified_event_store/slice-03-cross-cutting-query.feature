@feature-unified-event-store
Feature: A cross-cutting query caller gets one merged view with an honest could-not-verify count

  Charter: docs/product/expectations/unified-event-store/
           as-a-cross-cutting-query-caller-i-get-one-merged-view-across-legacy-and-unified-records-with-an.md

  A cross-cutting query caller asks the unified event store what it can say
  about a population that may include records it cannot fully determine. The
  store must never answer with a bare, possibly-shrunk total: a correct
  integer with no could-not-verify companion is the exact defect this slice
  exists to prevent (DD-9). The merged view must also say WHICH generation
  each record came from -- legacy (pre-cutover) or new-envelope -- and must
  never let "nothing happened" and "I never looked" print the same thing.

  # Driving port (Mandate 13): NO new @walking_skeleton here -- the feature's
  # ONE subprocess-E2E WS already lives in slice-02
  # (slice-02-startup-refusal.feature); the WS Strategy section forbids a
  # second one. Every scenario below drives
  # des.cli.event_store_query.main(argv, output=CapturingOutput()) --
  # Layer 2, content facet, IN-PROCESS. Real-CLI wiring for this new
  # subcommand (registry row, catalog entry, `des --help` discoverability)
  # is DELIVER's job this slice and is proven by Vera's real-surface EXAMINE
  # against EXP-unified-event-store-2 plus the feature-end env-e2e/full-suite
  # cycle -- never by a second subprocess scenario here (feature-delta.md
  # [REF] WS Strategy).
  #
  # Contract shape (Mandate 14): bounded-change -- a single-family read of
  # one partition key's ledger file is a BOUNDED filesystem read, never an
  # unbounded scan.
  #
  # Status (updated post-DELIVER, round-3 code-review): the first 7
  # scenarios below are GREEN -- des.cli.event_store_query is implemented
  # for real. The two round-2 scenarios (malformed / non-object ledger
  # line) are RED at HEAD for a REAL reason, not a scaffold: a code-review
  # pass found that UnifiedEventStoreAdapter.read() does not defend
  # against a corrupted line inside an otherwise-readable ledger file --
  # it raises uncaught instead of raising could_not_verify_count with a
  # named reason. The two round-3 scenarios (missing agent_id / missing
  # reduction_seq on an otherwise well-formed derived row) are RED at
  # HEAD for the SAME defect class one layer deeper: the row sails past
  # `_classify_line` clean into `derived_rows`, then crashes
  # `ReductionKeyDeduper.dedupe` with an uncaught `KeyError`. Every
  # scenario below fails for a semantic reason today (an assertion in the
  # step, or the composition's captured `unhandled_exception`) -- never a
  # collection/import error.
  #
  # Round-4 (DD-17, ADR-EVT-002 "Read-Path Row Recognition Contract --
  # Deny-by-Default"): inverts the read path from open-ended
  # "recognize known-bad, else accept" to closed "recognize known-good,
  # else could_not_verify". The R34 Gate-0 Outline is a GREEN pin (today's
  # non-dict-top-level closure already degrades correctly, by ACCIDENT of
  # TypeError control flow -- DD-17 turns that into a designed
  # precondition, and this Outline protects the refactor from regressing).
  # R35-R44 are genuinely RED at HEAD: every wrong-typed
  # agent_id/reduction_key/reduction_seq value on a primary-new or derived
  # row is TODAY silently counted as `measured` with zero could_not_verify
  # signal (SILENT-WRONG, verified by executing the real code against
  # every fixture below) -- except the lone NaN row, which today degrades
  # via the self-contradictory "0 records tied" reason R44 closes. The two
  # boundary-repair scenarios (R41 non-UTF-8 file, R42 oversized-integer
  # line, R43 extreme-nesting line) crash uncaught at HEAD
  # (`UnicodeDecodeError` / `ValueError` / `RecursionError`, none caught by
  # today's narrower `except` clauses -- verified by executing the real
  # code). R45 is a GREEN pin correcting a previously-WRONG test oracle
  # (the OLD "measured + could_not_verify == raw row count" law is false
  # in general once a reduction_key group holds more than one row; the
  # SAME `Then` step used by R32/R33/R45 was reformulated over KEYS, not
  # rows, so it now states a law that is actually true).

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R24 @covers-R25
  Scenario Outline: A query over a mixed ledger tags every row with the generation it came from
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding <legacy_count> legacy row(s) and <derived_count> new-envelope row(s) for partition key "unified-event-store"
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query reports <expected_measured> measured record(s)
    And every returned record is tagged with the generation it came from

    # Fixture note (peer-review BLOCKER 2, closed): each derived row this
    # fixture writes carries a DISTINCT reduction_key -- DD-7's
    # MAX(reduction_seq)-per-key rule therefore does NOT collapse any of
    # them, so expected_measured is simply legacy_count + derived_count.
    # This scenario's own oracle is about TAGGING (every row says which
    # generation it came from), never about dedup collapse -- DD-7/DD-8
    # collapse semantics already have real, dedicated coverage in the 31
    # green `test_event_store_aggregate.py` unit tests. Asserting a
    # collapsed count here would let a crafter implement the WRONG dedup
    # semantics and still pass this scenario.
    Examples:
      | legacy_count | derived_count | expected_measured |
      | 2            | 0             | 2                  |
      | 0            | 2             | 2                  |
      | 2            | 2             | 4                  |

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R26
  Scenario: The total and the could-not-verify count travel together, never a bare total
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the single reported output carries both a measured count and a could-not-verify count in the same answer
    And the caller never has to issue a second query to learn the could-not-verify count

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R27
  Scenario: An unreadable ledger file raises the could-not-verify count instead of silently shrinking the total
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger file itself has been made unreadable inside the caller's own sandbox
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the could-not-verify count is raised, naming a reason, rather than the measured total silently dropping

  # Two-When scenario (peer-review flagged, not blocking): deliberate. The
  # charter's own oracle (EXP-2 negative oracle c) is a COMPARISON between
  # two answers -- "distinguishable from" is a relational property that
  # cannot be pinned by observing either query in isolation, so this
  # scenario legitimately drives the CLI twice and asserts on the pair.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R28
  Scenario: A query for a never-seen partition key is distinguishable from a query that genuinely found zero events
    Given the cross-cutting query caller has a real repo with an empty "atdd-pure" ledger file for partition key "genuinely-empty-feature"
    And the cross-cutting query caller's repo has no ledger file at all for partition key "never-queried-feature"
    When the cross-cutting query caller queries family "atdd-pure" partition key "genuinely-empty-feature"
    And the cross-cutting query caller queries family "atdd-pure" partition key "never-queried-feature"
    Then the two answers are distinguishable
    And the "genuinely-empty-feature" answer reports zero measured records with zero could-not-verify
    And the "never-queried-feature" answer names a could-not-verify reason for the absent ledger

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R29
  Scenario: The query never mutates the store it reads
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 1 new-envelope row(s) for partition key "unified-event-store"
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query reports 3 measured record(s)
    And the telemetry root is left with the same entries it started with

  # Code-review gap (closed here): a ledger line can be PRESENT and
  # READABLE but not valid JSON -- a truncated write (e.g. earlyoom killing
  # a process mid-append, concretely observed on this box). This is a
  # DIFFERENT fault than an unreadable FILE (the scenario above): there,
  # the whole file could not be opened; here, the file opens fine and most
  # of its lines parse fine, but ONE line is corrupt. The two must be told
  # apart in the store's own words, or an operator debugging "why did my
  # count include a could-not-verify" cannot tell a permissions problem
  # from a corrupted-write problem.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R30
  Scenario: A malformed (truncated) ledger line raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one truncated (malformed JSON) line
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a malformed ledger line, distinguishable from an unreadable-file reason

  # Sibling corruption class (author's call, recorded per code-review
  # ask): valid JSON that is NOT a JSON object (here, a bare string) is
  # truncation-ADJACENT but structurally distinct from a truncated line --
  # `json.loads` succeeds on it, so any defect must surface one step
  # later, wherever a row is classified/read as a mapping (e.g. `"key" in
  # row` or `LegacyEnvelopeNormalizer.normalize`'s own Mapping check).
  # Kept as its OWN scenario rather than folded into the one above:
  # (1) the two faults trip different code paths (json.loads failing vs.
  # succeeding-but-wrong-shape), so a fix that only handles one class must
  # not read green on the other; (2) one fixture asserting two distinct
  # reason strings on two different corrupt rows in the SAME payload would
  # blur which assertion pins which fault.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R31
  Scenario: A ledger line that is valid JSON but not an object raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one row that is valid JSON but not a JSON object
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a non-object ledger row, distinguishable from an unreadable-file reason

  # Round-3 regression (code-review found the SAME defect class as the two
  # scenarios above, one layer DEEPER): a ledger row can be well-formed
  # JSON, BE a dict, HAVE envelope_generation and reduction_key -- so it
  # sails past `_classify_line` clean into `derived_rows` -- and STILL be
  # missing a key `ReductionKeyDeduper.dedupe` requires. Reproduced: a row
  # missing `agent_id` entirely crashes with an uncaught `KeyError:
  # 'agent_id'` at `event_store_aggregate.py:100`; a row missing
  # `reduction_seq` (agent_id present) crashes with an uncaught `KeyError:
  # 'reduction_seq'` at `event_store_aggregate.py:111`. Same consequence as
  # the two scenarios above: a raw traceback, zero `EventStoreQueryResult`
  # emitted, zero telemetry. DISTINCT from DD-8's already-covered
  # agent_id-present-but-NULL case (that degrades correctly today) --
  # ABSENT is a different fault than NULL, and the two must not be
  # conflated in the reported reason.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R32
  Scenario: A derived ledger row missing its agent_id key raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row with no agent_id key at all
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the query exits with status 0
    And the could-not-verify count names a reason identifying a derived row missing its agent_id key entirely, distinguishable from a null-agent_id reason, a malformed-line reason, a non-object-row reason, and an unreadable-file reason
    And the measured and could-not-verify counts conserve the ledger's population, counting rows that share a reduction key as one fact

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R33
  Scenario: A derived ledger row missing its reduction_seq key raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row with no reduction_seq key at all
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the query exits with status 0
    And the could-not-verify count names a reason identifying a derived row missing its reduction_seq key entirely, distinguishable from an ambiguous-tied-max reason, a malformed-line reason, a non-object-row reason, and an unreadable-file reason
    And the measured and could-not-verify counts conserve the ledger's population, counting rows that share a reduction key as one fact

  # Round-4 (DD-17, ADR-EVT-002 "Read-Path Row Recognition Contract --
  # Deny-by-Default"): the read path inverts from open-ended "recognize
  # known-bad, else accept" to closed "recognize known-good, else
  # could_not_verify". Gate 0 (isinstance(row, dict)) already degrades
  # correctly TODAY for the bare-string case (R31) via an ACCIDENT of
  # control flow (TypeError bubbling out of the `in` operator / out of
  # LegacyEnvelopeNormalizer.normalize's own Mapping check) -- this Outline
  # pins the REMAINING closed vocabulary of non-dict top-level JSON values
  # ADR-EVT-002 names explicitly, which today ALSO already degrade
  # correctly via that SAME accident (verified by executing the real code).
  # DD-17 turns the accident into a designed precondition; these scenarios
  # protect that refactor from a regression, they do not newly fail today.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R34
  Scenario Outline: A ledger row whose top-level JSON value is not an object is rejected the same way a bare string already is, naming the type it actually found
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one row whose top-level JSON value is <shape>
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a non-object ledger row, distinguishable from an unreadable-file reason

    Examples:
      | shape          |
      | a JSON array   |
      | a bare number  |
      | a bare boolean |
      | a bare null    |

  # From here down: the SILENT-WRONG half of DD-17 -- today, EVERY row in
  # every Outline below is silently counted as `measured` with ZERO
  # could_not_verify signal (verified by executing the real code against
  # each fixture: measured=1, could_not_verify=0 in every case except the
  # NaN row, which degrades today via the self-contradictory reason R44
  # closes). These scenarios are genuinely RED at HEAD.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R35
  Scenario Outline: A primary-new row whose agent_id is not None or a string is rejected instead of silently counted as measured
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one primary-new row whose agent_id is <wrong_type>
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a primary-new row's agent_id as the wrong type

    Examples:
      | wrong_type |
      | a list     |
      | a dict     |
      | an int     |
      | a float    |
      | a bool     |

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R36
  Scenario Outline: A derived row whose agent_id is not None or a string is rejected instead of silently counted as measured
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row whose agent_id is <wrong_type>
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a derived row's agent_id as the wrong type, distinguishable from a null-agent_id reason

    Examples:
      | wrong_type |
      | a list     |
      | a dict     |
      | an int     |
      | a float    |
      | a bool     |

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R37
  Scenario Outline: A derived row whose reduction_key is not a non-empty string is rejected instead of silently counted as measured
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row whose reduction_key is <wrong_value>
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a derived row's reduction_key as inadmissible

    Examples:
      | wrong_value     |
      | null            |
      | an empty string |
      | an int          |
      | a float         |
      | a bool          |
      | a list          |
      | a dict          |

  # bool is excluded even though isinstance(True, int) is True in Python
  # (`type(value) is int`, not isinstance) -- and float/NaN are excluded,
  # which removes the NaN != NaN self-contradiction (R44) by construction,
  # never by special-casing NaN inside max().
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R38 @covers-R39
  Scenario Outline: A derived row whose reduction_seq is not exactly an int is rejected instead of silently counted as measured or ambiguously tied
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row whose reduction_seq is <wrong_value>
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying a derived row's reduction_seq as the wrong type, distinguishable from an ambiguous-tied-max reason

    Examples:
      | wrong_value |
      | true        |
      | false       |
      | a float     |
      | NaN         |
      | a string    |
      | null        |
      | a list      |
      | a dict      |

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R40
  Scenario: A derived row with agent_id, reduction_key, and reduction_seq all wrong at once is rejected in one pass, naming every violated field
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row whose agent_id, reduction_key, and reduction_seq are all the wrong type at once
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names every one of the three violated fields from this single query, never requiring a second round to discover the rest

  # Two SEPARATE boundary repairs (ADR-EVT-002 keeps them distinct from the
  # row-shape gate above and from each other -- different granularity,
  # different representation transition, different control-flow mechanism).
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R41
  Scenario: A ledger file that is not valid UTF-8 raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger file itself has been corrupted with invalid UTF-8 bytes
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the could-not-verify count is raised, naming a reason, rather than the measured total silently dropping

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R42
  Scenario: A ledger line containing an oversized integer literal raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one line with an integer literal beyond CPython's int-string conversion limit
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying an oversized-integer ledger line, distinguishable from a malformed-JSON-line reason

  @slice-03 @driving_port @contract-shape:bounded-change @covers-R43
  Scenario: A ledger line with extreme JSON nesting depth raises the could-not-verify count instead of crashing the query
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one line with extreme JSON nesting depth
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And the query reports 2 measured record(s)
    And the could-not-verify count names a reason identifying an excessively-nested ledger line, distinguishable from a malformed-JSON-line reason

  # A group of size ONE whose sole member's reduction_seq is NaN reproduces
  # today's self-contradictory "ambiguous tied-max ... (0 records tied)"
  # reason (NaN != NaN discards even the max() winner). DD-17 closes this
  # by rejecting the row via R39's type contract BEFORE it can ever reach
  # the tied-max grouping code -- the Then step asserts the GENERAL
  # invariant, not merely this one fixture, so it would also catch a
  # future regression of the same shape.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R44
  Scenario: A could-not-verify reason never claims a tie among fewer than two records
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 0 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds one derived row, alone in its reduction_key group, whose reduction_seq is NaN
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query completes without crashing
    And no could-not-verify reason claims a tie among fewer than two records

  # Corrects the conservation LAW itself (not new production behaviour --
  # DD-7's MAX-per-key collapse already ships correctly; this AT exercises
  # it at the CLI surface for the first time and proves the corrected,
  # KEY-based oracle is non-vacuous): 3 raw rows sharing one reduction_key
  # with a single unambiguous winner collapse into exactly 1 accounting
  # unit, which the OLD row-count-based law would have wrongly rejected.
  @slice-03 @driving_port @contract-shape:bounded-change @covers-R45
  Scenario: Rows sharing one reduction key collapse into a single accounting unit, never one unit per row
    Given the cross-cutting query caller has a real repo with a "atdd-pure" ledger holding 2 legacy row(s) and 0 new-envelope row(s) for partition key "unified-event-store"
    And the ledger also holds 3 derived rows sharing one reduction key with a single unambiguous winner
    When the cross-cutting query caller queries family "atdd-pure" partition key "unified-event-store"
    Then the query reports 3 measured record(s)
    And the measured and could-not-verify counts conserve the ledger's population, counting rows that share a reduction key as one fact
