@feature-oss-earned-verdict-gate
Feature: The commit gate denies theater and proves itself by self-perturbation
  As an nWave framework developer committing a slice of acceptance tests
  I want the installed pre-commit gate to break each green test's dependency and
    deny the commit when any test holds green against broken code -- and to prove
    its own honesty by breaking the verdict CORE and demanding its own verdict
    flips red
  So that no theater test ever reaches the history, and the gate that guards the
    history is itself guarded against being theater

  # carpaccio slice-04 (DISCUSS [REF] Slice Plan). THE end-to-end capstone: the
  # installed PreToolUse hook fires on a `git commit`, perturbs each GREEN AT in
  # the slice (slice-03 SeamInjectionPort), re-runs it (slice-02 TestRunnerPort),
  # rules a verdict (slice-01 CORE), and DENIES the commit on theater-held.
  # Exactly TWO ATs (DISCUSS slice plan): AT-1 the gate denies a commit whose
  # slice contains a theater AT; AT-2 the SELF-TEST -- perturb the CORE itself
  # and demand the gate's OWN verdict flips RED (the gate proves it is not
  # theater).
  #
  # DEPENDENCY (FLAGGED): this slice depends on slice-02 (TestRunnerPort) AND
  # slice-03 (SeamInjectionPort) being SHIPPED -- the gate cannot perturb-and-
  # re-run without them. Both ATs are authored as the e2e capstone and scaffolded
  # @skip @pending; they cannot fail-for-the-right-reason on a SEMANTIC assertion
  # until 02 + 03 land (today they RED because the commit-gate hook branch does
  # not exist -- a driving-port-absent RED, the correct RED for an unbuilt
  # capstone). DELIVER unskips them only after 02 + 03 are green.
  #
  # Driving port (Mandate-13, Layer 4 wiring_e2e): the REAL installed PreToolUse
  # hook invoked as a subprocess over its JSON stdin protocol with a
  # `git commit` tool event (`tool_name: Bash`, `tool_input.command` a
  # `git commit`). The observable is the hook's decision body
  # (`permissionDecision:deny` / `{decision:block}`) + exit code. Layer 4: real
  # hook subprocess, real I/O, example-only (Mandate 9/11); traditional
  # assertions permitted at this layer (Mandate 8 universe-guard is a layer-1..3
  # requirement).

  # AT-0 -- the allow path: a commit whose slice is all-earned is allowed
  # (GAP-3(a), MINOR-1). Witnesses the {all-earned -> allow} decision-table row
  # so a deny-only gate is no longer mechanically indistinguishable from a
  # hard-wired-deny. AT-0 (allow) + AT-1 (deny) + AT-2 (self-deny) together
  # witness all three observable gate outcomes. Defensible deviation from the
  # slice plan's "exactly TWO" (slice-04 -> 3 ATs): the third AT closes a
  # decision-table hole the slice plan did not foresee.
  @driving_port @real-io @wiring_e2e @slice-04 @contract-shape:unbounded-preservation
  Scenario: A commit whose slice tests are all earned is allowed
    Given a slice whose acceptance tests are "all earned"
    When a commit of that slice is attempted through the pre-commit gate
    Then the commit gate decision is "allowed"

  # AT-1 -- the gate denies a commit whose slice contains a theater AT.
  @driving_port @real-io @wiring_e2e @slice-04 @error @contract-shape:unbounded-preservation
  Scenario: A commit carrying a theater test is denied by the gate
    Given a slice whose acceptance tests are "a theater AT"
    When a commit of that slice is attempted through the pre-commit gate
    Then the commit gate decision is "denied"
    And the gate reports the theater test as the reason

  # AT-2 -- SELF-TEST: the gate proves it is not itself theater. Perturb the
  # verdict CORE and demand the gate's own verdict flips RED -- a gate that
  # stayed GREEN against a broken CORE would itself be theater. The differential
  # `(perturbed -> RED) and (un-perturbed -> GREEN)` is the honesty proof
  # (GAP-3(b), MAJOR-1): the baseline-control leg closes the hard-coded-RED hole
  # INSIDE the AT -- a gate that emitted RED regardless of perturbation would
  # fail the control. Single scenario, two-run witnessed differential.
  @driving_port @real-io @wiring_e2e @slice-04 @contract-shape:bounded-change
  Scenario: The gate proves itself by flipping red when its own core is broken
    Given the gate's own verdict core has been perturbed at its seam
    When the gate runs its self-test over the perturbed core
    Then the gate's self-test verdict is "RED"
    And the gate denies its own commit
    And the gate's self-test verdict over an un-perturbed core is "GREEN"
