"""Property-level acceptance tests for an explicit Codex install target."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.install.install_nwave import NWaveInstaller, show_installation_summary
from scripts.install.install_utils import Logger


CLAUDE_ACTIVATION = {"agents", "commands", "skills", "attribution"}
CODEX_ARTIFACTS = {"codex-skills", "codex-agents", "codex-des"}


def _installer(tmp_path: Path, monkeypatch, platform: str | set[str]) -> NWaveInstaller:
    """Build an installer whose target set is DECLARED, never detected.

    Accepts a set so a caller wanting several targets states them at
    construction. Reassigning `_platform_override` afterwards does not work and
    must not be attempted: the target set is resolved once, in `__init__`, so the
    ambient read happens where the caller controls the environment.
    """
    monkeypatch.setattr(
        "scripts.install.install_utils.PathUtils.get_claude_config_dir",
        lambda: tmp_path / ".claude",
    )
    targets = {platform} if isinstance(platform, str) else set(platform)
    subject = NWaveInstaller(platform_override=targets)
    subject.claude_config_dir = tmp_path / ".claude"
    subject.framework_source = tmp_path / "framework"
    subject.project_root = tmp_path / "project"
    return subject


def test_explicit_codex_selects_only_codex_activation_even_without_binary(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: explicit Codex users receive a Codex-loadable install.
    """
    subject = _installer(tmp_path, monkeypatch, "codex")
    # Negative control: discovery sees Claude only. Explicit selection is still
    # authoritative and must not inherit Claude activation.
    monkeypatch.setattr(
        "scripts.install.install_nwave.detect_target_platforms",
        lambda: {SimpleNamespace(value="claude_code")},
    )

    plugins = set(subject._create_plugin_registry(target_platforms={"codex"}).plugins)

    assert plugins >= CODEX_ARTIFACTS, (
        "WHAT: --platform codex omitted part of the Codex artifact universe. "
        f"Observed {sorted(plugins)!r}. WHY: explicit selection must override "
        "binary discovery. HOW: compose every Codex artifact plugin."
    )
    assert not (CLAUDE_ACTIVATION & plugins), (
        "WHAT: --platform codex selected Claude activation plugins "
        f"{sorted(CLAUDE_ACTIVATION & plugins)!r}. WHY: shared runtime support "
        "must not masquerade as Claude activation. HOW: register host activation "
        "plugins only for requested hosts."
    )


def test_codex_health_fails_closed_for_a_healthy_claude_only_tree(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: absent Codex roots/artifacts can never be reported healthy.
    """
    codex_home = tmp_path / "isolated-codex-home"
    agents_home = tmp_path / "isolated-agents-home"
    codex_home.mkdir()
    agents_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(agents_home))
    subject = _installer(tmp_path, monkeypatch, "codex")
    for name in (
        "nw-deliver",
        "nw-design",
        "nw-discuss",
        "nw-distill",
        "nw-devops",
        "nw-review",
    ):
        skill = subject.claude_config_dir / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("claude-only\n", encoding="utf-8")

    generic_result = SimpleNamespace(
        success=True, manifest_exists=True, missing_essential_files=[]
    )
    monkeypatch.setattr(
        "scripts.install.install_nwave.InstallationVerifier",
        lambda **_kwargs: SimpleNamespace(run_verification=lambda: generic_result),
    )
    monkeypatch.setattr(
        subject,
        "_create_plugin_registry",
        lambda **_kwargs: SimpleNamespace(verify_all=lambda _context: {}),
    )

    assert subject.validate_installation() is False, (
        "WHAT: Codex validation accepted a Claude-only tree. WHY: success must "
        "describe the requested host's usable artifact universe. HOW: verify "
        "~/.agents/skills plus CODEX_HOME native artifacts before success."
    )


def test_all_platform_health_composes_codex_validation(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: an all-platform install is healthy only when Codex is usable.
    """
    subject = _installer(tmp_path, monkeypatch, {"claude_code", "codex"})
    codex_validation_calls = 0

    def broken_codex_surface(*, verify_plugins: bool = True) -> bool:
        nonlocal codex_validation_calls
        assert verify_plugins is False
        codex_validation_calls += 1
        return False

    monkeypatch.setattr(subject, "_validate_codex_installation", broken_codex_surface)
    monkeypatch.setattr(
        "scripts.install.install_nwave.InstallationVerifier",
        lambda **_kwargs: SimpleNamespace(
            run_verification=lambda: SimpleNamespace(
                success=True, manifest_exists=True, missing_essential_files=[]
            )
        ),
    )
    monkeypatch.setattr(
        subject,
        "_create_plugin_registry",
        lambda **_kwargs: SimpleNamespace(verify_all=lambda _context: {}),
    )

    result = subject.validate_installation()

    assert codex_validation_calls == 1, (
        "WHAT: mixed/all health never exercised Codex validation. WHY: a generic "
        "Claude result cannot establish Codex usability. HOW: compose the Codex "
        "validator whenever codex is requested."
    )
    assert result is False, (
        "WHAT: mixed/all validation ignored a broken Codex surface. WHY: each "
        "requested host is part of the health claim. HOW: compose Codex "
        "validation whenever codex is in the requested platform set."
    )


def test_all_platform_registry_preserves_claude_and_codex_activation(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: selecting all keeps explicit Claude and Codex experiences.
    """
    subject = _installer(tmp_path, monkeypatch, "codex")
    requested = {"claude_code", "codex"}
    plugins = set(subject._create_plugin_registry(target_platforms=requested).plugins)

    assert plugins >= CLAUDE_ACTIVATION
    assert plugins >= CODEX_ARTIFACTS


def test_codex_validator_treats_empty_codex_home_as_default(
    tmp_path: Path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: empty CODEX_HOME validates the native default, never cwd.
    """
    monkeypatch.setenv("CODEX_HOME", "")
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    subject = _installer(tmp_path, monkeypatch, "codex")
    skills = tmp_path / ".agents" / "skills"
    for name in (
        "nw-deliver",
        "nw-design",
        "nw-discuss",
        "nw-distill",
        "nw-devops",
        "nw-review",
    ):
        artifact = skills / name / "SKILL.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("loadable\n", encoding="utf-8")
    (skills / ".nwave-manifest.json").write_text("{}\n", encoding="utf-8")
    codex_home = tmp_path / ".codex"
    (codex_home / "agents").mkdir(parents=True)
    for artifact in (
        codex_home / "agents" / ".nwave-agents-manifest.json",
        codex_home / "hooks.json",
        codex_home / ".nwave-des-manifest.json",
    ):
        artifact.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        subject,
        "_create_plugin_registry",
        lambda **_kwargs: SimpleNamespace(verify_all=lambda _context: {}),
    )

    assert subject._validate_codex_installation() is True

    (codex_home / "hooks.json").unlink()
    assert subject._validate_codex_installation() is False, (
        "WHAT: validator accepted a missing artifact after CODEX_HOME=''. "
        "WHY: empty means default, not disabled or current-directory. HOW: "
        "resolve once with the same non-empty override rule used by plugins."
    )


def test_codex_validator_treats_empty_agents_home_as_default(
    tmp_path: Path, monkeypatch
) -> None:
    """An empty test-isolation override must not redirect validation to cwd."""
    monkeypatch.setenv("NWAVE_AGENTS_HOME", "")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    subject = _installer(tmp_path, monkeypatch, "codex")

    skills = tmp_path / ".agents" / "skills"
    for name in (
        "nw-deliver",
        "nw-design",
        "nw-discuss",
        "nw-distill",
        "nw-devops",
        "nw-review",
    ):
        artifact = skills / name / "SKILL.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("loadable\n", encoding="utf-8")
    (skills / ".nwave-manifest.json").write_text("{}\n", encoding="utf-8")

    codex_home = tmp_path / ".codex"
    (codex_home / "agents").mkdir(parents=True)
    for artifact in (
        codex_home / "agents" / ".nwave-agents-manifest.json",
        codex_home / "hooks.json",
        codex_home / ".nwave-des-manifest.json",
    ):
        artifact.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        subject,
        "_create_plugin_registry",
        lambda **_kwargs: SimpleNamespace(verify_all=lambda _context: {}),
    )

    assert subject._validate_codex_installation() is True, (
        "WHAT: empty NWAVE_AGENTS_HOME did not fall back to HOME/.agents. "
        "WHY: an empty override must not make health depend on cwd. HOW: use "
        "the same truthy-override rule as the skills installer."
    )


