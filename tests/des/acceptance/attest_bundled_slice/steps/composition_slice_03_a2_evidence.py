"""Composition root for f-attest-bundled-slice slice-03 ATs (the A2 contract).

slice-03 scope (feature-delta sec.5 step 3 / sec.11 row 3): A2 REPLACES reverify's
inherited P2 (trailer-name-must-CONTAIN-slice) with the bundle-binding evidence:

  * A2.a -- real-AT presence: the slice's @slice-NN .feature AT is present in the
            bundle commit's tree OR recoverable from commit~1 (reverify P4 promoted
            to the binding evidence; ``_in_commit_at_presence`` + the
            ``_tracked_before_at_presence`` fallback, reused verbatim by DELIVER).
  * A2.b -- TWO-BRANCH carpaccio/wave-trailer presence:
                bool(extract_slice_ids(msg)) OR _has_step_id_line(msg)
            branch 1 = a Slice-Id:/Step-Id: trailer NAMING a slice-NN; branch 2 =
            a raw ``Step-Id:`` line regardless of its value (the NEW
            ``_has_step_id_line`` helper). THE CRUX: a ``Step-Id: <feature>-design``
            bundle commit (extract_slice_ids -> []) must PASS via branch 2 -- else
            f-design's 531cfb59a is refused (the C1/C2 finding). A commit with
            NEITHER trailer is refused (the arbitrary-hotfix guard).
  * A2.c -- no deferred scenario: the matched @slice-NN .feature is scanned for
            @skip/@xfail/@wip; any tag -> refused (the H2 anti-theater hole -- a
            deferred scenario must not be attested as if exercised).

DRIVING SURFACE (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des attest-bundled-slice`` invoked BY PATH against a crafted TEMP git repo, the
SAME hard-won harness slice-02 proved -- ``_run_des`` by-path dispatch +
``_mint_verified_via_reverify`` subprocess seeding + git-fixture builders, REUSED
verbatim. This composition imports ZERO ``des.adapters.*`` (or any production
module): every behavioural assertion is subprocess-only; the one seeded ledger
record is minted via a REAL reverify subprocess, never an ``AtCompletionLedger``
import (driving-port-only boundary, Self-Review item 13 / F-005 / slice-02 RC-2).

ACTIVE-RED scaffold (atdd_pure -- NOT @skip). At HEAD ``main()`` is the slice-02
shape: it runs the shared ``_preconditions`` (P1->P2->P3->P4->P5->P6) then emits
``BundledSliceAttestPreconditionsCleared`` (exit 0). slice-03 DELIVER restructures
``main()`` to compose P1, A2 (replacing the strict P2/P4), P3, P5, P6. So at HEAD:

  * STEP_ID_ONLY (crux) + DIFFERENT-slice trailer -> inherited P2 REFUSES now
    (slice ∉ extract_slice_ids); slice-03 A2.b branch 2 / A2.a will PROCEED. The
    proceed assertion is active-RED (refused now, proceeds at GREEN).
  * NO_SLICE_AT -> inherited P4 refuses now WITH the reverify-vocabulary
    diagnosis; A2.a will refuse with its OWN diagnosis. The oracle asserts the
    refusal is NOT the inherited P4 text -> active-RED (HEAD text present now).
  * NO_TRAILER -> inherited P2 refuses now WITH the reverify-vocabulary
    diagnosis; A2.b will refuse with its OWN diagnosis. Same discriminating
    oracle -> active-RED.
  * XFAIL_SCENARIO -> P1-P6 all pass at HEAD (valid trailer, AT present, buried,
    predecessor-clear) -> PROCEEDS past the preconditions (exit 0); A2.c will
    REFUSE. The refusal assertion is active-RED (proceeds now, refuses at GREEN).

Every Then turns a captured subprocess observable into a semantic AssertionError;
no @skip, no import / collection error in THIS process.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_attest_bundled_slice import (
    ATTEST_SUBCOMMAND,
    REVERIFY_P2_DIAGNOSIS,
    REVERIFY_P4_DIAGNOSIS,
    A2Fixture,
    AttestEvent,
)


# Driving-port-only boundary (Self-Review item 13 / F-005, slice-02 RC-2): this
# composition imports ZERO ``des.adapters.*`` (or any production module). Every
# observable is subprocess-only against the crafted temp repo + its own ledger.
_FEATURE_ID = "f-attest-bundled-slice-fixture"

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

# The SAME AT shape but with an @xfail tag on the @slice-NN scenario (the H2
# deferred-scenario theater hole A2.c closes). The scenario is tagged @xfail ON
# TOP of the @slice-NN tag, so A2.c's raw-line scan of the matched .feature must
# find the @xfail and refuse. (The fixture .feature is only RAW-LINE SCANNED by
# the CLI -- never collected by pytest in the temp repo -- so @xfail is inert.)
_XFAIL_SLICE_FEATURE = """\
@feature-{fid} @{slice}
Feature: bundled slice with a deferred scenario

  @{slice} @xfail
  Scenario: the bundled slice criterion is deferred
    Given a bundle-delivered slice
    When the attestation runs
    Then the slice is NOT yet exercised
