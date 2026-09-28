"""Installed nWave hosts expose the same wave-end preference behaviour.

This is a real installed-artifact observation.  It drives the public installer
CLI for each supported host in an isolated home, reads the skills the installer
actually wrote, and asks the runtime recorded by that install for its wave-end
offer.  It does not claim that a live host conversation happened.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


pytestmark = [pytest.mark.acceptance, pytest.mark.wiring_e2e]


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INSTALLER = REPOSITORY_ROOT / "scripts" / "install" / "install_nwave.py"
WAVES = ("discover", "diverge", "discuss", "design", "devops", "distill", "deliver")
PREFERENCES = ("ask", "always-skip")


@dataclass(frozen=True)
class InstalledHost:
    """The public files and runtime belonging to one isolated host install."""

    platform: str
    home: Path
    skills_dir: Path
    runtime: Path
    catalogue: frozenset[str]
    offer_rows: dict[str, tuple[str, ...]]


def _isolated_environment(home: Path) -> dict[str, str]:
    """Point every installer-resolved host location into one temporary home."""
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "OPENCODE_CONFIG_DIR": str(home / ".config" / "opencode"),
    }
    return environment


def _skills_directory(platform: str, home: Path) -> Path:
    """Return the host's documented installed skills discovery surface."""
    return {
        "claude-code": home / ".claude" / "skills",
        "codex": home / ".agents" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }[platform]


def _run(
    argv: list[str], *, environment: dict[str, str], failure_message: str
) -> subprocess.CompletedProcess[str]:
    """Run a public command and teach the crafter which installed contract failed."""
    completed = subprocess.run(
        argv,
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert completed.returncode == 0, (
        f"{failure_message}; expected the public command to complete successfully "
        "so its installed artifact could be observed. Make the installer/runtime "
        "complete this host journey.\n"
        f"--- stdout ---\n{completed.stdout[-4000:]}\n"
        f"--- stderr ---\n{completed.stderr[-4000:]}"
    )
    return completed


def _write_preference(home: Path, preference: str) -> None:
    """Give every host the same explicit preference, independent of bootstrap defaults."""
    config_dir = home / ".nwave"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "schema-version": 1,
                "documentation": {"expansion_prompt": preference},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _install_host(platform: str, home: Path) -> InstalledHost:
    """Install one host and capture its shipped catalogue and runtime responses."""
    home.mkdir()
    environment = _isolated_environment(home)
    _run(
        [sys.executable, str(INSTALLER), "--platform", platform],
        environment=environment,
        failure_message=(f"the real installer refused the {platform} install"),
    )

    skills_dir = _skills_directory(platform, home)
    assert skills_dir.is_dir(), (
        f"{platform} installed no skills at {skills_dir}; users cannot invoke a "
        "wave that was never written. Make the real installer write its public "
        "skills surface."
    )
    catalogue = frozenset(path.name for path in skills_dir.iterdir() if path.is_dir())

    for wave in WAVES:
        skill = skills_dir / f"nw-{wave}" / "SKILL.md"
        assert skill.is_file(), (
            f"{platform} omitted the nw-{wave} wave from its installed catalogue; "
            "that user cannot receive the wave-end offer. Include every public "
            "command skill in this host's shared visibility filter."
        )
        wave_entry = f"des wave-entry --repo-root <repository top level> --wave {wave}"
        assert wave_entry in skill.read_text(encoding="utf-8"), (
            f"the installed {platform} nw-{wave} skill does not resolve its "
            "wave-end preference at its own entry; preserve the declared wave "
            "entry instruction when rendering this host skill."
        )

    runtime_marker = home / ".nwave" / "active-runtime"
    runtime = Path(runtime_marker.read_text(encoding="utf-8").strip())
    assert (runtime / "des").is_dir(), (
        f"{platform} recorded no installed DES runtime at {runtime}; the host "
        "cannot answer its wave entry from an installed artifact. Install and "
        "record the runtime before reporting success."
    )

    origin = _run(
        [sys.executable, "-c", "import des; print(des.__file__)"],
        environment={**environment, "PYTHONPATH": str(runtime)},
        failure_message=(f"{platform} could not import its installed DES runtime"),
    ).stdout.strip()
    assert Path(origin).is_relative_to(runtime), (
        f"{platform} answered from {origin!r}, not its installed runtime {runtime}; "
        "the parity observation must exercise the runtime this host install owns. "
        "Correct the installed runtime path or import environment."
    )

    offer_rows: dict[str, tuple[str, ...]] = {}
    for preference in PREFERENCES:
        _write_preference(home, preference)
        response = _run(
            [
                sys.executable,
                "-m",
                "des.cli",
                "wave-entry",
                "--repo-root",
                str(REPOSITORY_ROOT),
                "--wave",
                "design",
            ],
            environment={**environment, "PYTHONPATH": str(runtime)},
            failure_message=(
                f"the installed {platform} wave entry failed under {preference}"
            ),
        )
        offer_rows[preference] = tuple(
            line
            for line in response.stdout.splitlines()
            if line.startswith("WAVE-END-OFFER")
        )
        assert offer_rows[preference], (
            f"the installed {platform} runtime produced no wave-end offer rows "
            f"under {preference}; users need the public decision emitted by their "
            "installed runtime. Emit the declared WAVE-END-OFFER contract."
        )

    return InstalledHost(platform, home, skills_dir, runtime, catalogue, offer_rows)


def test_installed_hosts_offer_the_same_wave_end_behaviour(tmp_path: Path) -> None:
    """Claude Code, Codex and OpenCode install equal catalogues and decisions.

    # bypass: this is one real-I/O, installed-artifact journey; generated inputs
    would neither widen its finite host/preference population nor prove wiring.
    """
    hosts = tuple(
        _install_host(platform, tmp_path / platform)
        for platform in ("claude-code", "codex", "opencode")
    )
    reference = hosts[0]

    for host in hosts[1:]:
        assert host.catalogue == reference.catalogue, (
            f"{host.platform} installed a different public skill catalogue than "
            f"{reference.platform}; wave-end behaviour must be available to every "
            "installed host. Route command skills through the same shared public "
            "visibility filter.\n"
            f"only {reference.platform}: {sorted(reference.catalogue - host.catalogue)}\n"
            f"only {host.platform}: {sorted(host.catalogue - reference.catalogue)}"
        )

    for preference in PREFERENCES:
        for host in hosts[1:]:
            assert host.offer_rows[preference] == reference.offer_rows[preference], (
                f"under {preference}, {host.platform} produced a different installed "
                f"wave-end decision from {reference.platform}; equal installed "
                "catalogues must deliver the same preference-controlled offer. "
                "Make the host install preserve the shared wave-entry contract.\n"
                f"{reference.platform}: {reference.offer_rows[preference]}\n"
                f"{host.platform}: {host.offer_rows[preference]}"
            )

    assert reference.offer_rows["ask"] != reference.offer_rows["always-skip"], (
        "the installed wave-end decision is constant across two explicit preferences; "
        "cross-host agreement would then prove no user-visible preference behaviour. "
        "Make the installed runtime resolve documentation.expansion_prompt."
    )
