@feature-fix-commit-slice-omits-slice-id-trailer
Feature: des commit-slice stamps the Slice-Id trailer mechanically from --slice-id
  As a spine driver committing a carpaccio slice with des commit-slice
  I want the Slice-Id: trailer stamped mechanically from --slice-id (like Gate-Scope is)
  So that I never ship a slice commit missing its Slice-Id and hit a downstream
    verify-slice-commit failure

  # C9 of consolidation-for-wider-beta-testing. Mode: atdd_pure, cohort S, single
  # slice-01.
  #
  # The defect: `des commit-slice` (src/des/cli/commit_slice.py) appends the
  # Gate-Scope: trailer mechanically (correct-by-construction) but does NOT handle
  # the Slice-Id: trailer -- the orchestrator must hand-add `Slice-Id: slice-NN`
  # to the --message. This is the SAME discipline-gap class the Gate-Scope amend
  # already closed (commit_slice.py:9-19): a forgotten Slice-Id surfaces downstream
  # at verify-slice-commit, not at commit-time.
  #
  # The fix, three seams (none exist at HEAD):
  #   (1) `_build_parser` (commit_slice.py:87) gains an optional `--slice-id` arg.
  #   (2) `main` appends `Slice-Id: {slice_id}` to the message body IDEMPOTENTLY
  #       (skip if a Slice-Id trailer is already present) BEFORE the Gate-Scope
  #       placeholder commit -- reusing `des.domain.slice_id_trailer.extract_slice_ids`
  #       for the presence check + the trailer shape.
  #   (3) `main` refuses up-front (exit 2, MalformedInput-class) if neither
  #       --slice-id is given nor a Slice-Id: trailer is already in the message.
  #
  # Driving port (Mandate-13): the REAL `commit_slice.main` CLI surface, driven
  # in-process (Layer 3) over a HERMETIC tmp_path git repo (git init + a staged
  # file -- NOT this repo). The observable Universe is the committed git artifact:
  # `git log -1 --format=%B HEAD` trailers + the CLI exit code. Only the git
  # work-tree is real-IO; the commit_slice resolution is the REAL production code
  # under test (it runs its own run_contract_gate verify subprocess unchanged).
  #
  # active-RED scaffold (atdd_pure -- NOT @skip):
  #   * AC-1 RED: no `--slice-id` arg exists at HEAD -> argparse raises SystemExit
  #     (the arg is unrecognised) -> the stamp never happens -> no `Slice-Id:`
  #     trailer in HEAD. The Then RED-fails for the right reason (missing
  #     functionality: the arg + the stamp), never a fixture/import error.
  #   * AC-3 RED: no refuse-if-absent guard at HEAD -> a Slice-Id-less message
  #     commits with exit 0 -> the refusal assertion RED-fails.
  #   * AC-2 / AC-4: live-green preservation guards (a message-carried Slice-Id is
  #     committed verbatim today; the Gate-Scope SliceCommitted/GateScopeVerified
  #     mechanics already pass).

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A passed --slice-id stamps a Slice-Id trailer on the slice commit
    Given a hermetic git repo with a staged change ready to commit
    And the slice-commit message body carries no Slice-Id trailer
    When the slice is committed with slice id "slice-01"
    Then the committed slice commit carries the trailer "Slice-Id: slice-01"

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A message already carrying a Slice-Id is preserved with no duplicate
    Given a hermetic git repo with a staged change ready to commit
    And the slice-commit message body already carries the trailer "Slice-Id: slice-02"
    When the slice is committed with no slice id passed
    Then the committed slice commit carries exactly one Slice-Id trailer for "slice-02"

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Neither a --slice-id nor a message Slice-Id is refused up-front
    Given a hermetic git repo with a staged change ready to commit
    And the slice-commit message body carries no Slice-Id trailer
    When the slice is committed with no slice id passed
    Then the slice commit is refused with a non-zero exit
    And no Slice-Id-less slice commit is produced

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Stamping a Slice-Id leaves the Gate-Scope commit mechanics unchanged
    Given a hermetic git repo with a staged change ready to commit
    And the slice-commit message body carries no Slice-Id trailer
    When the slice is committed with slice id "slice-01"
    Then the slice commit is a verified Gate-Scope commit
