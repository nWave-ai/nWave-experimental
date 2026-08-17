"""E2E: Claude vs Codex install parity for the PyPI-shaped wheel.

Installs the SAME locally-built PyPI-shape wheel (``pypi_shape_wheel`` from
tests/e2e/conftest.py) into two isolated ``$HOME`` sandboxes -- one seeded
with only ``~/.claude/``, one seeded with only ``~/.codex/`` -- and checks
the real cross-host gap the existing suites leave uncovered:

  - both hosts get a representative, manifest-tracked install (parity)
  - Codex honestly ships no slash-command surface (it has none), and a
    foreign, non-nWave file sitting beside nWave's ``~/.codex/`` assets
    survives the install untouched
  - Claude's ``settings.json`` carries exactly ONE universal Bash
    PreToolUse registration -- not the retired independent
    ``pre-commit-attribution`` entry (commit 5aaf380a3, "retire duplicate
    attribution hook registration")
  - the installed ``des`` console script resolves a code fact through the
    Ast/TextSearch tiers with NO ``PYTHONPATH`` and no external
    Graphify/Tsunami binary -- the ordinary OSS install shape
  - the wheel itself carries no case-insensitive ``graphify`` residue

Reuses ``pypi_shape_wheel`` (tests/e2e/conftest.py) and the pure subprocess
helper + runtime-deps tuple from test_pypi_shape_install_chain.py -- no wheel
build/install machinery is duplicated here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tests.e2e.test_pypi_shape_install_chain import _RUNTIME_DEPS, _run


pytestmark = pytest.mark.e2e_smoke

_TEXT_SCAN_SUFFIXES = (".py", ".md", ".json", ".toml", ".yaml", ".yml", ".cfg")
_FOREIGN_MARKER_TEXT = "# pre-existing, not nWave-owned\n"

# The real, checked-in DeliveryContract fixture -- read from the checkout
# under test (never embedded as a dict literal here; see the identical
# rationale on `_DELIVERY_CONTRACT_FIXTURE` in
# tests/des/acceptance/test_dispatch_delivery_contract_locator.py, the
# in-process sibling this installed-shape test complements).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DELIVERY_CONTRACT_FIXTURE = (
    _REPO_ROOT / "docs" / "delivery-contracts" / "retarget-des-dispatch-contract.json"
)
# The fixture's `applicability.examine=true` axis requires its real, checked-in
# expectation charter namespace to exist under the dispatched `--repo-root` --
# copied verbatim (never embedded/synthesized here) so product validation is
# not weakened for this installed-shape test.
_EXPECTATION_CHARTER_REL = Path(
    "docs", "product", "expectations", "retarget-des-dispatch-contract"
)
_EXPECTATION_CHARTER_FIXTURE = _REPO_ROOT / _EXPECTATION_CHARTER_REL
_SKILLS_ROOT = {"claude": (".claude", "skills"), "codex": (".agents", "skills")}
_REPRESENTATIVE_AGENT_GLOB = {
    "claude": (".claude", "agents/nw", "*.md"),
    "codex": (".codex", "agents", "nw-*.toml"),
}


def _seed_claude(home: Path) -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        '{"permissions": {}, "hooks": {}}', encoding="utf-8"
    )


def _seed_codex(home: Path) -> None:
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "foreign-marker.toml").write_text(
        _FOREIGN_MARKER_TEXT, encoding="utf-8"
    )


def _install_into_home(venv: Path, home: Path, seed) -> str:
    """Seed *home*, then run the installed ``nwave-ai install`` console script."""
    seed(home)
    console = venv / "bin" / "nwave-ai"
    env = {
        "HOME": str(home),
        "PATH": f"{venv / 'bin'}:{os.environ.get('PATH', '')}",
        "NWAVE_AUTO_CONFIRM": "1",
    }
    proc = subprocess.run(
        [str(console), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        input=b"y\n" * 20,
        env=env,
        timeout=600,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"nwave-ai install failed for {home}:\n{out}"
    return out


@pytest.fixture(scope="module")
def _venv_with_wheel(pypi_shape_wheel: Path, tmp_path_factory) -> Path:
    """A venv with the local PyPI-shape wheel + runtime deps installed once."""
    venv = tmp_path_factory.mktemp("nwave_parity_venv") / "venv"
    code, out = _run([sys.executable, "-m", "venv", str(venv)])
    assert code == 0, f"venv creation failed:\n{out}"
    pip = venv / "bin" / "pip"
    code, out = _run([str(pip), "install", "--quiet", *_RUNTIME_DEPS], timeout=300)
    assert code == 0, f"runtime deps install failed:\n{out}"
    code, out = _run(
        [str(pip), "install", "--quiet", str(pypi_shape_wheel)], timeout=300
    )
    assert code == 0, f"wheel install failed:\n{out}"
    return venv


# Module-scoped cache: a host's prepared $HOME + install stdout is installed
# ONCE per host and reused by every fixture below that needs that host's
# install, so `host_install` and `_both_host_homes` never re-run the same
# install for the same host.
_PREPARED_HOST_HOMES: dict[str, tuple[Path, str]] = {}


def _prepared_host_home(host: str, venv: Path, tmp_path_factory) -> tuple[Path, str]:
    if host not in _PREPARED_HOST_HOMES:
        home = tmp_path_factory.mktemp(f"nwave_{host}_home")
        seed = _seed_claude if host == "claude" else _seed_codex
        stdout = _install_into_home(venv, home, seed)
        _PREPARED_HOST_HOMES[host] = (home, stdout)
    return _PREPARED_HOST_HOMES[host]


@pytest.fixture(scope="module", params=["claude", "codex"])
def host_install(request, _venv_with_wheel: Path, tmp_path_factory):
    """Install the same wheel into an isolated, single-host $HOME (parity matrix)."""
    host = request.param
    home, stdout = _prepared_host_home(host, _venv_with_wheel, tmp_path_factory)
    return host, home, stdout


@pytest.mark.e2e
class TestClaudeCodexInstallParity:
    """Representative install shape parity across the two isolated hosts."""

    def test_skills_manifest_and_representative_agent_present(self, host_install):
        host, home, _ = host_install
        base, sub = _SKILLS_ROOT[host]
        skills_dir = home / base / sub
        manifest = skills_dir / ".nwave-manifest.json"
        assert manifest.is_file(), f"{host}: skills manifest missing at {manifest}"
        assert "installed_skills" in json.loads(manifest.read_text())
        assert any(
            (p / "SKILL.md").is_file() for p in skills_dir.iterdir() if p.is_dir()
        ), f"{host}: no installed skill directory carries SKILL.md"

        agent_base, agent_sub, pattern = _REPRESENTATIVE_AGENT_GLOB[host]
        assert list((home / agent_base / agent_sub).glob(pattern)), (
            f"{host}: no representative agent asset matching {pattern!r}"
        )

    def test_codex_has_no_commands_surface_and_preserves_foreign_sibling(
        self, host_install
    ):
        host, home, _ = host_install
        if host != "codex":
            pytest.skip("commands-surface + foreign-sibling guard is Codex-specific")
        assert not (home / ".codex" / "commands").exists(), (
            "Codex has no slash-command surface; nWave must not create one"
        )
        assert (home / ".codex" / "agents").is_dir(), (
            "nWave did not write its own Codex assets alongside the foreign sibling"
        )
        foreign = home / ".codex" / "foreign-marker.toml"
        assert foreign.is_file() and foreign.read_text() == _FOREIGN_MARKER_TEXT, (
            "foreign, non-nWave ~/.codex/ sibling was not preserved by install"
        )

    def test_claude_settings_single_bash_registration_no_retired_markers(
        self, host_install
    ):
        host, home, _ = host_install
        if host != "claude":
            pytest.skip("settings.json shape guard is Claude-specific")
        settings_path = home / ".claude" / "settings.json"
        raw = settings_path.read_text(encoding="utf-8")
        assert "pre-commit-attribution" not in raw, (
            "retired independent attribution hook marker leaked into settings.json"
        )
        pre_tool_use = json.loads(raw)["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 1, (
            "expected exactly one universal Bash PreToolUse registration, found "
            f"{len(bash_entries)}: {bash_entries}"
        )


@pytest.mark.e2e
def test_installed_code_fact_resolves_via_ast_or_textsearch_without_pythonpath(
    _venv_with_wheel: Path, tmp_path: Path
) -> None:
    """The installed ``des`` console script degrades to Ast/TextSearch honestly.

    No ``PYTHONPATH`` is set (the env dict below fully replaces the process
    env) and no Graphify/Tsunami binary is on PATH -- the ordinary OSS shape.

    ``des code-fact``'s contract is stdout-is-pure-JSON (its own module
    docstring: "renders the existing result envelope as JSON"). Running
    pytest from a git checkout makes ``des.runtime.freshness`` emit its
    dev-checkout autoskip event -- correctly, on stderr (see
    ``des.runtime.freshness._emit_event``) -- so streams are captured
    SEPARATELY here rather than through the shared ``_run`` helper, which
    merges them on purpose for tests that want combined diagnostics.
    """
    site_packages = next((_venv_with_wheel / "lib").glob("python3.*/site-packages"))
    des_pkg = site_packages / "des"
    assert des_pkg.is_dir(), f"installed des package missing at {des_pkg}"

    des_script = _venv_with_wheel / "bin" / "des"
    env = {"HOME": str(tmp_path), "PATH": str(_venv_with_wheel / "bin")}
    proc = subprocess.run(
        [str(des_script), "code-fact", "query.atoms-in-file", "--root", str(des_pkg)],
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, (
        f"des code-fact failed:\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    )
    result = json.loads(out)
    assert result["provider"] in {"ast", "textsearch"}, (
        f"code-fact resolved via {result['provider']!r}, expected ast/textsearch "
        f"(no Graphify/Tsunami in an OSS install): {result}"
    )
    assert result["confidence"] in {"approx", "noisy"}
    assert "health.gate.code-fact.tsunami-absent" in result["health_events"], (
        "chain did not honestly LOUD-skip the absent Tsunami/Graphify tier"
    )
    # tsunami-absent health text is expected and legitimate; what must never
    # appear is an instruction to acquire/run a direct provider (dependency,
    # executable, or MCP server) instead of degrading through Ast/TextSearch.
    forbidden = re.compile(r"graphify|pip install|npm install|\bmcp\b", re.IGNORECASE)
    assert not forbidden.search(out), (
        f"code-fact output leaked a dependency/executable/MCP instruction: {out}"
    )


@pytest.mark.e2e
def test_installed_dispatch_accepts_valid_delivery_contract_without_pythonpath(
    host_install, _venv_with_wheel: Path, tmp_path: Path
) -> None:
    """The installed ``des dispatch`` console script accepts a schema-valid,
    repository-root-relative DeliveryContract, under both isolated Claude and
    Codex ``$HOME``s, with no ``PYTHONPATH`` -- the installed-shape gap this
    suite left uncovered: the SAME wheel's ``nWave/nWave/schemas/`` PyPI
    layout previously resolved to a nonexistent
    ``lib/python3.12/nWave/schemas/`` path (checkout/Claude-runtime-shaped
    locator applied to a PyPI/pipx site-packages install), so a schema-valid
    explicit contract exited 2 instead of dispatching.

    The real, checked-in fixture has ``applicability.examine=true``, so a
    genuine dispatch also requires its real, checked-in expectation charter
    namespace (``docs/product/expectations/retarget-des-dispatch-contract/``)
    to exist under ``--repo-root``; this test supplies both the real Contract
    and its real required charter, copied verbatim into the isolated repo,
    rather than weakening ``examine`` or synthesizing a charter.
    """
    host, home, _ = host_install
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    contract_rel = "delivery-contract.json"
    shutil.copyfile(_DELIVERY_CONTRACT_FIXTURE, repo_root / contract_rel)
    shutil.copytree(_EXPECTATION_CHARTER_FIXTURE, repo_root / _EXPECTATION_CHARTER_REL)

    des_script = _venv_with_wheel / "bin" / "des"
    env = {"HOME": str(home), "PATH": str(_venv_with_wheel / "bin")}
    proc = subprocess.run(
        [
            str(des_script),
            "dispatch",
            "--repo-root",
            str(repo_root),
            "--delivery-contract",
            contract_rel,
        ],
        capture_output=True,
        cwd=str(repo_root),
        env=env,
        timeout=60,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, (
        f"{host}: installed des dispatch rejected a schema-valid, installed "
        f"thin-delivery-contract schema lookup:\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    )
    digest = hashlib.sha256((repo_root / contract_rel).read_bytes()).hexdigest()
    expected_out = (
        f"THIN-DELIVERY-CONTRACT: {contract_rel}\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
    )
    assert out == expected_out, (
        f"{host}: installed des dispatch must emit exactly the thin-contract "
        f"locator + digest headers -- route, outcome, delivery-id and charter "
        f"paths stay in their canonical authorities, never copied into prompt "
        f"output:\n{out}"
    )


@pytest.mark.e2e
def test_wheel_has_no_case_insensitive_graphify_leak(pypi_shape_wheel: Path) -> None:
    """Wheel metadata + assets must carry no case-insensitive 'graphify' residue."""
    pattern = re.compile("graphify", re.IGNORECASE)
    hits: list[str] = []
    with zipfile.ZipFile(pypi_shape_wheel) as zf:
        for name in zf.namelist():
            if pattern.search(name):
                hits.append(f"member name: {name}")
                continue
            if name.endswith(_TEXT_SCAN_SUFFIXES) or name.endswith(
                ("METADATA", "RECORD")
            ):
                text = zf.read(name).decode("utf-8", errors="replace")
                if pattern.search(text):
                    hits.append(f"content: {name}")
    assert not hits, "case-insensitive 'graphify' leaked into the wheel:\n" + "\n".join(
        hits
    )


@pytest.fixture(scope="module")
def _both_host_homes(_venv_with_wheel: Path, tmp_path_factory):
    """The same wheel's claude and codex homes, side by side.

    Reuses `_prepared_host_home`'s module-scoped cache instead of installing
    again -- `host_install` already installed both hosts for this module.
    """
    return {
        host: _prepared_host_home(host, _venv_with_wheel, tmp_path_factory)[0]
        for host in ("claude", "codex")
    }


@pytest.mark.e2e
def test_same_wheel_installs_matching_skill_catalog_across_hosts(
    _both_host_homes,
) -> None:
    """The one wheel built for this run projects the same skill catalog onto both hosts."""
    claude_base, claude_sub = _SKILLS_ROOT["claude"]
    codex_base, codex_sub = _SKILLS_ROOT["codex"]
    claude_skills = _both_host_homes["claude"] / claude_base / claude_sub
    codex_skills = _both_host_homes["codex"] / codex_base / codex_sub

    def _skill_ids(root: Path) -> set[str]:
        return {
            p.name for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
        }

    claude_ids, codex_ids = _skill_ids(claude_skills), _skill_ids(codex_skills)
    assert claude_ids, "claude host installed zero skills"
    assert claude_ids == codex_ids, (
        "same-wheel install produced divergent skill catalogs across hosts: "
        f"claude-only={claude_ids - codex_ids}, codex-only={codex_ids - claude_ids}"
    )


@pytest.mark.e2e
def test_project_guidance_has_no_retired_loop_controller_and_temp_write_is_clean(
    host_install, _venv_with_wheel: Path, tmp_path: Path
) -> None:
    """Project enable injects no standing-loop controller or temp residue."""
    host, home, _ = host_install
    if host != "claude":
        pytest.skip("project enable --yes CLAUDE.md splice is Claude-specific here")
    project_root = tmp_path / "consenting_project"
    project_root.mkdir()
    console = _venv_with_wheel / "bin" / "nwave-ai"
    env = {
        "HOME": str(home),
        "PATH": f"{_venv_with_wheel / 'bin'}:{os.environ.get('PATH', '')}",
    }
    proc = subprocess.run(
        [str(console), "project", "enable", "--yes"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(project_root),
        env=env,
        timeout=60,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"project enable --yes failed:\n{out}"

    claude_md = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Standing Loops" not in claude_md
    assert "standing-loop" not in claude_md.casefold()
    leftover_tmp = list(project_root.glob(".claude-md-*.tmp"))
    assert not leftover_tmp, f"atomic-write temp file not cleaned up: {leftover_tmp}"


_SIBLING_USER_HOOK_COMMAND = "echo user-owned-sibling-hook"


def _seed_legacy_attribution_settings(
    claude_dir: Path, attribution_command: str
) -> None:
    """Seed *claude_dir*/settings.json with the retired independent attribution
    entry (exact historical command) plus a sibling user Bash hook, so a
    reinstall/upgrade exercises the real cleanup + universal-registration path."""
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "permissions": {},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {"type": "command", "command": attribution_command},
                                {
                                    "type": "command",
                                    "command": _SIBLING_USER_HOOK_COMMAND,
                                },
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.e2e
@pytest.mark.parametrize(
    "custom_config_dir,attribution_enabled",
    [(False, True), (False, False), (True, True), (True, False)],
    ids=["default_dir-on", "default_dir-off", "custom_dir-on", "custom_dir-off"],
)
def test_legacy_attribution_upgrade_collapses_to_one_universal_registration(
    _venv_with_wheel: Path,
    tmp_path_factory,
    custom_config_dir: bool,
    attribution_enabled: bool,
) -> None:
    """Reinstalling over a CA-004-era ``~/.claude/settings.json`` (the exact
    retired ``pre-commit-attribution`` command, ADR-CA-006 D6/D7) collapses to
    exactly one universal Bash PreToolUse registration, drops the legacy entry
    byte-for-byte, preserves the sibling user hook untouched, and preserves the
    pre-existing ``attribution.enabled`` preference -- across both the default
    and a ``CLAUDE_CONFIG_DIR``-relocated profile."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.install.attribution_utils import _attribution_hook_command
    from scripts.shared import hook_definitions as shared_hooks

    home = tmp_path_factory.mktemp("nwave_legacy_attr_home")
    claude_dir = (
        (home / "custom-profile" / ".claude")
        if custom_config_dir
        else (home / ".claude")
    )
    legacy_command = _attribution_hook_command(claude_dir)
    _seed_legacy_attribution_settings(claude_dir, legacy_command)

    nwave_dir = home / ".nwave"
    nwave_dir.mkdir(parents=True)
    (nwave_dir / "global-config.json").write_text(
        json.dumps({"attribution": {"enabled": attribution_enabled}}), encoding="utf-8"
    )

    console = _venv_with_wheel / "bin" / "nwave-ai"
    env = {
        "HOME": str(home),
        "PATH": f"{_venv_with_wheel / 'bin'}:{os.environ.get('PATH', '')}",
        "NWAVE_AUTO_CONFIRM": "1",
    }
    if custom_config_dir:
        env["CLAUDE_CONFIG_DIR"] = str(claude_dir)
    proc = subprocess.run(
        [str(console), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        input=b"y\n" * 20,
        env=env,
        timeout=600,
        check=False,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"upgrade install failed:\n{out}"

    raw = (claude_dir / "settings.json").read_text(encoding="utf-8")
    assert legacy_command not in raw, (
        f"exact retired pre-commit-attribution command survived upgrade:\n{raw}"
    )
    settings = json.loads(raw)
    pre_tool_use = settings["hooks"]["PreToolUse"]
    bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]

    # Stripping is per-hook, not per-entry: the seeded entry that bundled the
    # retired attribution hook alongside the sibling hook loses only the
    # DES-owned hook and survives (with the sibling intact) as its own Bash
    # entry; the reinstall then appends a brand-new universal Bash entry.
    # So there are two Bash-matcher entries after upgrade, not one.
    universal_commands = [
        h.get("command")
        for e in bash_entries
        for h in e.get("hooks", [])
        if shared_hooks._is_des_command(h.get("command", ""))
    ]
    assert len(universal_commands) == 1, (
        "expected exactly one nWave universal Bash PreToolUse command after "
        f"upgrade, found {len(universal_commands)}: {universal_commands}"
    )
    assert legacy_command not in universal_commands, (
        "the exact retired pre-commit-attribution command must not be one of "
        f"the surviving DES-owned commands: {universal_commands}"
    )

    sibling_entries = [
        e
        for e in bash_entries
        for h in e.get("hooks", [])
        if h.get("command") == _SIBLING_USER_HOOK_COMMAND
    ]
    assert len(sibling_entries) == 1, (
        "expected exactly one entry carrying the user-owned sibling Bash hook "
        f"after upgrade, found {len(sibling_entries)}: {sibling_entries}"
    )
    assert sibling_entries[0] == {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": _SIBLING_USER_HOOK_COMMAND}],
    }, (
        "user-owned sibling Bash hook entry was not preserved byte-semantically "
        f"(only the retired DES hook should have been stripped from it): "
        f"{sibling_entries[0]}"
    )

    preference = json.loads(
        (nwave_dir / "global-config.json").read_text(encoding="utf-8")
    )["attribution"]["enabled"]
    assert preference == attribution_enabled, (
        f"attribution.enabled preference was not preserved across upgrade: "
        f"expected {attribution_enabled}, got {preference}"
    )


@pytest.mark.e2e
def test_installed_universal_handler_emits_dual_trailer_on_real_commit(
    _venv_with_wheel: Path, tmp_path_factory
) -> None:
    """The installed universal PreToolUse handler still rewrites a real ``git
    commit`` Bash invocation to carry the dual ``Co-Authored-By`` trailer
    (Claude + nWave) once run against an actual, disposable git repo -- proving
    the installed console-script package, not just source-tree unit coverage."""
    home = tmp_path_factory.mktemp("nwave_dual_trailer_home")
    nwave_dir = home / ".nwave"
    nwave_dir.mkdir(parents=True)
    (nwave_dir / "global-config.json").write_text(
        json.dumps({"attribution": {"enabled": True}}), encoding="utf-8"
    )

    repo = tmp_path_factory.mktemp("nwave_dual_trailer_repo")
    marker_dir = repo / ".nwave"
    marker_dir.mkdir()
    (marker_dir / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": True}), encoding="utf-8"
    )
    env = {
        "HOME": str(home),
        "PATH": f"{_venv_with_wheel / 'bin'}:{os.environ.get('PATH', '')}",
    }
    for git_cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "e2e@nwave.ai"],
        ["git", "config", "user.name", "nWave E2E"],
    ):
        code, out = _run(git_cmd, cwd=repo, env=env)
        assert code == 0, f"{git_cmd} failed:\n{out}"
    (repo / "README.md").write_text("e2e dual-trailer fixture\n", encoding="utf-8")
    code, out = _run(["git", "add", "README.md"], cwd=repo, env=env)
    assert code == 0, f"git add failed:\n{out}"

    hook_input = json.dumps(
        {
            "tool_name": "Bash",
            "agent_id": "e2e-dual-trailer-probe",
            "cwd": str(repo),
            "tool_input": {"command": 'git commit -m "e2e dual-trailer probe"'},
        }
    )
    python = _venv_with_wheel / "bin" / "python3"
    proc = subprocess.run(
        [
            str(python),
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "pre-tool-use",
        ],
        input=hook_input.encode("utf-8"),
        capture_output=True,
        cwd=str(repo),
        env=env,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"universal handler rejected the commit mutation:\n"
        f"STDOUT:{proc.stdout.decode('utf-8', errors='replace')}\n"
        f"STDERR:{proc.stderr.decode('utf-8', errors='replace')}"
    )
    hook_out = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    rewritten_command = hook_out["hookSpecificOutput"]["updatedInput"]["command"]
    assert rewritten_command != 'git commit -m "e2e dual-trailer probe"', (
        "universal handler did not rewrite the commit command"
    )

    code, out = _run(["bash", "-c", rewritten_command], cwd=repo, env=env)
    assert code == 0, f"rewritten commit command failed:\n{out}"

    log_code, log_out = _run(["git", "log", "-1", "--format=%B"], cwd=repo, env=env)
    assert log_code == 0, f"git log failed:\n{log_out}"
    assert "Co-Authored-By: Claude <noreply@anthropic.com>" in log_out, (
        f"dual trailer missing Claude co-author line:\n{log_out}"
    )
    assert "Co-Authored-By: nWave <nwave@nwave.ai>" in log_out, (
        f"dual trailer missing nWave co-author line:\n{log_out}"
    )


