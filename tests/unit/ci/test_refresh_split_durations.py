"""CI phase records become pytest-split timing input without xdist duplication."""

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/ci/refresh_split_durations.py"


def test_refresh_sums_phases_but_not_controller_worker_duplicates(tmp_path):
    records = [
        {"nodeid": "tests/test_a.py::test_a", "when": phase, "duration": duration}
        for phase, duration in [("setup", 1.0), ("call", 4.0), ("teardown", 0.5)]
    ]
    source = tmp_path / "records.jsonl"
    source.write_text("\n".join(json.dumps(record) for record in records * 2))
    output = tmp_path / ".test_durations"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--records",
            str(source),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == {"tests/test_a.py::test_a": 5.5}


def test_newer_artifacts_override_baseline_and_unknown_tests_remain_absent(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(
        json.dumps(
            {
                "nodeid": "tests/test_a.py::test_a",
                "when": "call",
                "duration": 99,
            }
        )
    )
    records = tmp_path / "records.jsonl"
    records.write_text(
        json.dumps(
            {
                "nodeid": "tests/test_b.py::test_b",
                "when": "call",
                "duration": 7,
            }
        )
    )
    allure = tmp_path / "allure"
    allure.mkdir()
    for name in ("test_a", "test_b"):
        (allure / f"{name}-result.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "start": 1000,
                    "stop": 4000,
                    "labels": [{"name": "package", "value": f"tests.{name}"}],
                }
            )
        )
    nodeids = tmp_path / "nodeids.json"
    nodeids.write_text(
        json.dumps(
            [
                "tests/test_a.py::test_a",
                "tests/test_b.py::test_b",
                "tests/test_unknown.py::test_unknown",
            ]
        )
    )
    output = tmp_path / ".test_durations"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline",
            str(baseline),
            "--records",
            str(records),
            "--allure",
            str(allure),
            "--nodeids",
            str(nodeids),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == {
        "tests/test_a.py::test_a": 3.0,
        "tests/test_b.py::test_b": 7.0,
    }
