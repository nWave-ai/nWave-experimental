"""slice-02 (the accountability layer) ATs for fix-self-extending-gate-deadlock.

Builds strictly ON TOP of the SHIPPED slice-01 DES-BOOTSTRAP mechanism (commit
171adf76a) -- it re-litigates NO slice-01 behavior; it ADDS the rejection +
non-degradation paths that keep the surgical exemption trustworthy under abuse:

  * (b1) a marker naming an OUT-OF-VOCAB gate-id (not in `BOOTSTRAPPABLE_GATES`)
         -> `malformed` verdict -> fail-CLOSED BLOCK `BootstrapMarkerMalformed`.
  * (b2) a marker with a MISSING/empty justification -> `malformed` verdict ->
         fail-CLOSED BLOCK `BootstrapJustificationMissing`.
  * (d)  the per-feature-per-gate reuse cap of 1 (D8): a SECOND `valid` bootstrap
         of the SAME (feature, gate) -- when a prior `BootstrapGateExempted{gate,
         feature_id}` record already exists in the ledger -> BLOCK
         `BootstrapReuseCapExceeded`; and fail-CLOSED on an UNREADABLE ledger
         (cannot prove the cap unspent -> BLOCK, never silent-pass).

This is HOOK-INTERNAL behavior -> pytest, NOT Gherkin. The tests drive the REAL
seams shipped by slice-01 (built ON, never re-tested), extended by slice-02:
  * `des_marker_parser.classify_bootstrap(markers, firing_gate_id)` -- the pure
    classifier, whose slice-02 verdict extension is the `malformed` value.
  * `carpaccio_intercept._gate_invoker_for(...)._invoke` -- the per-gate decision
    seam where a `malformed` verdict fail-closed-BLOCKS and a `valid` verdict now
    first consults the reuse cap against the REAL `AtCompletionLedger`.
  * `AtCompletionLedger.append_gate_event(..., gate=, justification=)` /
    `read_records()` -- the REAL ledger the reuse cap reads (prior exemptions) +
    fail-closes on when it is corrupt.

Step vocabulary (Mandate-12 SSOT): the pure builders/recorders/context helpers
are IMPORTED from the slice-01 module, never copy-pasted -- one shared surface
across the two AT modules.

RED-not-BROKEN discipline (the in-process active-RED pattern, P1-P4): there are
ZERO net-new production SYMBOLS to import -- the slice-02 behavior surfaces only
as different RETURN VALUES of already-shipped functions (`classify_bootstrap`
returning `"malformed"` where it returns `"absent-for-this-gate"`/`"valid"`
today; `_invoke` BLOCKING where it runs/skips today). Every import at module top
resolves against HEAD, so absence surfaces as a semantic AssertionError at
RUNTIME, never a collection error.

What each AT locks (Handoff-to-DISTILL (b1)/(b2)/(d) -- slice-02 scope only):
  * test_classify_bootstrap_malformed_and_slice01_verdicts -> the pure classifier
    truth table: the two `malformed` rows (b1/b2) PLUS the three slice-01 rows
    (valid / divergence-absent / no-marker) as an unchanged-verdict regression pin.
  * test_malformed_bootstrap_fails_closed_at_invoke -> the two DISTINCT fail-closed
    BLOCK events at `_invoke` (BootstrapMarkerMalformed vs BootstrapJustification-
    Missing), the real runner NOT invoked, and NO exemption earned (b1 + b2).
  * test_reuse_cap_blocks_second_bootstrap_of_same_gate -> the (feature,gate)
    reuse cap of 1: a second valid bootstrap BLOCKs `BootstrapReuseCapExceeded`
    and writes no new exemption, while the FIRST still clears (d + slice-01 pin).
  * test_reuse_cap_fails_closed_on_unreadable_ledger -> an unreadable ledger
    cannot prove the cap unspent, so a valid bootstrap BLOCKs, never silent-passes.
  * test_slice01_no_marker_path_unchanged_by_slice02 -> the zero-blast-radius pin:
    the added malformed + reuse-cap branches never touch the normal (unmarked)
    path -- every gate runs exactly as slice-01 shipped, no ledger read, no block.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain import des_marker_parser as dmp

# Mandate-12 SSOT: the slice-01 step vocabulary is SHARED, not duplicated. These
# are pure builders / recorders / context helpers -- importing them (not the
# slice-01 `captured_ledger` fake, which the reuse-cap ATs deliberately avoid so
# the REAL ledger read path is exercised) keeps ONE canonical helper surface.
from tests.des.unit.adapters.test_carpaccio_intercept_bootstrap_marker import (
    _ALL_GATES,
    _CARPACCIO,
    _FEATURE_ID,
    _JUSTIFICATION,
    _NO_BOOTSTRAP_PROMPT,
    _WAVE,
    _bootstrap_prompt,
    _build_invoker,
    _ctx,
)


# A gate-id that is NOT a member of the closed `BOOTSTRAPPABLE_GATES` vocabulary
# (D6) -- naming it is the (b1) out-of-vocab malformation.
_OUT_OF_VOCAB_GATE = "totally-made-up-gate"


def _prompt_gate_only(gate: str) -> str:
    """A DES-BOOTSTRAP dispatch naming ``gate`` but carrying NO justification marker.

    The (b2) malformation: the mandatory `DES-BOOTSTRAP-JUSTIFICATION` marker is
    OMITTED, so the parser yields `bootstrap_justification is None` (an empty
    `<!-- DES-BOOTSTRAP-JUSTIFICATION : -->` parses to None identically, so this
    one builder covers both the missing and the empty case).
    """
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-02 -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
        f"<!-- DES-BOOTSTRAP : {gate} -->\n"
    )


def _event_of(stdout: str) -> str | None:
    """The `event` field of a gate's JSON stdout, or None when unparseable."""
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return payload.get("event") if isinstance(payload, dict) else None


