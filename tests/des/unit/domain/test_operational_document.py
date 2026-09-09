"""Closed OperationalDocument v1 grammar and canonical-facts laws."""

from __future__ import annotations

import json

import pytest

from des.domain.operational_document import (
    OperationalDocument,
    OperationalDocumentInvalid,
    operational_facts_from_json,
)


def _input() -> dict[str, object]:
    return {
        "schema_version": 1,
        "authority": {"heading": "  Widget operations  "},
        "purpose": "  Operate Widget safely.  ",
        "environment": {
            "applicability": "applicable",
            "reason": "  The service has a runtime.  ",
            "obligations": [
                {
                    "id": "  runtime  ",
                    "requirement": "  Pin the runtime.  ",
                    "verification": "  Inspect the deployed runtime.  ",
                    "owner": "  platform  ",
                }
            ],
        },
        "deployment": {
            "applicability": "not_applicable",
            "reason": "  Releases are managed elsewhere.  ",
            "obligations": [],
        },
        "recovery": {
            "applicability": "not_applicable",
            "reason": "  This service stores no state.  ",
            "obligations": [],
        },
        "observability": {
            "applicability": "not_applicable",
            "reason": "  Monitoring is owned by the platform.  ",
            "obligations": [],
        },
    }


def test_closed_v1_input_normalizes_text_into_canonical_facts() -> None:
    document = OperationalDocument.from_json(json.dumps(_input()))

    assert document.facts("docs/operations/widget.md") == {
        "schema_version": 1,
        "authority": {
            "destination": "docs/operations/widget.md",
            "heading": "Widget operations",
        },
        "purpose": "Operate Widget safely.",
        "environment": {
            "applicability": "applicable",
            "reason": "The service has a runtime.",
            "obligations": [
                {
                    "id": "runtime",
                    "requirement": "Pin the runtime.",
                    "verification": "Inspect the deployed runtime.",
                    "owner": "platform",
                }
            ],
        },
        "deployment": {
            "applicability": "not_applicable",
            "reason": "Releases are managed elsewhere.",
            "obligations": [],
        },
        "recovery": {
            "applicability": "not_applicable",
            "reason": "This service stores no state.",
            "obligations": [],
        },
        "observability": {
            "applicability": "not_applicable",
            "reason": "Monitoring is owned by the platform.",
            "obligations": [],
        },
    }, (
        "whitespace-equivalent closed input must normalize once into the facts PO consumes"
    )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda value: value.update({"unknown": True}),
            "input must contain exactly",
        ),
        (
            lambda value: value["environment"].update(  # type: ignore[index,union-attr]
                {"obligations": []}
            ),
            "non-empty exactly when applicable",
        ),
    ],
)
def test_closed_v1_input_refuses_unknown_or_incoherent_section_grammar(
    mutate: object, expected: str
) -> None:
    value = _input()
    mutate(value)  # type: ignore[operator]

    with pytest.raises(OperationalDocumentInvalid, match=expected):
        OperationalDocument.from_json(json.dumps(value))


@pytest.mark.parametrize("surrogate_codepoint", (0xD800, 0xDCFF))
@pytest.mark.parametrize(
    "replace",
    (
        lambda value, text: value["authority"].update({"heading": text}),  # type: ignore[index,union-attr]
        lambda value, text: value.update({"purpose": text}),
        lambda value, text: value["environment"].update({"reason": text}),  # type: ignore[index,union-attr]
        lambda value, text: value["environment"]["obligations"][0].update(  # type: ignore[index,union-attr]
            {"id": text}
        ),
        lambda value, text: value["environment"]["obligations"][0].update(  # type: ignore[index,union-attr]
            {"requirement": text}
        ),
        lambda value, text: value["environment"]["obligations"][0].update(  # type: ignore[index,union-attr]
            {"verification": text}
        ),
        lambda value, text: value["environment"]["obligations"][0].update(  # type: ignore[index,union-attr]
            {"owner": text}
        ),
    ),
)
def test_closed_v1_input_refuses_lone_surrogates_in_required_semantic_text(
    surrogate_codepoint: int, replace: object
) -> None:
    value = _input()
    replace(value, chr(surrogate_codepoint))  # type: ignore[operator]

    with pytest.raises(OperationalDocumentInvalid, match="UTF-8"):
        OperationalDocument.from_json(json.dumps(value))


def test_closed_v1_input_retains_supplementary_unicode_in_utf8_facts() -> None:
    value = _input()
    value["purpose"] = "Operate Widget safely with operator approval 🚀."

    document = OperationalDocument.from_json(json.dumps(value, ensure_ascii=False))

    assert document.facts_bytes("docs/operations/widget.md") == json.dumps(
        document.facts("docs/operations/widget.md"),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8"), (
        "valid supplementary Unicode must remain accepted and facts must serialize as "
        "strict UTF-8 bytes, so surrogate rejection is not an arbitrary text restriction"
    )


def test_operational_facts_requires_exact_canonical_json_and_safe_destination() -> None:
    document = OperationalDocument.from_json(json.dumps(_input()))
    canonical = document.facts_bytes("docs/operations/widget.md").decode()

    assert operational_facts_from_json(canonical) == document.facts(
        "docs/operations/widget.md"
    ), "a canonical facts sidecar must round-trip to the normalized prompt fact"
    with pytest.raises(OperationalDocumentInvalid, match="not canonical"):
        operational_facts_from_json(json.dumps(json.loads(canonical)))
    for destination in ("../outside.md", "docs/operations/facts.txt"):
        unsafe = json.loads(canonical)
        unsafe["authority"]["destination"] = destination
        with pytest.raises(OperationalDocumentInvalid, match="repository-relative .md"):
            operational_facts_from_json(
                json.dumps(unsafe, ensure_ascii=False, separators=(",", ":"))
            )
