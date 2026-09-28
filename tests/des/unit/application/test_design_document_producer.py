import hashlib
import json
from dataclasses import replace
from pathlib import Path

from des.application.design_document_producer import (
    DesignAuthorityBinding,
    DesignPublicationWidenings,
    PublishedDesignDocument,
    publish_design_document,
)
from des.application.handover import Blocked, replace_exact_bytes
from des.domain.design_document import DesignDocument


def _document() -> DesignDocument:
    return DesignDocument.from_json(
        json.dumps(
            {
                "schema_version": 1,
                "authority": {"heading": "Widget"},
                "purpose": "Expose Widget.",
                "constraints": ["Preserve callers."],
                "targets": [
                    {"path": "src/widget.py", "decision": "EXTEND", "reason": "Owner."}
                ],
                "paradigm": "object_oriented",
                "decisions": ["Keep ownership."],
                "reuse_analysis": {"candidates": []},
                "prefactoring": {
                    "applicability": "applicable",
                    "existing_oracle": "tests/test_widget.py",
                    "move": "Extract lookup.",
                    "preserved_observation": "Widget remains visible.",
                },
                "agreement_analysis": {
                    "applicability": "not_applicable",
                    "reason": "No shared contract is touched.",
                },
                "boundaries": {"applicability": "not_applicable", "reason": "None."},
                "public_oracle": {
                    "observation": "Widget is visible.",
                    "stimulus": "Run widget.",
                    "expected": "Widget prints.",
                    "falsifier": "Widget does not print.",
                },
                "oracle": "tests/test_widget.py::test_widget",
                "acceptance_supports": [],
                "verification": [["pytest", "-q"]],
                "oracle_verification_index": 0,
            }
        )
    )


def _append_to(tmp_path: Path, monkeypatch, existing: bytes) -> bytes:
    destination = tmp_path / "docs" / "authority.md"
    destination.parent.mkdir()
    destination.write_bytes(existing)
    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )

    result = publish_design_document(tmp_path, "docs/authority.md", _document())

    assert not isinstance(result, Blocked), result
    return destination.read_bytes()


def test_appending_after_a_single_newline_inserts_one_blank_line(
    tmp_path: Path, monkeypatch
) -> None:
    """The appended H2 is preceded by exactly one blank line, as markdownlint requires."""
    existing = b"# Architecture authority\n\nHuman text.\n"

    rendered = _append_to(tmp_path, monkeypatch, existing)

    assert rendered == existing + b"\n" + _document().markdown().encode()


def test_appending_after_a_blank_line_adds_only_the_section(
    tmp_path: Path, monkeypatch
) -> None:
    existing = b"# Architecture authority\n\nHuman text.\n\n"

    rendered = _append_to(tmp_path, monkeypatch, existing)

    assert rendered == existing + _document().markdown().encode()


def test_directory_destination_is_refused_before_reading(tmp_path: Path) -> None:
    destination = tmp_path / "docs" / "authority.md"
    destination.mkdir(parents=True)

    result = publish_design_document(tmp_path, "docs/authority.md", _document())

    assert isinstance(result, Blocked)
    assert result.what == "UnsafeDesignDestination"
    assert result.refusal


def test_dangling_symlink_destination_is_refused_without_target_write(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "docs" / "authority.md"
    destination.parent.mkdir()
    target = destination.parent / "generated-target.md"
    destination.symlink_to(target.name)

    result = publish_design_document(tmp_path, "docs/authority.md", _document())

    assert isinstance(result, Blocked)
    assert result.what == "UnsafeDesignDestination"
    assert result.refusal
    assert destination.is_symlink()
    assert not target.exists()


def test_directory_sync_failure_reports_indeterminate_after_whole_authority_replace(
    tmp_path: Path, monkeypatch
) -> None:
    """Rename completed, so the caller must not claim rollback or a retry-safe no-op."""
    destination = tmp_path / "docs" / "authority.md"
    destination.parent.mkdir()
    original = _document()
    destination.write_bytes(original.markdown().encode())
    updated = replace(original, purpose="Expose corrected Widget.")

    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )
    monkeypatch.setattr(
        "des.application.handover._fsync_directory",
        lambda _path, **_kwargs: Blocked(
            "DesignAuthorityUnavailable", "fsync failed", "repair"
        ),
    )

    result = publish_design_document(
        tmp_path,
        "docs/authority.md",
        updated,
        widenings=DesignPublicationWidenings(replace_current=True),
        binding=DesignAuthorityBinding(authority_locator="docs/authority.md#Widget"),
    )

    assert isinstance(result, Blocked)
    assert result.what == "DesignAuthorityUnavailable"
    assert not result.refusal and not result.retry
    assert destination.read_bytes() == updated.markdown().encode()


