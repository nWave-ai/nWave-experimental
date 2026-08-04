@feature-dispatch-template-ssot-reconciliation @driving_port @real-io @contract-shape:bounded-change
Feature: The dispatch-ref coherence gate holds the no-inline-restatement rule for skill prose

  A maintainer runs the git-free `des verify-dispatch-ref-coherence` gate over a
  named skill file. The gate FAILs when the file carries no `dispatch-ref` pointer,
  when the pointer's `mode`/`lane` names do not resolve in `nWave/dispatch/atdd_pure.yaml`,
  or when the prose inline-restates dispatch section bodies instead of pointing.
  It PASSes on a well-formed `dispatch-ref` pointer pair with zero inline
  restatement -- including when the prose mentions a single section id in
  passing, which is NOT a restatement -- and degrades LOUD to INDETERMINATE --
  never a silent pass -- when the target skill file itself is missing or
  unreadable. Every FAIL diagnostic explains WHAT is wrong, WHY it matters, and
  HOW to fix it by naming `des dispatch` as the producing tool -- never a manual
  repair. This is ADDITIVE: it does not yet gate `nw-execute/SKILL.md` (a later
  slice's scope).

  Driving surface (Core Principle 7 -- in-process is the default; subprocess-e2e
  is reserved for exactly one `@walking_skeleton` scenario per command): ONE
  scenario below (the walking skeleton) drives the REAL
  `des verify-dispatch-ref-coherence` subcommand as a Layer-3 subprocess through
  the shipped `des` dispatcher, proving `des verify-dispatch-ref-coherence` is
  wired end-to-end as the installed command -- a wiring proof no in-process call
  can give (it bypasses argv parsing and subcommand registration entirely). ONE
  further scenario (the git-boundary probe) also stays on subprocess because its
  own property -- "does the gate spawn a child process that fails to find `git`
  on PATH" -- can only be observed by actually spawning a child. Every other
  scenario drives the REAL `verify_dispatch_ref_coherence.main(argv)` entry
  directly IN-PROCESS (Layer 2), stdout/stderr captured, no interpreter fork --
  mirroring `tests/des/acceptance/at_in_process_port_default/`. Both surfaces
  are the CONCEPT reused from `des verify-wave-contract-coherence`
  (f-wave-contract-coherence slice-02) -- pointer + registry + no-inline-
  restatement, git-free, target-agnostic -- not its list-diff algorithm (design
  Decision 5: dispatch's registry declares `{mode, lane}` names resolved by a
  render CLI, with no equivalent enumerable list to diff prose against).
  Observable: the §17 GateVerdict token the gate emits on JSON-stdout (ADR-GV-001
  -- one of the five existing verdicts; no sixth, no engine). Mandate-14 real-io
  contract: every scenario reads real on-disk skill prose + the real
  `nWave/dispatch/atdd_pure.yaml` registry over the OS filesystem; the two
  subprocess scenarios additionally spawn a real OS process -- those two would
  fail if the dispatcher or the registry file were absent.

  # Property 1: PASS on a well-formed dispatch-ref pointer pair (mode + lane both
  #             resolve in nWave/dispatch/atdd_pure.yaml) with zero inline
  #             restatement. The walking skeleton for this feature: the ONE
  #             subprocess-e2e scenario proving `des verify-dispatch-ref-coherence`
  #             is wired end-to-end through the installed `des` dispatcher.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-1 @walking_skeleton @driving_port
  Scenario: The gate passes on a well-formed dispatch-ref pointer with zero inline restatement
    Given a skill file carrying a valid dispatch-ref pointer with zero inline restatement
    When the maintainer runs the installed des verify-dispatch-ref-coherence command over that skill file
    Then the dispatch-ref coherence gate emits the PASS verdict

  # Property 2: FAIL naming WHAT/WHY/HOW when the dispatch-ref pointer is MISSING.
  # In-process (Layer 2, the default) -- this property does not need a real
  # child process to observe.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-2 @error
  Scenario: The gate fails when the skill file carries no dispatch-ref pointer at all
    Given a skill file carrying no dispatch-ref pointer
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the FAIL verdict
    And the failure diagnostic explains the missing pointer, why it matters, and how to fix it by running des dispatch

  # Property 3: FAIL naming WHAT/WHY/HOW when the pointed-at lane does NOT resolve
  #             in nWave/dispatch/atdd_pure.yaml. In-process.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-3 @error
  Scenario: The gate fails when the dispatch-ref pointer names a lane that does not resolve
    Given a skill file carrying a dispatch-ref pointer naming an unresolvable lane
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the FAIL verdict
    And the failure diagnostic names the unresolvable lane, why it matters, and how to fix it by running des dispatch

  # Property 3 (mode variant): the SAME property, exercised on the mode name instead
  # of the lane name -- both are pointed-at names the pointer resolves in the SSOT.
  # In-process.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-3 @error
  Scenario: The gate fails when the dispatch-ref pointer names a mode that does not resolve
    Given a skill file carrying a dispatch-ref pointer naming an unresolvable mode
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the FAIL verdict
    And the failure diagnostic names the unresolvable mode, why it matters, and how to fix it by running des dispatch

  # Property 4: FAIL naming WHAT/WHY/HOW when the prose INLINE-RESTATES dispatch
  #             section bodies (>=2 consecutive canonical section ids enumerated
  #             as a bullet list) instead of pointing -- the same duplication-
  #             drift concept `verify-wave-contract-coherence` polices, reused
  #             here. In-process.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-4 @error
  Scenario: The gate fails when the skill prose inline-restates dispatch section bodies
    Given a skill file carrying a valid dispatch-ref pointer that also inline-restates dispatch section bodies
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the FAIL verdict
    And the failure diagnostic names the restated section body, why it matters, and how to fix it by running des dispatch

  # Property 4 near-miss boundary (MEDIUM finding): naming exactly ONE dispatch
  # section id, in passing prose, must NOT trigger the restatement rule -- an
  # over-eager implementation flagging a single mention must not pass this suite.
  # In-process.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-4b
  Scenario: The gate passes when the skill prose mentions exactly one dispatch section id
    Given a skill file carrying a valid dispatch-ref pointer that mentions exactly one dispatch section id
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the PASS verdict

  # Property 5: the gate degrades LOUD to INDETERMINATE -- a third state distinct
  #             from both PASS and FAIL -- when the target skill file itself is
  #             missing/unreadable, rather than passing (Invariant 2 degrade-LOUD).
  #             In-process.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-5 @error
  Scenario: The gate is indeterminate when the target skill file is missing
    Given a skill file path that does not exist on disk
    When the maintainer runs the dispatch-ref coherence gate over that skill file
    Then the dispatch-ref coherence gate emits the INDETERMINATE verdict
    And the indeterminate diagnostic names the missing skill file

  # Property 6: the gate is filesystem+import only -- it must never shell out to
  # git. Proven behaviourally: stripping git off PATH must not change the
  # verdict. STAYS on subprocess: this property is "does the gate spawn a child
  # process that fails to find git" -- only a real child process can be probed
  # this way; an in-process call runs inside this interpreter's already-resolved
  # image and cannot exercise child-process PATH lookup at all.
  @slice-04 @feature-dispatch-template-ssot-reconciliation @AT-6 @boundary
  Scenario: The gate never depends on git -- it still runs correctly with git absent from PATH
    Given a skill file carrying a valid dispatch-ref pointer with zero inline restatement
    And a process environment where no git executable is reachable on PATH
    When the maintainer runs the installed des verify-dispatch-ref-coherence command over that skill file
    Then the dispatch-ref coherence gate emits the PASS verdict
