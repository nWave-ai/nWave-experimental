"""Characterization AT -- `des parallel-safety-report` UNMEASURED (slice-02).

CHARACTERIZATION TEST -- NO RED PHASE (by explicit human decision, 2026-07-20).
The UNMEASURED verdict path (blast-radius timeout -> honest do-not-know, D-4) was
shipped INSIDE slice-01 (commit fe43d162) as a dormant seam: the domain type
`SliceUnmeasured`, the application short-circuit in `run_parallel_safety_report`,
the subprocess adapter's `TimeoutExpired -> SliceUnmeasured` mapping, and the CLI
`--timeout` + `UNMEASURED -> INDETERMINATE (❓)` face already exist and work
end-to-end. slice-01's own AT deliberately EXCLUDED UNMEASURED (it is slice-02).
Because the behaviour already exists and was verified empirically (a forced
`--timeout 0.001` emits the full UNMEASURED verdict), the standard atdd_pure
RED->GREEN cycle is not applicable here: there is no implementation to drive, so
this test cannot be sealed RED. It is a CHARACTERIZATION test -- it PINS the
pre-existing behaviour so the dormant seam becomes a covered, attested seam. The
real attestation of the behaviour is the EXAMINE verdict (Vera) on the slice-02
charter; this test is the permanent regression net beside it.

Charter (slice-02): docs/product/expectations/measured-parallel-safety-report/
  a-maintainer-gets-honest-unmeasured-never-a-coerced-guess.md

Oracle pinned here (charter-2 "Expected observations"):
  * a slice whose `des blast-radius` measurement times out is reported UNMEASURED,
    NAMING the file it could not measure;
  * UNMEASURED is visibly distinct from MEASURED-SAFE (❓ vs ✅) -- "I could not
    look" reads apart from "I looked and it is disjoint";
  * the report still advises (exit 0), it does not crash or refuse on the timeout;
  * (negative) the timed-out slice is NEVER coerced to MEASURED-SAFE (no false
    confidence) NOR to DRIFT (no false alarm), and is NEVER silently dropped.

The subprocess drives the REAL installed `des` CLI + REAL `des blast-radius`
(mirroring slice-01's walking skeleton); a trivially small `--timeout` forces the
blast-radius subprocess past its wall-clock budget, exercising the real
`TimeoutExpired -> SliceUnmeasured` path rather than a faked measurement.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_git_repo(root: Path, files: dict[str, str]) -> None:
    """A real git work-tree with the given tracked {relpath: content} files."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for relpath, content in files.items():
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


_PLAN_ROWS = [
    "| slice-02 | Maintainer measures the pricing slice for independence. "
    "| pending | @walking_skeleton | Thinnest end-to-end vertical over the "
    "declared plan. |",
    "| slice-03 | Maintainer measures the orders-summary slice for independence. "
    "| pending |  | Second declared-parallel row read from the same plan. |",
    "| slice-04 | Maintainer extends the report with a degraded branch. "
    "| pending | depends-on slice-03 | Depends on slice-03: extends the "
    "verdict-emission surface slice-03 builds. |",
]


def _write_feature_delta(root: Path, plan_rows: list[str]) -> Path:
    header = (
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|----------------|\n"
    )
    body = "\n".join(plan_rows) + "\n"
    content = (
        textwrap.dedent(
            """\
        # Feature Delta -- fixture

        ## Wave: DISCUSS / [REF] Slice Plan

        """
        )
        + header
        + body
    )
    path = root / "feature-delta.md"
    path.write_text(content, encoding="utf-8")
    return path


def _last_json_line(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a single-line JSON event on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def test_parallel_safety_report_characterizes_a_timed_out_slice_as_unmeasured(
    tmp_path: Path,
) -> None:
    """CHARACTERIZATION: pins the pre-existing UNMEASURED behaviour (slice-01 seam).

    A declared-parallel slice whose `des blast-radius` measurement cannot complete
    within the wall-clock budget is reported UNMEASURED, naming the un-measurable
    file, advisory (exit 0), visibly distinct from MEASURED-SAFE, and never coerced
    to a clean verdict nor dropped.
    """
    des_binary = shutil.which("des")
    assert des_binary is not None, (
        "the `des` console-script must be on PATH for this characterization "
        "subprocess AT to run -- if this fails, the dev environment install is the "
        "problem, not this AT"
    )

    repo = tmp_path / "repo"
    _init_git_repo(
        repo,
        {
            "ranking.py": "def rank():\n    return 1\n",
            "orders_summary.py": "def summary():\n    return 2\n",
        },
    )
    feature_delta = _write_feature_delta(repo, _PLAN_ROWS)

    completed = subprocess.run(
        [
            des_binary,
            "parallel-safety-report",
            "--feature-delta",
            str(feature_delta),
            "--repo",
            str(repo),
            "--timeout",
            "0.001",
            "--scope",
            "slice-02=ranking.py",
            "--scope",
            "slice-03=orders_summary.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    # Advisory (D-2): a timeout is a report line, NEVER a refusal -- exit 0.
    assert completed.returncode == 0, (
        "UNMEASURED is ADVISORY -- a timeout does not crash or refuse the plan; "
        f"got exit={completed.returncode} stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "ParallelSafetyReport"
    # The verdict is UNMEASURED -- honest do-not-know.
    assert payload["verdict"] == "UNMEASURED"
    # Negative: NEVER coerced to a clean verdict (no false confidence / false alarm).
    assert payload["verdict"] != "MEASURED-SAFE"
    assert payload["verdict"] != "DRIFT"
    # UNMEASURED NAMES the un-measurable file, and does NOT silently drop the slice.
    unmeasured = payload["unmeasured"]
    assert unmeasured["slice"] == "slice-02"
    assert "ranking.py" in unmeasured["paths"]
    assert "ranking.py" in " ".join(payload["reasons"])
    # Distinct human face: UNMEASURED -> ❓ INDETERMINATE (absence-vs-incapacity),
    # NOT the ✅ of MEASURED-SAFE nor the ⚠️ of DRIFT.
    assert "❓" in completed.stderr
    assert "✅" not in completed.stderr
    assert "⚠️" not in completed.stderr
