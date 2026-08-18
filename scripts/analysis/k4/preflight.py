#!/usr/bin/env python3
"""Build the K4 arms, then REFUSE the campaign unless nWave actually landed.

The reason this exists is a silent-skip, read in the CLI rather than guessed:

    a non-interactive context WITHOUT `--yes` skips injection and prints how to
    add it                                   -- nwave_ai/cli.py, project enable

`paired_campaign.py` spawns every step with `stdin=DEVNULL`, which is exactly
that non-interactive context. So `nwave-ai project enable` without `--yes`
returns 0, prints a friendly note nobody reads, and leaves the workspace with no
nWave guidance at all. The campaign then runs to completion, produces a clean
comparison table, and the table says vanilla versus vanilla.

An exit code cannot catch it: the step SUCCEEDED. The only thing that can is
observing the property the step was supposed to establish, which is what this
does -- GDP-8's witness corollary, verify on a second axis when the first is not
locally inspectable.

    preflight.py --root <campaign-root> [--wheel <path>]

It builds a wheel once from the current checkout (lane A: the benchmark's pinned
`nwave-ai==3.21.0` is a MAJOR version behind this tree, so a pinned package
cannot represent the trunk), installs it into one shared venv, then runs the
nWave arm's setup in a throwaway workspace and checks what arrived.

Nothing here touches the operator's `~/.claude`: every step runs with
CLAUDE_CONFIG_DIR pointed inside the probe workspace. That is not caution for
its own sake -- a campaign rewrote a live `~/.claude` down to 12 skills and 0
agents twice on 2026-08-06.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.analysis.k4 import prepare_examiner_fixture as pef


#: Injected by `nwave-ai project enable`. An HTML comment, so it is invisible in
#: rendered markdown and unambiguous to look for.
_SECTION_MARKER = "BEGIN nWave-beta-section"

#: Executables the fail-closed Claude delivery sandbox needs at RUN time: `claude`
#: is the arm itself, `socat` backs the sandbox's localhost network bridge (see
#: `_render_sandbox_settings(...).sandbox.network`). A host missing either
#: still lets a campaign build its wheel, write `arms.json`, and spend a pair
#: before the gap surfaces as an opaque sandbox failure mid-delivery -- a K4
#: delivery, and a dead campaign it broke, both burned that way.
#: `failIfUnavailable=true` in the rendered settings catches it too, but only
#: inside the timed run; this catches it before the campaign is even built.
#: Never install anything to satisfy this -- a bounded, non-global executable
#: on PATH is sufficient and is exactly what an operator stages for a host
#: with no global socat. That bounded directory must also reach Claude's LATER
#: `socat` bridge spawn, which reads PATH from `--settings env.PATH`, not from
#: this preflight's process PATH -- see `delivery_argv`.
_REQUIRED_SANDBOX_EXECUTABLES = ("claude", "socat")


def missing_sandbox_prerequisites(path: str | None = None) -> list[str]:
    """Names from `_REQUIRED_SANDBOX_EXECUTABLES` not resolvable on PATH.

    `path=None` resolves against the process's own inherited PATH -- the same
    PATH a spawned setup/delivery step would see, since neither arm's `env`
    override touches PATH resolution for this check. This is Claude's
    STARTUP preflight; its LATER `socat` bridge spawn resolves PATH
    differently -- see `delivery_argv`.
    """
    return [
        exe
        for exe in _REQUIRED_SANDBOX_EXECUTABLES
        if shutil.which(exe, path=path) is None
    ]


_SUT = "https://github.com/healthchecks/healthchecks.git"


def _run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 1800,
) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return done.returncode, (done.stderr or done.stdout)[-600:]


#: The release packaging sequence, verbatim from `publish-experimental.yml`.
#: A plain `uv build --wheel` from the dev tree produces a wheel WITHOUT
#: `nWave/framework-catalog.yaml`, because the dev `pyproject.toml` force-includes
#: only `scripts/install` and `scripts/shared` -- the asset tree is added by
#: `patch_pyproject.py` at release time. Measured 2026-08-07: installing that
#: wheel and running `nwave-ai install` dies with CatalogNotFoundError.
#:
#: So the arm must be packaged the way a user's package is packaged, and this
#: runs in a COPY of the checkout because step one rewrites `pyproject.toml` in
#: place. The live tree is never touched.
_PACKAGING = (
    [
        "python",
        "scripts/release/patch_pyproject.py",
        "--input",
        "pyproject.toml",
        "--output",
        "pyproject.toml",
        "--target-name",
        "nwave-ai",
        "--target-version",
        "0.0.0+k4",
    ],
    ["python", "scripts/build_dist.py"],
    ["python", "scripts/release/stage_public_wheel_des.py", "--cleanup-dist"],
    ["python", "-m", "build", "--wheel"],
)

_NEVER_COPY = shutil.ignore_patterns(
    ".git", ".venv", "node_modules", ".claude", ".tsunami", "dist", "graphify-out"
)


def _ensure_venv(root: Path) -> Path:
    venv = root / "nwave-venv"
    if not venv.exists():
        code, tail = _run([sys.executable, "-m", "venv", str(venv)], cwd=root)
        if code != 0:
            raise SystemExit(f"WHAT: could not create the arm venv.\n{tail}")
    return venv


def _install_exact_wheel(venv: Path, root: Path, wheel: Path) -> None:
    """The one install call both build_arm_runtime and the --wheel path share.

    Factored so the venv-creation-then-install shape has exactly one place
    that runs `pip install <wheel>`, not two paths that could drift apart.
    """
    code, tail = _run(
        [str(venv / "bin" / "pip"), "install", "-q", str(wheel)], cwd=root
    )
    if code != 0:
        raise SystemExit(f"WHAT: could not install {wheel.name}.\n{tail}")


def build_arm_runtime(root: Path, checkout: Path) -> tuple[Path, Path]:
    """Package the trunk the way release packages it, into one shared venv.

    Once, deliberately: every pair then installs identical bits, which removes a
    difference no one would have thought to record.
    """
    source = root / "arm-src"
    if not source.exists():
        shutil.copytree(checkout, source, ignore=_NEVER_COPY, symlinks=True)
    venv = _ensure_venv(root)
    python = str(venv / "bin" / "python")
    code, tail = _run(
        [
            str(venv / "bin" / "pip"),
            "install",
            "-q",
            "build",
            "packaging",
            "tomli",
            "pyyaml",
        ],
        cwd=root,
    )
    if code != 0:
        raise SystemExit(f"WHAT: could not install the packaging tools.\n{tail}")
    for step in _PACKAGING:
        code, tail = _run([python, *step[1:]], cwd=source)
        if code != 0:
            raise SystemExit(
                f"WHAT: release packaging step `{' '.join(step[1:3])}` exited {code}.\n"
                "WHY:  an arm packaged differently from a user's install measures a\n"
                "      product no user has.\n"
                f"HOW:  reproduce it in {source} and read the error below.\n{tail}"
            )
    dist = source / "dist"
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"WHAT: expected exactly one wheel in {dist}, found {len(wheels)}.\n"
            "WHY:  an ambiguous wheel means the arm's version is undetermined, and\n"
            "      the campaign would not know what it measured.\n"
            "HOW:  remove the stale wheels and re-run."
        )
    wheel = wheels[0].resolve()
    _install_exact_wheel(venv, root, wheel)
    return venv, wheel


def resolve_wheel(path: Path) -> Path:
    """Validate `--wheel` names one existing regular `.whl` file; return it resolved.

    Refuses before any probe setup on disk: an invalid path here must fail
    loud and early, not surface later as a cryptic pip error after the venv
    and workspace already exist.
    """
    if not path.exists():
        raise SystemExit(
            f"WHAT: --wheel path does not exist: {path}\n"
            "WHY:  the campaign measures exactly whatever pip installs; a path\n"
            "      that resolves to nothing cannot be the measured artifact.\n"
            "HOW:  pass an existing wheel file, e.g. from `dist/*.whl`."
        )
    if not path.is_file():
        raise SystemExit(
            f"WHAT: --wheel path is not a regular file: {path}\n"
            "WHY:  a directory or other non-file path cannot be installed by\n"
            "      pip as a single wheel.\n"
            "HOW:  point --wheel at the .whl file itself, not its directory."
        )
    if path.suffix != ".whl":
        raise SystemExit(
            f"WHAT: --wheel path is not a .whl file: {path}\n"
            "WHY:  an exact-wheel run must measure exactly the named artifact;\n"
            "      a non-wheel path would install something else or fail with\n"
            "      an unrelated pip error deep inside setup.\n"
            "HOW:  pass the .whl file produced by `python -m build --wheel`."
        )
    return path.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_arm_runtime_from_wheel(root: Path, wheel: Path) -> Path:
    """Install one exact, pre-built wheel into the shared venv.

    Never copies or builds the checkout, and never installs the packaging
    tools `build_arm_runtime` needs: the wheel already IS the measured
    artifact, so there is nothing left to package.
    """
    venv = _ensure_venv(root)
    _install_exact_wheel(venv, root, wheel)
    return venv


class GitProvenanceUnavailable(RuntimeError):
    """`git` is not resolvable on PATH.

    K4 matrix row 16: provenance must bind the packaged wheel to a clean
    EXACT commit SHA, never just the wheel's own digest. `git` is optional
    tooling, never a runtime dependency of this harness's own job -- so its
    absence degrades LOUD as this exception (INDETERMINATE provenance),
    never a silent skip that lets a campaign proceed with no binding at all.
    """


def resolve_clean_commit_sha(checkout: Path, *, git: str | None = None) -> str:
    """Return `checkout`'s exact HEAD commit SHA, refusing a dirty tree.

    A wheel built from an uncommitted change cannot be reproduced from its
    recorded commit SHA alone -- the SHA would name a source state the tree
    was not actually in when the wheel was packaged. This must run BEFORE
    packaging (`build_arm_runtime`) or wheel resolution (`--wheel`), so a
    dirty checkout is refused before either path spends any work.
    """
    git = git if git is not None else shutil.which("git")
    if git is None:
        raise GitProvenanceUnavailable(
            "WHAT: `git` is not on PATH.\n"
            "WHY:  wheel provenance must bind to the exact clean commit SHA\n"
            "      the wheel was packaged from; without git this cannot be\n"
            "      established, and proceeding would silently record no\n"
            "      provenance at all.\n"
            "HOW:  install git or run this preflight where it is on PATH.\n"
            "      This failure is INDETERMINATE, not a pass.\n"
        )
    status = subprocess.run(
        [git, "-C", str(checkout), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )
    if status.returncode != 0:
        raise SystemExit(
            f"WHAT: `git -C {checkout} status --porcelain` exited "
            f"{status.returncode}.\n"
            "WHY:  provenance cannot be bound to a commit without a working\n"
            "      git status read.\n"
            f"HOW:  reproduce the command and read the error below.\n{status.stderr}"
        )
    if status.stdout.strip():
        raise SystemExit(
            f"WHAT: {checkout} has uncommitted changes:\n{status.stdout}"
            "WHY:  a wheel built from a dirty tree cannot be reproduced from\n"
            "      its recorded commit SHA alone -- the SHA would name a\n"
            "      state the tree was not actually in.\n"
            "HOW:  commit or stash the changes, then rerun. This refusal is\n"
            "      deliberate: provenance must bind to a CLEAN exact SHA.\n"
        )
    sha = subprocess.run(
        [git, "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    if sha.returncode != 0 or not sha.stdout.strip():
        raise SystemExit(
            f"WHAT: `git -C {checkout} rev-parse HEAD` failed.\n"
            "WHY:  no resolvable HEAD means there is no commit to bind\n"
            "      provenance to.\n"
            f"HOW:  ensure {checkout} is a git checkout with at least one\n"
            f"      commit.\n{sha.stderr}"
        )
    return sha.stdout.strip()


#: Both arms seed the SAME subscription login into their own config dir, first.
#: Measured 2026-08-07, after it cost $15.04: an isolated `CLAUDE_CONFIG_DIR`
#: does NOT inherit the subscription. It authenticates -- and bills API CREDIT,
#: a different payer with a different quota. Both arms of the calibration pair
#: died within one second of each other when that credit ran out, having drawn
#: nothing from the Max plan that was supposed to pay for them.
#:
#: The login and the ACCOUNT live in two different files: the token in
#: `.credentials.json`, `oauthAccount` in `.claude.json`. Seeding the token alone
#: still bills credit -- verified, not assumed.
#: Which profile pays is an OWNER decision, not a default: it decides whose Max
#: window the campaign spends and therefore who is blocked if it runs dry. Ale
#: named claude3 (`~/.claude-alt3`) on 2026-08-07. Recorded in `arms.json` so a
#: reader can see which account the numbers were drawn against.
_DEFAULT_AUTH_PROFILE = Path.home() / ".claude-alt3"


def seed_step(auth_profile: Path) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve().parent / "seed_auth.py"),
        "--from",
        str(auth_profile),
        "--into",
        ".claude-k4",
        "--trust-project",
        ".",
    ]


#: `git clone <url> .` leaves HEAD attached to the SUT's default branch. Read
#: literally against `nWave/skills/nw-auto/SKILL.md`'s worktree-ownership rule
#: ("if the current checkout is ... otherwise shared/non-isolated, create or
#: reuse an isolated detached worktree"), an attached checkout is exactly the
#: shared/non-isolated case: Auto abandons this directory and creates ANOTHER
#: detached worktree elsewhere for the actual delivery. `paired_campaign.py`
#: then times and captures THIS directory, and the hidden acceptance suite and
#: blind review only ever inspect `pair-dir/{arm}` -- so they measure the
#: unchanged clone while the real delivery landed somewhere neither looks.
#: Detaching HEAD here, in the already-isolated per-arm clone, makes the
#: workspace match Auto's OTHER branch of that same rule ("if the current
#: checkout is already an isolated detached worktree, keep using it") by
#: construction, so Auto reuses this directory instead of relocating.
_DETACH_STEP = ["git", "checkout", "--detach", "HEAD"]


def nwave_setup_steps(venv: Path, auth_profile: Path) -> list[list[str]]:
    """The nWave arm's declared setup. `--yes` is load-bearing, see module doc."""
    cli = str(venv / "bin" / "nwave-ai")
    return [
        # Clone FIRST. `git clone <url> .` refuses a non-empty directory, and the
        # seed creates `.claude-k4/` in exactly that directory - so seeding first
        # made the clone exit 128. Caught by the preflight on its own run.
        ["git", "clone", "--depth", "1", _SUT, "."],
        _DETACH_STEP,
        pef.delivery_setup_step(),
        seed_step(auth_profile),
        # `--platform claude-code`, never the `auto` default. Measured 2026-08-07:
        # auto-detect installs into EVERY platform it finds, and CLAUDE_CONFIG_DIR
        # governs only the Claude one -- so an install the operator scoped to a
        # throwaway directory still rewrote their real Codex configuration and
        # left a backup in their real `~/.nwave/backups`. The arm runs `claude -p`,
        # so every other platform is out of scope for the measurement as well.
        [cli, "install", "--platform", "claude-code"],
        [cli, "project", "enable", "--yes"],
    ]


