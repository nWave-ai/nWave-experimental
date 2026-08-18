"""Composition root for the f-coherence-and-attestation slice-01 ATs.

Mandate-13 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam the slice-01 Code-Design pins -- the
``CodeFactPort`` / ``TextSearchAdapter`` / the slice-01 code-fact gate / the
byte-lock guard -- built via lazy import inside the driving-port invocation. No
production module is imported-and-called at the step boundary for its business
logic; the step bodies (in ``test_slice_*`` below) delegate to these composition
methods (Mandate-12 -- no logic in step bodies).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD every pinned seam is
ABSENT (``code_fact_port.py`` / ``text_search_code_fact_adapter.py`` / the
slice-01 gate / ``locked-vocabulary.json`` do not exist). Each driving-port
invocation captures the absence as a "seam absent" sentinel; the ``Then`` reads
the observable and fires a NAMED semantic ``AssertionError`` (the expected
observable is missing because the seam is unbuilt) -- never a collection /
import / setup error. GREEN once DELIVER lands the seams so the real observable
appears.

DESIGN-pinned seam paths (slice-01 Code-Design + Reuse table):
  * port              : src/des/ports/code_fact_port.py
                        -> CodeFactPort (Protocol, query(descriptor, request)
                           -> CodeFactResult), CodeFactResult (frozen dataclass
                           {provider, confidence, payload} -- ADR-LA-001 D9
                           slice (c): `reason_code` moved into the
                           capability-owned payload schema, no longer an
                           envelope field), CapabilityDescriptor (frozen
                           {id, stability, contract_version, io_schema,
                           providing_adapter}), the 5 locked capability-id
                           constants.
  * floor adapter     : src/des/adapters/driven/codefact/
                        text_search_code_fact_adapter.py
                        -> TextSearchAdapter (confidence=noisy, stdlib re/pathlib).
  * slice-01 gate     : ASSUMPTION -- the slice-01 Code-Design pins ONE code-fact
                        gate re-deriving query.never-wired through the port but
                        does NOT fix a concrete des subcommand for it (gate_g.py
                        is slice-03). Driven at the composition root via a real
                        gate callable. DELIVER MUST wire AT-3 to the real slice-01
                        code-fact gate callable it ships (see _drive_slice01_gate).
  * byte-lock guard   : tests/build/test_codefact_locked_vocabulary.py +
                        tests/build/fixtures/locked-vocabulary.json
                        (ADR-CA-001 D2). AT-4 drives the guard's byte-comparison
                        AND its self-probe (planted drift -> RED).

The driving surface is the SEAM / the CodeFactResult envelope / the gate verdict
/ the guard's byte-comparison -- NEVER a line number.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_coherence_codefact import (
    LOCKED_CAPABILITY_IDS,
    LOCKED_CONFIDENCES,
    LOCKED_PROVIDERS,
    LOCKED_REASON_CODES,
    CapabilityId,
    CodeFactObservable,
    Confidence,
    GuardProbe,
    Provider,
    WiringCase,
)


# tests/des/acceptance/coherence_codefact/steps/<this file>
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# Sentinel an absent-seam invocation records, so the Then can name the missing
# observable instead of letting an ImportError escape as a collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"


@dataclass
class CoherenceCodeFactComposition:
    """Drives the slice-01 seams through their REAL production driving surface."""

    # AT-1 / AT-2 / AT-3 observable
    _capability: CapabilityId | None = field(default=None)
    _wiring_case: WiringCase | None = field(default=None)
    _observable: CodeFactObservable | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # AT-4 observable
    _guard_probe: GuardProbe | None = field(default=None)
    _guard_red: bool | None = field(default=None)
    _guard_error: str | None = field(default=None)

    # =====================================================================
    # AT-1 -- the CodeFactPort + registry two-axis floor (foundation)
    # AT-2 -- the TextSearchAdapter floor answers a stable-core capability
    #         textually at `noisy`
    # =====================================================================

    def given_capability_required(self, capability: CapabilityId) -> None:
        """Arm which LOCKED stable-core capability the floor must answer."""
        self._capability = capability

    def given_wiring_case(self, wiring_case: WiringCase) -> None:
        """Arm whether the probed symbol IS or is NOT production-wired (AT-3)."""
        self._wiring_case = wiring_case

    def when_floor_answers_via_port(self, tmp_path: Path) -> None:
        """Drive the REAL TextSearchAdapter THROUGH the CodeFactPort.

        Builds a tiny real tree under tmp_path, then asks the universal floor for
        the armed stable-core capability via the port's ``query``. The observable
        is the ``CodeFactResult`` envelope. At HEAD the port + adapter are absent
        -> sentinel; the Then names the missing envelope.
        """
        assert self._capability is not None
        tree = self._write_probe_tree(tmp_path, wiring_case=WiringCase.WIRED)
        self._observable = self._query_floor(self._capability, tree)

    # =====================================================================
    # AT-3 -- ONE code-fact gate re-derives query.never-wired via the port
    #         + the answer is {provider, confidence} tagged, its payload
    #         owning the never_wired disambiguating flag
    # =====================================================================

    def when_gate_rederives_never_wired(self, tmp_path: Path) -> None:
        """Drive the REAL slice-01 code-fact gate re-deriving query.never-wired.

        The gate must NOT hand-roll ``import ast`` -- it re-derives the fact
        THROUGH the CodeFactPort substrate (one honest provider), tagging the
        result. The observable is the gate's CodeFactResult-tagged verdict. At
        HEAD the gate (and the port it would delegate to) is absent -> sentinel.
        """
        assert self._wiring_case is not None
        tree = self._write_probe_tree(tmp_path, wiring_case=self._wiring_case)
        self._observable = self._drive_slice01_gate(tree, self._wiring_case)

    # ---- AT-1/2/3 observable readers (Then) ------------------------------

    def then_a_usable_answer_came_back(self) -> None:
        """The floor ALWAYS answers -- a usable (non-empty) answer came back."""
        obs = self._require_observable()
        assert obs.answered, (
            f"the CodeFactPort substrate must ALWAYS return a usable answer for the "
            f"stable-core capability {self._capability_value()!r} (the universal "
            f"TextSearchAdapter floor guarantees a non-empty answer on any "
            f"Python-only target) -- got no usable answer. {self._observed()}"
        )

    def then_provenance_is_tagged(self) -> None:
        """The answer carries {provider, confidence} provenance (Invariant 2)."""
        obs = self._require_observable()
        assert obs.provider is not None and obs.confidence is not None, (
            "the answer must carry {provider, confidence} provenance in the "
            "CodeFactResult envelope (the confidence label IS the loud signal, "
            f"Invariant 2) -- provenance missing. {self._observed()}"
        )

    def then_provider_is_text_search_floor(self) -> None:
        """With only the floor wired, the provider is textsearch @ noisy."""
        obs = self._require_observable()
        assert obs.provider == Provider.TEXTSEARCH.value, (
            f"with only the universal floor wired the answer must be tagged "
            f"provider={Provider.TEXTSEARCH.value!r} -- got "
            f"provider={obs.provider!r}. {self._observed()}"
        )
        assert obs.confidence == Confidence.NOISY.value, (
            f"the TextSearchAdapter must declare its true (lowest) confidence "
            f"{Confidence.NOISY.value!r} -- never inflated -- got "
            f"confidence={obs.confidence!r}. {self._observed()}"
        )

    def then_confidence_token_is_locked(self) -> None:
        """The confidence token is one of the LOCKED cross-tier values."""
        obs = self._require_observable()
        assert obs.confidence in LOCKED_CONFIDENCES, (
            f"the confidence token must be one of the cross-tier-LOCKED set "
            f"{sorted(LOCKED_CONFIDENCES)!r} (ADR-LA-001 §5a) -- got "
            f"confidence={obs.confidence!r}. {self._observed()}"
        )

    def then_provider_token_is_locked(self) -> None:
        """The provider token is one of the LOCKED cross-tier values."""
        obs = self._require_observable()
        assert obs.provider in LOCKED_PROVIDERS, (
            f"the provider token must be one of the cross-tier-LOCKED set "
            f"{sorted(LOCKED_PROVIDERS)!r} (ADR-LA-001 §5a) -- got "
            f"provider={obs.provider!r}. {self._observed()}"
        )

    def then_never_wired_payload_is_locked(self) -> None:
        """A never-wired verdict carries its OWN payload-owned disambiguating flag.

        ADR-LA-001 D9 slice (c), D6-R3: ``absent``/``live-non-callable`` is no
        longer an envelope ``reason_code`` -- it is the ``never-wired``
        payload's own ``never_wired`` bool (owned by that capability's
        schema, never the generic envelope).
        """
        obs = self._require_observable()
        assert obs.never_wired is not None, (
            "a never-wired re-derivation must tag its payload with the LOCKED "
            "disambiguating `never_wired` bool (ADR-LA-001 §5a/D9(c) -- "
            "disambiguating genuinely-absent from live-but-non-callable) -- got "
            f"never_wired={obs.never_wired!r}. {self._observed()}"
        )

    # =====================================================================
    # AT-4 -- the Published-Language byte-lock guard (planted-drift -> RED)
    # =====================================================================

    def given_guard_probe(self, probe: GuardProbe) -> None:
        """Arm whether the guard runs against the PRISTINE or a DRIFTED fixture."""
        self._guard_probe = probe

    def when_byte_lock_guard_runs(self, tmp_path: Path) -> None:
        """Drive the REAL byte-lock guard mechanism.

        The guard asserts the OSS-serialized locked-vocabulary token set is
        byte-identical to the committed ``locked-vocabulary.json`` fixture. The
        self-probe drives it against a PLANTED-DRIFT fixture variant (e.g.
        ``binding-resolved`` -> ``precise``): a correct guard goes RED on drift.
        At HEAD the guard module + the fixture are absent -> sentinel; the Then
        names the missing guard.
        """
        assert self._guard_probe is not None
        self._guard_red, self._guard_error = self._run_byte_lock_guard(
            tmp_path, self._guard_probe
        )

    def then_pristine_fixture_passes(self) -> None:
        """The PRISTINE locked vocabulary is byte-identical -> guard PASSES (not RED)."""
        if self._guard_error == _SEAM_ABSENT:
            raise AssertionError(
                "the Published-Language byte-lock guard "
                "(tests/build/test_codefact_locked_vocabulary.py) and its committed "
                "tests/build/fixtures/locked-vocabulary.json fixture must exist and "
                "PASS against the pristine LOCKED token set (capability ids "
                f"{sorted(LOCKED_CAPABILITY_IDS)!r} + provider/confidence/reason_code "
                "vocabularies, ADR-LA-001 §2/§5a) -- the guard mechanism is ABSENT "
                "at HEAD (active-RED, DELIVER builds it). "
                f"{self._guard_observed()}"
            )
        assert self._guard_red is False, (
            "with the PRISTINE locked-vocabulary fixture (byte-identical to the "
            "cross-tier Published Language) the byte-lock guard must PASS (not RED) "
            f"-- the guard flagged drift on the pristine token set. "
            f"{self._guard_observed()}"
        )

    def then_planted_drift_makes_guard_red(self) -> None:
        """A planted-drift variant MUST make the guard RED (the self-probe)."""
        if self._guard_error == _SEAM_ABSENT:
            raise AssertionError(
                "the byte-lock guard must be SELF-PROBED (Earned-Trust, Principle "
                "13): a planted-drift fixture variant (e.g. 'binding-resolved' "
                "renamed to 'precise', or a 6th confidence label added) MUST make "
                "the guard RED -- the guard mechanism is ABSENT at HEAD (active-RED, "
                f"DELIVER builds it). {self._guard_observed()}"
            )
        assert self._guard_red is True, (
            "a planted-drift locked-vocabulary variant (an OSS edit that renames / "
            "adds / drops a LOCKED token) MUST make the byte-lock guard go RED "
            "(otherwise the cross-tier byte-lock with SF erodes silently) -- the "
            f"guard did NOT catch the planted drift. {self._guard_observed()}"
        )

    # =====================================================================
    # driving-port invocations (lazy seam import -> sentinel on absence)
    # =====================================================================

    def _query_floor(self, capability: CapabilityId, tree: Path) -> CodeFactObservable:
        """Drive the REAL TextSearchAdapter through the REAL CodeFactPort."""
        try:
            from des.adapters.driven.codefact.text_search_code_fact_adapter import (
                TextSearchAdapter,
            )
            from des.ports.code_fact_port import (
                CapabilityDescriptor,
                CodeFactPort,
            )
        except (ImportError, ModuleNotFoundError) as exc:
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable(exc)

        adapter: CodeFactPort = TextSearchAdapter(root=tree)
        descriptor = CapabilityDescriptor(
            id=capability.value,
            stability="stable",
            contract_version="1.0.0",
            io_schema=capability.value,
            providing_adapter=Provider.TEXTSEARCH.value,
        )
        result = adapter.query(descriptor, {"root": str(tree)})
        return self._read_envelope(result)

    def _drive_slice01_gate(
        self, tree: Path, wiring_case: WiringCase
    ) -> CodeFactObservable:
        """Drive the REAL slice-01 code-fact gate re-deriving query.never-wired.

        ASSUMPTION (flagged to DELIVER): the slice-01 gate callable is reached at
        the composition root. The probed import path follows the DESIGN Reuse
        table family (``des.adapters.driven.codefact``). DELIVER MUST wire this to
        the real slice-01 code-fact gate it ships; if the gate lands elsewhere,
        update this single invocation (the SEAM, not a line number).
        """
        try:
            from des.adapters.driven.codefact.code_fact_chain import (
                CodeFactChain,
            )
            from des.ports.code_fact_port import (
                CapabilityDescriptor,
            )
        except (ImportError, ModuleNotFoundError) as exc:
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable(exc)

        # The gate re-derives query.never-wired THROUGH the port substrate (one
        # honest provider), not a per-gate import ast. With only the floor wired
        # the chain answers textually @ noisy.
        chain = CodeFactChain(root=tree)
        descriptor = CapabilityDescriptor(
            id=CapabilityId.NEVER_WIRED.value,
            stability="stable",
            contract_version="1.0.0",
            io_schema=CapabilityId.NEVER_WIRED.value,
            providing_adapter=Provider.TEXTSEARCH.value,
        )
        result = chain.query(descriptor, {"symbol": "CacheWriter.flush"})
        return self._read_envelope(result)

    def _run_byte_lock_guard(
        self, tmp_path: Path, probe: GuardProbe
    ) -> tuple[bool | None, str | None]:
        """Drive the REAL byte-lock guard; return (is_red, error_sentinel)."""
        try:
            from tests.build.test_codefact_locked_vocabulary import (
                assert_locked_vocabulary_unchanged,
            )
        except (ImportError, ModuleNotFoundError):
            return (None, _SEAM_ABSENT)

        # The self-probe: PRISTINE drives the committed fixture; DRIFTED drives a
        # planted-drift variant the guard MUST reject. The guard signals drift by
        # raising AssertionError.
        candidate = self._fixture_for_probe(tmp_path, probe)
        try:
            assert_locked_vocabulary_unchanged(fixture_path=candidate)
        except AssertionError:
            return (True, None)  # guard went RED (drift caught)
        return (False, None)  # guard PASSED (no drift)

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _read_envelope(self, result: object) -> CodeFactObservable:
        """Read the port-exposed {provider, confidence} + answered + the
        never-wired payload's own `never_wired` disambiguating flag (ADR-LA-001
        D9 slice (c): `reason_code` is no longer an envelope field)."""
        provider = getattr(result, "provider", None)
        confidence = getattr(result, "confidence", None)
        payload = getattr(result, "payload", None)
        never_wired = payload.get("never_wired") if isinstance(payload, dict) else None
        return CodeFactObservable(
            answered=payload is not None,
            provider=self._token(provider),
            confidence=self._token(confidence),
            never_wired=never_wired,
        )

    def _absent_observable(self, exc: Exception) -> CodeFactObservable:
        """The seam is absent -> no observable; the Then names the missing seam."""
        return CodeFactObservable(
            answered=False, provider=None, confidence=None, never_wired=None
        )

    @staticmethod
    def _token(value: object) -> str | None:
        """Coerce an enum-or-str port value to its wire token (or None)."""
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # substrate plumbing
    # =====================================================================

    def _write_probe_tree(self, tmp_path: Path, wiring_case: WiringCase) -> Path:
        """A tiny real source tree the floor scans (real I/O, stdlib only).

        Defines a net-new effectful symbol ``CacheWriter.flush``; the WIRED case
        adds a production call-site, the NEVER_WIRED case omits it -- so the
        floor's textual answer is a non-vacuous, observable difference.
        """
        root = tmp_path / "probe_tree" / "src"
        root.mkdir(parents=True, exist_ok=True)
        (root / "cache_writer.py").write_text(
            "class CacheWriter:\n"
            "    def flush(self) -> None:\n"
            "        self._buffer.clear()\n",
            encoding="utf-8",
        )
        if wiring_case is WiringCase.WIRED:
            (root / "service.py").write_text(
                "from .cache_writer import CacheWriter\n\n"
                "def run() -> None:\n"
                "    CacheWriter().flush()\n",
                encoding="utf-8",
            )
        return root

    def _fixture_for_probe(self, tmp_path: Path, probe: GuardProbe) -> Path:
        """The locked-vocabulary fixture the guard compares against.

        PRISTINE -> the committed fixture (byte-identical to the LOCKED language).
        DRIFTED  -> a planted-drift variant (rename binding-resolved -> precise),
                    written to tmp_path; the guard MUST reject it.
        """
        committed = (
            REPO_ROOT / "tests" / "build" / "fixtures" / "locked-vocabulary.json"
        )
        if probe is GuardProbe.PRISTINE:
            return committed

        drifted = {
            "capability_ids": sorted(LOCKED_CAPABILITY_IDS),
            "providers": sorted(LOCKED_PROVIDERS),
            # planted drift: rename binding-resolved -> precise
            "confidences": sorted(
                {
                    "precise" if c == "binding-resolved" else c
                    for c in LOCKED_CONFIDENCES
                }
            ),
            "reason_codes": sorted(LOCKED_REASON_CODES),
        }
        drifted_path = tmp_path / "drifted-locked-vocabulary.json"
        drifted_path.write_text(json.dumps(drifted, indent=2), encoding="utf-8")
        return drifted_path

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_observable(self) -> CodeFactObservable:
        if self._observable is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-01 CodeFactPort substrate (the port + the "
                "TextSearchAdapter floor + the code-fact gate re-deriving the fact "
                "through the port) must exist and return a tagged CodeFactResult "
                "envelope -- the seam is ABSENT at HEAD (active-RED, DELIVER builds "
                f"src/des/ports/code_fact_port.py + "
                f"src/des/adapters/driven/codefact/...). {self._observed()}"
            )
        return self._observable

    def _capability_value(self) -> str | None:
        return self._capability.value if self._capability else None

    def _observed(self) -> str:
        return (
            f"capability={self._capability_value()!r}; "
            f"wiring_case={self._wiring_case!r}; observable={self._observable!r}; "
            f"seam_error={self._seam_error!r}"
        )

    def _guard_observed(self) -> str:
        return (
            f"guard_probe={self._guard_probe!r}; guard_red={self._guard_red!r}; "
            f"guard_error={self._guard_error!r}"
        )
