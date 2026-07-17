"""Regression: `des` freshness REFUSE (exit 78) is JSON-only on stderr, with
no paired human-readable what/why/how line, and its remediation is a single
hardcoded "reinstall" string wrong for the dev-editable-binary-from-a-non-
project-cwd case (F-fix-des-silent-config-failure).

RCA: `docs/feature/fix-des-silent-config-failure/deliver/rca.md`. The
reported "exit 78, ZERO output" does NOT reproduce -- `_refuse()`
(`src/des/runtime/freshness.py:72-82`) ALWAYS emits a JSON event on stderr
before `sys.exit(78)`. The REAL defect is a house-style drift (GDP-3):

  (A) the refusal is JSON-ONLY -- no paired human "⚠ WHAT -- WHY. Fix: HOW"
      line, unlike every other des gate refusal (contrast:
      `src/des/cli/verify_negative_at.py:150-160` `_indeterminate()` pairs
      its `NegativeAtIndeterminate` JSON event with exactly such a line).
  (B) the remediation is the single hardcoded `_REMEDIATION` constant
      (`freshness.py:69`, "python scripts/install/install_nwave.py") used
      for EVERY refuse cause -- misleading for the dev-editable-binary
      topology (manifest absent because the editable install has no
      manifest at all; nothing to "reinstall" -- the real fix is "run from
      a project/source checkout").

Bug observable (feature-delta `[REF] Value`): a freshness refusal must give
an actionable human-readable what/why/how line (not JSON alone) AND a
remediation that fits the actual cause; exit code + the JSON event + the
success/silent-proceed path unchanged.

Driving surface: `des.runtime.freshness.assert_fresh_or_explain` -- the
composition-root function `des/cli/__init__.py:15-18` calls at import time.
Triggered in-process via its documented `probe` injection seam (a legitimate
part of the function's public signature, mirroring the installer-side
freshness ATs' seam use) + `NWAVE_FRESHNESS_FORCE_GATE=1` (the documented
test-only bypass of the `.git`-adjacency autoskip, `freshness.py:50-61`) so
the four-state classifier runs deterministically regardless of this
repo-checkout's own `.git` adjacency -- no subprocess, no real filesystem
manifest needed.

@contract-shape:bounded-change -- the refuse path (JSON payload) gains a
paired human stderr line + a cause-appropriate remediation string; exit code
and the JSON event's presence/shape are UNCHANGED (pinned as regression
oracles alongside the two active-RED oracles).
"""

from __future__ import annotations

import json

import pytest

from des.ports.driven_ports.freshness_port import FreshnessVerdict
from des.runtime.freshness import assert_fresh_or_explain


class _FakeProbe:
    """Test-only `FreshnessProbe` -- returns a pre-built verdict.

    Duck-types the `FreshnessProbe` Protocol (`.probe() -> FreshnessVerdict`)
    via the function's own documented `probe` injection seam -- no monkeypatch
    of `RepoSourceProbe` internals, no synthetic install tree on disk.
    """

    def __init__(self, verdict: FreshnessVerdict) -> None:
        self._verdict = verdict

    def probe(self) -> FreshnessVerdict:
        return self._verdict


#: The exact DEGRADED reason `RepoSourceProbe._load_and_validate_manifest`
#: returns for the dev-editable-binary-from-a-non-project-cwd topology (RCA
#: root-cause B): `_INSTALLED_PACKAGE_ROOT` resolves to the repo's own
#: `src/des` for an editable install, which never carries
#: `_install_manifest.json` -- always DEGRADED, "no install manifest".
_EDITABLE_NO_MANIFEST_VERDICT = FreshnessVerdict(
    state="DEGRADED",
    reason="no install manifest — reinstall required",
)

#: A silent-proceed verdict (customer install, source tree not reachable) --
#: the state-A path the RCA's Risk clause pins as untouched (RCA line 35-36).
_CUSTOMER_SILENT_PROCEED_VERDICT = FreshnessVerdict(
    state="A",
    reason="customer install — source tree not reachable",
)


