"""Direct-cutover projection laws for DeliveryContract -> DISTILL/ATD."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "nWave/agents/nw-acceptance-designer.md"
SKILL = ROOT / "nWave/skills/nw-distill/SKILL.md"
TASK = ROOT / "nWave/tasks/nw/distill.md"
ARCHITECT = ROOT / "nWave/agents/nw-solution-architect.md"
ARCHITECT_REVIEWER = ROOT / "nWave/agents/nw-solution-architect-reviewer.md"
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
    # fa7d9730a: compile-contract now runs between resolve-charters and ATD's
    # dispatch, but the property this pin protects is unchanged -- ATD still
    # receives only the CLI-printed producer envelope verbatim, never a
    # root-authored or root-augmented one.
    assert (
        "ATD always receives the original fourteen-line producer stdout "
        "verbatim, unchanged by this step" in auto_compact
    )
    assert (
        "never hand-authored, never reconstructed, never re-augmented with "
        "compile-contract's own output" in auto_compact
    )
    assert "Nonzero is the terminal `Blocked` WHAT/WHY/HOW" in auto_compact

    # ATD now FILLS a compiler-written skeleton (never authors one from
    # scratch) but remains the sole owner of writing the oracle.
    assert "ATD fills it" in auto_compact
    assert "rather than authoring from scratch" in auto_compact
    assert (
        "alone owns writing the oracle at the skeleton's own given locator"
        in auto_compact
    )
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
    assert (
        "alone owns writing the oracle at the skeleton's own given locator"
        in auto_compact
    )
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
    # fa7d9730a: compile-contract now runs between resolve-charters and
    # ATD's dispatch; the property protected here (ATD receives only the
    # CLI-printed producer envelope verbatim, never root-authored) is
    # unchanged -- only the exact pinned wording moved.
    assert (
        "ATD always receives the original fourteen-line producer stdout "
        "verbatim, unchanged by this step" in compact
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


def test_agent_pins_declared_imports_self_check_without_a_bash_tool() -> None:
    """Run 4 defects A/B (K4 matrix row 12 self-reference variant): ATD must
    self-audit `declared-imports` against what it actually read, but it
    holds no `Bash` tool -- the interrogative must not tell it to run
    `des code-fact`/`des validate-delivery-contract` itself; `des dispatch`
    (root, immediately after CONTRACT_READY, before any crafter starts)
    remains the sole independent re-verification."""
    agent = _text(AGENT)
    compact = " ".join(agent.split())

    assert "`EVIDENCE_GAP`, never a guess written into the contract" in compact
    assert "a target this same contract itself" in compact
    assert "asks the crafter to create (a self-reference)" in compact
    assert "checks it with the Read capability it holds alone" in compact
    assert "it runs no shell" in compact
    assert (
        "never invokes `des code-fact` or `des validate-delivery-contract`" in compact
    )
    # Ale's construction-over-file correction (2026-08-20): ATD now holds
    # Bash, but locked down to exactly `des fill-contract` by an installed
    # PreToolUse hook -- this self-check step itself still never reaches
    # for it (the "runs no shell" pin above is about THIS specific check).
    assert "tools: Read, Write, Edit, Bash" in agent
    assert (
        "`des dispatch` independently re-verifies every `declared-imports` "
        "entry against the base tree immediately after `CONTRACT_READY`, "
        "before any crafter is dispatched" in compact
    )


def test_agent_pins_bare_vs_dotted_declared_import_form() -> None:
    """Run 6 false-reject: the resolver now accepts a bare name bound in the
    target's own file (third-party/stdlib included), but the FORM still
    matters -- a dotted third-party reference (`cronsim.CronSim`) is still
    unresolvable and rejected as invented. ATD must write the form that
    matches what the authority showed, never guess between them."""
    agent = _text(AGENT)
    compact = " ".join(agent.split())

    assert (
        "Write the FORM the authority actually showed: a bare name "
        "(`CronSim`, `ZoneInfo`) when it is bound at the top of THIS "
        "target's own file" in compact
    )
    assert "third-party/stdlib included" in compact
    assert (
        "a dotted base-tree path "
        "(`des.domain.repo_path_resolver.resolve_repo_root`) only for an "
        "in-repo symbol the target does not itself import" in compact
    )
    assert (
        "Never write a dotted form for a third-party/stdlib symbol "
        "(`cronsim.CronSim`) — unresolvable there by design, rejected as "
        "invented" in compact
    )
    # The stale disqualifier this row removes: third-party/stdlib names are
    # a legitimate bare-form citation now, never blanket-excluded.
    assert "or from a third-party/" not in compact


def test_agent_pins_lossless_overlap_projection_and_single_regular_oracle_file() -> (
    None
):
    """Run 5 evidence: the DESIGN authority already carried precise file:line
    reuse citations, but the compiled DeliveryContract's overlap/
    justification dropped most of them, forcing the crafter to re-discover
    them at a cost of 30 Read/Bash calls before its first production edit
    (nw-software-crafter.md's bound is 15). Pin the lossless-projection law
    plus the oracle-locator regularity rule Run 5's third dispatch rejection
    named (a directory locator is not a stable oracle identity)."""
    agent = _text(AGENT)
    compact = " ".join(agent.split())

    assert (
        "`overlap`/ `justification` is a LOSSLESS projection of the cited "
        "architecture authority's own reuse-decision facts for that target" in compact
    )
    assert "ADR-SSOT-002 Section 4b" in compact
    assert (
        "every file:line citation, existing symbol name and exemplar "
        "call-site pattern the authority already gives for that target "
        "must survive into `overlap`/`justification` verbatim" in compact
    )
    assert (
        "`acceptance-tests.locator` names exactly ONE regular file this "
        "role wrote or extended, never a directory, symlink or fifo" in compact
    )
    assert (
        "designate exactly one as the primary locator and route every "
        "other file through `verification-scope.commands`" in compact
    )
    # Both routes carry the law -- GREEN_TO_GREEN points back rather than
    # dropping it, mirroring the declared-imports pointer pattern.
    assert "RED_TO_GREEN step 7's lossless-projection law unchanged" in compact
    # RED_TO_GREEN and GREEN_TO_GREEN both carry the check (or GREEN_TO_GREEN
    # points back to the shared RED_TO_GREEN rule) -- not authored once and
    # silently dropped from the other route.
    assert agent.count("declared-imports") >= 4
    assert "RED_TO_GREEN step 6 question" in compact


def test_agent_pins_verification_command_copied_from_authority() -> None:
    """K4 Run 9: ATD-1 constructed a `manage.py test` dotted path itself
    (`api.tests.*`) instead of copying the architecture authority's own
    fragment (`hc.api.tests.*`), a wrong-package-prefix defect `des
    dispatch` now catches, but only after ATD guessed it in the first
    place. One interrogative line: copy the command, never construct it."""
    compact = " ".join(_text(AGENT).split())

    assert (
        "Does the read architecture authority's own fragment already "
        "state the exact test invocation" in compact
    )
    assert "or are you constructing the package/module prefix yourself?" in compact
    assert "Copy it verbatim" in compact
    assert (
        "K4 Run 9: `api.tests.*` guessed instead of the authority's own "
        "`hc.api.tests.*`" in compact
    )


def test_agent_pins_oracle_read_back_indentation_check() -> None:
    """K4 Run 10: a test method spliced into the MIDDLE of another's body
    compiled fine but was never collected by any runner, silently
    swallowing the host method's own tail assertions -- a crafter hit it
    only at BASELINE after implementing a full production change. ATD must
    read the oracle back once immediately after writing it and confirm
    every test def sits at class-body indentation."""
    compact = " ".join(_text(AGENT).split())

    assert "Immediately after that Write, Read the oracle back whole once" in compact
    assert "not the forbidden discovery call" in compact
    assert (
        "confirm every `def test_`/`async def test_` line starts at "
        "class-body indentation" in compact
    )
    assert "never nested inside another `def`/`async def`" in compact
    assert "no runner ever collects it" in compact


def test_auto_skill_routes_contract_fact_gap_as_friction_not_a_gate() -> None:
    """Run 5: root's routing table must not turn a high first-mutation
    tool-call number into a routing branch -- it is evidence for ATD's next
    contract, reported alongside the verdict-driven route, never a reason to
    change it."""
    compact = " ".join(_text(AUTO_SKILL).split())

    assert (
        "A non-`none` `contract-fact-gap` (`first-production-mutation-tool-call` "
        "past 15) never changes the row above" in compact
    )
    assert "friction evidence for ATD's next contract" in compact
    assert "not a gate on this one" in compact


def test_auto_skill_pins_deterministic_examine_criterion() -> None:
    """K4 Run 10: `--examine` flipped between runs (true, then false) with
    no stated reason -- root guessed. `des prepare-ordinary-request` itself
    deliberately never infers this (it is a closed-rule semantic decision,
    not a producer projection); the deterministic criterion belongs at
    root's own decision point, before the producer call, citing
    ADR-SSOT-002 Section 5."""
    compact = " ".join(_text(AUTO_SKILL).split())

    assert (
        "does the VALUE-SEED name a user-observable surface the request "
        "drives — an API endpoint, a CLI, a UI, a workflow a human or an "
        "external client exercises? Then `--examine true`" in compact
    )
    assert (
        "Does it name only an internal-only refactor with no new or "
        "changed user-observable surface? Then `--examine false`" in compact
    )
    assert "ADR-SSOT-002 Section 5" in compact
    assert (
        "`des prepare-ordinary-request` deliberately never infers, "
        "defaults or guesses `examine` itself" in compact
    )
    assert "never a flip-a-coin or copy-the-last-run's value" in compact


def test_architect_self_verifies_every_citation_before_covered() -> None:
    """Run 5 evidence: the architect returned `ARCHITECTURE-COVERED` with a
    factually wrong citation in brief.md; root then spent 263s/185K tokens
    fact-checking it by Reading source files itself. The architect must
    self-verify every citation with the deterministic tool it already has
    before it ever returns `COVERED`."""
    architect = _text(ARCHITECT)
    compact = " ".join(architect.split())

    assert "Citation self-verification" in architect
    assert "des code-fact query.atoms-in-file" in compact
    assert "Citations verified: N/N (line-checked: k, symbol-checked: m)" in compact
    assert "return `ARCHITECTURE-BLOCKED`" in compact
    # The self-check is positioned before the terminal one-line return, not
    # after -- an afterthought check race-condition-loses to a fast COVERED.
    assert compact.index("Citation self-verification") < compact.index(
        "Return exactly one line, nothing else"
    )


def test_architect_verifies_each_citation_by_what_it_claims() -> None:
    """Team-lead review of 241507fff: `query.atoms-in-file` returns symbol
    names only (no line numbers) and `callers-of`/`reads-of` return usage
    sites, not definitions -- neither can honestly certify a `path:line`
    citation. A `path:line` claim must be Read at the exact line; only a
    symbol-only claim with no line goes through code-fact; no
    `query.where-defined` capability exists in the closed five-capability
    CLI, so the text must not invent one."""
    compact = " ".join(_text(ARCHITECT).split())

    assert "path:line` citation" in compact
    assert "`Read` that exact line" in compact
    assert "symbol-only citation" in compact
    assert "no `query.where-defined` capability exists" in compact
    assert "cannot be self-verified deterministically" in compact
    assert "never a partial `COVERED`" in compact
    assert "batch Reads by file" in compact


def test_architect_reviewer_falsifies_citation_verification() -> None:
    reviewer = _text(ARCHITECT_REVIEWER)
    compact = " ".join(reviewer.split())

    assert "Citations verified: N/N (line-checked: k, symbol-checked: m)" in compact
    assert "spot check at least one cited" in compact
    assert "NEEDS_REVISION" in compact


def test_auto_skill_forbids_root_source_reads_and_names_one_verification_command() -> (
    None
):
    """Run 5 evidence: root re-read whole implementation/test files to
    fact-check a returned brief -- 44% of its total token spend in one
    block. Root's only allowed verification is one bounded `des code-fact`
    call; it must never Read source, and never hand-edit the durable
    authority itself (root Edited brief.md directly in the same run)."""
    auto = _text(AUTO_SKILL)
    compact = " ".join(auto.split())

    assert "Root verification discipline" in auto
    assert "des code-fact query.atoms-in-file --root" in compact
    assert "never a broad `Read`" in compact
    assert (
        "never repair it by reading further source or editing the authority directly"
        in compact
    )


def test_auto_skill_warns_off_spine_crafter_dispatch_before_the_attempt() -> None:
    """Run 5 evidence: root attempted a bare off-spine crafter Agent
    dispatch, wasting ~44s before the existing guard denied it. The warning
    must sit at the point root is about to act, not only be discoverable
    after rejection."""
    auto = _text(AUTO_SKILL)
    compact = " ".join(auto.split())

    heading_index = auto.index("## CLI dispatch — the only bridge")
    warning_index = compact.index("cryptographically gated and refused every time")
    atd_returns_index = compact.index("ATD returns exactly")
    # The warning is inside the CLI-dispatch section, before the mechanics.
    assert heading_index != -1
    assert warning_index < atd_returns_index


def test_auto_skill_pins_pre_producer_recipe_check() -> None:
    """Run 8 debrief: root had Read access to the project's own API/README
    docs the whole time and never used it before writing the first
    VALUE-SEED, forcing a wasted PO round (INDETERMINATE) plus a full ATD
    re-author under a new DeliveryId. The interrogative must fire BEFORE the
    first `des prepare-ordinary-request` call, not after PO reports the gap."""
    auto = _text(AUTO_SKILL)
    compact = " ".join(auto.split())

    check_index = compact.index(
        "does the VALUE-SEED already carry the literal public start recipe"
    )
    first_call_index = compact.index("Run exactly once, with VALUE-SEED bytes on stdin")
    assert check_index < first_call_index
    assert "PO is Write-only" in compact
    assert "Read the project's own API/README docs" in compact
    assert "BEFORE the first producer call, not after an `INDETERMINATE`" in compact


def test_auto_skill_routes_po_scope_gap_to_po_never_atd() -> None:
    """Run 8 debrief: root misrouted a PO-scope INDETERMINATE (missing
    PublicStartRecipe) to ATD via REVISE-CONTRACT, costing a full wasted
    dispatch when ATD correctly bounced it back EVIDENCE_GAP. Pin both the
    routing rule and the DeliveryId-changes-with-the-seed consequence
    (ADR-SSOT-002), plus the complementary same-DeliveryId REVISE-CONTRACT
    rule for a charter-only fix."""
    compact = " ".join(_text(AUTO_SKILL).split())

    assert (
        "is a PO-scope gap, never a DISTILL/ATD defect: never route it to "
        "ATD via `REVISE-CONTRACT`" in compact
    )
    assert "Run 8's own mistake" in compact
    assert (
        "`DeliveryId` is `auto-` plus the first 16 hex characters of the "
        "SHA-256 digest over the exact VALUE-SEED bytes" in compact
    )
    assert "so it is a DIFFERENT `DeliveryId`" in compact
    assert "restart from step 1 with the corrected seed" in compact
    assert (
        "If instead the SAME `DeliveryId`'s contract already exists and "
        "only the charter needed a fix" in compact
    )
    assert (
        "dispatch ATD via `REVISE-CONTRACT` exactly as the crafter-citing-contract"
        in compact
    )


def test_auto_skill_routing_table_names_self_flagged_oracle_gap() -> None:
    """The crafter's own self-flagged coverage/oracle gap must route exactly
    like an invented import or self-referential obligation -- REVISE-CONTRACT
    to ATD, never accepted as a silent PASS."""
    compact = " ".join(_text(AUTO_SKILL).split())

    assert "a self-flagged coverage/oracle gap" in compact
    assert (
        "a self-flagged gap is never `PASS` with the gap only noted in "
        "`residuals`" in compact
    )


def test_architect_states_budget_arithmetic_and_doubles_it_for_maxturns() -> None:
    """Discord (yuki.uthman, 2026-08-19): nw-solution-architect capped at 30
    exceeded to 37 on a Flutter/Dart project. K4 runs 10-11: architect at
    28-34 calls. The mechanical 4-step Workflow floor cannot see the real
    cost -- citation self-verification (bb77997f9) scales with cited-file
    count, and a non-Python project falls back to the TextSearch floor,
    needing more Reads per file. The agent must state its own arithmetic
    and maxTurns must double it, not merely meet it."""
    text = _text(ARCHITECT)
    compact = " ".join(text.split())

    assert "maxTurns: 60" in text
    assert "reuse survey ≤15 (broader than the consult's six calls" in compact
    assert (
        "citation self-verification ≤1 call per cited FILE (batched) plus "
        "≤1 per symbol-only citation, up to 12 cited files/symbols" in compact
    )
    assert "= 15 + 2 + 12 + 1 = 30 as the arithmetic floor" in compact
    assert (
        "`maxTurns` below is set to TWICE that floor, not the bare floor: "
        "Discord (yuki.uthman, 2026-08-19, capped at 30, exceeded to 37 on "
        "a Flutter/Dart project) and K4 runs 10-11 (architect at 28-34 "
        "calls)" in compact
    )
    assert "`des code-fact` falls back to the TextSearch floor" in compact


def test_guard_stop_returns_a_terminal_result_atd_po_architect() -> None:
    """The installed budget guard turns any overrun into a clean terminal at
    N-2; each route agent must return ITS OWN closed vocabulary's blocking
    state naming what is unfinished, never a silent kill (GDP-6). ATD and
    the architect carry no literal `INDETERMINATE` verdict field, so they
    use their own closed terms (`EVIDENCE_GAP`, `ARCHITECTURE-BLOCKED`)
    rather than an invented token their own spec never declares."""
    atd = " ".join(_text(AGENT).split())
    po = " ".join(_text(PRODUCT_OWNER).split())
    architect = " ".join(_text(ARCHITECT).split())

    assert (
        "If the budget guard stops you, return `EVIDENCE_GAP` naming what "
        "is unfinished" in atd
    )
    assert (
        "If the budget guard stops you, return your terminal result as "
        "`INDETERMINATE` naming what is unfinished" in po
    )
    assert (
        "If the budget guard stops you, return `ARCHITECTURE-BLOCKED` "
        "naming what is unfinished" in architect
    )
