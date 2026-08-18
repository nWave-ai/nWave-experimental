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
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

from scripts.analysis.k4 import prepare_examiner_fixture as pef
from scripts.analysis.k4 import subject as k4_subject


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


#: Mirrors `k4_subject.SUT_URL`/`SUT_PINNED_REV` as plain module attributes
#: (rather than referencing `k4_subject.*` inline everywhere below) so a test
#: can monkeypatch either one -- e.g. pointing `_SUT` at a local throwaway
#: repo and `_SUT_PINNED_REV` at that repo's own HEAD commit -- without
#: reaching into a second module. `scripts/analysis/k4/subject.py` is the
#: canonical source both this module and `run_acceptance.py` read; bump the
#: pin there, never here.
_SUT = k4_subject.SUT_URL
_SUT_PINNED_REV = k4_subject.SUT_PINNED_REV


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
#:
#: The checkout target is `_SUT_PINNED_REV`, read at CALL time (never
#: baked into a module-level literal) so a test can monkeypatch it -- e.g.
#: to a local throwaway repo's own HEAD commit, the way
#: `test_k4_arm_workspace_is_detached.py` already monkeypatches `_SUT`.
#: Reproducibility (K4 matrix rows 2/4) needs BOTH arms of every pair, and
#: every pair of a campaign, checked out to the identical commit -- a bare
#: `--detach HEAD` merely detaches from whatever the shallow clone's
#: default-branch tip happened to be at that exact moment, which can differ
#: run to run and even arm to arm.
def _detach_step() -> list[str]:
    return ["git", "checkout", "--detach", _SUT_PINNED_REV]


