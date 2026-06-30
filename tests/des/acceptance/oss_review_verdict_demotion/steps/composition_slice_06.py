"""Composition root for the oss-review-verdict-demotion S6 acceptance slice.

Mandate 13 (Driving-Port-Only Boundary, Layer 3 subprocess) + Mandate-12
(Pillar 3). Drives TWO production CLIs end-to-end as subprocess black boxes:

  * ``des verify-commit-trailers --commit <sha>`` -- the REPURPOSED verifier
    (D-verify-repurpose). Post-demotion it resolves the commit's ``Slice-Id:``
    trailer and AUDITS the AT-completion ledger record for that slice, reusing
    the carpaccio gate's record-presence logic. The audit window over the gate's
    verdict logic, never a second verifier.
  * ``des carpaccio-slice-gate --feature-id <f> --entering-slice <s>`` -- the
    AT-review gate, co-driven in the no-drift scenario to prove the two surfaces
    reach the SAME verdict from the SAME ledger record.

NO direct-domain import of ``check_at_review`` or any ``verify_commit_trailers``
internal at the step boundary -- both SUTs are exercised only through the ``des``
dispatcher subprocess. The observable surface is the process exit code + the
structured JSON payload, nothing else.

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a real ``git init``
work-tree under tmp_path carrying a commit whose body has a ``Slice-Id: slice-NN``
trailer (read through the production git commit-read port), PLUS the
AT-completion ledger + feature-delta slice plan + the slice ``.feature`` file the
carpaccio record logic reads. NO reviewer signing key is provisioned anywhere --
the repurposed verifier never resolves one.

RED contract (fail-for-right-reason): on the pre-demotion tree
``verify-commit-trailers`` is a GIT-TRAILER HMAC verifier -- it parses
``Reviewed-by:``/``Verdict-Payload:`` trailers and recomputes an HMAC. The S6
commits carry a ``Slice-Id:`` trailer and NO ``Reviewed-by:``/``Verdict-Payload:``
pair, so the pre-demotion verifier finds no trailers and (non-strict) exits 0
WITHOUT auditing any ledger record -- it cannot reach a present-and-approved
audit verdict for a slice, and it cannot surface the gate's ``not-approved``
reason. The audit/no-drift assertions therefore fail with AssertionError against
the observable audit verdict (missing functionality: the ledger-record audit
the repurpose must add). For the deletion-safety scenario the
``scripts/cli/derive_review_trailer.py`` module still EXISTS on the pre-demotion
tree, so the "absent" assertion fails with AssertionError. Every dependency
(state-delta port, pytest-bdd, the ``des`` dispatcher subprocess) resolves
cleanly -- these are deliberate missing-functionality REDs, not test bugs.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_06 import (
    NOTHING_TO_AUDIT_EXIT,
    NOTHING_TO_AUDIT_REASON,
    FeatureId,
    GateRejectReason,
    ReviewRecordState,
    SliceId,
)


# tests/des/acceptance/oss_review_verdict_demotion/steps/composition_slice_06.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production des dispatcher module (single entry point).
DES_MODULE = "des.cli.__main__"

# The trailer-derivation CLI this slice HARD-DELETES (deletion-safety target).
DERIVE_CLI_PATH = REPO_ROOT / "scripts" / "cli" / "derive_review_trailer.py"
DERIVE_MODULE = "scripts.cli.derive_review_trailer"

# Signing-key env / file -- referenced ONLY to guarantee they stay ABSENT.
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"

_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"
_CARPACCIO_SLICE_MAX = 3


@dataclass
class CliResult:
    """Observable outcome of one des subcommand subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def payload(self) -> dict[str, object]:
        """The single-line JSON object the surface emits (empty dict if none)."""
        for line in (self.stdout + "\n" + self.stderr).splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                with contextlib.suppress(json.JSONDecodeError):
                    return json.loads(stripped)
        return {}


