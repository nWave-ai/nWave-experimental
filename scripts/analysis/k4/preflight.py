#!/usr/bin/env python3
"""Build direct Claude and direct installed-DES K4 arms.

Preflight proves the per-workspace DES launcher and its provider resolver under
the rendered arm environment before a finite Request reaches either arm.

    python3 -m scripts.analysis.k4.preflight --root <campaign-root> [--wheel <path>]

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
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from scripts.analysis import paired_campaign
from scripts.analysis.k4 import prepare_examiner_fixture as pef
from scripts.analysis.k4 import subject as k4_subject


#: Executables the fail-closed Claude delivery sandbox needs at RUN time: `claude`
#: is the arm itself, `socat` backs the sandbox's localhost network bridge (see
#: `seed_auth._sandbox_settings().sandbox.network`). A host missing either
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
#: named claude3 (`~/.claude-alt3`) on 2026-08-07; on 2026-08-20 that org
#: disabled Claude Code subscription access permanently ("claude3 e' andato e
#: non tornera'" -- Ale), and Ale named the PRIMARY profile (`~/.claude`) as
#: the payer going forward. Recorded in `arms.json` so a reader can see which
#: account the numbers were drawn against.
_DEFAULT_AUTH_PROFILE = Path.home() / ".claude"


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


#: `git clone <url> .` leaves HEAD attached to the SUT's default branch, which
#: is a shared, non-isolated checkout. Delivery tooling that refuses to work in
#: one abandons this directory and creates ANOTHER detached worktree elsewhere
#: for the actual delivery. (This comment used to attribute that behaviour to a
#: worktree-ownership rule in `nWave/skills/nw-auto/SKILL.md`; that skill
#: carries no such rule, and the false attribution was removed on
#: 2026-09-04.) `paired_campaign.py`
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


def _git_identity_steps(arm_name: str) -> list[list[str]]:
    """Repo-local git commit identity for this arm -- deterministic,
    neutral, never the operator's own identity.

    Run 10 (K4 matrix): the delivered feature staged cleanly and `git
    commit` failed `fatal: empty ident name` -- the arm env's isolated
    HOME/config carries no `user.name`/`user.email`. The crafter
    correctly refused to set git config itself, then correctly had its
    retry (`git -c user.name=<the OPERATOR's real name> ...`) blocked by
    Auto-root's own Bash allowlist -- exactly the IP/authorship leak this
    repo-LOCAL config forecloses at the source. `git config` with no
    `--global` writes ONLY this workspace's `.git/config`, never the
    operator's real identity anywhere.
    """
    return [
        ["git", "config", "user.name", f"K4 {arm_name} arm"],
        ["git", "config", "user.email", f"k4-{arm_name}@nwave.invalid"],
    ]


def nwave_setup_steps(venv: Path, auth_profile: Path) -> list[list[str]]:
    """The nWave arm's declared setup. `--yes` is load-bearing, see module doc."""
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
        *_git_identity_steps("nwave"),
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
        #
        # Run 14 (K4 matrix): a FIXED port meant any leaked prior server
        # (setsid survives every ancestor's teardown by design) collided
        # with EVERY later run forever. `pef.free_port()` binds a fresh
        # OS-assigned ephemeral port at setup time -- baked into this
        # exact argv, and the SAME value `prepare()` renders into
        # `pef.DOC_NAME` (`_render`) and the project CLAUDE.md fragment
        # reads back via `pef.existing_port` -- one source, never a
        # second hand-typed 18772.
        pef.fixture_setup_step(pef.free_port()),
        seed_step(auth_profile),
        # `--platform claude-code`, never the `auto` default. Measured 2026-08-07:
        # auto-detect installs into EVERY platform it finds, and CLAUDE_CONFIG_DIR
        # governs only the Claude one -- so an install the operator scoped to a
        # throwaway directory still rewrote their real Codex configuration and
        # left a backup in their real `~/.nwave/backups`. The arm runs `claude -p`,
        # so every other platform is out of scope for the measurement as well.
        # THE treatment, and the only reason this list differs from
        # `control_setup_steps` beyond the identity label and the fixture port.
        # Named once in `treatment_steps` so `refuse_undeclared_arm_footprint`
        # checks the SAME two steps this arm actually runs, never a second
        # hand-typed copy that could drift out from under the check.
        *treatment_steps(venv),
    ]


def control_setup_steps(auth_profile: Path) -> list[list[str]]:
    # Same seed, same source profile. Two arms on different accounts would carry
    # different rate-limit windows, and the arm that happened to start with more
    # headroom would be measured under a condition nobody declared -- exactly the
    # confound pairing exists to remove.
    #
    # Detached for the same reason as the nWave arm, even though the control
    # arm installs no nWave tooling at all: a treatment-only locator
    # convention would make the workspace construction asymmetric, and the
    # comparison arms must differ only in what their setup installs.
    return [
        ["git", "clone", _SUT, "."],
        _detach_step(),
        *_git_identity_steps("control"),
        pef.delivery_setup_step(),
        # Symmetric with the nWave arm's own step above, at its OWN fresh
        # ephemeral port (Run 14) so the two fixtures never collide on
        # one port if a campaign ever ran them side by side -- same
        # reasoning as `pef.free_port()` above, independently bound.
        # Kept identical on BOTH arms deliberately: the fixture facts are
        # a property of the SUBJECT, not of nWave being installed, so
        # the comparison arms must still differ only in what their setup
        # installs.
        pef.fixture_setup_step(pef.free_port()),
        seed_step(auth_profile),
    ]


# --- the footprint diff, computed instead of maintained by discipline --------

#: What each DECLARED per-arm variable is replaced by before the two setups are
#: compared. A mask is not an exemption: `_masked_arm_step` still checks that the
#: value it masks matches the template declared for THAT arm, so an operator's
#: real name in `user.name` is a finding, not a masked-away difference.
_ARM_MASK = "<per-arm>"


#: The one setup step that IS the treatment: nWave installed into the arm's own
#: `CLAUDE_CONFIG_DIR`. Named here beside `delivery_argv` because the two
#: together are the whole experiment -- same agent invocation on both arms, and
#: exactly one of them carries nWave.
#:
#: WHY THE TREATMENT IS NOT A `des` COMMAND. ADR-SSOT-002 Section 4b retires
#: `des dispatch` as an orchestrator: what ships is an LLM that invokes the
#: steps one at a time, reading each terminal's `NEXT`. So the thing to measure
#: is that LLM, and the way to measure it is to give both arms the same agent
#: invocation and let the installed skill (`nw-auto`, shipped by the install
#: step above, which teaches the step loop) be the only difference.
#:
#: A harness that timed a `des` command instead would measure either a composer
#: nobody runs, or one step against a whole control delivery. It would also
#: break the symmetry the pairing depends on: one timed invocation per arm, one
#: session, one cost total, both read out of the same agent envelope.
#:
#: This restores the shape both arms shared before `fd905f4cc` (2026-09-04)
#: split them; that commit's other halves -- the `--settings` sandbox move and
#: the treatment-footprint check -- are untouched.
TREATMENT_INSTALL_STEP = ("nwave-ai", "install", "--platform", "claude-code")


