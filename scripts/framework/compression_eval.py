"""
Compression evaluation tool for nWave framework files.

Compares original vs compressed markdown files across three dimensions:
1. Token efficiency — how many tokens saved
2. Structural preservation — all sections, rules, constraints preserved
3. Semantic equivalence — extracted semantic units match

Usage:
    # Compare two files
    python scripts/framework/compression_eval.py compare original.md compressed.md

    # Batch compare: original dir vs compressed dir
    python scripts/framework/compression_eval.py batch nWave/agents/ compressed/agents/

    # Validate a single compressed file against git HEAD version
    python scripts/framework/compression_eval.py validate nWave/agents/nw-product-owner.md

    # Report: measure all framework files and report compression opportunities
    python scripts/framework/compression_eval.py report
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Fallback: rough estimate (1 token ≈ 4 chars for English)
        return len(text) // 4


# ---------------------------------------------------------------------------
# Semantic unit extraction
# ---------------------------------------------------------------------------


@dataclass
class SemanticProfile:
    """Extracted semantic units from a markdown file."""

    sections: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    keywords: set[str] = field(default_factory=set)
    agent_refs: set[str] = field(default_factory=set)
    file_refs: set[str] = field(default_factory=set)
    commands: set[str] = field(default_factory=set)
    tokens: int = 0
    lines: int = 0


def extract_profile(text: str) -> SemanticProfile:
    """Extract semantic units from markdown text."""
    profile = SemanticProfile()
    profile.tokens = count_tokens(text)
    profile.lines = len(text.splitlines())

    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()

        # Skip code blocks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Sections (## headers)
        if stripped.startswith("#"):
            header = re.sub(r"^#+\s*", "", stripped)
            profile.sections.append(header)

        # Numbered rules (1. **Bold**: description or 1. Description)
        rule_match = re.match(r"^\d+\.\s+(.+)", stripped)
        if rule_match:
            rule_text = rule_match.group(1)
            # Extract the bold keyword if present
            bold = re.search(r"\*\*([^*]+)\*\*", rule_text)
            if bold:
                profile.rules.append(bold.group(1).lower())
            else:
                # Use first 8 words as rule identifier
                words = rule_text.split()[:8]
                profile.rules.append(" ".join(words).lower().rstrip(":.,"))

        # Constraints (lines starting with "- " containing "not", "never", "must", "only")
        if stripped.startswith("- ") or stripped.startswith("* "):
            constraint_words = {"not", "never", "must", "only", "always", "required"}
            if any(w in stripped.lower() for w in constraint_words):
                # Normalize: extract key phrase
                clean = re.sub(r"^[-*]\s+", "", stripped)
                clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)  # remove bold
                words = clean.split()[:10]
                profile.constraints.append(" ".join(words).lower())

        # Examples (### Example or ### 1:)
        if re.match(r"^###\s+(Example|[0-9]+[:.)])", stripped):
            profile.examples.append(re.sub(r"^###\s+", "", stripped))

        # Agent references (@nw-*)
        for ref in re.findall(r"@nw-[\w-]+", stripped):
            profile.agent_refs.add(ref)

        # File/path references
        for ref in re.findall(r"(?:docs|nWave|src|tests)/[\w/{}.*-]+", stripped):
            profile.file_refs.add(ref)

        # Commands (*command or /nw:command)
        # *command must be at line start, after pipe, or after backtick (not bold markdown)
        for cmd in re.findall(r"/nw:\w[\w-]*", stripped):
            profile.commands.add(cmd)
        for cmd in re.findall(r"(?:^|[|`\s])\*(\w[\w-]*)", stripped):
            if cmd not in {"md", "py", "yaml", "feature", "txt"}:
                profile.commands.add(f"*{cmd}")

        # Important keywords (CRITICAL, NEVER, MUST, IMPORTANT)
        for kw in re.findall(
            r"\b(CRITICAL|NEVER|MUST|IMPORTANT|REQUIRED|MANDATORY)\b", stripped
        ):
            profile.keywords.add(kw)

    return profile


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    """Result of comparing original vs compressed profiles."""

    file_name: str
    original_tokens: int
    compressed_tokens: int
    token_savings: int
    token_savings_pct: float
    original_lines: int
    compressed_lines: int
    missing_sections: list[str] = field(default_factory=list)
    missing_rules: list[str] = field(default_factory=list)
    missing_examples: list[str] = field(default_factory=list)
    missing_agent_refs: set[str] = field(default_factory=set)
    missing_commands: set[str] = field(default_factory=set)
    missing_keywords: set[str] = field(default_factory=set)
    missing_constraints: list[str] = field(default_factory=list)
    semantic_score: float = 0.0  # 0-100%
    verdict: str = ""

    @property
    def has_losses(self) -> bool:
        return bool(
            self.missing_sections
            or self.missing_rules
            or self.missing_agent_refs
            or self.missing_commands
            or self.missing_keywords
        )


_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "out",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "and",
    "but",
    "or",
    "nor",
    "not",
    "so",
    "if",
    "when",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "any",
    "you",
    "your",
    "we",
    "they",
    "them",
    "their",
    "he",
    "she",
}


def _key_words(text: str) -> set[str]:
    """Extract significant words, filtering stopwords."""
    words = set(re.findall(r"[a-z][a-z-]+", text.lower()))
    return words - _STOPWORDS


def _fuzzy_match(needle: str, haystack: list[str], threshold: float = 0.6) -> bool:
    """Check if needle fuzzy-matches any item in haystack using key words."""
    needle_kw = _key_words(needle)
    if not needle_kw:
        return True  # nothing significant to match

    for item in haystack:
        item_kw = _key_words(item)
        if not item_kw:
            continue
        # Check if key words from needle appear in item
        overlap = len(needle_kw & item_kw)
        # Match if ≥threshold of needle's key words found
        if overlap / len(needle_kw) >= threshold:
            return True

    # Also check against full text of all items combined
    all_kw = set()
    for item in haystack:
        all_kw |= _key_words(item)
    overlap = len(needle_kw & all_kw)
    return overlap / len(needle_kw) >= threshold


def compare_profiles(
    original: SemanticProfile,
    compressed: SemanticProfile,
    file_name: str = "",
) -> ComparisonResult:
    """Compare two semantic profiles and report differences."""
    result = ComparisonResult(
        file_name=file_name,
        original_tokens=original.tokens,
        compressed_tokens=compressed.tokens,
        token_savings=original.tokens - compressed.tokens,
        token_savings_pct=(
            (original.tokens - compressed.tokens) / original.tokens * 100
            if original.tokens > 0
            else 0
        ),
        original_lines=original.lines,
        compressed_lines=compressed.lines,
    )

    # Check sections (fuzzy match - compressed may rename slightly)
    for section in original.sections:
        if not _fuzzy_match(section, compressed.sections, threshold=0.5):
            result.missing_sections.append(section)

    # Check rules (fuzzy match)
    for rule in original.rules:
        if not _fuzzy_match(rule, compressed.rules, threshold=0.5):
            result.missing_rules.append(rule)

    # Check examples (just count - names may change)
    if len(compressed.examples) < len(original.examples):
        for i, ex in enumerate(original.examples):
            if i >= len(compressed.examples):
                result.missing_examples.append(ex)

    # Check agent refs (exact)
    result.missing_agent_refs = original.agent_refs - compressed.agent_refs

    # Check commands (exact)
    result.missing_commands = original.commands - compressed.commands

    # Check keywords (exact)
    result.missing_keywords = original.keywords - compressed.keywords

    # Check constraints (fuzzy — also search full compressed text)
    for constraint in original.constraints:
        constraint_kw = _key_words(constraint)
        # Check against constraint list
        if _fuzzy_match(constraint, compressed.constraints, threshold=0.4):
            continue
        # Fallback: check if key words appear anywhere in compressed rules/constraints
        all_compressed_kw = set()
        for r in compressed.rules + compressed.constraints:
            all_compressed_kw |= _key_words(r)
        if (
            constraint_kw
            and len(constraint_kw & all_compressed_kw) / len(constraint_kw) >= 0.4
        ):
            continue
        result.missing_constraints.append(constraint)

    # Calculate semantic score
    checks = [
        (len(result.missing_sections) == 0, 25),  # sections: 25%
        (len(result.missing_rules) == 0, 25),  # rules: 25%
        (len(result.missing_agent_refs) == 0, 15),  # agent refs: 15%
        (len(result.missing_commands) == 0, 10),  # commands: 10%
        (len(result.missing_keywords) == 0, 10),  # keywords: 10%
        (len(result.missing_examples) == 0, 10),  # examples: 10%
        (len(result.missing_constraints) == 0, 5),  # constraints: 5%
    ]
    result.semantic_score = sum(weight for passed, weight in checks if passed)

    # Verdict
    if result.semantic_score == 100 and result.token_savings_pct >= 15:
        result.verdict = "EXCELLENT"
    elif result.semantic_score >= 90 and result.token_savings_pct >= 10:
        result.verdict = "GOOD"
    elif result.semantic_score >= 75:
        result.verdict = "ACCEPTABLE"
    elif result.has_losses:
        result.verdict = "NEEDS REVIEW"
    else:
        result.verdict = "POOR"

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_result(result: ComparisonResult) -> str:
    """Format a comparison result as a human-readable report."""
    lines = [
        f"\n{'=' * 60}",
        f"  {result.file_name}",
        f"{'=' * 60}",
        "",
        f"  Tokens:  {result.original_tokens:,} → {result.compressed_tokens:,}  "
        f"(-{result.token_savings:,}, {result.token_savings_pct:.1f}%)",
        f"  Lines:   {result.original_lines} → {result.compressed_lines}",
        f"  Score:   {result.semantic_score:.0f}/100",
        f"  Verdict: {result.verdict}",
    ]

    if result.missing_sections:
        lines.append(f"\n  Missing sections ({len(result.missing_sections)}):")
        for s in result.missing_sections:
            lines.append(f"    - {s}")

    if result.missing_rules:
        lines.append(f"\n  Missing rules ({len(result.missing_rules)}):")
        for r in result.missing_rules:
            lines.append(f"    - {r}")

    if result.missing_agent_refs:
        lines.append(
            f"\n  Missing agent refs: {', '.join(sorted(result.missing_agent_refs))}"
        )

    if result.missing_commands:
        lines.append(
            f"\n  Missing commands: {', '.join(sorted(result.missing_commands))}"
        )

    if result.missing_keywords:
        lines.append(
            f"\n  Missing keywords: {', '.join(sorted(result.missing_keywords))}"
        )

    if result.missing_constraints:
        lines.append(f"\n  Missing constraints ({len(result.missing_constraints)}):")
        for c in result.missing_constraints[:5]:
            lines.append(f"    - {c}")
        if len(result.missing_constraints) > 5:
            lines.append(f"    ... and {len(result.missing_constraints) - 5} more")

    if result.missing_examples:
        lines.append(f"\n  Missing examples ({len(result.missing_examples)}):")
        for e in result.missing_examples:
            lines.append(f"    - {e}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two files."""
    original_text = Path(args.original).read_text(encoding="utf-8")
    compressed_text = Path(args.compressed).read_text(encoding="utf-8")

    original_profile = extract_profile(original_text)
    compressed_profile = extract_profile(compressed_text)

    result = compare_profiles(
        original_profile,
        compressed_profile,
        file_name=Path(args.compressed).name,
    )
    print(format_result(result))
    return 0 if result.semantic_score >= 75 else 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate compressed file against git HEAD version."""
    file_path = args.file
    try:
        original_text = subprocess.check_output(
            ["git", "show", f"HEAD:{file_path}"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")
    except subprocess.CalledProcessError:
        print(f"ERROR: Cannot get git HEAD version of {file_path}")
        return 1

    compressed_text = Path(file_path).read_text(encoding="utf-8")

    original_profile = extract_profile(original_text)
    compressed_profile = extract_profile(compressed_text)

    result = compare_profiles(
        original_profile,
        compressed_profile,
        file_name=Path(file_path).name,
    )
    print(format_result(result))
    return 0 if result.semantic_score >= 75 else 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Batch compare original dir vs compressed dir."""
    original_dir = Path(args.original_dir)
    compressed_dir = Path(args.compressed_dir)

    results = []
    for compressed_file in sorted(compressed_dir.glob("*.md")):
        original_file = original_dir / compressed_file.name
        if not original_file.exists():
            continue

        original_profile = extract_profile(original_file.read_text(encoding="utf-8"))
        compressed_profile = extract_profile(
            compressed_file.read_text(encoding="utf-8")
        )
        result = compare_profiles(
            original_profile, compressed_profile, file_name=compressed_file.name
        )
        results.append(result)

    if not results:
        print("No matching files found.")
        return 1

    # Print individual results
    for result in results:
        print(format_result(result))

    # Summary
    total_orig = sum(r.original_tokens for r in results)
    total_comp = sum(r.compressed_tokens for r in results)
    avg_score = sum(r.semantic_score for r in results) / len(results)

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY ({len(results)} files)")
    print(f"{'=' * 60}")
    print(
        f"  Total tokens: {total_orig:,} → {total_comp:,} (-{total_orig - total_comp:,}, {(total_orig - total_comp) / total_orig * 100:.1f}%)"
    )
    print(f"  Avg semantic score: {avg_score:.0f}/100")
    print(
        f"  Verdicts: "
        f"{sum(1 for r in results if r.verdict == 'EXCELLENT')} excellent, "
        f"{sum(1 for r in results if r.verdict == 'GOOD')} good, "
        f"{sum(1 for r in results if r.verdict == 'ACCEPTABLE')} acceptable, "
        f"{sum(1 for r in results if r.verdict == 'NEEDS REVIEW')} needs review"
    )

    return 0 if avg_score >= 75 else 1


