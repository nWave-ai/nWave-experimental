"""PlaintextKeywordLoader — loads Gherkin keyword lists from text files."""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_KEYWORD_DIR = _REPO_ROOT / "nWave" / "data" / "gherkin-keywords"


class PlaintextKeywordLoader:
    """Load Gherkin keyword lists from .txt files (one keyword per line)."""

    def load_keywords(self, lang: str) -> tuple[str, ...]:
        """Return Gherkin keywords for `lang` from nWave/data/gherkin-keywords/{lang}.txt."""
        path = _KEYWORD_DIR / f"{lang}.txt"
        return self._load(path)

    def probe(self) -> None:
        """Startup health check — verify en.txt is accessible and non-empty."""
        keywords = self.load_keywords("en")
        assert len(keywords) > 0, (
            f"en.txt is empty or missing at {_KEYWORD_DIR / 'en.txt'}"
        )

    def _load(self, path: Path) -> tuple[str, ...]:
        if not path.exists():
            return ()
        lines = path.read_text(encoding="utf-8").splitlines()
        return tuple(
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        )
