"""Public oracle: `des design --value N`, one architect turn invoked alone.

ADR-SSOT-002 Section 4b names the step by PROPERTY -- «One role turn under a
provider-enforced typed contract: takes the role, the minimum facts that role
consumes, the private workspace; returns the closed outcome, the role's typed
output, its diagnostic verbatim.»

Three properties are measured here rather than argued.  The step buys EXACTLY
one turn and executes nothing its own `NEXT` names.  It is REPEATABLE: a second
invocation over a bound value carries a finding and REPLACES the typed facts,
which is the correction the orchestrator decides on, not an edge the software
takes.  And a refusing turn forwards the architect's own words and names both
available moves without ranking them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "one Request whose single value the architect binds typed facts to"
HANDOVER = Path(".nwave") / "des" / "handover.json"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"


def design_facts(
    target: str = TARGET,
    decision: str = "CREATE_NEW",
    *,
    authority_locator: str | None = None,
) -> dict:
    """One accepted architect envelope.

    `authority_locator` is passed through EXPLICITLY only when a scenario is
    about that field.  Left unstated, the fake provider fills the same empty
    string a real provider-authored fact set carries when no DESIGN-document
    constructor has assigned a section identity yet, so every other scenario
    keeps measuring what it was written for.
    """
    facts = {
        "targets": [{"path": target, "decision": decision}],
        "paradigm": "object_oriented",
        "decisions": ["one opaque semantic decision"],
        "oracle": ORACLE,
        "acceptance_supports": [SUPPORT],
        "verification": [[sys.executable, "-m", "pytest", ORACLE]],
        "oracle_verification_index": 0,
    }
    if authority_locator is not None:
        facts["authority_locator"] = authority_locator
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": facts,
        }
    }


def decomposed(root: Path, step) -> None:
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err


def authority(root: Path, position: int = 1) -> str | None:
    stored = json.loads((root / HANDOVER).read_text())
    return stored["values"][position - 1]["authority"]


def test_an_accepted_turn_binds_the_typed_facts_and_names_the_oracle_step(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert "bound the value to its typed design facts" in lines["DIAGNOSTIC"]
    assert nexts(out) == [f"des oracle --repo-root {root} --value 1"]
    bound = authority(root)
    assert bound is not None
    assert bound["oracle"] == ORACLE
    assert bound["targets"] == [{"path": TARGET, "decision": "CREATE_NEW"}]
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]


def test_a_second_turn_with_a_finding_replaces_the_bound_facts(
    root: Path, step, turns: Path
) -> None:
    """Correction is a REPEAT of the same step, decided by the orchestrator."""
    decomposed(root, step)
    step("design", "--repo-root", str(root), "--value", "1", answers=[design_facts()])
    assert authority(root)["targets"][0]["path"] == TARGET

    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts(target="src/product/other.py")],
        stdin="the declared target does not exist in this repository",
    )

    assert code == 0, out + err
    assert authority(root)["targets"][0]["path"] == "src/product/other.py"
    assert asked(turns) == [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-solution-architect",
    ]
    forwarded = json.loads(turns.read_text())[-1]["prompt"]
    assert "the declared target does not exist" in forwarded


def test_a_correction_repeating_the_current_facts_is_measured_not_refused(
    root: Path, step
) -> None:
    """ADR-DES-003 §2.5: identity of an answer with the previous one is a FACT.

    The refusal it replaces existed to stop a loop the composer ran, and the
    composer no longer decides. The census had already ruled it: software
    measures identity, the model decides what identity means.
    """
    decomposed(root, step)
    step("design", "--repo-root", str(root), "--value", "1", answers=[design_facts()])
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts()],
        stdin="a finding the architect answers by repeating itself",
    )
    assert code == 0, out + err
    assert "UNCHANGED" in block(out, err)


def test_a_rejecting_turn_forwards_the_architect_words_and_ranks_no_move(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    finding = (
        "this value's observation names two outcomes, so no single design binds it"
    )
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": finding,
                    "design_facts": None,
                }
            }
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == "DesignRejected"
    assert "names two outcomes" in lines["DIAGNOSTIC"]
    assert authority(root) is None
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]
    moves = nexts(out)
    assert len(moves) > 1
    assert any(item.startswith(f"des state --repo-root {root}") for item in moves)


def test_a_value_position_outside_the_graph_is_refused_before_a_turn_is_bought(
    root: Path, step, turns: Path
) -> None:
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "9", answers=[design_facts()]
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "ValueOutOfRange"
    assert "1" in lines["WHY"]
    assert asked(turns) == ["nw-product-owner"]


#: Where the DESIGN section is published when nothing is configured, which is
#: what this fixture repository leaves unconfigured -- so the destination the
#: judgement reads is the one a real unconfigured subject presents.
DESTINATION = Path("docs") / "product" / "architecture" / "brief.md"

#: A destination somebody ELSE owns: a regular file, Git does not track it, and
#: it carries an `## ` heading that is not this step's.  That is exactly the
#: shape `publish_design_document` refuses AFTER the turn today.
FOREIGN = "# Architecture\n\n## Someone Else's Section\n\nprose.\n"

UNSAFE = "UnsafeDesignDestination"

#: The ONE WHY both untracked arms share.  Value 1's promise is the EQUALITY of
#: the pre-turn and the post-turn refusal text, never these literal bytes, so the
#: constants move with the rule and the scenarios below keep measuring equality.
WHY_UNSAFE = "an untracked DESIGN destination may hold only sections this Request bound"


def how_foreign(heading: str) -> str:
    """The HOW of the arm that found a section no value of this Request bound.

    It QUOTES the offending heading, because the repair an operator can act on
    is about that one section and a HOW that named the file alone would leave
    them reading the whole document to find what the step objected to.
    """
    return (
        f'the untracked destination holds the section "## {heading}", which no '
        "value of this Request bound; track it with Git, or move that section "
        "out before re-invoking this step"
    )


#: The other untracked arm: bytes that own no section at all.  It names the
#: BYTES rather than a heading, because inventing one to quote here would be a
#: refusal that lies about what it read.
HOW_NO_SECTION = (
    "the untracked destination holds bytes no DESIGN section owns; track it "
    "with Git, or move those bytes out before re-invoking this step"
)

HOW_UNSAFE = how_foreign("Someone Else's Section")

#: The section identities this Request's two values bind.  Stated EXPLICITLY
#: wherever a scenario needs a section on disk, because the shared `design_facts`
#: helper leaves `authority_locator` empty -- and with it empty the step
#: publishes nothing at all, so a scenario about document bytes that omitted it
#: would be measuring a turn that never wrote one.
HEADING_ONE = "Value One"
HEADING_TWO = "Value Two"


def section(heading: str) -> str:
    return f"{DESTINATION}#{heading}"


def refusal_rows(out: str, err: str, *, turns_bought: str) -> None:
    """The refusal the post-turn rule prints today, row for row."""
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == UNSAFE
    assert lines["WHY"] == WHY_UNSAFE
    assert lines["HOW"] == HOW_UNSAFE
    assert lines["TURNS-BOUGHT"] == turns_bought


def test_a_destination_the_post_turn_rule_refuses_costs_no_architect_turn(
    root: Path, step, turns: Path, another
) -> None:
    """The destination judgement moves BEFORE the turn, and nothing else moves.

    Four arms over one stimulus family, because the value is a claim about WHEN
    a judgement runs and a claim about when it runs is only falsifiable against
    the cases it must NOT change.  A destination the post-turn rule refuses is
    refused with the same WHAT/WHY/HOW at `TURNS-BOUGHT: 0`; an absent and a
    tracked destination still buy their turn exactly as today; and a destination
    that was safe before the turn and replaced DURING it is still refused after
    the turn is spent -- the pre-turn judgement is a cost gate, never a lock.

    Every refusing arm also measures that the refusal WROTE NOTHING: the
    destination bytes and the handover are byte-identical and the value is
    unbound, so a gate that refused after mutating something cannot pass here.
    """
    # ARM 1: an untracked regular destination holding a foreign heading.
    decomposed(root, step)
    destination = root / DESTINATION
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(FOREIGN)
    before = (root / HANDOVER).read_bytes()

    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )

    assert code == 1, out + err
    refusal_rows(out, err, turns_bought="0")
    # The falsifier, measured directly: no architect turn was invoked at all.
    assert asked(turns) == ["nw-product-owner"]
    assert destination.read_text() == FOREIGN
    assert (root / HANDOVER).read_bytes() == before
    assert authority(root) is None

    # ARM 2: an ABSENT destination is admitted by the same judgement, and the
    # step proceeds to buy the turn and publish exactly as today.
    destination.unlink()
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[design_facts(authority_locator=section(HEADING_ONE))],
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["TURNS-BOUGHT"] == "1"
    assert lines["DOCUMENT"] == section(HEADING_ONE)
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]
    assert authority(root) is not None

    # ARM 3: an existing TRACKED regular destination is admitted too, on a
    # second repository so the arms never read each other's bytes.
    other, other_step, other_turns = another()
    decomposed(other, other_step)
    tracked = other / DESTINATION
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text(FOREIGN)
    git(other, "add", str(DESTINATION))
    git(other, "commit", "-qm", "authority")

    code, out, err = other_step(
        "design", "--repo-root", str(other), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["TURNS-BOUGHT"] == "1"
    assert asked(other_turns)[-1] == "nw-solution-architect"

    # ARM 4: safe before the turn, replaced DURING it by someone else -- here
    # the provider itself, writing through its own `writes` key.  Today's
    # post-turn refusal still answers, and the turn is spent.
    third, third_step, third_turns = another()
    decomposed(third, third_step)
    stored = (third / HANDOVER).read_bytes()
    answer = design_facts(authority_locator=section(HEADING_ONE)) | {
        "writes": {str(DESTINATION): FOREIGN}
    }

    code, out, err = third_step(
        "design", "--repo-root", str(third), "--value", "1", answers=[answer]
    )

    assert code == 1, out + err
    refusal_rows(out, err, turns_bought="1")
    assert asked(third_turns)[-1] == "nw-solution-architect"
    assert (third / DESTINATION).read_text() == FOREIGN
    assert (third / HANDOVER).read_bytes() == stored
    assert authority(third) is None


def two_values(root: Path, step) -> None:
    """One Request decomposed into two ordered values, the second depending on the first."""
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A", "B")],
        stdin=REQUEST,
    )
    assert code == 0, out + err


def design_into(step, root: Path, position: int, heading: str, target: str):
    """One design turn that NAMES the section it publishes, as a real one does."""
    return step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        str(position),
        answers=[design_facts(target=target, authority_locator=section(heading))],
    )


SECOND_TARGET = "src/product/second.py"

#: Bytes that own no `## ` section at all: an untracked file somebody started by
#: hand.  There is nothing here this Request bound, so the append would be
#: writing past the end of a document the step has no evidence it owns.
NO_SECTION = "architecture notes with no section marker at all\n"


def headings(text: str) -> list[str]:
    """Every `## ` line, by the publisher's own notion of what owns a section."""
    return [line for line in text.splitlines() if line.startswith("## ")]


