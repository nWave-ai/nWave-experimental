"""Composition root for the reverify-E1-via-scoped-wrapper acceptance suite.

Mandate-12: the test-side business logic -- "build a real temp-git repo whose
slice ATs live across N features sharing @slice-NN" and "invoke the wrapper
CLI port" -- lives here as a service object. Step methods delegate; no inline
git fixture construction, no inline subprocess wiring.

Pillar 3 (app as in production): the SUT is the real production CLI invoked
through its argv entry point. Slice-01 drives ``check_slice_at_completeness``
as a subprocess via ``python -m`` (the production install path -- the F3
bootstrap-blind residuality probe). Slice-02 drives the real
``reverify_slice_commit.main(argv)`` in-process (matching the existing P4
acceptance pattern) AND verifies the swapped E1 invocation reaches the
wrapper.

Layer 3 (subprocess / real-I/O acceptance): real git, real filesystem under
``tmp_path``. Per Mandate 9/11 this suite is example-based -- no PBT on the
real-I/O layer. The SSOT scoping property (slice-01 AT-(a)) IS PBT, but at
layer 2 (in-process call to the pure function over an in-memory parametrized
list of feature ids).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.reverify_slice_commit import main as reverify_main

from .domain_types import (
    FeatureUnderSlice,
    ReverifyE1Outcome,
    WrapperOutcome,
)


# Per-test contract: a feature_id used by the single-feature row and the
# wrapper's --feature-id arg. Cross-feature-collision rows enumerate multiple.
_FEATURE_ID_PRIMARY = "fix-reverify-e1-via-scoped-wrapper"
_FEATURE_ID_COLLIDER = "fix-other-feature-sharing-slice-01"
_SLICE_ID = "slice-01"

_TEMP_PYTEST_INI = """\
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    acceptance: Acceptance tests
"""

_CONTRACT_TEST_GREEN = """\
import pytest


@pytest.mark.acceptance
def test_slice_contract_holds():
    assert 1 + 1 == 2
"""


def _feature_file(feature_id: str, slice_id: str = _SLICE_ID) -> str:
    """The `.feature` body for one feature carrying ``@slice-NN`` + ``@feature-{id}``.

    The two tags are the SSOT for E1's feature-scoping (W5): `_feature_tag_files`
    keys on ``@feature-{id}``; `_SLICE_TAG_RE` keys on ``@slice-NN``. Both are
    required for a file to participate in feature-scoped E1.
    """
    return f"""\
@feature-{feature_id} @{slice_id}
Feature: {feature_id} -- {slice_id}

  Scenario: this slice ships its acceptance criterion
    Given a committed slice
    When the gate runs
    Then the slice is certified green
