"""Composition root for the evidence-locus-and-absence-detection slice-01 ATs.

This is the *only* place the production system is wired for the slice-01 ATs.
Driving-port-only (Mandate-13, Layer 3 in-process composition): the behaviour is
driven through the REAL ``des`` CLI dispatcher --
``des.cli.__main__.main(argv)`` -- called IN-PROCESS via the shared
``run_cli_in_process`` driver (no ``subprocess.run([sys.executable, ...])``
fork), mirroring the proven in-process pattern of the sibling suite
``tests/des/acceptance/gate-trailer-read-git-port-extract/steps/composition.py``.

DRIVING PORT (load-bearing): the NEW ``des verify-examine-attestation`` CLI is
NEVER imported directly at this module's top -- ``src/des/cli/
verify_examine_attestation.py`` does not exist yet (DESIGN: CREATE_NEW). The
production CLI dispatcher DOES exist (``des.cli.__main__``), so it is the
stable entry driven here; the absent subcommand surfaces as a RUNTIME argparse
rejection *inside* that stable entry's own call (the in-process active-RED
pattern, P1-P4 -- ``nw-distill-red-scaffolding``).

  P1  This module imports ONLY the stable dispatcher entry
      (``run_cli_in_process``'s default ``main=des.cli.__main__.main``) --
      never ``des.cli.verify_examine_attestation`` (absent at HEAD).
  P2  The driving call is ``run_cli_in_process(["verify-examine-attestation",
      "--repo", ...], cwd=...)`` -- IN-PROCESS, no fork.
  P3  At HEAD ``"verify-examine-attestation"`` is not a row in the dispatcher's
      ``_REGISTRY``, so ``argparse``'s ``add_subparsers(..., required=True)``
      rejects it as an invalid choice -- a RUNTIME ``SystemExit(2)`` raised
      *inside* ``main()``, never a collection-time ``ImportError``.
  P4  Each Then asserts on the CAPTURED observable (parsed stdout/stderr/exit
      code) -- at HEAD nothing is parseable (exit 2, empty report), so every
      assertion is a NAMED semantic ``AssertionError``, never an import
      traceback.

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a real ``git init``
work-tree carrying one or more commits with a controlled ``GIT_AUTHOR_DATE``
and a ``Slice-Id:`` trailer, plus a real examine-ledger file seeded through the
EXISTING production writer ``des.cli.record_examine_verdict.record_examine_verdict``
(Pillar 3: production-like fixtures, not hand-rolled JSON). This is the ONLY
"git" and "ledger" mutation in this module -- both are substrate setup, never
the SUT (the SUT is the read-only detector).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER
picks a different surface shape -- mirrors ``at_in_process_port_default``'s
convention):

  A1 (subcommand): the wired surface is ``des verify-examine-attestation
     --repo <path>`` (DESIGN Component Decomposition + the charter's own start
     recipe, verbatim).
  A2 (report line): the detector emits >=1 single-line JSON object on stdout
     carrying ``"unattested_count"`` (int) and ``"unattested_slices"`` (a list
     of objects each carrying ``"slice_id"``, and EITHER ``"commit_sha"`` or
     ``"sha"``, and EITHER ``"authored_date"`` or ``"date"``) plus a
     REQUIRED top-level ``"oldest_unattested_date"`` key. That top-level key
     is the ONLY source ``_parse_observable`` reads for ``oldest_date`` --
     there is NO fallback that derives it from per-entry dates. DESIGN D-6
     and requirement R3 make the top-level aggregate a SYSTEM obligation
     (the report states the date; answerable from output ALONE, not
     something the operator or the test derives by scanning per-entry
     dates); an implementation that ships per-entry dates but never emits
     the top-level key must fail ``then_report_states_oldest_date``, not
     pass it (BLOCKING review finding, corrected -- do not reintroduce a
     ``min(dates)`` fallback here). The parser below is still tolerant of
     both `commit_sha`/`sha` and `authored_date`/`date` spellings for the
     other fields precisely so a small DELIVER field-naming choice does not
     invalidate the AT -- the OBSERVABLE (named slice + count + date) is
     pinned, not the exact key spelling (mirrors D-6's own "JSON payload
     always carries" contract without over-fitting a field name DESIGN left
     open). This tolerance does NOT extend to the top-level date key: that
     key's NAME is pinned (``oldest_unattested_date``, verbatim), only its
     PRESENCE-as-the-sole-source is what changed.
  A3 (never-green): when >=1 slice is unattested, the human-readable summary
     (``des.cli.human_surface.print_human_summary``'s ``✅ PASS`` face) MUST
     NOT appear anywhere in the captured output, and the exit code MUST NOT be
     0 (WD-3's "never print a green summary", D-6 exit 1).
  A4 (pure read): the detector is a pure observer (DESIGN: "Pure read -- no
     filesystem mutation"). The universe guard snapshots the git ref + ledger
     byte-size before/after and asserts both are unchanged (Mandate 8).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.record_examine_verdict import record_examine_verdict

from .domain_types import (
    EXAMINE_LEDGER_RELATIVE_DIR,
    EvidenceLocusObservable,
    FeatureId,
    IsoDate,
    LedgerFillerRecord,
    SliceId,
    UnattestedCommit,
)


# A1: the wired subcommand + flag DESIGN names, verbatim from the charter's
# own start recipe.
_SUBCOMMAND = "verify-examine-attestation"

# A3: the human-readable PASS face (human_surface.py) that must never appear
# alongside a reported problem.
_PASS_FACE_TOKEN = "PASS"

# A dummy charter file the real `record_examine_verdict` writer seals (its
# bytes are hashed into `charter_seal`; content is irrelevant to this feature).
_FILLER_CHARTER_TEXT = (
    "# filler charter (evidence-locus-and-absence-detection AT fixture)\n"
)


@dataclass
class EvidenceLocusComposition:
    """Drives the production `des verify-examine-attestation` CLI for slice-01."""

    _tmp: Path | None = field(default=None)
    _project_dir: Path | None = field(default=None)
    _commits: list[UnattestedCommit] = field(default_factory=list)
    _completed_exit_code: int | None = field(default=None)
    _completed_stdout: str = field(default="")
    _completed_stderr: str = field(default="")
    _observable: EvidenceLocusObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)
    _first_run_observable: EvidenceLocusObservable | None = field(default=None)

    # ---- given: repo + commit substrate ---------------------------------

    def given_committed_slice_with_unreachable_verdict(self) -> None:
        """One committed slice whose bare id appears NOWHERE in the ledger.

        A single ``Slice-Id:``-bearing commit, authored AFTER the ledger's one
        filler record (so it is NOT a pre-mechanism commit -- the temporal
        boundary/COULD_NOT_VERIFY split is slice-02 scope, deliberately kept
        out of reach here by construction) and whose bare slice-id has zero
        entries anywhere in the ledger -> DESIGN D-2's
        ``UNATTESTED, join_confidence: heuristic`` row.
        """
        self._init_project()
        self._seed_filler_ledger_record(before="2026-01-01T00:00:00+00:00")
        commit = self._commit(
            slice_id=SliceId("slice-42"),
            authored_date=IsoDate("2026-02-01T09:00:00+00:00"),
        )
        self._commits = [commit]

    def given_two_committed_slices_with_unreachable_verdicts(self) -> None:
        """Two unattested commits, authored on different dates.

        Deepens the count/date assertions beyond N=1: proves ``count`` is a
        real tally (not hardcoded 1) and ``oldest`` is a real minimum (not
        merely "the" date).
        """
        self._init_project()
        self._seed_filler_ledger_record(before="2026-01-01T00:00:00+00:00")
        earlier = self._commit(
            slice_id=SliceId("slice-07"),
            authored_date=IsoDate("2026-02-01T09:00:00+00:00"),
        )
        later = self._commit(
            slice_id=SliceId("slice-11"),
            authored_date=IsoDate("2026-03-15T14:30:00+00:00"),
        )
        self._commits = [earlier, later]

    def given_every_committed_slice_reachable_in_ledger(self) -> None:
        """Non-vacuity control: a committed slice whose bare id IS in the ledger.

        HONEST CLASSIFICATION (review finding, corrected 2026-07-29): this
        fixture carries NO `Feature-Id:` trailer (slice-03 is out of scope), so
        per Decisions Table Revision 1 row 4 -- bare `slice_id` found under
        >=1 OTHER feature, no exact-pair match -- this is `COULD_NOT_VERIFY`,
        NEVER `ATTESTED`. `ATTESTED` is definitionally unreachable by any
        slice-01 fixture (it requires the exact-pair `Feature-Id:` join
        slice-03 introduces) -- no slice-01 AT may claim a "cleanly attested"
        outcome. What slice-01 CAN honestly claim: this commit is NOT in the
        `UNATTESTED` bucket (the non-vacuity proof that the detector's
        UNATTESTED classification is bound to genuine bare-id absence, not
        vacuously always-on -- KPI #2 guardrail). The exit-code claim is
        deliberately DROPPED: D-6 assigns a COULD_NOT_VERIFY-only run its own
        non-zero exit (2), and `Design -> Slice Mapping` names that
        distinction slice-02 scope ("the COULD_NOT_VERIFY distinction is not
        yet surfaced -- slice-02") -- asserting exit 0 here would be a FALSE
        claim (D-6 says exit 2), and asserting exit 2 would be an early claim
        on a slice-02 contract this slice does not own.
        """
        self._init_project()
        slice_id = SliceId("slice-99")
        commit = self._commit(
            slice_id=slice_id, authored_date=IsoDate("2026-02-01T09:00:00+00:00")
        )
        # The MATCHING record: bare slice_id present, timestamp before the
        # commit (so it is a genuinely-reachable, non-pre-mechanism entry).
        self._seed_ledger_record(
            LedgerFillerRecord(
                feature_id=FeatureId("some-other-feature"),
                slice_id=slice_id,
                timestamp=IsoDate("2026-01-01T00:00:00+00:00"),
            )
        )
        self._commits = [commit]

    def given_prior_report_run_once(self) -> None:
        """Run the detector once and record its report as the WD-2 baseline."""
        self.when_operator_runs_detector()
        self._first_run_observable = self._require_observable()

    # ---- when -------------------------------------------------------------

    def when_operator_runs_detector(self) -> None:
        """Invoke the REAL des verify-examine-attestation CLI in-process (P2).

        Universe-bound pure-read guard (Mandate 8, A4): the project is
        snapshot before and after; the detector is a pure observer.
        """
        self._universe_before = self.capture_universe()
        self._run_detector()
        self._observable = self._parse_observable()
        self._assert_pure_read(self._universe_before)

    def when_unrelated_file_touched_under_telemetry_and_detector_rerun(self) -> None:
        """WD-2: touch a non-ledger file under `.nwave/telemetry/`, then re-run.

        The touched file is NOT a valid `*.jsonl` ledger record (empty, wrong
        suffix) -- it must not change the detector's classification. Proves
        the detector decides on evidence-reachable-per-committed-slice, never
        on telemetry-DIRECTORY write recency (WD-2, the disease this whole
        feature exists to close).
        """
        project = self._require_project()
        telemetry_dir = project.joinpath(*EXAMINE_LEDGER_RELATIVE_DIR)
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        (telemetry_dir / "not-a-ledger-record.touch").write_text("", encoding="utf-8")
        self.when_operator_runs_detector()

    # ---- then ---------------------------------------------------------------

    def then_report_names_the_unattested_slice(self) -> None:
        """The report names EXACTLY the unattested slice-ids, count conserved.

        Tightened from a subset check to SET EQUALITY (review item 2): every
        scenario using this Then controls its fixture's full committed-slice
        population (only its own commits, plus a non-matching filler LEDGER
        record which has no commit and therefore is never a classification
        candidate) -- so the expected unattested population is fully known,
        and a report naming MORE than expected (a phantom/padded entry) must
        fail exactly as one naming FEWER must. Paired with a population-
        conservation check: `unattested_count` must equal the length of the
        named list, so a `count: 1` beside a padded/truncated list cannot
        pass silently.
        """
        observable = self._require_observable()
        expected = {str(c.slice_id) for c in self._commits}
        named = set(observable.unattested_slice_ids)
        assert named == expected, (
            "the detector must name EXACTLY the unattested slice-ids -- no "
            f"more, no fewer; expected {sorted(expected)!r}, got "
            f"{sorted(named)!r}. {self._diag()}"
        )
        self._assert_count_conserved(observable)

    def then_report_names_the_unattested_commit(self) -> None:
        """The report names the COMMIT the unattested slice came from.

        Tolerant of a short (>=8 char) sha as well as the full 40-char sha --
        a DELIVER field-naming/truncation choice, not the pinned observable.
        """
        observable = self._require_observable()
        expected_shas = {c.sha for c in self._commits if c.sha}
        reported_shas = set(observable.unattested_shas)
        matched = {
            expected
            for expected in expected_shas
            for reported in reported_shas
            if expected == reported or expected.startswith(reported)
        }
        assert expected_shas and matched == expected_shas, (
            "the report must name the COMMIT the unattested slice came from "
            f"(a sha), not merely the slice-id; expected every one of "
            f"{sorted(expected_shas)!r} to match a reported sha among "
            f"{sorted(reported_shas)!r}. {self._diag()}"
        )

    def then_report_states_the_count(self, expected_count: int) -> None:
        observable = self._require_observable()
        assert observable.unattested_count == expected_count, (
            f"the report must state the COUNT of unattested slices as {expected_count} "
            f"(a number the operator can act on), got {observable.unattested_count!r}. "
            f"{self._diag()}"
        )

    def then_report_states_oldest_date(self, expected_date: str) -> None:
        observable = self._require_observable()
        assert observable.oldest_unattested_date == expected_date, (
            "the report must state the DATE of the OLDEST unattested commit "
            f"so 'since when' is answerable from output alone; expected "
            f"{expected_date!r}, got {observable.oldest_unattested_date!r}. "
            f"{self._diag()}"
        )

    def then_command_exits_non_zero(self) -> None:
        observable = self._require_observable()
        assert observable.exit_code != 0, (
            "the command must exit non-zero when >=1 slice is unattested "
            f"(WD-1/D-6 exit 1); got exit_code={observable.exit_code}. "
            f"{self._diag()}"
        )

    def then_report_names_no_unattested_slice(self) -> None:
        """Non-vacuity control (review item 1): NOT-unattested, no exit claim.

        Asserts `unattested_count == 0` (not merely "the list happens to be
        empty") -- at HEAD the unimplemented command yields
        `unattested_count is None`, so `None == 0` is False and this fails
        RED for the right reason; a bare "list is empty" check would pass
        vacuously against the unimplemented command's empty stdout. Carries
        NO exit-code claim: see `given_every_committed_slice_reachable_in_ledger`
        for why slice-01 cannot honestly assert either exit 0 or exit 2 here.
        """
        observable = self._require_observable()
        assert observable.unattested_count == 0, (
            "a committed slice whose bare id IS reachable somewhere in the "
            "ledger must NOT be counted as unattested (non-vacuity control); "
            f"got unattested_count={observable.unattested_count!r}. "
            f"{self._diag()}"
        )
        assert observable.unattested_slice_ids == (), (
            "a committed slice whose bare id IS reachable somewhere in the "
            "ledger must not be NAMED in the unattested bucket; got "
            f"{observable.unattested_slice_ids!r}. {self._diag()}"
        )

    def then_report_does_not_read_as_success(self) -> None:
        observable = self._require_observable()
        self._assert_reported_a_real_problem(observable)
        captured = f"{observable.stdout}\n{observable.stderr}"
        assert _PASS_FACE_TOKEN not in captured, (
            "the command must NEVER print a green/success summary while a "
            f"slice is reported as missing evidence (WD-3). Captured output "
            f"contained the {_PASS_FACE_TOKEN!r} face: {self._diag()}"
        )
        assert observable.exit_code != 0, (
            f"a report listing a problem must never exit 0 green. {self._diag()}"
        )

    def then_report_unchanged_from_first_run(self) -> None:
        first = self._first_run_observable
        second = self._require_observable()
        assert first is not None, (
            "the WD-2 negative requires a recorded baseline run before the "
            "telemetry-directory touch."
        )
        # Non-vacuity: the BASELINE run must have genuinely surfaced the
        # problem (a real report, not merely an unimplemented-command usage
        # error) before "unchanged" can mean anything -- otherwise two
        # identically-broken runs would trivially "agree".
        self._assert_reported_a_real_problem(first)
        assert first.unattested_slice_ids == second.unattested_slice_ids, (
            "touching an unrelated file under .nwave/telemetry/ (NOT a valid "
            "ledger record) must not change which slices are reported "
            f"unattested -- the detector must decide on evidence-reachable-"
            f"per-committed-slice, never on telemetry-DIRECTORY write "
            f"recency (WD-2). first={first.unattested_slice_ids!r} "
            f"second={second.unattested_slice_ids!r}. {self._diag()}"
        )
        assert first.unattested_count == second.unattested_count, (
            "the reported COUNT must be identical before/after an unrelated "
            f"telemetry-directory touch. first={first.unattested_count!r} "
            f"second={second.unattested_count!r}. {self._diag()}"
        )
        # Review item 4: the FULL observable tuple, not only the name/count/
        # exit-code triple -- a cheat that perturbs only the reported DATE or
        # SHA from the touched file's mtime/inode would sail through the
        # narrower check. Extended to guard the designation-vs-property
        # distinction this scenario exists to pin (WD-2).
        assert first.oldest_unattested_date == second.oldest_unattested_date, (
            "the reported OLDEST UNATTESTED DATE must be identical before/"
            "after an unrelated telemetry-directory touch -- a detector "
            "deriving this date from filesystem mtime rather than the "
            f"commit's OWN authored date would fail this. "
            f"first={first.oldest_unattested_date!r} "
            f"second={second.oldest_unattested_date!r}. {self._diag()}"
        )
        assert first.unattested_shas == second.unattested_shas, (
            "the reported unattested SHAs must be identical (same set, same "
            "order) before/after an unrelated telemetry-directory touch. "
            f"first={first.unattested_shas!r} second={second.unattested_shas!r}. "
            f"{self._diag()}"
        )
        assert first.exit_code == second.exit_code, (
            "the exit code must be identical before/after an unrelated "
            f"telemetry-directory touch. first={first.exit_code!r} "
            f"second={second.exit_code!r}. {self._diag()}"
        )

    def _assert_count_conserved(self, observable: EvidenceLocusObservable) -> None:
        """Population conservation (review item 2): count == len(named list).

        Without this, a report of `unattested_count: 1` beside a padded (or
        truncated) `unattested_slices` list would pass a bare
        subset/membership check on the names alone -- the count and the named
        list must agree, always.
        """
        assert observable.unattested_count == len(observable.unattested_slice_ids), (
            "the reported COUNT must equal the number of NAMED unattested "
            f"slices -- got count={observable.unattested_count!r} but "
            f"{len(observable.unattested_slice_ids)} slice(s) named "
            f"({observable.unattested_slice_ids!r}). {self._diag()}"
        )

    def _assert_reported_a_real_problem(
        self, observable: EvidenceLocusObservable
    ) -> None:
        """Non-vacuity guard: a GENUINE parseable report, not merely a broken run.

        At HEAD the subcommand is unregistered, so ``unattested_count`` is
        ``None`` (nothing parseable) -- this fails RED for the right reason.
        Without this guard a negative Then could pass vacuously against an
        unimplemented command (exit 2 "isn't" exit 0 either), which would
        defeat the active-RED contract (Critical Rules #7 no fixture theater).
        """
        assert (
            observable.unattested_count is not None and observable.unattested_count > 0
        ), (
            "this assertion requires a GENUINE unattested report (a real "
            "problem the detector surfaced), not merely a non-zero exit from "
            "an unimplemented command -- otherwise the negative would pass "
            f"vacuously. {self._diag()}"
        )

    # ---- observable parsing -----------------------------------------------

    def _require_observable(self) -> EvidenceLocusObservable:
        assert self._observable is not None, (
            "des verify-examine-attestation must be run (When) before "
            "asserting on its observable report surface (Then)."
        )
        return self._observable

    def _parse_observable(self) -> EvidenceLocusObservable:
        """Parse the CLI's observable surface -- tolerant per A2 (see module doc).

        At HEAD (RED): the subcommand is unregistered, so the dispatcher exits
        2 with an argparse usage error on stderr and prints NOTHING parseable
        on stdout -- every field below resolves to its RED default (empty
        tuple / ``None``), and every Then above therefore fails with a named
        semantic ``AssertionError`` (P4), never a collection error.
        """
        slice_ids: list[str] = []
        shas: list[str] = []
        count: int | None = None
        # Per-entry authored dates are collected below (kept for the
        # legitimate authored_date/date field-name aliasing tolerance) but
        # are NEVER a source for `oldest_date` -- see the comment on
        # `oldest_date` below.
        per_entry_dates: list[str] = []
        # `oldest_date` has EXACTLY ONE source: the top-level
        # `oldest_unattested_date` key (see module docstring A2). NO
        # min(per_entry_dates) fallback -- DESIGN D-6 / R3 make the
        # top-level aggregate a SYSTEM obligation (the report states the
        # date; answerable from output ALONE, not by an operator or a test
        # scanning per-entry dates). A fallback deriving it from per-entry
        # dates would make the TEST compute the answer itself, letting an
        # implementation that ships per-entry dates but never emits the
        # top-level key still pass this Then (BLOCKING review finding,
        # fixed -- do not reintroduce).
        oldest_date: str | None = None
        for line in self._completed_stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if "unattested_count" in payload:
                value = payload["unattested_count"]
                if isinstance(value, int):
                    count = value
            for entry in payload.get("unattested_slices", []) or []:
                if not isinstance(entry, dict):
                    continue
                if "slice_id" in entry:
                    slice_ids.append(str(entry["slice_id"]))
                sha = entry.get("commit_sha", entry.get("sha"))
                if sha:
                    shas.append(str(sha))
                date = entry.get("authored_date", entry.get("date"))
                if date:
                    per_entry_dates.append(str(date))
            top_date = payload.get("oldest_unattested_date")
            if top_date:
                oldest_date = str(top_date)
        del per_entry_dates  # tolerance kept (parsed above); intentionally
        # NEVER read into `oldest_date` -- see the comment above.
        return EvidenceLocusObservable(
            exit_code=self._completed_exit_code or 0,
            stdout=self._completed_stdout,
            stderr=self._completed_stderr,
            unattested_slice_ids=tuple(slice_ids),
            unattested_shas=tuple(shas),
            unattested_count=count,
            oldest_unattested_date=oldest_date,
        )

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "(the detector was never run)"
        return (
            f"(exit_code={obs.exit_code}, stdout={obs.stdout!r}, stderr={obs.stderr!r})"
        )

    # ---- universe (Mandate 8 pure-read guard, A4) --------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate 8).

        The detector is documented as a pure observer (DESIGN: "Pure read --
        no filesystem mutation"). The universe is the git HEAD ref + the
        ledger family's total byte-size -- port-exposed filesystem
        observables, never internal struct fields.
        """
        project = self._require_project()
        head = self._git("rev-parse", "HEAD").strip()
        ledger_dir = project.joinpath(*EXAMINE_LEDGER_RELATIVE_DIR)
        ledger_bytes = (
            sum(f.stat().st_size for f in ledger_dir.glob("*.jsonl"))
            if ledger_dir.is_dir()
            else 0
        )
        return {"git.head": head, "ledger.total_bytes": ledger_bytes}

    def _assert_pure_read(self, before: dict[str, object]) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert_state_delta(
            before=before,
            after=self.capture_universe(),
            universe={"git.head", "ledger.total_bytes"},
            expected={
                "git.head": unchanged(),
                "ledger.total_bytes": unchanged(),
            },
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) --------------

    def _init_project(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="evidence-locus-at-"))
        self._project_dir = self._tmp
        run = lambda *a: subprocess.run(  # noqa: E731 -- terse local for git setup
            list(a), cwd=self._tmp, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q")
        run("git", "config", "user.email", "at@example.com")
        run("git", "config", "user.name", "at")
        (self._tmp / ".nwave").mkdir(parents=True, exist_ok=True)
        (self._tmp / ".nwave" / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )

    def _commit(self, *, slice_id: SliceId, authored_date: IsoDate) -> UnattestedCommit:
        """Make ONE real git commit carrying a `Slice-Id:` trailer at `authored_date`."""
        project = self._require_project()
        marker = project / f"{slice_id}.txt"
        marker.write_text(f"substrate marker for {slice_id}\n", encoding="utf-8")
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_DATE": str(authored_date),
                "GIT_COMMITTER_DATE": str(authored_date),
                "GIT_AUTHOR_NAME": "at",
                "GIT_AUTHOR_EMAIL": "at@example.com",
                "GIT_COMMITTER_NAME": "at",
                "GIT_COMMITTER_EMAIL": "at@example.com",
            }
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "commit",
                "-q",
                "-m",
                f"ship {slice_id}\n\nSlice-Id: {slice_id}",
            ],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        sha = self._git("rev-parse", "HEAD").strip()
        return UnattestedCommit(slice_id=slice_id, authored_date=authored_date, sha=sha)

    def _git(self, *args: str) -> str:
        project = self._require_project()
        completed = subprocess.run(
            ["git", *args], cwd=project, check=True, capture_output=True, text=True
        )
        return completed.stdout

    def _seed_filler_ledger_record(self, *, before: str) -> None:
        """Seed ONE unrelated ledger record so the scan never reads zero total.

        Avoids the slice-02-scoped `EmptyLedgerAmbiguous` refusal (DESIGN
        Revision 1 answer 3) -- deliberately out of THIS slice's AT scope.
        """
        self._seed_ledger_record(
            LedgerFillerRecord(
                feature_id=FeatureId("unrelated-filler-feature"),
                slice_id=SliceId("slice-00-filler"),
                timestamp=IsoDate(before),
            )
        )

    def _seed_ledger_record(self, record: LedgerFillerRecord) -> None:
        """Append ONE examine-ledger record via the REAL production writer.

        Reuses `des.cli.record_examine_verdict.record_examine_verdict` --
        production-like fixtures (Pillar 3), not a hand-rolled JSON write.
        """
        project = self._require_project()
        charter_dir = project / "docs" / "product" / "expectations" / "filler-feature"
        charter_dir.mkdir(parents=True, exist_ok=True)
        charter_path = charter_dir / "filler-charter.md"
        if not charter_path.exists():
            charter_path.write_text(_FILLER_CHARTER_TEXT, encoding="utf-8")
        record_examine_verdict(
            repo=project,
            feature_id=str(record.feature_id),
            slice_id=str(record.slice_id),
            charter_path=charter_path,
            verdict="PASS",
            observations="AT fixture filler record",
            examiner="at-fixture",
            timestamp=str(record.timestamp),
        )

    def _run_detector(self) -> None:
        """Run `des verify-examine-attestation --repo <project>` in-process (P2)."""
        project = self._require_project()
        from tests.common.in_process_cli import run_cli_in_process

        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        exit_code, stdout, stderr = run_cli_in_process(
            [_SUBCOMMAND, "--repo", str(project)],
            cwd=str(project),
            env=env,
            catch_all=True,
        )
        self._completed_exit_code = exit_code
        self._completed_stdout = stdout
        self._completed_stderr = stderr

    def _require_project(self) -> Path:
        assert self._project_dir is not None, (
            "the synthetic repo must be built (Given) before capturing its "
            "universe or running the detector (When)."
        )
        return self._project_dir

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
