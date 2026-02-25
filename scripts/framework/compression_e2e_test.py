"""
E2E compression test: compare agent behavior with original vs compressed instructions.

Uses Claude Haiku to simulate agent responses to test scenarios, comparing
outputs from original (git HEAD) vs compressed (working tree) instruction files.

Usage:
    # Test a single file with default scenarios
    python scripts/framework/compression_e2e_test.py test nWave/agents/nw-product-owner.md

    # Test with custom scenario
    python scripts/framework/compression_e2e_test.py test nWave/tasks/nw/deliver.md \
        --scenario "User says: /nw:deliver 'Add rate limiting to API'"

    # Test all modified files
    python scripts/framework/compression_e2e_test.py test-all

Requires: ANTHROPIC_API_KEY environment variable
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:

    def count_tokens(text: str) -> int:
        return len(text) // 4


# ---------------------------------------------------------------------------
# Test scenarios (file -> scenarios)
# ---------------------------------------------------------------------------

DEFAULT_SCENARIOS: dict[str, list[dict[str, str]]] = {
    "nw-product-owner.md": [
        {
            "name": "journey_start",
            "prompt": "User says: *journey 'release pipeline for nWave'\n\nWhat are your first 5 actions? List them as numbered steps.",
        },
        {
            "name": "skip_discovery",
            "prompt": "User says: Just sketch me a quick flow for the install process, skip the questions.\n\nHow do you respond?",
        },
        {
            "name": "dor_gate",
            "prompt": "User requests handoff to DESIGN wave. The story has:\n- Persona: 'User' (no specifics)\n- 1 example with abstract data (user123)\n- AC: 'System should work correctly'\n\nDo you approve the handoff? What specific failures do you report?",
        },
        {
            "name": "subagent_mode",
            "prompt": "You are invoked via Task tool with: TASK BOUNDARY -- execute *journey 'update agents' with these requirements: [agents should auto-update on install]\n\nWhat do you do? Do you ask questions or proceed?",
        },
        {
            "name": "antipattern_detection",
            "prompt": "Review this user story:\n# US-42: Implement Authentication\n## Problem\nUser needs auth.\n## AC\n- Use JWT tokens\n- Add Redis session store\n\nWhat anti-patterns do you detect? List each with the fix.",
        },
    ],
    "deliver.md": [
        {
            "name": "fresh_feature",
            "prompt": "User says: /nw:deliver 'Add rate limiting to the API gateway'\n\nList the exact sequence of phases you execute, with which agent handles each.",
        },
        {
            "name": "paradigm_detection",
            "prompt": "The project's CLAUDE.md contains:\n## Development Paradigm\nThis project uses functional programming with @nw-functional-software-crafter.\n\nWhich crafter do you dispatch for step execution? What testing approach is default?",
        },
        {
            "name": "mutation_strategy",
            "prompt": "Project CLAUDE.md has:\n## Mutation Testing Strategy\nStrategy: nightly-delta\n\nWhat happens at Phase 5 (Mutation Testing)?",
        },
        {
            "name": "boundary_violation",
            "prompt": "Step 01-03 needs implementation. You notice the code is simple (just adding a constant). Can you implement it directly without dispatching a sub-agent? Explain your reasoning.",
        },
        {
            "name": "des_integrity",
            "prompt": "After all steps complete, the integrity verification (Phase 6) exits with code 1 and reports step 02-01 has no execution-log entries. What do you do?",
        },
    ],
}


# ---------------------------------------------------------------------------
# LLM evaluation
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """Result of testing one scenario with both versions."""

    scenario_name: str
    original_response: str = ""
    compressed_response: str = ""
    original_tokens_used: int = 0
    compressed_tokens_used: int = 0
    judge_score: float = 0.0
    judge_analysis: str = ""
    judge_differences: list[str] = field(default_factory=list)


def run_scenario(
    client: anthropic.Anthropic,
    instructions: str,
    scenario_prompt: str,
    model: str = "claude-haiku-4-5-20251001",
) -> tuple[str, int]:
    """Run a scenario with given instructions and return (response, input_tokens)."""
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=instructions,
        messages=[{"role": "user", "content": scenario_prompt}],
    )
    text = response.content[0].text  # type: ignore[union-attr]
    input_tokens = response.usage.input_tokens
    return text, input_tokens


def judge_responses(
    client: anthropic.Anthropic,
    scenario_name: str,
    scenario_prompt: str,
    original_response: str,
    compressed_response: str,
    model: str = "claude-haiku-4-5-20251001",
) -> tuple[float, str, list[str]]:
    """Use LLM as judge to compare two responses. Returns (score, analysis, differences)."""
    judge_prompt = textwrap.dedent(f"""\
        You are evaluating whether two AI agent responses are functionally equivalent.
        The responses come from the same agent given identical user input, but with
        different versions of the instruction file (original vs compressed).

        ## Scenario
        {scenario_prompt}

        ## Response A (Original Instructions)
        {original_response}

        ## Response B (Compressed Instructions)
        {compressed_response}

        ## Evaluation Criteria
        Score from 0-100 on functional equivalence:
        - 100: Responses are functionally identical (same actions, same rules applied)
        - 90-99: Minor wording differences, same behavior
        - 70-89: Some behavioral differences but core actions preserved
        - 50-69: Significant behavioral differences, some rules missed
        - 0-49: Major divergence, critical rules or actions missing

        Focus on:
        1. Are the same RULES applied? (e.g., DoR gate, boundary rules)
        2. Are the same ACTIONS taken? (e.g., same agents dispatched, same phases)
        3. Are the same CONSTRAINTS respected? (e.g., never implement directly)
        4. Are the same EXAMPLES/PATTERNS used?

        Respond in this exact JSON format:
        {{"score": <number>, "analysis": "<1-2 sentences>", "differences": ["<diff1>", "<diff2>"]}}

        If no meaningful differences, use empty differences array.
    """)

    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    text = response.content[0].text  # type: ignore[union-attr]

    # Parse JSON from response
    try:
        # Find JSON in response
        json_start = text.index("{")
        json_end = text.rindex("}") + 1
        data = json.loads(text[json_start:json_end])
        return (
            float(data.get("score", 0)),
            data.get("analysis", ""),
            data.get("differences", []),
        )
    except (ValueError, json.JSONDecodeError):
        return 0.0, f"Failed to parse judge response: {text[:200]}", []


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def get_original_from_git(file_path: str) -> str | None:
    """Get original file content from git HEAD."""
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{file_path}"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def get_scenarios_for_file(file_path: str) -> list[dict[str, str]]:
    """Get test scenarios for a file."""
    name = Path(file_path).name
    return DEFAULT_SCENARIOS.get(name, [])


def run_test(
    file_path: str,
    scenarios: list[dict[str, str]] | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> list[ScenarioResult]:
    """Run e2e comparison test for a file."""
    if anthropic is None:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Get original and compressed content
    original_text = get_original_from_git(file_path)
    if original_text is None:
        print(f"ERROR: Cannot get git HEAD version of {file_path}")
        sys.exit(1)

    compressed_text = Path(file_path).read_text(encoding="utf-8")

    # Get scenarios
    if scenarios is None:
        scenarios = get_scenarios_for_file(file_path)
    if not scenarios:
        print(f"No scenarios defined for {Path(file_path).name}")
        return []

    results: list[ScenarioResult] = []

    print(f"\n{'=' * 70}")
    print(f"  E2E Test: {Path(file_path).name}")
    print(f"  Original: {count_tokens(original_text):,} tokens")
    print(f"  Compressed: {count_tokens(compressed_text):,} tokens")
    print(f"  Scenarios: {len(scenarios)}")
    print(f"  Model: {model}")
    print(f"{'=' * 70}")

    for i, scenario in enumerate(scenarios, 1):
        name = scenario["name"]
        prompt = scenario["prompt"]
        print(f"\n  [{i}/{len(scenarios)}] {name}...", end=" ", flush=True)

        # Run with original
        orig_response, orig_tokens = run_scenario(client, original_text, prompt, model)

        # Run with compressed
        comp_response, comp_tokens = run_scenario(
            client, compressed_text, prompt, model
        )

        # Judge
        score, analysis, differences = judge_responses(
            client, name, prompt, orig_response, comp_response, model
        )

        result = ScenarioResult(
            scenario_name=name,
            original_response=orig_response,
            compressed_response=comp_response,
            original_tokens_used=orig_tokens,
            compressed_tokens_used=comp_tokens,
            judge_score=score,
            judge_analysis=analysis,
            judge_differences=differences,
        )
        results.append(result)

        token_saved = orig_tokens - comp_tokens
        print(f"score={score:.0f}/100  tokens={token_saved:+d}")

        if differences:
            for diff in differences:
                print(f"    - {diff}")

    # Summary
    if results:
        avg_score = sum(r.judge_score for r in results) / len(results)
        total_orig_tokens = sum(r.original_tokens_used for r in results)
        total_comp_tokens = sum(r.compressed_tokens_used for r in results)
        total_saved = total_orig_tokens - total_comp_tokens

        print(f"\n{'─' * 70}")
        print(f"  SUMMARY: {Path(file_path).name}")
        print(f"{'─' * 70}")
        print(f"  Avg equivalence score: {avg_score:.0f}/100")
        print(
            f"  Total input tokens: {total_orig_tokens:,} → {total_comp_tokens:,} "
            f"(-{total_saved:,}, {total_saved / total_orig_tokens * 100:.1f}%)"
        )
        print(
            f"  Per-scenario savings: ~{total_saved // len(results):,} tokens/scenario"
        )

        verdict = (
            "PASS" if avg_score >= 85 else "MARGINAL" if avg_score >= 70 else "FAIL"
        )
        print(f"  Verdict: {verdict}")
        print(f"{'─' * 70}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_test(args: argparse.Namespace) -> int:
    """Test a single file."""
    scenarios = None
    if args.scenario:
        scenarios = [{"name": "custom", "prompt": args.scenario}]

    results = run_test(args.file, scenarios, model=args.model)
    if not results:
        return 1

    avg_score = sum(r.judge_score for r in results) / len(results)
    return 0 if avg_score >= 85 else 1


def cmd_test_all(args: argparse.Namespace) -> int:
    """Test all modified files that have scenarios."""
    # Find modified .md files
    try:
        modified = (
            subprocess.check_output(
                ["git", "diff", "--name-only", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
            .splitlines()
        )
    except subprocess.CalledProcessError:
        print("ERROR: git diff failed")
        return 1

    md_files = [f for f in modified if f.endswith(".md")]
    testable = [f for f in md_files if Path(f).name in DEFAULT_SCENARIOS]

    if not testable:
        print("No modified files with test scenarios found.")
        print(f"Modified .md files: {md_files}")
        print(f"Files with scenarios: {list(DEFAULT_SCENARIOS.keys())}")
        return 0

    all_results: list[ScenarioResult] = []
    for file_path in testable:
        results = run_test(file_path, model=args.model)
        all_results.extend(results)

    if all_results:
        avg_score = sum(r.judge_score for r in all_results) / len(all_results)
        print(f"\n{'=' * 70}")
        print(f"  OVERALL: {len(testable)} files, {len(all_results)} scenarios")
        print(f"  Avg equivalence: {avg_score:.0f}/100")
        print(f"{'=' * 70}")
        return 0 if avg_score >= 85 else 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E compression test for nWave framework files"
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to use for testing (default: haiku)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # test
    p_test = subparsers.add_parser("test", help="Test a single file")
    p_test.add_argument("file", help="File path to test")
    p_test.add_argument("--scenario", help="Custom scenario prompt")

    # test-all
    subparsers.add_parser("test-all", help="Test all modified files with scenarios")

    args = parser.parse_args()
    handlers = {
        "test": cmd_test,
        "test-all": cmd_test_all,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
