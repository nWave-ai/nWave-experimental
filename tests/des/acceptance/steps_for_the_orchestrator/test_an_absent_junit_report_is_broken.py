"""Public oracle: a pytest vector ASKED for a junit report and given none is broken.

THE INCIDENT THIS REFUSES. `des oracle` appends `--junitxml=<report>` to every
vector it executes, then reads the report to tell a genuine assertion failure
from an oracle that never reached its own assertion. When the vector names an
interpreter that carries no pytest, the process exits `1` with `No module named
pytest` and writes NO report -- and exit-status-only scored that `red`, the
ADMITTED answer, so the false RED bought a craft turn against an oracle whose
assertions were never observed (EVIDENCE.md row 6, measured against the
unmodified product).

WHAT IS MEASURED HERE, through the one public port and nothing else: `des po`,
`des design` carrying the verification vector, `des oracle`. Four arms, because
the value is a boundary and a boundary needs both of its sides:

1. THE INCIDENT -- a pytest vector under a pytest-less interpreter is `broken`
   on axis `junit-report-absent` whatever the exit status, refused before a
   craft turn is bought, with a WHAT/WHY/HOW an operator can act on.
2. NON-PYTEST CONTROL -- a vector that asks for nothing keeps `exit-status-only`
   and stays ADMITTED. This arm is the one that fails if the new branch is
   written on «no report» instead of on «a report was asked for».
3. REPORT CONTROL -- a pytest vector that DOES produce a report keeps
   `junit-report` and its verdicts.
4. WRAPPER CONTROL -- a vector whose argv names no pytest yet reaches pytest
   through the inherited variable still produces a report and is still judged on
   it. The request stays broader than the judgement, deliberately: a produced
   report is always judged, an absent one is damning only where the runner can
   see it asked. The wrapper narrows the inherited variable to the runner's own
   `--junitxml=` word, so the arm measures that ask and never the options of
   whatever outer session happens to be executing this oracle.

THE PYTEST-LESS INTERPRETER IS BUILT, NEVER FOUND. Depending on a host `python3`
or on `PATH` order would measure the developer's box instead of the law.
"""

from __future__ import annotations

import sys
import venv
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "one Request whose single value carries an executable public oracle"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
WRAPPER = "tests/acceptance/wrap.sh"
TARGET = "src/product/value.py"

#: An oracle that FAILS on its own assertion, which is the admitted answer before
#: any production byte exists: the import is inside the test body, so a pytest
#: session records one FAILURE and zero errors.
RED_ORACLE = "def test_value():\n    import product.value  # noqa\n"
#: The same observation as a plain journey: the import is at module level, so
#: running the file as a script exits non-zero without any pytest session.
JOURNEY_ORACLE = (
    "import product.value  # noqa\n\n\ndef test_value():\n    assert False\n"
)


def wrapper_body() -> str:
    """A vector whose argv names no pytest and which nonetheless runs pytest.

    The interpreter is BAKED IN rather than read from the environment: this
    script's whole job is to be unrecognisable to the runner's argv predicate
    while still reaching a real pytest session, and an interpreter resolved off
    `PATH` inside the child would make the arm measure the host instead.

    THE INHERITED VARIABLE IS NARROWED TO THE ASK, and this is the arm's premise
    rather than a convenience.  `_executed_oracle_set` CONCATENATES the runner's
    `--junitxml=<report>` onto whatever `PYTEST_ADDOPTS` the OUTER session
    already exported, so a wrapper that forwards the variable whole also
    forwards the outer session's own options -- e.g. a `-p <plugin>` naming a
    probe that is importable only under the outer interpreter.  That kills the
    inner session before it starts and the arm would then measure the harness
    that happens to be running it, not the law.  Keeping ONLY the
    `--junitxml=` word preserves exactly what this control asserts -- the
    runner's ask reaching a session whose argv names no pytest, and a report
    produced from it -- while making the arm indifferent to who invoked it.
    """
    return (
        "#!/bin/sh\n"
        "kept=''\n"
        "for word in $PYTEST_ADDOPTS; do\n"
        '  case "$word" in --junitxml=*) kept="$kept $word" ;; esac\n'
        "done\n"
        'PYTEST_ADDOPTS="$kept"\n'
        "export PYTEST_ADDOPTS\n"
        f'exec "{sys.executable}" -m pytest "$@" -q\n'
    )


