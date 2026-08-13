"""RED acceptance contracts for the Codex bootstrap control plane.

The tests drive the public ``nwave-ai`` dispatch, not installer plugins or
helpers, and observe the complete isolated user state.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
from functools import lru_cache
from pathlib import Path

import pytest

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    load_public_agents,
)
from scripts.shared.frontmatter import parse_frontmatter
from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills


REPO = Path(__file__).resolve().parents[4]
PUBLIC_CLI = "import sys; from nwave_ai.cli import main; raise SystemExit(main())"


def _tree_state(root: Path) -> dict[str, tuple[str, str]]:
    """Return a deterministic, byte-sensitive view of a user's complete state."""
    state: dict[str, tuple[str, str]] = {}
    if not root.exists():
        return state
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            state[relative] = ("symlink", str(path.readlink()))
        elif path.is_dir():
            state[relative] = ("dir", "")
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            state[relative] = ("file", digest)
    return state


def _run(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "NWAVE_AGENTS_HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "PYTHONPATH": str(REPO),
            "NO_COLOR": "1",
            "PATH": "",
        }
    )
    return subprocess.run(
        [sys.executable, "-c", PUBLIC_CLI, *args],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def test_explicit_codex_install_never_uses_legacy_claude_runtime_migration(
    tmp_path: Path,
) -> None:
    """Codex-only installation leaves legacy Claude runtime migration out of its plan.

    This is intentionally a Codex-integration boundary, not a new specification
    for ordinary Claude installation.  It asserts only that the new path neither
    relocates pre-existing Claude bytes nor treats the retired migration
    receipt/journal as live control state. An explicit Codex target must also
    leave the entire Claude tree untouched. Mixed and all-platform installs do
    target Claude, whose installer-owned ``lib/python/des`` runtime is replaced
    on upgrade; that behavior belongs to Claude installation contracts.
    """
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    hooks_path = codex / "hooks.json"
    old_pythonpath = "/legacy/nwave/lib/python"
    old_des_command = (
        f"PYTHONPATH={old_pythonpath} /legacy/bin/python -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
    )
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": old_des_command,
                                    "timeout": 30,
                                }
                            ],
                        }
                    ]
                }
            }
        )
        + "\n"
    )
    (codex / ".nwave-des-manifest.json").write_text(
        json.dumps(
            {
                "hooks_file": str(hooks_path),
                "python_path": "/legacy/bin/python",
                "pythonpath": old_pythonpath,
            }
        )
        + "\n"
    )
    claude = home / ".claude"
    legacy_des = claude / "lib" / "python" / "des" / "user_extension.py"
    claude_config = claude / "settings.json"
    legacy_des.parent.mkdir(parents=True, exist_ok=True)
    legacy_des.write_bytes(b"Claude-owned DES extension must not relocate\n")
    claude_config.write_bytes(b'{"user_setting": "keep"}\n')
    legacy_des_before = legacy_des.read_bytes()
    claude_config_before = claude_config.read_bytes()
    config = home / ".nwave" / "global-config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"custom": {"allowed-outside-claude": True}}) + "\n")
    opencode_asset = home / ".opencode" / "user-config.json"
    copilot_asset = home / ".copilot" / "user-instructions.md"
    for asset, contents in (
        (opencode_asset, b'{"vendor":"opencode"}\n'),
        (copilot_asset, b"# user-owned Copilot instructions\n"),
    ):
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(contents)

    # A Codex-inclusive invocation must neither consume nor replace retired
    # migration control files.  Pre-seeding them makes accidental preflight,
    # restore, or recovery use externally observable.
    runtime = home / ".nwave" / "runtime"
    receipt = runtime / ".nwave-migration-receipt.json"
    journal = runtime / ".nwave-migration-journal.json"
    runtime.mkdir()
    receipt.write_bytes(b"foreign retired migration receipt\n")
    journal.write_bytes(b"foreign retired migration journal\n")

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode == 0, (
        "WHAT: an explicit Codex installation was refused by retired Claude-runtime "
        f"migration state. Observed stdout/stderr:\n{result.stdout}{result.stderr}\n"
        "WHY: Codex has no migration or restore lifecycle. HOW: omit legacy runtime "
        "preflight/recovery entirely."
    )
    assert legacy_des.read_bytes() == legacy_des_before, (
        "WHAT: the Codex integration relocated or changed a pre-existing Claude DES "
        "extension. WHY: the retired migration has no authority over Claude runtime "
        "bytes. HOW: leave legacy Claude runtime content in place."
    )
    assert claude_config.read_bytes() == claude_config_before, (
        "WHAT: an explicit Codex installation changed Claude configuration. WHY: "
        "Codex-only must not activate Claude configuration handling."
    )
    assert receipt.read_bytes() == b"foreign retired migration receipt\n"
    assert journal.read_bytes() == b"foreign retired migration journal\n"
    assert json.loads(config.read_text())["custom"] == {"allowed-outside-claude": True}
    assert opencode_asset.read_bytes() == b'{"vendor":"opencode"}\n'
    assert copilot_asset.read_bytes() == b"# user-owned Copilot instructions\n"


def _install(home: Path, platform: str = "codex") -> subprocess.CompletedProcess[str]:
    return _run(home, "install", "--yes", "--platform", platform)


def _current_codex_desired_skill_names(*, dev: bool) -> set[str]:
    """Derive the final Codex skill catalogue from the current source policy."""
    skills_source = REPO / "nWave" / "skills"
    entries = enumerate_skills(skills_source)
    if dev:
        return {entry.name for entry in entries}

    return {
        entry.name
        for entry in filter_public_skills(
            entries,
            load_public_agents(REPO / "nWave"),
            build_ownership_map(REPO / "nWave" / "agents"),
            detect_command_skills(skills_source),
        )
    }


def _legacy_codex_launcher_source(python_path: str, pythonpath: str) -> str:
    """The exact launcher body recorded by the three-field public manifest."""
    return (
        '"""nWave Codex DES launcher. Generated; reinstall to update."""\n'
        "import os\nimport subprocess\nimport sys\n\n"
        f"PYTHON_PATH = {json.dumps(python_path)}\n"
        f"PYTHONPATH = {json.dumps(pythonpath)}\n"
        'env = os.environ.copy()\nenv["PYTHONPATH"] = PYTHONPATH\n'
        'argv = [PYTHON_PATH, "-m", '
        '"des.adapters.drivers.hooks.claude_code_hook_adapter", "pre-tool-use"]\n'
        "completed = subprocess.run(argv, env=env, check=False)\n"
        "sys.exit(completed.returncode)\n"
    )


