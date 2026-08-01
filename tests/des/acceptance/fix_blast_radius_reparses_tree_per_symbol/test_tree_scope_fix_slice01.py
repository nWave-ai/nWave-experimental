# @feature-fix-blast-radius-reparses-tree-per-symbol
"""Acceptance tests -- CodeFactPort floor-tier tree-walk fix (DISTILL, slice-01).

Feature-delta: docs/feature/fix-blast-radius-reparses-tree-per-symbol/feature-delta.md
  ([REF] Slice Plan slice-01 row, [REF] Scenario List with Tags, [REF] Reuse
  Analysis -- New components, [REF] Dangling decision surfaced to DELIVER).

Slice-01 value (feature-delta Slice Plan): `AstAdapter`/`TextSearchAdapter` (the
`CodeFactPort` floor tiers `des blast-radius` always runs on an OSS-tier target)
exclude a target's OWN declared vendor/build directories -- parsed from its own
ignore file in pure Python, never a hardcoded per-repo-shape list -- from every
tree walk, and answer N distinct `query.callers-of` symbol requests over the SAME
tree in a call-count that does not scale with N; an absent ignore file walks
everything and says so.

THE TRAP this module exists to guard against (dispatch's own framing): the
obvious fix is "exclude .venv/node_modules/.git" -- a HARDCODED list validated on
THIS repo's shape, the SAME DISEASE as master-hardcoded / the pytest marker
filter / `EXCLUDED_SEARCH_DIRS` (`feature_at_files.py`, a DIFFERENT already-shipped
mechanism that hardcodes exactly this list for a DIFFERENT purpose -- proof the
trap is real, not hypothetical, in THIS codebase). Every fixture below uses vendor
directory NAMES (`target/`, `_build/`, `out/`) that do not appear in ANY plausible
Python-repo hardcoded exclude list, so a hardcoded-list "fix" fails these ATs
exactly as today's zero-exclusion code does.

Contract under test (DOES NOT EXIST YET -- active-RED by design):
  * `AstAdapter._iter_files` / `TextSearchAdapter._iter_files` (currently an
    UNFILTERED `rglob`, `ast_code_fact_adapter.py:444-452` /
    `text_search_code_fact_adapter.py:196-202`) must derive exclusions from the
    target repo's own root `.gitignore`.
  * `CodeFactChain.health_events()` (currently only ever emits the
    `health.gate.code-fact.tsunami-absent` member) must gain a NEW "filtered"/
    "unfiltered" signal member of the SAME `health.gate.code-fact.*` family.
  * A single adapter instance answering N `query.callers-of` calls for N distinct
    symbols must not re-walk/re-parse/re-read the tree N times (observed via an
    in-memory call-count seam -- an injected counting parser wrapping the REAL
    `PythonAstAdapter`, and a monkeypatched `Path.read_text` counter -- NEVER
    wall-clock, which is an artifact on a shared/contended box).

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`): today
`_iter_files` on both adapters walks the WHOLE tree unfiltered, and every parser/
read call is a real, uncached call, once per `query()` invocation. Every scenario
below observes this REAL current behaviour and fails with a semantic
`AssertionError` comparing it to this feature's contract -- never a naked
traceback, never a collection-time error (confirmed empirically below).

Driving surface: the walking-skeleton scenario is the ONE subprocess-E2E AT for
the whole feature (F-V5 test-pyramid default) -- it invokes the REAL installed
`des` console-script. Every OTHER scenario drives `AstAdapter` / `TextSearchAdapter`
/ `CodeFactChain` directly IN-PROCESS (Layer 3 composition -- the established
pattern for this exact seam, see
`tests/des/acceptance/coherence_codefact/steps/composition_slice_02_fallback_chain.py:274`
and `composition_coherence_codefact.py:275`).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from des.ports.code_fact_port import CodeFactPort


# --- shared fixtures (git-free -- the in-process adapters walk a plain
# filesystem tree, no git repo needed except for the one subprocess WS) -------


def _write_producer_and_real_caller(repo: Path) -> None:
    """`producer.py` defining `helper()` + a REAL (never-excluded) caller."""
    (repo / "producer.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (repo / "caller_real.py").write_text(
        "from producer import helper\n\n\ndef use():\n    return helper()\n",
        encoding="utf-8",
    )


def _write_caller_in(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        "from producer import helper\n\n\ndef use_vendored():\n    return helper()\n",
        encoding="utf-8",
    )


def _seed_declared_and_undeclared_vendor_dirs(
    tmp_path: Path, declared_vendor_dir_name: str
) -> Path:
    """A repo whose `.gitignore` names ONE vendor dir (`declared_vendor_dir_name`)
    while a DIFFERENT, deliberately UNRELATED vendor-shaped dir (`vendor/`) is
    left undeclared -- proving derivation from the declared file, never a name
    heuristic (Pillar 2: one chained scenario, two embedded assertions)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(f"{declared_vendor_dir_name}/\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    _write_caller_in(repo / declared_vendor_dir_name, "generated_caller.py")
    _write_caller_in(repo / "vendor", "lookalike_caller.py")
    return repo


def _seed_no_ignore_file_with_dotvenv_caller(tmp_path: Path) -> Path:
    """A repo with NO ignore file at all; a `.venv`-named dir holds a caller."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_producer_and_real_caller(repo)
    _write_caller_in(repo / ".venv", "sneaky_caller.py")
    return repo


def _seed_only_excluded_caller(tmp_path: Path, vendor_dir_name: str = "target") -> Path:
    """A repo whose ONLY caller of `helper` lives inside a DECLARED-excluded dir."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(f"{vendor_dir_name}/\n", encoding="utf-8")
    (repo / "producer.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    _write_caller_in(repo / vendor_dir_name, "only_caller.py")
    return repo


def _seed_many_symbols(tmp_path: Path, symbol_count: int) -> Path:
    """A repo with ONE file declaring `symbol_count` distinct top-level
    functions, each with a real caller -- the shape `query.callers-of`,
    queried once per touched symbol, actually drives (mirrors
    `blast_radius_measurement._consumer_counts`)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    producer_lines = "\n".join(
        f"def symbol_{i}():\n    return {i}\n" for i in range(symbol_count)
    )
    (repo / "producer.py").write_text(producer_lines, encoding="utf-8")
    caller_lines = "\n".join(
        f"def use_{i}():\n    return symbol_{i}()\n" for i in range(symbol_count)
    )
    (repo / "caller.py").write_text(
        "from producer import (\n"
        + ",\n".join(f"    symbol_{i}" for i in range(symbol_count))
        + ",\n)\n\n\n"
        + caller_lines,
        encoding="utf-8",
    )
    return repo


def _make_ast_adapter(root: Path) -> CodeFactPort:
    from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter

    return AstAdapter(root=root)


def _make_textsearch_adapter(root: Path) -> CodeFactPort:
    from des.adapters.driven.codefact.text_search_code_fact_adapter import (
        TextSearchAdapter,
    )

    return TextSearchAdapter(root=root)


_BOTH_TIERS = pytest.mark.parametrize(
    "adapter_factory,tier_id",
    [(_make_ast_adapter, "ast"), (_make_textsearch_adapter, "textsearch")],
)


def _callers_descriptor():
    from des.ports.code_fact_port import CAPABILITY_CALLERS_OF, CapabilityDescriptor

    return CapabilityDescriptor(
        id=CAPABILITY_CALLERS_OF,
        stability="stable",
        contract_version="1.0.0",
        io_schema="sites",
        providing_adapter="test-fix-blast-radius-reparses-tree-per-symbol",
    )


def _sites_for(adapter: CodeFactPort, symbol: str) -> list[str]:
    result = adapter.query(_callers_descriptor(), {"symbol": symbol})
    return list(result.payload["sites"])


def _last_json_line(stdout: str) -> dict:
    """Mirrors the `blast_radius_measured_tier` precedent -- `des` prefixes real
    invocations with an unrelated freshness-autoskip event line to skip past."""
    import json

    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    return json.loads(json_lines[-1])


def _consumer_value(consumer_counts: dict[str, object], suffix: str) -> object:
    matches = [v for k, v in consumer_counts.items() if k.endswith(f".{suffix}")]
    assert matches, (
        f"expected a consumer_counts key ending in '.{suffix}', got keys "
        f"{list(consumer_counts)}"
    )
    return matches[0]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


# --- @walking_skeleton -- the ONE subprocess-E2E for the whole feature -------


def test_blast_radius_excludes_declared_vendor_directory_end_to_end(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R7

    A maintainer runs `des blast-radius` against a repo whose `.gitignore`
    declares a Rust-shaped `target/` vendor directory (a name no plausible
    Python-repo hardcoded exclude list would ever carry). A caller living
    inside it must NOT inflate the reported `consumer_counts` -- only the real,
    non-vendored caller counts. A hardcoded `.venv`/`node_modules`/`.git`
    exclude-list "fix" does not know `target/` and would still count 2,
    failing this AT exactly as today's zero-exclusion code does.
    """
    des_binary = shutil.which("des")
    assert des_binary is not None, (
        "the `des` console-script must be on PATH for the feature's single "
        "walking-skeleton subprocess AT to run -- if this fails, the dev "
        "environment install is the problem, not this AT"
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "--local", "core.hooksPath", ".git/hooks")
    (repo / ".gitignore").write_text("target/\n", encoding="utf-8")
    _write_producer_and_real_caller(repo)
    _write_caller_in(repo / "target", "generated_caller.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed producer + real caller + vendor caller")
    with (repo / "producer.py").open("a", encoding="utf-8") as handle:
        handle.write("# touched\n")

    completed = subprocess.run(
        [des_binary, "blast-radius", "--repo", str(repo), "--paths", "producer.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        f"expected a clean measurement, got exit={completed.returncode} "
        f"stderr={completed.stderr!r}"
    )
    payload = _last_json_line(completed.stdout)
    assert payload["event"] == "BlastRadiusMeasured"
    consumer_counts = payload["measures"]["consumer_counts"]
    assert _consumer_value(consumer_counts, "helper") == 1, (
        "only caller_real.py's call may be counted -- the target/ vendor "
        "caller, declared excluded via .gitignore, must NOT inflate the "
        "count. A hardcoded exclude-list fix (.venv/node_modules/.git) does "
        f"not know 'target/' and would count 2. got {consumer_counts!r}"
    )


# --- the property: derived-from-declared-ignore-file, not name-guessed ------


@_BOTH_TIERS
@pytest.mark.parametrize("declared_vendor_dir_name", ["target", "_build", "out"])
def test_declared_vendor_dir_excluded_undeclared_lookalike_stays_walked(
    tmp_path: Path, adapter_factory, tier_id: str, declared_vendor_dir_name: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R1, R2, R4

    THE central property, not an instance: a directory declared in the target's
    OWN `.gitignore` (`declared_vendor_dir_name`, parametrized over three names
    -- Rust `target/`, OCaml/Dune `_build/`, Next.js `out/` -- none of which
    exist in any hardcoded Python-repo exclude list) is excluded from the tree
    walk at BOTH the AST and TextSearch floor tiers, while a DIFFERENT,
    deliberately UNDECLARED vendor-shaped sibling directory (`vendor/`, present
    in the SAME repo but named nowhere in `.gitignore`) stays walked -- proving
    the exclusion reads the DECLARED file, never a disguised name-heuristic (the
    same disease as `EXCLUDED_SEARCH_DIRS`/master-hardcoded, in a new outfit).
    """
    repo = _seed_declared_and_undeclared_vendor_dirs(tmp_path, declared_vendor_dir_name)
    adapter = adapter_factory(repo)

    sites = _sites_for(adapter, "helper")

    assert any("caller_real.py" in site for site in sites), (
        f"the real, non-vendored caller must always be found ({tier_id} tier)"
    )
    assert not any(declared_vendor_dir_name in site for site in sites), (
        f"a directory DECLARED excluded via .gitignore ('{declared_vendor_dir_name}/') "
        f"must not appear in the {tier_id}-tier call sites -- a hardcoded "
        f"exclude list (.venv/node_modules/.git) does not know this name and "
        f"would still include it. got {sites!r}"
    )
    assert any("vendor" in site and "lookalike_caller.py" in site for site in sites), (
        f"'vendor/' is a common vendor-dir NAME but is NOT declared in "
        f".gitignore (only '{declared_vendor_dir_name}/' is) -- the {tier_id} "
        f"tier must still walk it. Excluding it anyway would prove the fix "
        f"guesses names instead of reading the declared ignore file (the "
        f"exact hardcoded-list disease in a disguise). got {sites!r}"
    )


# --- the negative oracle: absent ignore file never narrows the walk --------


def test_absent_ignore_file_walks_everything_and_signals_loud(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R3 -- MANDATORY NEGATIVE (GDP-6: never a silent narrower scan)

    With NO ignore file present at all, the walk must include EVERYTHING it
    always did -- a `.venv`-named directory (today's de-facto scanned reality)
    stays scanned; the fix must never silently apply a default exclude list
    that was never configured. AND the answer must be accompanied by a LOUD
    `CodeFactChain.health_events()` signal naming the unfiltered condition, so
    a caller can tell "no filtering was possible" apart from "filtering ran
    and excluded nothing" -- both look identical in the raw `sites` list alone.
    """
    from des.adapters.driven.codefact.code_fact_chain import CodeFactChain

    repo = _seed_no_ignore_file_with_dotvenv_caller(tmp_path)
    chain = CodeFactChain(root=repo, tsunami_present=False)

    result = chain.query(_callers_descriptor(), {"symbol": "helper"})

    assert result is not None
    sites = list(result.payload["sites"])
    assert any(".venv" in site for site in sites), (
        "with NO ignore file present, today's unfiltered walk must be "
        f"preserved -- a .venv-named dir must still be scanned when nothing "
        f"declares it excluded. got {sites!r}"
    )
    events = chain.health_events()
    assert any(
        "unfiltered" in event.lower() or "no-ignore" in event.lower()
        for event in events
    ), (
        "an unfiltered scan (no ignore file present) must emit a LOUD "
        "health_events() signal naming the no-ignore-file condition (the "
        "health.gate.code-fact.* family) -- never a silent full walk that "
        f"looks identical to a filtered-and-found-nothing one. got {events!r}"
    )


def test_symbol_with_only_excluded_consumer_is_never_a_silent_verified_zero(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R5 -- MANDATORY NEGATIVE (the dangerous direction: a false S).

    A symbol whose ONLY caller lives inside a DECLARED-excluded directory must
    never be reported as an unqualified, confident "0 call sites" -- that is
    indistinguishable from a genuinely verified zero-callers answer, and a
    downstream consumer (`blast_radius_measurement`) would silently under-report
    the blast radius as S when it might be far larger. Whenever the underlying
    walk excluded at least one path, the SAME `health_events()` "filtered"
    signal `test_absent_ignore_file_walks_everything_and_signals_loud` proves
    for the unfiltered case must ALSO fire here for the filtered case -- the
    two are one signal family, not two independent ones (errors degrade toward
    L, per GDP-6, never silently toward a smaller S).
    """
    from des.adapters.driven.codefact.code_fact_chain import CodeFactChain

    repo = _seed_only_excluded_caller(tmp_path)
    chain = CodeFactChain(root=repo, tsunami_present=False)

    result = chain.query(_callers_descriptor(), {"symbol": "helper"})

    assert result is not None
    sites = list(result.payload["sites"])
    assert sites == [], (
        f"the declared-excluded vendor-dir caller must not appear in the "
        f"answer. got {sites!r}"
    )
    events = chain.health_events()
    assert any("filter" in event.lower() for event in events), (
        "a scan that excluded at least one path must emit a LOUD 'filtered' "
        "health_events() signal -- a bare empty `sites` list here is "
        "otherwise indistinguishable from a genuinely verified zero-callers "
        "answer, which is the exact dangerous silent-narrowing (a false S) "
        f"this AT guards against. got {events!r}"
    )


# --- the cost property: N symbol queries do not cost N tree passes ---------


def test_ast_tier_callers_of_query_does_not_reparse_the_tree_per_symbol(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R6

    Querying `query.callers-of` for 5 DISTINCT symbols over the SAME
    `AstAdapter` instance must not re-parse the tree 5 times -- the measured
    defect (`ast_code_fact_adapter.py:378-393`, `_call_sites` re-derives
    `_iter_files()` + `_parse()` for every file on EVERY symbol query). Asserted
    via an in-memory CALL-COUNT seam (an injected counting proxy wrapping the
    REAL `PythonAstAdapter` -- never a stub that fakes parse results, only
    counts real calls), NEVER wall-clock (a timing assertion on a shared,
    contended box is an artifact, not a fact --
    `[[feedback_test_speed_measure_only_in_clean_worktree_contention_is_the_artifact_2026_07_15]]`).
    """
    from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
    from des.testarch.adapters.python_ast import PythonAstAdapter

    class _CountingParser:
        def __init__(self) -> None:
            self._real = PythonAstAdapter()
            self.parse_call_count = 0

        def parse(self, source: str, filename: str) -> object:
            self.parse_call_count += 1
            return self._real.parse(source, filename)

        def __getattr__(self, name: str) -> object:
            return getattr(self._real, name)

    symbol_count = 5
    repo = _seed_many_symbols(tmp_path, symbol_count)
    counting_parser = _CountingParser()
    adapter = AstAdapter(root=repo, parser=counting_parser)

    for i in range(symbol_count):
        adapter.query(_callers_descriptor(), {"symbol": f"symbol_{i}"})

    file_count = sum(1 for _ in repo.rglob("*.py"))
    assert counting_parser.parse_call_count < file_count * symbol_count, (
        f"{symbol_count} distinct symbol queries over a {file_count}-file tree "
        f"parsed {counting_parser.parse_call_count} times -- the current "
        f"defect re-parses the WHOLE tree on every symbol query "
        f"({file_count * symbol_count} calls expected under it); the fix must "
        f"cost O(files), not O(files x symbols). A single-pass-then-cache "
        f"implementation would parse exactly {file_count} times."
    )


def test_textsearch_tier_callers_of_query_does_not_reread_the_tree_per_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R6

    The TextSearch/grep floor tier carries the IDENTICAL defect on an even
    WIDER glob (`text_search_code_fact_adapter.py:196-202`, `_SOURCE_GLOB =
    "*.*"`). Querying `query.callers-of` for 5 distinct symbols over the SAME
    `TextSearchAdapter` instance must not re-read the tree 5 times -- asserted
    via a monkeypatched `Path.read_text` CALL-COUNT seam (the read still
    returns the REAL file content; only the invocation count is intercepted),
    never wall-clock.
    """
    from des.adapters.driven.codefact.text_search_code_fact_adapter import (
        TextSearchAdapter,
    )

    symbol_count = 5
    repo = _seed_many_symbols(tmp_path, symbol_count)
    adapter = TextSearchAdapter(root=repo)

    read_call_count = 0
    real_read_text = Path.read_text

    def _counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        nonlocal read_call_count
        read_call_count += 1
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    for i in range(symbol_count):
        adapter.query(_callers_descriptor(), {"symbol": f"symbol_{i}"})

    file_count = sum(1 for _ in repo.rglob("*.*") if _.is_file())
    assert read_call_count < file_count * symbol_count, (
        f"{symbol_count} distinct symbol queries over a {file_count}-file tree "
        f"read files {read_call_count} times -- the current defect re-reads "
        f"the WHOLE tree on every symbol query ({file_count * symbol_count} "
        f"calls expected under it); the fix must cost O(files), not "
        f"O(files x symbols). A single-pass-then-cache implementation would "
        f"read exactly {file_count} times."
    )
