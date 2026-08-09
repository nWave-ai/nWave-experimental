"""Unit tests for the managed guidance-section helpers + CLI consent wiring.

Covers both hosts (Claude Code's CLAUDE.md, Codex's AGENTS.md) through the same
marker/atomic-write engine and the same parameterized CLI sync path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.install.project_claude_section import (
    BEGIN_MARKER,
    END_MARKER,
    HOSTS,
    inject_managed_section,
    load_section_content,
    remove_managed_section,
    resolve_section_template,
)


HOST_IDS = sorted(HOSTS)


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


# --- template resolution ---------------------------------------------------


@pytest.mark.parametrize("host", HOST_IDS)
def test_section_template_resolves_and_loads(host: str) -> None:
    template = resolve_section_template(host=host)
    assert template.is_file(), template
    content = load_section_content(host=host)
    assert "nWave (beta)" in content
    # The body must NOT carry the markers — those are added at inject time.
    assert BEGIN_MARKER not in content and END_MARKER not in content


def test_codex_projection_forbids_claude_specific_language() -> None:
    """AGENTS.md never carries Claude slash-command/Skill-tool prose."""
    content = load_section_content(host="codex").lower()
    for forbidden in ("/nw-", "skill tool", "slash command"):
        assert forbidden not in content, forbidden


# --- CLI consent wiring (parametrized across both hosts) -------------------


@pytest.mark.parametrize("host", HOST_IDS)
def test_cli_enable_injects_with_assume_yes(host: str, tmp_path: Path) -> None:
    from nwave_ai import cli

    cli._sync_guidance_section_for_host(host, "enable", tmp_path, assume_yes=True)
    target = tmp_path / HOSTS[host].filename
    assert target.is_file()
    assert BEGIN_MARKER in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("host", HOST_IDS)
def test_cli_disable_removes_section(host: str, tmp_path: Path) -> None:
    from nwave_ai import cli

    cli._sync_guidance_section_for_host(host, "enable", tmp_path, assume_yes=True)
    cli._sync_guidance_section_for_host(host, "disable", tmp_path, assume_yes=False)
    assert not (tmp_path / HOSTS[host].filename).exists()


@pytest.mark.parametrize("host", HOST_IDS)
def test_cli_enable_skips_when_non_interactive_without_yes(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    cli._sync_guidance_section_for_host(host, "enable", tmp_path, assume_yes=False)
    assert not (tmp_path / HOSTS[host].filename).exists()


@pytest.mark.parametrize("host", HOST_IDS)
def test_cli_enable_skips_on_declined_prompt(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    cli._sync_guidance_section_for_host(host, "enable", tmp_path, assume_yes=False)
    assert not (tmp_path / HOSTS[host].filename).exists()


@pytest.mark.parametrize("host", HOST_IDS)
def test_cli_enable_injects_on_accepted_prompt(
    host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nwave_ai import cli

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")  # bare Enter = yes
    cli._sync_guidance_section_for_host(host, "enable", tmp_path, assume_yes=False)
    assert (tmp_path / HOSTS[host].filename).is_file()


def test_sync_project_claude_section_drives_both_hosts_at_once(tmp_path: Path) -> None:
    """The top-level CLI sync path writes every registered host, not just Claude."""
    from nwave_ai import cli

    cli._sync_project_claude_section("enable", tmp_path, assume_yes=True)
    for host, guidance in HOSTS.items():
        target = tmp_path / guidance.filename
        assert target.is_file(), host
        assert BEGIN_MARKER in target.read_text(encoding="utf-8")

    cli._sync_project_claude_section("disable", tmp_path, assume_yes=False)
    for guidance in HOSTS.values():
        assert not (tmp_path / guidance.filename).exists()


# --- standing loops consent fragment ---------------------------------------


def _fragment_source_bytes() -> bytes:
    repo_root = resolve_section_template(host="claude").parents[2]
    fragment_path = repo_root / "nWave" / "templates" / "loop-consent-fragment.md"
    return fragment_path.read_text(encoding="utf-8").strip().encode("utf-8")


@pytest.mark.parametrize("host", HOST_IDS)
def test_consent_fragment_bytes_match_source_verbatim(host: str) -> None:
    """Extract the fragment as spliced into each host's projection and compare
    its bytes against the fragment source file — not a hash of derived content
    against itself, an independent byte-for-byte extraction per host."""
    fragment_bytes = _fragment_source_bytes()
    content_bytes = load_section_content(host=host).encode("utf-8")

    start = content_bytes.find(fragment_bytes)
    assert start != -1, f"fragment not found verbatim in {host} projection"
    extracted = content_bytes[start : start + len(fragment_bytes)]
    assert extracted == fragment_bytes


def test_consent_fragment_semantics_and_token_cap() -> None:
    from scripts.measure_doc_tokens import count_tokens

    fragment = _fragment_source_bytes().decode("utf-8")
    lowered = fragment.lower()

    # Required semantics: optional/OFF, explicit repo+scope+mode+budget consent,
    # session-scoped with no restart/compact rearm, stop/status, details on demand.
    assert "off" in lowered
    assert "repo" in lowered and "scope" in lowered
    assert "mode" in lowered and "budget" in lowered
    assert "session" in lowered
    assert "restart" in lowered and "compaction" in lowered
    assert "stop" in lowered and "status" in lowered

    forbidden = ["auto-arm", "auto-rearm", "opt-out", "opt out", "on by default"]
    for term in forbidden:
        assert term not in lowered, f"forbidden term '{term}' found in fragment"

    token_count = count_tokens(fragment)
    assert token_count <= 51, f"fragment too large: {token_count} tokens (max 51)"