def treatment_steps(venv: Path) -> list[list[str]]:
    """Install nWave into the arm's own config dir. THE treatment, and only it.

    Built from `TREATMENT_INSTALL_STEP` rather than from a second hand-typed
    argv, so the constant that documents what the treatment IS and the step that
    performs it cannot drift apart.
    """
    binary, *arguments = TREATMENT_INSTALL_STEP
    return [[str(venv / "bin" / binary), *arguments]]


def _masked_arm_step(step: list[str], arm: str) -> tuple[list[str], list[str]]:
    """(step with the declared per-arm values masked, problems found masking it).

    Only two values in a setup step are allowed to differ per arm, and each is
    checked against the template that declares it before it is masked:

    * the repo-local git identity (`_git_identity_steps`) -- and the check that
      the value is `K4 {arm} arm` is load-bearing, not decorative: run 10 of the
      K4 matrix had a crafter retry `git -c user.name=<the OPERATOR's real name>`,
      which is an authorship leak. A blanket mask would have hidden exactly that.
    * the examiner fixture's ephemeral port (`pef.fixture_setup_step`), which is
      OS-assigned per arm on purpose (run 14: a fixed port collided forever).
    """
    problems: list[str] = []
    if step[:3] == ["git", "config", "user.name"]:
        expected = f"K4 {arm} arm"
        if step[3:] != [expected]:
            problems.append(
                f"git identity name is {step[3:]!r}, not the declared "
                f"[{expected!r}] -- a per-arm identity is declared, an "
                "arbitrary one is not"
            )
        return [*step[:3], _ARM_MASK], problems
    if step[:3] == ["git", "config", "user.email"]:
        expected = f"k4-{arm}@nwave.invalid"
        if step[3:] != [expected]:
            problems.append(
                f"git identity email is {step[3:]!r}, not the declared [{expected!r}]"
            )
        return [*step[:3], _ARM_MASK], problems
    # `pef.delivery_setup_step()` shares this exact prefix and differs only in
    # its trailing token (`--delivery-only`), so the DIGIT is what discriminates
    # the two, not the prefix. A fixture step whose trailing token is not a port
    # therefore falls through to the byte-equality comparison below unmasked --
    # which is the safe direction: it is compared, never excused.
    fixture_shape = pef.fixture_setup_step(0)
    if (
        len(step) == len(fixture_shape)
        and step[:-1] == fixture_shape[:-1]
        and step[-1].isdigit()
    ):
        return [*step[:-1], _ARM_MASK], problems
    return list(step), problems


def arm_footprint_problems(
    control: list[list[str]], nwave: list[list[str]], *, venv: Path
) -> list[str]:
    """Every way the two arms differ that is NOT one of the three declared points.

    The campaign's entire claim is single-variable: whatever the nWave arm does
    differently, it does because nWave is installed. Until this function existed
    that claim was held by DISCIPLINE -- the comment above `control_setup_steps`
    says the arms "must differ only in what their setup installs", and nothing
    computed it or failed when it stopped being true. A fourth difference could
    be added in either list and every gate in this repo would stay green while
    the measurement silently stopped being a measurement of nWave.

    The declared set has exactly three members: the git identity label, the
    examiner fixture port, and the two treatment steps. The rule is mechanical
    and total -- mask the first two, remove the third from the nWave arm, and
    what remains must be BYTE-EQUAL to the control arm, step for step, in order.
    Anything else is returned as a problem, in both directions: a missing
    treatment step is as much a footprint breach as an extra one, because a
    campaign whose treatment arm never installs nWave measures nothing and still
    reports a ratio.
    """
    problems: list[str] = []
    masked: dict[str, list[list[str]]] = {}
    for arm, steps in (("control", control), ("nwave", nwave)):
        rendered: list[list[str]] = []
        for index, step in enumerate(steps):
            step_masked, why = _masked_arm_step(list(step), arm)
            problems.extend(f"{arm} setup step {index}: {reason}" for reason in why)
            rendered.append(step_masked)
        masked[arm] = rendered

    treatment = treatment_steps(venv)
    for step in treatment:
        if step not in masked["nwave"]:
            problems.append(
                f"the nWave arm does not carry the declared treatment step {step} "
                "-- with no treatment installed the campaign compares two controls "
                "and still computes a ratio"
            )
        if step in masked["control"]:
            problems.append(
                f"the control arm carries the treatment step {step} -- the control "
                "is the arm nWave is absent from; this makes the campaign "
                "single-armed"
            )

    residue = [step for step in masked["nwave"] if step not in treatment]
    if residue != masked["control"]:
        problems.append(
            f"outside the declared three points the arms are not the same "
            f"footprint: the nWave arm has {len(residue)} non-treatment step(s), "
            f"the control arm {len(masked['control'])}"
        )
        for index in range(max(len(residue), len(masked["control"]))):
            left = residue[index] if index < len(residue) else None
            right = masked["control"][index] if index < len(masked["control"]) else None
            if left != right:
                problems.append(f"  step {index}: nwave {left!r} vs control {right!r}")
    return problems