def test_a_destination_this_request_published_is_extended_without_staging_it(
    root: Path, step, turns: Path, another
) -> None:
    """A destination the RUNNER ITSELF wrote is safe to extend, and stays untracked.

    Three arms over one stimulus family.  The permissive direction is the value:
    a first value's DESIGN step creates the brief and leaves it untracked, and
    the next value appends into it exactly as into a tracked file -- because
    every `## ` heading the file carries is the heading of an authority locator
    this Request's own handover binds.  The two refusing directions are what
    make that claim falsifiable rather than a widening of the rule to nothing:
    one foreign `## ` section, or non-empty bytes owning no section at all, and
    the step still refuses at zero cost with a HOW that names what it found.

    The promise that NOTHING IS STAGED is a property of what the step does not
    do, so it is measured on the REAL index bytes on either side of the command
    -- snapshotted after a settling `git status`, so a refreshed stat cache
    cannot be mistaken for a write -- and on `git status` still reporting the
    destination as untracked.  A proxy (counting `git add` call sites, say)
    would pass for a step that staged through any other spelling.
    """
    # ARM 1: value 1 creates the destination untracked; value 2 extends it.
    two_values(root, step)
    code, out, err = design_into(step, root, 1, HEADING_ONE, TARGET)
    assert code == 0, out + err
    destination = root / DESTINATION
    first = destination.read_bytes()
    assert headings(first.decode()) == [f"## {HEADING_ONE}"]
    # Settle the stat cache BEFORE the snapshot, so the comparison below is
    # about the step's writes and not about this suite's own bookkeeping.
    assert (
        git(root, "status", "--porcelain", "--untracked-files=all", "--", DESTINATION)
        == f"?? {DESTINATION}"
    )
    index = root / ".git" / "index"
    before_index = index.read_bytes()

    code, out, err = design_into(step, root, 2, HEADING_TWO, SECOND_TARGET)

    assert code == 0, out + err
    # The index FIRST: read before this scenario issues any Git command of its
    # own, so nothing between the step and the measurement could have moved it.
    assert index.read_bytes() == before_index
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["TURNS-BOUGHT"] == "1"
    assert lines["DOCUMENT"] == section(HEADING_TWO)
    assert asked(turns) == [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-solution-architect",
    ]
    # Appended, never rewritten: value 1's bytes are an exact PREFIX, and the
    # file owns exactly the two sections this Request bound.
    extended = destination.read_bytes()
    assert extended.startswith(first)
    assert len(extended) > len(first)
    assert headings(extended.decode()) == [f"## {HEADING_ONE}", f"## {HEADING_TWO}"]
    # Still untracked: the runner performed no `git add`.  Scoped to the
    # DESTINATION, because the whole-tree status also carries the runner's own
    # bookkeeping and would measure the fixture's gitignore, not this value.
    assert (
        git(root, "status", "--porcelain", "--untracked-files=all", "--", DESTINATION)
        == f"?? {DESTINATION}"
    )
    assert authority(root, 2) is not None

    # And the projection names no repair for the operator to perform.
    code, out, err = step("state", "--repo-root", str(root))
    assert code == 0, out + err
    projected = block(out, err)
    assert "design=bound" in projected["VALUE-1"]
    assert "design=bound" in projected["VALUE-2"]
    assert "HOW" not in projected

    # ARM 2: the SAME runner-published file, carrying one foreign section.  A
    # second checkout, so the arms never read each other's bytes.
    other, other_step, other_turns = another()
    two_values(other, other_step)
    code, out, err = design_into(other_step, other, 1, HEADING_ONE, TARGET)
    assert code == 0, out + err
    published = other / DESTINATION
    published.write_bytes(published.read_bytes() + FOREIGN.encode())
    foreign_bytes = published.read_bytes()
    stored = (other / HANDOVER).read_bytes()

    code, out, err = design_into(other_step, other, 2, HEADING_TWO, SECOND_TARGET)

    assert code == 1, out + err
    refusal_rows(out, err, turns_bought="0")
    assert block(out, err)["HOW"] == how_foreign("Someone Else's Section")
    assert asked(other_turns) == ["nw-product-owner", "nw-solution-architect"]
    assert published.read_bytes() == foreign_bytes
    assert (other / HANDOVER).read_bytes() == stored
    assert authority(other, 2) is None

    # ARM 3: an untracked destination holding non-empty bytes no section owns.
    third, third_step, third_turns = another()
    two_values(third, third_step)
    prose = third / DESTINATION
    prose.parent.mkdir(parents=True, exist_ok=True)
    prose.write_text(NO_SECTION)
    handover = (third / HANDOVER).read_bytes()

    code, out, err = design_into(third_step, third, 1, HEADING_ONE, TARGET)

    assert code == 1, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert lines["WHAT"] == UNSAFE
    assert lines["WHY"] == WHY_UNSAFE
    assert lines["HOW"] == HOW_NO_SECTION
    assert lines["TURNS-BOUGHT"] == "0"
    assert asked(third_turns) == ["nw-product-owner"]
    assert prose.read_text() == NO_SECTION
    assert (third / HANDOVER).read_bytes() == handover
    assert authority(third, 1) is None