@dataclass
class DemotionAuditComposition:
    """Production-wired composition root for the S6 verify-repurpose slice.

    ``repo_dir`` is a real git work-tree under tmp_path. The feature-delta slice
    plan, the slice ``.feature`` AT file, the AT-completion ledger and a commit
    carrying a ``Slice-Id:`` trailer are provisioned via dedicated methods. NO
    reviewer signing key is ever written.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("oss-review-verdict-demotion"))
    entering_slice: SliceId = field(default=SliceId("slice-01"))
    _slice_at_count: int = field(default=2)
    _commit_sha: str | None = field(default=None)

    # --- paths ---------------------------------------------------------------

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_dir / "feature-delta.md"

    @property
    def _acceptance_dir(self) -> Path:
        return (
            self.repo_dir / "tests" / "scripts" / "cli" / self.feature_id / "acceptance"
        )

    @property
    def feature_file_path(self) -> Path:
        return self._acceptance_dir / "slice.feature"

    @property
    def _nwave_dir(self) -> Path:
        return self.repo_dir / ".nwave"

    @property
    def config_path(self) -> Path:
        return self._nwave_dir / "config.yaml"

    @property
    def ledger_path(self) -> Path:
        return self._nwave_dir / "telemetry" / "atdd-pure" / f"{self.feature_id}.jsonl"

    @property
    def _signing_key_path(self) -> Path:
        return self.repo_dir / _SIGNING_KEY_FILE

    # --- Given: repo + slice plan + scenarios + git commit -------------------

    def create_keyless_repo(self, feature_id: FeatureId) -> None:
        """Create a real git work-tree with a valid slice plan and NO key.

        Writes the feature-delta slice plan + the matching 2-scenario
        ``.feature`` file + the atdd_pure config, then ``git init`` + a commit
        carrying a ``Slice-Id: slice-01`` trailer. The chained-narrative baseline
        (Pillar 2): every S6 scenario starts from this keyless git repo.
        """
        self.feature_id = feature_id
        self._acceptance_dir.mkdir(parents=True, exist_ok=True)
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        self._nwave_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(
                {
                    "workflow": {"mode": "atdd_pure"},
                    "atdd_pure": {"carpaccio_slice_max": _CARPACCIO_SLICE_MAX},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        self._write_feature_delta()
        self._write_feature_file()
        self._commit_sha = self._init_git_repo_with_slice_id_trailer()

    def _write_feature_delta(self) -> None:
        self.feature_delta_path.write_text(
            "# Feature Delta: oss-review-verdict-demotion fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            "| slice-01 | Operator audits a reviewed slice | pending | "
            "@walking-skeleton | thinnest end-to-end vertical |\n",
            encoding="utf-8",
        )

    def _write_feature_file(self) -> None:
        blocks = [
            f"@feature-{self.feature_id} @slice-01\n"
            f"Scenario: fixture scenario {n}\n"
            "  Given a fixture precondition\n"
            "  When the fixture action occurs\n"
            "  Then the fixture outcome holds\n"
            for n in range(1, self._slice_at_count + 1)
        ]
        self.feature_file_path.write_text(
            "Feature: oss-review-verdict-demotion fixture\n\n" + "\n".join(blocks),
            encoding="utf-8",
        )

    def _init_git_repo_with_slice_id_trailer(self) -> str:
        """``git init`` + a commit whose body carries a ``Slice-Id:`` trailer.

        The repurposed verifier reads this trailer through the production git
        commit-read port to resolve which slice's ledger record to audit. NO
        ``Reviewed-by:``/``Verdict-Payload:`` HMAC trailer is present -- the
        post-demotion verifier audits the ledger, not a recomputed HMAC.
        """
        run = lambda *a: subprocess.run(  # noqa: E731
            list(a), cwd=self.repo_dir, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q")
        run("git", "config", "user.email", "at@example.com")
        run("git", "config", "user.name", "at")
        run("git", "add", "-A")
        commit_body = (
            "feat(demotion): ship the audited slice\n"
            "\n"
            f"Slice-Id: {self.entering_slice}\n"
        )
        run("git", "commit", "-q", "-m", commit_body)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _init_git_repo_without_slice_id_trailer(self) -> str:
        """Append a commit whose body carries NO ``Slice-Id:`` trailer.

        A-absent-trailer substrate (architect-final 2026-06-11): a legitimate
        non-slice commit -- docs / fix / chore / infra / merge -- appended on
        the Background-initialized work-tree. The repurposed verifier finds no
        ``Slice-Id:`` trailer to resolve -> it must report the distinct
        nothing-to-audit INDETERMINATE (exit 7, reason "no Slice-Id trailer"),
        never a silent exit-0 and never a BLOCK.
        """
        run = lambda *a: subprocess.run(  # noqa: E731
            list(a), cwd=self.repo_dir, check=True, capture_output=True, text=True
        )
        marker = self.repo_dir / "docs-note.md"
        marker.write_text("a documentation-only change\n", encoding="utf-8")
        run("git", "add", "-A")
        run("git", "commit", "-q", "-m", "docs: a non-slice commit with no trailer")
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def provision_commit_without_slice_id_trailer(self) -> None:
        """Point the audit at a commit carrying no ``Slice-Id:`` trailer."""
        self._commit_sha = self._init_git_repo_without_slice_id_trailer()

    # --- Given: review verdict record ----------------------------------------

    def provision_review_record(self, state: ReviewRecordState) -> None:
        """Provision the AT-completion ledger for the requested S6 state.

        No signing key is written for any state -- the post-demotion audit must
        not need one.
        """
        provisioner = _RECORD_PROVISIONERS[state]
        provisioner(self)

    def _current_at_ids(self) -> list[str]:
        return [f"AT-{n}" for n in range(1, self._slice_at_count + 1)]

    def _normalized_at_bodies_hash(self) -> str:
        """SHA-256 over the slice's normalized AT bodies (content seal, keyless)."""
        bodies = sorted(
            "given a fixture precondition\n"
            "when the fixture action occurs\n"
            "then the fixture outcome holds"
            for _ in self._current_at_ids()
        )
        return hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()

    def _approved_record(self) -> dict[str, object]:
        """A well-formed keyless APPROVED record (no ``hmac_sha256`` field)."""
        return {
            "event": "ATReviewVerdict",
            "schema_version": "1.0.0",
            "slice_id": str(self.entering_slice),
            "verdict": "APPROVED",
            "reviewer_agent_id": _REVIEWER_AGENT_ID,
            "at_ids": self._current_at_ids(),
            "at_content_hash": self._normalized_at_bodies_hash(),
            "timestamp": "2026-06-11T00:00:00Z",
            "findings_summary": [],
        }

    def _write_ledger_record(self, record: dict[str, object]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # --- When: run the repurposed verifier -----------------------------------

    def run_verifier(self) -> CliResult:
        """Invoke ``des verify-commit-trailers --commit <sha>`` as a subprocess.

        The signing-key env var is scrubbed for the duration so NO key is
        resolvable from env, and no key file is written -- the repurposed audit
        runs entirely keyless.
        """
        assert self._commit_sha is not None, (
            "the git commit carrying the Slice-Id trailer must be created (Given) "
            "before running the verifier (When)"
        )
        return self._run_des(["verify-commit-trailers", "--commit", self._commit_sha])

    def run_gate(self) -> CliResult:
        """Invoke ``des carpaccio-slice-gate`` as a subprocess (the no-drift co-drive)."""
        return self._run_des(
            [
                "carpaccio-slice-gate",
                "--feature-id",
                str(self.feature_id),
                "--entering-slice",
                str(self.entering_slice),
                "--repo-root",
                str(self.repo_dir),
            ]
        )

    def _run_des(self, subcommand_argv: list[str]) -> CliResult:
        """Drive ``des.cli.__main__ <subcommand> ...`` IN-PROCESS.

        The in-process analogue of the former ``python -m des.cli.__main__`` fork
        via the shared ``run_cli_in_process`` driver (default EDGE =
        ``des.cli.__main__.main``); cwd is chdir'd to the synthetic tmp tree and
        restored. Env-parity is applied IN-PROCESS around the call and restored in
        ``finally``: ``NWAVE_FRESHNESS=skip`` (belt-and-suspenders -- the dev
        checkout already auto-skips freshness) and the signing-key env var scrubbed
        so the repurposed surface runs keyless. PYTHONPATH is irrelevant in-process
        (``des`` is already importable).
        """
        prior_env = dict(os.environ)
        os.environ["NWAVE_FRESHNESS"] = "skip"
        os.environ["PIPENV_DONT_LOAD_ENV"] = "1"
        os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                subcommand_argv, cwd=str(self.repo_dir)
            )
        finally:
            os.environ.clear()
            os.environ.update(prior_env)
        return CliResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    # --- audit-verdict observable surface ------------------------------------

    def audit_clears(self, result: CliResult) -> bool:
        """True iff the audit reports the slice's review present-and-approved.

        The observable: exit 0 AND the audit surface reports the slice's review
        record as present-and-approved (not the legacy ``no trailers`` git path).
        The repurposed verifier emits a structured audit payload; a present-and-
        approved audit clears with exit 0 and an event naming the audited slice.
        """
        if result.exit_code != 0:
            return False
        payload = result.payload
        # The repurposed audit names the audited slice on a present-and-approved
        # clear; the legacy git-trailer verifier emitted no slice-bound payload.
        return payload.get("slice_id") == str(self.entering_slice) or (
            str(self.entering_slice) in result.stdout
        )

    def audit_refusal_reason(self, result: CliResult) -> str | None:
        """The rejection reason the audit surfaces, or None if it cleared.

        The repurposed verifier reuses the gate's ``_at_review_rejection`` shape:
        a refusal carries ``event == "ATReviewGateRejected"`` and a ``reason``
        from the gate's closed set. The audit window MUST surface the gate's own
        reason -- never a verifier-private one.
        """
        payload = result.payload
        if payload.get("event") == "ATReviewGateRejected":
            reason = payload.get("reason")
            return reason if isinstance(reason, str) else None
        return None

    def gate_refusal_reason(self, result: CliResult) -> str | None:
        """The rejection reason the carpaccio gate surfaces (same shape as audit)."""
        return self.audit_refusal_reason(result)

    def audit_is_nothing_to_audit(self, result: CliResult) -> bool:
        """True iff the audit reported the nothing-to-audit INDETERMINATE.

        A-absent-trailer (architect-final 2026-06-11): a commit with no
        ``Slice-Id:`` trailer exits 7 (the verifier's existing cannot-evaluate
        channel) -- never a silent exit-0 (the unarmed-gate silent-pass class)
        and never an exit-45 BLOCK (non-slice commits are legitimate).
        """
        return result.exit_code == NOTHING_TO_AUDIT_EXIT

    def audit_names_missing_trailer(self, result: CliResult) -> bool:
        """True iff the INDETERMINATE reason names the missing Slice-Id trailer.

        The stderr reason distinguishes the nothing-to-audit INDETERMINATE from
        the git-absent INDETERMINATE (same exit code, distinct reason string).
        """
        return NOTHING_TO_AUDIT_REASON in (result.stderr + result.stdout)

    def no_signing_key_provisioned(self) -> bool:
        """True iff no signing key file exists and the env var is unset."""
        return (
            not self._signing_key_path.exists()
            and os.environ.get(_SIGNING_KEY_ENV) is None
        )

    # --- deletion-safety: the derive CLI is gone -----------------------------

    def derive_cli_exists_on_disk(self) -> bool:
        """True iff ``scripts/cli/derive_review_trailer.py`` exists in the repo tree.

        Read against the REAL repo tree (REPO_ROOT), not the synthetic tmp repo
        -- the deletion target is the production source file, deleted in the S6
        commit. Post-demotion this MUST be False.
        """
        return DERIVE_CLI_PATH.is_file()

    def derive_module_importable(self) -> bool:
        """True iff the trailer-derivation module can still be imported.

        A second observable of the deletion: after the module is deleted, it is no
        longer importable. The in-process analogue of the former
        ``python -c "import {DERIVE_MODULE}"`` probe -- ``importlib.util.find_spec``
        resolves the module's spec against ``sys.path`` (the ``scripts`` package is
        importable from the repo root in this process) WITHOUT executing any body
        or polluting ``sys.modules``. Post-demotion the module is gone, so
        ``find_spec`` returns None (or a missing parent raises) -> not importable.
        """
        try:
            return importlib.util.find_spec(DERIVE_MODULE) is not None
        except ModuleNotFoundError:
            # a missing PARENT package on the dotted path == not importable
            return False

    # --- universe (Mandate 8 pure-read guard) --------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The repurposed verifier is a pure observer: it reads the commit body +
        the ledger record but MUST mutate no repository file and materialize no
        signing key. The universe is every file the audit reads plus the keyless
        invariant.
        """
        return {
            "feature_delta.bytes": _read_bytes_or_none(self.feature_delta_path),
            "feature_file.bytes": _read_bytes_or_none(self.feature_file_path),
            "ledger.exists": self.ledger_path.exists(),
            "ledger.bytes": _read_bytes_or_none(self.ledger_path),
            "config.bytes": _read_bytes_or_none(self.config_path),
            "signing_key.exists": self._signing_key_path.exists(),
        }


def _read_bytes_or_none(path: Path) -> object:
    return path.read_bytes() if path.exists() else None


# --- review-record provisioners ---------------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup + a
# single composition call (Mandate-12 criterion 3: no control flow in steps).


def _provision_approved_no_signature(comp: DemotionAuditComposition) -> None:
    comp._write_ledger_record(comp._approved_record())


def _provision_not_approved(comp: DemotionAuditComposition) -> None:
    record = comp._approved_record()
    record["verdict"] = "NEEDS_REVISION"
    comp._write_ledger_record(record)


_RECORD_PROVISIONERS: dict[
    ReviewRecordState, callable[[DemotionAuditComposition], None]
] = {
    ReviewRecordState.APPROVED_NO_SIGNATURE: _provision_approved_no_signature,
    ReviewRecordState.NOT_APPROVED: _provision_not_approved,
}


# Re-export for the step module's typed reason lookup.
__all__ = [
    "CliResult",
    "DemotionAuditComposition",
    "GateRejectReason",
]
