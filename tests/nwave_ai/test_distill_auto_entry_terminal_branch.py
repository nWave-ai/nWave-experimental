"""Contract checks for the thin Auto M/L route and DISTILL terminal redirect."""

from __future__ import annotations

import re
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
    """CONTRACT_SHAPE: bounded-change. Unified M/L preserves the thin role order."""
    text = _auto_skill_text()
    route = text[text.index("## Deterministic crafter selection") :]
    expected = (
        "DeliveryContract.paradigm",
        "missing or has any other value",
        "1. `nw-acceptance-designer`",
        "dispatch crafter by paradigm",
        "4. `nw-user-examiner`",
        "Report role verdicts + Git",
    )
    positions = [route.index(token) for token in expected]
    assert positions == sorted(positions)
    assert "`functional` | `nw-functional-software-crafter`" in text
    assert "`object_oriented` | `nw-software-crafter`" in text
    assert "missing or has any other value" in text


def test_m_and_l_share_exactly_one_architecture_readiness_prefix() -> None:
    """CONTRACT_SHAPE: bounded-change. Unified M/L has one readiness prefix."""
    text = _auto_skill_text()
    assert text.count("## Architecture readiness — shared M/L prefix") == 1
    prefix = text[
        text.index("## Architecture readiness — shared M/L prefix") : text.index(
            "## M/L route — shared reuse floor"
        )
    ]
    compact_prefix = _compact(prefix)
    for token in (
        "Covered/NoImpact",
        "Unresolved",
        "Dispatch one DESIGN consult",
        "AUTO-ARCHITECTURE-CONSULT",
        "ARCHITECTURE-COVERED",
        "ARCHITECTURE-BLOCKED",
        "Missing/malformed header",
        "Any incomplete result",
    ):
        assert token in compact_prefix
    route = text[
        text.index("## M/L route — shared reuse floor") : text.index(
            "## Examiner input isolation"
        )
    ]
    for token in (
        "delivery-route",
        "applicability.examine",
        "No new carrier/controller",
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
    assert "Run exactly one stable" in _compact(atd_text)
    assert executable_form in _compact(atd_text)
    assert "`targets[]`" in atd_text or "targets[].{" in atd_text
    for nested_field in ("overlap", "decision", "justification", "boundary"):
        assert nested_field in atd_text
    assert "no top-level" in _compact(atd_text)
    assert "targets[].{overlap, decision, justification, boundary}" in _compact(
        atd_text
    )
    assert "no top-level `reuse`/`boundaries` field" in _compact(atd_text)
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
        "not a workflow runtime",
        "does not author the contract",
        "No infrastructure",
        "sequencer/controller",
        "PASS",
        "FAIL",
        "INDETERMINATE",
        "no ledger",
    ):
        assert token in text


def test_auto_preserves_direct_s_and_human_routes() -> None:
    """CONTRACT_SHAPE: bounded-change. Thin Auto leaves other routes unchanged."""
    text = _compact(_auto_skill_text())
    assert "Human mode and direct S work keep their existing routes" in text


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


def test_atd_and_crafter_specs_reference_installed_schema_locator_only() -> None:
    """CONTRACT_SHAPE: bounded-change. ATD and both OO/FP crafters use exactly
    one installed schema path and no backticked fallback.
    """
    installed_locator = (
        "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/"
        "thin-delivery-contract.schema.json"
    )
    backticked_fallback = "`nWave/schemas/thin-delivery-contract.schema.json`"
    for spec_path in (ATD_AGENT_PATH, OO_CRAFTER_PATH, FP_CRAFTER_PATH):
        text = spec_path.read_text(encoding="utf-8")
        assert text.count(installed_locator) == 1
        assert backticked_fallback not in text


