"""Regression AT — ``_parse_nextest_list`` must parse the REAL flat
``cargo nextest list`` output, not the grouped/indented shape it currently
assumes.

RCA (confirmed by two independent parties -- sister's live Rust repo `cat -A`
trace + orchestrator code-read): the docstring on
``des.adapters.driven.runner.cargo_runner._parse_nextest_list`` (lines 235-255)
assumes ``cargo nextest list`` groups its output -- a non-indented
``<binary>:`` header followed by INDENTED test paths, only the indented lines
appended as identities. The REAL default output is FLAT: every line is a
complete, non-indented ``<binary-id> <test-path>`` pair (space-separated, zero
leading whitespace -- verified with ``cat -A``, no trailing header colon, no
indent marker). Because every line is non-indented, the current parser treats
EACH line as a binary header and appends ZERO identities -> returns ``()`` ->
``_list_cargo_scope`` raises ``RunnerAdapterUnavailable`` (empty-scope) on
EVERY Rust target -> ``des verify-slice-commit`` can never mint a Gate-Scope
digest on any Rust repo (Rust is one of the 5 beta languages -- a
language-agnosticism-mandate blocker).

Golden fixture: 4 real lines captured from a live ``cargo nextest list`` run
against the ``tsunami`` crate (sister's repo), reproduced verbatim below.

This AT drives the PARSER directly (pure unit, no cargo/subprocess needed on
this box) -- it is RED against the current grouped/indented parser and must
turn GREEN once the parser is rewritten to split each flat line on its first
whitespace run.
"""

from __future__ import annotations

import pytest

from des.adapters.driven.runner.cargo_runner import _parse_nextest_list


# The golden fixture -- 4 real, flat, non-indented lines from a live
# `cargo nextest list` run. Each line is `<binary-id> <test-path>`, exactly
# ONE space-separated pair, ZERO leading indentation, no trailing `:` header.
_GOLDEN_FLAT_STDOUT = (
    "tsunami adapters::contexts::json::tests::"
    "render_json_cohesion_score_within_valid_range\n"
    "tsunami adapters::contexts::json::tests::"
    "render_json_each_context_has_required_fields\n"
    "tsunami adapters::contexts::json::tests::render_json_includes_contexts_array\n"
    "tsunami adapters::contexts::json::tests::render_json_includes_modularity_field\n"
)

_EXPECTED_IDENTITIES = (
    "tsunami::adapters::contexts::json::tests::"
    "render_json_cohesion_score_within_valid_range",
    "tsunami::adapters::contexts::json::tests::"
    "render_json_each_context_has_required_fields",
    "tsunami::adapters::contexts::json::tests::render_json_includes_contexts_array",
    "tsunami::adapters::contexts::json::tests::render_json_includes_modularity_field",
)


# ── 1. POSITIVE — the bug reproduced (RED today, GREEN after the fix) ──────


def test_flat_golden_fixture_yields_four_binary_qualified_identities() -> None:
    """The 4-line real ``cat -A``-verified flat fixture must yield 4 identities,
    each ``tsunami::<test-path>`` (binary-id joined to the test path with
    ``::``) -- never the empty tuple the grouped/indented parser mints today.
    """
    identities = _parse_nextest_list(_GOLDEN_FLAT_STDOUT)

    assert len(identities) == 4
    assert all(
        identity.startswith("tsunami::adapters::contexts::json::tests::")
        for identity in identities
    )
    assert set(identities) == set(_EXPECTED_IDENTITIES)


# ── 2. Order-stability — sorted + deduplicated, shuffle- and dup-proof ─────


@pytest.mark.parametrize(
    "shuffled_stdout",
    [
        # Original order, plus a duplicate of the first line appended.
        _GOLDEN_FLAT_STDOUT + _GOLDEN_FLAT_STDOUT.splitlines()[0] + "\n",
        # Reverse order, plus a duplicate of the last (now first) line.
        "\n".join(reversed(_GOLDEN_FLAT_STDOUT.splitlines()))
        + "\n"
        + _GOLDEN_FLAT_STDOUT.splitlines()[-1]
        + "\n",
        # Interleaved/shuffled order, plus a mid-list duplicate.
        "\n".join(_GOLDEN_FLAT_STDOUT.splitlines()[i] for i in (2, 0, 3, 1))
        + "\n"
        + _GOLDEN_FLAT_STDOUT.splitlines()[2]
        + "\n",
    ],
    ids=["dup-appended", "reversed-plus-dup", "shuffled-plus-dup"],
)
def test_flat_fixture_with_duplicates_and_reordering_yields_sorted_unique_tuple(
    shuffled_stdout: str,
) -> None:
    """Feeding the fixture out-of-order and with a duplicated line always
    collapses to the SAME sorted, deduplicated 4-tuple -- the order-stable
    digest input ``_list_cargo_scope`` relies on for a reproducible sha256.
    """
    identities = _parse_nextest_list(shuffled_stdout)

    assert identities == tuple(sorted(_EXPECTED_IDENTITIES))
    assert len(identities) == len(set(identities)) == 4


# ── 3. NEGATIVE AT — noise never mints a vacuous identity ──────────────────


@pytest.mark.parametrize(
    "noisy_stdout",
    ["", "   ", "\n\n\n", "   \n\t\n   \n"],
    ids=["empty", "single-blank", "blank-lines", "mixed-whitespace"],
)
def test_blank_or_garbage_stdout_never_mints_a_vacuous_identity(
    noisy_stdout: str,
) -> None:
    """Empty stdout and whitespace-only stdout must both parse to the EMPTY
    tuple ``()`` -- never a fabricated identity from noise. This is the
    invariant that protects ``_list_cargo_scope``'s degrade-LOUD
    ``RunnerAdapterUnavailable`` (empty-scope) path, which refuses to mint a
    vacuous ``sha256("")`` digest as a 'verified' fingerprint.
    """
    identities = _parse_nextest_list(noisy_stdout)

    assert identities == ()


# ── 4. Single-line FLAT input — exactly one identity ────────────────────────


def test_single_flat_line_yields_exactly_one_identity() -> None:
    """A single non-indented ``<binary-id> <test-path>`` line yields exactly
    one ``<binary-id>::<test-path>`` identity -- the minimal flat-format case.
    """
    stdout = "tsunami adapters::contexts::json::tests::render_json_includes_modularity_field\n"

    identities = _parse_nextest_list(stdout)

    assert identities == (
        "tsunami::adapters::contexts::json::tests::render_json_includes_modularity_field",
    )
