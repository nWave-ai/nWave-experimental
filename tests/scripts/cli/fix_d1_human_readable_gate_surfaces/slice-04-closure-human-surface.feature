@feature-fix-d1-human-readable-gate-surfaces @slice-04
Feature: An operator sees a colored verdict line on every remaining D1 gate CLI

  The slice-04 closure: the slice-01 helper module
  (``src/des/cli/human_surface.py``) covers the two remaining D1 gate CLIs
  the operator dispatches —
  ``scripts/cli/check_reuse_first_design.py`` (reuse-first design gate) and
  ``scripts/cli/check_scorecard_freshness.py`` (scorecard freshness audit)
  — without revisiting the helper itself (DDD-1 adopt-by-import). Each gate
  gains the same human-readable verdict line on stderr as the slice-01
  contract gate + slice-02 spine triple + slice-03 gate-class triple: a
  colored summary alongside the existing stdout token surface. After slice-04
  lands every D1 gate CLI in the 9-gate inventory emits the human surface.

  Verdict mapping per gate (the per-CLI semantics decide which prefix the
  operator sees on each path):
    * check_reuse_first_design
        - every NEW component justified in Reuse Analysis → ✅ PASS
        - at least one NEW component unjustified           → ❌ FAIL
    * check_scorecard_freshness
        - every cited F-id has a recent commit             → ✅ PASS
        - at least one cited F-id has no recent commit     → ❌ FAIL

  Note on existing structured surface — both closure CLIs emit a L1.4 stdout
  token line (``reuse_first feature=...`` and ``scorecard_freshness
  scorecard=...`` respectively). The slice-04 ATs assert (a) the per-CLI
  human verdict line is present on stderr with matching ANSI color (TTY
  mode), (b) the human line is plain readable with escapes stripped (PIPE
  mode), and (c) the existing stdout token surface remains stable across TTY
  vs PIPE invocations — Mandate 8 universe is the staged-artefact presence
  flags (gates are pure-function reads).

  # Driving ports: ``python scripts/cli/check_reuse_first_design.py``
  # | ``python scripts/cli/check_scorecard_freshness.py`` (subprocess).
  # Layer 3 (subprocess / FS acceptance). Example-only sad paths (Mandate
  # 11). The composition stages per-CLI minimal repo artefacts under tmp_path
  # (including an initialised git repo under scorecard/ for the freshness
  # probe), then spawns each gate as a real subprocess and inspects stderr
  # for both surfaces. The three Scenario Outlines parametrize-collapse the
  # three decision-table cells (GREEN-VERDICT × NEGATIVE-VERDICT × NO-TTY)
  # across the closure pair into 3 ATs × 2 Examples each — total 6
  # instances, fits the carpaccio_slice_max ceiling of 3 ATs with maximum
  # parametrize density (per max-PBT-parametrize mandate).

  Background:
    Given a tmp_path repository prepared for the D1 inventory closure pair

  @slice-04 @walking-skeleton @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator sees the green verdict line alongside the existing surface when a closure gate clears
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the existing structured surface for <gate> remains stable on the success path
    And the stderr carries the success colored verdict line summarising the <gate> outcome

    # The success path per gate clears its exit semantics (exit 0) + emits
    # its named success surface (verdict=PASS in the stdout token). Both
    # closure CLIs map to PASS on the success path. None of the two CLIs
    # have yet been wired to the human_surface helper, so each row FAILS
    # for the right reason (missing functionality, Mandate 7).
    Examples: the D1 inventory closure pair, success path
      | gate                      |
      | check-reuse-first-design  |
      | check-scorecard-freshness |

  @slice-04 @driving_port @error @contract-shape:bounded-change
  Scenario Outline: The operator sees the negative verdict line alongside the existing surface when a closure gate refuses
    Given the staged repository satisfies the negative path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the existing structured surface for <gate> remains stable on the negative path
    And the stderr carries the negative colored verdict line summarising the <gate> outcome

    # The negative verdict semantics per gate:
    #   check_reuse_first_design  → exit 1 + verdict=FAIL → ❌ FAIL (red)
    #   check_scorecard_freshness → exit 1 + verdict=FAIL → ❌ FAIL (red)
    # The composition routes the per-gate expected negative verdict via the
    # NEGATIVE_VERDICT_BY_CLOSURE_CLI lookup; the Then step asserts the
    # verdict-matching prefix glyph + the verdict-matching ANSI color escape.
    Examples: the D1 inventory closure pair, negative path
      | gate                      |
      | check-reuse-first-design  |
      | check-scorecard-freshness |

  @slice-04 @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator running a closure gate under a pipe sees a plain readable line and the existing surface remains stable
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository under a non terminal stderr
    Then the existing structured surface for <gate> remains stable on the success path
    And the stderr carries a plain readable success line summarising the <gate> outcome with no ANSI escapes
    And the existing structured surface for <gate> equals the surface observed when stderr is a real terminal

    # The NO-TTY surface preservation: pipe-mode strips ANSI escapes while
    # keeping the prefix glyph + summary text readable; the existing stdout
    # token surface per gate (reuse_first / scorecard_freshness) remains
    # byte-stable across TTY vs pipe (the new helper MUST NOT mutate the
    # existing surface contract per DISCUSS#row4 — no breaking change for
    # CI / hook consumers).
    Examples: the D1 inventory closure pair, pipe-mode preservation
      | gate                      |
      | check-reuse-first-design  |
      | check-scorecard-freshness |