def refuse_undeclared_arm_footprint(
    control: list[list[str]], nwave: list[list[str]], *, venv: Path
) -> int:
    """0 when the arms differ only where declared; 1 and a LOUD refusal otherwise."""
    problems = arm_footprint_problems(control, nwave, venv=venv)
    if not problems:
        return 0
    sys.stderr.write(
        "WHAT: the two campaign arms differ somewhere they were never declared to.\n"
        + "".join(f"      - {problem}\n" for problem in problems)
        + "WHY:  this campaign's only claim is single-variable -- whatever the nWave\n"
        "      arm does differently, it does because nWave is installed. An\n"
        "      undeclared fourth difference does not make the campaign fail; it\n"
        "      makes it succeed while measuring something nobody named, and every\n"
        "      ratio it computes afterwards is attributed to the wrong cause.\n"
        "HOW:  the declared set is three points and lives in ONE place --\n"
        "      `_git_identity_steps` (the identity label), `pef.fixture_setup_step`\n"
        "      (the ephemeral port) and `treatment_steps` (install + project\n"
        "      enable). Either put the new step in BOTH `nwave_setup_steps` and\n"
        "      `control_setup_steps`, or, if it genuinely belongs to the treatment,\n"
        "      add it to `treatment_steps` -- which is a decision about what this\n"
        "      campaign measures, so state it there in prose too.\n"
    )
    return 1


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
    (setup steps, launcher probe, delivery argv
    construction) must build its env through this single function, never a
    hand-rolled dict.

    Row 22 (K4 matrix), found again in an installed run: `probe_engagement`
    built its OWN inline `{**os.environ, "CLAUDE_CONFIG_DIR": ...}` for the
    nWave arm's SETUP steps (`nwave-ai install`) instead of reusing
    `_arm_env()` -- a second copy that pinned only CLAUDE_CONFIG_DIR, so
    `install_nwave.py`'s `record_install_metadata` fell through to the
    operator's real `Path.home()`. The three OTHER call sites
    (`probe_delivery_permissions`, `probe_installed_step_surface`,
    `probe_engagement`'s launcher probe) already rendered `_arm_env()`
    inline, correctly, each in their own copy of this exact expression --
    also consolidated here so there is exactly one rendering, not four.
    """
    rendered = {
        key: value.replace("{workspace}", str(workspace))
        for key, value in _arm_env().items()
    }
    return {**os.environ, **rendered}


def delivery_argv(model: str) -> list[str]:
    """The direct-control Claude argv, under the shared fail-closed profile.

    The shared isolated `.claude-k4/settings.json` is seeded before either arm
    runs. Both arms get this SAME argv -- same model, same settings, same
    accounting envelope; the only difference is `TREATMENT_INSTALL_STEP`, which
    puts nWave (and with it the step loop the model drives) on one arm only.
    """
    argv = [
        "claude",
        "-p",
        "--model",
        model,
        "--effort",
        "low",
        "--output-format",
        "json",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "default",
        "--setting-sources",
        "user",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-chrome",
    ]
    return argv


def _probe_workspace(root: Path) -> Path:
    return root / "probe-nwave"


_STEP_SURFACE_FAILURE_MARKERS = (
    "ModuleNotFoundError",
    "Traceback (most recent call last)",
)

#: The step the probe interrogates, and why this one. `des state` is the
#: read-only projection of ADR-SSOT-002 Section 4b's step surface: it writes no
#: byte, invokes no role and spawns no provider, so a real invocation of it
#: costs nothing and changes nothing in the workspace it is pointed at. Every
#: other surviving step either buys a provider turn or refuses on owned state
#: the probe workspace deliberately does not have.
_STEP_PROBE = "state"

#: What a step's terminal carries, every time, whatever its outcome
#: (`des.cli.step_terminal.render`). Present together they are the only
#: property the probe can decide on: that the `des` first on the arm's PATH is
#: a runtime speaking the STEP grammar. `DELIVERY-RUNTIME` cannot serve here --
#: it is written by `des dispatch` alone, the composer Section 4b retires, so
#: keying the probe to it would pin the arm to the surface that is going away.
_STEP_TERMINAL_ROWS = ("DELIVERY-OUTCOME: ", "NEXT: ", "HOW-TO-INVOKE: ")


def probe_installed_step_surface(workspace: Path, venv: Path) -> list[str]:
    """Run the real installed `des state` under the effective arm PATH.

    This is the causal reproduction of the class this preflight exists to
    catch, run BEFORE any delivery model call: the installed console script's
    `#!/usr/bin/env python3` shebang resolves against whatever `python3` sits
    first on PATH at execution time, and `_arm_env` deliberately puts the
    caller project's fixture venv there -- so a caller venv that lacks a
    package the invoked subcommand imports crashes before argument parsing,
    silently, on a call that costs nothing. Catching that here means a campaign
    never spends a model call on a delivery runtime whose own entry point
    cannot run.

    It interrogates a STEP and not the composer. ADR-SSOT-002 Section 4b
    retires `des dispatch` as an orchestrator, so a probe keyed to
    `des dispatch --help` measured a surface that is being removed: it would
    have kept passing against a runtime carrying the composer and no steps, and
    would start failing for the retirement rather than for a broken install.

    Three properties, decided on what the invocation actually produced and
    never on a name:

    1. the console script RAN -- exit 0, no Python failure marker in its
       output. That is the original shebang/PATH class, unchanged;
    2. the installed `des` CARRIES the step surface -- a runtime without
       `des state` answers argparse's `invalid choice`, non-zero, which is this
       probe saying the installed runtime is not the one the arm expects;
    3. the terminal speaks the step GRAMMAR -- the three rows every step
       renders. A command that exits 0 and prints something else is not the
       step surface, and admitting it would let the campaign measure an
       unrelated `des` that happens to accept the word `state`.

    `--repo-root` is the probe workspace itself: the projection reads the
    handover that is not there, reports `REQUEST: (none)` and names `des po` as
    the canonical next step. That is a Success on an empty root, so a non-zero
    exit here is always about the runtime and never about the state.

    WHAT THIS PROBE DOES NOT OWE. It does not check WHICH build answered, and it
    should not: the arm installs one exact wheel, built by `build_arm_runtime`
    from a commit `resolve_clean_commit_sha` refuses to resolve while the
    checkout is dirty, into a venv of its own. Identity is pinned by
    construction upstream of here, so a second identity check would be a gate
    over a state the preflight already makes unrepresentable (GDP-0, GDP-10).
    What construction cannot pin is whether that install RUNS under the arm's
    own PATH and answers as the step surface, and that is exactly what is
    measured above.
    """
    argv = [
        str(workspace / ".claude-k4" / "bin" / "des"),
        _STEP_PROBE,
        "--repo-root",
        str(workspace),
    ]
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
            f"`des {_STEP_PROBE}` exited {code} under the arm PATH: {output[-600:]}"
        )
    if any(marker in output for marker in _STEP_SURFACE_FAILURE_MARKERS):
        problems.append(
            f"`des {_STEP_PROBE}` output carries a Python failure marker: "
            f"{output[-600:]}"
        )
    absent = [row for row in _STEP_TERMINAL_ROWS if row not in output]
    if code == 0 and absent:
        problems.append(
            f"`des {_STEP_PROBE}` exited 0 but its terminal carries none of "
            f"{absent}: the installed `des` answered the word `{_STEP_PROBE}` "
            f"without speaking the step grammar, so it is not the runtime this "
            f"arm measures. Output: {output[-600:]}"
        )
    return problems


def des_fenced_lines(markdown_text: str) -> list[str]:
    """Return literal des commands from fenced code blocks."""
    in_fence = False
    lines: list[str] = []
    pending: str | None = None
    for raw_line in markdown_text.split("\n"):
        if raw_line.strip().startswith(chr(96) * 3):
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


def _authenticated_get_ready(
    base_url: str, api_key: str, *, env: dict[str, str], workspace: Path
) -> bool:
    """One SEPARATE `subprocess.run` authenticated GET, exit 0 iff it
    succeeded -- the SAME `pef.integration_probe_argv` a real examiner's
    documented HTTP journey uses, never a hand-typed second probe."""
    argv = pef.integration_probe_argv(base_url, api_key)
    try:
        done = subprocess.run(
            argv,
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def _wait_until_authenticated_get_ready(
    base_url: str, api_key: str, *, env: dict[str, str], workspace: Path, timeout: float
) -> bool:
    """Bounded poll, one SEPARATE `subprocess.run` per attempt (never a
    single long-lived probe) -- `True` once an authenticated GET
    succeeds, `False` if `timeout` elapses first."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _authenticated_get_ready(base_url, api_key, env=env, workspace=workspace):
            return True
        time.sleep(1)
    return False


#: Run 15 probe report (K4 matrix), $0.22 differential probe: `curl
#: http://127.0.0.1:<port>` inside Claude's OWN sandbox returns exit 7 at
#: the SAME instant the host shell gets 200 -- the sandboxed Bash's
#: network NAMESPACE does not share the host's loopback. Every prior
#: row-11 check in this file (`_authenticated_get_ready` and friends) runs
#: as a PLAIN, unsandboxed harness subprocess -- it proves the HARNESS can
#: reach the arm's server, not that the SANDBOXED EXAMINER can, which is
#: the actual boundary that matters (all 4 examiner INDETERMINATEs the
#: report traces were this exact gap). `_probe_sandbox_loopback_bridge`
#: below reproduces the namespace isolation directly via `bwrap
#: --unshare-net` (zero cost, no `claude`, no model) and proves the
#: REAL, current `pef.health_or_reset_block` text -- fixed to route
#: through `$HTTP_PROXY` -- reaches the server through a socat bridge
#: shaped exactly like the one Claude's own sandbox already provides for
#: its API egress. `bwrap` is not one of `_REQUIRED_SANDBOX_EXECUTABLES`
#: (only `claude`/`socat` are hard campaign prerequisites) -- this is a
#: bonus structural proof, so its own absence degrades to skipping this
#: ONE check, never to refusing the whole campaign.
_MINI_FORWARD_PROXY_SOURCE = (
    "import socket, sys, threading\n"
    "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
    "from urllib.parse import urlsplit\n"
    "class P(BaseHTTPRequestHandler):\n"
    "    def do_GET(self):\n"
    "        u = urlsplit(self.path)\n"
    "        try:\n"
    "            with socket.create_connection((u.hostname, u.port or 80), timeout=5) as s:\n"
    "                lines = [\n"
    "                    'GET ' + (u.path or '/') + ' HTTP/1.1',\n"
    "                    'Host: ' + u.hostname,\n"
    "                    'Connection: close',\n"
    "                ]\n"
    "                api_key = self.headers.get('X-Api-Key')\n"
    "                if api_key:\n"
    "                    lines.append('X-Api-Key: ' + api_key)\n"
    "                request = '\\r\\n'.join(lines) + '\\r\\n\\r\\n'\n"
    "                s.sendall(request.encode())\n"
    "                resp = b''\n"
    "                while True:\n"
    "                    c = s.recv(4096)\n"
    "                    if not c:\n"
    "                        break\n"
    "                    resp += c\n"
    "            he = resp.find(b'\\r\\n\\r\\n')\n"
    "            code = int(resp[:resp.find(b'\\r\\n')].decode().split()[1])\n"
    "            body = resp[he + 4:]\n"
    "            self.send_response(code)\n"
    "            self.send_header('Content-Length', str(len(body)))\n"
    "            self.end_headers()\n"
    "            self.wfile.write(body)\n"
    "        except OSError:\n"
    "            self.send_response(502)\n"
    "            self.end_headers()\n"
    "    def log_message(self, *a):\n"
    "        pass\n"
    "port = int(sys.argv[1])\n"
    "srv = ThreadingHTTPServer(('127.0.0.1', port), P)\n"
    "threading.Thread(target=srv.serve_forever, daemon=True).start()\n"
    "import time; time.sleep(120)\n"
)


#: `sun_path` in `struct sockaddr_un` is a fixed 108-BYTE field (`man 7
#: unix`), NUL included -- 107 usable bytes, a hard kernel limit no caller
#: can raise. `socat` refuses outright past it ("unix socket address N
#: characters long, max length is 108"). This is the ONE number
#: `_bridge_socket_path` below is bounded against; it is not a tuning knob.
_UNIX_SOCKET_PATH_LIMIT = 107


def _bridge_socket_path() -> Path:
    """A bridge-socket path whose LENGTH does not depend on the caller's
    workspace path.

    F-K4-ROW11-CANARY-RED-UNDER-XDIST (2026-08-23): the socket used to be
    `workspace / ".k4-sandbox-probe-bridge.sock"`. `workspace` is
    caller-supplied and unbounded, so its depth silently decided whether
    the bridge could exist at all. Under pytest-xdist the ONE extra
    `popen-gw0/` path element pushed the real path from 103 to 113 bytes
    -- past `_UNIX_SOCKET_PATH_LIMIT` -- and BOTH socats (outer and inner)
    refused to bind. The bridge was then simply absent, so the sandboxed
    health-check block could never reach the server, touched the reset
    marker, and reported "the supervisor consumed the marker, but the
    restart itself did not succeed": a LYING rejection blaming a perfectly
    healthy supervisor for a socket that was never created. Serial runs,
    10 bytes shorter, passed -- the defect was never load, concurrency or
    a too-short timeout.

    GDP-0 (make the wrong state unrepresentable): the socket now lives in
    its OWN short private directory, so no workspace depth can push it
    past the limit. Only a pathological `TMPDIR` could, and that is
    reported LOUD by the caller rather than degrading into a dead bridge
    again.
    """
    return Path(tempfile.mkdtemp(prefix="k4b-")) / "b.sock"


def probe_sandbox_loopback_bridge(
    workspace: Path, *, port: int, api_key: str
) -> list[str]:
    """Prove the examiner's REAL, rendered health-check block reaches the
    arm's server through a namespace-isolated bridge -- the sandboxed
    examiner's actual boundary, not the harness's own unsandboxed one
    every other row-11 check proves. See the module-level docstring
    above `_MINI_FORWARD_PROXY_SOURCE` for the full rationale.

    Skips silently (returns `[]`) when `bwrap` is not resolvable -- this
    is a bonus structural proof, never a hard campaign prerequisite the
    way `claude`/`socat` already are."""
    bwrap = shutil.which("bwrap")
    socat = shutil.which("socat")
    if bwrap is None or socat is None:
        return []

    proxy_script = workspace / ".k4-sandbox-probe-proxy.py"
    proxy_script.write_text(_MINI_FORWARD_PROXY_SOURCE, encoding="utf-8")
    proxy_port = pef.free_port()
    proxy_proc = subprocess.Popen(
        [sys.executable, str(proxy_script), str(proxy_port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    bridge_sock = _bridge_socket_path()
    bridge_dir = bridge_sock.parent
    if len(str(bridge_sock).encode()) > _UNIX_SOCKET_PATH_LIMIT:
        # GDP-6, degrade LOUD: the only way to land here is a TMPDIR long
        # enough to overflow `sun_path` on its own. Never fall through to
        # a socat that cannot bind -- that is exactly the silent, lying
        # "supervisor is down" this repair exists to remove.
        shutil.rmtree(bridge_dir, ignore_errors=True)
        return [
            f"the sandbox bridge socket path {str(bridge_sock)!r} is "
            f"{len(str(bridge_sock).encode())} bytes, past the "
            f"{_UNIX_SOCKET_PATH_LIMIT}-byte AF_UNIX sun_path limit -- "
            "point TMPDIR at a shorter directory and re-run; the bridge "
            "cannot be built here and this probe refuses to report a "
            "healthy server as unreachable"
        ]
    outer_bridge = subprocess.Popen(
        [
            socat,
            f"UNIX-LISTEN:{bridge_sock},fork,reuseaddr",
            f"TCP:localhost:{proxy_port}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.3)
        inner_port = pef.free_port()
        bridge_setup = (
            f"{socat} TCP-LISTEN:{inner_port},fork,reuseaddr "
            f"UNIX-CONNECT:{bridge_sock} > /dev/null 2>&1 &\n"
            'trap "kill %1 2>/dev/null" EXIT\n'
            "sleep 0.3\n"
            f"export HTTP_PROXY=http://127.0.0.1:{inner_port}\n"
        )
        block = pef.health_or_reset_block(port, api_key)
        result = subprocess.run(
            [
                bwrap,
                "--unshare-net",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/bin",
                "/bin",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind-try",
                "/lib64",
                "/lib64",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--bind",
                "/tmp",
                "/tmp",
                # The block's reset marker (`.k4-reset`) is written by
                # the sandboxed block and consumed by the supervisor, both
                # IN `workspace` -- so the sandbox must SEE it, and
                # `cwd=workspace` below must be where the block's relative
                # `touch` lands. Binding only `/tmp` silently worked while
                # every campaign root sat under `/tmp`; the moment the root
                # moves off `/tmp` (the durable-evidence correction), that
                # `touch .k4-reset` lands in the sandbox's own ephemeral
                # root where no supervisor can ever consume it, and this
                # probe reports a healthy supervisor as DOWN -- a lying
                # rejection, not a red. Binding it is also FAITHFUL: the
                # real examiner sandbox has its project workspace mounted.
                # Harmless when the workspace is already under `/tmp`
                # (bwrap applies binds in order, so this one simply lands
                # on top).
                "--bind",
                str(workspace),
                str(workspace),
                # The bridge socket lives OUTSIDE `workspace` now (see
                # `_bridge_socket_path`), so its own short directory must
                # be visible to the inner socat by the SAME path the outer
                # socat listens on.
                "--bind",
                str(bridge_dir),
                str(bridge_dir),
                "--",
                "bash",
                "-c",
                bridge_setup + block,
            ],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=45,
        )
    finally:
        outer_bridge.terminate()
        proxy_proc.terminate()
        outer_bridge.wait(timeout=10)
        proxy_proc.wait(timeout=10)
        bridge_sock.unlink(missing_ok=True)
        shutil.rmtree(bridge_dir, ignore_errors=True)
        proxy_script.unlink(missing_ok=True)

    if result.returncode != 0:
        return [
            "the examiner's documented health-check block, run through a "
            "network-namespace-isolated bridge reproducing Claude's own "
            "sandbox loopback isolation, did not reach the server -- "
            f"stdout: {result.stdout.strip()[-300:]!r} "
            f"stderr: {result.stderr.strip()[-300:]!r}"
        ]
    return []


def probe_examiner_start_recipe(workspace: Path) -> list[str]:
    """Prove the examiner's ACTUAL rendered environment -- the SAME
    `pef.DOC_NAME` file `fixture_setup_step` already wrote into this exact
    workspace -- runs under this harness's actual rendered env
    (`_rendered_arm_env`), deterministically, with NO model call, before a
    single (expensive, long) delivery/examiner turn is spent. One source,
    twice over: the API key AND the port both come from the rendered doc
    itself (`pef._existing_api_key` / `pef.existing_port`).

    Run 9 (K4 matrix): the examiner's server died between separate Bash
    tool calls and she burned 25 calls restarting it. Run 12: it also died
    the instant the STARTING Bash tool call itself returned (the tool
    kills the whole process group of a call when it ends). Both were
    survivable with enough process-group engineering (`setsid`,
    `start_new_session=True`, PID files) -- but Run 14 take 3 (PROBE-D-E.md)
    found a THIRD failure mode neither survives: the server, even
    `setsid`-started from Vera's own Bash tool call, was repeatedly reaped
    ~30-45s later by something in the agent sandbox itself, regardless of
    process-group tricks. GDP-0: no amount of defensive engineering
    INSIDE an agent tool call closes that gap, because the producer of
    the failure is the agent sandbox boundary itself -- the server must
    not be BORN there at all.

    This canary now proves the STABLE construction: `pef.start_supervisor`
    launches the keepalive supervisor from THIS process (a preflight
    subprocess, never an agent Bash call, exactly mirroring how
    `prepare()` itself starts it during real setup), waits for it to bring
    the server up, then -- the exact PROBE-D-E.md failure mode,
    reproduced directly -- kills the server's OWN PID and proves the
    supervisor notices and restarts it on its own, from OUTSIDE any agent
    sandbox, before a SEPARATE authenticated GET succeeds again. This
    function DOES mutate the workspace now (starts/restarts a real
    supervisor+server pair) -- superseding Run 11's "never mutates"
    commitment, which predates the supervisor's existence: proving the
    self-healing property AT ALL requires actually exercising it.
    """
    api_key = pef._existing_api_key(workspace)
    if api_key is None:
        return [
            f"no {pef.DOC_NAME} (or no API key line in it) exists in "
            f"{workspace} -- row 11's start recipe was never provisioned "
            "for this arm before this canary ran"
        ]
    port = pef.existing_port(workspace)
    if port is None:
        return [
            f"no {pef.DOC_NAME} (or no Base URL line in it) exists in "
            f"{workspace} -- its port cannot be recovered for this canary"
        ]

    env = _rendered_arm_env(workspace)
    base_url = f"http://127.0.0.1:{port}"
    problems: list[str] = []

    try:
        pef.start_supervisor(workspace, port=port, api_key=api_key)
    except OSError as exc:
        return [
            "the keepalive supervisor could not even be started under "
            f"the arm's rendered env: {type(exc).__name__}: {exc}"
        ]

    try:
        appearance = _supervisor_child_phase(workspace, active=True)
        if appearance is not None:
            problems.append(appearance)
            return problems
        if not _wait_until_authenticated_get_ready(
            base_url, api_key, env=env, workspace=workspace, timeout=40
        ):
            problems.append(
                "the supervisor did not bring the server to a reachable, "
                "authenticated state within 40s of being started"
            )
            return problems

        # Negative control, same discipline as row 11's own proof:
        # nothing listens on a dead port under the SAME arm env -- a
        # probe that passes anyway proves nothing about the recipe.
        dead_port = pef.free_port()
        if _authenticated_get_ready(
            f"http://127.0.0.1:{dead_port}", api_key, env=env, workspace=workspace
        ):
            problems.append(
                "the probe succeeded against a dead port under the "
                "arm's rendered env -- it does not discriminate"
            )

        settlement = _supervisor_child_phase(workspace, active=False)
        if settlement is not None:
            problems.append(settlement)
            return problems

        # Run 14 take 3 (PROBE-D-E.md), reproduced directly: kill the
        # server's OWN PID -- exactly what the agent sandbox does to a
        # Vera-started server, no Bash-tool-call boundary needed to
        # reproduce it -- and prove the supervisor (running OUTSIDE any
        # agent sandbox) notices and restarts it on its own.
        pid_file = workspace / pef.SERVER_PID_FILE_NAME
        try:
            old_pid = int(pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            problems.append(
                f"no {pef.SERVER_PID_FILE_NAME} exists after the "
                "supervisor's own first start"
            )
            return problems
        try:
            os.kill(old_pid, signal.SIGKILL)
        except OSError:
            pass

        if not _wait_until_authenticated_get_ready(
            base_url, api_key, env=env, workspace=workspace, timeout=30
        ):
            problems.append(
                "the supervisor did not restart the server within 30s of "
                f"its PID ({old_pid}) being killed directly -- the "
                "examiner's server must survive the agent sandbox "
                "reaping it, by construction, not merely by luck"
            )
            return problems

        # Run 15 probe report: every check above proves the HARNESS (an
        # unsandboxed subprocess) can reach the server -- the examiner's
        # actual boundary is the SANDBOXED Bash tool call, a structurally
        # different network namespace. Proves the rendered health-check
        # block reaches through a namespace-isolated bridge too, while
        # the server is still known-good from the restart proof above.
        problems.extend(
            probe_sandbox_loopback_bridge(workspace, port=port, api_key=api_key)
        )
    finally:
        pef.stop_supervisor(workspace)
    return problems


def _supervisor_child_phase(
    workspace: Path, *, active: bool, timeout: float = 10
) -> str | None:
    """Observe one supervisor child phase before the destructive probe step."""
    try:
        supervisor_pid = int(
            (workspace / pef.SUPERVISOR_PID_FILE_NAME)
            .read_text(encoding="utf-8")
            .strip()
        )
        if supervisor_pid <= 0:
            raise ValueError
    except (OSError, ValueError):
        return f"no valid {pef.SUPERVISOR_PID_FILE_NAME} exists before server reaping"
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.kill(supervisor_pid, 0)
        except OSError:
            return "the keepalive supervisor died before its restart block settled"
        try:
            child = subprocess.run(
                ["pgrep", "-P", str(supervisor_pid)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=1,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"could not observe the keepalive supervisor child: {type(exc).__name__}: {exc}"
        if child.returncode == 1 and not active:
            return None
        if child.returncode == 0 and active:
            return None
        if child.returncode not in (0, 1):
            return (
                "the keepalive supervisor child observation is indeterminate: "
                f"{(child.stderr or child.stdout).strip()[-300:]}"
            )
        if time.monotonic() >= deadline:
            return (
                "the keepalive supervisor child never appeared before authenticated "
                "reachability"
                if active
                else "the keepalive supervisor restart block remained active for 10s "
                "before server reaping"
            )
        time.sleep(0.1)


def probe_git_identity(workspace: Path, env: dict[str, str]) -> list[str]:
    """Prove a commit is possible in this arm workspace, under the arm's
    OWN rendered env, before any model call.

    Run 10 (K4 matrix): a crafter staged the whole delivered feature
    cleanly and `git commit` failed `fatal: empty ident name` -- the arm
    env's isolated HOME/config carries no `user.name`/`user.email` for
    git to fall back on. `git var GIT_COMMITTER_IDENT` is the SAME
    identity check `git commit` itself performs before touching the
    object store -- read-only, no branch or commit created here, so this
    canary can never itself mutate the workspace it is proving.
    """
    try:
        done = subprocess.run(
            ["git", "var", "GIT_COMMITTER_IDENT"],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [
            "git var GIT_COMMITTER_IDENT could not even run under the "
            f"arm's rendered env: {type(exc).__name__}: {exc}"
        ]
    if done.returncode != 0:
        return [
            "the arm workspace has no usable git commit identity under "
            "the arm's rendered env: "
            f"{(done.stderr or done.stdout).strip()[-400:]}"
        ]
    return []


def probe_engagement(
    root: Path, venv: Path, auth_profile: Path
) -> tuple[str, list[str]]:
    """Run the nWave arm's setup for real; return (verdict, detail).

    Four verdicts, never merged, because they need different HOWs and a rejection
    that names the wrong cause is worse than a bare traceback:

    * `broke`            -- a setup step exited non-zero. Loud already; read
      the error.
    * `absent`           -- every step succeeded and nWave still is not there;
    * `broken-steps`     -- nWave arrived, but the real installed step surface
      (`des state`) failed under the arm's effective PATH -- checked before any
      delivery model call.
    * `present`          -- setup, the installed step surface and the launcher
      all passed; the arm is ready to be measured.

    The first version returned one list and printed the `absent` explanation for
    both, so a step that exited 1 was reported as "every step exited 0" and the
    remedy offered was `--yes` for a missing-catalog failure. Caught on its own
    first real run, 2026-08-07.
    """
    workspace = _probe_workspace(root)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    env = _rendered_arm_env(workspace)

    for step in nwave_setup_steps(venv, auth_profile):
        code, tail = _run(step, cwd=workspace, env=env)
        if code != 0:
            return "broke", [
                f"`{' '.join(step[:3])}` exited {code}",
                tail.strip(),
            ]

    step_surface_problems = probe_installed_step_surface(workspace, venv)
    if step_surface_problems:
        return "broken-steps", step_surface_problems
    try:
        launcher = subprocess.run(
            [
                str(venv / "bin" / "python"),
                "-c",
                "from des.adapters.driven.task_invocation.claude_code_task_adapter "
                "import resolve_launcher; raise SystemExit(0 if resolve_launcher() else 1)",
            ],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "absent", [f"installed resolve_launcher could not run: {exc}"]
    if launcher.returncode != 0:
        return "absent", [
            "installed resolve_launcher found no usable Claude executable under the "
            f"rendered arm env: {(launcher.stderr or launcher.stdout)[-300:]}"
        ]
    return "present", []


def cleanup_probe_workspace(root: Path, verdict: str, detail: list[str]) -> bool:
    """Remove the probe workspace after a PASS engagement only; return whether removed.

    PASS is decided on the PROPERTY `main` itself acts on -- `detail` empty --
    never on the `verdict` DESIGNATION (GDP-8). `main`'s own control flow
    only special-cases `verdict in {"broke", "broken-steps"}`
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
    parser.add_argument("--model", default="claude-opus-5")
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
        "--wall-clock-minutes",
        type=int,
        default=60,
        help=(
            "the campaign's own declared wall-clock ceiling (stable-design "
            "report 2026-08-19 Sec.1.3: 'root-level wall-clock budget as a "
            "proactive loop check') -- declared HERE, once, by the harness "
            "that owns the delivery route, never re-derived downstream. "
            "Rendered into both arms.json's own spec and each arm's project "
            "fragment (render_project_fragment) alongside the campaign's "
            "start epoch, so the root reads its OWN declared ceiling and "
            "elapsed time directly from its own project context and can "
            "stop before an external kill, not merely be killed by one"
        ),
    )
    args = parser.parse_args(argv)

    # Run 14 debrief stable-design report Sec.1.3: the campaign's OWN start
    # moment, recorded ONCE here, propagated to every arm's setup subprocess
    # through the SAME `_rendered_arm_env`/`os.environ` channel every OTHER
    # arm-specific fact already travels through -- never a second, parallel
    # plumbing mechanism.
    campaign_start_epoch = int(time.time())
    os.environ["K4_WALL_CLOCK_CEILING_MINUTES"] = str(args.wall_clock_minutes)
    os.environ["K4_CAMPAIGN_START_EPOCH"] = str(campaign_start_epoch)
    # Defect `il-supervisore-non-riavvia-...-si-autotermina-da-orfano`
    # (2026-08-24 RCA): `pef.fixture_setup_step`'s argv runs `prepare()` in
    # a SHORT-LIVED setup-step subprocess (part of `nwave_setup_steps`/
    # `control_setup_steps`), which starts a keepalive supervisor and then
    # exits within a second or two -- its own job done. Left to
    # `start_supervisor`'s `os.getpid()` default, that supervisor's
    # OWNER_PID is bound to this ALREADY-DYING subprocess, not to THIS
    # (long-lived, campaign-length) process, so it self-terminates as an
    # orphan a couple of poll cycles later, by construction. Propagated
    # through the SAME env channel as the two lines above -- one source,
    # never a second plumbing mechanism -- and read back by `prepare_
    # examiner_fixture.main()`.
    os.environ["K4_SUPERVISOR_OWNER_PID"] = str(os.getpid())

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

    # Built ONCE, here, and carried to `arms.json` unchanged at the bottom of
    # this function. The check below therefore decides on the very object the
    # campaign will run, not on a second call that could differ -- and it runs
    # HERE, before `probe_engagement` spends minutes standing an arm up, because
    # a campaign whose arms differ in an undeclared way is not worth probing.
    control_steps = control_setup_steps(args.auth_profile)
    nwave_steps = nwave_setup_steps(venv, args.auth_profile)
    if refuse_undeclared_arm_footprint(control_steps, nwave_steps, venv=venv):
        return 1
    print(
        "arm diff    : proven -- identity label, fixture port, "
        f"{len(treatment_steps(venv))} treatment step(s), nothing else"
    )

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
    if verdict == "broken-steps":
        sys.stderr.write(
            "WHAT: the real installed step surface (`des state`) failed under the\n"
            "      arm's effective PATH.\n"
            + "".join(f"      - {line}\n" for line in detail)
            + "WHY:  two causes reach this one verdict and the detail above says\n"
            "      which. Either the installed console script's\n"
            "      `#!/usr/bin/env python3` shebang resolved against the caller\n"
            "      project's fixture venv, which the arm's PATH deliberately puts\n"
            "      first, and a missing package crashed it before argument parsing;\n"
            "      or the installed `des` does not carry the step surface\n"
            "      ADR-SSOT-002 Section 4b makes the delivery shape, in which case it\n"
            "      is not the runtime this arm measures. A model call spent now is\n"
            "      wasted either way.\n"
            f"HOW:  inspect {args.root / 'probe-nwave'} and run, by hand and under the\n"
            "      same rendered env, `<probe>/.claude-k4/bin/des state --repo-root\n"
            "      <probe>`. Fix the installed entry point, or install a runtime that\n"
            "      carries the steps, before rerunning this preflight.\n"
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
    print("engagement  : setup, installed step surface and launcher proven")

    # Row 11 (K4 matrix), Run 8/9 evidence: the examiner's server-start +
    # HTTP-probe MECHANISM proven under this arm's rendered env, still
    # with NO model call, before arms.json is written.
    #
    # Run 11: upgraded from a campaign INDETERMINATE to a hard refusal.
    # `probe_examiner_start_recipe` authenticates against the REAL
    # running Django server with the REAL seeded key -- a failure here
    # means the documented key CANNOT authenticate ANY request, the
    # exact structural defect that burned 3 examiner dispatches + 3
    # troubleshooter diagnostics (~25 minutes) discovering the same
    # broken fixture three separate ways before finalize refused to
    # commit anyway. Softly proceeding into a campaign whose EXAMINE
    # stage is guaranteed to fail this same way is strictly worse than
    # refusing before a single (expensive) delivery/examiner turn is
    # spent -- unlike a merely-unprovisioned recipe (row 11's original
    # softer case), a real auth failure here is not "not yet ready", it
    # is "structurally cannot work".
    # Run 14: `probe_examiner_start_recipe` now recovers its own port from
    # the workspace's rendered doc internally (`pef.existing_port`) -- no
    # caller-supplied port, since `nwave_setup_steps` binds a fresh
    # ephemeral one per call and the doc is the one place that recorded
    # which.
    start_recipe_problems = probe_examiner_start_recipe(_probe_workspace(args.root))
    if start_recipe_problems:
        sys.stderr.write(
            "WHAT: the examiner's start recipe did not authenticate "
            "against the real running server under the arm's rendered "
            "env.\n"
            + "".join(f"      - {p}\n" for p in start_recipe_problems)
            + "WHY:  a documented key that cannot authenticate ANY "
            "request is not a readiness gap the examiner can work "
            "around -- every EXAMINE-stage dispatch in a real campaign "
            "would fail the same way, for the same reason, discovered "
            "independently and expensively each time (Run 11: 3 "
            "examiner dispatches + 3 troubleshooter diagnostics, ~25 "
            "minutes, before finalize refused to commit anyway).\n"
            f"HOW:  inspect {_probe_workspace(args.root)}, reproduce "
            "`pef.start_and_wait_block`'s own printed block by hand, "
            "and the seed step's own self-verification "
            "(`project.compare_api_key(raw)` immediately after "
            "`refresh_from_db()`) before rerunning this preflight.\n"
        )
        return 1
    start_recipe_status: dict[str, object] = {"status": "proven"}
    print("start recipe: proven under the arm's rendered env")

    # Row 10 (K4 matrix): a crafter commit died `fatal: empty ident name`
    # -- no model call spent (`probe_git_identity`, `git var
    # GIT_COMMITTER_IDENT`), and a hard refusal, not an INDETERMINATE:
    # unlike the examiner's own recipe, EVERY delivery needs a working
    # commit identity, so a campaign with none would measure nothing.
    identity_problems = probe_git_identity(
        _probe_workspace(args.root), _rendered_arm_env(_probe_workspace(args.root))
    )
    if identity_problems:
        sys.stderr.write(
            "WHAT: the arm workspace has no usable git commit identity "
            "under the arm's rendered env.\n"
            + "".join(f"      - {p}\n" for p in identity_problems)
            + "WHY:  the arm env's isolated HOME/config carries no "
            "user.name/user.email, and `git commit` fails `fatal: empty "
            "ident name` mid-delivery -- after the crafter has already "
            "done the real work, and the crafter can never fix this "
            "itself without either a forbidden global write or injecting "
            "the operator's own real identity (an IP/authorship leak).\n"
            "HOW:  fix `_git_identity_steps`/`nwave_setup_steps`/"
            "`control_setup_steps` so the arm workspace carries a "
            "repo-local `user.name`/`user.email` before this preflight "
            "runs, then rerun it before writing arms.json.\n"
        )
        return 1
    print("git identity: proven under the arm's rendered env")

    if cleanup_probe_workspace(args.root, verdict, detail):
        print(f"probe clean : removed {_probe_workspace(args.root)}")

    arm_env = _arm_env()
    # ONE argv, both arms. The arms differ in their SETUP -- `treatment_steps`
    # installs nWave -- and in nothing else, which is what makes a pair a pair.
    control_delivery = delivery_argv(args.model)
    nwave_delivery = delivery_argv(args.model)
    # Both arms share one finite Request, model, effort, environment and
    # subscription profile. The treatment's only different launcher is direct
    # installed DES; the control is direct external Claude.
    spec = {
        "task": args.task_file.read_text(encoding="utf-8").strip(),
        # Stable-design report 2026-08-19 Sec.1.3: the campaign's ONE
        # declared wall-clock ceiling and start epoch, the SAME two values
        # `os.environ["K4_WALL_CLOCK_CEILING_MINUTES"/"K4_CAMPAIGN_START_
        # EPOCH"]` already carried into every arm's setup subprocess and
        # `render_project_fragment`'s own fragment text -- one source,
        # three surfaces, never three independently re-derived numbers.
        "budget": {
            "wall_clock_minutes": args.wall_clock_minutes,
            "start_epoch": campaign_start_epoch,
        },
        # Stable-design report 2026-08-19 phase3 §5 item 4 /
        # `AutoRouteStable_HonorSystemBudget.tla` (`NoUnenforcedExternalKill`
        # VIOLATED): `budget` above is advisory prose the ROOT reads at its
        # own discretion, never enforced by construction. The one REAL
        # external cap is `paired_campaign._run_delivery`'s subprocess
        # `timeout` (SIGTERM then SIGKILL on the whole process group,
        # regardless of whether the bullet was ever read) -- named here
        # from `paired_campaign.DELIVERY_TIMEOUT_S`, the ONE source, so a
        # reader of arms.json can see which of the two numbers actually
        # kills the process (GDP-8: decide on the property, not the
        # designation).
        "ceiling": {
            "seconds": paired_campaign.DELIVERY_TIMEOUT_S,
            "enforced_by": "harness-timeout",
        },
        # Row 11 (K4 matrix): the sandbox facts every arm's project
        # fragment states (`pef.render_project_fragment`) and the row-11
        # start-recipe canary's own verdict, so a reader of arms.json sees
        # WHAT was proven about the sandbox, not just that a campaign ran.
        "sandbox": {
            "network_allowed_domains": list(k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS),
            "start_recipe": start_recipe_status,
            # Row 10: only ever reaches this write as "proven" -- a
            # failure returns 1 above, before arms.json exists at all.
            "git_identity": "proven",
        },
        "artifact": {
            "kind": "wheel",
            "path": str(wheel),
            "sha256": _sha256(wheel),
            "commit_sha": commit_sha,
        },
        "arms": {
            "control": {
                "setup": control_steps,
                "argv": control_delivery,
                "env": arm_env,
            },
            "nwave": {
                "setup": nwave_steps,
                "argv": nwave_delivery,
                "env": arm_env,
            },
        },
    }
    out = args.root / "arms.json"
    out.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    print(f"arms spec   : {out}")
    print(
        "\nBoth arms carry the SAME Request, model, effort, environment, auth AND"
        "\ndelivery argv; the treatment alone carries nWave installed, so the agent"
        "\nthere reads the skill that teaches the DES step loop. Each is"
        "\nseeded with the SAME subscription login. An earlier note here claimed an"
        "\nempty config dir was 'still authenticated' and needed no credential: it"
        "\nwas authenticated by API CREDIT, which is a different payer. That claim"
        "\nis withdrawn - a probe that SUCCEEDS tells you the operation worked,"
        "\nnever which mechanism made it work."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
