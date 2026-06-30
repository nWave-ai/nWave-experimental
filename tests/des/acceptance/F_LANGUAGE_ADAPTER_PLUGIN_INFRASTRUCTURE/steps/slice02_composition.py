"""Composition root for F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-02.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root -- the real installed Python package boundary. The
composition launches a subprocess that imports the production
``src.des.ports.language_adapter_plugin`` module (post-DELIVER) and
introspects the ABC via ``inspect`` / ``abc`` / ``issubclass`` -- all from
WITHIN the subprocess, NEVER from this composition module.

Mandate-13 (driving-port-only, CRITICAL P0, identity-essential per Ale
2026-05-25): ZERO direct domain imports in this composition module. The
driving port for slice-02 ATs is the as-installed Python runtime subprocess.
The import + ``issubclass`` check happens INSIDE the subprocess script (a
short ``-c`` snippet); the assertion observes the subprocess exit code and
stdout JSON shape -- port-exposed observables only.

This is the F-ATDD-PURE-AT-DIRECT-DOMAIN-TESTING-ANTI-PATTERN (friction #34)
avoidance: the test EXERCISES the production module through the install /
package import boundary, never bypasses it.

RED scaffold (Mandate 7 / ADR-025): every scenario reds for the RIGHT
reason -- the production ABC module ``src/des/ports/language_adapter_plugin.py``
does NOT YET exist (empirical reads at DISTILL time: file absent, the
in-tree conformance-fixture plugin module + entry-point registration are
also absent). The subprocess exits non-zero with ImportError because the
module is missing, NOT because the test infrastructure is broken. DELIVER's
GREEN phase creates:
  - ``src/des/ports/language_adapter_plugin.py`` with ``LanguageAdapterPlugin``
    ABC (subclass of ``scripts.install.plugins.base.InstallationPlugin``) +
    ``ProbeResult`` dataclass
  - in-tree conformance-fixture plugin (a minimal concrete subclass) +
    entry-point registration in the local installable wheel under group
    ``nwave.lang.adapter``

Layer note: every scenario here is layer 3 (subprocess / FS acceptance
against the real installed package) -- example-only, no PBT (Mandate 9/11).
Every state-mutating step asserts via port-exposed observables -- subprocess
exit codes + stdout JSON shapes (Mandate 8 universe-bound).

Driving ports (per DESIGN §Reuse Analysis + slice-02 substrate):
- ``python -c <introspection snippet>`` -- subprocess loading ``LanguageAdapterPlugin``
  via its package path and reporting JSON-encoded introspection facts
- ``python -c <conformance snippet>`` -- subprocess querying
  ``importlib.metadata.entry_points(group='nwave.lang.adapter')`` and
  asserting every discovered class is-a ``LanguageAdapterPlugin`` subclass

The composition module's responsibility is: build the subprocess invocation,
capture its observable outcome, and expose typed assertions over the
observed JSON envelope. NEVER import the production module here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .slice02_domain_types import (
    AbcContractMember,
    AbcIntrospectionShape,
    EntryPointConformanceShape,
)


# Repo root -- the in-process snippet runs with cwd=repo so the production
# module resolves through the package (post-DELIVER, the module at
# ``src/des/ports/language_adapter_plugin.py`` is importable as
# ``des.ports.language_adapter_plugin`` via the installed package path or
# directly via the in-repo src layout).
_REPO_ROOT = Path(__file__).resolve().parents[5]


def _run_py_snippet_in_process(snippet: str, *, cwd: Path) -> tuple[int, str, str]:
    """Drive a ``python -c <snippet>`` fork IN-PROCESS (corpus-migration-in-process).

    Reuses ``run_cli_in_process`` to ``exec`` the IDENTICAL snippet under ``cwd``
    with stdout/stderr captured and the snippet's ``sys.exit(n)`` mapped onto the
    exit code -- behaviour-identical to the fresh-interpreter fork the corpus
    ran, minus the interpreter spawn. Returns ``(exit_code, stdout, stderr)``.
    """

    def _exec_snippet(_argv: list[str]) -> int:
        exec(compile(snippet, "<in-process-snippet>", "exec"), {"__name__": "__main__"})
        return 0

    return run_cli_in_process([], cwd=cwd, main=_exec_snippet)


# Subprocess snippets -- live as module-level constants so they are
# inspectable + reviewable. Each is a self-contained Python script that
# imports the production module, performs introspection, and prints a
# JSON envelope to stdout. Exits non-zero on any failure (ImportError,
# attribute absent, type mismatch).

_ABC_INTROSPECTION_SNIPPET = """
import inspect
import json
import sys
from abc import ABC

