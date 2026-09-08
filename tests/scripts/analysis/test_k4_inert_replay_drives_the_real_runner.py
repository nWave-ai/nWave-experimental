"""The frozen model output must carry the REAL steps from Request to examine.

This is the whole claim the replay exists to support, and a unit test cannot
make it: the deterministic layer -- role invocation, handovers, the architect's
declared targets, candidate construction in an ephemeral worktree, native
verification -- only runs when the real DES runs. With the recorded envelopes on
PATH it runs at zero spend.

WHAT DRIVES IT, AND WHY THAT CHANGED. ADR-SSOT-002 Section 4b retires
`des dispatch` as an orchestrator: «No executor in the software composes the
steps. No code path calls one step and then calls the next.» So this test is the
orchestrator. It invokes one step, reads the `NEXT` line that step printed, and
invokes what it names -- which is also how the canonical order is asserted, as
DATA the steps hand over rather than as a list this file keeps in sync with
them.

WHAT THIS TEST DOES **NOT** CLAIM. It does not claim a Success. The recorded
examiner turn rejected its candidate (see the case's README), so a faithful
replay stops at `des verify`. A replay that closed Success would mean an
envelope no model produced, which is the one failure mode a replay must not
have. `ExamineRejected` here IS the replay working: every earlier step ran.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.analysis.k4 import inert_claude


pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLED_CASE = (
    Path(inert_claude.__file__).resolve().parent
    / "replay"
    / inert_claude._DEFAULT_REPLAY_CASE
)
BASE_COMMIT = (BUNDLED_CASE / "base-commit.txt").read_text(encoding="utf-8").split()[0]

#: Every role a stepped run buys for one delivered value, in the order the steps
#: buy them. READ OFF THE RUNNER rather than assumed: `des oracle` buys the
#: acceptance author alone -- `oracle_value` authors, measures the set RED and
#: records the turn, with no pre-craft judge, which is ADR-DES-003 Section 2.4
#: («the record is written on RED, no judge») as delivered -- and `des verify`
#: buys the whole-diff reviewer and the source-blind examiner. The retirement of
#: the composition did not take a role out of this list: it removed aggregate
#: methods only the composer could reach.
EXPECTED_ROLES = (
    "nw-product-owner",
    "nw-solution-architect",
    "nw-acceptance-designer",
    "nw-software-crafter",
    "nw-software-crafter-reviewer",
    "nw-user-examiner",
)

#: The roles whose recorded turn comes from run 17, the run the walk's own
#: earlier turns reproduce. The other two were recorded in a different run whose
#: earlier turns differ, so their questions are not comparable -- see the case's
#: README provenance table.
FROM_RUN_17 = (
    "nw-product-owner",
    "nw-solution-architect",
    "nw-acceptance-designer",
    "nw-software-crafter",
)

#: The steps this orchestrator expects to be walked to, in order. Asserted as a
#: whole rather than step by step, because what is under test is that the DES
#: names the canonical order correctly as data -- not that this file remembers
#: it.
EXPECTED_STEPS = ("po", "design", "oracle", "craft", "verify")

#: The one step whose input is the Request itself.
READS_STDIN = "po"

#: How many invocations the orchestrator will make before it declares the walk
#: unterminated. A ceiling, never a schedule: the walk stops on the first step
#: that does not succeed, and this only stops a `NEXT` cycle from hanging.
STEP_CEILING = 12

_SHIM = """#!/usr/bin/env python3
import runpy
import sys

