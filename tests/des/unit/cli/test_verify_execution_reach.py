"""P0.4 execution-reach gate — the observed proofs, pinned as regression.

These three tests ARE the evolution-plan P0.4 done-currency, made permanent:
the gate was proven by execution against a planted defect of its target class
(a throwing scaffold module never executed by the feature's verification —
the class the eval'd seat-booking repo shipped as done), a full-reach case,
and the degrade-LOUD case. Deleting the gate's logic turns these RED.

Hermetic: the Cobertura XML is hand-written inline (a file at 0 hits vs >0
hits) — no pytest-in-pytest, no coverage runner invoked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_execution_reach import main


def _cobertura(src_abs: Path, classes: str) -> str:
    return (
        '<?xml version="1.0" ?>\n'
        '<coverage version="7.0">\n'
        f"  <sources><source>{src_abs}</source></sources>\n"
        '  <packages><package name="."><classes>\n'
        f"{classes}"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )


def _cls(filename: str, hits: int, n_lines: int = 2) -> str:
    lines = "".join(
        f'      <line number="{i + 1}" hits="{hits}"/>\n' for i in range(n_lines)
    )
    return (
        f'    <class name="{filename}" filename="{filename}">'
        f"<methods/><lines>\n{lines}    </lines></class>\n"
    )


def _write_repo(repo: Path, files: dict[str, str]) -> None:
    (repo / "src").mkdir(parents=True)
    for name, body in files.items():
        (repo / "src" / name).write_text(body)


def test_never_executed_scaffold_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: a zero-hit module AND an absent-from-report module.

    dead_scaffold.py appears in the report with every line at 0 hits (the
    throwing-scaffold class); ghost.py does not appear at all (the
    never-wired class). Both must be named RED — never a silent pass.
    """
    repo = tmp_path / "planted"
    _write_repo(
        repo,
        {
            "used.py": "def greet():\n    return 'ok'\n",
            "dead_scaffold.py": "def reconcile():\n    raise RuntimeError('x')\n",
            "ghost.py": "def never_wired():\n    return None\n",
        },
    )
    xml = repo / "coverage.xml"
    xml.write_text(
        _cobertura(
            repo / "src", _cls("used.py", hits=3) + _cls("dead_scaffold.py", hits=0)
        )
    )

    exit_code = main(
        ["--coverage-xml", str(xml), "--src-dir", "src", "--repo", str(repo)]
    )

    assert exit_code == 1
    event = json.loads(capsys.readouterr().out.splitlines()[0])
    assert event["event"] == "ExecutionReachRefused"
    assert all(k in event for k in ("what", "why", "how"))
    unreached = {u["file"]: u["reason"] for u in event["unreached"]}
    assert unreached == {
        "src/dead_scaffold.py": "zero-hits",
        "src/ghost.py": "absent-from-report",
    }


def test_full_reach_tree_is_verified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE proof: every production file executed >0 times -> exit 0.

    Includes an empty __init__.py reported with zero executable lines —
    vacuously reached, not a false RED.
    """
    repo = tmp_path / "clean"
    _write_repo(
        repo,
        {
            "__init__.py": "",
            "used.py": "def greet():\n    return 'ok'\n",
            "dead_scaffold.py": "def reconcile():\n    raise RuntimeError('x')\n",
        },
    )
    xml = repo / "coverage.xml"
    xml.write_text(
        _cobertura(
            repo / "src",
            _cls("__init__.py", hits=0, n_lines=0)
            + _cls("used.py", hits=3)
            + _cls("dead_scaffold.py", hits=1),
        )
    )

    exit_code = main(
        ["--coverage-xml", str(xml), "--src-dir", "src", "--repo", str(repo)]
    )

    assert exit_code == 0
    event = json.loads(capsys.readouterr().out.splitlines()[0])
    assert event["event"] == "ExecutionReachVerified"
    assert event["files"] == 3


def test_missing_coverage_xml_degrades_loud_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: no report -> exit 2 with what/why/how, never a pass."""
    repo = tmp_path / "noreport"
    _write_repo(repo, {"used.py": "def greet():\n    return 'ok'\n"})

    exit_code = main(
        [
            "--coverage-xml",
            str(repo / "nonexistent.xml"),
            "--src-dir",
            "src",
            "--repo",
            str(repo),
        ]
    )

    assert exit_code == 2
    event = json.loads(capsys.readouterr().out.splitlines()[0])
    assert event["event"] == "ExecutionReachIndeterminate"
    assert all(k in event for k in ("what", "why", "how"))
