"""Regression AT — feature-delta ``fix-runner-scope-discover-dedup``, slice-01.

RCA (measured this session, not re-derived here): ``discover_cargo_ats`` /
``discover_csharp_ats`` / ``discover_java_ats`` / ``discover_kotlin_ats``
(``src/des/adapters/driven/runner/{cargo,csharp,java,kotlin}_runner.py``) are
IDENTICAL under AST-extract+normalize+unified-diff, normalizing exactly the
compiled regex, the private ``_strip_*_line_comments`` helper, and the
zero-found noun string — the 4 ``_strip_*_line_comments`` helpers are
byte-identical modulo docstring. ``tests/des/acceptance/cpp_test_runner_adapter``
is ACTIVE-RED and specifies a would-be 5th copy (``discover_cpp_ats``) — this
fix lands BEFORE that 5th copy is written, so C++ (and any future language)
gets a thin wrapper by construction instead of another duplicate.

THE FIX (crafter's job — zero ``src/`` edits authored by this AT): introduce
``des.adapters.driven.runner.at_discovery`` (a narrow shared concern with a
docstring header, matching the package convention set by ``tool_discovery.py``
/ ``runner_json.py`` / ``reentrancy_guard.py``) hosting ONE
``strip_line_comments`` and ONE shared regex-scan/discovery primitive
(``discover_ats_by_regex``). The 4 ``discover_*_ats`` become thin wrappers
supplying ONLY their own compiled regex + their own zero-found noun; their
private ``_strip_*_line_comments`` helpers are REMOVED (consolidated, not
additively wrapped). OUT OF SCOPE for this slice (untouched by this AT):
``discover_pytest_ats`` (uses ``ast``, stays as-is); ``run_*_scope`` (slices
2-3); ``src/des/cli/at_review_verdict.py`` (slice 4 — it keeps its OWN
``_strip_rust_line_comments`` + ``GateError`` exit-2 translation, pinned by
``tests/bugs/des/test_record_at_review_verdict_rust_regression_at_kind.py``).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
every behavioral scenario drives the REAL, STABLE, EXISTING production entry
``RunnerAdapter(name=...).discover_ats(target_root, regression_test_file)``
dispatched through ``GLOBAL_REGISTRY`` (``des.ports.test_runner_port`` /
``des.adapters.driven.runner.runner_registry``, both modules ALREADY EXIST —
only the new shared module is absent, so importing them at module top is
P1-safe). No subprocess fork — this bugfix ships no new user-facing entry
point, only an internal dedup (no ``@walking_skeleton``).

RED-for-right-reason (per ``nw-distill-red-scaffolding`` P1-P4): the dedup-fact
test below probes the shared module's PRESENCE via ``importlib.util.find_spec``
BEFORE importing it, so today's failure is a genuine, message-carrying
``AssertionError`` (MISSING_FUNCTIONALITY), never a bare ``ModuleNotFoundError``
at collection (which would misclassify as BROKEN). The 4 per-language behavioral
invariant tests below drive the ALREADY-SHIPPED, ALREADY-GREEN production
functions — they must stay green THROUGH the refactor (Critical Rule: pin the
correct behaviour of neighbouring/existing branches so a fix cannot pass by
flattening 4 distinct per-language error messages into one generic response).
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from des.adapters.driven.runner.runner_registry import (
    seed_runner_registry,
)
from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable


_AT_DISCOVERY_MODULE = "des.adapters.driven.runner.at_discovery"

_MISSING_SHARED_MODULE_MSG = (
    f"{_AT_DISCOVERY_MODULE} must exist -- the ONE shared strip_line_comments "
    "+ shared regex-scan/discovery primitive that slice-01 of "
    "fix-runner-scope-discover-dedup introduces, hosting the logic today "
    "duplicated byte-identically across cargo_runner.py, csharp_runner.py, "
    "java_runner.py, and kotlin_runner.py (matching the package convention "
    "set by tool_discovery.py / runner_json.py / reentrancy_guard.py) -- "
    "not yet implemented."
)

# The 4 pre-existing PRIVATE per-language strip helpers this slice consolidates
# into des.adapters.driven.runner.at_discovery.strip_line_comments. Their
# survival after the fix would mean the dedup did NOT actually happen -- only
# additive wrapping did (MEASURED: the 4 are byte-identical modulo docstring).
_OLD_PRIVATE_STRIP_HELPERS = (
    ("des.adapters.driven.runner.cargo_runner", "_strip_rust_line_comments"),
    ("des.adapters.driven.runner.csharp_runner", "_strip_csharp_line_comments"),
    ("des.adapters.driven.runner.java_runner", "_strip_java_line_comments"),
    ("des.adapters.driven.runner.kotlin_runner", "_strip_kotlin_line_comments"),
)

# Leak-risk guard: each language module's __all__ is ASYMMETRIC (cargo carries
# list_cargo_scope, the others don't; go/vitest carry no discover_*_ats at
# all) and must stay byte-identical through the consolidation -- a dedup that
# accidentally widens/narrows a module's export surface is itself a
# behavioural delta.
_EXPECTED_ALL = {
    "des.adapters.driven.runner.cargo_runner": {
        "CARGO_KNOWN_LOCATIONS",
        "discover_cargo_ats",
        "list_cargo_scope",
        "run_cargo_scope",
    },
    "des.adapters.driven.runner.csharp_runner": {
        "DOTNET_KNOWN_LOCATIONS",
        "discover_csharp_ats",
        "run_csharp_scope",
    },
    "des.adapters.driven.runner.java_runner": {
        "JAVA_KNOWN_LOCATIONS",
        "discover_java_ats",
        "run_java_scope",
    },
    "des.adapters.driven.runner.kotlin_runner": {
        "GRADLE_KNOWN_LOCATIONS",
        "discover_kotlin_ats",
        "run_kotlin_scope",
    },
    "des.adapters.driven.runner.go_runner": {"GO_KNOWN_LOCATIONS", "run_go_scope"},
    "des.adapters.driven.runner.vitest_runner": {
        "VITEST_KNOWN_LOCATIONS",
        "run_vitest_scope",
    },
}

# Leak-risk guard: the language regex constants must stay importable at their
# CURRENT names from their CURRENT modules (a consolidation that relocates
# them into the shared module, or renames them, breaks any external reader).
_EXPECTED_REGEX_CONSTANT = (
    ("des.adapters.driven.runner.cargo_runner", "_RUST_TEST_FN_RE"),
    ("des.adapters.driven.runner.csharp_runner", "_CSHARP_FACT_METHOD_RE"),
    ("des.adapters.driven.runner.java_runner", "_JAVA_TEST_METHOD_RE"),
    ("des.adapters.driven.runner.kotlin_runner", "_KOTLIN_TEST_FN_RE"),
)


# ===========================================================================
# 1. THE dedup fact itself: the shared module exists, exposes ONE
#    strip_line_comments + ONE shared scan primitive, and the 4 previously
#    duplicated private per-language strip helpers are GONE.
# ===========================================================================


def test_at_discovery_scan_is_shared_not_duplicated_per_language() -> None:
    """The AT-discovery line-strip + regex-scan is ONE shared primitive, not
    4 duplicated per-language copies.

    Active-RED at HEAD: ``at_discovery.py`` does not exist yet, so
    ``find_spec`` returns ``None`` and this fires a semantic
    ``AssertionError`` (never a collection-time ``ModuleNotFoundError``).
    GREEN once DELIVER lands the shared module AND removes the 4 private
    per-language strip helpers it replaces.
    """
    spec = importlib.util.find_spec(_AT_DISCOVERY_MODULE)
    assert spec is not None, _MISSING_SHARED_MODULE_MSG

    at_discovery = importlib.import_module(_AT_DISCOVERY_MODULE)
    assert hasattr(at_discovery, "strip_line_comments"), (
        f"{_AT_DISCOVERY_MODULE} must expose ONE shared strip_line_comments "
        "-- not yet implemented."
    )
    assert hasattr(at_discovery, "discover_ats_by_regex"), (
        f"{_AT_DISCOVERY_MODULE} must expose ONE shared regex-scan/discovery "
        "primitive (discover_ats_by_regex) that the 4 thin per-language "
        "wrappers call, supplying only their own compiled regex + own "
        "zero-found noun -- not yet implemented."
    )

    for module_path, old_strip_name in _OLD_PRIVATE_STRIP_HELPERS:
        module = importlib.import_module(module_path)
        assert not hasattr(module, old_strip_name), (
            f"{module_path} must no longer define its own {old_strip_name} "
            f"-- it must be consolidated into {_AT_DISCOVERY_MODULE}."
            "strip_line_comments (measured evidence: the 4 pre-existing "
            "copies are byte-identical modulo docstring). A surviving "
            "private copy means the dedup did NOT happen, only additive "
            "wrapping did."
        )


@pytest.mark.parametrize(
    "module_path,old_strip_name",
    _OLD_PRIVATE_STRIP_HELPERS,
    ids=[m.rsplit(".", 1)[-1] for m, _ in _OLD_PRIVATE_STRIP_HELPERS],
)
def test_language_runner_no_longer_defines_its_own_private_strip_helper(
    module_path: str, old_strip_name: str
) -> None:
    """Per-language isolation of the dedup-fact assertion above -- a check
    that only asserts the aggregate could pass vacuously if only 3 of 4
    modules were actually deduplicated; this fires independently per module.
    """
    module = importlib.import_module(module_path)
    assert not hasattr(module, old_strip_name), (
        f"{module_path} must no longer define {old_strip_name} after "
        f"consolidation into {_AT_DISCOVERY_MODULE}.strip_line_comments."
    )


# ===========================================================================
# 2. Leak-risk guards: __all__ symmetry + regex-constant importability must
#    survive the consolidation byte-identical (already GREEN today -- pins
#    the neighbouring behaviour so the refactor cannot silently drift it).
# ===========================================================================


@pytest.mark.parametrize(
    "module_path,expected",
    list(_EXPECTED_ALL.items()),
    ids=list(_EXPECTED_ALL.keys()),
)
def test_runner_module_export_surface_stays_byte_identical_through_the_dedup(
    module_path: str, expected: set[str]
) -> None:
    module = importlib.import_module(module_path)
    assert set(module.__all__) == expected, (
        f"{module_path}.__all__ must stay byte-identical through the "
        f"at_discovery consolidation -- expected {sorted(expected)}, got "
        f"{sorted(module.__all__)}. The asymmetry across languages (cargo "
        "alone carries list_cargo_scope; go/vitest carry no discover_*_ats "
        "at all) is intentional and must not be flattened by the dedup."
    )


@pytest.mark.parametrize(
    "module_path,constant_name",
    _EXPECTED_REGEX_CONSTANT,
    ids=[m.rsplit(".", 1)[-1] for m, _ in _EXPECTED_REGEX_CONSTANT],
)
def test_language_regex_constant_stays_importable_at_its_current_name(
    module_path: str, constant_name: str
) -> None:
    module = importlib.import_module(module_path)
    assert hasattr(module, constant_name), (
        f"{constant_name} must stay importable from {module_path} at its "
        "CURRENT name after the at_discovery consolidation -- relocating or "
        "renaming it breaks any external reader of this compiled regex."
    )
    constant = getattr(module, constant_name)
    assert isinstance(constant, re.Pattern), (
        f"{module_path}.{constant_name} must remain a compiled re.Pattern "
        f"-- got {type(constant)!r}."
    )


# ===========================================================================
# 3. Per-language behavioral invariants the dedup MUST NOT change (Critical
#    Rule: pin the correct behaviour of neighbouring branches). Every
#    scenario is parametrized over the 4 languages so a check that cannot
#    discriminate one language's own noun/message from another's can never
#    pass vacuously.
# ===========================================================================


@dataclass(frozen=True)
class _LanguageAtDiscoveryFixture:
    runner_name: str
    filename: str
    good_source: str
    expected_ids: frozenset[str]
    zero_source: str
    zero_found_noun_fragment: str


_CARGO_GOOD_SOURCE = """\
// Balance invariants regression fixture.

