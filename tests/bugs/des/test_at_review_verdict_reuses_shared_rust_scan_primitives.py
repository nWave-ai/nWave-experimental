"""Regression AT -- feature-delta ``fix-runner-scope-discover-dedup``, slice-04.

RCA (measured this session): ``src/des/cli/at_review_verdict.py`` carries a
byte-identical copy of ``_RUST_TEST_FN_RE`` (line 260) and
``_strip_rust_line_comments`` (line 266) -- both duplicating the shared
primitives ``des.adapters.driven.runner.at_discovery`` introduced in slice-01
and ``des.adapters.driven.runner.cargo_runner`` relocated (and re-EXPORTED
under the same constant name) in a later slice. ``cargo_runner.py``'s own
module docstring for its at-discovery facet already CLAIMS it "relocates
[_RUST_TEST_FN_RE / _strip_rust_line_comments] VERBATIM" from
``at_review_verdict.py`` -- but the original definitions were never actually
deleted, so today the codebase carries BOTH the shared copy AND the original.

THE FIX (crafter's job, NOT implemented by this AT -- test-authoring only,
zero ``src/`` edits): ``at_review_verdict._count_rust_regression_ats`` must
stop compiling its own independent ``_RUST_TEST_FN_RE`` and stop defining its
own ``_strip_rust_line_comments`` -- it must scan with the EXACT SAME
(``is``-identical) regex object as ``cargo_runner._RUST_TEST_FN_RE`` and
strip comments via the EXACT SAME function object as
``at_discovery.strip_line_comments``. WHAT MUST NOT CHANGE (the whole point
of this slice, zero behavioural delta on the CLI's own observable contract):
``_count_rust_regression_ats`` keeps its OWN ``read_text(encoding="utf-8")``
read, its OWN combined ``except (OSError, UnicodeDecodeError)`` catch into
ONE message, its OWN ``GateError(2, {"event": "MalformedInput", "cause":
"the rust regression-test file", ...})`` raise, and its OWN ``list[str]``
return type -- distinct from the adapter facet
(``at_discovery.discover_ats_by_regex``), which does ``read_bytes`` + a
SEPARATE decode step, TWO distinct messages, raises
``RunnerAdapterUnavailable``, and returns a tuple inside
``AtDiscoveryResult``. The fix must NOT delegate to
``carpaccio_format.native_regression_at_discovery`` or to
``at_discovery.discover_ats_by_regex`` directly -- either would change the
CLI's observable error channel (a different exception type, a different
message, "no AT detector for this language" instead of the pinned
MalformedInput wording).

LESSON FROM SLICES 2 AND 3 (applied here): an AT anchored only to the CLI
SITE being changed stops discriminating the moment the fix rewrites that
site. This file anchors instead to the two SHARED definitions
(``cargo_runner._RUST_TEST_FN_RE`` / ``at_discovery.strip_line_comments``)
via OBJECT IDENTITY (``is``, never mere pattern-text equality -- a freshly
re-``re.compile``'d byte-identical copy is equal-looking but NOT
identity-equal, and identity is exactly what "reuse" means here), and to a
content-anchored scan of the file's raw SOURCE TEXT (never a fixed list of
known site/function names) for the literal duplicated definitions -- a
reintroduced duplicate under a brand-new name, in a brand-new function, or in
a brand-new module-level constant is still caught, closing the known gap of
the slice-03-style "enumerate five named wrapper functions" check.

Driving surface: this is a STRUCTURAL dedup-fact regression (no new user-
observable behaviour), matching the established precedent of
``test_at_discovery_scan_is_shared_not_duplicated_per_language.py``
(slice-01) -- direct introspection of the production module under test is
the correct surface for a "is this internal definition still duplicated"
fact, which cannot be observed through the CLI's black-box behaviour (the
CLI's OBSERVABLE behaviour is designed to stay byte-identical through this
fix). The behavioural-pin tests at the bottom additionally drive
``_count_rust_regression_ats`` directly to pin the CLI's OWN error-channel
contract (exit shape, message, return type) that must survive the dedup
unchanged -- mirroring ``tests/bugs/des/test_record_at_review_verdict_
rust_regression_at_kind.py``'s already-shipped CLI-level pins for the SAME
observable contract, from the introspection angle a CLI-level assertion
cannot reach.

RED-for-right-reason (per ``nw-distill-red-scaffolding`` P1-P4): every
dedup-fact assertion below fires today because the duplicate genuinely
exists at HEAD (measured: ``src/des/cli/at_review_verdict.py:260-275``) --
a real, message-carrying ``AssertionError``, never an import/collection
error (``des.cli.at_review_verdict``, ``des.adapters.driven.runner.
cargo_runner``, and ``des.adapters.driven.runner.at_discovery`` all already
exist and already export the names this file imports).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import ModuleType

import pytest

from des.adapters.driven.runner import at_discovery, cargo_runner
from des.cli import at_review_verdict
from des.cli.carpaccio_format import GateError


_AT_REVIEW_VERDICT_SOURCE_PATH = Path(inspect.getfile(at_review_verdict))


def _at_review_verdict_source() -> str:
    return _AT_REVIEW_VERDICT_SOURCE_PATH.read_text(encoding="utf-8")


def _write_rust_fixture_with_two_tests(path: Path) -> None:
    """A controlled, pytest-independent Rust ``.rs`` fixture: two ``#[test]``
    functions, realistic idiom (descriptive names, not ``test_``-prefixed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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


def _write_garbage_bytes_fixture(path: Path) -> None:
    """A ``.rs`` fixture containing raw non-UTF-8 bytes -- the undecodable-
    file case the CLI's own combined ``except (OSError, UnicodeDecodeError)``
    guard must keep catching after the dedup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe garbage \x00")


# ===========================================================================
# 1. Content-anchored source scan -- no duplicate definition anywhere in the
#    file (not a fixed list of known site names; a duplicate moved to a new
#    name/function/module-level constant is still caught).
# ===========================================================================


def test_at_review_verdict_source_has_no_independent_rust_test_fn_regex_definition() -> (
    None
):
    """No ``re.compile(...)`` call anywhere in ``at_review_verdict.py`` may
    carry the Rust ``#[test]``-attribute pattern text -- that regex is owned
    by ``cargo_runner._RUST_TEST_FN_RE``. A reintroduced duplicate (any
    name, any function, any location in this file) still contains the
    literal ``#\\[test\\]`` substring inside a ``re.compile(...)`` call,
    which is exactly what this scan catches regardless of where it is
    placed -- anchored to the file's raw SOURCE TEXT, never to one fixed
    site name.
    """
    source = _at_review_verdict_source()
    duplicate_pattern_marker = r"#\[test\]"
    compile_count = source.count("re.compile(")
    marker_count = source.count(duplicate_pattern_marker)
    assert not (compile_count and marker_count), (
        "at_review_verdict.py must NOT define its own Rust #[test]-function "
        "regex anywhere in the file -- it must reuse "
        "cargo_runner._RUST_TEST_FN_RE instead (fix-runner-scope-discover-"
        f"dedup slice-04). Found {marker_count} occurrence(s) of the "
        f"literal pattern marker {duplicate_pattern_marker!r} alongside "
        f"{compile_count} 're.compile(' call(s) in "
        f"{_AT_REVIEW_VERDICT_SOURCE_PATH} -- this is the exact "
        "byte-identical duplicate regex that must be removed, not merely "
        "renamed or moved to a new function."
    )


def test_at_review_verdict_source_has_no_independent_line_comment_stripper_definition() -> (
    None
):
    """No function definition anywhere in ``at_review_verdict.py`` may
    reproduce the ``//``-line-comment-stripping idiom -- that logic is owned
    by ``at_discovery.strip_line_comments``. A reintroduced duplicate (any
    name, any location) necessarily performs
    ``line.split("//", 1)[0]`` to strip a trailing line comment; this is a
    content-anchored scan of the file's raw source text, not a lookup of one
    fixed function name -- a duplicate hidden in a brand-new function or
    module-level helper is still caught.
    """
    source = _at_review_verdict_source()
    duplicate_idiom = 'split("//", 1)[0]'
    assert duplicate_idiom not in source, (
        "at_review_verdict.py must NOT define its own '//' line-comment "
        "stripper anywhere in the file -- it must reuse "
        "des.adapters.driven.runner.at_discovery.strip_line_comments "
        "instead (fix-runner-scope-discover-dedup slice-04). Found the "
        f"duplicated stripping idiom {duplicate_idiom!r} still present in "
        f"{_AT_REVIEW_VERDICT_SOURCE_PATH}."
    )


# ===========================================================================
# 2. Fixed-name absence checks -- cheap, redundant sanity checks matching the
#    established sibling-file convention (slice-01's
#    test_at_discovery_scan_is_shared_not_duplicated_per_language.py).
# ===========================================================================


def test_at_review_verdict_module_no_longer_defines_its_own_private_rust_regex_constant() -> (
    None
):
    assert not hasattr(at_review_verdict, "_RUST_TEST_FN_RE"), (
        "des.cli.at_review_verdict must no longer define its own "
        "_RUST_TEST_FN_RE constant -- it must reuse "
        "cargo_runner._RUST_TEST_FN_RE instead (fix-runner-scope-discover-"
        "dedup slice-04). A surviving local copy under this exact name "
        "means the dedup did not happen, only additive wrapping did."
    )


def test_at_review_verdict_module_no_longer_defines_its_own_private_strip_helper() -> (
    None
):
    assert not hasattr(at_review_verdict, "_strip_rust_line_comments"), (
        "des.cli.at_review_verdict must no longer define its own "
        "_strip_rust_line_comments helper -- it must reuse "
        "des.adapters.driven.runner.at_discovery.strip_line_comments "
        "instead (fix-runner-scope-discover-dedup slice-04). A surviving "
        "local copy under this exact name means the dedup did not happen, "
        "only additive wrapping did."
    )


# ===========================================================================
# 3. Object-identity delegation proof -- the strongest anchor: the shared
#    definitions themselves, never the CLI site being rewritten. A byte-
#    identical but independently re.compile()'d duplicate is EQUAL-LOOKING
#    but NOT identity-equal; identity is exactly what "reuse" means.
# ===========================================================================


def _referenced_global_objects(func: object) -> list[object]:
    """Every object ``func``'s top-level global-name references resolve to,
    PLUS (for any referenced MODULE) that module's ``strip_line_comments`` /
    ``_RUST_TEST_FN_RE`` attributes if present -- covers both
    ``from X import Y`` (bare-name reference) and ``import X`` (qualified
    ``X.Y`` reference) call styles without presuming which one the fix
    picks.
    """
    closure_vars = inspect.getclosurevars(func)  # type: ignore[arg-type]
    objects: list[object] = list(closure_vars.globals.values())
    for value in list(objects):
        if isinstance(value, ModuleType):
            for attr_name in ("strip_line_comments", "_RUST_TEST_FN_RE"):
                if hasattr(value, attr_name):
                    objects.append(getattr(value, attr_name))
    return objects


def test_at_review_verdict_reuses_the_shared_rust_scan_instead_of_its_own_copy() -> (
    None
):
    """The central discriminator (named per this dispatch's own
    justification): ``_count_rust_regression_ats`` must scan with the EXACT
    SAME (``is``-identical) regex object as ``cargo_runner._RUST_TEST_FN_RE``
    and strip comments via the EXACT SAME function object as
    ``at_discovery.strip_line_comments`` -- never an independently
    ``re.compile()``'d or independently ``def``'d copy of the identical
    logic. FAILS with a semantic AssertionError today, naming the offending
    copy, because ``_count_rust_regression_ats`` currently references its
    OWN module-local ``_RUST_TEST_FN_RE`` / ``_strip_rust_line_comments``
    (distinct objects, even though the pattern text and stripping logic are
    byte-identical to the shared ones).
    """
    assert hasattr(at_review_verdict, "_count_rust_regression_ats"), (
        "des.cli.at_review_verdict._count_rust_regression_ats must still "
        "exist -- this slice dedups its INTERNAL regex/stripper, it does "
        "not remove or rename the function itself (that function's own "
        "read_text/GateError/list[str] contract is pinned below)."
    )
    referenced = _referenced_global_objects(
        at_review_verdict._count_rust_regression_ats
    )

    regex_is_shared = any(obj is cargo_runner._RUST_TEST_FN_RE for obj in referenced)
    assert regex_is_shared, (
        "at_review_verdict._count_rust_regression_ats does NOT scan with "
        "cargo_runner._RUST_TEST_FN_RE (object identity) -- it references "
        "an independent copy of the same pattern text instead. The regex "
        "objects actually referenced by this function's globals are: "
        f"{[obj for obj in referenced if hasattr(obj, 'pattern')]!r}. "
        "Reuse cargo_runner._RUST_TEST_FN_RE directly (import it, or "
        "reference cargo_runner._RUST_TEST_FN_RE qualified) instead of "
        "compiling a fresh, independently-owned copy."
    )

    stripper_is_shared = any(
        obj is at_discovery.strip_line_comments for obj in referenced
    )
    assert stripper_is_shared, (
        "at_review_verdict._count_rust_regression_ats does NOT call "
        "at_discovery.strip_line_comments (object identity) -- it calls an "
        "independent, byte-identical _strip_rust_line_comments copy "
        "instead. Reuse des.adapters.driven.runner.at_discovery."
        "strip_line_comments directly instead of defining a fresh, "
        "independently-owned stripper."
    )


# ===========================================================================
# 4. Behavioural pins -- GREEN today, must stay GREEN after the dedup: the
#    CLI's OWN error channel, wording, and return type must survive
#    unchanged. If the fix mistakenly delegates to the adapter facet
#    (at_discovery.discover_ats_by_regex / carpaccio_format.
#    native_regression_at_discovery) instead of reusing ONLY the shared
#    regex + stripper, these pins catch the channel-collapse.
# ===========================================================================


def test_count_rust_regression_ats_still_returns_a_plain_list_for_two_real_tests(
    tmp_path: Path,
) -> None:
    """Behavioural pin: the return TYPE stays the CLI's own ``list[str]`` --
    distinct from the adapter facet's ``AtDiscoveryResult`` (a tuple inside
    a dataclass). The dedup shares ONLY the regex + stripper, never the
    return-shape/wiring.
    """
    rust_file = tmp_path / "balance_invariants.rs"
    _write_rust_fixture_with_two_tests(rust_file)

    at_ids = at_review_verdict._count_rust_regression_ats(rust_file)

    assert isinstance(at_ids, list), (
        "_count_rust_regression_ats must keep returning a plain list[str] "
        f"-- got {type(at_ids)!r}. The adapter facet "
        "(at_discovery.discover_ats_by_regex) returns an AtDiscoveryResult "
        "with a TUPLE at_ids -- these must NOT be conflated by the dedup."
    )
    assert set(at_ids) == {
        "balance_reflects_deposit",
        "balance_rejects_negative_withdrawal",
    }, f"got the WRONG function names -- at_ids={at_ids!r}"


@pytest.mark.negative_at
def test_count_rust_regression_ats_still_raises_its_own_gateerror_shape_on_garbage_bytes(
    tmp_path: Path,
) -> None:
    """Behavioural pin: an unreadable/undecodable ``.rs`` file must still
    raise the CLI's OWN ``GateError`` (exit 2, event ``MalformedInput``,
    cause ``"the rust regression-test file"``) via ONE combined ``except
    (OSError, UnicodeDecodeError)`` clause -- NEVER the adapter facet's
    ``RunnerAdapterUnavailable`` (a DIFFERENT exception type with a SEPARATE
    read-bytes-then-decode split, and a message mentioning "malformed (not
    valid UTF-8)" rather than this CLI's own wording). If the dedup fix
    narrows this to only catching ``OSError`` (the shared primitive's own
    split-exception shape), a raw ``UnicodeDecodeError`` would escape
    uncaught -- this pin catches that channel-collapse.
    """
    garbage_file = tmp_path / "garbage.rs"
    _write_garbage_bytes_fixture(garbage_file)

    with pytest.raises(GateError) as excinfo:
        at_review_verdict._count_rust_regression_ats(garbage_file)

    assert excinfo.value.exit_code == 2, (
        f"expected exit_code=2 -- got {excinfo.value.exit_code!r}"
    )
    assert excinfo.value.payload.get("event") == "MalformedInput", (
        f"expected event='MalformedInput' -- got payload={excinfo.value.payload!r}"
    )
    assert excinfo.value.payload.get("cause") == "the rust regression-test file", (
        "the CLI's OWN cause wording must survive the dedup -- got "
        f"payload={excinfo.value.payload!r}"
    )


@pytest.mark.negative_at
def test_count_rust_regression_ats_never_raises_runner_adapter_unavailable() -> None:
    """Negative guard: the wrong outcome (the adapter facet's exception
    type leaking through the CLI's own boundary) must be structurally
    absent, not merely "usually doesn't happen". Imported lazily so a
    missing/renamed symbol degrades this ONE test, never collection.
    """
    from des.ports.test_runner_port import RunnerAdapterUnavailable

    assert not issubclass(RunnerAdapterUnavailable, GateError), (
        "RunnerAdapterUnavailable and GateError must stay distinct "
        "exception hierarchies -- a common base would let the adapter "
        "facet's exception silently satisfy this CLI's `except GateError` "
        "handling, defeating the pin above."
    )


__all__: list[str] = []
