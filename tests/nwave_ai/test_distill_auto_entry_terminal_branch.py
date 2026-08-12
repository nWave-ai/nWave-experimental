"""Contract checks for the thin Auto M/L route and DISTILL terminal redirect."""

from __future__ import annotations

from pathlib import Path

from des.cli.dispatch import _default_skill_loading_body


REPO = Path(__file__).resolve().parents[2]
AUTO_SKILL_PATH = REPO / "nWave/skills/nw-auto/SKILL.md"
DISTILL_SKILL_PATH = REPO / "nWave/skills/nw-distill/SKILL.md"
MODE_SKILL_PATH = REPO / "nWave/skills/nw-mode-select/SKILL.md"
ATD_AGENT_PATH = REPO / "nWave/agents/nw-acceptance-designer.md"
OO_CRAFTER_PATH = REPO / "nWave/agents/nw-software-crafter.md"
FP_CRAFTER_PATH = REPO / "nWave/agents/nw-functional-software-crafter.md"

DISTILL_AUTO_HEADING = "## Auto entry (root reads this FIRST — terminal branch)"
DISTILL_HUMAN_HEADING = "## Human-only ceremony (Human-on-the-loop path — Auto never reads past this heading)"


def _auto_skill_text() -> str:
    return AUTO_SKILL_PATH.read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return " ".join(text.split())


def _distill_sections() -> tuple[str, str]:
    content = DISTILL_SKILL_PATH.read_text(encoding="utf-8")
    idx_auto = content.index(DISTILL_AUTO_HEADING)
    idx_human = content.index(DISTILL_HUMAN_HEADING)
    assert idx_auto < idx_human
    return content[idx_auto:idx_human], content[idx_human:]


def test_auto_m_route_reuses_the_three_roles_then_git_evidence() -> None:
    """CONTRACT_SHAPE: bounded-change. Auto M preserves the thin role order."""
    text = _auto_skill_text()
    route = text[text.index("## Deterministic crafter") : text.index("## L route")]
    expected = (
        "DeliveryContract.paradigm",
        "missing or has any other value",
        "nw-acceptance-designer",
        "exactly one crafter",
        "nw-user-examiner",
        "Git",
    )
    positions = [route.index(token) for token in expected]
    assert positions == sorted(positions)
    assert "`functional` | `nw-functional-software-crafter`" in text
    assert "`object_oriented` | `nw-software-crafter`" in text
    assert "missing or has any other value" in text


def test_auto_l_route_bounds_serial_gap_specific_consults() -> None:
    """CONTRACT_SHAPE: bounded-change. L resolves two ordered gap classes."""
    text = _auto_skill_text()
    route = text[text.index("## L route") : text.index("## Examiner input isolation")]
    for token in (
        "If an intent gap exists, dispatch DISCUSS once",
        "If the gap remains, refuse",
        "An architecture gap triggers exactly one DESIGN consult",
        "consult bound is two total",
        "independent, and serial",
        "same acceptance-designer",
    ):
        assert token in route


def test_auto_root_delegates_the_code_fact_query_to_the_acceptance_designer() -> None:
    """CONTRACT_SHAPE: bounded-change. Root owns no CodeFact command; ATD does."""
    text = _auto_skill_text()
    assert (
        "Root does not run `des code-fact query.* SUBJECT --root ROOT` itself" in text
    )
    assert "delegates the bounded brief" in text
    assert "nw-acceptance-designer" in text
    assert "CodeFactPort" in text
    assert "graphify" not in text.lower()
    assert "tsunami" not in text.lower()

    atd_text = ATD_AGENT_PATH.read_text(encoding="utf-8")
    executable_form = "des code-fact query.* SUBJECT --root ROOT"
    assert "run\nexactly one bounded provider-neutral" in atd_text
    assert executable_form in atd_text
    assert "`targets[]`" in atd_text or "targets[].{" in atd_text
    for nested_field in ("overlap", "decision", "justification", "boundary"):
        assert nested_field in atd_text
    assert "no top-level" in _compact(atd_text)
    assert "targets[].{overlap, decision, justification, boundary}" in atd_text
    assert "there is no top-level `reuse` or `boundaries` field" in _compact(atd_text)
    dispatch_loading = _default_skill_loading_body("nw-acceptance-designer")
    assert executable_form in dispatch_loading


