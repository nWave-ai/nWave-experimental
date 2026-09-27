"""The terminal projection states the boundary of what it measured, in one place.

The acceptance corpus measures this observation end-to-end through the public
driving port. This corpus pins the PROJECTION ITSELF, which is where the property
actually lives: ``_terminal`` is the single point every verdict passes through,
so a boundary built there is inherited by construction rather than by each branch
remembering to add one.

Two things are worth pinning here that an end-to-end run states only implicitly:

* the known/unknown distinction is carried by ONE parameter, the declaration
  itself, so "the contract is known while the population is UNKNOWN" -- and its
  reverse -- is UNREPRESENTABLE rather than merely avoided;
* nothing in the boundary is measured by reading the tree: the same declaration
  object yields the same ``in_reach`` whatever the repository contains, and
  ``out_of_reach.count`` is never a number.
"""

from __future__ import annotations

from pathlib import Path

from des.application.agreement_crossing import (
    BOUNDARY_LEAD_IN,
    OUT_OF_REACH_RULE,
    UNKNOWN,
    WIDEN_ACTION,
    _terminal,
    cross_agreement,
)
from des.domain.agreement_declaration import AgreementDeclaration, DeclaredParty


DECLARATION = "schemas/agreements/some-contract.json"
REPO_ROOT = "/somewhere/a/repository"


def _declaration(*names: str) -> AgreementDeclaration:
    """A declaration of ``names``, built in memory: no tree is ever consulted."""
    return AgreementDeclaration(
        schema_version=2,
        contract="some.contract.v1",
        producer=DeclaredParty(name="the.producer", argv=("build", "{artifact}")),
        consumers=tuple(
            DeclaredParty(name=name, argv=("read", "{artifact}")) for name in names
        ),
    )


def _projected(declared: AgreementDeclaration | None):
    return _terminal(
        exit_code=0,
        payload={"verdict": "AgreementCrossed"},
        human="a verdict",
        census=[],
        verified_consumers=0,
        repo_root=REPO_ROOT,
        declaration=DECLARATION,
        declared=declared,
    )


def test_every_terminal_carries_a_closed_scope_derived_from_the_declaration_it_was_given():
    """The shape is CLOSED and every field comes from THIS run, not a banner."""
    outcome = _projected(_declaration("first.reader", "second.reader"))
    scope = outcome.payload["scope"]

    assert set(scope) == {
        "declaration",
        "contract",
        "measured",
        "out_of_reach",
        "widen_by",
    }
    assert scope["declaration"] == DECLARATION
    assert scope["contract"] == "some.contract.v1"
    assert scope["measured"] == (
        f"2 declared consumer(s) of some.contract.v1, listed in {DECLARATION}"
    )

    # THE BOUNDARY IS STATED BY ENUMERATING ITS INSIDE, in declaration order,
    # and by carrying the PREDICATE a machine reader applies to the outside.
    assert scope["out_of_reach"] == {
        "rule": OUT_OF_REACH_RULE,
        "in_reach": ["first.reader", "second.reader"],
        "count": UNKNOWN,
    }
    # NEVER a number, and `0` least of all: that would assert nobody else reads
    # the contract, which no executable crossing can ever establish.
    assert not isinstance(scope["out_of_reach"]["count"], int)

    # A STATED LIMIT AN OPERATOR CAN ACT ON: the one file that decides the
    # population, and the exact command that re-runs THIS crossing.
    assert scope["widen_by"] == {
        "action": WIDEN_ACTION,
        "edit": DECLARATION,
        "rerun": [
            "des",
            "verify-agreement",
            "--repo-root",
            REPO_ROOT,
            "--declaration",
            DECLARATION,
        ],
    }

    # THE HUMAN HALF STATES THE SAME LIMIT, behind the fixed greppable lead-in,
    # collapsed into the single line that sits beside the one JSON object.
    assert (
        f"{BOUNDARY_LEAD_IN} 2 consumer(s) declared in {DECLARATION}; any other "
        f"reader of some.contract.v1 was NOT executed and is counted in no field "
        f"of this outcome." in outcome.human
    )
    assert "\n" not in outcome.human


def test_the_scope_changes_with_the_population_so_it_can_never_be_a_constant_banner():
    """A scope whose bytes do not change is indistinguishable from boilerplate."""
    renderings = {
        repr(_projected(_declaration(*names)).payload["scope"])
        for names in (("one",), ("one", "two"), ("one", "two", "three"))
    }
    assert len(renderings) == 3


def test_where_no_declaration_was_read_the_population_is_unknown_and_no_contract_is_invented():
    """ "I could not find out WHAT to measure" is not "there was nothing to measure"."""
    outcome = _projected(None)
    scope = outcome.payload["scope"]

    assert scope["contract"] == UNKNOWN
    assert scope["measured"] == (
        f"UNKNOWN: the declared population could not be read from {DECLARATION}"
    )
    # With nothing read, the INSIDE of the boundary is empty rather than guessed
    # -- but the count of the outside is still UNKNOWN, never zero.
    assert scope["out_of_reach"]["in_reach"] == []
    assert scope["out_of_reach"]["count"] == UNKNOWN
    assert outcome.payload["declared_consumers"] == 0

    assert (
        f"{BOUNDARY_LEAD_IN} the consumer(s) declared in {DECLARATION}, and that "
        f"population is UNKNOWN because the declaration could not be read; this "
        f"run executed no reader of any contract and counts none in any field of "
        f"this outcome." in outcome.human
    )


def test_a_repository_root_that_is_not_a_directory_is_indeterminate_and_still_states_its_boundary(
    tmp_path: Path,
):
    """The earliest failure there is still says what it could not measure.

    Driven through ``cross_agreement`` rather than the projection, so the claim
    covers a real branch of the crossing and not only the helper it calls. No
    party is spawned: the run cannot get that far.
    """
    not_a_directory = tmp_path / "a-file"
    not_a_directory.write_text("not a repository root", encoding="utf-8")

    outcome = cross_agreement(not_a_directory, DECLARATION)

    assert outcome.exit_code == 2
    assert outcome.payload["verdict"] == "AgreementIndeterminate"
    scope = outcome.payload["scope"]
    assert scope["declaration"] == DECLARATION
    assert scope["contract"] == UNKNOWN
    assert scope["widen_by"]["rerun"][3] == str(not_a_directory), (
        "the re-run command must carry the repository root AS THE OPERATOR GAVE "
        "IT, so it is a command that can be pasted back"
    )
    assert BOUNDARY_LEAD_IN in outcome.human
