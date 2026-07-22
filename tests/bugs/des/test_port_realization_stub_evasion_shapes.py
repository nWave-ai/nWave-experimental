"""RED regression test: the port-realization stub classifier is a SHAPE ALLOWLIST.

Defect (measured, not theorised). ``_is_pure_notimplementederror_stub``
(``src/des/testarch/port_realization_discovery.py:138-181``) classifies a
language-adapter facet method as a stub ONLY when its body is EXACTLY one
``raise NotImplementedError``, after stripping at most one leading docstring.
Its default answer for every UNRECOGNISED body is "real". It is an allowlist
for one spelling of a stub, where the gate's charter needs a WORK-CHECK.

The gate it feeds -- ``python -m scripts.cli.validate_language_adapter_catalog
--check-port-realization`` -- is wired BLOCKING into the pre-push hook
(``.pre-commit-config.yaml``) and CI (``.github/workflows/ci.yml``). Its
charter is "make partial language support impossible". It does not.

Measured today, one synthetic plugin per shape, each declaring its port
``True`` in ``port_coverage``:

    CONTROL   bare `raise NotImplementedError`              exit 1  flagged
    EVASION A `...` then `raise NotImplementedError`        exit 0  MISSED
    EVASION B never raises, does nothing (return/pass/...)  exit 0  MISSED
    EVASION C subclasses the real Protocol, overrides none  exit 0  MISSED
    EVASION D body is only a docstring                      exit 0  MISSED
    EVASION E `raise RuntimeError("not implemented yet")`   exit 0  MISSED
    ORACLE    a genuine, minimal implementation             exit 0  CORRECT

EVASION C is the most serious and it is NOT adversarial: ``EnvironmentalE2EPort``
and ``RobustnessDensityPort`` are ``typing.Protocol`` classes whose method
bodies are ``[docstring, ...]``. Inheriting one for type-checker help is the
natural thing a well-meaning author does; ``getattr`` then resolves to the
Protocol's ``...`` body and the gate certifies a facet in which NO method is
implemented at all.

WHY the 53 existing tests missed this -- do not repeat their mistake. The
probe-contract AT file
(``tests/build/language_port_realization_gate/acceptance/test_port_realization_discovery.py``)
has 3 positive stub cases, ALL ``NotImplementedError`` raises, and 6
``@negative_at`` cases, ALL PRECISION-side ("does it avoid firing on real
code?"). Not one is RECALL-side ("does it fire on fake code that is not the
known stub?"). And they were authored from the SAME design sentence as the
implementation, so they could not falsify it. Every assertion here therefore
pins the FLAGGED OUTCOME (exit code + printed diagnostic), never "matches
shape X" -- so it stays valid across a change of criterion.

Charter (the independently-authored oracle Vera examines against):
``docs/product/expectations/fix-port-realization-stub-evasion/
a-plugin-that-only-pretends-to-support-a-capability-cannot-be-pushed.md``
Negative oracles: N-1 no do-nothing spelling passes; N-2 honest plugins are
never refused; N-3 a refusal always names plugin + capability; N-4
"conformant" is never printed having inspected nothing.

BOTH-DIRECTION obligation. The fix must not become a pass-all in the other
direction -- that would be WORSE than the hole, because it trains maintainers
to ignore the gate. RECALL scenarios (must be FLAGGED) and PRECISION
scenarios (must NOT be flagged, all ``@negative_at``) are therefore weighted
equally here; the precision half is the oracle that matters most.

Known-accepted residuals, deliberately NOT closed and NOT tested as gaps: a
constant return that fakes success (``return {"verdict": "PASS"}``) and a
log-only single-``Expr(Call)`` body still pass -- the SHIPPED
``PythonEnvironmentalE2EAdapter.run_against_installed`` IS a single
``Expr(Call)``, so any rule excluding it would fire on production code. Both
are pinned on the PRECISION side so an over-correction is caught.

Driving surface (Mandate-16 driving-port-only): drives the real
composition-root gate runner ``run_port_realization_gate`` -- the same symbol
the CLI's ``main()`` dispatches to for ``--check-port-realization`` -- in
process, Layer 3 composition, mirroring the sibling
``test_port_realization_gate_refuses_zero_probed.py``.

Author-only: this file authors the RED test. A crafter fixes the classifier
against it later. Do not weaken, skip, or rewrite these assertions to make
them pass.
"""

