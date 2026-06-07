@feature-fix-d1-human-readable-gate-surfaces @slice-03
Feature: An operator sees a colored verdict line on every D1 gate-class-triple gate

  The slice-03 gate-class-triple extension: the slice-01 helper module
  (``src/des/cli/human_surface.py``) covers the three remaining D1 gate-class
  CLIs the operator most often dispatches —
  ``des.cli.verify_environmental_e2e`` (environmental gate),
  ``scripts/cli/verify_coverage_map.py`` (coverage-map gate) and
  ``scripts/cli/check_robustness_density.py`` (robustness-PBT gate) — without
  revisiting the helper itself (DDD-1 adopt-by-import). Each gate gains the
  same human-readable verdict line on stderr as the slice-01 contract gate +
  the slice-02 spine triple: a colored summary alongside whatever existing
  structured surface the CLI already emits.

  Verdict mapping per gate (the per-CLI semantics decide which prefix the
  operator sees on each path):
    * verify_environmental_e2e (--mode verify-authored)
        - block ABSENT (misscoped detected) → ⚠️ DEGRADED  (operator's
          legitimate "this feature does not need env-e2e" outcome)
        - feature-delta path UNREADABLE (parse/IO)      → ❌ FAIL
    * verify_coverage_map (verify subcommand)
        - structurally complete + digest matches        → ✅ PASS
        - mandatory section out of order                → ❌ FAIL
    * check_robustness_density
        - every declared domain has @given coverage     → ✅ PASS
        - a declared domain lacks coverage              → ❌ FAIL

  Note on existing structured surface — unlike slice-02 spine-triple where the
  pre-existing surface is a single-line JSON event on stderr, each slice-03
  CLI emits a DIFFERENT structured surface today:
    * verify_environmental_e2e emits the L1.4 stdout token on stdout
    * verify_coverage_map emits a free-text refusal line on stderr
    * check_robustness_density emits no structured payload (exit code only)
  The slice-03 ATs assert (a) the per-CLI human verdict line is present on
  stderr with matching ANSI color (TTY mode), (b) the human line is plain
  readable with escapes stripped (PIPE mode), and (c) the existing structured
  surface remains stable across TTY vs PIPE invocations — Mandate 8 universe
  is the staged-artefact presence flags (gates are pure-function reads).

  # Driving ports: ``des verify-environmental-e2e
  # --mode verify-authored`` | ``python scripts/cli/verify_coverage_map.py
  # verify`` | ``python scripts/cli/check_robustness_density.py`` (subprocess).
  # Layer 3 (subprocess / FS acceptance). Example-only sad paths (Mandate 11).
  # The composition stages per-CLI minimal repo artefacts under tmp_path, then
  # spawns each gate as a real subprocess and inspects stderr for both
  # surfaces. The three Scenario Outlines parametrize-collapse the three
  # decision-table cells (GREEN-VERDICT × NEGATIVE-VERDICT × NO-TTY) across
  # the gate-class triple into 3 ATs × 3 Examples each — fits the
  # carpaccio_slice_max ceiling of 3 with maximum parametrize density (per
  # max-PBT-parametrize mandate).

  Background:
    Given a tmp_path repository prepared for the D1 gate-class triple

  @slice-03 @walking-skeleton @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator sees the green verdict line alongside the existing surface when a gate-class gate clears
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the existing structured surface for <gate> remains stable on the success path
    And the stderr carries the success colored verdict line summarising the <gate> outcome

    # The success path per gate clears its exit semantics + emits its named
    # success surface. The success verdict per gate is looked up via
    # SUCCESS_VERDICT_BY_CLI: PASS for verify_coverage_map +
    # check_robustness_density; DEGRADED for verify_environmental_e2e because
    # the only verify-authored success outcome reachable in current scope is
    # the misscoped-detection branch (block absent → operator's legitimate
    # "feature does not need env-e2e" outcome). None of the three CLIs have
    # yet been wired to the human_surface helper, so each row FAILS for the
    # right reason (missing functionality, Mandate 7).
    Examples: the D1 gate-class triple, success path
      | gate                      |
      | verify-environmental-e2e  |
      | verify-coverage-map       |
      | check-robustness-density  |

  @slice-03 @driving_port @error @contract-shape:bounded-change
  Scenario Outline: The operator sees the negative verdict line alongside the existing surface when a gate-class gate refuses
    Given the staged repository satisfies the negative path for <gate>
    When the operator runs <gate> against the repository inside a real terminal
    Then the existing structured surface for <gate> remains stable on the negative path
    And the stderr carries the negative colored verdict line summarising the <gate> outcome

    # The negative verdict semantics per gate:
    #   verify_environmental_e2e → exit 2 (parse/IO) → ❌ FAIL (red)
    #   verify_coverage_map      → exit 1 + StructuralIncomplete → ❌ FAIL (red)
    #   check_robustness_density → exit 1 (CHECK_FAILED) → ❌ FAIL (red)
    # The composition routes the per-gate expected negative verdict via the
    # NEGATIVE_VERDICT_BY_CLI lookup; the Then step asserts the
    # verdict-matching prefix glyph + the verdict-matching ANSI color escape.
    Examples: the D1 gate-class triple, negative path
      | gate                      |
      | verify-environmental-e2e  |
      | verify-coverage-map       |
      | check-robustness-density  |

  @slice-03 @driving_port @contract-shape:bounded-change
  Scenario Outline: The operator running a gate-class gate under a pipe sees a plain readable line and the existing surface remains stable
    Given the staged repository satisfies the success path for <gate>
    When the operator runs <gate> against the repository under a non terminal stderr
    Then the existing structured surface for <gate> remains stable on the success path
    And the stderr carries a plain readable success line summarising the <gate> outcome with no ANSI escapes
    And the existing structured surface for <gate> equals the surface observed when stderr is a real terminal

    # The NO-TTY surface preservation: pipe-mode strips ANSI escapes while
    # keeping the prefix glyph + summary text readable; the existing
    # structured surface per gate (stdout token for env-e2e; stderr refusal
    # text for coverage-map; exit-code-only for robustness-density) remains
    # stable across TTY vs pipe (the new helper MUST NOT mutate the existing
    # surface contract per DISCUSS#row4 — no breaking change for CI / hook
    # consumers).
    Examples: the D1 gate-class triple, pipe-mode preservation
      | gate                      |
      | verify-environmental-e2e  |
      | verify-coverage-map       |
      | check-robustness-density  |
