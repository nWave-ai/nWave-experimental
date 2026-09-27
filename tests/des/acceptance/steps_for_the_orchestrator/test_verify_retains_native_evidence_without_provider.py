"""Public oracle for the separate native-verify boundary.

`des verify` first constructs a candidate and runs its declared native command.
That observation is sufficient for this command: review and source-blind
examination are host choices which consume candidate-bound artifacts later.

The environment for the final command deliberately contains only Git and
Python.  Thus a passing scenario proves both that native verification does not
resolve a model provider and that no provider process was bought accidentally.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    accepted_values,
    asked,
    block,
)


REQUEST = "one Request whose native evidence must outlive provider-free verify"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
RED_ORACLE = (
    "import pathlib\nimport sys\n\n\ndef test_value():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n\n    assert VALUE == 1\n"
)


def _crafted(root: Path, step, *, verification: list[list[str]] | None = None) -> None:
    """Reach a real crafted state through explicit, pre-existing public steps."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "bound the typed facts for native verification",
                        "design_facts": {
                            "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                            "paradigm": "object_oriented",
                            "decisions": ["one observable value"],
                            "oracle": ORACLE,
                            "acceptance_supports": [SUPPORT],
                            "verification": verification
                            or [[sys.executable, "-m", "pytest", ORACLE]],
                            "oracle_verification_index": 0,
                        },
                    }
                }
            ],
        )[0]
        == 0
    )
    assert (
        step(
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored a red acceptance oracle",
                    },
                    "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
                },
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "the oracle set is admissible",
                    }
                },
            ],
        )[0]
        == 0
    )
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value behind its oracle",
                    },
                    "writes": {TARGET: "VALUE = 1\n"},
                }
            ],
        )[0]
        == 0
    )


def _native_only_environment(directory: Path) -> dict[str, str]:
    """An execution PATH that can run the declared native argv, never a model."""
    directory.mkdir()
    git = shutil.which("git")
    assert git is not None
    (directory / "git").symlink_to(git)
    # The design-declared argv spells `python`; the host running this oracle
    # may provide only `python3`, so expose the executing interpreter by that
    # declared name without admitting any model launcher.
    (directory / "python").symlink_to(Path(sys.executable))
    return {"PATH": str(directory), "PYTHONPATH": str(PACKAGE_PARENT)}


def test_verify_succeeds_without_a_provider_and_retains_the_native_observation(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    _crafted(root, step)
    turns_before_verify = asked(turns)

    code, out, err = run_cli_in_process(
        ["verify", "--repo-root", str(root)],
        cwd=root,
        env=_native_only_environment(tmp_path / "native-bin"),
        catch_all=True,
    )

    assert code == 0, out + err
    lines = block(out, err)
    candidate = lines["CANDIDATE"]
    assert len(candidate) == 40
    # The test setup bought its own explicit turns. Verify bought none: the
    # absence of a launcher is itself a counterexample to accidental review or
    # EXAMINE invocation, rather than a fake-port accounting assertion.
    assert asked(turns) == turns_before_verify

    records = list(
        (root / ".nwave" / "des" / "logs" / "native").glob(f"{candidate}-*.json")
    )
    assert len(records) == 1
    evidence = json.loads(records[0].read_text(encoding="utf-8"))
    assert len(evidence) == 1
    assert evidence[0]["argv"] == [sys.executable, "-m", "pytest", ORACLE]
    assert evidence[0]["exit"] == 0
    assert "1 passed" in evidence[0]["stdout"]
