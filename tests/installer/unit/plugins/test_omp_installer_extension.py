"""Focused public installation and refusal observations for the OMP projection."""

import importlib
import json
import os
import shutil
import subprocess
import venv
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext


class Logger:
    def __init__(self):
        self.lines = []

    def info(self, message):
        self.lines.append(message)

    error = info
    warn = info


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path))
    monkeypatch.setenv("PI_CONFIG_DIR", ".omp")
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("OMP_PROFILE", raising=False)
    monkeypatch.delenv("PI_PROFILE", raising=False)
    # A clean Python prevents editable/site-installed DES from satisfying the
    # missing-runtime probe; HOME and PATH must describe the same sandbox.
    python_home = tmp_path.parent / f"{tmp_path.name}-python"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(python_home)
    python_bin = python_home / ("Scripts" if os.name == "nt" else "bin")
    bun = shutil.which("bun")
    if bun:
        (python_bin / Path(bun).name).symlink_to(bun)
    monkeypatch.setenv("PATH", str(python_bin))
    root = Path(__file__).resolve().parents[4]
    return InstallContext(
        claude_dir=tmp_path / ".claude",
        scripts_dir=root / "scripts/install",
        templates_dir=root / "nWave/templates",
        logger=Logger(),
        project_root=root,
        framework_source=root / "nWave",
        target_platforms={"omp"},
    )


def plugin(module, name):
    implementation = importlib.import_module(f"scripts.install.plugins.{module}")
    assert hasattr(implementation, name), f"OMP installer is missing {name}"
    return getattr(implementation, name)()


