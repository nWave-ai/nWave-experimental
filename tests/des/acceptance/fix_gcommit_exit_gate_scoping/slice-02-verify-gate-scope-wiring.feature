@feature-fix-gcommit-exit-gate-scoping
Feature: The exit-gate verify check re-verifies a Gate-Scope trailer over the committed tree

  As the U2 G_COMMIT exit gate that re-verifies a committed Gate-Scope trailer
    on the spine's hot path
  I want the verify check (and the terminating trailer compute it mirrors) to
    fingerprint the committed contract suite at the pinned revision, not whatever
    untracked work happens to sit beside it in the working tree
  So that one pinned commit verifies the same way whether or not co-resident
    untracked work-in-progress is present -- the daily amend-loop and the
    near-data-loss off-tree-hold bootstrap are retired for every commit

  # slice-02 (WIRING -- the constraint-elevating slice).
  #
  # slice-01 shipped a reproducible `des run-contract-gate
  # --committed-scope-digest` MODE, but nothing on the exit-gate hot path
  # invokes it: the verify check
  # (`run_contract_gate._mode_verify_gate_scope:488`, `--verify-gate-scope`)
  # AND the terminating Gate-Scope trailer compute (`:547`) both still derive a
  # WORKING-TREE digest (`gate_scope_digest(repo)`). slice-02 switches BOTH
  # sites to the committed-scope digest shipped in slice-01.
  #
  # OBSERVABLE OUTCOME: for ONE pinned commit carrying a `Gate-Scope:` trailer,
  # the verify check produces a BYTE-IDENTICAL verdict (verified, exit 0)
  # whether or not an untracked co-resident contract file is present in the
  # working tree. Today, at HEAD, the working-tree verify (`:488`) PERTURBS the
  # fresh digest when an untracked co-resident file is on disk ->
  # `GateScopeUnverified reason=mismatch` (exit 1) -> the amend-loop. After
  # GREEN both working-tree states verify identically.
  #
  # WHOLE-COMMITTED-TREE BREADTH PRESERVED (OPT-b guard): a commit whose trailer
  # no longer matches its committed tree must STILL fail the verify check. The
  # fix removes only UNTRACKED-WIP noise, never the committed-tree witness.
  #
  # git-ABSENT LOUD refusal PRESERVED (inherited from the committed-scope mode):
  # the verify check against a tree it cannot pin to a committed revision must
  # REFUSE loudly (fail-closed exit 2 + the committed-scope INDETERMINATE health
  # event), never silently fingerprint the working tree.
  #
  # SUT contract-shape: bounded-change -- the only declared mutation is the
  # digest source the verify check (`:488`) + the trailer compute (`:547`)
  # collect over (working tree -> committed tree at the pinned revision); the
  # universe is the verify verdict event + exit code + health events.
  #
  # Driving port (Mandate-13): the real `des run-contract-gate
  # --verify-gate-scope` CLI, driven as a Layer-3 SUBPROCESS black-box -- the
  # same definition the U2 G_COMMIT exit-gate hook invokes (port-to-port). The
  # AT never imports the digest or verify function.
  #
  # Layer 3+ -> example-only (Mandate 9, 11). All four ATs share the ONE
  # verify-check committed-scope wiring contract closure (@coupled): the same
  # indivisible behaviour (verify over the committed tree at the pinned
  # revision) under four perturbations of the SAME composition root --
  # untracked-WIP invariance (AT-1), committed-tree regression breadth (AT-2),
  # git-absent LOUD refusal (AT-3), and the committed mixed (`.py` + `.feature`)
  # suite under the untracked-WIP perturbation the `.py`-only fixtures could
  # never witness (AT-4).

  @slice-02 @coupled @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A pinned commit verifies the same way whether or not untracked work sits beside it
    Given a commit whose Gate-Scope trailer pins its committed contract suite
    When the exit gate verifies that commit over the pristine working tree
     And an untracked co-resident contract file is dropped beside the commit
     And the exit gate verifies that same commit again
    Then both verifications return the identical verified verdict
     And the second verification ignored the untracked co-resident file

  @slice-02 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A commit whose trailer no longer matches its committed tree still fails the verify check
    Given a commit whose Gate-Scope trailer pins a stale committed contract suite
    When the exit gate verifies that commit
    Then the verify check reports the commit's scope as unverified
     And the whole committed tree's contract suite is still witnessed by the verify check

  @slice-02 @coupled @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: The verify check refuses loudly when it cannot pin the commit to a committed revision
    Given a Gate-Scope trailer to verify against a tree that is not under revision control
    When the exit gate verifies that commit
    Then the verify check refuses to fingerprint a tree it cannot pin to a revision
     And the operator is loudly told the committed suite is indeterminate

  # GENUINE-WITNESS AT (the zero-isolation twin, mirrored from slice-01 AT-4).
  #
  # The committed suite MIXES a `.py` test module AND a specification `.feature`
  # file -- the file-kind composition the `.py`-only fixtures never witnessed
  # (the real tree has 227 committed `.feature`). To make this a genuine slice-02
  # RED witness (not a vacuous pristine pass -- slice-01 already verified the
  # committed-scope mode handles a mixed suite), the verify is driven under the
  # untracked-WIP perturbation: the same mixed-suite commit must verify
  # IDENTICALLY with and without an untracked co-resident file. At HEAD the
  # working-tree verify (`:488`) perturbs the fresh digest -> mismatch in the
  # co-resident state (RED); GREEN (committed-scope wiring) verifies both states.

  @slice-02 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: A commit pinning a committed suite of tests and specifications verifies under untracked work
    Given a commit whose Gate-Scope trailer pins a committed suite of tests and specifications
    When the exit gate verifies that commit over the committed mixed suite
     And an untracked co-resident contract file is dropped beside the commit
     And the exit gate verifies that same commit again
    Then both verifications return the identical verified verdict
     And the verify check does not refuse the commit for a specification it cannot collect directly
