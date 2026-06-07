"""Composition root for slice-01 -- the `scripts/cli` canonical-set reader.

slice-01 of dor-items-ssot (the walking-skeleton): a reviewer reads the
canonical Definition-of-Ready item-set from ONE authoritative place and sees
all nine items, including Item 9 (Outcome-KPIs) -- closing the live hole where
the loaded 8-item skill silently drops the Outcome-KPIs hard gate (AD-55).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION driving port -- the real `scripts/cli/read_dor_items.py` standalone
reader invoked end-to-end as a subprocess (Layer 3 subprocess, the same
driving surface as its `scripts/cli/` siblings `check_reuse_first_design.py` /
`verify_coverage_map.py`: hook-invocable, stdlib-only, NO `des` gate-catalog
coupling). DESIGN D-2 mandates "static data read by plain Python, NO engine,
OSS hooks-only" -- it never mandated a `des` subcommand, and cataloguing a
READER as a `des` GATE would mis-model it (the `des` `_REGISTRY` is reserved
for catalogued gates). The composition NEVER imports the reader's `main` and
calls it at the step boundary, and NEVER imports any `load_dor_items` pure
function directly (that would collapse the AT into a Layer-1 unit test --
forbidden by Mandate-13 / S2). The only entry is the real subprocess, exactly
as an operator/reviewer or hook invokes the standalone.

There are no test doubles: the `nWave/data/dor-items.yaml` SSOT is real
repo-tracked data and the `scripts/cli/read_dor_items.py` reader is real I/O --
a layer-3 `@real-io` surface (Mandate 9/11: example-only, no PBT machinery; the
9-item domain is a fixed closed contract anyway -> pinned literal, not PBT).

Why this RED-fails for the RIGHT reason (MISSING_FUNCTIONALITY, never BROKEN):
`scripts/cli/read_dor_items.py` does not yet exist AND
`nWave/data/dor-items.yaml` does not yet exist, so the subprocess errors (a
missing-script non-zero exit) and emits NO item lines. The reader of the
observable (`read_canonical_set`) therefore surfaces an EMPTY set, and each
Then asserts a missing item / count / hard-gate -- a semantic `AssertionError`,
never a collection / import / setup error. The composition imports only
test-local types + stdlib subprocess, so the suite COLLECTS cleanly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .domain_types import CanonicalReadinessSet, ReadinessItem


# THIS file lives at
# tests/des/acceptance/dor_items_ssot/steps/composition.py -> 5 parents up is
# the repo root. The reader subprocess is launched with cwd=repo_root so it
# resolves `nWave/data/dor-items.yaml` from the real tracked tree (the SSOT is
# repo-tracked data, not a per-test tmp fixture).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REPO_SRC = _REPO_ROOT / "src"

# The production driving port the crafter must implement: a `scripts/cli/`
# standalone reader (the `check_reuse_first_design.py` / `verify_coverage_map.py`
# precedent -- stdlib-only, hook-invocable, NO `des` gate-catalog coupling).
_READER_RELPATH = "scripts/cli/read_dor_items.py"


class CanonicalSetReaderComposition:
    """Production-wired composition root for the `scripts/cli` reader slice.

    The driving port is the real `scripts/cli/read_dor_items.py` standalone
    invoked as a subprocess; the observable surface is the canonical readiness
    set the reader prints (the enumerated items + the separately listed hard
    gates) and the unchanged authoritative place.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _REPO_ROOT
        self._ssot_path = self._repo_root / "nWave" / "data" / "dor-items.yaml"

    # --- driving-port invocation --------------------------------------------

    def read_canonical_set(self) -> CanonicalReadinessSet:
        """Invoke the REAL `scripts/cli/read_dor_items.py` and parse its output.

        The reader is asked for a machine-readable listing (`--format json`)
        of the canonical item-set so the test observes the items + hard gates
        the reviewer sees. A non-zero exit (missing script today, or a
        malformed SSOT once the reader exists) surfaces as an EMPTY set -- the
        Then steps then RED-fail on the missing items / count / hard-gate.
        """
        completed = self._run_reader(["--format", "json"])
        return self._parse_set(completed.stdout, completed.returncode)

    def authoritative_place_digest(self) -> str | None:
        """A content digest of the authoritative SSOT file, or None if absent.

        Used to assert the read leaves the authoritative place unchanged
        (`@contract-shape:unbounded-preservation`): a read MUST NOT mutate the
        SSOT. None today (the SSOT does not exist yet) -- once it exists, the
        digest before and after the read must be identical.
        """
        if not self._ssot_path.is_file():
            return None
        import hashlib

        return hashlib.sha256(self._ssot_path.read_bytes()).hexdigest()

    # --- internals ----------------------------------------------------------

    def _run_reader(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Invoke the real `scripts/cli/read_dor_items.py` standalone reader.

        A missing script today (pre-implementation) yields a non-zero exit and
        empty stdout -- the honest MISSING_FUNCTIONALITY observable, surfaced as
        the EMPTY set by `_parse_set`, never a raised setup error.
        """
        return subprocess.run(
            [sys.executable, _READER_RELPATH, *argv],
            capture_output=True,
            text=True,
            cwd=str(self._repo_root),
            env=_subprocess_env(),
        )

    @staticmethod
    def _parse_set(stdout: str, returncode: int) -> CanonicalReadinessSet:
        """Parse the reader's JSON listing into the observable domain shape.

        A non-zero exit or unparseable output yields the EMPTY set -- the
        honest observable when the subcommand / SSOT does not yet exist
        (MISSING_FUNCTIONALITY), never a raised setup error.
        """
        if returncode != 0:
            return CanonicalReadinessSet(items=(), separate_hard_gates=())
        try:
            payload = json.loads(stdout)
        except (ValueError, TypeError):
            return CanonicalReadinessSet(items=(), separate_hard_gates=())
        item_names = payload.get("items", []) if isinstance(payload, dict) else []
        hard_gates = payload.get("hard_gates", []) if isinstance(payload, dict) else []
        return CanonicalReadinessSet(
            items=tuple(ReadinessItem(name=str(name)) for name in item_names),
            separate_hard_gates=tuple(str(gate) for gate in hard_gates),
        )


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    # ABSOLUTE repo-`src/` path so the subprocess imports `des` regardless of
    # cwd (mirrors the oss-feature-end-emit-cli composition env-parity shape).
    env["PYTHONPATH"] = str(_REPO_SRC)
    return env


__all__ = [
    "CanonicalSetReaderComposition",
]
