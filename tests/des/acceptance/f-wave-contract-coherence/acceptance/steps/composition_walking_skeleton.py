"""Composition root for f-wave-contract-coherence slice-01 (walking skeleton).

DRIVING SURFACE (Mandate-13 driving-port-only -- ONE real surface, no
direct-domain testing):

  * Layer 3 composition (pure seam through its real read path) -- the REAL
    ``flavor_dispatcher`` resolving the DISCUSS gate stack from the SHIPPED
    canonical wave-contract registry ``nWave/waves/discuss.yaml`` in the repo.
    This is the DESIGN-declared net-new SOURCE move (brief §2 "dispatcher stack
    source"): the dispatcher's gate-stack source becomes the flavor-independent
    registry (default) instead of the flavor-private ``wave_gate_stacks`` block,
    with behaviour byte-identical to today (brief §3 SSOT-A). The observable is
    the ordered gate-id sequence the resolution returns for each boundary, read
    over the SHIPPED registry FILE -- I/O over the real filesystem (Mandate-14
    @real-io: the test would fail if the registry file is absent).

No production module is imported-and-called at the step boundary for its business
logic -- only the REAL ``flavor_dispatcher`` registry-resolution seam reads the
SHIPPED ``nWave/waves/discuss.yaml`` file.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DESIGN driving-surface declares
the load-bearing net-new seam reached from the dispatcher's real read path:

  (1) the canonical registry file ``nWave/waves/discuss.yaml`` carrying the
      ``gate_stack`` SSOT-A (brief §3) -- the DATA home of the migrated stack.
  (2) the dispatcher resolving the DISCUSS gate stack FROM that registry as the
      DEFAULT source (brief §2 / feature-delta DD-6: the dispatcher's stack source
      becomes the registry default) -- the re-pointed read path.

Each slice-01 AT NAMES one of these seams, drives it through the REAL resolution
read path, and asserts an observable effect (the resolved gate-id sequence).

INDUCED SEAM NAME (faithful, NOT crafter-matches-design contract):
``flavor_dispatcher.resolve_wave_gate_stack_from_registry`` is induced from the
existing ``resolve_wave_gate_stack`` sibling (same module, same row schema) + the
brief §2 "dispatcher stack source becomes the registry default". The crafter MUST
reconcile the concrete registry-resolution entry against the DESIGN before
GREENing -- if the crafter re-points the EXISTING ``resolve_wave_gate_stack`` to
read the registry instead of adding a new function, update ``_REGISTRY_RESOLVERS``
here to match. The ASSERTION (the DISCUSS stack is sourced from the registry and
preserves the gate-id sequence in force today) is the contract; the literal entry
name is the late-bound detail.

slice-06 retarget (MOVE-completion): the registry ``nWave/waves/discuss.yaml`` is now
shipped and the spine ``wave_gate_stack_dispatch.resolve_stack`` is wired to it, so the
walking skeleton is GREEN. AT-3's "sequence in force today" oracle was retargeted from
the now-DELETED flavor-private ``wave_gate_stacks.discuss`` block (the source the move
came FROM) to a two-independent-reads cross-check: the sequence DECLARED in the registry
FILE (direct stdlib parse) == the sequence the WIRED spine ``resolve_stack`` resolves
(the live PreToolUse / SubagentStop path, pre_tool_use_service.py:327). Agreement proves
resolve_stack reads the registry and returns the declared sequence -- not registry==registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import WaveBoundary


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The SHIPPED canonical wave-contract registry dir (ADR-FLOW-006 D1).
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DISCUSS_REGISTRY_FILE = _WAVES_DIR / "discuss.yaml"

# The DISCUSS-wave being migrated to the canonical registry.
_DISCUSS_WAVE = "discuss"


def _discuss_sequence_declared_in_registry_file(
    boundary: WaveBoundary,
) -> tuple[str, ...]:
    """Read the DISCUSS gate-id sequence DIRECTLY from the registry FILE.

    Independent read #1 of the AT-3 two-reads cross-check: a direct stdlib parse
    of the SHIPPED ``nWave/waves/discuss.yaml`` file, walking ``gate_stack[boundary]``
    WITHOUT going through the spine. This is the DECLARED sequence -- what a
    maintainer authored in the registry.

    slice-06 retarget: the migration MOVED the gate-stack source from the now-DELETED
    flavor-private ``wave_gate_stacks.discuss`` block to this registry file, and the
    spine (``wave_gate_stack_dispatch.resolve_stack``) was re-pointed to read it. The
    old AT-3 oracle read the flavor block (the source the move came FROM); that source
    is gone. The "sequence in force today" is now what the registry FILE declares, read
    here independently of the spine so AT-3 stays a genuine two-independent-reads
    cross-check (registry-FILE-declared == spine-resolved), never registry==registry.
    """
    if not _DISCUSS_REGISTRY_FILE.is_file():
        return ()
    # mandate-13-ok: same stdlib-only subset parser flavor_dispatcher uses, but
    # invoked DIRECTLY on the file here -- this read does NOT pass through the spine,
    # so it is independent of resolve_stack (the wired path read #2 exercises).
    from des._internal import subset_parser

    try:
        doc = subset_parser.load_file(_DISCUSS_REGISTRY_FILE)
    except (ValueError, OSError):
        return ()
    if not isinstance(doc, dict):
        return ()
    gate_stack = doc.get("gate_stack")
    if not isinstance(gate_stack, dict):
        return ()
    rows = gate_stack.get(boundary.value)
    if not isinstance(rows, list):
        return ()
    return tuple(
        str(row["gate_id"])
        for row in rows
        if isinstance(row, dict) and "gate_id" in row
    )


def _discuss_sequence_resolved_by_spine(boundary: WaveBoundary) -> tuple[str, ...]:
    """Resolve the DISCUSS gate-id sequence through the WIRED spine entry.

    Independent read #2 of the AT-3 two-reads cross-check: drives the REAL
    ``wave_gate_stack_dispatch.resolve_stack(wave, boundary)`` -- the entry the live
    PreToolUse / SubagentStop callers use (pre_tool_use_service.py:327 imports it as
    ``wgs`` and calls ``wgs.resolve_stack(wave, "gate-in")``). This is the wired path
    the walking skeleton proves end-to-end: resolve_stack must actually READ the
    registry and RETURN the declared sequence. Comparing this against the directly-read
    registry FILE sequence proves the registry -> dispatcher wiring, not a tautology.
    """
    from des.application import wave_gate_stack_dispatch

    resolved = wave_gate_stack_dispatch.resolve_stack(_DISCUSS_WAVE, boundary.value)
    return tuple(
        str(row["gate_id"])
        for row in resolved.rows
        if isinstance(row, dict) and "gate_id" in row
    )


# Candidate dispatcher entries that resolve a wave's gate stack FROM the registry.
# The DESIGN re-points the dispatcher stack source to the registry default; the
# concrete entry is one of these (induced from the existing sibling + the brief).
# Whichever the crafter ships, the resolution is driven through the REAL module.
_REGISTRY_RESOLVER_NAMES: tuple[str, ...] = (
    "resolve_wave_gate_stack_from_registry",
    "resolve_wave_contract_gate_stack",
)


@dataclass
class WaveContractRegistryComposition:
    """Drives the DISCUSS gate-stack resolution through the REAL registry read path."""

    _contract: dict[str, object] | None = field(default=None)
    _contract_read: bool = field(default=False)
    _resolved_stack: list[dict[str, object]] | None = field(default=None)
    _resolved_boundary: WaveBoundary | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_discuss_registry_file_is_shipped(self) -> None:
        """Arm the SUT to read the SHIPPED canonical registry file from the repo.

        No fixture authoring of the expected output -- the registry FILE is the
        shipped artifact the SUT reads (Mandate-13 protocol-driver: assert a shipped
        artifact, never a string the test fabricated). At HEAD the file is absent;
        the absence is the RED.
        """
        # Nothing to set up beyond pointing at the shipped path -- the file itself
        # (or its absence) is the contract under test.

    # ---- when ---------------------------------------------------------------

    def when_maintainer_reads_discuss_wave_contract_from_registry(self) -> None:
        """Read the DISCUSS wave-contract from the SHIPPED registry via the REAL parser.

        Drives the production stdlib-only subset parser the dispatcher uses
        (``des._internal.subset_parser`` / ``flavor_dispatcher._parse_flavor_file``)
        over the SHIPPED ``nWave/waves/discuss.yaml``. At HEAD the file is absent ->
        the contract stays None -> the Then fires a semantic AssertionError naming
        the missing registry file.
        """
        self._contract_read = True
        self._contract = self._read_discuss_registry_contract()

    def when_dispatcher_resolves_discuss_stack_from_registry(
        self, boundary: WaveBoundary
    ) -> None:
        """Drive the REAL dispatcher resolving the DISCUSS stack FROM the registry.

        Reaches the dispatcher's registry-resolution read path (the DESIGN-declared
        re-pointed source) for the DISCUSS wave + boundary, reading the SHIPPED
        registry dir. At HEAD no registry-resolution entry exists / the registry dir
        is absent -> the resolved stack is empty -> the Then fires a semantic
        AssertionError naming the missing registry-resolution seam.
        """
        self._resolved_boundary = boundary
        self._resolved_stack = self._resolve_stack_from_registry(boundary)

    # ---- then: AT-1 (registry declares the gate stack) -----------------------

    def then_discuss_contract_declares_gate_stack_with_both_boundaries(self) -> None:
        """The DISCUSS wave-contract carries a gate_stack with gate-in + gate-out.

        Seam-named oracle (Mandate-15 seam #1): the SHIPPED registry file must carry
        the ``gate_stack`` SSOT-A with both wave boundaries (brief §3). RED at HEAD:
        ``nWave/waves/discuss.yaml`` does not exist -> the contract is None ->
        semantic AssertionError naming the missing registry file.
        """
        assert self._contract_read, (
            "the DISCUSS wave-contract must be read (When) before asserting (Then)"
        )
        assert self._contract is not None, (
            "the canonical DISCUSS wave-contract registry file must be shipped at "
            f"{_DISCUSS_REGISTRY_FILE} (ADR-FLOW-006 D1: one flavor-independent file "
            "per wave carrying the gate_stack SSOT-A) -- it does not exist yet, so "
            f"the contract could not be read. {self._observed()}"
        )
        gate_stack = self._contract.get("gate_stack")
        assert isinstance(gate_stack, dict), (
            "the DISCUSS wave-contract must declare a `gate_stack` mapping (SSOT-A, "
            f"ADR-FLOW-006 D2); got gate_stack={gate_stack!r}. {self._observed()}"
        )
        for boundary in (WaveBoundary.GATE_IN, WaveBoundary.GATE_OUT):
            rows = gate_stack.get(boundary.value)
            assert isinstance(rows, list) and rows, (
                f"the DISCUSS gate_stack must declare a non-empty `{boundary.value}` "
                "boundary (the gate-stack SSOT carries BOTH boundaries, brief §3); "
                f"got {boundary.value}={rows!r}. {self._observed()}"
            )

    # ---- then: AT-2 (the dispatcher sources the stack from the registry) ------

    def then_resolved_stack_is_sourced_from_registry_and_nonempty(
        self, boundary: WaveBoundary
    ) -> None:
        """The dispatcher resolves a NON-EMPTY DISCUSS stack FROM the registry.

        Seam-named oracle (Mandate-15 seam #2): the dispatcher's registry-resolution
        read path returns the declared stack for the boundary. RED at HEAD: no
        registry-resolution entry reads ``nWave/waves/`` -> the resolved stack is the
        empty list -> semantic AssertionError naming the missing registry-source seam.
        """
        self._assert_then_boundary_matches_when(boundary)
        stack = self._resolved_stack or []
        assert stack, (
            f"the dispatcher must resolve the DISCUSS {self._resolved_boundary.value} "
            "stack FROM the canonical registry as the default source (brief §2 / "
            "feature-delta DD-6: the dispatcher stack source becomes the registry "
            "default), via one of "
            f"flavor_dispatcher.{{{', '.join(_REGISTRY_RESOLVER_NAMES)}}} over "
            f"{_WAVES_DIR} -- it resolved EMPTY (no registry-resolution read path / "
            f"the registry dir is absent). {self._observed()}"
        )

    # ---- then: AT-3 (behaviour byte-identical to the stack in force today) ----

    def then_resolved_sequence_equals_sequence_in_force_today(
        self, boundary: WaveBoundary
    ) -> None:
        """The spine-resolved gate-id sequence equals the registry-FILE-declared one.

        Walking-skeleton end-to-end wiring proof (Mandate-15 seam #2): two INDEPENDENT
        reads of the DISCUSS gate-id sequence must agree --

          (read #1) the sequence DECLARED in the registry FILE, read directly with the
                    stdlib subset parser (``_discuss_sequence_declared_in_registry_file``),
                    NOT through the spine; and
          (read #2) the sequence the WIRED spine entry resolves
                    (``wave_gate_stack_dispatch.resolve_stack``, the live PreToolUse /
                    SubagentStop path).

        Agreement proves resolve_stack ACTUALLY reads the registry and returns the
        declared sequence (the walking skeleton's job: registry -> dispatcher wiring) --
        NOT registry==registry (the two reads use different code paths). The sequence
        must also be NON-EMPTY, so a both-empty trivial pass cannot satisfy it.

        slice-06 retarget: the old oracle read the now-DELETED flavor-private
        ``wave_gate_stacks.discuss`` block as "in force today"; that source is gone. The
        live source is the spine (registry-sourced after the MOVE), cross-checked against
        the independently-read registry FILE.
        """
        self._assert_then_boundary_matches_when(boundary)
        declared = _discuss_sequence_declared_in_registry_file(boundary)
        resolved = _discuss_sequence_resolved_by_spine(boundary)
        assert declared, (
            f"the DISCUSS {boundary.value} gate stack must be DECLARED (non-empty) in "
            f"the registry file {_DISCUSS_REGISTRY_FILE} -- read #1 of the wiring proof "
            f"resolved EMPTY (registry file absent / boundary missing). {self._observed()}"
        )
        assert resolved == declared, (
            f"the WIRED spine entry wave_gate_stack_dispatch.resolve_stack must resolve "
            f"the DISCUSS {boundary.value} stack to the SAME gate-id sequence the "
            "registry FILE declares (walking-skeleton end-to-end wiring, AT-3) -- two "
            "independent reads (registry-FILE-declared vs spine-resolved) must agree, "
            "proving resolve_stack reads the registry, not registry==registry; "
            f"declared {declared!r}, spine-resolved {resolved!r}. {self._observed()}"
        )

    def _assert_then_boundary_matches_when(self, boundary: WaveBoundary) -> None:
        """Guard: the Then's parsed boundary must match the boundary resolved in When.

        Binds each Then explicitly to its scenario-outline <boundary> row (so the
        per-boundary parameter is USED, not silently dropped) and catches a When/Then
        wiring drift in the parametrized shape.
        """
        assert self._resolved_boundary is not None, (
            "the dispatcher resolution must run (When) before asserting (Then)"
        )
        assert self._resolved_boundary is boundary, (
            f"Then boundary {boundary.value!r} must match the boundary resolved in "
            f"When ({self._resolved_boundary.value!r}) -- scenario-outline wiring drift"
        )

    # ---- registry read path (the REAL resolution seam) -----------------------

    def _read_discuss_registry_contract(self) -> dict[str, object] | None:
        """Parse the SHIPPED DISCUSS registry file via the production subset parser.

        At HEAD the file is absent -> returns None (the RED). Uses the SAME
        stdlib-only parser the dispatcher reads flavor files with, so the AT exercises
        the real parse path, not a test-local YAML reader.
        """
        if not _DISCUSS_REGISTRY_FILE.is_file():
            return None
        # mandate-13-ok: same parse path flavor_dispatcher._parse_flavor_file uses
        # (des._internal.subset_parser) -- the production reader, not a test-local
        # YAML parser; the AT exercises the real registry parse path.
        from des._internal import subset_parser

        try:
            doc = subset_parser.load_file(_DISCUSS_REGISTRY_FILE)
        except (ValueError, OSError):
            return None
        return doc if isinstance(doc, dict) else None

    def _resolve_stack_from_registry(
        self, boundary: WaveBoundary
    ) -> list[dict[str, object]]:
        """Drive the REAL dispatcher resolving the DISCUSS stack from the registry.

        Looks up the registry-resolution entry on the REAL ``flavor_dispatcher``
        module (induced names; the crafter binds the concrete one) and drives it over
        the SHIPPED registry dir. At HEAD no such entry exists -> returns the empty
        list so the caller's Then fires a semantic AssertionError naming the missing
        seam (RED-for-right-reason).
        """
        from des.application import flavor_dispatcher

        resolver = None
        for name in _REGISTRY_RESOLVER_NAMES:
            candidate = getattr(flavor_dispatcher, name, None)
            if callable(candidate):
                resolver = candidate
                break
        if resolver is None:
            return []
        try:
            stack = resolver(
                _DISCUSS_WAVE,
                boundary.value,
                waves_dir=_WAVES_DIR,
            )
        except TypeError:
            # The crafter's concrete signature differs from the induced one; the
            # ASSERTION is the contract, the signature is late-bound. Try the
            # positional form the existing sibling uses.
            try:
                stack = resolver(_DISCUSS_WAVE, boundary.value, _WAVES_DIR)
            except (TypeError, KeyError, ValueError, FileNotFoundError):
                return []
        except (KeyError, ValueError, FileNotFoundError):
            return []
        return [row for row in stack if isinstance(row, dict)]

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"registry_file_exists={_DISCUSS_REGISTRY_FILE.is_file()}; "
            f"waves_dir={_WAVES_DIR}; contract={self._contract!r}; "
            f"resolved_stack={self._resolved_stack!r}; "
            f"resolved_boundary={self._resolved_boundary!r}"
        )