try:
    from des.ports.language_adapter_plugin import LanguageAdapterPlugin
except ImportError as exc:
    print(json.dumps({"error": "ImportError", "detail": str(exc)}))
    sys.exit(2)

declared_members = []
for member_name in ("target_language", "register_adapters", "probe", "port_coverage"):
    declared_members.append({
        "name": member_name,
        "declared": hasattr(LanguageAdapterPlugin, member_name),
    })

# M52 ATD amendment (2026-05-25, friction #43 closure): the
# `is_installation_plugin_subclass` field was REMOVED. M44 Option (a)
# decouples the pure ABC from `InstallationPlugin` (F-D-09); the dual-base
# contract is asserted on the CONCRETE fixture via AT-3's separate
# `_ENTRY_POINT_CONFORMANCE_SNIPPET` dual-issubclass check.
envelope = {
    "is_abstract": inspect.isabstract(LanguageAdapterPlugin) or bool(
        getattr(LanguageAdapterPlugin, "__abstractmethods__", frozenset())
    ),
    "declared_members": declared_members,
}
print(json.dumps(envelope))
sys.exit(0)
"""


_ENTRY_POINT_CONFORMANCE_SNIPPET = """
import json
import sys
from importlib.metadata import entry_points

try:
    from des.ports.language_adapter_plugin import LanguageAdapterPlugin
    from scripts.install.plugins.base import InstallationPlugin
except ImportError as exc:
    print(json.dumps({"error": "ImportError", "detail": str(exc)}))
    sys.exit(2)

registered = []
non_conforming = []
for ep in entry_points(group="nwave.lang.adapter"):
    try:
        cls = ep.load()
    except Exception as load_exc:
        non_conforming.append({"name": ep.name, "reason": f"load-failed: {load_exc}"})
        continue
    registered.append(ep.name)
    if not isinstance(cls, type):
        non_conforming.append({
            "name": ep.name,
            "reason": "loaded-object-is-not-a-class",
        })
        continue
    # M44 Option (a) dual-base contract: every discovered plugin MUST be
    # BOTH a LanguageAdapterPlugin subclass (language-adapter contract:
    # target_language / port_coverage / register_adapters / probe) AND an
    # InstallationPlugin subclass (install-pipeline contract: install /
    # verify). Pure-ABC LanguageAdapterPlugin (no scripts.* import) +
    # concrete dual-base inheritance at the scripts/install/plugins/ site
    # preserves both contracts on every conformant plugin.
    if not issubclass(cls, LanguageAdapterPlugin):
        non_conforming.append({
            "name": ep.name,
            "reason": "not-a-LanguageAdapterPlugin-subclass",
        })
        continue
    if not issubclass(cls, InstallationPlugin):
        non_conforming.append({
            "name": ep.name,
            "reason": "not-an-InstallationPlugin-subclass",
        })

envelope = {
    "registered": registered,
    "non_conforming": non_conforming,
    "all_conform": len(non_conforming) == 0 and len(registered) >= 1,
}
print(json.dumps(envelope))
sys.exit(0)
"""


# --- Domain observation types ------------------------------------------------


@dataclass(frozen=True)
class AbcIntrospectionResult:
    """The user-observable verdict of one ABC-introspection subprocess.

    Port-exposed observable: subprocess exit code + stdout JSON envelope.
    Frozen: an observation is immutable.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def parsed_envelope(self) -> dict | None:
        """The structured JSON envelope on stdout, or None if unparseable."""
        try:
            return json.loads(self.stdout)
        except (json.JSONDecodeError, ValueError):
            return None

    @property
    def is_abstract(self) -> bool:
        """Whether the introspected class is an abstract class.

        Slice-02 floor: LanguageAdapterPlugin MUST be abstract -- the substrate
        every per-language plugin must subclass + implement.
        """
        envelope = self.parsed_envelope
        if envelope is None:
            return False
        return bool(envelope.get("is_abstract", False))

    # M52 ATD amendment (2026-05-25, friction #43 closure): the
    # ``is_installation_plugin_subclass`` property was REMOVED. M44 Option (a)
    # decouples the pure ABC from ``InstallationPlugin`` (F-D-09); the dual-base
    # contract now lives ONLY on the concrete fixture and is asserted by
    # ``EntryPointConformanceResult`` (AT-3) via the dual-issubclass check
    # inside ``_ENTRY_POINT_CONFORMANCE_SNIPPET``.

    def member_declared(self, member: AbcContractMember) -> bool:
        """Whether the introspected class declares the named contract member.

        Slice-02 contract: the four mandatory members
        (target_language, register_adapters, probe, port_coverage) MUST be
        declared on the ABC so every subclass inherits the contract surface.
        """
        envelope = self.parsed_envelope
        if envelope is None:
            return False
        declared = envelope.get("declared_members", [])
        for entry in declared:
            if entry.get("name") == member.value:
                return bool(entry.get("declared", False))
        return False


