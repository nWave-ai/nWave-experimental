"""Composition root for f-attest-bundled-slice slice-02 ATs.

slice-02 scope (feature-delta sec.11 row 2 / sec.5): the REUSED preconditions
from ``des.cli._reverify_core`` are wired into ``attest_bundled_slice.main()`` so
``des attest-bundled-slice`` enforces, before the slice-03 A2 evidence check:

  * P1 -- ancestor:    ``--bundle-commit`` not an ancestor of HEAD -> refused.
  * P3 -- not-already-verified: a slice already carrying a SliceCommitVerified
          -> refused (idempotent).
  * P5 -- orphan-state: the bundle commit is HEAD / not strictly buried -> refused.
  * P6 -- predecessor-verified: slice-N (N>1) with slice-(N-1) unverified -> refused.

P3's corrupt-ledger -> ``LedgerIntegrityViolation`` branch is INHERITED VERBATIM
from ``_reverify_core`` and is already covered by reverify's own acceptance suite
(``tests/des/acceptance/test_reverify_slice_commit.py``), so it is NOT re-tested
at attest slice-02 -- the same code, the same coverage, no duplication. slice-02
ATs = P1 / P3-already-verified / P5 / P6 / all-clear (5, within the ceiling).

ONE driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
``des`` dispatcher invoked BY PATH (``python <src/des/cli/__main__.py> ...``)
against a crafted TEMP git repo (its own ``.git/`` + ``.nwave/`` ledger). The SUT
is the dispatcher + the ``attest-bundled-slice`` subcommand; the observables are
the process exit code + the terminal attest JSON event parsed from stdout (the
freshness autoskip line a developer-checkout temp repo emits is skipped over).

The git fixtures MIRROR reverify's own precondition ATs verbatim
(``tests/des/acceptance/test_reverify_slice_commit.py``): a buried green slice
(P1/P5 pass), a HEAD slice (P5 refuse), a side-branch commit (P1 refuse), an
already-verified ledger seeded via a REAL reverify mint (P3 refuse), a buried
slice-03 with an unverified slice-02 (P6 refuse), and the all-clear shape.

ACTIVE-RED scaffold (atdd_pure -- NOT @skip): at HEAD the slice-01 SCAFFOLD emits
``BundledSliceAttestNotApplicable`` (exit 0) for EVERY invocation, ignoring the
preconditions entirely (proven: the scaffold's ``main`` only parses args + emits
NotApplicable -- it never imports the precondition group). So a fixture that MUST
refuse currently gets NotApplicable exit 0 -- the refusal Then turns that captured
observable into a semantic AssertionError (expected ``SliceAttestRefused`` exit 1,
got the scaffold marker exit 0). GREEN once slice-02 DELIVER wires P1/P3/P5/P6
from the shared core into ``main()``. No @skip, no import / collection error in
THIS process.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.reverify_slice_commit import main as _reverify_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_attest_bundled_slice import (
    ATTEST_SUBCOMMAND,
    AttestEvent,
    AttestFixture,
)


# Driving-port-only boundary (Self-Review Checklist item 13 / F-005): this
# composition imports ZERO ``des.adapters.*`` (or any production module). Every
# behavioural assertion is subprocess-only. The ONE fixture that needs a
# pre-existing ledger record (P3 already-verified) seeds it by MINTING through a
# REAL ``des reverify-slice-commit`` subprocess -- which writes a genuine
# HMAC-valid ``SliceCommitVerified`` record into the fixture ledger -- never by
# importing ``AtCompletionLedger`` and never by hand-writing a JSONL line (the M7
# integrity check rejects a forged ``record_hash`` with LedgerIntegrityViolation).
_FEATURE_ID = "f-attest-bundled-slice-fixture"

# A green slice .feature carrying the @slice-NN + @feature-{id} tags -- the
# slice's real acceptance evidence (A2.a / P4 territory). slice-02's
# preconditions (P1/P3/P5/P6) run BEFORE A2, but the all-clear fixture carries
# the AT so the run does not trip an earlier check while we exercise P1/P3/P5/P6.
_SLICE_FEATURE = """\
@feature-{fid} @{slice}
Feature: bundled slice acceptance evidence

  Scenario: the bundled slice ships its acceptance criterion
    Given a bundle-delivered slice
    When the attestation runs
    Then the slice is certified green
