#!/usr/bin/env python3
"""Execute the hidden acceptance suite against every delivery, identically.

Emits the `session_id`-keyed `verdicts.json` that `paired_quality_join.py`
consumes. It does not judge anything else: the join holds a reference to this
verdict, and the source-blind rubric scores the delivery around it. A run can
fail acceptance and still score well on the rubric, and that combination is
informative rather than contradictory.

    run_acceptance.py --campaign <dir> --suite <acceptance file> --out verdicts.json

## Two things it runs, and why both

* **the hidden suite** -- did the feature actually work;
* **the subject's own test suite** -- did the delivery break something else.

The second is not politeness. A delivery that satisfies maintenance windows by
changing how every check computes its status would pass the first and wreck the
product, and only the pre-existing 200 test modules can see that. Both results
are recorded; `accepted` requires both.

## What makes it identical across arms

The arm's own `requirements.txt` is installed, because a delivery may
legitimately add a dependency, and refusing that would score the arms on a
constraint neither was told about. Next comes only the slice of
`requirements-dev.txt` the delivery itself added or changed versus its own
Git HEAD -- never the whole file. A delivered test suite may declare
test-only dependencies there, and a workspace that has one but cannot
install it fails outright, before either suite runs; but that file also
carries whatever dev dependencies pre-existed the delivery, and one of those
can need system packages this environment doesn't have, for reasons that
have nothing to do with the delivery under test. Installing the whole file
would then fail both arms identically before either suite runs and call
that a measurement. Everything else -- the suite file, the command, the
interpreter version -- comes from here, not from the workspace.

The name `test_k4_acceptance.py` is written INTO the arm's tree at run time.
That is deliberate: it never exists while the arm works, so no delivery can be
tuned to it, and a delivery that happens to have created a file by that name is
reported rather than silently overwritten.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from scripts.analysis.k4 import prepare_examiner_fixture as pef
from scripts.analysis.k4 import subject as k4_subject


_SUITE_TARGET = Path("hc") / "api" / "tests" / "test_k4_acceptance.py"
_SUITE_LABEL = "hc.api.tests.test_k4_acceptance"
_ACCEPTANCE_VENV_NAME = ".k4-acceptance-venv"
_DEV_DELTA_REQUIREMENTS_NAME = "requirements-dev-delta.txt"

#: Measurement/setup bulk that must never ride into the disposable snapshot:
#: VCS metadata, Claude runtime/session dirs, a prior run's own venv, and
#: interpreter/tool caches. Everything else -- tracked or not, modified or
#: not -- is delivered content and is copied.
_EXCLUDED_SNAPSHOT_NAMES = frozenset(
    {
        ".git",
        ".claude",
        ".claude-k4",
        _ACCEPTANCE_VENV_NAME,
        "k4-fixture-venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".hypothesis",
    }
)


@dataclass(frozen=True)
class Outcome:
    """One delivery's acceptance, with the evidence that produced it."""

    arm: str
    session_id: str | None
    accepted: bool
    evidence: str


def _run(argv: list[str], cwd: Path, timeout: int = 2400) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return done.returncode, (done.stdout + done.stderr)[-1500:]


