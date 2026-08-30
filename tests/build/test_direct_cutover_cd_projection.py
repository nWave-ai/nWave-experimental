"""Pins the direct-cutover Crafter -> EXAMINE projection to ADR-SSOT-002.

These tests protect observable coordination laws, not prose layout. They forbid
the retired parallel control plane and require terminal, identity-joined
evidence at the two live role boundaries.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DELIVER = ROOT / "nWave/skills/nw-deliver/SKILL.md"
DELIVER_TASK = ROOT / "nWave/tasks/nw/deliver.md"
OO = ROOT / "nWave/agents/nw-software-crafter.md"
FP = ROOT / "nWave/agents/nw-functional-software-crafter.md"
EXAMINER = ROOT / "nWave/agents/nw-user-examiner.md"
IMPLEMENTATION_REVIEWER = ROOT / "nWave/agents/nw-software-crafter-reviewer.md"
FINALIZE = ROOT / "nWave/skills/nw-finalize/SKILL.md"
PROJECTIONS = (DELIVER, DELIVER_TASK, OO, FP, EXAMINER)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", PROJECTIONS, ids=lambda path: path.stem)
@pytest.mark.parametrize(
    "retired",
    (
        "feature-delta",
        "slice plan",
        "carpaccio",
        "ledger",
        "des-exempt",
        "des-mode",
        "des-phase",
        "des-slice",
    ),
)
def test_live_cd_projection_has_no_retired_control_plane(
    path: Path, retired: str
) -> None:
    assert retired not in _text(path).casefold()


def test_deliver_uses_one_discoverable_contract_authority() -> None:
    text = _text(DELIVER)
    task = _text(DELIVER_TASK)
    compact_text = " ".join(text.split())
    compact_task = " ".join(task.split())

    assert "--repo-root <ROOT> --delivery-contract <PATH>" in text
    assert "PATH` is relative to `ROOT`" in text
    assert "one immutable, DISTILL-produced `DeliveryContract` value vertical" in text
    assert "There is no alternate carrier or textual bypass" in compact_text
    assert "exactly the two thin headers" in text
    assert "then one blank line" in text
    assert "REPO-ROOT: <absolute physical root>" in text
    assert "never a third header or carrier" in text
    assert "sole orchestration owner" in task
    assert "Root never implements or repairs the candidate" in compact_task


def test_green_to_green_binds_locator_only_until_dispatch() -> None:
    adr = _text(
        ROOT / "docs/product/architecture/ADR-SSOT-002-canonical-delivery-model.md"
    )
    g2g = adr.split("2. `GREEN_TO_GREEN`:", 1)[1].split("**Axis 2", 1)[0]

    assert "binds\n   its existing locator" in g2g
    assert "produced later" in g2g
    assert "`des dispatch`" in g2g
    assert "locator/digest" not in g2g


@pytest.mark.parametrize("path", (DELIVER, DELIVER_TASK))
def test_deliver_invokes_the_distill_validation_port_without_reimplementation(
    path: Path,
) -> None:
    text = _text(path)

    # Single dispatch invocation by root/DELIVER, never by root itself
    assert text.count("des dispatch --repo-root ROOT --delivery-contract PATH") == 1
    assert (
        text.count("des validate-delivery-contract") == 0
        if path == DELIVER_TASK
        # Delivered contract owns its consumer-boundary validation, not root
        else (text.count("des validate-delivery-contract") >= 1)
    )
    assert "contract+oracle closure digest" in text


@pytest.mark.parametrize("path", (OO, FP), ids=("oo", "fp"))
def test_crafter_requires_immutable_oracle_and_early_mutation(path: Path) -> None:
    text = _text(path)
    compact = " ".join(text.split())

    assert "THIN-DELIVERY-CONTRACT:" in text
    assert "THIN-DELIVERY-CONTRACT-DIGEST:" in text
    assert "by tool-call 15" in text
    assert "Do not author, edit, regenerate or weaken" in text
    assert "zero-diff result is never `PASS`" in text
    assert "CRAFTER-RESULT" in text
    assert "first-production-mutation-tool-call:" in text
    # Oracle is terminal identity (locator only), not a digest carrier
    assert "oracle: <locator>" in text
    assert "oracle: <locator>@sha256:<digest>" not in text
    # Canonical validator command at two consumer boundaries
    assert (
        "des validate-delivery-contract --repo-root <absolute-current-repository-root> --delivery-contract <locator>"
        in compact
    )
    assert "before BASELINE" in text or "point-of-use" in compact
    assert "before PASS" in text or "PASS/REPORT" in text
    assert "**RESOLVE LENSES**" in text
    assert '"Mandatory lens resolution"' in text
    assert "sole normative routing authority" in text
    assert "never silently skip a matched row" in text.lower()


@pytest.mark.parametrize("path", (OO, FP), ids=("oo", "fp"))
def test_first_mutation_bound_is_friction_evidence_not_a_gate(path: Path) -> None:
    """Run 5 evidence: a real 30-call investigation (bound 15) succeeded --
    the crafter was recovering file:line facts the architecture authority
    already named but the compiled contract dropped, not inventing them.
    Exceeding the bound must report friction, never abort a delivery that is
    otherwise on track; authority the contract never named at all must still
    stop immediately, at any tool-call number."""
    text = _text(path)
    compact = " ".join(text.split())

    assert "Exceeding it is friction evidence, never itself a stop condition" in compact
    assert "contract-fact-gap" in text
    assert (
        "this softening never licenses inventing a fact the contract "
        "never gave" in compact
    )
    assert (
        "Authority missing entirely (nothing the contract names) still "
        "returns `INDETERMINATE` immediately, at any tool-call number" in compact
    )
    assert "recovering the authority's own" in compact
    assert "never a research detour into facts the contract never named" in compact


@pytest.mark.parametrize("path", (OO, FP), ids=("oo", "fp"))
def test_self_flagged_oracle_gap_is_indeterminate_never_pass(path: Path) -> None:
    """Run 8: a self-flagged coverage/oracle gap must be terminal
    INDETERMINATE citing the oracle -- never a PASS with the gap merely
    noted as an FYI in `residuals`, which records a bounded observation
    AFTER a genuine PASS only."""
    compact = " ".join(_text(path).split())

    assert (
        "A self-flagged coverage/oracle gap is terminal `INDETERMINATE` "
        "citing the oracle, never `PASS` with the gap merely noted in "
        "`residuals`" in compact
    )
    assert (
        "`residuals` records a bounded observation AFTER a genuine `PASS`, "
        "it never demotes an unresolved oracle defect to an FYI" in compact
    )


@pytest.mark.parametrize("path", (OO, FP), ids=("oo", "fp"))
def test_baseline_runs_before_any_read_beyond_the_contract(path: Path) -> None:
    """K4 Run 9: crafter-1 spent 525.8s/62 tool calls before discovering the
    contract's own verification command cited a wrong test path -- it had
    read the oracle, targets and source first. BASELINE must now be the
    first Bash call after VALIDATE, with a fast INDETERMINATE exit when the
    command itself cannot even run."""
    text = _text(path)
    compact = " ".join(text.split())

    assert (
        "the first Bash call after VALIDATE, before reading any\n   file "
        "beyond the contract itself".replace("\n   ", " ")
        in compact
    )
    assert (
        "immediate terminal `INDETERMINATE` citing the contract's own "
        "`verification-scope` entry, within 3 tool calls total" in compact
    )
    assert "K4 Run 9: a wrong test path cost 525.8s/62 calls" in compact
    # BASELINE now precedes RESOLVE LENSES in step order.
    baseline_index = text.index("**BASELINE**")
    lenses_index = text.index("**RESOLVE LENSES**")
    assert baseline_index < lenses_index


def test_examiner_bounds_start_reachability_before_indeterminate() -> None:
    """Run 8: Vera lost 213.6s / 40 tool calls trying to stand up a live
    server within her own budget, the worst return in the run. She must
    stop and report INDETERMINATE well before exhausting the whole budget,
    naming the exact failing step -- never spend it on infrastructure."""
    compact = " ".join(_text(EXAMINER).split())

    assert (
        "If the surface is not reachable/responsive after the documented "
        "start block plus ≤3 more calls (8 tool calls total spent on "
        "START as the outer bound)" in compact
    )
    assert (
        "stop and return terminal `INDETERMINATE` naming the exact failing "
        "command and its observed result" in compact
    )
    assert "never spend the remaining budget standing up infrastructure" in compact
    # Run 9: never fall back to the project's own test suite as a stand-in
    # for observing the candidate.
    assert "run the project's own test suite as a stand-in for observing it" in compact


def test_examiner_walks_one_call_per_journey_with_stated_budget_arithmetic() -> None:
    """K4 Run 11: Vera got the server up, verified POST create, then the
    budget guard stopped her at 38/40 before four of five journeys were
    even attempted -- repeated/exploratory calls around the one journey she
    did drive burned the budget. WALK must be one call per journey, and the
    agent must state the arithmetic sizing its own maxTurns."""
    text = _text(EXAMINER)
    compact = " ".join(text.split())

    assert (
        "once the surface is up (step 3 done), ONE call per charter journey" in compact
    )
    assert (
        "never a preliminary GET, a diagnostic probe, a second attempt at "
        "the same journey, or any other exploratory read once the server "
        "is up" in compact
    )
    assert "K4 Run 11: repeated/exploratory calls around a single journey" in compact
    assert (
        "never a cue to retry with a different request shape or add a "
        "diagnostic call" in compact
    )
    assert (
        "**Budget arithmetic** (sizes `maxTurns` below): READ (step 1, one "
        "call) +" in compact
    )
    assert "sized for up to 8 journeys per delivery (≤8)" in compact
    assert "1 + 8 + 8 + 3 = 20 as the arithmetic floor" in compact
    # K4 run 9 (44 calls) and run 11 (killed mid-walk at 38/40) both show
    # the walk overruns the bare arithmetic floor in practice -- maxTurns
    # is twice the floor, never the bare floor itself (GDP-6).
    assert "maxTurns: 40" in text
    assert (
        "set to TWICE that floor, not the bare floor: real evidence (K4 "
        "run 9, 44 calls; run 11, killed mid-walk at 38/40)" in compact
    )
    assert (
        "a cap sized to the bare floor would recreate the exact "
        "silent-kill risk this budget exists to prevent" in compact
    )


@pytest.mark.parametrize("path", (OO, FP, EXAMINER), ids=("oo", "fp", "examiner"))
def test_guard_stop_returns_a_terminal_result(path: Path) -> None:
    """The installed budget guard turns any overrun into a clean terminal
    at N-2; the crafters and examiner must return their own literal
    `INDETERMINATE` verdict naming what is unfinished, never a silent
    kill a caller cannot distinguish from success (GDP-6)."""
    compact = " ".join(_text(path).split())

    assert (
        "If the budget guard stops you, return your terminal result as "
        "`INDETERMINATE` naming what is unfinished" in compact
    )


def test_deliver_refuses_nonterminal_crafter_completion() -> None:
    text = _text(DELIVER)
    compact = " ".join(text.split())

    assert "A stopped process, timeout, partial narration or" in text
    assert "zero-diff run is not delivery completion" in text
    assert "Root never fills in a missing implementation" in compact
    assert "`changed-targets` to be non-empty" in text
    assert "`PASS` as identity, `FAIL` as" in text
    assert "Missing, nonterminal, stale or identity-mismatched evidence" in text


def test_examine_is_source_blind_total_and_ephemeral() -> None:
    text = _text(EXAMINER)
    frontmatter = text.split("---", 2)[1]
    compact = " ".join(text.split())

    # The examiner declares Read + Bash and NO MCP tool. Deliberate, not
    # erosion: a disconnected MCP server kills the subagent spawn silently
    # (3 repro 2026-08-21, commit 5fde6a905, techdebt entry
    # subagent-spawn-dies-silently-when-declared-mcp-tool-server-is-disconnected
    # records the condition for re-adding the browser tools). Pinned exactly
    # so re-adding an MCP grant without that degrade-safe mechanism fails here.
    assert "tools: Read, Bash\n" in frontmatter
    assert "mcp__" not in frontmatter
    assert "browser tools are NOT declared here" in compact
    assert "`INDETERMINATE` browser-only observation, never a silent crash" in compact
    assert "every validated expectation charter" in text
    assert "Every charter, no filtering" in text
    assert "PASS | FAIL | INDETERMINATE" in text
    assert "Create or edit nothing" in text
    assert "Never write a session log, record a verdict, edit a charter" in text
    assert "partial narration" in text
    assert "npx playwright screenshot" in text


def test_examine_axis_is_independent_of_delivery_route() -> None:
    deliver = _text(DELIVER)
    examiner = _text(EXAMINER)

    assert "applicability.examine=true" in deliver
    assert "applicability.examine=true" in examiner
    assert "independent of implementation route" in examiner
    assert "both a\nnew behavior and a behavior-preserving transformation" in examiner


@pytest.mark.parametrize("path", (OO, FP), ids=("oo", "fp"))
def test_crafter_terminal_result_declares_execution_root_without_candidate(
    path: Path,
) -> None:
    """Crafters report their execution root; E4 alone constructs K."""
    text = _text(path)
    terminal = text[text.index("CRAFTER-RESULT") : text.index("## Constraints")]

    assert "candidate:" not in terminal
    assert "execution-root: <absolute-execution-root>" in terminal
    assert "+worktree:" not in text


def test_deliver_e4_seals_k_before_downstream_consumers() -> None:
    """The crafter returns no candidate; E4 seals and injects K/root."""
    deliver = _text(DELIVER)
    compact = " ".join(deliver.split())

    assert "CRAFTER-RESULT PASS` has no `candidate:` field" in deliver
    assert "seals or replays K" in compact
    assert "implementation-reviewer/Examiner/finalize consumer" in compact
    assert "root-injected existing `candidate` K" in compact
    assert "+worktree:" not in deliver


def test_deliver_e2_requires_an_unconditional_at_approval_before_craft() -> None:
    deliver = _text(DELIVER)
    auto = _text(ROOT / "nWave/skills/nw-auto/SKILL.md")

    assert deliver.index("**E2 AT REVIEW**") < deliver.index("**E3 DISPATCH**")
    assert "bare exact `APPROVE` or `APPROVED`" in deliver
    assert "Only bare `APPROVE` or `APPROVED`" in auto
    for text in (deliver, auto):
        assert "`APPROVED WITH CONDITIONS`" in text
        assert "NEEDS_REVISION" in text


def test_k_implementation_review_requires_a_bare_approval() -> None:
    consumers = (
        _text(ROOT / "nWave/skills/nw-auto/SKILL.md"),
        _text(DELIVER),
        _text(DELIVER_TASK),
        _text(IMPLEMENTATION_REVIEWER),
    )

    for consumer in (" ".join(text.split()) for text in consumers):
        assert "bare `APPROVE` or `APPROVED`" in consumer
        assert "`APPROVED WITH CONDITIONS`" in consumer


def test_implementation_review_producer_declares_both_approval_verdicts() -> None:
    reviewer = _text(IMPLEMENTATION_REVIEWER)

    assert "verdict: APPROVE | APPROVED | NEEDS_REVISION | INDETERMINATE" in reviewer


def test_at_review_producer_declares_both_approval_verdicts() -> None:
    reviewer = _text(ROOT / "nWave/agents/nw-acceptance-designer-reviewer.md")

    assert "AT-REVIEW" in reviewer
    assert "verdict: APPROVE | APPROVED | NEEDS_REVISION | INDETERMINATE" in reviewer
    for field in ("contract:", "oracle:", "findings:"):
        assert field in reviewer
    # Oracle is terminal identity (locator only): closure-v2 already binds its
    # bytes into the contract digest, so a separate raw oracle SHA is redundant.
    assert "oracle: <locator>" in reviewer
    assert "oracle: <locator>@sha256:<digest>" not in reviewer


def test_examiner_receives_execution_root_only_as_internal_input() -> None:
    """Examiner gets root internally but emits only the candidate grammar."""
    examiner = _text(EXAMINER)
    compact = " ".join(examiner.split())
    examiner_lower = examiner.lower()

    terminal = examiner[
        examiner.index("EXAMINE-RESULT") : examiner.index("Echo `candidate`")
    ]

    # Examiner processes both fields as inputs, but root is not public grammar.
    assert "candidate" in examiner_lower
    assert "execution-root" in examiner_lower or "execution root" in examiner_lower
    assert "execution-root:" not in terminal
    # Source-blind: echoes candidate unchanged, never parses or reconstructs it.
    unchanged = "unchanged" in compact
    echo = "echo" in compact
    opaque = "opaque" in compact
    assert "candidate" in examiner_lower and (unchanged or echo or opaque)
    # No internal schema or artifact persistence for these fields
    assert "+worktree:" not in examiner and "persisted" not in examiner_lower


def test_k_is_forwarded_without_base_or_root_reinterpretation() -> None:
    """Every E4 consumer treats root-injected candidate as admitted K."""
    oo, fp = _text(OO), _text(FP)
    deliver, examiner = _text(DELIVER), _text(EXAMINER)
    reviewer, finalize = _text(IMPLEMENTATION_REVIEWER), _text(FINALIZE)

    for crafter in (oo, fp):
        terminal = crafter[
            crafter.index("CRAFTER-RESULT") : crafter.index("## Constraints")
        ]
        assert "candidate:" not in terminal
        assert "execution-root: <absolute-execution-root>" in terminal
        assert "+worktree:" not in crafter
    assert "seals or replays K" in deliver
    assert "root-injected existing `candidate` K" in " ".join(deliver.split())
    assert "candidate is admitted `K`, never base `B`" in examiner
    assert "root's HEAD to be exactly K" in " ".join(reviewer.split())
    reviewer_terminal = reviewer[
        reviewer.index("IMPLEMENTATION-REVIEW") : reviewer.index(
            "Route only this existing grammar"
        )
    ]
    assert "execution-root" in reviewer
    assert "execution-root:" not in reviewer_terminal
    assert "require root HEAD=K" in finalize