def _current_codex_launcher_source(python_path: str, pythonpath: str) -> str:
    """The exact current launcher bytes; keep this fixture implementation-local.

    Restated by hand, in lockstep with the generator, when the emitted spawn
    gained its explicit stdin decision and its wall-clock bound, and again when
    it started capturing the child's stdout/stderr into seekable temp files so
    it could translate an rc=2 block reason onto its own stderr.  Unlike
    ``_legacy_codex_launcher_source`` above -- a frozen fingerprint of bytes the
    public v1 bootstrap already wrote on real machines, which must never move --
    this one tracks whatever the installer emits today.
    """
    return (
        '"""nWave Codex DES launcher. Generated; reinstall to update."""\n'
        "import json\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "import tempfile\n\n"
        f"PYTHON_PATH = {json.dumps(python_path)}\n"
        f"PYTHONPATH = {json.dumps(pythonpath)}\n"
        'TIMEOUT_ENV = "NWAVE_CODEX_HOOK_TIMEOUT"\n'
        "DEFAULT_TIMEOUT_SECONDS = 25.0\n"
        "env = os.environ.copy()\n"
        'env["PYTHONPATH"] = PYTHONPATH\n'
        "argv = [\n"
        "    PYTHON_PATH,\n"
        '    "-m",\n'
        '    "des.adapters.drivers.hooks.claude_code_hook_adapter",\n'
        '    "pre-tool-use",\n'
        "]\n"
        "try:\n"
        "    bound = float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS))\n"
        "except (TypeError, ValueError):\n"
        "    bound = DEFAULT_TIMEOUT_SECONDS\n"
        "try:\n"
        "    stdin_channel = sys.stdin.fileno()\n"
        "except (AttributeError, OSError, ValueError):\n"
        "    stdin_channel = subprocess.DEVNULL\n"
        "with tempfile.TemporaryFile(\n"
        '    mode="w+", encoding="utf-8", errors="replace"\n'
        ") as stdout_tmp, tempfile.TemporaryFile(\n"
        '    mode="w+", encoding="utf-8", errors="replace"\n'
        ") as stderr_tmp:\n"
        "    try:\n"
        "        completed = subprocess.run(\n"
        "            argv,\n"
        "            env=env,\n"
        "            check=False,\n"
        "            stdin=stdin_channel,\n"
        "            timeout=bound,\n"
        "            stdout=stdout_tmp,\n"
        "            stderr=stderr_tmp,\n"
        "        )\n"
        "    except subprocess.TimeoutExpired:\n"
        "        sys.stderr.write(\n"
        '            f"WHAT: the nWave DES PreToolUse validation did not finish "\n'
        '            f"within its {bound:g}s bound and was killed.\\n"\n'
        '            f"WHY: a hook that never returns hangs the Codex session, "\n'
        '            f"so this launcher bounds its child and always yields.\\n"\n'
        '            f"HOW: re-run. If the validation genuinely needs longer, "\n'
        '            f"set {TIMEOUT_ENV}=<seconds>. Allowing the tool without "\n'
        '            f"a verdict.\\n"\n'
        "        )\n"
        "        sys.exit(0)\n"
        "    stdout_tmp.seek(0)\n"
        "    stderr_tmp.seek(0)\n"
        "    child_stdout = stdout_tmp.read()\n"
        "    child_stderr = stderr_tmp.read()\n"
        "sys.stdout.write(child_stdout)\n"
        "if completed.returncode == 2:\n"
        "    reason = child_stderr.strip()\n"
        "    if not reason:\n"
        "        try:\n"
        "            payload = json.loads(child_stdout)\n"
        "        except (TypeError, ValueError):\n"
        "            payload = None\n"
        "        candidate = None\n"
        "        if isinstance(payload, dict):\n"
        '            candidate = payload.get("reason")\n'
        "            if not (isinstance(candidate, str) and candidate.strip()):\n"
        '                hook_specific = payload.get("hookSpecificOutput")\n'
        "                candidate = (\n"
        '                    hook_specific.get("permissionDecisionReason")\n'
        "                    if isinstance(hook_specific, dict)\n"
        "                    else None\n"
        "                )\n"
        "        if isinstance(candidate, str) and candidate.strip():\n"
        "            reason = candidate.strip()\n"
        "    if not reason:\n"
        "        reason = (\n"
        '            "WHAT: the nWave DES PreToolUse hook blocked this tool "\n'
        '            "call (exit 2) without a readable reason.\\n"\n'
        '            "WHY: its child wrote nothing to stderr, and stdout was "\n'
        '            "not valid JSON with a `reason` or "\n'
        '            "`hookSpecificOutput.permissionDecisionReason` field.\\n"\n'
        '            "HOW: re-run to reproduce, or inspect the DES adapter "\n'
        '            "raw stdout above.\\n"\n'
        "        )\n"
        '    sys.stderr.write(reason if reason.endswith("\\n") else reason + "\\n")\n'
        "else:\n"
        "    sys.stderr.write(child_stderr)\n"
        "sys.exit(completed.returncode)\n"
    )


def _seed_legacy_direct_hook_with_orphan_launcher(
    home: Path, orphan_contents: str
) -> Path:
    """Seed only the reviewed legacy-direct + self-contained-orphan shape."""
    codex = home / ".codex"
    codex.mkdir(parents=True)
    hooks_path = codex / "hooks.json"
    legacy_python = "/legacy/nwave/bin/python"
    legacy_runtime = "/legacy/nwave/runtime"
    direct = (
        f"PYTHONPATH={legacy_runtime} {legacy_python} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
    )
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {"type": "command", "command": direct, "timeout": 30}
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n"
    )
    (codex / ".nwave-des-manifest.json").write_text(
        json.dumps(
            {
                "hooks_file": str(hooks_path),
                "python_path": legacy_python,
                "pythonpath": legacy_runtime,
            },
            indent=2,
        )
        + "\n"
    )
    orphan = codex / "nwave_claude_code_hook_adapter_launcher.py"
    orphan.write_text(orphan_contents, encoding="utf-8")
    return orphan


_V1_CODEX_BOOTSTRAP_REVISION = "02749ab6f"
_V1_CANDIDATE_PROFILE_REVISION = "a365196b1"

# Captured from the actual v1 Codex candidate.  The profile remains closed by
# payload rather than by names that may later leave the product.  Names are
# recovered only from the pinned revision and must agree with frontmatter.
_V1_CANDIDATE_UNLISTED_PUBLIC_SKILL_DIGEST_PROFILE = (
    "bc0d60b68de55abc36e8e273e729a36887f3808b4b6369ba58dbced76df2d0bb",
    "0ca4c2438ded122439db8ead2abbaf0f5522ba35e5fd091855e866476a328b55",
    "1fe801835ab0800b9e9c8fde3bef10b561aab9e84c55079acd888b526b24d86a",
    "ac8def71068d07bd072f9a18317ded0a206d77797335a38e77489d29d4ddfd8c",
    "b7b43b7189cff072c94517a8fab3e5b2688ec8386e7bbd0d4fb15b2553ded306",
    "a902b5d9b876411f2b73cf1fec3f6fb8681f70ec19155d500290eeaa8eb49f71",
    "5e4f3231f3b68ba4d1af796ff31c7fc80d6db2d7cc8f0558e2fb6a3f98d0bd98",
    "98daa12c8ffdc3dae9c3e5b3452f9afc107207e568ee495a8ea8f95bfdaa3b7f",
    "93d94f1d5a02293eab210028c0eb1fc4a143924dc7fd0e2c6331022a83d8f2fa",
    "95de6f0a9ab9235768bf902c0726d1284127796ce10e6377e71f2870bec114c3",
    "df6ddadeee36257d79806da2349a442f18c4597e39dbd2fe0f7ee8e1905e0be0",
    "12472465a632d881592b391d4665ab48231ecbc0d3527898e53c5c65527402dd",
    "3c5c450e4b1a07ff5f886c40c6cc8b4db3abfaa227acfb2a4f3c39ff46e8d68f",
    "8e92edd03e10e14b3795714fc24bcfd8ac1c87e7d4c05a7865e4008cfe21a47b",
    "019ec548e58da0640d82b989365041bfb079ada2e9396c781f7a4de500bc399a",
    "94c30ad58319bddf587a65696d269184fb5ab336584e3a4d1763a3a2e760f546",
    "9279af248efa74789f1ebf03d3ecd97bacd96c77adbd60dfe86ac30bb06fe7e9",
    "0747cf3379c1f311fa5ddfdcb4f16c62320995cca997e0c07256caa3729c75c9",
    "051b21677ae1506852393832c0903e1b9b34a658ea9fde3ad1db3ac5d3338e21",
    "87be14adc1430ddd1b042f41023799a2b2f87c57d0e08fdfb6fbad1d821902be",
    "e5233e5218bdc2d9408b81e9c0dbfd57939ad8b3ca7a280945eb9d7de7c24623",
    "f0683d0c8118c189bc6d3b2c1f5499e4dd2ae8c310fc43a2ed69b809f18f219b",
    "afbe4234a6d4c4c40a96c336e0b85528e968f258922af3021050b3dfd6c248f2",
    "3e3f460531b46c3e780cc992f81d8bb229784983a01f49c766d75e9b94b07f68",
    "51f0c0b27c941ef1f2e3613aecde8afad3db6e60c44b1f49fe2219d05598868c",
    "6fbe991edc39410df327803ceb3a1c5e48f9e55e08573de1870ff71b6378cfed",
    "c6c39bac491e1fc852c06e3e760c36ea992d62cb617f2c41a11fff3048d2060a",
)


