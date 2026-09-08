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

from scripts.analysis import blind_review
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


_GITIGNORE_NAME = ".gitignore"


@dataclass(frozen=True)
class Outcome:
    """One delivery's acceptance, with the evidence that produced it.

    `delivered` is TRI-STATE -- True, False, or None for NOT ESTABLISHED --
    and the third state is written as an OMISSION, never as a value; see
    `main`.
    """

    arm: str
    session_id: str | None
    accepted: bool
    evidence: str
    delivered: bool | None = None
    delivered_evidence: str = ""


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


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """One real `git` invocation in `workspace`, or None if it could not run.

    Real subprocess calls, like `_dev_requirements_delta`'s -- not routed
    through the mockable `_run` seam, because what they inspect (this
    workspace's actual commit graph) is not something a build/test double
    can stand in for."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _base_commit_sha(
    workspace: Path, pinned_subject_rev: str | None = None
) -> tuple[str | None, str]:
    """The undelivered base commit this delivery started from, READ from the
    campaign's declared pin rather than guessed from the shape of the clone.

    `pinned_subject_rev` is `scripts.analysis.k4.subject.SUT_PINNED_REV` --
    the very revision `preflight.py`'s setup steps `git checkout --detach`,
    and the one both arms' `*.setup.json` record having checked out. When a
    caller has it, the base is not a derivation at all: the campaign already
    declared which subject state it measured against, so the only open
    question is whether THIS workspace actually sits on it, i.e. whether the
    pin is reachable from HEAD. Equality with HEAD is not required -- a
    delivery that committed on top of the pin is the normal case, and one
    that left its work in the working tree (camp7's actual shape) is
    equally normal.

    Deriving it instead from `git rev-list --max-parents=0 HEAD` was correct
    only while `preflight.py` cloned `--depth 1`, where the clone's single
    root commit IS the checked-out tip. `c8622cf32` (2026-08-18) replaced
    that with a FULL clone plus `git checkout --detach <pin>` and added the
    pin cross-check, but never updated this derivation -- so the root
    resolved to the subject's first commit ever and EVERY arm of EVERY
    campaign since was refused for "not matching the pinned subject
    revision" before its hidden suite or its row-2 RED probe ever ran.
    Measured on camp7: root `00cdc313`, HEAD `49653c35` (== the pin), no
    `.git/shallow`.

    Without a pin -- unit tests over a synthetic workspace -- there is
    nothing declared to read, and the old root-commit derivation still
    reconstructs the state that workspace started from.

    Returns `(sha, reason)`; on failure `sha` is None and `reason` states
    what could not be established."""
    if pinned_subject_rev is not None:
        resolved = _git(
            workspace, "rev-parse", "--verify", f"{pinned_subject_rev}^{{commit}}"
        )
        if resolved is None or resolved.returncode != 0:
            return None, (
                f"the campaign's declared subject revision {pinned_subject_rev} "
                "(scripts/analysis/k4/subject.py) is not a commit in this "
                "workspace's own history -- reproducibility (K4 matrix rows "
                "2/4) needs every pair measured against the identical subject "
                "state; re-run preflight so the clone checks it out"
            )
        base = resolved.stdout.strip()
        head = _git(workspace, "rev-parse", "--verify", "HEAD^{commit}")
        head_sha = head.stdout.strip() if head and head.returncode == 0 else "<unknown>"
        reachable = _git(workspace, "merge-base", "--is-ancestor", base, "HEAD")
        if reachable is None or reachable.returncode != 0:
            return None, (
                f"the campaign's declared subject revision {pinned_subject_rev} "
                f"is not reachable from this workspace's HEAD {head_sha}: this "
                "delivery was not built on the pinned subject state"
            )
        return base, ""

    done = _git(workspace, "rev-list", "--max-parents=0", "HEAD")
    if done is None or done.returncode != 0:
        return None, "`git rev-list --max-parents=0 HEAD` did not resolve"
    roots = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    # More than one root is a merged/grafted history this harness has never
    # seen from an unpinned SUT clone; refuse rather than guess which root
    # the delivery actually started from.
    if len(roots) != 1:
        return None, f"{len(roots)} root commits in this workspace's history"
    return roots[0], ""


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


def _is_setup_residue(rel_path: str) -> bool:
    """True when a changed path is SETUP's footprint, not the delivery's.

    Reuses `blind_review`'s own exclusion list and path matcher rather than
    keeping a second copy: the sealed review packet and this discriminant have
    to agree on what "the delivery changed" means, or a run can be sealed for
    review as a delivery and recorded here as none.
    """
    if rel_path == _DEV_DELTA_REQUIREMENTS_NAME:
        return True
    if blind_review._excluded_path(rel_path):
        return True
    return any(part in _EXCLUDED_SNAPSHOT_NAMES for part in Path(rel_path).parts)


def _gitignore_is_setup_only(workspace: Path, base_sha: str) -> bool | None:
    """Did SETUP write EVERY line by which `.gitignore` differs from `base_sha`?

    `.gitignore` cannot be handled by the path exclusions above. It is a real
    subject file a delivery may legitimately edit, so excluding it outright
    would hide delivery content, while counting it marks the nWave arm as
    delivering for a block `nwave-ai project enable` wrote.
    `blind_review.strip_setup_traces` is the existing answer to exactly that,
    and it is applied here to a COPY of the file inside a throwaway directory:
    the arm's workspace is evidence and is never mutated to take a measurement.

    None when the fact could not be established.
    """
    current = workspace / _GITIGNORE_NAME
    if not current.is_file():
        return None
    shown = _git(workspace, "show", f"{base_sha}:{_GITIGNORE_NAME}")
    if shown is None:
        return None
    baseline_text = shown.stdout if shown.returncode == 0 else ""
    probe_root = Path(tempfile.mkdtemp(prefix="k4-gitignore-"))
    try:
        shutil.copy2(current, probe_root / _GITIGNORE_NAME)
        blind_review.strip_setup_traces(probe_root)
        stripped = (probe_root / _GITIGNORE_NAME).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)
    return stripped.splitlines() == baseline_text.splitlines()


def delivery_present(workspace: Path, base_sha: str) -> tuple[bool | None, str]:
    """Did this arm produce a DELIVERY at all -- True, False, or NOT ESTABLISHED.

    Deliberately separate from `examine`'s verdict, and owned here because
    acceptance is the only actor that sees an arm's workspace before it judges
    it. `admission_verdict.Delivery` already separates NO_DELIVERY from
    DELIVERED_REJECTED and refuses to infer either from the presence of an
    `accepted` field; until this function existed nothing ever wrote the field
    it reads, so every arm of every campaign resolved UNSCORED.

    Returns `(None, why)` when the fact cannot be established. The caller then
    OMITS the field rather than writing a false one: `_resolve_delivery` reads
    an absent field as UNSCORED (never evaluated) and a present `false` as
    NO_DELIVERY (a finding against the arm), and converting an unknown into a
    finding is the failure mode this tri-state exists to prevent.
    """
    if not (workspace / ".git").is_dir():
        return None, "the workspace is not a git checkout"

    listed = _git(workspace, "diff", "--name-status", "-z", "-M", base_sha)
    if listed is None or listed.returncode not in (0, 1):
        detail = "git could not run" if listed is None else listed.stderr.strip()
        return None, f"`git diff --name-status {base_sha}` failed: {detail}"

    changed: set[str] = set()
    for _status, path, old_path in blind_review._parse_name_status(listed.stdout):
        changed.add(path)
        if old_path:
            changed.add(old_path)

    try:
        entries = blind_review._git_status(workspace)
    except RuntimeError as exc:
        return None, f"could not read this workspace's untracked paths: {exc}"
    changed.update(path for code, path, _old in entries if code == "??")

    delivered = sorted(path for path in changed if not _is_setup_residue(path))
    if _GITIGNORE_NAME in delivered:
        setup_only = _gitignore_is_setup_only(workspace, base_sha)
        if setup_only is None:
            return None, (
                f"{_GITIGNORE_NAME} differs from base {base_sha} and this run "
                "could not establish whether SETUP wrote every differing line"
            )
        if setup_only:
            delivered.remove(_GITIGNORE_NAME)

    if not delivered:
        return False, (
            "no delivery: nothing outside this arm's own setup footprint "
            f"differs from the pinned base {base_sha}"
        )
    head = ", ".join(delivered[:5])
    more = "" if len(delivered) <= 5 else f", +{len(delivered) - 5} more"
    return True, f"{len(delivered)} delivered path(s) vs {base_sha}: {head}{more}"


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

    `pinned_subject_rev`, when given, IS the base commit -- the campaign's
    own declared subject state (see `_base_commit_sha`), not a second
    opinion cross-checked against a derived one. The pair is refused when
    the pin is absent from this workspace's history or unreachable from its
    HEAD, because then this delivery was not built on the state the campaign
    says it measures. `main` passes `scripts.analysis.k4.subject
    .SUT_PINNED_REV` for a real campaign; left `None` (the default) for
    every other caller -- unit tests exercising this function against a
    synthetic workspace have no declared pin to read.
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
    base_sha, base_why = _base_commit_sha(workspace, pinned_subject_rev)
    if base_sha is None:
        return False, (
            f"refused: could not establish this workspace's undelivered base "
            f"commit -- {base_why}; the oracle self-probe (row 2, GDP-8 "
            "witness corollary) cannot run without it, so this pair is "
            "refused rather than scored unproven"
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
        base_sha, base_why = _base_commit_sha(workspace, k4_subject.SUT_PINNED_REV)
        if base_sha is None:
            delivered, delivered_why = None, base_why
        else:
            delivered, delivered_why = delivery_present(workspace, base_sha)
        outcomes.append(
            Outcome(
                payload.stem,
                _session_id(payload),
                accepted,
                evidence,
                delivered,
                delivered_why,
            )
        )
        shown = "NOT-ESTABLISHED" if delivered is None else str(delivered)
        print(
            f"{payload.parent.name}/{payload.stem}: "
            f"delivered={shown} accepted={accepted}",
            flush=True,
        )

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

    verdicts: dict[str, dict[str, object]] = {}
    for o in outcomes:
        if not o.session_id:
            continue
        record: dict[str, object] = {
            "accepted": o.accepted,
            "evidence": o.evidence,
            "scorer": "k4-hidden-acceptance",
        }
        # The third state is an OMISSION, not a fourth value: the reader
        # (`admission_verdict._resolve_delivery`) already maps an absent
        # `delivered` to UNSCORED -- "never established" -- while a present
        # `false` means NO_DELIVERY, which is a finding against the arm.
        if o.delivered is not None:
            record["delivered"] = o.delivered
            record["delivery_evidence"] = o.delivered_evidence
        verdicts[o.session_id] = record
    args.out.write_text(json.dumps(verdicts, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out} — {len(verdicts)} verdicts, session-keyed")
    return 0 if verdicts and not unkeyed else 1


if __name__ == "__main__":
    raise SystemExit(main())
