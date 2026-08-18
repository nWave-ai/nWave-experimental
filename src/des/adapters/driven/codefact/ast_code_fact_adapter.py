"""``AstAdapter`` — the per-language structural tier (ADR-LA-001 §5 tier 2).

The middle provider in the CodeFact fallback chain: more precise than the textual
floor, less precise than the paid Tsunami tier. It answers every stable-core
capability *structurally* by parsing the real source tree — and it does so by
DELEGATING to the sole testarch parser
(:class:`des.testarch.adapters.python_ast.PythonAstAdapter`, the ONLY code-query
``import ast`` site, ADR-TEST-002 D-A / C2). There is **NO second parser** here —
the AstAdapter never imports ``ast`` itself; it consumes only the plain-data
``TestSuiteAstAdapter`` Protocol queries.

It declares its TRUE confidence — ``approx`` (structural, never the floor's
``noisy``, never a faked ``binding-resolved``). A consumer reads the provenance in
the :class:`CodeFactResult` envelope; the confidence label IS the loud signal
(Invariant 2).

For a Python-only target this is the highest-precision tier the chain reaches when
the paid Tsunami tier is absent (the NORMAL case, ADR-LA-001 C7).
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
    CAPABILITY_SIMILAR_RESPONSIBILITY,
    TRACE_EXEMPLARS_MAX,
    Answered,
    CodeFactResult,
    Confidence,
    Failed,
    ManifestEntry,
    TraceEntry,
)
from des.testarch.adapters.python_ast import PythonAstAdapter


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from des.ports.code_fact_port import CapabilityDescriptor, Manifest
    from des.testarch.ports import TestSuiteAstAdapter


# A source file the structural tier parses. Python-only here (the reference
# adapter is ``PythonAstAdapter``); a target in another language wires its own
# per-language ``TestSuiteAstAdapter`` behind this same seam (genericità).
_PYTHON_SOURCE_GLOB = "*.py"

# A candidate's minimum name-token Jaccard overlap to be ranked at all (WS-9b
# similar-responsibility slice-01). Zero-overlap candidates (no shared
# name-token) are noise, never surfaced.
_SIMILAR_RESPONSIBILITY_OVERLAP_THRESHOLD = 0.0

# Every capability this structural tier can attempt (LOCKED stable core +
# additive similar-responsibility). Shared by ``probe`` (request-scoped
# availability) and ``manifest`` (the static coverage claim, ADR-LA-001 D2)
# so the two never drift apart.
_HANDLED_CAPABILITY_IDS = frozenset(
    {
        CAPABILITY_CALLERS_OF,
        CAPABILITY_READS_OF,
        CAPABILITY_NEVER_WIRED,
        CAPABILITY_ATOMS_IN_FILE,
        CAPABILITY_ADR_SECTION,
        CAPABILITY_SIMILAR_RESPONSIBILITY,
    }
)

# Matches a lowercase/digit-to-uppercase camelCase boundary, so
# ``parseFeatureDelta`` tokenizes the same as ``parse_feature_delta``.
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class _FaultObservation:
    """A local, per-call accumulator of THIS query's parse/read failures.

    Constructed fresh by :meth:`AstAdapter.query`/:meth:`AstAdapter.resolve`
    and threaded explicitly through the private query/read/parse plumbing as
    a plain parameter -- never stored on ``self`` -- so it carries no state
    across calls and is never a mutable adapter side-channel. Exemplars are
    capped at ``TRACE_EXEMPLARS_MAX`` at the point of recording, in file-
    traversal order (``TreeScope.files`` is sorted), so the first N faulting
    paths observed are always the same N for the same tree.
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