"""

# The terminal attest events slice-02 cares about -- everything else on stdout
# (the freshness autoskip / skipped lines) is a non-terminal prefix.
_ATTEST_EVENTS = frozenset(e.value for e in AttestEvent)


@dataclass
class AttestPreconditionComposition:
    """Drives the REAL ``des attest-bundled-slice`` against crafted temp repos."""

    tmp_path: Path
    _repo: Path | None = field(default=None)
    _feature_id: str = field(default=_FEATURE_ID)
    _slice_id: str = field(default="slice-01")
    _bundle_commit: str = field(default="HEAD")
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")
    _stderr: str = field(default="")

    # ---- given (fixture construction) ---------------------------------------

    def given_fixture(self, fixture: AttestFixture) -> None:
        """Build the temp-git repo + ledger shape for ``fixture``."""
        builder = {
            AttestFixture.NON_ANCESTOR: self._build_non_ancestor,
            AttestFixture.ALREADY_VERIFIED: self._build_already_verified,
            AttestFixture.STILL_HEAD: self._build_still_head,
            AttestFixture.PREDECESSOR_UNVERIFIED: self._build_predecessor_unverified,
            AttestFixture.ALL_PRECONDITIONS_CLEAR: self._build_all_clear,
        }[fixture]
        builder()

    # ---- when ---------------------------------------------------------------

    def when_operator_attests_the_bundled_slice(self) -> None:
        """Invoke the REAL ``des attest-bundled-slice`` against the fixture repo.

        Drives BY PATH through the in-tree dispatcher (immune to an editable
        install shadowing ``des.cli.__main__`` for ``-m`` resolution), with
        ``cwd`` + ``--repo`` set to the crafted TEMP repo. ``--reason`` is a
        present, non-empty human GO (the A0 gate is slice-01's concern, satisfied
        here so the run reaches the slice-02 preconditions).
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

    def then_attest_refuses_on_precondition(self) -> None:
        """The command REFUSES on a reused precondition: ``SliceAttestRefused`` exit 1.

        Active-RED at HEAD: the scaffold ignores the preconditions and emits
        ``BundledSliceAttestNotApplicable`` (exit 0) -- so this fires until
        slice-02 DELIVER wires P1/P3/P5/P6. The discriminating oracle is the
        TERMINAL event name (the scaffold marker is structurally distinct from a
        precondition refusal), paired with exit 1.
        """
        event = self._terminal_event()
        assert self._exit_code == 1 and event == AttestEvent.REFUSED.value, (
            "a reused precondition (P1/P3/P5/P6) must fail-closed with "
            f"'{AttestEvent.REFUSED.value}' (exit 1); at HEAD the slice-01 scaffold "
            "ignores the preconditions and emits "
            f"'{AttestEvent.NOT_APPLICABLE.value}' (exit 0). {self._observed()}"
        )

    def then_attest_proceeds_past_the_preconditions(self) -> None:
        """All preconditions clear: the command does NOT refuse on a precondition.

        The all-clear fixture satisfies P1/P3/P5/P6, so the command must PROCEED
        INTO the post-precondition flow (A2 + gates, slices 03-04) rather than
        emitting a precondition refusal. The active-RED oracle is the
        SCAFFOLD-MARKER detail: at HEAD ``main`` short-circuits to NotApplicable
        BEFORE evaluating any precondition (the slice-01 detail names "slices
        02-04"); once slice-02 wires the preconditions, an all-clear run reaches
        the post-precondition stage whose detail names the slice-03/04 tail. So
        this asserts the run consumed-and-cleared the preconditions -- it must NOT
        be the slice-01 short-circuit, and must NOT be a refusal.
        """
        event = self._terminal_event()
        # It must NOT be a precondition refusal (the preconditions are all clear).
        assert event != AttestEvent.REFUSED.value, (
            "an all-clear fixture (P1/P3/P5/P6 all satisfied) must NOT refuse on a "
            f"precondition; got '{event}'. {self._observed()}"
        )
        # And it must have PASSED THROUGH the preconditions, not short-circuited
        # at the slice-01 scaffold (which emits NotApplicable BEFORE evaluating
        # any precondition). The slice-01 short-circuit detail names "slices
        # 02-04"; once the preconditions are wired, the post-precondition detail
        # names the slice-03/04 tail. Active-RED at HEAD on the short-circuit.
        detail = self._terminal_detail()
        assert "02-04" not in detail, (
            "an all-clear run must PROCEED PAST the slice-02 preconditions into the "
            "A2/gate flow (slices 03-04), not short-circuit at the slice-01 "
            "scaffold; at HEAD main emits the slice-01 NotApplicable marker "
            f"('...slices 02-04') before any precondition runs. {self._observed()}"
        )

    # ---- fixture builders (mirror reverify's precondition ATs) ---------------

    def _build_non_ancestor(self) -> None:
        """P1: the bundle commit lives on a SIDE BRANCH, not an ancestor of HEAD.

        History: base -> (branch off) side commit carrying the slice AT;
        HEAD advances on the original branch. ``git merge-base --is-ancestor
        <side> HEAD`` is false -> P1 refuses.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")
        base = self._head(repo)

        # Side branch carrying the slice AT.
        self._git(repo, "checkout", "-q", "-b", "side")
        self._write_slice_feature(repo, "slice-01")
        side_sha = self._commit(
            repo, "feat: slice-01 on a side branch\n\nSlice-Id: slice-01\n"
        )

        # HEAD advances on the original branch -- the side commit is NOT an ancestor.
        self._git(repo, "checkout", "-q", self._default_branch(repo, base))
        (repo / "later.txt").write_text("advance HEAD\n", encoding="utf-8")
        self._commit(repo, "chore: advance HEAD off the side branch\n")

        self._slice_id = "slice-01"
        self._bundle_commit = side_sha

    def _build_already_verified(self) -> None:
        """P3: the slice already carries a SliceCommitVerified ledger record.

        A buried green slice (P1/P5 pass) whose ledger already records
        ``SliceCommitVerified`` for slice-01 -> P3 refuses (idempotent no-op).

        The pre-existing verification is MINTED by a REAL ``des
        reverify-slice-commit`` subprocess against this same fixture -- which runs
        the genuine gate composition and appends an HMAC-valid
        ``SliceCommitVerified`` record. No ``AtCompletionLedger`` import and no
        hand-written JSONL line (a forged ``record_hash`` would trip the M7
        integrity check). The fixture carries a contract-marked test so reverify's
        E2 gate passes and the mint succeeds.
        """
        repo, slice_sha = self._buried_slice_repo("slice-01", with_contract_test=True)
        self._mint_verified_via_reverify(repo, "slice-01", slice_sha)
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    def _build_still_head(self) -> None:
        """P5: the bundle commit IS HEAD -- nothing buries it.

        base -> slice commit (HEAD). ``git rev-list <slice>..HEAD`` is empty
        -> P5 refuses (a still-HEAD slice is the U2 gate's domain).
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")
        self._write_slice_feature(repo, "slice-01")
        slice_sha = self._commit(repo, "feat: slice-01 at HEAD\n\nSlice-Id: slice-01\n")

        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha  # == HEAD

    def _build_predecessor_unverified(self) -> None:
        """P6: attest slice-03 whose predecessor slice-02 is unverified.

        A buried slice-03 commit; the ledger carries NO SliceCommitVerified for
        slice-02 -> P6 refuses (reverify cannot mint an out-of-order slice).
        """
        _repo, slice_sha = self._buried_slice_repo("slice-03")
        self._slice_id = "slice-03"
        self._bundle_commit = slice_sha

    def _build_all_clear(self) -> None:
        """All-clear: P1/P3/P5/P6 all satisfiable for slice-01.

        A genuinely-buried slice-01 commit (P1 + P5 pass), a clean ledger with no
        prior SliceCommitVerified for slice-01 (P3 passes), slice-01 the base case
        of P6 (passes vacuously). The command must proceed past the preconditions.
        """
        _repo, slice_sha = self._buried_slice_repo("slice-01")
        self._slice_id = "slice-01"
        self._bundle_commit = slice_sha

    # ---- fixture primitives (mirror test_reverify_slice_commit.py) -----------

    def _buried_slice_repo(
        self, slice_label: str, *, with_contract_test: bool = False
    ) -> tuple[Path, str]:
        """A temp-git repo with a genuinely-buried slice commit (P1 + P5 pass).

        History (oldest -> newest):
          1. base commit (pytest.ini).
          2. SLICE COMMIT -- carries the @slice-NN .feature + Slice-Id trailer
             (and, when ``with_contract_test``, a green contract-marked test so a
             REAL reverify mint can pass its E2 whole-tree gate).
          3. a LATER commit -- buries the slice commit (P5: strict ancestor).

        Returns ``(repo, slice_commit_sha)``.
        """
        repo = self._init_repo()
        self._write_pytest_ini(repo)
        self._commit(repo, "chore: base\n")

        self._write_slice_feature(repo, slice_label)
        if with_contract_test:
            self._write_contract_test(repo)
        slice_sha = self._commit(
            repo, f"feat: {slice_label}\n\nSlice-Id: {slice_label}\n"
        )

        (repo / "later.txt").write_text("bury the slice commit\n", encoding="utf-8")
        self._commit(repo, "chore: bury the slice commit\n")

        return repo, slice_sha

    def _mint_verified_via_reverify(
        self, repo: Path, slice_label: str, slice_sha: str
    ) -> None:
        """Seed a genuine SliceCommitVerified record via a REAL reverify run.

        Drives the reverify EDGE ``des.cli.reverify_slice_commit.main(argv)``
        IN-PROCESS against the fixture, which runs reverify's gate composition for
        real and appends an HMAC-valid ``SliceCommitVerified`` record to the
        fixture ledger. Driving-port-only (the EDGE ``main``, never a leaf), no
        hand-forged ``record_hash``. Asserts the mint succeeded so a failed seed
        never masquerades as the P3-refusal-under-test.
        """
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--repo",
                str(repo),
                "--feature-id",
                self._feature_id,
                "--slice-id",
                slice_label,
                "--commit",
                slice_sha,
            ],
            cwd=repo,
            main=_reverify_main,
        )
        assert exit_code == 0, (
            "the P3 already-verified fixture must SEED a genuine SliceCommitVerified "
            "record via a REAL reverify in-process run; the mint failed -- "
            f"rc={exit_code}; stdout={stdout!r}; "
            f"stderr={stderr!r}"
        )

    def _write_contract_test(self, repo: Path) -> None:
        (repo / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
        (repo / "tests" / "test_contract.py").write_text(
            "import pytest\n\n\n@pytest.mark.acceptance\n"
            "def test_bundled_slice_contract_holds():\n    assert 1 + 1 == 2\n",
            encoding="utf-8",
        )

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

    def _git(self, repo: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        ).stdout

    def _commit(self, repo: Path, message: str) -> str:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
        return self._git(repo, "rev-parse", "HEAD").strip()

    def _head(self, repo: Path) -> str:
        return self._git(repo, "rev-parse", "HEAD").strip()

    def _default_branch(self, repo: Path, base_sha: str) -> str:
        """The branch name HEAD pointed at before the side checkout (master/main)."""
        name = self._git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        # After ``checkout side`` the current branch is ``side``; the original is
        # whatever ``git branch --contains base`` names that is NOT ``side``.
        branches = self._git(repo, "branch", "--format=%(refname:short)").split()
        for candidate in branches:
            if candidate != "side":
                return candidate
        return name

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_des(self, argv: list[str]) -> None:
        """Invoke the REAL des dispatcher BY FILE PATH against the temp repo.

        ``cwd`` is the crafted temp repo so the dispatcher's runtime-freshness
        guard auto-skips via ``.git`` adjacency (a harmless prefix line on
        stdout) rather than running the content probe; the terminal attest event
        is parsed past it. Running BY PATH (not ``-m des.cli``) exercises the
        in-tree dispatcher regardless of an editable-install shadow.
        """
        assert self._repo is not None
        self._exit_code, self._stdout, self._stderr = run_cli_in_process(
            argv, cwd=self._repo
        )

    # ---- stdout parsing -----------------------------------------------------

    def _terminal_record(self) -> dict[str, object]:
        """The last stdout JSON object whose ``event`` is an attest event.

        Skips non-terminal prefix lines (``des.runtime.freshness.*`` autoskip /
        skipped notices). Returns ``{}`` when no attest event was emitted (e.g. a
        hard crash) -- the Then then fails its assertion with the diagnostics.
        """
        terminal: dict[str, object] = {}
        for line in self._stdout.splitlines():
            line = line.strip()
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

    def _terminal_detail(self) -> str:
        return str(self._terminal_record().get("detail", ""))

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; slice_id={self._slice_id!r}; "
            f"bundle_commit={self._bundle_commit!r}; "
            f"stdout={self._stdout!r}; stderr={self._stderr!r}"
        )
