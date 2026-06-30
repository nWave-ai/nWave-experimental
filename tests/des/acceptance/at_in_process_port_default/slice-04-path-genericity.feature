@feature-at-in-process-port-default
Feature: The AXIS-B levers discover the target project's source and tests directories generically

  Mara, an nWave maintainer, runs the AXIS-B enforcement levers on a project that is
  NOT laid out like nWave: its tests live in `spec/` (not `tests/`) and its source in
  `lib/` (not `src/des/`). Today the levers HARDCODE nWave's own structure --
  `_TESTS = _REPO_ROOT / "tests"` and `_SRC_DES = _REPO_ROOT / "src" / "des"` -- so on
  her project they scan the WRONG directory: they either find nothing (false-PASS on an
  absent `tests/`) or scan nWave's OWN tree instead of hers (a nonsense result). This
  slice makes the levers GENERIC to the target machine's project: they DISCOVER the
  source + tests roots from the target (`pyproject.toml [tool.pytest.ini_options]
  testpaths`, a `.nwave/` config, or explicit `--source-dir`/`--tests-dir` args) and scan
  the RIGHT dirs -- and when the layout cannot be resolved they degrade LOUD
  (NOT_APPLICABLE / INDETERMINATE with a named reason), never a false-PASS on a wrong or
  empty directory, never a crash on a layout that is not nWave's.

  # DISCUSS slice-04 (Metà-B, code): the generic-to-target-machine mandate (System
  # Constraints: depend ONLY on Python; no assumption about the target's layout) applied
  # to the levers' scan roots -- the PATH axis of the same wiring-audit that slice-03 did
  # on the language axis. DESIGN DDD-9 (per-language, git-free, degrade-LOUD) + DDD-4
  # (pure resolvers: filesystem-read -> return paths, mutate nothing) extended to PATH
  # discovery. Same Locked Decision lineage as slice-03 (generality / target-machine
  # agnosticism, the "ENFORCED, not merely available" + no-silent-pass invariants).
  #
  # THE DEFECT (verified via Tsunami atoms + grep, 2026-06-24): `axis_b_levers.py`
  # hardcodes `_SRC_DES` (line 53), `_TESTS` (line 54), `chain = CodeFactChain(root=
  # _SRC_DES)` (line 114), `scan_spawn_sites(_TESTS, ...)` (line 491), `tests_dir = repo /
  # "tests"` (lines 545, 622). The lever entry functions (`check_unwired_entry`,
  # `check_integration_per_adapter`, `check_contract_per_port`, `check_non_ws_spawn`)
  # take NO source/tests-dir argument -- they read the module-level globals, so they
  # ALWAYS scan the host nWave layout, never the target's `spec/`/`lib/`. No discovery
  # mechanism exists at HEAD (zero `testpaths`/`.nwave`/`--source-dir`/`--tests-dir`/
  # `resolve` in the module).
  #
  # Driving port (Architecture-of-Reference / the inverted in-process default this
  # feature ships): the REAL gate entry `verify_readiness_pre_dispatch.main(argv)` driven
  # IN-PROCESS with stdout/stderr captured -- NOT a `python -m` subprocess. These ATs eat
  # the feature's own dog food (subprocess-e2e reserved for @walking_skeleton; none here
  # is @walking_skeleton, so none forks). Mandate-13 satisfied in-process.
  #
  # active-RED mechanism (DESIGN P1-P4): the step modules import ONLY the stable
  # `verify_readiness_pre_dispatch.main` entry at module top (P1) -- never the absent
  # path-resolution seam. The discovery is reached at RUNTIME inside the in-process
  # `main()` call (P2/P3): at HEAD the levers ignore the target roots (the `--source-dir`/
  # `--tests-dir` args are unrecognized argparse + the levers read the host globals), so
  # the gate produces NO resolved-roots observable and scans the wrong dir -- a runtime
  # absence surfaced as a verdict, not a collection error. Each Then asserts the captured
  # observable (the resolved roots / the degrade-LOUD reason), which is absent at HEAD, so
  # every assertion is a NAMED semantic AssertionError (P4). Collection succeeds (only the
  # stable `main` imported); every scenario RED-fails for the right reason.
  #
  # Mandate-15 (dormant-seam): the AT-oracle target is the PATH-RESOLUTION seam in
  # `axis_b_levers.py` (the hardcoded `_TESTS`/`_SRC_DES` -> resolved roots), driven
  # through the REAL `verify_readiness_pre_dispatch.main` entry, asserting an observable
  # effect (the gate scanned the fixture's `spec/`/`lib/`, not the host `tests/`/`src`).
  #
  # Layer 3 (in-process composition acceptance) -- example-only, no PBT (Mandate 9/11):
  # each scenario pins a single closed observable (the resolved roots, the degrade-LOUD
  # reason). Sad paths (unresolvable layout) enumerated explicitly (Mandate 11).

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The levers discover a non-standard layout from explicit source and tests arguments
    Given a target project whose tests live in "spec" and whose source lives in "lib"
    And the target project declares its layout with explicit source and tests arguments
    When the maintainer drives the readiness levers against the target project in-process
    Then the levers resolve the target tests root to its "spec" directory
    And the levers resolve the target source root to its "lib" directory
    And the levers scan the target project layout, not the host nwave layout
    And the levers drove the gate without forking an interpreter

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The levers discover a non-standard layout from the target pyproject testpaths
    Given a target project whose tests live in "spec" and whose source lives in "lib"
    And the target project declares its tests root in pyproject testpaths
    When the maintainer drives the readiness levers against the target project in-process
    Then the levers resolve the target tests root to its "spec" directory
    And the levers scan the target project layout, not the host nwave layout
    And the levers drove the gate without forking an interpreter

  @slice-04 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: The levers degrade loud when the target layout cannot be resolved
    Given a target project with no conventional layout and no layout configuration
    When the maintainer drives the readiness levers against the target project in-process
    Then the levers report the layout as not resolvable with a named reason
    And the levers do not raise a false pass on a wrong or empty directory
    And the levers do not crash on the unresolvable layout
    And the levers drove the gate without forking an interpreter