from __future__ import annotations

import pytest

from scripts.cli.validate_language_adapter_catalog import (
    PORT_REALIZATION_GATE_CONFORMANT,
    PORT_REALIZATION_GATE_GAP,
    run_port_realization_gate,
)
from tests.build.language_port_realization_gate.acceptance.synthetic_language_adapter_fixtures import (
    CHECK_ROBUSTNESS_DENSITY,
    VERIFY_ENVIRONMENTAL_E2E,
    EvasionDocstringOnlyRobustnessAdapter,
    EvasionEllipsisThenRaiseRobustnessAdapter,
    EvasionInheritedProtocolEnvironmentalE2EAdapter,
    EvasionInheritedProtocolRobustnessAdapter,
    EvasionMethodAbsentRobustnessAdapter,
    EvasionReturnNotImplementedRobustnessAdapter,
    EvasionRuntimeErrorRaiseRobustnessAdapter,
    EvasionSilentBareReturnRobustnessAdapter,
    EvasionSilentEllipsisRobustnessAdapter,
    EvasionSilentPassRobustnessAdapter,
    EvasionSilentReturnNoneRobustnessAdapter,
    HonestAttributeReturnRobustnessAdapter,
    HonestConditionalRaiseRobustnessAdapter,
    HonestConstantReturnRobustnessAdapter,
    HonestDelegatingRobustnessAdapter,
    HonestDocstringThenWorkRobustnessAdapter,
    HonestEarlyReturnRobustnessAdapter,
    HonestRealEnvironmentalE2EAdapter,
    HonestSideEffectingCallRobustnessAdapter,
    HonestTryExceptRaiseRobustnessAdapter,
    StubFixtureRobustnessDensityAdapter,
    SyntheticShapeProbeEnvironmentalE2EPlugin,
    SyntheticShapeProbeRobustnessPlugin,
)


# ---------------------------------------------------------------------------
# Reason vocabulary. The RCA proposes reason CODES so a refusal says something
# TRUE and SPECIFIC about why: RAISES_NOT_IMPLEMENTED / ALWAYS_RAISES /
# NO_OBSERVABLE_EFFECT / INHERITED_UNIMPLEMENTED / ABSENT. Asserted as
# any-of-these-substrings (case-insensitive) rather than exact-string equality
# so the crafter keeps latitude over the exact wording, while the CONTENT
# obligation stays firm. Today's single wording is "method `X` is a stub" --
# for a silent no-op that is not the clearest TRUE thing: a maintainer greps
# for NotImplementedError, finds none, and concludes the gate is broken.
# ---------------------------------------------------------------------------

_REASON_RAISES_NOT_IMPLEMENTED = (
    "raises_not_implemented",
    "notimplementederror",
    "not implemented",
)
_REASON_NO_OBSERVABLE_EFFECT = (
    "no_observable_effect",
    "no observable effect",
    "no effect",
    "does no work",
    "does nothing",
    "never does anything",
)
_REASON_ALWAYS_RAISES = (
    "always_raises",
    "always raises",
    "unconditional",
    "unconditionally raises",
)
_REASON_INHERITED_UNIMPLEMENTED = (
    "inherited_unimplemented",
    "inherited",
    "protocol",
)
_REASON_ABSENT = (
    "absent",
    "missing",
    "not defined",
    "does not define",
    "no such method",
)

# A shape whose body NEVER mentions NotImplementedError must not be described
# as raising one -- a false diagnostic is a failed refusal even when the
# verdict is right (charter N-3).
_FORBID_NIE = ("notimplementederror",)
_FORBID_NOTHING: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# RECALL corpus -- every shape a maintainer might plausibly write behind a
# claimed capability. `(case_id, plugin_id, plugin_factory, adapter_factory,
# port, reason_tokens, forbidden_tokens)`.
#
# `case_id` is the human-readable pytest id; `plugin_id` is the identifier the
# synthetic plugin reports as its `target_language` and which the gate echoes
# into its diagnostic. They are DELIBERATELY different: an earlier revision
# reused the descriptive id as the plugin id, and words like "absent" /
# "notimplementederror" inside it then satisfied the reason-token assertions
# by accident -- the gate got credit for a reason it never printed. Every
# `plugin_id` below is checked to contain NONE of the reason vocabulary above,
# so a reason assertion can only pass on text the gate itself produced.
# ---------------------------------------------------------------------------

