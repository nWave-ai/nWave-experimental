"""K4 matrix row 22 -- install-scope escape.

First divergence: a paired campaign install touched the operator's REAL
configuration instead of staying inside the isolated fixture scope.
Confirmed mechanism: `scripts/install/install_nwave.py`'s
`NWaveInstaller.create_backup()` resolves, for a Codex-target install,
`agents_home = Path(os.environ.get("NWAVE_AGENTS_HOME", Path.home()))` --
`CLAUDE_CONFIG_DIR` never reaches this branch. Left unset, it falls through
to the operator's real `Path.home()` and writes `.nwave/backups` and reads
`.agents/skills` there.

ADMISSION falsifier: a sandbox install against a sentinel standing in for
the operator's real config must leave that sentinel byte-identical
afterward. `preflight._arm_env()` must pin `NWAVE_AGENTS_HOME` so this
stays true regardless of which platform an arm's setup happens to request.

This is a REAL run of the actual installer code (`NWaveInstaller.
create_backup`), not a mock: the sentinel `Path.home()` is monkeypatched to
a throwaway directory (never the operator's real one) so the escape, if
present, is observed rather than assumed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.analysis.k4 import preflight


install_nwave = pytest.importorskip("scripts.install.install_nwave")


def test_arm_env_pins_agents_home_keeping_codex_backup_off_the_sentinel_home(
    tmp_path, monkeypatch
):
    sentinel_home = tmp_path / "sentinel-operator-home"
    # Sentinels that have NOTHING to do with the isolated campaign -- they
    # must stay byte-identical no matter what the install does, because
    # nothing about a K4 campaign should ever write under the operator's
    # real home once NWAVE_AGENTS_HOME/CODEX_HOME are pinned.
    claude_sentinel = sentinel_home / ".claude" / "SENTINEL.txt"
    claude_sentinel.parent.mkdir(parents=True)
    claude_sentinel.write_text("do-not-touch\n", encoding="utf-8")
    claude_before = claude_sentinel.read_bytes()

    # A pre-existing Codex agent under the operator's real (sentinel) CODEX
    # HOME -- content that must never be read into a backup this campaign
    # produces, and whose directory must never be touched, once CODEX_HOME
    # is pinned to the workspace.
    codex_sentinel = sentinel_home / ".codex" / "agents" / "operator-agent.toml"
    codex_sentinel.parent.mkdir(parents=True)
    codex_sentinel.write_text("operator's real codex agent\n", encoding="utf-8")
    codex_before = codex_sentinel.read_bytes()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # A pre-existing Codex skill AND agent INSIDE the isolated workspace --
    # this is what create_codex_backup needs to find something to snapshot;
    # it must resolve here, not under the operator's real home, once
    # NWAVE_AGENTS_HOME/CODEX_HOME are pinned to the workspace.
    (workspace / ".agents" / "skills" / "existing-skill").mkdir(parents=True)
    (workspace / ".agents" / "skills" / "existing-skill" / "SKILL.md").write_text(
        "isolated pre-existing skill\n", encoding="utf-8"
    )
    (workspace / ".codex" / "agents").mkdir(parents=True)
    (workspace / ".codex" / "agents" / "isolated-agent.toml").write_text(
        "isolated pre-existing codex agent\n", encoding="utf-8"
    )

    rendered_env = {
        key: value.replace("{workspace}", str(workspace))
        for key, value in preflight._arm_env().items()
    }
    monkeypatch.setattr(Path, "home", lambda: sentinel_home)
    for key, value in rendered_env.items():
        monkeypatch.setenv(key, value)

    installer = install_nwave.NWaveInstaller(
        dry_run=False, platform_override={"codex"}, dev_mode=True
    )
    installer.create_backup()

    assert not (sentinel_home / ".nwave").exists(), (
        "the codex backup path escaped into the operator's real home even "
        "though _arm_env() was rendered and exported"
    )
    assert claude_sentinel.read_bytes() == claude_before, (
        "the .claude sentinel file must stay byte-identical after the install"
    )
    assert codex_sentinel.read_bytes() == codex_before, (
        "the .codex sentinel file must stay byte-identical after the install "
        "-- CODEX_HOME must be pinned, not just NWAVE_AGENTS_HOME"
    )
    assert (workspace / ".nwave" / "backups").exists(), (
        "the backup must land inside the isolated workspace instead"
    )
    backup_files = {
        p.read_text(encoding="utf-8")
        for p in (workspace / ".nwave" / "backups").rglob("*.toml")
    }
    assert "isolated pre-existing codex agent\n" in backup_files, (
        "the backup must have captured the ISOLATED codex agent"
    )
    assert "operator's real codex agent\n" not in backup_files, (
        "the backup must never capture the operator's real codex agent"
    )


def test_without_agents_home_the_codex_backup_escapes_to_operator_home(
    tmp_path, monkeypatch
):
    """Negative control: reproduces the confirmed row-22 mechanism directly,
    proving the assertions above are not vacuously true. Only CLAUDE_CONFIG_DIR
    is exported here -- exactly what a campaign predating this fix declared."""
    sentinel_home = tmp_path / "sentinel-operator-home"
    skill_file = sentinel_home / ".agents" / "skills" / "existing-skill" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("pre-existing operator skill\n", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(Path, "home", lambda: sentinel_home)
    monkeypatch.delenv("NWAVE_AGENTS_HOME", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(workspace / ".claude-k4"))

    installer = install_nwave.NWaveInstaller(
        dry_run=False, platform_override={"codex"}, dev_mode=True
    )
    installer.create_backup()

    assert (sentinel_home / ".nwave" / "backups").exists(), (
        "this negative control must reproduce the escape without "
        "NWAVE_AGENTS_HOME pinned, or the positive test above proves nothing"
    )


def test_full_real_install_leaves_every_operator_root_untouched(tmp_path, monkeypatch):
    """A real, full, non-dry-run `install_nwave.main()` run -- --dev
    --platform claude-code, no mocking of validate_installation/
    install_framework -- must never write into ANY of the operator's real
    ~/.claude, ~/.codex, or ~/.nwave, even though platform=claude-code never
    exercises the Codex-specific create_backup branch tested above.

    This is what actually surfaced two escapes NOT in the original K4-matrix
    row-22 finding, both independent of NWAVE_AGENTS_HOME/CODEX_HOME/
    CLAUDE_CONFIG_DIR and confirmed by running this exact test unfixed:

    1. `main()`'s own `record_install_metadata(Path.home() / ".nwave" /
       "global-config.json", ...)` call, hardcoded, unconditionally, for
       every non-dry-run install that resolves an installed version.
    2. `AttributionPlugin()` registered with no `config_dir`, defaulting to
       `Path.home() / ".nwave"` for its hooks/global-config
       read-and-write (migrate_legacy_hook, install_prepare_commit_msg_hook,
       read/write_global_config).

    Both now resolve through the SAME NWAVE_AGENTS_HOME override every
    other ~/.nwave-rooted call in install_nwave.py already honors.
    """
    sentinel_home = tmp_path / "sentinel-operator-home"
    sentinels = {
        "claude": sentinel_home / ".claude" / "SENTINEL.txt",
        "codex": sentinel_home / ".codex" / "SENTINEL.txt",
        "nwave": sentinel_home / ".nwave" / "SENTINEL.txt",
    }
    before_bytes: dict[str, bytes] = {}
    before_listing: dict[str, set[Path]] = {}
    for name, path in sentinels.items():
        path.parent.mkdir(parents=True)
        path.write_text(f"do-not-touch-{name}\n", encoding="utf-8")
        before_bytes[name] = path.read_bytes()
        before_listing[name] = set(path.parent.rglob("*"))

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".claude-k4").mkdir()

    monkeypatch.setattr(Path, "home", lambda: sentinel_home)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(workspace / ".claude-k4"))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(workspace))
    monkeypatch.setenv("CODEX_HOME", str(workspace / ".codex"))
    monkeypatch.setattr(
        sys, "argv", ["install_nwave.py", "--platform", "claude-code", "--dev"]
    )
    monkeypatch.chdir(workspace)

    code = install_nwave.main()

    assert code == 0, "the real install must succeed for this test to say anything"
    for name, path in sentinels.items():
        after_listing = set(path.parent.rglob("*"))
        assert path.read_bytes() == before_bytes[name], (
            f"the {name} sentinel file must stay byte-identical"
        )
        assert after_listing == before_listing[name], (
            f"no NEW file may appear under the operator's real .{name} root: "
            f"found {after_listing - before_listing[name]}"
        )
    assert (workspace / ".nwave" / "global-config.json").exists(), (
        "install provenance must land inside the isolated workspace instead"
    )


def test_apply_retention_never_reads_the_operators_real_global_config(
    tmp_path, monkeypatch
):
    """Read-escape (independent of NWAVE_AGENTS_HOME being pinned for
    WRITES): `create_backup()` always calls `apply_retention(max_count=None)`,
    which -- unfixed -- read `backups.max_count` from `Path.home() /
    ".nwave" / "global-config.json"` regardless of platform. A byte-diff
    sentinel test cannot see a READ, so this poisons the operator's real
    config with an INVALID `backups.max_count` that raises
    ConfigValidationError if it is ever actually read; the isolated install
    must complete without raising.
    """
    sentinel_home = tmp_path / "sentinel-operator-home"
    poisoned_config = sentinel_home / ".nwave" / "global-config.json"
    poisoned_config.parent.mkdir(parents=True)
    poisoned_config.write_text(
        json.dumps({"backups": {"max_count": -1}}), encoding="utf-8"
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    rendered_env = {
        key: value.replace("{workspace}", str(workspace))
        for key, value in preflight._arm_env().items()
    }
    monkeypatch.setattr(Path, "home", lambda: sentinel_home)
    for key, value in rendered_env.items():
        monkeypatch.setenv(key, value)

    installer = install_nwave.NWaveInstaller(
        dry_run=False, platform_override={"claude_code"}, dev_mode=True
    )
    installer.create_backup()  # must NOT raise ConfigValidationError


def test_probe_engagement_setup_step_env_keeps_operator_roots_untouched(
    tmp_path, monkeypatch
):
    """Row 22, found AGAIN by a real installed run (not a defect this suite
    previously covered): `probe_engagement`'s SETUP-step env built its OWN
    inline `{**os.environ, "CLAUDE_CONFIG_DIR": ...}` instead of reusing
    `_arm_env()`/`_rendered_arm_env()` -- pinning only CLAUDE_CONFIG_DIR, so
    `install_nwave.py`'s `record_install_metadata` fell through to the
    operator's real `Path.home()` and wrote `installed_version` there. The
    existing sentinel tests in this file cover the DELIVERY path
    (`_arm_env()` rendered for `ArmSpec`/the permission canary); none of
    them exercised `probe_engagement`'s own setup-step subprocess spawn.

    Real subprocess execution through `probe_engagement`'s actual
    `_run(step, cwd=workspace, env=env)` call: `nwave_setup_steps` is
    monkeypatched to ONE real `install_nwave.py --platform claude-code
    --dev` invocation (substituting for the full git-clone/seed multi-step
    setup, which needs network and a live SUT clone -- orthogonal to what
    this test verifies: whether `probe_engagement`'s OWN env construction
    isolates the install). `HOME` is set via `monkeypatch.setenv`, not
    `Path.home` patching -- this crosses a real subprocess boundary, and
    only an env var, not an in-process attribute patch, reaches the child.
    """
    sentinel_home = tmp_path / "sentinel-operator-home"
    sentinels = {
        "claude": sentinel_home / ".claude" / "SENTINEL.txt",
        "codex": sentinel_home / ".codex" / "SENTINEL.txt",
        "nwave": sentinel_home / ".nwave" / "SENTINEL.txt",
    }
    before_bytes: dict[str, bytes] = {}
    before_listing: dict[str, set[Path]] = {}
    for name, path in sentinels.items():
        path.parent.mkdir(parents=True)
        path.write_text(f"do-not-touch-{name}\n", encoding="utf-8")
        before_bytes[name] = path.read_bytes()
        before_listing[name] = set(path.parent.rglob("*"))

    # tests/conftest.py's session-scoped `_isolate_codex_and_agents_home`
    # ALREADY pins NWAVE_AGENTS_HOME/CODEX_HOME for the whole suite, to
    # protect the operator's real home from every OTHER test's real
    # installs. Left in place, that session-level pin -- inherited here via
    # `**os.environ` -- would cover for `probe_engagement`'s own missing
    # pin and mask exactly the bug under test. Removed here, per that
    # conftest's own documented escape hatch ("a test that wants the real
    # fallback semantics still overrides this with its own function-scoped
    # monkeypatch.delenv"), so this test genuinely exercises the
    # unset-fallback path a real, non-test invocation faces.
    monkeypatch.delenv("NWAVE_AGENTS_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("HOME", str(sentinel_home))

    real_setup_step = [
        sys.executable,
        install_nwave.__file__,
        "--platform",
        "claude-code",
        "--dev",
    ]
    monkeypatch.setattr(
        preflight, "nwave_setup_steps", lambda venv, auth_profile: [real_setup_step]
    )
    monkeypatch.setattr(preflight, "probe_installed_dispatch_help", lambda *a, **k: [])
    monkeypatch.setattr(preflight, "probe_delivery_permissions", lambda *a, **k: [])

    root = tmp_path / "root"
    verdict, detail = preflight.probe_engagement(
        root,
        tmp_path / "unused-venv",
        tmp_path / "unused-auth-profile",
        "claude-sonnet-5",
    )

    # "absent" is expected and fine here: the stubbed single-step setup runs
    # only install_nwave.py's --dev install, never `nwave-ai project
    # enable` (which needs the packaged `nwave-ai` console script, not this
    # raw script invocation) -- so workspace/CLAUDE.md never lands, and
    # probe_engagement correctly reports "absent". "broke" would mean the
    # real install itself failed for a reason unrelated to isolation, which
    # WOULD invalidate this test.
    assert verdict != "broke", (
        f"the real install step must succeed for this test to say anything "
        f"about isolation; got verdict={verdict!r} detail={detail!r}"
    )
    for name, path in sentinels.items():
        after_listing = set(path.parent.rglob("*"))
        assert path.read_bytes() == before_bytes[name], (
            f"the {name} sentinel file must stay byte-identical"
        )
        assert after_listing == before_listing[name], (
            f"no NEW file may appear under the operator's real .{name} root: "
            f"found {after_listing - before_listing[name]}"
        )