def nwave_setup_steps(venv: Path, auth_profile: Path) -> list[list[str]]:
    """The nWave arm's declared setup. `--yes` is load-bearing, see module doc."""
    cli = str(venv / "bin" / "nwave-ai")
    return [
        # Clone FIRST. `git clone <url> .` refuses a non-empty directory, and the
        # seed creates `.claude-k4/` in exactly that directory - so seeding first
        # made the clone exit 128. Caught by the preflight on its own run.
        #
        # No `--depth 1`: pinning to a specific historical commit needs the
        # commit reachable in the local object store, and a shallow clone
        # only guarantees the CURRENT default-branch tip -- which, for an
        # older pin, it may not even be an ancestor of. A full clone of a
        # small OSS repo costs seconds, not the reproducibility this pin
        # exists for.
        ["git", "clone", _SUT, "."],
        _detach_step(),
        pef.delivery_setup_step(),
        # Row 11 (K4 matrix): provisions `pef.DOC_NAME` -- the value
        # authority `nw-user-examiner` reads its `PublicStartRecipe` from
        # -- before any model call. Runs AFTER `delivery_setup_step`
        # (which unlinks it), so it is the doc actually present when
        # setup finishes. Supersedes the earlier "examiner-only credential"
        # rationale: `pef.DOC_NAME`'s API key is a throwaway
        # fixture-owned dev credential the clone-local DB alone
        # recognizes, not a real secret, and every agent touching this
        # workspace -- architect, crafter, examiner alike -- now sees the
        # SAME facts from turn one instead of the examiner alone
        # discovering them empirically (Run 8: 40 wasted calls).
        pef.fixture_setup_step(pef.NWAVE_PORT),
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
        ["git", "clone", _SUT, "."],
        _detach_step(),
        pef.delivery_setup_step(),
        # Symmetric with the nWave arm's own step above, at the arm-
        # declared control port so the two fixtures never collide on one
        # port if a campaign ever ran them side by side. Kept identical
        # on BOTH arms deliberately: the fixture facts are a property of
        # the SUBJECT, not of nWave being installed, so the comparison
        # arms must still differ only in what their setup installs.
        pef.fixture_setup_step(pef.CONTROL_PORT),
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
                "network": {
                    "allowedDomains": list(k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS)
                },
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


#: Repo root for THIS checkout of nwave-dev, resolved from preflight.py's own
#: location (`scripts/analysis/k4/preflight.py` -> parents[3]) -- the same
#: computation `tests/des/unit/adapters/drivers/hooks/
#: test_auto_root_bash_lockdown.py::_REPO_ROOT` does from its own deeper
#: location. `route_walk` reads nw-auto/SKILL.md from the CHECKOUT (never
#: from an installed arm's copy), matching what a live delivery agent's own
#: session actually consults.
_ROUTE_WALK_REPO_ROOT = Path(__file__).resolve().parents[3]
_NW_AUTO_SKILL_MD = _ROUTE_WALK_REPO_ROOT / "nWave" / "skills" / "nw-auto" / "SKILL.md"


def des_fenced_lines(markdown_text: str) -> list[str]:
    """Every literal `des ...` invocation inside a FENCED code block --
    i.e. a command a reader is meant to copy verbatim, as opposed to a
    backtick-prose mention (a prohibition like "Root never calls `des
    validate-delivery-contract` itself", or a descriptive aside like
    "`des verify-charter-filled` is a structural gate only"). A fenced
    line counts only when its STRIPPED form starts with `des ` -- prose
    mentioning `des X` mid-sentence inside a fence (there is none today,
    but the stricter anchor keeps a future one from being misread as a
    command). `\\`-continued lines are joined into one logical command
    before the `des `-prefix check, so a multi-line invocation (e.g.
    `des prepare-ordinary-request \\` continuing across several
    `--flag value \\` lines) is returned as a single string. Fences may be
    indented under a numbered step, so the fence marker itself is matched
    with leading whitespace stripped.

    THE one shared fence parser: `des_subcommands_root_is_told_to_run`
    below (subcommand-name-only view) and the executable-example guard
    (`tests/build/test_des_examples_are_executable.py`, full-argv view)
    both derive from this single extraction -- two independently
    hand-typed views is exactly the drift class that let `des
    resolve-charters` go missing from the allowlist while SKILL.md
    mandated it (`fix(auto): allow every des subcommand the root route
    mandates`), and that let a malformed `des code-fact` example ship
    unnoticed (`fix(auto): documented des examples must parse`).
    """
    in_fence = False
    lines: list[str] = []
    pending: str | None = None
    for raw_line in markdown_text.split("\n"):
        if raw_line.strip().startswith("```"):
            in_fence = not in_fence
            if pending is not None:
                lines.append(pending)
                pending = None
            continue
        if not in_fence:
            continue
        stripped = raw_line.strip()
        if pending is not None:
            pending = f"{pending} {stripped}"
        elif stripped.startswith("des "):
            pending = stripped
        else:
            continue
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
        else:
            lines.append(pending)
            pending = None
    if pending is not None:
        lines.append(pending)
    return lines


def des_subcommands_root_is_told_to_run(skill_md_text: str) -> set[str]:
    """The `des <subcommand>` tokens named by every `des_fenced_lines`
    entry -- THE one shared source for "which `des` subcommands does
    root's own documented route mandate": `route_walk_steps` below drives
    its root-Bash coverage checks off this same parser, and
    `tests/des/unit/adapters/drivers/hooks/test_auto_root_bash_lockdown.py`'s
    `TestAutoRootBashAllowlistCoversSkillMandatedSubcommands` imports this
    exact function rather than carrying its own copy.
    """
    subcommands: set[str] = set()
    for line in des_fenced_lines(skill_md_text):
        subcommands.update(
            match.group(1)
            for match in re.finditer(r"\bdes\s+([a-zA-Z][a-zA-Z-]*)", line)
        )
    return subcommands


# The exact quoted-delimiter suffixes a seed-heredoc header line ends in --
# must stay byte-identical to `pre_tool_use_handler._VALUE_SEED_HEREDOC_
# HEADER_SUFFIXES`, the ONE other place this exact pair is spelled out.
_HEREDOC_HEADER_SUFFIXES = (" <<'NW_SEED'", ' <<"NW_SEED"')
_ANGLE_PLACEHOLDER_RE = re.compile(r"<([^>]+)>")
_BRACKETED_OPTIONAL_RE = re.compile(r"\[[^\]]*\]")


def substitute_example_placeholder(name: str, *, root: str, delivery_id: str) -> str:
    """One concrete value for a documentation placeholder NAME (the
    contents of a `<...>` span) shaped by what it claims to hold -- an
    enum (`M|L`, `true|false`, ...) resolves to its first member; anything
    naming "root" or "id" resolves to the caller's own real value. Callers
    needing a broader placeholder vocabulary (files, symbols, anchors,
    locators -- the ones no single real value can stand in for) are
    `tests/build/test_des_examples_are_executable.py`'s own concern, not
    this one: this function exists ONLY for `route_walk_steps`, which
    feeds the hook exactly two known heredoc headers with exactly these
    two placeholder kinds."""
    if "|" in name:
        return name.split("|", 1)[0].strip()
    lowered = name.lower()
    if "root" in lowered:
        return root
    if "id" in lowered:
        return delivery_id
    return name


def substitute_heredoc_header(header: str, *, root: str, delivery_id: str) -> str:
    """`header` (one `des_fenced_lines` entry ending in the seed-heredoc
    redirect) with every `<...>`/bracketed-optional placeholder resolved
    to a concrete value. Never touches the heredoc redirect suffix itself
    or an already-literal token -- a quoted `"ARCHITECTURE-COVERED:
    path.md#anchor"` example is already a valid architecture-authority
    line and needs no substitution."""
    resolved = _BRACKETED_OPTIONAL_RE.sub("", header)
    resolved = _ANGLE_PLACEHOLDER_RE.sub(
        lambda match: substitute_example_placeholder(
            match.group(1), root=root, delivery_id=delivery_id
        ),
        resolved,
    )
    return " ".join(resolved.split())


def route_walk_heredoc_command(
    skill_md_text: str, *, subcommand: str, root: str, delivery_id: str, seed: str
) -> str | None:
    """The EXACT fenced `des <subcommand> ... <<'NW_SEED'` header from
    `skill_md_text` -- never hand-retyped -- with its placeholders resolved
    to this walk's own real `root`/`delivery_id`, and `seed` as the
    heredoc body. `None` when no fenced example for `subcommand` exists at
    all (a genuine documentation gap `route_walk_steps` must report as a
    failing step, never paper over with a fallback command it invents).
    Genesis: `nw-auto/SKILL.md` mandated the seed heredoc into `des
    resolve-charters` once it started building the PO envelope; the
    hand-typed `resolve-charters-allow` step in `route_walk_steps` kept
    using the OLD plain-argv shape and never caught the drift -- this is
    THE fix for that class, not just that one instance: any future
    heredoc-header example change in SKILL.md is picked up automatically,
    never re-hand-typed here.
    """
    for line in des_fenced_lines(skill_md_text):
        if not line.endswith(_HEREDOC_HEADER_SUFFIXES):
            continue
        try:
            tokens = shlex.split(line.split("<<", 1)[0])
        except ValueError:
            continue
        if len(tokens) >= 2 and tokens[0] == "des" and tokens[1] == subcommand:
            header = substitute_heredoc_header(line, root=root, delivery_id=delivery_id)
            return f"{header}\n{seed}\nNW_SEED"
    return None


def _route_walk_workspace(root: Path) -> Path:
    return root / "probe-route-walk"


def _write_auto_engaged_transcript(workspace: Path) -> Path:
    """A minimal, self-contained transcript observing `Skill(nw-mode-select)`
    then `Skill(nw-auto)` -- the two tool_use markers
    `des.application.skill_tracking_service.resolve_root_mode_state` reads
    to project `RootModeState.AUTO_ENGAGED`. `route_walk` never depends on
    any prior real run's transcript file existing on disk; it manufactures
    its own evidence of the one precondition the Auto-root lockdown arms on.
    """
    path = workspace / "route-walk-auto-engaged-transcript.jsonl"
    entries = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "nw-mode-select"},
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
                ]
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return path


