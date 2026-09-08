"""Unit tests for `resolve_verification_authority` (SF friction 2026-08-21,
verification-authority delegation).

The sister's real Slice brief declares NO per-line `Verification command:`
labels -- it DELEGATES: prose ("Verification scope is the ADR-112 D-112.14
order") pointing at an authority document whose heading carries the marker
sentence "The exact clean-checkout verification order is:" followed by one
fenced block holding the LITERAL script (assignments, command substitution,
`!` negations, pipes). The sister's own falsifier:
`extract_declared_verification_commands` over that brief returns `[]`, so
the campaign would stay Blocked. The fixture below is byte-faithful to that
shape, sanitized only in its paths.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from des.domain.verification_authority_resolver import (
    AmbiguousAuthorityReference,
    LiteralScriptBlock,
    UnresolvedAuthorityReference,
    resolve_verification_authority,
)


def test_changed_authority_locator_selects_the_nested_changed_section() -> None:
    from des.domain.verification_authority_resolver import changed_authority_locator

    old = "# Brief\nintro\n## Feature\nold\n"
    new = "# Brief\nintro\n## Feature\nnew\n"

    assert changed_authority_locator(old, new, "docs/brief.md") == (
        "docs/brief.md#Feature"
    )


def test_changed_authority_locator_permits_one_new_section_in_existing_document() -> (
    None
):
    from des.domain.verification_authority_resolver import changed_authority_locator

    assert (
        changed_authority_locator(
            "# Brief\n", "# Brief\n## Feature\nnew\n", "docs/brief.md"
        )
        == "docs/brief.md#Feature"
    )


ADR_RELATIVE_PATH = "docs/adrs/ADR-112-formal-drive-verification-substrate.md"
ADR_HEADING = "D-112.14 — Test substrate and literal verification order"
#: The hand-written anchor spelling (dot kept, single hyphen at the dash).
ANCHOR = "d-112.14-test-substrate-and-literal-verification-order"
#: The GitHub-generated spelling of the SAME heading (dot dropped, the
#: removed em dash leaves a double hyphen).
GITHUB_ANCHOR = "d-11214--test-substrate-and-literal-verification-order"
LOCATOR = f"{ADR_RELATIVE_PATH}#{ANCHOR}"

#: The literal script block, VERBATIM: an authority SCRIPT (assignment,
#: command substitution, `!` negations, a pipe), never argv-splittable.
SCRIPT_LINES = [
    'FORMAL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/formal.XXXXXX")"',
    'cp -R formal/agda/. "$FORMAL_TMP/"',
    '/usr/bin/agda --safe "$FORMAL_TMP/DriveLaws.agda"',
    "/usr/bin/java -cp tools/tla2tools.jar tlc2.TLC -deadlock formal/tla/Drive.tla",
    "cargo build --release --manifest-path rust-shell/Cargo.toml",
    "! nm -g rust-shell/target/release/libdrive.rlib | grep -w mock_checkpoint",
    '! rg -n "unsafe_bypass" rust-shell/src/',
    "cargo test --workspace --manifest-path rust-shell/Cargo.toml",
    "go test ./drive -count=1 -run '^TestVerifiedCheckpointLive$'",
    "go test ./... -count=1",
]

EXPECTED_DIGEST = (
    "sha256:" + hashlib.sha256("\n".join(SCRIPT_LINES).encode("utf-8")).hexdigest()
)


def adr_document(*, with_heading: bool = True, with_fence: bool = True) -> str:
    lines = [
        "# ADR-112 — Formal drive verification substrate",
        "",
        "## D-112.13 — An earlier decision",
        "",
        "Unrelated prose.",
        "",
    ]
    if with_heading:
        lines += [
            f"## {ADR_HEADING}",
            "",
            "The `go test` commands run from `go-shell/`; the",
            "`cargo build --release` line is a precondition for the `nm`",
            "symbol check (release-build precondition).",
            "",
            "The exact clean-checkout verification order is:",
            "",
        ]
        if with_fence:
            lines += ["```text", *SCRIPT_LINES, "```", ""]
    lines += [
        "## D-112.15 — A later decision",
        "",
        "```text",
        "echo this fence belongs to a DIFFERENT section",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _write_adr(repo_root: Path, content: str) -> None:
    path = repo_root / ADR_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolves_the_literal_block_verbatim_with_digest(tmp_path: Path) -> None:
    _write_adr(tmp_path, adr_document())
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, LiteralScriptBlock)
    assert resolved.locator == LOCATOR
    assert list(resolved.lines) == SCRIPT_LINES
    assert resolved.content_digest == EXPECTED_DIGEST


def test_github_generated_anchor_spelling_resolves_the_same_heading(
    tmp_path: Path,
) -> None:
    # Anchor matching is normalized-slug equality (runs of non-alphanumerics
    # collapse to one hyphen), so the hand-written and the GitHub-generated
    # spellings of the same heading both resolve -- never a byte-equality
    # trap on how the author happened to spell the dash.
    _write_adr(tmp_path, adr_document())
    resolved = resolve_verification_authority(
        tmp_path, f"{ADR_RELATIVE_PATH}#{GITHUB_ANCHOR}"
    )
    assert isinstance(resolved, LiteralScriptBlock)
    assert list(resolved.lines) == SCRIPT_LINES


@pytest.mark.parametrize(
    ("locator", "prepare", "reason_fragment"),
    [
        pytest.param(LOCATOR, None, "no document", id="doc-absent"),
        pytest.param(
            f"{ADR_RELATIVE_PATH}#a-heading-that-does-not-exist",
            adr_document(),
            "heading",
            id="heading-absent",
        ),
        pytest.param(
            LOCATOR,
            adr_document(with_fence=False),
            "fenced",
            id="fence-absent-in-section",
        ),
        pytest.param(
            f"../outside.md#{ANCHOR}", adr_document(), "repository", id="parent-escape"
        ),
        pytest.param(
            f"/etc/passwd#{ANCHOR}", adr_document(), "repository", id="absolute-path"
        ),
        pytest.param(ADR_RELATIVE_PATH, adr_document(), "#", id="malformed-no-anchor"),
    ],
)
def test_unresolvable_reference_returns_typed_unresolved(
    tmp_path: Path,
    locator: str,
    prepare: str | None,
    reason_fragment: str,
) -> None:
    if prepare is not None:
        _write_adr(tmp_path, prepare)
    resolved = resolve_verification_authority(tmp_path, locator)
    assert isinstance(resolved, UnresolvedAuthorityReference)
    assert resolved.locator == locator
    assert reason_fragment.lower() in resolved.reason.lower()


def test_a_fence_in_a_later_section_never_leaks_into_this_one(
    tmp_path: Path,
) -> None:
    # The target section carries no fence; the NEXT section does. The
    # resolver must refuse, never silently bind the wrong section's block.
    _write_adr(tmp_path, adr_document(with_fence=False))
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, UnresolvedAuthorityReference)
    assert "DIFFERENT section" not in str(resolved)


def test_an_unclosed_fence_is_unresolved_never_a_runaway_block(
    tmp_path: Path,
) -> None:
    content = adr_document(with_fence=False).replace(
        "The exact clean-checkout verification order is:",
        "The exact clean-checkout verification order is:\n\n```text\n"
        + "\n".join(SCRIPT_LINES),
    )
    _write_adr(tmp_path, content)
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, UnresolvedAuthorityReference)


def test_an_empty_fenced_block_is_unresolved(tmp_path: Path) -> None:
    content = adr_document(with_fence=False).replace(
        "The exact clean-checkout verification order is:",
        "The exact clean-checkout verification order is:\n\n```text\n```",
    )
    _write_adr(tmp_path, content)
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, UnresolvedAuthorityReference)
    assert "empty" in resolved.reason.lower()


def test_colliding_headings_are_an_ambiguous_reference_never_first_match(
    tmp_path: Path,
) -> None:
    # Sister counterexample 2026-08-21: "D-112.14 -- A-B" and "D-11214 AB"
    # normalize to the SAME anchor key. First-match would silently bind
    # whichever section happens to come first -- the resolver must refuse,
    # naming every colliding candidate.
    content = adr_document().replace(
        "## D-112.15 — A later decision",
        "## D-112.14 — Test substrate and literal verification: order\n"
        "\n"
        "```text\n"
        "echo the WRONG order a first-match bind would execute\n"
        "```\n"
        "\n"
        "## D-112.15 — A later decision",
    )
    _write_adr(tmp_path, content)
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, AmbiguousAuthorityReference)
    assert resolved.locator == LOCATOR
    assert len(resolved.candidates) == 2
    assert ADR_HEADING in resolved.candidates
    assert "matches 2 headings" in resolved.reason
    # Both colliding headings are NAMED for the operator.
    for candidate in resolved.candidates:
        assert candidate in resolved.reason


def test_em_dash_and_dotless_heading_spellings_collide_ambiguously(
    tmp_path: Path,
) -> None:
    # The sister's literal ambiguous shape: "D-112.14 — A-B" vs
    # "D-11214 AB" -- punctuation-only differences, identical key.
    lines = [
        "# Doc",
        "",
        "## D-112.14 — A-B",
        "",
        "```text",
        "first order",
        "```",
        "",
        "## D-11214 AB",
        "",
        "```text",
        "second order",
        "```",
    ]
    _write_adr(tmp_path, "\n".join(lines) + "\n")
    resolved = resolve_verification_authority(
        tmp_path, f"{ADR_RELATIVE_PATH}#d-112.14-a-b"
    )
    assert isinstance(resolved, AmbiguousAuthorityReference)
    assert resolved.candidates == ("D-112.14 — A-B", "D-11214 AB")


def test_symlink_escaping_the_repository_is_refused_by_realpath(
    tmp_path: Path,
) -> None:
    # The lexical no-'..' guard cannot see a symlink: a link UNDER the
    # repository pointing OUTSIDE it satisfies both the path rule and
    # is_file(). The guard must decide on the resolved physical path.
    repo_root = tmp_path / "repo"
    outside = tmp_path / "outside-authority.md"
    outside.write_text(adr_document(), encoding="utf-8")
    link = repo_root / ADR_RELATIVE_PATH
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    resolved = resolve_verification_authority(repo_root, LOCATOR)
    assert isinstance(resolved, UnresolvedAuthorityReference)
    assert "outside the repository root" in resolved.reason


def test_symlink_staying_inside_the_repository_still_resolves(
    tmp_path: Path,
) -> None:
    # An INTERNAL symlink (both link and target under the repo root) is a
    # legitimate repo-relative authority -- the realpath guard rejects
    # only the escape, never in-repo indirection.
    real_doc = tmp_path / "docs" / "real-authority.md"
    real_doc.parent.mkdir(parents=True, exist_ok=True)
    real_doc.write_text(adr_document(), encoding="utf-8")
    link = tmp_path / ADR_RELATIVE_PATH
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(real_doc)
    resolved = resolve_verification_authority(tmp_path, LOCATOR)
    assert isinstance(resolved, LiteralScriptBlock)
    assert list(resolved.lines) == SCRIPT_LINES