def _invoke_and_capture_refusal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    verdict: FreshnessVerdict,
) -> tuple[int, str]:
    """Force the four-state classifier to run against `verdict`, capture the
    `SystemExit` code + everything printed to stderr.

    `NWAVE_FRESHNESS_FORCE_GATE=1` bypasses the `.git`-adjacency autoskip
    (documented test-only seam, `freshness.py:50-61`) so this repo checkout's
    own `.git/` does not short-circuit the classifier before it reaches the
    injected probe. `NWAVE_FRESHNESS` (the operator opt-out) is cleared so it
    cannot pre-empt the classifier either.
    """
    monkeypatch.setenv("NWAVE_FRESHNESS_FORCE_GATE", "1")
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        assert_fresh_or_explain(probe=_FakeProbe(verdict))
    captured = capsys.readouterr()
    return exc_info.value.code, captured.err


def _first_freshness_json_payload(stderr_text: str) -> dict[str, object]:
    """Extract the first parseable JSON line whose `event` is a freshness
    event. Mirrors the existing `parse_structured_event_line` idiom
    (`tests/installer/acceptance/fix-des-self-hosted-gate-sync/conftest.py:
    554-575`) -- non-JSON lines (the human `⚠` line this fix adds) are
    silently skipped, exactly the parser robustness the RCA's Risk clause
    verifies. Returns `{}` when no such line is present.
    """
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = payload.get("event")
        if isinstance(event, str) and event.startswith("des.runtime.freshness."):
            return payload
    return {}


# ---------------------------------------------------------------------------
# Oracle A -- human-readable line. ACTIVE-RED today: `_refuse()` emits JSON
# only; no "⚠ ..." line is ever printed alongside it.
# ---------------------------------------------------------------------------


