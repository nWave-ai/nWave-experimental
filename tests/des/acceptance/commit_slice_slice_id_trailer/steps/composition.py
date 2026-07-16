"""Composition root for the commit-slice-slice-id-trailer slice (C9).

Wires the PRODUCTION surface the feature changes:

  * ``des.cli.commit_slice.main`` -- the REAL ``des commit-slice`` CLI driving
    port, driven in-process (Layer 3). The fix adds a ``--slice-id`` arg, the
    idempotent ``Slice-Id:`` trailer stamp (reusing
    ``des.domain.slice_id_trailer.extract_slice_ids`` for the presence check + the
    trailer shape), and the refuse-if-absent guard. All four ACs drive THIS
    function and observe the resulting committed git artifact + the CLI exit code.

Mandate-13 (driving-port-only) -- the SUT is the production ``commit_slice.main``;
nothing in the resolution is re-implemented in the test. The observable Universe
is the committed git artifact, read back from the REAL work-tree:
``git log -1 --format=%B HEAD`` (the message trailers) and the CLI exit code.

HERMETICITY (load-bearing): the git repo is a fresh ``tmp_path`` work-tree built
by ``_init_repo`` (git init + a committed base file + one staged change) -- NEVER
this repo. No real home-directory / personal-hook paths are touched. The pre-commit
hooks dir is pinned to the repo's own ``.git/hooks`` and emptied so a global
``core.hooksPath`` cannot leak into the commit; the staged change is a single tiny
file so the (real) ``run_contract_gate`` committed-scope verify subprocess
commit_slice runs stays fast.

Business logic lives in the production surface above; step bodies delegate to
``CommitSliceComposition`` methods and never inline logic (Mandate-15 /
Mandate-12 criterion 3).

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD (verified via Tsunami
``atoms_in_file`` on commit_slice.py):
  * AC-1 -- ``_build_parser`` has NO ``--slice-id`` arg, so driving
    ``main(["--slice-id", ...])`` raises ``SystemExit`` (argparse: unrecognised
    argument). ``commit_slice_main`` catches that SystemExit and reports it as a
    non-zero exit with no commit produced, so the observed HEAD message carries no
    ``Slice-Id:`` trailer -> the Then RED-fails for the right reason (the arg +
    the stamp are missing), never an ImportError.
  * AC-3 -- ``main`` has NO refuse-if-absent guard, so a Slice-Id-less message
    commits with exit 0 -> the refusal assertion RED-fails.
  * AC-2 / AC-4 -- live-green preservation guards (a message-carried Slice-Id is
    committed verbatim today; the SliceCommitted/GateScopeVerified mechanics
    already pass).
The composition imports ``commit_slice.main`` at module load; it exists on HEAD,
so collection never errors -- every failure is a value AssertionError, never an
ImportError.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.commit_slice import main as commit_slice_main
from des.domain.slice_id_trailer import extract_slice_ids

from .domain_types import CommitMessageBody, SliceId


def _git(root: Path, *args: str) -> str:
    """Run a git subprocess in ``root`` (real-IO driven port for the work-tree)."""
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a hermetic git work-tree with one committed base file (the slice's parent).

    Pins ``core.hooksPath`` to the repo's own ``.git/hooks`` (emptied) so a
    global/user-level hooks path cannot leak in. Lays down the minimal pytest
    scaffold the committed-scope digest / verify machinery expects, then commits a
    base walking-skeleton commit so HEAD exists.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _last_json_event(stdout: str) -> dict | None:
    """Return the last single-line JSON event commit_slice emitted, or None."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    if not json_lines:
        return None
    return json.loads(json_lines[-1])


@dataclass
class CommitOutcome:
    """Port-exposed observable of one ``commit_slice.main`` invocation.

    The Universe (Mandate-8) is exactly what the C9 feature governs, read back
    from the REAL work-tree -- nothing internal:
      * ``exit_code`` -- the CLI exit code.
      * ``head_message`` -- ``git log -1 --format=%B HEAD`` (or the PARENT's
        message when the invocation produced no new commit), so a refusal is
        observed as "the slice-less message never became HEAD".
      * ``produced_commit`` -- whether a NEW commit landed past the recorded
        parent (the refusal observable for AC-3).
      * ``event`` -- the emitted JSON event (``SliceCommitted`` etc.), used by AC-4
        to witness the Gate-Scope mechanics are unchanged.
    """

    exit_code: int
    head_message: str
    produced_commit: bool
    event: dict | None = field(default=None)