def _render_codex_skill(source: str) -> bytes:
    """Render a skill with the current Codex installer rules, without imports."""
    rendered = "\n".join(
        line
        for line in source.split("\n")
        if not line.startswith(("user-invocable:", "disable-model-invocation:"))
    )
    for legacy_path, codex_path in (
        ("~/.claude/nWave/skills/", "~/.agents/skills/"),
        ("~/.claude/nWave/", "~/.codex/"),
        ("~/.claude/skills/", "~/.agents/skills/"),
        ("~/.claude/agents/", "~/.codex/agents/"),
        ("~/.claude/hooks/", "~/.codex/hooks/"),
    ):
        rendered = rendered.replace(legacy_path, codex_path)
    return rendered.encode("utf-8")


@lru_cache(maxsize=1)
def _pinned_v1_candidate_profile() -> dict[str, str]:
    """Recover the closed historical payload profile with path/name binding."""
    closed_digests = set(_V1_CANDIDATE_UNLISTED_PUBLIC_SKILL_DIGEST_PROFILE)
    assert len(_V1_CANDIDATE_UNLISTED_PUBLIC_SKILL_DIGEST_PROFILE) == 27
    assert len(closed_digests) == 27

    archive = subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            _V1_CANDIDATE_PROFILE_REVISION,
            "nWave/skills",
        ],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    selected: list[tuple[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as historical:
        for member in historical.getmembers():
            path = Path(member.name)
            if not member.isfile() or path.name != "SKILL.md":
                continue
            asset = historical.extractfile(member)
            assert asset is not None
            source = asset.read().decode("utf-8")
            digest = hashlib.sha256(_render_codex_skill(source)).hexdigest()
            if digest not in closed_digests:
                continue

            name = path.parent.name
            metadata, _ = parse_frontmatter(source)
            assert metadata is not None and metadata.get("name") == name, (
                "WHAT: a closed historical payload is not bound to its path name. "
                "WHY: digest membership alone cannot authorize relocation. HOW: "
                "require historical frontmatter name and directory name to agree."
            )
            selected.append((name, digest))

    assert len(selected) == 27
    assert len({name for name, _ in selected}) == 27
    assert {digest for _, digest in selected} == closed_digests
    return dict(selected)


def _render_v1_codex_skill(source: str) -> bytes:
    """Reproduce the v1 Codex installer: strip frontmatter fields only."""
    return "\n".join(
        line
        for line in source.split("\n")
        if not line.startswith(("user-invocable:", "disable-model-invocation:"))
    ).encode("utf-8")


def _pinned_v1_codex_public_skill(name: str) -> bytes:
    """Return the byte-exact Codex asset a v1 public command could omit.

    These are installer source assets, not name-shaped stand-ins: v1 wrote the
    Codex rendering of the public command skill (with the Claude-only
    frontmatter removed).  A legacy manifest therefore proves an omitted name
    only when this exact rendering is still present on disk.
    """
    historical = subprocess.run(
        [
            "git",
            "show",
            f"{_V1_CODEX_BOOTSTRAP_REVISION}:nWave/skills/{name}/SKILL.md",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return _render_v1_codex_skill(historical)


def _current_codex_public_skill(name: str) -> bytes:
    """The current asset must not be confused with the pinned v1 witness."""
    return _render_codex_skill(
        (REPO / "nWave" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    )


def _pinned_v1_candidate_codex_skill(name: str) -> bytes:
    """Render one fixed candidate-release asset, never the mutable worktree."""
    source = subprocess.run(
        [
            "git",
            "show",
            f"{_V1_CANDIDATE_PROFILE_REVISION}:nWave/skills/{name}/SKILL.md",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return _render_codex_skill(source)


def _assert_actual_v1_candidate_profile_matches_pinned_source() -> dict[str, str]:
    """Make candidate/profile drift an explicit test-review event.

    The opaque digest profile is closed.  Names are recovered only by matching
    those payloads in the fixed revision and verifying their frontmatter paths.
    """
    profile = _pinned_v1_candidate_profile()
    observed = {
        name: hashlib.sha256(_pinned_v1_candidate_codex_skill(name)).hexdigest()
        for name in profile
    }
    assert observed == profile, (
        "WHAT: the candidate's fixed v1 omission profile no longer matches pinned "
        "candidate revision a365196b1. WHY: historical ownership admission is a "
        "reviewed byte contract, not dynamic name discovery. HOW: explicitly review "
        "and update the closed profile for a new candidate release."
    )
    return profile


def _seed_v1_codex_bootstrap(
    home: Path, *, omitted_public_skills: tuple[str, ...]
) -> tuple[Path, Path, Path]:
    """Seed the narrow, corroborated v1 Codex ownership shape."""
    skills = home / ".agents" / "skills"
    catalogued = "nw-bugfix"
    for name in (catalogued, *omitted_public_skills):
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_bytes(_pinned_v1_codex_public_skill(name))
    (skills / ".nwave-manifest.json").write_text(
        json.dumps({"installed_skills": [catalogued], "version": "1.0"}) + "\n"
    )

    codex = home / ".codex"
    codex.mkdir(parents=True)
    launcher = codex / "nwave_claude_code_hook_adapter_launcher.py"
    pythonpath = str(home / ".nwave" / "runtime")
    launcher.write_text(_legacy_codex_launcher_source(sys.executable, pythonpath))
    hooks_path = codex / "hooks.json"
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": shlex.join(
                                        [sys.executable, str(launcher), "pre-tool-use"]
                                    ),
                                    "timeout": 30,
                                }
                            ],
                        }
                    ]
                }
            }
        )
        + "\n"
    )
    manifest = codex / ".nwave-des-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "hooks_file": str(hooks_path),
                "python_path": sys.executable,
                "pythonpath": pythonpath,
            }
        )
        + "\n"
    )
    return skills, hooks_path, manifest


def test_auto_detected_codex_is_part_of_the_effective_validation_set(
    tmp_path: Path,
) -> None:
    """B1: auto detection may not validate a different, Claude-only target set."""
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)

    result = _run(home, "install", "--yes", "--platform", "auto")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / ".codex" / "hooks.json").is_file()
    assert (home / ".agents" / "skills" / "nw-design" / "SKILL.md").is_file()
    assert "Codex deployment validated" in result.stdout


def test_public_cli_dev_codex_install_composes_the_ownership_preflight(
    tmp_path: Path,
) -> None:
    """The public CLI reaches the Codex ownership preflight on the dev path."""
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)

    result = _run(home, "install", "--yes", "--dev", "--platform", "codex")

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "AttributeError" not in output
    assert (home / ".agents" / "skills" / "nw-design" / "SKILL.md").is_file()
    assert (home / ".codex" / ".nwave-des-manifest.json").is_file()


