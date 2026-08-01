# @feature-measured-parallel-safety-report
"""Acceptance tests -- `des parallel-safety-report` (DISTILL, slice-01, walking skeleton).

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Slice Plan slice-01 row; DESIGN [REF] Contract Tests CT-1..CT-11;
  DESIGN [REF] Driving Ports; DESIGN [REF] Decisions Table DA/DE/DF/DH;
  Reuse Analysis -- New components).
Charter: docs/product/expectations/measured-parallel-safety-report/
  a-maintainer-sees-a-measured-verdict-on-a-parallel-claim.md (Fixture A / Fixture B).

Slice-01 value (feature-delta Slice Plan): a maintainer runs the parallel-safety
report over a feature-delta whose Slice Plan declares two rows parallel-safe (no
`depends-on`), supplies each declared-parallel row's touched paths via
`--scope slice-id=<paths>`, and gets a MEASURED verdict per pair:
  - MEASURED-SAFE when the two rows' blast radii (touched files / boundary_files /
    high-fan-in consumer symbols) are disjoint on ALL three axes, or
  - DRIFT when the measured diffs overlap on ANY axis, NAMING the overlapping
    file(s) -- the declaration contradicted by reality, the disagreement the finding.
The verdict is ADVISORY: exit 0 on BOTH verdicts, never a refusal (D-2).
(UNMEASURED is slice-02, CT-6 -- ABSENT from this slice per per-slice JIT.)

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/cli/parallel_safety_report.py::main(argv) -> int`, registered as the
`des parallel-safety-report` subcommand. Grammar (DESIGN [REF] Driving Ports):

    des parallel-safety-report --feature-delta <path> --repo <path>
        --scope <slice-id>=<p1>[,<p2>...]   # EXACTLY TWO for slice-01

stdout token (single-line JSON, DESIGN [REF] Contract Tests "JSON event schema"):
    {"event": "ParallelSafetyReport",
     "verdict": "MEASURED-SAFE" | "DRIFT",           # UNMEASURED is slice-02
     "pair": ["slice-02", "slice-03"],
     "overlap": {"files": [...], "boundary_files": [...], "consumer_symbols": [...]},
     "reasons": [<str>, ...]}                         # overlap non-empty on >=1 axis iff DRIFT

Malformed invocation (exit 2, mirrors blast-radius's `BlastRadiusInputRejected`):
    {"event": "ParallelSafetyInputRejected", "reasons": [<str>, ...]}

Driving surface (F-V5 test-pyramid default, ratified 2026-07-18 /
`nw-distill-port-treatment-policy` inverted driving default):
  * `test_parallel_safety_report_measures_two_disjoint_slices_as_safe`
    (`@walking_skeleton`) is the ONE walking-skeleton subprocess-E2E proving the
    installed `des parallel-safety-report` is wired end-to-end through the REAL
    `des blast-radius` subprocess -- the DoD's "real `des` CLI + real
    `des blast-radius`" anchor (CT-11).
  * `test_parallel_safety_report_measures_two_overlapping_slices_as_drift`
    (`@real-io @driving_port`) is a SECOND subprocess-E2E, EXPLICITLY JUSTIFIED
    against the one-WS-per-feature default: the slice's VALUE *is* the real-
    blast-radius integration, and BOTH the DoD ("DRIFT ... verified end-to-end
    through the real `des` CLI + real `des blast-radius`") AND the charter's
    Fixture B ("DRIFT ... grounded in a real `des blast-radius` measurement")
    demand DRIFT observed through the real surface, not a faked measurement.
    Vera EXAMINEs both fixtures through the real `des` CLI.
  * Every OTHER scenario (the malformed-invocation rejections) drives
    `des.cli.parallel_safety_report.main(argv)` IN-PROCESS (Mandate 13 / L2
    default) -- they reject at --scope validation BEFORE any measurement, so no
    real repo and no blast-radius fork is needed.

State-delta (Mandate 8) is N/A: the SUT is READ-ONLY (Effect Isolation, DESIGN
[REF] Driving Ports -- `run_parallel_safety_report` mutates nothing; the CLI shell
only writes stdout/stderr). The observable is the emitted report (stdout JSON +
exit code + stderr face), asserted traditionally -- there is no mutated observable
state universe. Mirrors the sibling `blast-radius` acceptance suite.

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`src/des/cli/parallel_safety_report.py` does not exist and `parallel-safety-report`
is not a registered `des` subcommand. The subprocess scenarios observe the REAL
current dispatcher rejecting `parallel-safety-report` (exit 2, invalid choice) and
fail with a semantic `AssertionError` comparing that to the expected
`ParallelSafetyReport` contract. Each in-process scenario lazily imports `main`
from `des.cli.parallel_safety_report` INSIDE its invocation helper (P3); the
`ModuleNotFoundError` is a runtime exception raised WITHIN the test's own call
stack, never a collection-time error -- collection stays green (P1), and each test
fails for a semantic reason once the module ships (P4).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


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
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    for relpath, content in files.items():
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


def _write_feature_delta(root: Path, plan_rows: list[str]) -> Path:
    """Write a minimal well-formed feature-delta whose Slice Plan declares the
    given rows -- reusing row-1's grammar (`depends-on` = declared-serial, empty
    Annotation = declared-parallel), the exact SSOT `des parallel-safety-report`
    reads via the reused `validate_feature_delta` Slice-Plan parser.
    """
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


# A well-formed three-row plan: slice-02 + slice-03 declared-parallel (no
# `depends-on`), slice-04 declared-serial (`depends-on slice-03`, with a why).
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


def _last_json_line(stdout: str) -> dict:
    """The last `{...}`-shaped stdout line, parsed -- `des` may prefix an
    unrelated freshness-autoskip event line the AT must skip past (mirrors the
    `_last_json_line` precedent in the sibling blast-radius acceptance suite)."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a single-line JSON event on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _invoke_in_process(argv: list[str], capsys) -> tuple[int, str, dict | None]:
    """Drive `des.cli.parallel_safety_report.main(argv)` IN-PROCESS (P3 lazy import).

    Returns (exit_code, stderr, parsed-stdout-JSON-or-None).
    """
    from des.cli.parallel_safety_report import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    payload: dict | None = None
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    if json_lines:
        payload = json.loads(json_lines[-1])
    return exit_code, captured.err, payload


