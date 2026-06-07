"""Shared roadmap parsing helpers.

These pure helpers normalize over the two historical roadmap formats:

- **Flat** — top-level ``steps`` list with ``id`` or ``step_id`` keys.
- **Nested** — top-level ``phases`` list, each phase containing a ``steps`` list.

Extracted 2026-05-03 to eliminate the duplicated ``_extract_step_ids``
implementations in ``cli/verify_deliver_integrity.py`` and
``domain/deliver_progress_tracker.py`` (RPP L3).

Both formats accept either ``id`` or ``step_id`` as the step identifier
key — the helper falls back to whichever is present.
"""

from __future__ import annotations


def extract_step_ids(roadmap: dict) -> list[str]:
    """Return ordered step IDs from a roadmap dict, supporting flat or nested.

    Args:
        roadmap: Parsed roadmap.json content. Supports either:
            * ``{"steps": [{"id": "01-01"}, ...]}`` (flat)
            * ``{"phases": [{"steps": [{"id": "01-01"}, ...]}, ...]}`` (nested)

    Returns:
        Step IDs in document order. Empty list if neither format applies or
        no steps carry an ``id``/``step_id`` field.
    """
    if "steps" in roadmap:
        return [
            s.get("id") or s.get("step_id")
            for s in roadmap["steps"]
            if s.get("id") or s.get("step_id")
        ]
    step_ids: list[str] = []
    for phase in roadmap.get("phases", []):
        for step in phase.get("steps", []):
            step_id = step.get("id") or step.get("step_id")
            if step_id:
                step_ids.append(step_id)
    return step_ids