def design_facts(verification: list[list[str]]) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": verification,
                "oracle_verification_index": 0,
            },
        }
    }


def authored(body: str, extra: dict[str, str] | None = None) -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": "authored"},
        "writes": {ORACLE: body, SUPPORT: "MARKER = 1\n", **(extra or {})},
    }


def bound(root: Path, step, verification: list[list[str]]) -> None:
    """Decompose and bind, so the value carries the vector this arm measures."""
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[design_facts(verification)],
    )
    assert code == 0, out + err


def run_oracle(root: Path, step, verification: list[list[str]], answer: dict):
    bound(root, step, verification)
    return step("oracle", "--repo-root", str(root), "--value", "1", answers=[answer])


def turn_refs(root: Path) -> list[str]:
    listed = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")
    return [line for line in listed.splitlines() if line]


@pytest.fixture
def pytest_less_python(tmp_path: Path) -> str:
    """A real interpreter that carries no pytest, BUILT from this one.

    `with_pip=False` keeps it empty and fast (measured 0.02 s); `symlinks=True`
    keeps it a genuine interpreter rather than a copied shell. Its
    `-m pytest` answers exit 1 `No module named pytest`, which IS the incident.
    """
    home = tmp_path / "nopytest"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(home)
    return str(home / "bin" / "python")


def test_a_pytest_vector_that_produced_no_report_is_broken_and_refused(
    root: Path, step, turns: Path, pytest_less_python: str
) -> None:
    """THE INCIDENT: the runner asked for a report, none exists, nothing observed."""
    code, out, err = run_oracle(
        root,
        step,
        [[pytest_less_python, "-m", "pytest", ORACLE, "-q"]],
        authored(RED_ORACLE),
    )

    assert code == 1, out + err
    lines = block(out, err)
    assert lines["WHAT"] == "OracleNotRed", lines
    assert "verdict=broken" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=junit-report-absent" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "exit=1" in lines["ORACLE-RED"], lines["ORACLE-RED"]

    why = lines["WHY"].lower()
    assert "asked" in why, why
    assert "report" in why, why
    assert "none was produced" in why, why
    assert "did not complete a session" in why, why

    assert "run the printed vector" in lines["HOW"].lower(), lines["HOW"]

    # Refused BEFORE a craft turn is bought, and nothing is settled.
    assert asked(turns)[-1] == "nw-acceptance-designer", asked(turns)
    assert not any(ref.endswith("/oracle") for ref in turn_refs(root)), turn_refs(root)
    assert not any("des craft" in item for item in nexts(out)), nexts(out)


def test_a_vector_that_asked_for_no_report_keeps_exit_status_only(
    root: Path, step, turns: Path
) -> None:
    """CONTROL: no report was asked for, so its absence accuses nothing."""
    code, out, err = run_oracle(
        root, step, [[sys.executable, ORACLE]], authored(JOURNEY_ORACLE)
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success", lines
    assert "verdict=indeterminate" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=exit-status-only" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "exit=1" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert nexts(out) == [f"des craft --repo-root {root} --value 1"], nexts(out)


def test_a_pytest_vector_that_produced_a_report_is_still_judged_on_it(
    root: Path, step, turns: Path
) -> None:
    """CONTROL: a present report keeps the report axis and its four verdicts."""
    code, out, err = run_oracle(
        root,
        step,
        [[sys.executable, "-m", "pytest", ORACLE, "-q"]],
        authored(RED_ORACLE),
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success", lines
    assert "verdict=red" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=junit-report" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=junit-report-absent" not in lines["ORACLE-RED"], lines["ORACLE-RED"]


def test_a_wrapper_vector_naming_no_pytest_still_earns_the_report_axis(
    root: Path, step, turns: Path
) -> None:
    """CONTROL: the request stays broader than the judgement, deliberately.

    This vector's argv names no pytest, so the runner cannot see it ask -- yet
    the runner's `--junitxml=` still reaches the session through the inherited
    variable and a report IS produced. Judging it on anything but that report
    would demote every wrapper spelling to `exit-status-only`, the opposite of
    this value.
    """
    code, out, err = run_oracle(
        root,
        step,
        [["bash", WRAPPER, ORACLE]],
        authored(RED_ORACLE, {WRAPPER: wrapper_body()}),
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success", lines
    assert "axis=junit-report" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=junit-report-absent" not in lines["ORACLE-RED"], lines["ORACLE-RED"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
