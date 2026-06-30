@feature-sustainable-test-suite
Feature: Executable eval distinguishes a consolidate-on-add ATD run from add-only

  slice-08 of sustainable-test-suite — the EVAL slice (DDD-7). The shipped slice-07 added
  the `--consolidate-on-add` MODE + the `consolidate_on_add_gain` calc, so the gate can now
  SEE the consolidate-on-add gain WHEN a maintainer DECLARES it. slice-07's own scope note
  is explicit: the agent BEHAVIOR — the ATD actually CHOOSING to consolidate-on-add and
  REUSE the shared vocabulary — is irreducibly eval-validated and is slice-08's job. This
  slice closes that gap: an EXECUTABLE eval that, given an ATD/crafter agent TRACE, validates
  the consolidate-on-add behavior so methodology reliability is enforced by eval, not by a
  prose reviewer (slice-08 value statement; cure-principle ③, goal 8).

  Driving port (DDD-7 EXTEND, NOT a new framework): the `nw-agent-evals` substrate, which
  already parses captured agent traces (the `agent-*.jsonl` transcript — each line a
  `tool_use`/`tool_result`/assistant-text event, the SAME JSONL shape the shipped
  `SkillTrackingService` transcript parser consumes). slice-08 EXTENDS that substrate with
  ONE new deterministic grader row: `grade_consolidate_on_add(trace) -> verdict`. The grader
  is the SUT; the ATs drive it over TWO real trace-JSONL fixtures on disk
  (`fixtures/trace_consolidate_on_add.jsonl`, `fixtures/trace_add_only.jsonl`) plus an
  empty-trace degrade-LOUD fixture. Deterministic + git-free: trace-JSONL in, closed verdict
  out — no live agent dispatch, no git, no network.

  SIGNAL #2 — the mechanical discriminator (DESIGN line 411, C4 line 369): "steps reuse the
  ATD-authored shared vocabulary". The grader parses the trace's authoring `tool_use` entries
  (`Write`/`Edit` of `*steps*.py`) and classifies a CONSOLIDATE-ON-ADD run (a newly-authored
  step file IMPORTS from the shared step/schema vocabulary module AND binds a declarative
  step to an EXISTING shared step definition — reuse, not re-declaration — AND the run
  declared a CONSOLIDATE/REUSE intent) apart from an ADD-ONLY run (fresh per-feature step
  definitions re-declaring their own constants/steps, no import-from-shared, no reuse, no
  CONSOLIDATE intent). Fully mechanical — no prose-only / model-graded leg in this slice.

  Active-RED: the consolidate-on-add grader row does not exist in the substrate yet
  (`nw-agent-evals` is METHODOLOGY + the shipped transcript parser `SkillTrackingService`
  extracts skill READS only — there is NO `grade_consolidate_on_add` / no signal-#2
  classifier). The substrate import in the composition resolves to a MISSING symbol, so each
  scenario's verdict accessor raises a clean AssertionError (MISSING_FUNCTIONALITY — the
  new deterministic grader row is not yet implemented), NOT a malformed-fixture/ImportError
  at the step boundary. DELIVER makes them GREEN by adding `grade_consolidate_on_add` to the
  substrate — it does NOT author a new eval framework (DDD-7).

  @slice-08 @driving_port @real-io @contract-shape:pure-function
  Scenario: A consolidate-and-reuse trace is graded consolidate-on-add
    Given a captured ATD trace that reused the shared vocabulary when adding a slice
    When the consolidate-on-add grader runs over the trace
    Then the grader reports the verdict "consolidate-on-add"

  @slice-08 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: An add-only trace is flagged add-only
    Given a captured ATD trace that only added fresh per-feature steps without reuse
    When the consolidate-on-add grader runs over the trace
    Then the grader reports the verdict "add-only"

  @slice-08 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: An unparseable trace degrades LOUD to indeterminate
    Given a captured ATD trace that cannot be parsed for the reuse signal
    When the consolidate-on-add grader runs over the trace
    Then the grader reports the verdict "indeterminate"

  @slice-08 @driving_port @real-io @error @contract-shape:pure-function
  Scenario: A nonexistent trace path degrades LOUD to indeterminate
    Given a captured ATD trace path that does not exist on the filesystem
    When the consolidate-on-add grader runs over the trace
    Then the grader reports the verdict "indeterminate"