#[test]
fn balance_reflects_deposit() {
    assert_eq!(2 + 2, 4);
}

#[test]
fn balance_rejects_negative_withdrawal() {
    assert_eq!(1 + 1, 2);
}

// #[test] fn commented_out_fake_test() {}

pub fn helper_not_a_test() {}
"""

_CARGO_ZERO_SOURCE = """\
// No #[test] functions in this file at all.

pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""

_CSHARP_GOOD_SOURCE = """\
using Xunit;

namespace Fixture
{
    public class FixtureRegressionTest
    {
        [Fact]
        public void AdditionIsCommutative()
        {
            Assert.Equal(1 + 2, 2 + 1);
        }

        [Fact]
        public void SubtractionIsNotCommutative()
        {
            Assert.NotEqual(5 - 2, 2 - 5);
        }

        // [Fact] public void CommentedOutFakeTest() {}

        public void HelperNotATest()
        {
        }
    }
}
"""

_CSHARP_ZERO_SOURCE = """\
using Xunit;

namespace Fixture
{
    public class FixtureRegressionTestEmpty
    {
        public void HelperNotATest()
        {
            // no [Fact] attributes anywhere in this file
        }
    }
}
"""

_JAVA_GOOD_SOURCE = """\
import org.junit.jupiter.api.Test;

public class FixtureRegressionTest {
    @Test
    void additionIsCommutative() {
        assert (1 + 2) == (2 + 1);
    }

    @Test
    void subtractionIsNotCommutative() {
        assert (5 - 2) != (2 - 5);
    }

    // @Test void commentedOutFakeTest() {}

    void helperNotATest() {
    }
}
"""

