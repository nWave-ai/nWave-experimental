"""FR-5 regression: `_resolve_wave_only_context` false-positives on a DOCUMENTED
DES-WAVE marker, producing a false ``WAVE_GATEOUT_INDETERMINATE``.

RCA (confirmed by reading source — see
``src/des/adapters/drivers/hooks/subagent_stop_handler.py:456-513``):

  * Line ~468 (``if "DES-WAVE" not in content:``) scans the RAW, unstripped
    content of EVERY message in the returning agent's own transcript — not just
    messages where THIS agent is dispatching another via an Agent/Task tool
    call. A skill (e.g. ``nw-distill``'s SKILL.md) that shows the marker syntax
    as copy-paste GUIDANCE for a FUTURE sub-dispatch — prose, not a directive —
    gets injected into the agent's context and is indistinguishable, at HEAD,
    from a real dispatch declaration.
  * The scan also skips ``_strip_fenced_regions`` (the C8 guard the sibling
    ``extract_des_context_from_transcript`` already applies at line ~169)
    before the marker match.
  * The matched doc-marker then parses to an in-vocabulary ``declared_wave``
    (e.g. "distill") with no accompanying ``DES-PROJECT-ID`` → lines ~492-495
    build the "missing project identity" reason → the caller returns
    ``_WaveOnlyUnresolved`` → the hook emits ``WAVE_GATEOUT_INDETERMINATE`` for
    an agent that never dispatched anything.

THE FIX (implemented by the crafter, NOT this test):
  (1) scope the marker match to messages where THIS agent is dispatching
      ANOTHER (a real Agent/Task tool_use block's ``prompt`` field), not any
      message content containing the substring;
  (2) apply ``_strip_fenced_regions`` before the ``"DES-WAVE" in content``
      check, for parity with ``extract_des_context_from_transcript``.

CONTRACT_SHAPE: bounded-change
Universe: the ``_resolve_wave_only_context`` return value (``None`` |
``_WaveOnlyResolvedContext`` | ``_WaveOnlyUnresolved``).

Fixture-shape note (empirically probed, not assumed): `_resolve_wave_only_context`
extracts message text via `_normalize_message_content`, which — at HEAD and
after the planned fix's fence-stripping addition — only reads a message's plain
string content or its `"text"`-typed content blocks; it never inspects a
`tool_use` block's `input` dict. A marker placed *only* inside a `tool_use`
block's `prompt` field is therefore invisible to this resolver today (probed:
resolves to `None`, not `_WaveOnlyUnresolved`) — using that shape for the
"genuine dispatch" fixture below would make assertion (b) FAIL at HEAD, which
contradicts the "GREEN both before and after" requirement. The genuine-dispatch
fixture instead mirrors the EXISTING acceptance-level regression lock for this
exact resolver (`tests/des/acceptance/wave_gateout_enforced_under_orchestration/
acceptance/steps/composition_wave_boundary.py::_write_transcript`,
`MarkerShape.NO_PROJECT_ID` arm): a plain-string assistant-message content whose
ENTIRE body IS the marker declaration (no surrounding prose) — the shape the
crafter's fix must not regress, since that acceptance suite already asserts
`WaveClosure.REFUSED` for it.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.drivers.hooks.subagent_stop_handler import (
    _resolve_wave_only_context,
    _WaveOnlyUnresolved,
)


def _write_transcript(tmp_path: Path, lines: list[dict]) -> str:
    transcript_path = tmp_path / "agent.jsonl"
    transcript_path.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )
    return str(transcript_path)


# ---------------------------------------------------------------------------
# (a) THE BUG — a documented marker, quoted as prose/guidance, with NO real
#     Agent/Task dispatch anywhere in the transcript, must NOT be treated as a
#     wave-only self-declaration.
# ---------------------------------------------------------------------------


def test_documented_des_wave_marker_is_not_a_dispatch_directive(tmp_path: Path) -> None:
    """A DES-WAVE marker quoted as SKILL.md copy-paste guidance is documentation.

    The returning agent never dispatched anything (no Agent/Task tool_use block
    anywhere in its transcript) — the marker is a doc-injected illustrative
    example, exactly as ``nw-distill``'s SKILL.md instructs authors to show:
    "Include the ``<!-- DES-WAVE: distill -->`` marker line above verbatim in
    EACH active step's Agent dispatch prompt". `_resolve_wave_only_context`
    must resolve ``None`` (a genuine non-DES return → the existing byte-stable
    passthrough-allow), not treat the quoted marker as this agent's own
    wave-only self-declaration.
    """
    injected_skill_text = (
        "Consult `DESConfig.resolve_review_steps()` ... For each active step, "
        "dispatch its agent on the resolved model:\n\n"
        "   <!-- DES-WAVE: distill -->\n\n"
        "Include the `<!-- DES-WAVE: distill -->` marker line above verbatim in "
        "EACH active step's Agent dispatch prompt -- it declares the wave so the "
        "PreToolUse hook can arm enforcement even on runtimes whose "
        "prompt-submission anchor never fired (INFERRED fallback; the marker "
        "can only ADD gating, never remove it)."
    )
    transcript = _write_transcript(
        tmp_path,
        [
            {"message": {"role": "user", "content": injected_skill_text}},
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "Understood — I have not dispatched any sub-agent yet; "
                        "just reading the skill guidance."
                    ),
                }
            },
        ],
    )

    result = _resolve_wave_only_context(
        transcript, str(tmp_path), "nw-acceptance-designer"
    )

    assert result is None, (
        "a DES-WAVE marker that appears ONLY as documentation/prose in a "
        "non-dispatch message (no Agent/Task tool_use block anywhere carries "
        "it) must NOT be treated as a wave-only self-declaration -- expected "
        f"None (genuine non-DES passthrough-allow), got {result!r}. At HEAD, "
        "_resolve_wave_only_context (subagent_stop_handler.py ~463-478) scans "
        "the RAW content of every message in the transcript for the substring "
        "'DES-WAVE' with no dispatch-scoping and no fence-stripping, so the "
        "quoted marker is matched and -- having no accompanying "
        "DES-PROJECT-ID -- resolves to _WaveOnlyUnresolved('missing project "
        "identity'), which the caller surfaces as a false-positive "
        "WAVE_GATEOUT_INDETERMINATE for an agent that never dispatched "
        "anything (FR-5)."
    )


# ---------------------------------------------------------------------------
# (b) PRESERVE THE GENUINE CASE — a real wave-only dispatch declaration with a
#     governed wave but no project id must still degrade LOUD to
#     _WaveOnlyUnresolved. Regression-lock: the fix must not throw the baby
#     out with the bathwater.
# ---------------------------------------------------------------------------


def test_real_wave_dispatch_missing_project_id_stays_unresolved(tmp_path: Path) -> None:
    """A genuine governed-wave declaration with no DES-PROJECT-ID stays INDETERMINATE.

    Mirrors the shape the existing acceptance-level regression lock already
    pins for this exact resolver (`composition_wave_boundary.py`,
    `MarkerShape.NO_PROJECT_ID`): the ENTIRE assistant-message content IS the
    dispatch's marker declaration -- a governed ``DES-WAVE`` with no
    ``DES-PROJECT-ID`` alongside it. This must keep resolving to
    ``_WaveOnlyUnresolved`` (degrade-LOUD, never silent-allow) both before and
    after the FR-5 fix -- proving the fix's dispatch-scoping does not
    over-correct and start treating a genuine wave-only declaration as mere
    documentation.
    """
    dispatch_declaration = (
        "<!-- DES-VALIDATION : required -->\n<!-- DES-WAVE : design -->\n"
    )
    transcript = _write_transcript(
        tmp_path,
        [{"message": {"role": "assistant", "content": dispatch_declaration}}],
    )

    result = _resolve_wave_only_context(
        transcript, str(tmp_path), "nw-solution-architect"
    )

    assert isinstance(result, _WaveOnlyUnresolved), (
        "a real wave-only declaration (governed DES-WAVE, no DES-PROJECT-ID) "
        f"must resolve to _WaveOnlyUnresolved -- got {result!r}."
    )
    assert result.declared_wave == "design", (
        f"expected the governed wave 'design' to be captured, got {result.declared_wave!r}"
    )
    assert "missing project identity" in result.reason, (
        f"expected the missing-project-identity reason, got {result.reason!r}"
    )
