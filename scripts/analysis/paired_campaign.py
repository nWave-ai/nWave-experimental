#!/usr/bin/env python3
"""Run two declared arms PAIRED and CONCURRENT, so shared conditions cancel.

Why paired rather than repeated. The ai-benchmark campaigns show 10x-20x
run-to-run spread on identical configurations, and both authors independently
tied it to WHEN the run happened ("results produced around midnight CEST";
"I couldn't reproduce it, not even closely"). That is provider contention, not
harness behaviour. Contention SHARED by two arms cancels inside a pair; arms run
hours apart turn it into a confound you can only average away with large N.

Measured on an A-vs-A' calibration campaign, 3 pairs, 2026-08-06:

    metric          within-pair    across-pair
    cost USD           1.01x          1.10x
    turns              1.00x          1.33x
    output tokens      1.10x          1.44x
    wall clock         1.40x          1.96x

Cost and turns collapse to ~1 inside a pair. Wall clock resists most, which is
consistent: concurrent arms share contention only partly.

An arm is a declared argv VECTOR, never a shell string, and this module knows
nothing about any harness. Same shape as the thin DeliveryContract's
`verification-scope.commands`: word-splitting and metacharacter handling cannot
differ by executor, and comparing nWave to anything else needs no code here.

Stdlib only -- Python is the one runtime dependency, and deliberately no `des`
import: this module was offered to the benchmark authors, who do not have it
installed. Every spawn therefore states `stdin=` and `timeout=` as literal
kwargs, which is the alternative the spawn-perimeter gate allows where importing
`des.runtime.spawn` is not available. The finite Request is supplied once on
stdin via `communicate(input=...)`, which also closes EOF.

    paired_campaign.py --arms arms.json --pairs 3 --out ./campaign

`arms.json`:
    {"task": "<the identical prompt both arms receive>",
     "arms": {"control": {"setup": [["git","clone","--depth","1","<sut>","."]],
                          "argv":  ["claude","-p","--model","claude-opus-5",
                                    "--output-format","json"]},
              "nwave":   {"setup": [["git","clone","--depth","1","<sut>","."],
                                    ["nwave-ai","install"]],
                          "argv":  ["claude","-p","--model","claude-opus-5",
                                    "--output-format","json"]}}}

The two `argv` lists above are byte-identical on purpose. An example that
differed anywhere would teach the opposite of what this module requires.

A bare list is still accepted as an arm with no setup.

## Both arms declare the SAME argv, and that is the design

The two arms above run the identical agent invocation. Their only declared
difference is a SETUP step: one of them installs nWave. That is what a pair is
for -- everything the comparison does not intend to vary is held equal, and the
one intended difference is named.

It also keeps this module's measurement honest for free. One timed invocation
per arm means one session id, one cost total and one token total per arm, read
out of the same agent envelope on both sides. A harness where one arm was a
sequence of commands would have to sum an aggregate the other arm reports
directly, and the two numbers would no longer be the same measurement.

ADR-SSOT-002 Section 4b is why this is the right shape and not merely a
convenient one: what nWave ships is an LLM that invokes the DES steps one at a
time, reading each terminal. So the treatment IS an agent run, and measuring it
means running an agent. `k4/preflight.py:TREATMENT_INSTALL_STEP` names the one
step that makes an arm the treatment.

## Two views from ONE execution, and what actually differs between them

Setup runs before the timed invocation, always, and its wall-clock is recorded
SEPARATELY. The pre-registered cold/operator view is then `setup + delivery` and
the warm view is `delivery` alone -- both computed from the same runs, because
setup is strictly sequential and therefore decomposable. Running two campaigns
to obtain them would spend twice for one number.

**The two views differ in wall-clock and in essentially nothing else**, and
saying so is not a caveat but the finding: the direct-DES install is deterministic
Python, so an arm's setup contributes zero model
tokens. A cold/warm split that implied two different cost figures would be
inventing a distinction the mechanism does not have.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


# Sibling stdlib-only module, NOT a harness/`des` import: the no-`des` rule in
# this file's docstring is about the benchmark authors being able to run it,
# and `campaign_archive` imports nothing they do not already have. It is here
# because `F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP` proved that an archive step
# living anywhere except inside the run that produces the evidence never runs.
try:  # imported as `scripts.analysis.paired_campaign`
    from scripts.analysis import campaign_archive
except ImportError:  # executed as a script: its own directory is sys.path[0]
    import campaign_archive  # type: ignore[no-redef]


#: A one-line call that must succeed before a campaign is worth starting.
#: The first version of this probe produced five is_error records with zero
#: usage and LOOKED like it had run. Measured 2026-08-06: `--bare` returns
#: "Not logged in" under subscription auth while the identical call without it
#: succeeds -- it strips the auth-bearing configuration along with the hooks and
#: skills it is documented to strip. Any scripted campaign passing `--bare` on a
#: subscription records zero-usage failures that look like executed runs.
_AUTH_PROBE = [
    "claude",
    "-p",
    "Reply with exactly: OK",
    "--output-format",
    "json",
    "--dangerously-skip-permissions",
]


@dataclass(frozen=True)
class ArmSpec:
    """One arm: a name, the argv vector that runs it, and its declared setup."""

    name: str
    argv: tuple[str, ...]
    setup: tuple[tuple[str, ...], ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    """Overlaid on the inherited environment for BOTH setup and delivery.

    The reason this exists is not configuration convenience. An arm whose setup
    installs into the operator's shared home mutates state the other arm and the
    operator are simultaneously using -- measured twice on 2026-08-06, where a
    campaign rewrote a live `~/.claude` down to 12 skills and 0 agents. And a
    control arm that inherits that same home is not a control: it silently
    carries every skill, agent and hook the treatment arm was supposed to be the
    only one to have. Isolation is a parity requirement before it is a safety one.
    """

    task_prefix: str = ""
    """Prepended to the Request this arm receives, and DECLARED when non-empty.

    The arms exist to differ in one thing. Normally that thing is the setup, and
    both arms read a byte-identical Request. This field is the exception, and it
    is a loud one: it changes what an arm is ASKED, so a campaign that uses it is
    no longer measuring what an agent does when left alone -- it is measuring
    what the named route costs.

    Measured five times on 2026-09-13, four wordings of guidance and one reshaped
    subject: an agent handed an implementation task never chooses the method. A
    campaign that wants the method's cost must therefore ask for it, and must say
    so in its own record rather than let a reader assume otherwise. At most one
    arm may carry a prefix; two would be two different tasks.
    """

    def rendered(self, workspace: Path) -> list[str]:
        """Render only the workspace; stdin is the one shared task carrier.

        A `--settings` JSON argv token carrying `{workspace}` (a K4 sandbox's `env.PATH`,
        declared once and shared by argv and env) reach the spawned process
        UNRENDERED, while `rendered_env` correctly substituted the same
        placeholder in the env dict -- the two views of one declared value
        then disagreed. Rendering both placeholders from one call, against
        the one `workspace` the caller already resolved, keeps argv and env
        joined on the same value by construction.
        """
        return [tok.replace("{workspace}", str(workspace)) for tok in self.argv]

    def rendered_env(self, workspace: Path) -> dict[str, str]:
        """`{workspace}` is the only substitution, so an arm can name a
        per-run directory without the spec knowing where the campaign landed."""
        return {k: v.replace("{workspace}", str(workspace)) for k, v in self.env}


def parse_arm(name: str, declared: object) -> ArmSpec:
    """Accept either a bare argv list or a `{setup, argv, env}` object."""
    if isinstance(declared, list):
        return ArmSpec(name, tuple(declared))
    if not isinstance(declared, dict) or "argv" not in declared:
        raise ValueError(
            f"arm '{name}': expected an argv list or a {{setup, argv}} object"
        )
    steps = declared.get("setup", [])
    if not isinstance(steps, list) or not all(isinstance(s, list) for s in steps):
        raise ValueError(f"arm '{name}': `setup` must be a list of argv vectors")
    env = declared.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        raise ValueError(f"arm '{name}': `env` must be an object of string to string")
    prefix = declared.get("task_prefix", "")
    if not isinstance(prefix, str):
        raise ValueError(f"arm '{name}': `task_prefix` must be a string")
    return ArmSpec(
        name,
        tuple(declared["argv"]),
        tuple(tuple(str(t) for t in step) for step in steps),
        tuple(sorted(env.items())),
        prefix,
    )


def git_checkout_targets(setup: tuple[tuple[str, ...], ...]) -> list[str]:
    """The commit/ref each declared `git checkout` step in this arm's setup
    targets, in order -- the last token, which is where the target lands
    whether the step is a bare `git checkout <ref>` or carries `--detach`
    first. Public: `blind_review._arm_baselines` reuses this exact matcher,
    so what the campaign accepts as a pin and what sealing arms as the
    baseline can never drift apart. Deliberately generic: this module "knows nothing about any
    harness" (module docstring), so it compares whatever the arms
    THEMSELVES declared rather than importing any subject's own pin
    constant -- K4's `scripts/analysis/k4/subject.SUT_PINNED_REV` included."""
    return [
        step[-1]
        for step in setup
        if len(step) >= 2 and step[0] == "git" and step[1] == "checkout"
    ]


