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
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


#: Injected by `nwave-ai project enable`. An HTML comment, so it is invisible in
#: rendered markdown and unambiguous to look for.
_SECTION_MARKER = "BEGIN nWave-beta-section"

_SUT = "https://github.com/healthchecks/healthchecks.git"


def _run(
    argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after 1800s"
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


def build_arm_runtime(root: Path, checkout: Path) -> Path:
    """Package the trunk the way release packages it, into one shared venv.

    Once, deliberately: every pair then installs identical bits, which removes a
    difference no one would have thought to record.
    """
    source = root / "arm-src"
    if not source.exists():
        shutil.copytree(checkout, source, ignore=_NEVER_COPY, symlinks=True)
    venv = root / "nwave-venv"
    if not venv.exists():
        code, tail = _run([sys.executable, "-m", "venv", str(venv)], cwd=root)
        if code != 0:
            raise SystemExit(f"WHAT: could not create the arm venv.\n{tail}")
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
    code, tail = _run(
        [str(venv / "bin" / "pip"), "install", "-q", str(wheels[0])], cwd=root
    )
    if code != 0:
        raise SystemExit(f"WHAT: could not install {wheels[0].name}.\n{tail}")
    return venv


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
        seed_step(auth_profile),
    ]


def _probe_workspace(root: Path) -> Path:
    return root / "probe-nwave"


def probe_engagement(
    root: Path, venv: Path, auth_profile: Path
) -> tuple[str, list[str]]:
    """Run the nWave arm's setup for real; return (verdict, detail).

    Two verdicts, never merged, because they need different HOWs and a rejection
    that names the wrong cause is worse than a bare traceback:

    * `broke`   -- a setup step exited non-zero. Loud already; read the error.
    * `absent`  -- every step succeeded and nWave still is not there. This is the
      silent one, and the only reason this function exists.

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
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir)}

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
    return "absent", missing


def cleanup_probe_workspace(root: Path, verdict: str, detail: list[str]) -> bool:
    """Remove the probe workspace after a PASS verdict only; return whether removed.

    PASS is exactly `verdict != "broke"` and `detail` empty -- the same
    condition `main` already checks before printing the engagement success
    line. `broke` and `absent`-with-detail both leave the probe in place: the
    failure messages above point a reader at `<root>/probe-nwave` for the HOW,
    and a probe deleted out from under that pointer would make the HOW a lie.
    """
    if verdict == "broke" or detail:
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
    args = parser.parse_args(argv)

    args.root.mkdir(parents=True, exist_ok=True)
    venv = build_arm_runtime(args.root, args.checkout)
    print(f"arm runtime : {venv}")

    verdict, detail = probe_engagement(args.root, venv, args.auth_profile)
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

    if cleanup_probe_workspace(args.root, verdict, detail):
        print(f"probe clean : removed {_probe_workspace(args.root)}")

    delivery = [
        "claude",
        "-p",
        "{task}",
        "--model",
        args.model,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
    ]
    # IDENTICAL argv in both arms. The only declared difference is the setup,
    # which makes the campaign single-variable: anything the treatment arm does
    # differently, it does because nWave is installed, not because its prompt
    # was worded to invite it.
    spec = {
        "task": args.task_file.read_text(encoding="utf-8").strip(),
        "arms": {
            "control": {
                "setup": control_setup_steps(args.auth_profile),
                "argv": delivery,
                "env": {"CLAUDE_CONFIG_DIR": "{workspace}/.claude-k4"},
            },
            "nwave": {
                "setup": nwave_setup_steps(venv, args.auth_profile),
                "argv": delivery,
                "env": {"CLAUDE_CONFIG_DIR": "{workspace}/.claude-k4"},
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