@dataclass(frozen=True)
class EntryPointConformanceResult:
    """The user-observable verdict of one entry-point conformance subprocess.

    Port-exposed observable: subprocess exit code + stdout JSON envelope.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def parsed_envelope(self) -> dict | None:
        """The structured JSON envelope on stdout."""
        try:
            return json.loads(self.stdout)
        except (json.JSONDecodeError, ValueError):
            return None

    @property
    def registered_names(self) -> list[str]:
        """The discovered plugin names, or empty if discovery failed."""
        envelope = self.parsed_envelope
        if envelope is None:
            return []
        names = envelope.get("registered", [])
        if not isinstance(names, list):
            return []
        return names

    @property
    def non_conforming_entries(self) -> list[dict]:
        """The list of non-conformance findings from the conformance check."""
        envelope = self.parsed_envelope
        if envelope is None:
            return []
        non_conforming = envelope.get("non_conforming", [])
        if not isinstance(non_conforming, list):
            return []
        return non_conforming

    @property
    def all_conform(self) -> bool:
        """Whether every discovered plugin satisfied the conformance check."""
        envelope = self.parsed_envelope
        if envelope is None:
            return False
        return bool(envelope.get("all_conform", False))


# --- Composition root --------------------------------------------------------


@dataclass
class LanguageAdapterAbcComposition:
    """Production-composition root for slice-02 ATs.

    Each ``given_*`` / ``when_*`` / ``then_*`` is a single service method.
    Step bodies in ``slice02_common_steps.py`` invoke exactly one of these
    per Gherkin step (Mandate-12 criterion 3): typed lookup + one
    composition call, zero control flow in step bodies.
    """

    _abc_query_staged: bool = False
    _conformance_query_staged: bool = False
    abc_result: AbcIntrospectionResult | None = None
    conformance_result: EntryPointConformanceResult | None = None

    # --- Given services ----------------------------------------------------

    def given_abc_substrate_query_staged(self) -> None:
        """Stage the per-scenario ABC introspection query.

        Slice-02 uses the REAL installed package path -- the subprocess
        imports ``des.ports.language_adapter_plugin`` (post-DELIVER) via the
        repo's src layout / installed wheel boundary. At slice-02 RED the
        production module is ABSENT; the subprocess subsequently exits with
        ImportError (exit 2 per snippet contract). DELIVER's GREEN phase
        creates the module + ABC, the subprocess succeeds.
        """
        self._abc_query_staged = True

    def given_conformance_query_staged(self) -> None:
        """Stage the per-scenario entry-point conformance query.

        Slice-02 floor: the in-tree conformance-fixture plugin is registered
        in the local installable wheel under group ``nwave.lang.adapter``.
        At RED neither the ABC nor the fixture entry-point exist; the
        subprocess exits with ImportError. GREEN: ABC + fixture both exist,
        the discovered list is non-empty and every discovered class is-a
        LanguageAdapterPlugin subclass.
        """
        self._conformance_query_staged = True

    # --- When services -----------------------------------------------------

    def when_abc_introspection_runs(self) -> AbcIntrospectionResult:
        """Run the production ABC introspection IN-PROCESS.

        Drives the IDENTICAL ``<snippet>`` (formerly ``python -c <snippet>``,
        cwd=repo) in-process (corpus-migration-in-process). The snippet imports
        ``des.ports.language_adapter_plugin.LanguageAdapterPlugin``, performs the
        introspection (is_abstract, declared-member presence), and prints a JSON
        envelope. Exits 0 on success, 2 on ImportError (mapped from the
        snippet's ``sys.exit`` -- behaviour-identical to the fork).
        """
        assert self._abc_query_staged, "abc query not staged"
        exit_code, stdout, stderr = _run_py_snippet_in_process(
            _ABC_INTROSPECTION_SNIPPET, cwd=_REPO_ROOT
        )
        result = AbcIntrospectionResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr
        )
        self.abc_result = result
        return result

    def when_entry_point_conformance_runs(self) -> EntryPointConformanceResult:
        """Run the production entry-point conformance check IN-PROCESS.

        Drives the IDENTICAL ``<snippet>`` (formerly ``python -c <snippet>``,
        cwd=repo) in-process (corpus-migration-in-process). The snippet queries
        ``importlib.metadata.entry_points(group='nwave.lang.adapter')``, loads
        each discovered entry-point's class, and verifies each is-a
        ``LanguageAdapterPlugin`` subclass. Prints a JSON envelope and exits 0
        on success, 2 on ImportError (mapped from the snippet's ``sys.exit``).
        """
        assert self._conformance_query_staged, "conformance query not staged"
        exit_code, stdout, stderr = _run_py_snippet_in_process(
            _ENTRY_POINT_CONFORMANCE_SNIPPET, cwd=_REPO_ROOT
        )
        result = EntryPointConformanceResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr
        )
        self.conformance_result = result
        return result

    # --- Then services -----------------------------------------------------

    def then_abc_introspection_shape_is(self, shape: AbcIntrospectionShape) -> None:
        """Assert the ABC-introspection envelope reports the expected shape fact.

        Port-exposed observable: subprocess stdout JSON envelope's
        ``is_abstract`` boolean field. RED path: subprocess exited 2 with no
        JSON, observation resolves False, assertion fails for the right reason
        (ImportError).

        M52 ATD amendment (2026-05-25, friction #43 closure): the
        ``IS_INSTALLATION_PLUGIN_SUBCLASS`` branch was REMOVED. M44 Option (a)
        decouples the pure ABC from ``InstallationPlugin`` (F-D-09); the
        dual-base contract is asserted on the concrete fixture by AT-3's
        ``then_conformance_envelope_shape_is`` over the dual-issubclass
        snippet -- the equivalent dimension lives at the correct layer.
        """
        assert self.abc_result is not None, "abc introspection not run"
        observed = {
            AbcIntrospectionShape.IS_ABSTRACT: self.abc_result.is_abstract,
        }
        assert observed.get(shape, False), (
            f"ABC introspection shape {shape.value} not satisfied\n"
            f"exit={self.abc_result.exit_code}\n"
            f"stdout: {self.abc_result.stdout}\n"
            f"stderr: {self.abc_result.stderr}"
        )

    def then_abc_member_is_declared(self, member: AbcContractMember) -> None:
        """Assert the introspected ABC declares the named contract member.

        Slice-02 contract: target_language, register_adapters, probe,
        port_coverage MUST all be declared on LanguageAdapterPlugin. RED
        path: subprocess exited 2 with no envelope, ``member_declared``
        returns False, assertion fails for the right reason.
        """
        assert self.abc_result is not None, "abc introspection not run"
        assert self.abc_result.member_declared(member), (
            f"ABC contract member {member.value} not declared on "
            f"LanguageAdapterPlugin\n"
            f"exit={self.abc_result.exit_code}\n"
            f"stdout: {self.abc_result.stdout}\n"
            f"stderr: {self.abc_result.stderr}"
        )

    def then_conformance_envelope_shape_is(
        self, shape: EntryPointConformanceShape
    ) -> None:
        """Assert the conformance envelope reports the expected shape fact.

        Port-exposed observable: subprocess stdout JSON envelope's
        ``all_conform`` / ``non_conforming`` empty-list fields.
        """
        assert self.conformance_result is not None, "conformance check not run"
        observed = {
            EntryPointConformanceShape.ALL_CONFORM: (
                self.conformance_result.all_conform
            ),
            EntryPointConformanceShape.NO_NON_CONFORMING: (
                len(self.conformance_result.non_conforming_entries) == 0
            ),
        }
        assert observed.get(shape, False), (
            f"conformance envelope shape {shape.value} not satisfied\n"
            f"exit={self.conformance_result.exit_code}\n"
            f"stdout: {self.conformance_result.stdout}\n"
            f"stderr: {self.conformance_result.stderr}"
        )
