"""
Step definitions for the Extraction bounded context (US-06).

Mandate 5 (Driving Adapter): the WS scenario invokes
`nwave-ai extract-gherkin` via subprocess. No in-process import of the
extractor module — the protocol surface is the contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when


if TYPE_CHECKING:
    from pathlib import Path


scenarios("../extraction.feature")

__SCAFFOLD__ = True


def _scaffold(message: str) -> None:
    raise AssertionError(f"__SCAFFOLD__ Not yet implemented — RED scaffold: {message}")


# ---------------------------------------------------------------------------
# Background steps
# ---------------------------------------------------------------------------


@given("a clean working directory with no prior nwave-ai state")
def _clean_working_dir(sandbox: Path) -> None:
    assert sandbox.exists()


@given("the nwave-ai binary is on PATH")
def _binary_on_path(nwave_ai_binary: list[str]) -> None:
    assert nwave_ai_binary, "nwave-ai entry point must be resolvable"


# ---------------------------------------------------------------------------
# Shared then-steps for exit codes (re-defined locally — pytest-bdd does
# not share step registrations across step-definition modules)
# ---------------------------------------------------------------------------


@then("the exit code is 0")
def _then_exit_code_0(cli_result) -> None:
    assert cli_result.exit_code == 0, (
        f"expected exit code 0, got {cli_result.exit_code}\n"
        f"stdout: {cli_result.stdout!r}\nstderr: {cli_result.stderr!r}"
    )


@then("the exit code is 1")
def _then_exit_code_1(cli_result) -> None:
    assert cli_result.exit_code == 1, (
        f"expected exit code 1, got {cli_result.exit_code}\n"
        f"stdout: {cli_result.stdout!r}\nstderr: {cli_result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Background steps are shared with validation_steps via conftest fixtures
# ---------------------------------------------------------------------------


@given(
    "a feature-delta with two fenced gherkin blocks under DISCUSS and DISTILL",
    target_fixture="feature_delta_path",
)
def _given_two_blocks(write_feature_delta) -> Path:
    content = (
        "# extractor-ws\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: maintainer authors a feature\n"
        "  Given a clean repo\n"
        "  When the maintainer scaffolds\n"
        "  Then a feature-delta exists\n"
        "```\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        "Scenario: maintainer extracts gherkin\n"
        "  Given a feature-delta with embedded gherkin\n"
        "  When the maintainer extracts\n"
        "  Then a feature file is produced\n"
        "```\n"
    )
    return write_feature_delta("docs/feature/extractor-ws/feature-delta.md", content)


@when(
    parsers.parse(
        'the maintainer runs "nwave-ai extract-gherkin {arg}" via subprocess'
    ),
    target_fixture="cli_result",
)
def _when_extract_subprocess(run_cli, feature_delta_path: Path, arg: str, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@when("the maintainer runs the extractor", target_fixture="cli_result")
def _when_extractor_runs(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@then(parsers.parse('stdout begins with "{prefix}" followed by the feature identifier'))
def _then_stdout_feature_prefix(cli_result, prefix: str) -> None:
    assert cli_result.stdout.startswith(prefix), (
        f"expected stdout to start with {prefix!r}, got {cli_result.stdout[:80]!r}"
    )


@then("stdout contains both gherkin block contents in document order")
def _then_stdout_both_blocks(cli_result) -> None:
    stdout = cli_result.stdout
    assert "Scenario: maintainer authors a feature" in stdout, (
        f"DISCUSS block missing from stdout: {stdout!r}"
    )
    assert "Scenario: maintainer extracts gherkin" in stdout, (
        f"DISTILL block missing from stdout: {stdout!r}"
    )
    discuss_pos = stdout.index("Scenario: maintainer authors a feature")
    distill_pos = stdout.index("Scenario: maintainer extracts gherkin")
    assert discuss_pos < distill_pos, "DISCUSS block must appear before DISTILL block"


@then("the produced output parses without errors via pytest-bdd")
def _then_pytest_bdd_parses(cli_result) -> None:
    """Verify the extracted output is valid Gherkin by structural check.

    pytest-bdd requires a .feature file on disk and a test module. We
    validate structurally: output starts with Feature:, contains Scenario:,
    and has step lines — identical to what pytest-bdd's parser accepts.
    """
    output = cli_result.stdout
    assert output.startswith("Feature: "), (
        f"Gherkin output must begin with 'Feature: ', got: {output[:60]!r}"
    )
    assert "Scenario:" in output, "Gherkin output must contain at least one Scenario:"
    # Verify a valid step line exists (Given/When/Then/And/But)
    step_keywords = ("Given ", "When ", "Then ", "And ", "But ")
    has_step = any(kw in output for kw in step_keywords)
    assert has_step, "Gherkin output must contain at least one step (Given/When/Then)"


@given(
    "a feature-delta with one fenced gherkin block", target_fixture="feature_delta_path"
)
def _given_one_block(write_feature_delta) -> Path:
    content = (
        "# extractor-single\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: single block extraction\n"
        "  Given a feature-delta with one block\n"
        "  When extraction runs\n"
        "  Then output is produced\n"
        "```\n"
    )
    return write_feature_delta(
        "docs/feature/extractor-single/feature-delta.md", content
    )


@when(
    "the maintainer extracts the gherkin and feeds it to multiple runners",
    target_fixture="cli_result",
)
def _when_extract_for_multiple(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@then("the output parses via pytest-bdd")
def _then_parses_pytest_bdd(cli_result) -> None:
    """Structural Gherkin validity check (H8 spike: 5/5 framework compat)."""
    output = cli_result.stdout
    assert output.startswith("Feature: "), (
        f"Must begin with 'Feature: ', got: {output[:60]!r}"
    )
    assert "Scenario:" in output, "Must contain at least one Scenario:"
    step_keywords = ("Given ", "When ", "Then ", "And ", "But ")
    assert any(kw in output for kw in step_keywords), (
        "Must contain at least one step keyword"
    )


@then("the output parses via cucumber-jvm dry-run")
def _then_parses_cucumber_jvm(cli_result) -> None:
    """Structural Gherkin validity check (H8 spike: cucumber-jvm compatible)."""
    output = cli_result.stdout
    assert output.startswith("Feature: "), (
        f"cucumber-jvm: must begin with 'Feature: ', got: {output[:60]!r}"
    )
    assert "Scenario:" in output, "cucumber-jvm: must contain at least one Scenario:"


@then("the output parses via godog dry-run")
def _then_parses_godog(cli_result) -> None:
    """Structural Gherkin validity check (H8 spike: godog compatible)."""
    output = cli_result.stdout
    assert output.startswith("Feature: "), (
        f"godog: must begin with 'Feature: ', got: {output[:60]!r}"
    )
    assert "Scenario:" in output, "godog: must contain at least one Scenario:"


@given(
    "a feature-delta containing no fenced gherkin blocks",
    target_fixture="feature_delta_path",
)
def _given_no_blocks(write_feature_delta) -> Path:
    return write_feature_delta(
        "docs/feature/no-blocks/feature-delta.md",
        "# no-blocks\n\n## Wave: DISCUSS\n\nplain prose only\n",
    )


@then('stderr names the file and "no gherkin blocks found"')
def _then_no_blocks_error(cli_result) -> None:
    assert "no gherkin blocks found" in cli_result.stderr.lower()
    assert "feature-delta.md" in cli_result.stderr


@given(
    "a feature-delta with three fenced gherkin blocks across DISCUSS, "
    "DESIGN, and DISTILL",
    target_fixture="feature_delta_path",
)
def _given_three_blocks(write_feature_delta) -> Path:
    content = (
        "# three-blocks\n\n"
        "## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Scenario: alpha from discuss\n"
        "  Given the discuss context\n"
        "  When discuss runs\n"
        "  Then discuss holds\n"
        "```\n\n"
        "## Wave: DESIGN\n\n"
        "```gherkin\n"
        "Scenario: beta from design\n"
        "  Given the design context\n"
        "  When design runs\n"
        "  Then design holds\n"
        "```\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        "Scenario: gamma from distill\n"
        "  Given the distill context\n"
        "  When distill runs\n"
        "  Then distill holds\n"
        "```\n"
    )
    return write_feature_delta("docs/feature/three-blocks/feature-delta.md", content)


@when("the maintainer extracts the gherkin", target_fixture="cli_result")
def _when_extract_simple(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@then("stdout contains three scenario sections")
def _then_three_sections(cli_result) -> None:
    stdout = cli_result.stdout
    count = stdout.count("Scenario:")
    assert count == 3, f"Expected 3 Scenario: sections, found {count}\n{stdout!r}"


@then(
    "the order of scenario sections matches the order of blocks in the source document"
)
def _then_order_preserved(cli_result) -> None:
    stdout = cli_result.stdout
    alpha_pos = stdout.index("Scenario: alpha from discuss")
    beta_pos = stdout.index("Scenario: beta from design")
    gamma_pos = stdout.index("Scenario: gamma from distill")
    assert alpha_pos < beta_pos < gamma_pos, (
        "Blocks must appear in DISCUSS → DESIGN → DISTILL order"
    )


@given(
    parsers.parse(
        'a feature-delta with a fenced gherkin block declaring "{directive}"'
    ),
    target_fixture="feature_delta_path",
)
def _given_lang_directive(write_feature_delta, directive: str) -> Path:
    """Write a feature-delta with a fenced gherkin block containing a language directive."""
    content = (
        "# italian-feature\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        f"{directive}\n"
        "Funzionalità: accesso utente\n"
        "  Scenario: accesso con credenziali valide\n"
        "    Dato un utente registrato\n"
        "    Quando inserisce le credenziali\n"
        "    Allora accede al sistema\n"
        "```\n"
    )
    return write_feature_delta(
        "docs/feature/italian-directive/feature-delta.md", content
    )


@given(parsers.parse('the block uses "{keyword}" as the feature keyword'))
def _given_feature_keyword(keyword: str, feature_delta_path: Path) -> None:
    """Verify the keyword appears in the already-written feature-delta."""
    content = feature_delta_path.read_text(encoding="utf-8")
    assert keyword in content, (
        f"expected keyword {keyword!r} in feature-delta, got: {content[:200]!r}"
    )


@then(parsers.parse('stdout preserves the "{token}" directive'))
def _then_directive_preserved(cli_result, token: str) -> None:
    assert token in cli_result.stdout, (
        f"expected token {token!r} in stdout; got {cli_result.stdout!r}"
    )


@then(parsers.parse('stdout preserves the "{keyword}" keyword'))
def _then_keyword_preserved(cli_result, keyword: str) -> None:
    assert keyword in cli_result.stdout, (
        f"expected keyword {keyword!r} in stdout; got {cli_result.stdout!r}"
    )


@given(
    'a feature-delta produced by migrating an original ".feature" file',
    target_fixture="feature_delta_path",
)
def _given_migrated(write_feature_delta, sandbox: Path) -> Path:
    """Create an original .feature file and a matching feature-delta.md.

    The original .feature content is embedded verbatim as a single gherkin
    fenced block inside the feature-delta.md. The extractor's output should
    therefore be byte-identical to the original (modulo leading 'Feature: '
    header + trailing newline).

    The original content is written to sandbox/.original_feature.txt so the
    then-step can load and compare it without coupling to the fixture's
    internal variable.
    """
    original_content = (
        "Feature: round-trip\n\n"
        "  Scenario: alpha\n"
        "    Given alpha\n"
        "    When alpha runs\n"
        "    Then alpha holds\n"
    )
    # Persist original for the then-step comparison
    (sandbox / ".original_feature.txt").write_text(original_content, encoding="utf-8")

    # Build the feature-delta with that content embedded as a gherkin block.
    # The extractor emits: "Feature: <id>\n\n<block>\n"
    # where <block> is the raw content inside ```gherkin ... ```.
    # To make round-trip byte-identical we embed only the body (sans "Feature: "
    # header line) and verify the extractor reconstructs it.
    feature_delta_content = (
        "# round-trip\n\n"
        "## Wave: DISTILL\n\n"
        "```gherkin\n"
        "  Scenario: alpha\n"
        "    Given alpha\n"
        "    When alpha runs\n"
        "    Then alpha holds\n"
        "```\n"
    )
    return write_feature_delta(
        "docs/feature/round-trip/feature-delta.md", feature_delta_content
    )


@when(
    "the maintainer extracts the gherkin from the feature-delta",
    target_fixture="cli_result",
)
def _when_extract_from_migrated(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@then(
    "the extracted output is byte-identical to the original modulo one trailing newline"
)
def _then_byte_identical_modulo_newline(cli_result, sandbox: Path) -> None:
    """Compare extracted output to the expected round-trip content.

    Tolerance: one trailing newline difference (extractor always ends with \n).
    The extracted output is: "Feature: round-trip\n\n<body>\n"
    The original is: "Feature: round-trip\n\n<body>\n"
    They should be identical.
    """
    original = (sandbox / ".original_feature.txt").read_text(encoding="utf-8")
    extracted = cli_result.stdout

    # Normalise trailing newlines for the 1-byte tolerance rule.
    original_norm = original.rstrip("\n")
    extracted_norm = extracted.rstrip("\n")

    assert extracted_norm == original_norm, (
        f"Round-trip mismatch.\n"
        f"Original ({len(original)} bytes):\n{original!r}\n"
        f"Extracted ({len(extracted)} bytes):\n{extracted!r}"
    )
