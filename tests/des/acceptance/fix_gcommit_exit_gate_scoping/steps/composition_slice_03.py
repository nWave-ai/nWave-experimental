"""Composition root for fix-gcommit-exit-gate-scoping slice-03 (Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): every service method drives the REAL
`handle_subagent_stop` hook end-to-end over its JSON stdin protocol -- the same
SubagentStop driving port the U2 G_COMMIT exit gate runs behind in production.
The intercept (`subagent_stop_handler._handle_g_commit_exit_gate`) runs E1
(`verify_slice_commit_completeness`) and E2 (`run_contract_gate
--verify-gate-scope`) as its own subprocesses and emits a `{"decision":"block"}`
body + a U3 ledger record. The AT NEVER imports `verify_slice_commit_completeness`
or `feature_files_for_slice` -- it observes only the hook's decision body, its
exit code, the E1 exit code the block reason carries, and the ledger records the
intercept wrote.

slice-03 (E1 cross-feature scoping): at HEAD the hook invokes E1 with NO feature
scope (`subagent_stop_handler.py:618-630`), so E1 falls back to a WHOLE-TREE
`rglob("*.feature")`. A co-resident foreign feature B carrying the SAME
`@slice-NN` value as the committing feature A is then demanded inside A's commit
-> E1 reports A's commit INCOMPLETE naming B's `.feature` (`e1=1`, the
cross-feature collision RED witness). The fix wires `resolved.project_id` to E1
via the Seam-A E1-ONLY scoping path, so E1's `.feature` candidate scan is scoped
to feature A's `@feature-{id}`-tagged files only -- B's tag no longer cross-binds.

These ATs materialise a real two-feature git repo, build feature A's slice
commit with a matching committed-scope `Gate-Scope:` trailer (so E2 verifies and
the intercept can reach the verified path for the E2-runs-once / single-ledger
discriminator), then drive the real hook subprocess under two co-resident states.

git enters ONLY as a real subprocess inside the fixture builder (a driven
dependency of the test harness), never as production code the AT imports.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from des.cli.run_contract_gate import main as _run_contract_gate_main
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process

from .domain_types_slice_03 import (
    CoResidentState,
    E1Outcome,
    FeatureId,
    GcommitGateOutcome,
    OwnSliceState,
)


_SRC_ROOT = Path("src").resolve()

# The slice the committing feature A delivers; the co-resident foreign feature B
# carries the SAME slice tag value -- that shared tag is the collision the
# unscoped whole-tree scan provokes.
_SHARED_SLICE_ID = "slice-01"

# The block reason embeds the E1 exit code verbatim: `... (e1=N, e2=M)`.
_E1_CODE_RE = re.compile(r"e1=(\d+)")


@dataclass
class InterceptRun:
    """The observable outcome of one real U2 G_COMMIT SubagentStop intercept."""

    exit_code: int
    decision_event: str | None
    block_reason: str | None
    stdout: str
    stderr: str
    verified_record_count: int

    @property
    def gate_outcome(self) -> GcommitGateOutcome:
        """ALLOWED when no block body surfaced; BLOCKED on a block decision."""
        if self.exit_code != 0:
            return GcommitGateOutcome.UNEXPECTED
        if self.decision_event is None and self.block_reason is None:
            return GcommitGateOutcome.ALLOWED
        return GcommitGateOutcome.BLOCKED

    @property
    def e1_outcome(self) -> E1Outcome:
        """Lift the E1 half's verdict out of the decision body.

        A verified commit (ALLOWED) implies E1 cleared (`e1=0`). A block whose
        reason carries `e1=N` reports COMPLETE when N==0 (the block was E2's
        fault) and INCOMPLETE when N!=0 (E1 found a missing `.feature`). A block
        with no parseable `e1=` token is INDETERMINATE so an assertion never
        passes for the wrong reason.
        """
        if self.gate_outcome is GcommitGateOutcome.ALLOWED:
            return E1Outcome.COMPLETE
        if self.block_reason is None:
            return E1Outcome.INDETERMINATE
        match = _E1_CODE_RE.search(self.block_reason)
        if match is None:
            return E1Outcome.INDETERMINATE
        return E1Outcome.COMPLETE if match.group(1) == "0" else E1Outcome.INCOMPLETE


@dataclass
class GcommitE1ScopingComposition:
    """Production composition root driving the real SubagentStop G_COMMIT hook."""

    committing_feature: FeatureId = field(
        default_factory=lambda: FeatureId("feat-alpha")
    )
    coresident_feature: FeatureId = field(
        default_factory=lambda: FeatureId("feat-beta")
    )
    repo: Path | None = field(default=None)
    last_run: InterceptRun | None = field(default=None)

    # --- fixture builders (real git repo; git is a test-harness dependency) ---

    def make_two_feature_commit(self, root: Path, own_slice: OwnSliceState) -> Path:
        """Materialise a two-feature repo + the committing feature's slice commit.

        Feature A (the committing feature) authors a `@slice-01` `.feature`
        under `tests/` tagged `@feature-{A}`. A seed commit establishes a base
        and a pytest-collectable committed test so the committed-scope digest
        (E2's trailer source) is stable. Feature A's slice commit then carries
        its `Slice-Id: slice-01` trailer and a MATCHING committed-scope
        `Gate-Scope:` trailer so E2 verifies -- letting the intercept reach the
        verified path for the E2-runs-once / single-ledger discriminator.

        * OwnSliceState.COMMITTED -- A's own `tests/.../a.feature` is IN the
          slice commit (the complete case; AT-A drives this).
        * OwnSliceState.AUTHORED_BUT_NOT_COMMITTED -- A's own `.feature` is on
          disk but kept OUT of every commit (the genuine-incompleteness case;
          AT-B drives this, and E1 must STILL report incomplete after scoping).
        """
        self.repo = root
        self._git_init(root)
        self._write_seed_contract(root)
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "chore: seed contract suite")

        own_feature_file = self._feature_file_path(root, self.committing_feature)
        self._write_feature_file(
            own_feature_file, self.committing_feature, _SHARED_SLICE_ID
        )

        if own_slice is OwnSliceState.COMMITTED:
            self._git(root, "add", str(own_feature_file.relative_to(root)))
        else:
            # AUTHORED_BUT_NOT_COMMITTED: stage an unrelated code file so the
            # slice commit is non-empty, but keep the feature's own `.feature`
            # OUT of the commit -- the genuine RCA Branch-A incompleteness.
            (root / "code.py").write_text("x = 1\n", encoding="utf-8")
            self._git(root, "add", "code.py")

        self._git(
            root,
            "commit",
            "-qm",
            f"feat: {self.committing_feature} slice work\n\n"
            f"Slice-Id: {_SHARED_SLICE_ID}",
        )
        self._amend_matching_gate_scope_trailer(root)
        return root

    def place_coresident_feature(self, root: Path, state: CoResidentState) -> Path:
        """Bring the co-resident foreign feature into the requested on-tree state.

        PRESENT_SHARING_SLICE_TAG drops feature B's `@slice-01` `.feature`
        (tagged `@feature-{B}`) on-tree as UNTRACKED co-resident WIP -- the exact
        perturbation that, under the unscoped whole-tree E1 scan, is demanded
        inside feature A's commit -> cross-feature collision. ABSENT leaves only
        feature A's files on-tree.
        """
        beta_file = self._feature_file_path(root, self.coresident_feature)
        if state is CoResidentState.PRESENT_SHARING_SLICE_TAG:
            self._write_feature_file(
                beta_file, self.coresident_feature, _SHARED_SLICE_ID
            )
        elif beta_file.exists():
            beta_file.unlink()
        return root

    # --- driving port: the real `handle_subagent_stop` G_COMMIT intercept ---

    def run_g_commit_intercept(self, root: Path) -> InterceptRun:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol.

        Mandate-13 Layer-3 composition/wiring: spawn the real SubagentStop hook
        as a subprocess with a `G_COMMIT` crafter transcript whose
        `DES-PROJECT-ID` marker names the committing feature. The intercept runs
        E1 + E2 + ledger emission internally; the AT observes only the decision
        body, exit code, and the ledger records written. This is the exact path
        the U2 exit gate runs behind in production.
        """
        transcript = self._write_g_commit_transcript(root)
        hook_input = json.dumps(
            {
                "session_id": "slice-03-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "crafter-1",
                "agent_type": "software-crafter",
                "agent_transcript_path": str(transcript),
                "stop_hook_active": False,
                "cwd": str(root),
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )
        # In-process analogue of the former `python -c "from <handler> import
        # handle_subagent_stop; sys.exit(handle_subagent_stop())"` fork with the
        # JSON event on stdin: drive the REAL no-argv handler directly, dropping
        # the per-scenario interpreter fork. The handler reads its event from
        # stdin and resolves the repo from the event `cwd`, so process cwd stays
        # the repo root. The two load-bearing env keys (PYTHONPATH for the child
        # E2 gate subprocess, NWAVE_FRESHNESS=skip to isolate the install-freshness
        # probe) are applied to os.environ around the call and restored in finally
        # (shared-process safe); the inner gate subprocess inherits them.
        target_env = self._subprocess_env()
        managed_keys = ("PYTHONPATH", "NWAVE_FRESHNESS")
        priors = {key: os.environ.get(key) for key in managed_keys}
        try:
            for key in managed_keys:
                os.environ[key] = target_env[key]
            exit_code, stdout, stderr = run_hook_in_process(
                handle_subagent_stop,
                stdin_text=hook_input,
                cwd=Path.cwd(),
            )
        finally:
            for key, value in priors.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        completed = subprocess.CompletedProcess(
            args=[], returncode=exit_code, stdout=stdout, stderr=stderr
        )
        decision_event, block_reason = self._read_decision(completed.stdout)
        self.last_run = InterceptRun(
            exit_code=completed.returncode,
            decision_event=decision_event,
            block_reason=block_reason,
            stdout=completed.stdout,
            stderr=completed.stderr,
            verified_record_count=self._verified_record_count(root),
        )
        return self.last_run

    # --- observation helpers --------------------------------------------------

    def _read_decision(self, stdout: str) -> tuple[str | None, str | None]:
        """Extract the (event, reason) of the intercept's block body, if any."""
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                event = payload.get("event")
                reason = payload.get("reason")
                return (
                    str(event) if event is not None else None,
                    str(reason) if reason is not None else None,
                )
        return None, None

    def _verified_record_count(self, root: Path) -> int:
        """Count `SliceCommitVerified` ledger records for the committing feature.

        Seam A (E1-only scoping) leaves the hook the SOLE author of the
        verified record -> exactly one. The rejected Seam B (passing
        `--feature-id`, flipping E1 into verify-then-record) would make the E1
        CLI ALSO append a `SliceCommitVerified` -> two records: the discriminator
        AT-C pins. A read failure (corrupt / absent) returns -1 so an assertion
        never passes for the wrong reason.
        """
        ledger = AtCompletionLedger(self.committing_feature, root)
        try:
            records = ledger.read_records()
        except Exception:
            return -1
        return sum(
            1
            for record in records
            if record.get("event") == "SliceCommitVerified"
            and record.get("slice_id") == _SHARED_SLICE_ID
        )

    # --- committed-scope digest (slice-01 mode) used to build the trailer -----

    def _amend_matching_gate_scope_trailer(self, root: Path) -> None:
        """Amend HEAD so it carries a MATCHING committed-scope `Gate-Scope:`.

        The trailer the E2 verify check must match is the committed-scope digest
        (slice-02 wired E2 to committed-scope). Driven through the shipped
        `--committed-scope-digest` CLI (subprocess), never an import.
        """
        digest = self._committed_scope_digest(root)
        original = self._git(root, "log", "-1", "--format=%B", "HEAD").strip()
        self._git(
            root,
            "commit",
            "-q",
            "--amend",
            "-m",
            f"{original}\nGate-Scope: {digest}",
        )

    def _committed_scope_digest(self, root: Path) -> str:
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--repo",
                str(root),
                "--committed-scope-digest",
            ],
            cwd=root,
            main=_run_contract_gate_main,
        )
        for line in (ln.strip() for ln in stdout.splitlines()):
            if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
                return line
        raise AssertionError(
            "could not derive a committed-scope digest to build the trailer "
            f"(exit {exit_code}); stdout={stdout!r} "
            f"stderr={stderr!r}"
        )

    # --- transcript ----------------------------------------------------------

    def _write_g_commit_transcript(self, root: Path) -> Path:
        """Write a transcript whose LAST atdd_pure block is a G_COMMIT return."""
        marker = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : G_COMMIT -->\n"
            f"<!-- DES-SLICE : {_SHARED_SLICE_ID} -->\n"
            f"<!-- DES-PROJECT-ID : {self.committing_feature} -->\n"
            f"<!-- DES-PROJECT-ROOT : {root} -->\n"
        )
        transcript = root / "agent.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": marker},
                    "uuid": "live-block",
                    "timestamp": "2026-05-20T10:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return transcript

    # --- git + filesystem (test-harness dependency, NOT production import) ----

    def _feature_file_path(self, root: Path, feature: FeatureId) -> Path:
        return root / "tests" / feature / "acceptance.feature"

    def _write_feature_file(
        self, path: Path, feature: FeatureId, slice_id: str
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"@feature-{feature}\n"
            f"@{slice_id}\n"
            f"Feature: {feature} {slice_id}\n"
            "  Scenario: a scenario\n"
            "    Given a precondition\n"
            "    When an action occurs\n"
            "    Then an outcome is observed\n",
            encoding="utf-8",
        )

    def _write_seed_contract(self, root: Path) -> None:
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n',
            encoding="utf-8",
        )
        (root / "test_seed_contract.py").write_text(
            "import pytest\n\n@pytest.mark.unit\ndef test_seed():\n    assert True\n",
            encoding="utf-8",
        )

    def _git_init(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "atdd@nwave.ai")
        self._git(root, "config", "user.name", "atdd")

    @staticmethod
    def _git(repo: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    @staticmethod
    def _subprocess_env() -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(_SRC_ROOT)
        # The two-feature tmp repo is not an nWave install; skip the freshness
        # probe (its DEGRADED refusal is unrelated to the E1-scoping behaviour
        # under test) so the gate runs to its real E1/E2 verdict.
        env["NWAVE_FRESHNESS"] = "skip"
        return env