"""

# The terminal attest events slice-03 cares about; everything else on stdout
# (the freshness autoskip prefix) is a non-terminal line, parsed past.
_ATTEST_EVENTS = frozenset(e.value for e in AttestEvent)


@dataclass
class A2EvidenceComposition:
    """Drives the REAL ``des attest-bundled-slice`` against A2-evidence temp repos."""

    tmp_path: Path
    _repo: Path | None = field(default=None)
    _feature_id: str = field(default=_FEATURE_ID)
    _slice_id: str = field(default="slice-01")
    _bundle_commit: str = field(default="HEAD")
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")
    _stderr: str = field(default="")

    # ---- given (fixture construction) ---------------------------------------

    def given_fixture(self, fixture: A2Fixture) -> None:
        """Build the temp-git repo shape for the A2 ``fixture``."""
        builder = {
            A2Fixture.NO_SLICE_AT: self._build_no_slice_at,
            A2Fixture.NO_TRAILER: self._build_no_trailer,
            A2Fixture.STEP_ID_ONLY: self._build_step_id_only,
            A2Fixture.DIFFERENT_SLICE_TRAILER: self._build_different_slice_trailer,
            A2Fixture.XFAIL_SCENARIO: self._build_xfail_scenario,
        }[fixture]
        builder()

    # ---- when ---------------------------------------------------------------

    def when_operator_attests_the_bundled_slice(self) -> None:
        """Invoke the REAL ``des attest-bundled-slice`` against the fixture repo.

        Drives BY PATH through the in-tree dispatcher (immune to an editable
        install shadowing ``des.cli.__main__`` for ``-m`` resolution), ``cwd`` +
        ``--repo`` set to the crafted TEMP repo. ``--reason`` is a present,
        non-empty human GO (the A0 gate is slice-01's concern, satisfied so the
        run reaches the A2 evidence check).
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
            "bundle slice landed green; attesting per recovery runbook",
        ]
        self._run_des(argv)

    # ---- then ---------------------------------------------------------------

    def then_attest_refuses_on_absent_at(self) -> None:
        """A2.a refuses: ``SliceAttestRefused`` exit 1 on an ABSENT @slice-NN AT.

        Active-RED at HEAD: the inherited P4 ALSO refuses an absent AT (exit 1),
        but with its reverify-vocabulary diagnosis. slice-03's A2.a must produce
        an A2-specific refusal instead. The discriminating oracle: a genuine
        refusal (exit 1, SliceAttestRefused) whose error does NOT quote the
        inherited P4 text. At HEAD the P4 text IS present -> the assertion fires.
        """
        event = self._terminal_event()
        error = self._terminal_error()
        assert self._exit_code == 1 and event == AttestEvent.REFUSED.value, (
            "an absent @slice-NN AT must fail-closed with "
            f"'{AttestEvent.REFUSED.value}' (exit 1) via A2.a. {self._observed()}"
        )
        assert REVERIFY_P4_DIAGNOSIS not in error, (
            "the absent-AT refusal must come from slice-03's A2.a evidence check, "
            "not the INHERITED reverify P4 precondition; at HEAD main() still "
            "composes the strict _preconditions, so the refusal quotes the "
            f"reverify P4 text {REVERIFY_P4_DIAGNOSIS!r}. Once A2 replaces P2/P4, "
            f"the A2.a refusal carries its own diagnosis. {self._observed()}"
        )

    def then_attest_refuses_on_absent_trailer(self) -> None:
        """A2.b refuses: ``SliceAttestRefused`` exit 1 on a NEITHER-trailer commit.

        Active-RED at HEAD: the inherited P2 ALSO refuses (extract_slice_ids=[],
        slice ∉ []), but with its reverify-vocabulary diagnosis. slice-03's A2.b
        (both branches fail -> refuse) must produce an A2-specific refusal. The
        oracle: a genuine refusal (exit 1, SliceAttestRefused) whose error does
        NOT quote the inherited P2 text. At HEAD the P2 text IS present.
        """
        event = self._terminal_event()
        error = self._terminal_error()
        assert self._exit_code == 1 and event == AttestEvent.REFUSED.value, (
            "a NEITHER-Slice-Id-NOR-Step-Id bundle commit must fail-closed with "
            f"'{AttestEvent.REFUSED.value}' (exit 1) via A2.b. {self._observed()}"
        )
        assert REVERIFY_P2_DIAGNOSIS not in error, (
            "the no-trailer refusal must come from slice-03's A2.b two-branch "
            "predicate, not the INHERITED reverify P2; at HEAD main() still "
            "composes the strict _preconditions, so the refusal quotes the "
            f"reverify P2 text {REVERIFY_P2_DIAGNOSIS!r}. Once A2.b replaces P2, "
            f"the refusal carries its own diagnosis. {self._observed()}"
        )

    def then_attest_not_refused_on_the_trailer_ground(self) -> None:
        """A2.b branch-2 PASSES (THE CRUX): the run is NOT refused on the trailer.

        A ``Step-Id: <feature>-design``-only bundle commit (extract_slice_ids ->
        [], but a raw ``Step-Id:`` line present) carrying the @slice-NN AT must
        satisfy A2.b via branch 2 (``_has_step_id_line``). The observable is "the
        slice is NOT refused on the trailer ground" -- A2.a (AT present) and A2.b
        (Step-Id line) hold, so the run proceeds to the gate/ledger tail
        (slice-04). It must NOT emit a precondition/A2 refusal.

        Active-RED at HEAD: the inherited P2 REFUSES this commit (slice ∉
        extract_slice_ids=[]) -> SliceAttestRefused exit 1. So the "not refused"
        assertion fires until slice-03 DELIVER replaces P2 with the A2.b
        two-branch predicate. This AT proves f-design's 531cfb59a case unblocks.
        """
        event = self._terminal_event()
        error = self._terminal_error()
        # It must NOT be a refusal (A2.a holds, A2.b branch 2 holds).
        assert event != AttestEvent.REFUSED.value, (
            "a Step-Id:-only bundle commit carrying the @slice-NN AT must NOT be "
            "refused on the trailer ground -- A2.b branch 2 (_has_step_id_line) "
            "passes even though extract_slice_ids returns []. At HEAD the "
            "inherited P2 refuses it (slice not in the trailer set); once A2.b "
            f"replaces P2 the run proceeds. {self._observed()}"
        )
        # Belt-and-braces: the refusal, if any, must not be the inherited P2 text.
        assert REVERIFY_P2_DIAGNOSIS not in error, (
            "the Step-Id:-only crux commit must clear the trailer ground via "
            "A2.b branch 2; at HEAD the inherited P2 refuses it with "
            f"{REVERIFY_P2_DIAGNOSIS!r}. {self._observed()}"
        )

    def then_attest_not_refused_on_a_present_slice_trailer(self) -> None:
        """A2.b branch-1 PRESENCE (THE CANONICAL BUNDLE CASE, sec.11 row 3).

        A bundle commit whose ``Slice-Id:`` trailer names a DIFFERENT slice
        (slice-99) while carrying THIS slice's (@slice-01) AT -- the
        f-deliver-wave-migration shape. A2.b branch 1 is ``bool(['slice-99'])``
        = True (PRESENCE of a recognised slice trailer, NOT slice ∈ membership),
        so the run is NOT refused on the trailer ground; A2.a (AT present) also
        holds, so it proceeds to the gate/ledger tail (slice-04).

        This AT pins A2.b branch 1 as PRESENCE, not MEMBERSHIP: a DELIVER that
        implements ``slice_id in extract_slice_ids(msg) OR _has_step_id_line(msg)``
        would pass the Step-Id-only crux AND all three refusals yet REFUSE this
        canonical case (slice-01 not in ['slice-99']) -- breaking f-deliver's
        unblock. The behavioural oracle (event != REFUSED) is the ONLY check
        the Step-Id-only AT does not already cover.

        Active-RED at HEAD: the inherited P2 REFUSES this commit ('slice-01' not
        in the trailer set ['slice-99']) -> SliceAttestRefused exit 1. So the
        "not refused" assertion fires until slice-03 DELIVER replaces the strict
        membership P2 with the presence-based A2.b branch 1.
        """
        event = self._terminal_event()
        error = self._terminal_error()
        # It must NOT be a refusal (A2.a holds, A2.b branch 1 PRESENCE holds).
        assert event != AttestEvent.REFUSED.value, (
            "a bundle commit trailing a DIFFERENT slice (Slice-Id: slice-99) but "
            "carrying THIS slice's (@slice-01) AT must NOT be refused on the "
            "trailer ground -- A2.b branch 1 is bool(extract_slice_ids)=PRESENCE, "
            "not slice-membership. At HEAD the inherited P2 refuses it ('slice-01' "
            "not in ['slice-99']); once A2.b branch 1 replaces the membership P2 "
            f"the run proceeds. This pins PRESENCE-not-membership. {self._observed()}"
        )
        # Belt-and-braces: the refusal, if any, must not be the inherited P2 text
        # (the membership refusal). Distinguishes the canonical-case pass from the
        # HEAD membership refusal even if a future A2 emits a different non-refused
        # terminal event.
        assert REVERIFY_P2_DIAGNOSIS not in error, (
            "the canonical bundle commit (different-slice trailer + this slice's "
            "AT) must clear the trailer ground via A2.b branch 1 PRESENCE; at HEAD "
            f"the inherited membership P2 refuses it with {REVERIFY_P2_DIAGNOSIS!r}. "
            f"{self._observed()}"
        )

    def then_attest_refuses_on_deferred_scenario(self) -> None:
        """A2.c refuses: ``SliceAttestRefused`` exit 1 on an @xfail/@skip scenario.

        The @slice-NN scenario carries an @xfail tag (deferred / expected-fail
        theater). A2.c scans the matched .feature for @skip/@xfail/@wip and
        refuses. Active-RED at HEAD: P1-P6 all pass (valid Slice-Id trailer, AT
        present, buried, predecessor-clear) -> main() PROCEEDS past the
        preconditions and emits BundledSliceAttestPreconditionsCleared (exit 0).
        So the refusal assertion fires until slice-03 DELIVER adds A2.c.
        """
        event = self._terminal_event()
        assert self._exit_code == 1 and event == AttestEvent.REFUSED.value, (
            "an @xfail/@skip-tagged @slice-NN scenario is a deferred-scenario "
            "theater hole that A2.c must close with "
            f"'{AttestEvent.REFUSED.value}' (exit 1); at HEAD all of P1-P6 pass "
            "and the run proceeds past the preconditions "
            f"('{AttestEvent.PRECONDITIONS_CLEARED.value}', exit 0) because A2.c "
            f"is not yet wired. {self._observed()}"
        )

    # ---- fixture builders ----------------------------------------------------

    def _build_no_slice_at(self) -> None:
        """A2.a: a buried bundle commit (+ commit~1) carrying NO @slice-01 AT.

        A valid ``Slice-Id: slice-01`` trailer is present (so once A2 replaces P2
        the trailer ground is satisfied and A2.a -- absent AT -- is the sole
        refusal ground). NO @slice-01 .feature lands in the bundle commit OR its
        parent. At HEAD the inherited P4 refuses with the reverify-vocabulary
        text; the oracle discriminates that from the A2.a diagnosis.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")
        # Bundle commit: a non-.feature change + a valid Slice-Id trailer, NO AT.
        (repo / "production.py").write_text("x = 1\n", encoding="utf-8")
        slice_sha = self._commit(
            repo,
            "feat: slice-01 production with NO acceptance AT\n\nSlice-Id: slice-01\n",
        )
        (repo / "later.txt").write_text("bury the bundle commit\n", encoding="utf-8")
        self._commit(repo, "chore: bury the bundle commit\n")
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_no_trailer(self) -> None:
        """A2.b: a buried bundle commit carrying the @slice-01 AT but NO trailer.

        An arbitrary non-spine hotfix: the @slice-01 .feature IS present (A2.a
        holds), but the commit message has NEITHER a ``Slice-Id:`` NOR a
        ``Step-Id:`` line -> both A2.b branches fail -> refused. At HEAD the
        inherited P2 refuses (extract_slice_ids=[], slice ∉ []) with its
        reverify-vocabulary text; the oracle discriminates.
        """
        _repo, slice_sha = self._buried_slice_repo(
            "slice-01", commit_message="fix: a hotfix carrying the AT but no trailer\n"
        )
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_step_id_only(self) -> None:
        """A2.b branch-2 CRUX: a ``Step-Id: <feature>-design``-only bundle commit.

        Mirrors f-design's 531cfb59a: a Step-Id: trailer whose value is a
        FEATURE-id (not a slice-NN), so ``extract_slice_ids`` returns [] (branch
        1 fails), but a raw ``Step-Id:`` line IS present (branch 2 passes). The
        @slice-01 AT is present (A2.a holds). Once A2.b replaces P2, the run is
        NOT refused on the trailer ground. At HEAD the inherited P2 refuses it.
        """
        _repo, slice_sha = self._buried_slice_repo(
            "slice-01",
            commit_message=(
                "feat: f-design slices bundled in the DESIGN commit\n\n"
                "Step-Id: f-design-wave-migration\n"
            ),
        )
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_different_slice_trailer(self) -> None:
        """A2.b branch-1 PRESENCE / CANONICAL BUNDLE CASE (sec.11 row 3).

        Mirrors f-deliver-wave-migration's bundle (18b1930f5 trailered
        ``Slice-Id: slice-01`` while covering slices 02+): the ``Slice-Id:``
        trailer names a DIFFERENT slice (slice-99) than the one being attested
        (slice-01), while the bundle commit CARRIES the @slice-01 AT. So
        ``extract_slice_ids`` -> ['slice-99'] (non-empty), A2.b branch 1
        ``bool(['slice-99'])`` = True (PRESENCE), and A2.a (the @slice-01 AT) is
        present -> NOT refused on the trailer ground. At HEAD the inherited
        membership P2 refuses it ('slice-01' not in ['slice-99']).
        """
        _repo, slice_sha = self._buried_slice_repo(
            "slice-01",
            commit_message=(
                "feat: a bundle commit trailered for a different slice\n\n"
                "Slice-Id: slice-99\n"
            ),
        )
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_xfail_scenario(self) -> None:
        """A2.c: a buried bundle commit whose @slice-01 scenario is @xfail-tagged.

        A valid ``Slice-Id: slice-01`` trailer + the @slice-01 .feature is
        present, BUT its scenario carries an @xfail tag (deferred theater). At
        HEAD P1-P6 all pass -> the run proceeds (exit 0). A2.c's raw-line scan
        must find the @xfail and refuse. The .feature is only scanned, never
        collected, so @xfail is inert in the temp repo.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")
        self._write_xfail_slice_feature(repo, "slice-01")
        slice_sha = self._commit(
            repo,
            "feat: slice-01 with a deferred @xfail scenario\n\nSlice-Id: slice-01\n",
        )
        (repo / "later.txt").write_text("bury the bundle commit\n", encoding="utf-8")
        self._commit(repo, "chore: bury the bundle commit\n")
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    # ---- fixture primitives (mirror slice-02 / test_reverify_slice_commit.py) -

    def _buried_slice_repo(
        self, slice_label: str, *, commit_message: str
    ) -> tuple[Path, str]:
        """A temp-git repo with a genuinely-buried slice commit (P1 + P5 pass).

        History (oldest -> newest): base (pytest.ini) -> the BUNDLE COMMIT
        carrying the @slice-NN .feature with the caller-chosen ``commit_message``
        (which controls the trailer shape A2.b discriminates on) -> a LATER
        commit that buries it (P5 strict-ancestor). Returns ``(repo, sha)``.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")
        self._write_slice_feature(repo, slice_label)
        slice_sha = self._commit(repo, commit_message)
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

    def _write_xfail_slice_feature(self, repo: Path, slice_label: str) -> None:
        features = repo / "tests" / "acceptance"
        features.mkdir(parents=True, exist_ok=True)
        (features / f"{slice_label}.feature").write_text(
            _XFAIL_SLICE_FEATURE.format(fid=self._feature_id, slice=slice_label),
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
        editable-install shadow. REUSED verbatim from slice-02.
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

    def _terminal_error(self) -> str:
        """The terminal record's diagnosis text (``error`` then ``detail``).

        A precondition / A2 refusal carries its diagnosis in ``error``; the
        proceed placeholder carries ``detail``. The discriminating oracle reads
        whichever is present so the inherited-P2/P4 vocabulary check holds on a
        refusal AND the proceed-path detail is inspectable.
        """
        record = self._terminal_record()
        return str(record.get("error", "")) + " " + str(record.get("detail", ""))

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; slice_id={self._slice_id!r}; "
            f"bundle_commit={self._bundle_commit!r}; "
            f"stdout={self._stdout!r}; stderr={self._stderr!r}"
        )
