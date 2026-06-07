"""Unit tests for i18n verb loader (US-13 AC-1, AC-2, AC-3).

Test Budget: 3 distinct behaviors x 2 = 6 unit tests max.
Using 3.

Behaviors:
  B1 — it.txt ships with ≥3 patterns, UTF-8 without BOM
  B2 — es/fr header-only stubs load to empty list (parametrized: 1 test covers both)
  B3 — per-repo override at .nwave/protocol-verbs.txt unions with framework default

Port: PlaintextVerbLoader.load_protocol_verbs() — driving port for all three.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from nwave_ai.feature_delta.adapters.verbs import PlaintextVerbLoader


_REPO_ROOT = Path(__file__).parents[3]
_VERB_DIR = _REPO_ROOT / "nWave" / "data" / "protocol-verbs"


# ---------------------------------------------------------------------------
# B1 — Italian verb list ships with ≥3 patterns; file is UTF-8 without BOM
# ---------------------------------------------------------------------------


def test_italian_verb_list_loads_at_least_three_patterns() -> None:
    """it.txt must ship with ≥3 protocol-surface placeholder patterns (US-13 AC-1)."""
    loader = PlaintextVerbLoader()
    patterns = loader.load_protocol_verbs("it")
    assert len(patterns) >= 3, (
        f"it.txt must contain ≥3 patterns; found {len(patterns)}: {patterns}"
    )


def test_italian_verb_list_is_utf8_without_bom() -> None:
    """it.txt must be UTF-8 encoded without BOM (US-13 AC-1)."""
    raw = (_VERB_DIR / "it.txt").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), (
        "it.txt must not have a UTF-8 BOM — save as UTF-8 (no BOM)"
    )


# ---------------------------------------------------------------------------
# B2 — es/fr header-only stubs load to empty list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["es", "fr"])
def test_stub_language_verb_list_loads_to_empty(lang: str) -> None:
    """es.txt and fr.txt are header-only stubs that load to an empty tuple (US-13 AC-3)."""
    loader = PlaintextVerbLoader()
    patterns = loader.load_protocol_verbs(lang)
    assert patterns == (), (
        f"{lang}.txt must be a header-only stub loading to empty; got {patterns}"
    )


# ---------------------------------------------------------------------------
# B3 — per-repo override at .nwave/protocol-verbs.txt unions with framework default
# ---------------------------------------------------------------------------


def test_per_repo_override_unions_with_framework_default(tmp_path: Path) -> None:
    """Per-repo override extends framework verbs via union (US-13 AC-3)."""
    override_dir = tmp_path / ".nwave"
    override_dir.mkdir()
    override_file = override_dir / "protocol-verbs.txt"
    override_file.write_text("my-custom-verb\n", encoding="utf-8")

    loader = PlaintextVerbLoader(repo_root=tmp_path)
    patterns = loader.load_protocol_verbs("en")

    # Framework defaults (en.txt) must be present
    assert "GET" in patterns, "Framework default 'GET' must be in union result"
    # Per-repo override must also be present
    assert "my-custom-verb" in patterns, (
        "Per-repo override 'my-custom-verb' must be in union result"
    )