def test_atd_auto_route_honors_wave_order_before_red_execution() -> None:
    """CONTRACT_SHAPE: bounded-change. ATD Auto route reads/validates the
    installed schema deterministically BEFORE any native obligation Skill
    fires, invokes only triggered generated skills, then the very next tool
    call is the sole acceptance-test `Write` -- the hard boundary -- sha256s
    its bytes, assembles/schema-validates the DeliveryContract, executes the
    expected RED, re-verifies the digest, and gates crafter dispatch on
    RedConfirmed. No product Read/Grep/Glob/Bash, git query, dependency
    probe, or legacy `nw-distill-red-scaffolding` Skill may sit between the
    bounded pre-authoring window and that `Write`.
    """
    text = ATD_AGENT_PATH.read_text(encoding="utf-8")
    auto_section = text[
        text.index("## Route contract") : text.index("## Language Convention")
    ]
    compact = _compact(auto_section)
    resolver_command = (
        "printf '%s\\n' \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/"
        'thin-delivery-contract.schema.json"'
    )
    materialization_order = [
        "Once step 5 returns",
        resolver_command,
        "then Read exactly the returned path",
        "git -C ROOT rev-parse HEAD",
        "Then derive the applicable obligation tokens",
        "last ON-TRIGGER `Skill(...)` return",
        "the next tool call is the `Write`",
        "Sha256 its bytes",
        "assemble and schema-validate the `DeliveryContract` v1.2",
        "Execute every stored command",
        "Only after complete-scope RED holds",
        "re-verify the digest",
        "Only `RedConfirmed` enables crafter dispatch here",
    ]
    positions = [compact.index(token) for token in materialization_order]
    assert positions == sorted(positions)
    for prerequisite in (
        "this is direct locator resolution",
        "never a diagnostic `env` probe",
        "never a guessed literal `$HOME/.claude` path",
        "never a host-wide `find`/`bfs` scan",
        "determine `paradigm`",
        "verification-scope.commands",
        "acceptance-test artifact FILE",
        "command-not-found, import, collection, or setup failure is BROKEN",
        "no git query, dependency probe, or `nw-distill-red-scaffolding`/other "
        "Skill call may intervene between the last triggered row and that "
        "`Write`",
    ):
        assert prerequisite in compact
    assert "find /" not in compact
    assert "bfs /" not in compact
    assert (
        compact.count(
            "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/"
            "thin-delivery-contract.schema.json"
        )
        == 1
    )
    assert "Using that already-read schema, determine" in compact


def test_worktree_ownership_is_a_deterministic_two_probe_grammar() -> None:
    """CONTRACT_SHAPE: bounded-change. Worktree ownership is a compact,
    deterministic git grammar: two cwd-local probes feeding a decision
    table with exact sibling-path, collision/failure refusal, and explicit
    forbidden constructs -- no example path, no repeated explanations."""
    text = _auto_skill_text()
    section = text[
        text.index("## Worktree ownership") : text.index("## Architecture readiness")
    ]
    compact = _compact(section)

    for token in (
        # Closed git grammar: exactly these commands, forbidden constructs.
        "git rev-parse --show-toplevel",
        "git rev-parse --abbrev-ref HEAD",
        "git worktree list --porcelain",
        "git worktree add --detach <sibling> HEAD",
        "never `git -C`/`cd`/compound shell/substitution",
        # Detached reuse is independent of dirt.
        "reuse cwd as-is, dirt or clean",
        "zero `git worktree add`, zero relocation",
        "no session heuristic",
        # Attached branch: exact deterministic sibling, no example path.
        "sibling = root + `.nwave-auto`",
        # Registered-collision and add-occupied-failure share one refusal.
        "registered, or `git worktree add --detach <sibling> HEAD` fails occupied",
        "refuse fail-closed",
        "WHAT: path registered/occupied",
        "WHY: ownership/cleanliness unprovable",
        "HOW: reconcile/remove, retry",
        "never adopt",
        # Destructive-ops refusal and WIP preservation.
        "Never branch, or delete/reset/clean/stash/force/adopt",
        "WIP stays bit-identical",
    ):
        assert token in compact

    assert "/x/repo.nwave-auto" not in compact

    # Probe-before-table ordering: both probes precede either row.
    ordered_tokens = [
        "git rev-parse --show-toplevel",
        "git rev-parse --abbrev-ref HEAD",
        "reuse cwd as-is",
        "sibling = root",
    ]
    positions = [compact.index(token) for token in ordered_tokens]
    assert positions == sorted(positions)


def test_root_propagation_binds_every_dispatch_role() -> None:
    """CONTRACT_SHAPE: bounded-change. The canonical root measured by the
    worktree-ownership probe is an immutable dispatch input propagated
    verbatim to every dispatched role; no role may rediscover it via global
    find, nearest-repo, transcript inference, or another clone."""
    text = _auto_skill_text()
    idx_worktree = text.index("## Worktree ownership")
    idx_propagation = text.index("**Root propagation:**")
    idx_architecture = text.index("## Architecture readiness — shared M/L prefix")
    assert idx_worktree < idx_propagation < idx_architecture

    block = text[idx_propagation:idx_architecture].strip()
    section = _compact(block)
    assert "immutable dispatch input" in section
    for role in ("DISCUSS", "DESIGN", "PO", "ATD", "crafter", "examiner"):
        assert role in section
    assert (
        "never rediscovered via global find, nearest-repo, transcript "
        "inference, or another clone" in section
    )

    assert text.count("**Root propagation:**") == 1
    assert len(block.split()) <= 50


def _atd_sibling_bullet(text: str) -> str:
    start = text.index("1. `nw-acceptance-designer` (every run):")
    end = text.index("2. `nw-product-owner`")
    return text[start:end]


def _atd_route_contract_paragraph() -> str:
    text = ATD_AGENT_PATH.read_text(encoding="utf-8")
    return text[text.index("## Route contract") : text.index("## Language Convention")]


