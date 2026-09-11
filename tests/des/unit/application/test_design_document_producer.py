import json
from dataclasses import replace
from pathlib import Path

from des.application.design_document_producer import publish_design_document
from des.application.handover import Blocked
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
            }
        )
    )


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
        replace_current=True,
        authority_locator="docs/authority.md#Widget",
    )

    assert isinstance(result, Blocked)
    assert result.what == "DesignAuthorityUnavailable"
    assert not result.refusal and not result.retry
    assert destination.read_bytes() == updated.markdown().encode()
