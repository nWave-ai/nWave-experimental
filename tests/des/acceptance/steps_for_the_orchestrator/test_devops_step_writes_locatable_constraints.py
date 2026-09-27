"""Public oracle: `des devops`, the OPTIONAL step upstream of decomposition.

`F-DEVOPS-CONSTRAINTS-INTO-DISTILL` (docs/product/backlog.md) states the
decision it implements: «DEVOPS e' opzionale ... MA quando e' richiesto, il suo
prodotto non e' un saggio: deve generare VINCOLI consumati dal Product Owner e
dall'acceptance designer in DISTILL, cosi' che l'infrastruttura abbia oracoli
eseguibili che ne verificano l'implementazione, e passi dall'EXAMINE come il
resto del codice.»  The same row names what was missing, and item (3) of it is
the falsifier this step is built around: «verifica che il resolver dell'autorita'
legga le sezioni che DEVOPS scrive».

So the step does not merely record that a turn happened. It RESOLVES its own
product through `resolve_authority_section` -- the identical function the
architect will later cite that section by -- and refuses when the turn left
something the downstream reader cannot find. A constraint that no locator
reaches is an essay, which is exactly what the backlog row forbids.

NO DEVOPS ROLE INSIDE THE RUNNER, per the same row: «Nessun ruolo devops nel
runner: la verifica dell'infra e' un valore come gli altri.»  This step runs
BEFORE `des po`, writes durable authority, and hands back locators. The
constraints then become ordinary values, ordinary oracles and ordinary EXAMINE.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "the deployed service must report its own health on a documented endpoint"
AUTHORITY = "docs/product/architecture/operational-authority.md"
SECTION = "Operational constraints"
HANDOVER = Path(".nwave") / "des" / "handover.json"

CONSTRAINTS = (
    "# Operational authority\n"
    "\n"
    "## Operational constraints\n"
    "\n"
    "- The service exposes `/healthz` returning 200 within 500 ms of a cold start.\n"
    "- A failed dependency is reported as 503 with the dependency named.\n"
)


def seeded(root: Path) -> None:
    """The tracked authority file the turn writes a section INTO, committed."""
    path = root / AUTHORITY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Operational authority\n")
    git(root, "add", AUTHORITY)
    git(root, "commit", "-qm", "seed the operational authority")


def turn(
    body: str = CONSTRAINTS, diagnostic: str = "declared two operational constraints"
) -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": diagnostic},
        "writes": {AUTHORITY: body},
    }


def devops(root: Path, step, answers: list[dict]):
    return step(
        "devops",
        "--repo-root",
        str(root),
        "--project",
        "--authority",
        AUTHORITY,
        "--section",
        SECTION,
        answers=answers,
        stdin=REQUEST,
    )


def test_an_accepted_turn_returns_a_locator_the_resolver_can_read(
    root: Path, step, turns: Path
) -> None:
    seeded(root)
    code, out, err = devops(root, step, [turn()])
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["CONSTRAINTS"] == f"{AUTHORITY}#{SECTION}"
    assert "declared two operational constraints" in lines["DIAGNOSTIC"]
    assert "/healthz" in (root / AUTHORITY).read_text()
    assert asked(turns) == ["nw-platform-architect"]
    assert nexts(out)[0].startswith(f"des po --repo-root {root}")
    # The locator the step hands back is the one the Request must carry, so the
    # NEXT line names it rather than leaving the orchestrator to retype it.
    assert f"{AUTHORITY}#{SECTION}" in " ".join(nexts(out))


def test_a_turn_whose_section_the_resolver_cannot_find_is_refused(
    root: Path, step, turns: Path
) -> None:
    """The falsifier from the backlog row: a constraint no locator reaches."""
    seeded(root)
    code, out, err = devops(
        root,
        step,
        [turn("# Operational authority\n\n## Something else entirely\n\n- a note\n")],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "ConstraintsUnlocatable"
    assert SECTION in lines["WHY"]
    assert asked(turns) == ["nw-platform-architect"]


def test_an_empty_section_is_refused_because_an_essay_is_not_a_constraint(
    root: Path, step
) -> None:
    seeded(root)
    code, out, err = devops(
        root, step, [turn("# Operational authority\n\n## Operational constraints\n")]
    )
    assert code == 1
    assert block(out, err)["WHAT"] == "ConstraintsEmpty"


def test_a_turn_that_writes_outside_the_declared_authority_is_refused(
    root: Path, step
) -> None:
    seeded(root)
    answer = turn()
    answer["writes"]["src/sneaky.py"] = "VALUE = 1\n"
    code, out, err = devops(root, step, [answer])
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "ConstraintScopeDrift"
    assert "src/sneaky.py" in lines["WHY"]


def test_a_rejecting_turn_forwards_its_words_and_writes_no_authority(
    root: Path, step
) -> None:
    seeded(root)
    before = (root / AUTHORITY).read_text()
    code, out, err = devops(
        root,
        step,
        [
            {
                "structured_output": {
                    "outcome": "rejected",
                    "diagnostic": "this project deploys nothing, so no operational constraint applies",
                }
            }
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Refusal"
    assert "deploys nothing" in lines["DIAGNOSTIC"]
    assert (root / AUTHORITY).read_text() == before


def test_constraints_after_a_decomposition_are_accepted_and_counted(
    root: Path, step, turns: Path
) -> None:
    """ADR-DES-003 §2.5: the refusal claimed content on an argument, no incident.

    Writing constraints after a decomposition is an admissible order. What the
    orchestrator needs is not a veto but the FACT that those values were
    decomposed without these constraints in front of the Product Owner, so the
    step measures it and accepts.
    """
    seeded(root)
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            "--project",
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    spent = len(asked(turns))
    code, out, err = devops(root, step, [turn()])
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DECOMPOSED-BEFORE"] == "1"
    assert lines["CONSTRAINTS"] == f"{AUTHORITY}#{SECTION}"
    assert len(asked(turns)) == spent + 1


def test_an_authority_that_is_not_repo_local_markdown_is_refused_first(
    root: Path, step, turns: Path
) -> None:
    code, out, err = step(
        "devops",
        "--repo-root",
        str(root),
        "--project",
        "--authority",
        "../escape.md",
        "--section",
        SECTION,
        answers=[turn()],
        stdin=REQUEST,
    )
    assert code == 1
    assert block(out, err)["WHAT"] == "AuthorityInadmissible"
    assert asked(turns) == []
