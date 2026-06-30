"""Composition root for f-attest-bundled-slice slice-04 ATs (gates + ledger).

slice-04 scope (feature-delta sec.5 step 6-7 / sec.11 row 4): the FINAL slice.
``attest_bundled_slice.main()`` replaces the post-A2
``BundledSliceAttestPreconditionsCleared`` placeholder with the gate composition
(E1+E2 via the REUSED ``_compose_gates``) and the ledger emit (via the REUSED
``_record_outcome``), exactly mirroring ``reverify_slice_commit.main()``:

  * SUCCESS path -- both gates pass: append a genuine ``SliceCommitVerified``
    (the origin-blind, scorecard-counted record, byte-shape-identical to a
    U2-/reverify-minted one) THEN the adjacent ``SliceAttestedFromBundle``
    provenance record carrying ``{slice_id, bundle_commit, reason, timestamp}``;
    emit ``SliceAttestedFromBundle`` to stdout, exit 0.
  * BLOCK path -- a gate fails (E1 or E2): append one ``SliceCommitBlocked``,
    emit ``SliceAttestBlocked`` naming the failing gate, exit 1, and -- the
    anti-theater guarantee -- NO ``SliceCommitVerified`` (red ATs are never
    attested).

DRIVING SURFACE (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des attest-bundled-slice`` invoked BY PATH against a crafted TEMP git repo, the
SAME hard-won harness slices 02/03 proved (``_run_des`` by-path dispatch +
git-fixture builders, REUSED verbatim). The one piece of new realism: the
fixtures carry a REAL contract-marked test (green for the success path, red for
the block path) so E2's whole-tree ``run_contract_gate`` suite GENUINELY passes
or fails -- never a flag, never a stub (invariant I-2, no gate fabrication).

LEDGER ASSERTIONS READ THE LEDGER FILE AS DATA. The success/block paths mutate
the AT-completion ledger ``.jsonl`` (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``).
This composition asserts on the ledger by READING THAT FILE as raw JSON lines
(the same shape the closure scorecard reads -- a line carrying the feature-id +
the event token + a ``slice-NN`` token), NEVER by importing ``AtCompletionLedger``
or any ``des.adapters.*`` (the slice-02 RC-2 lesson / Self-Review item 13 / F-005).
The scorecard-countability assertion (AT4) applies the scorecard's OWN predicate
verbatim against the ledger file.

ACTIVE-RED scaffold (atdd_pure -- NOT @skip). At HEAD ``main()`` is the slice-03
shape: P1, A2, P3, P5, P6 run, then it emits the
``BundledSliceAttestPreconditionsCleared`` placeholder (exit 0) -- it runs NO
gates and touches NO ledger. So at HEAD, for a fully-clear GREEN bundle slice:

  * the success terminal ``SliceAttestedFromBundle`` is never emitted -> the
    success exit/event assertions fire (got the placeholder, exit 0);
  * NO ``SliceCommitVerified`` line is appended -> the ledger-record + countability
    assertions fire (the ledger has no such line);
  * NO ``SliceAttestedFromBundle`` provenance line is appended -> the provenance
    assertion fires.

For a RED-contract-suite fixture at HEAD: main() STILL stops at the placeholder
(exit 0) BEFORE running E2, so the block terminal ``SliceAttestBlocked`` is never
emitted and the block assertion fires. Every Then turns a captured subprocess
observable OR a ledger-file read into a semantic AssertionError; no @skip, no
import / collection error in THIS process. GREEN once slice-04 DELIVER wires the
gate composition + ledger emit into main().
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_attest_bundled_slice import (
    ATTEST_SUBCOMMAND,
    AttestEvent,
    GateOutcomeFixture,
    LedgerEvent,
)


# Driving-port-only boundary (Self-Review item 13 / F-005, slice-02 RC-2): this
# composition imports ZERO ``des.adapters.*`` (or any production module). Every
# observable is subprocess-only against the crafted temp repo, and every ledger
# assertion reads the ledger ``.jsonl`` file AS DATA.
_FEATURE_ID = "f-attest-bundled-slice-fixture"

# The human-GO reason threaded through the success path. The provenance record
# must carry it verbatim (I-7), so the AT pins it to a recognisable sentinel.
_REASON = "bundle slice 01 landed green in the DESIGN bundle; attesting per runbook"

# The @slice-NN AT .feature carrying @feature-{id} + @{slice} tags -- the slice's
# real acceptance evidence (A2.a's binding artifact). One trailing happy scenario.
_SLICE_FEATURE = """\
@feature-{fid} @{slice}
Feature: bundled slice acceptance evidence

  Scenario: the bundled slice ships its acceptance criterion
    Given a bundle-delivered slice
    When the attestation runs
    Then the slice is certified green
