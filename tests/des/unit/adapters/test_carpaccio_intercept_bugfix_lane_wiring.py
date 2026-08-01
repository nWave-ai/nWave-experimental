"""RC4-b hook-wiring: the PreToolUse intercept threads a DES-LANE: bugfix marker
into the readiness-gate subprocess invocation.

The RC4-b gate-logic (verify_readiness_pre_dispatch `--lane bugfix`) is shipped, but
unreachable from a live dispatch until the carpaccio PreToolUse intercept (a) parses
the `DES-LANE: bugfix` + justification markers from the dispatch prompt and (b) passes
`--lane`/`--lane-justification` to the readiness gate subprocess.

Wiring design (ADD-not-mutate, contained): the lane is baked into the readiness runner
at BUILD time (`_real_readiness_runner(project_root, lane=..., lane_justification=...)`)
so the `ReadinessRunner` Callable signature `(feature_id, entering_slice)` stays
UNCHANGED — no blast-radius on the registry / injected test doubles. A runner built
with no lane invokes the gate byte-identically (default path preserved).

Markers (two, to avoid embedded-colon ambiguity in the justification):
  <!-- DES-LANE : bugfix -->
  <!-- DES-LANE-JUSTIFICATION : <names the defect + a test_<name> regression test> -->
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from des.adapters.drivers.hooks import carpaccio_intercept as ci


_JUSTIFICATION = "off-by-one in _resolve_head_sha; regression test test_resolve_head_sha_returns_head"


def _spawn_args(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch des_spawn in the intercept module; return the recorded positional args."""
    recorded: dict[str, tuple] = {}

    def fake_spawn(*args, **kwargs):
        recorded["args"] = args
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = '{"event": "ReadinessVerified", "verdict": "cleared"}'
        return completed

    monkeypatch.setattr(ci, "des_spawn", fake_spawn)
    return recorded  # type: ignore[return-value]


def test_readiness_runner_threads_lane_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A readiness runner built WITH a bugfix lane passes --lane / --lane-justification."""
    recorded = _spawn_args(monkeypatch)
    runner = ci._real_readiness_runner(
        tmp_path, lane="bugfix", lane_justification=_JUSTIFICATION
    )
    runner("synthetic-feature", "slice-01")
    args = list(recorded["args"])
    assert "--lane" in args and "bugfix" in args, (
        "a readiness runner built with lane='bugfix' must pass `--lane bugfix` to the "
        f"gate subprocess. des_spawn args={args}"
    )
    assert "--lane-justification" in args and _JUSTIFICATION in args, (
        "the runner must forward the lane justification to the gate so the gate's "
        f"fail-closed anti-abuse check can run. des_spawn args={args}"
    )


def test_readiness_runner_no_lane_is_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A readiness runner built with NO lane invokes the gate without --lane (default)."""
    recorded = _spawn_args(monkeypatch)
    runner = ci._real_readiness_runner(tmp_path)
    runner("synthetic-feature", "slice-01")
    args = list(recorded["args"])
    assert "--lane" not in args, (
        "the default readiness runner (no lane) must invoke the gate byte-identically "
        f"-- no --lane arg (ADD-not-mutate). des_spawn args={args}"
    )


def test_parse_lane_from_prompt_extracts_bugfix_and_justification() -> None:
    """The intercept extracts (lane, justification) from the DES-LANE markers."""
    prompt = (
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-LANE : bugfix -->\n"
        f"<!-- DES-LANE-JUSTIFICATION : {_JUSTIFICATION} -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
    )
    lane, justification = ci._parse_lane_from_prompt(prompt)
    assert lane == "bugfix"
    assert justification == _JUSTIFICATION


def test_parse_lane_from_prompt_absent_returns_none() -> None:
    """A prompt with no DES-LANE marker yields (None, '') -- the default path."""
    prompt = "<!-- DES-MODE : atdd_pure -->\n<!-- DES-SLICE : slice-01 -->\n"
    lane, justification = ci._parse_lane_from_prompt(prompt)
    assert lane is None
    assert justification == ""


def test_intercept_threads_des_lane_into_readiness_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dormant-seam lock: the intercept THREADS the parsed lane into the builder.

    The pieces (`_parse_lane_from_prompt`, the lane-baked runner) are unit-tested
    above, but nothing pins the CONNECTION: if a future edit drops the
    `evaluate_atdd_pure_dispatch` line that feeds the parsed lane into
    `_real_readiness_runner`, the unit tests stay green while the bugfix lane
    silently stops reaching a live dispatch (the dormant-seam class). This test
    locks the thread: a DES-LANE prompt driven through the REAL intercept must
    build the DEFAULT readiness runner WITH `lane="bugfix"`. The builder is
    invoked before the gate stack runs, so capturing its kwargs is sufficient
    (the dispatch may proceed/raise afterwards on the synthetic tmp tree).
    """
    captured: dict[str, object] = {}

    def _capturing_builder(
        project_root,
        lane=None,
        lane_justification="",
        at_kind="gherkin",
        regression_test_file=None,
    ):
        captured["lane"] = lane
        captured["justification"] = lane_justification
        return lambda _fid, _slice: (0, '{"event": "ReadinessVerified"}')

    monkeypatch.setattr(ci, "_real_readiness_runner", _capturing_builder)

    prompt = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        "<!-- DES-PROJECT-ID : synthetic-feature -->\n"
        "<!-- DES-LANE : bugfix -->\n"
        f"<!-- DES-LANE-JUSTIFICATION : {_JUSTIFICATION} -->\n"
    )
    try:
        ci.evaluate_atdd_pure_dispatch(
            prompt=prompt, feature_id="synthetic-feature", project_root=tmp_path
        )
    except Exception:
        # The readiness builder is called BEFORE the gate stack runs; a downstream
        # crash on the synthetic tmp tree does not unset the capture.
        pass

    assert captured.get("lane") == "bugfix", (
        "the intercept must thread the parsed DES-LANE into the DEFAULT readiness "
        "runner builder -- if this is None the parse->builder connection was "
        f"dropped (dormant seam). captured={captured}"
    )
    assert _JUSTIFICATION in (captured.get("justification") or "")
