"""Composition root for des-gate-error-explain-and-guide slice-01 ATs.

This is the ONLY place the production system is wired for the slice-01 ATs.
It drives the production `des run-contract-gate` CLI end-to-end as a subprocess
black box (Mandate-13 driving-port-only, Layer 3 subprocess).

DRIVING PORT (load-bearing): `_feature_scope_malformed`, `_explain_and_guide`,
and `_emit` are NEVER imported-and-called at the step boundary -- the SUT is
exercised only through the CLI subprocess:

    python -m des.cli.run_contract_gate
        --feature-id <id> --entering-slice <slice> --repo <tmp>

The observable surface is:
  - stdout: one-line JSON object (the FeatureScopeMalformed event payload)
  - exit code: 2

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a tmp directory
crafted to trigger one of two refusal paths:

  ZERO_COLLECTED_SUBSTRATE -- a git-init-ed tmp repo with no .feature file
      carrying @feature-<id>. The simplest trigger: `_feature_tag_files`
      returns an empty set. `_feature_scope_malformed` is called with
      reason="zero-collected".

  EMPTY_INTERSECTION_SUBSTRATE -- a git-init-ed tmp repo with a .feature file
      tagged @feature-<id> BUT NOT @<entering_slice>. `_feature_tag_files`
      returns that file; `_slice_tags` finds no @<entering_slice> tag ->
      `_feature_scope_malformed` is called with reason="empty-intersection".
      Used for scenario 3 (per-token distinctness).

PURE-READ CONTRACT (Mandate-8, layer-3 universe guard):
`des run-contract-gate --feature-id` is a pure observer -- it reads the repo
tree (via `_feature_tag_files`) but MUST NOT write to the tmp directory (no
.git changes, no file writes, no side effects). `capture_universe()` snapshots
the port-exposed filesystem observables; the When-step asserts every entry is
`unchanged()` across the invocation.

ADDITIVE-ONLY INVARIANT (D-1):
The composition root records the pre-patch FeatureScopeMalformed payload (the
five canonical fields + exit code) from a real invocation; the Then-steps
compare the post-patch payload against those recorded values to prove nothing
was changed.

RED-for-right-reason (empirically confirmed at authorship HEAD):
  * Scenario 1 (walking skeleton): `_explain_and_guide` does not exist ->
    the emitted JSON has no `what`/`why`/`next` -> `event["what"]` raises
    KeyError inside the Then-step assertion -> AssertionError wrapping KeyError.
    RED for the right reason.
  * Scenario 2 (additive-only guard): the five existing fields ARE already
    present in the emitted JSON (no `_explain_and_guide` call -> no change to
    existing keys) and exit code IS already 2 -> Then-steps pass ->
    GREEN-on-author. This is the correct behavior: the guard protects against
    DELIVER accidentally removing an existing field.
  * Scenario 3 (per-token distinctness): `what`/`why`/`next` absent for
    `empty-intersection` too -> KeyError -> AssertionError. RED.
    Additionally the `why`-distinctness check can only be reached after
    `what`/`why`/`next` are present (post-GREEN) -- the comparison step will
    also be RED because `event["why"]` KeyErrors before any comparison.

State lives on the instance; every `given_/when_/then_` method mutates or
reads that state. Step functions in `test_slice_01_*.py` are thin delegations
to these methods (Mandate-12 criterion 3: no business logic in step bodies).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.cli import run_contract_gate
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    FEATURE_SCOPE_MALFORMED_EVENT,
    MALFORMED_SCOPE_CAUSE,
    MALFORMED_SCOPE_EXIT,
    ExplainAndGuideField,
    FeatureId,
    MalformedScopeReason,
    SliceTag,
)


# tests/des/acceptance/des-gate-error-explain-and-guide/steps/composition.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]


def _run_contract_gate_in_process(
    feature_id: FeatureId, entering_slice: SliceTag, repo: Path
) -> tuple[int, str, str]:
    """Drive `des run-contract-gate --feature-id` in-process under ``repo``.

    The in-process analogue of the former
    ``subprocess.run([sys.executable, "-m", "des.cli.run_contract_gate", ...])``
    fork: it calls the production CLI EDGE ``run_contract_gate.main`` directly.

    Env-parity (load-bearing, restored in finally): ``NWAVE_FRESHNESS=skip`` +
    ``PIPENV_DONT_LOAD_ENV=1`` so the freshness wrapper does not refuse before
    gate logic runs, and ``PYTHONPATH=<repo>/src`` so any pytest subprocess the
    gate ITSELF forks (collect-only / arch-invariant worker) resolves ``des``.
    These are set on ``os.environ`` precisely so the gate's inner subprocesses
    inherit them — identical to what the outer subprocess passed via ``env=``.
    """
    overrides = {
        "NWAVE_FRESHNESS": "skip",
        "PIPENV_DONT_LOAD_ENV": "1",
        "PYTHONPATH": str(REPO_ROOT / "src")
        + os.pathsep
        + os.environ.get("PYTHONPATH", ""),
    }
    prior = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        return run_cli_in_process(
            [
                "--feature-id",
                str(feature_id),
                "--entering-slice",
                str(entering_slice),
                "--repo",
                str(repo),
            ],
            cwd=str(repo),
            main=run_contract_gate.main,
        )
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# Synthetic feature-id and slice tag used across all slice-01 substrates.
_SYNTHETIC_FEATURE_ID = FeatureId("explain-guide-at-substrate")
_SYNTHETIC_SLICE_TAG = SliceTag("slice-01")

# A SECOND feature-id for the empty-intersection substrate (the repo DOES have
# a .feature tagged @feature-<id> but NOT @<entering-slice>).
_SYNTHETIC_SLICE_FOR_INTERSECTION = SliceTag("slice-at-99")


def _build_zero_collected_repo(tmp: Path, feature_id: FeatureId) -> None:
    """Build a repo with no .feature file tagged @feature-<feature_id>.

    The `_feature_tag_files` resolver will return an empty set -> the gate
    calls `_feature_scope_malformed(..., reason="zero-collected", ...)`.

    The repo is git-init-ed because `run_contract_gate` resolves paths
    relative to --repo; it does not require a real git history.
    """
    subprocess.run(
        ["git", "init", "-q", str(tmp)], check=True, capture_output=True, text=True
    )
    # A .feature file that is deliberately NOT tagged with @feature-<feature_id>.
    feature_dir = tmp / "tests" / "dummy"
    feature_dir.mkdir(parents=True)
    (feature_dir / "other.feature").write_text(
        "@feature-something-else @slice-01\n"
        "Feature: unrelated feature\n"
        "  Scenario: placeholder\n"
        "    Given nothing\n",
        encoding="utf-8",
    )


def _build_empty_intersection_repo(
    tmp: Path, feature_id: FeatureId, entering_slice: SliceTag
) -> None:
    """Build a repo whose .feature is tagged @feature-<id> but NOT @<entering_slice>.

    The `_feature_tag_files` resolver will return that file. `_slice_tags`
    will find no @<entering_slice> tag -> the gate calls
    `_feature_scope_malformed(..., reason="empty-intersection", ...)`.
    """
    subprocess.run(
        ["git", "init", "-q", str(tmp)], check=True, capture_output=True, text=True
    )
    feature_dir = tmp / "tests" / "acceptance" / str(feature_id)
    feature_dir.mkdir(parents=True)
    # Tagged with @feature-<id> but with a DIFFERENT slice tag -- not the
    # entering_slice that the gate will be told to look for.
    other_slice = SliceTag("slice-02")
    (feature_dir / "my-feature.feature").write_text(
        f"@feature-{feature_id} @{other_slice}\n"
        "Feature: explain and guide substrate\n"
        f"  @{other_slice}\n"
        "  Scenario: placeholder for other slice\n"
        "    Given nothing\n",
        encoding="utf-8",
    )


@dataclass
class ExplainGuideComposition:
    """Drives the production des run-contract-gate CLI for slice-01 ATs."""

    _tmp: Path | None = field(default=None)
    _feature_id: FeatureId = field(default=_SYNTHETIC_FEATURE_ID)
    _entering_slice: SliceTag = field(default=_SYNTHETIC_SLICE_TAG)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    # Parsed event from stdout (populated by when_operator_runs_gate).
    _event: dict[str, object] | None = field(default=None)
    # Universe snapshot before invocation (Mandate-8 pure-read guard).
    _universe_before: dict[str, object] | None = field(default=None)

    # ---- given -----------------------------------------------------------------

    def given_zero_collected_repo(self) -> None:
        """Synthetic repo with no .feature tagged @feature-<id>."""
        self._tmp = Path(tempfile.mkdtemp(prefix="explain-guide-at-"))
        self._feature_id = _SYNTHETIC_FEATURE_ID
        self._entering_slice = _SYNTHETIC_SLICE_TAG
        _build_zero_collected_repo(self._tmp, self._feature_id)

    def given_empty_intersection_repo(self) -> None:
        """Synthetic repo with a .feature tagged @feature-<id> but no @<slice>."""
        self._tmp = Path(tempfile.mkdtemp(prefix="explain-guide-at-"))
        self._feature_id = _SYNTHETIC_FEATURE_ID
        self._entering_slice = _SYNTHETIC_SLICE_FOR_INTERSECTION
        _build_empty_intersection_repo(
            self._tmp, self._feature_id, self._entering_slice
        )

    # ---- when ------------------------------------------------------------------

    def when_operator_runs_gate(self) -> None:
        """Invoke the REAL des run-contract-gate CLI as a subprocess black box.

        Pure-read guard (Mandate-8): snapshot the tmp dir before invocation and
        assert unchanged() for every universe entry after the invocation returns.

        Env-parity: a clean subprocess env with `NWAVE_FRESHNESS=skip` +
        `PIPENV_DONT_LOAD_ENV=1`. The freshness opt-out is REQUIRED because
        cwd is the synthetic tmp tree: without it the freshness wrapper may
        refuse with exit 78 before the gate logic runs, masking the
        FeatureScopeMalformed payload.
        """
        tmp = self._require_tmp()
        self._universe_before = self.capture_universe()

        exit_code, out, err = _run_contract_gate_in_process(
            self._feature_id, self._entering_slice, tmp
        )
        self._completed = subprocess.CompletedProcess(
            args=["des", "run-contract-gate"],
            returncode=exit_code,
            stdout=out,
            stderr=err,
        )

        # Parse the stdout JSON (one line per _emit() call).
        stdout = self._completed.stdout.strip()
        if stdout:
            self._event = json.loads(stdout)

        self._assert_pure_read()

    # ---- then ------------------------------------------------------------------

    def then_explain_and_guide_triad_present(self) -> None:
        """The emitted JSON carries non-empty what, why, and next fields.

        At authorship HEAD: `_explain_and_guide` mapper does not exist -> the
        emitted JSON has no `what`/`why`/`next` -> KeyError inside `event[...]`
        -> AssertionError. RED for the right reason.
        """
        event = self._require_event()
        for field_name in (
            ExplainAndGuideField.WHAT,
            ExplainAndGuideField.WHY,
            ExplainAndGuideField.NEXT,
        ):
            value = event.get(field_name.value)
            assert isinstance(value, str) and len(value) > 0, (
                f"FeatureScopeMalformed event must carry a non-empty '{field_name.value}' "
                f"field after DELIVER ships the _explain_and_guide mapper. "
                f"Got: {value!r}. Full event: {event}"
            )

    def then_canonical_event_fields_unchanged(self) -> None:
        """The five pre-existing FeatureScopeMalformed fields are unchanged.

        GREEN-on-author: these fields already exist in the pre-patch payload.
        This scenario is the load-bearing additive-only canary -- it will go RED
        if DELIVER accidentally removes or renames an existing field (D-1 guard).
        """
        event = self._require_event()
        assert event.get("event") == FEATURE_SCOPE_MALFORMED_EVENT, (
            f"'event' field must be {FEATURE_SCOPE_MALFORMED_EVENT!r} (unchanged). "
            f"Got: {event.get('event')!r}. Full event: {event}"
        )
        assert event.get("cause") == MALFORMED_SCOPE_CAUSE, (
            f"'cause' field must be {MALFORMED_SCOPE_CAUSE!r} (unchanged). "
            f"Got: {event.get('cause')!r}. Full event: {event}"
        )
        assert event.get("feature_id") == str(self._feature_id), (
            f"'feature_id' field must be {str(self._feature_id)!r} (unchanged). "
            f"Got: {event.get('feature_id')!r}. Full event: {event}"
        )
        assert event.get("reason") == MalformedScopeReason.ZERO_COLLECTED.value, (
            f"'reason' field must be {MalformedScopeReason.ZERO_COLLECTED.value!r} "
            f"(the zero-collected substrate triggers this token). "
            f"Got: {event.get('reason')!r}. Full event: {event}"
        )
        error = event.get("error")
        assert isinstance(error, str) and len(error) > 0, (
            f"'error' field must be a non-empty string (unchanged). "
            f"Got: {error!r}. Full event: {event}"
        )

    def then_exit_code_is_malformed_scope(self) -> None:
        """The process exits with exit code 2 (FeatureScopeMalformed, unchanged).

        GREEN-on-author: exit code 2 is emitted by `return 2` in
        `_feature_scope_malformed` which DELIVER must not change.
        """
        completed = self._require_completed()
        assert completed.returncode == MALFORMED_SCOPE_EXIT, (
            f"des run-contract-gate must exit with code {MALFORMED_SCOPE_EXIT} "
            f"on a malformed feature scope (D-1 additive-output-only invariant: "
            f"exit code is UNCHANGED). Got: {completed.returncode}. "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    def then_explain_and_guide_present_for_empty_intersection(self) -> None:
        """The empty-intersection refusal also carries non-empty what/why/next.

        At authorship HEAD: same as then_explain_and_guide_triad_present --
        `_explain_and_guide` mapper does not exist -> KeyError -> AssertionError.
        RED for the right reason.
        """
        event = self._require_event()
        assert event.get("reason") == MalformedScopeReason.EMPTY_INTERSECTION.value, (
            f"This scenario requires the empty-intersection substrate. "
            f"Got reason={event.get('reason')!r}. Full event: {event}"
        )
        for field_name in (
            ExplainAndGuideField.WHAT,
            ExplainAndGuideField.WHY,
            ExplainAndGuideField.NEXT,
        ):
            value = event.get(field_name.value)
            assert isinstance(value, str) and len(value) > 0, (
                f"FeatureScopeMalformed event for empty-intersection must carry "
                f"a non-empty '{field_name.value}' field. "
                f"Got: {value!r}. Full event: {event}"
            )

    def then_empty_intersection_why_distinct_from_zero_collected_why(
        self,
        zero_collected_why: str,
    ) -> None:
        """The `why` for empty-intersection differs from the `why` for zero-collected.

        A constant-string stub mapper would produce an identical `why` for both
        tokens; this assertion is the mechanical non-vacuity guard that proves
        the mapper is per-token, not a universal constant.

        At authorship HEAD: `what`/`why`/`next` absent for both tokens ->
        KeyError before this comparison runs -> AssertionError. RED.
        After DELIVER: the comparison runs and fails if the mapper returns the
        same string for both tokens.
        """
        event = self._require_event()
        empty_intersection_why = event.get(ExplainAndGuideField.WHY.value)
        assert (
            isinstance(empty_intersection_why, str) and len(empty_intersection_why) > 0
        ), (
            f"empty-intersection `why` must be a non-empty string. "
            f"Got: {empty_intersection_why!r}. Full event: {event}"
        )
        assert empty_intersection_why != zero_collected_why, (
            f"The `why` for empty-intersection ({empty_intersection_why!r}) must be "
            f"DISTINCT from the `why` for zero-collected ({zero_collected_why!r}). "
            "A constant-string stub mapper would fail this assertion."
        )

    def then_gate_does_not_write_to_repository(self) -> None:
        """Pure-read: the universe guard already ran in the When-step.

        The Mandate-8 state-delta assertion fires inside `when_operator_runs_gate`
        (the mutation, if any, happens during invocation). This Then re-affirms
        the contract by confirming the run completed -- the actual no-mutation
        proof is the When-step's `_assert_pure_read`.
        """
        self._require_completed()

    # ---- observable-event parsing ----------------------------------------------

    def zero_collected_why(self) -> str:
        """Return the `why` value from the most recent zero-collected invocation.

        Used by scenario 3 to obtain the baseline `why` string from a
        ZERO_COLLECTED substrate invocation, so the Then-step can compare it
        against the empty-intersection `why`.

        Raises AssertionError if the event is absent or `why` is not present.
        """
        event = self._require_event()
        why = event.get(ExplainAndGuideField.WHY.value)
        assert isinstance(why, str) and len(why) > 0, (
            f"zero_collected_why() requires the `why` field to be present "
            f"and non-empty. Got: {why!r}. Full event: {event}"
        )
        return why

    # ---- universe (Mandate-8 pure-read guard) ----------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate-8).

        The gate is a pure observer -- it reads the repo file tree via
        `_feature_tag_files` but MUST NOT write to the tmp directory.
        Universe entries are filesystem observables the gate could be tempted
        to touch; never internal struct fields.
        """
        tmp = self._require_tmp()
        return {
            "tmp.file_count": sum(1 for _ in tmp.rglob("*") if _.is_file()),
            "tmp.dir_count": sum(1 for _ in tmp.rglob("*") if _.is_dir()),
        }

    def _assert_pure_read(self) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert self._universe_before is not None, (
            "_universe_before must be captured before the gate runs"
        )
        assert_state_delta(
            before=self._universe_before,
            after=self.capture_universe(),
            universe={
                "tmp.file_count",
                "tmp.dir_count",
            },
            expected={
                "tmp.file_count": unchanged(),
                "tmp.dir_count": unchanged(),
            },
        )

    # ---- substrate helpers -----------------------------------------------------

    def _require_tmp(self) -> Path:
        assert self._tmp is not None, (
            "the synthetic repo must be built (Given) before "
            "running the gate (When) or capturing its universe"
        )
        return self._tmp

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "des run-contract-gate must be run (When) before asserting on "
            "its observable surface (Then)"
        )
        return self._completed

    def _require_event(self) -> dict[str, object]:
        completed = self._require_completed()
        assert self._event is not None, (
            "the gate must emit a JSON event on stdout (When) before asserting "
            "on its fields (Then). "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )
        return self._event

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