def cmd_report(args: argparse.Namespace) -> int:
    """Report token counts for all framework files."""
    base = Path()
    categories = {
        "CLAUDE.md": [base / "CLAUDE.md"],
        "Agents": sorted((base / "nWave" / "agents").glob("*.md")),
        "Commands": sorted((base / "nWave" / "tasks" / "nw").glob("*.md")),
    }

    # Skills by group
    skills_dir = base / "nWave" / "skills"
    if skills_dir.exists():
        for group in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
            files = sorted(group.glob("*.md"))
            if files:
                categories[f"Skills/{group.name}"] = files

    grand_total = 0
    print(f"\n{'Category':<40} {'Files':>5} {'Tokens':>8} {'Lines':>6}")
    print("-" * 65)

    for category, files in categories.items():
        if not files:
            continue
        cat_tokens = 0
        cat_lines = 0
        for f in files:
            if f.exists():
                text = f.read_text(encoding="utf-8")
                cat_tokens += count_tokens(text)
                cat_lines += len(text.splitlines())
        grand_total += cat_tokens
        print(f"  {category:<38} {len(files):>5} {cat_tokens:>8,} {cat_lines:>6}")

    print("-" * 65)
    print(f"  {'TOTAL':<38} {'':>5} {grand_total:>8,}")
    print(
        f"\n  Estimated savings at 30% compression: ~{int(grand_total * 0.3):,} tokens"
    )

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compression evaluation for nWave framework files"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare two files")
    p_compare.add_argument("original", help="Original file path")
    p_compare.add_argument("compressed", help="Compressed file path")

    # validate
    p_validate = subparsers.add_parser(
        "validate", help="Validate compressed file against git HEAD"
    )
    p_validate.add_argument("file", help="File path (compared against git HEAD)")

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch compare directories")
    p_batch.add_argument("original_dir", help="Original directory")
    p_batch.add_argument("compressed_dir", help="Compressed directory")

    # report
    subparsers.add_parser("report", help="Token count report for all framework files")

    args = parser.parse_args()
    handlers = {
        "compare": cmd_compare,
        "validate": cmd_validate,
        "batch": cmd_batch,
        "report": cmd_report,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
