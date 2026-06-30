"""slice-01 — SubagentStop ignores DES markers documented inside code fences.

Feature: fix-subagent-stop-fenced-marker-false-block (epic member C8).

The SubagentStop return-resolver (`extract_des_context_from_transcript` in
`src/des/adapters/drivers/hooks/subagent_stop_handler.py`, the function that
calls `DesMarkerParser().parse(content)` at line 148) resolves the DES dispatch
context by parsing markers over the WHOLE return content with no exclusion of
fenced / inline-code regions. So a read-only return that merely DOCUMENTS a DES
marker inside a ``` fence (or an inline `backtick` span) is mistaken for a real
directive → the wrong context is resolved → the return is false-blocked, jamming
the run. The fix strips fenced / inline-code regions before the marker parse.

Driving surface (Mandate-13, Layer-3 composition): the REAL resolver is driven
over a REAL JSONL transcript under `tmp_path` (real resolver + real parser +
real file I/O → `@real-io`). No direct DesMarkerParser import in step
composition; no personal-hook home-directory path is touched.

Active-RED classification (atdd_pure — NOT @skip):
  * AC-1 fenced-marker-ignored      — ACTIVE-RED at HEAD: the resolver matches
    the fenced marker → a context IS resolved (it should be None). Verified at
    HEAD: `{'project_id': 'doc-quoted-feature', ...}`.
  * AC-2 inline-code-marker-ignored — ACTIVE-RED at HEAD: same for an inline
    `backtick` span.
  * AC-3 real-marker-preserved      — live-green: a real unfenced marker already
    resolves today and must keep resolving (unbounded-preservation).
  * AC-4 no-marker-unchanged        — live-green: no marker already resolves to
    no-context (unbounded-preservation).

GREEN requires the single seam: `_strip_fenced_regions(text)` in
subagent_stop_handler applied before `DesMarkerParser().parse(content)` at line
148. The composition fails AC-1/AC-2 for the RIGHT reason (the fenced marker IS
matched at HEAD), not on a fixture error.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from .steps.composition import resolve_return_context
from .steps.domain_types import MarkerPlacement, ResolvedContext


scenarios("slice-01-subagent-stop-fenced-marker.feature")


# ---------------------------------------------------------------------------
# Given — typed precondition: where the DES marker sits in the return content
# ---------------------------------------------------------------------------


@given(
    "a read-only agent return that documents a DES marker inside a fenced block",
    target_fixture="placement",
)
def given_fenced_block() -> MarkerPlacement:
    return MarkerPlacement.FENCED_BLOCK


@given(
    "a read-only agent return that quotes a DES marker in an inline code span",
    target_fixture="placement",
)
def given_inline_code() -> MarkerPlacement:
    return MarkerPlacement.INLINE_CODE


@given(
    "a read-only agent return carrying a real DES marker outside any fence",
    target_fixture="placement",
)
def given_unfenced() -> MarkerPlacement:
    return MarkerPlacement.UNFENCED


@given(
    "a read-only agent return that carries no DES marker at all",
    target_fixture="placement",
)
def given_absent() -> MarkerPlacement:
    return MarkerPlacement.ABSENT


# ---------------------------------------------------------------------------
# When — drive the REAL SubagentStop resolver over the return
# ---------------------------------------------------------------------------


@when(
    "the SubagentStop resolver resolves the DES context from the return",
    target_fixture="resolved",
)
def when_resolve(tmp_path, placement: MarkerPlacement) -> ResolvedContext:
    return resolve_return_context(tmp_path, placement)


# ---------------------------------------------------------------------------
# Then — assert on the port-exposed observable (resolved DES context)
# ---------------------------------------------------------------------------


@then("no DES dispatch context is resolved from the documented marker")
def then_no_context(resolved: ResolvedContext) -> None:
    assert resolved.has_des_context is False, (
        "a DES marker that lives only inside a code fence / inline-code span is "
        "documentation, not a directive — the SubagentStop resolver must strip "
        "fenced regions before parsing and resolve NO DES context; instead a "
        f"context was resolved (project_id={resolved.project_id!r}). At HEAD the "
        "marker parse runs over the un-stripped content, so the fenced marker is "
        "matched (active-RED)."
    )
    assert resolved.project_id is None, (
        "no project_id must leak from a fenced / absent marker; got "
        f"{resolved.project_id!r}"
    )


@then(parsers.parse("the DES dispatch context is resolved from the real marker"))
def then_context_resolved(resolved: ResolvedContext) -> None:
    assert resolved.has_des_context is True, (
        "a REAL DES marker OUTSIDE any fence is a genuine dispatch directive — "
        "the fence-strip removes ONLY fenced / inline-code spans, so an unfenced "
        "marker stays in the residual and must still resolve a DES context "
        "(preservation); got no context."
    )
    assert resolved.project_id == "doc-quoted-feature", (
        "the unfenced real marker must resolve its project_id unchanged; got "
        f"{resolved.project_id!r}"
    )
