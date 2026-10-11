"""Public update-consent continuity through the real ``nwave-ai`` CLI.

The subprocess owns an isolated HOME. Assertions read only the config the
command wrote and its public process result; no update service is patched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import time
import venv
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)
PINNED_SITE = Path(sysconfig.get_path("purelib"))


def _command(home: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ | {
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "PYTHONPATH": f"{REPO / 'src'}:{REPO}",
        "NO_COLOR": "1",
    }
    return subprocess.run(
        [str(PYTHON), "-P", "-m", "nwave_ai.cli", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_separate_global_update_permissions_are_explicit_revocable_and_preserve_choices(
    tmp_path: Path,
) -> None:
    """A retired key cannot grant consent; each new grant has its own lifetime."""
    home, project = tmp_path / "home", tmp_path / "project"
    project.mkdir()
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(parents=True)
    original = {
        "schema-version": 1,
        "update_check": {"frequency": "daily"},
        "documentation": {"density": "full", "expansion_prompt": False},
        "install": {"target_platforms": ["codex"], "dev_mode": True},
        "operator_choice": {"retain": ["one", "two"]},
    }
    config.write_text(json.dumps(original), encoding="utf-8")

    check_on = _command(home, project, "update", "consent", "check", "on")
    assert check_on.returncode == 0, (
        "WHAT: the public check-consent command failed. WHY: the user must grant "
        "checks separately from installation. HOW: accept update consent check on "
        f"and persist only that permission. stderr={check_on.stderr!r}"
    )
    after_check = json.loads(config.read_text(encoding="utf-8"))
    assert after_check.get("updates") == {"check": True, "install": False}, (
        "WHAT: granting checks also granted installation or failed to persist checks. "
        "WHY: the two global permissions are independent and default off. "
        "HOW: persist updates.check=true and updates.install=false."
    )

    before_unconfirmed_install = config.read_bytes()
    unconfirmed_install = _command(home, project, "update", "consent", "install", "on")
    assert (
        unconfirmed_install.returncode != 0
        and config.read_bytes() == before_unconfirmed_install
    ), (
        "WHAT: install consent succeeded or changed config without legacy-session closure confirmation. "
        "WHY: the first install grant requires an explicit attestation before any config mutation. "
        "HOW: refuse install on until --confirm-old-sessions-closed is supplied."
    )
    assert "--confirm-old-sessions-closed" in unconfirmed_install.stderr, (
        "WHAT: the install refusal omitted the confirmation needed to retry. "
        "WHY: the operator needs a clear safe path to grant installation. "
        "HOW: name --confirm-old-sessions-closed in the refusal."
    )

    # Approved initial-confirmation contract: the first install grant carries the
    # operator's one-time attestation that pre-registry sessions are closed.
    install_on = _command(
        home,
        project,
        "update",
        "consent",
        "install",
        "on",
        "--confirm-old-sessions-closed",
    )
    assert install_on.returncode == 0, (
        "WHAT: the public install-consent command failed. WHY: installation needs "
        "a separate explicit grant. HOW: accept update consent install on. "
        f"stderr={install_on.stderr!r}"
    )
    after_install = json.loads(config.read_text(encoding="utf-8"))
    assert after_install.get("updates") == {"check": True, "install": True}, (
        "WHAT: the install grant lost the check grant or failed to persist itself. "
        "WHY: each consent is independent. HOW: merge the chosen permission into "
        "the existing global updates block."
    )

    before_unconfirmed_launch = config.read_bytes()
    unconfirmed_launch = _command(
        home, project, "update", "consent", "controlled-launch", "on"
    )
    assert (
        unconfirmed_launch.returncode != 0
        and config.read_bytes() == before_unconfirmed_launch
    ), (
        "WHAT: controlled-launch consent succeeded or changed config without its commitment. "
        "WHY: install consent cannot silently grant authority to launch managed hosts. "
        "HOW: refuse until --confirm-controlled-launch is supplied."
    )
    assert "--confirm-controlled-launch" in unconfirmed_launch.stderr, (
        "WHAT: controlled-launch refusal omitted the separate confirmation. "
        "WHY: the operator must know how to make the distinct commitment. "
        "HOW: name --confirm-controlled-launch in the refusal."
    )

    check_off = _command(home, project, "update", "consent", "check", "off")
    install_off = _command(home, project, "update", "consent", "install", "off")
    assert check_off.returncode == install_off.returncode == 0, (
        "WHAT: a permission could not be revoked through the public CLI. "
        "WHY: each automatic action requires continuing user consent. "
        "HOW: accept off for each permission and persist both false."
    )
    revoked = json.loads(config.read_text(encoding="utf-8"))
    assert revoked.get("updates") == {"check": False, "install": False}, (
        "WHAT: one or both automatic update permissions remained enabled after revocation. "
        "WHY: revocation must stop future startup actions. "
        "HOW: persist both permissions as false."
    )
    for key in ("documentation", "install", "operator_choice"):
        assert revoked.get(key) == original[key], (
            f"WHAT: consent changes altered the unrelated {key} choice. "
            "WHY: config writes must preserve all explicit user choices. "
            "HOW: merge only the updates permission field through the config writer."
        )
    assert revoked.get("update_check") in (None, original["update_check"]), (
        "WHAT: retired update_check was transformed into a new permission. "
        "WHY: the retired key grants neither automatic action. "
        "HOW: ignore or remove the retired key without converting its value."
    )


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"fixture git {args!r} failed: {result.stderr}"


def _active_project(root: Path, *, wip: str | None = None) -> None:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Update Oracle")
    _git(root, "config", "user.email", "oracle@example.invalid")
    config = root / ".nwave" / "config.json"
    config.parent.mkdir()
    config.write_text('{"schema-version":1,"enabled":true}', encoding="utf-8")
    (root / "README.md").write_text("Active nWave project\n", encoding="utf-8")
    if wip == "des":
        handover = root / ".nwave" / "des" / "handover.json"
        handover.parent.mkdir()
        handover.write_text('{"work":"in progress"}', encoding="utf-8")
    if wip == "feature":
        feature = root / "docs" / "feature" / "current" / "brief.md"
        feature.parent.mkdir(parents=True)
        feature.write_text("# Work in progress\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture baseline")
    if wip == "dirty":
        (root / "README.md").write_text("Unsaved work\n", encoding="utf-8")


def _startup_environment(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Own both executable siblings and all external effects inside tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(environment)
    bin_dir = environment / "bin"
    python = bin_dir / "python"
    events = tmp_path / "external-events.jsonl"
    tools = tmp_path / "tools"
    tools.mkdir()
    # The real CLI reads its installed distribution's origin before it may
    # replace a package. Supply index-shaped metadata in the isolated import
    # environment; an absent direct_url.json is the observed public-index case.
    distribution = tmp_path / "nwave_ai-1.4.0.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: nwave-ai\nVersion: 1.4.0\n",
        encoding="utf-8",
    )
    (distribution / "top_level.txt").write_text("nwave_ai\n", encoding="utf-8")
    fake_external = (
        "#!" + str(python) + "\n"
        "import json, os, pathlib, sys\n"
        "with pathlib.Path(os.environ['UPDATE_ORACLE_EVENTS']).open('a') as out:\n"
        "    out.write(json.dumps({'tool': pathlib.Path(sys.argv[0]).name, "
        "'argv': sys.argv[1:]}) + '\\n')\n"
        "sys.exit(71)\n"
    )
    # The update command itself is real. Only the package manager and the
    # owned DES executable stand at controlled external process boundaries.
    console = bin_dir / "nwave-ai"
    console.write_text(
        "#!" + str(python) + "\n"
        "from nwave_ai.cli import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    console.chmod(0o755)
    for path in (bin_dir / "des", tools / "uv"):
        path.write_text(fake_external, encoding="utf-8")
        path.chmod(0o755)
    # Replace only the external HTTP boundary, never a product module. The
    # response proves a check occurred without access to the public network.
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        "import io, json, os, pathlib, urllib.request\n"
        "class Response(io.BytesIO):\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *args): self.close()\n"
        "def controlled_release(url, *, timeout):\n"
        "    with pathlib.Path(os.environ['UPDATE_ORACLE_EVENTS']).open('a') as out:\n"
        "        out.write(json.dumps({'tool':'public-index', 'url':url, "
        "'timeout':timeout}) + '\\n')\n"
        '    return Response(b\'{"releases":{"999.0.0":[{"yanked":false}]}}\')\n'
        "urllib.request.urlopen = controlled_release\n",
        encoding="utf-8",
    )
    env = os.environ | {
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "PYTHONPATH": f"{tmp_path}:{REPO / 'src'}:{REPO}:{PINNED_SITE}",
        "PATH": f"{tools}:{os.environ.get('PATH', '')}",
        "NWAVE_INSTALLER": "uv",
        "UPDATE_ORACLE_EVENTS": str(events),
        "NO_COLOR": "1",
    }
    return python, events, env


def _session_start(
    python: Path, root: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(python),
            "-P",
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "session-start",
        ],
        cwd=root,
        env=env,
        input=json.dumps(
            {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(root)}
        ),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _events(path: Path) -> list[dict[str, object]]:
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def test_update_refuses_missing_persisted_host_destinations_before_replacement(
    tmp_path: Path,
) -> None:
    """Recorded install provenance controls refusal before replacement."""
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    config = tmp_path / "home" / ".nwave" / "config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                },
            }
        ),
        encoding="utf-8",
    )
    # The selected destination differs from the process's ambient override.
    # The old config has no binding for either, so neither may receive a sync.
    alternate = tmp_path / "alternate-codex"
    env["CODEX_HOME"] = str(alternate)
    result = subprocess.run(
        [str(python.with_name("nwave-ai")), "update", "--yes", "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    refusal = result.stdout + result.stderr
    assert result.returncode != 0 and "install-provenance" in refusal, (
        "WHAT: update accepted a legacy install with no recorded host destinations. "
        "WHY: replaying it from ambient overrides can redirect the selected host. "
        f"HOW: refuse at install-provenance before package replacement. output={refusal!r}"
    )
    assert "host" in refusal.lower() and "HOW:" in refusal, (
        "WHAT: the missing destination refusal omitted its cause or recovery. "
        "WHY: the user needs to record exact host paths before retrying. "
        "HOW: name the missing persisted host destinations and the explicit repair."
    )
    assert [event["tool"] for event in _events(events)] == ["public-index"], (
        "WHAT: missing host provenance launched a package manager or DES process. "
        "WHY: the target cannot be replayed safely and replacement is destructive. "
        "HOW: stop after release discovery and before every mutating stage."
    )
    assert not alternate.exists(), (
        "WHAT: refusal wrote to the ambient Codex destination. "
        "WHY: an absent persisted host path cannot authorize a new destination. "
        "HOW: leave the ambient host untouched until explicit provenance exists."
    )

    # A complete destination does not turn a recorded source-checkout choice
    # into permission to replace it with a public stable package.
    recorded_dev = {
        "schema-version": 1,
        "install": {
            "target_platforms": ["codex"],
            "dev_mode": True,
            "host_paths": {
                "agents_home": env["NWAVE_AGENTS_HOME"],
                "claude_config_dir": env["CLAUDE_CONFIG_DIR"],
                "codex_config_dir": env["CODEX_HOME"],
            },
        },
    }
    config.write_text(json.dumps(recorded_dev), encoding="utf-8")
    before_choice = config.read_bytes()
    distribution = tmp_path / "nwave_ai-1.4.0.dist-info"
    before_source = {path.name: path.read_bytes() for path in distribution.iterdir()}
    before_events = _events(events)
    dev_refusal = subprocess.run(
        [str(python.with_name("nwave-ai")), "update", "--yes", "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    dev_report = dev_refusal.stdout + dev_refusal.stderr
    assert dev_refusal.returncode != 0 and "selected-mode" in dev_report, (
        "WHAT: update accepted the recorded dev-mode install for a stable package. "
        "WHY: stable package assets cannot preserve the selected source-checkout mode. "
        f"HOW: refuse at selected-mode before replacement. output={dev_report!r}"
    )
    assert "--dev" in dev_report and "HOW:" in dev_report, (
        "WHAT: the dev-mode refusal did not explain how to keep the selected source. "
        "WHY: the user must update from the source checkout explicitly. "
        "HOW: name the --dev reinstall path in the refusal."
    )
    assert [event["tool"] for event in _events(events)[len(before_events) :]] == [
        "public-index"
    ], (
        "WHAT: dev-mode refusal launched package replacement or host sync. "
        "WHY: release discovery cannot authorize a stable package over dev assets. "
        "HOW: stop after the release check, before uv or DES."
    )
    assert (
        config.read_bytes() == before_choice
        and {path.name: path.read_bytes() for path in distribution.iterdir()}
        == before_source
    ), (
        "WHAT: the refused update changed the recorded dev choice or installed source metadata. "
        "WHY: refusal must preserve the selected installation and its source continuity. "
        "HOW: leave the global config and installed distribution unchanged."
    )


def test_update_syncs_the_recorded_host_instead_of_an_ambient_redirect(
    tmp_path: Path,
) -> None:
    """A completed real host sync uses the install's recorded destination."""
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    home = tmp_path / "home"
    recorded_codex = tmp_path / "recorded-codex"
    ambient_codex = tmp_path / "ambient-codex"
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": str(tmp_path / "recorded-claude"),
                        "codex_config_dir": str(recorded_codex),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    env["CODEX_HOME"] = str(ambient_codex)
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "ambient-claude")
    # Package replacement and release discovery are external boundaries. The
    # owned console still dispatches the real public install command.
    (tmp_path / "tools" / "uv").write_text(
        "#!" + str(python) + "\n"
        "import json, os, pathlib, sys\n"
        "with pathlib.Path(os.environ['UPDATE_ORACLE_EVENTS']).open('a') as out:\n"
        "    out.write(json.dumps({'tool':'uv','argv':sys.argv[1:]}) + '\\n')\n",
        encoding="utf-8",
    )
    console = python.with_name("nwave-ai")
    console.write_text(
        "#!" + str(python) + "\n"
        "import sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('nwave-ai 999.0.0')\n"
        "else:\n"
        "    from nwave_ai.cli import main\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    console.chmod(0o755)
    result = subprocess.run(
        [str(console), "update", "--yes", "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "synchronize-framework: completed" in output, (
        "WHAT: the selected host did not complete a real framework sync. "
        "WHY: a command trace alone cannot prove the persisted destination won. "
        f"HOW: run the owned public install after replacement and preflight. output={output!r}"
    )
    assert (
        any((recorded_codex / "agents").glob("nw-*.toml"))
        and (recorded_codex / "hooks.json").is_file()
        and not ambient_codex.exists()
    ), (
        "WHAT: update installed host assets at the ambient Codex path or missed "
        "the recorded one. WHY: the persisted host choice survives package sync. "
        "HOW: write Codex agents and hooks to the recorded CODEX_HOME only."
    )
    assert [event["tool"] for event in _events(events)][:2] == ["public-index", "uv"], (
        "WHAT: the update did not cross the controlled release and package boundaries. "
        "WHY: this scenario must exercise the update pipeline before real host sync. "
        "HOW: discover the newer release and complete the controlled replacement."
    )


@pytest.mark.parametrize("platform", ["codex", "claude-code"])
def test_update_install_mode_keeps_project_guidance_unchanged(
    tmp_path: Path, platform: str
) -> None:
    """The public install mode used by update changes only selected host assets."""
    home, project = tmp_path / "home", tmp_path / "project"
    project.mkdir()
    claude = project / "CLAUDE.md"
    agents = project / "AGENTS.md"
    claude.write_text("User-owned Claude guidance\n", encoding="utf-8")
    agents.write_text("User-owned Codex guidance\n", encoding="utf-8")
    before = (claude.read_bytes(), agents.read_bytes())

    installed = _command(
        home,
        project,
        "install",
        "--yes",
        "--no-project-guidance",
        "--platform",
        platform,
    )
    assert installed.returncode == 0, (
        "WHAT: the public selected-host install mode used by update failed. "
        "WHY: a successful update needs a real host synchronization path. "
        f"HOW: accept --no-project-guidance while installing {platform} assets. stderr={installed.stderr!r}"
    )
    assert (claude.read_bytes(), agents.read_bytes()) == before, (
        "WHAT: update's selected-host install mode changed project guidance. "
        "WHY: update permission does not consent to enrolling the current project. "
        "HOW: skip project CLAUDE.md and AGENTS.md writes for --no-project-guidance."
    )
    host_skills = home / (".agents" if platform == "codex" else ".claude") / "skills"
    assert host_skills.is_dir(), (
        f"WHAT: the {platform} host did not receive assets during the no-guidance install. "
        "WHY: skipping project guidance must still synchronize the selected host. "
        "HOW: run the existing host installer while omitting only project guidance."
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="process-state observation uses /proc"
)
def test_timed_out_replacement_reports_unknown_state_and_stops_its_descendant(
    tmp_path: Path,
) -> None:
    """A package manager timeout cannot leave a writer behind or claim later stages."""
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    home = tmp_path / "home"
    config = home / ".nwave" / "config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": str(home / ".claude"),
                        "codex_config_dir": str(home / ".codex"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    pid_path = tmp_path / "descendant.pid"
    marker = tmp_path / "late-package-write"
    fake_uv = tmp_path / "tools" / "uv"
    fake_uv.write_text(
        "#!" + str(python) + "\n"
        "import pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        + repr(
            "import pathlib, time; time.sleep(28); "
            f"pathlib.Path({str(marker)!r}).write_text('late', encoding='utf-8')"
        )
        + "])\n"
        + f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid), encoding='utf-8')\n"
        + "time.sleep(60)\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    result = subprocess.run(
        [str(python.with_name("nwave-ai")), "update", "--yes", "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    refusal = result.stdout + result.stderr
    assert (
        result.returncode != 0
        and "replace-package" in refusal
        and "timed out" in refusal
    ), (
        "WHAT: a timed-out package replacement did not name its failed stage. "
        "WHY: later stages cannot be trusted after a package manager timeout. "
        f"HOW: stop at replace-package and report its timeout. output={refusal!r}"
    )
    journal = json.loads(
        (
            Path(env["NWAVE_AGENTS_HOME"]) / ".nwave/activity/update-in-progress.json"
        ).read_text()
    )
    assert journal["running_stage"] == "replace-package"
    assert journal["completed_stages"] == []
    assert "verify-executable: completed" not in refusal and pid_path.exists(), (
        "WHAT: timeout claimed a later stage or failed to start the controlled descendant. "
        "WHY: this oracle must observe a real process-tree stop at the replacement boundary. "
        "HOW: report only prior completed stages and terminate the package-manager group."
    )
    child_pid = int(pid_path.read_text(encoding="utf-8"))
    time.sleep(4)
    process_state = Path(f"/proc/{child_pid}/stat")
    assert (
        not process_state.exists() or process_state.read_text().split()[2] == "Z"
    ) and not marker.exists(), (
        "WHAT: the timed-out package manager left its child able to write later. "
        "WHY: an orphan installer could race an operator's recovery attempt. "
        "HOW: terminate the whole process group and wait for it before reporting refusal."
    )
    assert [event["tool"] for event in _events(events)] == ["public-index"], (
        "WHAT: timeout launched DES migration or another external stage. "
        "WHY: a failed replacement cannot authorize later work. "
        "HOW: stop after the timed-out replacement stage."
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="POSIX launch signal and /proc required"
)
def test_signal_during_package_launch_cannot_leave_an_installer_descendant(
    tmp_path: Path,
) -> None:
    """A termination signal in the real Popen launch window is fail closed."""
    python, _events_path, env = _startup_environment(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    home = tmp_path / "home"
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": str(home / ".claude"),
                        "codex_config_dir": str(home / ".codex"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    pids = tmp_path / "launch-pids.json"
    marker = tmp_path / "late-launch-write"
    fake_uv = tmp_path / "tools" / "uv"
    fake_uv.write_text(
        "#!" + str(python) + "\n"
        "import json, os, pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        + repr(
            "import pathlib, time; time.sleep(15); "
            f"pathlib.Path({str(marker)!r}).write_text('late', encoding='utf-8')"
        )
        + "])\n"
        + f"pathlib.Path({str(pids)!r}).write_text(json.dumps({{'parent': os.getpid(), 'child': child.pid}}))\n"
        + "time.sleep(60)\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    # Intercept the operating-system process boundary only: Popen still starts
    # the real fake-uv executable. Signal arrives before Popen returns to the
    # updater, which is the precise launch/cleanup registration race.
    with (tmp_path / "sitecustomize.py").open("a", encoding="utf-8") as site:
        site.write(
            "import os, pathlib, signal, subprocess, time\n"
            "_real_launch = subprocess.Popen\n"
            "def _signal_after_launch(argv, *args, **kwargs):\n"
            "    process = _real_launch(argv, *args, **kwargs)\n"
            "    if isinstance(argv, (list, tuple)) and argv and pathlib.Path(argv[0]).name == 'uv':\n"
            f"        marker = pathlib.Path({str(pids)!r})\n"
            "        deadline = time.monotonic() + 5\n"
            "        while not marker.exists() and time.monotonic() < deadline:\n"
            "            time.sleep(0.01)\n"
            "        if marker.exists(): os.kill(os.getpid(), signal.SIGTERM)\n"
            "    return process\n"
            "subprocess.Popen = _signal_after_launch\n"
        )
    result = subprocess.run(
        [str(python.with_name("nwave-ai")), "update", "--yes", "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert pids.exists(), (
        "WHAT: the fake package manager did not reach the launch window. "
        "WHY: a refusal before launch cannot falsify this process race. "
        f"HOW: reach real package-manager Popen before injecting SIGTERM. output={result.stdout + result.stderr!r}"
    )
    launched = json.loads(pids.read_text(encoding="utf-8"))
    try:
        time.sleep(2)
        child_state = Path(f"/proc/{launched['child']}/stat")
        assert (
            not child_state.exists() or child_state.read_text().split()[2] == "Z"
        ) and not marker.exists(), (
            "WHAT: a signal during package launch left an installer descendant alive. "
            "WHY: it could write after update refused and race manual recovery. "
            "HOW: cover Popen and cleanup registration as one interrupt-safe operation, "
            "then stop and reap the process group before returning."
        )
    finally:
        try:
            os.killpg(launched["parent"], 9)
        except ProcessLookupError:
            pass


def test_windows_update_refuses_before_package_replacement(
    tmp_path: Path,
) -> None:
    """Unsupported process-tree cleanup refuses the actual mutating update port."""
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "clean-project"
    _active_project(root)
    home = tmp_path / "home"
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "updates": {"check": True, "install": True},
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": str(home / ".claude"),
                        "codex_config_dir": str(home / ".codex"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    with (tmp_path / "sitecustomize.py").open("a", encoding="utf-8") as site:
        site.write("import sys\nsys.platform = 'win32'\n")
    response = subprocess.run(
        [
            str(python),
            "-P",
            "-m",
            "nwave_ai.cli",
            "update",
            "--yes",
            "--root",
            str(root),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert response.returncode == 1
    rendered = response.stdout + response.stderr
    assert "platform-process-tree" in rendered and "Windows" in rendered, (
        "WHAT: update concealed the Windows process-tree refusal. "
        "WHY: explicit consent cannot make unverified descendant cleanup safe. "
        "HOW: surface the pre-mutation platform refusal."
    )
    assert [event["tool"] for event in _events(events)] == ["public-index"], (
        "WHAT: update launched package replacement on Windows. "
        "WHY: the platform process-tree boundary has no verified safe installer cleanup. "
        "HOW: stop after release discovery, before uv or DES."
    )


def test_native_startup_never_spends_automatic_update_permissions(
    tmp_path: Path,
) -> None:
    """Native startup preserves framing and never checks or installs releases."""
    python, events, env = _startup_environment(tmp_path)
    config = tmp_path / "home" / ".nwave" / "config.json"
    config.parent.mkdir()
    base = {"schema-version": 1, "update_check": {"frequency": "daily"}}

    root = tmp_path / "clean"
    _active_project(root)
    config.write_text(json.dumps(base), encoding="utf-8")
    off = _session_start(python, root, env)
    assert off.returncode == 0 and _events(events) == [], (
        "WHAT: startup checked or installed with only retired update_check. "
        "WHY: neither new permission has been granted. HOW: keep both off by default "
        f"and ignore the retired key. stderr={off.stderr!r}"
    )
    assert "Automatic update" not in off.stdout + off.stderr, (
        "WHAT: startup reported an automatic update before either permission was granted. "
        "WHY: retired update_check is not consent and cannot produce update noise. "
        "HOW: return no update context until the new check permission is true."
    )
    assert len(off.stdout.splitlines()) == 1 and json.loads(off.stdout), (
        "WHAT: SessionStart did not emit one valid JSON object. WHY: the host "
        "consumes one hook response. HOW: combine route and update notices in one JSON."
    )

    config.write_text(
        json.dumps(base | {"updates": {"check": True, "install": False}}),
        encoding="utf-8",
    )
    check_only = _session_start(python, root, env)
    assert check_only.returncode == 0 and _events(events) == []
    assert len(check_only.stdout.splitlines()) == 1 and json.loads(check_only.stdout), (
        "WHAT: the check notice broke SessionStart JSON framing. WHY: the host "
        "reads one object. HOW: fold the update observation into that object."
    )

    config.write_text(
        json.dumps(
            base
            | {"updates": {"check": True, "install": True, "controlled_launch": True}}
        ),
        encoding="utf-8",
    )
    consented = _session_start(python, root, env)
    assert consented.returncode == 0 and _events(events) == []
    assert len(consented.stdout.splitlines()) == 1 and json.loads(consented.stdout)


def test_startup_install_refuses_when_another_repository_has_unfinished_v3_work(
    tmp_path: Path,
) -> None:
    """A clean startup repository cannot attest global installation quiescence."""
    python, events, env = _startup_environment(tmp_path)
    current = tmp_path / "current-project"
    historical = tmp_path / "historical-project"
    _active_project(current)
    _active_project(historical)
    execution_log = (
        historical / "docs" / "feature" / "unfinished" / "execution-log.json"
    )
    execution_log.parent.mkdir(parents=True)
    execution_log.write_text(
        json.dumps(
            {
                "schema_version": "3.0",
                "events": [
                    {
                        "sid": "01-01",
                        "p": "PREPARE",
                        "s": "EXECUTED",
                        "d": "PASS",
                        "t": "2026-09-28T10:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # This is historical workflow state, not a dirty-tree shortcut. Both
    # repositories appear clean to a local git-status-only startup check.
    _git(historical, "add", ".")
    _git(historical, "commit", "-qm", "historical wave in progress")

    home = tmp_path / "home"
    config = home / ".nwave" / "config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema-version": 1,
                "updates": {"check": True, "install": True},
                "install": {
                    "target_platforms": ["codex"],
                    "dev_mode": False,
                    "host_paths": {
                        "agents_home": str(home),
                        "claude_config_dir": str(home / ".claude"),
                        "codex_config_dir": str(home / ".codex"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = _session_start(python, current, env)
    observed = result.stdout + result.stderr
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 1, (
        "WHAT: a cross-repository update refusal broke the SessionStart reply. "
        "WHY: the host still needs one route notice. "
        f"HOW: emit one valid JSON object with a safe refusal. stderr={result.stderr!r}"
    )
    assert isinstance(json.loads(result.stdout), dict), (
        "WHAT: SessionStart did not emit its JSON route notice. "
        "WHY: refusing an automatic install must preserve the host protocol. "
        "HOW: combine the route notice and update refusal in one JSON object."
    )
    assert all(event["tool"] not in {"uv", "des"} for event in _events(events)), (
        "WHAT: consented startup launched package replacement or host sync while "
        "another repository held unfinished v3 work. WHY: the installation is "
        "global and the clean current repository does not prove global idle. "
        "HOW: refuse destructive update stages until all affected work is positively idle."
    )
    assert "Automatic update" in observed and any(
        term in observed.lower() for term in ("work", "idle", "v3", "unknown")
    ), (
        "WHAT: startup did not explain its global work-state refusal. "
        "WHY: local cleanliness cannot prove another repository's v3 wave finished. "
        "HOW: name the unknown or active work and give a safe retry path."
    )


def test_startup_updater_import_failure_is_silent_without_consent_and_visible_with_it(
    tmp_path: Path,
) -> None:
    """A broken updater cannot make noise before consent or disappear after it."""
    python, events, env = _startup_environment(tmp_path)
    root = tmp_path / "clean-project"
    _active_project(root)
    config = tmp_path / "home" / ".nwave" / "config.json"
    config.parent.mkdir(exist_ok=True)
    with (tmp_path / "sitecustomize.py").open("a", encoding="utf-8") as site:
        site.write(
            "import builtins\n"
            "_real_update_import = builtins.__import__\n"
            "def _fail_update_import(name, *args, **kwargs):\n"
            "    if name == 'nwave_ai.update.startup':\n"
            "        raise ImportError('controlled updater import failure')\n"
            "    return _real_update_import(name, *args, **kwargs)\n"
            "builtins.__import__ = _fail_update_import\n"
        )

    config.write_text(json.dumps({"schema-version": 1}), encoding="utf-8")
    off = _session_start(python, root, env)
    assert off.returncode == 0 and len(off.stdout.splitlines()) == 1, (
        "WHAT: an updater import failure broke SessionStart without consent. "
        "WHY: the route notice must still reach the host. "
        f"HOW: preserve one valid JSON response. stderr={off.stderr!r}"
    )
    assert "Automatic update" not in off.stdout + off.stderr, (
        "WHAT: a broken updater emitted update noise before any permission was granted. "
        "WHY: an import failure is not itself consent to update checks or notices. "
        "HOW: read the separate global check permission before reporting the failure."
    )

    config.write_text(
        json.dumps({"schema-version": 1, "updates": {"check": True, "install": False}}),
        encoding="utf-8",
    )
    consented = _session_start(python, root, env)
    assert consented.returncode == 0 and len(consented.stdout.splitlines()) == 1, (
        "WHAT: a consented updater import failure broke SessionStart framing. "
        "WHY: the host still consumes one route response on a diagnostic failure. "
        f"HOW: add the refusal as context to one JSON object. stderr={consented.stderr!r}"
    )
    visible = consented.stdout + consented.stderr
    assert "Automatic update" in visible and "import" in visible.lower(), (
        "WHAT: a consented check hid the updater import failure. "
        "WHY: the user granted a check and must see why it could not run. "
        "HOW: report the import refusal with a repair path while preserving the route notice."
    )
    assert _events(events) == [], (
        "WHAT: the failed import reached release discovery or a package manager. "
        "WHY: no updater action can run before its entry point loads. "
        "HOW: stop before external effects and report only the consented refusal."
    )
