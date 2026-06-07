"""Composition root for the behavioral witness-check slice (slice-03).

Extends the slice-01 walking-skeleton composition (``composition.py``) with the
slice-03 outcome assertions for the behavioral witness core (ADR-001):

* **DT-7a + DT-7b** -- a clause earns ``witnessed`` ONLY when an acceptance test
  genuinely asserts its target's RETURN behaviour. DT-7 is split across two
  scenarios over THREE name-matched fixture poles so that ONLY a genuine
  wrong-RETURN-perturbation-with-AssertionError-from-AT-body gate passes; every
  cheaper gate is caught by at least one pole:
  - ``DT-GENUINE`` (``WitnessKind.GENUINE_ASSERTS_RETURN``: ``assert accept(1)
    is True``) -- passes on correct code, FAILS with an ``AssertionError`` on a
    wrong-RETURN-perturbed copy -> WITNESSED -> the gate stays SILENT (DT-7a).
  - ``DT-VACUOUS`` (``WitnessKind.EXECUTES_NO_ASSERT``: ``accept(1)`` only) --
    stays GREEN under perturbation -> SURVIVED -> the gate surfaces it (DT-7b).
    Catches the coverage-equivalent gate (witnessed-iff-executes warns about
    neither pole).
  - ``DT-EXEC-ASSERT-UNRELATED`` (``WitnessKind.EXEC_ASSERT_UNRELATED``:
    ``r = accept(1); assert 1 == 1``) -- executes the target AND has a genuine
    ``assert`` node, but the assertion is INDEPENDENT of the return value. A
    wrong-RETURN perturbation leaves the independent assert GREEN -> SURVIVED ->
    the gate surfaces it (DT-7b). This is the KEYSTONE pole (reviewer-mandated):
    it is the only shape that catches BOTH (a) a syntactic-assert-shape gate
    (has-assert / has-assert-referencing-target -> marks it witnessed because an
    ``assert`` node is present -> FAILS the surfacing assertion) AND (b) a
    coverage/crash-perturbation gate (the AT executes the target / a crash makes
    it RED -> marks it witnessed -> FAILS). Forces wrong-RETURN over crash,
    closing the slice-03/slice-04 reason-discrimination split coherence.

  DT-7a asserts the gate stays SILENT about DT-GENUINE (guards a
  warn-every-clause gate); DT-7b asserts the gate SURFACES both DT-VACUOUS and
  DT-EXEC-ASSERT-UNRELATED as ``survived`` (guards every non-behavioral gate).
  The two scenarios are @coupled (ADR-028 D2 escape): the 3-state witness
  verdict is one indivisible behavioral contract; the poles are vacuous in
  isolation, so they ship as a coupled discrimination set, not separate slices.

* **DT-8** -- the witness-check is git-free + tree-safe. The perturbation runs in
  an ISOLATED tmp copy; the REAL production source file the ``# target:`` names is
  byte-identical before and after; no ``git`` is invoked. The assertion captures
  the real source bytes before the hook runs and re-reads them after, asserting
  equality (a true tree-safety observable, stronger than "no git stash").

* **DT-12** -- a clause whose ``# target:`` does not resolve in the source tree is
  surfaced ``unwitnessed: target-unresolved`` LOUD, never a soft skip. The fixture
  name-matches the clause (slice-01 would stay silent) but points its ``# target:``
  at a symbol absent from the tree; the assertion is the gate SURFACES it loud.

DRIVING PORT (Mandate-13, unchanged from slice-01/02): the real
``handle_subagent_stop`` SubagentStop hook over its JSON stdin protocol as a
subprocess (Layer 3/4 wiring_e2e). slice-03 REUSES the slice-01 ``when`` verbatim
by subclassing; the NEW code is three behaviorally-rich ``Given`` substrate
builders (each plants real witnessing AT MODULES + a real production source file
under the tmp repo) and three ``Then`` assertions over the gate's stderr warning
surface (+ the real-source-byte observable for DT-8).

WHY RED NOW: ``ClauseWitnessPort`` / ``PerturbationWitnessAdapter`` do not exist
yet, and the shipped slice-01 gate is purely SYNTACTIC -- it marks every
name-matched clause ``witnessed-by-name`` and stays SILENT. So for every slice-03
fixture (whose clause IS name-matched) the current gate produces NO warning about
it. The slice-03 ``Then`` steps assert the gate DOES surface the vacuous /
unresolved clause -- which fails with a semantic ``AssertionError`` (the gate's
stderr carries no such warning). Never a collection / import / setup error: the
suite collects cleanly and the hook is driven as a subprocess. It PASSES once
DELIVER slice-03 wires the behavioral witness-check into the D_DISTILL branch.

NO production gate / port / adapter module is imported here for the SUT -- the SUT
is exercised only via the hook subprocess. ``AtCompletionLedger`` is reused ONLY
to seed the signed precondition verdict (substrate, the S2 tolerable-variant),
inherited from the slice-01 composition.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
that state. Step functions in ``test_g_traceability_gate_slice_03.py`` are thin
delegations to these methods (Mandate-12: no business logic in step bodies).
"""