def _event_matches(stdout: str, expected: str) -> bool:
    """Whether the gate stdout carries ``expected`` (as the JSON event or a substring)."""
    return _event_of(stdout) == expected or expected in stdout


def _bootstrap_exemptions_on_disk(tmp_path: Path) -> list[dict]:
    """Every `BootstrapGateExempted` record on the REAL per-feature ledger.

    Reads the same `.nwave/telemetry/atdd-pure/{feature_id}.jsonl` substrate the
    slice-01 `_bootstrap_exempt` writes to and the slice-02 reuse cap reads. An
    absent ledger file returns `[]` (M7 read contract: absence is not corruption).
    """
    records = AtCompletionLedger(_FEATURE_ID, tmp_path).read_records()
    return [r for r in records if r.get("event") == "BootstrapGateExempted"]


# ---------------------------------------------------------------------------
# AT 1 -- the pure classifier truth table: two malformed rows + slice-01 pin.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt, firing_gate_id, expected_verdict",
    [
        pytest.param(
            _bootstrap_prompt(_OUT_OF_VOCAB_GATE),
            _CARPACCIO,
            "malformed",
            id="out-of-vocab-gate-malformed",
        ),
        pytest.param(
            _prompt_gate_only(_CARPACCIO),
            _CARPACCIO,
            "malformed",
            id="missing-justification-malformed",
        ),
        # --- slice-01 regression pins (unchanged verdicts) -------------------
        pytest.param(
            _bootstrap_prompt(_CARPACCIO),
            _CARPACCIO,
            "valid",
            id="slice01-valid-unchanged",
        ),
        pytest.param(
            _bootstrap_prompt(_CARPACCIO),
            _WAVE,
            "absent-for-this-gate",
            id="slice01-divergence-absent-unchanged",
        ),
        pytest.param(
            _NO_BOOTSTRAP_PROMPT,
            _CARPACCIO,
            "absent-for-this-gate",
            id="slice01-no-marker-unchanged",
        ),
    ],
)
def test_classify_bootstrap_malformed_and_slice01_verdicts(
    prompt: str, firing_gate_id: str, expected_verdict: str
) -> None:
    """`classify_bootstrap` gains the slice-02 `malformed` verdict; slice-01 unchanged.

    The 1:1 truth-table-to-AT for the security-adjacent classifier (D4): an
    OUT-OF-VOCAB gate-id (b1) and a MISSING justification (b2) are BOTH the
    intrinsic `malformed` verdict, INDEPENDENT of divergence-within-a-valid-
    composition. The three slice-01 rows pin that `valid` / `absent-for-this-gate`
    (divergence) / `absent-for-this-gate` (no marker) are UNCHANGED.

    RED against HEAD: `classify_bootstrap` has no `malformed` verdict yet -- the
    out-of-vocab prompt returns `"absent-for-this-gate"` and the missing-
    justification prompt returns `"valid"` today, so both malformed rows fail
    the equality. (No collection error: `classify_bootstrap` already exists.)
    """
    markers = dmp.DesMarkerParser().parse(prompt)
    verdict = dmp.classify_bootstrap(markers, firing_gate_id)
    assert verdict == expected_verdict, (
        f"classify_bootstrap(firing_gate_id={firing_gate_id!r}) must be "
        f"{expected_verdict!r}; got {verdict!r}"
    )