def test_default_skill_loading_body_uses_native_skill_invocation_not_read() -> None:
    """CONTRACT_SHAPE: non-regression. The generic reminder must send Claude at
    the native `Skill` tool -- not the old `Read the Read tool, by exact path`
    instruction -- and must not duplicate any role's actual skill list."""
    body = _default_skill_loading_body("nw-acceptance-designer")
    assert "Invoke Skill(<exact skill name>) at the role table's phase trigger" in body
    assert "with the Read tool" not in body
    assert "by exact path" not in body
    """CONTRACT_SHAPE: non-regression. OO and FP crafters keep the conformance phrase."""
    phrase = "demonstrate declared reuse/architecture conformance"
    for path in (OO_CRAFTER_PATH, FP_CRAFTER_PATH):
        assert phrase in path.read_text(encoding="utf-8")


def test_auto_examiner_receives_only_expectation_and_start_recipe() -> None:
    """CONTRACT_SHAPE: bounded-change. Examiner input remains epistemically isolated."""
    text = _auto_skill_text()
    section = _compact(
        text[
            text.index("## Examiner input isolation") : text.index(
                "## Route boundaries"
            )
        ]
    )
    assert "exactly two inputs" in section
    assert "expectation charter" in section
    assert "user-surface start recipe" in section
    for forbidden in (
        "code facts",
        "acceptance tests",
        "test command",
        "source paths",
        "source-reading fallback",
    ):
        assert forbidden in section


def test_auto_is_not_a_second_controller_or_persistent_workflow() -> None:
    """CONTRACT_SHAPE: bounded-change. Terminal outcomes do not create a controller."""
    text = _compact(_auto_skill_text())
    for token in (
        "prompt-level routing",
        "duplicate sequencer/controller",
        "PASS",
        "neither `main` nor `master`",
        "exact commit SHA",
        "Vera's failure rule",
        "preserve the current WIP exactly as-is",
        "INDETERMINATE",
        "current branch plus `git status`",
        "no ledger or seal",
    ):
        assert token in text


def test_auto_preserves_direct_s_and_human_routes() -> None:
    """CONTRACT_SHAPE: bounded-change. Thin Auto leaves other routes unchanged."""
    text = _auto_skill_text()
    assert "Direct S and Human-on-the-loop routes are unchanged" in text


def test_mode_select_classifies_then_delegates_auto_without_restatement() -> None:
    """CONTRACT_SHAPE: bounded-change. Mode selection delegates Auto authority once."""
    text = MODE_SKILL_PATH.read_text(encoding="utf-8")
    auto = _compact(text[text.index("## Auto mode") : text.index("## What this skill")])
    for token in (
        "After classification",
        "delegate explicit Auto M/L to `nw-auto`",
        "sole route authority",
        "Do not restate or execute its M/L algorithm here",
        "do not route Auto through `nw-deliver`, `nw-distill`, or a generic wave command",
    ):
        assert token in auto
    for duplicated_route_token in ("nw-acceptance-designer", "DISCUSS", "DESIGN"):
        assert duplicated_route_token not in auto
    assert "every existing nWave/DES rule" not in auto


def test_mode_select_preserves_direct_s_and_human_routes() -> None:
    """CONTRACT_SHAPE: bounded-change. Classification keeps Human and S semantics."""
    text = _compact(MODE_SKILL_PATH.read_text(encoding="utf-8"))
    assert "Direct S and Human routes are unchanged" in text
    assert "Human-on-the-loop: what" in text


def test_distill_auto_entry_is_a_short_terminal_redirect() -> None:
    """CONTRACT_SHAPE: bounded-change. DISTILL Auto remains a terminal redirect."""
    auto_section, _ = _distill_sections()
    assert "nw-auto" in auto_section
    assert "thin Auto M/L prompt router" in auto_section
    assert len(auto_section) < 700


