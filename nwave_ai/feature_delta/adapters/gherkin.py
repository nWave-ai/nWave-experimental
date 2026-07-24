"""PlaintextKeywordLoader — loads Gherkin keyword lists from text files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nwave_ai.feature_delta.adapters.refusal import refuse_startup
from nwave_ai.feature_delta.resources import packaged_resource


if TYPE_CHECKING:
    from pathlib import Path


# A PACKAGE RESOURCE — it travels with the install. Previously resolved by
# walking four `.parent` hops OUT of the package to `nWave/data/`, which exists
# in a source checkout and on no distribution channel.
_KEYWORD_DIR = packaged_resource("data", "gherkin-keywords")


class PlaintextKeywordLoader:
    """Load Gherkin keyword lists from .txt files (one keyword per line)."""

    def load_keywords(self, lang: str) -> tuple[str, ...]:
        """Return Gherkin keywords for `lang` from the packaged keyword list."""
        path = _KEYWORD_DIR / f"{lang}.txt"
        return self._load(path)

    def probe(self) -> None:
        """Startup health check — verify en.txt is accessible and non-empty.

        Refuses LOUDLY and identically to every other adapter (D-6a): structured
        event, adapter name, resource, cure, exit 70. Never a bare ``assert``,
        whose ``AssertionError`` reaches the maintainer as a raw traceback.
        """
        keywords = self.load_keywords("en")
        if not keywords:
            refuse_startup(
                "PlaintextKeywordLoader",
                _KEYWORD_DIR / "en.txt",
                "gherkin keyword list is empty or missing",
            )

    def _load(self, path: Path) -> tuple[str, ...]:
        if not path.is_file():
            return ()
        lines = path.read_text(encoding="utf-8").splitlines()
        return tuple(
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        )
