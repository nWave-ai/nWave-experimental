"""Composition root for the f-coherence-and-attestation slice-04 ATs (self-attest).

Mandate-13 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam slice-04 introduces -- the **self-attest verdict
classifier** (D9 / ADR-CA-001 D1) that EXTENDS the keyless content-seal
(``src/des/domain/at_review_signing.py``) into the dual-source classifier -- built
via lazy import inside the driving-port invocation. No production module is
imported-and-called at the step boundary for its business logic; the step bodies
(in ``test_slice_04_*``) delegate to these composition methods (Mandate-12 -- no
logic in step bodies).

The self-attest layer is the seam flow-v2-design §R D9 named PARTIAL: the keyless
SHA-256 content-seal EXISTS (``at_review_signing.py`` -- ``SIGNED_FIELDS``,
``canonical_signed_json``; HMAC removed 2026-06-11) but there is NO
dual-source-agree / bare-LLM-detection / watchdog classifier. THIS slice drives
the classifier that EXTENDS the content-seal into the full layer. It CONSUMES the
5-verdict GateVerdict SSOT unchanged (C6, no sixth) -- gate-G (slice-03) and the
runner port (slice-05) are mechanical-evidence SOURCES it reads, never forked.

DRIVING SURFACE: the self-attest VERDICT (a §17 ``GateVerdict``) + the reason the
classifier names -- NEVER a line number. The classifier is driven over a REAL
dual-source verdict record carrying
``{mechanical_verdict, llm_verdict, mechanical_evidence_ref, watchdog}`` (ADR-CA-001
D1); the observable is the returned classified verdict envelope (verdict + reason).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the self-attest classifier is
ABSENT -- ``src/des/domain/self_attest.py`` does not exist (verified: no
``self_attest`` module, no ``mechanical_verdict``/``llm_verdict`` classifier
anywhere in ``src/des`` -- only docstring mentions of the memory anchor). Each
driving-port invocation captures the absent seam as a sentinel; the ``Then`` reads
the observable and fires a NAMED semantic ``AssertionError`` (the expected §17
verdict is missing because the self-attest seam is unbuilt) -- never a collection /
import / setup error. GREEN once DELIVER lands ``src/des/domain/self_attest.py``
(the classifier EXTENDING ``at_review_signing.canonical_signed_json``).

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches --
the SEAM, never a line number):
  A1 (classifier entry point): ADR-CA-001 D1 pins the classifier at
     ``src/des/domain/self_attest.py`` (CREATE_NEW) EXTENDING the keyless
     content-seal. Per Mandate-13 + the slice-03 ASSUMPTION (the `des` dispatcher
     has no self-attest row at HEAD -> a subprocess dispatch would be a
     collection-stage failure, not a semantic RED), the classifier is driven at
     the **composition root**: a real classifier callable over a real
     verdict-record. This composition tries, in order,
     ``des.domain.self_attest``'s ``classify`` / ``classify_verdict`` /
     ``self_attest`` / ``attest`` -- or a ``SelfAttest`` / ``SelfAttestClassifier``
     class with an ``evaluate`` / ``classify`` method -- whichever DELIVER ships,
     wire THIS single invocation (``_drive_classifier``) to it. If DELIVER ships a
     subprocess ``des self-attest`` dispatcher instead, update ``_drive_classifier``
     -- the SEAM, not a line number.
  A2 (record input shape): ADR-CA-001 D1 names the additive signed-field schema
     ``{mechanical_verdict: GateVerdict | None, llm_verdict: GateVerdict | None,
     mechanical_evidence_ref: str | None}`` + a watchdog/timeout signal. This
     composition passes a real record carrying those fields (keyword args; falls
     back to a single positional dict / record object). The watchdog signal is
     modelled as ``watchdog_timed_out: bool`` (the ADR names the signal, not the
     field name). If DELIVER's classifier takes a different record shape / a
     different watchdog field, update ``_drive_classifier`` / ``_record_kwargs``.
  A3 (verdict envelope): the classifier returns a §17 ``GateVerdict`` (PASS / FAIL
     / UNVERIFIED / INDETERMINATE -- never a sixth, C6) + a reason naming why it
     floored to a NO / degraded LOUD. This composition reads the verdict token +
     the reason from whichever envelope shape the classifier returns (a
     ``GateOutcome``-like object, a dict, or a ``(verdict, reason)`` tuple). If
     DELIVER names the envelope fields differently, update ``_read_envelope``.
  A4 (seal projection -- NOT asserted at this layer): ADR-CA-001 D1 requires the
     seal be PROJECTED by the spine, never self-signed. slice-04 asserts the
     CLASSIFICATION (the dual-source verdict), not the projection mechanics (that
     is the spine's concern / a later slice). Flagged so DELIVER does not read a
     projection assertion into these ATs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .domain_types_slice_04_self_attest import (
    LOCKED_GATE_VERDICTS,
    AttestationCase,
    AttestObservable,
    GateVerdict,
    VerdictRecord,
)


# Sentinel an absent classifier invocation records, so the Then can name the
# missing verdict instead of letting an ImportError escape as a collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"

# A stable mechanical-evidence reference (a gate-G digest shape) the
# mechanically-grounded record carries. NOT a file path (ADR-CA-001 D1).
_EVIDENCE_REF = "gate-g:9f2c1ab"


@dataclass
class SelfAttestComposition:
    """Drives the slice-04 self-attest classifier through its REAL driving surface."""

    _case: AttestationCase | None = field(default=None)

    _observable: AttestObservable | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # Given -- arm the dual-source attestation case (builds the record)
    # =====================================================================

    def given_attestation_case(self, case: AttestationCase) -> None:
        """Arm which dual-source attestation case the classifier decides."""
        self._case = case

    # =====================================================================
    # When -- drive the REAL self-attest classifier over the case's record
    # =====================================================================

    def when_self_attest_classifies_the_verdict(self) -> None:
        """Drive the REAL self-attest classifier over the armed case's record.

        Builds the CONTENT-DISTINCT verdict record for the armed AttestationCase
        (the {mechanical_verdict, llm_verdict, mechanical_evidence_ref, watchdog}
        fields differ per case, ADR-CA-001 D1) and asks the classifier to decide.
        The observable is the returned classified §17 verdict envelope.
        """
        # No silent None->default collapse: every classify path arms an explicit
        # attestation case. A None case here is a scaffold-authoring error.
        assert self._case is not None, (
            "a self-attest classification scenario must arm an explicit "
            "AttestationCase (MECHANICAL_EVIDENCE_AGREE / BARE_LLM_NO_EVIDENCE / "
            "DUAL_SOURCE_DIVERGENCE / WATCHDOG_TIMEOUT) -- got None (would collapse "
            "distinct verdict records onto one, an unsatisfiable spec)."
        )
        record = self._build_record(self._case)
        self._observable = self._drive_classifier(record)

    # =====================================================================
    # Then -- observable readers (the §17 verdict + the reason)
    # =====================================================================

    def then_verdict_is(self, expected: GateVerdict) -> None:
        """The classifier returned EXACTLY the expected §17 verdict (one of the LOCKED five)."""
        obs = self._require_observable()
        assert obs.verdict in LOCKED_GATE_VERDICTS, (
            f"the self-attest classifier must return one of the §17 LOCKED FIVE "
            f"verdicts {sorted(LOCKED_GATE_VERDICTS)!r} (ADR-GV-001, no sixth -- C6) "
            f"-- got verdict={obs.verdict!r}. {self._observed()}"
        )
        assert obs.verdict == expected.value, (
            f"the self-attest classifier must return {expected.value!r} for the "
            f"{self._case.value if self._case else None!r} attestation case "
            f"(ADR-CA-001 D1) -- got {obs.verdict!r}. {self._observed()}"
        )

    def then_reason_names_the_floor(self, cause_fragment: str) -> None:
        """On a NO-floor / degrade verdict, the reason NAMES ITS CAUSE.

        Asserts (a) the reason is non-empty (Invariant 2 -- no silent degrade) AND
        (b) the case's DISCRIMINATING ``cause_fragment`` is a case-insensitive
        substring of the reason. The three fragments ("evidence" / "disagree" /
        "watchdog") are mutually exclusive, so a hollow classifier that returns
        INDETERMINATE with ONE constant reason for BOTH the divergence and the
        watchdog cause RED-fails -- it can carry at most one of the two fragments.
        This pins the CAUSE-in-reason, not just the verdict token (closing the
        "INDETERMINATE-for-the-wrong-reason still passes" hole).
        """
        obs = self._require_observable()
        assert obs.reason, (
            f"a NO-floor / degrade verdict (bare-LLM->UNVERIFIED, "
            f"dual-source-divergence->INDETERMINATE, watchdog-timeout->INDETERMINATE) "
            f"must come back with a NON-EMPTY reason naming WHY the machine YES did "
            f"not authorize (Invariant 2 -- no silent degrade) -- the classifier "
            f"returned no reason. {self._observed()}"
        )
        assert cause_fragment.lower() in obs.reason.lower(), (
            f"the reason must NAME ITS CAUSE -- the discriminating fragment "
            f"{cause_fragment!r} must appear in the reason so the two INDETERMINATE "
            f"causes (divergence vs watchdog) are not conflated by a constant string "
            f"(Invariant 2 -- the degrade names what failed) -- reason={obs.reason!r} "
            f"does not name {cause_fragment!r}. {self._observed()}"
        )

    # =====================================================================
    # record builder -- a CONTENT-DISTINCT record per attestation case
    # =====================================================================

    @staticmethod
    def _build_record(case: AttestationCase) -> VerdictRecord:
        """Build the CONTENT-DISTINCT verdict record for the attestation case.

        Each of the four cases differs in the {mechanical_verdict, llm_verdict,
        mechanical_evidence_ref, watchdog} 4-tuple so a deterministic classifier
        cannot map two distinct cases to the same record:

          MECHANICAL_EVIDENCE_AGREE -> (PASS, PASS, <evidence-ref>, False)
          BARE_LLM_NO_EVIDENCE      -> (None, PASS, None,           False)
          DUAL_SOURCE_DIVERGENCE    -> (FAIL, PASS, <evidence-ref>, False)
          WATCHDOG_TIMEOUT          -> (None, PASS, None,           True)

        BARE_LLM_NO_EVIDENCE and WATCHDOG_TIMEOUT share the (None, PASS, None)
        head but DIFFER on the watchdog flag (False vs True) -- the discriminator
        ADR-CA-001 D1 names ("watchdog timeout before mechanical_verdict is set").
        """
        passv = GateVerdict.PASS.value
        failv = GateVerdict.FAIL.value
        if case is AttestationCase.MECHANICAL_EVIDENCE_AGREE:
            # Mechanical evidence present AND both sources agree -> PASS.
            return VerdictRecord(
                mechanical_verdict=passv,
                llm_verdict=passv,
                mechanical_evidence_ref=_EVIDENCE_REF,
                watchdog_timed_out=False,
            )
        if case is AttestationCase.BARE_LLM_NO_EVIDENCE:
            # An LLM say-so, NO mechanical evidence -> UNVERIFIED (a NO floor).
            return VerdictRecord(
                mechanical_verdict=None,
                llm_verdict=passv,
                mechanical_evidence_ref=None,
                watchdog_timed_out=False,
            )
        if case is AttestationCase.DUAL_SOURCE_DIVERGENCE:
            # Mechanical and LLM sources present and DISAGREE -> INDETERMINATE.
            return VerdictRecord(
                mechanical_verdict=failv,
                llm_verdict=passv,
                mechanical_evidence_ref=_EVIDENCE_REF,
                watchdog_timed_out=False,
            )
        # WATCHDOG_TIMEOUT: the mechanical leg never completed -> INDETERMINATE.
        return VerdictRecord(
            mechanical_verdict=None,
            llm_verdict=passv,
            mechanical_evidence_ref=None,
            watchdog_timed_out=True,
        )

    # =====================================================================
    # driving-port invocation (lazy seam import -> sentinel on absence)
    # =====================================================================

    def _drive_classifier(self, record: VerdictRecord) -> AttestObservable:
        """Drive the REAL self-attest classifier over the record (assumptions A1-A3).

        At HEAD ``src/des/domain/self_attest.py`` is ABSENT -> the lazy import
        fails -> the sentinel records the absent seam and the Then fires the named
        RED. GREEN once DELIVER ships the classifier EXTENDING the content-seal.
        """
        try:
            from des.domain import self_attest as self_attest_module
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        callable_ = self._resolve_classifier_callable(self_attest_module)
        if callable_ is None:
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        kwargs = self._record_kwargs(record)
        try:
            result = callable_(**kwargs)
        except TypeError:
            # DELIVER may take a single positional record (a dict / a record
            # object) instead of keyword fields -- try those shapes before giving up.
            for candidate in (kwargs, record):
                try:
                    result = callable_(candidate)
                    break
                except Exception:
                    continue
            else:
                self._seam_error = _SEAM_ABSENT
                return self._absent_observable()

        return self._read_envelope(result)

    @staticmethod
    def _resolve_classifier_callable(module: object) -> object | None:
        """Resolve whichever self-attest entry the DELIVER ships (A1 -- the SEAM)."""
        for name in ("classify", "classify_verdict", "self_attest", "attest"):
            candidate = getattr(module, name, None)
            if callable(candidate):
                return candidate
        for cls_name in ("SelfAttest", "SelfAttestClassifier"):
            cls = getattr(module, cls_name, None)
            if cls is None:
                continue
            try:
                instance = cls()
            except Exception:
                continue
            for method_name in ("evaluate", "classify"):
                method = getattr(instance, method_name, None)
                if callable(method):
                    return method
        return None

    @staticmethod
    def _record_kwargs(record: VerdictRecord) -> dict[str, object]:
        """The keyword shape of the verdict record (A2 -- the field NAMES are the contract)."""
        return {
            "mechanical_verdict": record.mechanical_verdict,
            "llm_verdict": record.llm_verdict,
            "mechanical_evidence_ref": record.mechanical_evidence_ref,
            "watchdog_timed_out": record.watchdog_timed_out,
        }

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _read_envelope(self, result: object) -> AttestObservable:
        """Read the port-exposed §17 verdict + reason (A3)."""
        verdict = self._token(self._field(result, "verdict"))
        reason = self._field(result, "reason", "diagnostic", "message")
        # A tuple envelope (verdict, reason).
        if verdict is None and isinstance(result, tuple) and result:
            verdict = self._token(result[0])
            reason = result[1] if len(result) > 1 else reason
        return AttestObservable(
            verdict=verdict,
            reason=reason if isinstance(reason, str) else None,
        )

    def _absent_observable(self) -> AttestObservable:
        """The classifier seam is absent -> no verdict; the Then names the missing mechanism."""
        return AttestObservable(verdict=None, reason=None)

    @staticmethod
    def _field(obj: object, *names: str) -> object:
        """Read the first present attribute (or dict key) from a result envelope."""
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return value
            if isinstance(obj, dict) and name in obj:
                return obj[name]
        return None

    @staticmethod
    def _token(value: object) -> str | None:
        """Coerce an enum-or-str verdict value to its wire token (or None)."""
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_observable(self) -> AttestObservable:
        if self._observable is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-04 self-attest classifier (the dual-source verdict "
                "layer -- it reads {mechanical_verdict, llm_verdict, "
                "mechanical_evidence_ref, watchdog} and returns a §17 GateVerdict: "
                "mechanical-evidence+agree -> PASS, bare-LLM -> UNVERIFIED, "
                "dual-source-divergence -> INDETERMINATE, watchdog-timeout -> "
                "INDETERMINATE) must exist and return a verdict envelope -- the "
                "self-attest seam is ABSENT at HEAD (active-RED; DELIVER builds "
                "src/des/domain/self_attest.py EXTENDING the keyless content-seal "
                "at_review_signing.canonical_signed_json -- never HMAC, never "
                "self-signed, ADR-CA-001 D1). "
                f"{self._observed()}"
            )
        return self._observable

    def _observed(self) -> str:
        return (
            f"case={self._case!r}; observable={self._observable!r}; "
            f"seam_error={self._seam_error!r}"
        )
