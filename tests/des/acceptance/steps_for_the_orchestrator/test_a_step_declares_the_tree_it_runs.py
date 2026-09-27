"""Public oracle: a step that buys a turn names the code tree it is running.

MIGRATED FROM THE RETIRED COMPOSED RUN. These scenarios drove `des dispatch`
(`tests/des/acceptance/dispatch_owns_e2_e4/test_dispatch_declares_its_projection.py`,
census rows 1-5 of 2026-09-06). ADR-DES-003 Section 11 sorts the property to
the MODEL: it is stated over ONE invocation -- inputs in, rows out -- so it
survives the composer and is asserted here on a step instead.

Three projections of DES coexist -- an editable checkout, a global install and a
per-campaign wheel -- and a consumer picks one through PATH, a runtime pointer or
a venv, never by naming it. On 2026-09-04 a Software Factory run died on a
defect the source had closed seventeen minutes earlier, because it was executing
an installed copy two commits behind, and nothing in the run said so.

WHAT DID NOT SURVIVE, and why it is not a silent loss. The sixth scenario
asserted that `--json` mode carried the identity while stdout stayed exactly one
JSON object. A step has no `--json` projection at all: Section 4b makes the
terminal LINE the machine form and `des.cli.step_terminal._emit` writes one
block on one stream, so there is no second stream shape left to state the
property over. It is reconciled to the composer family in the census rather than
re-expressed here.

These scenarios drive the real CLI as a real subprocess, exactly as such a
consumer does, and they refuse an implementation that answers the same identity
for two genuinely different trees.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SOURCE_PACKAGE = Path(__file__).parents[4] / "src" / "des"

#: The step under observation. `po` is the FIRST step of a Request and the one
#: that buys a turn from a Request on stdin, so it is where a reader most needs
#: to know which tree answered -- and the two shapes below (a root refused
#: before any work, and a run killed while blocked on stdin) are both reachable
#: through it without a Git command, a handover or a single model call.
STEP = "po"

#: An absolute path that is not a directory: the step refuses it immediately.
NO_SUCH_ROOT = "/nwave-step-projection-probe-not-a-directory"


def run_step(
    package_parent: Path,
    *extra: str,
    repo_root: str = NO_SUCH_ROOT,
    path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the real `des po` against the `des` package under `package_parent`."""
    environment = {**os.environ, "PYTHONPATH": str(package_parent)}
    environment.pop("PYTHONSTARTUP", None)
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli",
            STEP,
            "--project",
            "--repo-root",
            repo_root,
            *extra,
        ],
        input="Deliver value\n",
        text=True,
        capture_output=True,
        env=environment,
        timeout=180,
        check=False,
    )


def declaration(completed: subprocess.CompletedProcess[str]) -> str:
    """The one runtime-identity line the step emitted, wherever it wrote it."""
    lines = [
        line
        for line in (completed.stdout + "\n" + completed.stderr).splitlines()
        if line.startswith("DELIVERY-RUNTIME: ")
    ]
    assert len(lines) == 1, completed.stdout + completed.stderr
    return lines[0]


@pytest.fixture
def divergent_projection(tmp_path: Path) -> Path:
    """A second copy of the running package, differing in one file's bytes.

    This is the Software Factory shape reduced to its cause: two trees that a
    reader cannot tell apart from the command line, running the same command.
    """
    parent = tmp_path / "projection-b"
    parent.mkdir()
    shutil.copytree(
        SOURCE_PACKAGE,
        parent / "des",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    drifted = parent / "des" / "cli" / f"{STEP}.py"
    drifted.write_text(drifted.read_text() + "\n# one byte of drift\n")
    return parent


def test_a_step_names_the_entry_point_and_the_tree_it_executes() -> None:
    done = run_step(SOURCE_PACKAGE.parent)

    line = declaration(done)
    # The entry point is what a consumer picked off PATH; the package is what
    # that entry point actually imported. The 09-04 diagnosis needed both.
    assert "entry=" in line and "package=" in line and "tree=sha256:" in line
    assert str(SOURCE_PACKAGE.resolve()) in line
    # The declaration never replaces the terminal, and never costs a turn.
    assert "InvalidRepositoryRoot" in done.stdout


def test_two_projections_of_one_step_declare_different_identities(
    divergent_projection: Path,
) -> None:
    # Without this, an implementation answering a constant would pass above.
    mine = declaration(run_step(SOURCE_PACKAGE.parent))
    other = declaration(run_step(divergent_projection))

    assert "tree=sha256:" in mine and "tree=sha256:" in other
    assert mine.split("tree=")[1] != other.split("tree=")[1]


def test_the_declaration_never_becomes_a_gate(tmp_path: Path) -> None:
    """An unreadable projection is REPORTED; it never changes the outcome.

    Making a divergence visible is not the same as blocking on one. Whether a
    projection should ever stop a step is a separate decision with its own
    evidence, so this refuses an implementation that grew a check while nobody
    was looking: an identity the step cannot compute must leave the exit status
    and the terminal it would have produced exactly as they were.
    """
    parent = tmp_path / "unreadable-projection"
    parent.mkdir()
    shutil.copytree(
        SOURCE_PACKAGE,
        parent / "des",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    # A `.py` the package never imports, so only the tree walk meets it. A
    # latin-1 byte is what a real checkout carrying one legacy file looks like.
    (parent / "des" / "_legacy_encoding_probe.py").write_bytes(b"# caf\xe9\n")

    healthy = run_step(SOURCE_PACKAGE.parent)
    degraded = run_step(parent)

    assert "tree=unreadable(UnicodeDecodeError)" in declaration(degraded)
    # Same command, same terminal, same exit status: only the identity differs.
    assert degraded.returncode == healthy.returncode
    assert degraded.stdout == healthy.stdout


def test_a_step_killed_before_it_reads_its_request_still_names_its_tree(
    tmp_path: Path,
) -> None:
    """The declaration survives a kill, which is the case it exists for.

    `step_terminal.read_request` blocks until stdin reaches EOF, so a caller
    that holds stdin open leaves the step waiting there indefinitely, and a
    bounded harness kills it exactly at that point. Such an invocation writes no
    terminal, no stdout and no exit report: the one line it emits before the
    work begins is the entire record of which tree was running. Declaring any
    later would trade that away to save latency on the very path where it is the
    only evidence left.

    A REAL directory, unlike the other scenarios here, and the difference is a
    measured one: a step validates its root BEFORE it reads stdin, so the
    refused root that makes the others free would end this one before it ever
    blocked. An empty directory is enough -- nothing past the read is reached.
    """
    environment = {**os.environ, "PYTHONPATH": str(SOURCE_PACKAGE.parent)}
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "des.cli",
            STEP,
            "--project",
            "--repo-root",
            str(tmp_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    ) as running:
        # Long enough to pass the declaration, far short of any EOF on stdin.
        try:
            running.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        assert running.poll() is None, f"des {STEP} did not block on an open stdin"
        running.kill()
        stdout, stderr = running.communicate()

    assert "DELIVERY-OUTCOME" not in stdout
    line = [x for x in stderr.splitlines() if x.startswith("DELIVERY-RUNTIME: ")]
    assert len(line) == 1 and "tree=sha256:" in line[0], stderr
