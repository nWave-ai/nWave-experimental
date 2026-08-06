"""Pytest collection policy for installer acceptance tests."""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Serialize process-global installer acceptance fixtures under xdist."""
    suite_dir = Path(__file__).parent
    group = pytest.mark.xdist_group("installer_walking_skeleton")
    for item in items:
        item_path = getattr(item, "path", None)
        if item_path is None:
            continue
        if suite_dir in Path(item_path).parents or Path(item_path) == suite_dir:
            item.add_marker(group)
