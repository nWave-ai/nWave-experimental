"""Persistence-boundary protections for DEVOPS operational documents."""

from __future__ import annotations

import json
from pathlib import Path

from des.application.handover import Blocked
from des.application.operational_document_producer import publish_operational_document
from des.domain.operational_document import OperationalDocument


DESTINATION = "docs/product/operations/brief.md"


def _document() -> OperationalDocument:
    return OperationalDocument.from_json(
        json.dumps(
            {
                "schema_version": 1,
                "authority": {"heading": "Widget operations"},
                "purpose": "Operate Widget safely.",
                **{
                    name: {
                        "applicability": "not_applicable",
                        "reason": "This concern is managed outside Widget.",
                        "obligations": [],
                    }
                    for name in (
                        "environment",
                        "deployment",
                        "recovery",
                        "observability",
                    )
                },
            }
        )
    )


def test_ambiguous_existing_heading_is_refused_without_artifact_changes(
    tmp_path: Path,
) -> None:
    authority = tmp_path / DESTINATION
    sidecar = authority.with_suffix(".operational-facts.json")
    authority.parent.mkdir(parents=True)
    authority.write_text("## Widget operations\n\nold\n## Widget operations\n\nold\n")
    sidecar.write_bytes(b"existing facts")
    before = authority.read_bytes(), sidecar.read_bytes()

    result = publish_operational_document(tmp_path, DESTINATION, _document())

    assert (
        isinstance(result, Blocked)
        and result.what == "OperationalAuthorityAmbiguous"
        and result.refusal
    ), (
        "duplicate DEVOPS headings must refuse because ownership cannot be selected uniquely"
    )
    assert (authority.read_bytes(), sidecar.read_bytes()) == before, (
        "an ambiguous authority must leave both persisted DEVOPS artifacts byte-identical"
    )


def test_divergent_existing_sidecar_is_refused_before_markdown_append(
    tmp_path: Path,
) -> None:
    authority = tmp_path / DESTINATION
    sidecar = authority.with_suffix(".operational-facts.json")
    authority.parent.mkdir(parents=True)
    authority.write_text("# Existing operational notes\n")
    sidecar.write_bytes(b"divergent facts")
    before = authority.read_bytes(), sidecar.read_bytes()

    result = publish_operational_document(tmp_path, DESTINATION, _document())

    assert (
        isinstance(result, Blocked)
        and result.what == "OperationalFactsDrift"
        and result.refusal
    ), (
        "a divergent facts sidecar must refuse rather than append Markdown without its matching facts"
    )
    assert (authority.read_bytes(), sidecar.read_bytes()) == before, (
        "a sidecar refusal must preserve the authority and sidecar bytes as one artifact pair"
    )


def test_sidecar_write_failure_reports_possible_partial_markdown_change(
    tmp_path: Path, monkeypatch
) -> None:
    authority = tmp_path / DESTINATION
    sidecar = authority.with_suffix(".operational-facts.json")
    original_write_bytes = Path.write_bytes

    def fail_sidecar_write(path: Path, content: bytes) -> int:
        if path == sidecar:
            raise OSError("sidecar storage failed")
        return original_write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail_sidecar_write)

    result = publish_operational_document(tmp_path, DESTINATION, _document())

    assert isinstance(result, Blocked)
    assert result.what == "OperationalAuthorityUnavailable"
    assert "writing OperationalFacts sidecar failed" in result.why
    assert (
        "Markdown authority and/or OperationalFacts sidecar may already have changed"
        in result.why
    )
    assert "sidecar storage failed" in result.why
    assert authority.read_bytes() == _document().markdown().encode(), (
        "the Markdown write has already persisted when the subsequent sidecar write fails"
    )
    assert not sidecar.exists(), (
        "the injected sidecar write failure leaves no sidecar artifact"
    )


def test_multiline_semantic_content_cannot_create_owned_markdown_structure(
    tmp_path: Path,
) -> None:
    value = _document()
    raw = value.facts(DESTINATION)
    raw["purpose"] = (
        "First line\n## Unrelated-looking heading\r## Carriage-return heading\nLast line"
    )
    raw["environment"] = {
        "applicability": "applicable",
        "reason": "Reason first\n### Not a section\r### Carriage-return section",
        "obligations": [
            {
                "id": "id|cell",
                "requirement": "Need\n## not heading",
                "verification": "Check|cell",
                "owner": "team\nowner",
            }
        ],
    }
    document = OperationalDocument.from_json(
        json.dumps(
            {
                "schema_version": 1,
                "authority": {"heading": "Widget operations"},
                "purpose": raw["purpose"],
                **{
                    name: raw[name]
                    for name in (
                        "environment",
                        "deployment",
                        "recovery",
                        "observability",
                    )
                },
            }
        )
    )

    first = publish_operational_document(tmp_path, DESTINATION, document)
    authority = tmp_path / DESTINATION
    sidecar = authority.with_suffix(".operational-facts.json")
    before = authority.read_bytes(), sidecar.read_bytes()
    second = publish_operational_document(tmp_path, DESTINATION, document)

    assert not isinstance(first, Blocked) and not isinstance(second, Blocked)
    assert (authority.read_bytes(), sidecar.read_bytes()) == before
    text = authority.read_text()
    for injected in (
        "## Unrelated-looking heading",
        "## Carriage-return heading",
        "### Not a section",
        "### Carriage-return section",
    ):
        assert f"    {injected}" in text
        assert not any(
            line.lstrip(" ") == injected and len(line) - len(line.lstrip(" ")) <= 3
            for line in text.splitlines()
        ), "CommonMark recognizes ATX headings with up to three leading spaces"
    assert "Need<br>## not heading" in text and "id\\|cell" in text
    assert json.loads(sidecar.read_text()) == document.facts(DESTINATION)
