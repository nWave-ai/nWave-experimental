@feature-fix-gcommit-exit-gate-scoping
Feature: The contract gate-scope digest is reproducible over the committed tree

  As the U2 G_COMMIT exit gate that must re-verify a committed Gate-Scope
    trailer on any checkout of a commit
  I want the gate-scope digest to fingerprint the committed contract suite at
    HEAD, not whatever untracked files happen to sit in the committer's
    working tree
  So that a committed Gate-Scope trailer is reproducible on any machine and
    stable across the compute-then-verify window -- the daily amend-loop is
    removed without narrowing the contract the gate protects

  # slice-01 (#2) -- THE bootstrap-critical reproducibility constraint.
  #
  # The reproducible committed-tree digest is a NEW, DISTINCT mode:
  # `des run-contract-gate --committed-scope-digest`. It is SEPARATE from the
  # general `--collect-only --print-digest`, which stays a WORKING-TREE,
  # non-git-OK, collect-then-classify digest (the dogfood + backward-compat
  # contract -- UNTOUCHED by this feature). The new mode is what the G_COMMIT
  # exit gate's `Gate-Scope` trailer + the hook's `--verify-gate-scope` consume.
  #
  # The general digest is computed over the WORKING TREE: the worker runs
  # `pytest --collect-only` over the live filesystem, so its collected node-set
  # INCLUDES untracked co-resident `.feature`/test files. Binding a committed
  # `Gate-Scope` trailer to THAT digest fingerprints "the suite as it happened
  # to sit in the committer's working tree", which no other checkout / CI can
  # reproduce (target-machine-independence violation, the ~36-min amend-loop).
  # The new committed-scope mode collects only the COMMITTED file-set at HEAD,
  # so its digest is reproducible on any checkout of that commit.
  #
  # Empirical RED witness (orchestrator-verified): over one pinned commit, a
  # working-tree digest WITH an untracked co-resident file differs from the
  # digest WITHOUT it. The committed-scope digest must be STABLE across that
  # perturbation (the property AT-1 pins) -- which is exactly why it is a
  # distinct mode and not a re-purposing of the general digest.
  #
  # SUT contract-shape: bounded-change -- the only declared mutation is the
  # collected node-set's input restricted to committed paths; the universe is
  # the printed digest + exit code + health events.
  #
  # Driving port (Mandate-13): the real `des run-contract-gate
  # --committed-scope-digest` CLI, driven as a Layer-3 SUBPROCESS black-box. The
  # AT never imports the digest function -- it observes only stdout / exit code
  # / health events.
  #
  # Layer 3+ (real subprocess collection over a real git repo) -> example-only
  # (Mandate 9, 11); the reproducibility property is perturbation-bound (the
  # untracked-WIP working-tree state), not a vacuous constant.

  @slice-01 @coupled @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: The committed-tree digest is invariant to untracked co-resident work
    Given a repository whose contract suite is fully committed at one revision
    When the operator derives the gate-scope digest over the pristine working tree
     And an untracked co-resident contract file is dropped into the working tree
     And the operator derives the gate-scope digest again over the same revision
    Then both derivations print the identical gate-scope digest
     And the second digest ignored the untracked co-resident file

  @slice-01 @coupled @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A test committed anywhere in the tree stays inside the digest
    Given a repository whose contract suite is fully committed at one revision
    When the operator derives the gate-scope digest over the committed suite
     And a new contract test is committed under an unrelated part of the tree
     And the operator derives the gate-scope digest after the new commit
    Then the digest after the new commit differs from the digest before it
     And the whole committed tree's contract suite is still covered by the digest

  @slice-01 @coupled @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: The gate refuses loudly when it cannot establish the committed suite
    Given a contract tree that is not under revision control
    When the operator derives the gate-scope digest over that tree
    Then the gate refuses to fingerprint a tree it cannot pin to a revision
     And the operator is loudly told the committed suite is indeterminate

  # GENUINE-WITNESS AT (the zero-isolation twin the slice was missing).
  #
  # The other slice-01 fixtures commit ONLY `.py` test modules -- so they could
  # never witness what the real repo does: a committed contract suite is a MIX
  # of `.py` test modules AND specification `.feature` files (the real tree has
  # 227 committed `.feature` files). The committed-scope digest collects the
  # committed file-set by passing each committed contract path to pytest as a
  # `--path` argument; pytest CANNOT collect a `.feature` file directly (it is
  # bound to its `.py` `@scenario` step module, not collected as a path itself),
  # so passing a committed `.feature` makes pytest exit 4 -> the gate fails
  # closed with MalformedInput instead of printing a reproducible digest.
  #
  # This is precisely the fixture-isolation masking class this whole feature
  # exists to prevent: the small `.py`-only fixtures pass GREEN while the real
  # repo's mixed committed tree fails. This AT commits the missing twin -- a
  # realistic mix including at least one committed `.feature` alongside
  # committed `.py` test modules -- so the digest mode must SUCCEED over it.
  #
  # RED today: the committed `.feature` is passed to pytest -> exit 4 ->
  # MalformedInput -> exit 2 (REFUSED), not DIGEST_PRINTED. GREEN after the fix
  # excludes `.feature` from the explicit pytest `--path` set (no coverage lost:
  # `.feature` scenarios are collected via their bound `@scenario` `.py`
  # modules, which remain in the path-set).

  @slice-01 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: The committed-tree digest covers a realistic mix of tests and specifications
    Given a repository whose committed contract suite mixes test modules and specification files
    When the operator derives the gate-scope digest over the committed mixed suite
    Then the gate prints a reproducible gate-scope digest over the committed mixed suite
     And the gate does not refuse the committed suite for a specification it cannot collect directly
