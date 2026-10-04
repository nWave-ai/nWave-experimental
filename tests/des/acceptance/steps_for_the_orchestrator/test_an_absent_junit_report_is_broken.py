"""Public oracle: a pytest vector ASKED for a junit report and given none is broken.

THE INCIDENT THIS REFUSES. `des oracle` requests `--junitxml=<report>` through
the environment of declared Python vectors, then reads the report to tell a
genuine assertion failure from an oracle that never reached its own assertion.
When the vector names an interpreter that carries no pytest, the process exits
`1` with `No module named pytest` and writes NO report -- and exit-status-only scored that `red`, the
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
4. WRAPPER CONTROL -- a declared Python vector whose argv names no pytest yet
   reaches pytest through a wrapper still produces an authentic report and is
   judged on it. A produced report is always judged; absence is damning where
   pytest or an explicit report output was declared. Genuinely native vectors
   receive no Python runtime preparation or pytest option injection.

THE PYTEST-LESS INTERPRETER IS BUILT, NEVER FOUND. Depending on a host `python3`
or on `PATH` order would measure the developer's box instead of the law.
"""

from __future__ import annotations

import json
import sys
import venv
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    git,
    nexts,
)


REQUEST = "one Request whose single value carries an executable public oracle"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
WRAPPER = "tests/acceptance/wrap.py"
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
    """An explicitly Python wrapper whose argv never names pytest.

    Keep only the runner's report request, not outer-session pytest plugins.
    The inherited product import path remains intact across the real exec.
    """
    return (
        "import os\n"
        "import shlex\n"
        "import sys\n"
        "os.environ['PYTEST_ADDOPTS'] = shlex.join([\n"
        "    word for word in shlex.split(os.environ.get('PYTEST_ADDOPTS', ''))\n"
        "    if word.startswith('--junitxml=')\n"
        "])\n"
        "os.execv(sys.executable, [sys.executable, '-m', 'pytest', *sys.argv[1:], '-q'])\n"
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
                "architectural_tests": {
                    "applicability": "not_applicable",
                    "reason": "The fixture has no structural boundary change.",
                },
                "contract_tests": {
                    "applicability": "not_applicable",
                    "reason": "The fixture changes no shared contract.",
                },
                "prefactoring": {
                    "applicability": "not_applicable",
                    "reason": "The fixture requires no preservation move.",
                },
                "agreement_analysis": {
                    "applicability": "not_applicable",
                    "reason": "The fixture has no affected agreement.",
                },
                "reuse_analysis": {"candidates": []},
                "impact_closure": {
                    "applicability": "not_applicable",
                    "reason": "The fixture reaches no public surface, consumer or build metadata.",
                },
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
    """A declared Python wrapper preserves import lineage and its real report."""
    module = root / "src" / "existing_answer.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("ANSWER = 41\n")
    git(root, "add", "src/existing_answer.py")
    git(root, "commit", "-qm", "Existing product imported through the wrapper")
    code, out, err = run_oracle(
        root,
        step,
        [[sys.executable, WRAPPER, ORACLE]],
        authored(
            "def test_value():\n"
            "    from existing_answer import ANSWER\n"
            "    assert ANSWER == 42\n",
            {WRAPPER: wrapper_body()},
        ),
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success", lines
    assert "axis=junit-report" in lines["ORACLE-RED"], lines["ORACLE-RED"]
    assert "axis=junit-report-absent" not in lines["ORACLE-RED"], lines["ORACLE-RED"]
    locator = (
        lines["ORACLE-RED"]
        .split(" native-evidence=", 1)[1]
        .split(" diagnostic=", 1)[0]
        .strip()
    )
    record = json.loads((root / locator).read_text())[0]
    assert record["argv"] == [sys.executable, WRAPPER, ORACLE]
    assert record["exit"] == 1
    assert "assert 41 == 42" in record["stdout"], record


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
