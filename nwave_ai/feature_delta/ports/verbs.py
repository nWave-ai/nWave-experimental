"""VerbListProviderPort — RED scaffold."""

from __future__ import annotations

from typing import Protocol


__SCAFFOLD__ = True


class VerbListProviderPort(Protocol):
    def load_protocol_verbs(self, lang: str) -> tuple: ...
    def load_substantive_verbs(self, lang: str) -> tuple: ...
    def probe(self) -> None: ...
