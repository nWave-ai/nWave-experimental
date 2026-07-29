"""Regression: shipped prose claims an event/ledger record the code never
produces -- the "declared-vs-emitted" defect class (docs/mikado/codex-parity-
and-performance-delivery.mikado.md). Confirmed instances found by manual audit
before `des verify-declared-events` existed: `FeatureEnd` (CLAUDE.md's own
DONE-definition), `FeatureEndCycleComplete`/`FeatureEndCycleRefused`
(assumed ledger events, actually `feature_end.py`'s CLI-stdout-only `_emit()`
payload), `FeatureEndCheckpoint` (four shipped skill/task files described it
as a firing resume-signal; zero producers anywhere in `src/des`), and
`DocumentationDensityEvent` (eleven citation sites across seven skill files;
`DocumentationDensityEvent(` has zero constructor call sites).

Two test tiers:

1. Fixture-level unit tests pin the regex behavior of the two extraction
   halves (`extract_producer_names`, `extract_claims`) and the two-tier
   (strict/broad) classification against small, hand-built strings --
   RED-for-right-reason verified by mutating `src/des/cli/verify_declared_events.py`
   and observing each assertion fail on the mutated behavior, not on
   import/collection.
2. An acceptance-level test runs the REAL gate over THIS repo's live prose +
   source corpus (`compute_declared_events(repo_root)`) and asserts it is
   `.clean` -- the actual CI enforcement surface. This is the test that
   catches a FUTURE reintroduction of a phantom claim anywhere in
   nWave/skills, nWave/agents, nWave/tasks/nw, CLAUDE.md, or
   docs/product/architecture, not just the four instances fixed alongside
   this gate.

DRIVING SURFACE (Mandate 16, no direct domain testing): both extraction
functions and the orchestrating `compute_declared_events` are the same pure
functions / driving surface `des verify-declared-events`'s `main()` calls --
this test exercises them directly rather than shelling out, matching the
sibling `skill_normative_gate` test's convention.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.verify_declared_events import (
    DeclaredEventsInputUnavailableError,
    compute_declared_events,
    compute_producer_registry,
    extract_claims,
    extract_producer_names,
)


def _repo_root() -> Path:
    """This test file sits at tests/bugs/des/ -- the same depth-to-root as
    src/des/cli/, so parents[2] is the checkout root."""
    return Path(__file__).resolve().parents[3]


# --- extract_producer_names -------------------------------------------------


def test_extract_producer_names_finds_a_module_constant_assignment() -> None:
    source = '_RED_OBSERVED_EVENT = "RedObserved"\n'
    names = extract_producer_names(source)
    assert "RedObserved" in names.strict
    assert "RedObserved" in names.broad


def test_extract_producer_names_finds_an_append_call_literal() -> None:
    source = (
        "        AtCompletionLedger(feature_id, repo).append_gate_event(\n"
        '            "SliceAttestedFromBundle", slice_id\n'
        "        )\n"
    )
    names = extract_producer_names(source)
    assert "SliceAttestedFromBundle" in names.strict


def test_extract_producer_names_finds_an_event_kwarg() -> None:
    source = 'ledger.append_gate_event(event="CarpaccioGateCleared", slice_id=x)\n'
    names = extract_producer_names(source)
    assert "CarpaccioGateCleared" in names.strict


def test_extract_producer_names_resolves_the_wave_review_spec_template() -> None:
    source = 'WaveReviewSpec(\n    wave="discuss",\n    reviewer_role="PO-review",\n)\n'
    names = extract_producer_names(source)
    assert "DiscussReviewVerdict" in names.strict


def test_extract_producer_names_dict_literal_is_broad_tier_only() -> None:
    """The exact FeatureEndCycleComplete/Refused shape: a dict-literal
    `_emit()` payload is a REAL code-emitted string (broad tier) but NOT
    durable ledger evidence (strict tier) -- this asymmetry is the fix for
    the confirmed defect: a blanket dict-literal scan would have made
    FeatureEndCycleRefused pass a "claims a ledger record" check it should
    fail."""
    source = '_emit({"event": "FeatureEndCycleRefused", "verb": verb})\n'
    names = extract_producer_names(source)
    assert "FeatureEndCycleRefused" in names.broad
    assert "FeatureEndCycleRefused" not in names.strict


def test_extract_producer_names_finds_nothing_for_unrelated_source() -> None:
    names = extract_producer_names("def foo():\n    return 1\n")
    assert names.strict == frozenset()
    assert names.broad == frozenset()


# --- extract_claims ----------------------------------------------------------


def test_extract_claims_requires_a_trigger_word_near_the_name() -> None:
    # No trigger word anywhere near the backtick name -- not a claim.
    claims = extract_claims("See `SliceCommitVerified` for details.", "f.md")
    assert claims == ()


def test_extract_claims_finds_a_name_near_a_trigger_word() -> None:
    claims = extract_claims(
        "the DES sequencer appends a `FeatureEndCheckpoint` record to the ledger",
        "f.md",
    )
    assert len(claims) == 1
    assert claims[0].name == "FeatureEndCheckpoint"


def test_extract_claims_ignores_a_backtick_name_with_no_known_suffix() -> None:
    """`FeatureEnd` (the confirmed CLAUDE.md defect) carries no suffix from
    this codebase's event vocabulary -- a documented gap (module docstring),
    not a bug: broadening the suffix list to catch it would also catch
    ordinary prose nouns. Pinned here so a future "fix" doesn't silently
    change this trade-off without a conscious decision."""
    claims = extract_claims("a `FeatureEnd` ledger record attests it", "f.md")
    assert claims == ()


# --- compute_declared_events (end-to-end over a fixture tree) --------------


def _write_fixture_repo(root: Path, *, skill_body: str, producer_body: str) -> None:
    (root / "src" / "des" / "cli").mkdir(parents=True)
    (root / "src" / "des" / "cli" / "some_gate.py").write_text(
        producer_body, encoding="utf-8"
    )
    (root / "nWave" / "skills" / "nw-fixture").mkdir(parents=True)
    (root / "nWave" / "skills" / "nw-fixture" / "SKILL.md").write_text(
        skill_body, encoding="utf-8"
    )


def test_compute_declared_events_fails_on_a_phantom_claim(tmp_path: Path) -> None:
    _write_fixture_repo(
        tmp_path,
        skill_body="the gate writes a `TotallyMadeUpVerdict` record.\n",
        producer_body='_OTHER_EVENT = "SomethingElse"\n',
    )
    result = compute_declared_events(tmp_path)
    assert not result.clean
    assert [c.name for c in result.undeclared] == ["TotallyMadeUpVerdict"]


def test_compute_declared_events_passes_when_the_claim_has_a_producer(
    tmp_path: Path,
) -> None:
    _write_fixture_repo(
        tmp_path,
        skill_body="the gate writes a `RealVerdict` record.\n",
        producer_body='_REAL_EVENT = "RealVerdict"\n',
    )
    result = compute_declared_events(tmp_path)
    assert result.clean
    assert [c.name for c in result.claims] == ["RealVerdict"]


def test_compute_declared_events_self_exempts_an_explicit_not_yet_built_caveat(
    tmp_path: Path,
) -> None:
    _write_fixture_repo(
        tmp_path,
        skill_body="the gate would write a `FutureVerdict` record (not yet built).\n",
        producer_body='_OTHER_EVENT = "SomethingElse"\n',
    )
    result = compute_declared_events(tmp_path)
    assert result.clean
    assert [c.name for c in result.exempted] == ["FutureVerdict"]


def test_compute_declared_events_honors_a_registered_exemption(tmp_path: Path) -> None:
    _write_fixture_repo(
        tmp_path,
        skill_body="the gate writes a `PedagogicalVerdict` record.\n",
        producer_body='_OTHER_EVENT = "SomethingElse"\n',
    )
    (tmp_path / "nWave" / "data").mkdir(parents=True)
    (tmp_path / "nWave" / "data" / "declared-event-exemptions.json").write_text(
        (
            '{"schema_version": 1, "exemptions": [{"file": '
            '"nWave/skills/nw-fixture/SKILL.md", "name": "PedagogicalVerdict", '
            '"reason": "unit-test fixture"}]}'
        ),
        encoding="utf-8",
    )
    result = compute_declared_events(tmp_path)
    assert result.clean
    assert [c.name for c in result.exempted] == ["PedagogicalVerdict"]


def test_compute_declared_events_requires_ledger_tier_for_a_durability_claim(
    tmp_path: Path,
) -> None:
    """A claim that says "ledger" is claiming DURABILITY -- a name a reader
    expects to read BACK later. A name that is only ever printed to CLI
    stdout (broad tier, not strict) must still FAIL this stronger claim --
    the exact FeatureEndCycleComplete/Refused confirmed defect shape."""
    _write_fixture_repo(
        tmp_path,
        skill_body="the DES sequencer appends `StdoutOnlyVerdict` to the ledger.\n",
        producer_body='_emit({"event": "StdoutOnlyVerdict", "verb": "run"})\n',
    )
    result = compute_declared_events(tmp_path)
    assert not result.clean
    assert [c.name for c in result.undeclared] == ["StdoutOnlyVerdict"]


def test_compute_producer_registry_raises_when_no_python_source_exists(
    tmp_path: Path,
) -> None:
    with pytest.raises(DeclaredEventsInputUnavailableError):
        compute_producer_registry(tmp_path)


def test_compute_declared_events_raises_when_no_prose_corpus_exists(
    tmp_path: Path,
) -> None:
    (tmp_path / "src" / "des" / "cli").mkdir(parents=True)
    (tmp_path / "src" / "des" / "cli" / "x.py").write_text(
        '_X = "Y"\n', encoding="utf-8"
    )
    with pytest.raises(DeclaredEventsInputUnavailableError):
        compute_declared_events(tmp_path)


# --- acceptance: the real gate over THIS repo's live corpus -----------------


@pytest.mark.negative_at
def test_the_real_shipped_corpus_has_no_undeclared_event_claims() -> None:
    """The actual CI enforcement surface: run the real gate over nWave-dev's
    OWN prose + source tree. Catches any FUTURE reintroduction of a phantom
    event/ledger-record claim anywhere in nWave/skills, nWave/agents,
    nWave/tasks/nw, CLAUDE.md, or docs/product/architecture -- not just the
    instances fixed alongside this gate (FeatureEnd, FeatureEndCycleComplete/
    Refused/Indeterminate, FeatureEndCheckpoint, DocumentationDensityEvent)."""
    result = compute_declared_events(_repo_root())
    assert result.clean, (
        f"{len(result.undeclared)} claimed event/record name(s) with no "
        "matching producer and no exemption: "
        + "; ".join(f"`{c.name}` at {c.file}:{c.line}" for c in result.undeclared)
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
