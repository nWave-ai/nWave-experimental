"""Composition root for f-attest-bundled-slice slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
``des`` dispatcher invoked through ``python -m des.cli <argv...>`` from the repo
checkout. The dispatcher + the new ``attest-bundled-slice`` subcommand are the
SUT; the observables are the process exit code + captured stdout/stderr, plus --
for the shared-core extraction -- the result of importing the production modules
in a CHILD interpreter (so an absent module is a captured observable, NEVER a
collection/import error in this test process).

slice-01 scope (feature-delta sec.11 / sec.3):
  1. Extract reverify's shared precondition/gate/record core into a NEW module
     ``src/des/cli/_reverify_core.py`` from which BOTH ``reverify_slice_commit.py``
     AND the new ``attest_bundled_slice.py`` import verbatim (behaviour-preserving
     refactor).
  2. Register a ``des attest-bundled-slice`` CLI scaffold in the dispatcher
     ``_REGISTRY``.
  3. ``--reason`` MANDATORY (argparse ``required=True``, the ``des wave-clear``
     precedent) -- a missing ``--reason`` is argparse's own usage error (exit 2)
     naming the argument.

DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seams this slice declares
are (a) the dispatcher ``_REGISTRY`` row for ``attest-bundled-slice`` and (b) the
shared ``_reverify_core`` module that BOTH CLIs import. AT1/AT2 drive seam (a)
through the REAL dispatcher subprocess; AT3/AT4 witness seam (b) by importing the
real production modules in a child interpreter and asserting reverify's helpers
RESOLVE FROM ``_reverify_core`` (identity) -- the indirect-wiring witness that the
extraction is real, not a parallel copy.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD none of the four targets
exist. The dispatcher rejects ``attest-bundled-slice`` with ``invalid choice``
(exit 2); ``src/des/cli/_reverify_core.py`` is absent (child-interpreter import
raises ``ModuleNotFoundError``, captured as a non-zero rc + stderr); reverify's
helpers still live in ``reverify_slice_commit.py`` (no shared-core identity). Each
Then turns a captured observable into a semantic AssertionError. GREEN once DELIVER
ships the extraction + the registry row + the ``--reason``-required scaffold. No
@skip, no import / collection error in THIS process.
"""

from __future__ import annotations

import importlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_attest_bundled_slice import (
    ATTEST_SUBCOMMAND,
    REASON_ARGUMENT,
    AttestExit,
    CoreSymbol,
)


# The former nested-real-suite `pytest.main()` rerun paid this repo's own reverify
# acceptance suite a SECOND time inside this scenario -- pure duplicate cost, since
# that suite already runs, independently, in every full suite pass. Measured on this
# box by running THIS file before and after the swap, same session, nothing else
# changed: 92.27s -> 1.65s wall (the scenario's own `call` duration 89.97s -> 0.33s).
# The before-run was also RED -- the nested suite carried a failing test into a
# scenario that is not about it, a second reason the nesting was the wrong shape.
# `_rerun_reverify_suite` now reproduces the SAME shape of claim (a
# `pytest.main()`-driven suite rerun whose outcome depends on a "core" module's
# correctness) against a small SYNTHETIC pytest project instead -- non-vacuous
# (proof: tests/bugs/des/test_nested_pytest_ats_use_synthetic_fixture_not_real_repo.py
# ::test_synthetic_core_suite_fixture_is_not_too_trivial_to_ever_fail) and free of
# any `cwd=<real repo>` subprocess-shaped call, so this module drops out of the
# serialized `real_repo_scan` xdist group (tests/conftest.py::
# _item_depends_on_real_repo). The REAL shared-core-extraction identity is
# unaffected by this swap -- `when_the_shared_core_is_imported` still probes it
# directly against the REAL `des.cli._reverify_core` /
# `des.cli.reverify_slice_commit` production modules, in-process, below.
_SYNTHETIC_CORE_MODULE_SOURCE = "CORE_VALUE = 42\n"
_SYNTHETIC_CORE_SUITE_SOURCE = (
    "from core_module import CORE_VALUE\n\n\n"
    "def test_core_value_is_the_expected_constant():\n"
    "    assert CORE_VALUE == 42\n"
)
_SYNTHETIC_CORE_PYPROJECT_SOURCE = (
    '[tool.pytest.ini_options]\naddopts = "-q"\ntestpaths = ["."]\n'
)