_RECALL_SHAPES: tuple[
    tuple[str, str, object, object, str, tuple[str, ...], tuple[str, ...]], ...
] = (
    (
        "control-bare-raise-notimplementederror",
        "lang-alpha",
        SyntheticShapeProbeRobustnessPlugin,
        StubFixtureRobustnessDensityAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_RAISES_NOT_IMPLEMENTED,
        _FORBID_NOTHING,
    ),
    (
        "evasion-a-ellipsis-then-raise",
        "lang-bravo",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionEllipsisThenRaiseRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_RAISES_NOT_IMPLEMENTED,
        _FORBID_NOTHING,
    ),
    (
        "evasion-b1-silent-return-none",
        "lang-charlie",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionSilentReturnNoneRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-b2-silent-pass",
        "lang-delta",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionSilentPassRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-b3-silent-bare-ellipsis",
        "lang-echo",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionSilentEllipsisRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-b4-silent-bare-return",
        "lang-foxtrot",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionSilentBareReturnRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-b5-return-notimplemented-sentinel",
        "lang-golf",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionReturnNotImplementedRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NOTHING,
    ),
    (
        "evasion-c-inherits-robustness-protocol-overrides-nothing",
        "lang-hotel",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionInheritedProtocolRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_INHERITED_UNIMPLEMENTED + _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-c-inherits-e2e-protocol-overrides-nothing",
        "lang-india",
        SyntheticShapeProbeEnvironmentalE2EPlugin,
        EvasionInheritedProtocolEnvironmentalE2EAdapter,
        VERIFY_ENVIRONMENTAL_E2E,
        _REASON_INHERITED_UNIMPLEMENTED + _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-d-docstring-only-body",
        "lang-juliett",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionDocstringOnlyRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_NO_OBSERVABLE_EFFECT,
        _FORBID_NIE,
    ),
    (
        "evasion-e-unconditional-non-notimplementederror-raise",
        "lang-kilo",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionRuntimeErrorRaiseRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_ALWAYS_RAISES,
        _FORBID_NIE,
    ),
    (
        "evasion-f-port-method-absent-from-facet",
        "lang-lima",
        SyntheticShapeProbeRobustnessPlugin,
        EvasionMethodAbsentRobustnessAdapter,
        CHECK_ROBUSTNESS_DENSITY,
        _REASON_ABSENT,
        _FORBID_NOTHING,
    ),
)

_RECALL_IDS = [shape[0] for shape in _RECALL_SHAPES]

_ALL_REASON_TOKENS = (
    _REASON_RAISES_NOT_IMPLEMENTED
    + _REASON_NO_OBSERVABLE_EFFECT
    + _REASON_ALWAYS_RAISES
    + _REASON_INHERITED_UNIMPLEMENTED
    + _REASON_ABSENT
)


def _run_shape(plugin_id: str, plugin_factory: object, adapter_factory: object) -> int:
    """Drive the real gate runner over ONE synthetic plugin carrying ONE shape."""
    plugin = plugin_factory(plugin_id, adapter_factory())  # type: ignore[operator]
    return run_port_realization_gate([plugin])


def test_no_synthetic_plugin_id_can_satisfy_a_reason_assertion_by_accident() -> None:
    """Meta-guard: the fixture ids must not contain the reason vocabulary.

    Without this, a plugin named e.g. ``...-absent-...`` makes the gate's
    echoed identifier satisfy the ABSENT reason token and the reason
    assertions pass while the gate prints no reason at all -- a self-inflicted
    false green of exactly the kind this whole file exists to prevent.
    """
    contaminated = {
        plugin_id: [token for token in _ALL_REASON_TOKENS if token in plugin_id]
        for _, plugin_id, *_ in _RECALL_SHAPES
    }
    offenders = {pid: hits for pid, hits in contaminated.items() if hits}

    assert not offenders, (
        f"these synthetic plugin ids embed reason vocabulary the gate echoes "
        f"back, so a reason assertion could pass on the test's own text "
        f"rather than the gate's: {offenders!r}"
    )