@pytest.mark.parametrize("mixed", [False, True], ids=["codex", "mixed"])
def test_auto_detected_broken_codex_hook_is_not_reported_healthy(
    tmp_path: Path, mixed: bool
) -> None:
    """B1: auto mode cannot hide a broken Codex surface behind Claude success."""
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    if mixed:
        (home / ".claude").mkdir()
    (codex / "hooks.json").write_text('{"hooks": [ broken ]}\n')

    result = _run(home, "install", "--yes", "--platform", "auto")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "Codex deployment validated" not in result.stdout


def test_all_platform_reinstall_preserves_foreign_user_assets_and_config(
    tmp_path: Path,
) -> None:
    """All-platform re-install replaces nWave only and preserves user state."""
    home = tmp_path / "home"
    foreign = home / ".codex" / "foreign-user-setting.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text('{"owner":"user"}\n')
    config_path = home / ".nwave" / "global-config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"custom": {"keep": "user setting"}}) + "\n")

    first = _install(home, "all")
    assert first.returncode == 0, first.stdout + first.stderr
    second = _install(home, "all")
    assert second.returncode == 0, second.stdout + second.stderr
    assert foreign.read_text() == '{"owner":"user"}\n', (
        "WHAT: all-platform re-install changed a foreign Codex setting. WHY: an "
        "installation refresh owns nWave surfaces only. HOW: retain foreign files "
        "while replacing nWave artifacts."
    )
    assert json.loads(config_path.read_text())["custom"] == {"keep": "user setting"}, (
        "WHAT: all-platform re-install discarded a user global-config field. WHY: "
        "configuration migration must preserve user settings. HOW: merge nWave "
        "configuration changes without replacing unrelated keys."
    )


def test_explicit_codex_restore_is_a_noop_for_user_owned_codex_and_claude_state(
    tmp_path: Path,
) -> None:
    """Codex-only lifecycle explicitly excludes backup, migration, and restore."""
    home = tmp_path / "home"
    codex_asset = home / ".codex" / "my-user-setting.json"
    claude_asset = home / ".claude" / "nested" / "my-user-setting.json"
    claude_backup = home / ".claude" / "backups" / "nwave-user-backup" / "keep.txt"
    for path, contents in (
        (codex_asset, b'{"codex":"user-owned"}\n'),
        (claude_asset, b'{"claude":"user-owned"}\n'),
        (claude_backup, b"do not restore or prune this backup\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    codex_before = _tree_state(home / ".codex")
    claude_before = _tree_state(home / ".claude")

    restored = _run(home, "install", "--yes", "--platform", "codex", "--restore")

    assert restored.returncode == 0, (
        "WHAT: explicit Codex restore was not accepted as a no-op. "
        f"Observed stdout/stderr:\n{restored.stdout}{restored.stderr}\n"
        "WHY: backup, migration, and restore are irrelevant to the Codex-only "
        "lifecycle. HOW: complete this target without entering Claude restore logic."
    )
    assert (
        _tree_state(home / ".codex"),
        _tree_state(home / ".claude"),
    ) == (codex_before, claude_before), (
        "WHAT: explicit Codex restore changed user-owned Codex or Claude state. "
        "WHY: no restore authority exists for this lifecycle. HOW: leave both trees "
        "byte-identical and do not create, prune, or restore backups."
    )
    assert not (
        home / ".nwave" / "runtime" / ".nwave-migration-receipt.json"
    ).exists(), (
        "WHAT: explicit Codex restore created a legacy-runtime migration receipt. "
        "WHY: migration is excluded from this lifecycle. HOW: return from the Codex "
        "no-op before invoking the legacy migration transaction."
    )


def test_reinstall_after_interpreter_change_keeps_one_current_des_hook(
    tmp_path: Path,
) -> None:
    """B3: a launcher change replaces nWave's hook; it never appends a duplicate."""
    home = tmp_path / "home"
    first = _install(home)
    assert first.returncode == 0, first.stdout + first.stderr

    hooks_path = home / ".codex" / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    hooks_path.write_text(
        json.dumps(hooks).replace(sys.executable, "/obsolete/venv/bin/python")
    )

    second = _install(home)
    assert second.returncode == 0, second.stdout + second.stderr
    rendered = hooks_path.read_text()
    assert "/obsolete/venv/bin/python" not in rendered
    current = json.loads(rendered)["hooks"]
    pretool = [
        handler
        for group in current["PreToolUse"]
        for handler in group.get("hooks", [])
        if "nwave_claude_code_hook_adapter_launcher" in handler.get("command", "")
    ]
    assert len(pretool) == 1
    assert "SessionStart" not in current


def test_codex_only_install_has_no_claude_activation_surface(tmp_path: Path) -> None:
    """B4: Codex uses host-neutral runtime and leaves Claude state untouched."""
    home = tmp_path / "home"
    before = _tree_state(home / ".claude")

    result = _install(home)

    assert result.returncode == 0, result.stdout + result.stderr
    after = _tree_state(home / ".claude")
    assert after == before
    assert (home / ".nwave" / "runtime").is_dir()
    assert (home / ".codex" / ".nwave-des-manifest.json").is_file()


def test_normal_claude_manifest_reinstall_is_not_misclassified_as_legacy_runtime(
    tmp_path: Path,
) -> None:
    """A normal install manifest supports re-install; it is not migration input."""
    home = tmp_path / "home"
    config_path = home / ".nwave" / "global-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"custom": {"keep": "config value"}}) + "\n")

    first = _install(home, "claude-code")
    manifest_path = home / ".claude" / "nwave-manifest.txt"
    assert first.returncode == 0, first.stdout + first.stderr
    assert manifest_path.is_file(), (
        "WHAT: the first normal Claude install did not create its installation "
        "manifest. WHY: re-install must receive the product's own manifest shape. "
        "HOW: write the normal manifest before the subsequent public invocation."
    )

    second = _install(home, "claude-code")

    assert second.returncode == 0, (
        "WHAT: a normal generated Claude manifest was refused on re-install. "
        f"Observed stdout/stderr:\n{second.stdout}{second.stderr}\n"
        "WHY: current installation state is not legacy runtime migration input. "
        "HOW: recognise the generated manifest as normal install state."
    )
    assert json.loads(config_path.read_text())["custom"] == {"keep": "config value"}, (
        "WHAT: re-install discarded a user global-config field. WHY: the lifecycle "
        "migrates configuration while preserving user values. HOW: merge nWave "
        "configuration updates without replacing unrelated keys."
    )


@pytest.mark.parametrize(
    "hazard", ["collision", "tampered-manifest", "malformed-hooks"]
)
def test_unsafe_ownership_state_fails_closed_without_any_write(
    tmp_path: Path, hazard: str
) -> None:
    """B5: ambiguous ownership cannot permit partial install or foreign-data loss."""
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "foreign.json").write_text('{"must":"survive"}\n')
    if hazard == "collision":
        (codex / "agents").mkdir()
        (codex / "agents" / "nw-architect.toml").write_text("owner = 'foreign'\n")
    elif hazard == "tampered-manifest":
        (codex / ".nwave-des-manifest.json").write_text(
            '{"owner":"nwave","files":["../../foreign.json"]}\n'
        )
    else:
        (codex / "hooks.json").write_text('{"hooks": [ definitely-not-json }\n')
    before = _tree_state(home)

    result = _install(home)

    assert result.returncode != 0
    assert _tree_state(home) == before
    assert json.loads((codex / "foreign.json").read_text()) == {"must": "survive"}


def test_b5_failure_does_not_even_change_preexisting_claude_log_or_config_bytes(
    tmp_path: Path,
) -> None:
    """B5: fail-closed includes incidental logger/config writes outside Codex."""
    home = tmp_path / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True)
    (claude / "nwave-install.log").write_bytes(b"foreign-log-byte-sequence\n")
    (claude / "settings.json").write_bytes(b'{"foreign":true}\n')
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "hooks.json").write_text('{"hooks": [ definitely-not-json }\n')
    before = _tree_state(home)

    result = _install(home)

    assert result.returncode != 0
    assert _tree_state(home) == before
    assert (claude / "nwave-install.log").read_bytes() == b"foreign-log-byte-sequence\n"
    assert (claude / "settings.json").read_bytes() == b'{"foreign":true}\n'