"""


@dataclass
class ReverifyE1WrapperComposition:
    """Service object: builds the fixture repo and drives both CLI ports.

    One composition root per test (function-scoped fixture). Constructs a
    real git repo under ``tmp_path/repo``, optionally seeds N features
    sharing the slice tag, and exposes typed driver methods for the wrapper
    CLI (subprocess) + the reverify CLI (in-process).
    """

    tmp_path: Path
    _repo: Path = field(init=False)
    _slice_commit: str = field(init=False, default="")
    _features: list[FeatureUnderSlice] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._repo = self.tmp_path / "repo"
        self._repo.mkdir()
        self._init_repo()

    # -- git fixture primitives --------------------------------------------

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self._repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def _init_repo(self) -> None:
        self._git("init", "-q")
        self._git("config", "user.email", "t@t")
        self._git("config", "user.name", "t")

    def _commit(self, message: str) -> str:
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD").strip()

    def _write(self, rel: str, content: str) -> None:
        target = self._repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    # -- SSOT services -----------------------------------------------------

    def given_features_sharing_slice(self, n_features: int) -> list[FeatureUnderSlice]:
        """Seed the repo with ``n_features`` distinct features sharing @slice-01.

        The PRIMARY feature is always first; colliders follow as
        ``fix-other-feature-sharing-slice-01-{i}``. Each feature lives under a
        dedicated subdirectory carrying both ``@feature-{id}`` and
        ``@slice-01`` tags. The slice commit carries every feature's
        `.feature` so single-feature E1 against the primary clears, but
        global-scope E1 would walk all ``n_features`` and could mis-attribute
        a delete in feature[k] to the primary.

        Returns the list in seeded order (primary at index 0).
        """
        # Base commit: pytest config so E2's contract suite collects later.
        self._write("pytest.ini", _TEMP_PYTEST_INI)
        self._commit("chore: base\n")

        self._features = []
        if n_features < 1:
            raise ValueError("n_features must be >= 1")

        primary = FeatureUnderSlice(
            feature_id=_FEATURE_ID_PRIMARY,
            feature_file_rel=f"tests/{_FEATURE_ID_PRIMARY}/acceptance/{_SLICE_ID}.feature",
        )
        self._write(primary.feature_file_rel, _feature_file(primary.feature_id))
        self._features.append(primary)

        for i in range(1, n_features):
            collider_id = f"{_FEATURE_ID_COLLIDER}-{i}"
            collider = FeatureUnderSlice(
                feature_id=collider_id,
                feature_file_rel=(
                    f"tests/{collider_id}/acceptance/{_SLICE_ID}.feature"
                ),
            )
            self._write(collider.feature_file_rel, _feature_file(collider.feature_id))
            self._features.append(collider)

        # A genuinely-passing contract test so reverify's E2 stays green.
        self._write("tests/test_contract.py", _CONTRACT_TEST_GREEN)

        # The slice commit lands every feature's .feature + the contract test.
        self._slice_commit = self._commit(
            f"feat: {_SLICE_ID}\n\nSlice-Id: {_SLICE_ID}\n"
        )

        # A later commit buries the slice commit -- existing reverify P5
        # orphan-state precondition passes.
        self._write("src/later.py", "X = 1\n")
        self._commit("test: grow the suite after the slice commit\n")
        return list(self._features)

    # -- driving-port: the new wrapper CLI (subprocess, F3 probe) ---------

    def invoke_wrapper(
        self,
        feature_id: str | None = _FEATURE_ID_PRIMARY,
        slice_id: str = _SLICE_ID,
        omit_feature_id: bool = False,
        repo_override: Path | None = None,
        commit_override: str | None = None,
    ) -> WrapperOutcome:
        """Subprocess-invoke ``des check-slice-at-completeness``.

        ``omit_feature_id=True`` reproduces the C5/C6 regression vector --
        the wrapper MUST refuse argv without ``--feature-id`` (exit 2). All
        other parameters thread the feature-scoping decision-table dimensions.
        Post-slice-03 single-entry-point dispatcher form.
        """
        repo = repo_override if repo_override is not None else self._repo
        commit = commit_override if commit_override is not None else self._slice_commit
        argv = [
            "des",
            "check-slice-at-completeness",
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--slice-id",
            slice_id,
        ]
        if not omit_feature_id and feature_id is not None:
            argv.extend(["--feature-id", feature_id])
        completed = subprocess.run(argv, capture_output=True, text=True)
        payload: dict[str, object] = {}
        stdout = completed.stdout.strip()
        if stdout:
            try:
                payload = json.loads(stdout.splitlines()[-1])
            except json.JSONDecodeError:
                payload = {}
        return WrapperOutcome(
            exit_code=completed.returncode,
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            payload=payload,
        )

    # -- driving-port: the reverify CLI (in-process, layer-3) -------------

    def invoke_reverify(
        self,
        capsys,
        feature_id: str = _FEATURE_ID_PRIMARY,
        slice_id: str = _SLICE_ID,
    ) -> ReverifyE1Outcome:
        """Drive ``reverify_slice_commit.main`` against the fixture repo.

        Returns the typed E1 outcome (SUCCESS or E1_BLOCKED). Other reverify
        outcomes (P-precondition refusal, E2 failure) are out of scope for
        this feature -- they have dedicated acceptance suites.
        """
        argv = [
            "--repo",
            str(self._repo),
            "--feature-id",
            feature_id,
            "--slice-id",
            slice_id,
            "--commit",
            self._slice_commit,
        ]
        exit_code = reverify_main(argv)
        captured = capsys.readouterr().out.strip()
        payload: dict[str, object] = {}
        if captured:
            try:
                payload = json.loads(captured.splitlines()[-1])
            except json.JSONDecodeError:
                payload = {}
        event = str(payload.get("event", ""))
        failing_gate = str(payload.get("failing_gate", ""))
        if exit_code == 0 and event == "SliceReverified":
            return ReverifyE1Outcome.SUCCESS
        if (
            exit_code == 1
            and event == "SliceReverifyBlocked"
            and "verify_slice_commit_completeness" in failing_gate
        ) or "check_slice_at_completeness" in failing_gate:
            return ReverifyE1Outcome.E1_BLOCKED
        # Any other shape is a test-design error (e.g. P-precondition fired).
        raise AssertionError(
            f"unexpected reverify outcome: exit={exit_code} event={event!r} "
            f"failing_gate={failing_gate!r} payload={payload!r}"
        )

    @property
    def repo(self) -> Path:
        return self._repo

    @property
    def slice_commit(self) -> str:
        return self._slice_commit

    @property
    def features(self) -> list[FeatureUnderSlice]:
        return list(self._features)
