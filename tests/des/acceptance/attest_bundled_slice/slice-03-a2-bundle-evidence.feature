@feature-f-attest-bundled-slice @slice-03
Feature: Bundled-slice attestation binds on the slice's real acceptance evidence, not a trailer name
  As a maintainer recovering a bundle-delivered slice the closure scorecard counts partial
  I want `des attest-bundled-slice` to replace reverify's trailer-name precondition (P2) with the
    A2 bundle-binding evidence -- the slice's real @slice-NN acceptance test (A2.a), a recognised
    carpaccio/wave trailer present by EITHER branch (A2.b), and no deferred scenario (A2.c)
  So that a slice bundled under a DIFFERENT trailer (the f-design `Step-Id:` shape) can be honestly
    attested on the artifact the trailer pointed at, while an arbitrary hotfix or a deferred-scenario
    theater is still refused -- a STRONGER evidence basis than the trailer string it replaces

  # slice-03 of f-attest-bundled-slice (classic spine; engine CLI, no LLM in path).
  # slice-03 DELIVER restructures attest_bundled_slice.main() to compose P1, A2, P3,
  # P5, P6 -- A2 REPLACING the inherited strict P2 (trailer-name) + promoting P4 to the
  # binding evidence. A2 is the conjunction:
  #   A2.a -- the @slice-NN .feature AT is present in the bundle commit's tree OR
  #           recoverable from commit~1 (reuse _in_commit_at_presence +
  #           _tracked_before_at_presence verbatim).
  #   A2.b -- TWO-BRANCH trailer presence: bool(extract_slice_ids(msg)) OR
  #           _has_step_id_line(msg) (a NEW raw-line helper). THE CRUX: a
  #           `Step-Id: <feature>-design`-only bundle commit (extract_slice_ids -> [])
  #           PASSES via branch 2 -- else f-design's 531cfb59a is refused (C1/C2).
  #   A2.c -- the matched @slice-NN .feature is scanned for @skip/@xfail/@wip; any tag
  #           -> refused (the H2 deferred-scenario theater hole).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL `des` dispatcher via
  # `python <src/des/cli/__main__.py> attest-bundled-slice ...` against a crafted TEMP
  # git repo (its own .git/ + .nwave/ ledger), REUSING slice-02's hard-won harness
  # (_run_des by-path dispatch + git-fixture builders) verbatim. The observables =
  # process exit code + the terminal attest JSON event/diagnosis on stdout (the
  # freshness autoskip prefix line a developer-checkout temp repo emits is parsed past).
  # The composition imports ZERO des.adapters.* (slice-02 RC-2 / F-005 boundary).
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam this slice wires is the
  # A2 evidence check (A2.a/A2.b/A2.c, the P2 replacement) inside main(). Each scenario
  # drives that seam through the REAL dispatcher subprocess and asserts the observable
  # refusal (SliceAttestRefused, exit 1) or the not-refused-on-the-trailer-ground effect
  # -- not an import-shape check.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD main()
  # is the slice-02 shape -- it runs the shared _preconditions (P1->P2->P3->P4->P5->P6)
  # then emits BundledSliceAttestPreconditionsCleared (exit 0). So:
  #   * the absent-AT fixture is refused now by the INHERITED P4 (with the reverify
  #     diagnosis); A2.a will refuse with its OWN diagnosis -> the oracle asserts the
  #     refusal is NOT the inherited P4 text (active-RED, the P4 text is present now).
  #   * the no-trailer fixture is refused now by the INHERITED P2; same discriminating
  #     oracle -> active-RED.
  #   * the Step-Id:-only crux fixture is REFUSED now by the INHERITED P2 (slice not in
  #     extract_slice_ids=[]); A2.b branch 2 will let it PROCEED -> the not-refused
  #     assertion is active-RED.
  #   * the @xfail-scenario fixture PROCEEDS past P1-P6 now (exit 0); A2.c will REFUSE
  #     -> the refusal assertion is active-RED.
  # Each Then turns a captured subprocess observable into a semantic AssertionError. No
  # @skip, no import / collection error. GREEN once slice-03 DELIVER wires A2 into main().

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a bundle commit that carries no acceptance test for the slice is refused
    Given a bundle commit that names the slice in its trailer but carries no acceptance test for it
    When the maintainer attests the bundled slice
    Then the attestation is refused because the slice's real acceptance evidence is absent

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting an arbitrary commit that carries no carpaccio or wave trailer is refused
    Given a bundle commit that carries the slice's acceptance test but neither a slice nor a step trailer
    When the maintainer attests the bundled slice
    Then the attestation is refused because the commit carries no recognised carpaccio or wave trailer

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A slice bundled under a feature-level step trailer is not refused on the trailer ground
    Given a bundle commit trailered only with a feature-level step that names no slice but carries the slice's acceptance test
    When the maintainer attests the bundled slice
    Then the attestation is not refused on the trailer ground because the step trailer is recognised

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A slice bundled under a commit trailing a DIFFERENT slice is not refused on the trailer ground
    Given a bundle commit trailing a different slice but carrying this slice's acceptance test
    When the maintainer attests the bundled slice
    Then the attestation is not refused on the trailer ground because a recognised slice trailer is present

  @slice-03 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: Attesting a slice whose only scenario is deferred is refused
    Given a bundle commit whose slice acceptance test carries a deferred scenario
    When the maintainer attests the bundled slice
    Then the attestation is refused because a deferred scenario is not genuinely exercised
