"""Acceptance tests -- `des blast-radius` (DISTILL, slice-01, walking skeleton).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Slice Plan slice-01 row, [REF] Architecture & Contract Tests,
  [REF] Reuse Analysis -- New components).

**SUPERSEDED NOTE (2026-07-18, transitional contract retired by slice-02, NOT
a weakening):** the historical description below (paragraphs 2-5) documents
slice-01's ORIGINAL, DECLAREDLY TRANSITORY contract, written when nothing
existed yet to reverse-engineer -- it explicitly said "not yet wired --
slice-02 scope" for `boundary_files`/`consumer_counts`. Slice-02 has now
wired both for real. Two of the original assertions in
`test_blast_radius_reports_a_small_tier_from_real_git_measures` became
logically incompatible with slice-02's own contract once its fixture files
carried real top-level Python symbols: `consumer_counts == {}` cannot hold
for a touched `.py` file that DECLARES a symbol (slice-02's own
`test_a_file_outside_every_boundary_glob_never_triggers_boundary_escalation`
requires a zero-caller symbol to be a REAL entry valued `0`, never an absent
key). Rather than relax the `consumer_counts == {}` assertion (which would
lose the anti-fabrication guardrail this AT exists to enforce), the WS
fixture now uses two plain-text (non-`.py`) data files -- `consumer_counts`
stays HONESTLY `{}` because a non-Python touched file contributes ZERO
`consumer_counts` entries BY DESIGN (feature-delta obligation (b)), not
because nothing was computed. The `reasons`-names-"not yet wired" assertion
is retired outright (that phrasing no longer exists once boundary/consumer
detection is real) and replaced with the equally strong, now-true claim that
a clean S-tier verdict fires ZERO reasons. See `_init_git_repo_data_only`
below and its use in the walking-skeleton test.

Slice-01 value (feature-delta Slice Plan): `des blast-radius --repo <path>
--paths <f1> <f2> ...` is a real, E2E-wired CLI command -- given a trivial
fixture repo it reports REAL `files` + `lines_changed` measures (via
`git diff HEAD --numstat`) and an honest tier (`S`/`M` from files+lines only;
`boundary_files` always `[]` and `consumer_counts` always `{}` -- not yet
wired, never fabricated as a real zero-crossings/zero-consumers signal) as
one single-line JSON verdict plus a human summary line.

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/cli/blast_radius.py::main(argv) -> int`, registered as the `des
blast-radius` subcommand. Grammar for slice-01 (only `--paths` mode ships
this slice; `--staged`/`--diff <ref>` are slice-02 scope per the Slice Plan):

    des blast-radius --repo <path> --paths <f1> [<f2> ...]

stdout token (single-line JSON), success:
    {"event": "BlastRadiusMeasured", "tier": "S"|"M",
     "measures": {"files": <int>, "lines_changed": <int|null>,
                  "boundary_files": [], "consumer_counts": {}},
     "reasons": [<str>, ...]}

`tier` is computed from `files`/`lines_changed` ONLY for slice-01 (the full
S/M/L decision table over `boundary_files`/`consumer_counts` is slice-02
scope): `S` iff `files <= 2` AND `lines_changed` is not `null` AND
`lines_changed <= 10` (the feature-delta's canonical default thresholds --
`small_max_files=2`, `small_max_lines=10`); `M` otherwise. `reasons` ALWAYS
names that `boundary_files`/`consumer_counts` are not yet wired (GDP-6: an
empty list/dict must never be presented as a real "zero crossings" /
"zero consumers" measurement -- the vacuous-truth family) -- this is the
DISTILL-pinned contract for slice-01, since nothing exists yet to reverse
engineer.

stdout token, input rejection (a named `--paths` entry does not exist on
disk -- DISTILL's own slice-01 contract addition, not silently reporting a
fabricated S): exit 2,
    {"event": "BlastRadiusInputRejected", "reasons": [<str naming the path>]}
-- no `tier`/`measures` key ever appears alongside a rejection.

Driving surface: the walking-skeleton scenario below is the ONE
subprocess-E2E acceptance test for the WHOLE `blast-radius-measured-tier`
feature (F-V5 test-pyramid default, ratified 2026-07-18) -- it invokes the
REAL installed `des` console-script (resolved via `shutil.which`, the same
production composition root `single_entry_point`'s acceptance suite already
established) against a real git fixture repo. Every OTHER scenario in this
module drives `des.cli.blast_radius.main(argv)` IN-PROCESS (Mandate 13 /
`nw-distill-port-treatment-policy` inverted driving default) -- no further
subprocess forks.

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`src/des/cli/blast_radius.py` does not exist and `blast-radius` is not yet a
registered `des` subcommand. The walking-skeleton scenario observes the
REAL current dispatcher behaviour (`des: error: argument subcommand: invalid
choice: 'blast-radius'`, exit 2 -- verified empirically against the
installed `des` binary) and fails with a semantic `AssertionError` comparing
that to the expected `BlastRadiusMeasured` contract, never a naked
traceback. Every in-process test lazily imports `main` from
`des.cli.blast_radius` INSIDE its own invocation helper (P3); the resulting
`ModuleNotFoundError` is a runtime exception raised WITHIN the test's own
call stack, not a collection-time error -- collection stays green, and each
test fails for a semantic reason once the module ships (P4).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


# Canonical default thresholds (feature-delta "Canonical default thresholds"
# table) -- slice-01's OWN reduced files+lines-only tier rule reads these
# same two numbers; slice-02 wires the full `DESConfig` cascade around them.
SMALL_MAX_FILES = 2
SMALL_MAX_LINES = 10


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_git_repo(root: Path) -> None:
    """A real git work-tree with two small tracked files at HEAD."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    (root / "module_a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "module_b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


