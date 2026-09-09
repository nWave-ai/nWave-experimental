"""nw-agent-evals deterministic graders (DDD-7 EXTEND, not a new framework).

slice-08 of sustainable-test-suite adds ONE new deterministic grader row to the
shipped nw-agent-evals substrate: given a captured ATD/crafter agent TRACE
(trace-JSONL — the SAME shape SkillTrackingService parses), mechanically
distinguish a run that CONSOLIDATED-ON-ADD (reused the ATD-authored shared
vocabulary) from a run that merely ADDED fresh per-feature step definitions.

The grader REUSES the substrate's transcript parser (the module-level
`read_transcript_tool_calls` extracted from SkillTrackingService) — it does NOT
author a parallel parser nor a new eval framework. Pure + git-free + deterministic:
trace-JSONL path in, closed verdict token out — no live agent dispatch, no network.

SIGNAL #2 (DESIGN line 411, C4 line 369): "steps reuse the ATD-authored shared
vocabulary". A consolidate-on-add run shows, across its authoring `Write`/`Edit`
tool_use entries:
  1. import-from-shared  — a newly-authored step/schema file IMPORTS from the
     shared vocabulary module (`from .slice_02_...`);
  2. reuse-not-redeclare — a step file binds a declarative step while importing a
     shared step driver/definition (reuse), rather than re-declaring its own;
  3. consolidate-intent  — an authoring entry carries a CONSOLIDATE/REUSE decision.
All three present -> consolidate-on-add. Otherwise -> add-only. Trace unparseable
or carrying no authoring entries -> indeterminate (degrade LOUD; never fabricate
a consolidate-on-add pass on unreadable evidence).
"""

from __future__ import annotations

from des.application.skill_tracking_service import read_transcript_tool_calls


_CONSOLIDATE_ON_ADD = "consolidate-on-add"
_ADD_ONLY = "add-only"
_INDETERMINATE = "indeterminate"

_AUTHORING_TOOLS = ("Write", "Edit")
_STEP_FILE_MARKER = "steps"
_IMPORT_FROM_SHARED = "from .slice_02_"
_CONSOLIDATE_INTENT_TOKENS = ("CONSOLIDATE", "REUSE")


def grade_consolidate_on_add(trace_path: str) -> str:
    """Grade one captured trace for signal #2 ('steps reuse the shared vocabulary').

    Returns a CLOSED verdict token: "consolidate-on-add" | "add-only" |
    "indeterminate". Deterministic, git-free, pure (trace path in, verdict out).
    """
    authoring_entries = _authoring_entries(trace_path)
    if not authoring_entries:
        return _INDETERMINATE
    step_entries = [entry for entry in authoring_entries if _is_step_file(entry)]
    if _has_import_from_shared(step_entries) and _has_consolidate_intent(
        authoring_entries
    ):
        return _CONSOLIDATE_ON_ADD
    return _ADD_ONLY


def _authoring_entries(trace_path: str) -> list[dict]:
    """The authoring tool_use entries in the trace (any Write/Edit).

    An unreadable trace (nonexistent path, permission error) degrades LOUD to no
    entries -> the caller maps that to "indeterminate" (DDD-7: never fabricate a
    pass on unreadable evidence). The shared parser is left untouched.
    """
    try:
        tool_calls = read_transcript_tool_calls(trace_path)
    except OSError:
        return []
    return [call for call in tool_calls if call.get("name", "") in _AUTHORING_TOOLS]


def _is_step_file(entry: dict) -> bool:
    file_path = entry.get("input", {}).get("file_path", "")
    return _STEP_FILE_MARKER in file_path


def _has_import_from_shared(entries: list[dict]) -> bool:
    """A newly-authored step/schema file imports from the shared vocabulary module."""
    return any(_IMPORT_FROM_SHARED in _authored_text(entry) for entry in entries)


def _has_consolidate_intent(entries: list[dict]) -> bool:
    """An authoring entry declares a CONSOLIDATE/REUSE intent."""
    return any(
        token in _authored_text(entry)
        for entry in entries
        for token in _CONSOLIDATE_INTENT_TOKENS
    )


def _authored_text(entry: dict) -> str:
    """The authored payload of a Write/Edit entry (content for Write, new_string for Edit)."""
    payload = entry.get("input", {})
    return payload.get("content", "") + payload.get("new_string", "")
