"""Test-side composition for slice-08: drive the REAL nw-agent-evals substrate + the NEW
consolidate-on-add deterministic grader over a trace-JSONL fixture, assert its verdict.

slice-08 of sustainable-test-suite — the EVAL slice (DDD-7). The shipped slice-07 added the
`--consolidate-on-add` MODE + the `consolidate_on_add_gain` calc: the gate can now SEE the
consolidate-on-add gain WHEN a maintainer DECLARES it. But slice-07's own scope note is
explicit: "The agent BEHAVIOR (the ATD actually CHOOSING to consolidate-on-add) is
irreducibly eval-validated and is slice-08's job." slice-08 closes that: an EXECUTABLE eval
that, given an ATD/crafter agent TRACE, mechanically distinguishes a run that
CONSOLIDATED-AND-REUSED the shared vocabulary from a run that merely ADDED.

Driving port (DDD-7 EXTEND, NOT a new framework): the `nw-agent-evals` substrate already
parses captured agent traces (the `agent-*.jsonl` transcript: each line a `tool_use` /
`tool_result` / assistant-text event — the SAME JSONL shape
`des.application.skill_tracking_service.SkillTrackingService._read_transcript_tool_calls`
consumes). slice-08 EXTENDS that substrate with ONE new deterministic grader row:
`grade_consolidate_on_add(trace_path) -> ConsolidateOnAddEvalVerdict`. The grader is the SUT;
this composition drives it over the two real trace-JSONL fixtures on disk.

SIGNAL #2 — the mechanical discriminator (DESIGN line 411, C4 line 369): "steps reuse the
ATD-authored shared vocabulary". The grader parses the trace's authoring `tool_use` entries
(`Write` / `Edit` of `*steps*.py` files) and classifies:

  * CONSOLIDATE-ON-ADD — a newly-authored step file IMPORTS from the shared step/schema
    vocabulary module (e.g. `from .slice_02_domain_types import ...` /
    `from .slice_02_composition import ...`) AND binds a declarative step to an EXISTING
    shared step definition (reuse, not re-declaration), AND the run declared a
    CONSOLIDATE/REUSE intent (an `Edit`/`Write` carrying a `CONSOLIDATE`/`REUSE` decision
    cell). Signal #2 DETECTED.
  * ADD-ONLY — the newly-authored step files re-declare their OWN constants/steps with NO
    import-from-shared and NO reuse of an existing shared step definition, and NO
    CONSOLIDATE/REUSE intent. Signal #2 ABSENT → the grader flags it `add-only`.

Deterministic + git-free: the input is the trace-JSONL file (the captured run), parsed with
stdlib `json` + text inspection of the authored tool inputs — no git, no live agent dispatch,
no network. Same trace-JSONL-in / verdict-out shape the substrate already uses.

Active-RED: the consolidate-on-add grader row does not exist in the substrate yet
(`nw-agent-evals` is METHODOLOGY + the transcript parser is `SkillTrackingService`, which
extracts skill READS only — it has NO `grade_consolidate_on_add` / no signal-#2
classifier). The substrate's import below resolves to a MISSING symbol, so each scenario's
verdict accessor raises a clean AssertionError (MISSING_FUNCTIONALITY — the new grader row is
not yet implemented), NOT a malformed-fixture error. DELIVER makes them GREEN by adding the
`grade_consolidate_on_add` deterministic grader to the substrate — it does NOT author a new
eval framework (DDD-7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .eval_domain_types import ConsolidateOnAddEvalVerdict


# The two real trace-JSONL fixtures live alongside this steps dir under ../fixtures.
_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_CONSOLIDATE_TRACE = _FIXTURES_DIR / "trace_consolidate_on_add.jsonl"
_ADD_ONLY_TRACE = _FIXTURES_DIR / "trace_add_only.jsonl"
_EMPTY_TRACE = _FIXTURES_DIR / "trace_empty.jsonl"
# Boundary-ZERO: a captured-trace path that does NOT exist on disk. NO fixture file is
# written — the ABSENCE is the condition. A nonexistent path IS unreadable evidence; the
# grader must degrade LOUD to `indeterminate`, never crash (FileNotFoundError) on the
# substrate parser's bare open(). The .jsonl name keeps the shape consistent; it is never
# created.
_NONEXISTENT_TRACE = _FIXTURES_DIR / "trace_nonexistent_does_not_exist.jsonl"


@dataclass(frozen=True)
class GraderResult:
    """The observable surface of one consolidate-on-add grader run over a trace."""

    verdict_token: str

    def verdict(self) -> str:
        return self.verdict_token


def _grade(trace_path: Path) -> GraderResult:
    """Drive the REAL nw-agent-evals substrate consolidate-on-add grader (the SUT).

    Active-RED: imports the NEW grader row the substrate gains in DELIVER. At HEAD that
    symbol does not exist, so the import raises ImportError/AttributeError — caught here and
    surfaced as a clean MISSING_FUNCTIONALITY AssertionError (a semantic business-logic
    failure: the consolidate-on-add grader row is not yet implemented), NOT a fixture/setup
    error. The fixtures are valid trace-JSONL on disk; the SUT is what is missing.
    """
    try:
        # DDD-7: EXTEND the substrate with ONE new deterministic grader row. DELIVER homes
        # `grade_consolidate_on_add` in the eval-substrate grader module (the new row added
        # alongside the transcript parser the substrate already ships). The grader takes the
        # trace-JSONL path and returns the closed verdict token.
        from des.application.agent_eval_graders import (  # type: ignore[import-not-found]
            grade_consolidate_on_add,
        )
    except (ImportError, AttributeError) as exc:  # pragma: no cover - RED path
        raise AssertionError(
            "the nw-agent-evals consolidate-on-add grader row is not yet implemented "
            "(MISSING_FUNCTIONALITY — DDD-7 EXTEND: a deterministic "
            "`grade_consolidate_on_add(trace_path) -> verdict` that detects signal #2 "
            "'steps reuse the ATD-authored shared vocabulary' from a trace-JSONL fixture "
            "does not exist at HEAD; the substrate ships only the skill-READ transcript "
            "parser, no signal-#2 classifier). DELIVER adds the grader row to the substrate "
            "— it does NOT author a new eval framework. "
            f"import error: {exc!r}"
        ) from exc
    token = grade_consolidate_on_add(str(trace_path))
    return GraderResult(verdict_token=str(token))


class ConsolidateOnAddEvalDriver:
    """Test-side driving facade over the nw-agent-evals consolidate-on-add grader (the SUT).

    Selects ONE of the real trace-JSONL fixtures (consolidate-on-add / add-only / empty),
    runs the deterministic grader over it, and exposes the closed verdict token for
    assertion. No live agent dispatch, no git, no network — trace-JSONL in, verdict out.
    """

    def __init__(self) -> None:
        self._trace_path: Path | None = None
        self._result: GraderResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_consolidate_on_add_trace(self) -> None:
        """A captured ATD trace that REUSED the shared vocabulary (signal #2 present)."""
        assert _CONSOLIDATE_TRACE.exists(), (
            f"the consolidate-on-add trace fixture is missing at {_CONSOLIDATE_TRACE} — "
            "the eval fixture, not the SUT, is absent"
        )
        self._trace_path = _CONSOLIDATE_TRACE

    def given_add_only_trace(self) -> None:
        """A captured ATD trace that only ADDED fresh per-feature steps (signal #2 absent)."""
        assert _ADD_ONLY_TRACE.exists(), (
            f"the add-only trace fixture is missing at {_ADD_ONLY_TRACE} — "
            "the eval fixture, not the SUT, is absent"
        )
        self._trace_path = _ADD_ONLY_TRACE

    def given_unparseable_trace(self) -> None:
        """An empty/unparseable trace — the grader must degrade LOUD, not fabricate a pass."""
        # Bootstrap an empty trace fixture for the degrade-LOUD scenario (test-arrangement).
        _EMPTY_TRACE.write_text("", encoding="utf-8")
        self._trace_path = _EMPTY_TRACE

    def given_nonexistent_trace(self) -> None:
        """A captured-trace path that does NOT exist on disk — boundary-ZERO unreadable evidence.

        No fixture file is written: the ABSENCE is the condition. A nonexistent path is
        unreadable evidence, so the grader must degrade LOUD to `indeterminate`, never crash.
        """
        assert not _NONEXISTENT_TRACE.exists(), (
            f"the boundary-ZERO trace path must NOT exist at {_NONEXISTENT_TRACE} — "
            "its absence IS the condition under test"
        )
        self._trace_path = _NONEXISTENT_TRACE

    # -- act (When) ----------------------------------------------------------

    def when_grader_runs(self) -> None:
        assert self._trace_path is not None, "no trace fixture was selected"
        self._result = _grade(self._trace_path)

    # -- assert (Then) -------------------------------------------------------

    def then_verdict_is(self, expected: ConsolidateOnAddEvalVerdict) -> None:
        result = self._require_result()
        assert result.verdict() == expected.value, (
            f"the consolidate-on-add grader must emit {expected.value!r} for this trace "
            f"(signal #2 = 'steps reuse the ATD-authored shared vocabulary'); "
            f"got {result.verdict()!r}"
        )

    # -- internals -----------------------------------------------------------

    def _require_result(self) -> GraderResult:
        assert self._result is not None, "the consolidate-on-add grader was not run"
        return self._result