def _seed_user_flat_nw_assets(parent: Path, noun: str) -> dict[str, object]:
    """Seed user-owned flat siblings beside the dedicated ``{noun}/nw/`` root.

    Covers the three shapes ``_is_legacy_flat_nw_symlink`` must NOT claim: a
    regular ``nw-*`` file, an ``nw-*`` directory, and an ``nw-*`` symlink whose
    raw target resolves OUTSIDE ``{noun}/nw/`` (a sibling foreign target) --
    every one of them starts with the ``nw-`` prefix the uninstaller globs on,
    so only the positive symlink-into-nested-dir check may remove anything.
    """
    parent.mkdir(parents=True, exist_ok=True)
    note_bytes = f"user-owned {noun} note, not nWave's\n".encode()
    note = parent / "nw-note.md"
    note.write_bytes(note_bytes)

    keep_dir = parent / "nw-dir"
    keep_dir.mkdir()
    keep_text = f"user-owned {noun} keepsake\n"
    (keep_dir / "keep.txt").write_text(keep_text, encoding="utf-8")

    foreign_text = f"foreign {noun} target, outside nw/\n"
    foreign_target = parent / "foreign-target.md"
    foreign_target.write_text(foreign_text, encoding="utf-8")
    symlink = parent / "nw-foreign.md"
    symlink.symlink_to("foreign-target.md")

    return {
        "note": note,
        "note_bytes": note_bytes,
        "keep_file": keep_dir / "keep.txt",
        "keep_text": keep_text,
        "foreign_target": foreign_target,
        "foreign_text": foreign_text,
        "symlink": symlink,
    }


