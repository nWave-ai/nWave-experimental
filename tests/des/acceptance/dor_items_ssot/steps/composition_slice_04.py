"""Composition root for dor-items-ssot slice-04 (the DoR-home drift gate).

slice-04 (the FINAL slice) ships the **drift gate**: a maintainer who edits any
Definition-of-Ready home is mechanically stopped when a home's item-list diverges
from the one authoritative place (DISCUSS K2/K3 / DESIGN DDD-5). The gate is the
dev/CI check ``scripts/cli/check_dor_items_drift.py`` (CREATE_NEW per the DESIGN
component table) -- a pure functional core + thin CLI shell, the same shape as
``validate_feature_delta.py`` (closed verdict tokens, ``--format json``, exit-0
on PASS).

ONE driving surface, no test doubles (Pillar 3, Mandate 9/11 example-only): the
REAL ``scripts/cli/check_dor_items_drift.py`` standalone, driven as a subprocess
(Layer 3 subprocess, Mandate-13 driving-port-only -- the SAME driving-surface
class slices 01-03 established with ``read_dor_items.py``). The composition NEVER
imports the gate / its ``main`` and calls it at the step boundary (that would
collapse the leg into a Layer-1 unit test, forbidden by Mandate-13 / S2): the
only entry is the real subprocess.

The gate's DRIVING SURFACE the GREEN must expose (pinned here so the AT can drive
a read-only universe without mutating the real repo homes -- Mandate 8):

    python scripts/cli/check_dor_items_drift.py [--ssot <path>]
                                                [--home <path> ...]
                                                [--format json]

  --ssot <path>   the authoritative SSOT YAML (default the real
                  ``nWave/data/dor-items.yaml``); the gate reads its
                  ``items:`` block-sequence and measures each home against
                  ``len(items)``.
  --home <path>   a DoR home markdown file to drift-check (REPEATABLE). When
                  one or more --home flags are given the gate checks exactly
                  those; when none are given it defaults to the REAL enumerated
                  home-set (the consistent-state AT relies on this default).
  --format json   emit the structured closed-token verdict object to stdout:
                  {"verdict": "PASS"|"FAIL"|"MALFORMED",
                   "diverged_homes": [...home paths...],
                   "checked_homes": [...home paths the gate actually traversed...],
                   "ssot_item_count": <int>}

  exit 0 = PASS (all homes consistent) | 1 = FAIL (>=1 diverged) | 2 = MALFORMED.

The ``checked_homes`` field is the discovery-coverage observable (AT-review
dimension-5 fix): the consistent-state AT asserts the gate's DEFAULT discovery
set TRAVERSED all canonical homes, so an under-discovering GREEN -- one that
silently inspects fewer homes than exist -- fails the AT (its ``checked_homes``
would be missing a required home) instead of vacuously passing on an empty
``diverged_homes``. The GREEN gate MUST therefore emit ``checked_homes``.

Because the divergent-home AT points ``--home`` at a TMP FIXTURE file (a home
that enumerates 8 items vs the SSOT's 9), it never mutates the real repo homes --
the universe stays read-only. The consistent-state AT runs the gate against the
REAL reconciled tree (no --home / --ssot override) asserting PASS / exit-0.

WHY THIS RED-fails for the RIGHT reason (MISSING_FUNCTIONALITY, never BROKEN):
``scripts/cli/check_dor_items_drift.py`` does not exist yet, so the subprocess
exits non-zero (a Python "can't open file" / "No such file or directory" on
stderr) and prints NO JSON object on stdout. The parser therefore surfaces a
``DriftReport`` with the sentinel ``MALFORMED`` verdict + the subprocess's
non-zero exit code -- and each Then asserts the GREEN-state opposite (PASS/exit-0
on the consistent tree; FAIL/exit-1 + the named diverged home on the divergent
fixture; the structured token shape under --format json). The composition imports
only test-local types + stdlib (``json`` / ``subprocess`` / ``os`` / ``sys``), so
the suite COLLECTS cleanly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.cli import check_dor_items_drift
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_04 import (
    DRIFT_VERDICT_FAIL,
    DRIFT_VERDICT_MALFORMED,
    DRIFT_VERDICT_PASS,
    DriftReport,
)


# THIS file lives at
# tests/des/acceptance/dor_items_ssot/steps/composition_slice_04.py -> 5 parents
# up is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The closed verdict-token set the gate's stdout may carry. Anything else (or a
# missing JSON object) is treated as the MALFORMED sentinel -- the today's-RED
# state, where the gate file does not exist and prints no JSON.
_KNOWN_VERDICTS: frozenset[str] = frozenset(
    {DRIFT_VERDICT_PASS, DRIFT_VERDICT_FAIL, DRIFT_VERDICT_MALFORMED}
)


class DorItemsDriftGateComposition:
    """Production composition root over the real drift-gate standalone.

    Drives ``scripts/cli/check_dor_items_drift.py`` as a subprocess (the only
    entry) and parses its ``--format json`` stdout + exit code into the
    port-exposed ``DriftReport``. Two scenario-shaped surfaces:

      * ``check_real_homes()``        -- run against the REAL reconciled tree
                                         (no overrides); the consistent-state AT.
      * ``check_homes(ssot, homes)``  -- run against an injected SSOT + an
                                         explicit home-set (a tmp divergent
                                         fixture); the drift-caught AT. Read-only:
                                         the gate inspects the given paths, never
                                         writes them.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _REPO_ROOT

    # --- scenario-shaped driving surfaces -----------------------------------

    def check_real_homes(self) -> DriftReport:
        """Drive the gate over the REAL reconciled tree (default home-set + SSOT).

        Layer 3 subprocess (Mandate-13): no --home / --ssot override, so the gate
        drift-checks its real enumerated home-set against the real SSOT. On the
        slice-04 GREEN baseline (homes reconciled to 9) this is PASS / exit-0.
        """
        completed = self._run_gate(["--format", "json"])
        return _parse_drift_report(completed.stdout, completed.returncode)

    def check_homes(self, ssot_path: Path, home_paths: tuple[Path, ...]) -> DriftReport:
        """Drive the gate over an injected SSOT + explicit home-set (read-only).

        Layer 3 subprocess (Mandate-13): the divergent-home AT points --home at a
        TMP FIXTURE (a home enumerating 8 vs the SSOT's 9) so the real repo homes
        are never mutated -- the universe stays read-only (Mandate 8). On GREEN
        this is FAIL / exit-1 with the fixture home named in ``diverged_homes``.
        """
        argv = ["--ssot", str(ssot_path)]
        for home_path in home_paths:
            argv.extend(["--home", str(home_path)])
        argv.extend(["--format", "json"])
        completed = self._run_gate(argv)
        return _parse_drift_report(completed.stdout, completed.returncode)

    # --- internals ----------------------------------------------------------

    def _run_gate(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        exit_code, stdout, stderr = run_cli_in_process(
            argv,
            cwd=self._repo_root,
            main=check_dor_items_drift.main,
        )
        return subprocess.CompletedProcess(
            args=argv, returncode=exit_code, stdout=stdout, stderr=stderr
        )


# --- pure parsers -----------------------------------------------------------
# Each composition method is a single delegation (Mandate-12 criterion 3); the
# parsing logic is the single source of truth, kept out of step bodies.


def _parse_drift_report(stdout: str, returncode: int) -> DriftReport:
    """Parse the gate's ``--format json`` stdout + exit code into a DriftReport.

    Tolerates leading diagnostic lines the gate subprocess may emit before the
    JSON object (Mandate-13 driving-port-only: we read what the real subprocess
    prints, we never reach into the gate). When no well-formed verdict object is
    found (today's RED state: the gate file does not exist, prints no JSON), the
    report carries the MALFORMED sentinel verdict + the subprocess's exit code.
    """
    payload = _extract_json_object(stdout)
    if payload is None:
        return DriftReport(
            verdict=DRIFT_VERDICT_MALFORMED,
            diverged_homes=(),
            checked_homes=(),
            ssot_item_count=0,
            exit_code=returncode,
        )
    verdict = str(payload.get("verdict", DRIFT_VERDICT_MALFORMED))
    if verdict not in _KNOWN_VERDICTS:
        verdict = DRIFT_VERDICT_MALFORMED
    diverged_homes = _string_tuple(payload.get("diverged_homes"))
    checked_homes = _string_tuple(payload.get("checked_homes"))
    raw_count = payload.get("ssot_item_count", 0)
    ssot_item_count = raw_count if isinstance(raw_count, int) else 0
    return DriftReport(
        verdict=verdict,
        diverged_homes=diverged_homes,
        checked_homes=checked_homes,
        ssot_item_count=ssot_item_count,
        exit_code=returncode,
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    """Coerce a JSON list field into a tuple of strings (empty when absent)."""
    if isinstance(value, list):
        return tuple(str(entry) for entry in value)
    return ()


def _extract_json_object(stdout: str) -> dict | None:
    """Return the first JSON object carrying a ``verdict`` key found in stdout.

    Scans the whole string then each line (the gate may prefix diagnostic lines
    before the JSON payload). Mandate-13 driving-port-only: we read what the real
    subprocess prints, we never reach into the gate.
    """
    for candidate in (stdout, *stdout.splitlines()):
        candidate = candidate.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and "verdict" in payload:
            return payload
    return None


__all__ = [
    "DorItemsDriftGateComposition",
]