# ---------------------------------------------------------------------------
# AT 2 -- malformed markers fail-CLOSED at `_invoke` with two DISTINCT events.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt, firing_gate_id, expected_event",
    [
        pytest.param(
            _bootstrap_prompt(_OUT_OF_VOCAB_GATE),
            _CARPACCIO,
            "BootstrapMarkerMalformed",
            id="out-of-vocab-gate-blocks-marker-malformed",
        ),
        pytest.param(
            _prompt_gate_only(_CARPACCIO),
            _CARPACCIO,
            "BootstrapJustificationMissing",
            id="missing-justification-blocks-justification-missing",
        ),
    ],
)
def test_malformed_bootstrap_fails_closed_at_invoke(
    prompt: str, firing_gate_id: str, expected_event: str, tmp_path: Path
) -> None:
    """A malformed DES-BOOTSTRAP marker fail-CLOSED BLOCKs at `_invoke`.

    The two malformations map 1:1 to two DISTINCT block events (D4): an OUT-OF-
    VOCAB gate-id -> `BootstrapMarkerMalformed`; a MISSING/empty justification ->
    `BootstrapJustificationMissing`. In BOTH cases the dispatch is neither run nor
    skipped -- it is BLOCKED (the real gate runner is NOT invoked, exit != 0) and
    NO exemption is earned (a malformed claim must never buy a surgical skip).

    RED against HEAD: `_invoke` has no malformed branch. The out-of-vocab marker
    classifies `absent-for-this-gate` today -> the carpaccio runner IS invoked
    (the `calls == []` assertion fails). The missing-justification marker
    classifies `valid` today -> `_bootstrap_exempt` clears with exit 0 AND writes
    an exemption (the `exit_code != 0` and no-exemption assertions fail).
    """
    invoke, recs = _build_invoker()
    exit_code, stdout = invoke(firing_gate_id, _ctx(prompt, tmp_path))

    assert recs[firing_gate_id].calls == [], (
        "a malformed bootstrap must FAIL-CLOSED: the real gate runner must NOT "
        f"run (neither run nor skipped). calls={recs[firing_gate_id].calls}"
    )
    assert exit_code != 0, (
        "a malformed bootstrap marker must BLOCK (fail-closed), never clear with "
        f"exit 0. exit_code={exit_code}"
    )
    assert _event_matches(stdout, expected_event), (
        f"the block must name the distinct {expected_event!r} event; got {stdout!r}"
    )
    assert _bootstrap_exemptions_on_disk(tmp_path) == [], (
        "a malformed bootstrap must NOT earn a BootstrapGateExempted record -- an "
        "invalid claim can never buy a surgical skip."
    )


# ---------------------------------------------------------------------------
# AT 3 -- the per-feature-per-gate reuse cap of 1 (D8).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seed_prior_exemption, expect_block, expected_event",
    [
        pytest.param(
            True,
            True,
            "BootstrapReuseCapExceeded",
            id="second-use-of-same-gate-blocked",
        ),
        pytest.param(
            False,
            False,
            None,
            id="first-use-of-gate-granted-slice01-pin",
        ),
    ],
)
def test_reuse_cap_blocks_second_bootstrap_of_same_gate(
    seed_prior_exemption: bool,
    expect_block: bool,
    expected_event: str | None,
    tmp_path: Path,
) -> None:
    """A SECOND valid bootstrap of the same (feature, gate) is fail-closed BLOCKed.

    The committed non-degradation control (D8, cap = 1): before granting a
    `valid` bootstrap, `_invoke` reads the REAL ledger for a prior
    `BootstrapGateExempted{gate, feature_id}` record. When one already exists the
    second bootstrap BLOCKs `BootstrapReuseCapExceeded` and writes NO new
    exemption -- a gate can never be silently disabled by repeated stamping. The
    FIRST bootstrap of a (feature, gate) still clears exactly as slice-01 shipped
    (the empty-ledger regression pin), so the cap gates only re-use.

    RED against HEAD: `_invoke`/`_bootstrap_exempt` never reads the ledger for a
    prior exemption. With a seeded prior record the second bootstrap still clears
    with exit 0 AND writes a SECOND exemption today, so both the `exit_code != 0`
    and the no-new-record assertions fail. The empty-ledger param is green-before-
    and-after (the slice-01 grant behavior).
    """
    if seed_prior_exemption:
        AtCompletionLedger(_FEATURE_ID, tmp_path).append_gate_event(
            event="BootstrapGateExempted",
            slice_id="slice-01",
            gate=_CARPACCIO,
            justification=_JUSTIFICATION,
        )
    pre_count = len(_bootstrap_exemptions_on_disk(tmp_path))

    invoke, recs = _build_invoker()
    exit_code, stdout = invoke(
        _CARPACCIO, _ctx(_bootstrap_prompt(_CARPACCIO), tmp_path)
    )
    post = _bootstrap_exemptions_on_disk(tmp_path)

    # Whether granted (skip) or capped (block), the real carpaccio runner never runs.
    assert recs[_CARPACCIO].calls == [], (
        "a bootstrapped carpaccio gate is never run by its real runner (it is "
        f"skipped-or-blocked). calls={recs[_CARPACCIO].calls}"
    )
    if expect_block:
        assert exit_code != 0, (
            "a SECOND bootstrap of the same (feature, gate) must be BLOCKed "
            f"(reuse cap = 1); got exit {exit_code}"
        )
        assert expected_event is not None and _event_matches(stdout, expected_event), (
            f"the capped block must name {expected_event!r}; got {stdout!r}"
        )
        assert len(post) == pre_count, (
            "a capped second bootstrap must NOT write a new BootstrapGateExempted "
            f"record. pre={pre_count} post={len(post)}"
        )
    else:
        assert exit_code == 0, (
            "the FIRST bootstrap of a (feature, gate) still clears with exit 0 "
            f"(slice-01 grant behavior preserved); got exit {exit_code}"
        )
        assert len(post) == pre_count + 1, (
            "the first bootstrap writes exactly one BootstrapGateExempted record. "
            f"pre={pre_count} post={len(post)}"
        )


