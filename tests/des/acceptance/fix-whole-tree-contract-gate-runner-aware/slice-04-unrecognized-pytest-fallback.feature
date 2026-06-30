@feature-fix-whole-tree-contract-gate-runner-aware
Feature: An unrecognised whole-tree target falls back to pytest, only ambiguous degrades (D9)

  ADR-FLOW-011 D9 (regression fix). #73 slice-02 routed BOTH whole-tree legs
  through resolve(repo, None) and degraded EVERY Indeterminate to exit-3 -- but
  Indeterminate conflates two cases needing OPPOSITE treatment:

    * UNRECOGNISED (0 lockfiles)  -> pre-#73 ran pytest-collect / pytest directly
                                     -> MUST FALL BACK to pytest (the home runner)
    * AMBIGUOUS  (2+ lockfiles)   -> genuinely ambiguous (sister-Tsunami's polyglot)
                                     -> MUST degrade-LOUD exit-3 (the .nwave/runner.json
                                        escape hatch is the operator's declaration)

  These two scenarios pin both sides of the discriminant: scenario 1 is the
  active-RED witness that a lockfile-less target falls back on BOTH whole-tree
  routers (the run leg AND the digest leg share the conflation); scenario 2 is the
  over-correction guard proving the fix changes ONLY the unrecognised branch and
  leaves the polyglot degrade intact. The pre-existing
  tests/des/cli/fix_contract_gate_digest_undercount (its --repo points at the
  lockfile-less tests/ tree) is the independent digest-router RED witness the D9
  fix also flips RED->GREEN.

  Driving port: the REAL shipped CLI `python -m des.cli.run_contract_gate --repo
  <fixture>` (Mandate-13, Layer-3 subprocess) -- the slice-01/02/03
  WholeTreeGateComposition reused, EXTENDED only with a lockfile-less fixture.

  # === Scenario 1: the active-RED witness (BOTH routers fall back) ===
  # At HEAD both legs resolve the 0-lockfile Indeterminate and degrade exit-3
  # naming no recognised lockfile -> the WholeTreeRunnerResolved(pytest) preamble
  # is absent and degraded_loud_indeterminate is True on BOTH legs -> the
  # assertion RED-fails for the right reason (missing functionality: the
  # UnrecognizedRunner discriminant + the two router pre-checks). The fixture's
  # test file is a precondition (a tree to fall back ONTO), never the expected
  # output -- no fixture theater.
  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A repository with no recognised test-runner lockfile falls back to pytest on both whole-tree legs
    Given a repository with no recognised test-runner lockfile
    When the maintainer runs the whole-tree contract gate on both the run leg and the digest leg
    Then both legs fall back to the pytest runner and neither degrades to an ambiguous-runner refusal

  # === Scenario 2: the over-correction guard (polyglot still degrades) ===
  # A polyglot ROOT (Cargo.toml + package.json(vitest)) with NO .nwave/runner.json
  # is genuinely ambiguous and MUST stay exit-3 naming both lockfiles -- the D9
  # fix must NOT swallow polyglot ambiguity into a pytest fallback (that would
  # re-break sister-Tsunami's D8 path). Green-by-construction at HEAD (polyglot
  # already degrades) and after a CORRECT fix; RED only if DELIVER over-corrects
  # the Indeterminate branch -- the non-vacuity guard that the fallback
  # distinguishes unrecognised (fall back) from ambiguous (degrade).
  @slice-04 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A polyglot root with no declaration still degrades loud on a digest leg
    Given a polyglot repository root with no whole-tree runner declaration
    When the maintainer runs the whole-tree digest leg against the root
    Then the gate still refuses indeterminate and names the competing lockfiles, never falling back to pytest
