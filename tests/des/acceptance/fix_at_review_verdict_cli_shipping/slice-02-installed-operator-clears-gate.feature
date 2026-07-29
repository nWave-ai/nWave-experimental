@feature-fix-at-review-verdict-cli-shipping
Feature: An installed operator records a verdict that clears the carpaccio gate
  # fix-at-review-verdict-cli-shipping — DISTILL (Quinn), 2026-05-29.
  # DESIGN SSOT: docs/feature/fix-at-review-verdict-cli-shipping/design/architecture.md §6 + ADR-001.
  #
  # The keystone: a non-Lyra operator on an installed instance — which has NO
  # enclosing repository at any location the recorder could deduce from its own
  # file path — records an approval that the carpaccio DISTILL->DELIVER gate
  # then trusts. The recorder must locate the working repository the operator
  # names explicitly (an environment pointer, or the directory the operator
  # runs from), never from where the recorder file happens to sit. This slice
  # exercises that no-enclosing-repo environment end to end (Earned Trust: the
  # installed layout lies about file-relative roots).
  #
  # Driving port (Mandate-13): the installed recorder module subprocess
  # (`python -m des.cli.at_review_verdict`, Layer-3 subprocess) to record, then
  # the installed carpaccio gate module subprocess
  # (`python -m des.cli.carpaccio_slice_gate`, Layer-3 subprocess) to observe
  # the gate decision. The recorder process runs from a working directory with
  # NO enclosing repository, pointed at the working repository only by an
  # explicit environment pointer. NO direct domain import; NO behavioral AT
  # under tests/des/unit/.
  #
  # Layer 3/4 (subprocess wiring_e2e) — example-only, no PBT (Mandate 9/11).
  # The repo-root-resolution environment (manifest C6: environment-pointer
  # absent/present, run-from directory) is covered example-based across the
  # three scenarios, not Hypothesis-generated.
  #
  # Observable surface = exit code + ledger record (verdict line present/absent)
  # + gate decision (cleared / blocked). Never an internal call.
  #
  # KEYLESS re-authoring (oss-review-verdict-demotion S2, 2026-06-11): the
  # producer no longer writes an hmac_sha256 field and resolves no signing key
  # (key absence is a non-event). The signed-verdict assertion this suite
  # carried is superseded by the keyless equal-or-stronger pair: the record
  # binds the reviewer identity + content seal, and carries no signature field.
  # The installed-operator routing, ledger append, cwd-resolution keystone and
  # gate round-trip survive unchanged — they never depended on the key.
  #
  # ADR-028 RED scaffold: these scenarios are UNSKIPPED and FAIL on current
  # master for the RIGHT reason — the recorder is not importable from the
  # installed recorder namespace (it lives outside the shipped source tree),
  # so the recording subprocess cannot run on the installed layout and the
  # gate never sees an approval to clear on.

  Background:
    Given an installed instance with no enclosing repository and an empty AT-completion ledger

  @slice-02 @driving_port @walking_skeleton @real-io @contract-shape:bounded-change @coupled
  Scenario: The installed recorder appends an approval the gate can trust
    Given the operator points the recorder at the working repository explicitly
    When the operator records an approved AT-review verdict from the installed instance
    Then the working repository's ledger gains one AT-review verdict for the slice
    And the recorded verdict binds the reviewer identity and the content seal it was reviewed under
    And the recorded verdict carries no signature field and needed no key

  @slice-02 @driving_port @real-io @contract-shape:bounded-change @coupled
  Scenario: The carpaccio gate clears for a slice the installed operator approved
    Given the operator points the recorder at the working repository explicitly
    And the operator has recorded an approved AT-review verdict from the installed instance
    When the operator runs the carpaccio gate for that slice from the installed instance
    Then the carpaccio gate clears the slice

  @slice-02 @driving_port @error @real-io @contract-shape:bounded-change @coupled
  Scenario: A needs-revision review records a NEEDS_REVISION verdict and the gate stays blocked
    Given the operator points the recorder at the working repository explicitly
    When the operator records a needs-revision AT-review verdict from the installed instance
    Then the installed recorder completes the recording cleanly
    And the working repository's ledger gains one AT-review verdict for the slice
    And the recorded verdict is not an approval
    And the carpaccio gate refuses to clear the slice

  # PRR keystone witness (reviewer iteration 1 blocker): the recorder is run
  # with NO repository pointer at all — neither a flag nor an environment
  # pointer — from inside the working repository the operator is standing in.
  # The only way the approval can land in that working repository's ledger is
  # if the recorder resolves the repository from the directory the operator
  # runs in. Restoring the dropped file-path-relative resolution would resolve
  # into the shipped recorder's own package instead, so no approval would land.
  @slice-02 @driving_port @real-io @contract-shape:bounded-change @coupled
  Scenario: The recorder resolves the working repository from where the operator stands
    When the operator records an approved AT-review verdict standing in the working repository with no repository pointer
    Then the working repository's ledger gains one AT-review verdict for the slice
