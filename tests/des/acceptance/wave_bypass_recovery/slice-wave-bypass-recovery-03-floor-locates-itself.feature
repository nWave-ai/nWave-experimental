@feature-fix-wave-bypass-recovery-truthful @slice-03
Feature: A wave-bypass veto names WHERE the blocking floor lives and WHY it exists
  As an LLM whose Task dispatch is vetoed by the wave-bypass spine veto
  I want the refusal to name the floor file's absolute path, the resolved
    project root, and -- for an INFERRED floor -- the signal it was deduced
    from
  So that I do not have to run four investigation commands to find what the
    gate already read to decide the refusal

  # slice-03 of fix-wave-bypass-recovery-truthful (docs/mikado/EXECUTION-SSOT-
  # des-optimization.md, defect 3 -- "the refusal is silent on WHERE and WHO").
  # At HEAD `_describe_wave_floor` states wave/provenance/age/TTL but omits the
  # floor file's PATH, the RESOLVED project root, and -- for an INFERRED floor
  # -- WHICH signal it was deduced from ("inferred" without an antecedent is a
  # label, not information). The system already read the path and the root to
  # decide the refusal; withholding them pushes an investigation the producer
  # already did back onto the reader (the same cost-on-the-operator asymmetry
  # named for defects 1 and 2).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the REAL spine service
  # via the production composition root, same seam as slice-01 --
  #   PreToolUseService.validate (service_factory.create_pre_tool_use_service).
  # observable = HookDecision.reason on a WAVE_MARKER_BYPASS block.
  #
  # ARMED PRECONDITION: reuses slice-01's stale inferred floor + partial-context
  # sub-dispatch (the same empirically-hit WAVE_MARKER_BYPASS trigger).
  #
  # ORACLE:
  #   * the reason names the floor file's absolute PATH (the literal
  #     `.nwave/wave-active/active.json` suffix under the armed project root).
  #   * the reason names the resolved project ROOT (the same root the floor was
  #     armed under).
  #   * the reason names WHAT INFERRED means for THIS floor -- the concrete
  #     signal it was deduced from -- not the bare word "inferred" alone.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # `_describe_wave_floor` emits neither the path nor the root nor the
  # inferred-signal sentence, so all three assertions fire a semantic
  # AssertionError, never a collection / import / setup error.

  @slice-03 @walking_skeleton @driving_port @real-io @us-truthful-recovery @error @contract-shape:bounded-change
  Scenario: A wave-bypass veto names the floor's path, root, and inferred signal
    Given a stale inferred wave floor the dispatch is not entering
    When a partial-context in-wave dispatch is vetoed for the bypass
    Then the reason names the floor file's absolute path
    And the reason names the resolved project root
    And the reason names the concrete signal the inferred floor was deduced from
