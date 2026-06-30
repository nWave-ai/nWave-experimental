"""Domain types for fix-whole-tree-contract-gate-runner-aware slice-01 (Mandate-12 criterion 1).

Every domain noun used in the Gherkin is expressed ONCE here as a typed enum /
NewType / frozen dataclass. Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain type exists (criterion 1 + 2).

The SUT is the REAL whole-tree contract gate driven via subprocess (Mandate-13
Layer-3). The single keystone observable is the net-new ``WholeTreeRunnerResolved``
resolution event the gate emits on its captured output -- the typed
``GateOutcome`` below parses the gate's emitted single-line-JSON events from the
combined stdout/stderr and exposes the resolution facts the ATs assert on.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import NewType


class TargetKind(Enum):
    """The target the whole-tree gate resolves a runner for."""

    RUST = "rust"  # a single Cargo.toml -> resolves the cargo-test run facet
    PYTHON = "python"  # a single pyproject.toml -> resolves pytest (router -> None)
    POLYGLOT = (
        "polyglot"  # Cargo.toml + package.json(vitest) -> 2 matched, no fast-path
    )
    UNRECOGNIZED = "unrecognized"  # NO recognized lockfile (slice-04 D9): a test
    # file but zero of {pyproject.toml, pytest.ini, package.json, go.mod,
    # Cargo.toml} -> resolve() returns the 0-lockfile UnrecognizedRunner subtype,
    # which both whole-tree routers MUST treat as a pytest FALLBACK (D9), not an
    # ambiguous degrade. pytest is nWave-dev's home runner; a lockfile-less Python
    # tree must not regress to exit-3.


class RepoRunnerOverride(Enum):
    """A repo-level ``.nwave/runner.json`` whole-tree runner declaration (D8).

    The operator's whole-tree runner declaration -- the repo-level sibling of the
    feature-scoped ``docs/feature/<id>/runner.json``. Consulted by ``resolve`` ONLY
    when ``feature is None`` (whole-tree), BEFORE the lockfile-scan, so it escapes a
    polyglot-root ``Indeterminate``. Each member carries the EXACT file bytes the
    composition writes to ``<repo>/.nwave/runner.json`` -- the three D8 override
    states (valid registry key / unknown key / malformed JSON).
    """

    VALID_CARGO = '{"runner": "cargo-test"}\n'  # registry key -> BYPASS scan, cargo
    UNKNOWN_KEY = '{"runner": "bogus-runner"}\n'  # not in _REGISTRY -> INDETERMINATE
    MALFORMED_JSON = '{"runner": "cargo-test"\n'  # truncated -> JSONDecodeError, LOUD

    @property
    def content(self) -> str:
        """The exact ``.nwave/runner.json`` bytes this override declares."""
        return self.value


class DigestMode(Enum):
    """A whole-tree DIGEST mode of the contract gate (slice-02 enumerate facet).

    Each member carries the exact CLI argv tail (after ``--repo <target>``) that
    selects the mode -- the digest leg must enumerate the target's scope through
    the resolved runner's OWN enumerate facet (``cargo nextest list`` /
    ``_collect_scope``), never the slice-01 D6 no-digest placeholder. The router
    intercepts a non-pytest target at the preamble BEFORE any git use, so the
    Cargo fixtures need no git work-tree (``--verify-gate-scope`` still requires
    ``--commit`` at the argparse layer -- supplied as ``HEAD``).
    """

    COMMITTED_SCOPE_DIGEST = ("--committed-scope-digest",)
    VERIFY_GATE_SCOPE = ("--verify-gate-scope", "--commit", "HEAD")
    PRINT_DIGEST = ("--collect-only", "--print-digest")

    @property
    def argv(self) -> tuple[str, ...]:
        """The CLI argv tail that selects this digest mode."""
        return self.value


# The abstract runner identity the target's lockfile resolves to (mirrors
# ``test_runner_port._REGISTRY`` row names -- the SSOT for these strings).
ResolvedRunner = NewType("ResolvedRunner", str)

CARGO_RUNNER: ResolvedRunner = ResolvedRunner("cargo-test")
PYTEST_RUNNER: ResolvedRunner = ResolvedRunner("pytest")

# The net-new resolution event DELIVER must emit (declared by DISTILL). Present
# in the gate's output ONLY once the whole-tree runner router is wired -- ABSENT
# at HEAD, which is what makes every slice-01 behavioural assertion active-RED.
RESOLUTION_EVENT: str = "WholeTreeRunnerResolved"

# The digest event the gate emits when a digest mode produces a real digest
# (slice-02 enumerate facet). Its ``runner`` provenance proves WHICH runner's
# enumerate facet the digested node-id set came from (cargo-test vs pytest).
GATE_SCOPE_DIGEST_EVENT: str = "GateScopeDigest"

# A SHA-256 hex digest line: the bare-stdout ``gate_scope_digest`` the digest
# modes print. Used to witness that a pytest target still yields a REAL digest.
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

# The #73 symptom token: the hardcoded-pytest-seam crash on a non-Python target.
# A correctly-routed gate NEVER emits this on a Rust target.
INTERPRETER_UNAVAILABLE_TOKEN: str = "InterpreterUnavailable"

# The degrade-LOUD INDETERMINATE marker the whole-tree router emits when it resolves
# no trustworthy runner (polyglot root with no override / unknown-or-malformed
# override / cargo-absent run leg). Source: run_contract_gate._WHOLE_TREE_RUNNER_
# INDETERMINATE_EVENT. Its ``reason`` is the SSOT the D8 sad-path ATs assert on.
WHOLE_TREE_INDETERMINATE_EVENT: str = "health.gate.whole-tree-runner.indeterminate"

# The repo-level whole-tree runner declaration path (D8). A wired override-aware
# reason names THIS file; the at-HEAD polyglot reason names the feature-scoped
# ``docs/feature/<id>/runner.json`` instead (the ``.nwave/`` prefix discriminates).
REPO_RUNNER_OVERRIDE_FILE: str = ".nwave/runner.json"

# The unregistered runner key the UNKNOWN_KEY override declares -- a wired reason
# names it verbatim ("declared runner '<X>' not registered"), NEVER guessed.
UNREGISTERED_RUNNER_NAME: str = "bogus-runner"

# The exit code the whole-tree router returns on a degrade-LOUD INDETERMINATE
# (run_contract_gate._GATE_INDETERMINATE_EXIT_CODE) -- a clean refusal, not a crash.
WHOLE_TREE_INDETERMINATE_EXIT: int = 3

# The competing-lockfile filenames a polyglot fixture stages; the no-override
# polyglot reason (D2) names BOTH (the no-regression witness reads them).
POLYGLOT_LOCKFILES: tuple[str, ...] = ("Cargo.toml", "package.json")


@dataclass(frozen=True)
class GateOutcome:
    """The shipped observable of one whole-tree gate run (Mandate-13 artifact).

    Parses the gate's emitted single-line-JSON events from the combined captured
    channels -- NOTHING the test fabricated. Every accessor reads only what the
    SUT actually shipped (the emitted events + the process exit code).
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        """Both captured channels (events are emitted on stdout AND stderr)."""
        return f"{self.stdout}\n{self.stderr}"

    def events(self) -> list[dict[str, object]]:
        """Every single-line-JSON event object the gate emitted (dedup-stable)."""
        seen: list[dict[str, object]] = []
        for line in self.combined.splitlines():
            line = line.strip()
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj not in seen:
                seen.append(obj)
        return seen

    def resolution_event(self) -> dict[str, object] | None:
        """The ``WholeTreeRunnerResolved`` event, or None when it was never emitted."""
        for ev in self.events():
            if ev.get("event") == RESOLUTION_EVENT:
                return ev
        return None

    def emitted_interpreter_unavailable(self) -> bool:
        """Did the gate crash on the hardcoded pytest seam (the #73 symptom)?"""
        return INTERPRETER_UNAVAILABLE_TOKEN in self.combined

    # --- slice-02: runner-aware digest observables --------------------------

    def resolution_digest_degraded(self) -> object | None:
        """The ``digest_degraded`` flag on the resolution event (None if absent).

        slice-02 RED discriminator: in a digest mode the wired enumerate facet
        makes this ``False``; at HEAD the mode-agnostic router stamps the slice-01
        D6 placeholder ``True`` for every Cargo invocation (the enumerate facet is
        not built yet).
        """
        ev = self.resolution_event()
        return None if ev is None else ev.get("digest_degraded")

    def digest_event(self) -> dict[str, object] | None:
        """The ``GateScopeDigest`` event (a real digest), or None when not emitted."""
        for ev in self.events():
            if ev.get("event") == GATE_SCOPE_DIGEST_EVENT:
                return ev
        return None

    def printed_digest(self) -> str | None:
        """The bare SHA-256 ``gate_scope_digest`` line printed to stdout, if any."""
        for line in self.stdout.splitlines():
            candidate = line.strip()
            if _SHA256_HEX.match(candidate):
                return candidate
        return None

    # --- slice-03: D8 repo-level override / degrade-LOUD observables ---------

    def indeterminate_event(self) -> dict[str, object] | None:
        """The whole-tree-runner INDETERMINATE marker, or None when not emitted.

        The degrade-LOUD channel: a polyglot root that resolved no trustworthy
        runner (no override / unknown-or-malformed override). A wired override
        BYPASSES this for a VALID declared runner (the keystone), so its ABSENCE on
        the resolution layer is the proof the declaration was honoured.
        """
        for ev in self.events():
            if ev.get("event") == WHOLE_TREE_INDETERMINATE_EVENT:
                return ev
        return None

    def indeterminate_reason(self) -> str:
        """The ``reason`` text of the INDETERMINATE marker (empty when absent).

        The D8 sad-path discriminator: an override-aware reason names the
        ``.nwave/runner.json`` declaration (and the unregistered key); the at-HEAD
        polyglot reason names only the competing lockfiles + the feature-scoped
        ``docs/feature/<id>/runner.json``.
        """
        ev = self.indeterminate_event()
        reason = None if ev is None else ev.get("reason")
        return reason if isinstance(reason, str) else ""

    def announced_polyglot_ambiguity(self) -> bool:
        """Did the gate refuse with the polyglot-ambiguity reason (D2 fall-back)?

        A honoured override RESOLVES the runner BEFORE the scan, so this LOUD
        "polyglot target" refusal is ABSENT -- its presence on a declared root is
        the at-HEAD symptom (the override was never consulted).
        """
        return "polyglot target" in self.combined

    def emitted_python_traceback(self) -> bool:
        """Did the gate crash with an uncaught Python traceback (the no-crash guard)?"""
        return "Traceback (most recent call last)" in self.combined

    # --- slice-04: D9 unrecognized -> pytest fallback observables ------------

    def fell_back_to_pytest(self) -> bool:
        """Did the whole-tree router treat an UNRECOGNIZED target as a pytest fallback?

        The D9 contract: a 0-lockfile (unrecognized) target must resolve the
        EXISTING pytest path -- ``WholeTreeRunnerResolved(runner="pytest",
        routed=False)`` -- NOT degrade to an ambiguous-runner refusal. At HEAD
        the routers degrade EVERY ``Indeterminate`` (including the 0-lockfile
        case) to exit-3, so no resolution event is emitted and this is False.
        """
        ev = self.resolution_event()
        return (
            ev is not None
            and ev.get("runner") == PYTEST_RUNNER
            and ev.get("routed") is False
        )

    def degraded_loud_indeterminate(self) -> bool:
        """Did the gate degrade LOUD to the whole-tree INDETERMINATE refusal?

        True iff the ``health.gate.whole-tree-runner.indeterminate`` marker was
        emitted OR the gate exited with the dedicated INDETERMINATE exit code.
        For an UNRECOGNIZED target (slice-04) this must be False (pytest
        fallback); for a POLYGLOT root with no declaration it must stay True (the
        D2/D8 path the fix must NOT over-correct).
        """
        return (
            self.indeterminate_event() is not None
            or self.exit_code == WHOLE_TREE_INDETERMINATE_EXIT
        )
