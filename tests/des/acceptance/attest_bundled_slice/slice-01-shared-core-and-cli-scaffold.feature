@feature-f-attest-bundled-slice @slice-01
Feature: The bundled-slice attestation command is reachable and reuses reverify's core
  As a maintainer recovering a bundle-delivered slice the closure scorecard counts partial
  I want one sanctioned `des attest-bundled-slice --reason` command built on reverify's
    shared precondition/gate/record core
  So that the new command reuses the proven attestation machinery verbatim (no parallel
    path), demands a human GO, and never weakens reverify's existing behaviour

  # slice-01 of f-attest-bundled-slice (classic spine; engine CLI, no LLM in path).
  # At HEAD no `des attest-bundled-slice` subcommand exists (the dispatcher registry
  # has no row -- grep + Tsunami: zero matches tree-wide) and no shared-core module
  # `src/des/cli/_reverify_core.py` exists. The fix (a) extracts reverify's shared
  # precondition/gate/record core into that NEW module from which BOTH CLIs import,
  # (b) registers the `attest-bundled-slice` subcommand, (c) makes `--reason`
  # mandatory (argparse required=True, the `des wave-clear` precedent).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL `des` dispatcher via
  # `python -m des.cli attest-bundled-slice` for the CLI scaffold scenarios; for the
  # shared-core scenarios, the production modules imported in a CHILD interpreter and
  # reverify's existing acceptance suite re-run as a child pytest -- so an absent
  # module / a behaviour regression is a captured observable, never a collection
  # error in this process. observables = process exit code + stdout/stderr + child
  # probe rc + child pytest rc.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seams are the dispatcher
  # `_REGISTRY` row for `attest-bundled-slice` and the shared `_reverify_core` module
  # BOTH CLIs import. The CLI scenarios drive the registry seam through the REAL
  # dispatcher subprocess; the shared-core scenarios witness the extraction seam by
  # importing the real production modules and asserting reverify's helpers resolve
  # FROM the shared core (identity) AND its behaviour is preserved (suite green).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # dispatcher rejects `attest-bundled-slice` with `invalid choice` (exit 2); the
  # `_reverify_core` import raises ModuleNotFoundError in the child (rc != 0, no
  # CORE_OK marker); reverify's helpers still live in reverify_slice_commit.py (no
  # shared-core identity). Each Then turns a captured observable into a semantic
  # AssertionError. GREEN once DELIVER ships the extraction + the registry row + the
  # `--reason`-required scaffold. No @skip, no import / collection error.

  @slice-01 @driving_port @real-io @us-cli-scaffold @contract-shape:bounded-change
  Scenario: The attestation subcommand is registered and recognized by the dispatcher
    When the maintainer runs the bundled-slice attestation command
    Then the dispatcher recognizes the bundled-slice attestation subcommand

  @slice-01 @driving_port @real-io @us-human-go @error @contract-shape:bounded-change
  Scenario: Attesting without a reason is a usage error so the human authorizes the attestation
    Given the maintainer omits the mandatory reason on the attestation
    When the maintainer runs the bundled-slice attestation command
    Then the attestation command exits with the USAGE_OR_MALFORMED outcome
    And the usage error names the mandatory reason argument

  @slice-01 @driving_port @real-io @us-shared-core @contract-shape:bounded-change
  Scenario: The shared reverify core exists and reverify reuses it verbatim
    When the maintainer imports the shared reverify core
    Then the shared core exposes every reused reverify helper to both commands

  @slice-01 @driving_port @real-io @us-backward-compat @contract-shape:unbounded-preservation
  Scenario: Extracting the shared core preserves reverify's existing behaviour
    When the maintainer re-runs reverify's existing acceptance suite
    Then reverify's existing acceptance suite stays green after the core extraction