from __future__ import annotations

from .composition import TraceabilityGateComposition
from .domain_types import ClauseVerdict, WitnessKind


# The slice-03 fixture clause-IDs. All are NAME-MATCHED in their feature carriers
# (so the shipped slice-01 syntactic gate stays silent about them) but each is
# behaviorally a distinct witness shape, so a genuine witness-check must
# discriminate them.
_GENUINE_CLAUSE = "DT-GENUINE"  # asserts the RETURN value -> must stay witnessed
_VACUOUS_CLAUSE = "DT-VACUOUS"  # executes, asserts nothing -> survived
# KEYSTONE pole (reviewer-mandated): executes + has a genuine `assert` that is
# INDEPENDENT of the return value -> survived. The only pole that catches BOTH a
# syntactic-assert-shape gate AND a coverage/crash-perturbation gate.
_EXEC_ASSERT_UNRELATED_CLAUSE = "DT-EXEC-ASSERT-UNRELATED"
_TREE_SAFE_CLAUSE = "DT-TREESAFE"  # checked against a real source file (DT-8)
_UNRESOLVED_CLAUSE = "DT-NOTARGET"  # # target: names an absent symbol (DT-12)

# The unwitnessed-semantics tokens the gate's warning must carry adjacent to a
# DOWNGRADED clause-ID. These are the slice-03 behavioral verdicts (sourced from
# the typed domain vocabulary), distinct from slice-01's `unwitnessed-no-at`: a
# behaviorally-downgraded clause is `survived` / `target-unresolved`, NOT
# `unwitnessed-no-at` (it HAS a name-matched AT; the AT just does not witness).
_SURVIVED_TOKENS: tuple[str, ...] = (
    ClauseVerdict.SURVIVED.value,  # "survived"
    "survived",
    "does not assert",
    "asserts nothing",
    "unwitnessed",
)
_TARGET_UNRESOLVED_TOKENS: tuple[str, ...] = (
    ClauseVerdict.TARGET_UNRESOLVED.value,  # "target-unresolved"
    "target-unresolved",
    "target unresolved",
    "cannot be located",
    "could not resolve",
)

# The real production source the DT-8 witness-check resolves + perturbs IN A COPY.
# The fixture plants this under the tmp repo's src/ tree so the `# target:` of
# the DT-TREESAFE clause resolves to a real on-disk symbol.
_TREE_SAFE_TARGET_MODULE_PATH = ("src", "probeapp", "widget.py")
_TREE_SAFE_TARGET_DOTTED = "probeapp.widget::accept"
_TREE_SAFE_SOURCE = (
    '"""Probe production target for the DT-8 tree-safety witness-check."""\n'
    "\n\n"
    "def accept(value: int) -> bool:\n"
    '    """Return True iff value is positive (the behaviour the AT asserts)."""\n'
    "    return value > 0\n"
)


