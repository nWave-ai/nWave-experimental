"""Composition root for fix-wave-dispatch-marker-contract slice-02 ATs.

Two driving surfaces (Mandate-13):

  * AT-2a -- the REAL ``PreToolUseService.validate`` via the production
    composition root (Layer 3 composition), driven with the DES-WAVE-only entry
    shape EXACTLY as a command template ships it. This is the test the original
    slice-07d AT fixture should have been (Root Cause B: that fixture carried the
    full classic marker set + DES-WAVE, so it never reached the :146 hinge and
    validated a path no template takes). Reuses the slice-01 real-service driving
    pattern; the distinct value is that the prompt shape is sourced from the
    SHIPPED template literal, not a hand-built classic-marker set.

  * AT-2b -- the drift guard. A pure Python + filesystem reconciliation
    (git-free, target-machine-agnostic, no new tool dependency) over the
    entry-marker Contract SSOT block + the four ``nWave/tasks/nw/{discuss,design,
    devops,distill}.md`` templates. NOT a service call -- the SUT here is the
    static SSOT-template agreement (a closed, finite file set -> example/parametrize
    treatment, NOT PBT, per the PBT falsifier-gate). RED on divergence:
      (a) the canonical Contract SSOT block is ABSENT from flow-v2-design.md at
          HEAD (it is authored in this slice's DELIVER doc delta) -> RED;
      (b) any template missing its ``<!-- DES-WAVE: <wave> -->`` literal, OR
          carrying an instruction requiring classic markers on the ENTERING
          dispatch, diverges from the SSOT -> RED.

RED-for-right-reason (active-RED scaffold, ADR-025 + ADR-028, atdd_pure):
  * AT-2a -- like slice-01 AT-1a, the :146 veto fires on the DES-WAVE-only entry
    at HEAD (the wave_entering exemption is slice-01's not-yet-shipped fix) -> the
    service BLOCKS WAVE_MARKER_BYPASS where ALLOW is expected -> semantic
    AssertionError. (slice-02 depends-on slice-01: once the exemption lands AT-2a
    goes GREEN.)
  * AT-2b -- the entry-marker Contract SSOT block does not exist in
    flow-v2-design.md at HEAD -> the drift guard cannot find the canonical
    declaration -> semantic AssertionError naming the absent SSOT block. GREEN
    once DELIVER authors the §22.7.A Contract SSOT block.
No collection / import error (only test-local types + already-shipped production
composition + stdlib file reads).

SUT STATE MACHINE (C2):
  AT-2a states = {WAVE_ENTERING(template-shipped DES-WAVE-only)} ->
    allow (recognized entry, post-slice-01).
  AT-2b states = {SSOT_PRESENT, SSOT_ABSENT} x {TEMPLATES_AGREE, TEMPLATES_DRIFT}
    SSOT_ABSENT                      --> RED (no canonical declaration)
    SSOT_PRESENT + TEMPLATES_DRIFT   --> RED (emitter diverges from contract)
    SSOT_PRESENT + TEMPLATES_AGREE   --> GREEN (contract == emitter == fixture)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_marker_contract import GateDecision, WaveUnderTest
from .domain_types_slice_marker_contract_02 import CommandTemplate


# parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_PRODUCT_DIR_REL = "docs/product"
_SSOT_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md", "jobs.yaml")
_BYPASS_TOKEN = "wave_marker_bypass"

# The entry-marker Contract SSOT lives beside the keystone it amends (one
# canonical home, feature-delta §Code-Design "Contract SSOT — canonical home").
_CONTRACT_SSOT_REL = "docs/product/architecture/flow-v2-design.md"

# The machine-parseable anchor the DELIVER doc-delta authors: a sentinel heading
# the drift guard greps for, plus the declaration that DES-WAVE alone is
# sufficient for an ENTERING dispatch. The guard asserts the SSOT CONTAINS these
# (its presence is the contract's existence; its text is the contract).
_CONTRACT_ANCHOR = "Entry-Dispatch Marker Contract"
_CONTRACT_SUFFICIENCY_PHRASES: tuple[str, ...] = (
    "des-wave",
    "alone",
)

# A template instruction that would CONTRADICT the contract: requiring the
# classic marker set on the ENTERING dispatch. The drift guard greps for
# `_DES_MARKER_KEY` tokens appearing as a REQUIREMENT on the entry. (The fix is
# Approach (a): templates are NOT changed to co-emit these; if a template grows
# such an instruction it diverges from the SSOT.)
_CLASSIC_MARKER_TOKENS: tuple[str, ...] = (
    "DES-VALIDATION",
    "DES-PROJECT-ID",
    "DES-PROJECT-ROOT",
    "DES-STEP-ID",
)


@dataclass
class ContractSsotComposition:
    """Drives AT-2a (production shape) + AT-2b (SSOT<->template drift guard)."""

    _project_root: Path | None = field(default=None)
    _wave: WaveUnderTest | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _drift_findings: list[str] = field(default_factory=list)
    _reconciled_paths: tuple[Path, ...] = field(default_factory=tuple)

    # ---- given (AT-2a) ------------------------------------------------------

    def given_wave_entering_with_template_shape(
        self, tmp_path: Path, wave: WaveUnderTest
    ) -> None:
        """Arm the wave as ENTERING and satisfy its entry preconditions (AT-2a)."""
        self._project_root = tmp_path
        self._wave = wave
        self._arm_floor(tmp_path, wave, entry_pending=True)
        if wave is WaveUnderTest.DISCUSS:
            self._seed_product_ssot(tmp_path)

    # ---- when (AT-2a) -------------------------------------------------------

    def when_template_shipped_dispatch_checked(self) -> None:
        """Drive the REAL service with the DES-WAVE-only shape a template ships."""
        assert self._wave is not None
        self._run_pre_tool_use_gate(
            prompt=self._template_shipped_prompt(self._wave), wave_entering=True
        )

    # ---- then (AT-2a) -------------------------------------------------------

    def then_production_shape_allowed(self) -> None:
        """The shipped DES-WAVE-only shape passes via the real gate (post-slice-01).

        RED-for-right-reason at HEAD: the slice-01 wave_entering exemption is not
        shipped, so the :146 veto fires -> BLOCK WAVE_MARKER_BYPASS where ALLOW is
        expected. (slice-02 depends-on slice-01.)
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the DES-WAVE-only entry shape EXACTLY as a command template ships it "
            "must pass via the production gate (the test the original slice-07d "
            "fixture should have been -- it exercised the classic-marker shape no "
            f"template takes, Root Cause B); the gate returned "
            f"{self._decision_action!r}. {self._observed()}"
        )
        reason = (self._decision_reason or "").lower()
        assert _BYPASS_TOKEN not in reason, (
            "the recognized template-shipped entry must NOT carry a "
            f"WAVE_MARKER_BYPASS veto; got reason={self._decision_reason!r}. "
            f"{self._observed()}"
        )

    # ---- given (AT-2b) ------------------------------------------------------

    def given_ssot_and_templates_exist(self) -> None:
        """Name the AT-2b filesystem precondition: the SSOT home + four templates.

        Records the repo-relative paths the drift guard reconciles. Does NOT
        assert they are present -- the entry-marker Contract SSOT block is
        intentionally ABSENT at HEAD (that absence is AT-2b's RED reason, which
        the Then surfaces); asserting presence here would mis-locate the failure
        in the Given setup instead of the outcome.
        """
        self._reconciled_paths = (
            (REPO_ROOT / _CONTRACT_SSOT_REL),
            *(
                REPO_ROOT / "nWave" / "tasks" / "nw" / f"{t.value}.md"
                for t in CommandTemplate
            ),
        )

    # ---- when (AT-2b) -------------------------------------------------------

    def when_contract_and_templates_reconciled(self) -> None:
        """Reconcile the entry-marker Contract SSOT against the four templates.

        Pure Python + filesystem (git-free). Collects every divergence into
        ``_drift_findings``; the Then asserts the set is empty.
        """
        findings: list[str] = []
        contract_text = self._read_contract_ssot()

        # (a) the canonical Contract SSOT block must exist and declare the
        #     DES-WAVE-alone sufficiency rule.
        if contract_text is None:
            findings.append(
                f"the entry-marker Contract SSOT file {_CONTRACT_SSOT_REL!r} is "
                "absent / unreadable"
            )
        else:
            lowered = contract_text.lower()
            if _CONTRACT_ANCHOR.lower() not in lowered:
                findings.append(
                    f"the canonical anchor {_CONTRACT_ANCHOR!r} is absent from "
                    f"{_CONTRACT_SSOT_REL!r} -- the entry-marker contract is not "
                    "declared in its one canonical home (§22.7.A)"
                )
            if not all(p in lowered for p in _CONTRACT_SUFFICIENCY_PHRASES):
                findings.append(
                    "the Contract SSOT does not declare that a DES-WAVE marker "
                    "ALONE is sufficient for an entering dispatch (missing one of "
                    f"{_CONTRACT_SUFFICIENCY_PHRASES!r})"
                )

        # (b) each template must emit its DES-WAVE literal and impose no
        #     classic-marker REQUIREMENT on the entering dispatch.
        for template in CommandTemplate:
            findings.extend(self._template_divergences(template))

        # (c) the AT-2a fixture itself must agree: the DES-WAVE-only prompt the
        #     fixture ships for each AT-2a wave must carry that wave's entry
        #     marker AND carry NO classic _DES_MARKER_KEY token. This is the
        #     third arm of the three-way claim (contract <-> templates <->
        #     fixture); without it the original slice-07d fixture could drift to
        #     a classic-marker shape no template takes (Root Cause B) and this
        #     guard would never notice.
        for wave in (WaveUnderTest.DESIGN, WaveUnderTest.DISCUSS):
            findings.extend(self._fixture_divergences(wave))

        self._drift_findings = findings

    # ---- then (AT-2b) -------------------------------------------------------

    def then_contract_and_templates_agree(self) -> None:
        """The SSOT, the four templates, and the AT-2a fixture all agree (no drift)."""
        assert self._drift_findings == [], (
            "the entry-marker contract SSOT, the four command templates, and the "
            "DES-WAVE-only AT fixture must all agree -- a divergence is the "
            "fixture-theater drift that hid Root Cause B. Findings:\n  - "
            + "\n  - ".join(self._drift_findings)
        )

    # ---- driving-port invocation (AT-2a) ------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, wave_entering: bool) -> None:
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=wave_entering)
            )
        finally:
            os.chdir(prev_cwd)
        self._decision_action = decision.action
        self._decision_reason = decision.reason

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    # ---- contract / template readers (AT-2b, pure filesystem) ---------------

    def _read_contract_ssot(self) -> str | None:
        path = REPO_ROOT / _CONTRACT_SSOT_REL
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def _template_divergences(self, template: CommandTemplate) -> list[str]:
        """Return divergences for one template vs the entry-marker contract."""
        findings: list[str] = []
        path = REPO_ROOT / "nWave" / "tasks" / "nw" / f"{template.value}.md"
        if not path.is_file():
            return [f"command template {path.name!r} is absent / unreadable"]
        text = path.read_text(encoding="utf-8")
        marker = f"<!-- DES-WAVE: {template.value} -->"
        if marker not in text:
            findings.append(
                f"template {template.value!r} does not emit its entry marker "
                f"{marker!r} (the SSOT-declared sufficient entry shape)"
            )
        if self._requires_classic_markers_on_entry(text):
            findings.append(
                f"template {template.value!r} instructs the ENTERING dispatch to "
                "carry classic _DES_MARKER_KEY markers -- this contradicts the "
                "Contract SSOT (Approach (a): the entering dispatch is sufficiently "
                "marked by DES-WAVE alone; templates are NOT changed to co-emit "
                "classic markers)"
            )
        return findings

    def _fixture_divergences(self, wave: WaveUnderTest) -> list[str]:
        """Return divergences for the AT-2a fixture prompt vs the contract.

        The fixture (``_template_shipped_prompt``) is the prompt shape AT-2a
        drives the real service with. It must carry the wave's DES-WAVE entry
        marker and NONE of the classic ``_DES_MARKER_KEY`` tokens -- otherwise it
        re-introduces the slice-07d fixture drift (a classic-marker shape no
        template ships, which never reaches the :146 hinge -- Root Cause B).
        """
        findings: list[str] = []
        prompt = self._template_shipped_prompt(wave)
        marker = f"<!-- DES-WAVE: {wave.value} -->"
        if marker not in prompt:
            findings.append(
                f"the AT-2a fixture prompt for {wave.value!r} does not carry its "
                f"entry marker {marker!r} (the SSOT-declared sufficient entry shape)"
            )
        present_classic = [tok for tok in _CLASSIC_MARKER_TOKENS if tok in prompt]
        if present_classic:
            findings.append(
                f"the AT-2a fixture prompt for {wave.value!r} carries classic "
                f"_DES_MARKER_KEY tokens {present_classic!r} -- this is the "
                "slice-07d fixture drift (a classic-marker shape no template "
                "ships) the entering dispatch must NOT require (Root Cause B)"
            )
        return findings

    @staticmethod
    def _requires_classic_markers_on_entry(text: str) -> bool:
        """Detect a template POSITIVELY requiring classic markers on the ENTRY.

        A genuine drift (rejected Approach (b) / fixture-theater regression) is a
        single SENTENCE that, scoped to the ENTERING dispatch, frames a classic
        ``_DES_MARKER_KEY`` token as a positive requirement -- with NO negation
        prohibiting it.

        Three corrections over the naive whole-file ``any(token) AND any(word)``
        conjunction that false-positived on correct Approach-(a) prose
        (RCA: commit bb3d52546):

          1. **Sentence-scoping.** Evaluate at sentence granularity, not raw file
             lines. The correct entry paragraph fuses two sentences on one
             markdown line -- "Include the ``<!-- DES-WAVE: ... -->`` marker ..."
             (whose ``include`` governs DES-WAVE) and "Do not add
             ``DES-VALIDATION``/... to the ... entry dispatch ..." (a prohibition
             on the classic tokens). Splitting on sentence boundaries lets each be
             judged on its own; the conjunction can no longer fuse the ``include``
             of one with the classic tokens of the other.

          2. **Negation guard.** A sentence framing the classic tokens with an
             explicit prohibition (``do not add``, ``must not``, ``never``,
             ``exclude``, ``not ... co-emit``, ``can only add ... never remove``)
             is NOT a requirement -- it AFFIRMS Approach (a).

          3. **Entry-scoping.** The legitimate "In-wave child dispatch
             (non-entering)" paragraph DOES require the ``DES-*`` marker set, but
             that is the CHILD, not the ENTERING dispatch. A sentence belonging to
             the explicitly non-entering child clause is excluded -- its
             requirement is not attributed to the entry.

        Returns True only when one entry-scoped, non-negated sentence positively
        requires a classic token -- so it stays GREEN on the correct shipped
        templates and still fires on a real Approach-(b) regression.
        """
        requirement_words = ("require", "must", "include", "co-emit", "mandatory")
        negation_phrases = (
            "do not add",
            "do not include",
            "must not",
            "never add",
            "never carry",
            "never include",
            "exclude",
            "without",
            "no classic",
            "not co-emit",
            "can only add gating, never remove",
        )
        # A sentence belonging to the explicitly NON-ENTERING child clause: its
        # legitimate DES-marker requirement is the child's, never the entry's.
        non_entry_markers = (
            "non-entering",
            "in-wave child",
            "child dispatch",
            "child prompt",
            "a child",
            "the child",
            "further sub-agent",
            "already active",
            "not the entry dispatch",
        )

        for sentence in ContractSsotComposition._split_sentences(text):
            lowered = sentence.lower()
            if not any(tok in sentence for tok in _CLASSIC_MARKER_TOKENS):
                continue
            if not any(w in lowered for w in requirement_words):
                continue
            # The classic token is framed as a requirement in this sentence.
            # It is a genuine entry-drift ONLY if neither prohibited nor scoped
            # to the non-entering child dispatch.
            if any(neg in lowered for neg in negation_phrases):
                continue
            if any(scope in lowered for scope in non_entry_markers):
                continue
            return True
        return False

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split template prose into sentence-granular fragments.

        Sentence boundaries: terminal punctuation (``.``, ``;``, ``:``, ``!``,
        ``?``) and newlines. Coarse but sufficient -- it isolates the two clauses
        of the fused entry markdown line ("Include the DES-WAVE marker ..." vs
        "Do not add DES-VALIDATION/... to the entry dispatch ...") so each is
        judged independently. Em-dash (``—``) also splits, so the negation
        "can only ADD gating, never remove it" stays attached to its own clause.
        """
        import re

        fragments = re.split(r"[.;:!?\n—]+", text)
        return [frag.strip() for frag in fragments if frag.strip()]

    # ---- substrate plumbing -------------------------------------------------

    def _arm_floor(
        self, root: Path, wave: WaveUnderTest, *, entry_pending: bool
    ) -> None:
        import json

        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"wave": wave.value, "provenance": "command"}
        if entry_pending:
            record["entry_pending"] = True
        floor_path.write_text(json.dumps(record), encoding="utf-8")

    def _seed_product_ssot(self, root: Path) -> None:
        product_dir = root / _PRODUCT_DIR_REL
        product_dir.mkdir(parents=True, exist_ok=True)
        for doc in _SSOT_DOCS:
            (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")

    # ---- dispatch shape (AT-2a) ---------------------------------------------

    @staticmethod
    def _template_shipped_prompt(wave: WaveUnderTest) -> str:
        """The DES-WAVE-only shape the command template ships for ``wave``.

        Sourced from the template literal contract (``<!-- DES-WAVE: <wave> -->``
        alone) -- NOT a hand-built classic-marker set. This is the shape Root
        Cause B's fixture drift never exercised.
        """
        return f"<!-- DES-WAVE: {wave.value} -->\nbegin the {wave.value} wave"

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}); "
            f"wave={self._wave!r}; project_root={self._project_root!r}"
        )
