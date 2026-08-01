"""Composition root for the charter-obligation ATs.

Every scenario reaches the SUT through a REAL production CLI EDGE
(`des.cli.__main__.main(argv) -> int`), never through a production internal.
Two driving surfaces, and the split is deliberate:

  * `run_des` -- L2 IN-PROCESS acceptance (the DEFAULT). Reuses the shipped
    `tests.common.in_process_cli.run_module_in_process` driver, so no scenario
    forks an interpreter.
  * `run_des_subprocess` -- L1, used by the SINGLE `@walking_skeleton` of this
    feature and by nothing else. It proves the operator's literal terminal
    command produces the durable record; every other scenario is in-process.

Step bodies delegate here; no business logic lives in a step (Mandate 12,
criterion 3).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from des.cli.record_examine_verdict import examine_ledger_path
from tests.common.in_process_cli import run_module_in_process
from tests.des._helpers.commit_slice_git_template import provision_commit_slice_repo


#: tests/des/acceptance/<this dir>/composition.py -> parents[4] is the checkout root.
REPO_ROOT = Path(__file__).resolve().parents[4]

#: The probe feature id MUST NOT contain the word "charter". The rendered
#: envelope echoes the feature id back in its own marker lines
#: (`DES-PROJECT-ID`, `TASK_CONTEXT`), so a charter-bearing id makes the
#: operator-surface oracle in `domain_types.charter_lines` match lines that
#: merely repeat the id -- a false positive that would let "the operator was
#: told about the charter obligation" pass on an entirely silent surface.
FEATURE_ID = "obligation-declared-probe"

#: The DELIVER-scope phase a lane-carrying dispatch must name. `--phase` is
#: REQUIRED unless the lane is phaseless (`charter`) or the wave is an
#: authoring wave (`dispatch.py:1331-1344`).
DELIVER_PHASE = "A_GREEN"

#: The lanes that name NO phase (`des.domain.lane_profile.PHASELESS_LANES`).
PHASELESS_LANES = ("charter",)

#: The bugfix lane's own required companions -- `des dispatch` refuses with
#: "--lane bugfix requires --defect and --regression-test". Supplying them is
#: pre-existing CLI grammar, not part of this feature's contract.
#:
#: Neither value may contain the word "charter": both are rendered VERBATIM
#: into the envelope, and the operator-surface oracle would then match a line
#: that is only echoing this test's own arguments back (same false-positive
#: class as the feature id above).
BUGFIX_LANE_COMPANIONS: tuple[str, ...] = (
    "--defect",
    "the examine gate is silently unarmed by an undeclared lane",
    "--regression-test",
    "test_obligation_is_declared_at_dispatch",
)


def des_env() -> dict[str, str]:
    """Env with `src` importable and the freshness gate silenced.

    Without `NWAVE_FRESHNESS=skip` the CLI prints a `des.runtime.freshness.*`
    JSON line ahead of the payload -- an unrelated cross-cutting concern that
    would confound the stdout assertions here (reused verbatim from
    `tests/bugs/des/test_dispatch_charter_lane_carries_intent.py`).
    """
    env = dict(os.environ)
    src = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def provision_project(root: Path) -> Path:
    """A real git work-tree standing in for the operator's own project.

    Reuses the session-cached `provision_commit_slice_repo` template (six real
    `git` spawns paid ONCE per process, a `copytree` thereafter) rather than
    re-deriving a repo fixture. The project carries no `nWave/dispatch/` of its
    own, so `des dispatch --repo-root <here>` resolves its SSOT through the
    installed-runtime fallback -- the same shape a consuming project has.
    """
    provision_commit_slice_repo(root)
    return root


def run_des(*argv: str, cwd: Path) -> tuple[int, str, str]:
    """Drive the production `des` CLI EDGE IN-PROCESS. Returns (exit, out, err)."""
    return run_module_in_process("des.cli.__main__", *argv, cwd=cwd, env=des_env())


def run_des_subprocess(*argv: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Drive the production `des` CLI in a REAL forked interpreter.

    Reserved for this feature's ONE `@walking_skeleton`. It is the only
    scenario that pays an interpreter fork; every other scenario uses
    `run_des`.
    """
    return subprocess.run(
        [sys.executable, "-m", "des.cli.__main__", *argv],
        cwd=str(cwd),
        env=des_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def dispatch(
    project: Path,
    slice_id: str,
    *,
    lane: str | None = None,
    wave: str | None = None,
    phase: str | None = DELIVER_PHASE,
    extra: tuple[str, ...] = (),
    feature_id: str = FEATURE_ID,
) -> tuple[int, str, str]:
    """Run a real `des dispatch` against ``project`` -- the PRODUCER of the
    declaration.

    ``phase`` defaults to the DELIVER-scope phase the CLI requires
    (`dispatch.py:1331-1344`); pass ``phase=None`` for a PHASELESS lane
    (`charter`) or an AUTHORING wave, neither of which runs a DELIVER phase.
    """
    argv = [
        "dispatch",
        "--mode",
        "atdd_pure",
        "--project-id",
        feature_id,
        "--slice",
        slice_id,
        "--repo-root",
        str(project),
    ]
    if phase is not None and lane not in PHASELESS_LANES:
        argv += ["--phase", phase]
    if lane is not None:
        argv += ["--lane", lane]
    if lane == "bugfix":
        argv += list(BUGFIX_LANE_COMPANIONS)
    if wave is not None:
        argv += ["--wave", wave]
    argv += list(extra)
    return run_des(*argv, cwd=project)


def dispatch_argv_for_subprocess(
    project: Path, slice_id: str, lane: str, feature_id: str = FEATURE_ID
) -> tuple[str, ...]:
    """The literal argv an operator types -- shared by the walking skeleton."""
    return (
        "dispatch",
        "--mode",
        "atdd_pure",
        "--project-id",
        feature_id,
        "--slice",
        slice_id,
        "--phase",
        DELIVER_PHASE,
        "--lane",
        lane,
        *(BUGFIX_LANE_COMPANIONS if lane == "bugfix" else ()),
        "--repo-root",
        str(project),
    )


def commit_slice(
    project: Path, slice_id: str, *, feature_id: str = FEATURE_ID
) -> tuple[int, str, str]:
    """Run a real `des commit-slice` -- the CONSUMER of the declaration."""
    return run_des(
        "commit-slice",
        "--repo",
        str(project),
        "--all",
        "--feature-id",
        feature_id,
        "--message",
        f"feat(slice): behaviour\n\nSlice-Id: {slice_id}",
        cwd=project,
    )


def verify_slice_commit_completeness(
    project: Path, slice_id: str, *, feature_id: str = FEATURE_ID
) -> tuple[int, str, str]:
    """Run the OTHER production consumer of `check_examine_verdict` (OQ-6).

    Registered as the `verify-slice-commit` subcommand
    (`src/des/cli/__main__.py:52-56` -> `des.cli.verify_slice_commit_completeness`).
    It audits a LANDED commit, so it takes `--commit`; `HEAD` names the commit
    the project's own template already carries.
    """
    return run_des(
        "verify-slice-commit",
        "--repo",
        str(project),
        "--commit",
        "HEAD",
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        cwd=project,
    )


def report_charter_obligation_coverage(
    project: Path, *, feature_id: str = FEATURE_ID
) -> tuple[int, str, str]:
    """Run the end-of-feature summary -- the AGGREGATE the third state must reach.

    `des report-delivery-metrics` is the shipped read-side query CLI that
    already degrades LOUD (`status: could-not-verify`, never a silent zero) and
    already carries the `--feature-id` / `--repo-root` plumbing; slice-03
    EXTENDS it with a third `--metric` rather than opening a second read
    surface.
    """
    return run_des(
        "report-delivery-metrics",
        "--feature-id",
        feature_id,
        "--metric",
        "charter-obligation-coverage",
        "--repo-root",
        str(project),
        cwd=project,
    )


def ledger_for(project: Path, feature_id: str = FEATURE_ID) -> Path:
    """The EXISTING examine ledger the declaration lands on (DDD-4)."""
    return examine_ledger_path(project, feature_id)


def emitted_events(stdout: str, stderr: str) -> list[dict[str, object]]:
    """Every JSON object the CLI emitted, on either stream, in order."""
    events: list[dict[str, object]] = []
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
    return events


def event_named(events: list[dict[str, object]], name: str) -> dict[str, object] | None:
    """The LAST emitted event whose `event` field is ``name``, or None."""
    matches = [record for record in events if record.get("event") == name]
    return matches[-1] if matches else None