_JAVA_ZERO_SOURCE = """\
public class FixtureRegressionTestEmpty {
    void helperNotATest() {
    }
}
"""

_KOTLIN_GOOD_SOURCE = """\
import org.junit.jupiter.api.Test

class FixtureRegressionTest {
    @Test
    fun additionIsCommutative() {
        assert(1 + 2 == 2 + 1)
    }

    @Test
    fun subtractionIsNotCommutative() {
        assert(5 - 2 != 2 - 5)
    }

    // @Test fun commentedOutFakeTest() {}

    fun helperNotATest() {
    }
}
"""

_KOTLIN_ZERO_SOURCE = """\
class FixtureRegressionTestEmpty {
    fun helperNotATest() {
    }
}
"""

_LANGUAGE_FIXTURES = (
    _LanguageAtDiscoveryFixture(
        runner_name="cargo-test",
        filename="fixture_regression.rs",
        good_source=_CARGO_GOOD_SOURCE,
        expected_ids=frozenset(
            {"balance_reflects_deposit", "balance_rejects_negative_withdrawal"}
        ),
        zero_source=_CARGO_ZERO_SOURCE,
        zero_found_noun_fragment="#[test] functions",
    ),
    _LanguageAtDiscoveryFixture(
        runner_name="dotnet-test",
        filename="FixtureRegressionTest.cs",
        good_source=_CSHARP_GOOD_SOURCE,
        expected_ids=frozenset(
            {"AdditionIsCommutative", "SubtractionIsNotCommutative"}
        ),
        zero_source=_CSHARP_ZERO_SOURCE,
        zero_found_noun_fragment="[Fact] methods",
    ),
    _LanguageAtDiscoveryFixture(
        runner_name="maven-test",
        filename="FixtureRegressionTest.java",
        good_source=_JAVA_GOOD_SOURCE,
        expected_ids=frozenset(
            {"additionIsCommutative", "subtractionIsNotCommutative"}
        ),
        zero_source=_JAVA_ZERO_SOURCE,
        zero_found_noun_fragment="@Test methods",
    ),
    _LanguageAtDiscoveryFixture(
        runner_name="gradle-test",
        filename="FixtureRegressionTest.kt",
        good_source=_KOTLIN_GOOD_SOURCE,
        expected_ids=frozenset(
            {"additionIsCommutative", "subtractionIsNotCommutative"}
        ),
        zero_source=_KOTLIN_ZERO_SOURCE,
        zero_found_noun_fragment="@Test functions",
    ),
)