def test_designing_before_any_decomposition_is_refused_and_names_the_owner(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "HandoverAbsent"
    assert asked(turns) == []
    assert any(item.startswith(f"des po --repo-root {root}") for item in nexts(out))


#: The architect's OWN authoring surface, as a real step resolves it: the role
#: spec inside the checkout the step was pointed at (`conftest.base_repository`
#: commits `nWave/agents` into it), never the developer tree this suite happens
#: to run from.  A statement that exists only in the source tree is a statement
#: the turn never reads.
ARCHITECT_SPEC = Path("nWave") / "agents" / "nw-solution-architect.md"

#: The region that carries the statement, and the module the marker must name as
#: the source it was derived from.  The marker is the projection's own claim of
#: provenance: a body derived from anything else is a false fact shipped inside
#: generated prose.
GRAMMAR_REGION = "design-authority-locator"
GRAMMAR_SOURCE_MODULE = "des.domain.design_authority_locator"

#: The paragraph the statement has to sit with, because that is where the field
#: is authored.  A rule published three paragraphs away from the field it
#: governs is read after the turn has already answered.
AUTHORING_PARAGRAPH = "its requested `design_facts`"

#: Every shape the published grammar refuses, one per clause it states: a
#: traversal document, a prose locator carrying no `#` at all, a second `#`
#: inside the heading, a line break inside the heading, an empty heading.
REFUSED_LOCATORS = (
    "../outside/DESIGN.md#Slice 1",
    "the design section named in the architecture document",
    "docs/DESIGN.md#Slice # 1",
    "docs/DESIGN.md#Slice\n1",
    "docs/DESIGN.md#",
)

#: The word the refusal carries today, and the one the statement must name, so
#: the architect can recognise the terminal it is being taught to avoid.
REFUSAL = "DesignFactsUnsafeLocator"


def statement(root: Path) -> str:
    """The generated statement as the architect reads it, markers included."""
    text = (root / ARCHITECT_SPEC).read_text()
    start = text.index(f"<!-- GENERATED:{GRAMMAR_REGION} START")
    end = text.index(f"<!-- GENERATED:{GRAMMAR_REGION} END -->", start)
    return text[start:end]


def test_the_architect_turn_ships_the_locator_grammar_that_refuses_it(
    root: Path, step, turns: Path
) -> None:
    """The rule the decoder enforces is READABLE where the field is authored.

    Measured today: an architect that answers `authority_locator` with a
    traversal or a prose sentence ends the whole design turn
    `Indeterminate / ModelEnvelopeUnavailable / DesignFactsUnsafeLocator`, and
    the grammar that produced that refusal is stated in no surface the role
    reads -- so the turn is paid for, refused, and teaches nothing.

    Two halves of ONE fact are measured here, and only together.  The
    architect's own spec, IN THE CHECKOUT A REAL STEP RESOLVES IT FROM, carries
    a generated statement of the `<document>#<heading>` grammar, naming the
    refusal it produces and the empty answer it admits.  And a real `des design`
    turn REFUSES exactly the shapes that statement calls ill-formed and BINDS
    the empty one it calls admissible.  A statement that drifted from the rule
    would leave one half green and the other red; that is what makes this an
    oracle rather than a prose check.
    """
    decomposed(root, step)

    published = statement(root)
    spec = (root / ARCHITECT_SPEC).read_text()
    # ONE projection of this fact, at the point the field is authored: a second
    # copy elsewhere is a second thing to keep true.
    assert spec.count(f"GENERATED:{GRAMMAR_REGION} START") == 1
    assert spec.index(AUTHORING_PARAGRAPH) < spec.index(
        f"<!-- GENERATED:{GRAMMAR_REGION} START"
    )
    # The marker declares WHERE the body came from, and it is the module that
    # also decides admissibility -- not a hand-written paraphrase of it.
    assert GRAMMAR_SOURCE_MODULE in published.splitlines()[0]
    body = published.partition("-->\n")[2]
    assert body.strip()
    # The grammar itself, the refusal it produces, and the empty answer a
    # provider-authored fact set carries while no section identity is assigned.
    assert "#" in body
    assert REFUSAL in body
    assert "empty" in body.lower()

    # The same rule, as the step actually enforces it on a paid turn.
    for locator in REFUSED_LOCATORS:
        answer = design_facts(authority_locator=locator)
        code, out, err = step(
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[answer, answer, answer],
        )
        assert code != 0, f"{locator!r} was admitted: {out + err}"
        assert REFUSAL in out + err, f"{locator!r} refused for another reason"
        assert authority(root) is None, f"{locator!r} became bound DesignFacts"

    # And the one answer the statement admits still binds, so the published
    # empty-string case is honest rather than a rule stated and not held.
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[design_facts(authority_locator="")],
    )
    assert code == 0, out + err
    assert authority(root)["oracle"] == ORACLE
    assert asked(turns)[0] == "nw-product-owner"
    assert set(asked(turns)[1:]) == {"nw-solution-architect"}


def test_the_design_terminal_states_what_the_algebra_obligation_rests_on(
    root: Path, step
) -> None:
    """Section 1a item 6, said out loud in both directions.

    Discord feedback, 2026-09-05: a tool absent without a warning. Algebra-driven
    design is a non-inferiority obligation, and whether anything can CHECK it
    mechanically is a fact about this environment, not about this Request. A
    terminal that stays silent teaches the reader that silence means met.
    """
    decomposed(root, step)
    code, out, err = step(
        "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
    )
    assert code == 0, out + err
    line = block(out, err)["ALGEBRA"]
    assert "Section 1a item 6" in line
    assert ("INDETERMINATE" in line) or ("on PATH" in line)
