"""Unit tests for the managed CLAUDE.md beta-section helpers + CLI consent wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.install.project_claude_section import (
    BEGIN_MARKER,
    END_MARKER,
    inject_managed_section,
    load_section_content,
    remove_managed_section,
    resolve_section_template,
)


SECTION = "## nWave (beta)\n\nDrive work through the spine."


# --- pure helpers: inject -------------------------------------------------


def test_inject_creates_file_when_absent(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    outcome = inject_managed_section(claude, SECTION)
    assert outcome == "created"
    text = claude.read_text(encoding="utf-8")
    assert BEGIN_MARKER in text and END_MARKER in text
    assert "Drive work through the spine." in text


def test_inject_appends_preserving_user_content(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# My Project\n\nUser rules here.\n", encoding="utf-8")
    outcome = inject_managed_section(claude, SECTION)
    assert outcome == "appended"
    text = claude.read_text(encoding="utf-8")
    assert "# My Project" in text
    assert "User rules here." in text
    assert text.index("User rules here.") < text.index(BEGIN_MARKER)


def test_inject_is_idempotent_no_duplication(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# My Project\n\nUser rules.\n", encoding="utf-8")
    inject_managed_section(claude, SECTION)
    outcome = inject_managed_section(claude, SECTION)
    assert outcome == "updated"
    text = claude.read_text(encoding="utf-8")
    assert text.count(BEGIN_MARKER) == 1
    assert text.count(END_MARKER) == 1
    assert "User rules." in text


def test_inject_refreshes_content_between_markers(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    inject_managed_section(claude, "## nWave (beta)\n\nold body")
    inject_managed_section(claude, "## nWave (beta)\n\nnew body")
    text = claude.read_text(encoding="utf-8")
    assert "new body" in text
    assert "old body" not in text
    assert text.count(BEGIN_MARKER) == 1


# --- pure helpers: remove -------------------------------------------------


def test_remove_absent_file_is_noop(tmp_path: Path) -> None:
    assert remove_managed_section(tmp_path / "CLAUDE.md") == "absent"


def test_remove_no_markers_is_noop(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# Just user content\n", encoding="utf-8")
    assert remove_managed_section(claude) == "absent"
    assert claude.read_text(encoding="utf-8") == "# Just user content\n"


def test_remove_preserves_user_content(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# My Project\n\nUser rules.\n", encoding="utf-8")
    inject_managed_section(claude, SECTION)
    outcome = remove_managed_section(claude)
    assert outcome == "removed-section"
    text = claude.read_text(encoding="utf-8")
    assert "User rules." in text
    assert BEGIN_MARKER not in text and END_MARKER not in text


def test_remove_deletes_file_when_only_section(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    inject_managed_section(claude, SECTION)  # created — file holds only the block
    outcome = remove_managed_section(claude)
    assert outcome == "removed-file"
    assert not claude.exists()


def test_inject_then_remove_round_trips_user_content(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    original = "# My Project\n\nUser rules.\n"
    claude.write_text(original, encoding="utf-8")
    inject_managed_section(claude, SECTION)
    remove_managed_section(claude)
    assert claude.read_text(encoding="utf-8").strip() == original.strip()


# --- template resolution --------------------------------------------------


def test_section_template_resolves_and_loads() -> None:
    template = resolve_section_template()
    assert template.is_file(), template
    content = load_section_content()
    assert "nWave (beta)" in content
    # The body must NOT carry the markers — those are added at inject time.
    assert BEGIN_MARKER not in content and END_MARKER not in content


# --- CLI consent wiring ---------------------------------------------------


def test_cli_enable_injects_with_assume_yes(tmp_path: Path) -> None:
    from nwave_ai import cli

    cli._sync_project_claude_section("enable", tmp_path, assume_yes=True)
    claude = tmp_path / "CLAUDE.md"
    assert claude.is_file()
    assert BEGIN_MARKER in claude.read_text(encoding="utf-8")


def test_cli_disable_removes_section(tmp_path: Path) -> None:
    from nwave_ai import cli

    cli._sync_project_claude_section("enable", tmp_path, assume_yes=True)
    cli._sync_project_claude_section("disable", tmp_path, assume_yes=False)
    assert not (tmp_path / "CLAUDE.md").exists()


def test_cli_enable_skips_when_non_interactive_without_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    cli._sync_project_claude_section("enable", tmp_path, assume_yes=False)
    assert not (tmp_path / "CLAUDE.md").exists()


def test_cli_enable_skips_on_declined_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    cli._sync_project_claude_section("enable", tmp_path, assume_yes=False)
    assert not (tmp_path / "CLAUDE.md").exists()


def test_cli_enable_injects_on_accepted_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")  # bare Enter = yes
    cli._sync_project_claude_section("enable", tmp_path, assume_yes=False)
    assert (tmp_path / "CLAUDE.md").is_file()


# --- standing loops consent teaser ---


def test_standing_loops_teaser_present_and_valid() -> None:
    """Verify consent teaser for standing loops: authority, token cap, correct semantics."""
    from scripts.install.project_claude_section import load_section_content
    from scripts.measure_doc_tokens import count_tokens

    content = load_section_content()

    # Teaser must exist
    assert "Standing Loops" in content or "standing loops" in content, (
        "Standing loops teaser missing"
    )

    # Extract the teaser section (between heading and next section)
    import re

    teaser_match = re.search(
        r"###?\s+Standing Loops.*?\n\n(.*?)(?=\n###|\n##[^#]|$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    assert teaser_match, "Standing loops section not found"
    teaser_body = teaser_match.group(1)

    # Must NOT mention auto-arm, auto-rearm, opt-out, or "on by default"
    forbidden = [
        "auto-arm",
        "auto-rearm",
        "opt-out",
        "opt out",
        "on by default",
        "arm themselves",
    ]
    for term in forbidden:
        assert term not in teaser_body.lower(), (
            f"Forbidden term '{term}' found in teaser"
        )

    # Must mention OFF by default and explicit consent
    assert "off" in teaser_body.lower(), "Teaser must state loops are OFF by default"
    assert "explicit" in teaser_body.lower() or "consent" in teaser_body.lower(), (
        "Teaser must mention explicit consent"
    )

    # Token cap: must be ≤64 tokens
    token_count = count_tokens(teaser_body)
    assert token_count <= 64, (
        f"Teaser too large: {token_count} tokens (max 64). Body:\n{teaser_body}"
    )

    # Byte cap: must be ≤256 bytes
    byte_count = len(teaser_body.encode("utf-8"))
    assert byte_count <= 256, f"Teaser exceeds 256 bytes: {byte_count}"
