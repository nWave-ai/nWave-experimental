"""GherkinKeywordPort — RED scaffold."""

from __future__ import annotations

from typing import Protocol


__SCAFFOLD__ = True


class GherkinKeywordPort(Protocol):
    def load_keywords(self, lang: str) -> tuple: ...
    def probe(self) -> None: ...
