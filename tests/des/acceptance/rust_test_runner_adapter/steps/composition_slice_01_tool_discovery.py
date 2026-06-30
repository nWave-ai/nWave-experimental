"""Composition root for f-rust-test-runner-adapter slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
production ``resolve_tool(name, known_locations)`` helper
(``src/des/adapters/driven/runner/tool_discovery.py``) imported + invoked in a
CHILD interpreter over a GENUINE controlled filesystem + PATH/HOME env. The SUT
is the shared discovery scale; the observable is the RUNG that resolved the tool
(PATH / known-location / not-found) plus, on the terminal rung, the remediation
string the INDETERMINATE result names.

WHY a child interpreter (not a thin in-process call): at HEAD
``des.adapters.driven.runner.tool_discovery`` does NOT exist (Tsunami callers-of:
0; grep tree-wide: 0). Importing it in THIS process would raise ModuleNotFoundError
at COLLECTION -> a BROKEN test, not active-RED. Running the import in a child
``python -c`` makes the absent module a CAPTURED observable (child rc != 0, no
``RESOLVED:`` marker) that each Then turns into a SEMANTIC AssertionError. This is
the same pattern the f-attest-bundled-slice slice-01 harness uses for an
absent-module probe.

REAL fixtures (no mocks -- the genuine discovery behaviour):
  - rung-1: a real executable file written into a tmp ``bin`` dir that IS on the
    child's PATH.
  - rung-2 (the WSL2 GOTCHA #1 pin -- load-bearing): a real executable file
    written into a tmp ``known-location`` dir that is NOT on the child's PATH but
    IS passed in ``known_locations``; PATH is scrubbed of the tool. resolve_tool
    must resolve via the known-location rung, NOT degrade to INDETERMINATE.
  - rung-3: the tool exists NOWHERE -- PATH scrubbed AND the known_locations dirs
    empty -- so the full scale exhausts and yields the named INDETERMINATE.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``resolve_tool`` is absent,
so the child import fails (rc != 0, no ``RESOLVED:``/``INDETERMINATE:`` marker) and
each Then fires a semantic AssertionError. GREEN once DELIVER ships
``tool_discovery.py`` with the 3-rung scale. No @skip, no collection/import error
in THIS process.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_resolve_tool import DiscoveryRung


# The production helper the in-process probe imports + invokes (the SUT).
_TOOL_DISCOVERY_MODULE = "des.adapters.driven.runner.tool_discovery"

# A synthetic tool name that is GUARANTEED absent from any real PATH (so rung-1/2
# fixtures are the ONLY way it can resolve -- no ambient host binary can satisfy
# the probe by accident, which would mask a real RED).
_TOOL_NAME = "nwave-fake-cargo-xyz"


def _resolve_tool_probe_main(argv: list[str]) -> int:
    """In-process EDGE replacing the former ``python -c`` resolve_tool probe.

    ``argv == [name, *known_locations]``. Imports the production
    ``tool_discovery`` module and calls ``resolve_tool(name, known)``, then prints
    the SAME machine-readable marker the child program printed:
      - ``RESOLVED:<path>`` when the result carries a filesystem path (rung 1/2),
      - ``INDETERMINATE:<remediation>`` when it carries a remediation (terminal).
    The result's TYPE is probed structurally (``.path`` / ``.remediation``) without
    coupling to a concrete class name; neither shape raises a LOUD ``SystemExit``
    (mapped to the exit code by ``run_cli_in_process``, faithful to the child).
    """
    import importlib

    name = argv[0]
    known = list(argv[1:])
    mod = importlib.import_module(_TOOL_DISCOVERY_MODULE)
    result = mod.resolve_tool(name, known)
    path = getattr(result, "path", None)
    remediation = getattr(result, "remediation", None)
    if path is not None:
        print("RESOLVED:" + str(path))
    elif remediation is not None:
        print("INDETERMINATE:" + str(remediation))
    else:
        raise SystemExit(
            "resolve_tool returned neither a .path (resolved) nor a "
            ".remediation (indeterminate): " + repr(result)
        )
    return 0


@dataclass
class ToolDiscoveryComposition:
    """Drives the REAL ``resolve_tool`` over a genuine controlled filesystem/env."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the controlled child env (PATH/HOME) + the known_locations passed to resolve
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # the planted tool's real on-disk path (rung-1/2) -- the expected resolution
    _planted_tool_path: str | None = field(default=None)
    # child-interpreter probe results
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + env fixtures) -----------------------------

    def given_tool_on_path(self) -> None:
        """Rung-1 fixture: the tool is a REAL executable in a dir that IS on PATH.

        Plants ``<root>/path-bin/<tool>`` (executable) and sets the child PATH to
        ONLY that dir, so ``shutil.which(name)`` resolves it on rung 1. The
        known_locations are deliberately EMPTY so this scenario can only pass via
        the PATH rung.
        """
        root = self._ensure_root()
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._planted_tool_path = str(self._plant_executable(path_bin / _TOOL_NAME))
        self._child_path = str(path_bin)
        self._known_locations = []

    def given_tool_off_path_in_known_location(self) -> None:
        """Rung-2 fixture (the WSL2 GOTCHA #1 pin -- load-bearing).

        Plants ``<root>/cargo-bin/<tool>`` (executable, the ``~/.cargo/bin``
        analogue) and:
          - sets the child PATH to an EMPTY dir (the tool is ABSENT from PATH --
            the WSL2 hook-env lie),
          - passes ``<root>/cargo-bin`` in ``known_locations``.
        resolve_tool MUST resolve via the known-location rung (rung 2) and return
        that path -- NEVER a false INDETERMINATE. This is the load-bearing
        scenario: a present toolchain outside PATH must be USED.
        """
        root = self._ensure_root()
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        cargo_bin = root / "cargo-bin"
        cargo_bin.mkdir(parents=True, exist_ok=True)
        self._planted_tool_path = str(self._plant_executable(cargo_bin / _TOOL_NAME))
        # PATH scrubbed of the tool: only an empty dir is on it.
        self._child_path = str(empty_path)
        self._known_locations = [str(cargo_bin)]

    def given_tool_absent_everywhere(self) -> None:
        """Rung-3 fixture: the tool exists NOWHERE after the full scale.

        PATH is an EMPTY dir AND the known_locations dirs are real-but-EMPTY (no
        planted executable anywhere). The full 3-rung scale exhausts, so
        resolve_tool returns the terminal INDETERMINATE naming the remediation.
        """
        root = self._ensure_root()
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        empty_known = root / "empty-known"
        empty_known.mkdir(parents=True, exist_ok=True)
        self._planted_tool_path = None
        self._child_path = str(empty_path)
        self._known_locations = [str(empty_known)]

    # ---- when (drive the REAL resolve_tool in a child interpreter) -----------

    def when_resolve_tool_is_invoked(self) -> None:
        """Invoke the REAL ``resolve_tool`` over the controlled fixture in a child.

        The child imports ``tool_discovery``, calls
        ``resolve_tool(name, known_locations)`` with the planted env, and prints a
        machine-readable marker:
          - ``RESOLVED:<path>`` when a path is returned (rung 1 or 2),
          - ``INDETERMINATE:<remediation>`` when the terminal rung is reached.
        The probe inspects the result's TYPE structurally (a resolved tool exposes
        a filesystem path; a terminal result exposes a remediation string) without
        coupling to a concrete class name the design has not frozen -- it tries the
        documented shapes and the child fails LOUD if neither holds.

        At HEAD the module is absent -> the child import raises ModuleNotFoundError
        (rc != 0, no marker), captured here as the observable.
        """
        self._probe_rc, self._probe_out, self._probe_err = self._run_resolve_probe(
            _TOOL_NAME, list(self._known_locations)
        )

    # ---- then (assert ON the discovery OUTCOME -- the port-exposed observable) -

    def then_tool_is_resolved_via(self, rung: DiscoveryRung) -> None:
        """resolve_tool resolved the tool, and to the PLANTED on-disk path.

        Used by AT-1 (rung ON_PATH) and AT-2 (rung KNOWN_LOCATION -- the WSL2 pin).
        Asserts the child returned ``RESOLVED:<path>`` AND the path is exactly the
        planted executable -- so a present-outside-PATH tool is USED via the
        known-location rung, NEVER a false INDETERMINATE.

        Active-RED at HEAD: ``tool_discovery`` is absent, the child import fails
        (rc != 0, no ``RESOLVED:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "RESOLVED:" in self._probe_out, (
            f"resolve_tool must DISCOVER the tool via the {rung.value} rung and "
            f"return its on-disk path (the {rung.name} scenario); at HEAD "
            f"{_TOOL_DISCOVERY_MODULE} is absent so the child probe could not "
            f"resolve it. {self._probe_observed()}"
        )
        resolved = self._probe_out.split("RESOLVED:", 1)[1].strip().splitlines()[0]
        assert resolved == self._planted_tool_path, (
            f"resolve_tool resolved the wrong path on the {rung.value} rung: "
            f"expected the planted executable {self._planted_tool_path!r}, got "
            f"{resolved!r}. {self._probe_observed()}"
        )

    def then_indeterminate_names_remediation(self) -> None:
        """resolve_tool exhausted the scale -> INDETERMINATE naming the remediation.

        Used by AT-3. Asserts the terminal rung returned an actionable, NON-EMPTY
        remediation string (NOT a bare/silent failure) -- the LOUD INDETERMINATE
        the genericità mandate requires. The remediation must NAME an install path
        (e.g. ``rustup`` / ``cargo install``) so an operator can act, not merely
        ``not found``.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:`` marker ->
        this AssertionError fires.
        """
        assert self._probe_rc == 0 and "INDETERMINATE:" in self._probe_out, (
            "a tool absent everywhere after the full discovery scale must yield a "
            "LOUD INDETERMINATE naming the remediation (never a silent degrade); "
            f"at HEAD {_TOOL_DISCOVERY_MODULE} is absent so the child probe could "
            f"not produce the terminal result. {self._probe_observed()}"
        )
        remediation = (
            self._probe_out.split("INDETERMINATE:", 1)[1].strip().splitlines()[0]
        )
        assert remediation, (
            "the INDETERMINATE result must carry a NON-EMPTY remediation string "
            f"(actionable, not a bare failure); got empty. {self._probe_observed()}"
        )
        lowered = remediation.lower()
        assert any(token in lowered for token in ("install", "rustup", "cargo")), (
            "the remediation must NAME an actionable install path (e.g. 'install "
            "via rustup' / 'cargo install') so the operator can act -- not a bare "
            f"'not found'; got {remediation!r}. {self._probe_observed()}"
        )

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-tool-discovery-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_executable(target: Path) -> Path:
        """Write a REAL executable file at ``target`` (chmod +x) and return it."""
        target.write_text("#!/bin/sh\necho planted\n", encoding="utf-8")
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    # ---- driving-port invocation (in-process driver) ------------------------

    def _run_resolve_probe(self, name: str, known: list[str]) -> tuple[int, str, str]:
        """Drive the REAL ``resolve_tool`` IN-PROCESS over the controlled fixture.

        The in-process analogue of the former ``python -c`` child fork: the
        ``_resolve_tool_probe_main`` EDGE imports ``tool_discovery`` and calls
        ``resolve_tool(name, known)``, printing the RESOLVED/INDETERMINATE marker.
        ``run_cli_in_process`` reproduces the subprocess observable -- chdir to the
        repo root (restored), stdout/stderr capture, and ``SystemExit``-to-exit-code
        mapping for the LOUD neither-shape failure.

        The env is HERMETIC for discovery and applied IN-PROCESS around the call
        (saved/restored in ``finally`` so the shared test process is never left
        mutated): PATH is the fixture's controlled dir ONLY (``resolve_tool`` reads
        it live via ``shutil.which`` at call-time, so the in-process value takes
        effect), HOME is the fixture's tmp home, and CARGO_HOME is neutralised so a
        real one on the host cannot leak into the rung-2/rung-3 fixtures.
        ``resolve_tool`` has NO module-level env-read (the known locations are the
        explicit ``known`` argument), so no fresh interpreter is needed for
        fidelity.
        """
        prior_env = dict(os.environ)
        os.environ["PATH"] = self._child_path
        os.environ["HOME"] = self._child_home
        os.environ.pop("CARGO_HOME", None)
        try:
            return run_cli_in_process(
                [name, *known],
                cwd=str(_repo_root()),
                main=_resolve_tool_probe_main,
            )
        finally:
            os.environ.clear()
            os.environ.update(prior_env)

    # ---- diagnostics --------------------------------------------------------

    def _probe_observed(self) -> str:
        return (
            f"probe_rc={self._probe_rc!r}; "
            f"known_locations={self._known_locations!r}; "
            f"planted={self._planted_tool_path!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/rust_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=rust_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