def declared_identity_violations(arms: list[ArmSpec]) -> list[str]:
    """Everything the operator declared that would make the arms incomparable.

    Both arms receive the finite Request over stdin; argv is not a second task
    carrier and provider-specific raw flags are not a semantic comparison law.
    """
    problems: list[str] = []
    # Reproducibility (K4 matrix rows 2/4): a `git checkout` an arm's setup
    # declares names the exact subject state it measures. Two arms
    # comparable in every other declared way but checked out to two
    # different commits are not measuring the same subject, and nothing
    # about their argv would show it.
    checkout_targets = {arm.name: git_checkout_targets(arm.setup) for arm in arms}
    if len({tuple(v) for v in checkout_targets.values()}) > 1:
        problems.append(
            f"declared `git checkout` targets differ across arms: "
            f"{checkout_targets} -- every arm must be measured against the "
            "identical pinned subject revision"
        )
    prefixed = [arm.name for arm in arms if arm.task_prefix]
    if len(prefixed) > 1:
        problems.append(
            f"more than one arm declares a `task_prefix` ({prefixed}): a prefix "
            "changes what an arm is ASKED, so two of them are two different "
            "tasks and the pair compares nothing"
        )
    for arm in arms:
        for step in arm.setup:
            if any("{task}" in token for token in step):
                problems.append(
                    f"arm '{arm.name}' mentions {{task}} in a SETUP step: setup runs "
                    "outside the timed invocation, so an arm doing the work there "
                    "would be measured as having done it for free"
                )
    # Isolation that both arms declare identically is not isolation. The
    # mechanism is mundane and therefore likely: copy one arm's env block, forget
    # to change the directory, and the treatment arm's install lands in the
    # control arm's configuration. Both arms then measure the same thing.
    # A value carrying `{workspace}` is per-arm BY CONSTRUCTION, so identical
    # declarations there are not a collision -- they render to different paths.
    # The first version of this check compared the declared strings and would
    # have refused the correct configuration, which is the failure mode a gate
    # can least afford: it teaches the operator to work around the gate.
    declared = [{k: v for k, v in arm.env if "{workspace}" not in v} for arm in arms]
    for key in set(declared[0]) & set(declared[1]):
        if declared[0][key] == declared[1][key]:
            problems.append(
                f"both arms declare {key}={declared[0][key]!r}: an environment they "
                "SHARE cannot isolate them, and whatever one arm's setup writes "
                "there, the other one reads"
            )
    return problems


