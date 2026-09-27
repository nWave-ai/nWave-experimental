import pytest

from des.domain.design_document import DesignDocument, DesignFactsSection
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


ROLE_FACTS = DesignFacts(
    (DesignTarget("src/widget.py", "EXTEND"),),
    "object_oriented",
    ("Keep color validation at Widget construction.",),
    "tests/test_widget.py::test_selected_color",
    (),
    (("pytest", "-q", "tests/test_widget.py"),),
    0,
    ("Preserve existing callers.",),
    "docs/product/architecture/brief.md#Widget color",
)


def test_closed_v1_document_projects_canonical_facts() -> None:
    document = DesignDocument.from_json(
        '{"schema_version":1,"authority":{"heading":"H"},"purpose":"P","constraints":["C"],"targets":[{"path":"src/x.py","decision":"EXTEND","reason":"R"}],"paradigm":"object_oriented","decisions":["D"],"reuse_analysis":{"candidates":[]},"prefactoring":{"applicability":"applicable","existing_oracle":"tests/x.py","move":"M","preserved_observation":"O"},"agreement_analysis":{"applicability":"not_applicable","reason":"N"},"boundaries":{"applicability":"not_applicable","reason":"N"},"public_oracle":{"observation":"O","stimulus":"S","expected":"E","falsifier":"F"},"oracle":"tests/x.py::test_x","acceptance_supports":[],"verification":[["pytest","-q"]],"oracle_verification_index":0}'
    )
    assert (
        document.facts_json()
        == '{"targets":[{"path":"src/x.py","decision":"EXTEND"}],"paradigm":"object_oriented","decisions":["D"],"oracle":"tests/x.py::test_x","acceptance_supports":[],"verification":[["pytest","-q"]],"oracle_verification_index":0,"obligations":["C"]}'
    )
    bound = document.facts_at("docs/architecture.md#H")
    assert bound.authority_locator == "docs/architecture.md#H"
    assert document.facts_json(bound).endswith(
        '"authority_locator":"docs/architecture.md#H"}'
    )


def test_typed_facts_render_the_section_their_own_locator_names() -> None:
    """The role-turn projection is derivable from the typed facts ALONE."""
    section = DesignFactsSection.for_locator(ROLE_FACTS.authority_locator, ROLE_FACTS)

    assert section is not None
    assert section.heading == "Widget color"
    rendered = section.markdown()
    assert rendered.startswith("## Widget color\n")
    assert rendered.endswith("\n")
    missing = {
        fact
        for fact in (
            "Preserve existing callers.",
            "`src/widget.py`",
            "EXTEND",
            "object_oriented",
            "Keep color validation at Widget construction.",
            "`tests/test_widget.py::test_selected_color`",
            "`pytest -q tests/test_widget.py`",
        )
        if fact not in rendered
    }
    assert not missing, (
        "the rendered section must retain every returned typed fact so the "
        f"document and the bound facts are two projections of one turn: {missing!r}"
    )


def test_the_rendered_heading_begins_its_own_line_for_the_consuming_resolver() -> None:
    """A value may bind only to a heading the consumer's resolver can reach."""
    section = DesignFactsSection.for_locator(ROLE_FACTS.authority_locator, ROLE_FACTS)

    assert section is not None
    assert "\n## Widget color\n" in "\n" + section.markdown()


def test_no_field_the_architect_did_not_return_is_invented() -> None:
    """Absent facts leave no subsection; the authority is human-owned."""
    bare = DesignFacts(
        (DesignTarget("src/widget.py", "EXTEND"),),
        "functional",
        (),
        "tests/test_widget.py::test_selected_color",
        (),
        (("pytest",),),
        0,
        (),
        "docs/brief.md#Bare",
    )
    section = DesignFactsSection.for_locator(bare.authority_locator, bare)

    assert section is not None
    rendered = section.markdown()
    assert "### Constraints" not in rendered
    assert "### Decisions" not in rendered
    assert "### Acceptance supports" not in rendered
    assert "### Targets" in rendered and "### Paradigm" in rendered


@pytest.mark.parametrize(
    ("case", "locator"),
    [
        ("no separator", "docs/brief.md"),
        ("empty heading", "docs/brief.md#"),
        ("blank heading", "docs/brief.md#   "),
        ("markdown heading", "docs/brief.md### Widget"),
        ("multiline heading", "docs/brief.md#Widget\ncolor"),
    ],
)
def test_a_locator_naming_no_renderable_section_is_refused_not_guessed(
    case: str, locator: str
) -> None:
    """A heading the role never declared is never invented by this projection."""
    assert DesignFactsSection.for_locator(locator, ROLE_FACTS) is None, (
        f"a {case} locator names no renderable section; returning one would let "
        "the software guess the identity of a human-owned authority section"
    )