def test_refuse_prints_human_readable_line_alongside_the_json_event(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A freshness REFUSE must pair its JSON event with a human-readable
    "⚠ WHAT -- WHY. Fix: HOW" line on stderr -- mirroring the
    `NegativeAtIndeterminate` pairing already established elsewhere in the
    codebase (`src/des/cli/verify_negative_at.py:150-160`).

    ACTIVE-RED today: `_refuse()` (`freshness.py:72-82`) calls `_emit_event`
    (JSON only) then `sys.exit(78)` -- no human line is ever printed. This
    assertion fails for the diagnosed business reason (no "⚠" line found),
    never an import/collection error.
    """
    exit_code, stderr_text = _invoke_and_capture_refusal(
        monkeypatch, capsys, _EDITABLE_NO_MANIFEST_VERDICT
    )

    # Pin (unchanged by the fix): exit code stays 78.
    assert exit_code == 78, (
        f"freshness REFUSE must keep exit code 78 (EX_CONFIG) unchanged by "
        f"this fix; got exit_code={exit_code}"
    )
    # Pin (unchanged by the fix): the JSON event is STILL emitted.
    payload = _first_freshness_json_payload(stderr_text)
    assert payload.get("event") == "des.runtime.freshness.refused", (
        f"the structured JSON refusal event must still be emitted on stderr "
        f"(not removed by this fix); got stderr={stderr_text!r}"
    )

    human_lines = [ln for ln in stderr_text.splitlines() if ln.strip().startswith("⚠")]
    assert human_lines, (
        "WHAT: no human-readable '⚠ WHAT -- WHY. Fix: HOW' line found on "
        "stderr alongside the JSON refusal event. "
        "WHY: `_refuse()` (src/des/runtime/freshness.py:72-82) prints only "
        "the structured JSON event -- a developer glancing at the terminal "
        "sees nothing (RCA fix-des-silent-config-failure, root cause A). "
        "HOW: pair the JSON event with a human line, mirroring "
        "`_indeterminate()` in src/des/cli/verify_negative_at.py:150-160 "
        f"('print(f\"⚠ {{what}} — {{why}}. Fix: {{how}}\")'). "
        f"got stderr={stderr_text!r}"
    )


# ---------------------------------------------------------------------------
# Oracle B -- cause-appropriate remediation. ACTIVE-RED today: `_REMEDIATION`
# is one hardcoded "reinstall" string used for every refuse cause.
# ---------------------------------------------------------------------------


def test_refuse_remediation_is_not_the_blanket_reinstall_string_for_editable_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """For the dev-editable-binary-from-a-non-project-cwd cause (manifest
    absent because the editable install never carries one), the remediation
    must NOT be the blanket "reinstall" wording -- there is nothing to
    reinstall. It must point the developer at the actual fix: run from a
    project/source checkout.

    ACTIVE-RED today: `_REMEDIATION` (`freshness.py:69`) is a single
    hardcoded "python scripts/install/install_nwave.py" string used for
    EVERY refuse, regardless of cause (RCA root cause B). This assertion
    fails for the diagnosed business reason (the misleading remediation
    string is present), never an import/collection error.
    """
    _exit_code, stderr_text = _invoke_and_capture_refusal(
        monkeypatch, capsys, _EDITABLE_NO_MANIFEST_VERDICT
    )

    payload = _first_freshness_json_payload(stderr_text)
    remediation = str(payload.get("remediation", ""))

    assert "install_nwave.py" not in remediation, (
        "WHAT: the editable-binary-from-non-project-cwd refusal's "
        f"remediation is the blanket reinstall string ({remediation!r}). "
        "WHY: `_REMEDIATION` (src/des/runtime/freshness.py:69) is a single "
        "hardcoded string used for every refuse cause -- there is nothing "
        "to reinstall for a dev-editable install with no manifest because "
        "it was invoked from a directory with no project (RCA root cause B). "
        "HOW: give `FreshnessVerdict` a remediation channel supplied by "
        "`RepoSourceProbe` per branch, so this cause reports 'run from a "
        "project directory or the nWave source checkout' instead. "
        f"got remediation={remediation!r}"
    )
    assert "project" in remediation.lower() or "checkout" in remediation.lower(), (
        "WHAT: the editable-binary-from-non-project-cwd remediation does "
        "not name a project/source checkout. "
        "WHY: the blanket 'reinstall' remediation is cause-inappropriate "
        "here (RCA root cause B). "
        "HOW: supply a per-branch remediation on `FreshnessVerdict` naming "
        "'run from a project directory or the nWave source checkout'. "
        f"got remediation={remediation!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT -- the state-A silent-proceed path must stay silent. Pins the
# RCA's Risk clause: "the state-A SILENT-PROCEED path ... stays SILENT -- no
# new ⚠ line added there". GREEN today and after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_success_path_never_gains_a_noisy_human_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative AT: pairing the JSON refusal with a human `⚠` line must NOT
    leak a `⚠` line (or any stderr output) onto the state-A silent-proceed
    path (a fresh/healthy customer-install runtime) -- the wrong outcome
    (noise on success) must NOT be produced.

    RCA Risk clause: "a second human print() line is safe ... Additive print
    changes neither exit code nor flow" -- but the additive print belongs
    ONLY inside `_refuse()`; the state-A branch in `assert_fresh_or_explain`
    must remain a silent no-op untouched by this fix.
    """
    monkeypatch.setenv("NWAVE_FRESHNESS_FORCE_GATE", "1")
    monkeypatch.delenv("NWAVE_FRESHNESS", raising=False)

    assert_fresh_or_explain(probe=_FakeProbe(_CUSTOMER_SILENT_PROCEED_VERDICT))

    captured = capsys.readouterr()
    assert captured.err == "", (
        "the wrong outcome under test: state-A (customer install, silent "
        "PROCEED) must emit ZERO stderr output -- any '⚠' line or JSON "
        "event here would be new noise on the success path introduced by "
        f"this fix, which must touch ONLY the REFUSE path. got "
        f"stderr={captured.err!r}"
    )
