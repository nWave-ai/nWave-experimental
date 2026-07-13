"""Regression (#203): relative ``known_locations`` entries must resolve against
the TARGET REPO, never the process CWD.

RCA: ``docs/feature/fix-resolve-tool-repo-relative-locations/deliver/
rca-and-at-contract.md``.

Found in ``src/des/adapters/driven/runner/tool_discovery.py::resolve_tool``
rung-2: ``candidate = Path(location) / name`` resolves a RELATIVE
``known_locations`` entry (e.g. ``"node_modules/.bin"``) against the process
CWD. ``run_suite(repo)`` (``contract_gate/vitest_contract_gate_adapter.py``)
calls ``resolve_tool`` BEFORE shelling with ``cwd=repo``, so when ``des`` runs
from any CWD other than the target repo, a repo-local ``node_modules/.bin/
vitest`` is MISSED and the gate falsely reports ``RunnerAdapterUnavailable``
("vitest not found") even though the repo-local vitest exists. Effect:
TypeScript "coverage" is false-green, JS beta-lang slice-02 cannot be examined
end-to-end.

Fix direction (NOT implemented here, crafter's job): add an optional
``base_dir: Path | str | None = None`` parameter. When provided, each
RELATIVE ``known_locations`` entry resolves against ``base_dir`` instead of
CWD; ABSOLUTE entries and the PATH rung are unchanged. ``base_dir=None``
(the default) preserves EXACTLY today's CWD-relative behaviour for every
existing caller/test.

Active-RED at HEAD: ``resolve_tool`` has no ``base_dir`` parameter, so the
POSITIVE case below raises ``TypeError: resolve_tool() got an unexpected
keyword argument 'base_dir'`` -- a real, business-reason RED (the missing
parameter IS the defect), never an import/collection error.

Driving surface (Mandate-13 driving-port-only): ``resolve_tool`` IS the
driven-adapter primitive under regression (the genericità discovery scale
every language-adapter's ``probe()`` inherits) -- not domain/cli business
logic, so this bugfix-class regression AT drives it directly, mirroring the
``tests/bugs/des/test_cargo_scope_nomatch_is_indeterminate.py`` /
``tests/bugs/des/test_run_contract_gate_scope_unverified_names_how.py``
adapter-direct precedent.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from des.adapters.driven.runner.tool_discovery import resolve_tool


_TOOL_NAME = "vitest"
_KNOWN_LOCATIONS = ("node_modules/.bin",)


def _make_repo_local_tool(repo: Path, tool_name: str = _TOOL_NAME) -> Path:
    """Create an executable fake ``<repo>/node_modules/.bin/<tool_name>``."""
    bin_dir = repo / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    fake_tool = bin_dir / tool_name
    fake_tool.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(fake_tool, 0o755)
    return fake_tool


# --- POSITIVE (active-RED today: base_dir kwarg does not exist yet) --------


def test_repo_local_tool_resolves_via_base_dir_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo-local ``node_modules/.bin/vitest`` MUST resolve when
    ``base_dir=<repo>`` is passed, even though the process CWD is a
    DIFFERENT directory entirely.

    Active-RED at HEAD: ``resolve_tool`` accepts no ``base_dir`` keyword ->
    ``TypeError`` (the missing parameter IS the not-yet-implemented fix;
    once added, this becomes a real assertion on ``rung``/``path``).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    fake_tool = _make_repo_local_tool(repo)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolution = resolve_tool(_TOOL_NAME, _KNOWN_LOCATIONS, base_dir=repo)

    assert resolution.rung == "known-location", (
        "a repo-local tool passed via base_dir must resolve at the "
        f"known-location rung; got rung={resolution.rung!r}"
    )
    assert resolution.path == str(fake_tool), (
        f"expected path={str(fake_tool)!r} (resolved against base_dir), "
        f"got path={resolution.path!r}"
    )


# --- NEGATIVE (anti-recurrence witness) -------------------------------------


@pytest.mark.negative_at
def test_repo_local_tool_not_found_without_base_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SAME repo-local tool, from the SAME foreign CWD, but WITHOUT
    ``base_dir`` (omitted / ``None``) must NOT be found -- proving this test
    catches a regression that removes the ``base_dir`` threading (e.g. a
    caller that stops passing it, or an implementation that ignores it).

    This assertion is TRUE today (current CWD-relative behaviour) and MUST
    stay true after the fix -- ``base_dir=None`` never widens resolution.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_repo_local_tool(repo)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolution = resolve_tool(_TOOL_NAME, _KNOWN_LOCATIONS)

    assert resolution.path is None, (
        "without base_dir, a repo-local tool at a foreign CWD must NOT "
        f"resolve; got path={resolution.path!r}"
    )
    assert resolution.rung == "not-found"


# --- BACKWARD-COMPAT (current CWD-relative behaviour is preserved) ---------


def test_relative_location_still_resolves_against_cwd_when_base_dir_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``base_dir=None`` with CWD == repo must still resolve the relative
    location -- the exact behaviour every existing caller/test relies on
    today must be unchanged by the fix.

    Current (pre-fix) behaviour returns the CANDIDATE AS CONSTRUCTED --
    ``Path(location) / name`` -- which is itself relative (filesystem calls
    resolve it against CWD implicitly; the returned string is never made
    absolute). This pins that exact contract so the fix cannot silently
    change what existing callers receive when ``base_dir`` is omitted.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_repo_local_tool(repo)
    monkeypatch.chdir(repo)

    resolution = resolve_tool(_TOOL_NAME, _KNOWN_LOCATIONS)

    expected_relative_path = str(Path(_KNOWN_LOCATIONS[0]) / _TOOL_NAME)
    assert resolution.rung == "known-location"
    assert resolution.path == expected_relative_path