def _parse_producer_stdout(text: str) -> dict[str, str]:
    """Split one `des prepare-ordinary-request`/`des dispatch`-shaped
    stdout into its `KEY: value` lines, keyed by KEY, value kept RAW (JSON
    string literals stay encoded) -- callers that need the decoded text
    (e.g. re-deriving VALUE-SEED) decode it themselves. `OUTCOME`/
    `VALUE-SEED` values can themselves contain embedded newlines once
    decoded, but the PRODUCER always emits them as one JSON-encoded line,
    so a plain line-by-line split is exact here."""
    fields: dict[str, str] = {}
    for line in text.split("\n"):
        if ": " not in line:
            continue
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


#: Fixed, non-secret probe seed: `route_walk` never delivers this, it only
#: proves the deterministic gate chain accepts and threads a well-formed
#: seed end to end. Kept short and unambiguous as a probe, never mistakable
#: for a real value-seed if it ever leaked into a log.
_ROUTE_WALK_SEED = (
    "K4 route-walk canonical probe -- exercises the deterministic gate chain "
    "end to end with no model call. Not a real feature request; never delivered."
)
_ROUTE_WALK_ARCH_AUTHORITY = "ARCHITECTURE-COVERED: docs/product/architecture/route-walk-probe.md#route-walk-probe"
_ROUTE_WALK_CHARTER_VALUE = (
    "Route-walk probe: an operator-facing value statement is required by the "
    "charter-scaffold producer's contract, never actually read by a human."
)


def _minimal_delivery_contract(
    *, delivery_id: str, outcome: str, base_revision: str, oracle_locator: str
) -> dict:
    """The smallest instance of `nWave/schemas/thin-delivery-contract.schema.json`
    that validates -- built directly against the schema's own `required`
    lists, never against an ATD's real design judgment. `route_walk` uses
    this ONLY to exercise `des validate-delivery-contract`/`des dispatch`'s
    own CLI mechanics; it says nothing about what a real DeliveryContract's
    `targets`/`obligations`/`boundary` content should be."""
    return {
        "schema-version": "1.2",
        "delivery-id": delivery_id,
        "repository": {"worktree": ".", "base-revision": base_revision},
        "outcome": outcome,
        "targets": {
            "route-walk-probe.txt": {
                "candidate": "route-walk-probe.txt",
                "overlap": "route-walk probe -- no real target",
                "decision": "CREATE_NEW",
                "justification": "smallest schema-valid instance for CLI-mechanics probing",
                "declared-imports": [],
                "contract-shape": "bounded-change",
                "boundary": {
                    "failure-behavior": "probe-only placeholder",
                    "substrate-lie": "probe-only placeholder",
                    "substrate-probe": "probe-only placeholder",
                    "double-blind-spot": "probe-only placeholder",
                },
            }
        },
        "paradigm": "object_oriented",
        "delivery-route": "RED_TO_GREEN",
        "obligations": ["PRESERVATION"],
        "acceptance-tests": {"locator": oracle_locator},
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "toolchain", "name": "pytest"},
                    "arguments": [oracle_locator],
                }
            ]
        },
        "applicability": {"independent-review": False, "examine": True},
        "budget": {"token-limit": 2000000, "wall-clock-minutes": 30},
    }


def _hook_step(
    name: str,
    mandate: str,
    *,
    expect_allow: bool,
    hook_run: Callable[[dict], tuple[int, str]],
    payload: dict,
) -> dict:
    code, output = hook_run(payload)
    allowed = code == 0
    passed = allowed == expect_allow
    return {
        "name": name,
        "kind": "hook",
        "mandate": mandate,
        "expected": "allow" if expect_allow else "deny",
        "observed": "allow" if allowed else f"deny (exit {code})",
        "detail": output[:400],
        "passed": passed,
    }


def _cli_step(
    name: str,
    mandate: str,
    *,
    expect_exit: int,
    cli_run: Callable[[list[str], str | None], tuple[int, str]],
    argv: list[str],
    stdin: str | None = None,
) -> tuple[dict, str]:
    code, output = cli_run(argv, stdin)
    passed = code == expect_exit
    step = {
        "name": name,
        "kind": "cli",
        "mandate": mandate,
        "expected": f"exit {expect_exit}",
        "observed": f"exit {code}",
        "detail": output[:400],
        "passed": passed,
    }
    return step, output


