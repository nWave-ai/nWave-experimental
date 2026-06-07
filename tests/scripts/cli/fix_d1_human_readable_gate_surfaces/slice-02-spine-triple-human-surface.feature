@feature-fix-d1-human-readable-gate-surfaces @slice-02
Feature: An operator sees a colored verdict line on every D1 spine-triple gate

  The slice-02 spine-triple extension: the slice-01 helper module
  (``src/des/cli/human_surface.py``) covers the three remaining most
  operator-visible D1 gates — ``verify_slice_commit_completeness``,
  ``carpaccio_slice_gate`` and ``at_review_verdict`` — without revisiting the
  helper itself (DDD-1 adopt-by-import). Each gate gains the same dual
  surface as the contract gate: a single-line JSON event (unchanged
  byte-content for machine consumers) AND a short colored human-readable
  summary line on stderr.

  Verdict mapping per gate (the per-CLI semantics decide which prefix the
  operator sees):
    * verify_slice_commit_completeness   — APPROVED → ✅ PASS / refused → ❌ FAIL
    * carpaccio_slice_gate               — cleared → ✅ PASS / refused → ❌ FAIL
    * at_review_verdict                  — APPROVED → ✅ PASS / NEEDS_REVISION → ⚠️ DEGRADED

  # Driving port: ``des verify-slice-commit`` |
  # ``des carpaccio-slice-gate`` |
  # ``python scripts/cli/at_review_verdict.py`` (subprocess). Layer 3
  # (subprocess / FS acceptance). Example-only sad paths (Mandate 11). The
  # composition stages per-CLI minimal repo artefacts under tmp_path, then
  # spawns each gate as a real subprocess and inspects stderr for both
  # surfaces. The three Scenario Outlines parametrize-collapse the three
  # decision-table cells (GREEN × NEGATIVE × NO-TTY) across the spine triple
  # into 3 ATs × 3 Examples each — fits the carpaccio_slice_max ceiling of 3
  # with maximum parametrize density (per max-PBT-parametrize mandate).

  Background:
    Given a tmp_path repository prepared for the D1 spine-triple gates

  @slice-02 @walking-skeleton @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator sees a green PASS line alongside the structured event when a spine-triple gate clears
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the stderr carries a single-line JSON success event for <gate>
    And the stderr carries a green colored PASS line summarising the <gate> outcome

    # The success path per gate clears its exit semantics + emits its named
    # success event (SliceCommitComplete / SliceCleared / ATReviewVerdictCLI
    # with verdict_written=True). All three rows on master have NOT yet been
    # wired to the human_surface helper, so each row FAILS for the right
    # reason (missing functionality, Mandate 7).
    Examples: the D1 spine triple, success path
      | gate                              |
      | verify-slice-commit-completeness  |
      | carpaccio-slice-gate              |
      | at-review-verdict                 |

  @slice-02 @driving_port @error @contract-shape:bounded-change
  Scenario Outline: The operator sees the negative verdict line alongside the structured event when a spine-triple gate refuses
    Given the staged repository satisfies the negative path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the stderr carries a single-line JSON negative event for <gate>
    And the stderr carries the negative colored verdict line summarising the <gate> outcome

    # The negative verdict semantics differ per gate:
    #   verify-slice-commit-completeness  → SliceCommitIncomplete   → ❌ FAIL  (red)
    #   carpaccio-slice-gate              → CARPACCIO_SLICE_TOO_LARGE → ❌ FAIL  (red)
    #   at-review-verdict (NEEDS_REVISION) → ATReviewVerdictCLI       → ⚠️ DEGRADED (yellow)
    # The composition routes the per-gate expected verdict via the
    # NEGATIVE_VERDICT_BY_CLI lookup; the Then step asserts the
    # verdict-matching prefix glyph + the verdict-matching ANSI color escape.
    Examples: the D1 spine triple, negative path
      | gate                              |
      | verify-slice-commit-completeness  |
      | carpaccio-slice-gate              |
      | at-review-verdict                 |

  @slice-02 @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator running a spine-triple gate under a pipe sees a plain readable line and the JSON event remains stable
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository under a non terminal stderr
    Then the stderr carries a single-line JSON success event for <gate>
    And the stderr carries a plain readable PASS line summarising the <gate> outcome with no ANSI escapes
    And the JSON success event for <gate> equals the event observed when stderr is a real terminal

    # The NO-TTY surface preservation: pipe-mode strips ANSI escapes while
    # keeping the prefix glyph + summary text readable; the structured JSON
    # event remains byte-content stable across TTY vs pipe (the new helper
    # MUST NOT mutate the existing machine-readable contract per DISCUSS#row4
    # — no breaking change for CI / hook consumers).
    Examples: the D1 spine triple, pipe-mode preservation
      | gate                              |
      | verify-slice-commit-completeness  |
      | carpaccio-slice-gate              |
      | at-review-verdict                 |
