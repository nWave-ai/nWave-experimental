"""GREEN characterization -- ADR-LA-001 D9 resolution algebra.

Proves the internal unification is real, not decorative: every normal
bundled OSS provider implements the identical ``manifest()``/``resolve()``
protocol (LA1-L2 -- exercised through a foreign, non-adapter class to
demonstrate the fold dispatches structurally, never on concrete provider
type), the fold's strict-identity law holds (LA1-L5), composition-time
coverage is verified (LA1-L8), an unexpected provider fault degrades to one
bounded trace entry instead of crashing (LA1-L3), and ``CodeFactChain`` is a
stateless, concurrency-safe ``Ast -> TextSearch`` fold whose per-query
``Resolution.trace`` is the only diagnostic projection (D6-R1/R5: the paid
``TsunamiAdapter`` stub, its ``tsunami_present`` ctor flag, its
``tsunami-absent`` skip event, and the mutable ``health_events()`` side
channel are DELETED -- unrepresentable in OSS, LA1-L7).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.codefact.text_search_code_fact_adapter import TextSearchAdapter
from des.ports.code_fact_port import (
    CAPABILITY_CALLERS_OF,
    CAPABILITY_NEVER_WIRED,
    CAPABILITY_SIMILAR_RESPONSIBILITY,
    TRACE_DETAIL_MAX_CHARS,
    TRACE_EXEMPLARS_MAX,
    Answered,
    CapabilityDescriptor,
    Failed,
    ManifestEntry,
    TraceEntry,
    resolve_through_fold,
    verify_composition_coverage,
)


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        stability="stable",
        contract_version="1.0.0",
        io_schema="code-fact.v1",
        providing_adapter="negotiated",
    )


def test_every_bundled_provider_implements_the_identical_manifest_resolve_shape(
    tmp_path: Path,
) -> None:
    """LA1-L2: every normal bundled OSS provider (floor, structural) satisfies
    one uniform protocol -- driven through a single generic loop, never a
    per-provider branch. The witnessless ``present=True`` Tsunami stub is
    excluded on purpose (see module docstring)."""
    (tmp_path / "subject.py").write_text(
        "def target():\n    return 1\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    descriptor = _descriptor(CAPABILITY_CALLERS_OF)
    request = {"symbol": "target"}

    for provider in (
        AstAdapter(root=tmp_path),
        TextSearchAdapter(root=tmp_path),
    ):
        manifest = provider.manifest()
        assert all(isinstance(entry, ManifestEntry) for entry in manifest)
        assert any(entry.capability_id == CAPABILITY_CALLERS_OF for entry in manifest)
        outcome = provider.resolve(descriptor, request)
        assert isinstance(outcome, Answered)
        assert outcome.provider_id == provider.provider_id


def test_fold_dispatches_structurally_never_on_concrete_provider_type(
    tmp_path: Path,
) -> None:
    """A provider outside every known adapter class participates in the
    fold identically -- proving zero ``isinstance``/``getattr``/arity
    branching on provider identity (LA1-L2)."""

    class ForeignProvider:
        provider_id = "foreign"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

        def resolve(self, descriptor, request):
            return Answered(
                provider_id="foreign",
                confidence="approx",
                payload={"symbol": request["symbol"]},
                trace=(
                    TraceEntry(
                        provider_id="foreign",
                        event="answered",
                        scope="complete",
                        fault_count=0,
                        exemplars=(),
                        detail="",
                    ),
                ),
            )

    resolution = resolve_through_fold(
        _descriptor(CAPABILITY_NEVER_WIRED),
        {"symbol": "anything"},
        (ForeignProvider(), AstAdapter(root=tmp_path)),
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "foreign"
    assert resolution.payload == {"symbol": "anything"}


def test_fold_strict_identity_a_non_covering_provider_is_noise_free(
    tmp_path: Path,
) -> None:
    """LA1-L5: inserting a non-covering provider anywhere leaves the
    Resolution -- trace included -- observationally unchanged."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class NonCovering:
        provider_id = "noncovering"

        def manifest(self):
            return ()

        def resolve(self, descriptor, request):  # pragma: no cover
            raise AssertionError("a non-covering provider must never be resolved")

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}
    providers = (AstAdapter(root=tmp_path), TextSearchAdapter(root=tmp_path))

    without_noise = resolve_through_fold(descriptor, request, providers)
    with_noise = resolve_through_fold(descriptor, request, (NonCovering(), *providers))

    assert with_noise == without_noise