def _init_git_repo_data_only(root: Path) -> None:
    """A real git work-tree with two small tracked NON-PYTHON data files.

    WS-only fixture variant (2026-07-18, see the module docstring's SUPERSEDED
    NOTE) -- the shared `_init_git_repo` (used unchanged by every other
    slice-01/slice-02 test) still seeds `.py` files with a top-level `def`
    each. This variant seeds `.txt` files instead, precisely so the
    walking-skeleton's `consumer_counts == {}` claim stays true post-slice-02:
    a non-`.py` touched file contributes ZERO `consumer_counts` entries by
    design (never because nothing was computed).
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    (root / "note_a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "note_b.txt").write_text("beta\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base commit")


def _last_json_line(stdout: str) -> dict:
    """The last `{...}`-shaped stdout line, parsed. Mirrors the
    `_last_json_event` precedent in `tests/des/integration/test_commit_slice.py`
    -- `des` prefixes real invocations with an unrelated freshness-autoskip
    event line the AT must skip past."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def _invoke_in_process(
    repo_root: Path, argv: list[str], capsys
) -> tuple[int, str, dict | None]:
    """Drive `des.cli.blast_radius.main(argv)` IN-PROCESS (P3 lazy import).

    Returns (exit_code, stderr, parsed-stdout-JSON-or-None).
    """
    from des.cli.blast_radius import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    payload: dict | None = None
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    if json_lines:
        payload = json.loads(json_lines[-1])
    return exit_code, captured.err, payload


# --- @walking_skeleton -- the ONE subprocess-E2E for the whole feature ----


