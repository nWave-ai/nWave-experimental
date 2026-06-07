"""Pytest fixtures for fix-slice-id-regex-suffix-support carpaccio slice.

Driving port: `verify_slice_commit_completeness._SLICE_ID_TRAILER_RE` regex
object — loaded via direct import (composition-root) per Mandate-13: ATs
drive via the function-level regex extraction, NEVER via internal field
introspection.
"""

from __future__ import annotations

import re

import pytest


@pytest.fixture
def trailer_regex() -> re.Pattern[str]:
    """Load the production trailer regex from verify_slice_commit_completeness."""
    from des.cli.verify_slice_commit_completeness import _SLICE_ID_TRAILER_RE

    return _SLICE_ID_TRAILER_RE


class ExtractionComposition:
    """Composition root for the trailer extraction service.

    Wraps the production regex's `re.match(body).group(1)` shape so step
    bodies stay ≤2 statements per Mandate-12.
    """

    def __init__(self, regex: re.Pattern[str]) -> None:
        self._regex = regex
        self._body: str = ""
        self._extracted: str | None = None

    def stage_body(self, body: str) -> None:
        self._body = body

    def extract(self) -> None:
        match = self._regex.match(self._body)
        self._extracted = match.group(1) if match else None

    @property
    def extracted(self) -> str | None:
        return self._extracted


@pytest.fixture
def extraction(trailer_regex: re.Pattern[str]) -> ExtractionComposition:
    return ExtractionComposition(trailer_regex)
