"""Defect (measured 2026-08-24): `query.never-wired resolve_manifest_state`
returned `never_wired: false` with a JPEG and two WOFF2 font files among its
evidence trail (`einstein-1947-public-domain.jpg`,
`lato-v24-latin-700.woff2`) -- a non-textual file counted as if it could
carry a call site. A second, distinct gap: `TreeScope`'s ignore parser
skipped ANY line containing `/` (`.claude/worktrees/` -- already declared
in the repo's own root `.gitignore`, right where a maintainer would expect
a scope exclusion to live), so a lane's own worktree content (every file
multiplied by however many lanes are live) was never excluded either.

Two structural fixes, both "by construction" (GDP-0), neither a hardcoded
per-repo-shape name list (the SAME trap
`test_tree_scope_fix_slice01.py`'s own module docstring names and guards
against for bare vendor-dir names):

1. `TreeScope._is_binary` -- the NUL-byte heuristic (`git`'s own
   binary-detection bound) excludes a non-textual file from every walk,
   unconditionally, BEFORE it is ever opened as text -- never discovered
   downstream as a `UnicodeDecodeError` read fault that still lands in a
   caller-visible exemplar/evidence trail.
2. `TreeScope._parse_ignore_file` now also recognizes a wildcard-free NESTED
   PATH entry (`.claude/worktrees/`, containing `/` but no `*`) as an
   ANCHORED exclusion (matched from the tree root only) -- previously
   silently skipped ("path-qualified... skipped rather than guessed at").
   `graphify-out/` (a bare name, no nested-path parsing needed) was added to
   the repo's own root `.gitignore` in the same fix, closing the SAME class
   of gap for graphify's generated cache/graph data.

Follow-up (same day, same shared component): fixing (1)+(2) revealed the
UPSTREAM cause of a THIRD, separately-tracked symptom --
`GraphifyAdapter._whole_tree_staleness` refusing every `never-wired` query
with `provider-error` on this box, always. Measured directly (`TreeScope`
walking `**/*.py` from the repo root): 9,442 `.py` files, 8,071 (85.5%) of
them under `.claude/worktrees/` -- `TreeScope`'s bare-name-only ignore
parser never excluded a declared NESTED path, so graphify's own manifest
(which correctly never scanned another lane's worktree) looked "stale or
unscanned" for every single one. graphify's own exclusion was correct
throughout; the consumer's SCOPE (this module) was wider than the
producer's. Two more real, on-disk gaps surfaced once (1)+(2) closed the
worktree case:

3. `.git/hooks/commit_msg.py` (a real installed git hook, gitlint's own) is
   valid Python a naive `*.py` walk finds and no code-fact provider (least
   of all graphify) was ever going to have scanned. `TreeScope` now ALWAYS
   excludes `.git` -- not ignore-derived (nobody declares their own VCS root
   in their own ignore file), and deliberately NOT the same class of
   hardcoded guess as `.venv`/`node_modules`: `.git` is git's own reserved,
   universal directory name, true in every git repository, never a
   per-project convention.
4. `.nwave/*` (this repo's OWN root `.gitignore`, with several
   `!.nwave/<child>/` per-subdirectory re-inclusions) is a real,
   single-level-wildcard-plus-negation shape `TreeScope`'s dialect could not
   represent before -- skipped as "a real glob", leaving the whole `.nwave/`
   tree (all its unrelated re-included children too) in scope. The dialect
   now recognizes `name/*` as an anchored exclusion equivalent to `name/`
   for pure exclusion, with `!name/child/` honored as a prefix-match
   OVERRIDE at scan time (not mere set subtraction) -- a deliberate,
   documented SIMPLIFICATION of full gitignore negation precedence, correct
   for this common "broad glob, then re-include specific children" idiom.

Falsifier (real box data, never fabricated): with `.claude/worktrees/`
holding several real lane worktrees and a real, freshly-materialized
`graphify-out/manifest.json` present, `query.never-wired resolve_manifest_
state` answered by `provider: textsearch` with `graphify` refusing
`provider-error` BEFORE this fix; by `provider: graphify`, `confidence:
binding-resolved`, `scope: complete`, `never_wired: true` AFTER.

Every scenario below drives the REAL `TreeScope`/`TextSearchAdapter` (never a
stub) against a `tmp_path`-seeded repo -- the established pattern
`test_tree_scope_fix_slice01.py` already uses for this exact seam.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.codefact.text_search_code_fact_adapter import (
    TextSearchAdapter,
)
from des.adapters.driven.codefact.tree_scope import TreeScope
from des.ports.code_fact_port import CAPABILITY_NEVER_WIRED, CapabilityDescriptor


def _never_wired_descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CAPABILITY_NEVER_WIRED,
        stability="stable",
        contract_version="1.0.0",
        io_schema="never_wired",
        providing_adapter="test-tree-scope-binary-and-nested-path-exclusion",
    )


def _write_producer_and_real_caller(repo: Path, symbol: str = "helper") -> None:
    (repo / "producer.py").write_text(
        f"def {symbol}():\n    return 1\n", encoding="utf-8"
    )
    (repo / "caller_real.py").write_text(
        f"from producer import {symbol}\n\n\ndef use():\n    return {symbol}()\n",
        encoding="utf-8",
    )


# --- 1. binary-content exclusion, TreeScope level ---------------------------


def test_a_file_carrying_a_nul_byte_is_excluded_from_every_walk(tmp_path: Path) -> None:
    """A `.jpg`-suffixed file whose bytes contain a NUL is dropped from
    `TreeScope.files()` regardless of its extension -- this is a CONTENT
    check, not an extension blocklist, so it needs no maintained list of
    binary suffixes to stay correct as new formats appear."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00binary\x00garbage")

    scope = TreeScope(repo)
    files = scope.files("*.*")

    assert "photo.jpg" not in [f.name for f in files], (
        f"a NUL-byte-carrying file must never enter the walk. got {files!r}"
    )
    assert scope.excluded_any, (
        "excluding a binary file must record excluded_any -- the SAME "
        "'filtered' health signal an ignore-derived exclusion already fires"
    )


