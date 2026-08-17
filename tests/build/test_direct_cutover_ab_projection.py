"""Direct-cutover projection laws for DeliveryContract -> DISTILL/ATD."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "nWave/agents/nw-acceptance-designer.md"
SKILL = ROOT / "nWave/skills/nw-distill/SKILL.md"
TASK = ROOT / "nWave/tasks/nw/distill.md"
ARCHITECT = ROOT / "nWave/agents/nw-solution-architect.md"
AUTO_SKILL = ROOT / "nWave/skills/nw-auto/SKILL.md"
ADR = ROOT / "docs/product/architecture/ADR-SSOT-002-canonical-delivery-model.md"
CHARTER_SKILL = ROOT / "nWave/skills/nw-expectation-charter/SKILL.md"
CHARTER_TEMPLATE = ROOT / "nWave/templates/expectation-charter.md"
PRODUCT_OWNER = ROOT / "nWave/agents/nw-product-owner.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ab_projection_has_no_retired_carrier_or_separate_human_workflow() -> None:
    projected = "\n".join(_text(path) for path in (AGENT, SKILL, TASK)).casefold()

    for retired in (
        "feature-delta",
        "feature_delta",
        "human-only",
        "**human route:**",
        "slice plan",
        "carpaccio",
        "completion ledger",
    ):
        assert retired not in projected


def test_ab_projection_preserves_route_and_examine_independence() -> None:
    agent = _text(AGENT)
    skill = _text(SKILL)

    for route in ("RED_TO_GREEN", "GREEN_TO_GREEN"):
        assert route in agent
        assert route in skill
    assert "applicability.examine" in agent
    assert "independent orchestration decision" in agent
    assert "never reads or writes it" in skill


def test_ab_projection_pins_oracle_immutability_and_terminal_handoff() -> None:
    agent = _text(AGENT)
    compact = " ".join(agent.split())

    assert "Write exactly one consolidated executable oracle" in agent
    assert "Do not search for, create, edit or broaden it" in compact
    assert "DISTILL-RESULT: CONTRACT_READY" in agent
    assert "REPO-ROOT: <absolute physical repository root>" in agent
    assert "DELIVERY-CONTRACT: <repo-relative locator>" in agent
    assert "An interrupted, timed-out or nonterminal turn is `INDETERMINATE`" in compact


def test_ab_projection_gives_envelope_validation_ownership_to_producer_and_hook() -> (
    None
):
    agent = _text(AGENT)
    compact = " ".join(agent.split())

    assert (
        "des prepare-ordinary-request` and the installed `PreToolUse` dispatch hook "
        "already validate this envelope before this role ever runs" in compact
    )
    assert "exact key set" in compact
    assert "nonempty lexical shape of every line" in compact
    assert "`BASE-REVISION` SHA length" in compact
    assert "the `DELIVERY-ID`/locator relation" in compact
    assert "producer- and\nhook-owned facts, never this role's to establish" in agent
    assert (
        "Reaching this role at all\nis proof the hook already admitted the envelope"
        in agent
    )
    assert (
        "must never recount characters,\nregex-check, normalize, hash or otherwise rederive"
        in agent
    )
    assert (
        "a correctly-shaped line is never `EVIDENCE_GAP`\non this role's own relexing"
        in agent
    )

    assert (
        "required and non-empty; a missing or malformed line is `EVIDENCE_GAP` before\nany read"
        not in agent
    )
    assert "this role validates" not in compact.casefold()
    assert "this role checks the sha length" not in compact.casefold()
    assert "this role recomputes" not in compact.casefold()
    assert compact.casefold().count("must never recount characters") == 1


def test_ab_projection_seals_dependency_readiness_before_atd() -> None:
    agent = _text(AGENT)
    compact = " ".join(agent.split())
    architect_compact = " ".join(_text(ARCHITECT).split())
    auto = _text(AUTO_SKILL)

    assert "for each dependency" in compact and "declared=yes, present=yes" in agent
    assert "resolving those facts is DESIGN's ownership" in agent
    assert (
        "every dependency is already declared and present by authority, so this role performs no dependency mutation"
        in compact
    )
    assert (
        "Any dependency recorded as undeclared or absent returns `EVIDENCE_GAP` immediately"
        in compact
    )
    assert "Multiple plausible verification vectors" in compact
    assert "one executable artifact file whose cases are minimized" in agent

    assert "Dependency readiness is your own precondition" in architect_compact
    assert "Before returning the brief" in architect_compact
    assert "declared=yes, present=yes" in architect_compact

    assert "des dispatch --repo-root ROOT --delivery-contract PATH" in auto


def test_expectation_charter_skill_projects_canonical_dispatch_headings() -> None:
    skill = _text(CHARTER_SKILL)
    template = _text(CHARTER_TEMPLATE)

    for heading in (
        "## Intent",
        "## Preconditions",
        "## Charter",
        "## Expected observations (oracle)",
        "## Session log (append-only)",
    ):
        assert heading in skill
        assert heading in template

    assert "Negative:" in skill
    assert "Negative:" in template

    for synonym in (
        "Start Recipe",
        "Positive Observation",
        "Negative Observation",
        "Vera Session Observations",
    ):
        assert synonym not in skill


def test_expectation_charter_skill_and_adr_pin_value_conservation_law() -> None:
    skill = _text(CHARTER_SKILL)
    skill_compact = " ".join(skill.split())
    adr_compact = " ".join(_text(ADR).split())

    assert "## Value conservation" in skill
    assert (
        "lossless projection of the immutable value seed or a cited durable "
        "product authority" in skill_compact
    )
    assert (
        "never add or remove an input class, case, surface, failure mode, "
        "quality or promise" in skill_compact
    )
    assert (
        "A `Negative:` bullet negates the same promised observation on the "
        "same admitted input/surface — it is not a new scenario" in skill_compact
    )
    assert (
        "block or clarify at value authority; never guess a new requirement "
        "to fill the gap" in skill_compact
    )

    assert "Value-conservation law (charter/PO authorship)." in adr_compact
    assert (
        "lossless human projection of the immutable value seed or a cited "
        "durable product authority" in adr_compact
    )
    assert (
        "must never add or remove an input class, case, surface, failure "
        "mode, quality or promise the seed or cited authority did not "
        "already state" in adr_compact
    )
    assert (
        "A `Negative:` bullet is the negation of that same promised "
        "observation on the same admitted input/surface — never a new "
        "scenario, input or surface" in adr_compact
    )
    assert (
        "the PO blocks or clarifies at value authority instead of guessing; "
        "the PO never invents a requirement to fill the gap" in adr_compact
    )

    # Reject widening language: an uncited additional/different input or case
    # must never appear as though it were part of the conservation law itself.
    for widening in (
        "try another",
        "try a different",
        "additional input",
        "another name",
    ):
        assert widening not in skill_compact.casefold()
        assert widening not in adr_compact.casefold()


def test_expectation_charter_skill_and_adr_pin_public_start_recipe_precondition() -> (
    None
):
    skill_compact = " ".join(_text(CHARTER_SKILL).split())
    adr_compact = " ".join(_text(ADR).split())
    owner = _text(PRODUCT_OWNER)
    owner_compact = " ".join(owner.split())
    template_compact = " ".join(_text(CHARTER_TEMPLATE).split())
    examiner_compact = " ".join(
        _text(ROOT / "nWave/agents/nw-user-examiner.md").split()
    )
    auto_compact = " ".join(_text(AUTO_SKILL).split())
    verify_charter_filled = _text(ROOT / "src/des/cli/verify_charter_filled.py")

    assert "PublicStartRecipe" in skill_compact
    assert "PublicStartRecipe" in adr_compact
    assert "PublicStartRecipe" in owner_compact
    assert "PublicStartRecipe" in template_compact
    assert "PublicStartRecipe" in examiner_compact
    assert "PublicStartRecipe" in auto_compact
    assert "PublicStartRecipe" in verify_charter_filled
    assert "deterministic non-empty sequence of validated expectation charters" in (
        auto_compact
    )
    assert "candidate identity and execution root" in auto_compact
    assert "exactly once and byte-for-byte" in examiner_compact
    assert "tool or permission refusal is terminal" in examiner_compact
    for forbidden_recovery in (
        "alter the command",
        "request sandbox bypass",
        "compile/import-inspect the candidate",
        "retry through a substitute probe",
    ):
        assert forbidden_recovery in examiner_compact

    assert "is not a `PublicStartRecipe`" in skill_compact
    assert "is not a `PublicStartRecipe`" in adr_compact
    assert "is not a `PublicStartRecipe`" in owner_compact

    assert "CLARIFICATION_NEEDED" in owner_compact
    assert (
        "return `CLARIFICATION_NEEDED` and write nothing" in owner_compact
        or "return\n   `CLARIFICATION_NEEDED` and write nothing" in owner
    )

    assert "never recovered\nfrom the architecture brief" in _text(ADR) or (
        "never recovered" in adr_compact and "architecture brief" in adr_compact
    )
    for forbidden_source in ("DeliveryContract", "design", "source", "tests"):
        assert forbidden_source in adr_compact  # sanity: words exist in ADR

    # C -> D precondition and AB guarantee (Section 9b) are stated once, not
    # re-derived per role.
    assert "AB's guarantee" in adr_compact
    assert "C -> D precondition" in adr_compact
    assert "never includes\nor waits on a charter fact" in _text(ADR) or (
        "never includes" in adr_compact and "charter fact" in adr_compact
    )

    # verify-charter-filled stays structural-only; no brittle regex added to
    # approximate the semantic PublicStartRecipe judgment.
    assert "Structural, not semantic" in verify_charter_filled
    assert "never a brittle" in verify_charter_filled.replace("\n", " ")


def test_distill_task_delegates_to_one_methodology_authority() -> None:
    task = _text(TASK)

    assert "Load `~/.claude/skills/nw-distill/SKILL.md`" in task
    assert "sole methodology owner" in task
    assert "Do not reproduce" in task


def test_adr_attributes_runtime_red_evidence_to_crafter_baseline_not_atd() -> None:
    compact = " ".join(_text(ADR).split())

    assert "intended to be RED against current behavior" in compact
    assert (
        "crafter's BASELINE run against the unmodified candidate supplies the "
        "runtime RED/GREEN/BROKEN evidence, never ATD itself" in compact
    )
    assert "ATD authors the acceptance locator and the" in compact
    assert "intended-RED oracle" in compact
    assert (
        "DELIVER's crafter BASELINE run — not ATD — supplies the runtime "
        "RED/GREEN/BROKEN evidence" in compact
    )
    assert "proves it intended-RED" not in compact
    assert "proves intended RED before DELIVER" not in compact


def test_auto_skill_pins_exact_atd_envelope_and_root_fact_resolution() -> None:
    auto = _text(AUTO_SKILL)
    auto_compact = " ".join(auto.split())
    adr_compact = " ".join(_text(ADR).split())

    for line in (
        "des prepare-ordinary-request",
        "--repo-root <absolute physical root>",
        "--delivery-route <RED_TO_GREEN|GREEN_TO_GREEN>",
        "--examine <true|false>",
        "--independent-review <true|false>",
    ):
        assert line in auto

    # Transport representation belongs to the ADR/producer, while the thin
    # root owns only the single stdin invocation and verbatim forwarding.
    assert "reads the value seed as raw bytes from stdin to EOF" in adr_compact
    assert "compact JSON string literals" in adr_compact
    assert "with VALUE-SEED bytes on stdin" in auto_compact
    assert "VALUE-SEED is never argv/env/temp/transcript data" in auto_compact
    assert "Prepared(SeededAuthority)" in auto_compact
    assert "ATD always receives producer stdout verbatim" in auto_compact
    assert "Nonzero is the terminal `Blocked` WHAT/WHY/HOW" in auto_compact

    assert "alone owns oracle plus complete contract" in auto_compact
    assert "returns `DISTILL-RESULT: CONTRACT_READY`" in auto_compact

    # `CONTRACT-SCHEMA` is ephemeral dispatch context, never a contract field:
    # this invariant now lives on the ATD side that actually reads it, since
    # root no longer hand-assembles the envelope (`des prepare-ordinary-
    # request` does).
    agent_compact = " ".join(_text(AGENT).split())
    assert "`CONTRACT-SCHEMA` is ephemeral dispatch context" in agent_compact
    assert "never a contract field or persistent output" in agent_compact

    # ADR-SSOT-002 §4c total constructor, projected here: the old exclusive
    # "value owner" source for `applicability.examine` is retired in favor of
    # the closed-evidence-rule fallback below; it never comes back.
    assert "| `applicability.examine` | value owner |" not in auto
    assert "| `applicability.examine` | charter/PO/Vera |" not in auto

    # Deterministic formulas remain in the ADR/producer authority; the thin
    # root skill must not make the LLM recompute them.
    assert (
        "`auto-` + the first 16 lowercase hex characters of the SHA-256 "
        "digest over the exact UTF-8 bytes of the value seed" in adr_compact
    )
    assert "docs/delivery-contracts/{DeliveryId}.json" in adr_compact
    assert "first 16 lowercase hex characters" not in auto
    assert "docs/delivery-contracts/{DeliveryId}.json" not in auto

    # Root consumes closed facts; it does not duplicate the ADR's decision
    # tables or infer an absent semantic fact.
    assert "Root resolves only explicit/direct inputs" in auto_compact
    assert "Ambiguous semantic facts block with WHAT/WHY/HOW" in auto_compact
    assert "root never searches for or supplies the schema" in auto_compact
    assert "--contract-schema" not in auto

    assert "| M | 2,000,000 processed tokens | 30 |" in adr_compact
    assert "M = 2,000,000 processed tokens" not in auto

    # One contract, written once, by ATD alone.
    assert "alone owns oracle plus complete contract" in auto_compact
    assert "ATD remains the sole final contract author" in adr_compact


def test_auto_skill_batches_independent_po_and_atd_before_dispatch() -> None:
    auto = _text(AUTO_SKILL)
    compact = " ".join(auto.split())

    assert "one **AB batch in the same assistant message**" in compact
    assert "foreground (`run_in_background=false`)" in compact
    assert "PO concurrently receives" in compact
    assert (
        "PO concurrently receives only the producer-emitted DeliveryId, "
        "namespace, root and VALUE-SEED" in compact
    )
    assert "never the architecture-authority anchor" in compact
    assert "--architecture-authority" in auto
    assert "Neither call observes the other result" in compact
    assert "Join every terminal batch result before any dependent action" in compact
    assert "a partial/non-PASS batch stops without retry" in compact
    assert compact.index(
        "one **AB batch in the same assistant message**"
    ) < compact.index("Validate the charter when applicable")
    assert "results returned before root's next step" not in compact


def test_product_owner_author_constructor_has_only_value_side_inputs() -> None:
    owner = _text(PRODUCT_OWNER)
    compact = " ".join(owner.split())
    frontmatter = owner.split("---", 2)[1]
    tools_line = next(
        line for line in frontmatter.splitlines() if line.startswith("tools:")
    )

    assert "skills:\n  - nw-expectation-charter" in frontmatter
    assert "Skill" not in tools_line
    assert "## Skill Loading" in owner
    skill_loading_section = owner.split("## Skill Loading")[1].split("\n##")[0]
    assert "eagerly preloaded" in skill_loading_section
    assert "never invoke" in skill_loading_section.casefold()
    assert "read" in skill_loading_section.casefold()
    assert "already eagerly preloaded through this agent's frontmatter" in compact
    assert "never invoke it through the `Skill` tool" in compact

    for value_input in (
        "the physical repository root",
        "the schema-valid `DeliveryId`",
        "the exact charter namespace",
        "immutable value-side facts carried entirely by the VALUE-SEED",
    ):
        assert value_input in owner

    assert "Never receive or read an architecture-authority anchor" in owner
    assert "it is a DESIGN/ATD readiness input, not value authority" in compact

    charter_frontmatter = _text(CHARTER_SKILL).split("---", 2)[1]
    assert "user-invocable: false" in charter_frontmatter
    assert "disable-model-invocation" not in charter_frontmatter

    # PO's tool grant is exactly `Write`: source-blindness is a capability
    # boundary, not a prose promise, so the contaminated read/discover state
    # is unrepresentable rather than merely forbidden.
    assert tools_line.strip() == "tools: Write"
    for forbidden_tool in ("Read", "Edit", "Glob", "Grep"):
        assert forbidden_tool not in tools_line

    # PO never rechecks the upstream Discover/Resolve fact or the namespace.
    assert "Confirm the namespace is missing or empty" not in owner
    assert (
        "this role never\nrechecks the namespace, rereads repository contents "
        "or otherwise reverifies\nthat fact" in owner
    )
    assert "holding no\nRead/Edit/Glob/Grep tool, cannot do otherwise" in owner

    # The destination is deterministic and closed, never an open/inferred
    # filename within the namespace.
    assert (
        "exactly\n   `docs/product/expectations/{delivery-id}/charter.md`, "
        "joined beneath the\n   supplied physical repository root" in owner
    )
    assert "Never search for, list or infer any\n   other filename" in owner
    assert (
        "terminal `INDETERMINATE`/`FAIL` — never permission to explore, "
        "read or\n   repair the destination" in owner
    )

    # The ADR's authority-map law states the same Write-only capability and
    # deterministic destination, not a second SSOT restating the agent body.
    adr_compact = " ".join(_text(ADR).split())
    assert (
        "The fresh PO's tool grant is exactly `Write` — no `Read`, `Edit`, "
        "`Glob` or `Grep`" in adr_compact
    )
    assert (
        "so it writes exactly one deterministic destination, "
        "`docs/product/expectations/{delivery-id}/charter.md`" in adr_compact
    )
    assert (
        "can neither recheck the upstream `Discover=Missing\\|Empty`/"
        "`Resolve=Author` fact nor discover any other file" in adr_compact
    )


def test_auto_skill_projects_exact_resolve_charters_command_and_routing() -> None:
    auto = _text(AUTO_SKILL)
    compact = " ".join(auto.split())

    assert (
        "des resolve-charters --repo-root <root> --delivery-id <producer id> "
        "--examine <true|false>" in compact
    )
    assert compact.index("Prepared(SeededAuthority)") < compact.index(
        "des resolve-charters --repo-root <root> --delivery-id <producer id> "
        "--examine <true|false>"
    )
    assert "Route only by its closed `status`" in compact
    assert (
        "never runs `find`, a global search, or any ad-hoc filesystem "
        "inference" in compact
    )
    assert (
        "ATD always receives only the original fourteen-line producer stdout "
        "verbatim" in compact
    )


def test_auto_skill_forbids_duplicate_producer_probes() -> None:
    compact = " ".join(_text(AUTO_SKILL).split())

    assert "Run exactly once, with VALUE-SEED bytes on stdin" in compact
    for forbidden_probe in (
        "`des --help`",
        "`which des`",
        "`des validate-delivery-contract`",
        "hashing, recounting or another producer probe",
    ):
        assert forbidden_probe in compact
    assert "never recomputes, revalidates or restates those formulas" in compact
