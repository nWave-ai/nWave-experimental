from des.domain.design_document import DesignDocument


def test_closed_v1_document_projects_canonical_facts() -> None:
    document = DesignDocument.from_json(
        '{"schema_version":1,"authority":{"heading":"H"},"purpose":"P","constraints":["C"],"targets":[{"path":"src/x.py","decision":"EXTEND","reason":"R"}],"paradigm":"object_oriented","decisions":["D"],"reuse_analysis":{"candidates":[]},"prefactoring":{"applicability":"applicable","existing_oracle":"tests/x.py","move":"M","preserved_observation":"O"},"agreement_analysis":{"applicability":"not_applicable","reason":"N"},"boundaries":{"applicability":"not_applicable","reason":"N"},"public_oracle":{"observation":"O","stimulus":"S","expected":"E","falsifier":"F"},"oracle":"tests/x.py::test_x","acceptance_supports":[],"verification":[["pytest","-q"]]}'
    )
    assert (
        document.facts_json()
        == '{"targets":[{"path":"src/x.py","decision":"EXTEND"}],"paradigm":"object_oriented","decisions":["D"],"oracle":"tests/x.py::test_x","acceptance_supports":[],"verification":[["pytest","-q"]],"obligations":["C"]}'
    )
    bound = document.facts_at("docs/architecture.md#H")
    assert bound.authority_locator == "docs/architecture.md#H"
    assert document.facts_json(bound).endswith(
        '"authority_locator":"docs/architecture.md#H"}'
    )
