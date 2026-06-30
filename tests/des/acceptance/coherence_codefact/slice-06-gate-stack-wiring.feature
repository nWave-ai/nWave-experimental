@feature-f-coherence-and-attestation @slice-06
Feature: The three feature modules are wired into the gate-stack so a maintainer can reach them
  As a maintainer running a governed flow-v2 gate
  I want the mechanical gate-G, the self-attest verdict layer, and the per-language
    test-runner — all already built (slices 03/04/05) — CONNECTED into the gate-stack
  So that I can actually reach them through `des`, a firing surface references them,
    and the closure scorecard sees the feature WIRED, not catalogued-but-dormant

  # slice-06 of f-coherence-and-attestation (JOB-028). The WIRING slice: it closes
  # the `catalogato ≠ cablato` gap the closure scorecard reports
  # (`f-coherence-and-attestation  delivering 5/5  no UNWIRED`). The three modules
  # SHIP at HEAD; this slice makes them FIRE. No domain re-implementation — the CLI
  # wrappers are thin drivers over the existing slice-03/04/05 logic
  # (evaluate_gate_g / self_attest.classify / run_tests).
  #
  # THE THREE MODULES (verified at HEAD — all UNWIRED):
  #   gate-g             -> src/des/cli/gate_g.py `evaluate_gate_g` (callable, NOT a
  #                         registered `des` subcommand — its own docstring ~line 48
  #                         says so). DISTILL gate-OUT #5 (flow-v2-design §12).
  #   self-attest        -> src/des/domain/self_attest.py `classify` (pure domain, NO
  #                         CLI module at HEAD). The verdict-validity layer (D9).
  #   verify-test-runner -> src/des/cli/run_tests.py `main` (a CLI module but NOT in
  #                         the dispatcher _REGISTRY under any name). Test-exec (§V/D8).
  #
  # THREE WITNESSING AXES (the closure scorecard's two-leg `_module_wired` +
  # behavioural drive — scripts/flow_v2_closure_scorecard.py:212-223):
  #   (1) REGISTRATION   — each subcommand is a `_SubcommandRow` in _REGISTRY,
  #                        advertised by `des --help`, with a 1:1 catalog mirror row.
  #   (2) GATE-STACK REF — each module name matches the scorecard's EXACT
  #                        `_term_wired` regex in a `nWave/flavors/*.yaml` surface
  #                        (the literal `catalogato ≠ cablato` closure leg).
  #   (3) BEHAVIOURAL    — driving `des <subcommand>` DRIVES the existing domain
  #                        logic and emits a §17 GateVerdict-shaped result.
  #
  # DRIVING SURFACES (Mandate-13, driving-port-only):
  #   axes (1) + (3) -> Layer 3 SUBPROCESS: the REAL `des` dispatcher (`python -m
  #                     des <subcommand>`), the way an operator runs it. Observable =
  #                     `des --help` listing / argparse exit (registered vs invalid-
  #                     choice exit 2) / the §17 verdict the driven subcommand emits.
  #                     NEVER a line number, never a direct-domain import (the
  #                     oss-review-verdict-demotion slice-02 D-register pattern).
  #   axis (2)       -> the REAL shipped `nWave/flavors/*.yaml` artifacts, scanned
  #                     with the EXACT scorecard `_term_wired` regex. A shipped
  #                     artifact, never an inline test string (Mandate-13
  #                     prose-surface discriminating-token rule).
  #
  # §17 verdict map (ADR-GV-001, FIVE verdicts — CONSUMED unchanged, no sixth, C6):
  #   gate-G bijection found no objection                       -> PASS
  #   self-attest mechanical evidence + sources agree           -> PASS
  #   runner real run, failed==0                                -> PASS (mapped)
  #
  # active-RED scaffold (atdd_pure — NOT @skip): at HEAD all three subcommands are
  # ABSENT from the dispatcher _REGISTRY (verified), no module name is referenced in
  # any nWave/flavors/*.yaml gate-stack, and self_attest.py has no CLI main. Each
  # scenario RED-fails with a NAMED semantic AssertionError naming the missing
  # wiring (registry row / flavor reference / thin-driver), never a collection /
  # import / setup error (the dispatcher imports cleanly; only the _REGISTRY rows
  # are absent — a clean missing-functionality RED). GREEN once DELIVER (a) adds the
  # three _REGISTRY rows + catalog mirrors, (b) references each module in a flavor
  # gate-stack, (c) ships the thin gate-g / self-attest CLI wrappers.
  #
  # DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (the SEAM, never a line number):
  #   A1 (registration) the three subcommand NAMES are fixed by the closure
  #      scorecard (`gate-g` / `self-attest` / `verify-test-runner`); the wrapper
  #      module paths are DELIVER's choice (gate-g -> new des.cli.gate_g main over
  #      evaluate_gate_g; self-attest -> new des.cli.self_attest main over classify;
  #      verify-test-runner -> existing des.cli.run_tests main).
  #   A2 (reference) gate-G is referenced at the `distill` gate-out stack
  #      (flow-v2-design §12 DISTILL gate-OUT #5); self-attest + runner per DESIGN.
  #      The witness is surface-agnostic (any flavor gate-stack the `_term_wired`
  #      regex matches greens it).
  #   A3 (behavioural) each driven subcommand emits a §17 GateVerdict-shaped result;
  #      the composition reads it from stdout / the --out envelope.

  # ===== AXIS 1: REGISTRATION (AT-20/21/22) — Zero/One/Many over the 3 modules ====
  # C3 ZERO-obligation: the registration surface is an iterative set (the _REGISTRY
  # rows). The "zero" case — a module catalogued but with NO registry row — is the
  # exact HEAD failure each row witnesses (resolvable=False). The Scenario Outline
  # ranges over all three (the "many" coverage); each row's HEAD state IS the zero
  # case for that module. PBT-shaped over the module set -> Scenario Outline.
  @slice-06 @driving_port @real-io @us-wiring-registration @property @contract-shape:bounded-change
  Scenario Outline: The <subcommand> module is a registered des subcommand
    Given the feature module reached through the <subcommand> subcommand
    When the registration of the subcommand is inspected through the real des dispatcher
    Then the subcommand is a registered des subcommand advertised with a catalog mirror

    Examples:
      | subcommand               |
      | gate-design-at-coherence |
      | self-attest              |
      | verify-test-runner       |

  # ===== AXIS 2: GATE-STACK REFERENCE (AT-23) — the catalogato ≠ cablato closure ===
  # Each module name must match the scorecard's EXACT `_term_wired` regex in a
  # shipped flavor gate-stack. This is the literal closure leg the goal-contract
  # measures. PBT-shaped over the module set -> Scenario Outline.
  @slice-06 @driving_port @real-io @us-wiring-gate-stack-reference @property @contract-shape:bounded-change
  Scenario Outline: The <subcommand> module is referenced in a flavor gate-stack
    Given the feature module reached through the <subcommand> subcommand
    When the gate-stack reference of the module is inspected in the shipped flavor surfaces
    Then the module is referenced in a flavor gate-stack so the closure scorecard sees it wired

    Examples:
      | subcommand               |
      | gate-design-at-coherence |
      | self-attest              |
      | verify-test-runner       |

  # ===== AXIS 3: BEHAVIOURAL WIRING (AT-24/25/26) — the thin driver fires ==========
  # Invoking each `des <subcommand>` over a real input DRIVES the existing
  # slice-03/04/05 domain logic and emits a §17 GateVerdict-shaped result, proving
  # the CLI wrapper is a thin driver (not a domain re-implementation). PBT-shaped
  # over the module set -> Scenario Outline.
  @slice-06 @driving_port @real-io @us-wiring-behavioural @property @contract-shape:bounded-change
  Scenario Outline: Driving the <subcommand> subcommand emits a gate verdict from the existing domain logic
    Given the feature module reached through the <subcommand> subcommand
    When the subcommand is driven end to end through the real des dispatcher
    Then driving the subcommand emits a gate verdict from the existing domain logic

    Examples:
      | subcommand               |
      | gate-design-at-coherence |
      | self-attest              |
      | verify-test-runner       |

  # ===== C6 ROBUSTNESS (AT-27) — the dispatcher rejects an unregistered name =======
  # A NAMED negative observable (one concrete example, not an outline): a name that
  # is NOT in the gate-stack wiring set must be rejected by the real `des`
  # dispatcher (argparse invalid-choice, not-resolvable). This pins the closed-set
  # rejection contract explicitly rather than leaving it implicit in the
  # registration ATs' active-RED state — proving the registration witness
  # DISCRIMINATES (a resolver that accepted everything would pass AT-20/21/22
  # vacuously). GREEN at HEAD (the dispatcher already rejects unknown names) and
  # STAYS green after DELIVER wires the three real subcommands — the always-true
  # closed-set guardrail, distinct from the active-RED wiring ATs.
  @slice-06 @feature-f-coherence-and-attestation @driving_port @real-io @us-wiring-robustness @contract-shape:bounded-change
  Scenario: An unregistered subcommand name is not resolvable through the des dispatcher
    Given an unknown subcommand name not in the gate-stack wiring set
    When the registration of the subcommand is inspected through the real des dispatcher
    Then the subcommand is rejected by the dispatcher as not resolvable
