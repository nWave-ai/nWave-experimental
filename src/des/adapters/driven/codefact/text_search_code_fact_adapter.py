"""``TextSearchAdapter`` — the pure-Python universal floor (ADR-LA-001 §5 tier 3).

The weakest, always-present provider in the CodeFact fallback chain. It answers
every stable-core capability *textually* by scanning real files with stdlib ``re``
+ ``pathlib`` — **NOT** the ``grep`` binary, honoring the git-free / tool-free /
Python-only mandate. It is language-agnostic and zero-dependency, so it answers
even for a language with no ``AstAdapter``.

It declares its TRUE (lowest) confidence — ``noisy`` — never inflated, and it
ALWAYS returns a usable :class:`CodeFactResult` (a non-empty payload): name
matching can produce false positives/negatives (ADR-LA-001 Consequences, the
honest tradeoff), but the answer is never silent-green and never a false-fail
dressed as certainty — the lower-confidence provenance is in the envelope.

This is the load-bearing "there is ALWAYS a usable answer" floor of slice-01.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.codefact.tree_scope import TreeScope
from des.ports.code_fact_port import (
    CAPABILITY_ADR_SECTION,
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_CALLERS_OF,
    CAPABILITY_NEVER_WIRED,
    CAPABILITY_READS_OF,
    STABLE_CORE_CAPABILITY_IDS,
    TRACE_EXEMPLARS_MAX,
    Answered,
    CapabilityDescriptor,
    CodeFactResult,
    Confidence,
    Manifest,
    ManifestEntry,
    TraceEntry,
)


if TYPE_CHECKING:
    from collections.abc import Mapping


# A defined atom (function / class) — ``def name`` or ``class name`` — matched
# textually. Language-agnostic enough for the C-family / Python; the floor never
# pretends to a parser's precision (that is the AstAdapter's ``approx`` tier).
_ATOM_DEFINITION = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|func|fn|function)\s+"
    r"([A-Za-z_]\w*)",
    re.MULTILINE,
)

# A source file the floor scans. Kept broad (the floor is language-agnostic);
# the textual scan tolerates non-source files (they simply contribute no atoms).
_SOURCE_GLOB = "*.*"


class _FaultObservation:
    """A local, per-call accumulator of THIS query's read failures.

    Constructed fresh by :meth:`TextSearchAdapter.query`/:meth:`resolve` and
    threaded explicitly through the private query/read plumbing as a plain
    parameter -- never stored on ``self`` -- so it carries no state across
    calls and is never a mutable adapter side-channel. Exemplars are capped
    at ``TRACE_EXEMPLARS_MAX`` at the point of recording, in file-traversal
    order (``TreeScope.files`` is sorted), so the first N faulting paths
    observed are always the same N for the same tree.
    """

    __slots__ = ("_exemplars", "fault_count")

    def __init__(self) -> None:
        self.fault_count = 0
        self._exemplars: list[str] = []

    def record(self, path: str) -> None:
        self.fault_count += 1
        if len(self._exemplars) < TRACE_EXEMPLARS_MAX:
            self._exemplars.append(path)

    @property
    def exemplars(self) -> tuple[str, ...]:
        return tuple(self._exemplars)


def _strip_own_declaration(text: str, callable_name: str) -> str:
    """Remove every `_ATOM_DEFINITION` span declaring exactly ``callable_name``.

    The single definition observation/SSOT: a call-site scan must never count
    a symbol's own declaration against itself, for every atom form
    `_ATOM_DEFINITION` recognizes (not a second, independently-drifting
    grammar). Only spans whose captured name matches ``callable_name`` are
    stripped -- an unrelated declaration elsewhere is left untouched.
    """
    pieces: list[str] = []
    cursor = 0
    for match in _ATOM_DEFINITION.finditer(text):
        if match.group(1) != callable_name:
            continue
        pieces.append(text[cursor : match.start()])
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


class TextSearchAdapter:
    """Pure-Python ``re``/``pathlib`` floor; answers stable-core capabilities textually.

    Constructed with the ``root`` of the tree to scan. ``confidence`` is always
    :attr:`Confidence.NOISY` — the floor declares its true confidence and never
    inflates it.
    """

    confidence = Confidence.NOISY.value
    provider = "textsearch"
    provider_id = "textsearch"

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._scope = TreeScope(self._root)
        self._read_cache: dict[Path, tuple[str, bool]] = {}

    def scope_health_event(self) -> str | None:
        """``"unfiltered"`` / ``"filtered"`` / ``None`` — see :class:`TreeScope`.

        Read by :class:`CodeFactChain` after a query answered by this tier, to
        emit the degrade-LOUD ``health.gate.code-fact.*`` scan-scope signal.
        """
        return self._scope.health_event()

    # -- the CodeFactPort surface ------------------------------------------

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult:
        """Answer the stable-core capability named by ``descriptor`` textually.

        Always returns a usable :class:`CodeFactResult` tagged ``textsearch`` @
        ``noisy``. Dispatches on the LOCKED capability id; an unknown id still
        gets a usable (empty-match) textual answer rather than raising — the floor
        never refuses (the universal-floor invariant).

        A throwaway :class:`_FaultObservation` absorbs this call's read
        faults (the public payload never carries them) — :meth:`resolve` is
        the one caller that keeps the observation, so this method stays
        observationally identical to before fault observation existed.
        """
        return self._query(descriptor, request, _FaultObservation())

    def _query(
        self,
        descriptor: CapabilityDescriptor,
        request: dict[str, object],
        faults: _FaultObservation,
    ) -> CodeFactResult:
        """The real dispatch, threading ``faults`` through the one traversal
        that computes the payload — never a second scan/read to count
        faults separately from computing the answer."""
        symbol = self._symbol_of(request)
        if descriptor.id == CAPABILITY_NEVER_WIRED:
            return self._never_wired(symbol, faults)
        if descriptor.id == CAPABILITY_CALLERS_OF:
            return self._sites_of(symbol, faults)
        if descriptor.id == CAPABILITY_READS_OF:
            return self._reads_of(symbol, faults)
        if descriptor.id == CAPABILITY_ATOMS_IN_FILE:
            return self._atoms(faults)
        if descriptor.id == CAPABILITY_ADR_SECTION:
            return self._adr_section(symbol, faults)
        # Unknown id: a usable, honestly-empty textual answer (never refuse).
        return self._answer(payload={"matches": []})

    def probe(self) -> list[dict[str, object]]:
        """Per-capability manifest (ADR-LA-001 §3): the floor honors all stable core.

        Every stable-core capability is answerable textually, so each appears with
        ``ok=True``. The floor honestly declares ``noisy`` confidence; a consumer
        reads this to know the floor covers the stable core on any Python-only
        target.
        """
        return [
            {
                "capability_id": capability_id,
                "stability": "stable",
                "contract_version": "1.0.0",
                "ok": True,
            }
            for capability_id in sorted(
                {
                    CAPABILITY_CALLERS_OF,
                    CAPABILITY_READS_OF,
                    CAPABILITY_NEVER_WIRED,
                    CAPABILITY_ATOMS_IN_FILE,
                    CAPABILITY_ADR_SECTION,
                }
            )
        ]

    # -- the uniform CodeFactProvider protocol (ADR-LA-001 D2/D9) -----------

    def manifest(self) -> Manifest:
        """Static coverage claim (LA1-L2): the floor honors all stable core.

        Unconditional — the textual floor never depends on the target
        containing a particular language (the universal-floor invariant),
        so this claim needs no request to be honest.
        """
        return tuple(
            ManifestEntry(capability_id=capability_id, confidence=self.confidence)
            for capability_id in sorted(STABLE_CORE_CAPABILITY_IDS)
        )

    def resolve(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> Answered:
        """Always answers (the floor never refuses); wraps :meth:`_query`.

        The payload carries the whole legacy :class:`CodeFactResult` so the
        edge renderer can unwrap it; D9 slice (c) / D6-R3 relocated
        ``reason_code`` into capability payload schemas (e.g.
        ``never-wired``'s ``never_wired`` bool) — no envelope-level field.
        Reports the exact read-fault count + deterministic capped exemplars
        observed during that one traversal — never a second scan/read to
        count them separately.
        """
        faults = _FaultObservation()
        result = self._query(descriptor, dict(request), faults)
        scope = self.scope_health_event() or "complete"
        return Answered(
            provider_id=self.provider_id,
            confidence=result.confidence,
            payload=result,
            trace=(
                TraceEntry(
                    provider_id=self.provider_id,
                    event="answered",
                    scope=scope,
                    fault_count=faults.fault_count,
                    exemplars=faults.exemplars,
                    detail="",
                ),
            ),
        )

    # -- capability realizations (textual, stdlib only) --------------------

    def _never_wired(self, symbol: str, faults: _FaultObservation) -> CodeFactResult:
        """Is ``symbol`` a net-new symbol with no production call-site?

        Splits ``Owner.method`` and scans for a textual call-site of the trailing
        callable name outside its own definition file. A match → wired; no match
        → not wired. ADR-LA-001 D9 slice (c) / D6-R3: the ``never_wired`` bool
        below IS the disambiguating signal — never a duplicated envelope field.
        """
        callable_name = symbol.rsplit(".", maxsplit=1)[-1]
        call_sites = self._call_sites(callable_name, faults)
        if call_sites:
            return self._answer(
                payload={
                    "symbol": symbol,
                    "never_wired": False,
                    "call_sites": call_sites,
                },
            )
        return self._answer(
            payload={"symbol": symbol, "never_wired": True, "call_sites": []},
        )

    def _sites_of(self, symbol: str, faults: _FaultObservation) -> CodeFactResult:
        """The textual call sites of ``symbol``'s trailing name — an empty
        ``sites`` list already discriminates, no envelope-level reason code
        needed."""
        callable_name = symbol.rsplit(".", maxsplit=1)[-1] if symbol else ""
        sites = self._call_sites(callable_name, faults) if callable_name else []
        return self._answer(payload={"symbol": symbol, "sites": sites})

    def _reads_of(self, symbol: str, faults: _FaultObservation) -> CodeFactResult:
        """The textual non-call READ sites of ``symbol``'s trailing name.

        Distinct from :meth:`_sites_of` (call sites): a bare reference such as
        an assignment (``const observed = target;``) is a read, never a call,
        so it must surface here even when `_call_sites` reports none.
        """
        callable_name = symbol.rsplit(".", maxsplit=1)[-1] if symbol else ""
        sites = self._read_sites(callable_name, faults) if callable_name else []
        return self._answer(payload={"symbol": symbol, "sites": sites})

    def _atoms(self, faults: _FaultObservation) -> CodeFactResult:
        """The defined atoms (functions/classes) across the scanned tree, textually."""
        atoms: list[str] = []
        for source_file in self._iter_files():
            atoms.extend(_ATOM_DEFINITION.findall(self._read(source_file, faults)))
        return self._answer(payload={"atoms": sorted(set(atoms))})

    def _adr_section(self, anchor: str, faults: _FaultObservation) -> CodeFactResult:
        """Text-shaped: the lines following a heading whose text contains ``anchor``."""
        matches: list[str] = []
        for source_file in self._iter_files():
            text = self._read(source_file, faults)
            if anchor and anchor in text:
                matches.append(source_file.name)
        return self._answer(payload={"anchor": anchor, "files": matches})

    # -- textual primitives ------------------------------------------------

    def _call_sites(self, callable_name: str, faults: _FaultObservation) -> list[str]:
        """Every textual ``<callable_name>(`` call SITE, one entry per occurrence.

        A declaration line is NOT a call-site; a ``.flush(`` or bare ``flush(``
        usage is. The declaration observation is `_ATOM_DEFINITION` itself (the
        single SSOT for "what counts as a declaration") — its captured symbol
        is compared to ``callable_name`` and only a matching declaration span is
        stripped before the call pattern scans, so every declaration form the
        floor claims as an atom (``def``/``class``/``func``/``fn``/``function``,
        with ``export``/``async`` prefixes) is honored language-agnostically,
        never just the subset a second, drifted grammar happened to recognize.
        Name matching only (the floor's declared-``noisy`` limitation, ADR-LA-001
        Consequences). A file with N distinct occurrences contributes N entries
        here — never collapsed to one entry per FILE containing a call (D1:
        `consumer_counts` counts call sites, not files; the AST tier applies the
        same rule).
        """
        if not callable_name:
            return []
        call_pattern = re.compile(rf"(?<![\w.]){re.escape(callable_name)}\s*\(")
        hits: list[str] = []
        for source_file in self._iter_files():
            text = self._read(source_file, faults)
            without_defs = _strip_own_declaration(text, callable_name)
            hits.extend(
                f"{source_file}:{match.start()}"
                for match in call_pattern.finditer(without_defs)
            )
        return hits

    def _read_sites(self, callable_name: str, faults: _FaultObservation) -> list[str]:
        """Every textual non-call READ occurrence of ``callable_name``.

        An identifier-boundary occurrence that is neither a declaration (the
        `_ATOM_DEFINITION` SSOT, stripped via `_strip_own_declaration` exactly
        as `_call_sites` does) nor immediately followed by call syntax (the
        `_call_sites` shape) -- e.g. a bare reference or assignment such as
        ``const observed = target;``. The read relation is language-neutral
        and intentionally disjoint from `_call_sites`: a name used as a call
        is not counted here, and vice versa. ``\\b`` anchors both ends so a
        longer identifier sharing ``callable_name`` as a substring (``target2``,
        ``retarget``) never false-positives.
        """
        if not callable_name:
            return []
        read_pattern = re.compile(rf"(?<![\w.]){re.escape(callable_name)}\b(?!\s*\()")
        hits: list[str] = []
        for source_file in self._iter_files():
            text = self._read(source_file, faults)
            without_defs = _strip_own_declaration(text, callable_name)
            hits.extend(
                f"{source_file}:{match.start()}"
                for match in read_pattern.finditer(without_defs)
            )
        return hits

    def _iter_files(self) -> list[Path]:
        """Every file under the root, ignore-derived-excluded and walked at
        most once per instance (delegated to :class:`TreeScope`, the shared
        floor-tier walk both ``TextSearchAdapter`` and ``AstAdapter`` use --
        NOT ``grep``)."""
        return self._scope.files(_SOURCE_GLOB)

    def _read(self, source_file: Path, faults: _FaultObservation | None = None) -> str:
        """Read a file's text, tolerating non-UTF-8 / binary content.

        Cached per instance (the no-reparse-per-symbol contract) -- a file is
        read at most once across every capability query this adapter instance
        answers, never once per queried symbol, and never twice to
        (re-)detect a fault. The cache carries a ``faulted`` flag alongside
        the text, so a cache HIT for a query after the one that first read
        the file still honestly reports that file's fault into ``faults`` --
        without repeating the read.
        """
        if source_file in self._read_cache:
            text, faulted = self._read_cache[source_file]
            if faulted and faults is not None:
                faults.record(str(source_file))
            return text
        try:
            text = source_file.read_text(encoding="utf-8")
            faulted = False
        except (UnicodeDecodeError, OSError):
            text = ""
            faulted = True
        self._read_cache[source_file] = (text, faulted)
        if faulted and faults is not None:
            faults.record(str(source_file))
        return text

    @staticmethod
    def _symbol_of(request: dict[str, object]) -> str:
        """The symbol/anchor the request targets (``symbol`` or ``root`` fallback)."""
        for key in ("symbol", "anchor", "name"):
            value = request.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _answer(self, *, payload: object) -> CodeFactResult:
        """Wrap a textual payload in the ``textsearch`` @ ``noisy``-tagged envelope
        (ADR-LA-001 §5a)."""
        return CodeFactResult(
            provider=self.provider,
            confidence=self.confidence,
            payload=payload,
        )
