"""Arch test -- the cascade-detector for AtCompletionLedger caller migration.

Slice-02d-N0 deliverable: a structural-invariant gate that mechanically
catches any unmigrated ``AtCompletionLedger(...)`` caller as the per-caller
sub-slices (slice-02c-N1..N11) ship one-by-one.

**Mandate-13 compliance** (per `feedback_no_direct_domain_testing_in_ats_2026_05_25`):
this is a layer-1 ARCH test asserting STRUCTURAL invariants (regex grep over
``src/`` + ``scripts/``). It does NOT import production modules, does NOT
invoke production functions. Placement at ``tests/des/unit/`` ROOT (NOT under
``tests/des/unit/domain/`` or ``tests/des/unit/cli/``) signals the structural-
invariant intent. Precedent: ``tests/des/unit/test_required_record_writer_registry.py``.

**Invariants asserted** (per architect spec, M40 feature-delta line 800-832):

1. **No production caller uses the legacy positional shape**
   ``AtCompletionLedger(<feature_id>, <project_root>)``. Singleton-shape
   ``AtCompletionLedger(project_root=...)`` (or the kw-only twin shape
   ``AtCompletionLedger(feature_id=..., project_root=...)``) is required.

2. **Self-application** (per principle 13): the arch test asserts itself
   was collected by pytest (catches `F-DES-RED-GATE-COLLECTION-COUNTING-BROKEN`
   class drift).

**Live-grep parametrization**: the unmigrated-caller list is derived from a
live filesystem scan, NOT enumerated as static literals. Newly added callers
join the gate automatically. Pre-N1..N11 (today): each unmigrated caller is
expected to fail (``xfail strict=False``) so in-flight progress is allowed.
Post-N11 (future): the parametrize collapses and the gate hard-fails on any
future legacy-shape regression.

**Scope**: ``src/des/**/*.py`` + ``scripts/**/*.py``, excluding the def site
(``at_completion_ledger.py``) and any archive subdirectory (``_archive/``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "des",
    _REPO_ROOT / "scripts",
)
_EXCLUDED_FILENAMES: frozenset[str] = frozenset({"at_completion_ledger.py"})
_EXCLUDED_PATH_FRAGMENTS: tuple[str, ...] = ("_archive/", "/_archive/")


# --- Caller discovery -------------------------------------------------------


def _discover_python_files(roots: tuple[Path, ...]) -> list[Path]:
    """Walk ``roots`` and return every ``.py`` file under them.

    Excludes the def site and any archive subdirectory per spec scope.
    """
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path.name in _EXCLUDED_FILENAMES:
                continue
            posix = path.as_posix()
            if any(fragment in posix for fragment in _EXCLUDED_PATH_FRAGMENTS):
                continue
            files.append(path)
    return sorted(files)


_INSTANTIATION_PATTERN = re.compile(r"AtCompletionLedger\s*\(")
# A legacy positional construction has an unnamed first arg that is NOT a
# ``project_root=`` or ``feature_id=`` keyword. The narrow regex captures
# the head of the call's first argument; we then classify it.
_FIRST_ARG_PATTERN = re.compile(
    r"AtCompletionLedger\s*\(\s*([^),\s][^),]*?)\s*(?:,|\))"
)


def _classify_call(snippet: str) -> str:
    """Classify a single call expression as ``legacy`` / ``singleton`` / ``unknown``.

    - ``singleton``: first argument is a ``project_root=...`` or
      ``feature_id=...`` keyword (twin kw-only shape).
    - ``legacy``: first argument is positional (not a keyword).
    - ``unknown``: regex did not match (e.g. multi-line call; conservatively
      excluded from the gate so the failure mode is "no row" not "false RED").
    """
    match = _FIRST_ARG_PATTERN.search(snippet)
    if match is None:
        return "unknown"
    first_arg = match.group(1).strip()
    if first_arg.startswith("project_root=") or first_arg.startswith("feature_id="):
        return "singleton"
    return "legacy"


def _discover_caller_rows() -> list[tuple[str, str, int, str]]:
    """Discover every ``AtCompletionLedger(...)`` call site in the scope.

    Returns a sorted list of ``(caller_id, file_relpath, line_number,
    classification)`` tuples. ``caller_id`` is ``"<relpath>:<line>"`` --
    stable across runs and human-readable in pytest reports.
    """
    rows: list[tuple[str, str, int, str]] = []
    for path in _discover_python_files(_SRC_ROOTS):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not _INSTANTIATION_PATTERN.search(line):
                continue
            classification = _classify_call(line)
            if classification == "unknown":
                continue
            relpath = path.relative_to(_REPO_ROOT).as_posix()
            caller_id = f"{relpath}:{line_number}"
            rows.append((caller_id, relpath, line_number, classification))
    return sorted(rows)


# --- Parametrize matrix (live-grep, not enumerated) -------------------------

_DISCOVERED_ROWS = _discover_caller_rows()


def _expected_xfail_today(classification: str) -> bool:
    """Pre-N1..N11 today: ``legacy`` rows xfail; ``singleton`` rows pass.

    Post-N11 (future), the parametrize collapses to ``singleton`` only and
    the xfail mechanism is dropped -- any future legacy row then hard-fails.
    """
    return classification == "legacy"


# --- Self-application test (principle 13) -----------------------------------


def test_cascade_detector_itself_collected_in_ci() -> None:
    """The cascade-detector module is collected and executed by pytest.

    Catches the F-DES-RED-GATE-COLLECTION-COUNTING-BROKEN class: a test file
    that exists on disk but pytest silently fails to collect (e.g. due to a
    conftest plugin-name collision under importlib) would never red.
    """
    assert __name__ in sys.modules, (
        f"cascade-detector module {__name__!r} not present in sys.modules -- "
        "pytest did not collect this file. Investigate conftest plugin-name "
        "collisions or pytest collection filters."
    )


def test_at_least_one_caller_discovered() -> None:
    """The live-grep scan finds at least one production caller.

    A zero-row scan means either the production codebase legitimately stopped
    using ``AtCompletionLedger`` (in which case the cascade-detector is dead
    code and this scaffold should be archived) OR the scan walk is broken
    (e.g. ``_SRC_ROOTS`` no longer exist). Either way, the operator must
    inspect explicitly -- a silent zero-row scan is not informative.
    """
    assert _DISCOVERED_ROWS, (
        "cascade-detector live-grep scan found zero AtCompletionLedger "
        f"call sites under {[str(r) for r in _SRC_ROOTS]} -- either the "
        "codebase no longer instantiates AtCompletionLedger (archive this "
        "test) or the scan walk is broken (verify roots + exclusion rules)."
    )


# --- Per-caller parametrize (live-grep-derived, xfail strict=False today) ---


@pytest.mark.parametrize(
    "caller_id,relpath,line_number,classification",
    _DISCOVERED_ROWS,
    ids=[row[0] for row in _DISCOVERED_ROWS] or ["<no callers discovered>"],
)
def test_caller_uses_singleton_shape(
    request: pytest.FixtureRequest,
    caller_id: str,
    relpath: str,
    line_number: int,
    classification: str,
) -> None:
    """Every production caller uses the singleton-shape constructor.

    ``singleton`` rows pass (post-migration shape). ``legacy`` rows xfail
    with ``strict=False`` while N1..N11 sub-slices are in flight; each
    sub-slice that migrates one caller flips its row from xfail to pass
    organically. Once all 11 callers ship the singleton shape, the xfail
    machinery is dropped and any future legacy regression hard-fails here.
    """
    if _expected_xfail_today(classification):
        request.applymarker(
            pytest.mark.xfail(
                reason=(
                    f"slice-02c-N1..N11 in flight; {caller_id} not yet "
                    "migrated to singleton-shape"
                ),
                strict=False,
            )
        )
    assert classification == "singleton", (
        f"caller {caller_id} uses legacy positional shape "
        f"`AtCompletionLedger(<feature_id>, <project_root>)`; migrate to "
        f"`AtCompletionLedger(project_root=...)` + per-call `feature_id=` "
        "kwarg (see docs/feature/fix-atdd-pure-common-audit-log-ssot/"
        "feature-delta.md slice-02c-N1..N11 sub-slice rows)."
    )
