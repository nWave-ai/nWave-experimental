from __future__ import annotations

import json
from pathlib import Path

from des.application.evolution_document_producer import publish_evolution_document
from des.application.handover import Blocked
from des.domain.evolution_document import EvolutionDocument


def _document() -> EvolutionDocument:
    return EvolutionDocument.from_json(
        json.dumps(
            {
                "schema_version": 1,
                "date": "2026-09-09",
                "feature_id": "feature-evolution",
                "purpose": "Preserve the completed feature evidence.",
                "key_decisions": ["Use explicit identity."],
                "delivered_work": ["Published the constructor."],
                "verification_results": ["Focused oracle passed."],
                "problems": {
                    "applicability": "not_applicable",
                    "reason": "No problems were encountered.",
                    "items": [],
                },
                "lessons": {
                    "applicability": "not_applicable",
                    "reason": "No new lesson was recorded.",
                    "items": [],
                },
                "durable_artifacts": [
                    {"label": "evidence", "path": "https://example.invalid/run"}
                ],
            }
        )
    )


def test_parent_symlink_destination_refuses_without_writing_outside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "docs").symlink_to(outside, target_is_directory=True)

    result = publish_evolution_document(root, "docs/evolution.md", _document())

    assert isinstance(result, Blocked) and result.what == "UnsafeEvolutionDestination"
    assert not (outside / "evolution.md").exists()


def test_exact_retry_does_not_duplicate_the_explicit_feature_identity(
    tmp_path: Path,
) -> None:
    document = _document()
    first = publish_evolution_document(
        tmp_path, "docs/evolution/2026-09-09-feature-evolution.md", document
    )
    before = (tmp_path / "docs/evolution/2026-09-09-feature-evolution.md").read_bytes()
    second = publish_evolution_document(
        tmp_path, "docs/evolution/2026-09-09-feature-evolution.md", document
    )

    assert not isinstance(first, Blocked) and not isinstance(second, Blocked)
    assert (
        tmp_path / "docs/evolution/2026-09-09-feature-evolution.md"
    ).read_bytes() == before
