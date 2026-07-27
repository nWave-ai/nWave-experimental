"""A DocCoherenceWarned record must not describe itself as REFUSED.

The doc-coherence gate is advisory at exit 1: the cycle PROCEEDS and records
``DocCoherenceWarned``. But the leg adopted the gate's own exit-1 stdout as its
detail verbatim, and that stdout announces ``"event": "DocCoherenceRefused"``
plus a ``REFUSED`` banner -- so an advisory record read as a refusal and
contradicted the very verdict carrying it.

The substantive content (which claims are false, and how many) must survive the
relabel: stripping the contradiction by discarding the diagnostic would trade a
confusing record for an empty one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.application import feature_end_cycle_service as svc


_VIOLATION_COUNT = 3


def _gate_exit_1_stdout() -> str:
    """Byte-shaped like the real gate's exit-1 stdout (JSON line + banner)."""
    payload = json.dumps(
        {
            "event": "DocCoherenceRefused",
            "what": f"{_VIOLATION_COUNT} doc claim(s) are false of the actual tree",
            "why": "docs promising absent scripts/files/modules ship a lie",
            "how": "make it true, or make the doc honest.",
        }
    )
    banner = f"✗ REFUSED — {_VIOLATION_COUNT} false doc claim(s):"
    return f"{payload}\n{banner}\n  - README.md claims scripts/nope.py\n"


@pytest.fixture
def warned_leg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    monkeypatch.setattr(svc, "_repo_has_doc_claims", lambda _root: True)
    monkeypatch.setattr(
        svc,
        "_dispatch",
        lambda _root, _argv: subprocess.CompletedProcess(
            args=_argv, returncode=1, stdout=_gate_exit_1_stdout(), stderr=""
        ),
    )

    class _Ledger:
        def append_doc_coherence_gate_ran(self, **_kwargs: object) -> None:
            return None

    return svc._run_doc_coherence_gate(
        ledger=_Ledger(),  # type: ignore[arg-type]
        repo_root=tmp_path,
        feature_id="f-doc-coherence-advisory",
    )


def test_warn_path_returns_the_advisory_leg(warned_leg: object) -> None:
    assert isinstance(warned_leg, svc.DocCoherenceLegWarned)


@pytest.mark.parametrize("refusal_token", ["DocCoherenceRefused", "REFUSED"])
def test_advisory_detail_never_calls_itself_refused(
    warned_leg: object, refusal_token: str
) -> None:
    """The detail must not carry the gate's refusal framing.

    Both tokens matter: the machine-readable ``event`` name is what a ledger
    reader greps for, and the human banner is what an operator sees.
    """
    assert refusal_token not in warned_leg.detail  # type: ignore[attr-defined]


def test_advisory_detail_says_it_is_advisory(warned_leg: object) -> None:
    detail = warned_leg.detail.lower()  # type: ignore[attr-defined]
    assert "advisory" in detail or "warn" in detail


def test_advisory_detail_keeps_the_substantive_finding(warned_leg: object) -> None:
    """Relabelling must not cost the operator the actual finding."""
    detail = warned_leg.detail  # type: ignore[attr-defined]
    assert str(_VIOLATION_COUNT) in detail
    assert "scripts/nope.py" in detail