def test_valid_manifest_does_not_authorize_unlisted_reserved_name_collision(
    tmp_path: Path,
) -> None:
    """B5: manifest ownership is per artifact, not a namespace-wide lease."""
    home = tmp_path / "home"
    agents = home / ".codex" / "agents"
    agents.mkdir(parents=True)
    (agents / "nw-owned.toml").write_text("name = 'owned fixture'\n")
    (agents / ".nwave-agents-manifest.json").write_text(
        json.dumps({"installed_agents": ["nw-owned"], "version": "1.0"}) + "\n"
    )
    collision = agents / "nw-foreign-extension.toml"
    collision.write_bytes(b"name = 'foreign reserved-name extension'\n")
    before = _tree_state(home)

    result = _install(home)

    assert result.returncode != 0
    assert _tree_state(home) == before
    assert collision.read_bytes() == b"name = 'foreign reserved-name extension'\n"


def test_canonical_des_manifest_cannot_adopt_a_foreign_launcher(
    tmp_path: Path,
) -> None:
    """B5: structural manifest validity is not proof of launcher ownership."""
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    hooks_path = codex / "hooks.json"
    hooks_path.write_text('{"hooks":{"PreToolUse":[]}}\n')
    launcher = codex / "nwave_claude_code_hook_adapter_launcher.py"
    launcher.write_bytes(b"# user-owned launcher at a reserved path\n")
    manifest = {
        "hooks_file": str(hooks_path),
        "python_path": sys.executable,
        "pythonpath": str(home / ".nwave" / "runtime"),
        "launcher_file": str(launcher),
    }
    (codex / ".nwave-des-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    before = _tree_state(home)

    result = _install(home)

    assert result.returncode != 0
    assert _tree_state(home) == before
    assert launcher.read_bytes() == b"# user-owned launcher at a reserved path\n"


def test_b3_reinstall_preserves_colocated_foreign_hook_and_unowned_adapter_string(
    tmp_path: Path,
) -> None:
    """B3: update only the proven-owned handler, never its foreign neighbours."""
    home = tmp_path / "home"
    first = _install(home)
    assert first.returncode == 0, first.stdout + first.stderr

    hooks_path = home / ".codex" / "hooks.json"
    doc = json.loads(hooks_path.read_text())
    pretool = doc["hooks"]["PreToolUse"]
    owned_group = next(
        group
        for group in pretool
        if any(
            "nwave_claude_code_hook_adapter_launcher.py" in hook["command"]
            for hook in group["hooks"]
        )
    )
    colocated_foreign = {
        "type": "command",
        "command": "/user/bin/audit-hook --preserve",
        "timeout": 7,
    }
    owned_group["hooks"].append(colocated_foreign)
    adapter_string_foreign = {
        "matcher": "^Read$",
        "hooks": [
            {
                "type": "command",
                "command": (
                    "/user/bin/notes "
                    "des.adapters.drivers.hooks.claude_code_hook_adapter"
                ),
                "timeout": 9,
            }
        ],
    }
    pretool.append(adapter_string_foreign)
    hooks_path.write_text(json.dumps(doc, indent=2) + "\n")

    second = _install(home)

    assert second.returncode == 0, second.stdout + second.stderr
    after = json.loads(hooks_path.read_text())["hooks"]["PreToolUse"]
    handlers = [hook for group in after for hook in group.get("hooks", [])]
    assert colocated_foreign in handlers
    assert adapter_string_foreign in after
    owned = [
        hook
        for hook in handlers
        if "nwave_claude_code_hook_adapter_launcher.py" in hook.get("command", "")
    ]
    assert len(owned) == 1


def test_public_codex_install_upgrades_legacy_owned_surfaces_without_adopting_user_state(
    tmp_path: Path,
) -> None:
    """A legacy Codex bootstrap is upgraded through ``nwave-ai install`` alone.

    The old three-field DES manifest identifies the direct DES handler and the
    standard, pre-manifest nWave agents as installer-owned.  A user's adjacent
    hook, agent, skill, and global-config extension are a separate population
    and must survive the upgrade.  Claude's state is deliberately unrelated:
    this journey is a Codex-bootstrap upgrade, not legacy-runtime migration or
    restore.
    """
    home = tmp_path / "home"
    codex = home / ".codex"
    agents = codex / "agents"
    agents.mkdir(parents=True)
    hooks_path = codex / "hooks.json"
    old_pythonpath = "/legacy/nwave/lib/python"
    old_des_command = (
        f"PYTHONPATH={old_pythonpath} /legacy/bin/python -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
    )

    user_hook = {
        "type": "command",
        "command": "/user/bin/audit-before-write --keep",
        "timeout": 7,
    }
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": old_des_command,
                                    "timeout": 30,
                                }
                            ],
                        },
                        {"matcher": "^Write$", "hooks": [user_hook]},
                    ]
                }
            },
            indent=2,
        )
        + "\n"
    )
    (codex / ".nwave-des-manifest.json").write_text(
        json.dumps(
            {
                "hooks_file": str(hooks_path),
                "python_path": "/legacy/bin/python",
                "pythonpath": old_pythonpath,
            },
            indent=2,
        )
        + "\n"
    )
    legacy_agents = {
        "nw-architect": "name = 'legacy architect'\n",
        "nw-crafter": "name = 'legacy crafter'\n",
    }
    for name, contents in legacy_agents.items():
        (agents / f"{name}.toml").write_text(contents)
    user_agent = agents / "my-local-specialist.toml"
    user_agent.write_text("name = 'personal agent'\n")
    user_skill = home / ".agents" / "skills" / "my-local-skill" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("# Personal skill\nKeep this byte-for-byte.\n")
    global_config = home / ".nwave" / "global-config.json"
    global_config.parent.mkdir()
    global_config.write_text(
        json.dumps(
            {"custom": {"keep": "this setting"}, "rigor": {"profile": "standard"}}
        )
        + "\n"
    )
    claude_foreign = home / ".claude" / "keep-me.txt"
    claude_foreign.parent.mkdir()
    claude_foreign.write_text("not a legacy runtime\n")

    result = _install(home)

    assert result.returncode == 0, (
        "WHAT: a public Codex install did not upgrade a concrete legacy Codex "
        f"bootstrap. Observed stdout/stderr:\n{result.stdout}{result.stderr}\n"
        "WHY: existing users must be able to receive the native Codex bootstrap "
        "without manually deleting nWave's prior direct hook and agents. "
        "HOW: recognise the three-field DES manifest plus standard unmanifested "
        "nw-*.toml population as the legacy nWave ownership witness."
    )
    assert "nameerror" not in (result.stdout + result.stderr).lower(), (
        "WHAT: the valid three-field direct DES witness reached a NameError. WHY: "
        "the public upgrade path must recognise and migrate the legacy direct hook. "
        "HOW: execute its ownership proof before referring to launcher-only state."
    )
    upgraded_hooks = json.loads(hooks_path.read_text())
    handlers = [
        handler
        for group in upgraded_hooks["hooks"]["PreToolUse"]
        for handler in group.get("hooks", [])
    ]
    assert user_hook in handlers, (
        "WHAT: the user's unrelated Codex hook disappeared during the legacy "
        "bootstrap upgrade. WHY: nWave owns only its recorded direct DES handler. "
        "HOW: remove or replace only that legacy handler while retaining adjacent "
        "user handlers."
    )
    assert all(old_des_command != handler.get("command") for handler in handlers), (
        "WHAT: the legacy direct DES hook remained after installation. WHY: the "
        "upgrade must replace the obsolete bootstrap rather than duplicate it. "
        "HOW: identify the hook recorded by the legacy manifest and replace it "
        "with the native launcher entry."
    )
    assert any(
        "nwave_claude_code_hook_adapter_launcher.py" in handler.get("command", "")
        for handler in handlers
    ), (
        "WHAT: no native nWave Codex launcher hook was installed. WHY: a success "
        "result must leave Codex able to invoke the upgraded DES bootstrap. "
        "HOW: write the canonical launcher hook after removing the legacy direct "
        "handler."
    )
    manifest_agents = set(
        json.loads((agents / ".nwave-agents-manifest.json").read_text())[
            "installed_agents"
        ]
    )
    assert set(legacy_agents) <= manifest_agents, (
        "WHAT: the standard legacy nWave agent population was not adopted into "
        f"the new manifest: {sorted(manifest_agents)!r}. WHY: those old files are "
        "the installer-owned agents that must be refreshed safely. HOW: seed the "
        "agent manifest from the recognised legacy population before replacement."
    )
    for name, old_contents in legacy_agents.items():
        assert (agents / f"{name}.toml").read_text() != old_contents, (
            "WHAT: a recognised legacy nWave agent was not replaced by its native "
            f"Codex representation: {name}. WHY: the old bootstrap remains stale. "
            "HOW: overwrite only the recognised standard legacy agent files."
        )
    preserved_config = json.loads(global_config.read_text())
    assert (
        user_agent.read_text(),
        user_skill.read_text(),
        preserved_config["custom"],
        preserved_config["rigor"],
        claude_foreign.read_text(),
        (home / ".nwave" / "runtime" / ".nwave-migration-receipt.json").exists(),
    ) == (
        "name = 'personal agent'\n",
        "# Personal skill\nKeep this byte-for-byte.\n",
        {"keep": "this setting"},
        {"profile": "standard"},
        "not a legacy runtime\n",
        False,
    ), (
        "WHAT: the legacy Codex bootstrap upgrade changed user-owned state or "
        "started a legacy-runtime migration. WHY: legacy ownership evidence gives "
        "nWave authority only over its direct hook and standard agents. HOW: retain "
        "unrelated agent, skill, and global-config fields, leave Claude untouched, "
        "and do not create a legacy-runtime migration receipt."
    )