def test_chain_resolve_proves_ast_textsearch_composition_via_trace(
    tmp_path: Path,
) -> None:
    """ADR-LA-001 D9 slice (b): the provider-neutral ``Resolution`` trace is
    the surface that proves the AST/TextSearch composition -- no
    ``tsunami_present`` constructor argument and no read of the retired
    mutable ``health_events()`` side channel (D6-R1, D6-R5). The composed
    chain's structural tier answers first and the fold records exactly one
    clean ``answered`` entry naming it."""
    (tmp_path / "subject.py").write_text(
        "def target():\n    return 1\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    chain = CodeFactChain(root=tmp_path)

    resolution = chain.resolve(_descriptor(CAPABILITY_CALLERS_OF), {"symbol": "target"})

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    assert resolution.confidence == "approx"
    assert resolution.payload.payload["sites"]
    answering_entries = [
        entry for entry in resolution.trace if entry.event == "answered"
    ]
    assert len(answering_entries) == 1
    assert answering_entries[0].provider_id == "ast"
    assert answering_entries[0].fault_count == 0


def test_similar_responsibility_could_not_look_is_failed_never_answered_absent(
    tmp_path: Path,
) -> None:
    """ADR-LA-001 D9 slice (c), D6-R3: the additive `query.similar-responsibility`
    capability's "could not look" case (every candidate file unparseable, zero
    module-level symbols found anywhere in scope) is a `Failed(cause=
    "unparseable-source")` -- never an `Answered` carrying the retired envelope
    `reason_code="absent"`. A real consumer as fixture (D10): `AstAdapter.resolve`
    directly, never a monkeypatch."""
    (tmp_path / "broken_one.py").write_text("def not_valid_python(:\n    pass\n")
    (tmp_path / "broken_two.py").write_text("def missing_paren(\n    pass\n")
    adapter = AstAdapter(root=tmp_path)
    descriptor = _descriptor(CAPABILITY_SIMILAR_RESPONSIBILITY)

    resolution = adapter.resolve(descriptor, {"name": "anything"})

    assert isinstance(resolution, Failed), (
        f"a scope where nothing is parseable must be a real Failed, never a "
        f"fabricated Answered -- got {resolution!r}"
    )
    assert resolution.cause == "unparseable-source"
    assert len(resolution.trace) == 1
    assert resolution.trace[0].provider_id == "ast"
    assert resolution.trace[0].event == "failed:unparseable-source"
    assert resolution.trace[0].fault_count == 2, (
        "both genuinely-unparseable files must be counted -- the same "
        "coverage-gap signal `des find-similar-responsibility` renders as "
        "`unparsed_count` (F-fix-find-similar-declares-unparseable-coverage)"
    )


def test_composition_missing_stable_core_coverage_refuses_composition() -> None:
    """LA1-L8: a provider tuple whose union(manifest) does not cover
    ``STABLE_CORE_CAPABILITY_IDS`` is refused at composition time -- one
    concise WHAT/WHY/HOW ``ValueError``, no new carrier/gate."""

    class OnlyNeverWired:
        provider_id = "partial"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

        def resolve(self, descriptor, request):  # pragma: no cover
            raise AssertionError("never called by this test")

    with pytest.raises(ValueError, match="WHAT.*WHY.*HOW"):
        verify_composition_coverage((OnlyNeverWired(),))


def test_fold_provider_exception_falls_through_with_one_preserved_failure_trace(
    tmp_path: Path,
) -> None:
    """LA1-L3 totality: an unexpected provider ``Exception`` never crashes
    the fold -- it degrades to exactly one bounded ``failed:provider-error``
    trace entry and the fold continues. A malformed ``Failed`` (empty trace)
    is likewise normalized to one ``provider-error`` entry, never lost, never
    duplicated (LA1-L9: exactly one ``TraceEntry`` per covering provider)."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class Exploding:
        provider_id = "exploding"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="binding-resolved"
                ),
            )

        def resolve(self, descriptor, request):
            raise RuntimeError("transport blew up")

    class MalformedFailure:
        provider_id = "malformed"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

        def resolve(self, descriptor, request):
            return Failed(cause="unparseable-source", trace=())

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor,
        request,
        (Exploding(), MalformedFailure(), AstAdapter(root=tmp_path)),
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    for provider_id in ("exploding", "malformed"):
        entries = [
            entry for entry in resolution.trace if entry.provider_id == provider_id
        ]
        assert len(entries) == 1
        assert entries[0].event == "failed:provider-error"


def test_trace_entry_bound_construction_rejects_overflow() -> None:
    """``TraceEntry`` bounds are real by construction -- exemplars <=
    ``TRACE_EXEMPLARS_MAX``, detail <= ``TRACE_DETAIL_MAX_CHARS``,
    ``fault_count`` nonnegative, ``provider_id`` non-empty. An out-of-bound
    entry can never exist."""
    base = {
        "provider_id": "ast",
        "event": "failed:provider-error",
        "scope": "complete",
        "fault_count": 0,
        "exemplars": (),
        "detail": "",
    }

    with pytest.raises(ValueError):
        overflow_exemplars = tuple(map(str, range(TRACE_EXEMPLARS_MAX + 1)))
        TraceEntry(**{**base, "exemplars": overflow_exemplars})
    with pytest.raises(ValueError):
        TraceEntry(**{**base, "detail": "x" * (TRACE_DETAIL_MAX_CHARS + 1)})
    with pytest.raises(ValueError):
        TraceEntry(**{**base, "fault_count": -1})
    with pytest.raises(ValueError):
        TraceEntry(**{**base, "provider_id": ""})


def test_malformed_answered_cannot_become_success_and_fallback_answers(
    tmp_path: Path,
) -> None:
    """LA1-L1/L3/L9: a provider returning ``Answered`` with a malformed trace
    (here, ``trace=()``) is not one atomic well-formed observation -- it must
    never be branched on as a success. It is normalized to exactly one
    ``failed:provider-error`` entry and the fold falls through to the next
    covering provider, whose real answer is preserved."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class MalformedAnswered:
        provider_id = "malformed-answered"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="binding-resolved"
                ),
            )

        def resolve(self, descriptor, request):
            return Answered(
                provider_id="malformed-answered",
                confidence="binding-resolved",
                payload={"never": "trusted"},
                trace=(),
            )

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (MalformedAnswered(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    entries = [
        entry for entry in resolution.trace if entry.provider_id == "malformed-answered"
    ]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


def test_manifest_noisy_answered_binding_resolved_cannot_inflate_and_fallback_answers(
    tmp_path: Path,
) -> None:
    """LA1-L6 (no inflation): a provider manifest-declaring ``noisy`` that
    returns an ``Answered`` claiming ``binding-resolved`` is not a real
    observation of that provider's own manifest -- it is normalized to a
    failure and the fold falls through, never inflating confidence."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class InflatingProvider:
        provider_id = "inflating"

        def manifest(self):
            return (
                ManifestEntry(capability_id=CAPABILITY_NEVER_WIRED, confidence="noisy"),
            )

        def resolve(self, descriptor, request):
            return Answered(
                provider_id="inflating",
                confidence="binding-resolved",
                payload={"never": "trusted"},
                trace=(
                    TraceEntry(
                        provider_id="inflating",
                        event="answered",
                        scope="complete",
                        fault_count=0,
                        exemplars=(),
                        detail="",
                    ),
                ),
            )

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (InflatingProvider(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    assert resolution.confidence == "approx"
    entries = [entry for entry in resolution.trace if entry.provider_id == "inflating"]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


def test_mismatched_failed_cause_event_normalizes(tmp_path: Path) -> None:
    """LA1-L1/L9/L10: a ``Failed`` whose single trace entry's event does not
    match its own ``cause`` is not a well-formed observation -- it is
    normalized to one ``failed:provider-error`` entry and the fold
    continues to the next covering provider."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class MismatchedFailed:
        provider_id = "mismatched"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

        def resolve(self, descriptor, request):
            return Failed(
                cause="unparseable-source",
                trace=(
                    TraceEntry(
                        provider_id="mismatched",
                        event="failed:out-of-scope-language",
                        scope="complete",
                        fault_count=1,
                        exemplars=(),
                        detail="",
                    ),
                ),
            )

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (MismatchedFailed(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    entries = [entry for entry in resolution.trace if entry.provider_id == "mismatched"]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


@pytest.mark.parametrize(
    ("kwargs_override", "expected_match"),
    [
        ({"event": "skipped"}, "TraceEntry.event"),
        ({"scope": "partial"}, "TraceEntry.scope"),
        ({"event": "failed:not-a-real-cause"}, "TraceEntry.event"),
    ],
)
def test_trace_entry_rejects_values_outside_closed_vocabularies(
    kwargs_override: dict[str, object], expected_match: str
) -> None:
    """The closed ``TraceEntry`` ``event``/``scope`` vocabularies (ADR-LA-001
    D5) are enforced by construction -- an out-of-vocabulary value can never
    exist."""
    base = {
        "provider_id": "ast",
        "event": "answered",
        "scope": "complete",
        "fault_count": 0,
        "exemplars": (),
        "detail": "",
    }
    with pytest.raises(ValueError, match=expected_match):
        TraceEntry(**{**base, **kwargs_override})


def test_manifest_entry_rejects_blank_capability_id_or_invalid_confidence() -> None:
    """``ManifestEntry`` construction rejects a blank ``capability_id`` and a
    ``confidence`` outside the existing ``Confidence`` vocabulary."""
    with pytest.raises(ValueError, match="capability_id"):
        ManifestEntry(capability_id="", confidence="noisy")
    with pytest.raises(ValueError, match="confidence"):
        ManifestEntry(capability_id=CAPABILITY_NEVER_WIRED, confidence="super-sure")


def test_composition_rejects_blank_provider_id() -> None:
    """Composition-time coverage verification refuses a blank ``provider_id``
    -- one concise WHAT/WHY/HOW ``ValueError``, no new carrier/gate."""

    class Blank:
        provider_id = ""

        def manifest(self):
            return ()

    with pytest.raises(ValueError, match="WHAT.*WHY.*HOW"):
        verify_composition_coverage((Blank(),))


def test_manifest_exception_falls_through_at_the_fold_and_at_composition(
    tmp_path: Path,
) -> None:
    """A ``manifest()`` call that raises must not escape either the fold
    (LA1-L3 totality -- normalized to one ``failed:provider-error`` entry,
    fold continues) or composition-time coverage verification (LA1-L8 --
    normalized to one WHAT/WHY/HOW ``ValueError``)."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class ExplodingManifest:
        provider_id = "exploding-manifest"

        def manifest(self):
            raise RuntimeError("registry unreachable")

        def resolve(self, descriptor, request):  # pragma: no cover
            raise AssertionError("never called: manifest() raised first")

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (ExplodingManifest(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    entries = [
        entry for entry in resolution.trace if entry.provider_id == "exploding-manifest"
    ]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"

    with pytest.raises(ValueError, match="WHAT.*WHY.*HOW"):
        verify_composition_coverage((ExplodingManifest(),))


@pytest.mark.parametrize("alien_outcome", [None, "boom", {"not": "a-resolution"}, 42])
def test_fold_alien_resolve_return_normalizes_and_falls_back(
    tmp_path: Path, alien_outcome: object
) -> None:
    """LA1-L1/L3/L9 totality: a ``resolve()`` that returns neither
    ``Answered`` nor a well-formed ``Failed`` (an alien value) is never
    branched on as either -- it normalizes to exactly one
    ``failed:provider-error`` trace entry and the fold falls through to the
    next covering provider, whose real answer is preserved."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class AlienReturn:
        provider_id = "alien"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="binding-resolved"
                ),
            )

        def resolve(self, descriptor, request):
            return alien_outcome

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (AlienReturn(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    entries = [entry for entry in resolution.trace if entry.provider_id == "alien"]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


def test_fold_all_providers_alien_resolve_return_yields_deterministic_failed(
    tmp_path: Path,
) -> None:
    """When every covering provider returns an alien value, the fold does
    not crash and does not silently drop the query -- it yields a
    deterministic ``Failed(cause="provider-error")`` (LA1-L10), not an
    ``Unsupported`` (the capability WAS covered, every attempt just
    normalized to a fallback failure)."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class AlienA:
        provider_id = "alien-a"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="binding-resolved"
                ),
            )

        def resolve(self, descriptor, request):
            return object()

    class AlienB:
        provider_id = "alien-b"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

        def resolve(self, descriptor, request):
            return []

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(descriptor, request, (AlienA(), AlienB()))

    assert isinstance(resolution, Failed)
    assert resolution.cause == "provider-error"
    assert [entry.provider_id for entry in resolution.trace] == ["alien-a", "alien-b"]
    assert all(entry.event == "failed:provider-error" for entry in resolution.trace)


def test_fold_malformed_manifest_entry_normalizes_and_falls_back_before_resolve(
    tmp_path: Path,
) -> None:
    """A manifest member that is not a real ``ManifestEntry`` (here: a
    duck-typed object missing ``confidence`` entirely) is never trusted as a
    coverage claim -- it normalizes to one ``failed:provider-error`` trace
    entry and the fold falls through WITHOUT ever calling ``resolve()`` on
    that provider, to the next covering provider whose real answer is
    preserved."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class _FakeManifestEntry:
        def __init__(self, capability_id: str) -> None:
            self.capability_id = capability_id
            # deliberately no `confidence` attribute at all

    class MalformedManifest:
        provider_id = "malformed-manifest"

        def manifest(self):
            return (_FakeManifestEntry(capability_id=CAPABILITY_NEVER_WIRED),)

        def resolve(self, descriptor, request):  # pragma: no cover
            raise AssertionError(
                "never called: a malformed manifest entry must short-circuit "
                "before resolve()"
            )

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (MalformedManifest(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    entries = [
        entry for entry in resolution.trace if entry.provider_id == "malformed-manifest"
    ]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


def test_fold_duck_typed_manifest_entry_with_confidence_still_normalizes(
    tmp_path: Path,
) -> None:
    """Even a duck-typed object carrying BOTH ``capability_id`` and
    ``confidence`` is not trusted unless it is a real ``ManifestEntry`` --
    the fold's totality boundary is identity, not attribute presence."""
    (tmp_path / "subject.py").write_text(
        "def existing():\n    return 1\n", encoding="utf-8"
    )

    class _DuckManifestEntry:
        capability_id = CAPABILITY_NEVER_WIRED
        confidence = "binding-resolved"

    class DuckManifest:
        provider_id = "duck-manifest"

        def manifest(self):
            return (_DuckManifestEntry(),)

        def resolve(self, descriptor, request):  # pragma: no cover
            raise AssertionError(
                "never called: a malformed manifest entry must short-circuit "
                "before resolve()"
            )

    descriptor = _descriptor(CAPABILITY_NEVER_WIRED)
    request = {"symbol": "existing"}

    resolution = resolve_through_fold(
        descriptor, request, (DuckManifest(), AstAdapter(root=tmp_path))
    )

    assert isinstance(resolution, Answered)
    assert resolution.provider_id == "ast"
    entries = [
        entry for entry in resolution.trace if entry.provider_id == "duck-manifest"
    ]
    assert len(entries) == 1
    assert entries[0].event == "failed:provider-error"


def test_composition_rejects_duplicate_provider_id() -> None:
    """Composition-time coverage verification refuses two composed providers
    sharing the same non-empty ``provider_id`` -- LA1-L9's per-provider
    trace aggregation requires uniqueness, not merely non-blankness -- one
    concise WHAT/WHY/HOW ``ValueError``, no new carrier/gate."""

    class DuplicateA:
        provider_id = "dup"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_NEVER_WIRED, confidence="approx"
                ),
            )

    class DuplicateB:
        provider_id = "dup"

        def manifest(self):
            return (
                ManifestEntry(
                    capability_id=CAPABILITY_CALLERS_OF, confidence="binding-resolved"
                ),
            )

    with pytest.raises(ValueError, match="WHAT.*WHY.*HOW"):
        verify_composition_coverage((DuplicateA(), DuplicateB()))