def _seed(tmp_path: Path, contents: bytes) -> Path:
    destination = tmp_path / "docs" / "authority.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    return destination


def test_unterminated_prefix_gains_a_separator_before_the_owned_heading(
    tmp_path: Path, monkeypatch
) -> None:
    """Appending supplies only the missing separator, so the heading remains resolvable."""
    document = _document()
    destination = _seed(tmp_path, b"# Authority\n\nUnterminated human line.")
    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )

    result = publish_design_document(tmp_path, "docs/authority.md", document)

    assert not isinstance(result, Blocked)
    assert result.locator == "docs/authority.md#Widget"
    assert destination.read_bytes() == (
        b"# Authority\n\nUnterminated human line.\n\n" + document.markdown().encode()
    ), (
        "the renderer preserves every human byte and inserts only the separator "
        "needed for an owned H2 to begin on its own line"
    )


def test_legacy_rendering_migration_refuses_a_section_that_is_not_byte_identical(
    tmp_path: Path, monkeypatch
) -> None:
    """An explicit renderer migration is not a general unbound replacement."""
    document = _document()
    original = document.legacy_markdown_v1().replace(
        "Expose Widget.", "Altered Widget."
    )
    destination = _seed(tmp_path, original.encode())
    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )

    result = publish_design_document(
        tmp_path,
        "docs/authority.md",
        document,
        widenings=DesignPublicationWidenings(migrate_legacy_rendering=True),
    )

    assert isinstance(result, Blocked)
    assert result.what == "DesignAuthorityDrift" and result.refusal
    assert destination.read_text() == original


def test_read_back_that_cannot_be_decoded_stays_indeterminate(
    tmp_path: Path, monkeypatch
) -> None:
    """The substrate did not answer intelligibly, so the step must not say no."""
    document = _document()
    _seed(tmp_path, document.markdown().encode())
    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )
    read_bytes = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda self: (
            b"\xff\xfe not utf-8" if self.name == "authority.md" else read_bytes(self)
        ),
    )

    result = publish_design_document(tmp_path, "docs/authority.md", document)

    assert isinstance(result, Blocked)
    assert result.what == "DesignAuthorityUnavailable" and not result.refusal, (
        "undecodable authority bytes are a substrate failure, not a decision that "
        f"the declared section is absent; got {result.what!r} refusal={result.refusal}"
    )


def test_digest_measures_the_bytes_on_disk_rather_than_the_rendered_buffer(
    tmp_path: Path, monkeypatch
) -> None:
    """A concurrent edit elsewhere is reported truthfully by the digest, not refused."""
    document = _document()
    destination = _seed(tmp_path, b"# Authority\n\n")
    monkeypatch.setattr(
        "des.application.design_document_producer._tracked", lambda _root, _path: True
    )

    def concurrent_human_append(path, existing, rendered, **kwargs):
        outcome = replace_exact_bytes(path, existing, rendered, **kwargs)
        path.write_bytes(path.read_bytes() + b"\n## Human appendix\n\nAdded.\n")
        return outcome

    monkeypatch.setattr(
        "des.application.design_document_producer.replace_exact_bytes",
        concurrent_human_append,
    )

    result = publish_design_document(tmp_path, "docs/authority.md", document)

    assert isinstance(result, PublishedDesignDocument), (
        "the read-back judges RESOLUTION only; an unrelated concurrent edit must "
        f"not be refused; got {result!r}"
    )
    assert result.digest == hashlib.sha256(destination.read_bytes()).hexdigest(), (
        "DOCUMENT-SHA256 must measure the file a consumer will read, never "
        "restate the buffer this step intended to write"
    )
    assert result.locator == "docs/authority.md#Widget"
    assert result.authority_persisted, (
        "authority_persisted still means 'this invocation changed the file'"
    )