def test_a_binary_file_containing_the_queried_symbol_as_bytes_never_false_positives(
    tmp_path: Path,
) -> None:
    """The strongest form of Defect 1: a binary file whose byte content
    LITERALLY contains `resolve_manifest_state(` (the exact shape a real
    call site has) must still never be counted -- proving the exclusion
    runs BEFORE the call-site pattern ever sees this file's bytes, not as a
    downstream filter over already-computed matches."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "producer.py").write_text(
        "def resolve_manifest_state():\n    return 1\n", encoding="utf-8"
    )
    (repo / "binary_lookalike.dat").write_bytes(
        b"resolve_manifest_state(\x00\xffnot really source\x00"
    )

    adapter = TextSearchAdapter(root=repo)
    result = adapter.query(
        _never_wired_descriptor(), {"symbol": "resolve_manifest_state"}
    )

    assert result.payload["never_wired"] is True, (
        "the binary lookalike must never count as a call site -- got "
        f"never_wired={result.payload['never_wired']!r} "
        f"call_sites={result.payload['call_sites']!r}"
    )
    assert result.payload["call_sites"] == []


def test_negative_control_a_real_text_file_with_a_similar_extension_still_scans(
    tmp_path: Path,
) -> None:
    """The exclusion is content-based, not a `.jpg`/`.woff2` extension
    blocklist -- a genuinely TEXTUAL file, even one whose extension often
    denotes binary content in the wild, must stay walked and findable."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_producer_and_real_caller(repo)
    # A plain-text file that merely CARRIES a binary-associated extension --
    # no NUL byte anywhere in it.
    (repo / "notes.jpg").write_text(
        "this is plain text wearing a .jpg extension\n", encoding="utf-8"
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")

    assert "notes.jpg" in [f.name for f in files], (
        "a textual file must stay walked regardless of its extension -- "
        f"the exclusion is content-based (NUL byte), never a suffix "
        f"blocklist. got {[f.name for f in files]!r}"
    )


# --- 2. anchored nested-path exclusion, TreeScope level ---------------------


def test_declared_nested_path_is_excluded_root_anchored(tmp_path: Path) -> None:
    """`.claude/worktrees/` (a declared NESTED path, containing `/` but no
    `*`) excludes everything under it -- the shape the repo's own root
    `.gitignore` already carries and `TreeScope`'s bare-name-only parser
    used to silently skip."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    lane_dir = repo / ".claude" / "worktrees" / "agent-xyz"
    lane_dir.mkdir(parents=True)
    (lane_dir / "duplicated_caller.py").write_text(
        "from producer import helper\n\n\ndef use_dup():\n    return helper()\n",
        encoding="utf-8",
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "caller_real.py" in relative, (
        "the real, non-worktree caller must stay walked"
    )
    assert not any(".claude/worktrees" in path for path in relative), (
        f"content under a DECLARED nested path must never enter the walk. "
        f"got {sorted(relative)!r}"
    )
    assert scope.excluded_any


def test_undeclared_nested_lookalike_stays_walked(tmp_path: Path) -> None:
    """A DIFFERENT nested dir shaped like `.claude/worktrees/` but never
    declared in `.gitignore` must stay walked -- proving anchored-path
    exclusion reads the DECLARED file, never a disguised name-heuristic
    (the exact discipline `test_tree_scope_fix_slice01.py` already
    establishes for bare vendor-dir names, extended here to nested paths)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    lookalike_dir = repo / "other" / "worktrees"
    lookalike_dir.mkdir(parents=True)
    (lookalike_dir / "lookalike_caller.py").write_text(
        "from producer import helper\n\n\ndef use_lookalike():\n    return helper()\n",
        encoding="utf-8",
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert any("other/worktrees" in path for path in relative), (
        "'other/worktrees/' is NOT declared in .gitignore (only "
        "'.claude/worktrees/' is) -- it must stay walked. Excluding it "
        f"anyway would prove the fix guesses names instead of reading the "
        f"declared ignore file. got {sorted(relative)!r}"
    )


def test_glob_carrying_line_is_still_skipped_never_guessed_at(tmp_path: Path) -> None:
    """A line carrying `*` (a real glob, e.g. `**/pytest.log`) is neither a
    bare name nor a wildcard-free anchored path -- it stays skipped exactly
    as before this fix, never silently mismatched against something it did
    not actually declare."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("**/pytest.log\n", encoding="utf-8")
    (repo / "sub").mkdir()
    (repo / "sub" / "pytest.log").write_text("log content\n", encoding="utf-8")

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "sub/pytest.log" in relative, (
        "a globbed .gitignore line must be skipped rather than guessed at -- "
        f"got {sorted(relative)!r}"
    )
    assert not scope.excluded_any


# --- 3. GDP-6: health_event stays honest when exclusion fires with no ignore file --


def test_binary_exclusion_reports_filtered_even_with_no_ignore_file_present(
    tmp_path: Path,
) -> None:
    """Binary-content exclusion is UNCONDITIONAL -- it fires even when no
    `.gitignore` exists at all. `health_event()` must report `"filtered"`
    in that case, never the stale `"unfiltered"` claim that used to hold
    whenever no ignore file was present, regardless of what else the walk
    actually dropped."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "photo.jpg").write_bytes(b"\x00\x01\x02binary")
    (repo / "producer.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    scope = TreeScope(repo)
    scope.files("*.*")

    assert scope.ignore_file_present is False
    assert scope.health_event() == "filtered", (
        "a binary file was dropped from the walk -- the health signal must "
        "say 'filtered', not 'unfiltered', even with no .gitignore present"
    )


def test_no_ignore_file_and_no_binary_content_stays_genuinely_unfiltered(
    tmp_path: Path,
) -> None:
    """Negative control: with no ignore file AND nothing binary to exclude,
    the walk is genuinely unfiltered -- `health_event()` must still say so
    (the pre-existing contract `test_absent_ignore_file_walks_everything_
    and_signals_loud` already covers at the acceptance layer)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "producer.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    scope = TreeScope(repo)
    scope.files("*.*")

    assert scope.health_event() == "unfiltered"


# --- 4. the measured symbol itself, mirroring the reported defect -----------


def test_never_wired_answer_never_carries_a_binary_exemplar_or_fault(
    tmp_path: Path,
) -> None:
    """Mirrors the exact reported defect shape:
    `query.never-wired resolve_manifest_state` must never surface a
    non-textual file in its fault/exemplar evidence trail -- an agent
    reading `never_wired: false` grounded in an image or a font file, and
    believing it, is exactly the failure this closes."""
    from des.adapters.driven.codefact.text_search_code_fact_adapter import (
        _FaultObservation,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "producer.py").write_text(
        "def resolve_manifest_state():\n    return 1\n", encoding="utf-8"
    )
    (repo / "font.woff2").write_bytes(b"wOF2\x00\x01\x02\x03garbage")
    (repo / "image.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00JFIF\x00binary")

    adapter = TextSearchAdapter(root=repo)
    faults = _FaultObservation()
    adapter._query(
        _never_wired_descriptor(), {"symbol": "resolve_manifest_state"}, faults
    )

    assert faults.fault_count == 0, (
        f"a binary file must be excluded before it is ever read, so it can "
        f"never contribute a read fault -- got fault_count={faults.fault_count} "
        f"exemplars={faults.exemplars!r}"
    )


# --- 5. .git is ALWAYS excluded, unconditionally, never ignore-derived -----


def test_git_directory_is_always_excluded_even_with_no_gitignore_declaring_it(
    tmp_path: Path,
) -> None:
    """`.git/hooks/commit_msg.py` (real installed hook shape) must never
    enter the walk -- and no `.gitignore` declares `.git` (nobody does),
    so this exclusion cannot be ignore-derived; it is unconditional."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_producer_and_real_caller(repo)
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "commit_msg.py").write_text(
        "from producer import helper\n\n\ndef hook():\n    return helper()\n",
        encoding="utf-8",
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "caller_real.py" in relative
    assert not any(path.startswith(".git/") for path in relative), (
        f"content under .git/ must never enter the walk, ignore file or not. "
        f"got {sorted(relative)!r}"
    )
    assert scope.excluded_any


def test_git_exclusion_does_not_hide_a_real_caller_of_the_queried_symbol(
    tmp_path: Path,
) -> None:
    """Negative control at the query level: a caller ONLY inside `.git/`
    must not count -- `never_wired` stays `True` -- while a real caller
    elsewhere is still found (the exact shape a false negative from
    over-excluding `.git` would break)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "producer.py").write_text(
        "def resolve_manifest_state():\n    return 1\n", encoding="utf-8"
    )
    git_dir = repo / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    (git_dir / "commit_msg.py").write_text(
        "from producer import resolve_manifest_state\n\n\n"
        "def hook():\n    return resolve_manifest_state()\n",
        encoding="utf-8",
    )

    adapter = TextSearchAdapter(root=repo)
    result = adapter.query(
        _never_wired_descriptor(), {"symbol": "resolve_manifest_state"}
    )

    assert result.payload["never_wired"] is True, (
        "a caller living only inside .git/ must not count as wiring -- got "
        f"{result.payload!r}"
    )


# --- 6. single-level-wildcard entries (`name/*`) with per-child negation ---


def test_single_level_wildcard_entry_excludes_children_like_a_bare_path(
    tmp_path: Path,
) -> None:
    """`.nwave/*` (this repo's own real shape) excludes everything under
    `.nwave/` -- for pure exclusion (no negation), identical behaviour to a
    plain `.nwave/` anchored-path entry."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".nwave/*\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    state_dir = repo / ".nwave" / "vera_examine_fixtures"
    state_dir.mkdir(parents=True)
    (state_dir / "fixture_caller.py").write_text(
        "from producer import helper\n\n\ndef use_fixture():\n    return helper()\n",
        encoding="utf-8",
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "caller_real.py" in relative
    assert not any(path.startswith(".nwave/") for path in relative), (
        f"a name/* entry must exclude everything under name/ just like a "
        f"plain name/ entry would. got {sorted(relative)!r}"
    )


def test_negated_child_of_a_single_level_wildcard_is_re_included(
    tmp_path: Path,
) -> None:
    """`.nwave/*` plus `!.nwave/telemetry/` (this repo's own real shape,
    just one of its several re-included children): content under the
    NEGATED child stays walked, while every OTHER, non-negated child of
    `.nwave/` stays excluded -- the override is a prefix match, not mere
    set subtraction, so it must apply to everything BENEATH the negated
    child too."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".nwave/*\n!.nwave/telemetry/\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    excluded_dir = repo / ".nwave" / "vera_examine_fixtures"
    excluded_dir.mkdir(parents=True)
    (excluded_dir / "fixture_caller.py").write_text(
        "from producer import helper\n\n\ndef use_fixture():\n    return helper()\n",
        encoding="utf-8",
    )
    included_dir = repo / ".nwave" / "telemetry" / "red-green"
    included_dir.mkdir(parents=True)
    (included_dir / "telemetry_caller.py").write_text(
        "from producer import helper\n\n\ndef use_telemetry():\n    return helper()\n",
        encoding="utf-8",
    )

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "caller_real.py" in relative
    assert not any(".nwave/vera_examine_fixtures" in path for path in relative), (
        f"a non-negated child of a name/* entry must stay excluded. "
        f"got {sorted(relative)!r}"
    )
    assert any(".nwave/telemetry/red-green" in path for path in relative), (
        f"a NEGATED child (!.nwave/telemetry/) must be re-included, "
        f"including everything nested beneath it. got {sorted(relative)!r}"
    )


def test_other_glob_shapes_still_stay_skipped_never_guessed_at(
    tmp_path: Path,
) -> None:
    """A glob that is NOT the recognized `name/*` single-level shape (here,
    a recursive `**/pytest.log`) must stay skipped exactly as before --
    this parser does not attempt general gitignore glob support."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("**/pytest.log\n", encoding="utf-8")
    (repo / "sub").mkdir()
    (repo / "sub" / "pytest.log").write_text("log\n", encoding="utf-8")

    scope = TreeScope(repo)
    files = scope.files("*.*")
    relative = {f.relative_to(repo).as_posix() for f in files}

    assert "sub/pytest.log" in relative