def _assert_user_flat_nw_assets_intact(assets: dict[str, object], noun: str) -> None:
    assert assets["note"].is_file(), f"{noun}: user nw-note.md vanished"
    assert assets["note"].read_bytes() == assets["note_bytes"], (
        f"{noun}: user nw-note.md bytes changed"
    )
    assert assets["keep_file"].is_file(), f"{noun}: user nw-dir/keep.txt vanished"
    assert assets["keep_file"].read_text(encoding="utf-8") == assets["keep_text"], (
        f"{noun}: user nw-dir/keep.txt content changed"
    )
    assert assets["foreign_target"].is_file(), f"{noun}: foreign-target.md vanished"
    assert (
        assets["foreign_target"].read_text(encoding="utf-8") == assets["foreign_text"]
    ), f"{noun}: foreign-target.md content changed"
    symlink = assets["symlink"]
    assert symlink.is_symlink(), f"{noun}: nw-foreign.md is no longer a symlink"
    assert symlink.readlink() == Path("foreign-target.md"), (
        f"{noun}: nw-foreign.md symlink target changed: {symlink.readlink()}"
    )
    assert symlink.read_text(encoding="utf-8") == assets["foreign_text"], (
        f"{noun}: nw-foreign.md no longer resolves to its foreign target"
    )