# ---------------------------------------------------------------------------
# AT 4 -- the reuse cap is fail-CLOSED on an unreadable ledger.
# ---------------------------------------------------------------------------


def test_reuse_cap_fails_closed_on_unreadable_ledger(tmp_path: Path) -> None:
    """An UNREADABLE ledger cannot prove the cap unspent -> the bootstrap BLOCKs.

    D8 fail-CLOSED: the reuse cap reads the ledger under the M7 fail-closed
    integrity contract; a corrupt substrate makes `read_records` raise. The cap
    cannot then prove the (feature, gate) exemption is unspent, so the valid
    bootstrap must NOT be granted -- it fail-closes to a BLOCK, never a silent
    pass. Fail-closed is accepted in EITHER shape: `_invoke` returns a non-zero
    block, OR it lets the integrity violation propagate (the upstream M1 wrapper
    then blocks it). The forbidden outcome is a silent grant (exit 0).

    RED against HEAD: `_bootstrap_exempt` never reads the ledger, so the corrupt
    substrate is ignored and the bootstrap is granted with exit 0 today -- the
    `exit_code != 0` assertion fails. (The corrupt file is written by the test, so
    it causes a runtime read failure, never a collection error.)
    """
    ledger_path = (
        tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("this line is not valid ledger json\n", encoding="utf-8")

    invoke, recs = _build_invoker()
    try:
        result: tuple[int, str] | None = invoke(
            _CARPACCIO, _ctx(_bootstrap_prompt(_CARPACCIO), tmp_path)
        )
    except Exception:
        # A propagated integrity violation is itself fail-closed: the upstream M1
        # wrapper turns any exception from `_invoke` into an AtddPureHookInternalError
        # block. Never a silent pass.
        result = None

    assert recs[_CARPACCIO].calls == [], (
        "fail-closed: an unreadable ledger must not let the gate be silently "
        f"skipped-and-cleared by its runner. calls={recs[_CARPACCIO].calls}"
    )
    if result is not None:
        exit_code, _stdout = result
        assert exit_code != 0, (
            "the reuse cap is FAIL-CLOSED: an unreadable ledger cannot prove the "
            "cap is unspent, so a valid bootstrap must BLOCK (exit != 0), never "
            f"silent-pass. exit_code={exit_code}"
        )


# ---------------------------------------------------------------------------
# AT 5 -- zero-blast-radius: the normal (unmarked) path is untouched by slice-02.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("firing_gate_id", _ALL_GATES)
def test_slice01_no_marker_path_unchanged_by_slice02(
    firing_gate_id: str, tmp_path: Path
) -> None:
    """slice-02's malformed + reuse-cap branches never touch the normal path.

    A dispatch with NO DES-BOOTSTRAP marker must run every `_invoke` exactly as
    slice-01 shipped -- the added malformed classification and the ledger-reading
    reuse cap must NOT fire on an unmarked dispatch (no ledger read, no block, no
    exemption). Green-before-and-after: the zero-blast-radius pin guarding the new
    slice-02 code, not a re-authoring of slice-01's suite.
    """
    invoke, recs = _build_invoker()
    exit_code, _stdout = invoke(firing_gate_id, _ctx(_NO_BOOTSTRAP_PROMPT, tmp_path))

    assert len(recs[firing_gate_id].calls) == 1, (
        f"an unmarked dispatch must run gate {firing_gate_id!r} exactly as today. "
        f"calls={recs[firing_gate_id].calls}"
    )
    assert exit_code == 0, (
        f"an unmarked dispatch clears (recorder default exit 0); got {exit_code}"
    )
    assert _bootstrap_exemptions_on_disk(tmp_path) == [], (
        "an unmarked dispatch must emit NO BootstrapGateExempted record."
    )