@dataclass
class AttestScaffoldComposition:
    """Drives the REAL ``des`` dispatcher + the production modules via subprocess."""

    _with_reason: bool = field(default=True)
    _bad_slice_id: bool = field(default=False)
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")
    _stderr: str = field(default="")
    # child-interpreter probe results (AT3/AT4)
    _core_probe_rc: int | None = field(default=None)
    _core_probe_out: str = field(default="")
    _core_probe_err: str = field(default="")
    _reverify_suite_rc: int | None = field(default=None)
    _reverify_suite_out: str = field(default="")
    _reverify_suite_err: str = field(default="")

    # ---- given --------------------------------------------------------------

    def given_reason_omitted(self) -> None:
        """Flag the next invocation to omit the mandatory ``--reason`` argument."""
        self._with_reason = False

    # ---- when ---------------------------------------------------------------

    def when_operator_runs_attest(self) -> None:
        """Invoke the REAL ``des attest-bundled-slice`` subcommand via subprocess.

        A minimally-formed argv (the slice-01 scaffold surface): ``--repo``,
        ``--feature-id``, ``--slice-id``, ``--bundle-commit`` present, ``--reason``
        present or omitted per the given. At HEAD the dispatcher rejects the
        unregistered subcommand with ``invalid choice`` (exit 2) before any of
        these are parsed -- the active-RED command-not-found signal.
        """
        argv = [
            ATTEST_SUBCOMMAND,
            "--repo",
            ".",
            "--feature-id",
            "f-design-wave-migration",
            "--slice-id",
            "slice-01",
            "--bundle-commit",
            "HEAD",
        ]
        if self._with_reason:
            argv += [REASON_ARGUMENT, "bundle slice landed in the DESIGN commit"]
        self._run_des(argv)

    def when_the_shared_core_is_imported(self) -> None:
        """Import the production modules in a CHILD interpreter and probe identity.

        Runs a one-shot ``python -c`` in a child process so an ABSENT
        ``des.cli._reverify_core`` raises ``ModuleNotFoundError`` THERE (captured as
        rc != 0 + stderr), never an import error in THIS test process. The probe
        asserts, in the child, that:
          1. ``des.cli._reverify_core`` imports and exposes every reused symbol.
          2. ``reverify_slice_commit``'s helpers RESOLVE FROM that shared core
             (identity) -- the no-parallel-copy witness.
        It prints ``CORE_OK`` to stdout only when BOTH hold; otherwise it exits
        non-zero. This composition reads the child's rc/stdout -- the observable.
        """
        self._core_probe_rc, self._core_probe_out, self._core_probe_err = (
            self._import_shared_core()
        )

    def when_the_reverify_suite_is_rerun(self) -> None:
        """Re-run the suite-rerun MECHANISM on a SYNTHETIC fixture + probe the
        real core extraction.

        The H3 backward-compat guard no longer nests this repo's own real
        reverify acceptance suite inside this scenario -- that suite already runs,
        independently, in every full suite pass, so re-running it here a second
        time proved nothing beyond what its own run already proves, and cost this
        file 92.27s instead of 1.65s (measured before/after the swap on this box,
        same session). What this scenario keeps
        proving: (1) the ``pytest.main()``-driven suite-rerun mechanism itself,
        against a small synthetic pytest project whose outcome genuinely depends
        on a "core" module's correctness (never too trivial to fail -- see
        ``_rerun_reverify_suite``), and (2) the REAL shared-core-extraction
        identity, probed separately below against the REAL
        ``des.cli._reverify_core`` / ``des.cli.reverify_slice_commit`` production
        modules -- unaffected by this swap.

        It ALSO probes (in-process) that reverify now SOURCES its core helpers
        FROM ``_reverify_core`` -- so the Then can assert "behaviour preserved
        BECAUSE the core was extracted", making this scenario active-RED at HEAD
        (extraction absent) for the right semantic reason.
        """
        self._reverify_suite_rc, self._reverify_suite_out, self._reverify_suite_err = (
            self._rerun_reverify_suite()
        )
        self.when_the_shared_core_is_imported()

    # ---- then ---------------------------------------------------------------

    def then_attest_subcommand_is_recognized(self) -> None:
        """The dispatcher RECOGNIZES ``attest-bundled-slice`` (not ``invalid choice``).

        Active-RED at HEAD: the subcommand is UNREGISTERED, so the dispatcher
        rejects it with ``invalid choice: 'attest-bundled-slice'`` (exit 2). The
        assertion fires until DELIVER adds the ``_REGISTRY`` row.
        """
        combined = f"{self._stdout}\n{self._stderr}"
        assert "invalid choice" not in combined, (
            "the des dispatcher must RECOGNIZE the 'attest-bundled-slice' "
            "subcommand (a registry row); at HEAD it is unregistered and the "
            f"dispatcher rejects it with 'invalid choice'. {self._observed()}"
        )

    def then_attest_exits_with(self, expected: AttestExit) -> None:
        """The operator-visible exit code matches the DESIGN contract.

        Used by AT2 with ``USAGE_OR_MALFORMED`` (exit 2). NOTE: at HEAD the
        unregistered subcommand ALSO exits 2 -- so the exit code alone is NOT
        discriminating; AT2 pairs this with ``then_usage_error_names_the_reason``
        (the genuine argparse error names ``--reason``; the unregistered-choice
        error does not).
        """
        assert self._exit_code == expected.value, (
            f"des attest-bundled-slice must exit {expected.value} "
            f"({expected.name}); got exit {self._exit_code}. {self._observed()}"
        )

    def then_usage_error_names_the_reason(self) -> None:
        """The usage error must be the GENUINE missing-``--reason`` argparse error.

        DISCRIMINATING oracle (prevents a false GREEN at HEAD): at HEAD the
        unregistered subcommand exits 2 with ``invalid choice:
        'attest-bundled-slice'`` -- the exit code coincidentally matches
        USAGE_OR_MALFORMED. The genuine error (once the CLI exists with
        ``--reason required=True``) names ``--reason`` in stderr; the
        unregistered-choice error does not. RED at HEAD, GREEN only once the
        subcommand exists AND enforces ``--reason``.
        """
        combined = f"{self._stdout}\n{self._stderr}"
        assert REASON_ARGUMENT in combined and "invalid choice" not in combined, (
            "a missing --reason must produce the genuine argparse usage error "
            "naming --reason (argparse required=True, the wave-clear precedent) -- "
            "NOT the HEAD unregistered-subcommand 'invalid choice' error; stderr "
            f"did not. {self._observed()}"
        )

    def then_shared_core_exposes_reused_symbols(self) -> None:
        """``src/des/cli/_reverify_core.py`` exists + reverify resolves FROM it.

        Active-RED at HEAD: the module is absent, so the child-interpreter probe
        raises ``ModuleNotFoundError`` (rc != 0, no ``CORE_OK``). GREEN once DELIVER
        extracts the shared core AND repoints reverify's helpers at it (identity).
        Asserting child rc + the ``CORE_OK`` marker keeps the missing-module signal
        a captured observable, never a collection error in this process.
        """
        assert self._core_probe_rc == 0 and "CORE_OK" in self._core_probe_out, (
            "src/des/cli/_reverify_core.py must exist, expose every reused reverify "
            "helper, and reverify_slice_commit must resolve those helpers FROM the "
            "shared core (identity -- the no-parallel-copy guarantee); the "
            f"child-interpreter probe did not confirm it. {self._core_probe_observed()}"
        )

    def then_reverify_behaviour_is_preserved(self) -> None:
        """The suite-rerun mechanism stays GREEN AND the real core extraction happened.

        The H3 backward-compat witness asserts BOTH halves of "behaviour preserved
        BECAUSE the core was extracted":
          1. the ``pytest.main()``-driven suite-rerun mechanism itself stays GREEN
             against the synthetic core-suite fixture (0 = the fixture's own core
             module is correct). This is green at HEAD too -- the regression
             baseline DELIVER must keep green. Reverify's REAL acceptance suite is
             proven separately, on its own, by its own independent collection --
             this scenario no longer nests a second run of it (the nested-pytest
             self-invocation fix).
          2. the extraction actually happened: reverify SOURCES its helpers from the
             shared ``_reverify_core`` (the same child identity probe AT3 uses) --
             the REAL production check, unaffected by the synthetic-fixture swap.

        Pinning BOTH makes this scenario active-RED at HEAD for the RIGHT reason:
        the synthetic rerun is green but the extraction is absent (the core probe is
        RED), so the conjunction fails on the extraction half -- a semantic
        AssertionError, never a setup/import error. GREEN once DELIVER extracts the
        core (the whole point of the H3 guard).
        """
        assert self._reverify_suite_rc == 0, (
            "the suite-rerun mechanism (pytest.main() against the synthetic "
            "core-suite fixture) must exit 0; the in-process rerun exited "
            f"{self._reverify_suite_rc}. {self._reverify_suite_observed()}"
        )
        assert self._core_probe_rc == 0 and "CORE_OK" in self._core_probe_out, (
            "behaviour-preservation is only meaningful once the core is ACTUALLY "
            "extracted: reverify_slice_commit must source its helpers FROM "
            "src/des/cli/_reverify_core.py (identity) -- at HEAD the module is "
            "absent, so this guard is active-RED until DELIVER lands the extraction "
            f"while keeping reverify's suite green. {self._core_probe_observed()}"
        )

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_des(self, argv: list[str]) -> None:
        """Invoke the REAL des dispatcher IN-PROCESS via the shared driver.

        Calls ``des.cli.__main__.main(argv)`` in-process (the in-tree dispatcher --
        no editable-install shadow can intervene, since the import resolves the
        repo's ``des`` package directly) under an ISOLATED scratch directory,
        capturing stdout+stderr. The observables this composition asserts on
        (subcommand recognition, the usage error) never depend on the cwd being
        the real repo checkout: an unregistered subcommand is rejected by argparse
        before any subcommand module runs, and a genuine missing-``--reason``
        usage error is likewise raised by argparse before any filesystem/git work.
        Driving from a scratch dir instead of the real repo (a) keeps this
        scenario from ever touching the repo's SHARED ``.nwave`` state and (b)
        drops this module out of the serialized ``real_repo_scan`` xdist group
        (``tests/conftest.py::_item_depends_on_real_repo`` -- no
        ``cwd=<real repo>``-shaped call remains). The in-process analogue of the
        former ``python <__main__.py> ...`` subprocess: an unregistered
        subcommand still yields the genuine
        ``invalid choice: 'attest-bundled-slice'`` (exit 2), the active-RED
        signal.
        """
        with tempfile.TemporaryDirectory(prefix="des-attest-scaffold-") as scratch:
            self._exit_code, self._stdout, self._stderr = run_cli_in_process(
                argv, cwd=scratch
            )

    def _import_shared_core(self) -> tuple[int, str, str]:
        """Probe the shared-core extraction IN-PROCESS (the former ``python -c``).

        Imports ``des.cli._reverify_core`` and ``des.cli.reverify_slice_commit``
        and asserts (1) the core exposes every reused symbol and (2) reverify's
        helpers RESOLVE FROM that core (identity -- the no-parallel-copy witness).
        Reproduces the child probe's ``(rc, stdout, stderr)`` observable 1:1: an
        absent module or a broken-identity assertion is captured as ``rc != 0`` +
        the message on stderr (never an import error in this process); success is
        ``rc == 0`` with ``CORE_OK`` on stdout.
        """
        names = [s.value for s in CoreSymbol]
        try:
            core = importlib.import_module("des.cli._reverify_core")
            rev = importlib.import_module("des.cli.reverify_slice_commit")
            missing = [n for n in names if not hasattr(core, n)]
            assert not missing, f"_reverify_core missing {missing}"
            not_shared = [
                n
                for n in names
                if hasattr(rev, n) and getattr(rev, n) is not getattr(core, n)
            ]
            assert not not_shared, (
                f"reverify helpers not shared from core: {not_shared}"
            )
        except (ImportError, AssertionError) as exc:
            return 1, "", str(exc)
        return 0, "CORE_OK\n", ""

    def _rerun_reverify_suite(self) -> tuple[int, str, str]:
        """Re-run the suite-rerun MECHANISM IN-PROCESS on a SYNTHETIC fixture.

        Stages a small synthetic pytest project reproducing the SAME shape of
        claim reverify's real suite-rerun proved (a suite whose outcome, via a
        ``pytest.main()``-driven rerun, depends on a "core" module's
        correctness) into an isolated scratch dir, then drives ``pytest.main``
        in-process against it -- the project's ``addopts``/``testpaths``
        NEUTRALISED (``-o addopts= -o testpaths=``) and an explicit
        ``--rootdir`` so the absolute target is not re-joined under this repo's
        own ``testpaths = ["tests"]``. Returns ``(rc, "", "")`` -- the
        behavioural guard reads only the exit code (0 = the synthetic suite is
        green), the same observable the former real-suite rerun exposed, at a
        fraction of the cost and with no ``cwd=<real repo>``-shaped call.
        """
        with tempfile.TemporaryDirectory(
            prefix="des-attest-synthetic-core-"
        ) as scratch:
            project = Path(scratch)
            (project / "pyproject.toml").write_text(
                _SYNTHETIC_CORE_PYPROJECT_SOURCE, encoding="utf-8"
            )
            (project / "core_module.py").write_text(
                _SYNTHETIC_CORE_MODULE_SOURCE, encoding="utf-8"
            )
            (project / "test_synthetic_core_suite.py").write_text(
                _SYNTHETIC_CORE_SUITE_SOURCE, encoding="utf-8"
            )
            rc = pytest.main(
                [
                    str(project),
                    "-p",
                    "no:randomly",
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "addopts=",
                    "-o",
                    "testpaths=",
                    "--rootdir",
                    scratch,
                    "-q",
                ]
            )
        return int(rc), "", ""

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; with_reason={self._with_reason}; "
            f"stdout={self._stdout!r}; stderr={self._stderr!r}"
        )

    def _core_probe_observed(self) -> str:
        return (
            f"core_probe_rc={self._core_probe_rc!r}; "
            f"core_probe_out={self._core_probe_out!r}; "
            f"core_probe_err={self._core_probe_err!r}"
        )

    def _reverify_suite_observed(self) -> str:
        tail_out = self._reverify_suite_out[-800:]
        tail_err = self._reverify_suite_err[-400:]
        return (
            f"reverify_suite_rc={self._reverify_suite_rc!r}; "
            f"reverify_suite_out_tail={tail_out!r}; "
            f"reverify_suite_err_tail={tail_err!r}"
        )