def _session_id(payload: Path) -> str | None:
    try:
        return json.loads(payload.read_text(encoding="utf-8")).get("session_id")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _verdict_line(output: str) -> str:
    """The line that says WHAT happened, not the last line printed.

    The first version took `splitlines()[-1]`, which is always Django's
    "Destroying test database..." teardown. Every verdict therefore carried
    evidence that named no failure at all -- a record that looks complete and
    explains nothing, which is worse than an empty field because nobody goes
    looking. Caught the first time a delivery actually failed.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    named = [
        line for line in lines if line.startswith(("FAIL:", "ERROR:", "AssertionError"))
    ]
    summary = [line for line in lines if line.startswith(("OK", "FAILED (", "Ran "))]
    parts = summary[-2:] + named[:3]
    return " ; ".join(parts) if parts else "<no output>"


def _snapshot_ignore(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _EXCLUDED_SNAPSHOT_NAMES}


class _RequirementsDeltaError(RuntimeError):
    """Git/HEAD could not be inspected for a reason other than
    requirements-dev.txt simply not existing at HEAD."""


def _requirement_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _dev_requirements_delta(workspace: Path) -> list[str]:
    """The requirements-dev.txt lines this delivery itself added or changed,
    versus `git show HEAD:requirements-dev.txt` in the delivery worktree --
    never the whole file, so that a dev dependency that pre-existed the
    delivery (and may need system packages this environment doesn't have)
    is never installed on the delivery's behalf. Order and duplicate counts
    from the current file are preserved; a changed pin has different text
    from anything at HEAD and so counts as an addition."""
    current_path = workspace / "requirements-dev.txt"
    if not current_path.is_file():
        return []
    current_lines = _requirement_lines(current_path.read_text(encoding="utf-8"))

    try:
        done = subprocess.run(
            ["git", "show", "HEAD:requirements-dev.txt"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RequirementsDeltaError(
            "`git show HEAD:requirements-dev.txt` in "
            f"{workspace} could not run: {type(exc).__name__}: {exc}"
        ) from exc

    if done.returncode == 0:
        head_lines = _requirement_lines(done.stdout)
    elif "does not exist in" in done.stderr or "exists on disk, but not" in done.stderr:
        head_lines = []
    else:
        raise _RequirementsDeltaError(
            "`git show HEAD:requirements-dev.txt` in "
            f"{workspace} failed (exit {done.returncode}): {done.stderr.strip()}"
        )

    remaining = Counter(head_lines)
    delta: list[str] = []
    for line in current_lines:
        if remaining.get(line, 0) > 0:
            remaining[line] -= 1
        else:
            delta.append(line)
    return delta


def _install_suite_venv(
    snapshot: Path, dev_delta: list[str]
) -> tuple[bool, str, Path | None]:
    """Create the disposable venv and install exactly what a scored delivery
    gets: its own requirements.txt, its own dev-requirements delta, and the
    suite's clock dependency. Returns the venv's python executable on
    success. Shared by `_examine_snapshot` (the real scored run) and
    `_self_probe_oracle_red` (the RED proof, GDP-8 witness corollary) so the
    two never drift apart on what "installed" means."""
    venv = snapshot / _ACCEPTANCE_VENV_NAME
    code, tail = _run([sys.executable, "-m", "venv", str(venv)], snapshot)
    if code != 0:
        return False, f"could not create the acceptance venv: {tail}", None
    pip = str(venv / "bin" / "pip")
    code, tail = _run([pip, "install", "-q", "-r", "requirements.txt"], snapshot)
    if code != 0:
        return False, f"the delivery's requirements.txt does not install: {tail}", None
    if dev_delta:
        delta_reqs = snapshot / _DEV_DELTA_REQUIREMENTS_NAME
        delta_reqs.write_text("\n".join(dev_delta) + "\n", encoding="utf-8")
        code, tail = _run([pip, "install", "-q", "-r", str(delta_reqs)], snapshot)
        if code != 0:
            return (
                False,
                "the delivery's test-dependency delta "
                f"{dev_delta} does not install: {tail}",
                None,
            )
    code, tail = _run([pip, "install", "-q", "time-machine"], snapshot)
    if code != 0:
        return False, f"could not install the suite's clock dependency: {tail}", None
    return True, "", venv / "bin" / "python"


def _examine_snapshot(
    snapshot: Path, suite: Path, dev_delta: list[str]
) -> tuple[bool, str]:
    """Run both suites against the disposable copy. Whatever this writes into
    `snapshot` (venv, delta requirements file, suite file) dies with it in
    `examine`'s `finally` -- nothing here needs its own cleanup."""
    ok, evidence, python = _install_suite_venv(snapshot, dev_delta)
    if not ok:
        return False, evidence

    target = snapshot / _SUITE_TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(suite, target)

    feature_code, feature_tail = _run(
        [str(python), "manage.py", "test", _SUITE_LABEL], snapshot
    )
    regression_code, regression_tail = _run(
        [str(python), "manage.py", "test", "hc", "--exclude-tag", "k4"],
        snapshot,
        timeout=3600,
    )

    accepted = feature_code == 0 and regression_code == 0
    evidence = (
        f"hidden suite exit {feature_code} [{_verdict_line(feature_tail)}]; "
        f"subject suite exit {regression_code} [{_verdict_line(regression_tail)}]"
    )
    return accepted, evidence


#: Row 2 (K4 matrix): the acceptance oracle itself once inverted the verdict
#: (`ef37b76b0` -- a fixture bug flipped which day the flip landed on, so a
#: CORRECT delivery read as a failure). Red-alone is half a verification; a
#: campaign that never watches the oracle fail against a subject with no
#: feature at all is trusting the other half by promise, not by evidence.
#: This prefix marks the self-probe's OWN disposable snapshot so a caller
#: (or a test double) can tell it apart from the snapshot a real delivery is
#: scored in -- see `_self_probe_oracle_red`.
_SELF_PROBE_DIR_MARKER = "k4-self-probe-"


def _base_commit_sha(workspace: Path) -> str | None:
    """This workspace's own pristine base commit: the shallow clone's root,
    or HEAD itself when the delivery added no commits on top. Never an
    externally-pinned SUT revision -- `preflight.py` clones `--depth 1` off
    the SUT's default branch at whatever moment a campaign happens to run,
    so no such pin exists to read anywhere. Resolving it from the
    workspace's OWN history means the self-probe below reconstructs exactly
    the state THIS campaign actually started from, for every campaign,
    without needing to know the subject's identity.

    A real subprocess call, like `_dev_requirements_delta`'s git calls --
    not routed through the mockable `_run` seam, because what it inspects
    (this workspace's actual commit graph) is not something a build/test
    double can stand in for."""
    try:
        done = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    roots = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    # More than one root is a merged/grafted history this harness has never
    # seen from a `--depth 1` SUT clone; refuse rather than guess which root
    # the delivery actually started from.
    return roots[0] if len(roots) == 1 else None


def _extract_base_tree(workspace: Path, base_sha: str, dest: Path) -> tuple[bool, str]:
    """Materialize `base_sha` -- exactly as committed, ignoring the
    delivery's own tracked and untracked changes -- into `dest`. A real
    `git archive`, for the same reason `_base_commit_sha` is real: there is
    no double for "what did this commit actually contain"."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest.parent / "base.tar"
    try:
        done = subprocess.run(
            ["git", "archive", "--format=tar", "-o", str(archive), base_sha],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"`git archive {base_sha}` did not run: {exc}"
    if done.returncode != 0:
        return (
            False,
            f"`git archive {base_sha}` exited {done.returncode}: {done.stderr}",
        )
    with tarfile.open(archive) as handle:
        try:
            handle.extractall(dest, filter="data")  # Python >= 3.12 (PEP 706)
        except TypeError:
            handle.extractall(dest)  # Python 3.10/3.11: no `filter` parameter
    return True, ""


def _self_probe_oracle_red(
    workspace: Path, base_sha: str, suite: Path
) -> tuple[bool, str]:
    """GDP-8 witness corollary: prove the oracle can go RED before trusting
    it to score anything against `base_sha` -- the checker is not exempt
    from the class it checks. Runs the oracle, UNMODIFIED, against a clean
    extraction of `workspace`'s own base commit: on the undelivered subject
    it must fail, never exit clean. A GREEN here means the oracle cannot
    discriminate delivered from undelivered and no pair sharing this base
    commit may be scored from it.

    Feature suite only, not the subject's full regression suite: proving RED
    is the whole job here, and doubling every campaign's runtime with the
    ~200-module regression pass `_examine_snapshot` runs for a REAL score
    would make this the opposite of cheap."""
    probe_root = Path(tempfile.mkdtemp(prefix=_SELF_PROBE_DIR_MARKER))
    try:
        snapshot = probe_root / "base"
        ok, evidence = _extract_base_tree(workspace, base_sha, snapshot)
        if not ok:
            return False, f"could not extract the undelivered base: {evidence}"

        ok, evidence, python = _install_suite_venv(snapshot, [])
        if not ok:
            return False, f"could not prepare the undelivered-base venv: {evidence}"

        target = snapshot / _SUITE_TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(suite, target)

        code, tail = _run([str(python), "manage.py", "test", _SUITE_LABEL], snapshot)
        if code == 0:
            return False, (
                f"the oracle exited 0 (GREEN) against its own undelivered base "
                f"{base_sha} -- it cannot discriminate delivered from undelivered"
            )
        return (
            True,
            f"oracle exit {code} on undelivered base {base_sha} [{_verdict_line(tail)}]",
        )
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)


def examine(
    workspace: Path,
    suite: Path,
    *,
    probe_cache: dict[str, tuple[bool, str]] | None = None,
    pinned_subject_rev: str | None = None,
) -> tuple[bool, str]:
    """Measure a disposable snapshot of the delivery, never the delivery
    itself. The original is written to only for the setup-owned user-
    environment doc, removed here regardless of outcome; every other
    original path -- tracked or not, before or after this call -- is
    unchanged. Because each call owns its own snapshot, two concurrent
    `examine` calls over the same workspace share no mutable state and
    cannot race on a target file or a venv.

    Refuses to score anything until `_self_probe_oracle_red` has proven the
    oracle goes RED on THIS workspace's own undelivered base commit (row 2,
    K4 matrix -- GDP-8 witness corollary). `probe_cache`, keyed by base
    commit sha, lets a caller scoring many pairs from the same campaign (see
    `main`) pay for that proof once per distinct base commit rather than
    once per pair -- proof, not ceremony, is what row 2 asks for. A caller
    that passes nothing gets a private cache scoped to this one call.

    `pinned_subject_rev`, when given, must equal this workspace's own
    resolved base commit or the pair is refused -- reproducibility (K4
    matrix rows 2/4) needs every pair of every campaign measured against the
    IDENTICAL subject state, and `_base_commit_sha` alone only proves a
    self-consistent one. `main` passes `scripts.analysis.k4.subject
    .SUT_PINNED_REV` for a real campaign; left `None` (the default) for
    every other caller -- unit tests exercising this function against a
    synthetic workspace never share a commit with the real SUT and are not
    what this check is for.
    """
    workspace = Path(workspace)
    if not (workspace / "manage.py").is_file():
        return False, "no manage.py: the workspace is not a usable checkout"

    if (workspace / _SUITE_TARGET).exists():
        return (
            False,
            f"the delivery already contains {_SUITE_TARGET}; refusing to overwrite",
        )

    if probe_cache is None:
        probe_cache = {}
    base_sha = _base_commit_sha(workspace)
    if base_sha is None:
        return False, (
            "could not resolve this workspace's own base commit via `git "
            "rev-list --max-parents=0 HEAD`; the oracle self-probe (row 2, "
            "GDP-8 witness corollary) cannot run without it, so this pair "
            "is refused rather than scored unproven"
        )
    if pinned_subject_rev is not None and base_sha != pinned_subject_rev:
        return False, (
            f"refused: this workspace's own base commit {base_sha} does not "
            f"match the pinned subject revision {pinned_subject_rev} "
            "(scripts/analysis/k4/subject.py) -- reproducibility (K4 matrix "
            "rows 2/4) needs every pair measured against the identical "
            "subject state; re-run preflight so the clone pins to it"
        )
    if base_sha not in probe_cache:
        probe_cache[base_sha] = _self_probe_oracle_red(workspace, base_sha, suite)
    proved_red, probe_evidence = probe_cache[base_sha]
    if not proved_red:
        return False, (
            f"refused: the acceptance oracle did not prove RED on this "
            f"campaign's undelivered base {base_sha} before scoring -- "
            f"{probe_evidence}"
        )

    try:
        dev_delta = _dev_requirements_delta(workspace)
    except _RequirementsDeltaError as exc:
        return False, f"could not derive the delivered test-dependency delta: {exc}"

    snapshot_root = Path(tempfile.mkdtemp(prefix="k4-examine-"))
    try:
        snapshot = snapshot_root / "snapshot"
        shutil.copytree(workspace, snapshot, ignore=_snapshot_ignore, symlinks=True)
        return _examine_snapshot(snapshot, suite, dev_delta)
    finally:
        shutil.rmtree(snapshot_root, ignore_errors=True)
        (workspace / pef.DOC_NAME).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    outcomes: list[Outcome] = []
    # Shared across every pair in this campaign: pairs cloned from the same
    # SUT run share the same base commit, so the row-2 self-probe (GDP-8
    # witness corollary) proves RED once per distinct base sha, not once per
    # pair -- see `examine`'s `probe_cache` parameter.
    probe_cache: dict[str, tuple[bool, str]] = {}
    for payload in sorted(args.campaign.glob("pair-*/*.json")):
        if payload.name in ("campaign.json",) or payload.stem.endswith(".setup"):
            continue
        workspace = payload.parent / payload.stem
        if not workspace.is_dir():
            continue
        accepted, evidence = examine(
            workspace,
            args.suite.resolve(),
            probe_cache=probe_cache,
            pinned_subject_rev=k4_subject.SUT_PINNED_REV,
        )
        outcomes.append(Outcome(payload.stem, _session_id(payload), accepted, evidence))
        print(f"{payload.parent.name}/{payload.stem}: accepted={accepted}", flush=True)

    unkeyed = [o for o in outcomes if not o.session_id]
    if unkeyed:
        sys.stderr.write(
            "WHAT: a delivery carries no session_id.\n"
            + "".join(f"      - {o.arm}\n" for o in unkeyed)
            + "WHY:  session_id is the ONLY key that binds cost to quality. Without it\n"
            "      the join would have to guess, and the capture spec rejects every\n"
            "      construction that guesses - timestamp proximity, directory name,\n"
            "      arm label.\n"
            "HOW:  the run failed or its payload is unreadable. Treat it as a failed\n"
            "      run in the spread, not as a missing verdict here.\n"
        )

    verdicts = {
        o.session_id: {
            "accepted": o.accepted,
            "evidence": o.evidence,
            "scorer": "k4-hidden-acceptance",
        }
        for o in outcomes
        if o.session_id
    }
    args.out.write_text(json.dumps(verdicts, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out} — {len(verdicts)} verdicts, session-keyed")
    return 0 if verdicts and not unkeyed else 1


if __name__ == "__main__":
    raise SystemExit(main())