# ---------------------------------------------------------------------------
# 1. RECALL -- every do-nothing spelling behind a `True` claim is REFUSED.
#    Charter oracle N-1. RED today for every shape except the CONTROL.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("shape_id", "plugin_factory", "adapter_factory", "port"),
    [(s[1], s[2], s[3], s[4]) for s in _RECALL_SHAPES],
    ids=_RECALL_IDS,
)
def test_gate_refuses_every_do_nothing_shape_behind_a_claimed_capability(
    shape_id: str,
    plugin_factory: object,
    adapter_factory: object,
    port: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A claim backed by a body that does no work must never exit 0.

    The gate's whole promise is "partial language support cannot be pushed".
    A plugin declaring ``port_coverage[<port>] = True`` while the code behind
    the claim does nothing is exactly the partial support the gate exists to
    block -- in EVERY spelling, not only the one the classifier happens to
    recognise. Probed one shape per case so catching one cannot mask a blind
    spot in another (charter: "do not settle for one probe").
    """
    exit_code = _run_shape(shape_id, plugin_factory, adapter_factory)
    combined_output = "".join(capsys.readouterr())

    assert exit_code != PORT_REALIZATION_GATE_CONFORMANT, (
        f"shape {shape_id!r} declares {port!r} True while doing no work, yet "
        f"the gate certified it CONFORMANT (exit 0). Partial language "
        f"support just shipped. output={combined_output!r}"
    )
    assert exit_code == PORT_REALIZATION_GATE_GAP, (
        f"shape {shape_id!r} is an unbacked capability CLAIM -- expected the "
        f"GAP lane ({PORT_REALIZATION_GATE_GAP}), got exit {exit_code}. "
        f"output={combined_output!r}"
    )
    assert "conformant" not in combined_output.lower(), (
        f"shape {shape_id!r} must never be described with green/success "
        f"wording: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 2. RECALL diagnostic -- a refusal NAMES which plugin and which capability.
#    Charter oracle N-3: an anonymous refusal is a failed refusal even when
#    the verdict is right.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("shape_id", "plugin_factory", "adapter_factory", "port"),
    [(s[1], s[2], s[3], s[4]) for s in _RECALL_SHAPES],
    ids=_RECALL_IDS,
)
def test_refusal_is_never_anonymous_it_names_plugin_and_capability(
    shape_id: str,
    plugin_factory: object,
    adapter_factory: object,
    port: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ "Port realization check failed" with no names is a failed refusal.

    The maintainer must be able to act without opening a source file: the
    output names WHICH plugin and WHICH capability carries the unbacked
    claim.
    """
    _run_shape(shape_id, plugin_factory, adapter_factory)
    combined_output = "".join(capsys.readouterr())

    assert shape_id in combined_output, (
        f"the refusal does not name the offending plugin {shape_id!r}: "
        f"{combined_output!r}"
    )
    assert port in combined_output, (
        f"the refusal does not name the unbacked capability {port!r}: "
        f"{combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 3. RECALL diagnostic -- the refusal says something TRUE and SPECIFIC about
#    WHY. Today every gap prints the one wording "method `X` is a stub"; for a
#    silent no-op that is not the clearest true thing (grep NotImplementedError
#    -> nothing -> "the gate is broken").
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape_id", "plugin_factory", "adapter_factory", "reason_tokens", "forbidden"),
    [(s[1], s[2], s[3], s[5], s[6]) for s in _RECALL_SHAPES],
    ids=_RECALL_IDS,
)
def test_refusal_reason_is_specific_to_the_shape_and_never_false(
    shape_id: str,
    plugin_factory: object,
    adapter_factory: object,
    reason_tokens: tuple[str, ...],
    forbidden: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The WHY names the actual defect class, and never asserts a falsehood.

    Any of the shape's acceptable reason tokens satisfies the obligation
    (content, not exact wording). The forbidden tokens are the FALSE claims:
    a body that never mentions ``NotImplementedError`` must not be reported
    as raising one.
    """
    _run_shape(shape_id, plugin_factory, adapter_factory)
    lowered = "".join(capsys.readouterr()).lower()

    assert any(token in lowered for token in reason_tokens), (
        f"shape {shape_id!r}: the refusal carries no specific reason -- "
        f"expected one of {reason_tokens}, got {lowered!r}"
    )
    for false_claim in forbidden:
        assert false_claim not in lowered, (
            f"shape {shape_id!r}: the refusal makes a FALSE claim "
            f"({false_claim!r}) about a body that never uses it -- a wrong "
            f"WHY sends the maintainer looking for something that is not "
            f"there: {lowered!r}"
        )


# ---------------------------------------------------------------------------
# 4. RECALL -- the shapes differ in the MESSAGE, never in the VERDICT.
#    Charter: "no spelling of 'not implemented yet' is treated as more
#    acceptable than another".
# ---------------------------------------------------------------------------


def test_verdict_is_identical_across_shapes_while_the_message_distinguishes_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same verdict for every fake; different explanation for each.

    A verdict that varies by spelling would make one way of writing "I do
    nothing" more acceptable than another. A message that does NOT vary
    leaves the maintainer with a WHY that is wrong for most shapes.
    """
    probed = {
        "lang-mike": StubFixtureRobustnessDensityAdapter,
        "lang-november": EvasionSilentReturnNoneRobustnessAdapter,
        "lang-oscar": EvasionInheritedProtocolRobustnessAdapter,
    }

    verdicts: dict[str, int] = {}
    messages: dict[str, str] = {}
    for shape_id, adapter_factory in probed.items():
        verdicts[shape_id] = _run_shape(
            shape_id, SyntheticShapeProbeRobustnessPlugin, adapter_factory
        )
        messages[shape_id] = "".join(capsys.readouterr())

    assert len(set(verdicts.values())) == 1, (
        f"the VERDICT must not vary by spelling -- one shape is being treated "
        f"as more acceptable than another: {verdicts!r}"
    )
    assert set(verdicts.values()) == {PORT_REALIZATION_GATE_GAP}, (
        f"all three shapes are unbacked claims and must all land in the GAP "
        f"lane ({PORT_REALIZATION_GATE_GAP}): {verdicts!r}"
    )

    # Strip the per-plugin identifier so the comparison is about the REASON,
    # not about the plugin name each message trivially echoes.
    reasons = {
        shape_id: message.replace(shape_id, "<plugin>")
        for shape_id, message in messages.items()
    }
    assert len(set(reasons.values())) == len(reasons), (
        f"the MESSAGE must distinguish the shapes -- every fake currently "
        f"gets the same explanation, so the WHY is wrong for most of them: "
        f"{reasons!r}"
    )


# ---------------------------------------------------------------------------
# 5. PRECISION -- a genuinely REAL, MINIMAL implementation is never branded a
#    stub. Charter oracle N-2. A gate that cries wolf is a gate maintainers
#    learn to ignore and then switch off; the over-correction into a pass-all
#    would be WORSE than the hole this fix closes.
# ---------------------------------------------------------------------------

_HONEST_ROBUSTNESS_SHAPES = (
    ("honest-one-line-delegation", HonestDelegatingRobustnessAdapter),
    ("honest-attribute-return", HonestAttributeReturnRobustnessAdapter),
    ("honest-constant-return", HonestConstantReturnRobustnessAdapter),
    ("honest-docstring-then-work", HonestDocstringThenWorkRobustnessAdapter),
    ("honest-early-return-guard", HonestEarlyReturnRobustnessAdapter),
)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("shape_id", "adapter_factory"),
    _HONEST_ROBUSTNESS_SHAPES,
    ids=[shape_id for shape_id, _ in _HONEST_ROBUSTNESS_SHAPES],
)
def test_gate_does_not_refuse_a_thin_but_honest_implementation(
    shape_id: str,
    adapter_factory: object,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Short, thin, early-returning -- but REAL -- must not be called a stub.

    Several spellings, not one: the fix must recognise work, not a second
    allowlist of "acceptable-looking" bodies.
    """
    exit_code = _run_shape(
        shape_id, SyntheticShapeProbeRobustnessPlugin, adapter_factory
    )
    combined_output = "".join(capsys.readouterr())

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"FALSE ACCUSATION: {shape_id!r} genuinely implements its declared "
        f"capability yet the gate refused it (exit {exit_code}). A gate that "
        f"cries wolf gets switched off. output={combined_output!r}"
    )
    assert shape_id not in combined_output, (
        f"{shape_id!r} is honest and must not be NAMED as a gap: {combined_output!r}"
    )


@pytest.mark.negative_at
def test_gate_does_not_refuse_a_single_side_effecting_call_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A lone ``Expr(Call)`` body is production shape, not a stub.

    The SHIPPED ``PythonEnvironmentalE2EAdapter.run_against_installed``
    (``src/des/adapters/driven/e2e/python_environmental_e2e_adapter.py``) IS
    a single delegating call. Any "does it do work?" rule that excludes that
    shape fires on nWave's own production adapter -- a known-accepted
    residual, pinned here so an over-correction is caught.
    """
    plugin = SyntheticShapeProbeRobustnessPlugin(
        "honest-single-side-effecting-call",
        HonestSideEffectingCallRobustnessAdapter([]),
    )

    exit_code = run_port_realization_gate([plugin])
    combined_output = "".join(capsys.readouterr())

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"FALSE ACCUSATION: a single side-effecting call is the shape of "
        f"nWave's own shipped Python e2e adapter -- refusing it (exit "
        f"{exit_code}) would fire on production code. "
        f"output={combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 6. PRECISION -- a CONDITIONAL / nested raise, with real work around it, is
#    ordinary defensive code. Keeps the existing
#    `_ConditionalStubRobustnessAdapter` scenario's verdict unchanged.
# ---------------------------------------------------------------------------

_NESTED_RAISE_SHAPES = (
    ("honest-guard-clause-raise", HonestConditionalRaiseRobustnessAdapter),
    ("honest-try-except-reraise", HonestTryExceptRaiseRobustnessAdapter),
)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("shape_id", "adapter_factory"),
    _NESTED_RAISE_SHAPES,
    ids=[shape_id for shape_id, _ in _NESTED_RAISE_SHAPES],
)
def test_gate_does_not_refuse_a_conditional_or_nested_raise(
    shape_id: str,
    adapter_factory: object,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A raise inside ``if``/``try``, with real work around it, is not a stub.

    The inverted criterion must key on TOP-LEVEL inertness, not on the mere
    presence of a ``raise`` anywhere in the body -- otherwise every
    guard-clause and every error-wrapping ``try`` in every adapter becomes a
    false accusation.
    """
    exit_code = _run_shape(
        shape_id, SyntheticShapeProbeRobustnessPlugin, adapter_factory
    )
    combined_output = "".join(capsys.readouterr())

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"FALSE ACCUSATION: {shape_id!r} raises only conditionally and does "
        f"real work otherwise, yet the gate refused it (exit {exit_code}). "
        f"output={combined_output!r}"
    )
    assert shape_id not in combined_output, (
        f"{shape_id!r} is honest and must not be NAMED as a gap: {combined_output!r}"
    )


@pytest.mark.negative_at
def test_gate_does_not_refuse_an_honest_multi_method_facet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """All three ``EnvironmentalE2EPort`` methods implemented -> conformant.

    The multi-method counterpart of the precision guard: a facet that really
    overrides every method its Protocol declares must stay clean, so the
    EVASION-C fix (inherited-but-unoverridden) cannot be implemented as
    "anything inheriting a Protocol is a stub".
    """
    plugin = SyntheticShapeProbeEnvironmentalE2EPlugin(
        "honest-full-e2e-facet", HonestRealEnvironmentalE2EAdapter()
    )

    exit_code = run_port_realization_gate([plugin])
    combined_output = "".join(capsys.readouterr())

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"FALSE ACCUSATION: every declared method is genuinely implemented, "
        f"yet the gate refused (exit {exit_code}). output={combined_output!r}"
    )
    assert "honest-full-e2e-facet" not in combined_output, (
        f"an honest facet must not be NAMED as a gap: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# 7. PRECISION -- a plugin that claims NOTHING is never refused. Declaring
#    `False` is an honest statement of non-support, not a gap.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_gate_does_not_refuse_a_plugin_that_claims_no_coverage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``port_coverage[<port>] = False`` behind a stub facet is honest.

    The gate judges unbacked CLAIMS. A plugin that never claimed the
    capability has told the truth -- refusing it would punish honesty and
    push authors toward declaring `True` to keep the gate quiet.
    """
    plugin = SyntheticShapeProbeRobustnessPlugin(
        "honest-declares-no-coverage",
        StubFixtureRobustnessDensityAdapter(),
        declared=False,
    )

    exit_code = run_port_realization_gate([plugin])
    combined_output = "".join(capsys.readouterr())

    assert exit_code == PORT_REALIZATION_GATE_CONFORMANT, (
        f"FALSE ACCUSATION: the plugin declares the capability False -- an "
        f"honest 'I do not support this' -- yet the gate refused (exit "
        f"{exit_code}). output={combined_output!r}"
    )
    assert "honest-declares-no-coverage" not in combined_output, (
        f"a plugin claiming nothing must not be NAMED as a gap: {combined_output!r}"
    )
