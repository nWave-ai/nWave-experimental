"""Composition root for the P4 tracked-before fallback acceptance suite.

Mandate-12: the test-side business logic -- "build a real temp-git repo whose
slice AT is in AT-presence state X" and "invoke the reverify CLI port" -- lives
here as services, NOT inline in step bodies. Step methods delegate to
``ReverifyP4Composition`` and never construct git history themselves.

Pillar 3 (app as in production): the SUT is the real ``reverify_slice_commit``
CLI invoked through its production ``main(argv)`` entry point. Only the
*fixture* git repository is constructed here -- the SUT is not rebuilt.

Layer-3 (subprocess / real-I/O acceptance): real git, real filesystem under a
pytest ``tmp_path``. Per Mandate 9/11 this suite is example-based -- no PBT
machinery -- and the input domain (4 enumerable AT-presence states) is bounded,
so slice-02 parametrize-collapses rather than generating.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.reverify_slice_commit import main

from .domain_types import AtPresenceState, P4Verdict


_FEATURE_ID = "fix-reverify-p4-tracked-before-fallback"
_SLICE_ID = "slice-01"

# The temp repo's own pytest config -- so the contract gate (E2) collects.
_TEMP_PYTEST_INI = """\
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    acceptance: Acceptance tests
"""

# A .feature carrying the @slice-01 tag P4 walks for. Also carries the
# @feature-{id} file-level tag -- E1 (`check_slice_at_completeness`) is
# feature-scoped since fix-reverify-e1-via-scoped-wrapper (2026-06-20,
# W5 cross-feature-collision close): `feature_tag_files` only matches a
# `.feature` file that self-identifies with `@feature-{feature_id}`
# preceding its `Feature:` header, so a fixture missing that tag is
# invisible to E1 regardless of its `@slice-NN` tag -- this fixture predates
# that scoping change and needs the tag to stay a genuine P4-ACCEPT case
# instead of an E1-vacuous refusal.
_SLICE_FEATURE_TAGGED = f"""\
@feature-{_FEATURE_ID} @slice-01
Feature: orphaned slice recovery

  Scenario: the slice ships its acceptance criterion
    Given a committed slice
    When the reverify gate runs
    Then the slice is certified green
"""

# The SAME .feature with the @slice-01 tag dropped (disownership) -- the
# @feature-{id} tag is KEPT: this variant tests slice-tag disownership, not
# feature-scoping, so it must still resolve as this feature's file up until
# the slice tag match fails.
_SLICE_FEATURE_TAG_DROPPED = f"""\
@feature-{_FEATURE_ID}
Feature: orphaned slice recovery

  Scenario: the slice ships its acceptance criterion
    Given a committed slice
    When the reverify gate runs
    Then the slice is certified green
"""

# A genuinely-passing contract-marked test -- E2 runs it green.
_CONTRACT_TEST_GREEN = """\
import pytest


@pytest.mark.acceptance
def test_slice_contract_holds():
    assert 1 + 1 == 2
