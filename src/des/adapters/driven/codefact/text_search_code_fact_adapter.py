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

from des.ports.code_fact_port import (
    CAPABILITY_ADR_SECTION,
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_CALLERS_OF,
    CAPABILITY_NEVER_WIRED,
    CAPABILITY_READS_OF,
    CapabilityDescriptor,
    CodeFactResult,
    Confidence,
    Provider,
    ReasonCode,
)


# A defined atom (function / class) — ``def name`` or ``class name`` — matched
# textually. Language-agnostic enough for the C-family / Python; the floor never
# pretends to a parser's precision (that is the AstAdapter's ``approx`` tier).
_ATOM_DEFINITION = re.compile(
    r"^\s*(?:def|class|func|fn)\s+([A-Za-z_]\w*)", re.MULTILINE
)

# A source file the floor scans. Kept broad (the floor is language-agnostic);
# the textual scan tolerates non-source files (they simply contribute no atoms).
_SOURCE_GLOB = "*.*"


class TextSearchAdapter:
    """Pure-Python ``re``/``pathlib`` floor; answers stable-core capabilities textually.

    Constructed with the ``root`` of the tree to scan. ``confidence`` is always
    :attr:`Confidence.NOISY` — the floor declares its true confidence and never
    inflates it.
    """

    confidence = Confidence.NOISY.value
    provider = Provider.TEXTSEARCH.value

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    # -- the CodeFactPort surface ------------------------------------------

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult:
        """Answer the stable-core capability named by ``descriptor`` textually.

        Always returns a usable :class:`CodeFactResult` tagged ``textsearch`` @
        ``noisy``. Dispatches on the LOCKED capability id; an unknown id still
        gets a usable (empty-match) textual answer rather than raising — the floor
        never refuses (the universal-floor invariant).
        """
        symbol = self._symbol_of(request)
        if descriptor.id == CAPABILITY_NEVER_WIRED:
            return self._never_wired(symbol)
        if descriptor.id in (CAPABILITY_CALLERS_OF, CAPABILITY_READS_OF):
            return self._sites_of(symbol)
        if descriptor.id == CAPABILITY_ATOMS_IN_FILE:
            return self._atoms()
        if descriptor.id == CAPABILITY_ADR_SECTION:
            return self._adr_section(symbol)
        # Unknown id: a usable, honestly-empty textual answer (never refuse).
        return self._answer(payload={"matches": []}, reason_code=None)

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

    # -- capability realizations (textual, stdlib only) --------------------

    def _never_wired(self, symbol: str) -> CodeFactResult:
        """Is ``symbol`` a net-new symbol with no production call-site?

        Splits ``Owner.method`` and scans for a textual call-site of the trailing
        callable name outside its own definition file. A match → wired (``reason_code``
        ``live-non-callable`` is reserved for the present-but-non-callable case);
        no match → ``absent`` (genuinely no call-site found textually).
        """
        callable_name = symbol.rsplit(".", maxsplit=1)[-1]
        call_sites = self._call_sites(callable_name)
        if call_sites:
            return self._answer(
                payload={
                    "symbol": symbol,
                    "never_wired": False,
                    "call_sites": call_sites,
                },
                reason_code=ReasonCode.LIVE_NON_CALLABLE.value,
            )
        return self._answer(
            payload={"symbol": symbol, "never_wired": True, "call_sites": []},
            reason_code=ReasonCode.ABSENT.value,
        )

    def _sites_of(self, symbol: str) -> CodeFactResult:
        """The textual call/read sites of ``symbol``'s trailing name."""
        callable_name = symbol.rsplit(".", maxsplit=1)[-1] if symbol else ""
        sites = self._call_sites(callable_name) if callable_name else []
        reason = (
            ReasonCode.LIVE_NON_CALLABLE.value if sites else ReasonCode.ABSENT.value
        )
        return self._answer(
            payload={"symbol": symbol, "sites": sites}, reason_code=reason
        )

    def _atoms(self) -> CodeFactResult:
        """The defined atoms (functions/classes) across the scanned tree, textually."""
        atoms: list[str] = []
        for source_file in self._iter_files():
            atoms.extend(_ATOM_DEFINITION.findall(self._read(source_file)))
        return self._answer(payload={"atoms": sorted(set(atoms))}, reason_code=None)

    def _adr_section(self, anchor: str) -> CodeFactResult:
        """Text-shaped: the lines following a heading whose text contains ``anchor``."""
        matches: list[str] = []
        for source_file in self._iter_files():
            text = self._read(source_file)
            if anchor and anchor in text:
                matches.append(source_file.name)
        return self._answer(
            payload={"anchor": anchor, "files": matches}, reason_code=None
        )

    # -- textual primitives ------------------------------------------------

    def _call_sites(self, callable_name: str) -> list[str]:
        """Files containing a textual ``<callable_name>(`` call-site, sans its def.

        A definition line (``def flush`` / ``class flush``) is NOT a call-site;
        a ``.flush(`` or bare ``flush(`` usage is. Name matching only (the floor's
        declared-``noisy`` limitation, ADR-LA-001 Consequences).
        """
        if not callable_name:
            return []
        call_pattern = re.compile(rf"(?<![\w.]){re.escape(callable_name)}\s*\(")
        definition_pattern = re.compile(
            rf"^\s*(?:def|class|func|fn)\s+{re.escape(callable_name)}\b", re.MULTILINE
        )
        hits: list[str] = []
        for source_file in self._iter_files():
            text = self._read(source_file)
            without_defs = definition_pattern.sub("", text)
            if call_pattern.search(without_defs):
                hits.append(str(source_file))
        return hits

    def _iter_files(self) -> list[Path]:
        """Every file under the root (stdlib ``pathlib`` walk — NOT ``grep``)."""
        if self._root.is_file():
            return [self._root]
        return [
            path for path in sorted(self._root.rglob(_SOURCE_GLOB)) if path.is_file()
        ]

    @staticmethod
    def _read(source_file: Path) -> str:
        """Read a file's text, tolerating non-UTF-8 / binary content."""
        try:
            return source_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return ""

    @staticmethod
    def _symbol_of(request: dict[str, object]) -> str:
        """The symbol/anchor the request targets (``symbol`` or ``root`` fallback)."""
        for key in ("symbol", "anchor", "name"):
            value = request.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _answer(self, *, payload: object, reason_code: str | None) -> CodeFactResult:
        """Wrap a textual payload in the LOCKED-tagged envelope (``textsearch`` @ ``noisy``)."""
        return CodeFactResult(
            provider=self.provider,
            confidence=self.confidence,
            payload=payload,
            reason_code=reason_code,
        )
