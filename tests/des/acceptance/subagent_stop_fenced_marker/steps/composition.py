"""Composition root for the SubagentStop fenced-marker acceptance suite.

Mandate-13 (Driving-Port-Only Boundary): the SUT is driven through the REAL
SubagentStop return-resolution entry point —
``extract_des_context_from_transcript`` in
``src/des/adapters/drivers/hooks/subagent_stop_handler.py`` — the exact function
that calls ``DesMarkerParser().parse(content)`` at line 148, i.e. the false-block
surface. It is reached over a REAL JSONL transcript file written under
``tmp_path`` (Layer-3 composition: real resolver + real parser + real file I/O).

Hermeticity: the transcript is ALWAYS built under a caller-supplied ``tmp_path``;
no personal-hook home-directory path is ever touched.

Business logic lives here, not in the step bodies / test bodies: a step states a
typed ``MarkerPlacement`` precondition and reads the typed ``ResolvedContext``
outcome; this composition owns building the return content for a placement and
driving the real resolver.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.drivers.hooks.subagent_stop_handler import (
    extract_des_context_from_transcript,
)

from .domain_types import MarkerPlacement, ResolvedContext


# A complete classic DES marker set. At HEAD the resolver matches this anywhere
# in the return content (no fence exclusion); the fix must exclude it when it
# sits inside a fenced / inline-code span. The PROJECT-ID is a documentation
# value — a read-only return quoting the marker syntax, NOT a real dispatch.
_DOCUMENTED_MARKER_PROJECT_ID = "doc-quoted-feature"
_CLASSIC_MARKER_SET = (
    "<!-- DES-VALIDATION : required -->\n"
    f"<!-- DES-PROJECT-ID : {_DOCUMENTED_MARKER_PROJECT_ID} -->\n"
    "<!-- DES-STEP-ID : 01-01 -->\n"
)
#: The same marker set collapsed onto one line, for an inline `backtick` span.
_CLASSIC_MARKER_ONE_LINE = (
    "<!-- DES-VALIDATION : required --> "
    f"<!-- DES-PROJECT-ID : {_DOCUMENTED_MARKER_PROJECT_ID} --> "
    "<!-- DES-STEP-ID : 01-01 -->"
)


def _return_content_for(placement: MarkerPlacement) -> str:
    """Build an agent's read-only return content carrying the marker per placement.

    The narrative prose around the marker is what a troubleshooter / read-only
    sister actually returns when EXPLAINING the marker syntax.
    """
    if placement is MarkerPlacement.FENCED_BLOCK:
        return (
            "Here is how a DES dispatch declares its wave context — note the "
            "marker block:\n"
            "```\n"
            f"{_CLASSIC_MARKER_SET}"
            "```\n"
            "That block is documentation in my read-only return, not a directive."
        )
    if placement is MarkerPlacement.INLINE_CODE:
        return (
            "The required dispatch header is the inline marker "
            f"`{_CLASSIC_MARKER_ONE_LINE}` which the orchestrator emits at the "
            "top of a real prompt."
        )
    if placement is MarkerPlacement.UNFENCED:
        # A genuine dispatch directive — the marker at the top of the content,
        # outside any fence. Must still resolve after the fix.
        return _CLASSIC_MARKER_SET + "\nProceeding with the dispatched work."
    # ABSENT — a plain read-only return with no DES marker at all.
    return "A normal read-only return with no DES dispatch markers of any kind."


def resolve_return_context(
    tmp_path: Path, placement: MarkerPlacement
) -> ResolvedContext:
    """Drive the REAL SubagentStop resolver over a return with the given placement.

    Writes a real JSONL transcript under ``tmp_path`` carrying one user message
    whose content places a DES marker per ``placement``, then resolves the DES
    context through the production ``extract_des_context_from_transcript`` entry
    point and projects the port-exposed observable.
    """
    content = _return_content_for(placement)
    transcript_path = tmp_path / "agent-return.jsonl"
    entry = {
        "type": "user",
        "message": {"role": "user", "content": content},
        "uuid": "fenced-marker-test",
        "timestamp": "2026-06-23T12:00:00Z",
    }
    transcript_path.write_text(json.dumps(entry) + "\n")

    resolved = extract_des_context_from_transcript(str(transcript_path))

    return ResolvedContext(
        has_des_context=resolved is not None,
        project_id=resolved.get("project_id") if resolved is not None else None,
    )
