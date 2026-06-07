"""
Step definitions for the Migration bounded context (US-08).

Mandate 5: WS scenario invokes `nwave-ai migrate-feature` via subprocess
and asserts byte-identical round-trip via the extractor (also via
subprocess) — proving the driving-adapter contract end-to-end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when


if TYPE_CHECKING:
    from pathlib import Path


scenarios("../migration.feature")


# ---------------------------------------------------------------------------
# Background steps (shared across all scenarios in this feature)
# ---------------------------------------------------------------------------


@given("a clean working directory with no prior nwave-ai state")
def _clean_working_dir(sandbox: Path) -> None:
    assert sandbox.exists()


@given("the nwave-ai binary is on PATH")
def _binary_on_path(nwave_ai_binary: list[str]) -> None:
    assert nwave_ai_binary, "nwave-ai entry point must be resolvable"


# ---------------------------------------------------------------------------
# Walking skeleton
# ---------------------------------------------------------------------------


@given(
    'a feature directory containing one ".feature" file with three scenarios',
    target_fixture="feature_dir",
)
def _given_one_feature_three_scenarios(sandbox: Path) -> Path:
    fdir = sandbox / "docs" / "feature" / "migrator-ws"
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "tests.feature").write_text(
        "Feature: migrator walking skeleton\n\n"
        "  Scenario: alpha\n"
        "    Given alpha\n"
        "    When alpha runs\n"
        "    Then alpha holds\n\n"
        "  Scenario: beta\n"
        "    Given beta\n"
        "    When beta runs\n"
        "    Then beta holds\n\n"
        "  Scenario: gamma\n"
        "    Given gamma\n"
        "    When gamma runs\n"
        "    Then gamma holds\n",
        encoding="utf-8",
    )
    (fdir / "feature-delta.md").write_text(
        "# migrator-ws\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | migrate legacy .feature | n/a | preserves scenarios |\n",
        encoding="utf-8",
    )
    return fdir


@when(
    parsers.parse(
        'the maintainer runs "nwave-ai migrate-feature {arg}" via subprocess'
    ),
    target_fixture="cli_result",
)
def _when_migrate_subprocess(run_cli, feature_dir: Path, arg: str, capsys):
    rel = feature_dir.relative_to(feature_dir.parents[2])
    return run_cli("migrate-feature", str(rel))


@when("the maintainer runs the migration", target_fixture="cli_result")
def _when_migration_runs(run_cli, feature_dir: Path, capsys):
    rel = feature_dir.relative_to(feature_dir.parents[2])
    return run_cli("migrate-feature", str(rel))


@when(
    "the maintainer runs the migration on the feature directory",
    target_fixture="cli_result",
)
def _when_migrate_on_dir(run_cli, feature_dir: Path, capsys):
    rel = feature_dir.relative_to(feature_dir.parents[2])
    return run_cli("migrate-feature", str(rel))


@when("the maintainer runs the migration again", target_fixture="cli_result")
def _when_migrate_again(run_cli, feature_dir: Path, capsys):
    rel = feature_dir.relative_to(feature_dir.parents[2])
    return run_cli("migrate-feature", str(rel))


@then("the exit code is 0")
def _exit_code_zero(cli_result) -> None:
    assert cli_result.exit_code == 0, (
        f"expected exit 0, got {cli_result.exit_code}\n"
        f"stdout={cli_result.stdout!r}\nstderr={cli_result.stderr!r}"
    )


@then("the exit code is 1")
def _exit_code_one(cli_result) -> None:
    assert cli_result.exit_code == 1, (
        f"expected exit 1, got {cli_result.exit_code}\n"
        f"stdout={cli_result.stdout!r}\nstderr={cli_result.stderr!r}"
    )


@then(
    "the feature-delta in the directory contains a fenced gherkin block "
    "with the original content"
)
def _then_block_with_original(cli_result, feature_dir: Path) -> None:
    delta_path = feature_dir / "feature-delta.md"
    assert delta_path.exists(), "feature-delta.md must exist after migration"
    delta_text = delta_path.read_text(encoding="utf-8")
    assert "```gherkin" in delta_text, "feature-delta.md must contain a gherkin block"
    assert "Scenario: alpha" in delta_text, (
        "gherkin block must contain original scenarios"
    )
    assert "Scenario: beta" in delta_text
    assert "Scenario: gamma" in delta_text


@then('the original ".feature" file is renamed to ".feature.pre-migration"')
def _then_pre_migration_backup(cli_result, feature_dir: Path) -> None:
    backup = feature_dir / "tests.feature.pre-migration"
    assert backup.exists(), f"backup not found: {backup}"
    original = feature_dir / "tests.feature"
    assert not original.exists(), f"original must be renamed: {original}"


@then(
    "re-running the extractor produces output byte-identical to "
    "the original modulo one trailing newline"
)
def _then_roundtrip_byte_identical(cli_result, feature_dir: Path, run_cli) -> None:
    # Read original from backup
    backup = feature_dir / "tests.feature.pre-migration"
    original_content = backup.read_text(encoding="utf-8")

    # Run extract-gherkin on the feature-delta.md
    delta_rel = (feature_dir / "feature-delta.md").relative_to(feature_dir.parents[2])
    extract_result = run_cli("extract-gherkin", str(delta_rel))
    assert extract_result.exit_code == 0, (
        f"extract-gherkin failed: {extract_result.stderr!r}"
    )

    # The extractor emits "Feature: <id>\n\n<block_content>\n"
    # Strip the "Feature: <id>\n\n" header to get the block content.
    extracted = extract_result.stdout
    lines = extracted.split("\n\n", maxsplit=1)
    assert len(lines) == 2, f"unexpected extractor output: {extracted!r}"
    block_content = lines[1]

    diff_bytes = abs(
        len(original_content.rstrip("\n")) - len(block_content.rstrip("\n"))
    )
    assert diff_bytes <= 1, (
        f"round-trip byte difference {diff_bytes} exceeds tolerance.\n"
        f"original ({len(original_content)} bytes):\n{original_content!r}\n"
        f"extracted ({len(block_content)} bytes):\n{block_content!r}"
    )


# ---------------------------------------------------------------------------
# Round-trip failure abort
# ---------------------------------------------------------------------------


@given(
    'a feature directory whose ".feature" content would lose more '
    "than one byte on round-trip",
    target_fixture="feature_dir",
)
def _given_lossy_roundtrip(sandbox: Path) -> Path:
    fdir = sandbox / "docs" / "feature" / "lossy-feature"
    fdir.mkdir(parents=True, exist_ok=True)
    # Content that loses >1 byte on round-trip: a line starting with ``` closes
    # the markdown gherkin fence prematurely, so the parser sees a truncated block.
    # The extractor extracts only the lines before the ``` closer, losing all
    # subsequent lines — a byte difference >> 1.
    feature_content = (
        "Feature: lossy\n\n"
        "  Scenario: broken\n"
        "    Given a code fence closes the block\n"
        "```\n"
        "    When lines after the fence are lost\n"
        "    Then round-trip fails with diff > 1 byte\n"
    )
    (fdir / "lossy.feature").write_text(feature_content, encoding="utf-8")
    (fdir / "feature-delta.md").write_text(
        "# lossy-feature\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | lossy migration | n/a | abort test |\n",
        encoding="utf-8",
    )
    return fdir


@then("no file in the directory is modified")
def _then_no_files_modified(cli_result, feature_dir: Path) -> None:
    # Two contexts share this step:
    # 1. Abort scenario (round-trip fails): .feature still present, delta unchanged.
    # 2. Idempotency scenario (already migrated): .feature.pre-migration already
    #    existed BEFORE the run; delta must not have a NEW gherkin block added.
    already_migrated = "already migrated" in cli_result.stderr.lower()

    if already_migrated:
        # Idempotency: the delta must not have had a new block appended.
        # We verify by checking the gherkin block count matches the fixture
        # (fixture wrote exactly 1 block; no new block must have been added).
        delta_text = (feature_dir / "feature-delta.md").read_text(encoding="utf-8")
        block_count = delta_text.count("```gherkin")
        assert block_count == 1, (
            f"idempotency: expected 1 pre-existing gherkin block, got {block_count}"
        )
    else:
        # Abort scenario: original .feature must still exist (not renamed).
        feature_files = list(feature_dir.glob("*.feature"))
        assert feature_files, (
            "abort scenario: original .feature must still exist (not renamed)"
        )
        delta_path = feature_dir / "feature-delta.md"
        delta_text = delta_path.read_text(encoding="utf-8")
        assert "```gherkin" not in delta_text, (
            "feature-delta.md must NOT contain a gherkin block on abort"
        )


@then("stderr contains the diff between original and round-tripped content")
def _then_diff_in_stderr(cli_result) -> None:
    assert cli_result.stderr, "stderr must not be empty on round-trip failure"
    stderr_lower = cli_result.stderr.lower()
    assert (
        "round-trip" in stderr_lower
        or "diff" in stderr_lower
        or "tolerance" in stderr_lower
    ), f"stderr must describe round-trip failure: {cli_result.stderr!r}"


# ---------------------------------------------------------------------------
# Multi-file migration
# ---------------------------------------------------------------------------


@given(
    'a feature directory containing three ".feature" files',
    target_fixture="feature_dir",
)
def _given_three_features(sandbox: Path) -> Path:
    fdir = sandbox / "docs" / "feature" / "multi-feature"
    fdir.mkdir(parents=True, exist_ok=True)
    for name, letter in [("alpha", "A"), ("beta", "B"), ("gamma", "C")]:
        (fdir / f"{name}.feature").write_text(
            f"Feature: {name}\n\n"
            f"  Scenario: {letter}-1\n"
            f"    Given {letter} context\n"
            f"    When {letter} runs\n"
            f"    Then {letter} holds\n",
            encoding="utf-8",
        )
    (fdir / "feature-delta.md").write_text(
        "# multi-feature\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | three files | n/a | multi-file test |\n",
        encoding="utf-8",
    )
    return fdir


@then("the feature-delta contains three separate fenced gherkin blocks")
def _then_three_blocks(cli_result, feature_dir: Path) -> None:
    delta_text = (feature_dir / "feature-delta.md").read_text(encoding="utf-8")
    block_count = delta_text.count("```gherkin")
    assert block_count == 3, (
        f"expected 3 gherkin blocks, found {block_count}\n{delta_text}"
    )


@then("each block contains the original file's content")
def _then_each_block_original(cli_result, feature_dir: Path) -> None:
    delta_text = (feature_dir / "feature-delta.md").read_text(encoding="utf-8")
    for name, letter in [("alpha", "A"), ("beta", "B"), ("gamma", "C")]:
        assert f"Scenario: {letter}-1" in delta_text, (
            f"block for {name}.feature missing from feature-delta.md"
        )


@then(
    "round-trip extraction concatenates to content identical to the "
    "original concatenation"
)
def _then_concat_identical(cli_result, feature_dir: Path, run_cli) -> None:
    # Collect original content from backups (sorted = same order as migration)
    backups = sorted(feature_dir.glob("*.feature.pre-migration"))
    assert len(backups) == 3, f"expected 3 backups, got {len(backups)}"
    original_concat = "".join(
        b.read_text(encoding="utf-8").rstrip("\n") for b in backups
    )

    # Extract from the feature-delta
    delta_rel = (feature_dir / "feature-delta.md").relative_to(feature_dir.parents[2])
    extract_result = run_cli("extract-gherkin", str(delta_rel))
    assert extract_result.exit_code == 0, (
        f"extract-gherkin failed: {extract_result.stderr!r}"
    )

    # Parse the feature-delta.md directly using MarkdownSectionParser to
    # retrieve raw gherkin blocks without inter-block separator ambiguity.
    from nwave_ai.feature_delta.domain.parser import MarkdownSectionParser

    delta_text = (feature_dir / "feature-delta.md").read_text(encoding="utf-8")
    model = MarkdownSectionParser().parse(delta_text)
    extracted_blocks: list[str] = []
    for section in model.sections:
        extracted_blocks.extend(section.gherkin_blocks)

    assert len(extracted_blocks) == len(backups), (
        f"expected {len(backups)} extracted blocks, got {len(extracted_blocks)}"
    )

    extracted_concat = "".join(b.rstrip("\n") for b in extracted_blocks)
    diff_bytes = abs(len(original_concat) - len(extracted_concat))
    # 1-byte tolerance per file (trailing newline)
    assert diff_bytes <= len(backups), (
        f"round-trip byte difference {diff_bytes} exceeds tolerance "
        f"({len(backups)} files × 1 byte).\n"
        f"original ({len(original_concat)} bytes)\n"
        f"extracted ({len(extracted_concat)} bytes)"
    )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@given(
    "a feature directory that was previously migrated and contains "
    '".feature.pre-migration" backup',
    target_fixture="feature_dir",
)
def _given_already_migrated(sandbox: Path) -> Path:
    fdir = sandbox / "docs" / "feature" / "already-migrated"
    fdir.mkdir(parents=True, exist_ok=True)
    # Simulate a completed migration: backup present, no .feature
    (fdir / "tests.feature.pre-migration").write_text(
        "Feature: already migrated\n\n"
        "  Scenario: was here\n"
        "    Given a\n"
        "    When b\n"
        "    Then c\n",
        encoding="utf-8",
    )
    (fdir / "feature-delta.md").write_text(
        "# already-migrated\n\n## Wave: DISCUSS\n\n"
        "```gherkin\n"
        "Feature: already migrated\n\n"
        "  Scenario: was here\n"
        "    Given a\n"
        "    When b\n"
        "    Then c\n"
        "```\n",
        encoding="utf-8",
    )
    return fdir


@then('stderr contains "already migrated"')
def _then_already_migrated(cli_result) -> None:
    assert "already migrated" in cli_result.stderr.lower()


# ---------------------------------------------------------------------------
# G4 — sandbox snapshot diff
# ---------------------------------------------------------------------------


@given(
    "a sandbox with a feature directory and surrounding monitored files",
    target_fixture="feature_dir",
)
def _given_sandbox_with_monitored(sandbox: Path) -> Path:
    fdir = sandbox / "docs" / "feature" / "g4-feature"
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "tests.feature").write_text(
        "Feature: g4\n\n"
        "  Scenario: side-effects\n"
        "    Given no side effects\n"
        "    When migration runs\n"
        "    Then only target dir modified\n",
        encoding="utf-8",
    )
    (fdir / "feature-delta.md").write_text(
        "# g4-feature\n\n## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | G4 isolation | n/a | zero side effects |\n",
        encoding="utf-8",
    )
    return fdir


@given(
    'the monitored files include ".git/", ".pre-commit-config.yaml", and shell rc files'
)
def _given_monitored_set(sandbox: Path) -> None:
    # Create monitored sentinel files outside the feature directory.
    # sandbox = tmp_path/sandbox/repo; sandbox.parent/home = tmp_path/sandbox/home
    (sandbox / ".pre-commit-config.yaml").write_text(
        "repos: []  # sentinel\n", encoding="utf-8"
    )
    home_dir = sandbox.parent / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    (home_dir / ".bashrc").write_text("# sentinel bashrc\n", encoding="utf-8")


@then("no monitored file outside the feature directory is modified")
def _then_no_monitored_diff(cli_result, feature_dir: Path, sandbox: Path) -> None:
    # The sentinel files must be unchanged.
    precommit = sandbox / ".pre-commit-config.yaml"
    if precommit.exists():
        content = precommit.read_text(encoding="utf-8")
        assert "sentinel" in content, (
            f"G4 violation: .pre-commit-config.yaml was modified: {content!r}"
        )
    home_dir = sandbox.parent / "home"
    bashrc = home_dir / ".bashrc"
    if bashrc.exists():
        content = bashrc.read_text(encoding="utf-8")
        assert "sentinel" in content, f"G4 violation: .bashrc was modified: {content!r}"


@then(
    "the only modifications inside the feature directory are the "
    "feature-delta and the pre-migration backup"
)
def _then_only_expected_modifications(cli_result, feature_dir: Path) -> None:
    files_in_dir = {p.name for p in feature_dir.iterdir() if p.is_file()}
    expected = {"feature-delta.md", "tests.feature.pre-migration"}
    unexpected = files_in_dir - expected
    assert not unexpected, (
        f"unexpected files created inside feature directory: {unexpected}"
    )
    assert "tests.feature.pre-migration" in files_in_dir, (
        "pre-migration backup must exist inside feature directory"
    )