"""

_FEATURE_REL = "tests/acceptance/slice_01.feature"


@dataclass
class ReverifyOutcome:
    """The observable outcome of one reverify CLI invocation at its port."""

    exit_code: int
    event: str
    error: str = ""

    @property
    def verdict(self) -> P4Verdict:
        """Map the port-observable outcome onto P4's accept/refuse verdict.

        P4 ACCEPT -> reverify proceeds; the terminal event is `SliceReverified`
        (or a `SliceReverifyBlocked` from a *later* gate, never a P4 refusal).
        P4 REFUSE -> the terminal event is `SliceReverifyRefused` with exit 1.
        """
        if self.event == "SliceReverifyRefused":
            return P4Verdict.REFUSE
        return P4Verdict.ACCEPT


@dataclass
class ReverifyP4Composition:
    """Service object: builds the fixture repo and drives the reverify port."""

    tmp_path: Path
    _repo: Path = field(init=False)
    _slice_commit: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self._repo = self.tmp_path / "repo"
        self._repo.mkdir()
        self._init_repo()

    # -- git fixture primitives -------------------------------------------

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

    # -- the SSOT service: build a repo in a given AT-presence state ------

    def given_slice_in_presence_state(self, state: AtPresenceState) -> None:
        """Build a real buried-slice git history matching ``state``.

        Every variant ends with the slice commit STRICTLY buried under HEAD
        (a later commit), so P5 (orphan-state) always passes and P4 is the
        precondition genuinely under test.
        """
        # Base commit -- pytest config so E2's contract suite collects.
        self._write("pytest.ini", _TEMP_PYTEST_INI)
        self._commit("chore: base\n")

        if state is AtPresenceState.IN_COMMIT:
            # The @slice-01 .feature is authored *by* the slice commit.
            self._write(_FEATURE_REL, _SLICE_FEATURE_TAGGED)
            self._slice_commit = self._commit("feat: slice-01\n\nSlice-Id: slice-01\n")

        elif state is AtPresenceState.TRACKED_BEFORE_UNMODIFIED:
            # The @slice-01 .feature is authored in an EARLIER (scaffold)
            # commit; the slice commit lands production code only and never
            # touches the .feature -- the canonical carpaccio-split orphan.
            self._write(_FEATURE_REL, _SLICE_FEATURE_TAGGED)
            self._commit("test: scaffold slice-01 AT\n\nSlice-Id: slice-01\n")
            self._write("src/feature.py", "VALUE = 1\n")
            self._slice_commit = self._commit(
                "feat: slice-01 production code\n\nSlice-Id: slice-01\n"
            )

        elif state is AtPresenceState.NEVER_AUTHORED:
            # No @slice-01 .feature anywhere -- not in the commit, not before.
            self._write("src/feature.py", "VALUE = 1\n")
            self._slice_commit = self._commit(
                "feat: slice-01 production code\n\nSlice-Id: slice-01\n"
            )

        elif state is AtPresenceState.TAG_DROPPED_BY_COMMIT:
            # The .feature is authored tagged in an earlier commit; the slice
            # commit MODIFIES it to drop the @slice-01 tag (disownership).
            self._write(_FEATURE_REL, _SLICE_FEATURE_TAGGED)
            self._commit("test: scaffold slice-01 AT\n\nSlice-Id: slice-01\n")
            self._write(_FEATURE_REL, _SLICE_FEATURE_TAG_DROPPED)
            self._slice_commit = self._commit(
                "feat: slice-01, drop @slice-01 tag\n\nSlice-Id: slice-01\n"
            )

        else:  # pragma: no cover -- exhaustive over the enum.
            raise ValueError(f"unhandled AT-presence state: {state!r}")

        # A later commit buries the slice commit -- P5 orphan-state passes.
        self._write("src/later.py", "X = 1\n")
        self._write("tests/test_contract.py", _CONTRACT_TEST_GREEN)
        self._commit("test: grow the suite after the slice commit\n")

    # -- the SSOT service: drive the reverify CLI port --------------------

    def reverify(self, capsys) -> ReverifyOutcome:
        """Invoke the production reverify CLI port; capture its outcome.

        Drives ``des.cli.reverify_slice_commit.main`` -- the real argv entry
        point -- against the fixture repo. Returns the port-observable
        outcome: exit code + terminal JSON event.
        """
        argv = [
            "--repo",
            str(self._repo),
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--commit",
            self._slice_commit,
        ]
        exit_code = main(argv)
        payload = json.loads(capsys.readouterr().out.strip())
        return ReverifyOutcome(
            exit_code=exit_code,
            event=str(payload.get("event", "")),
            error=str(payload.get("error", "")),
        )

    def ledger_has_verified_slice(self) -> bool:
        """True iff the slice carries a `SliceCommitVerified` ledger record."""
        return (
            _SLICE_ID in AtCompletionLedger(_FEATURE_ID, self._repo).verified_slices()
        )