def _render_codex_summary(logger: Logger, target: Path) -> None:
    """Drive the anticipated host-aware port, with a legacy-signature fallback."""
    try:
        show_installation_summary(logger, target, target_platforms={"codex"})
    except TypeError:
        show_installation_summary(logger, target)


def test_codex_completion_is_codex_native(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: completion tells Codex users how to start an nWave skill.
    """
    _render_codex_summary(Logger(log_file=None), tmp_path / ".codex")
    output = capsys.readouterr().out

    assert "Codex" in output
    assert "$nw-" in output
    assert "Claude Code" not in output
    assert "/nw-" not in output, (
        "WHAT: Codex completion advertises Claude slash commands. WHY: Codex "
        "invokes installed skills with $nw-*. HOW: render host-specific guidance."
    )


def test_mixed_completion_does_not_claim_a_single_claude_install_root(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: mixed completion names native roots without misleading users.
    """
    show_installation_summary(
        Logger(log_file=None),
        tmp_path / ".claude",
        target_platforms={"claude_code", "codex"},
    )
    output = capsys.readouterr().out

    singular_claim = f"Installed to: {tmp_path / '.claude'}"
    assert singular_claim not in output, (
        "WHAT: main completion reduced a mixed install to ~/.claude. WHY: Codex "
        "discovers skills and agents from native sibling roots. HOW: name all "
        "native roots, or omit the singular target claim."
    )


def test_mixed_completion_exposes_both_host_affordances_and_reopen_guidance(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: mixed users can start nWave correctly in either selected host.
    """
    show_installation_summary(
        Logger(log_file=None),
        tmp_path / ".claude",
        target_platforms={"claude_code", "codex"},
    )
    output = capsys.readouterr().out

    assert "/nw-design" in output
    assert "$nw-design" in output
    assert "reopen Claude Code" in output
    assert "reopen Codex" in output


def test_explicit_claude_code_behavior_is_preserved(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: Codex support does not change explicit Claude Code installs.
    """
    subject = _installer(tmp_path, monkeypatch, "claude_code")
    plugins = set(
        subject._create_plugin_registry(target_platforms={"claude_code"}).plugins
    )
    assert plugins >= CLAUDE_ACTIVATION
    assert not (CODEX_ARTIFACTS & plugins)

    show_installation_summary(Logger(log_file=None), tmp_path / ".claude")
    output = capsys.readouterr().out
    assert "Claude Code" in output
    assert "/nw-" in output