def test_public_codex_dry_run_previews_native_surfaces_without_claude_claims(
    tmp_path: Path,
) -> None:
    """An explicit Codex dry-run previews only the native Codex install plan."""
    home = tmp_path / "home"
    claude_sentinel = home / ".claude" / "keep-me.txt"
    claude_sentinel.parent.mkdir(parents=True)
    claude_sentinel.write_bytes(b"Claude-owned bytes must not change\n")
    claude_before = _tree_state(claude_sentinel.parent)

    result = _run(home, "install", "--yes", "--platform", "codex", "--dry-run")

    rendered = result.stdout + result.stderr
    assert result.returncode == 0, (
        "WHAT: explicit Codex dry-run did not render a successful preview. "
        f"Observed output:\n{rendered}\n"
        "WHY: operators need to inspect the native Codex plan without writes. "
        "HOW: return success after rendering the explicit Codex target plan."
    )
    assert all(
        marker in rendered.lower() for marker in ("codex", "skill", "agent", "hook")
    ), (
        "WHAT: the dry-run did not describe the complete Codex-native surface "
        f"(skills, agents, and DES hook). Observed output:\n{rendered}\n"
        "WHY: an operator cannot validate the requested host plan from a generic "
        "preview. HOW: render Codex skills, agents, and hook work explicitly."
    )
    assert str(home / ".claude") not in rendered, (
        "WHAT: explicit Codex dry-run claimed a Claude target or surface. "
        f"Observed output:\n{rendered}\n"
        "WHY: this command must not imply that Claude will be changed. HOW: derive "
        "the preview from the explicit Codex target rather than Claude defaults."
    )
    assert _tree_state(claude_sentinel.parent) == claude_before, (
        "WHAT: explicit Codex dry-run changed or created a Claude surface. WHY: dry-run "
        "must be observational and Codex-only. HOW: do not write Claude surfaces "
        "while rendering the Codex plan."
    )


@pytest.mark.parametrize("dev", [False, True], ids=["public", "dev"])
def test_explicit_codex_upgrade_adopts_only_byte_proven_v1_public_command_omissions(
    tmp_path: Path, dev: bool
) -> None:
    """A v1 manifest may omit only exact installer-rendered public commands."""
    home = tmp_path / "home"
    omitted = ("nw-design", "nw-deliver")
    skills, hooks_path, des_manifest = _seed_v1_codex_bootstrap(
        home, omitted_public_skills=omitted
    )
    user_skill = skills / "my-local-skill" / "SKILL.md"
    user_skill.parent.mkdir()
    user_skill.write_bytes(b"user-owned skill bytes\n")
    before_omitted = {
        name: (skills / name / "SKILL.md").read_bytes() for name in omitted
    }

    args = ["install", "--yes", "--platform", "codex"]
    if dev:
        args.insert(2, "--dev")
    result = _run(home, *args)

    assert result.returncode == 0, (
        "WHAT: an explicit Codex refresh rejected a corroborated v1 bootstrap with "
        "two byte-proven public-command omissions. "
        f"Observed stdout/stderr:\n{result.stdout}{result.stderr}\n"
        "WHY: historical public manifests could omit command skills, but only their "
        "exact pinned installer renderings are safe to adopt. HOW: admit those exact "
        "hash/name witnesses before refreshing the native Codex artifacts."
    )
    adopted = json.loads((skills / ".nwave-manifest.json").read_text())[
        "installed_skills"
    ]
    desired_names = _current_codex_desired_skill_names(dev=dev)
    assert set(adopted) == desired_names
    for name in omitted:
        assert before_omitted[name] == _pinned_v1_codex_public_skill(name)
        if name in desired_names:
            installed = (skills / name / "SKILL.md").read_bytes()
            assert before_omitted[name] != _current_codex_public_skill(name), (
                "WHAT: a current source rendering was accepted as historic v1 proof. "
                "WHY: ownership must be pinned to the historical installer asset. HOW: "
                "compare omitted bytes against the fixed v1 source revision."
            )
            assert installed == _current_codex_public_skill(name), (
                "WHAT: the refresh did not retain the exact installer-owned public "
                f"skill bytes for {name}. WHY: adoption is a hash witness, not a name "
                "claim. HOW: overwrite only the byte-proven v1 command candidate with "
                "the installer rendering."
            )
            assert (
                hashlib.sha256(installed).digest()
                != hashlib.sha256(before_omitted[name]).digest()
            )
        else:
            assert not (skills / name).exists(), (
                "WHAT: an attested historical skill outside the current desired "
                "catalogue survived upgrade. WHY: attestation grants safe removal, "
                "not permanent installation. HOW: reconcile it against the desired set."
            )
    assert user_skill.read_bytes() == b"user-owned skill bytes\n"
    assert hooks_path.is_file() and des_manifest.is_file(), (
        "WHAT: the corroborating v1 DES state was not upgraded to native Codex "
        "artifacts. WHY: successful ownership adoption must still leave a working "
        "hook installation. HOW: refresh the proven hook surfaces after preflight."
    )