def _skipped_step(name: str, mandate: str, reason: str) -> dict:
    """A step that never ran because an upstream step it depends on already
    failed -- reported explicitly as a failing entry in the table, never
    silently dropped. `route_walk`'s CLI chain is sequential (each stage
    consumes the previous stage's real stdout), so one failure invalidates
    every input downstream of it."""
    return {
        "name": name,
        "kind": "skipped",
        "mandate": mandate,
        "expected": "not evaluated",
        "observed": f"skipped: {reason}",
        "detail": "",
        "passed": False,
    }


def route_walk_steps(
    *,
    repo_root: str,
    hook_run: Callable[[dict], tuple[int, str]],
    cli_run: Callable[[list[str], str | None], tuple[int, str]],
    skill_md_text: str,
    transcript_path: str,
) -> dict:
    """Walk the canonical Auto route through the deterministic layer only --
    no model call -- and classify it `proven` or `blocked`.

    Pure(ish) evaluator: `hook_run`/`cli_run` are injected, so this never
    itself spawns a subprocess or touches any file outside `repo_root`
    (where it writes the probe DeliveryContract/oracle so `cli_run`'s real
    binding has something real to validate against). `route_walk` below
    binds both callables to the actual installed arm; tests inject fakes
    for RED/GREEN classification, or the real
    `pre_tool_use_handler.handle_pre_tool_use()` in-process for the two
    genesis cases.

    Order: the real CLI chain runs FIRST (`prepare-ordinary-request` ->
    `charter-scaffold` -> the hand-built minimal contract -> `validate-
    delivery-contract` -> `dispatch`), because the root-Bash envelope checks
    for the ATD/crafter Agent dispatch need that chain's REAL stdout --
    forwarding it verbatim is the entire point of the two envelope gates
    (`nw-auto/SKILL.md` 'CLI dispatch'). A CLI-chain failure short-circuits
    every step whose input it would have produced, each reported as an
    explicit failing `skipped` entry rather than silently absent from the
    table.
    """
    steps: list[dict] = []
    repo_root_path = Path(repo_root)

    # --- root-Bash: the heredoc shape, hook-level -- independent of whether
    # the CLI chain below actually executes cleanly, so it runs first and
    # unconditionally. Fed the EXACT fenced example `skill_md_text` itself
    # documents (`route_walk_heredoc_command`), never a hand-retyped
    # reconstruction -- the drift class this walk exists to catch.
    prep_heredoc_command = route_walk_heredoc_command(
        skill_md_text,
        subcommand="prepare-ordinary-request",
        root=repo_root,
        delivery_id="auto-0000000000000000",
        seed=_ROUTE_WALK_SEED,
    )
    steps.append(
        _hook_step(
            "seed-heredoc-allow",
            "nw-auto/SKILL.md step 1: 'Run exactly once, with VALUE-SEED bytes on "
            "stdin ... des prepare-ordinary-request ... <<\\'NW_SEED\\' ...'.",
            expect_allow=True,
            hook_run=hook_run,
            payload={
                "tool_name": "Bash",
                "tool_input": {
                    "command": prep_heredoc_command
                    or "# no fenced prepare-ordinary-request heredoc example found"
                },
                "transcript_path": transcript_path,
            },
        )
    )

    # --- real CLI chain, canonical stub inputs -------------------------------
    prep_step, prep_stdout = _cli_step(
        "cli-prepare-ordinary-request",
        "nw-auto/SKILL.md step 1: `des prepare-ordinary-request ... <<'NW_SEED' ... NW_SEED`.",
        expect_exit=0,
        cli_run=cli_run,
        argv=[
            "des",
            "prepare-ordinary-request",
            "--size",
            "M",
            "--repo-root",
            repo_root,
            "--architecture-authority",
            _ROUTE_WALK_ARCH_AUTHORITY,
            "--delivery-route",
            "RED_TO_GREEN",
            "--examine",
            "true",
            "--independent-review",
            "false",
        ],
        stdin=_ROUTE_WALK_SEED,
    )
    steps.append(prep_step)

    if not prep_step["passed"]:
        for name, mandate in (
            (
                "cli-charter-scaffold",
                "the DISTILL charter producer, `des charter-scaffold`.",
            ),
            (
                "cli-validate-delivery-contract",
                "`des validate-delivery-contract`, the crafter's own consumer-boundary check.",
            ),
            (
                "cli-dispatch",
                "nw-auto/SKILL.md 'CLI dispatch': `des dispatch --repo-root ROOT --delivery-contract PATH`.",
            ),
            (
                "resolve-charters-allow",
                "nw-auto/SKILL.md step 2: root's mandated next command after "
                "prepare-ordinary-request.",
            ),
            (
                "atd-dispatch-envelope-allow",
                "nw-auto/SKILL.md AB batch: ATD receives producer stdout verbatim.",
            ),
            (
                "crafter-dispatch-envelope-allow",
                "nw-auto/SKILL.md 'CLI dispatch': crafter receives dispatch stdout verbatim.",
            ),
        ):
            steps.append(
                _skipped_step(name, mandate, "cli-prepare-ordinary-request failed")
            )
        return {"status": "blocked", "steps": steps}

    producer_fields = _parse_producer_stdout(prep_stdout)
    delivery_id = producer_fields.get("DELIVERY-ID", "")
    base_revision = producer_fields.get("BASE-REVISION", "")
    outcome_raw = producer_fields.get("OUTCOME", '""')
    try:
        outcome_text = json.loads(outcome_raw)
    except json.JSONDecodeError:
        outcome_text = _ROUTE_WALK_SEED

    charter_step, _ = _cli_step(
        "cli-charter-scaffold",
        "the DISTILL charter producer, `des charter-scaffold`.",
        expect_exit=0,
        cli_run=cli_run,
        argv=[
            "des",
            "charter-scaffold",
            "--delivery-id",
            delivery_id,
            "--repo-root",
            repo_root,
            "--value",
            _ROUTE_WALK_CHARTER_VALUE,
        ],
    )
    steps.append(charter_step)

    oracle_relative = f"route_walk_probe_oracle_{delivery_id}.py"
    oracle_path = repo_root_path / oracle_relative
    oracle_path.write_text(
        '"""route_walk probe oracle placeholder -- not a real acceptance test."""\n\n\n'
        "def test_probe_placeholder() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    contract_relative = f"docs/delivery-contracts/{delivery_id}.json"
    contract_path = repo_root_path / contract_relative
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(
            _minimal_delivery_contract(
                delivery_id=delivery_id,
                outcome=outcome_text,
                base_revision=base_revision,
                oracle_locator=oracle_relative,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    validate_step, _ = _cli_step(
        "cli-validate-delivery-contract",
        "`des validate-delivery-contract`, the crafter's own consumer-boundary check.",
        expect_exit=0,
        cli_run=cli_run,
        argv=[
            "des",
            "validate-delivery-contract",
            "--repo-root",
            repo_root,
            "--delivery-contract",
            contract_relative,
        ],
    )
    steps.append(validate_step)

    dispatch_step, dispatch_stdout = _cli_step(
        "cli-dispatch",
        "nw-auto/SKILL.md 'CLI dispatch': `des dispatch --repo-root ROOT --delivery-contract PATH`.",
        expect_exit=0,
        cli_run=cli_run,
        argv=[
            "des",
            "dispatch",
            "--repo-root",
            repo_root,
            "--delivery-contract",
            contract_relative,
        ],
    )
    steps.append(dispatch_step)

    # --- root-Bash: resolve-charters, real shape, not just a coverage --help -
    # `prep_step` is guaranteed to have passed here -- the early return above
    # already handles the failure case -- so `delivery_id` is always real.
    # Fed the EXACT fenced example `skill_md_text` documents (heredoc
    # included -- resolve-charters now needs the seed on stdin to build the
    # PO envelope on AUTHOR), never a hand-retyped reconstruction. This is
    # the genesis defect this walk missed: the OLD hand-typed plain-argv
    # command here never exercised the heredoc shape SKILL.md actually
    # mandates, so it stayed green while a real run was denied.
    rc_heredoc_command = route_walk_heredoc_command(
        skill_md_text,
        subcommand="resolve-charters",
        root=repo_root,
        delivery_id=delivery_id,
        seed=_ROUTE_WALK_SEED,
    )
    steps.append(
        _hook_step(
            "resolve-charters-allow",
            "nw-auto/SKILL.md step 2: 'On Prepared(SeededAuthority), run exactly "
            "one command: des resolve-charters --repo-root <root> --delivery-id "
            "<producer id> --examine <true|false> <<\\'NW_SEED\\' ...'.",
            expect_allow=True,
            hook_run=hook_run,
            payload={
                "tool_name": "Bash",
                "tool_input": {
                    "command": rc_heredoc_command
                    or "# no fenced resolve-charters heredoc example found"
                },
                "transcript_path": transcript_path,
            },
        )
    )

    # --- root-Bash envelope checks, fed the CLI chain's REAL stdout ----------
    if prep_step["passed"]:
        atd_body = prep_stdout
        atd_payload = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "nw-acceptance-designer",
                "description": "route-walk probe: ATD dispatch envelope",
                "prompt": atd_body,
                "run_in_background": False,
            },
            "transcript_path": transcript_path,
        }
        steps.append(
            _hook_step(
                "atd-dispatch-envelope-allow",
                "nw-auto/SKILL.md AB batch: ATD receives producer stdout verbatim.",
                expect_allow=True,
                hook_run=hook_run,
                payload=atd_payload,
            )
        )
    if dispatch_step["passed"]:
        crafter_prompt = dispatch_stdout.strip() + f"\n\nREPO-ROOT: {repo_root}"
        crafter_payload = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "nw-software-crafter",
                "description": "route-walk probe: crafter dispatch envelope",
                "prompt": crafter_prompt,
                "run_in_background": False,
            },
            "transcript_path": transcript_path,
        }
        steps.append(
            _hook_step(
                "crafter-dispatch-envelope-allow",
                "nw-auto/SKILL.md 'CLI dispatch': crafter receives dispatch stdout verbatim.",
                expect_allow=True,
                hook_run=hook_run,
                payload=crafter_payload,
            )
        )
    else:
        steps.append(
            _skipped_step(
                "crafter-dispatch-envelope-allow",
                "nw-auto/SKILL.md 'CLI dispatch': crafter receives dispatch stdout verbatim.",
                "cli-dispatch failed",
            )
        )

    # --- root-Bash allowlist coverage, driven off the ONE shared parser ------
    mandated_subcommands = des_subcommands_root_is_told_to_run(skill_md_text)
    for subcommand in sorted(mandated_subcommands):
        steps.append(
            _hook_step(
                f"root-bash-mandated-{subcommand}-allow",
                f"nw-auto/SKILL.md's root route instructs root to run `des {subcommand}` directly.",
                expect_allow=True,
                hook_run=hook_run,
                payload={
                    "tool_name": "Bash",
                    "tool_input": {"command": f"des {subcommand} --help"},
                    "transcript_path": transcript_path,
                },
            )
        )

    # --- root-Bash negative controls: the allowlist must stay CLOSED ---------
    steps.append(
        _hook_step(
            "root-bash-negative-git-log-denied",
            "pre_tool_use_handler._AUTO_ROOT_BASH_ALLOWED_GIT_SUBCOMMANDS: `log` is not a member.",
            expect_allow=False,
            hook_run=hook_run,
            payload={
                "tool_name": "Bash",
                "tool_input": {"command": "git log --oneline -1"},
                "transcript_path": transcript_path,
            },
        )
    )
    steps.append(
        _hook_step(
            "root-bash-negative-unknown-des-subcommand-denied",
            "pre_tool_use_handler._AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS: an unlisted subcommand is denied.",
            expect_allow=False,
            hook_run=hook_run,
            payload={
                "tool_name": "Bash",
                "tool_input": {
                    "command": "des route-walk-probe-unknown-subcommand --help"
                },
                "transcript_path": transcript_path,
            },
        )
    )

    # --- subagent Bash calls (crafter), no Auto-root allowlist applies -------
    for name, mandate, command in (
        (
            "subagent-git-diff-allow",
            "the dispatched crafter's own verification Bash calls run unrestricted "
            "except the host-scan control below.",
            "git diff",
        ),
        (
            "subagent-pytest-allow",
            "the crafter runs its own verification-scope test command as a subagent.",
            "python -m pytest route_walk_probe_oracle.py",
        ),
        (
            "subagent-validate-delivery-contract-allow",
            "nw-auto/SKILL.md 'CLI dispatch': "
            "'that consumer-boundary check belongs to the selected crafter, not to root.'",
            "des validate-delivery-contract --repo-root . --delivery-contract docs/delivery-contracts/probe.json",
        ),
        (
            "subagent-find-repo-scoped-allow",
            "a repo-scoped find is never a host-wide traversal root.",
            "find . -iname '*.py'",
        ),
    ):
        steps.append(
            _hook_step(
                name,
                mandate,
                expect_allow=True,
                hook_run=hook_run,
                payload={
                    "tool_name": "Bash",
                    "tool_input": {"command": command},
                    "agent_type": "nw-software-crafter",
                    "agent_id": "route-walk-probe-crafter",
                },
            )
        )
    steps.append(
        _hook_step(
            "subagent-find-root-denied",
            "pre_tool_use_handler._evaluate_nwave_subagent_host_scan: an nWave "
            "subagent's find/bfs call rooted at the filesystem root is denied.",
            expect_allow=False,
            hook_run=hook_run,
            payload={
                "tool_name": "Bash",
                "tool_input": {"command": "find / -iname '*.py'"},
                "agent_type": "nw-software-crafter",
                "agent_id": "route-walk-probe-crafter",
            },
        )
    )

    status = "proven" if all(step["passed"] for step in steps) else "blocked"
    return {"status": status, "steps": steps}


