"""slice-01 (@walking-skeleton) ATs for fix-self-extending-gate-deadlock.

The DES-BOOTSTRAP mechanism dissolves the self-extending-gate deadlock class: a
dispatch whose purpose is to REPAIR a dispatch-gate G can clear exactly that ONE
gate and land, while every other composed gate still fires -- and the exemption
leaves an audit trail. These ATs pin the three load-bearing behaviors that alone
dissolve the deadlock end-to-end, plus the self-application arch-test.

This is HOOK-INTERNAL behavior -> pytest, NOT Gherkin. The tests drive the REAL
to-be-added seams (no reimplementation):
  * `des_marker_parser.classify_bootstrap(markers, firing_gate_id)` -- the pure
    3-verdict classifier (to be ADDED alongside `classify_atdd_pure_dispatch`).
  * `des_marker_parser.BOOTSTRAPPABLE_GATES` -- the closed 3-member dispatch-gate
    vocabulary (to be ADDED as the SSOT const).
  * `carpaccio_intercept._gate_invoker_for(...)._invoke` -- the per-gate decision
    seam where the bootstrap check is inserted (Reuse Analysis: "insert a per-gate
    bootstrap check at the top of `_invoke`").
  * `AtCompletionLedger.append_gate_event(..., gate=, justification=)` -- the
    signature-delta audit write carrying `BootstrapGateExempted{gate,justification,
    feature_id}` (observed via a captured fake ledger).

What each AT locks (Handoff-to-DISTILL (a)/(c)/(e) -- slice-01 scope only;
malformed / out-of-vocab / reuse-cap are slice-02 and are NOT authored here):
  * test_classify_bootstrap_three_verdicts     -> the pure 3-verdict truth table.
  * test_bootstrap_skips_only_the_named_firing_gate -> (a) surgical skip of the
    named+firing gate + `BootstrapGateExempted` audit AND (c) the CANONICAL
    DIVERGENCE anti-self-block: a marker naming gate G does NOT skip a DIFFERENT
    composed gate whose `_invoke` is firing -- that gate runs normally.
  * test_no_bootstrap_marker_runs_every_gate_and_emits_no_exemption -> the
    zero-blast-radius regression pin: a no-marker dispatch runs every gate exactly
    as today, no exemption emitted.
  * test_carpaccio_slice_gate_is_bootstrappable -> (e) self-application: the
    mechanism can bootstrap its OWN future repairs; feature-end EXCLUDED (Critical-1).

RED-not-BROKEN discipline (P1): the not-yet-added names (`classify_bootstrap`,
`BOOTSTRAPPABLE_GATES`, the `_invoke` bootstrap check) are referenced ONLY inside
test bodies -- never imported at module top -- so absence surfaces at RUNTIME
(AttributeError / AssertionError), NOT as a collection error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.drivers.hooks import carpaccio_intercept as ci
from des.domain import des_marker_parser as dmp


_FEATURE_ID = "fix-self-extending-gate-deadlock"

# The closed 3-member dispatch-gate class the bootstrap vocabulary spans (D6).
_CARPACCIO = "carpaccio-slice-gate"
_WAVE = "verify-wave-dispatch"
_READINESS = "verify-readiness-pre-dispatch"
_ALL_GATES = (_WAVE, _READINESS, _CARPACCIO)

_JUSTIFICATION = "repairs the carpaccio-slice-gate at_kind check (instance-3 deadlock)"


def _bootstrap_prompt(gate: str, justification: str = _JUSTIFICATION) -> str:
    """A well-formed atdd_pure dispatch prompt carrying the two DES-BOOTSTRAP markers."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
        f"<!-- DES-BOOTSTRAP : {gate} -->\n"
        f"<!-- DES-BOOTSTRAP-JUSTIFICATION : {justification} -->\n"
    )


_NO_BOOTSTRAP_PROMPT = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-MODE : atdd_pure -->\n"
    "<!-- DES-PHASE : A_GREEN_ATS -->\n"
    "<!-- DES-SLICE : slice-01 -->\n"
    f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
)


# ---------------------------------------------------------------------------
# Test doubles: per-gate runner recorders + a capturing fake ledger.
# ---------------------------------------------------------------------------


class _Recorder:
    """A gate runner double recording each call; accepts either runner shape.

    (feature_id, slice_id) for the slice gates OR (subagent_type, prompt) for the
    wave-dispatch guard -- both are 2-arg, captured uniformly via ``*args``.
    """

    def __init__(self, exit_code: int = 0, stdout: str = '{"event": "GateCleared"}'):
        self.calls: list[tuple] = []
        self._rc = exit_code
        self._stdout = stdout

    def __call__(self, *args: str) -> tuple[int, str]:
        self.calls.append(args)
        return self._rc, self._stdout


def _build_invoker() -> tuple:
    """Build the REAL `_invoke` with a distinct recorder per composed gate."""
    recs = {gid: _Recorder() for gid in _ALL_GATES}
    invoke = ci._gate_invoker_for(
        carpaccio_runner=recs[_CARPACCIO],
        readiness_runner=recs[_READINESS],
        wave_dispatch_runner=recs[_WAVE],
    )
    return invoke, recs


