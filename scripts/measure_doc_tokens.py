"""measure_doc_tokens — token-count utility for lean wave documentation (DDD-1).

Advisory tokenization tool used to measure feature-delta.md size against the
60% pilot success threshold from AC-1.c. The script ALWAYS exits 0 when the
target file exists; it is not a CI gate. Per DDD-1 (architect H1 closure),
the tokenizer is tiktoken's `cl100k_base` encoding.

CLI contract:
- `python scripts/measure_doc_tokens.py <path-to-md-file>`
  Prints the token count to stdout. Exit 0 on success.
- `python scripts/measure_doc_tokens.py <target> --baseline <baseline>`
  Prints the target token count plus the percentage versus baseline. Still
  exits 0 even if the percentage exceeds the 60% pilot success threshold —
  this is advisory only, not enforcement.

Architecture (functional split):
- Pure core: `count_tokens(content, encoding)` and `compare_to_baseline`.
- Thin I/O wrapper: `measure_doc(path)` reads the file then delegates.
- CLI shell: `main(argv)` parses arguments, formats stdout, returns exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

import tiktoken


# ---------------------------------------------------------------------------
# Domain types — pure data carriers
# ---------------------------------------------------------------------------


#: Default tokenizer per DDD-1 (architect H1 closure).
DEFAULT_ENCODING: str = "cl100k_base"

#: Pilot success threshold per AC-1.c / DDD-7 gate (1). 60% of legacy baseline.
PILOT_THRESHOLD: float = 0.60


class TokenMeasurement(NamedTuple):
    """A single tokenization observation. Immutable."""

    file: Path
    tokens: int
    encoding: str


class ComparisonResult(NamedTuple):
    """Outcome of comparing two TokenMeasurements. Immutable."""

    target: TokenMeasurement
    baseline: TokenMeasurement
    ratio: float
    passes_pilot_threshold: bool


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------


def count_tokens(content: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count tokens in `content` under the named tiktoken encoding. Pure.

    Args:
        content: text body to tokenize.
        encoding_name: tiktoken encoding name. Defaults to cl100k_base
            per DDD-1.

    Returns:
        Number of tokens produced by the encoder for `content`.
    """
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(content))


def compare_to_baseline(
    target: TokenMeasurement,
    baseline: TokenMeasurement,
) -> ComparisonResult:
    """Compute target/baseline ratio and the pilot-threshold flag. Pure.

    The pilot threshold is inclusive: a ratio of exactly 0.60 counts as pass
    (matches the AC-1.c "at most sixty percent" wording).

    Args:
        target: measurement of the candidate document (e.g. lean delta).
        baseline: measurement of the legacy-layout reference.

    Returns:
        ComparisonResult carrying both inputs, the ratio, and the threshold
        verdict.

    Raises:
        ValueError: if `baseline.tokens` is zero (ratio undefined).
    """
    if baseline.tokens == 0:
        raise ValueError(
            "Cannot compute ratio against a zero-token baseline; "
            "the baseline document must contain at least one token."
        )
    ratio = target.tokens / baseline.tokens
    return ComparisonResult(
        target=target,
        baseline=baseline,
        ratio=ratio,
        passes_pilot_threshold=ratio <= PILOT_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# Thin I/O wrapper
# ---------------------------------------------------------------------------


def measure_doc(
    file_path: Path, encoding_name: str = DEFAULT_ENCODING
) -> TokenMeasurement:
    """Read `file_path` and return a TokenMeasurement.

    Args:
        file_path: path to a UTF-8 text file (markdown expected).
        encoding_name: tiktoken encoding to use.

    Returns:
        TokenMeasurement carrying the file path, token count, and encoding.
    """
    content = file_path.read_text(encoding="utf-8")
    return TokenMeasurement(
        file=file_path,
        tokens=count_tokens(content, encoding_name),
        encoding=encoding_name,
    )


# ---------------------------------------------------------------------------
# CLI shell — only side effect boundary
# ---------------------------------------------------------------------------


def _format_count(measurement: TokenMeasurement) -> str:
    return f"{measurement.file}: {measurement.tokens} tokens ({measurement.encoding})"


def _format_comparison(comparison: ComparisonResult) -> str:
    pct = comparison.ratio * 100
    verdict = "PASS" if comparison.passes_pilot_threshold else "ABOVE"
    return (
        f"{comparison.target.file}: {comparison.target.tokens} tokens vs "
        f"baseline {comparison.baseline.file}: {comparison.baseline.tokens} "
        f"tokens -> {pct:.1f}% [{verdict} pilot threshold "
        f"{int(PILOT_THRESHOLD * 100)}%]"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="measure_doc_tokens",
        description=(
            "Advisory token counter for feature-delta.md (DDD-1). "
            "Uses tiktoken cl100k_base. Always exits 0 when the target "
            "exists; never enforces a CI gate."
        ),
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to the markdown file to measure.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "Optional path to a baseline markdown file. When supplied, the "
            "script prints the target/baseline percentage and a pilot "
            "threshold verdict (still always exits 0)."
        ),
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=DEFAULT_ENCODING,
        help=f"Tiktoken encoding name (default: {DEFAULT_ENCODING}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: argument list (defaults to `sys.argv[1:]`).

    Returns:
        0 on successful measurement (advisory contract per DDD-1).
        1 on usage error (missing argument, file not found).
    """
    args_list = sys.argv[1:] if argv is None else argv
    parser = _build_parser()

    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        # argparse exits with code 2 on usage error; normalise to non-zero.
        return int(exc.code) if exc.code else 1

    target_path: Path = args.target
    if not target_path.is_file():
        print(f"error: {target_path} is not a file", file=sys.stderr)
        return 1

    target_measurement = measure_doc(target_path, args.encoding)

    if args.baseline is None:
        print(_format_count(target_measurement))
        return 0

    baseline_path: Path = args.baseline
    if not baseline_path.is_file():
        print(f"error: {baseline_path} is not a file", file=sys.stderr)
        return 1

    baseline_measurement = measure_doc(baseline_path, args.encoding)
    comparison = compare_to_baseline(target_measurement, baseline_measurement)
    print(_format_comparison(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
