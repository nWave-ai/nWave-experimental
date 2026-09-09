import json
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