"""

# The terminal attest events slice-04 cares about; the freshness-autoskip prefix
# line on stdout is a non-terminal line, parsed past.
_ATTEST_EVENTS = frozenset(e.value for e in AttestEvent)


@dataclass
class GateAndLedgerComposition:
    """Drives the REAL ``des attest-bundled-slice`` against gate-outcome temp repos."""

    tmp_path: Path
    _repo: Path | None = field(default=None)
    _feature_id: str = field(default=_FEATURE_ID)
    _slice_id: str = field(default="slice-01")
    _bundle_commit: str = field(default="HEAD")
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")
    _stderr: str = field(default="")

    # ---- given (fixture construction) ---------------------------------------

    def given_fixture(self, fixture: GateOutcomeFixture) -> None:
        """Build the temp-git repo shape for the gate-outcome ``fixture``."""
        builder = {
            GateOutcomeFixture.GREEN_BUNDLE_SLICE: self._build_green_bundle_slice,
            GateOutcomeFixture.RED_CONTRACT_SUITE: self._build_red_contract_suite,
        }[fixture]
        builder()

    # ---- when ---------------------------------------------------------------

    def when_operator_attests_the_bundled_slice(self) -> None:
        """Invoke the REAL ``des attest-bundled-slice`` against the fixture repo.

        Drives BY PATH through the in-tree dispatcher with ``cwd`` + ``--repo``
        on the crafted TEMP repo. ``--reason`` is the present, non-empty human GO
        (the A0 gate is satisfied so the run reaches the gate composition). REUSED
        verbatim from slices 02/03 -- the only difference is the fixture realism.
        """
        assert self._repo is not None, "given_fixture must run before the when"
        argv = [
            ATTEST_SUBCOMMAND,
            "--repo",
            str(self._repo),
            "--feature-id",
            self._feature_id,
            "--slice-id",
            self._slice_id,
            "--bundle-commit",
            self._bundle_commit,
            "--reason",
            _REASON,
        ]
        self._run_des(argv)

    # ---- then ---------------------------------------------------------------

    def then_attest_blocked_and_no_verification(self) -> None:
        """AT1 (anti-theater): a RED bundle slice is BLOCKED and NOT attested.

        Two observables, both required: (1) the run blocks -- exit 1, terminal
        ``SliceAttestBlocked``; (2) the ledger gains NO ``SliceCommitVerified``
        record for the slice (a red AT is never attested). The ledger check reads
        the ledger FILE as data -- the anti-theater guarantee is that a red suite
        cannot mint a verification.

        Active-RED at HEAD: main() stops at the ``BundledSliceAttestPreconditionsCleared``
        placeholder (exit 0) BEFORE running E2, so neither the block terminal nor
        a ledger mutation occurs -- both legs of the assertion fire.
        """
        event = self._terminal_event()
        assert self._exit_code == 1 and event == AttestEvent.ATTEST_BLOCKED.value, (
            "a bundle slice whose contract suite is RED on HEAD must be BLOCKED "
            f"with '{AttestEvent.ATTEST_BLOCKED.value}' (exit 1) -- E2 "
            "(run_contract_gate) runs the REAL whole-tree suite, RED -> rc!=0 -> "
            "the block path. At HEAD main() stops at "
            f"'{AttestEvent.PRECONDITIONS_CLEARED.value}' (exit 0) before any gate "
            f"runs. {self._observed()}"
        )
        assert not self._ledger_has_verification(self._slice_id), (
            "a BLOCKED (red-suite) bundle slice must gain NO SliceCommitVerified "
            "ledger record -- the anti-theater guarantee that red ATs are never "
            f"attested. {self._observed()}; ledger={self._ledger_text()!r}"
        )

    def then_slice_gains_a_verification_record(self) -> None:
        """AT2 (success): a green bundle slice gains a ``SliceCommitVerified`` record.

        The success path appends the origin-blind ``SliceCommitVerified`` record
        the scorecard counts. Asserted by READING the ledger FILE (raw JSON lines),
        never by importing ``AtCompletionLedger``. The run also exits 0 with the
        success terminal ``SliceAttestedFromBundle``.

        Active-RED at HEAD: main() stops at the placeholder (exit 0) WITHOUT
        running the gates or touching the ledger -- no record is appended, so the
        ledger-record assertion fires.
        """
        event = self._terminal_event()
        assert (
            self._exit_code == 0 and event == AttestEvent.ATTESTED_FROM_BUNDLE.value
        ), (
            "a green bundle slice (both gates pass) must SUCCEED with "
            f"'{AttestEvent.ATTESTED_FROM_BUNDLE.value}' (exit 0). At HEAD main() "
            f"stops at '{AttestEvent.PRECONDITIONS_CLEARED.value}' (exit 0) without "
            f"running the gate composition. {self._observed()}"
        )
        assert self._ledger_has_verification(self._slice_id), (
            "a successful attest must APPEND a genuine SliceCommitVerified ledger "
            "record for the slice (the origin-blind, scorecard-counted record). At "
            "HEAD main() touches no ledger -- the record is absent. "
            f"{self._observed()}; ledger={self._ledger_text()!r}"
        )

    def then_provenance_record_carries_reason_and_commit(self) -> None:
        """AT3 (success): the adjacent ``SliceAttestedFromBundle`` provenance record.

        The success path ALSO appends a distinct ``SliceAttestedFromBundle``
        provenance record (the loud audit trail, I-6) carrying the slice_id, the
        ``bundle_commit``, and the human ``--reason``. Asserted by READING the
        ledger FILE: a ``SliceAttestedFromBundle`` line for the slice that carries
        BOTH the bundle commit and the reason text.

        Active-RED at HEAD: no provenance record is appended (main() stops at the
        placeholder) -- the assertion fires.
        """
        record = self._ledger_provenance_record(self._slice_id)
        assert record is not None, (
            "a successful attest must APPEND an adjacent SliceAttestedFromBundle "
            "provenance record (the loud audit trail, I-6). At HEAD main() appends "
            f"nothing. {self._observed()}; ledger={self._ledger_text()!r}"
        )
        assert record.get("bundle_commit") == self._bundle_commit, (
            "the SliceAttestedFromBundle provenance record must carry the "
            f"bundle_commit ({self._bundle_commit!r}); got "
            f"{record.get('bundle_commit')!r}. {self._observed()}"
        )
        assert record.get("reason") == _REASON, (
            "the SliceAttestedFromBundle provenance record must carry the human "
            f"--reason verbatim ({_REASON!r}); got {record.get('reason')!r} -- the "
            f"I-7 human-witness audit trail. {self._observed()}"
        )

    def then_scorecard_counts_the_slice_as_delivered(self) -> None:
        """AT4 (the whole point): the verified slice is COUNTABLE.

        The emitted ``SliceCommitVerified`` makes the bundled slice count as
        DELIVERED by the closure scorecard's OWN rule -- a ledger line carrying
        the feature-id AND ``SliceCommitVerified`` AND a ``slice-NN`` token
        (``scripts/flow_v2_closure_scorecard.py:_slice_commits_verified``). This
        AT applies that exact predicate against the ledger FILE (a driving-port /
        data assertion, never a production import) -- proving the record is not
        just present but COUNTABLE.

        Active-RED at HEAD: the ledger has no such line -> the slice counts 0 ->
        the assertion fires.
        """
        counted = self._scorecard_counts_slice(self._feature_id, self._slice_id)
        assert counted, (
            "the SliceCommitVerified the success path emits must make the slice "
            "COUNTABLE by the closure scorecard's rule (a ledger line with the "
            "feature-id + 'SliceCommitVerified' + a slice-NN token); the bundled "
            "slice was blocked-counted-partial precisely BECAUSE no such line "
            "existed. At HEAD main() appends no record -> the slice counts 0. "
            f"{self._observed()}; ledger={self._ledger_text()!r}"
        )

    # ---- fixture builders ----------------------------------------------------

    def _build_green_bundle_slice(self) -> None:
        """SUCCESS fixture: a buried bundle slice whose real ATs go GREEN.

        A genuinely-buried slice-01 commit (P1 + P5 pass), a valid ``Slice-Id:
        slice-01`` trailer (A2.b branch 1), the @slice-01 .feature AT present
        (A2.a), no deferred tag (A2.c), a clean ledger (P3), slice-01 the P6 base
        case -- so every precondition AND A2 clears. Critically it carries a GREEN
        contract-marked test so E2's REAL whole-tree ``run_contract_gate`` suite
        run exits 0. The success path then appends SliceCommitVerified +
        SliceAttestedFromBundle.
        """
        _repo, slice_sha = self._buried_slice_repo("slice-01", contract_test="green")
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_red_contract_suite(self) -> None:
        """BLOCK fixture: the same green-shaped bundle slice but a RED contract test.

        Every precondition AND A2 clears (valid trailer, AT present, buried,
        predecessor-clear, no deferred tag), but the contract-marked test FAILS,
        so E2's REAL whole-tree suite run exits non-zero -> the block path:
        SliceCommitBlocked appended, SliceAttestBlocked emitted, exit 1, and NO
        SliceCommitVerified (the anti-theater guarantee). This is the load-bearing
        realism: the suite is GENUINELY red, not a flag.
        """
        _repo, slice_sha = self._buried_slice_repo("slice-01", contract_test="red")
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    # ---- fixture primitives (mirror slice-02 / test_reverify_slice_commit.py) -

    def _buried_slice_repo(
        self, slice_label: str, *, contract_test: str
    ) -> tuple[Path, str]:
        """A temp-git repo with a genuinely-buried slice commit (P1 + P5 pass).

        History (oldest -> newest): base (pytest.ini) -> the BUNDLE COMMIT
        carrying the @slice-NN .feature + a ``Slice-Id:`` trailer + a
        contract-marked test (GREEN or RED per ``contract_test``, so E2's real
        whole-tree run reflects the slice's actual state) -> a LATER commit that
        buries it (P5 strict-ancestor). Returns ``(repo, slice_commit_sha)``.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")

        self._write_slice_feature(repo, slice_label)
        self._write_contract_test(repo, passing=(contract_test == "green"))
        slice_sha = self._commit(
            repo, f"feat: {slice_label}\n\nSlice-Id: {slice_label}\n"
        )

        (repo / "later.txt").write_text("bury the slice commit\n", encoding="utf-8")
        self._commit(repo, "chore: bury the slice commit\n")
        return repo, slice_sha

    def _init_repo(self) -> Path:
        repo = self.tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        self._repo = repo
        return repo

    def _write_pytest_ini(self, repo: Path) -> None:
        (repo / "pytest.ini").write_text(
            "[pytest]\nmarkers =\n    unit: Unit tests\n"
            "    integration: Integration tests\n    acceptance: Acceptance tests\n",
            encoding="utf-8",
        )

    def _write_slice_feature(self, repo: Path, slice_label: str) -> None:
        features = repo / "tests" / "acceptance"
        features.mkdir(parents=True, exist_ok=True)
        (features / f"{slice_label}.feature").write_text(
            _SLICE_FEATURE.format(fid=self._feature_id, slice=slice_label),
            encoding="utf-8",
        )

    def _write_contract_test(self, repo: Path, *, passing: bool) -> None:
        """A real contract-marked test E2's whole-tree suite collects + runs.

        ``passing`` controls whether E2's REAL ``run_contract_gate`` run exits 0
        (success path) or non-zero (block path). This is the load-bearing realism:
        E2 runs the genuine suite, never a flag, so the fixture's pass/fail must
        come from a test that REALLY goes green or red.
        """
        (repo / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
        body = "assert 1 + 1 == 2" if passing else "assert 1 + 1 == 3"
        (repo / "tests" / "test_contract.py").write_text(
            "import pytest\n\n\n@pytest.mark.acceptance\n"
            f"def test_bundled_slice_contract_holds():\n    {body}\n",
            encoding="utf-8",
        )

    def _commit(self, repo: Path, message: str) -> str:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_des(self, argv: list[str]) -> None:
        """Invoke the REAL des dispatcher BY FILE PATH against the temp repo.

        ``cwd`` is the crafted temp repo so the dispatcher's runtime-freshness
        guard auto-skips via ``.git`` adjacency (a harmless prefix line on
        stdout); the terminal attest event is parsed past it. Running BY PATH
        (not ``-m des.cli``) exercises the in-tree dispatcher regardless of an
        editable-install shadow. REUSED verbatim from slices 02/03.
        """
        assert self._repo is not None
        self._exit_code, self._stdout, self._stderr = run_cli_in_process(
            argv, cwd=self._repo
        )

    # ---- stdout parsing -----------------------------------------------------

    def _terminal_record(self) -> dict[str, object]:
        """The last stdout JSON object whose ``event`` is an attest event.

        Skips non-terminal prefix lines (``des.runtime.freshness.*`` autoskip).
        Returns ``{}`` when no attest event was emitted (a hard crash) -- the
        Then then fails its assertion with the diagnostics.
        """
        terminal: dict[str, object] = {}
        for raw in self._stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("event") in _ATTEST_EVENTS:
                terminal = obj
        return terminal

    def _terminal_event(self) -> str:
        return str(self._terminal_record().get("event", ""))

    # ---- ledger-as-data reads (NO des.adapters import) ----------------------

    def _ledger_path(self) -> Path:
        """The AT-completion ledger ``.jsonl`` file for the fixture feature.

        Per-feature shape: ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` under
        the fixture repo (the AtCompletionLedger ledger_path convention). Read AS
        DATA -- this is the file path string, not a production import.
        """
        assert self._repo is not None
        return (
            self._repo
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{self._feature_id}.jsonl"
        )

    def _ledger_text(self) -> str:
        """The raw ledger ``.jsonl`` text, or '' when the file does not exist."""
        path = self._ledger_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")

    def _ledger_records(self) -> list[dict[str, object]]:
        """Every ledger record parsed as a JSON object (data, not a production read)."""
        records: list[dict[str, object]] = []
        for line in self._ledger_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
        return records

    def _ledger_has_verification(self, slice_id: str) -> bool:
        """True iff the ledger carries a ``SliceCommitVerified`` record for ``slice_id``."""
        return any(
            record.get("event") == LedgerEvent.SLICE_COMMIT_VERIFIED.value
            and record.get("slice_id") == slice_id
            for record in self._ledger_records()
        )

    def _ledger_provenance_record(self, slice_id: str) -> dict[str, object] | None:
        """The ``SliceAttestedFromBundle`` provenance record for ``slice_id``, else None."""
        for record in self._ledger_records():
            if (
                record.get("event") == LedgerEvent.SLICE_ATTESTED_FROM_BUNDLE.value
                and record.get("slice_id") == slice_id
            ):
                return record
        return None

    def _scorecard_counts_slice(self, feature_id: str, slice_id: str) -> bool:
        """Apply the closure scorecard's OWN counting predicate against the ledger.

        Mirrors ``scripts/flow_v2_closure_scorecard.py:_slice_commits_verified``
        verbatim: a ledger line carrying the feature-id AND ``SliceCommitVerified``
        AND a ``slice-NN`` token counts the slice as delivered. Re-implemented as a
        line scan over the ledger file (data) -- NOT a production import -- so the
        countability assertion stays a driving-port / data assertion.
        """
        slices: set[str] = set()
        for line in self._ledger_text().splitlines():
            if feature_id in line and "SliceCommitVerified" in line:
                slices.update(re.findall(r"slice-\d+[a-z]?", line))
        return slice_id in slices

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; slice_id={self._slice_id!r}; "
            f"bundle_commit={self._bundle_commit!r}; "
            f"stdout={self._stdout!r}; stderr={self._stderr!r}"
        )
