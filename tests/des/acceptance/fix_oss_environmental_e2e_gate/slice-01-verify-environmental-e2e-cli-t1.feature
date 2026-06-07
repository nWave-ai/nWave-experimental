@feature-fix-oss-environmental-e2e-gate
Feature: An environmental e2e is proven against the artifact a consumer installs
  As an nWave framework developer finishing a feature
  I want the verify_environmental_e2e CLI to run a feature's environmental
    e2e against the delivered artifact installed into a hermetic clean prefix
  So that "this feature works" means the installed wheel works, not just the
    dev tree

  # carpaccio slice-01 (DESIGN slice plan, [REF] Slice Plan). THE walking
  # skeleton: the thinnest end-to-end vertical, and the gate run against the
  # gate's OWN delivered artifact (DESIGN [REF] Probe Specifications,
  # Self-application).
  #
  # CONTRACT SOURCE: this slice is authored against the NORMATIVE-FROZEN L1.4
  # contract (gate-family-implementation-2026-05-21.md §L1.4, v5). The
  # feature-delta's verify_environmental_e2e spec PREDATES the freeze and
  # DIVERGES (different --mode semantics, args, exit codes, stdout token).
  # L1.4 governs; the feature-delta needs a reconcile amendment (see DISTILL
  # report). The contract used here:
  #   modes: verify-authored | verify-present | run | verify-merge-ready | audit
  #   exit codes: 0 PASS | 1 check-failed | 2 parse/IO | 3 misscoped
  #   stdout: one-line token `environmental_e2e mode=.. feature=.. authored=..
  #           genuine=.. collected=.. verdict=.. verdict_input_digest=..
  #           fresh=.. xfail_present=..`
  #   results-JSON: schema_version 2.0, 3-input verdict_input_digest.
  #
  # slice-01 exercises `--mode run` — the only mode that actually builds,
  # installs into a clean prefix, and runs the e2e: it is the build->install
  # ->run->verdict seam, the walking skeleton.
  #
  # Layer 5/6 (WS @wiring_e2e + e2e): real stack, subprocess, real
  # `python -m build --wheel` + real `pip install --target`. Example-only,
  # no PBT (Mandate 9/11). Traditional assertions permitted at layer 4+
  # (Mandate 8). No fixture-folding: the subject is the production CLI, the
  # composition is the real build+install transform, the delivery form is the
  # .whl.
  #
  # Driving port: `verify_environmental_e2e` CLI invoked as a `python -m`
  # subprocess (per the project Infrastructure Policy walking_skeleton_gate
  # precedent row).

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A feature's environmental e2e passes against its freshly installed artifact
    Given a feature that ships a packaged CLI module with an environmental e2e test
    When the developer runs the environmental e2e gate in run mode against the delivered artifact
    Then the gate reports the environmental e2e verdict as passing
    And the gate exit status indicates success
    And the gate writes a results record stamped with a freshness digest over the wheel, the e2e files, and the continuous-integration job closure

  @slice-01 @walking-skeleton @wiring_e2e @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A feature whose environmental e2e is red against the installed artifact reports failure
    Given a feature that ships a packaged CLI module with a failing environmental e2e test
    When the developer runs the environmental e2e gate in run mode against the delivered artifact
    Then the gate reports the environmental e2e verdict as failing
    And the gate exit status indicates a check failed

  @slice-01 @wiring_e2e @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Running the gate leaves the developer's repository untouched
    Given a feature that ships a packaged CLI module with an environmental e2e test
    When the developer runs the environmental e2e gate in run mode against the delivered artifact
    Then the gate reports the environmental e2e verdict as passing
    And the developer's repository working tree is unchanged
    And no file under the developer's source tree was written during the gate run
