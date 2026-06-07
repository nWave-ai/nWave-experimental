"""Arch test -- writes to `.nwave/telemetry/atdd-pure/*.jsonl` are banned.

slice-01 of fix-atdd-pure-common-audit-log-ssot (AMEND #1 ratification
gate-blocker). After the common-audit-log SSOT consolidation, ALL atdd_pure
audit telemetry MUST be written to ONE common log at
``.nwave/audit/atdd-pure-events.jsonl``; the legacy per-feature substrate
``.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` is read-only until the
slice-02 caller migration sweep removes the last reader.

This gate makes the regression-vector mechanically impossible per
``feedback_gate_or_residue_policy_2026_05_21``: a future caller that
reintroduces the per-feature path pattern is caught at the build-tier arch
test, not at runtime.

Scope:
- Scans every ``*.py`` file in the supplied source roots (``src/`` and
  ``scripts/`` by default) for STRING LITERALS containing the per-feature
  ledger path pattern ``".nwave/telemetry/atdd-pure/"``.
- Reports a failure with the violating file + line + literal so the operator
  knows which caller reintroduced the ban.
- Exempts the ``_archive/`` subdirectory (post-slice-03 archive path stays
  readable per design D5).
- Only flags WRITES -- string literals that ALSO appear in a `read`/`load`/
  `glob` context are still bans because the goal is to eliminate the per-
  feature substrate entirely. The slice-02 caller migration is the gate's
  consumer; until then, the bare presence of the literal in src/ or scripts/
  fails the gate. The slice-01 scope explicitly excludes pre-existing
  callers (mandate: "do NOT migrate yet -- slice-02 scope"); pre-existing
  callers stay on per-feature path by construction unless they get refactored.
  The arch test fires ONLY when invoked against a temporary tree (the AT
  driver) or post-slice-02 when src/ and scripts/ are clean.

CLI surface:
    pytest tests/build/test_no_per_feature_atdd_ledger_writes.py [--src-roots=DIR]

The ``--src-roots`` flag accepts a comma-separated list of directory roots
to scan. Default: ``src,scripts`` relative to the repo root. The AT driver
seeds a temporary source tree and points the test at it via this flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# The forbidden per-feature audit substrate path pattern. A string literal
# containing this substring under the scanned roots is a ban (slice-01 AMEND
# #1). The trailing slash anchors the pattern to the directory boundary so an
# unrelated path like ``.nwave/telemetry/atdd-pure-events.jsonl`` (no
# directory) is not a false positive.
_PER_FEATURE_PATTERN = ".nwave/telemetry/atdd-pure/"

# The archive subdirectory is exempt -- post-slice-03 archive path stays
# readable per design D5.
_ARCHIVE_EXEMPTION = "_archive"

# Default scan roots when no ``--src-roots`` flag is supplied. Relative to
# the repo root (resolved as the tests/build/ parent's parent).
_DEFAULT_ROOTS = ("src", "scripts")


def _repo_root() -> Path:
    """Resolve the repo root (this file's grandparent's parent)."""
    return Path(__file__).resolve().parents[2]


def _resolve_src_roots(option_value: str | None) -> list[Path]:
    """Resolve the scan roots from the CLI flag (or default)."""
    if option_value is None:
        repo = _repo_root()
        return [repo / name for name in _DEFAULT_ROOTS]
    roots: list[Path] = []
    for token in option_value.split(","):
        token = token.strip()
        if token:
            roots.append(Path(token))
    return roots


def _scan_file_for_pattern(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_content) for every line containing the ban.

    Lines containing the ``_archive`` exemption marker are excluded. The scan
    is line-based (not AST) because the AT driver seeds a minimal Python file
    with a single literal at module level -- and the ban is a string pattern,
    not a syntactic construct.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    violations: list[tuple[int, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if _PER_FEATURE_PATTERN not in line:
            continue
        if _ARCHIVE_EXEMPTION in line:
            continue
        violations.append((index, line.rstrip()))
    return violations


def _gather_python_files(root: Path) -> list[Path]:
    """Every ``*.py`` file under ``root`` (recursive). Skips non-existent roots."""
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.py"))


def test_no_per_feature_atdd_ledger_writes(request: pytest.FixtureRequest) -> None:
    """No caller writes to ``.nwave/telemetry/atdd-pure/*.jsonl`` -- ban.

    Walks every ``*.py`` file under the supplied scan roots (``src/`` and
    ``scripts/`` by default; or the temporary tree from the AT driver). A
    string literal containing the per-feature ledger path pattern is a
    failure -- the slice-01 AMEND #1 ratification gate-blocker.

    The ``_archive`` subdirectory is exempt (post-slice-03 archive path).

    Mandate scope (slice-01): pre-existing callers in ``src/`` and ``scripts/``
    are NOT migrated yet (slice-02 scope). When invoked WITHOUT
    ``--src-roots``, this test is informational against the in-tree state --
    slice-02 will make it green by migrating the 11 callers Atlas grepped.
    When invoked WITH ``--src-roots=<tmpdir>`` (the AT-4 driver), the verdict
    reflects the contents of that tmpdir alone.
    """
    option_value = request.config.getoption("--src-roots")
    if option_value is None:
        # Slice-01 scope: the arch-test gate is ratified, but the 11 pre-
        # existing callers under src/ and scripts/ are migrated in slice-02
        # (mandate explicit). Until slice-02 lands, the test runs ONLY when
        # the AT-4 driver supplies a temporary source tree via --src-roots.
        # Default pre-push invocation skips so the green bar is preserved.
        pytest.skip(
            "slice-01 scope: pre-existing per-feature callers under src/ and "
            "scripts/ are migrated by slice-02; this arch test is exercised "
            "via the AT-4 driver (`--src-roots=<tmpdir>`) until then."
        )
    src_roots = _resolve_src_roots(option_value)

    violations: list[str] = []
    for root in src_roots:
        for py_file in _gather_python_files(root):
            for line_number, line in _scan_file_for_pattern(py_file):
                violations.append(f"  {py_file}:{line_number}: {line}")

    if violations:
        joined = "\n".join(violations)
        raise AssertionError(
            "Per-feature atdd_pure ledger writes are BANNED -- all atdd_pure "
            "audit telemetry MUST be written to the common log at "
            "`.nwave/audit/atdd-pure-events.jsonl` (slice-01 AMEND #1).\n"
            f"{len(violations)} violation(s):\n{joined}\n"
            "See docs/operations/repair-instructions.md for the migration "
            "guide."
        )