def test_distill_routes_code_facts_through_codefact_port() -> None:
    """CONTRACT_SHAPE: bounded-change. DISTILL names only the code-fact port."""
    content = DISTILL_SKILL_PATH.read_text(encoding="utf-8")
    preamble = content[: content.index(DISTILL_AUTO_HEADING)]
    assert "nw-code-analysis-port" in preamble
    assert "CodeFactPort" in preamble
    assert "bounded `des code-fact`" in preamble
    assert "graphify" not in preamble.lower()
    assert "tsunami" not in preamble.lower()


def test_distill_human_section_retains_representative_ceremony() -> None:
    """CONTRACT_SHAPE: bounded-change.

    Non-regression: the Human-on-the-loop ceremony survives in full past the
    Human-only heading.
    """
    _, human_section = _distill_sections()
    for token in (
        "AskUserQuestion",
        "docs/feature",
        "Final Wave Review Gate",
        "des charter-scaffold",
        "## Composition (load by trigger)",
    ):
        assert token in human_section


def test_crafter_specs_reference_installed_schema_locator_only() -> None:
    """CONTRACT_SHAPE: bounded-change. Both OO/FP crafters use exactly one installed
    schema path and no backticked fallback.
    """
    installed_locator = (
        "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/"
        "thin-delivery-contract.schema.json"
    )
    backticked_fallback = "`nWave/schemas/thin-delivery-contract.schema.json`"
    for crafter_path in (OO_CRAFTER_PATH, FP_CRAFTER_PATH):
        text = crafter_path.read_text(encoding="utf-8")
        assert text.count(installed_locator) == 1
        assert backticked_fallback not in text


def test_atd_auto_route_honors_wave_order_before_red_execution() -> None:
    """CONTRACT_SHAPE: bounded-change. ATD Auto route reads/validates schema,
    determines paradigm, identifies targets and commands, digests FILE, assembles
    DeliveryContract, executes RED, re-verifies, gates crafter on RedConfirmed.
    """
    text = ATD_AGENT_PATH.read_text(encoding="utf-8")
    auto_section = text[
        text.index("## Route contract") : text.index("## Language Convention")
    ]
    compact = _compact(auto_section)
    tokens_in_order = [
        "read and validate the installed `DeliveryContract` v1.1 schema",
        "determine the selected `paradigm`",
        "verification-scope.commands",
        "exactly ONE consolidated repository-relative acceptance-test artifact FILE",
        "sha256 its bytes",
        "Assemble and schema-validate the `DeliveryContract` v1.1 instance",
        "Execute the focused acceptance test and observe the expected RED",
        "re-verify the digest",
        "Only the `RedConfirmed` proof enables crafter dispatch",
    ]
    positions = [compact.index(token) for token in tokens_in_order]
    assert positions == sorted(positions)


def test_auto_m_route_requires_po_atd_same_message_and_no_invented_signup() -> None:
    """CONTRACT_SHAPE: bounded-change. Auto M dispatches PO+ATD with both
    dispatches issued before waiting, documents repository-owned onboarding,
    and examiner input stays exactly two.
    """
    text = _auto_skill_text()
    m_section = text[text.index("## Deterministic crafter") : text.index("## L route")]
    compact_m = _compact(m_section)
    assert "SAME assistant message" not in compact_m
    assert (
        "two background Agent dispatches, issuing both before waiting on either result"
        in compact_m
    )
    assert "nw-product-owner" in compact_m
    assert "nw-acceptance-designer" in compact_m
    assert "target repository" in compact_m
    assert "own documented user-facing local onboarding/setup excerpt" in compact_m
    assert "never inventing a signup path" in compact_m
    examiner_section = text[
        text.index("## Examiner input isolation") : text.index("## Route boundaries")
    ]
    assert "exactly two inputs" in _compact(examiner_section)
