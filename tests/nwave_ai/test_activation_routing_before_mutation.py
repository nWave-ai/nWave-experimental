"""Activation routing before mutation — M-path clauses 2/3 closure.

Closes two gaps left open by
`docs/analysis/2026-08-08-haiku-activation-guidance-review.md`:

- Clause 2 (S/M/L classification): the generated project CLAUDE.md section
  never named `nw-mode-select`, so a neutral M-sized request had no
  earliest-path reason to invoke it before the model reached for a wave/skill
  by ad-hoc description matching (observed: `Skill(nw-bugfix)` invoked
  directly, `nw-mode-select` never invoked, no formal S/M/L statement).
  `nw-mode-select`'s own M row also blocked on an interactive human/auto
  question with no escape for a single-shot/unattended session, so an
  unattended M-sized probe could never complete without a human reply ever
  arriving.
- Clause 3 (select the intended path): the section never named `nw-new`, the
  existing wizard that recommends a starting wave for undetermined-shape new
  work, so a neutral "build X" request had nothing pointing away from
  guessing directly at `/nw-deliver` (which the section's own prose singles
  out, skipping the wave that would otherwise decide DISCUSS vs DISTILL).

These are content assertions on the two existing SSOT prose files (the
project CLAUDE.md template + nw-mode-select's own skill body) plus the
SubagentStart reminder's D3-class hardcoded path (the "surviving hardcoded
SubagentStart path" flagged and quarantined by both prior reports) — no new
mechanism, hook, file, or parallel router is introduced.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.drivers.hooks.subagent_start_handler import _build_reminder_message
from scripts.install.project_claude_section import load_section_content


REPO = Path(__file__).resolve().parents[2]
MODE_SELECT_SKILL_PATH = REPO / "nWave/skills/nw-mode-select/SKILL.md"
AUTO_SKILL_PATH = REPO / "nWave/skills/nw-auto/SKILL.md"


def _mode_select_text() -> str:
    return MODE_SELECT_SKILL_PATH.read_text(encoding="utf-8")


# --- CLAUDE.md routes through nw-mode-select before any wave/skill dispatch


def test_claude_md_section_names_mode_select_before_dispatch() -> None:
    content = load_section_content()
    assert "nw-mode-select" in content, (
        "the generated CLAUDE.md section must name nw-mode-select so the "
        "earliest read (session start, before any hook fires) routes a "
        "neutral request through S/M/L classification"
    )


def test_claude_md_section_orders_mode_select_before_the_wave_list() -> None:
    content = load_section_content()
    mode_select_idx = content.index("nw-mode-select")
    wave_list_idx = content.index("/nw-discover")
    assert mode_select_idx < wave_list_idx, (
        "nw-mode-select must be introduced before the wave command list -- "
        "otherwise a model reading top-to-bottom reaches for a wave command "
        "before it has classified size/mode"
    )


def test_claude_md_section_names_nw_new_for_undetermined_shape_work() -> None:
    content = load_section_content()
    assert "nw-new" in content, (
        "undetermined-shape new work (no prior wave artifacts) needs a named "
        "entry point -- nw-new already recommends the correct starting wave; "
        "without naming it here a neutral 'build X' request has nothing "
        "pointing away from guessing directly at /nw-deliver"
    )


def test_claude_md_section_still_names_mandatory_distill_deliver_floor() -> None:
    """Non-regression: the pre-existing mandatory-floor sentence must survive
    the edit -- this slice adds a router, it does not weaken the floor."""
    content = load_section_content()
    assert "DISTILL" in content and "DELIVER" in content
    assert "Mandatory floor" in content


def test_claude_md_section_ties_routing_to_any_tool_call() -> None:
    """Outcome property 1: routing must precede ANY tool call, including
    read-only discovery -- not just the first mutating one, and not just
    precede the wave list in reading order. The instruction has to name the
    broadened trigger and require a stated route (posture, size, reason,
    path) at that trigger, not rely on top-to-bottom reading order alone."""
    content = load_section_content()
    assert "mutating tool call" not in content
    assert "any tool call" in content
    idx = content.index("any tool call")
    nearby = content[max(0, idx - 60) : idx + 250]
    assert "including read-only discovery" in nearby
    assert "establish and state your route" in nearby
    assert "size (S/M/L)" in nearby


def test_claude_md_section_routes_every_size_through_mode_select_before_dispatch() -> (
    None
):
    """Independent-review correction: S no longer skips nw-mode-select -- it
    invokes the skill once, same as M/L/undetermined, and only exits direct
    afterward (no wave, no re-ask, no nw-auto). Ordering: the S clause's own
    invocation is stated before the 'Everything else' M/L clause, and the
    stale 'without invoking' carve-out is gone from the section entirely."""
    content = load_section_content()
    assert "without invoking" not in content
    s_idx = content.index("self-contained S")
    everything_else_idx = content.index("Everything else")
    assert s_idx < everything_else_idx
    s_clause = content[s_idx:everything_else_idx]
    assert "nw-mode-select" in s_clause
    assert "exits direct" in s_clause
    assert "no `nw-auto`" in s_clause


def test_claude_md_section_routes_m_l_and_undetermined_through_mode_select() -> None:
    """M, L, and undetermined-size work still invoke nw-mode-select (only S is
    exempt) -- this is routing guidance only, it does not weaken M/L quality
    semantics."""
    content = load_section_content()
    idx = content.index("Everything else")
    nearby = content[idx : idx + 200]
    assert "M, L, or undetermined size" in nearby
    assert "nw-mode-select" in nearby


def test_claude_md_section_explicit_mode_still_requires_sizing() -> None:
    """An explicit mode removes the re-ask but never removes size
    classification (S/M/L)."""
    content = load_section_content()
    assert "still gets sized S/M/L" in content


def test_claude_md_section_does_not_require_manual_feedback_logging() -> None:
    """Outcome property 4: no manual feedback-log tax on the hot path --
    the shipped `.nwave/beta-feedback.md` per-wave logging instruction must
    be gone from the generated section entirely."""
    content = load_section_content()
    assert ".nwave/beta-feedback.md" not in content
    assert "log your observations" not in content.lower()


def test_claude_md_section_never_hand_roll_claim_names_the_role_floor() -> None:
    """Pre-fix regression (docs/analysis/2026-08-08-neutral-enterprise-
    activation-probe.md): the root read 'Use /nw-deliver in full, including
    its feature-end cycle' as an unconditional monolithic-pipeline claim and
    hand-rolled the work under budget pressure instead of routing through
    DISTILL->DELIVER, saying: 'rather than spawning the full multi-agent
    DISTILL-to-DELIVER pipeline.' The floor must be named as a small, fixed
    set of roles right where 'never hand-roll' is read, so the claim cannot
    be misread as 'many agents.' A later installed probe exposed the remaining
    ambiguity: the root said it would author the thin contract and ATs itself.
    The acceptance-designer ownership and no-substitution boundary therefore
    belong to the same regression contract."""
    content = load_section_content()
    idx = content.index("Never hand-roll feature work")
    nearby = content[idx : idx + 700]
    assert "nw-acceptance-designer" in nearby
    assert "never substitute" in nearby
    assert "independent examiner" in nearby
    assert "crafter" in nearby


def test_claude_md_section_no_longer_makes_an_unqualified_in_full_claim() -> None:
    """The ambiguous, unconditional 'Use /nw-deliver in full' phrasing --
    which the probe's root paraphrased into 'the full multi-agent pipeline'
    -- must be gone, not just qualified nearby."""
    content = load_section_content()
    assert "in full" not in content


def test_claude_md_section_scopes_feature_end_cycle_to_once_per_feature() -> None:
    """The feature-end cycle must read as bounded -- once per feature, not a
    second per-slice multi-agent round."""
    content = load_section_content()
    idx = content.index("feature-end cycle")
    nearby = content[idx : idx + 200]
    assert "once" in nearby


# --- nw-mode-select has NO unattended/headless fallback: silence never
# --- manufactures authorization, on M or L.


def test_mode_select_has_no_unattended_headless_fallback() -> None:
    """Independent-review correction: silence or the absence of a reply
    channel must never manufacture authorization. The prior M-only
    unattended/headless fallback (default to auto when no reply can arrive)
    is deleted outright, not narrowed."""
    text = _mode_select_text()
    assert "Unattended fallback" not in text
    assert "no reply can arrive" not in text


def test_mode_select_silence_never_manufactures_authorization_on_m_or_l() -> None:
    text = _mode_select_text()
    assert "never manufactures authorization" in text
    idx = text.index("never manufactures authorization")
    nearby = text[max(0, idx - 80) : idx + 200]
    assert "M or L" in nearby


def test_mode_select_explicit_phrase_remains_valid_auto_authorization() -> None:
    """Non-regression: deleting the unattended fallback must not touch the
    still-valid explicit-phrase authorization from Step 1 (e.g. "work
    autonomously")."""
    text = _mode_select_text()
    assert "work autonomously" in text.lower()


def test_mode_select_generic_autonomous_authorization_counts_as_auto() -> None:
    """Outcome property 2: a generic authorization to act autonomously (e.g.
    "work autonomously, make reasonable choices") must count as explicit
    `auto` -- an M-classified request must not ask a second time when this
    phrasing was already used, even though it never contains the literal
    word "auto"."""
    text = _mode_select_text().lower()
    assert "work autonomously" in text
    assert (
        "auto"
        in text[text.index("work autonomously") : text.index("work autonomously") + 400]
    )


def test_mode_select_l_row_default_to_human_is_unchanged() -> None:
    """Non-regression: the unattended fallback is scoped to M -- L must keep
    defaulting to human-on-the-loop, never silently promoted to auto."""
    text = _mode_select_text()
    assert 'Never infer "auto" for an L-classified request from silence' in text


def test_mode_select_auto_mode_delegates_without_repeating_the_route() -> None:
    """CONTRACT_SHAPE: bounded-change. Auto classification has one route owner."""
    text = _mode_select_text()
    auto = " ".join(
        text[text.index("## Auto mode") : text.index("## What this skill")].split()
    )
    assert "delegate explicit Auto M/L to `nw-auto`" in auto
    assert "sole route authority" in auto
    assert "Do not restate or execute its M/L algorithm here" in auto
    assert "DISCUSS" not in auto and "DESIGN" not in auto
    assert "every existing nWave/DES rule" not in auto


# --- SubagentStart D3-class fix: no hardcoded path on the exercised route --


def test_subagent_start_reminder_does_not_hardcode_a_home_relative_skill_path() -> None:
    """D3-class (k3a-root-activation-evidence-report.md Section 4.4), named
    as a related-but-quarantined finding by the closure report and confirmed
    by the Haiku independent review: SubagentStart fires on every real
    M-path agent dispatch (nw-acceptance-designer, the paradigm crafter,
    nw-user-examiner, ...), so this reminder IS on the exercised route and
    must resolve skills by NAME, not by a literal ~/.claude-relative path
    that need not exist under an isolated CLAUDE_CONFIG_DIR."""
    msg = _build_reminder_message("nw-software-crafter")
    assert "~/.claude" not in msg, (
        "reminder must not hardcode a ~/.claude-relative path -- it fails "
        "under an isolated CLAUDE_CONFIG_DIR install, exactly like the D3 "
        "defect fixed on the root_activation_context.py path"
    )


def test_subagent_start_reminder_names_the_skill_tool_as_the_resolution_mechanism() -> (
    None
):
    msg = _build_reminder_message("nw-software-crafter")
    assert "Skill tool" in msg


def test_subagent_start_reminder_still_names_flat_topical_skill_examples() -> None:
    """Non-regression: dropping the hardcoded path must not also drop the
    concrete example skill names that make the reminder actionable."""
    msg = _build_reminder_message("nw-software-crafter")
    assert "nw-tdd-methodology" in msg


# --- Routing SSOT correction: Auto M/L enters nw-distill directly, never
# --- nw-deliver first or in parallel; an explicit mode still invokes the
# --- nw-mode-select skill itself, not only the sizing.


def test_mode_select_explicit_mode_still_invokes_the_skill_not_only_sizing() -> None:
    text = _mode_select_text()
    assert "still invokes this skill once, every size included" in text
    idx = text.index("still invokes this skill")
    nearby = text[idx : idx + 300]
    assert "removes only the re-ask question" in nearby
    assert "never removes the one required `nw-mode-select` invocation" in nearby
    assert "S included" in nearby


def test_mode_select_auto_m_l_enters_nw_auto_directly_not_deliver() -> None:
    text = " ".join(_mode_select_text().split())
    assert "delegate explicit Auto M/L to `nw-auto`" in text
    idx = text.index("delegate explicit Auto M/L to `nw-auto`")
    nearby = " ".join(text[idx : idx + 350].split())
    assert "sole route authority" in nearby
    assert "Do not restate or execute its M/L algorithm here" in nearby
    assert "do not route Auto through `nw-deliver`, `nw-distill`" in nearby


def test_nw_auto_owns_thin_routing_and_bounded_code_fact_lookup() -> None:
    """CONTRACT_SHAPE: bounded-change. Thin Auto owns executable code-fact lookup."""
    mode_text = _mode_select_text()
    auto_text = " ".join(AUTO_SKILL_PATH.read_text(encoding="utf-8").split())
    assert "`nw-auto`; that skill is the sole route authority" in mode_text
    assert "des code-fact query.* SUBJECT --root ROOT" in auto_text


def test_claude_md_section_auto_m_l_uses_nw_auto_not_deliver() -> None:
    content = load_section_content()
    assert "For Auto mode on M/L work, load the `nw-auto` skill directly" in content
    idx = content.index("load the `nw-auto` skill directly")
    nearby = content[idx : idx + 150]
    assert "never `/nw-deliver` first" in nearby
    assert "never in parallel with it" in nearby


def test_claude_md_section_scopes_feature_end_cycle_to_human_only() -> None:
    """Feature-end wording must be scoped to Human mode -- Auto's floor ends
    with the terminal Auto branch's own examiner verdict, not a second
    feature-end cycle."""
    content = load_section_content()
    idx = content.index("For Human mode")
    nearby = content[idx : idx + 250]
    assert "feature-end cycle runs once per feature" in nearby
    assert "Auto mode has no separate feature-end cycle" in content