def test_atd_closed_grammar_root_forbidden_projections() -> None:
    """CONTRACT_SHAPE: bounded-change. ATD carrier is exactly CLOSED ROOT/VALUE-SEED
    in both nw-auto and ATD spec; root never names paraphrase/enumeration/
    paradigm/language/runner/design fields.
    """
    text = _auto_skill_text()
    bullet = _atd_sibling_bullet(text)
    compact = _compact(bullet)

    for token in (
        "architecture authority line",
        "then one blank line",
        "ROOT/VALUE-SEED/DELIVERY-ROUTE",
        "four non-empty lines total",
        "exactly one blank line between the architecture line and ROOT",
        "no design SSOT/language/framework",
    ):
        assert token in compact
    assert "four lines only" not in compact

    # Four carrier lines total: the authority line precedes this exact
    # three-line ROOT/VALUE-SEED/DELIVERY-ROUTE grammar in the ATD spec.
    section = _atd_route_contract_paragraph()
    exact_grammar = (
        "ROOT: <absolute-root>\n"
        "VALUE-SEED: <immutable-verbatim-seed>\n"
        "DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>"
    )
    assert exact_grammar in section
    assert "No fifth field" in _compact(section)
    assert "never the design SSOT" in _compact(section)

    # Root forbidden from paraphrase, enumeration, paradigm, language, runner, design
    for token in (
        "never a root restatement, paraphrase",
        "enumerated/numbered test-case list",
        "never a root-authored paradigm/targets/storage/boundary/implementation",
        "never a root-named or root-guessed language or test runner/framework",
    ):
        assert token in _compact(section)
    assert "functional" not in bullet
    assert "object_oriented" not in bullet
    assert not re.search(r"\n\s*\d+\.\s", bullet)


def test_atd_pre_authoring_window_is_bounded_and_terminal() -> None:
    """CONTRACT_SHAPE: bounded-change. Proves the Markdown contract is internally
    closed; runtime agent compliance remains for installed K4/K6 evidence.
    """
    section = _atd_route_contract_paragraph()
    compact = _compact(section)

    # Exact query command: exactly one occurrence.
    assert compact.count("des code-fact query.* SUBJECT --root ROOT") == 1

    # Five-call sequence fragments in order.
    ordered_tokens = [
        "AT MOST five calls total",
        "1. Read the cited architecture",
        "2. At most one bounded Glob/discovery call",
        "3. Read at most one selected language manifest",
        "4. Read at most one selected executable command source",
        "may reuse step 3's Read",
        "5. Run exactly one stable",
        "des code-fact query.* SUBJECT --root ROOT",
        "target/reuse/boundary facts",
        "never for language/runner discovery",
        "Once step 5 returns",
        "no further product-source Read/Grep/Glob or ad-hoc Bash",
    ]
    positions = [compact.index(token) for token in ordered_tokens]
    assert positions == sorted(positions)

    # Terminal phrases: EVIDENCE_GAP and surrounding context separately.
    assert "terminal `EVIDENCE_GAP`" in compact
    assert "no retry, no second query, no guessing" in compact

    # Verify deleted phrases are absent.
    assert (
        "First read the cited architecture at that Covered/NoImpact locator"
        not in compact
    )
    assert "run exactly one bounded provider-neutral" not in compact
    assert "Reading the cited architecture plus that one query" not in compact


def test_po_carrier_not_constrained_by_closed_atd_grammar() -> None:
    """CONTRACT_SHAPE: PO is conditional on examine Author, independently of route."""
    text = _auto_skill_text()
    route = text[
        text.index("## M/L route — shared reuse floor") : text.index(
            "## Examiner input isolation"
        )
    ]
    assert "nw-product-owner` (only if `examine=true, Author(Namespace)`" in route
    assert "No charter/PO/Vera this run" in route
    assert "ATD always; PO only when dispatched" in route


def test_auto_m_route_requires_po_atd_same_message_and_no_invented_signup() -> None:
    """CONTRACT_SHAPE: route and examine axes dispatch roles independently."""
    text = _auto_skill_text()
    route = text[
        text.index("## M/L route — shared reuse floor") : text.index(
            "## Examiner input isolation"
        )
    ]
    compact_route = _compact(route)
    assert "run_in_background=false" in compact_route
    assert "nw-acceptance-designer` (every run)" in compact_route
    assert "nw-product-owner` (only if `examine=true" in compact_route
    assert "nw-user-examiner` (only if `examine=true`)" in compact_route
    assert "DeliveryContract` v1.2" in route
    assert "DeliveryContract` v1.1" not in text
    examiner_section = text[
        text.index("## Examiner input isolation") : text.index("## Route boundaries")
    ]
    assert "exactly two inputs" in _compact(examiner_section)