def _ctx(prompt: str, tmp_path: Path) -> dict[str, str]:
    """The dispatcher context dict `_invoke` reads -- the prompt carries the marker."""
    return {
        "feature_id": _FEATURE_ID,
        "slice_id": "slice-01",
        "repo_root": str(tmp_path),
        "subagent_type": "nw-software-crafter",
        "prompt": prompt,
    }


@pytest.fixture
def captured_ledger(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture every `AtCompletionLedger.append_gate_event` the intercept issues.

    Mirrors how `_emit_carpaccio_gate_event` constructs the ledger from the
    module global `ci.AtCompletionLedger`; the bootstrap exemption emit follows
    the same precedent, so patching the class name captures it regardless of the
    exact construction shape (per-feature or singleton).
    """
    records: list[dict] = []

    class _FakeLedger:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._ctor_args = args
            self._ctor_kwargs = kwargs

        def append_gate_event(self, *args: object, **kwargs: object) -> dict:
            records.append(
                {
                    "args": args,
                    "kwargs": kwargs,
                    "ctor_args": self._ctor_args,
                    "ctor_kwargs": self._ctor_kwargs,
                }
            )
            return {"event": kwargs.get("event")}

        def read_records(self, *args: object, **kwargs: object) -> list[dict]:
            # slice-02 GREEN-phase double-maintenance: the reuse cap reads the
            # ledger before granting a `valid` bootstrap. The slice-01 fake has
            # no prior exemptions, so the cap is always unspent here -> [].
            return []

    monkeypatch.setattr(ci, "AtCompletionLedger", _FakeLedger)
    return records


def _exemption_records(captured: list[dict]) -> list[dict]:
    """The captured `BootstrapGateExempted` records (event may be positional/kw)."""
    out: list[dict] = []
    for r in captured:
        event = r["kwargs"].get("event")
        if event is None and r["args"]:
            event = r["args"][0]
        if event == "BootstrapGateExempted":
            out.append(r)
    return out


def _feature_id_seen(rec: dict, expected: str) -> bool:
    """feature_id may ride the append kwarg OR the ledger constructor -- accept either."""
    return (
        rec["kwargs"].get("feature_id") == expected
        or expected in rec["ctor_args"]
        or expected in rec["ctor_kwargs"].values()
    )


# ---------------------------------------------------------------------------
# AT 1 -- the pure 3-verdict classifier.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt, firing_gate_id, expected_verdict",
    [
        pytest.param(
            _bootstrap_prompt(_CARPACCIO),
            _CARPACCIO,
            "valid",
            id="names-the-firing-gate-valid",
        ),
        pytest.param(
            _bootstrap_prompt(_CARPACCIO),
            _WAVE,
            "absent-for-this-gate",
            id="names-a-different-composed-gate-absent",
        ),
        pytest.param(
            _NO_BOOTSTRAP_PROMPT,
            _CARPACCIO,
            "absent-for-this-gate",
            id="no-bootstrap-marker-absent",
        ),
    ],
)
def test_classify_bootstrap_three_verdicts(
    prompt: str, firing_gate_id: str, expected_verdict: str
) -> None:
    """`classify_bootstrap(markers, firing_gate_id)` returns the slice-01 verdicts.

    A well-formed in-vocab marker naming the CURRENTLY-firing gate -> `valid`;
    the SAME marker evaluated against a DIFFERENT in-vocab composed gate ->
    `absent-for-this-gate` (the canonical divergence rule, D4); no marker at all
    -> `absent-for-this-gate`. (malformed / out-of-vocab is slice-02.)

    RED against current code: `des_marker_parser.classify_bootstrap` does not
    exist yet -> AttributeError inside the body (module imports fine at top).
    """
    markers = dmp.DesMarkerParser().parse(prompt)
    verdict = dmp.classify_bootstrap(markers, firing_gate_id)
    assert verdict == expected_verdict, (
        f"classify_bootstrap for a marker naming {_CARPACCIO!r} evaluated with "
        f"firing_gate_id={firing_gate_id!r} must be {expected_verdict!r}; got {verdict!r}"
    )


# ---------------------------------------------------------------------------
# AT 2 (a surgical skip) + AT 3 (c canonical divergence) -- one truth table.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("firing_gate_id", _ALL_GATES)
def test_bootstrap_skips_only_the_named_firing_gate(
    firing_gate_id: str, tmp_path: Path, captured_ledger: list[dict]
) -> None:
    """A DES-BOOTSTRAP: carpaccio-slice-gate dispatch skips ONLY that gate.

    Driving the REAL `_invoke` per composed gate for the SAME bootstrap dispatch:
      * firing == carpaccio-slice-gate -> SKIPPED: the real carpaccio runner is
        NOT invoked, exit 0, and a `BootstrapGateExempted{gate,justification,
        feature_id}` audit record is written (AT a). [NET-NEW -> RED now]
      * firing == any OTHER composed gate -> `absent-for-this-gate`: the real
        runner for THAT gate fires NORMALLY (NOT a block, NOT a skip) and NO
        exemption is emitted -- the Critical-2 anti-self-block lock (AT c). [pin]

    RED against current code: `_invoke` has no bootstrap check, so the carpaccio
    param's `runner NOT invoked` assertion fails (the runner IS invoked today).
    The 3 divergence params are green-before-and-after regression pins.
    """
    invoke, recs = _build_invoker()
    exit_code, _stdout = invoke(
        firing_gate_id, _ctx(_bootstrap_prompt(_CARPACCIO), tmp_path)
    )
    exemptions = _exemption_records(captured_ledger)

    if firing_gate_id == _CARPACCIO:
        assert recs[_CARPACCIO].calls == [], (
            "a valid DES-BOOTSTRAP naming the firing carpaccio gate must SKIP it -- "
            f"the real carpaccio runner must NOT be invoked. calls={recs[_CARPACCIO].calls}"
        )
        assert exit_code == 0, (
            f"a skipped (bootstrapped) gate clears with exit 0; got {exit_code}"
        )
        assert len(exemptions) == 1, (
            "the surgical skip must write exactly ONE BootstrapGateExempted audit "
            f"record (auditable from the first commit). exemptions={exemptions}"
        )
        rec = exemptions[0]
        assert rec["kwargs"].get("gate") == _CARPACCIO, (
            f"the audit record must carry gate={_CARPACCIO!r}. rec={rec}"
        )
        assert rec["kwargs"].get("justification") == _JUSTIFICATION, (
            f"the audit record must carry the marker justification. rec={rec}"
        )
        assert _feature_id_seen(rec, _FEATURE_ID), (
            f"the audit record must carry feature_id={_FEATURE_ID!r}. rec={rec}"
        )
    else:
        assert len(recs[firing_gate_id].calls) == 1, (
            f"canonical divergence: a marker naming {_CARPACCIO!r} must NOT skip a "
            f"DIFFERENT firing gate {firing_gate_id!r} -- its real runner must fire "
            f"normally (absent-for-this-gate, NOT a self-block). calls={recs[firing_gate_id].calls}"
        )
        assert exemptions == [], (
            f"no exemption may be written when the firing gate {firing_gate_id!r} is "
            f"NOT the one the marker names. exemptions={exemptions}"
        )


# ---------------------------------------------------------------------------
# AT 4 -- zero-blast-radius: a no-marker dispatch is byte-identical to today.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("firing_gate_id", _ALL_GATES)
def test_no_bootstrap_marker_runs_every_gate_and_emits_no_exemption(
    firing_gate_id: str, tmp_path: Path, captured_ledger: list[dict]
) -> None:
    """A dispatch with NO DES-BOOTSTRAP marker runs every `_invoke` exactly as today.

    The regression pin that guards the deadlock fix against blast radius: a normal
    (unmarked) dispatch must still run every composed gate's real runner and emit
    no BootstrapGateExempted record. Green-before-and-after.
    """
    invoke, recs = _build_invoker()
    invoke(firing_gate_id, _ctx(_NO_BOOTSTRAP_PROMPT, tmp_path))

    assert len(recs[firing_gate_id].calls) == 1, (
        f"an unmarked dispatch must run gate {firing_gate_id!r} exactly as today. "
        f"calls={recs[firing_gate_id].calls}"
    )
    assert _exemption_records(captured_ledger) == [], (
        "an unmarked dispatch must emit NO BootstrapGateExempted record."
    )


# ---------------------------------------------------------------------------
# AT 5 (e) -- self-application arch-test.
# ---------------------------------------------------------------------------


def test_carpaccio_slice_gate_is_bootstrappable() -> None:
    """The mechanism can bootstrap its OWN future repairs (self-hosting property).

    `carpaccio-slice-gate` -- the gate this feature's landing crafter itself
    trips -- must be in the closed vocabulary, so a future carpaccio-gated repair
    of the recognizer surgically skips ONLY that gate. `feature-end-cycle-gate` is
    DELIBERATELY EXCLUDED (Critical-1: standing-recurrence gate, not a rare
    dispatch-gate).

    RED against current code: `des_marker_parser.BOOTSTRAPPABLE_GATES` does not
    exist yet -> AttributeError inside the body.
    """
    assert _CARPACCIO in dmp.BOOTSTRAPPABLE_GATES, (
        "carpaccio-slice-gate must be bootstrappable so the mechanism can repair "
        "its own future edits (self-hosting)."
    )
    assert "feature-end-cycle-gate" not in dmp.BOOTSTRAPPABLE_GATES, (
        "feature-end-cycle-gate is EXCLUDED (Critical-1) -- it is a standing-"
        "recurrence gate, not a rare/self-limiting dispatch-gate."
    )
    assert set(dmp.BOOTSTRAPPABLE_GATES) == set(_ALL_GATES), (
        "the bootstrap vocabulary is the closed 4-member dispatch-gate class (D6)."
    )