def test_altered_known_v1_command_is_not_adopted_despite_manifest_and_launcher(
    tmp_path: Path,
) -> None:
    """A recognised name with foreign bytes is never an adoption witness."""
    home = tmp_path / "home"
    skills, _, _ = _seed_v1_codex_bootstrap(
        home, omitted_public_skills=("nw-design", "nw-deliver")
    )
    altered = skills / "nw-deliver" / "SKILL.md"
    altered.write_bytes(_pinned_v1_codex_public_skill("nw-deliver") + b"foreign edit\n")
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--dev", "--platform", "codex")

    assert result.returncode != 0, (
        "WHAT: an altered known v1 public command was adopted by name. WHY: a "
        "manifest and launcher cannot prove bytes owned by the installer. HOW: "
        "require the pinned historical asset hash for every omitted candidate."
    )
    assert _tree_state(home) == before, (
        "WHAT: refusal over an altered command mutated config, hook, or manifest. "
        "WHY: an ownership refusal must be transactional. HOW: decide byte trust "
        "before any Codex install side effect."
    )


@pytest.mark.parametrize("dev", [False, True], ids=["public", "dev"])
def test_actual_v1_omission_profile_is_adopted_only_as_the_complete_reviewed_set(
    tmp_path: Path, dev: bool
) -> None:
    """The actual candidate's closed 27-skill omission profile upgrades publicly."""
    historical_profile = _assert_actual_v1_candidate_profile_matches_pinned_source()
    home = tmp_path / "home"
    skills, _, _ = _seed_v1_codex_bootstrap(home, omitted_public_skills=())
    for name in historical_profile:
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(exist_ok=True)
        skill.write_bytes(_pinned_v1_candidate_codex_skill(name))

    args = ["install", "--yes", "--platform", "codex"]
    if dev:
        args.insert(2, "--dev")
    result = _run(home, *args)

    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((skills / ".nwave-manifest.json").read_text())
    installed = set(manifest["installed_skills"])
    desired_names = _current_codex_desired_skill_names(dev=dev)
    historical_names = set(historical_profile)
    removed_historical_names = historical_names - desired_names

    assert installed == desired_names, (
        "WHAT: the final manifest differs from the current desired Codex catalogue. "
        "WHY: historical attestation grants refresh authority but does not extend the "
        "new installation set. HOW: publish exactly the current source/catalogue set."
    )
    assert {
        path.name
        for path in skills.iterdir()
        if path.is_dir()
        and path.name.startswith("nw-")
        and (path / "SKILL.md").is_file()
    } == desired_names
    assert all(not (skills / name).exists() for name in removed_historical_names), (
        "WHAT: an attested historical skill absent from the current desired catalogue "
        "survived upgrade. WHY: stale ownership must be reconciled after refresh. "
        "HOW: delete the attested stale member before publishing the manifest."
    )


def test_one_byte_drift_in_actual_v1_profile_refuses_before_any_write(
    tmp_path: Path,
) -> None:
    """One changed byte among the closed candidate names is not ownership proof."""
    historical_profile = _assert_actual_v1_candidate_profile_matches_pinned_source()
    home = tmp_path / "home"
    skills, _, _ = _seed_v1_codex_bootstrap(home, omitted_public_skills=())
    for name in historical_profile:
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(exist_ok=True)
        skill.write_bytes(_pinned_v1_candidate_codex_skill(name))
    drifted_name = sorted(historical_profile)[0]
    drifted = skills / drifted_name / "SKILL.md"
    drifted.write_bytes(drifted.read_bytes() + b"x")
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode != 0
    assert _tree_state(home) == before


def test_exact_historical_skill_payload_cannot_be_relocated_under_another_safe_name(
    tmp_path: Path,
) -> None:
    """Historical bytes are evidence only at their original frontmatter name."""
    historical_profile = _assert_actual_v1_candidate_profile_matches_pinned_source()
    home = tmp_path / "home"
    skills, _, _ = _seed_v1_codex_bootstrap(home, omitted_public_skills=())
    for name in historical_profile:
        skill = skills / name / "SKILL.md"
        skill.parent.mkdir(exist_ok=True)
        skill.write_bytes(_pinned_v1_candidate_codex_skill(name))

    original_name = sorted(historical_profile)[0]
    original = skills / original_name
    relocated = skills / f"{original_name}-relocated"
    original.rename(relocated)
    metadata, _ = parse_frontmatter(
        (relocated / "SKILL.md").read_text(encoding="utf-8")
    )
    assert metadata is not None and metadata.get("name") == original_name
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode != 0, (
        "WHAT: exact historical bytes were adopted from a different safe directory. "
        "WHY: a digest alone does not authorize relocation; the embedded skill name "
        "must bind the payload to its directory. HOW: reject before installation "
        "whenever a historical witness is not at its frontmatter name."
    )
    assert _tree_state(home) == before, (
        "WHAT: a rejected relocated witness changed user state. WHY: historical "
        "ownership must be decided before any installer mutation. HOW: keep the "
        "complete home tree byte-identical on refusal."
    )


@pytest.mark.parametrize("dev", [False, True], ids=["public", "dev"])
@pytest.mark.parametrize(
    "terminal_interpreter_symlink", [False, True], ids=["plain", "terminal-symlink"]
)
def test_self_contained_current_orphan_launcher_upgrades_legacy_direct_codex_state(
    tmp_path: Path, dev: bool, terminal_interpreter_symlink: bool
) -> None:
    """The reviewed in-home current launcher is a safe legacy collision witness."""
    home = tmp_path / "home"
    candidate_python = str(home / ".nwave" / "codex-candidate-venv" / "bin" / "python3")
    candidate_runtime = str(home / ".nwave" / "runtime")
    (home / ".nwave").mkdir(parents=True)
    if terminal_interpreter_symlink:
        interpreter = Path(candidate_python)
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to("/usr/bin/python3")
    orphan = _seed_legacy_direct_hook_with_orphan_launcher(
        home, _current_codex_launcher_source(candidate_python, candidate_runtime)
    )

    args = ["install", "--yes", "--platform", "codex"]
    if dev:
        args.insert(2, "--dev")
    result = _run(home, *args)

    assert result.returncode == 0, result.stdout + result.stderr
    hooks = json.loads((home / ".codex" / "hooks.json").read_text())
    commands = [
        hook["command"]
        for group in hooks["hooks"]["PreToolUse"]
        for hook in group["hooks"]
    ]
    assert any(
        "nwave_claude_code_hook_adapter_launcher.py" in command for command in commands
    )
    manifest = json.loads((home / ".codex" / ".nwave-des-manifest.json").read_text())
    assert orphan.is_file() and manifest["launcher_file"] == str(orphan), (
        "WHAT: a self-contained, byte-proven launcher was not adopted at the canonical "
        "Codex path. WHY: this exact retired candidate artifact is nWave-owned. HOW: "
        "replace it in place and record the resulting canonical launcher ownership."
    )


