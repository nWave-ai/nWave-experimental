"""Unit tests for E5 protocol-surface corpus expansion.

Test Budget: 2 distinct behaviors x 2 = 4 unit tests max.
Using 2.

Behaviors:
  B1 — en.txt loads ≥20 patterns (data set expansion from 01-01's 5)
  B2 — h10-corpus regression: 15 fixture files produce 100% expected outcomes
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]
_EN_TXT = _REPO_ROOT / "nWave" / "data" / "protocol-verbs" / "en.txt"
_CORPUS_DIR = _REPO_ROOT / "tests" / "fixtures" / "h10-corpus"


def _load_patterns(path: Path) -> list[str]:
    """Load non-blank, non-comment lines from a verb list file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


# ---------------------------------------------------------------------------
# B1 — en.txt contains ≥20 patterns after expansion
# ---------------------------------------------------------------------------


def test_en_txt_contains_at_least_20_patterns() -> None:
    """E5 data set must have ≥20 protocol-surface patterns (US-04 AC-1, AC-2)."""
    patterns = _load_patterns(_EN_TXT)
    assert len(patterns) >= 20, (
        f"en.txt has only {len(patterns)} patterns; ≥20 required by US-04 AC-1. "
        f"Patterns found: {patterns}"
    )


# ---------------------------------------------------------------------------
# B2 — H10 corpus: 15 fixture files produce 100% expected outcomes
# ---------------------------------------------------------------------------


def test_h10_corpus_100_percent_pass() -> None:
    """All 15 h10-corpus fixtures produce the expected E5 outcome (US-04 AC-4)."""
    from nwave_ai.feature_delta.domain.parser import MarkdownSectionParser
    from nwave_ai.feature_delta.domain.rules import e5_protocol_surface

    patterns = tuple(_load_patterns(_EN_TXT))
    fixture_files = sorted(_CORPUS_DIR.glob("*.md"))
    assert len(fixture_files) == 15, (
        f"h10-corpus must contain exactly 15 .md fixtures; "
        f"found {len(fixture_files)}: {[f.name for f in fixture_files]}"
    )

    parser = MarkdownSectionParser()
    failures: list[str] = []
    for fixture_path in fixture_files:
        content = fixture_path.read_text(encoding="utf-8")
        # Expected outcome encoded in filename: "pass_*.md" or "fail_*.md"
        name = fixture_path.stem
        if name.startswith("pass_"):
            expected_violations = 0
        elif name.startswith("fail_"):
            expected_violations = 1
        else:
            failures.append(
                f"{fixture_path.name}: unknown prefix — must start with 'pass_' or 'fail_'"
            )
            continue

        model = parser.parse(content)
        violations = e5_protocol_surface.check(model, patterns)
        actual = len(violations)
        if actual != expected_violations:
            failures.append(
                f"{fixture_path.name}: expected {expected_violations} violations, "
                f"got {actual}: {[v.offender for v in violations]}"
            )

    assert not failures, (
        f"H10 corpus regression failures ({len(failures)}/15):\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