@pytest.fixture(autouse=True)
def _seeded_registry() -> None:
    seed_runner_registry()


@pytest.mark.parametrize("fixture", _LANGUAGE_FIXTURES, ids=lambda f: f.runner_name)
def test_discover_ats_finds_real_tests_excludes_comment_only_and_seals_raw_bytes(
    tmp_path: Path, fixture: _LanguageAtDiscoveryFixture
) -> None:
    """A real test declaration is discovered; a comment-only lookalike is
    NOT; ``at_ids`` is a tuple; ``content_hash`` seals the file's RAW BYTES
    (never the decoded text).
    """
    adapter = RunnerAdapter(name=fixture.runner_name)
    regression_file = tmp_path / fixture.filename
    regression_file.write_text(fixture.good_source, encoding="utf-8")

    result = adapter.discover_ats(tmp_path, regression_file)

    assert isinstance(result.at_ids, tuple), (
        f"{fixture.runner_name}'s discover_ats must return at_ids as a "
        f"TUPLE -- got {type(result.at_ids)!r}."
    )
    assert set(result.at_ids) == fixture.expected_ids, (
        f"{fixture.runner_name} must discover EXACTLY the real test "
        f"declarations, excluding the comment-only lookalike: expected "
        f"{sorted(fixture.expected_ids)}, got {sorted(result.at_ids)}."
    )
    expected_hash = hashlib.sha256(regression_file.read_bytes()).hexdigest()
    assert result.content_hash == expected_hash, (
        f"{fixture.runner_name}'s content_hash must be sha256 over the "
        f"file's RAW BYTES (not the decoded text): expected "
        f"{expected_hash!r}, got {result.content_hash!r}."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("fixture", _LANGUAGE_FIXTURES, ids=lambda f: f.runner_name)
def test_discover_ats_refuses_loud_naming_its_own_noun_on_zero_matches(
    tmp_path: Path, fixture: _LanguageAtDiscoveryFixture
) -> None:
    """Zero matches must refuse LOUD naming THIS language's OWN noun --
    never a silent empty discovery, and never another language's noun
    (the exact vacuous-pass the shared primitive could introduce if the
    per-language noun were lost in consolidation).
    """
    adapter = RunnerAdapter(name=fixture.runner_name)
    regression_file = tmp_path / fixture.filename
    regression_file.write_text(fixture.zero_source, encoding="utf-8")

    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.discover_ats(tmp_path, regression_file)

    message = str(excinfo.value)
    assert fixture.zero_found_noun_fragment in message, (
        f"{fixture.runner_name}'s zero-match refusal must name ITS OWN "
        f"noun {fixture.zero_found_noun_fragment!r} -- got {message!r}."
    )
    other_nouns = {
        other.zero_found_noun_fragment
        for other in _LANGUAGE_FIXTURES
        if other.runner_name != fixture.runner_name
    }
    for other_noun in other_nouns:
        assert other_noun not in message, (
            f"{fixture.runner_name}'s zero-match refusal must NEVER name "
            f"another language's noun ({other_noun!r}) -- got {message!r}. "
            "A borrowed noun means the shared primitive lost the "
            "per-language zero-found wording during consolidation."
        )


@pytest.mark.negative_at
@pytest.mark.parametrize("fixture", _LANGUAGE_FIXTURES, ids=lambda f: f.runner_name)
def test_discover_ats_refuses_loud_naming_cannot_read_on_unreadable_file(
    tmp_path: Path, fixture: _LanguageAtDiscoveryFixture
) -> None:
    """An unreadable (missing) regression file is refused LOUD naming
    'cannot read <path>' -- distinctly from the undecodable-file message
    below (never collapsed into one generic wording).
    """
    adapter = RunnerAdapter(name=fixture.runner_name)
    missing_file = tmp_path / f"missing-{fixture.filename}"

    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.discover_ats(tmp_path, missing_file)

    message = str(excinfo.value)
    assert "cannot read" in message, (
        f"{fixture.runner_name}'s unreadable-file refusal must name "
        f"'cannot read' -- got {message!r}."
    )
    assert str(missing_file) in message, (
        f"{fixture.runner_name}'s unreadable-file refusal must name the "
        f"actual path -- got {message!r}, expected to contain "
        f"{str(missing_file)!r}."
    )
    assert "malformed" not in message.lower(), (
        f"{fixture.runner_name}'s unreadable-file message must be DISTINCT "
        f"from the undecodable-file ('malformed ... not valid UTF-8') "
        f"message -- got {message!r}."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("fixture", _LANGUAGE_FIXTURES, ids=lambda f: f.runner_name)
def test_discover_ats_refuses_loud_naming_malformed_utf8_on_undecodable_file(
    tmp_path: Path, fixture: _LanguageAtDiscoveryFixture
) -> None:
    """An undecodable (non-UTF-8) regression file is refused LOUD naming
    'cannot read/decode ...: malformed (not valid UTF-8)' -- a SEPARATE
    message from the plain unreadable-file case above, never a raw
    ``UnicodeDecodeError`` traceback escaping the facet.
    """
    adapter = RunnerAdapter(name=fixture.runner_name)
    regression_file = tmp_path / fixture.filename
    regression_file.write_bytes(b"\xff\xfe garbage \x00")

    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.discover_ats(tmp_path, regression_file)

    assert not isinstance(excinfo.value, UnicodeDecodeError), (
        f"{fixture.runner_name} must never let a raw UnicodeDecodeError "
        f"escape discover_ats uncaught -- got {excinfo.value!r}."
    )
    message = str(excinfo.value)
    assert "malformed" in message and "utf-8" in message.lower(), (
        f"{fixture.runner_name}'s undecodable-file refusal must name "
        f"'malformed (not valid UTF-8)' -- got {message!r}."
    )
    assert str(regression_file) in message, (
        f"{fixture.runner_name}'s undecodable-file refusal must name the "
        f"actual path -- got {message!r}."
    )
    assert "cannot read/decode" in message, (
        f"{fixture.runner_name}'s undecodable-file message must use the "
        f"'cannot read/decode' wording, distinct from the plain "
        f"unreadable-file 'cannot read' wording -- got {message!r}."
    )


# ===========================================================================
# 4. Unresolved language still degrades LOUD (unaffected by this slice --
#    a regression pin that the shared primitive never widens which runners
#    it silently answers for).
# ===========================================================================


def test_unresolved_language_still_degrades_loud_never_a_silent_pass(
    tmp_path: Path,
) -> None:
    adapter = RunnerAdapter(name="go-test")
    regression_file = tmp_path / "balance_invariants_test.go"
    regression_file.write_text(
        "package main\n\nfunc TestBalance(t *testing.T) {}\n", encoding="utf-8"
    )

    with pytest.raises(RunnerAdapterUnavailable):
        adapter.discover_ats(tmp_path, regression_file)


__all__: list[str] = []