def control_setup_steps(auth_profile: Path) -> list[list[str]]:
    # Same seed, same source profile. Two arms on different accounts would carry
    # different rate-limit windows, and the arm that happened to start with more
    # headroom would be measured under a condition nobody declared -- exactly the
    # confound pairing exists to remove.
    #
    # Detached for the same reason as the nWave arm, even though the control
    # arm never reads nw-auto's rule itself: a treatment-only locator
    # convention would make the workspace construction asymmetric, and the
    # comparison arms must differ only in what their setup installs.
    return [
        ["git", "clone", "--depth", "1", _SUT, "."],
        _DETACH_STEP,
        pef.delivery_setup_step(),
        seed_step(auth_profile),
    ]


def _arm_env() -> dict[str, str]:
    """The one declared env, identical for both arms; only `{workspace}`
    differs once `ArmSpec.rendered_env` substitutes it per arm.

    PATH prepends, in order: the DES shims directory
    `{workspace}/.claude-k4/bin`, then the fixture-owned interpreter's bin
    dir (see `pef.VENV_PYTHON`), then the inherited PATH.

    The shims entry closes row 9/14 (K4 matrix), found in an installed run:
    `scripts/install/plugins/des_plugin.py`'s `_install_des_shims` copies
    `des` (and friends) to `context.claude_dir / "bin"` -- `{workspace}/
    .claude-k4/bin` for this arm's own `CLAUDE_CONFIG_DIR` -- and separately
    writes that SAME absolute path into `.claude-k4/settings.json`'s
    `env.PATH`, which is how Claude's HOOKS resolve `des`. This harness's
    OWN `--settings` JSON (`_render_sandbox_settings`, built from THIS
    PATH) governs the delivery agent's Bash tool instead, and previously
    never carried that directory -- so hooks could resolve `des` while the
    agent's own Bash got `des: command not found` (exit 127). Deriving the
    value from `CLAUDE_CONFIG_DIR` (declared once, two lines below) rather
    than a second hardcoded `.claude-k4/bin` string keeps the two
    mechanisms reading the SAME path by construction, not by both authors
    remembering to update two literals in sync.

    The fixture-owned interpreter's bin dir lets a bare `python` on either
    arm's PATH resolve to the SAME clone-local venv the user-facing fixture
    doc points a human at -- without a role-specific carrier for it.

    Row 22 (K4 matrix): `CLAUDE_CONFIG_DIR` scopes ONLY the Claude-platform
    install. `scripts/install/install_nwave.py`'s Codex backup/skills path
    resolves a SEPARATE `agents_home = Path(os.environ.get("NWAVE_AGENTS_HOME",
    Path.home()))` -- unset, it falls through to the operator's real
    `Path.home()` and writes `.nwave/backups` and `.agents/skills` there
    regardless of CLAUDE_CONFIG_DIR. Its Codex-agents root resolves the
    SAME way from a separate `CODEX_HOME` (four call sites in
    install_nwave.py: `create_backup`, `_legacy_codex_dev_candidates`,
    `validate_codex_ownership_preflight`, `validate_codex_installation`, all
    sharing the identical `Path(os.environ.get("CODEX_HOME", Path.home() /
    ".codex"))` expression -- pinning the ONE env var closes all four
    uniformly). `nwave_setup_steps` pins `--platform claude-code` today, so
    none of these branches is exercised by the declared campaign, but a
    defensive isolation boundary must not depend on which platform happens
    to be requested. `OPENCODE_CONFIG_DIR` (`PathUtils.get_opencode_config_dir`,
    default `~/.config/opencode`) and `COPILOT_HOME`
    (`copilot_des_plugin._copilot_config_dir`, default `~/.copilot`) are the
    same established per-platform override shape; pinned here for symmetry.
    Pinning all of these here closes the escape for every current and
    future arm, not just the one in use.
    """
    claude_config_dir = "{workspace}/.claude-k4"
    des_shims_bin = f"{claude_config_dir}/bin"
    fixture_bin = "{workspace}/" + str(Path(pef.VENV_PYTHON).parent)
    inherited = os.environ.get("PATH", "")
    path = f"{des_shims_bin}{os.pathsep}{fixture_bin}"
    if inherited:
        path = f"{path}{os.pathsep}{inherited}"
    environment = {
        "CLAUDE_CONFIG_DIR": claude_config_dir,
        "NWAVE_AGENTS_HOME": "{workspace}",
        "CODEX_HOME": "{workspace}/.codex",
        "OPENCODE_CONFIG_DIR": "{workspace}/.opencode",
        "COPILOT_HOME": "{workspace}/.copilot",
        "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "{workspace}",
        "PATH": path,
    }
    if library_path := os.environ.get("LD_LIBRARY_PATH"):
        environment["LD_LIBRARY_PATH"] = (
            "{workspace}/.k4-sandbox-lib" + os.pathsep + library_path
        )
    return environment


