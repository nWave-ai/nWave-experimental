@feature-oss-dormant-seam-gate @slice-04
Feature: A pre-existing static-tree seam is never retroactively flagged, because the gate scopes to the net-new delta
  As an nWave operator turning the dormant-seam gate on for the first time
  I want a net-new dormant seam to be warned while every seam that already
    lived on the static tree (and may have shipped dormant long ago) stays
    silent -- the gate's blast-radius is the feature's net-new delta, not the
    whole tree --
  So that turning the gate on does NOT trigger a mass re-flag of the entire
    existing codebase: the gate is adoptable because it carries zero retroactive
    blast (DISCUSS D3 -- net-new-delta-only)

  # slice-04 of oss-dormant-seam-gate -- NET-NEW-DELTA SCOPING (DISCUSS D3 +
  # DESIGN D-2 / Reuse R4 + Per-Slice Companion slice-04). The FINAL slice. Closes
  # the gate's blast-radius contract: the gate evaluates ONLY the feature's net-new
  # delta -- a symbol already on the static tree is NEVER retroactively flagged --
  # layered on slice-01/02/03's detection / escape / precision seams.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
  # slice-01/02/03 -- the REAL `des dormant-seam-gate` composition-root CLI invoked
  # as a subprocess black box (`python -m des.cli.dormant_seam_gate`). The detector,
  # the changed-symbol port, and the git delta read are NEVER imported-and-called at
  # the step boundary. Observable surface: the single-line JSON verdict on stdout,
  # the loud human warning on stderr, the process exit code.
  #
  # SUBSTRATE (REUSE + EXTEND): the slice-01/02/03 synthetic-repo builder shape (a
  # real tmp git repo, a committed base branch, then net-new ADDED `src/des/`
  # modules) is reused, EXTENDED to seed a PRE-EXISTING static-tree symbol via the
  # INITIAL commit (on the base ref, before the delta), then the net-new delta in a
  # SECOND commit. The gate measures `git diff --diff-filter=A {base_ref}...HEAD`
  # (added files since the merge-base) -- so the base-committed symbol is OUT of the
  # delta by construction, and the second-commit added file is IN it.
  #
  # OQ-1 RESOLUTION (DESIGN D-2 -- the open question slice-04's AT pins): the net-new
  # granularity floor is the ADDED-FILE (NOT the added-LINE). A symbol added to a
  # MODIFIED file (a file that already existed on the static tree) is OUT of the
  # delta at the added-FILE floor, because `--diff-filter=A` returns ADDED files
  # only -- a modified file (and any net-new symbol it carries) is not in the
  # delta. This is an explicit, honestly-named limitation (the slice-04 OQ-1
  # contract), NOT a bug; added-LINE resolution is a future hardening concern. The
  # "modified-file-add" scenario pins this floor so the contract is unambiguous for
  # the next developer.
  #
  # RED-for-right-reason / GREEN-on-author (ADR-025 + ADR-028; verified from source
  # 2026-06-07): the shipped slice-01/02/03 production ALREADY scopes to the net-new
  # delta -- `ChangedSymbolPort`/`GitChangedSymbolAdapter` uses `git diff
  # --diff-filter=A` (added files only), and `_parse_added_src_modules` parses ONLY
  # files in that delta. A base-committed (pre-existing) symbol is therefore never
  # parsed and never flagged. slice-04 is consequently a GREEN-ON-AUTHOR regression
  # PIN (like an R3 parity pin): it pins the no-retroactive-blast safety property +
  # resolves OQ-1's added-FILE granularity, BOTH already satisfied by the shipped
  # added-FILE delta. Reported honestly as GREEN-on-author -- no production change
  # is required; the PIN guards the property against a future regression (e.g. a
  # well-meaning change to `--diff-filter=AM` that would suddenly re-flag the tree).
  #
  # HARD INVARIANT (non-halting, KPI-2 guardrail): every scoping outcome stays
  # exit 0; no scenario asserts a block / refuse.
  #
  # NON-VACUITY (perturbation-bound -- scoping is NOT vacuously "flag nothing"): in
  # the SAME repo as a pre-existing symbol, a NET-NEW added-file dormant symbol
  # STILL warns -- the scoping excludes the static tree, it does not silence the
  # delta. The pre-existing-clear is therefore bound to delta membership, not an
  # always-clean gate (KPI-1 recall control preserved alongside the KPI-3 guardrail).
  #
  # SUT verdict model (C2 / C5 -- the scoping decision table over an effectful
  # public symbol, by delta membership):
  #   | delta membership                          | verdict for the symbol           |
  #   | net-new added file, no call-site          | DORMANT -> warn-loud (recall)    |
  #   | pre-existing static tree, no call-site     | OUT OF SCOPE -> never flagged    |
  #   | net-new symbol in a MODIFIED file          | OUT OF SCOPE (added-FILE floor)  |
  #
  # CONTRACT-SHAPE (2026-05-15 mandate, machine-parseable):
  #   * the no-retroactive-blast + modified-file-floor scenarios are
  #     @contract-shape:unbounded-preservation -- the property is that the existing
  #     static tree (and the modified-file's net-new symbol, below the floor) is
  #     PRESERVED unflagged regardless of the delta contents (the warning does not
  #     leak onto out-of-scope symbols);
  #   * the discrimination scenario is @contract-shape:bounded-change -- in the same
  #     repo only the net-new added-file symbol moves INTO the flagged set; the
  #     pre-existing one stays out (the flagged set changes in a bounded, named way).
  #
  # TAG SCHEME (strict-markers safe -- mirrors slice-01/02/03 + the sibling suites):
  # scenario @tags become dynamic pytest marks via pytest-bdd's tag pipeline; the
  # project's filterwarnings suppresses PytestUnknownMarkWarning so --strict-markers
  # does not reject them. Binding goes through the RELATIVE `scenarios("../<feature>")`
  # from the slice-04 steps module. Every step decorator's literal text is UNIQUE
  # within this feature directory (S1 step-text-uniqueness: slice-04 step literals --
  # "delta-scoped dormant-seam gate", the pre-existing / discrimination / modified-
  # file Givens, the "delta-scoped gate exits with code zero" Then -- are distinct
  # from slice-01/02/03's step literals).

  @slice-04 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A seam that already lived on the static tree is never retroactively flagged
    Given a dormant effectful seam that already existed on the static tree before this change
    When the developer runs the delta-scoped dormant-seam gate at GREEN-phase
    Then the gate leaves the pre-existing static-tree seam unflagged and unnamed
    And the delta-scoped gate exits with code zero

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: Only the net-new seam is flagged when a dormant pre-existing seam shares the repo
    Given a net-new dormant seam alongside a pre-existing dormant seam already on the static tree
    When the developer runs the delta-scoped dormant-seam gate at GREEN-phase
    Then the gate flags only the net-new seam and leaves the pre-existing seam out of scope
    And the gate names the net-new seam in its loud warning
    And the delta-scoped gate exits with code zero

  @slice-04 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A net-new symbol added to a pre-existing modified file is out of scope at the added-file floor
    Given a net-new dormant symbol added to a file that already existed on the static tree
    When the developer runs the delta-scoped dormant-seam gate at GREEN-phase
    Then the gate leaves the modified-file symbol out of scope at the added-file granularity floor
    And the delta-scoped gate exits with code zero