class CommitSliceComposition:
    """Production-wired composition root driving the REAL ``des commit-slice``.

    One driving surface (``commit_slice.main``), one real-IO terminal (a hermetic
    ``tmp_path`` git work-tree). Step bodies call ``given_*`` to provision the
    repo + message, ``commit_slice`` to drive the SUT, and read the typed
    ``CommitOutcome`` back.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._message: CommitMessageBody | None = None

    # --- provisioning (Given) -----------------------------------------------

    def given_staged_change(self) -> None:
        """Init the hermetic repo + stage one new tiny file (the slice change)."""
        _init_repo(self._repo)
        (self._repo / "tests" / "unit" / "test_slice_new.py").write_text(
            "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
        )
        _git(self._repo, "add", "-A")

    def given_message_body(self, body: CommitMessageBody) -> None:
        """Record the commit message BODY the caller will hand --message."""
        self._message = body

    # --- driving-port invocation (When) -------------------------------------

    def commit_slice(self, slice_id: SliceId | None) -> CommitOutcome:
        """Drive the REAL ``commit_slice.main`` and observe the committed artifact.

        Records HEAD before the invocation so ``produced_commit`` can witness
        whether a NEW commit landed (the AC-3 refusal observable). Passes
        ``--slice-id`` only when a slice id is supplied (AC-1 / AC-4); omits it for
        the message-carried (AC-2) and refuse (AC-3) paths.

        ``commit_slice.main`` already returns a non-zero int on its own
        MalformedInput paths; a missing-arg ``SystemExit`` from argparse (the AC-1
        active-RED reason at HEAD) is captured here and surfaced as a non-zero
        exit with no commit produced, so the observable stays at the port (an exit
        code + the unchanged HEAD), never an uncaught test crash.
        """
        assert self._message is not None, "given_message_body must run first"
        parent = _git(self._repo, "rev-parse", "HEAD").strip()

        argv = [
            "--repo",
            str(self._repo),
            "--feature-id",
            "fix-commit-slice-omits-slice-id-trailer",
            "--all",
            "--message",
            str(self._message),
            # The hermetic tmp_path work-tree carries no `.feature` files (the
            # real slice-01 `.feature` lives in THIS repo, not the throwaway
            # one this composition commits into), so the default gherkin E2
            # leg would refuse `no .feature file resolves ... vacuously`
            # (ADR-DES-001 pre-flight, unrelated to the Slice-Id trailer this
            # slice actually tests). Point E2 at a REAL committed pytest file
            # already staged by `given_staged_change` so the pre-flight gets
            # genuine observed evidence instead of a vacuous pass.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
        ]
        if slice_id is not None:
            argv += ["--slice-id", str(slice_id)]

        captured = _CaptureStdout()
        with captured:
            try:
                exit_code = commit_slice_main(argv)
            except SystemExit as exc:  # argparse: unrecognised --slice-id at HEAD
                exit_code = exc.code if isinstance(exc.code, int) else 2

        head = _git(self._repo, "rev-parse", "HEAD").strip()
        produced = head != parent
        head_message = _git(self._repo, "log", "-1", "--format=%B", "HEAD")
        return CommitOutcome(
            exit_code=exit_code,
            head_message=head_message,
            produced_commit=produced,
            event=_last_json_event(captured.text),
        )

    # --- observation helpers (Then) -----------------------------------------

    @staticmethod
    def slice_ids_in(message: str) -> list[str]:
        """The slice ids the message carries, via the production trailer parser.

        Reuses ``des.domain.slice_id_trailer.extract_slice_ids`` -- the SAME
        production surface the fix consumes for its idempotent-append check -- so
        the test observes Slice-Id presence through the shipped trailer shape, not
        an ad-hoc regex.
        """
        return extract_slice_ids(message)


class _CaptureStdout:
    """Context manager capturing ``commit_slice.main``'s stdout JSON events.

    commit_slice emits its events with ``print`` (``_emit`` -> ``json.dumps``);
    capturing stdout lets AC-4 read the ``SliceCommitted`` / ``GateScopeVerified``
    event without coupling to pytest's ``capsys`` inside the composition.
    """

    def __init__(self) -> None:
        self.text = ""
        self._buf = None
        self._redirect = None

    def __enter__(self) -> _CaptureStdout:
        import contextlib
        import io

        self._buf = io.StringIO()
        self._redirect = contextlib.redirect_stdout(self._buf)
        self._redirect.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        assert self._redirect is not None and self._buf is not None
        self._redirect.__exit__(*exc)
        self.text = self._buf.getvalue()