def _rendered_arm_env(workspace: Path) -> dict[str, str]:
    """The ONE arm env, actually rendered against a concrete `workspace` --
    no `{workspace}` template placeholders left, overlaid on the inherited
    process environment. Every step that can touch real filesystem config
    (setup steps, permission canary, verification probe, delivery argv
    construction) must build its env through this single function, never a
    hand-rolled dict.

    Row 22 (K4 matrix), found again in an installed run: `probe_engagement`
    built its OWN inline `{**os.environ, "CLAUDE_CONFIG_DIR": ...}` for the
    nWave arm's SETUP steps (`nwave-ai install`) instead of reusing
    `_arm_env()` -- a second copy that pinned only CLAUDE_CONFIG_DIR, so
    `install_nwave.py`'s `record_install_metadata` fell through to the
    operator's real `Path.home()`. The three OTHER call sites
    (`probe_delivery_permissions`, `probe_installed_dispatch_help`,
    `probe_persisted_verification_commands`) already rendered `_arm_env()`
    inline, correctly, each in their own copy of this exact expression --
    also consolidated here so there is exactly one rendering, not four.
    """
    rendered = {
        key: value.replace("{workspace}", str(workspace))
        for key, value in _arm_env().items()
    }
    return {**os.environ, **rendered}


def _render_sandbox_settings(path: str) -> str:
    """Render the fail-closed sandbox settings JSON with `env.PATH` set to `path`.

    Two different consumers read PATH from two different places for the same
    delivery run, and a K4 host measured them disagreeing. Claude's STARTUP
    preflight (what `missing_sandbox_prerequisites` mirrors) resolves `socat`
    against the spawned PROCESS's own PATH. Claude then normalizes its tool
    environment before its LATER `socat` spawn that backs the sandbox's
    localhost network bridge -- that spawn reads PATH from these settings'
    top-level `env.PATH`, not from the process environment. A bounded socat
    directory present only on the process PATH passes the startup preflight
    and then fails the bridge spawn with an opaque sandbox network error;
    `path` must be the SAME value the process environment carries.
    """
    return json.dumps(
        {
            "env": {"PATH": path},
            "permissions": {
                # Claude's permission matcher treats bare tool names as the
                # pre-approval required by dontAsk. A real three-sentinel probe
                # proved path-pattern rules denied root and subagent writes.
                "allow": ["Read", "Edit", "Write", "Bash", "Agent"],
                "deny": [
                    "Read(/.claude-k4/.credentials.json)",
                    "Read(/.claude-k4/.claude.json)",
                    "Edit(./.claude-k4/**)",
                    "Write(./.claude-k4/**)",
                    "WebFetch",
                    "WebSearch",
                ],
            },
            "sandbox": {
                "enabled": True,
                "failIfUnavailable": True,
                "allowUnsandboxedCommands": False,
                "filesystem": {
                    "denyRead": [
                        "~/",
                        "/mnt/c/Users",
                        "/root",
                        "./.claude-k4/.credentials.json",
                        "./.claude-k4/.claude.json",
                    ],
                    "allowRead": ["."],
                    "denyWrite": ["./.claude-k4"],
                },
                "network": {"allowedDomains": ["localhost", "127.0.0.1", "[::1]"]},
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def delivery_argv(model: str, path: str, *, safe_mode: bool = False) -> list[str]:
    """One identical, fail-closed Claude runner for both comparison arms.

    `path` is projected into the `--settings` JSON's `env.PATH` here, for
    Claude's LATER `socat` bridge spawn; the caller must ALSO put this same
    `path` in the spawned subprocess's own environment, for Claude's STARTUP
    preflight -- `_render_sandbox_settings` explains why both places need the
    identical value.

    `path` takes one of two forms depending on the caller. `main` passes the
    declared PATH TEMPLATE straight from `_arm_env()["PATH"]`, still carrying
    `{workspace}`; that placeholder reaches `paired_campaign.ArmSpec` inside
    the `--settings` argv token unrendered, and `ArmSpec.rendered` substitutes
    it from the SAME `workspace` `ArmSpec.rendered_env` uses for the env dict,
    so the two views of this one declared value stay joined. The direct probe
    in `probe_delivery_permissions` instead passes an ALREADY-RENDERED literal
    path -- it renders and runs the delivery itself, with no `ArmSpec` in
    between.

    `safe_mode=True` appends `--safe-mode`, which starts Claude with EVERY
    customization disabled (CLAUDE.md, skills, plugins, hooks, MCP servers,
    agents...). Row 18 (K4 matrix): a launcher friction note measured three
    external Claude writers spending ~USD 3.70 and 3.5M cached/read tokens
    over ~3 minutes with ZERO edits under a non-safe-mode cold start, while
    safe-mode reached edits quickly. That makes `safe_mode=True` correct for
    a narrow diagnostic writer that needs no customization at all -- exactly
    `probe_delivery_permissions`'s Edit/Write canary -- but WRONG as the
    default for the real nWave/control delivery arms below, whose entire
    measured behavior depends on nWave's installed customizations being
    active. Defaulting to False here, and opting in per call site, keeps
    that distinction explicit rather than silently blanket-applied.
    """
    argv = [
        "claude",
        "-p",
        "{task}",
        "--model",
        model,
        "--output-format",
        "json",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "default",
        "--settings",
        _render_sandbox_settings(path),
        "--setting-sources",
        "user",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-chrome",
    ]
    if safe_mode:
        argv.append("--safe-mode")
    return argv


def _probe_workspace(root: Path) -> Path:
    return root / "probe-nwave"


_PERMISSION_CANARY_RESULT = "EDIT=OK WRITE=OK CONFIG_WRITE=DENIED"


def probe_delivery_permissions(workspace: Path, model: str) -> list[str]:
    """Exercise the exact delivery runner's effective Edit/Write boundary.

    Inspecting ``_render_sandbox_settings``'s output is insufficient: a K4 campaign declared
    Edit/Write allowed while Claude's effective ``dontAsk`` policy denied both
    arms.  Positive files prove the useful permissions; the absent config file
    plus the terminal result prove the deny boundary.  Any mismatch aborts
    before ``arms.json`` is written.

    Runs with ``safe_mode=True`` (row 18, K4 matrix): this canary is a
    three-tool-call diagnostic writer that needs none of nWave's installed
    customizations, so `--safe-mode` is correct for it and cuts the
    measured cold-start cost -- unlike the real delivery arms in `main`,
    whose whole point is exercising those customizations.
    """
    edit_path = workspace / "k4-permission-edit.txt"
    write_path = workspace / "k4-permission-write.txt"
    denied_path = workspace / ".claude-k4" / "k4-permission-denied.txt"
    edit_path.write_text("CANARY_BEFORE\n", encoding="utf-8")
    write_path.unlink(missing_ok=True)
    denied_path.unlink(missing_ok=True)

    task = (
        "Permission canary only. Use Edit to replace CANARY_BEFORE with "
        "CANARY_AFTER in k4-permission-edit.txt. Use Write to create "
        "k4-permission-write.txt containing exactly CANARY_WRITE_OK followed by "
        "a newline. Then attempt Write of SHOULD_NOT_EXIST to "
        ".claude-k4/k4-permission-denied.txt; that attempt must be denied. Do not "
        "use Bash, Agent, or read any other file. Finish with exactly: "
        f"{_PERMISSION_CANARY_RESULT}"
    )
    environment = _rendered_arm_env(workspace)
    argv = [
        token.replace("{task}", task)
        for token in delivery_argv(model, environment["PATH"], safe_mode=True)
    ]
    try:
        done = subprocess.run(
            argv,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=180,
        )
        code, output, diagnostic = done.returncode, done.stdout, done.stderr[-600:]
    except subprocess.TimeoutExpired:
        code, output, diagnostic = 124, "", "TIMEOUT after 180s"
    except OSError as exc:
        code, output, diagnostic = 127, "", f"{type(exc).__name__}: {exc}"

    problems: list[str] = []
    if code != 0:
        problems.append(f"delivery runner exited {code}: {diagnostic or output[-600:]}")
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = {}
        problems.append(f"delivery runner returned non-JSON: {output!r}")
    if payload.get("is_error"):
        problems.append(f"delivery runner reported is_error: {payload.get('result')}")
    if payload.get("result") != _PERMISSION_CANARY_RESULT:
        problems.append("delivery runner did not attest the three canary operations")
    if not edit_path.is_file() or edit_path.read_text(encoding="utf-8") != (
        "CANARY_AFTER\n"
    ):
        problems.append("Edit did not mutate the in-workspace sentinel")
    if not write_path.is_file() or write_path.read_text(encoding="utf-8") != (
        "CANARY_WRITE_OK\n"
    ):
        problems.append("Write did not create the in-workspace sentinel")
    if denied_path.exists():
        problems.append("Write escaped into the denied provider-config directory")

    if not problems:
        edit_path.unlink()
        write_path.unlink()
    return problems


_DISPATCH_HELP_FAILURE_MARKERS = (
    "ModuleNotFoundError",
    "Traceback (most recent call last)",
)


def probe_installed_dispatch_help(workspace: Path, venv: Path) -> list[str]:
    """Run the real installed `des dispatch --help` under the effective arm PATH.

    This is the causal reproduction of the class this preflight exists to catch,
    run BEFORE any delivery model call: the installed console script's
    `#!/usr/bin/env python3` shebang resolves against whatever `python3` sits
    first on PATH at execution time, and `_arm_env` deliberately puts the caller
    project's fixture venv there -- so a caller venv that lacks a package the
    installed `dispatch` subcommand imports crashes before argument parsing,
    silently, on a `--help` call that costs nothing. Catching that here means a
    campaign never spends a model call (`probe_delivery_permissions`) on a
    delivery runner whose own dispatch entry point cannot run.
    """
    argv = [str(venv / "bin" / "des"), "dispatch", "--help"]
    environment = _rendered_arm_env(workspace)
    try:
        done = subprocess.run(
            argv,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        code, output = 124, "TIMEOUT after 30s"
    except OSError as exc:
        code, output = 127, f"{type(exc).__name__}: {exc}"

    problems: list[str] = []
    if code != 0:
        problems.append(
            f"`des dispatch --help` exited {code} under the arm PATH: {output[-600:]}"
        )
    if any(marker in output for marker in _DISPATCH_HELP_FAILURE_MARKERS):
        problems.append(
            f"`des dispatch --help` output carries a Python failure marker: "
            f"{output[-600:]}"
        )
    return problems


#: Marker recorded verbatim, never paraphrased -- row 4's first divergence
#: was a persisted `python3 manage.py` command dying against the WRONG
#: interpreter. This is what that death looks like on stdout/stderr.
_MODULE_NOT_FOUND_MARKER = "ModuleNotFoundError"


def verification_command_argv(command: dict) -> list[str]:
    """Flatten one schema v1.1 verification-scope command into a runnable
    argv: the named executable followed by its arguments, VERBATIM -- no
    rewriting, no reinterpretation of `executable.kind`. A real verification
    executor invokes exactly this shape."""
    executable = command.get("executable", {})
    name = executable.get("name") or executable.get("path")
    if not name:
        raise ValueError(f"verification command names no executable: {command!r}")
    return [name, *command.get("arguments", [])]


#: ADR-SSOT-002 Section 4c: "`docs/delivery-contracts/{DeliveryId}.json` is
#: the one admitted deterministic authoring-time projection" -- the SAME
#: section also states plainly that this is "not a second path convention
#: or a CLI-side discovery/fallback mechanism": `des dispatch` itself NEVER
#: infers a contract path (no marker-walk, no cwd/env inference, no
#: registry/receipt/self-digest -- Section 4a item 3/5, deliberately). This
#: constant names the one canonical DIRECTORY that projection always
#: resolves under; it is not a search path, and `discover_delivery_contract`
#: below performs no walk beyond it.
_CANONICAL_DELIVERY_CONTRACTS_DIR = Path("docs") / "delivery-contracts"


def discover_delivery_contract(workspace: Path) -> Path | None:
    """Return the ONE DeliveryContract at the canonical authoring-time
    location inside `workspace`, or None when zero or more than one
    candidate exists there.

    This is a convenience lookup owned entirely by THIS harness for what
    value to pass its own `probe_persisted_verification_commands`; it does
    not change, extend, or shortcut `des dispatch`'s own resolution rule,
    which still requires an explicit `--delivery-contract` and still
    refuses any implicit discovery on its own boundary (ADR-SSOT-002
    Section 4a items 3 and 5). Ambiguity (more than one candidate) refuses
    exactly like absence: guessing which contract to verify would be worse
    than not verifying one.
    """
    contracts_dir = workspace / _CANONICAL_DELIVERY_CONTRACTS_DIR
    if not contracts_dir.is_dir():
        return None
    candidates = sorted(contracts_dir.glob("*.json"))
    if len(candidates) != 1:
        return None
    return candidates[0]


def probe_persisted_verification_commands(
    contract_path: Path, workspace: Path
) -> list[str]:
    """Execute every schema v1.1 `verification-scope.commands` entry VERBATIM
    against the SAME effective PATH/env a real K4 delivery arm runs under
    (`_arm_env`) -- the causal reproduction of row 4's first divergence: a
    persisted `python3 manage.py` command that resolved the wrong
    interpreter and died with `ModuleNotFoundError` in a clean fixture.

    This is a reusable capability, not wired into the default campaign
    pipeline: the exact contract a K4 delivery produces is discovered only
    after DISTILL, ahead of any given campaign run. A caller with a
    concrete DeliveryContract path calls this directly before trusting it.
    """
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    commands = contract.get("verification-scope", {}).get("commands", [])
    if not commands:
        raise SystemExit(
            f"WHAT: {contract_path} carries no verification-scope commands.\n"
            "WHY:  a preflight that finds nothing to execute proves nothing about\n"
            "      whether the persisted argv actually runs.\n"
            "HOW:  point --contract at a schema v1.1 DeliveryContract with a\n"
            "      non-empty verification-scope.commands list.\n"
        )
    environment = _rendered_arm_env(workspace)
    problems: list[str] = []
    for command in commands:
        argv = verification_command_argv(command)
        try:
            done = subprocess.run(
                argv,
                cwd=workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
            )
            code, output = done.returncode, done.stdout + done.stderr
        except subprocess.TimeoutExpired:
            problems.append(f"`{' '.join(argv)}` timed out after 300s")
            continue
        except OSError as exc:
            problems.append(
                f"`{' '.join(argv)}` did not run: {type(exc).__name__}: {exc}"
            )
            continue
        if _MODULE_NOT_FOUND_MARKER in output:
            problems.append(
                f"`{' '.join(argv)}` hit {_MODULE_NOT_FOUND_MARKER} under the "
                f"fixture env: {output[-400:]}"
            )
        elif code != 0:
            problems.append(f"`{' '.join(argv)}` exited {code}: {output[-400:]}")
    return problems


def probe_engagement(
    root: Path, venv: Path, auth_profile: Path, model: str
) -> tuple[str, list[str]]:
    """Run the nWave arm's setup for real; return (verdict, detail).

    Five verdicts, never merged, because they need different HOWs and a rejection
    that names the wrong cause is worse than a bare traceback:

    * `broke`            -- a setup step exited non-zero. Loud already; read
      the error.
    * `absent`           -- every step succeeded and nWave still is not there;
    * `broken-dispatch`  -- nWave arrived, but the real installed
      `des dispatch --help` failed under the arm's effective PATH -- checked
      BEFORE any delivery model call, so a broken dispatch entry point never
      burns a `probe_delivery_permissions` call first.
    * `unsafe`           -- nWave arrived and dispatch runs, but the exact
      delivery runner did not prove its effective Edit/Write confinement.
    * `present`          -- setup, installed dispatch and permission boundary all
      passed; the arm is ready to be measured.

    The first version returned one list and printed the `absent` explanation for
    both, so a step that exited 1 was reported as "every step exited 0" and the
    remedy offered was `--yes` for a missing-catalog failure. Caught on its own
    first real run, 2026-08-07.
    """
    workspace = _probe_workspace(root)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    config_dir = workspace / ".claude-k4"
    env = _rendered_arm_env(workspace)

    for step in nwave_setup_steps(venv, auth_profile):
        code, tail = _run(step, cwd=workspace, env=env)
        if code != 0:
            return "broke", [
                f"`{' '.join(step[:3])}` exited {code}",
                tail.strip(),
            ]

    missing: list[str] = []
    claude_md = workspace / "CLAUDE.md"
    if not claude_md.exists():
        missing.append(
            "no CLAUDE.md in the workspace: the guidance section never landed"
        )
    elif _SECTION_MARKER not in claude_md.read_text(encoding="utf-8", errors="replace"):
        missing.append(
            "CLAUDE.md carries no nWave section marker: `project enable` skipped "
            "injection, which is what it does in a non-interactive context without --yes"
        )
    for name in ("agents", "skills"):
        directory = config_dir / name
        if not directory.is_dir() or not any(directory.iterdir()):
            missing.append(f"{config_dir.name}/{name} is missing or empty")
    if missing:
        return "absent", missing
    dispatch_help_problems = probe_installed_dispatch_help(workspace, venv)
    if dispatch_help_problems:
        return "broken-dispatch", dispatch_help_problems
    permission_problems = probe_delivery_permissions(workspace, model)
    if permission_problems:
        return "unsafe", permission_problems
    return "present", []


def cleanup_probe_workspace(root: Path, verdict: str, detail: list[str]) -> bool:
    """Remove the probe workspace after a PASS engagement only; return whether removed.

    PASS is decided on the PROPERTY `main` itself acts on -- `detail` empty --
    never on the `verdict` DESIGNATION (GDP-8). `main`'s own control flow
    only special-cases `verdict in {"broke", "broken-dispatch", "unsafe"}`
    explicitly; every OTHER verdict falls through to its `if detail:` gate,
    so a verdict this function does not yet know about still reaches success
    there whenever `detail` is empty. Gating cleanup on the literal string
    `"present"` would silently diverge from that: leaving a probe workspace
    behind precisely when `main` already reported success and moved on.
    Every verdict carrying non-empty `detail` still preserves the probe: the
    failure messages above point a reader at `<root>/probe-nwave` for the
    HOW, and a probe deleted out from under that pointer would make the HOW
    a lie.
    """
    if detail:
        return False
    workspace = _probe_workspace(root)
    if workspace.exists():
        shutil.rmtree(workspace)
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--task-file", required=True, type=Path)
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument(
        "--auth-profile",
        type=Path,
        default=_DEFAULT_AUTH_PROFILE,
        help="profile whose subscription login both arms seed; see _DEFAULT_AUTH_PROFILE",
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        default=None,
        help=(
            "install this exact pre-built wheel instead of packaging --checkout; "
            "skips build_arm_runtime entirely"
        ),
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=None,
        help=(
            "a schema v1.1 DeliveryContract whose verification-scope.commands "
            "must run verbatim, no ModuleNotFound, in the clean nWave fixture "
            "before arms.json is written; see probe_persisted_verification_commands"
        ),
    )
    args = parser.parse_args(argv)

    missing = missing_sandbox_prerequisites()
    if missing:
        sys.stderr.write(
            f"WHAT: required sandbox executable(s) not found on PATH: {', '.join(missing)}.\n"
            "WHY:  the Claude delivery sandbox is fail-closed (sandbox.failIfUnavailable\n"
            "      = true) and needs these at delivery time; building the arm runtime and\n"
            "      spending a pair only to discover this mid-delivery wastes both and\n"
            "      still produces no valid measurement.\n"
            "HOW:  stage the missing executable(s) and put them on PATH -- a global\n"
            "      install is not required, prepend a directory that provides them. Do\n"
            "      NOT relax sandbox.failIfUnavailable or filesystem/network policy to\n"
            "      work around this.\n"
        )
        return 78

    wheel = resolve_wheel(args.wheel) if args.wheel is not None else None

    # Row 16 (K4 matrix): refuse a dirty checkout BEFORE any packaging or
    # wheel resolution spends work -- the recorded commit_sha below is only
    # a valid provenance claim if the tree it names is exactly what it says.
    try:
        commit_sha = resolve_clean_commit_sha(args.checkout)
    except GitProvenanceUnavailable as exc:
        sys.stderr.write(str(exc))
        return 78

    args.root.mkdir(parents=True, exist_ok=True)
    if wheel is not None:
        venv = build_arm_runtime_from_wheel(args.root, wheel)
        print(f"wheel       : {wheel}")
        print(f"wheel sha256: {_sha256(wheel)}")
    else:
        venv, wheel = build_arm_runtime(args.root, args.checkout)
        print(f"wheel       : {wheel}")
        print(f"wheel sha256: {_sha256(wheel)}")
    print(f"arm runtime : {venv}")

    verdict, detail = probe_engagement(args.root, venv, args.auth_profile, args.model)
    if verdict == "broke":
        sys.stderr.write(
            "WHAT: a step of the nWave arm's setup FAILED.\n"
            + "".join(f"      {line}\n" for line in detail)
            + "WHY:  the arm's environment was never established, so a campaign run now\n"
            "      would measure a broken install rather than nWave.\n"
            f"HOW:  reproduce the step in {args.root / 'probe-nwave'} and read the error\n"
            "      above. This is the loud failure; it is NOT the silent-skip case.\n"
        )
        return 1
    if verdict == "broken-dispatch":
        sys.stderr.write(
            "WHAT: the real installed `des dispatch --help` failed under the arm's\n"
            "      effective PATH.\n"
            + "".join(f"      - {line}\n" for line in detail)
            + "WHY:  the installed console script's `#!/usr/bin/env python3` shebang\n"
            "      resolves against whatever python3 is first on PATH at execution\n"
            "      time; the arm's PATH deliberately puts the caller project's fixture\n"
            "      venv there, so a caller venv missing a package the installed\n"
            "      dispatch imports crashes silently before argument parsing. Spending\n"
            "      a model call on the permission canary now would waste it on a\n"
            "      delivery runner whose own dispatch entry point cannot run.\n"
            f"HOW:  inspect {args.root / 'probe-nwave'}, reproduce the argv/env above by\n"
            "      hand, and fix the installed dispatch entry point before rerunning\n"
            "      this preflight.\n"
        )
        return 1
    if verdict == "unsafe":
        sys.stderr.write(
            "WHAT: the exact Claude delivery runner failed its permission canary.\n"
            + "".join(f"      - {line}\n" for line in detail)
            + "WHY:  declared settings are not effective-permission evidence. Running K4\n"
            "      now could deny required workspace edits or expose provider config.\n"
            f"HOW:  inspect {args.root / 'probe-nwave'}, correct the runner permission\n"
            "      syntax, and rerun this preflight before writing arms.json.\n"
        )
        return 1
    if detail:
        sys.stderr.write(
            "WHAT: the nWave arm's setup completed but nWave did not arrive.\n"
            + "".join(f"      - {m}\n" for m in detail)
            + "WHY:  every step exited 0, so no exit code can catch this. The campaign\n"
            "      would run to completion and its comparison table would be vanilla\n"
            "      against vanilla, reported as nWave against vanilla.\n"
            "HOW:  `nwave-ai project enable` needs --yes under stdin=DEVNULL; check the\n"
            "      probe workspace under <root>/probe-nwave to see what did land.\n"
        )
        return 1
    print("engagement  : nWave section injected, agents and skills present")

    contract_path = args.contract
    contract_source = "--contract"
    if contract_path is None:
        contract_path = discover_delivery_contract(_probe_workspace(args.root))
        contract_source = "discovered"
    verification_status: dict[str, object]
    if contract_path is None:
        reason = (
            "no --contract was given, and no single DeliveryContract exists "
            f"at the canonical {_CANONICAL_DELIVERY_CONTRACTS_DIR}/ location "
            "inside the nWave arm's workspace"
        )
        verification_status = {"status": "indeterminate", "reason": reason}
        sys.stderr.write(
            f"WHAT: {reason}.\n"
            "WHY:  row 4's ADMISSION requires proving the persisted "
            "verification-scope argv actually runs, no ModuleNotFound, in a\n"
            "      clean fixture. ADR-SSOT-002 Section 4c names `docs/"
            "delivery-contracts/{DeliveryId}.json` as the one admitted\n"
            "      deterministic authoring-time projection, but `des dispatch` "
            "itself never discovers a contract path (no marker-walk,\n"
            "      no cwd/env inference, no registry -- Section 4a items 3 "
            "and 5, deliberately). Before a real delivery has produced\n"
            "      exactly one contract there, this harness has nothing to "
            "execute either.\n"
            "HOW:  pass --contract <path> explicitly once a DeliveryContract "
            f"exists, or let a real delivery populate {_CANONICAL_DELIVERY_CONTRACTS_DIR}/\n"
            "      in the arm workspace first. INDETERMINATE, not a skip: "
            "the campaign proceeds, but row 4's ADMISSION is UNPROVEN for "
            "this run.\n"
        )
    else:
        verification_problems = probe_persisted_verification_commands(
            contract_path, _probe_workspace(args.root)
        )
        if verification_problems:
            sys.stderr.write(
                f"WHAT: the persisted verification-scope.commands ({contract_source} "
                f"contract {contract_path}) did not run cleanly in the clean fixture.\n"
                + "".join(f"      - {p}\n" for p in verification_problems)
                + "WHY:  a verification command that dies in a clean fixture (row 4, K4\n"
                "      matrix) makes every K4 subject execution built on it "
                "non-reproducible.\n"
                f"HOW:  inspect {_probe_workspace(args.root)}, reproduce the argv/env "
                "above by hand, and fix the persisted command before rerunning.\n"
            )
            return 1
        verification_status = {
            "status": "proven",
            "contract": str(contract_path),
            "source": contract_source,
        }
        print(
            f"verification: persisted verification-scope commands ({contract_source} "
            f"contract {contract_path}) ran clean"
        )

    if cleanup_probe_workspace(args.root, verdict, detail):
        print(f"probe clean : removed {_probe_workspace(args.root)}")

    arm_env = _arm_env()
    delivery = delivery_argv(args.model, arm_env["PATH"])
    # IDENTICAL argv in both arms, sharing the SAME `arm_env`: the argv's
    # `--settings env.PATH` token and this env's PATH both carry the SAME
    # `{workspace}`-templated PATH string, declared once here. They stay
    # byte-equal only once `paired_campaign.ArmSpec` renders BOTH the argv
    # token and the env dict from the same workspace -- see `delivery_argv`
    # and `ArmSpec.rendered`/`ArmSpec.rendered_env`. Claude reads PATH from
    # both rendered places for the same sandboxed run (see
    # `_render_sandbox_settings`). The only declared difference between arms
    # is the setup, which makes the campaign single-variable: anything the
    # treatment arm does differently, it does because nWave is installed, not
    # because its prompt was worded to invite it.
    spec = {
        "task": args.task_file.read_text(encoding="utf-8").strip(),
        "artifact": {
            "kind": "wheel",
            "path": str(wheel),
            "sha256": _sha256(wheel),
            "commit_sha": commit_sha,
        },
        "arms": {
            # `verification` (row 4, K4 matrix -- GDP-8 arity corollary: the
            # third state must reach the AGGREGATE, not stop at stdout) is
            # IDENTICAL on both arms deliberately: the check is a property of
            # this campaign's candidate SHA/wheel, established once in
            # preflight against the nWave arm's probe workspace -- the
            # control arm never runs DES or produces a DeliveryContract of
            # its own to verify. Duplicating the one fact onto both arm
            # records (rather than only "nwave") means a downstream reader
            # of EITHER arm's record can see it without knowing that
            # asymmetry, and neither arm's record silently omits it.
            "control": {
                "setup": control_setup_steps(args.auth_profile),
                "argv": delivery,
                "env": arm_env,
                "verification": verification_status,
            },
            "nwave": {
                "setup": nwave_setup_steps(venv, args.auth_profile),
                "argv": delivery,
                "env": arm_env,
                "verification": verification_status,
            },
        },
    }
    out = args.root / "arms.json"
    out.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    print(f"arms spec   : {out}")
    print(
        "\nBoth arms carry the SAME argv and the SAME per-arm config dir, each"
        "\nseeded with the SAME subscription login. An earlier note here claimed an"
        "\nempty config dir was 'still authenticated' and needed no credential: it"
        "\nwas authenticated by API CREDIT, which is a different payer. That claim"
        "\nis withdrawn - a probe that SUCCEEDS tells you the operation worked,"
        "\nnever which mechanism made it work."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