# --- @walking_skeleton -- the ONE subprocess-E2E for the whole feature --------


def test_parallel_safety_report_measures_two_disjoint_slices_as_safe(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: DISCUSS Outcome KPI 1 (a maintainer acts on a MEASURED
    independence verdict instead of the plan's bare assertion).

    Fixture A (charter): a maintainer runs `des parallel-safety-report` over a
    feature-delta declaring slice-02 and slice-03 parallel-safe, supplying each
    slice's disjoint touched paths. The report measures each via the REAL
    `des blast-radius` and, finding their files/boundary/consumer-symbols
    disjoint on all three axes, emits MEASURED-SAFE for the (slice-02, slice-03)
    pair -- her assumption of independence is now measured, not guessed. Exit 0:
    the verdict advises, it does not refuse.
    """
    # covers: R1
    # covers: R2
    # covers: R5
    # covers: R6
    # covers: R7
    # covers: R8
    des_binary = shutil.which("des")
    assert des_binary is not None, (
        "the `des` console-script must be on PATH for the feature's single "
        "walking-skeleton subprocess AT to run -- if this fails, the dev "
        "environment install is the problem, not this AT"
    )

    repo = tmp_path / "repo"
    _init_git_repo(
        repo,
        {
            "cart_pricing.py": "def price():\n    return 1\n",
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
            "--scope",
            "slice-02=cart_pricing.py",
            "--scope",
            "slice-03=orders_summary.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        "a safety verdict is ADVISORY (D-2) -- MEASURED-SAFE exits 0, never a "
        f"refusal; got exit={completed.returncode} stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "ParallelSafetyReport"
    assert payload["verdict"] == "MEASURED-SAFE"
    assert sorted(payload["pair"]) == ["slice-02", "slice-03"]
    # MEASURED-SAFE == disjoint on ALL three axes: no overlapping file, no
    # shared boundary file, no shared high-fan-in consumer symbol.
    overlap = payload["overlap"]
    assert overlap["files"] == []
    assert overlap["boundary_files"] == []
    assert overlap["consumer_symbols"] == []
    # Distinct human face: MEASURED-SAFE -> ✅ PASS (CT-9 / DESIGN DH).
    assert completed.stderr.strip() != ""
    assert "✅" in completed.stderr


# --- @real-io -- second subprocess-E2E, explicitly justified (see docstring) --


@pytest.mark.negative_at
def test_parallel_safety_report_measures_two_overlapping_slices_as_drift(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: unbounded-preservation

    Outcome anchor: DISCUSS Outcome KPI 2 (a maintainer SEES the contradiction --
    DRIFT -- before acting, never silently MEASURED-SAFE).

    Fixture B (charter): a maintainer runs the report over a plan declaring
    slice-02 and slice-03 parallel-safe, but their supplied scopes BOTH touch
    `ranking.py`. The report measures each via the REAL `des blast-radius` and,
    finding the touched-files axis overlapping, emits DRIFT for the pair, NAMING
    `ranking.py` -- the declaration contradicted by the diff. It does NOT
    adjudicate which side is wrong, and (negative) it must NOT emit MEASURED-SAFE
    for a measurably-overlapping pair, and must NOT refuse the plan (exit 0).
    """
    # covers: R1
    # covers: R3
    # covers: R5
    # covers: R6
    # covers: R7
    des_binary = shutil.which("des")
    assert des_binary is not None, (
        "the `des` console-script must be on PATH for this subprocess AT to run"
    )

    repo = tmp_path / "repo"
    _init_git_repo(
        repo,
        {
            "ranking.py": "def rank():\n    return 1\n",
            "alpha.py": "def alpha():\n    return 2\n",
            "beta.py": "def beta():\n    return 3\n",
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
            "--scope",
            "slice-02=ranking.py,alpha.py",
            "--scope",
            "slice-03=ranking.py,beta.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    # Advisory (D-2): a DRIFT verdict is a report line, NEVER a refusal -- exit 0.
    assert completed.returncode == 0, (
        "DRIFT is ADVISORY (D-2) -- it reports the disagreement, it does not "
        f"refuse the plan; got exit={completed.returncode} "
        f"stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "ParallelSafetyReport"
    # Negative: a measurably-overlapping pair must NEVER read MEASURED-SAFE.
    assert payload["verdict"] != "MEASURED-SAFE", (
        "no false-safe: a pair whose measured blast radii overlap must never be "
        "reported MEASURED-SAFE"
    )
    assert payload["verdict"] == "DRIFT"
    # DRIFT NAMES the overlap -- the disagreement is the finding.
    assert "ranking.py" in payload["overlap"]["files"], (
        "DRIFT must name the file both slices touched (charter Fixture B oracle)"
    )
    # Distinct human face: DRIFT -> ⚠️ DEGRADED (CT-9 / DESIGN DH).
    assert "⚠️" in completed.stderr


# --- error paths (in-process; reject at --scope validation, no measurement) ---


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("case", "scopes"),
    [
        # A --scope for a declared-serial (`depends-on`) row (slice-04).
        ("declared_serial_scope", ["slice-04=alpha.py", "slice-02=beta.py"]),
        # A --scope naming a slice-id absent from the plan.
        ("nonexistent_slice_id", ["slice-99=alpha.py", "slice-02=beta.py"]),
        # Not exactly two --scope bindings (slice-01 compares exactly one pair).
        ("only_one_scope", ["slice-02=alpha.py"]),
    ],
)
def test_parallel_safety_report_rejects_a_malformed_scope_invocation(
    tmp_path: Path, capsys, case: str, scopes: list[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Locked Decision D-2 / DESIGN CT-10 (input integrity).

    A --scope that names a declared-serial (`depends-on`) row, names a slice-id
    absent from the plan, or is not exactly two bindings is a MALFORMED
    invocation -- refused loudly as `ParallelSafetyInputRejected` with exit 2,
    never silently coerced into a fabricated MEASURED-SAFE/DRIFT verdict. The
    rejection fires at --scope validation, BEFORE any measurement.

    NOTE: no case-specific docstring branch -- a distinguishing assertion below
    (not the pspec-rendered docstring) proves each parametrize case independently.
    """
    # covers: R4
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (repo / "beta.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    feature_delta = _write_feature_delta(repo, _PLAN_ROWS)

    argv = ["--feature-delta", str(feature_delta), "--repo", str(repo)]
    for scope in scopes:
        argv += ["--scope", scope]

    exit_code, _stderr, payload = _invoke_in_process(argv, capsys)

    assert exit_code == 2, f"malformed --scope ({case}) must exit 2, got {exit_code}"
    assert payload is not None
    assert payload["event"] == "ParallelSafetyInputRejected"
    # Never a fabricated verdict alongside a rejection.
    assert payload["event"] != "ParallelSafetyReport"
    assert "verdict" not in payload
    assert payload["reasons"], "a rejection must self-explain WHY (>=1 reason)"