@pytest.mark.e2e
def test_claude_settings_receipt_uninstall_roundtrip_preserves_user_sentinel(
    _venv_with_wheel: Path, tmp_path_factory
) -> None:
    """Uninstall reverses nWave's own settings.json edits via its receipt, leaving a
    pre-existing user key untouched, and clears the receipt itself (D1 pool semantics:
    a settings-provenance receipt is per-``claude_dir``, not per-install-run).

    Also covers user-owned flat ``nw-*`` siblings seeded under both
    ``agents/`` and ``commands/`` AFTER the real install (a file, a directory,
    and a symlink to a foreign sibling target) -- all must survive uninstall
    byte/target-identical, AND survive a second, idempotent uninstall run.

    The other side of the same contract: the nWave-owned assets the install
    actually wrote (manifest-tracked skills, the ``agents/nw/`` root) must
    disappear after uninstall and stay gone across the idempotent rerun --
    proving removal, not just preservation."""
    home = tmp_path_factory.mktemp("nwave_settings_roundtrip_home")
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    user_sentinel = {"userOwnedKey": "leave-me-alone"}
    claude_dir.joinpath("settings.json").write_text(
        json.dumps({"permissions": {}, "hooks": {}, **user_sentinel}), encoding="utf-8"
    )

    console = _venv_with_wheel / "bin" / "nwave-ai"
    env = {
        "HOME": str(home),
        "PATH": f"{_venv_with_wheel / 'bin'}:{os.environ.get('PATH', '')}",
        "NWAVE_AUTO_CONFIRM": "1",
    }
    install_proc = subprocess.run(
        [str(console), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        input=b"y\n" * 20,
        env=env,
        timeout=600,
        check=False,
    )
    assert install_proc.returncode == 0, (
        f"install failed:\n{install_proc.stdout.decode('utf-8', errors='replace')}"
    )

    receipt_key = hashlib.sha256(str(claude_dir.resolve()).encode("utf-8")).hexdigest()[
        :16
    ]
    receipt_path = home / ".nwave" / "install-receipts" / f"settings-{receipt_key}.json"
    assert receipt_path.is_file(), (
        f"install did not write a settings receipt at {receipt_path}"
    )

    skills_dir = claude_dir / "skills"
    skills_manifest_path = skills_dir / ".nwave-manifest.json"
    installed_skill_ids = set(
        json.loads(skills_manifest_path.read_text())["installed_skills"]
    )
    assert installed_skill_ids, "install wrote an empty skills manifest"
    agents_nw_dir = claude_dir / "agents" / "nw"
    assert list(agents_nw_dir.glob("*.md")), (
        "install did not write representative nWave-owned agent assets"
    )

    def _assert_nwave_owned_assets_removed() -> None:
        assert not skills_manifest_path.exists(), (
            f"uninstall left the nWave skills manifest behind: {skills_manifest_path}"
        )
        surviving = {sid for sid in installed_skill_ids if (skills_dir / sid).exists()}
        assert not surviving, (
            f"uninstall left nWave-owned skill directories behind: {surviving}"
        )
        assert not agents_nw_dir.exists(), (
            f"uninstall left the nWave-owned agents/nw/ root behind: {agents_nw_dir}"
        )

    user_assets = {
        noun: _seed_user_flat_nw_assets(claude_dir / noun, noun)
        for noun in ("agents", "commands")
    }

    uninstall_proc = subprocess.run(
        [str(console), "uninstall", "--target", str(claude_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=300,
        check=False,
    )
    out = uninstall_proc.stdout.decode("utf-8", errors="replace")
    assert uninstall_proc.returncode == 0, f"uninstall failed:\n{out}"

    settings_after = json.loads(claude_dir.joinpath("settings.json").read_text())
    assert settings_after.get("userOwnedKey") == "leave-me-alone", (
        f"uninstall clobbered a user-owned settings.json key: {settings_after}"
    )
    assert not receipt_path.exists(), (
        f"successful uninstall did not clear its settings receipt: {receipt_path}"
    )
    for noun, assets in user_assets.items():
        _assert_user_flat_nw_assets_intact(assets, noun)
    _assert_nwave_owned_assets_removed()

    second_uninstall_proc = subprocess.run(
        [str(console), "uninstall", "--target", str(claude_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=300,
        check=False,
    )
    second_out = second_uninstall_proc.stdout.decode("utf-8", errors="replace")
    assert second_uninstall_proc.returncode == 0, (
        f"second (idempotent) uninstall failed:\n{second_out}"
    )
    assert not receipt_path.exists(), (
        f"second uninstall did not keep settings receipt absent: {receipt_path}"
    )
    for noun, assets in user_assets.items():
        _assert_user_flat_nw_assets_intact(assets, noun)
    _assert_nwave_owned_assets_removed()