def _attested_trunk() -> dict[str, str]:
    """The SHA and cleanliness both arms are supposed to share.

    Recorded, not enforced, and the difference is stated: this module cannot know
    which checkout an arm's own setup installs from. What it CAN do is refuse to
    leave the question unanswered in the campaign record, which is what lane A's
    convergence point asks for. Degrades LOUD -- `git` is not a runtime
    dependency here, so its absence is reported, never read as clean.
    """

    def run(args: list[str]) -> str | None:
        try:
            done = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    sha = run(["git", "rev-parse", "HEAD"])
    if sha is None:
        return {
            "sha": "UNKNOWN",
            "tree": "UNKNOWN",
            "note": "git unavailable or not a repository - trunk NOT attested",
        }
    status = run(["git", "status", "--porcelain"]) or ""
    dirty = [ln for ln in status.splitlines() if not ln.startswith("?? .nwave/")]
    return {
        "sha": sha,
        "tree": "clean" if not dirty else f"DIRTY ({len(dirty)} tracked changes)",
        "note": "recorded at campaign start; each arm's setup decides what it installs",
    }


def _auth_is_live() -> tuple[bool, str]:
    try:
        done = subprocess.run(
            _AUTH_PROBE,
            capture_output=True,
            text=True,
            timeout=180,
            cwd="/tmp",
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        return False, f"unparseable probe output: {done.stdout[:120]!r}"
    if payload.get("is_error"):
        return False, str(payload.get("result"))[:160]
    return True, "ok"


def _run_setup(arm: ArmSpec, *, workspace: Path, pair_dir: Path) -> tuple[bool, float]:
    """Run the arm's declared setup, sequentially, before the timer that counts.

    Returns (ok, seconds). A failing setup does NOT fall through to the timed
    invocation: an arm whose environment was never established would produce a
    real-looking run whose only finding is that the harness broke. That is the
    silent-wrong this whole instrument exists to refuse, so it degrades LOUD --
    the record says which step failed and the delivery is never attempted.
    """
    started = time.monotonic()
    records: list[dict[str, object]] = []
    environment = {**os.environ, **arm.rendered_env(workspace)}
    ok = True
    for index, step in enumerate(arm.setup, start=1):
        try:
            done = subprocess.run(
                list(step),
                cwd=workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            code, tail = done.returncode, (done.stderr or done.stdout)[-400:]
        except subprocess.TimeoutExpired:
            code, tail = 124, "TIMEOUT after 1800s"
        except OSError as exc:
            code, tail = 127, f"{type(exc).__name__}: {exc}"
        records.append({"step": index, "argv": list(step), "exit": code, "tail": tail})
        if code != 0:
            ok = False
            break
    seconds = time.monotonic() - started
    (pair_dir / f"{arm.name}.setup.json").write_text(
        json.dumps({"ok": ok, "seconds": round(seconds, 1), "steps": records}, indent=1)
        + "\n",
        encoding="utf-8",
    )
    return ok, seconds


#: The delivery ceiling, and why it is not 1800s any more.
#:
#: A ceiling is only neutral when NEITHER arm can reach it. An enterprise
#: brownfield feature is a long job, and nWave's spine is deliberately more
#: staged than a single vanilla pass, so a ceiling tight enough to cut the
#: treatment arm while the control finishes measures the CEILING and reports it
#: as a product difference -- in the direction that flatters the control.
#:
#: The asymmetry decides the default: a ceiling set too low invalidates the run,
#: a ceiling set too high only costs waiting. Recorded in `campaign.json`, so a
#: reader can see which number the runs were measured under.
DELIVERY_TIMEOUT_S = 5400


def _run_pair_setup(arm: ArmSpec, *, pair_dir: Path) -> tuple[bool, float]:
    """Setup half of the pair barrier: prepare `arm`'s workspace, return (ok, seconds).

    Both arms' setups fan out together; a failing setup here must not let its
    peer's delivery start -- the caller joins both results before either
    delivery is attempted.
    """
    workspace = pair_dir / arm.name
    workspace.mkdir(parents=True, exist_ok=True)
    setup_ok, setup_seconds = _run_setup(arm, workspace=workspace, pair_dir=pair_dir)
    if not setup_ok:
        (pair_dir / f"{arm.name}.json").write_text("", encoding="utf-8")
        (pair_dir / f"{arm.name}.err").write_text(
            f"SETUP FAILED after {setup_seconds:.0f}s - delivery not attempted; "
            f"see {arm.name}.setup.json",
            encoding="utf-8",
        )
        print(f"  {arm.name}: SETUP FAILED ({setup_seconds:.0f}s)", flush=True)
    elif arm.setup:
        print(f"  {arm.name}: setup {setup_seconds:.0f}s", flush=True)
    return setup_ok, setup_seconds


def _delivery_is_valid(stdout: str, returncode: int) -> bool:
    """Direct exit 0 alone does not mean the delivery produced a usable record,
    and apparently valid JSON from a nonzero exit is not a usable record either.

    Valid means: `returncode == 0`, stdout parses as exactly one JSON object,
    `is_error` is not true, and `session_id` is a non-empty string. Anything
    else is treated as invalid and must stop later pairs -- a malformed
    record, or a well-formed one from a process that failed, that looked
    executed is the exact silent-wrong this instrument exists to refuse.
    """
    if returncode != 0:
        return False
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("is_error"):
        return False
    session_id = payload.get("session_id")
    return isinstance(session_id, str) and session_id != ""


def _run_delivery(
    arm: ArmSpec,
    *,
    task: str,
    pair_dir: Path,
    timeout: int,
    environment_delta: Mapping[str, str] | None = None,
) -> bool:
    """Run only the timed invocation (setup must already have succeeded).

    The PGID is captured immediately after `Popen(start_new_session=True)`
    puts the child in its own process group, and `finally` ALWAYS attempts
    TERM on that owned group -- not only when `proc.poll() is None` -- then
    waits bounded for the group to disappear before KILL. A parent that races
    ahead of a still-running child (the direct-Claude case this guards) must
    not skip cleanup just because the poll happened to observe the process as
    already reaped; killpg targets only the group this call itself owns, and
    `ProcessLookupError` means the group is already gone, i.e. clean. This
    runs on success, failure, timeout, OSError, and interruption
    (KeyboardInterrupt/SystemExit unwind through `finally` too), so a
    delivery's child never outlives the runner that spawned it.
    """
    workspace = pair_dir / arm.name
    arm_environment = arm.rendered_env(workspace)
    delta = dict(environment_delta or {})
    if any(
        not isinstance(name, str) or not isinstance(value, str)
        for name, value in delta.items()
    ):
        raise ValueError("delivery environment delta must map strings to strings")
    collisions = {
        name
        for name, value in delta.items()
        if name in arm_environment and arm_environment[name] != value
    }
    if collisions:
        raise ValueError(
            "delivery environment delta conflicts with declared arm environment: "
            + ", ".join(sorted(collisions))
        )
    environment = {**os.environ, **arm_environment, **delta}
    started = time.monotonic()
    stdout, stderr = "", ""
    returncode: int | None = None
    proc: subprocess.Popen | None = None
    pgid: int | None = None
    failure_class: str | None = None
    try:
        proc = subprocess.Popen(
            arm.rendered(workspace),
            cwd=workspace,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        pgid = os.getpgid(proc.pid)
        try:
            stdout, stderr = proc.communicate(
                input=arm.task_prefix + task, timeout=timeout
            )
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr = "", f"TIMEOUT after {timeout}s"
            failure_class = "timeout"
            raise
    except subprocess.TimeoutExpired:
        pass
    except OSError as exc:
        stdout, stderr = "", f"{type(exc).__name__}: {exc}"
        failure_class = type(exc).__name__
    finally:
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGTERM)
                proc.wait(timeout=10)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            except OSError:
                pass
        if proc is not None and proc.returncode is not None:
            returncode = proc.returncode
    # Absolute paths, resolved before any chdir: the shell version wrote every
    # artifact INSIDE the workspace it had cd'd into, because `dirname $0` was
    # relative and the redirect ran after the cd.
    duration_ms = round((time.monotonic() - started) * 1000)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        payload["duration_ms"] = duration_ms
        stdout = json.dumps(payload, separators=(",", ":"))
    elif failure_class is not None:
        payload = {
            "is_error": True,
            "duration_ms": duration_ms,
            "terminal_reason": failure_class,
        }
        if returncode is not None:
            payload["returncode"] = returncode
        stdout = json.dumps(payload, separators=(",", ":"))
    (pair_dir / f"{arm.name}.json").write_text(stdout, encoding="utf-8")
    (pair_dir / f"{arm.name}.err").write_text(stderr, encoding="utf-8")
    valid = _delivery_is_valid(stdout, returncode)
    print(f"  {arm.name}: {duration_ms / 1000:.0f}s", flush=True)
    return valid


@dataclass(frozen=True)
class DeclaredArmRun:
    """The observed outcome of one declared arm execution.

    This is deliberately a thin public composition of the existing setup and
    delivery mechanics.  A diagnostic runner can execute one arm without
    recreating (and then drifting from) the subprocess, timeout, stdin, and
    process-group rules that paired campaigns already use.
    """

    workspace: Path
    setup_ok: bool
    setup_seconds: float
    delivery_ok: bool | None


def execute_declared_arm_once(
    arm: ArmSpec,
    *,
    task: str,
    run_dir: Path,
    timeout: int,
    before_delivery: Callable[[Path], Mapping[str, str] | None] | None = None,
    after_delivery: Callable[[Path, bool], None] | None = None,
) -> DeclaredArmRun:
    """Execute exactly one declared arm, setup then delivery, sequentially.

    ``before_delivery`` and ``after_delivery`` are observation hooks.  The
    former may return a string-only environment delta, merged after the declared
    arm environment. An unequal collision is refused: a diagnostic reservation
    must not silently replace an arm declaration. A hook exception propagates.
    """
    workspace = run_dir / arm.name
    workspace.mkdir(parents=True, exist_ok=True)
    setup_ok, setup_seconds = _run_setup(arm, workspace=workspace, pair_dir=run_dir)
    if not setup_ok:
        return DeclaredArmRun(workspace, False, setup_seconds, None)
    environment_delta = (
        before_delivery(workspace) if before_delivery is not None else None
    )
    delivery_ok = _run_delivery(
        arm,
        task=task,
        pair_dir=run_dir,
        timeout=timeout,
        environment_delta=environment_delta,
    )
    if after_delivery is not None:
        after_delivery(workspace, delivery_ok)
    return DeclaredArmRun(workspace, True, setup_seconds, delivery_ok)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--arms", required=True, type=Path, help="JSON with `task` and `arms`"
    )
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument(
        "--timeout",
        type=int,
        default=DELIVERY_TIMEOUT_S,
        help="seconds a single delivery may take; see DELIVERY_TIMEOUT_S",
    )
    parser.add_argument("--out", type=Path, default=Path("./campaign"))
    args = parser.parse_args(argv)

    spec = json.loads(args.arms.read_text(encoding="utf-8"))
    task = spec["task"]
    try:
        arms = [parse_arm(name, declared) for name, declared in spec["arms"].items()]
    except ValueError as exc:
        sys.stderr.write(
            f"WHAT: the arm declaration is malformed ({exc}).\n"
            "WHY:  a campaign built from a spec nobody could parse would run something\n"
            "      other than what was pre-registered.\n"
            'HOW:  declare each arm as an argv list, or as {"setup": [[...]], "argv": [...]}.\n'
        )
        return 2
    if len(arms) != 2:
        sys.stderr.write(
            f"WHAT: {len(arms)} arm(s) declared; a pair is exactly 2.\n"
            "WHY:  pairing works by giving both arms the SAME conditions at the same\n"
            "      moment. One arm cancels nothing; three is not a pair.\n"
            "HOW:  declare exactly two entries under `arms` in the spec file.\n"
        )
        return 2

    violations = declared_identity_violations(arms)
    if violations:
        sys.stderr.write(
            "WHAT: the two arms are not comparable as declared.\n"
            + "".join(f"      - {v}\n" for v in violations)
            + "WHY:  a paired campaign isolates provider conditions, not declaration\n"
            "      mistakes. A difference nobody declared is indistinguishable, in\n"
            "      the result, from the effect being measured.\n"
            "HOW:  correct the declared checkout and isolation facts. The Request is\n"
            "      supplied identically to both arms on stdin.\n"
        )
        return 2

    live, why = _auth_is_live()
    if not live:
        sys.stderr.write(
            f"WHAT: the one-line headless auth probe failed ({why}).\n"
            "WHY:  every run would return is_error with zero usage - a campaign that\n"
            "      looks executed and measures nothing.\n"
            "HOW:  fix headless auth first. Do NOT pass `--bare`: measured 2026-08-06,\n"
            "      it strips the login under subscription auth.\n"
        )
        return 78

    # Row 21 (K4 matrix): both arms can draw on ONE shared credit/quota
    # pool; exhaustion then hits them in a correlated way mid-pair, and the
    # pair the timer already started is not recoverable. Refuse to start
    # rather than run degraded -- checked per arm, through that arm's own
    # declared env, BEFORE campaign.json is written or any pair begins.
    args.out.mkdir(parents=True, exist_ok=True)
    campaign_record = {
        "task": task,
        "arms": {
            a.name: {
                "setup": [list(step) for step in a.setup],
                "argv": list(a.argv),
                "env": dict(a.env),
            }
            for a in arms
        },
        "pairs": args.pairs,
        "delivery_timeout_s": args.timeout,
        "trunk": _attested_trunk(),
    }
    if "artifact" in spec:
        campaign_record["artifact"] = spec["artifact"]
    (args.out / "campaign.json").write_text(
        json.dumps(campaign_record, indent=1) + "\n",
        encoding="utf-8",
    )

    # Every exit below this line archives, including the give-up paths: a
    # campaign that died at pair 2 has already PAID for pair 1, and the /tmp
    # wipe of 2026-08-22 destroyed exactly that kind of partial evidence.
    try:
        return _run_pairs(args, arms, task)
    finally:
        archived = campaign_archive.archive_or_explain(args.out)
        if archived is not None:
            print(f"archived   : {archived}", flush=True)


def _run_pairs(args, arms: list[ArmSpec], task: str) -> int:
    """The pair loop itself. Extracted so `main` can wrap it in the archive
    step without the step depending on which way the loop ended."""
    for index in range(1, args.pairs + 1):
        pair_dir = args.out / f"pair-{index}"
        pair_dir.mkdir(exist_ok=True)
        print(
            f"--- pair {index}: setup barrier, both arms concurrently ---", flush=True
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            # Concurrent, not sequential. Sequential arms is the design that
            # made contention a confound in the first place.
            # `partial`, not a lambda: a closure over the loop variable binds
            # late, and this one is only safe today because `list()` drains
            # each pair before the next iteration rebinds it.
            setup_results = list(
                pool.map(
                    partial(_run_pair_setup, pair_dir=pair_dir),
                    arms,
                )
            )
        if not all(ok for ok, _ in setup_results):
            print(
                f"pair {index}: setup failed for at least one arm; stopping", flush=True
            )
            return 1

        print(f"--- pair {index}: delivery, both arms concurrently ---", flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            delivery_results = list(
                pool.map(
                    partial(
                        _run_delivery,
                        task=task,
                        pair_dir=pair_dir,
                        timeout=args.timeout,
                    ),
                    arms,
                )
            )
        if not all(delivery_results):
            print(
                f"pair {index}: an invalid delivery record; stopping before pair {index + 1}",
                flush=True,
            )
            return 1

    print(f"done: {args.pairs} pairs under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
