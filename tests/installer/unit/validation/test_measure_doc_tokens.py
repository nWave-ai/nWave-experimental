"""Unit tests for `scripts.measure_doc_tokens` (DDD-1, AC-1.c).

Covers the pure-function core (`count_tokens`, `compare_to_baseline`) plus
thin I/O wrappers (`measure_doc`, `main`). Includes a dogfood test that
runs the script against this feature's own `feature-delta.md` and asserts a
non-zero token count, satisfying the 04-01 acceptance gate per the task
description (no acceptance scenario un-skipped at this milestone).

The script is advisory only per DDD-1: it always exits 0 even when ratios
exceed the 0.60 pilot threshold. The threshold flag lives on the
`ComparisonResult` for downstream consumers (e.g. pilot success metric)
but is not enforced here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.measure_doc_tokens import (
    ComparisonResult,
    TokenMeasurement,
    compare_to_baseline,
    count_tokens,
    main,
    measure_doc,
)


# ---------------------------------------------------------------------------
# Pure function: count_tokens
# ---------------------------------------------------------------------------


class TestCountTokens:
    """Pure tokenizer wrapper. No I/O, deterministic per encoding name."""

    def test_hello_world_uses_two_tokens_under_cl100k_base(self) -> None:
        """`hello world` encodes to exactly 2 tokens under cl100k_base.

        Verifiable via direct tiktoken call: `[15339, 1917]`.
        """
        assert count_tokens("hello world", "cl100k_base") == 2

    def test_empty_string_yields_zero_tokens(self) -> None:
        assert count_tokens("", "cl100k_base") == 0

    def test_default_encoding_is_cl100k_base(self) -> None:
        """DDD-1 architect choice: default encoding is cl100k_base."""
        # Equivalence: explicit cl100k_base call matches the default.
        assert count_tokens("hello world") == count_tokens("hello world", "cl100k_base")

    def test_count_is_deterministic_across_calls(self) -> None:
        """Same input + same encoding -> identical count every time."""
        sample = "## Wave: DISCUSS / [REF] Persona\n\nMarco is a solo dev.\n"
        first = count_tokens(sample, "cl100k_base")
        second = count_tokens(sample, "cl100k_base")
        assert first == second
        assert first > 0


# ---------------------------------------------------------------------------
# Thin I/O wrapper: measure_doc(Path) -> TokenMeasurement
# ---------------------------------------------------------------------------


class TestMeasureDoc:
    """Reads a markdown file and produces a TokenMeasurement record."""

    def test_returns_token_measurement_with_file_and_count(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "sample.md"
        target.write_text("hello world", encoding="utf-8")

        measurement = measure_doc(target)

        assert isinstance(measurement, TokenMeasurement)
        assert measurement.file == target
        assert measurement.tokens == 2
        assert measurement.encoding == "cl100k_base"

    def test_empty_file_yields_zero_tokens(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.md"
        target.write_text("", encoding="utf-8")

        measurement = measure_doc(target)

        assert measurement.tokens == 0


# ---------------------------------------------------------------------------
# Pure function: compare_to_baseline
# ---------------------------------------------------------------------------


def _make_measurement(tokens: int, name: str = "x.md") -> TokenMeasurement:
    """Test helper: synthesise a TokenMeasurement without touching disk."""
    return TokenMeasurement(file=Path(name), tokens=tokens, encoding="cl100k_base")


class TestCompareToBaseline:
    """Pure ratio computation + pilot threshold flag."""

    def test_ratio_is_target_over_baseline(self) -> None:
        target = _make_measurement(60)
        baseline = _make_measurement(100)

        result = compare_to_baseline(target, baseline)

        assert result.ratio == pytest.approx(0.60)

    def test_ratio_below_pilot_threshold_passes(self) -> None:
        """0.59 ratio (i.e. 59%) passes the 60% pilot success threshold."""
        target = _make_measurement(59)
        baseline = _make_measurement(100)

        result = compare_to_baseline(target, baseline)

        assert result.passes_pilot_threshold is True

    def test_ratio_above_pilot_threshold_fails(self) -> None:
        """0.61 ratio fails the 60% pilot success threshold."""
        target = _make_measurement(61)
        baseline = _make_measurement(100)

        result = compare_to_baseline(target, baseline)

        assert result.passes_pilot_threshold is False

    def test_ratio_at_exactly_pilot_threshold_passes(self) -> None:
        """0.60 boundary is inclusive — at-threshold counts as pass."""
        target = _make_measurement(60)
        baseline = _make_measurement(100)

        result = compare_to_baseline(target, baseline)

        assert result.passes_pilot_threshold is True

    def test_result_carries_target_and_baseline_for_traceability(self) -> None:
        target = _make_measurement(50, "lean.md")
        baseline = _make_measurement(100, "legacy.md")

        result = compare_to_baseline(target, baseline)

        assert result.target == target
        assert result.baseline == baseline

    def test_zero_baseline_is_explicitly_rejected(self) -> None:
        """Division by zero baseline is undefined; raise instead of silently
        returning inf or NaN. Pure-function contract failure is preferable to
        a misleading ratio."""
        target = _make_measurement(10)
        baseline = _make_measurement(0)

        with pytest.raises(ValueError, match="baseline"):
            compare_to_baseline(target, baseline)


# ---------------------------------------------------------------------------
# CLI shell: subprocess invocation + main(argv) entry
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _script_path() -> Path:
    return _project_root() / "scripts" / "measure_doc_tokens.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=_project_root(),
    )


class TestCliShell:
    """End-to-end CLI: prints token count, always exits 0 (advisory)."""

    def test_main_returns_zero_on_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.md"
        target.write_text("hello world", encoding="utf-8")

        exit_code = main([str(target)])

        assert exit_code == 0

    def test_main_returns_nonzero_on_missing_file(self, tmp_path: Path) -> None:
        """Missing file is a usage error, not an advisory measurement -> exit 1."""
        exit_code = main([str(tmp_path / "does-not-exist.md")])

        assert exit_code != 0

    def test_main_returns_nonzero_on_no_arguments(self) -> None:
        exit_code = main([])

        assert exit_code != 0

    def test_cli_prints_token_count_to_stdout(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.md"
        target.write_text("hello world", encoding="utf-8")

        result = _run_script(str(target))

        assert result.returncode == 0, (
            f"CLI exited {result.returncode}; stderr={result.stderr!r}"
        )
        assert "2" in result.stdout

    def test_cli_with_baseline_flag_reports_ratio(self, tmp_path: Path) -> None:
        target = tmp_path / "lean.md"
        baseline = tmp_path / "legacy.md"
        # 'hello world' -> 2 tokens; 'hello world hello world' -> 4 tokens.
        # Ratio = 2/4 = 0.50, below the 0.60 pilot threshold.
        target.write_text("hello world", encoding="utf-8")
        baseline.write_text("hello world hello world", encoding="utf-8")

        result = _run_script(str(target), "--baseline", str(baseline))

        assert result.returncode == 0
        # Percentage formatted with a `%` glyph for human reading.
        assert "50" in result.stdout
        assert "%" in result.stdout

    def test_cli_always_exits_zero_even_when_above_threshold(
        self, tmp_path: Path
    ) -> None:
        """DDD-1: advisory only. Above-threshold ratio still exits 0."""
        target = tmp_path / "above.md"
        baseline = tmp_path / "small.md"
        # Ratio well above 0.60 -> should still exit 0 (advisory).
        target.write_text("hello world hello world hello world", encoding="utf-8")
        baseline.write_text("hello world", encoding="utf-8")

        result = _run_script(str(target), "--baseline", str(baseline))

        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Dogfood: 04-01 acceptance gate per task description
# ---------------------------------------------------------------------------


class TestDogfoodOwnFeatureDelta:
    """Run measure_doc_tokens on this feature's own feature-delta.md.

    Per task description, 04-01's acceptance gate is the unit-test dogfood:
    "running measure_doc_tokens on this feature's own feature-delta.md
    produces a deterministic token count (tested as a unit test)."
    """

    def test_dogfood_produces_deterministic_nonzero_count(self) -> None:
        target = (
            _project_root()
            / "docs"
            / "feature"
            / "lean-wave-documentation"
            / "feature-delta.md"
        )
        if not target.is_file():
            pytest.skip(f"feature-delta.md not found at {target}")

        first = measure_doc(target)
        second = measure_doc(target)

        assert first.tokens > 0, "feature-delta.md must produce at least one token"
        assert first.tokens == second.tokens, (
            "Token count must be deterministic across calls"
        )
        assert first.encoding == "cl100k_base"


# ---------------------------------------------------------------------------
# Sanity: NamedTuple shape (purely structural — guards refactors)
# ---------------------------------------------------------------------------


def test_token_measurement_is_immutable_named_tuple() -> None:
    measurement = TokenMeasurement(file=Path("x.md"), tokens=10, encoding="cl100k_base")
    assert measurement.tokens == 10
    with pytest.raises(AttributeError):
        measurement.tokens = 20  # type: ignore[misc]


def test_comparison_result_is_immutable_named_tuple() -> None:
    target = _make_measurement(60)
    baseline = _make_measurement(100)
    result = ComparisonResult(
        target=target,
        baseline=baseline,
        ratio=0.60,
        passes_pilot_threshold=True,
    )
    assert result.ratio == 0.60
    with pytest.raises(AttributeError):
        result.ratio = 0.30  # type: ignore[misc]
