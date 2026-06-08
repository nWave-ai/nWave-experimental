@feature-gate-trailer-read-seam-a-indeterminate @slice-02
Feature: The CommitTrailerReadPort commit_messages contract is fully hardened across all partition boundaries
  As an nWave operator whose CI runs the deliver-integrity gate on any target machine
  I want the CommitTrailerReadPort.commit_messages method to correctly handle every
    partition its contract promises — a repo with many commits, a path that does not
    exist, and a path that exists but is not a work-tree
  So that the done-gate never silently reads "nothing shipped" when git fails, and
    never misses commits when the history is multi-entry (many-cardinality)

  # slice-02 of gate-trailer-read-seam-a-indeterminate (DISCUSS Slice Plan slice-02
  # + DESIGN Driving Surface table "slice-02 / No new seam"). These ATs close the
  # carry-forward deep-review findings from the predecessor feature:
  #   D1 (C3): commit_messages with N>1 commit messages -- the many-cardinality path
  #             was NOT AT-covered by predecessor slices 01-02. The done-gate scans
  #             ALL commit bodies for Slice-Id trailers; if the adapter silently
  #             truncated to 1 message the scan would miss shipped slices.
  #   D2 (C6a): non-existent repo Path -- a distinct partition from "path exists but
  #              is not a work-tree". Both must degrade LOUD to Indeterminate; the
  #              prior ATs only exercised the not-a-work-tree partition.
  #
  # DRIVING SURFACE (Mandate-13, tolerable contract-AT variant -- the same shape
  # as the predecessor slice-02 + DESIGN Driving Surface "slice-02" entry):
  # The DESIGN table states "ATs drive the adapter directly or via a thin harness;
  # no CLI surface change." commit_messages is a port-contract method on a driven
  # port, NOT a CLI behavior -- it has no CLI entry point. The honest shape is
  # therefore the port-contract variant: the PUBLIC design-intended boundary of
  # GitCommitTrailerReadAdapter (the driven-port implementation class), driven
  # directly from the composition root service method. This is NOT a forbidden
  # direct-domain import: GitCommitTrailerReadAdapter implements the
  # CommitTrailerReadPort ABC and is the textbook driven-port adapter (the
  # Architecture-of-Reference "driven internal" treatment -- real adapter via
  # the composition root). The adapter IS the composition root for this slice
  # because there is no CLI surface to drive. Per Mandate-13 the port boundary
  # is the driving surface; per the DESIGN table this is the sanctioned shape.
  # Mandate 9 v2 OR-reduction: the adapter exercises REAL git I/O (real git work
  # tree for D1, real filesystem for D2/D3), so this slice is @real-io and
  # example-based + assert_state_delta is the correct treatment (no PBT).
  #
  # NON-VACUITY (perturbation-bound): the many-cardinality scenario includes a
  # non-vacuity control -- a repo with exactly 1 commit also returns CommitMessages
  # containing that commit body. The N>1 result is NOT a trivial always-pass
  # because a buggy adapter that truncated to 1 message would fail the N=3
  # assertion. The Indeterminate scenarios use two structurally-distinct error
  # paths (FileNotFoundError vs CalledProcessError) to prove both degrade LOUD.
  #
  # RED-or-GREEN-on-author (empirically verified at authorship HEAD):
  #   D1 many-cardinality: GitCommitTrailerReadAdapter.commit_messages iterates all
  #     git log output and splits on \x1e. For N=3 commits the split produces N+1
  #     elements (trailing empty from the final \x1e). The AT asserts that all three
  #     known commit message bodies are present in the returned tuple -- this is
  #     GREEN-on-author (the adapter already returns all messages).
  #   D2 non-existent path: subprocess.run(cwd=non_existent) raises FileNotFoundError
  #     before any git process starts -> caught by the adapter's except FileNotFoundError
  #     branch -> returns Indeterminate. GREEN-on-author (already handled).
  #   D3 exists-but-not-work-tree: git log on a plain directory returns non-zero ->
  #     CalledProcessError -> caught -> returns Indeterminate. GREEN-on-author.
  #   All three are COVERAGE-PIN ATs (behavior already correct; the ATs pin the
  #   contract so future refactors cannot silently break these partitions).
  #
  # TAG SCHEME: scenario @tags convert to dynamic pytest marks via pytest-bdd's
  # tag pipeline; the project's filterwarnings (pyproject.toml) suppresses
  # PytestUnknownMarkWarning so --strict-markers does not reject them. Step literal
  # text is unique within this feature directory (S1 step-text-uniqueness invariant
  # -- no overlap with slice-01's step literals).

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A repo with three commits yields all three message bodies from the many-cardinality read
    Given a git work-tree containing three commits with distinct message bodies
    When the port reads the full commit-message stream from that work-tree
    Then the returned stream contains all three commit message bodies
    And the stream is not truncated to fewer messages than the repo holds
    And the port read does not modify the work-tree

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A path that does not exist on the filesystem degrades loud to cannot-read rather than an empty stream
    Given a repo path that does not exist on the filesystem
    When the port attempts to read the commit-message stream from that absent path
    Then the port signals a loud cannot-read refusal rather than an empty message stream
    And the cannot-read refusal carries a non-empty reason

  @slice-02 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A path that exists on the filesystem but is not a git work-tree also degrades loud to cannot-read
    Given a directory that exists on the filesystem but contains no git repository
    When the port attempts to read the commit-message stream from that non-work-tree path
    Then the port signals a loud cannot-read refusal rather than an empty message stream
    And the cannot-read refusal is structurally identical to the absent-path refusal