sys.argv[0] = "claude"
runpy.run_path({target!r}, run_name="__main__")
"""


#: How `DeliveryContinuationRunner._prompt` frames one dynamic fact: the key,
#: a colon, and the fact as exactly one JSON value.
_REQUEST_FRAMING = "request: "


def _recorded_request() -> str:
    """The Request the recorded run was given, recovered from the turn it framed.

    The record stores the PROMPT, which is the runner's framing of the Request,
    not the Request. Feeding that framed prompt back in as stdin makes the runner
    frame it a second time, and the first turn then receives a prompt the
    recorded run never saw -- measured 910 bytes against the recorded 894. The
    replay would still be faithful in its ANSWERS and quietly unfaithful in its
    QUESTIONS, which is the half a replay is least able to notice.
    """
    prompt = json.loads(
        (BUNDLED_CASE / "01-nw-product-owner.json").read_text(encoding="utf-8")
    )["prompt"]
    assert prompt.startswith(_REQUEST_FRAMING), prompt[:80]
    return json.loads(prompt[len(_REQUEST_FRAMING) :])


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _next_forms(terminal: str) -> list[list[str]]:
    """Every `NEXT` line of a terminal, as the argv it would be invoked with.

    A `NEXT` line carries the exact invocation form and may carry a ` -- ` tail
    explaining what the step needs; the tail is prose for the reader, so it is
    cut here rather than passed to argparse. What is left is split with `shlex`,
    the same way a shell would, and the leading `des` is dropped because this
    test reaches the CLI in process rather than through the console script.
    """
    forms = []
    for line in terminal.splitlines():
        if not line.startswith("NEXT: "):
            continue
        form = line[len("NEXT: ") :].split(" -- ", 1)[0].strip()
        words = shlex.split(form)
        if words and words[0] == "des":
            forms.append(words[1:])
    return forms


@pytest.fixture(scope="module")
def subject(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway clone checked out at the tree the recorded candidate applies to."""
    root = tmp_path_factory.mktemp("replay-subject") / "subject"
    cloned = _git(REPO_ROOT, "clone", "--quiet", "--local", str(REPO_ROOT), str(root))
    if cloned.returncode != 0:
        pytest.skip(f"cannot clone this repository: {cloned.stderr.strip()}")
    checked_out = _git(root, "checkout", "--quiet", "--detach", BASE_COMMIT)
    if checked_out.returncode != 0:
        pytest.skip(
            f"the replay case pins base commit {BASE_COMMIT}, which this clone "
            f"cannot reach ({checked_out.stderr.strip()}); re-record the case "
            "from a fresh run rather than re-rolling its patches"
        )
    _git(root, "config", "user.name", "Replay Probe")
    _git(root, "config", "user.email", "replay-probe@localhost")
    return root