class TraceabilityWitnessComposition(TraceabilityGateComposition):
    """slice-03 composition: behavioral witness core (DT-7, DT-8, DT-12).

    Inherits the slice-01 ``when`` (drive the real hook subprocess) + the signed
    -verdict precondition seed. Adds three behaviorally-rich ``Given`` substrate
    builders and three ``Then`` assertions over the gate's witness verdict.
    """

    # ---- given (slice-03 behavioral substrate) -------------------------

    def given_genuine_and_two_non_asserting_clauses(self) -> None:
        """DT-7 (a+b): three name-matched clauses of three distinct witness shapes.

        One feature-delta carries all three poles (slice-01 stays silent about
        all three because all are name-matched):
        - ``DT-GENUINE`` asserts the target's RETURN value -> WITNESSED.
        - ``DT-VACUOUS`` executes the target, asserts nothing -> SURVIVED.
        - ``DT-EXEC-ASSERT-UNRELATED`` executes the target AND has a genuine
          ``assert`` that is INDEPENDENT of the return value -> SURVIVED.

        Only a genuine wrong-RETURN-perturbation-with-AssertionError-from-AT-body
        gate keeps DT-GENUINE silent (DT-7a) AND surfaces BOTH non-asserting poles
        (DT-7b). The keystone third pole is what makes a syntactic-assert-shape
        gate and a coverage/crash-perturbation gate both FAIL.
        """
        self._ensure_project()
        self._write_decision_table(
            [_GENUINE_CLAUSE, _VACUOUS_CLAUSE, _EXEC_ASSERT_UNRELATED_CLAUSE]
        )
        self._plant_witness_target()
        self._write_witnessing_at(_GENUINE_CLAUSE, WitnessKind.GENUINE_ASSERTS_RETURN)
        self._write_witnessing_at(_VACUOUS_CLAUSE, WitnessKind.EXECUTES_NO_ASSERT)
        self._write_witnessing_at(
            _EXEC_ASSERT_UNRELATED_CLAUSE, WitnessKind.EXEC_ASSERT_UNRELATED
        )
        self._seed_signed_verdict_for_planned_slice()

    def given_clause_checked_against_real_source(self) -> None:
        """DT-8: a name-matched clause checked against a real production source.

        Captures the real source bytes as the before-snapshot so the Then-step
        can assert the witness-check left them byte-identical.
        """
        self._ensure_project()
        self._write_decision_table([_TREE_SAFE_CLAUSE])
        self._plant_witness_target()
        self._capture_real_source_before()
        self._write_witnessing_at(_TREE_SAFE_CLAUSE, WitnessKind.GENUINE_ASSERTS_RETURN)
        self._seed_signed_verdict_for_planned_slice()

    def given_clause_with_unresolvable_target(self) -> None:
        """DT-12: a name-matched clause whose `# target:` names an absent symbol.

        slice-01 stays silent (it is name-matched). A genuine witness-check must
        surface it LOUD as target-unresolved, never a soft skip.
        """
        self._ensure_project()
        self._write_decision_table([_UNRESOLVED_CLAUSE])
        self._write_unresolved_target_at(_UNRESOLVED_CLAUSE)
        self._seed_signed_verdict_for_planned_slice()

    # ---- then (slice-03 behavioral outcomes) ---------------------------

    def then_surfaces_both_non_asserting_clauses(self) -> None:
        """DT-7b surfacing half: BOTH non-asserting poles are surfaced survived.

        Both clauses are name-matched, so slice-01's syntactic gate stays SILENT
        about both -- the RED. A genuine wrong-RETURN-perturbation gate downgrades
        BOTH to ``survived``:
        - ``DT-VACUOUS`` (executes, asserts nothing) -- catches the
          coverage-equivalent gate.
        - ``DT-EXEC-ASSERT-UNRELATED`` (executes + genuine assert independent of
          the return) -- the KEYSTONE: catches the syntactic-assert-shape gate
          (which would mark it witnessed because an ``assert`` node is present)
          AND the crash-perturbation gate (which would mark it witnessed because
          the AT executes the target). Only a wrong-RETURN-perturbation gate that
          observes the AT staying GREEN surfaces it as survived.
        """
        self._assert_clause_downgraded(_VACUOUS_CLAUSE, _SURVIVED_TOKENS)
        self._assert_clause_downgraded(_EXEC_ASSERT_UNRELATED_CLAUSE, _SURVIVED_TOKENS)

    def then_silent_about_genuine_clause(self) -> None:
        """DT-7a: the genuinely-asserting clause keeps its witness (stays silent).

        NON-VACUITY (the DT-5 trap the reviewer flagged): a bare ``DT-GENUINE not
        in warning`` would pass VACUOUSLY at RED -- the syntactic gate is silent
        about ALL name-matched clauses, so the silence is satisfied for free
        whether or not the witness-check ran. To give DT-7a teeth NOW, the silence
        guarantee is BOUND to proof that the gate actually ran the differential:
        the keystone ``DT-EXEC-ASSERT-UNRELATED`` pole MUST be surfaced as
        ``survived`` (a gate that did not run the wrong-RETURN witness-check
        cannot reach that verdict). So this step asserts the CONJUNCTION
        "the gate surfaced the keystone non-asserting pole AND stayed silent about
        the genuinely-asserting pole". At RED (witness-check absent) the
        surfaced-keystone sub-assert FAILS with a semantic AssertionError -- a
        genuine RED, not a vacuous pass. At GREEN a warn-every-clause gate flips
        this RED on the silence sub-assert (it would surface DT-GENUINE); a
        coverage / syntactic-assert / crash gate flips it on the keystone
        sub-assert (it would NOT surface the keystone). Only a true wrong-RETURN
        differential gate satisfies both. (DT-7b independently asserts BOTH
        non-asserting poles are surfaced; DT-7a couples silence to discrimination.)
        """
        self._assert_clause_downgraded(_EXEC_ASSERT_UNRELATED_CLAUSE, _SURVIVED_TOKENS)
        warning = self._warning_text()
        assert _GENUINE_CLAUSE not in warning, (
            f"the genuinely-asserting clause {_GENUINE_CLAUSE!r} was wrongly "
            f"surfaced as unwitnessed; a genuine witness-check must keep an AT "
            f"that truly asserts its target's RETURN value silent (DT-7a "
            f"non-vacuity). {self._observed()}"
        )

    def then_real_source_byte_identical(self) -> None:
        """DT-8: the real production source file is byte-identical after the run.

        A true tree-safety observable: the perturbation must happen in an
        isolated copy, never on the live file. Re-reads the real source and
        asserts it equals the before-snapshot.
        """
        assert self._project_root is not None
        before = self._source_before
        assert before is not None, (
            "the real-source before-snapshot must be captured (Given) before "
            "asserting byte-identity (Then)"
        )
        after = self._real_source_path().read_bytes()
        assert after == before, (
            "the witness-check mutated the REAL production source file at "
            f"{self._real_source_path()!s}; the perturbation must run in an "
            "isolated copy, leaving the live tree byte-identical (DT-8 "
            f"tree-safety). before={len(before)}B after={len(after)}B. "
            f"{self._observed()}"
        )

    def then_no_version_control_used(self) -> None:
        """DT-8 git-free half: the witness-check undoes its perturbation by
        discard, not by version control.

        Observable proxy for "no git invoked to revert": the tmp repo's git
        working tree is clean of any traceability-introduced perturbation
        artifact AND the gate produced its verdict (warning present) -- i.e. the
        revert was by sandbox-discard, not a git checkout of a mutated live file.
        Binds to the gate having RUN (warning present) so a vacuous pass on the
        seeded substrate alone is impossible. At RED the warning is absent -> it
        fails here too, consistent with the other scenarios.
        """
        self._assert_clause_downgraded(
            _TREE_SAFE_CLAUSE, _SURVIVED_TOKENS + ("witnessed",)
        )

    def then_surfaces_unresolved_target(self) -> None:
        """DT-12: the clause is surfaced loud as target-unresolved.

        Name-matched, so slice-01 stays silent -- the RED. A genuine
        witness-check, unable to resolve the `# target:`, must surface it loud as
        target-unresolved rather than letting the syntactic name-match pass.
        """
        self._assert_clause_downgraded(_UNRESOLVED_CLAUSE, _TARGET_UNRESOLVED_TOKENS)

    # ---- assertion helpers ---------------------------------------------

    def _assert_clause_downgraded(
        self, clause_id: str, expected_tokens: tuple[str, ...]
    ) -> None:
        """Assert the gate surfaced ``clause_id`` as behaviorally unwitnessed.

        Stronger than slice-01's `unwitnessed-no-at`: the clause HAS a
        name-matched AT, so a syntactic gate stays silent. The warning must name
        the clause AND carry one of the behavioral-downgrade tokens.
        """
        warning = self._warning_text()
        assert clause_id in warning, (
            "the behavioral witness-check did not surface the clause "
            f"{clause_id!r} as unwitnessed in its loud warning; a name-matched "
            "clause whose AT does not genuinely witness it (or whose target "
            "cannot be resolved) must be downgraded, not left silently "
            f"witnessed-by-name. {self._observed()}"
        )
        assert any(token in warning for token in expected_tokens), (
            f"the warning named {clause_id!r} but did not bind it to a "
            f"behavioral-downgrade verdict (expected one of {expected_tokens!r}); "
            "a syntactic name-match gate cannot reach this verdict. "
            f"{self._observed()}"
        )

    # ---- behavioral substrate plumbing (NOT the SUT) -------------------

    def _plant_witness_target(self) -> None:
        """Plant the real production source the `# target:` resolves + perturbs."""
        assert self._project_root is not None
        target = self._real_source_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_TREE_SAFE_SOURCE, encoding="utf-8")

    def _real_source_path(self):
        """Path to the planted real production source under the tmp repo."""
        assert self._project_root is not None
        return self._project_root.joinpath(*_TREE_SAFE_TARGET_MODULE_PATH)

    def _capture_real_source_before(self) -> None:
        """Snapshot the real source bytes for the DT-8 byte-identity assertion."""
        self._plant_witness_target()
        self._source_before = self._real_source_path().read_bytes()

    # The witnessing AT body per WitnessKind. The keystone EXEC_ASSERT_UNRELATED
    # body executes the target (coverage-positive) AND has a genuine `assert`
    # node, but the assertion (`assert 1 == 1`) is INDEPENDENT of the target's
    # return -> a wrong-RETURN perturbation leaves it GREEN -> survived. This is
    # the body a syntactic-assert-shape gate cannot tell apart from the genuine
    # one, and a crash-perturbation gate cannot tell apart from the genuine one --
    # only a wrong-RETURN-perturbation gate observing GREEN classifies it survived.
    _WITNESS_BODY: dict[WitnessKind, str] = {
        WitnessKind.GENUINE_ASSERTS_RETURN: "    assert accept(1) is True\n",
        WitnessKind.EXECUTES_NO_ASSERT: "    accept(1)\n",
        WitnessKind.EXEC_ASSERT_UNRELATED: "    r = accept(1)\n    assert 1 == 1\n",
    }

    def _write_witnessing_at(self, clause_id: str, kind: WitnessKind) -> None:
        """Author a witnessing `.feature` (carrier) + executable AT of `kind`.

        Resolvable-target variant: the `# target:` points at the planted real
        source symbol. The body shape is selected by the typed ``WitnessKind``
        (Mandate-12: a typed domain noun, not a raw bool/str flag).
        """
        self._author_witness(
            clause_id=clause_id,
            target=_TREE_SAFE_TARGET_DOTTED,
            body=self._WITNESS_BODY[kind],
        )

    def _write_unresolved_target_at(self, clause_id: str) -> None:
        """A `.feature` whose `# target:` names a symbol absent from the tree.

        The witnessing AT body genuinely asserts (so the only reason it cannot be
        witnessed is the unresolvable target, isolating the DT-12 contract from
        the DT-7 vacuity contract).
        """
        self._author_witness(
            clause_id=clause_id,
            target="probeapp.widget::does_not_exist",
            body=self._WITNESS_BODY[WitnessKind.GENUINE_ASSERTS_RETURN],
        )

    def _author_witness(self, clause_id: str, target: str, body: str) -> None:
        """Write the carrier `.feature` + the executable witnessing AT module.

        The carrier comment (`# clause:` + `# target:`) is the SSOT the gate
        parses; the executable AT module is what the behavioral witness-check
        RUNS (baseline + perturbed). Both land under the tmp repo's
        tests/acceptance/<feature-id>/ tree so the gate discovers them.
        """
        assert self._project_root is not None
        at_dir = self._project_root / "tests" / "acceptance" / clause_id.lower()
        at_dir.mkdir(parents=True, exist_ok=True)
        feature = (
            "Feature: Probe behaviour\n\n"
            f"  # clause: {clause_id}\n"
            f"  # target: {target}\n"
            f"  Scenario: behaviour witnessing {clause_id}\n"
            "    Given a probe input\n"
            "    When the target is exercised\n"
            "    Then the outcome holds\n"
        )
        (at_dir / f"g-{clause_id.lower()}.feature").write_text(
            feature, encoding="utf-8"
        )
        at_module = (
            '"""Witnessing acceptance test for ' + clause_id + '."""\n'
            "\n"
            "from probeapp.widget import accept\n"
            "\n\n"
            "def test_witness():\n" + body
        )
        (at_dir / f"test_g_{clause_id.lower()}.py").write_text(
            at_module, encoding="utf-8"
        )
