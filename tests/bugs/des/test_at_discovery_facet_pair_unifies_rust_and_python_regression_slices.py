"""Regression (RCA this session, sister-reported gap, feature-delta
``fix-rust-regression-at-kind-wiring``): no SSOT/port abstraction for
"AT-discovery evidence kind" — 4 of 5 spine tools
(``carpaccio_slice_gate.py``, ``commit_slice.py``,
``verify_slice_commit_completeness.py``, ``run_contract_gate.py``) hand-roll
their own closed ``--at-kind {gherkin,pytest-regression}`` enum + Python
``ast``-based counting, while ``at_review_verdict.py`` already carries a 5th
ad-hoc ``rust-regression`` value with its OWN local regex ``#[test]`` scanner
that nothing else reuses. Separately, ``commit_slice.py``'s digest leg
assumes ``at_kind == "pytest-regression"`` means "this slice is Python" and
skips the runner-port routing the E2 execution leg
(``verify_slice_commit_completeness._routes_through_runner_port``, keyed on
the file's actual ``.suffix != ".py"``) already gets right — a
Rust-labeled-as-pytest-regression slice earns a vacuous Python digest while
E2 correctly runs cargo (Branch C, a live contradiction).

THE FIX (crafter's job, NOT implemented by this AT — test-authoring only,
zero ``src/`` edits): a 4th ``LanguageAdapterRegistry`` facet-slot-pair,
``register_at_discovery``/``lookup_at_discovery`` (mirrors the EXISTING
``register_contract_gate``/``register_environmental_e2e``/
``register_robustness_density`` pairs, ``runner_registry.py``), plus
``RunnerAdapter.discover_ats(target_root, regression_test_file)`` (mirrors
``.run()``/``.list_scope()``'s self-heal-seed-then-``RunnerAdapterUnavailable``
dispatch, ``test_runner_port.py``). A ``pytest`` at-discovery facet relocates
+ widens ``carpaccio_format.count_pytest_regression_ats`` (module-level ONLY
today) to also walk class-nested ``Test*.test_*`` methods
(``F-AT-DETECTION-IS-LANGUAGE-BOUND``). A ``cargo-test`` at-discovery facet
relocates the ALREADY-WRITTEN ``_count_rust_regression_ats`` /
``_rust_regression_content_hash`` from ``at_review_verdict.py:210-274``
verbatim (including its already-fixed comment-blindness +
``UnicodeDecodeError`` hardening). ``--at-kind`` gains an ADDITIVE
``native-regression`` choice (ADD-not-mutate) across the 5 call sites,
resolving language automatically via the SAME lockfile/file-suffix mechanism
``resolve()``/``_routes_through_runner_port`` already use — never
operator-declared. ``commit_slice._committed_scope_digest_or_degrade_reason``
gains a ``regression_test_file`` parameter so its routing decision AGREES
with the E2 execution leg's, closing Branch C.

Driving surface (Mandate 13 driving-port-only, Layer 3 in-process default):
every scenario drives a REAL, STABLE, EXISTING production entry in-process —
``LanguageAdapterRegistry`` / ``RunnerAdapter`` / ``seed_runner_registry``
(``des.ports.test_runner_port`` / ``des.adapters.driven.runner.runner_registry``,
both modules ALREADY EXIST — only the new facet-pair/method is absent, so
importing them at module top is P1-safe) or the REAL
``des.cli.carpaccio_slice_gate.main`` / ``des.cli.commit_slice`` CLI edges,
via ``tests.common.in_process_cli.run_cli_in_process`` where the driving
surface is a CLI. No subprocess fork — this bugfix ships no new user-facing
entry point, only a port abstraction + wiring fix (no ``@walking_skeleton``).

RED-for-right-reason (per ``nw-distill-red-scaffolding`` P1-P4): every
not-yet-existing attribute/method is guarded by an explicit
``assert hasattr(...)`` BEFORE use, so today's failure is a genuine, message-
carrying ``AssertionError`` (MISSING_FUNCTIONALITY), never a bare
``AttributeError``/``ImportError`` (which would misclassify as BROKEN).
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from des.adapters.driven.runner.runner_registry import (
    GLOBAL_REGISTRY,
    LanguageAdapterRegistry,
    seed_runner_registry,
)
from des.cli import commit_slice
from des.cli.carpaccio_slice_gate import main as carpaccio_slice_gate_main
from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable
from tests.common.in_process_cli import run_cli_in_process


_AT_DISCOVERY_HASATTR_MSG = (
    "must expose the AT-discovery facet slot-pair (register_at_discovery / "
    "lookup_at_discovery on LanguageAdapterRegistry, discover_ats on "
    "RunnerAdapter) -- mirrors the EXISTING register_contract_gate / "
    "register_environmental_e2e / register_robustness_density slot-pairs "
    "(src/des/adapters/driven/runner/runner_registry.py) and the EXISTING "
    ".run()/.list_scope() dispatch shape (src/des/ports/test_runner_port.py) "
    "-- not yet implemented (feature-delta fix-rust-regression-at-kind-wiring)."
)


# ===========================================================================
# 1. The registry facet-pair contract (mirrors the 3 EXISTING catalog slots).
# ===========================================================================


def test_language_adapter_registry_exposes_at_discovery_facet_slot_pair() -> None:
    """A fresh ``LanguageAdapterRegistry`` must expose
    ``register_at_discovery(name, facet)`` / ``lookup_at_discovery(name)`` —
    idempotent-overwrite registration + exact-callable resolution, mirroring
    ``register_contract_gate``/``lookup_contract_gate``'s contract byte for
    byte. An unregistered name resolves to ``None`` (never raises).
    """
    registry = LanguageAdapterRegistry()
    assert hasattr(registry, "register_at_discovery") and hasattr(
        registry, "lookup_at_discovery"
    ), f"LanguageAdapterRegistry {_AT_DISCOVERY_HASATTR_MSG}"

    assert registry.lookup_at_discovery("no-such-lang") is None, (
        "an unregistered name must resolve to None (mirrors lookup/"
        "lookup_contract_gate's absent-key contract) -- never raise"
    )

    def _fake_facet(adapter: object, target_root: object, regression_test_file: object):
        return "fake-facet-sentinel"

    registry.register_at_discovery("fake-lang", _fake_facet)
    assert registry.lookup_at_discovery("fake-lang") is _fake_facet, (
        "register_at_discovery must be idempotent-overwrite and "
        "lookup_at_discovery must resolve the EXACT registered callable -- "
        f"got {registry.lookup_at_discovery('fake-lang')!r}"
    )


# ===========================================================================
# 2. RunnerAdapter.discover_ats dispatches through GLOBAL_REGISTRY (mirrors
#    .run()/.list_scope()'s self-heal-seed-then-RunnerAdapterUnavailable).
# ===========================================================================


def test_runner_adapter_discover_ats_dispatches_through_the_global_registry(
    tmp_path: Path,
) -> None:
    """``RunnerAdapter(name=...).discover_ats(target_root, regression_test_file)``
    must dispatch to the facet registered under the adapter's own name in
    ``GLOBAL_REGISTRY`` — the exact dispatch shape ``.run()``/``.list_scope()``
    already use, proven here with a fake facet under a fresh, non-colliding
    runner token.
    """
    assert hasattr(RunnerAdapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )
    seed_runner_registry()
    sentinel = object()

    def _fake_at_discovery_facet(adapter, target_root, regression_test_file):
        return sentinel

    GLOBAL_REGISTRY.register_at_discovery(
        "fake-discovery-lang", _fake_at_discovery_facet
    )
    adapter = RunnerAdapter(name="fake-discovery-lang")
    regression_file = tmp_path / "whatever.txt"
    regression_file.write_text("irrelevant content", encoding="utf-8")

    result = adapter.discover_ats(tmp_path, regression_file)
    assert result is sentinel, (
        "discover_ats must dispatch to the registered at-discovery facet "
        f"under the adapter's own name -- got {result!r} instead of the "
        "registered facet's sentinel return value"
    )


# ===========================================================================
# 3. pytest at-discovery facet: module-level AND class-nested test_* methods
#    (closes F-AT-DETECTION-IS-LANGUAGE-BOUND's class-nested blindness).
# ===========================================================================


@pytest.mark.parametrize(
    "source,expected_count",
    [
        pytest.param(
            "def test_module_level_case():\n    assert True\n",
            1,
            id="module_level_only",
        ),
        pytest.param(
            "class TestGroup:\n    def test_class_nested_case(self):\n        assert True\n",
            1,
            id="class_nested_only",
        ),
        pytest.param(
            "def test_module_level_case():\n    assert True\n\n\n"
            "class TestGroup:\n    def test_class_nested_case(self):\n        assert True\n",
            2,
            id="both_module_level_and_class_nested",
        ),
    ],
)
def test_pytest_at_discovery_facet_discovers_module_level_and_class_nested_tests(
    tmp_path: Path, source: str, expected_count: int
) -> None:
    """The pytest at-discovery facet must count BOTH a module-level
    ``test_*`` function AND a class-nested ``Test*.test_*`` method --
    ``carpaccio_format.count_pytest_regression_ats``'s class-blindness (walks
    ``tree.body`` only, never recurses into a class) is the
    ``F-AT-DETECTION-IS-LANGUAGE-BOUND`` defect this facet closes.
    """
    seed_runner_registry()
    adapter = RunnerAdapter(name="pytest")
    assert hasattr(adapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )

    regression_file = tmp_path / "test_mixed_regression.py"
    regression_file.write_text(source, encoding="utf-8")

    result = adapter.discover_ats(tmp_path, regression_file)

    assert len(result.at_ids) == expected_count, (
        f"expected {expected_count} discovered AT(s) -- got "
        f"at_ids={result.at_ids!r} for source={source!r}"
    )
    assert result.content_hash, "content_hash must be a real, non-empty seal"
    assert (
        result.content_hash == hashlib.sha256(regression_file.read_bytes()).hexdigest()
    ), (
        "content_hash must seal the file's REAL raw bytes (mirrors "
        "pytest_regression_content_hash's sha256-over-raw-source contract)"
    )


# ===========================================================================
# 4. cargo at-discovery facet: real .rs fixture, real #[test] functions.
# ===========================================================================


def test_cargo_at_discovery_facet_discovers_rust_test_functions_in_real_fixture(
    tmp_path: Path,
) -> None:
    """The cargo at-discovery facet must discover BOTH ``#[test]``-attributed
    functions in a real, controlled ``.rs`` fixture and seal the raw file
    bytes -- the relocated mirror of ``at_review_verdict._count_rust_
    regression_ats`` / ``_rust_regression_content_hash``.
    """
    seed_runner_registry()
    adapter = RunnerAdapter(name="cargo-test")
    assert hasattr(adapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )

    regression_file = tmp_path / "balance_invariants.rs"
    regression_file.write_text(
        "// Regression fixture -- balance invariants.\n\n"
        "#[test]\n"
        "fn balance_reflects_deposit() {\n"
        "    assert_eq!(2 + 2, 4);\n"
        "}\n\n"
        "#[test]\n"
        "fn balance_rejects_negative_withdrawal() {\n"
        "    assert_eq!(1 + 1, 2);\n"
        "}\n",
        encoding="utf-8",
    )

    result = adapter.discover_ats(tmp_path, regression_file)

    assert len(result.at_ids) == 2, (
        "expected exactly 2 discovered #[test] functions -- got "
        f"at_ids={result.at_ids!r}"
    )
    assert set(result.at_ids) == {
        "balance_reflects_deposit",
        "balance_rejects_negative_withdrawal",
    }, f"got the WRONG function names -- at_ids={result.at_ids!r}"
    assert (
        result.content_hash == hashlib.sha256(regression_file.read_bytes()).hexdigest()
    ), (
        "content_hash must be sha256 over the REAL .rs raw source bytes -- "
        f"got {result.content_hash!r}"
    )


# ===========================================================================
# 5. NEGATIVE -- zero #[test] functions must refuse LOUD, never a silent
#    empty discovery (mirrors the relocated _malformed_rust_regression_file).
# ===========================================================================


@pytest.mark.negative_at
def test_cargo_at_discovery_facet_refuses_a_rust_file_with_zero_test_functions(
    tmp_path: Path,
) -> None:
    """A ``.rs`` fixture with ZERO ``#[test]`` functions must NEVER yield a
    silent-empty discovery (``at_ids == ()``) -- it must raise a structured,
    loud error, mirroring ``at_review_verdict._malformed_rust_regression_
    file``'s already-shipped contract.
    """
    seed_runner_registry()
    adapter = RunnerAdapter(name="cargo-test")
    assert hasattr(adapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )

    regression_file = tmp_path / "no_tests_here.rs"
    regression_file.write_text(
        "// No #[test] functions in this file at all.\n\n"
        "pub fn add(a: i32, b: i32) -> i32 {\n"
        "    a + b\n"
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception) as excinfo:
        adapter.discover_ats(tmp_path, regression_file)
    message = str(excinfo.value).lower()
    assert "zero" in message or "malformed" in message, (
        "a zero-#[test]-functions .rs file must raise an error NAMING the "
        f"malformed/zero-test condition -- got: {excinfo.value!r}"
    )


# ===========================================================================
# 6. NEGATIVE -- garbage non-UTF-8 bytes must never let a raw
#    UnicodeDecodeError traceback escape the facet (mirrors the ALREADY-
#    FIXED at_review_verdict hardening this relocation must carry over).
# ===========================================================================


@pytest.mark.negative_at
def test_cargo_at_discovery_facet_never_lets_a_raw_traceback_escape_on_garbage_bytes(
    tmp_path: Path,
) -> None:
    """A ``.rs`` file containing raw non-UTF-8 bytes must be refused via a
    structured error naming the unreadable file -- NEVER an uncaught
    ``UnicodeDecodeError`` escaping the facet (the class of crash
    ``at_review_verdict.py``'s ``except (OSError, UnicodeDecodeError)`` guard
    already fixed; the relocation must carry that fix over, not regress it).
    """
    seed_runner_registry()
    adapter = RunnerAdapter(name="cargo-test")
    assert hasattr(adapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )

    regression_file = tmp_path / "garbage_bytes.rs"
    regression_file.write_bytes(b"\xff\xfe garbage \x00")

    with pytest.raises(Exception) as excinfo:
        adapter.discover_ats(tmp_path, regression_file)
    assert not isinstance(excinfo.value, UnicodeDecodeError), (
        "a raw UnicodeDecodeError must NEVER escape the facet uncaught -- "
        "it must be caught and re-raised as a structured, named error "
        f"(mirrors _malformed_rust_regression_file); got {excinfo.value!r}"
    )
    message = str(excinfo.value).lower()
    assert "malformed" in message or "cannot read" in message or "decode" in message, (
        f"the raised error must NAME the undecodable-file condition -- got "
        f"{excinfo.value!r}"
    )


# ===========================================================================
# 7. NEGATIVE -- an unresolved language degrades LOUD, never silently
#    passes, and NEVER falls back to a Python-native discovery.
# ===========================================================================


@pytest.mark.negative_at
def test_unresolved_language_at_discovery_never_silently_passes_or_falls_back_to_python(
    tmp_path: Path,
) -> None:
    """A runner with NO at-discovery facet registered (e.g. ``go-test`` --
    only ``pytest`` and ``cargo-test`` are wired by this fix) must raise
    ``RunnerAdapterUnavailable`` -- degrade-LOUD, never a silent pass and
    never a Python-native discovery pretending to have read a Go file.
    """
    seed_runner_registry()
    adapter = RunnerAdapter(name="go-test")
    assert hasattr(adapter, "discover_ats"), (
        f"RunnerAdapter {_AT_DISCOVERY_HASATTR_MSG}"
    )

    regression_file = tmp_path / "balance_invariants_test.go"
    regression_file.write_text(
        "package main\n\nfunc TestBalance(t *testing.T) {}\n", encoding="utf-8"
    )

    with pytest.raises(RunnerAdapterUnavailable):
        adapter.discover_ats(tmp_path, regression_file)


# ===========================================================================
# 8. End-to-end: des carpaccio-slice-gate no longer misdiagnoses a Rust
#    regression file (Branch A/B of the RCA) -- it reaches the REAL
#    verdict-absence refusal (45/"absent"), never a malformed/invalid-choice
#    (2) dead end.
# ===========================================================================


def _stage_feature_delta_with_slice_01(repo_root: Path, feature_id: str) -> None:
    feature_delta_path = (
        repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
    feature_delta_path.write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | native-regression at-kind wiring coverage | done | | |\n",
        encoding="utf-8",
    )


def test_carpaccio_slice_gate_native_regression_at_kind_reaches_the_real_verdict_check_for_a_rust_file(
    tmp_path: Path,
) -> None:
    """Driving the REAL ``des carpaccio-slice-gate`` CLI with
    ``--at-kind native-regression --regression-test-file <rust>.rs`` over a
    real, controlled Rust fixture must clear assertions 1-4 (size/coverage/
    walking-skeleton/value-annotation) using the real Rust AT count, and
    reach assertion 5's genuine "no ATReviewVerdict recorded yet" refusal
    (exit 45, reason "absent") -- NEVER a Python-parse-shaped malformed-input
    refusal (exit 2) and NEVER argparse's "invalid choice" dead end (also
    exit 2, but for a DIFFERENT, wrong reason: the flag not existing at all).
    This is the exact charter oracle: the gate must point to something
    concrete it actually read from the fixture (the real AT count), not
    merely accept a flag it cannot act on.
    """
    repo = tmp_path / "repo"
    feature_id = "b-wiring-rust-regression-at-kind"
    _stage_feature_delta_with_slice_01(repo, feature_id)
    rust_file_rel = "tests/rust/regression/balance_invariants.rs"
    rust_file = repo / rust_file_rel
    rust_file.parent.mkdir(parents=True, exist_ok=True)
    rust_file.write_text(
        "#[test]\nfn balance_reflects_deposit() {\n    assert_eq!(2 + 2, 4);\n}\n\n"
        "#[test]\nfn balance_rejects_negative_withdrawal() {\n"
        "    assert_eq!(1 + 1, 2);\n}\n",
        encoding="utf-8",
    )

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "--feature-id",
            feature_id,
            "--entering-slice",
            "slice-01",
            "--repo-root",
            str(repo),
            "--at-kind",
            "native-regression",
            "--regression-test-file",
            rust_file_rel,
        ],
        cwd=repo,
        main=carpaccio_slice_gate_main,
    )

    assert exit_code == 45, (
        "the gate must progress all the way to assertion 5's genuine "
        "'no ATReviewVerdict recorded' refusal (exit 45) for a real, "
        f"well-formed Rust regression file -- got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}. Today '--at-kind "
        "native-regression' is not a recognized choice at all (argparse "
        "rejects it, also exit 2, but BEFORE any Rust content is ever "
        "read) -- see this test module's docstring for the fix direction."
    )
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, (
        f"expected a JSON diagnostic on stdout -- got none ({stderr!r})"
    )
    import json

    diagnostic = json.loads(stdout_lines[-1])
    assert diagnostic.get("reason") == "absent", (
        "the refusal must name reason='absent' (no ATReviewVerdict recorded "
        f"yet) -- got diagnostic={diagnostic!r}. A 'no-scenarios-for-slice' "
        "or malformed-input reason here would mean the gate mis-routed the "
        "Rust file as gherkin or tried (and failed) to Python-parse it."
    )
    diagnostic_text = json.dumps(diagnostic).lower()
    for forbidden in ("syntaxerror", "invalid syntax", "cannot parse"):
        assert forbidden not in diagnostic_text, (
            f"the gate must NEVER misdiagnose a well-formed Rust file as "
            f"broken Python -- found {forbidden!r} in diagnostic={diagnostic!r}"
        )


# ===========================================================================
# 9. Branch C -- the digest leg and the E2 execution leg must AGREE on
#    whether a regression file routes through the runner-port seam.
# ===========================================================================


@pytest.mark.parametrize(
    "regression_test_file,must_route_through_runner",
    [
        pytest.param(
            "tests/rust/regression/balance_invariants.rs", True, id="rust_file_routes"
        ),
        pytest.param(
            "tests/regression/test_balance_invariants.py",
            False,
            id="python_file_unchanged",
        ),
    ],
)
def test_commit_slice_digest_routing_agrees_with_e2_execution_routing_for_the_same_regression_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    regression_test_file: str,
    must_route_through_runner: bool,
) -> None:
    """``commit_slice._committed_scope_digest_or_degrade_reason`` must accept
    ``regression_test_file`` and route a NON-Python regression file through
    the SAME runner-port seam ``verify_slice_commit_completeness._routes_
    through_runner_port`` already uses for the E2 execution leg -- Branch C
    of the RCA: TODAY this function only inspects ``at_kind`` (never the
    file), so a ``.rs`` file forced through ``--at-kind pytest-regression``
    earns a vacuous Python-native digest while E2 correctly runs cargo -- a
    live contradiction between what was digested and what was executed. A
    genuine ``.py`` file must keep the EXISTING byte-identical Python-native
    routing (the regression guard for every already-shipped pytest-
    regression slice).
    """
    sig = inspect.signature(commit_slice._committed_scope_digest_or_degrade_reason)
    assert "regression_test_file" in sig.parameters, (
        "commit_slice._committed_scope_digest_or_degrade_reason must accept "
        "regression_test_file so the digest leg's routing decision can AGREE "
        "with verify_slice_commit_completeness._routes_through_runner_port's "
        "execution-leg decision (Branch C of the RCA) -- not yet implemented."
    )

    python_native_called: list[bool] = []

    def _fail_if_called(*_args: object, **_kwargs: object) -> object:
        python_native_called.append(True)
        raise AssertionError(
            "the Python-native digest path must not be invoked for a "
            f"non-Python regression_test_file={regression_test_file!r}"
        )

    sentinel_digest = "runner-routed-digest-sentinel"
    sentinel_python_digest = "python-native-digest-sentinel"

    class _FakeDigestRoute:
        digest = sentinel_digest

    class _FakeCommittedScopeDigest:
        digest = sentinel_python_digest

    def _fake_route(repo: Path) -> _FakeDigestRoute:
        return _FakeDigestRoute()

    def _fake_python_native(
        *_args: object, **_kwargs: object
    ) -> _FakeCommittedScopeDigest:
        python_native_called.append(True)
        return _FakeCommittedScopeDigest()

    if must_route_through_runner:
        # The Python-native path must NEVER be reached for a non-Python file
        # -- calling it is itself the Branch-C defect, so the stub raises.
        monkeypatch.setattr(
            commit_slice, "_committed_scope_digest_value", _fail_if_called
        )
        monkeypatch.setattr(
            commit_slice, "_maybe_route_digest_through_runner", _fake_route
        )
        monkeypatch.setattr(commit_slice, "_DigestRouteResult", _FakeDigestRoute)
    else:
        # A genuine .py file must keep routing to the Python-native path --
        # stubbed (not real git) so this parametrized case stays hermetic;
        # the runner seam must never even be consulted for it.
        monkeypatch.setattr(
            commit_slice, "_maybe_route_digest_through_runner", _fail_if_called
        )
        monkeypatch.setattr(
            commit_slice, "_committed_scope_digest_value", _fake_python_native
        )
        monkeypatch.setattr(
            commit_slice, "_CommittedScopeDigest", _FakeCommittedScopeDigest
        )

    repo = tmp_path / "repo"
    repo.mkdir()

    digest, degrade_reason = commit_slice._committed_scope_digest_or_degrade_reason(
        repo,
        at_kind="native-regression",
        regression_test_file=repo / regression_test_file,
    )

    assert degrade_reason is None, (
        f"expected a clean digest, got degrade_reason={degrade_reason!r}"
    )
    if must_route_through_runner:
        assert digest == sentinel_digest, (
            "a non-Python regression_test_file must route the digest through "
            "the SAME runner-resolution seam the whole-tree digest CLI modes "
            f"already use -- got digest={digest!r}"
        )
        assert not python_native_called, (
            "the Python-native digest path must NEVER be invoked for "
            f"regression_test_file={regression_test_file!r}"
        )
    else:
        assert digest == sentinel_python_digest, (
            "a genuine .py regression_test_file must keep routing to the "
            f"EXISTING Python-native digest path unchanged -- got digest={digest!r}"
        )
        assert python_native_called, (
            "the Python-native digest path must still be invoked for a "
            f"genuine .py regression_test_file={regression_test_file!r} -- "
            "the runner seam must never be consulted for it"
        )