@pytest.fixture(scope="module")
def walked(subject: Path, tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One orchestrated walk of the steps, driven by the recorded envelopes.

    Zero spend. The walk follows each terminal's own `NEXT` line, so the order
    it produces is the DES's answer and not this test's opinion of it.
    """
    scratch = tmp_path_factory.mktemp("replay-run")
    shim_dir = scratch / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "claude"
    shim.write_text(
        _SHIM.format(target=str(Path(inert_claude.__file__).resolve())),
        encoding="utf-8",
    )
    shim.chmod(0o755)
    ledger = scratch / "ledger.jsonl"
    environment = {
        **os.environ,
        # The shim FIRST, then the interpreter's own bin so the formatter
        # the repository declares stays reachable: a delivery that cannot
        # reach `ruff` refuses with `FormatContractUnreachable` long before
        # the examine step, which would look like a replay defect and is not.
        "PATH": os.pathsep.join(
            (str(shim_dir), str(Path(sys.executable).parent), os.environ["PATH"])
        ),
        "CLAUDE_CONFIG_DIR": str(scratch / "config"),
        "K4_INERT_CLAUDE_LEDGER": str(ledger),
    }

    def invoke(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "des.cli", *argv],
            input=_recorded_request() if argv[0] == READS_STDIN else "",
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
            cwd=str(REPO_ROOT),
            env=environment,
        )

    projection = invoke(["state", "--repo-root", str(subject)])
    if projection.returncode == 2 and "invalid choice" in (
        projection.stderr + projection.stdout
    ):
        pytest.skip(
            "the `des` this interpreter resolves carries no step surface, so "
            "there is nothing to orchestrate: ADR-SSOT-002 Section 4b's steps "
            "(`des state`, `des po`, `des design`, `des oracle`, `des craft`, "
            "`des verify`, `des integrate`) are owned by another lane and are "
            f"not in this projection. Resolved: {projection.stderr.strip()[:200]}"
        )

    walk: list[dict] = []
    pending = _next_forms(projection.stdout)
    while pending and len(walk) < STEP_CEILING:
        argv = pending[0]
        done = invoke(argv)
        walk.append(
            {
                "step": argv[0],
                "argv": argv,
                "returncode": done.returncode,
                "stdout": done.stdout,
                "stderr": done.stderr,
            }
        )
        if done.returncode != 0:
            break
        pending = _next_forms(done.stdout)

    records = [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {"projection": projection.stdout, "walk": walk, "records": records}


def test_the_projection_names_the_first_step_and_never_the_composer(
    walked: dict,
) -> None:
    """The walk starts where the DES says it starts, in an invocable form."""
    forms = _next_forms(walked["projection"])

    assert [form[0] for form in forms] == ["po"]
    # The claim is about the STEP VOCABULARY the projection names, so it is
    # decided on the invocation forms and on the composer's own invocation
    # string -- never on the bare word, which a workspace path may legitimately
    # carry (this lane's own directory does).
    assert "dispatch" not in {form[0] for form in forms}
    assert "des dispatch" not in walked["projection"]


def test_the_steps_walk_the_canonical_order_they_themselves_name(
    walked: dict,
) -> None:
    """Nothing composed them: each step was reached by reading the last NEXT."""
    assert tuple(entry["step"] for entry in walked["walk"]) == EXPECTED_STEPS


def test_every_declared_role_is_answered_from_a_recorded_turn(walked: dict) -> None:
    assert tuple(r["role"] for r in walked["records"]) == EXPECTED_ROLES


def test_the_turns_of_the_recorded_run_are_asked_the_recorded_question(
    walked: dict,
) -> None:
    """Same answers is half a replay; the other half is the same QUESTION.

    The ledger carries both digests per turn -- what the runner asked this time
    and what the recorded turn was asked -- precisely so this can be asserted
    instead of believed. Only the roles that come from run 17 are compared: the
    last two were recorded in a different run, whose earlier turns differ, so
    demanding equality there would assert something the case does not claim.

    The digest covers the QUESTION, not the whole prompt: the runner also states
    the absolute root the turn runs in, and a replay runs in a different
    directory than the recording did. Holding those facts equal would demand the
    replay happen in the recorded checkout, which no replay can do; every other
    byte is still compared exactly.
    """
    from_run_17 = [r for r in walked["records"] if r["role"] in FROM_RUN_17]

    divergent = [
        record["role"]
        for record in from_run_17
        if record["question_sha256"] != record["recorded_question_sha256"]
    ]

    assert divergent == []


def test_the_replay_spends_nothing(walked: dict) -> None:
    assert [r["spend_usd"] for r in walked["records"]] == [0.0] * len(EXPECTED_ROLES)


def test_native_verification_really_ran_inside_the_candidate_worktree(
    walked: dict,
) -> None:
    """The step a fixture cannot fake: real pytest, real candidate, real interpreter."""
    verify = walked["walk"][-1]
    native = [
        line
        for line in verify["stderr"].splitlines()
        if line.startswith("NATIVE-RUNTIME: ")
    ]

    assert native, verify["stderr"]
    assert "candidate=" in native[0]


def test_the_walk_stops_at_verify_on_the_recorded_verdict(walked: dict) -> None:
    """`ExamineRejected` is the recorded judgment, so every step before it ran."""
    verify = walked["walk"][-1]
    what = [line for line in verify["stdout"].splitlines() if line.startswith("WHAT: ")]

    assert verify["step"] == "verify"
    assert verify["returncode"] != 0
    assert what and what[0].startswith("WHAT: ExamineRejected on candidate "), verify[
        "stdout"
    ]


def test_the_refusing_step_leaves_the_next_move_to_the_orchestrator(
    walked: dict,
) -> None:
    """Section 4b: a refusal names every available move and ranks none.

    The composed run answered a refusing examiner itself. Invoked alone the step
    stops and prints the moves, so more than one `NEXT` is the observable
    difference between the two shapes.
    """
    forms = _next_forms(walked["walk"][-1]["stdout"])

    assert len(forms) > 1, walked["walk"][-1]["stdout"]
    assert any(form[0] == "integrate" for form in forms)


# The composed run's own aggregate -- `num_turns` and `total_cost_usd` summed
# across a whole Request -- was asserted here until 2026-09-06. It is deleted
# rather than rewritten: ADR-DES-003 Section 11 classes «one whole-Request
# disposition (the totalizer)» as a COMPOSER property and records it as «gone;
# was the defect». No step computes it, so there is no equivalent step property
# to move the assertion onto. What survives of it is per-turn and is asserted
# above, in `test_the_replay_spends_nothing`.
