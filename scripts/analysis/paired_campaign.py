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
`des.runtime.spawn` is not available. DEVNULL is not decoration: POSIX inherits
fd 0 transitively, so a child that inherits it can block forever on a descriptor
that delivers data and never reaches EOF -- the confirmed root cause of the
`des refactor --pile` deadlock, four nested processes asleep on pipes.

    paired_campaign.py --arms arms.json --pairs 3 --out ./campaign

`arms.json`:
    {"task": "<the identical prompt both arms receive>",
     "arms": {"control": {"setup": [["git","clone","--depth","1","<sut>","."]],
                          "argv":  ["claude","-p","{task}","--model","claude-sonnet-5",
                                    "--output-format","json",
                                    "--dangerously-skip-permissions"]},
              "nwave":   {"setup": [["git","clone","--depth","1","<sut>","."],
                                    ["nwave-ai","install"],
                                    ["nwave-ai","project","enable"]],
                          "argv":  ["claude","-p","{task}", ...]}}}

A bare list is still accepted as an arm with no setup.

## Two views from ONE execution, and what actually differs between them

Setup runs before the timed invocation, always, and its wall-clock is recorded
SEPARATELY. The pre-registered cold/operator view is then `setup + delivery` and
the warm view is `delivery` alone -- both computed from the same runs, because
setup is strictly sequential and therefore decomposable. Running two campaigns
to obtain them would spend twice for one number.

**The two views differ in wall-clock and in essentially nothing else**, and
saying so is not a caveat but the finding: `nwave-ai install` and `project
enable` are deterministic Python, so an arm's setup contributes zero model
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

    def rendered(self, task: str, workspace: Path) -> list[str]:
        """`{task}` and `{workspace}` are the ONLY substitutions, using the
        SAME `workspace` `rendered_env` renders for this call's env dict.

        A single-token substitution here (`{task}` alone) let a `--settings`
        JSON argv token carrying `{workspace}` (a K4 sandbox's `env.PATH`,
        declared once and shared by argv and env) reach the spawned process
        UNRENDERED, while `rendered_env` correctly substituted the same
        placeholder in the env dict -- the two views of one declared value
        then disagreed. Rendering both placeholders from one call, against
        the one `workspace` the caller already resolved, keeps argv and env
        joined on the same value by construction.
        """
        return [
            tok.replace("{task}", task).replace("{workspace}", str(workspace))
            for tok in self.argv
        ]

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
    return ArmSpec(
        name,
        tuple(declared["argv"]),
        tuple(tuple(str(t) for t in step) for step in steps),
        tuple(sorted(env.items())),
    )


#: Flags that must carry the SAME value in both arms. An arm may differ in what
#: it IS; it may not quietly differ in what it is measured under. Lane A leaves
#: the model pin open, so this is the check that stops an unpinned campaign
#: rather than a comment asking someone to remember.
_MUST_MATCH = ("--model", "--output-format")


def _flag_values(argv: tuple[str, ...], flag: str) -> list[str]:
    return [argv[i + 1] for i, t in enumerate(argv) if t == flag and i + 1 < len(argv)]


def declared_identity_violations(arms: list[ArmSpec]) -> list[str]:
    """Everything the operator declared that would make the arms incomparable.

    The docstring used to claim `{task}` substitution made both arms "provably"
    receive the same task. The lane-D audit refuted it: that is true of the
    MECHANISM and says nothing about what was DECLARED. An arm whose argv never
    mentions `{task}` runs a different task entirely, and nothing compared the
    models. These are checks now, not prose.
    """
    problems: list[str] = []
    for arm in arms:
        if not any("{task}" in token for token in arm.argv):
            problems.append(
                f"arm '{arm.name}' never substitutes {{task}}: it would run a "
                "different task from the other arm"
            )
    for flag in _MUST_MATCH:
        seen = {arm.name: _flag_values(arm.argv, flag) for arm in arms}
        if len({tuple(v) for v in seen.values()}) > 1:
            problems.append(f"{flag} differs across arms: {seen}")
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


#: One line, cheap. `_AUTH_PROBE` above is a HARD-CODED `claude` invocation
#: that cannot see per-arm env, so it can only prove auth is live once,
#: globally. Row 21 (K4 matrix) needs a probe PER ARM, through that arm's
#: own declared env -- the confound this exists to catch is both arms
#: drawing on ONE shared credit/quota pool, which a single global probe
#: cannot distinguish from two disjoint healthy accounts.
_HEADROOM_PROBE_TASK = "Reply with exactly: OK"