def test_parent_symlink_escape_in_orphan_launcher_interpreter_refuses_atomically(
    tmp_path: Path,
) -> None:
    """A lexical ~/.nwave path is insufficient when its parent escapes by symlink."""
    home = tmp_path / "home"
    external_venv = tmp_path / "external-user-venv"
    (external_venv / "bin").mkdir(parents=True)
    (external_venv / "bin" / "python3").symlink_to("/usr/bin/python3")
    nwave = home / ".nwave"
    nwave.mkdir(parents=True)
    (nwave / "codex-candidate-venv").symlink_to(external_venv, target_is_directory=True)
    candidate_python = str(nwave / "codex-candidate-venv" / "bin" / "python3")
    _seed_legacy_direct_hook_with_orphan_launcher(
        home,
        _current_codex_launcher_source(candidate_python, str(nwave / "runtime")),
    )
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode != 0
    assert _tree_state(home) == before


def test_symlinked_nwave_root_in_orphan_launcher_refuses_atomically(
    tmp_path: Path,
) -> None:
    """The ownership root itself cannot be a symlink to an external directory."""
    home = tmp_path / "home"
    external_root = tmp_path / "external-nwave-root"
    external_root.mkdir()
    home.mkdir()
    (home / ".nwave").symlink_to(external_root, target_is_directory=True)
    candidate_python = str(home / ".nwave" / "codex-candidate-venv" / "bin" / "python3")
    _seed_legacy_direct_hook_with_orphan_launcher(
        home,
        _current_codex_launcher_source(
            candidate_python, str(home / ".nwave" / "runtime")
        ),
    )
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode != 0
    assert _tree_state(home) == before


@pytest.mark.parametrize("variant", ["one-byte-drift", "external-template"])
def test_untrusted_orphan_launcher_refuses_legacy_direct_upgrade_atomically(
    tmp_path: Path, variant: str
) -> None:
    """Neither near-match bytes nor a template using an external path are trusted."""
    home = tmp_path / "home"
    candidate_runtime = str(home / ".nwave" / "runtime")
    contents = _current_codex_launcher_source(
        str(home / ".nwave" / "codex-candidate-venv" / "bin" / "python3"),
        candidate_runtime,
    )
    if variant == "one-byte-drift":
        contents += "# one foreign byte\n"
    else:
        contents = _current_codex_launcher_source(
            "/external/user/python", candidate_runtime
        )
    _seed_legacy_direct_hook_with_orphan_launcher(home, contents)
    before = _tree_state(home)

    result = _run(home, "install", "--yes", "--platform", "codex")

    assert result.returncode != 0
    assert _tree_state(home) == before


def test_arbitrary_v1_skill_name_is_not_adopted_despite_manifest_and_launcher(
    tmp_path: Path,
) -> None:
    """A v1 manifest is not a namespace-wide ownership grant."""
    home = tmp_path / "home"
    skills, _, _ = _seed_v1_codex_bootstrap(
        home, omitted_public_skills=("nw-design", "nw-deliver")
    )
    arbitrary = skills / "nw-foreign-user-skill" / "SKILL.md"
    arbitrary.parent.mkdir()
    arbitrary.write_bytes(b"foreign user skill bytes\n")
    before = _tree_state(home)

    result = _install(home)

    assert result.returncode != 0, (
        "WHAT: an arbitrary unlisted nw-* skill was adopted. WHY: neither the "
        "v1 manifest nor valid DES launcher evidence authorizes user-created "
        "names. HOW: admit only the exact known byte witnesses."
    )
    assert _tree_state(home) == before, (
        "WHAT: refusing an arbitrary skill changed user state. WHY: ownership "
        "refusal must precede all installation writes. HOW: fail before config, "
        "hook, or manifest mutation."
    )


@pytest.mark.parametrize("manifest_state", ["absent", "invalid"])
def test_foreign_legacy_direct_des_hook_without_a_valid_manifest_is_not_changed(
    tmp_path: Path, manifest_state: str
) -> None:
    """A syntactically legacy direct hook is not owned without its manifest."""
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    hooks_path = codex / "hooks.json"
    foreign_pythonpath = "/foreign/des/runtime"
    direct_command = (
        f"PYTHONPATH={foreign_pythonpath} {sys.executable} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
    )
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "^Bash$",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": direct_command,
                                    "timeout": 30,
                                }
                            ],
                        }
                    ]
                }
            }
        )
        + "\n"
    )
    if manifest_state == "invalid":
        (codex / ".nwave-des-manifest.json").write_text("{not valid json}\n")
    before = _tree_state(home)

    result = _install(home)

    if manifest_state == "invalid":
        assert result.returncode != 0, (
            "WHAT: an unreadable DES manifest was accepted. WHY: syntax alone is not "
            "installer provenance. HOW: fail closed before replacing any direct hook."
        )
        assert _tree_state(home) == before, (
            "WHAT: invalid-manifest refusal changed a foreign direct DES hook. WHY: "
            "ownership refusal must be side-effect free. HOW: stop before mutation."
        )
    else:
        handlers = [
            handler
            for group in json.loads(hooks_path.read_text())["hooks"]["PreToolUse"]
            for handler in group.get("hooks", [])
        ]
        assert any(handler.get("command") == direct_command for handler in handlers), (
            "WHAT: an absent manifest caused deletion of a foreign direct DES-shaped "
            "hook. WHY: command syntax is not ownership proof. HOW: preserve it while "
            "a successful install adds a separate canonical nWave hook, or refuse."
        )


def test_manifest_owned_codex_agent_symlink_refuses_before_mutating_its_target(
    tmp_path: Path,
) -> None:
    """A manifest entry cannot authorize a file reached through a symlink."""
    home = tmp_path / "home"
    agents = home / ".codex" / "agents"
    agents.mkdir(parents=True)
    external = tmp_path / "outside-agent.toml"
    external.write_bytes(b"foreign agent target bytes\n")
    (agents / "nw-architect.toml").symlink_to(external)
    (agents / ".nwave-agents-manifest.json").write_text(
        json.dumps({"installed_agents": ["nw-architect"], "version": "1.0"}) + "\n"
    )
    before_home = _tree_state(home)
    before_external = external.read_bytes()

    result = _install(home)

    assert result.returncode != 0, (
        "WHAT: a manifest-owned Codex agent symlink was accepted. WHY: following "
        "it grants the installer write access outside its target tree. HOW: reject "
        "symlinked owned artifacts during preflight."
    )
    assert (
        _tree_state(home) == before_home and external.read_bytes() == before_external
    ), (
        "WHAT: symlink refusal changed the home tree or external agent target. WHY: "
        "ownership failures must have no side effects. HOW: detect links before any "
        "installer transaction begins."
    )


@pytest.mark.parametrize(
    ("artifact", "contents"),
    [
        ("hooks.json", b'{"hooks": {}}\n'),
        ("nwave_claude_code_hook_adapter_launcher.py", b"foreign launcher bytes\n"),
        (".nwave-des-manifest.json", b'{"foreign": true}\n'),
    ],
)
def test_symlinked_codex_control_plane_artifact_refuses_before_mutation(
    tmp_path: Path, artifact: str, contents: bytes
) -> None:
    """Hook, launcher, and DES manifest links are never safe installer inputs."""
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    external = tmp_path / f"outside-{artifact}"
    external.write_bytes(contents)
    (codex / artifact).symlink_to(external)
    before_home = _tree_state(home)
    before_external = external.read_bytes()

    result = _install(home)

    assert result.returncode != 0, (
        f"WHAT: symlinked Codex {artifact} was accepted. WHY: it can redirect an "
        "installer write outside HOME. HOW: reject linked ownership/control-plane "
        "artifacts before dispatching plugins."
    )
    assert _tree_state(home) == before_home and external.read_bytes() == before_external