def files(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_commands_project_public_population_and_remove_private_on_upgrade(context):
    commands = plugin("omp_commands_plugin", "OmpCommandsPlugin")
    target = Path.home() / ".omp/agent/commands"
    target.mkdir(parents=True)
    foreign = target / "personal.md"
    foreign.write_text("keep my command")
    before = files(Path.home())
    context.dev_mode = True
    assert commands.install(context).success
    dev_names = {path.stem for path in target.glob("nw-*.md")}
    context.dev_mode = False
    result = commands.install(context)
    assert result.success, result.message
    names = {path.stem for path in target.glob("nw-*.md")}
    assert "nw-deliver" in names
    assert names <= dev_names
    text = (target / "nw-deliver.md").read_text()
    assert "~/.claude/skills/" not in text
    assert "complete DISCUSS v2 result" in text
    assert (
        files(Path.home())[".omp/agent/commands/personal.md"]
        == before[".omp/agent/commands/personal.md"]
    )
    assert not context.claude_dir.exists()


def test_commands_dry_run_preserves_home(context):
    commands = plugin("omp_commands_plugin", "OmpCommandsPlugin")
    before = files(Path.home())
    context.dry_run = True
    result = commands.install(context)
    assert result.success, result.message
    assert "nw-deliver.md" in {path.name for path in result.installed_files}
    assert files(Path.home()) == before


def test_command_collision_refuses_without_overwriting(context):
    commands = plugin("omp_commands_plugin", "OmpCommandsPlugin")
    target = Path.home() / ".omp/agent/commands"
    target.mkdir(parents=True)
    (target / "nw-deliver.md").write_text("foreign command")
    before = files(Path.home())
    result = commands.install(context)
    assert not result.success
    assert "collision" in result.message
    assert files(Path.home()) == before


def test_extension_dry_run_reports_runtime_and_capability_ceiling(context):
    extension = plugin("omp_des_plugin", "OmpDESPlugin")
    context.dry_run = True
    before = files(Path.home())
    result = extension.install(context)
    assert result.success, result.message
    assert "nwave-des.ts" in {path.name for path in result.installed_files}
    assert "not enforced" in result.message
    assert files(Path.home()) == before


def test_extension_installs_quoted_python_and_host_neutral_runtime(context):
    from scripts.shared.install_paths import host_neutral_runtime_dir

    extension = plugin("omp_des_plugin", "OmpDESPlugin")
    runtime = host_neutral_runtime_dir()
    runtime.mkdir(parents=True)
    # A real symlink to the checkout runtime keeps the test's I/O small.
    (runtime / "des").symlink_to(
        context.project_root / "src/des", target_is_directory=True
    )
    result = extension.install(context)
    assert result.success, result.message
    shim = Path.home() / ".omp/agent/extensions/nwave-des.ts"
    text = shim.read_text()
    assert "{{" not in text
    assert json.dumps(str(runtime)) in text
    assert 'pi.on("tool_call"' in text
    assert not context.claude_dir.exists()


def test_missing_python_refuses_before_writing(context, monkeypatch):
    extension = plugin("omp_des_plugin", "OmpDESPlugin")
    monkeypatch.setattr(
        "scripts.install.plugins.omp_des_plugin.resolve_python_command_for_spawn",
        lambda: "/missing/python",
    )
    context.dry_run = True
    before = files(Path.home())
    result = extension.install(context)
    assert not result.success
    assert "Python >=3.10" in result.message
    assert "HOW:" in result.message
    assert files(Path.home()) == before


def test_installer_registers_commands_and_extension(context):
    from scripts.install.install_nwave import NWaveInstaller

    installer = NWaveInstaller.__new__(NWaveInstaller)
    installer.logger = context.logger
    registry = installer._create_plugin_registry(target_platforms={"omp"})
    assert {"des", "omp-skills", "omp-agents", "omp-commands", "omp-des"} <= set(
        registry.plugins
    )
    assert "des" in registry.plugins["omp-des"].get_dependencies()


def test_private_command_is_excluded_and_dev_upgrade_is_clean(context, tmp_path):
    project = tmp_path / "source"
    tasks = project / "nWave/tasks/nw"
    tasks.mkdir(parents=True)
    (project / "nWave/framework-catalog.yaml").write_text(
        "agents:\n  sample:\n    public: true\n  secret:\n    public: false\n"
        "commands:\n  public-command:\n    agents: [sample]\n"
        "  private-command:\n    agents: [secret]\n"
    )
    for name in ("public-command", "private-command"):
        (tasks / f"{name}.md").write_text(
            "---\ndescription: A command\n---\nRead ~/.claude/skills/example/SKILL.md."
        )
    context.project_root = project
    context.framework_source = project / "nWave"
    commands = plugin("omp_commands_plugin", "OmpCommandsPlugin")
    context.dev_mode = True
    assert commands.install(context).success
    target = Path.home() / ".omp/agent/commands"
    assert (target / "nw-private-command.md").exists()
    context.dev_mode = False
    assert commands.install(context).success
    assert (target / "nw-public-command.md").exists()
    assert not (target / "nw-private-command.md").exists()
    assert (
        "~/.omp/agent/skills/example/SKILL.md"
        in (target / "nw-public-command.md").read_text()
    )


def test_mixed_claude_omp_install_includes_host_neutral_runtime(context):
    from scripts.install.plugins.des_plugin import DESPlugin
    from scripts.shared.install_paths import host_neutral_runtime_dir

    context.target_platforms = {"claude_code", "omp"}
    assert set(DESPlugin.resolve_des_module_locations(context)) == {
        context.claude_dir / "lib/python/des",
        host_neutral_runtime_dir() / "des",
    }


def test_missing_runtime_refuses_before_extension_write(context):
    extension = plugin("omp_des_plugin", "OmpDESPlugin")
    before = files(Path.home())
    result = extension.install(context)
    assert not result.success
    assert "DES runtime import failed" in result.message
    assert "HOW:" in result.message
    assert files(Path.home()) == before


def test_shim_calls_real_adapter_and_returns_host_refusal(context, monkeypatch):
    from scripts.shared.install_paths import host_neutral_runtime_dir

    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Bun, OMP's extension runtime, is unavailable")
    monkeypatch.delenv("NWAVE_GIT_STASH_ALLOW", raising=False)
    monkeypatch.delenv("NWAVE_GIT_STASH_GUARD_TARGET_ROOT", raising=False)
    runtime = host_neutral_runtime_dir()
    runtime.mkdir(parents=True)
    (runtime / "des").symlink_to(
        context.project_root / "src/des", target_is_directory=True
    )
    result = plugin("omp_des_plugin", "OmpDESPlugin").install(context)
    assert result.success, result.message
    shim = Path.home() / ".omp/agent/extensions/nwave-des.ts"
    fixture = Path(__file__).parent / "fixtures/omp_des_probe.ts"
    completed = subprocess.run(
        [bun, str(fixture), str(shim)],
        cwd=Path.home(),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    observed, edits = [json.loads(line) for line in completed.stdout.splitlines()]
    assert observed["blocked"]["block"] is True
    assert "stash" in observed["blocked"]["reason"]
    assert observed["allowed"] is None
    assert [item["input"]["subagent_type"] for item in observed["batch"]] == [
        "nw-software-crafter",
        "nw-product-owner",
    ]
    assert observed["batch"][0]["input"]["prompt"] == "Shared instructions\n\nFirst"
    assert observed["write"][0]["input"]["file_path"] == "file.py"
    assert observed["uri"] == []
    assert observed["hashline"][0]["input"]["file_path"] == "file.py"
    assert [item["input"]["file_path"] for item in edits["hashlineMoves"]] == [
        "old.py",
        "new file.py",
        "execution-log.json",
    ]
    assert [item["input"]["file_path"] for item in edits["applyPatch"]] == [
        "first.py",
        "second.py",
    ]


def test_untrusted_command_manifest_refuses_without_mutation(context):
    target = Path.home() / ".omp/agent/commands"
    target.mkdir(parents=True)
    (target / ".nwave-commands-manifest.json").write_text(
        '{"installed_commands": "nw-deliver", "version": "1.0"}'
    )
    before = files(Path.home())
    result = plugin("omp_commands_plugin", "OmpCommandsPlugin").install(context)
    assert not result.success
    assert "manifest" in result.message
    assert files(Path.home()) == before


def test_uninstall_removes_commands_and_extension_but_preserves_foreign_files(context):
    from scripts.install.uninstall_nwave import NWaveUninstaller
    from scripts.shared.install_paths import host_neutral_runtime_dir

    runtime = host_neutral_runtime_dir()
    runtime.mkdir(parents=True)
    (runtime / "des").symlink_to(
        context.project_root / "src/des", target_is_directory=True
    )
    assert plugin("omp_commands_plugin", "OmpCommandsPlugin").install(context).success
    assert plugin("omp_des_plugin", "OmpDESPlugin").install(context).success
    commands = Path.home() / ".omp/agent/commands"
    extensions = Path.home() / ".omp/agent/extensions"
    (commands / "personal.md").write_text("preserve")
    (extensions / "personal.ts").write_text("preserve extension")
    uninstaller = NWaveUninstaller(force=True)
    uninstaller.logger = context.logger
    uninstaller.remove_omp_assets()
    assert not (commands / "nw-deliver.md").exists()
    assert not (extensions / "nwave-des.ts").exists()
    assert (commands / "personal.md").read_text() == "preserve"
    assert (extensions / "personal.ts").read_text() == "preserve extension"


@pytest.mark.parametrize("dev_mode", [False, True], ids=["public", "dev"])
def test_command_names_exactly_match_catalog_filtered_task_roster(context, dev_mode):
    import yaml

    catalog = yaml.safe_load(
        (context.project_root / "nWave/framework-catalog.yaml").read_text()
    )
    public_agents = {
        name
        for name, metadata in catalog["agents"].items()
        if metadata.get("public", True)
    }
    declared_commands = {
        name.replace("_", "-"): metadata
        for name, metadata in catalog["commands"].items()
    }
    roster = context.project_root / "nWave/tasks/nw"
    expected = {
        f"nw-{source.stem}"
        for source in roster.glob("*.md")
        if dev_mode
        or (
            source.stem in declared_commands
            and (
                not declared_commands[source.stem].get("agents")
                or any(
                    agent.replace("_", "-") in public_agents
                    for agent in declared_commands[source.stem]["agents"]
                )
            )
        )
    }
    context.dev_mode = dev_mode
    result = plugin("omp_commands_plugin", "OmpCommandsPlugin").install(context)
    assert result.success, result.message
    target = Path.home() / ".omp/agent/commands"
    installed = {source.stem for source in target.glob("nw-*.md")}
    assert installed == expected
    assert "nw-mutation-test" in installed
    if not dev_mode:
        assert "nw-refactor" not in installed


def test_public_reinstall_removes_manifest_owned_command_skill_projection(context):
    target = Path.home() / ".omp/agent/commands"
    target.mkdir(parents=True)
    (target / "nw-ab-agent-template.md").write_text("obsolete command-skill projection")
    (target / ".nwave-commands-manifest.json").write_text(
        '{"installed_commands": ["nw-ab-agent-template"], "version": "1.0"}'
    )
    result = plugin("omp_commands_plugin", "OmpCommandsPlugin").install(context)
    assert result.success, result.message
    assert not (target / "nw-ab-agent-template.md").exists()
    assert (target / "nw-deliver.md").exists()