def _installed_hook_run(workspace: Path, venv: Path, payload: dict) -> tuple[int, str]:
    """Invoke the arm's INSTALLED PreToolUse hook exactly as Claude Code
    itself does -- `python3 -m
    des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use`, JSON
    on stdin, `PYTHONPATH` pointed at the arm's own `.claude-k4/lib/python`
    -- against `workspace`'s own config dir, never the operator's
    `~/.claude`. Mirrors `.claude-k4/settings.json`'s own `hooks.PreToolUse`
    command verbatim (the SAME file `nwave-ai install` wrote for this
    workspace), so this is the exact command Claude Code itself would run,
    not an approximation of it.
    """
    env = {
        **_rendered_arm_env(workspace),
        "PYTHONPATH": str(workspace / ".claude-k4" / "lib" / "python"),
    }
    try:
        done = subprocess.run(
            [
                str(venv / "bin" / "python3"),
                "-m",
                "des.adapters.drivers.hooks.claude_code_hook_adapter",
                "pre-tool-use",
            ],
            input=json.dumps(payload),
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return done.returncode, (done.stdout or done.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after 30s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"


def _installed_cli_run(
    workspace: Path, argv: list[str], stdin: str | None
) -> tuple[int, str]:
    """Invoke the arm's INSTALLED `des` CLI shim for real -- `argv[0]` is
    always the literal string `"des"` (matching what a root/subagent Bash
    call actually types), resolved via PATH exactly as a real Bash call
    would resolve it: `_rendered_arm_env(workspace)["PATH"]` already puts
    `{workspace}/.claude-k4/bin` first (`_arm_env`'s own doc), so
    `subprocess.run` (given an explicit `env=`, POSIX `execvpe` PATH search)
    finds the workspace's own per-arm shim.

    `venv` names the harness's SHARED build venv `nwave-ai` was pip-
    installed into to produce the wheel -- NEVER substitute `venv / "bin" /
    "des"` for the workspace shim here. That console-script entry point
    resolves `des.cli.charter_scaffold`'s package-relative asset lookups
    (`Path(__file__).resolve().parents[3]`) against the SHARED venv's own
    `site-packages`, which carries no co-located `nWave/` assets -- a real
    installed run never hits that path because `des` always resolves via
    the shim, which imports `des` from `{workspace}/.claude-k4/lib/python`
    instead (3 parents up from THERE is `.claude-k4/lib/`, sibling to the
    `nWave/` tree `nwave-ai install` populated). Caught live: run 5's
    preflight blocked on `cli-charter-scaffold` --
    `missing-charter-template: template absent at
    .../nwave-venv/lib/python3.12/nWave/templates/expectation-charter.md`
    -- exactly the shared-venv site-packages path, proving this exact bug.
    """
    env = _rendered_arm_env(workspace)
    try:
        # `subprocess.run(input=None)` inherits the CALLER's stdin rather
        # than closing it -- fine for `des prepare-ordinary-request`'s
        # heredoc (`input=stdin` sets PIPE and writes it), but every other
        # call here reads no stdin at all and must not silently inherit a
        # live/attached one, matching `_run`'s own explicit
        # `stdin=subprocess.DEVNULL` convention elsewhere in this file. Two
        # literal branches, not a `**{...}` splat: `tests/build/
        # test_no_unbounded_unstdin_spawn.py` statically checks for a
        # literal `stdin=`/`input=` keyword in the AST and cannot see
        # through a dynamic kwargs dict.
        if stdin is not None:
            done = subprocess.run(
                argv,
                input=stdin,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            done = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
        return done.returncode, (done.stdout or done.stderr)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after 60s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"


def route_walk(root: Path, venv: Path, auth_profile: Path) -> dict:
    """Build one throwaway workspace under `root`, install the real nWave
    arm into it (reusing `nwave_setup_steps`/`_rendered_arm_env` -- the SAME
    build/install/arm-env `probe_engagement` uses, never a second install
    path), and walk the canonical Auto route through it with NO model call.

    Called from `main()` AFTER the arm's own engagement probe passes and
    BEFORE `arms.json` is written: GDP-1, intercept the paid run's exact
    deterministic-layer blockers before the run is even built, not after
    burning a `claude -p` call on them.
    """
    workspace = _route_walk_workspace(root)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    env = _rendered_arm_env(workspace)

    for step in nwave_setup_steps(venv, auth_profile):
        code, tail = _run(step, cwd=workspace, env=env)
        if code != 0:
            return {
                "status": "blocked",
                "steps": [
                    {
                        "name": "route-walk-workspace-setup",
                        "kind": "setup",
                        "mandate": "the nWave arm's own declared setup, `nwave_setup_steps`.",
                        "expected": "exit 0",
                        "observed": f"exit {code}",
                        "detail": tail.strip()[:400],
                        "passed": False,
                    }
                ],
            }

    transcript_path = str(_write_auto_engaged_transcript(workspace))

    def hook_run(payload: dict) -> tuple[int, str]:
        return _installed_hook_run(workspace, venv, payload)

    def cli_run(argv: list[str], stdin: str | None) -> tuple[int, str]:
        return _installed_cli_run(workspace, argv, stdin)

    result = route_walk_steps(
        repo_root=str(workspace),
        hook_run=hook_run,
        cli_run=cli_run,
        skill_md_text=_NW_AUTO_SKILL_MD.read_text(encoding="utf-8"),
        transcript_path=transcript_path,
    )
    if result["status"] == "proven":
        shutil.rmtree(workspace)
    return result


_START_RECIPE_SERVER_TIMEOUT = 20.0
_START_RECIPE_POLL_INTERVAL = 0.2


def probe_examiner_start_recipe(workspace: Path, *, port: int) -> list[str]:
    """Prove the examiner's ACTUAL rendered start recipe -- the SAME
    `pef.DOC_NAME` file `fixture_setup_step` already wrote into this exact
    workspace, at this exact `port` -- runs under this harness's actual
    rendered env (`_rendered_arm_env`), deterministically, with NO model
    call, before a single (expensive, long) delivery/examiner turn is
    spent. One source: the API key comes from the rendered doc itself
    (`pef._existing_api_key`), the runserver command from the SAME
    `pef._runserver_argv_and_env` the doc's own display text derives
    from -- never a synthetic stand-in server or a second hand-typed key.

    Run 8 (K4 matrix): the examiner burned 40 calls trying to stand up a
    Django dev server and drive it with real HTTP requests, and got zero
    usable evidence. This canary answers, cheaply and up front, whether
    the recipe it will later read is even executable under this arm's
    env. A non-empty return here is a campaign INDETERMINATE (the harness
    itself could not prove the recipe executable, or never provisioned
    one at all), never a finding against Vera, who never got the chance
    to try.
    """
    api_key = pef._existing_api_key(workspace)
    if api_key is None:
        return [
            f"no {pef.DOC_NAME} (or no API key line in it) exists in "
            f"{workspace} -- row 11's start recipe was never provisioned "
            "for this arm before this canary ran"
        ]

    env = _rendered_arm_env(workspace)
    argv, env_overrides = pef._runserver_argv_and_env(port)
    server_env = {**env, **env_overrides}

    problems: list[str] = []
    try:
        server = subprocess.Popen(
            argv,
            cwd=workspace,
            env=server_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return [
            "the recipe's own server-start command could not even start "
            f"under the arm's rendered env: {type(exc).__name__}: {exc}"
        ]

    try:
        deadline = time.monotonic() + _START_RECIPE_SERVER_TIMEOUT
        up = False
        while time.monotonic() < deadline:
            if server.poll() is not None:
                break
            if pef._port_is_occupied(port):
                up = True
                break
            time.sleep(_START_RECIPE_POLL_INTERVAL)

        if not up:
            tail = server.stdout.read()[-600:] if server.stdout else ""
            problems.append(
                "the recipe's own server-start command never bound port "
                f"{port} under the arm's rendered env within "
                f"{_START_RECIPE_SERVER_TIMEOUT}s: {tail}"
            )
        else:
            base_url = f"http://127.0.0.1:{port}"

            # Negative control, same discipline as row 11's own proof:
            # nothing listens on a dead port under the SAME arm env -- a
            # probe that passes anyway proves nothing about the recipe.
            dead_port = pef.free_port()
            dead_argv = pef.integration_probe_argv(
                f"http://127.0.0.1:{dead_port}", api_key
            )
            try:
                dead = subprocess.run(
                    dead_argv,
                    cwd=workspace,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                dead = None
            if dead is not None and dead.returncode == 0:
                problems.append(
                    "the probe succeeded against a dead port under the "
                    "arm's rendered env -- it does not discriminate"
                )

            recipe_argv = pef.integration_probe_argv(base_url, api_key)
            try:
                done = subprocess.run(
                    recipe_argv,
                    cwd=workspace,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                problems.append(
                    "the recipe's own probe timed out against its own "
                    "live server under the arm's rendered env"
                )
            except OSError as exc:
                problems.append(
                    "the recipe's own probe could not even start under "
                    f"the arm's rendered env: {type(exc).__name__}: {exc}"
                )
            else:
                if done.returncode != 0:
                    problems.append(
                        "the recipe's own probe failed against its own "
                        "live server under the arm's rendered env: "
                        f"{(done.stderr or done.stdout)[-400:]}"
                    )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
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

    # GDP-1: intercept the paid run's exact deterministic-layer blockers
    # BEFORE the run is even built, not after burning a `claude -p` call on
    # them. `route_walk` walks the canonical Auto route through the
    # installed hook and installed `des` CLI with NO model call, in its own
    # throwaway workspace.
    route_walk_result = route_walk(args.root, venv, args.auth_profile)
    print(f"route walk  : {route_walk_result['status']}")
    for step in route_walk_result["steps"]:
        mark = "ok  " if step["passed"] else "FAIL"
        print(
            f"  [{mark}] {step['name']:45s} expected={step['expected']:10s} observed={step['observed']}"
        )
    if route_walk_result["status"] != "proven":
        first_blocked = next(
            step for step in route_walk_result["steps"] if not step["passed"]
        )
        sys.stderr.write(
            "WHAT: route_walk's canonical Auto-route step "
            f"`{first_blocked['name']}` did not behave as mandated -- "
            f"expected {first_blocked['expected']}, observed "
            f"{first_blocked['observed']}.\n"
            f"      mandate: {first_blocked['mandate']}\n"
            f"      detail:  {first_blocked['detail']}\n"
            "WHY:  the deterministic layer would deny (or wrongly allow) root's "
            "own documented next step during the real paid run -- exactly the "
            "class of defect a manual K4 replay caught after burning a\n"
            "      full delivery's tokens finding it live. Proving it here costs "
            "nothing.\n"
            f"HOW:  reproduce {first_blocked['name']} in "
            f"{_route_walk_workspace(args.root)}, fix the deterministic layer "
            "(or the mandate itself, if the SKILL.md route changed), and rerun "
            "this preflight before writing arms.json.\n"
        )
        return 1

    # Row 11 (K4 matrix), Run 8 evidence: the examiner's server-start +
    # HTTP-probe MECHANISM proven under this arm's rendered env, still
    # with NO model call, before arms.json is written. A non-empty result
    # is a campaign INDETERMINATE recorded into `spec["sandbox"]` below --
    # never a hard refusal: the crafter side can still be measured even
    # when the harness cannot prove the examiner's own recipe executable.
    start_recipe_problems = probe_examiner_start_recipe(
        _probe_workspace(args.root), port=pef.NWAVE_PORT
    )
    if start_recipe_problems:
        start_recipe_status: dict[str, object] = {
            "status": "indeterminate",
            "problems": start_recipe_problems,
        }
        print("start recipe: INDETERMINATE -- see arms.json sandbox.start_recipe")
    else:
        start_recipe_status = {"status": "proven"}
        print("start recipe: proven under the arm's rendered env")

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
        # Recorded even though `route_walk_result["status"] != "proven"`
        # already returned 1 above -- only a "proven" result ever reaches
        # this write, so `route_walk.status` is always "proven" in a written
        # `arms.json`. Kept as a real field (not folded away) so a reader of
        # arms.json can see WHICH steps were proven, not just a boolean.
        "route_walk": route_walk_result,
        # Row 11 (K4 matrix): the sandbox facts every arm's project
        # fragment states (`pef.render_project_fragment`) and the row-11
        # start-recipe canary's own verdict, so a reader of arms.json sees
        # WHAT was proven about the sandbox, not just that a campaign ran.
        "sandbox": {
            "network_allowed_domains": list(k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS),
            "start_recipe": start_recipe_status,
        },
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
