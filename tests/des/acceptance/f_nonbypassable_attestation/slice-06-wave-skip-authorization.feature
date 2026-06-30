@feature-f-nonbypassable-attestation @slice-06
Feature: An off-spine wave is allowed only with human-authorized skip authorization
  As an orchestrator that has been BLOCKED from entering a wave off-spine
  I want the block to be conceded ONLY by a form-valid human-authorized skip-witness
    or a non-expired session pre-grant, and any malformed invocation rejected
  So that skipping the spine is an asymmetric-authority EXCEPTION the human concedes
    (the LLM may PROPOSE a skip; only a HUMAN GO concedes it -- DDD-9, ADR-FLOW-001),
    never an LLM-self-authorized silent default

  # slice-06 of f-nonbypassable-attestation (DDD-9, KPI-1 family at the wave
  # boundary) — the SKIP-AUTHORIZATION half of the split slice-05 (carpaccio
  # sizing fix 2026-06-16: the original slice-05 carried 10 scenarios, over the
  # carpaccio ceiling of 5). slice-05 (guard half) = the 5 guard-verdict states. slice-06 (skip half) = these 5
  # skip-authorization states.
  #
  # RUNTIME ALREADY BUILT BY slice-05 (guard half): this sub-slice's DELIVER is ATs-only. The
  # production guard (wave_dispatch_guard_policy + `des verify-wave-dispatch` gate
  # + dispatch.pre + installer) is shipped by slice-05 (guard half); slice-06 (skip half) drives the SAME in-tree gate
  # to exercise the skip-authorization branches (witness FORM check + session
  # pre-grant freshness read) + the malformed-input verdict.
  #
  # DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the REAL in-tree gate
  #   `python -m des.cli.verify_wave_dispatch`, driven via its ARGS calling
  #   convention (§22.0 H-2): --subagent-type, --prompt-path (a tmp fixture FILE),
  #   --repo-root, --session-id. observable = the process EXIT CODE (ALLOW=0 /
  #   BLOCK=1 / malformed=2) + the one JSON line printed on stdout. No guard logic
  #   is re-implemented in the step bodies (protocol-driver contract).
  #
  # DORMANT-SEAM (D11 / DDD-9): the net-new load-bearing seams slice-06 (skip half) witnesses are
  #   (a) the generalized wave-parametric skip-witness FORM check (heading +
  #   non-empty rationale) and (b) the session-scoped pre-grant freshness read,
  #   both in the new domain policy reached via the real gate entry point. At HEAD
  #   the gate module is absent, so the subprocess exits non-zero (NEITHER the
  #   expected ALLOW (0) nor BLOCK (1)). Each scenario drives THAT seam through the
  #   real gate + asserts the exit-code observable effect.
  #
  # ASYMMETRIC AUTHORITY (DDD-9, ADR-FLOW-001): a control can only FORCE the wave
  #   (the BLOCK veto); only a human GO concedes the skip. The witness is FORM-only
  #   (heading + non-empty rationale) -- the gate CANNOT verify source-authorship
  #   of plain markdown; that is review-enforced (AT-A8, the fourth honest limit).
  #
  # DISTINCT FIXTURE PER VERDICT (§22.0 gap): form-valid-witness / form-invalid-
  #   witness / valid-pre-grant / expired-grant / malformed-input are GENUINELY
  #   different on-disk witness/grant states + arg shapes, never one payload
  #   re-asserted with different Thens.
  #
  # ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the policy + the gate do not
  #   exist, so every scenario observes a module-absent non-zero exit -- semantic
  #   AssertionErrors against the expected verdict. GREEN against the runtime slice-05 (guard half)
  #   ships.

  # ---- CT-10: off-spine allowed only with a form-valid witness or valid grant -

  @slice-06 @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: An off-spine dispatch with a human-authorized skip-witness is allowed and recognized
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries no DES-WAVE marker
    And a wave-skip witness with a non-empty rationale is recorded
    When the orchestrator dispatches the agent
    Then the dispatch is allowed and names the recognized on-spine signal

  @slice-06 @driving_port @real-io @us-non-silent-wave-entry @error @contract-shape:bounded-change
  Scenario: An off-spine dispatch with an empty-rationale witness is blocked
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries no DES-WAVE marker
    And a wave-skip witness with an empty rationale is recorded
    When the orchestrator dispatches the agent
    Then the dispatch is blocked with a warn-and-ask reason

  @slice-06 @driving_port @real-io @us-non-silent-wave-entry @contract-shape:bounded-change
  Scenario: An off-spine dispatch with a valid session pre-grant is allowed and recognized
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries no DES-WAVE marker
    And a non-expired session pre-grant is recorded
    When the orchestrator dispatches the agent
    Then the dispatch is allowed and names the recognized on-spine signal

  @slice-06 @driving_port @real-io @us-non-silent-wave-entry @error @contract-shape:bounded-change
  Scenario: An off-spine dispatch with an expired session pre-grant is blocked
    Given the orchestrator dispatches a wave-owner agent
    And the dispatch carries no DES-WAVE marker
    And an expired session pre-grant is recorded
    When the orchestrator dispatches the agent
    Then the dispatch is blocked with a warn-and-ask reason

  # ---- CT MALFORMED: a malformed invocation is a distinct verdict (exit 2) ----

  @slice-06 @driving_port @real-io @us-non-silent-wave-entry @error @contract-shape:bounded-change
  Scenario: A dispatch invoked without the required subagent type is rejected as malformed
    Given the orchestrator dispatches a wave-owner agent
    When the orchestrator dispatches the agent without naming the subagent type
    Then the dispatch is rejected as malformed input