#: Markers that name QUOTA/CREDIT exhaustion specifically. A transient
#: network blip or an unrelated `is_error` must never read as "this arm is
#: out of headroom" -- conflating them would refuse a campaign for the
#: wrong reason, and the refusal message would lie about WHY.
_HEADROOM_EXHAUSTION_MARKERS = (
    "Credit balance is too low",
    "rate_limit",
    "rate limit",
    "quota",
)


def _headroom_names_exhaustion(result: str) -> bool:
    lowered = result.lower()
    return any(marker.lower() in lowered for marker in _HEADROOM_EXHAUSTION_MARKERS)


def _arm_headroom_is_sufficient(arm: ArmSpec, workspace: Path) -> tuple[bool, str]:
    """One-line probe through THIS arm's own env, checked for a known
    exhaustion marker before any pair is timed.

    Refuses to CLASSIFY an unrecognized `is_error` as exhaustion: a probe
    that cannot reach the provider at all (network, malformed spec) is a
    different failure than a provider that reached back and said "no
    headroom" -- the caller decides what a plain probe failure means;
    this function answers only the exhaustion question.
    """
    environment = {**os.environ, **arm.rendered_env(workspace)}
    probe_argv = arm.rendered(_HEADROOM_PROBE_TASK, workspace)
    try:
        done = subprocess.run(
            probe_argv,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (
            True,
            f"probe could not run, not classified as exhaustion: "
            f"{type(exc).__name__}: {exc}",
        )
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError:
        return (
            True,
            f"unparseable probe output, not classified as exhaustion: {done.stdout[:160]!r}",
        )
    if not isinstance(payload, dict):
        return (
            True,
            "probe output is not a JSON object, not classified as exhaustion: "
            f"{done.stdout[:160]!r}",
        )
    result = str(payload.get("result", ""))
    if payload.get("is_error") and _headroom_names_exhaustion(result):
        return False, result[:200]
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
_DELIVERY_TIMEOUT_S = 5400


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


def _run_delivery(arm: ArmSpec, *, task: str, pair_dir: Path, timeout: int) -> bool:
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
    environment = {**os.environ, **arm.rendered_env(workspace)}
    started = time.monotonic()
    stdout, stderr = "", ""
    returncode = -1
    proc: subprocess.Popen | None = None
    pgid: int | None = None
    try:
        proc = subprocess.Popen(
            arm.rendered(task, workspace),
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        pgid = os.getpgid(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr = "", f"TIMEOUT after {timeout}s"
            raise
    except subprocess.TimeoutExpired:
        pass
    except OSError as exc:
        stdout, stderr = "", f"{type(exc).__name__}: {exc}"
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
    # Absolute paths, resolved before any chdir: the shell version wrote every
    # artifact INSIDE the workspace it had cd'd into, because `dirname $0` was
    # relative and the redirect ran after the cd.
    (pair_dir / f"{arm.name}.json").write_text(stdout, encoding="utf-8")
    (pair_dir / f"{arm.name}.err").write_text(stderr, encoding="utf-8")
    valid = _delivery_is_valid(stdout, returncode)
    print(f"  {arm.name}: {time.monotonic() - started:.0f}s", flush=True)
    return valid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--arms", required=True, type=Path, help="JSON with `task` and `arms`"
    )
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument(
        "--timeout",
        type=int,
        default=_DELIVERY_TIMEOUT_S,
        help="seconds a single delivery may take; see _DELIVERY_TIMEOUT_S",
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
            "HOW:  make both arms substitute {task}, and pin the shared flags to the\n"
            "      same values in the spec file.\n"
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
    exhausted: list[tuple[str, str]] = []
    for arm in arms:
        probe_workspace = args.out / f".headroom-probe-{arm.name}"
        probe_workspace.mkdir(parents=True, exist_ok=True)
        sufficient, detail = _arm_headroom_is_sufficient(arm, probe_workspace)
        if not sufficient:
            exhausted.append((arm.name, detail))
    if exhausted:
        sys.stderr.write(
            "WHAT: at least one arm's quota/credit headroom probe reports "
            "exhaustion.\n"
            + "".join(f"      - arm '{name}': {detail}\n" for name, detail in exhausted)
            + "WHY:  both arms may share one credit/quota pool; running a pair now\n"
            "      would hit exhaustion mid-pair in a CORRELATED way, invalidating\n"
            "      the pair rather than measuring anything -- and the timer already\n"
            "      started is not recoverable.\n"
            "HOW:  restore headroom on the exhausted arm's account, or use disjoint\n"
            "      or serialized credit sources per arm, then rerun. This refusal is\n"
            "      deliberate: the campaign never runs degraded.\n"
        )
        return 78
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