def test_blast_radius_reports_a_small_tier_from_real_git_measures(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A developer runs `des blast-radius --paths <f1> <f2>` against a repo
    where they touched two files with a handful of lines, and gets back a
    real S-tier verdict grounded in `git diff HEAD --numstat` -- not a
    fabricated placeholder. Uses `_init_git_repo_data_only` (non-`.py` data
    files, see the module docstring's SUPERSEDED NOTE): this keeps
    `consumer_counts == {}` honestly true post-slice-02 without touching the
    shared `_init_git_repo` every other slice-01/slice-02 test relies on.
    """
    des_binary = shutil.which("des")
    assert des_binary is not None, (
        "the `des` console-script must be on PATH for the feature's single "
        "walking-skeleton subprocess AT to run -- if this fails, the dev "
        "environment install is the problem, not this AT"
    )

    repo = tmp_path / "repo"
    _init_git_repo_data_only(repo)
    # Uncommitted, small edit across the two tracked files -- 2 files
    # touched (<= SMALL_MAX_FILES), 4 lines added total (<= SMALL_MAX_LINES).
    with (repo / "note_a.txt").open("a", encoding="utf-8") as handle:
        handle.write("second line\nthird line\n")
    with (repo / "note_b.txt").open("a", encoding="utf-8") as handle:
        handle.write("second line\nthird line\n")

    completed = subprocess.run(
        [
            des_binary,
            "blast-radius",
            "--repo",
            str(repo),
            "--paths",
            "note_a.txt",
            "note_b.txt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        f"expected a clean measurement, got exit={completed.returncode} "
        f"stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["tier"] == "S"
    assert payload["measures"]["files"] == 2
    assert payload["measures"]["lines_changed"] == 4
    # boundary/consumer are honestly empty AND self-explaining -- never a
    # silent fabricated "we checked, found zero" (GDP-6 vacuous-truth family).
    # Both are honestly empty because neither touched file is a `.py` file
    # (see the module docstring's SUPERSEDED NOTE) -- never because nothing
    # was computed once slice-02 wired real detection.
    assert payload["measures"]["boundary_files"] == []
    assert payload["measures"]["consumer_counts"] == {}
    assert payload["reasons"] == [], (
        "a clean S-tier verdict (no boundary crossing, no consumer count, no "
        "size overage) fires ZERO reasons -- reasons only names conditions "
        "that actually triggered (GDP-3), never a placeholder for absence"
    )
    # Dual-surface emission (Reuse Analysis: reuses `print_human_summary`) --
    # a human-readable line on stderr, distinct from the machine JSON.
    assert completed.stderr.strip() != ""
    assert any(marker in completed.stderr for marker in ("✅", "❌", "⚠️", "⚪", "❓"))
    assert "S" in completed.stderr


# --- in-process: the files+lines-only S/M classification ------------------


@pytest.mark.parametrize(
    "case",
    ["too_many_files", "too_many_lines"],
)
def test_blast_radius_escalates_to_medium_tier_beyond_small_thresholds(
    tmp_path: Path, capsys, case: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A change that exceeds either the small-files or small-lines threshold
    is measured M, not silently S -- regardless of WHICH signal tripped it.

    NOTE: deliberately no shared docstring content across the two
    parametrize cases beyond this fixed contract text (pytest-pspec renders
    the JUnit testcase name from the docstring verbatim, without the
    parametrize id -- a distinguishing case-specific assertion below, not
    the docstring, is what proves each branch independently).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    if case == "too_many_files":
        # 3 named paths > SMALL_MAX_FILES=2, each with a trivial diff.
        for name in ("m1.py", "m2.py", "m3.py"):
            (repo / name).write_text("x = 1\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed three files")
        with (repo / "m1.py").open("a", encoding="utf-8") as handle:
            handle.write("y = 2\n")
        paths = ["m1.py", "m2.py", "m3.py"]
        expected_files = 3
    else:
        # 1 named path (<= SMALL_MAX_FILES) but > SMALL_MAX_LINES lines
        # added in one uncommitted edit.
        big_edit = "".join(f"line_{i} = {i}\n" for i in range(SMALL_MAX_LINES + 2))
        with (repo / "module_a.py").open("a", encoding="utf-8") as handle:
            handle.write(big_edit)
        paths = ["module_a.py"]
        expected_files = 1

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", *paths], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["tier"] == "M"
    assert payload["measures"]["files"] == expected_files
    if case == "too_many_files":
        assert payload["measures"]["files"] > SMALL_MAX_FILES
    else:
        assert payload["measures"]["lines_changed"] > SMALL_MAX_LINES


# --- error paths (>= 40% of this module's scenarios) -----------------------


def test_blast_radius_rejects_a_nonexistent_path_instead_of_reporting_small(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A typo'd `--paths` entry that names no real file must be refused loudly
    -- never silently measured as a 0-line, 0-file S-tier change (the exact
    vacuous-truth footgun the orchestrator flagged for this slice).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    exit_code, _stderr, payload = _invoke_in_process(
        repo,
        ["--repo", str(repo), "--paths", "does-not-exist.py"],
        capsys,
    )

    assert exit_code == 2
    assert payload is not None
    assert payload["event"] != "BlastRadiusMeasured"
    assert "tier" not in payload
    assert "measures" not in payload
    assert any("does-not-exist.py" in reason for reason in payload["reasons"])


def test_blast_radius_requires_a_paths_argument(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    Omitting `--paths` entirely (slice-01's only supported input mode) is a
    usage error, not a silently-empty measurement.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    exit_code, stderr, payload = _invoke_in_process(repo, ["--repo", str(repo)], capsys)

    assert exit_code == 2
    assert payload is None or payload.get("event") != "BlastRadiusMeasured"
    assert "paths" in stderr.lower()


def test_blast_radius_degrades_lines_changed_to_null_outside_a_git_worktree(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A `--repo` that is not a git work-tree cannot honestly produce a
    `lines_changed` count -- the measurement degrades to `null` (never a
    fabricated 0) and the tier honestly escalates to M (S is unreachable
    without a real line count), naming the cause in `reasons`.
    """
    repo = tmp_path / "plain_dir"
    repo.mkdir(parents=True)
    (repo / "module_a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    # Deliberately NOT `git init`-ed.

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["lines_changed"] is None
    assert payload["measures"]["files"] == 1
    assert payload["tier"] == "M", (
        "an indeterminate lines_changed must never resolve to S -- an "
        "unknown blast radius is treated as the worse case, never silently "
        "smaller (GDP-6)"
    )
    assert any("git" in reason.lower() for reason in payload["reasons"]), (
        "the degrade cause (not a git work-tree) must be named, not silent"
    )