class AstAdapter:
    """Structural ``CodeFactPort`` tier; delegates to the sole testarch parser.

    Constructed with the ``root`` of the tree to parse. ``confidence`` is always
    :attr:`Confidence.APPROX` — the structural tier declares its true confidence
    and never inflates it to ``binding-resolved``. The parser is injected (the
    ``TestSuiteAstAdapter`` Protocol); the default is the Python reference adapter
    so a caller wiring ``AstAdapter(root=...)`` gets Python structural facts with
    NO second ``import ast``.
    """

    confidence = Confidence.APPROX.value
    provider = "ast"
    provider_id = "ast"

    def __init__(
        self, root: Path | str, parser: TestSuiteAstAdapter | None = None
    ) -> None:
        self._root = Path(root)
        self._parser: TestSuiteAstAdapter = parser or PythonAstAdapter()
        self._scope = TreeScope(self._root)
        self._parse_cache: dict[Path, tuple[object | None, bool]] = {}

    def scope_health_event(self) -> str | None:
        """``"unfiltered"`` / ``"filtered"`` / ``None`` — see :class:`TreeScope`.

        Read by :class:`CodeFactChain` after a query answered by this tier, to
        emit the degrade-LOUD ``health.gate.code-fact.*`` scan-scope signal.
        """
        return self._scope.health_event()

    # -- the CodeFactPort surface ------------------------------------------

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult | Failed:
        """Answer the stable-core capability named by ``descriptor`` structurally.

        Always returns a usable :class:`CodeFactResult` tagged ``ast`` @ ``approx``
        for the LOCKED stable core. Dispatches on the capability id; the structural
        payload is computed by parsing the real tree through the delegated
        ``TestSuiteAstAdapter`` — never a textual scan, never a faked
        ``binding-resolved``. An unknown id gets a usable (empty) structural answer
        rather than raising. The additive ``query.similar-responsibility``
        capability (ADR-LA-001 D9 slice (c)) can return :class:`Failed` instead —
        its "could not look" case is a real failure, never a fabricated empty
        answer.

        A throwaway :class:`_FaultObservation` absorbs this call's parse/read
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
    ) -> CodeFactResult | Failed:
        """The real dispatch, threading ``faults`` through the one traversal
        that computes the payload — never a second scan/parse/read to count
        faults separately from computing the answer."""
        symbol = self._symbol_of(request)
        if descriptor.id == CAPABILITY_NEVER_WIRED:
            return self._never_wired(symbol, faults)
        if descriptor.id == CAPABILITY_CALLERS_OF:
            return self._sites_of(symbol, faults, self._call_sites)
        if descriptor.id == CAPABILITY_READS_OF:
            return self._sites_of(symbol, faults, self._read_sites)
        if descriptor.id == CAPABILITY_ATOMS_IN_FILE:
            return self._atoms(faults)
        if descriptor.id == CAPABILITY_ADR_SECTION:
            return self._adr_section(symbol, faults)
        if descriptor.id == CAPABILITY_SIMILAR_RESPONSIBILITY:
            return self._similar_responsibility(request, faults)
        return self._answer(payload={"sites": []})

    def probe(
        self, request: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        """Per-capability manifest (ADR-LA-001 §3): the structural tier honors the
        stable core at ``approx`` confidence when the target contains Python
        source.  A non-Python target is not a Python-AST capability: reporting
        ``ok`` there would mask the language-agnostic textual floor with an
        honestly empty but operationally misleading structural answer.

        ``query.adr-section`` is a prose capability the structural tier degrades to
        a textual presence check (the parser has no notion of an ADR heading); the
        four code-structural capabilities (``callers-of`` / ``reads-of`` /
        ``never-wired`` / ``atoms-in-file``) are answered by parsing. Every entry
        honestly declares its ``approx`` confidence — never inflated.
        """
        available = bool(self._iter_files())
        if request is not None:
            available = available and self._request_is_python_scoped(request)
        return [
            {
                "capability_id": capability_id,
                "stability": "stable",
                "contract_version": "1.0.0",
                "ok": available,
            }
            for capability_id in sorted(_HANDLED_CAPABILITY_IDS)
        ]

    # -- the uniform CodeFactProvider protocol (ADR-LA-001 D2/D9) -----------

    def manifest(self) -> Manifest:
        """Static coverage claim (LA1-L2): every capability :meth:`probe`
        can attempt, at the declared ``approx`` confidence — unconditional,
        never scope- or request-qualified (that whole-scope honesty moves
        into :meth:`resolve`, LA1-L4)."""
        return tuple(
            ManifestEntry(capability_id=capability_id, confidence=self.confidence)
            for capability_id in sorted(_HANDLED_CAPABILITY_IDS)
        )

    def resolve(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> Answered | Failed:
        """Total over the observed scope (LA1-L4): ``Failed`` — never a
        partial Python-only answer dressed as complete — when this tier
        cannot honestly observe the whole requested scope (no Python source
        at all, or a non-Python file also named by the request); otherwise
        wraps :meth:`_query` (the GREEN_TO_GREEN thin edge convention: the
        payload carries the whole legacy :class:`CodeFactResult`, unwrapped
        byte-identical by the edge renderer) and reports the exact
        parse/read fault count + deterministic capped exemplars observed
        during THAT one traversal — never a second scan/parse/read to
        count them separately. ``_query`` can itself return a real
        :class:`Failed` (the additive similar-responsibility capability's
        "could not look" case, ADR-LA-001 D9 slice (c)) -- passed through
        unwrapped, never coerced into a fabricated ``Answered``."""
        request_dict = dict(request)
        available = bool(self._iter_files()) and self._request_is_python_scoped(
            request_dict
        )
        if not available:
            return Failed(
                cause="out-of-scope-language",
                trace=(
                    TraceEntry(
                        provider_id=self.provider_id,
                        event="failed:out-of-scope-language",
                        scope=self.scope_health_event() or "complete",
                        fault_count=0,
                        exemplars=(),
                        detail="",
                    ),
                ),
            )
        faults = _FaultObservation()
        result = self._query(descriptor, request_dict, faults)
        if isinstance(result, Failed):
            return result
        return Answered(
            provider_id=self.provider_id,
            confidence=result.confidence,
            payload=result,
            trace=(
                TraceEntry(
                    provider_id=self.provider_id,
                    event="answered",
                    scope=self.scope_health_event() or "complete",
                    fault_count=faults.fault_count,
                    exemplars=faults.exemplars,
                    detail="",
                ),
            ),
        )

    def _request_is_python_scoped(self, request: dict[str, object]) -> bool:
        """Whether Python AST can honestly cover this request's observed scope.

        A mixed repository may contain Python and another language.  For a
        symbol/anchor request, any occurrence in a non-Python file means the
        Python parser cannot claim the whole observed fact, so negotiation must
        continue to the textual floor.  Subject-free queries (currently atoms)
        require an all-Python scope for the same reason.

        This is conservative by design: the floor declares ``noisy`` rather
        than letting a precise-but-partial Python answer masquerade as the
        repository-wide result.
        """
        non_python_files = [
            path for path in self._scope.files("*.*") if path.suffix != ".py"
        ]
        if not non_python_files:
            return True
        subject = self._symbol_of(request)
        if not subject:
            return False
        return not any(subject in self._read(path) for path in non_python_files)

    # -- capability realizations (structural, via the delegated parser) ----

    def _never_wired(self, symbol: str, faults: _FaultObservation) -> CodeFactResult:
        """Is ``symbol`` a net-new symbol with no production call-site (structural)?

        Splits ``Owner.method`` and looks for a structural call-site of the trailing
        callable name (an ``ast.Call`` whose resolved callee names it) outside its
        own definition. A match → wired; no match → not wired. ADR-LA-001 D9 slice
        (c) / D6-R3: ``absent`` vs ``live-non-callable`` is owned by THIS payload's
        ``never_wired`` bool -- never a duplicated envelope-level field.
        """
        callable_name = self._callable_of(symbol)
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

    def _sites_of(
        self,
        symbol: str,
        faults: _FaultObservation,
        sites_fn: Callable[[str, _FaultObservation], list[str]],
    ) -> CodeFactResult:
        """The structural sites of ``symbol``'s trailing name, per ``sites_fn``
        (``_call_sites`` for ``callers-of``, ``_read_sites`` for ``reads-of``
        -- the two relations are structurally disjoint over the same source,
        see :meth:`des.testarch.adapters.python_ast.PythonAstAdapter.reads_in_function`).
        Whether ``sites`` is empty already tells the whole story -- no
        duplicated envelope-level reason code."""
        callable_name = self._callable_of(symbol)
        sites = sites_fn(callable_name, faults) if callable_name else []
        return self._answer(payload={"symbol": symbol, "sites": sites})

    def _atoms(self, faults: _FaultObservation) -> CodeFactResult:
        """The defined atoms (functions/classes/module-level constants) across
        the tree, parsed structurally.

        Combines three structural surfaces so a Reuse-Analysis citation of ANY
        of these kinds grounds, not only functions (F-fix-delta-grounding-
        incapacity-is-indeterminate slice-02, sister G-8): every function/
        method at any nesting depth (``functions_in_module`` -- UNCHANGED,
        byte-identical to before this slice), every MODULE-LEVEL class
        (``module_level_symbols_in_module`` filtered to ``kind == "class"`` --
        the same read-only sibling query WS-9b similar-responsibility already
        consumes, untouched here), and every MODULE-LEVEL simple assignment
        target (``module_level_assignment_targets_in_module``, e.g.
        ``LIMIT = 5`` -> ``"LIMIT"``).

        ``unparseable`` in the payload is the reason surface a content-grounding
        consumer (F-fix-delta-grounding-incapacity-is-indeterminate) reads to tell
        a genuine "no capable tier for this file's kind" INCAPACITY (every
        candidate file failed structural parse -- e.g. a non-Python source under
        this Python-AST tier) apart from a successful parse that simply defines
        zero atoms (ABSENT). ``False`` when there were no candidate files at all
        (nothing to be incapable of). This flag's semantics are UNCHANGED by the
        widened atom surface -- it signals parse capability, never symbol kind.
        """
        atoms: list[str] = []
        files = self._iter_files()
        parsed_any = False
        for source_file in files:
            tree = self._parse(source_file, faults)
            if tree is None:
                continue
            parsed_any = True
            atoms.extend(
                function.name for function in self._parser.functions_in_module(tree)
            )
            atoms.extend(
                symbol.name
                for symbol in self._parser.module_level_symbols_in_module(tree)
                if symbol.kind == "class"
            )
            atoms.extend(self._parser.module_level_assignment_targets_in_module(tree))
        return self._answer(
            payload={
                "atoms": sorted(set(atoms)),
                "unparseable": bool(files) and not parsed_any,
            },
        )

    def _adr_section(self, anchor: str, faults: _FaultObservation) -> CodeFactResult:
        """Prose-shaped: files whose text contains ``anchor`` (parser has no ADR notion).

        The structural tier degrades a prose capability to a textual presence check
        — it never fabricates a structural ADR-section answer it cannot compute.
        """
        matches: list[str] = []
        for source_file in self._iter_files():
            if anchor and anchor in self._read(source_file, faults):
                matches.append(source_file.name)
        return self._answer(payload={"anchor": anchor, "files": matches})

    def _similar_responsibility(
        self, request: dict[str, object], faults: _FaultObservation
    ) -> CodeFactResult | Failed:
        """Ranked EXISTING module-level ``def``/``class`` symbols whose structural
        fingerprint overlaps a proposed NEW symbol (WS-9b similar-responsibility
        slice-01).

        Parses every Python file under the root, collects each MODULE-LEVEL
        ``def``/``class`` symbol (delegated to
        ``module_level_symbols_in_module`` — no second parser), fingerprints
        each by its name-token set (identifier split on ``_``/camelCase,
        lowercased) plus its parameter arity, and ranks candidates whose
        Jaccard token overlap against the queried name exceeds the threshold
        (arity distance breaks ties; closer arity ranks first). A scope with
        ZERO parseable module-level symbols (nonexistent/empty/unparseable) is
        a real "could not look" -- :class:`Failed` (ADR-LA-001 D9 slice (c),
        D6-R3) -- never a fabricated empty candidate list that would look
        identical to a genuine "looked and found nothing" answer.

        ``unparsed_count`` in the payload / the ``Failed`` trace's
        ``fault_count`` (F-fix-find-similar-declares-unparseable-coverage) is
        the count of candidate files whose ``_parse`` returned ``None``
        during THIS same ranking pass -- no second parse. A
        genuinely-empty-but-parseable file (zero module-level symbols) never
        contributes to this count -- only a real parse failure does.
        """
        query_name = self._symbol_of(request)
        query_tokens = self._name_tokens(query_name)
        query_arity = request.get("arity")
        total_symbols = 0
        unparsed_count = 0
        ranked: list[tuple[float, int, dict[str, object]]] = []
        for source_file in self._iter_files():
            tree = self._parse(source_file, faults)
            if tree is None:
                unparsed_count += 1
                continue
            for symbol in self._parser.module_level_symbols_in_module(tree):
                total_symbols += 1
                if symbol.name == query_name:
                    continue
                overlap = self._token_overlap(query_tokens, symbol.name)
                if overlap <= _SIMILAR_RESPONSIBILITY_OVERLAP_THRESHOLD:
                    continue
                arity_distance = (
                    abs(symbol.arity - query_arity)
                    if isinstance(query_arity, int)
                    else 0
                )
                ranked.append(
                    (
                        overlap,
                        arity_distance,
                        {
                            "symbol": symbol.name,
                            "file": str(source_file),
                            "line": symbol.lineno,
                            "overlap": overlap,
                        },
                    )
                )
        if total_symbols == 0:
            return Failed(
                cause="unparseable-source",
                trace=(
                    TraceEntry(
                        provider_id=self.provider_id,
                        event="failed:unparseable-source",
                        scope=self.scope_health_event() or "complete",
                        fault_count=faults.fault_count,
                        exemplars=faults.exemplars,
                        detail="",
                    ),
                ),
            )
        ranked.sort(key=lambda entry: (-entry[0], entry[1]))
        return self._answer(
            payload={
                "candidates": [entry[2] for entry in ranked],
                "unparsed_count": unparsed_count,
            },
        )

    @staticmethod
    def _name_tokens(identifier: str) -> frozenset[str]:
        """The lowercase name-token set of ``identifier`` (split on ``_`` and
        camelCase boundaries) — the similar-responsibility fingerprint's name
        axis. ``""`` yields the empty set."""
        if not identifier:
            return frozenset()
        spaced = _CAMEL_BOUNDARY_RE.sub("_", identifier)
        return frozenset(token.lower() for token in spaced.split("_") if token)

    @classmethod
    def _token_overlap(cls, query_tokens: frozenset[str], candidate_name: str) -> float:
        """Jaccard overlap of ``query_tokens`` against ``candidate_name``'s own
        name-token set. Either side empty (e.g. an unnamed query) yields 0.0 —
        never a division by zero."""
        candidate_tokens = cls._name_tokens(candidate_name)
        if not query_tokens or not candidate_tokens:
            return 0.0
        intersection = query_tokens & candidate_tokens
        union = query_tokens | candidate_tokens
        return len(intersection) / len(union)

    # -- structural primitives (delegate-only, NO ``import ast`` here) ------

    def _call_sites(self, callable_name: str, faults: _FaultObservation) -> list[str]:
        """Every structural call SITE of ``callable_name``, one entry per occurrence.

        A call-site is an ``ast.Call`` whose resolved callee name equals (or ends
        with ``.``+) ``callable_name``. The function definition's ``name`` attribute
        is a plain string, not an ``ast.Call`` occurrence, so definition names are
        never mistaken for usages; recursive calls inside the body are real structural
        sites and are included. Resolution is structural via the delegated parser —
        never a textual ``name(`` regex. A file with N distinct calls contributes N
        entries here — never collapsed to one entry per FILE containing a call
        (D1: `consumer_counts` counts call sites, not files).
        """
        if not callable_name:
            return []
        sites: list[str] = []
        for source_file in self._iter_files():
            sites.extend(self._external_call_sites(source_file, callable_name, faults))
        return sites

    def _external_call_sites(
        self, source_file: Path, callable_name: str, faults: _FaultObservation
    ) -> list[str]:
        """Every ``"<file>:<lineno>"`` call-site location of ``callable_name``
        in ``source_file``.

        An unparseable ``source_file`` (``_parse`` returns ``None``) has no
        structural call-sites to report and degrades to an empty list. A
        recursive call site (inside ``callable_name``'s own definition) IS a
        real structural call-site and is reported here, never skipped — the
        function's ``name`` is a plain string, not an ``ast.Call``/``ast.Name``
        occurrence, so it can never itself be mistaken for a usage.
        """
        tree = self._parse(source_file, faults)
        if tree is None:
            return []
        locations: list[str] = []
        for function in self._parser.functions_in_module(tree):
            for call in self._parser.calls_in_function(tree, function):
                if self._callee_matches(call.callee, callable_name):
                    locations.append(f"{source_file}:{call.lineno}")
        return locations

    def _read_sites(self, name: str, faults: _FaultObservation) -> list[str]:
        """Every structural non-call read SITE of ``name``, one entry per occurrence.

        A read-site is a bare identifier reference (an ``ast.Name`` in ``Load``
        context) equal to ``name``. The symbol definition's ``name`` attribute is
        a plain string, not an ``ast.Name`` occurrence, so definition names are never
        mistaken for usages; recursive reads inside the body are real structural sites
        and are included. The SAME occurrence used as a call callee (``name()``) is a
        call-site, never a read-site (excluded structurally by the delegated parser's
        ``reads_in_function`` -- D1: ``reads-of`` and ``callers-of`` stay disjoint
        over the same source).
        """
        if not name:
            return []
        sites: list[str] = []
        for source_file in self._iter_files():
            sites.extend(self._external_read_sites(source_file, name, faults))
        return sites

    def _external_read_sites(
        self, source_file: Path, name: str, faults: _FaultObservation
    ) -> list[str]:
        """Every ``"<file>:<lineno>"`` read-site location of ``name`` in
        ``source_file``.

        An unparseable ``source_file`` has no structural read-sites to report
        and degrades to an empty list. A recursive read (a bare ``Load``
        reference to ``name`` inside ``name``'s own definition) IS a real
        structural read-site and is reported here, never skipped — the
        function's ``name`` is a plain string, not an ``ast.Name`` occurrence,
        so it can never itself be mistaken for a usage.
        """
        tree = self._parse(source_file, faults)
        if tree is None:
            return []
        locations: list[str] = []
        for function in self._parser.functions_in_module(tree):
            for read in self._parser.reads_in_function(tree, function):
                if read.name == name:
                    locations.append(f"{source_file}:{read.lineno}")
        return locations

    def _parse(
        self, source_file: Path, faults: _FaultObservation | None = None
    ) -> object | None:
        """Parse ``source_file`` into the opaque tree handle (delegated parser).

        Returns ``None`` when ``source_file`` is not valid Python (e.g. a real
        but non-Python file such as ``pyproject.toml`` or a ``.ts`` module) --
        the delegated parser's ``SyntaxError`` / ``ValueError`` is caught here
        so an unparseable citation degrades LOUD (an empty structural answer,
        already tagged ``approx``) instead of propagating an uncaught
        traceback through the whole ``CodeFactChain`` call stack
        (WS-9b, F-fix-reuse-analysis-content-grounding). Every caller of
        ``_parse`` MUST treat ``None`` as "no structural fact here" and skip
        the file, never re-raise.

        Cached per instance (the no-reparse-per-symbol contract) -- a file is
        READ and parsed at most once across every capability query this
        adapter instance answers, never once per queried symbol, and never
        twice to (re-)detect a fault. The cache carries a ``faulted`` flag
        alongside the tree, so a cache HIT for a query after the one that
        first read/parsed the file still honestly reports that file's fault
        into ``faults`` -- without repeating the read or the parse.
        """
        if source_file in self._parse_cache:
            tree, faulted = self._parse_cache[source_file]
            if faulted and faults is not None:
                faults.record(str(source_file))
            return tree
        probe = _FaultObservation()
        text = self._read(source_file, probe)
        faulted = probe.fault_count > 0
        try:
            tree = self._parser.parse(text, str(source_file))
        except (SyntaxError, ValueError):
            tree = None
            faulted = True
        self._parse_cache[source_file] = (tree, faulted)
        if faulted and faults is not None:
            faults.record(str(source_file))
        return tree

    @staticmethod
    def _callee_matches(callee: str, callable_name: str) -> bool:
        """True iff a resolved callee name names ``callable_name`` (bare or dotted)."""
        return callee == callable_name or callee.endswith(f".{callable_name}")

    @staticmethod
    def _callable_of(symbol: str) -> str:
        """The trailing callable name of an ``Owner.method`` symbol."""
        return symbol.rsplit(".", maxsplit=1)[-1] if symbol else ""

    def _iter_files(self) -> list[Path]:
        """Every Python source file under the root, ignore-derived-excluded and
        walked at most once per instance (delegated to :class:`TreeScope`,
        the shared floor-tier walk both ``AstAdapter`` and ``TextSearchAdapter``
        use)."""
        return self._scope.files(_PYTHON_SOURCE_GLOB)

    @staticmethod
    def _read(source_file: Path, faults: _FaultObservation | None = None) -> str:
        """Read a file's text, tolerating non-UTF-8 / binary content.

        A caught read failure is recorded into ``faults`` (when given) as
        this query's fault, at the exact file — never silently swallowed
        into an indistinguishable empty read.
        """
        try:
            return source_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            if faults is not None:
                faults.record(str(source_file))
            return ""

    @staticmethod
    def _symbol_of(request: dict[str, object]) -> str:
        """The symbol/anchor the request targets (``symbol`` or ``anchor`` fallback)."""
        for key in ("symbol", "anchor", "name"):
            value = request.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _answer(self, *, payload: object) -> CodeFactResult:
        """Wrap a structural payload in the ``ast`` @ ``approx``-tagged envelope
        (ADR-LA-001 §5a)."""
        return CodeFactResult(
            provider=self.provider,
            confidence=self.confidence,
            payload=payload,
        )
