"""Composition root for the fix-scorecard-freshness-audit-cli acceptance set.

F-CROSS-TREE-SCORECARD-FRESHNESS-AUDIT-CLI (Mandate-12 criteria 2-3, Pillar 3).
Wires the PRODUCTION ``check_scorecard_freshness`` CLI against a tmp_path
scorecard project carrying a real git repo (the cited F-id evidence the CLI's
``git log --grep`` interrogates).

Business logic (write a scorecard of a given shape with all-fresh or
one-stale cells, init the backing git repo with the cited commits, invoke
the CLI, capture the verdict + stdout/stderr) lives here as the single source
of truth; step bodies delegate to ``ScorecardFreshnessComposition`` methods
and never inline logic.

Layer 3 (subprocess / FS acceptance): the ``check_scorecard_freshness`` CLI
is the driving port; the driven ports are the real filesystem (tmp_path
scorecard) and the real git subprocess (``git init`` + ``git commit`` +
``git log --grep`` invoked by the CLI under test).

RED-scaffold note: ``scripts/cli/check_scorecard_freshness.py`` is authored
by the DELIVER crafter (NOT this DISTILL phase). Until the scaffold lands,
the slice-01 subprocess invocations FAIL with ``ModuleNotFoundError`` --
which still surfaces as a non-zero exit code, so the @then assertions fire
their assertion-error messages (the AT is RED, not BROKEN, once the crafter
authors the RED scaffold; this is the Mandate 7 prepare step the crafter
performs before any GREEN work).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    DEFAULT_STALE_THRESHOLD_DAYS,
    FreshnessCliResult,
    ScorecardFId,
    ScorecardFreshnessVerdict,
)


# Repo root -- the four-level-up parent of this file
# (tests/scripts/cli/fix_scorecard_freshness_audit_cli/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]


# An F-id cited by every walking-skeleton scorecard cell. Real backing-git
# commits use this in the commit message subject so the CLI's
# ``git log --grep '<F-id>'`` resolves the cell evidence.
_FRESH_FID: ScorecardFId = ScorecardFId("F-FRESH-EXAMPLE")
_STALE_FID: ScorecardFId = ScorecardFId("F-STALE-EXAMPLE")


@dataclass
class ScorecardFreshnessComposition:
    """Production-wired composition root for slice-01.

    ``project_root`` is a tmp_path subdirectory acting as the project the
    scorecard lives in; the composition root inits a backing git repo in
    that dir and authors a scorecard file referencing F-ids whose evidence
    lives (or does not live) in that repo's history.
    """

    project_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) -- port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observables this composition exposes.

        Universe entries are port-exposed names, never internal struct fields:
        the scorecard file presence + its raw bytes (so a post-invocation
        diff catches any mutation -- the read-only preservation contract).
        """
        scorecard_path = self.scorecard_path()
        return {
            "scorecard.present": scorecard_path.is_file(),
            "scorecard.bytes": (
                scorecard_path.read_bytes() if scorecard_path.is_file() else b""
            ),
        }

    # ------------------------------------------------------------------
    # Path accessors -- port-exposed file locations.
    # ------------------------------------------------------------------

    def scorecard_path(self) -> Path:
        """The scorecard file the CLI reads (port-exposed input path)."""
        return self.project_root / "scorecard.md"

    # ------------------------------------------------------------------
    # Given-step delegates -- author scorecard + backing git history.
    # ------------------------------------------------------------------

    def init_project_with_backing_git(self) -> None:
        """Initialise the tmp_path project root with a backing git repo.

        ``git init`` + a single bootstrap commit so subsequent
        ``write_fresh_commit_for_fid`` / ``write_stale_commit_for_fid`` calls
        have a HEAD to extend. Git author identity is set explicitly so the
        subprocess invocations do not pick up the system git config.
        """
        self.project_root.mkdir(parents=True, exist_ok=True)
        self._git("init", "-q")
        self._git("config", "user.email", "acceptance-fixture@nwave.test")
        self._git("config", "user.name", "Acceptance Fixture")
        # Bootstrap commit -- empty README so git has a HEAD.
        (self.project_root / "README.md").write_text(
            "# scorecard freshness acceptance fixture\n", encoding="utf-8"
        )
        self._git("add", "README.md")
        self._git("commit", "-q", "-m", "chore: bootstrap acceptance fixture repo")

    def write_scorecard_with_all_fresh_cells(self) -> None:
        """Author a scorecard whose every cell cites the fresh F-id.

        Pairs with ``write_fresh_commit_for_fid()`` -- the CLI's
        ``git log --grep '<F-id>'`` finds a commit within threshold for every
        cell, so the top-level verdict is PASS (exit 0).
        """
        body = (
            "# Scorecard\n"
            "\n"
            "| Dimension | Score | Cited evidence |\n"
            "|-----------|-------|----------------|\n"
            f"| D1        | 90%   | {_FRESH_FID}   |\n"
            f"| D2        | 95%   | {_FRESH_FID}   |\n"
        )
        self.scorecard_path().write_text(body, encoding="utf-8")

    def write_scorecard_with_one_stale_cell(self) -> None:
        """Author a scorecard with one fresh cell and one stale cell.

        Pairs with ``write_fresh_commit_for_fid()`` for the fresh F-id and
        ``write_stale_commit_for_fid()`` for the stale F-id. The CLI must
        flag the stale cell + emit FAIL verdict + exit 1; the stale F-id
        string MUST appear on stdout so the consumer (cron / CI / human PRR
        reader) knows WHICH cell is stale.
        """
        body = (
            "# Scorecard\n"
            "\n"
            "| Dimension | Score | Cited evidence |\n"
            "|-----------|-------|----------------|\n"
            f"| D1        | 90%   | {_FRESH_FID}   |\n"
            f"| D2        | 95%   | {_STALE_FID}   |\n"
        )
        self.scorecard_path().write_text(body, encoding="utf-8")

    def write_fresh_commit_for_fid(self) -> None:
        """Author a commit whose subject names the fresh F-id, dated today.

        The CLI's ``git log --grep '<F-id>' --since='14 days ago'`` resolves
        this commit, marking the cell as FRESH.
        """
        (self.project_root / "fresh-evidence.txt").write_text(
            "fresh evidence body\n", encoding="utf-8"
        )
        self._git("add", "fresh-evidence.txt")
        self._git(
            "commit", "-q", "-m", f"feat({_FRESH_FID.lower()}): recent producer commit"
        )

    def write_stale_commit_for_fid(self) -> None:
        """Author a commit whose subject names the stale F-id, dated FAR past.

        The commit author + committer dates are forced to 100 days ago via
        env vars so the CLI's ``--since='14 days ago'`` filter excludes it.
        The cell citing this F-id is STALE; the FAIL verdict + exit 1 fires.

        Date is supplied in RFC-2822-style ``Day Mon DD HH:MM:SS YYYY +0000``
        format (git refuses relative phrases like ``100 days ago`` in
        ``GIT_AUTHOR_DATE`` env vars; the relative form is accepted by
        ``--date`` only on the commit-line flag).
        """
        import datetime as _dt

        (self.project_root / "stale-evidence.txt").write_text(
            "stale evidence body\n", encoding="utf-8"
        )
        self._git("add", "stale-evidence.txt")
        stale_timestamp = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(
            days=100
        )
        # ISO-8601 with timezone offset -- git accepts this in
        # GIT_AUTHOR_DATE / GIT_COMMITTER_DATE.
        stale_iso = stale_timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")
        self._git_with_date(
            "commit",
            "-q",
            "-m",
            f"feat({_STALE_FID.lower()}): producer commit older than threshold",
            commit_date=stale_iso,
        )

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegate).
    # ------------------------------------------------------------------

    def run_check_scorecard_freshness(self) -> FreshnessCliResult:
        """Invoke the check_scorecard_freshness CLI as a subprocess.

        Subprocess (layer-3 wiring-proof) consistent with the sibling
        spine-gate CLIs (at_review_verdict, carpaccio_slice_gate,
        check_robustness_density, verify_coverage_map). The CLI is invoked
        from the tmp_path project_root via ``cwd=`` so its ``git log``
        subprocesses resolve against the backing fixture repo, not the
        nwave-dev repo itself.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.check_scorecard_freshness",
                "--scorecard",
                str(self.scorecard_path()),
                "--stale-threshold-days",
                str(DEFAULT_STALE_THRESHOLD_DAYS),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            check=False,
            env={**self._subprocess_env()},
        )
        return FreshnessCliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # ------------------------------------------------------------------
    # Then-step observables (verdict + token + stale F-id surfacing).
    # ------------------------------------------------------------------

    def stdout_carries_verdict(
        self, result: FreshnessCliResult, verdict: ScorecardFreshnessVerdict
    ) -> bool:
        """Return True iff the CLI stdout token carries the named verdict.

        Asserts the L1.x contract-style stdout token includes
        ``verdict=<PASS|FAIL>`` -- the structured cause-of-verdict SSOT
        consumers (cron / CI / human PRR reader) parse uniformly.
        """
        return f"verdict={verdict.value}" in result.stdout

    def stdout_names_stale_fid(self, result: FreshnessCliResult) -> bool:
        """Return True iff the CLI stdout (or stderr) names the stale F-id.

        AT2 sad-path: the consumer must know WHICH cell is stale, not just
        THAT the verdict is FAIL. The stale F-id string MUST appear in the
        CLI output so a human reading the verdict can re-baseline the cell.
        Stderr is accepted as a fallback channel (per-cell diagnostics
        often land on stderr alongside the stdout token).
        """
        return (_STALE_FID in result.stdout) or (_STALE_FID in result.stderr)

    # ------------------------------------------------------------------
    # Internal helpers -- git subprocess wrapper.
    # ------------------------------------------------------------------

    def _git(self, *args: str) -> None:
        """Invoke ``git <args>`` in the project_root, raising on failure."""
        subprocess.run(
            ["git", *args],
            cwd=str(self.project_root),
            check=True,
            capture_output=True,
            text=True,
        )

    def _git_with_date(self, *args: str, commit_date: str) -> None:
        """Invoke ``git <args>`` with both author + committer dates forced."""
        env = {
            **self._subprocess_env(),
            "GIT_AUTHOR_DATE": commit_date,
            "GIT_COMMITTER_DATE": commit_date,
        }
        subprocess.run(
            ["git", *args],
            cwd=str(self.project_root),
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def _subprocess_env(self) -> dict[str, str]:
        """Build a minimal env for subprocess invocations.

        Inherits PATH + HOME from the host (git needs both) and adds the
        repo root to PYTHONPATH so ``python -m scripts.cli.*`` resolves the
        CLI module. Pins LC_ALL=C so any date / git output the CLI parses
        is locale-deterministic.
        """
        import os as _os

        return {
            "PATH": _os.environ.get("PATH", ""),
            "HOME": _os.environ.get("HOME", ""),
            "PYTHONPATH": str(_REPO_ROOT),
            "LC_ALL": "C",
            "LANG": "C",
            # GIT_CONFIG_GLOBAL pointing at /dev/null prevents the test from
            # picking up the user's ~/.gitconfig (which may set
            # commit.gpgsign or similar that would break the fixture commits).
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            # NWAVE_FRESHNESS=skip bypasses the des.runtime.freshness gate
            # that fires at des.cli package import time. After slice-04 of
            # fix-d1-human-readable-gate-surfaces, check_scorecard_freshness.py
            # imports from des.cli.human_surface which triggers the gate; the
            # test must opt-out to exercise the CLI behaviour, not the gate.
            "NWAVE_FRESHNESS": "skip",
        }
