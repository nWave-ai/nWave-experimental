"""Acceptance tests -- `des blast-radius` classifier completeness (DISTILL, slice-02).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Slice Plan slice-02 row, [REF] Architecture & Contract Tests --
  Tier classification table + Config surface + Floor/ceiling validation).

Slice-02 value (Slice Plan): the tier classifier is COMPLETE -- `boundary_files`
detection (configurable globs), `consumer_counts` resolution via `CodeFactPort`
(degrading a genuinely-unparseable touched file to `null`, never a fabricated
0), the full S/M/L decision table, the `--staged`/`--diff <ref>` input modes,
and thresholds read from the `.nwave/des-config.json` `blast_radius` block via
the `DESConfig` cascade (falling back to canonical defaults when absent, HARD
FAILING loud when a present well-typed value is outside its floor/ceiling).

TEST-PYRAMID CONSTRAINT (Ale-ratified 2026-07-18, F-V5): the feature's ONE
`@walking_skeleton` subprocess-E2E is ALREADY SPENT on slice-01
(`test_blast_radius_slice01_walking_skeleton.py`). This module authors ZERO
new subprocess/E2E scenarios -- every scenario below drives
`des.cli.blast_radius.main(argv)` IN-PROCESS (`_invoke_in_process`, reused
from the slice-01 module via import -- Test Reuse & Consolidation Analysis).

Contract under test (DOES NOT EXIST YET at slice-01 HEAD -- active-RED by
design): `src/des/cli/blast_radius.py::main(argv)` extended with `--staged` /
`--diff <ref>` input modes; `src/des/application/blast_radius_measurement.py`
extended to resolve `boundary_files` / `consumer_counts` via `CodeFactChain`
and to read thresholds from `DESConfig`; `src/des/domain/blast_radius.py`
`classify_tier` extended to the full closed S/M/L table over
`BlastRadiusThresholds` (`small_max_consumers`, `large_min_consumers`,
`boundary_globs`).

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`): the
slice-01 shipped `classify_tier`/`measure_blast_radius`/CLI accept ONLY the
reduced files+lines rule and the `--paths` mode. Every scenario below drives
a code path (a new CLI flag, a `boundary_files`/`consumer_counts` measure, a
`DESConfig` threshold read) that does not exist yet, so each test fails with a
semantic `AssertionError` (an unexpected `TypeError`/`SystemExit` surfaced as
a `pytest.raises` mismatch, or a JSON payload missing the expected key/value)
comparing the REAL current (reduced) behaviour to the slice-02 contract --
never a naked traceback, never a collection-time error.

===========================================================================
DISTILL-PINNED CONTRACT ADDITIONS (unspecified by the feature-delta -- DISTILL's
own design decisions, since nothing exists yet to reverse-engineer; DELIVER
matches these, or raises the discrepancy back to DISTILL/DESIGN if it disagrees):
===========================================================================

D1 -- `consumer_counts` key format: `"<module-stem>.<symbol-name>"` (e.g. a
     touched `producer.py` defining `def helper(): ...` keys as
     `"producer.helper"`). The feature-delta's own docstring in
     `blast_radius.py` promises `"<qualified-symbol>"` without fixing the
     exact join; this pins the dotted module-relative form.
D2 -- an unparseable touched file (syntax error) cannot yield a symbol name at
     all, so its `consumer_counts` entry keys on the file's REPO-RELATIVE PATH
     (e.g. `"broken.py"`), value `null`.
D3 -- the CLI resolves `DESConfig(cwd=Path(args.repo))`, so
     `.nwave/des-config.json` lives under the MEASURED `--repo` root (not the
     orchestrator's cwd) -- consistent with every other measure already being
     scoped to that tree.
D4 -- a present, well-typed, out-of-range threshold HARD-FAILS with event
     `BlastRadiusConfigRejected` (mirrors `BlastRadiusInputRejected`'s shape),
     exit 2, naming the offending key/value/valid-range in `reasons` (GDP-3).
     `boundary_globs` on TYPE failure (a non-string entry) falls back to the
     default list silently (feature-delta: type-only validation for globs).
D5 -- `boundary_globs` in config REPLACES the default list wholesale (does not
     merge/append) -- consistent with every other `blast_radius` key being a
     full per-key override, never an accumulation.
D6 -- **RESOLVED 2026-07-18 (was a flagged SSOT ambiguity, no longer live):**
     the feature-delta's closed decision table (Architecture & Contract Tests,
     "L" row) originally stated `any consumer_counts value > large_min_consumers`
     (STRICT greater-than), while its own "Canonical default thresholds"
     rationale row for `large_min_consumers` stated "the M band exists between
     them, 4-9 consumers" and "10+ call sites is the point ... warranted"
     (implying `>= large_min_consumers` triggers L). With
     `large_min_consumers=10` these two SSOT passages contradicted each other.
     DISTILL flagged the contradiction instead of silently resolving it; the
     team lead reconciled it: `>=` is authoritative -- the key's OWN NAME
     settles it (`large_min_consumers` = "the MINIMUM count that counts as
     large", so 10 itself is large), and two passages (the name + the
     rationale prose) agreed against the one that didn't (the table's
     comparator, which was the actual typo). The feature-delta's closed table
     now reads `any consumer_counts value >= large_min_consumers`. This
     module pins that reading: EXACTLY `large_min_consumers` (10) callers is
     L (`test_consumer_count_at_large_min_consumers_boundary_value_is_large`),
     with an unambiguous anchor at 11 callers
     (`test_consumer_count_strictly_above_large_min_consumers_is_unambiguously_large`).

CLI GRAMMAR CONTRACT (extends slice-01's `des blast-radius --repo <path>
--paths <f1> ...` grammar; MUST remain byte-compatible with the shipped,
sealed slice-01 AT `test_blast_radius_requires_a_paths_argument`, which
asserts `"paths" in stderr.lower()` on a zero-input-mode invocation -- so the
"exactly one input mode" usage error MUST still mention "paths"):

    des blast-radius --repo <path> [--paths <f1> [<f2> ...] | --staged | --diff <ref>]

Exactly one of `--paths` / `--staged` / `--diff <ref>` is required; passing
zero or more than one is a `BlastRadiusInputRejected`-shaped usage error
(exit 2, mentioning "paths" per the compatibility constraint above).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.des.acceptance.blast_radius_measured_tier.test_blast_radius_slice01_walking_skeleton import (
    _git,
    _init_git_repo,
    _invoke_in_process,
)


# Canonical default thresholds (feature-delta "Canonical default thresholds"
# table) -- slice-02's full decision table reads these five keys.
SMALL_MAX_FILES = 2
SMALL_MAX_LINES = 10
SMALL_MAX_CONSUMERS = 3
LARGE_MIN_CONSUMERS = 10
DEFAULT_BOUNDARY_GLOBS = (
    "**/ports/**",
    "**/adapters/**",
    "**/schemas/**",
    "**/*.schema.json",
    "**/*.proto",
)

# Floor/ceiling sane-range table (feature-delta "Floor/ceiling validation").
_RANGE_TABLE: dict[str, tuple[int, int]] = {
    "small_max_files": (1, 20),
    "small_max_lines": (1, 500),
    "small_max_consumers": (1, 50),
    # floor is `small_max_consumers + 1` at the CANONICAL default (3); ceiling 1000.
    "large_min_consumers": (SMALL_MAX_CONSUMERS + 1, 1000),
}


# --- local helpers (D1-D5 fixture builders; slice-01's git/CLI helpers reused) --


def _write_config(repo: Path, blast_radius: dict[str, object]) -> None:
    """Write `.nwave/des-config.json` with a `blast_radius` block (D3: rooted
    at the measured `--repo`, not the orchestrator cwd)."""
    config_dir = repo / ".nwave"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "des-config.json").write_text(
        json.dumps({"blast_radius": blast_radius}), encoding="utf-8"
    )


def _seed_producer_with_callers(
    repo: Path, module_name: str, symbol: str, caller_count: int
) -> Path:
    """Commit a `<module_name>.py` defining `symbol` + `caller_count` distinct
    caller files (each a genuine external call-site, D1 key = `module.symbol`).
    Returns the producer's path (NOT yet touched -- caller decides how)."""
    producer_path = repo / f"{module_name}.py"
    producer_path.write_text(f"def {symbol}():\n    return 1\n", encoding="utf-8")
    for i in range(caller_count):
        (repo / f"caller_{i}.py").write_text(
            f"from {module_name} import {symbol}\n\n\n"
            f"def use_{i}():\n    return {symbol}()\n",
            encoding="utf-8",
        )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed producer + callers")
    return producer_path


def _touch(path: Path, extra: str = "# touched\n") -> None:
    """An uncommitted, trivially small edit -- puts `path` in the change scope."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(extra)


def _seed_producer_with_calls_in_one_file(
    repo: Path, module_name: str, symbol: str, call_count: int
) -> Path:
    """Commit a `<module_name>.py` defining `symbol` + ONE caller file making
    `call_count` DISTINCT calls to it.

    The deliberate inverse of `_seed_producer_with_callers` (which generates
    exactly ONE call per generated caller FILE, so file-count and call-site
    count coincide by construction in every other consumer-count AT -- the
    blind spot the D1 blocker lived in). Here the two diverge maximally:
    1 file, `call_count` call sites.
    """
    producer_path = repo / f"{module_name}.py"
    producer_path.write_text(f"def {symbol}():\n    return 1\n", encoding="utf-8")
    call_lines = "\n".join(
        f"def use_{i}():\n    return {symbol}()\n" for i in range(call_count)
    )
    (repo / "single_caller.py").write_text(
        f"from {module_name} import {symbol}\n\n\n{call_lines}",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed producer + one multi-call caller")
    return producer_path


def _consumer_value(consumer_counts: dict[str, object], suffix: str) -> object:
    """The single `consumer_counts` value whose key ends with `.{suffix}` (D1) --
    tolerant of the exact module-stem DELIVER computes, pinned only on the
    trailing symbol name."""
    matches = [v for k, v in consumer_counts.items() if k.endswith(f".{suffix}")]
    assert matches, (
        f"expected a consumer_counts key ending in '.{suffix}', got keys "
        f"{list(consumer_counts)}"
    )
    return matches[0]


# --- (a) boundary_files detection (configurable globs) --------------------


@pytest.mark.parametrize(
    "boundary_rel_path",
    [
        "src/ports/foo.py",
        "src/adapters/bar.py",
        "schemas/thing.py",
        "contracts/wire.schema.json",
        "proto/svc.proto",
    ],
)
def test_touching_a_default_boundary_glob_forces_large_tier_even_when_tiny(
    tmp_path: Path, capsys, boundary_rel_path: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: a

    A change under any DEFAULT boundary glob (`**/ports/**`, `**/adapters/**`,
    `**/schemas/**`, `**/*.schema.json`, `**/*.proto`) is ALWAYS L-tier -- even
    a 1-file, 1-line edit that would otherwise be S. The blast-radius the
    boundary crosses is never a size question.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / boundary_rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed boundary file")
    _touch(target, "y = 2\n")

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", boundary_rel_path], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["tier"] == "L", (
        f"a tiny (1 file, 1 line) boundary-glob touch must classify L, not "
        f"the fabricated-small verdict this feature exists to prevent -- got "
        f"{payload['tier']!r}"
    )
    assert payload["measures"]["files"] == 1
    assert payload["measures"]["lines_changed"] == 1
    assert payload["measures"]["boundary_files"] == [boundary_rel_path]
    assert any(boundary_rel_path in reason for reason in payload["reasons"]), (
        "the boundary-crossing reason must name the specific path, not a bare tier"
    )


def test_a_file_outside_every_boundary_glob_never_triggers_boundary_escalation(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: a

    A tiny, non-boundary file touch reports an EMPTY `boundary_files` list --
    the negative counterpart to the parametrized boundary case above. Also
    pins that `consumer_counts` is a REAL (non-vacuous) measurement even at
    zero callers -- an absent key here would be indistinguishable from "never
    computed" (the exact ambiguity D2/obligation (b) forbids).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    plain = repo / "plain_module.py"
    plain.write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed plain module")
    _touch(plain)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "plain_module.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["measures"]["boundary_files"] == []
    assert _consumer_value(payload["measures"]["consumer_counts"], "f") == 0, (
        "a touched symbol with zero external callers must still be a REAL "
        "measured 0 in consumer_counts, not an absent key (indistinguishable "
        "from 'never computed')"
    )
    assert payload["tier"] == "S"


def test_boundary_globs_are_configurable_and_replace_the_default_list(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: a, d

    D5: a project's `.nwave/des-config.json` `blast_radius.boundary_globs`
    REPLACES the default list -- a path matching a DEFAULT glob
    (`**/ports/**`) is NOT flagged once a custom list is configured, while a
    path matching the CUSTOM glob IS flagged.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"boundary_globs": ["**/custom_boundary/**"]})

    default_glob_path = repo / "src" / "ports" / "old_default.py"
    default_glob_path.parent.mkdir(parents=True, exist_ok=True)
    default_glob_path.write_text("x = 1\n", encoding="utf-8")
    custom_glob_path = repo / "custom_boundary" / "thing.py"
    custom_glob_path.parent.mkdir(parents=True, exist_ok=True)
    custom_glob_path.write_text("y = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed both boundary candidates")
    _touch(default_glob_path)
    _touch(custom_glob_path)

    exit_code, _stderr, payload = _invoke_in_process(
        repo,
        [
            "--repo",
            str(repo),
            "--paths",
            "src/ports/old_default.py",
            "custom_boundary/thing.py",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["measures"]["boundary_files"] == ["custom_boundary/thing.py"], (
        "the configured list REPLACES the default -- the old-default-glob path "
        "must NOT appear once a custom boundary_globs list is configured"
    )
    assert payload["tier"] == "L"


# --- (b) consumer_counts via CodeFactPort (query.callers-of) --------------


def test_consumer_count_resolves_the_real_number_of_call_sites(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c

    A touched symbol called from exactly `SMALL_MAX_CONSUMERS` (3) distinct
    files resolves `consumer_counts` to 3 via the REAL `CodeFactPort`
    (`query.callers-of`) chain -- never a fabricated/guessed number -- and
    stays S (every other axis small).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    producer = _seed_producer_with_callers(
        repo, "producer", "helper", caller_count=SMALL_MAX_CONSUMERS
    )
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    consumer_counts = payload["measures"]["consumer_counts"]
    assert _consumer_value(consumer_counts, "helper") == SMALL_MAX_CONSUMERS
    assert payload["tier"] == "S"


def test_consumer_count_at_large_min_consumers_boundary_value_is_large(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c

    D6 -- HISTORICAL NOTE (resolved 2026-07-18, not a live ambiguity): the
    feature-delta's closed decision table originally read `consumer_counts
    value > large_min_consumers` (strict), while the "Canonical default
    thresholds" rationale row for the same key said "the M band exists
    between them, 4-9 consumers" / "10+ call sites is the point... warranted"
    -- the two passages disagreed on whether EXACTLY 10 callers is M or L.
    DISTILL flagged the contradiction rather than silently picking a side;
    the team lead reconciled it: `>=` is authoritative, NOT `>` (the key's
    OWN NAME settles it -- `large_min_consumers` means "the MINIMUM count
    that counts as large", so 10 itself is large; the comparator in the
    original table text was the typo, not the rationale prose). The
    feature-delta's closed table now reads `consumer_counts value >=
    large_min_consumers`. This test pins that reading: EXACTLY
    `LARGE_MIN_CONSUMERS` (10) callers is L, not M.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    producer = _seed_producer_with_callers(
        repo, "producer", "helper", caller_count=LARGE_MIN_CONSUMERS
    )
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    consumer_counts = payload["measures"]["consumer_counts"]
    assert _consumer_value(consumer_counts, "helper") == LARGE_MIN_CONSUMERS
    assert payload["tier"] == "L", (
        "pinned to the now-canonical '>= large_min_consumers' formula (D6, "
        "reconciled 2026-07-18) -- exactly 10 callers IS '>= 10', so this is "
        "L, not the M/L boundary value it used to be under the retired "
        "strict-'>' reading"
    )


def test_consumer_count_strictly_above_large_min_consumers_is_unambiguously_large(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c

    11 callers is `> large_min_consumers` (10) under EITHER reading of the D6
    ambiguity -- the unambiguous L-tier anchor.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    producer = _seed_producer_with_callers(
        repo, "producer", "helper", caller_count=LARGE_MIN_CONSUMERS + 1
    )
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["tier"] == "L"
    assert any(
        "large_min_consumers" in reason or "consumer" in reason.lower()
        for reason in payload["reasons"]
    )


def test_untouched_unparseable_file_elsewhere_degrades_a_zero_consumer_count_to_null(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- MANDATORY NEGATIVE, ADR-LA-001 D9 slice (h)/D6-R14, LA1-L11

    A ZERO `consumer_counts` entry is a "verified zero" only when the
    repo-wide `query.callers-of` scan that produced it hit NO fault and NO
    scope degradation (LA1-L11 -- the `Resolution.trace` must be inspected,
    never the payload's `sites` list alone). The touched file's own symbol
    has genuinely zero callers, but an UNRELATED, UNTOUCHED file elsewhere in
    the repo cannot be parsed -- the repo-wide scan for callers therefore did
    NOT fully observe the tree, so a `0` here would be indistinguishable from
    a genuine verified zero (the exact silent-false-S this feature exists to
    prevent, sister of `fix_blast_radius_reparses_tree_per_symbol`'s
    `test_symbol_with_only_excluded_consumer_is_never_a_silent_verified_zero`).
    `consumer_counts` must report `null`, escalating to L, never a fabricated
    `0`.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    plain = repo / "plain_module.py"
    plain.write_text("def f():\n    return 1\n", encoding="utf-8")
    (repo / "broken_elsewhere.py").write_text(
        "def broken(:\n    pass\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed plain module + an unrelated broken file")
    _touch(plain)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "plain_module.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    consumer_counts = payload["measures"]["consumer_counts"]
    assert _consumer_value(consumer_counts, "f") is None, (
        "the repo-wide callers-of scan for `f` could not fully observe the "
        "tree (an unrelated file elsewhere is unparseable) -- a `0` reads as "
        "a verified zero it is not (LA1-L11); got "
        f"{_consumer_value(consumer_counts, 'f')!r} in {consumer_counts!r}"
    )
    assert payload["tier"] == "L", (
        "a null consumer_counts value must escalate to L, never resolve S/M"
    )


def test_unparseable_touched_file_degrades_consumer_count_to_null_never_zero(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- MANDATORY NEGATIVE (the exact vacuous-truth footgun this
    slice exists to prevent)

    A touched Python file with a genuine syntax error cannot be parsed, so its
    symbol(s) cannot be extracted -- `consumer_counts` must report `null`
    (D2: keyed on the file's repo-relative path) rather than a fabricated `0`
    (which would silently under-report the blast radius). `null` in
    `consumer_counts` escalates the tier to L (an unknown blast radius is the
    worst case, never silently smaller -- GDP-6), same rule as slice-01's
    `lines_changed is None` escalation.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    broken = repo / "broken.py"
    broken.write_text("def broken(:\n    pass\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed unparseable file")

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "broken.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    consumer_counts = payload["measures"]["consumer_counts"]
    assert consumer_counts, "an unparseable touched file must still yield an entry"
    assert None in consumer_counts.values(), (
        f"expected a null consumer_counts value for the unparseable file, got "
        f"{consumer_counts!r} -- a fabricated 0 is the exact footgun this AT guards"
    )
    assert payload["tier"] == "L", (
        "a null consumer_counts value must escalate to L, never resolve S/M"
    )
    assert any(
        "broken.py" in reason
        and ("pars" in reason.lower() or "indeterminate" in reason.lower())
        for reason in payload["reasons"]
    ), "the degrade cause (unparseable file) must be named, not silent"


def test_multiple_calls_within_one_file_count_as_multiple_call_sites(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c -- MANDATORY NEGATIVE (feature-end deep-review BLOCKER D1)

    `consumer_counts` must count CALL SITES, not FILES-containing-a-call. The
    feature-delta names the measure "the number of distinct call SITES
    resolved via the `CodeFactPort`" (Architecture & Contract Tests,
    `consumer_counts` bullet), and the `small_max_consumers` rationale row
    reads "A symbol with <=3 call SITES can be re-verified by reading all of
    them" -- the safety property is about how much a reviewer must hold in
    their head, which a second call in the same file adds to just as much as
    a call in a new file.

    WHY THE 49-AT CORPUS MISSED THIS: `_seed_producer_with_callers` emits
    exactly ONE call per generated caller file, ALWAYS -- so file-count and
    call-site-count coincide by construction in every pre-existing
    consumer-count AT, and a `len(files-with-a-call)` implementation is
    indistinguishable from a `len(call-sites)` one. This fixture
    (`_seed_producer_with_calls_in_one_file`) is the first to separate them.

    DISCRIMINATING BY CONSTRUCTION: `SMALL_MAX_CONSUMERS + 1` (4) calls from
    ONE file. Counting call sites -> 4 > 3 -> M. Counting files -> 1 <= 3 ->
    S. The tier assertion alone catches the defect even if the raw count
    assertion were ever relaxed.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    call_count = SMALL_MAX_CONSUMERS + 1
    producer = _seed_producer_with_calls_in_one_file(
        repo, "producer", "helper", call_count=call_count
    )
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    consumer_counts = payload["measures"]["consumer_counts"]
    assert _consumer_value(consumer_counts, "helper") == call_count, (
        f"{call_count} distinct calls to `helper` from a SINGLE file must "
        f"measure {call_count} call SITES, not 1 file-with-a-call -- counting "
        "files silently under-reports the blast radius by an unbounded factor "
        "(a symbol called 15 times from one file would measure 1 -> tier S)"
    )
    assert payload["tier"] == "M", (
        f"{call_count} call sites exceeds small_max_consumers="
        f"{SMALL_MAX_CONSUMERS}, so this is M -- a file-counting "
        "implementation measures 1 consumer and reports the fabricated-small "
        "S verdict this feature exists to prevent"
    )


def test_staged_deletion_of_a_called_symbol_is_never_silently_invisible(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c2 -- MANDATORY NEGATIVE (feature-end deep-review BLOCKER D2)

    A staged DELETION of a `.py` file whose symbol has known external callers
    must NEVER measure as touching nothing. Deleting a widely-called function
    is among the largest blast radii a change can have -- it breaks every
    caller -- so an input mode that reports zero `consumer_counts` entries for
    it inverts the measure exactly where it matters most.

    WHY THE 49-AT CORPUS MISSED THIS: the whole corpus never seeds a DELETED
    path in any scope -- the "D" leg of CRUD is absent from every fixture.
    Every scope builder either creates or edits; none removes.

    WHAT THE DESIGN DEMANDS: the feature-delta does not name deletion
    explicitly, so this AT asserts the SAFE side per the feature's OWN
    stated discipline -- "a `null` consumer count ... escalates the tier to
    `L` (unknown blast radius is treated as the WORST case, never silently
    smaller)" (Architecture & Contract Tests) and GDP-6. A deleted file
    cannot be parsed, so its symbols cannot be enumerated: `null` (keyed on
    the repo-relative path, D2) escalating to L is the honest answer. What is
    NOT acceptable is the current behaviour -- NO entry at all, neither
    measured nor flagged, because `Path.rglob()` on a nonexistent root
    silently yields `[]` rather than raising. If DELIVER can genuinely resolve
    the deleted symbol's callers from the pre-deletion revision and report a
    REAL count, that is strictly better than `null` and this assertion should
    be revisited upward -- but it must never resolve to silence.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _seed_producer_with_callers(
        repo, "producer", "helper", caller_count=SMALL_MAX_CONSUMERS
    )
    _git(repo, "rm", "-q", "producer.py")

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--staged"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["files"] == 1, (
        "the deleted path is in the staged scope -- `git diff --cached "
        "--numstat` lists it, so `files` sees it even today"
    )
    consumer_counts = payload["measures"]["consumer_counts"]
    assert consumer_counts, (
        "a staged DELETION of a .py file must yield a consumer_counts entry -- "
        "today `Path.rglob()` on the deleted (nonexistent) path silently "
        "yields [], so the file is neither measured NOR flagged unparseable "
        "and gets NO entry at all: deleting a widely-called function measures "
        "as touching nothing"
    )
    assert None in consumer_counts.values(), (
        f"the deleted file cannot be parsed, so its consumer count is honestly "
        f"INDETERMINATE (`null`, keyed on the repo-relative path per D2) -- "
        f"never a fabricated 0 and never an absent key, got {consumer_counts!r}"
    )
    assert payload["tier"] == "L", (
        "an indeterminate (null) consumer count escalates to L under the "
        "feature's own 'unknown blast radius is the WORST case, never "
        "silently smaller' rule (GDP-6) -- the same escalation the "
        "unparseable-file AT already pins"
    )


# --- (c) the full closed S/M/L decision table ------------------------------


def test_medium_tier_from_consumer_count_alone_all_other_axes_small(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: c

    A consumer count strictly between `small_max_consumers` (3) and
    `large_min_consumers` (10) -- e.g. 5 -- with every other axis small (1
    file, tiny diff, no boundary) is M, not S and not L: the closed table's
    genuine middle band.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    producer = _seed_producer_with_callers(repo, "producer", "helper", caller_count=5)
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["measures"]["files"] == 1
    assert payload["measures"]["boundary_files"] == []
    assert payload["tier"] == "M"


# --- (c2) --staged and --diff <ref> input modes ----------------------------


def test_staged_mode_measures_only_the_staged_scope(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: c2

    `--staged` measures `git diff --cached --numstat` -- a file staged via
    `git add` is IN scope; a separately-modified-but-NOT-staged file is
    excluded, even though it also differs from HEAD.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    staged_file = repo / "module_a.py"
    unstaged_file = repo / "module_b.py"
    with staged_file.open("a", encoding="utf-8") as handle:
        handle.write("def a2():\n    return 2\n")
    _git(repo, "add", "module_a.py")
    with unstaged_file.open("a", encoding="utf-8") as handle:
        handle.write("def b2():\n    return 3\n")
    # module_b.py deliberately NOT staged.

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--staged"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["files"] == 1
    assert payload["measures"]["lines_changed"] == 2


def test_diff_ref_mode_measures_the_scope_since_the_named_ref(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: c2

    `--diff <ref>` measures `git diff <ref> --numstat` -- a fully-committed
    change made AFTER the named ref is in scope even with a clean working
    tree (no staged/unstaged changes at invocation time).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _git(repo, "tag", "before-change")
    target = repo / "module_a.py"
    with target.open("a", encoding="utf-8") as handle:
        handle.write("def a2():\n    return 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "committed change after the tag")

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--diff", "before-change"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["files"] == 1
    assert payload["measures"]["lines_changed"] == 2


def test_every_input_mode_scopes_consumer_counts_to_the_whole_touched_file(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: c2 -- the CORRECTED per-mode symbol-scope rule (see below)

    `--paths`, `--staged` and `--diff <ref>` ALL scope `consumer_counts` to
    every top-level symbol the touched file declares. There is no per-mode
    difference: the conservative whole-file rule is universal.

    A two-function file where only ONE function's body is edited (staged):
    BOTH modes report `consumer_counts` for BOTH functions -- the untouched
    `beta` included, because the file it lives in is in the change scope.

    ===================================================================
    WHY THE DOCUMENTED HUNK-SCOPING RULE WAS RETIRED (2026-07-18)
    ===================================================================

    The feature-delta ("Symbol scope per input mode") originally declared
    that `--staged`/`--diff` scope to the symbols the diff HUNK touches,
    while `--paths` -- having no diff baseline -- scopes to the whole file.
    It called the `--paths` coarseness DELIBERATE and grounded it in a named
    safety argument: the conservative bias for `commit-slice --tier`'s
    pre-flight use, "over-counting toward a higher tier is the safe failure
    direction -- never under-counting toward a false S".

    That rationale is right, and following it one step further is what
    retires the rule it was written to justify. `commit-slice --tier` with
    `--all` measures via `staged=True` (`commit_slice.py`
    `_check_blast_radius_tier` -> `measure_blast_radius(repo, staged=True)`).
    So the STAGED path is the ENFORCEMENT path -- the one the cap actually
    runs on -- while `--paths`/`--diff` are predominantly INSPECTION. The
    original rule therefore applied the conservative bias to the inspection
    mode and WITHHELD it from the enforcement mode: implementing hunk-scoping
    as documented would make the enforcement path measure FEWER symbols, i.e.
    a safety control becoming LESS conservative by design. For a mechanism
    whose entire purpose is "never under-measure toward a false S" that is
    the wrong direction -- and the 2026-07-18 feature-end deep review already
    found three separate under-measurement paths (call-sites counted as
    files; deleted files measuring as nothing; a deleted path crashing the
    cap). A fourth, deliberate one is not being added.

    DECISION (team lead, 2026-07-18): all modes scope to the whole file. The
    feature-delta is the artifact that gets corrected, not the implementation
    -- which already behaves this way (`_consumer_counts` iterates
    `scope_paths` and enumerates every atom per file, with no hunk baseline),
    so this test is GREEN against current behaviour.

    D4 PROVENANCE (feature-end deep-review HIGH finding): the predecessor of
    this test was named `..._staged_mode_scopes_to_the_touched_hunk`, computed
    `staged_payload`, and then NEVER read its `consumer_counts` -- only the
    `--paths` half was asserted. The name and docstring claimed to prove
    hunk-scoping while nothing did, which is how the gap between the document
    and the implementation stayed invisible. Both halves are asserted below.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    module = repo / "two_functions.py"
    module.write_text(
        "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed two-function module")
    with module.open("a", encoding="utf-8") as handle:
        handle.write("\n\n# alpha touched, beta untouched\n")
    _git(repo, "add", "two_functions.py")

    staged_exit, _staged_stderr, staged_payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--staged"], capsys
    )
    paths_exit, _paths_stderr, paths_payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "two_functions.py"], capsys
    )

    assert staged_exit == 0
    assert paths_exit == 0
    assert staged_payload is not None
    assert paths_payload is not None
    paths_keys = set(paths_payload["measures"]["consumer_counts"])
    assert any(k.endswith(".alpha") for k in paths_keys), (
        "--paths must report the edited symbol"
    )
    assert any(k.endswith(".beta") for k in paths_keys), (
        "--paths must report EVERY top-level symbol the touched file "
        "declares, not just the recently-edited one"
    )

    # The --staged half (D4): the assertions whose ABSENCE let the old name
    # and docstring claim a hunk-scoping rule that nothing proved -- and so
    # hid the divergence between the document and the implementation.
    staged_keys = set(staged_payload["measures"]["consumer_counts"])
    assert any(k.endswith(".alpha") for k in staged_keys), (
        "--staged must report the EDITED symbol -- the necessary half of the "
        "whole-file rule. (Phrased as 'the symbol the staged hunk touches' "
        "until 2026-07-18: that wording survived the retirement of the "
        "hunk-scoping rule and read as if hunk semantics still applied. The "
        "sufficient half is the sibling assertion below: an UNTOUCHED symbol "
        "in the same file must be in scope too.)"
    )
    assert any(k.endswith(".beta") for k in staged_keys), (
        "--staged is the ENFORCEMENT path (`commit-slice --tier --all` "
        "measures via staged=True), so it carries the conservative "
        "whole-file rule with MORE force than the inspection modes, not "
        "less: an untouched symbol in a touched file stays in scope. "
        "Narrowing this to the diff hunk would make the enforcement path "
        "measure FEWER symbols than inspection -- a safety control becoming "
        f"less conservative by design. Got {sorted(staged_keys)}"
    )
    assert staged_keys == paths_keys, (
        "the whole-file symbol-scope rule is UNIVERSAL across input modes -- "
        "no mode may resolve a narrower symbol set than another for the same "
        f"touched file. Got staged={sorted(staged_keys)} vs "
        f"paths={sorted(paths_keys)}"
    )


def test_multiple_input_modes_is_malformed_input(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: c2 -- MANDATORY-adjacent negative (exactly-one-input-mode grammar)

    Passing BOTH `--paths` and `--staged` is malformed input -- never silently
    picking one and ignoring the other. Requires a REAL structured rejection
    payload (never just a bare argparse usage error that happens to also exit
    2) -- an unimplemented `--staged` flag would today die on
    "unrecognized arguments" with NO JSON payload at all, which this pins
    against explicitly via `payload is not None`.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    exit_code, stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py", "--staged"], capsys
    )

    assert exit_code == 2
    assert payload is not None, (
        "an exactly-one-input-mode violation must emit a structured JSON "
        "rejection payload, not merely die on an unrecognized-flag usage "
        "error with no machine-readable output"
    )
    assert payload.get("event") != "BlastRadiusMeasured"
    assert "paths" in stderr.lower() or any(
        "paths" in reason.lower() for reason in payload.get("reasons", [])
    )


# --- (d) thresholds read from .nwave/des-config.json via the DESConfig cascade --


def test_configured_thresholds_widen_the_small_band(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d

    An 11-line change is M under the CANONICAL default (`small_max_lines=10`,
    per slice-01's own pinned rule) but S once the project's
    `.nwave/des-config.json` `blast_radius.small_max_lines` is raised to 50 --
    proving the CLI actually reads the config cascade, not the hardcoded
    default, when the block is present.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"small_max_lines": 50})
    target = repo / "module_a.py"
    big_edit = "".join(f"line_{i} = {i}\n" for i in range(SMALL_MAX_LINES + 1))
    with target.open("a", encoding="utf-8") as handle:
        handle.write(big_edit)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["measures"]["lines_changed"] == SMALL_MAX_LINES + 1
    assert payload["tier"] == "S", (
        "small_max_lines=50 must widen the S band -- an 11-line change stays "
        "small under the configured (not canonical) threshold"
    )


def test_present_but_empty_blast_radius_block_falls_back_per_key_to_canonical_defaults(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d

    A `.nwave/des-config.json` with an explicit but EMPTY `blast_radius: {}`
    block (distinct from a wholly-absent config file) still resolves every
    individual key to its canonical default -- per-key fallback, not an
    all-or-nothing block read. Also requires a REAL `consumer_counts`
    measurement (a symbol resolved via the port, not the slice-01 hardcoded
    `{}`) so this cannot pass merely because config-reading was skipped
    wholesale.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {})
    # Seed + commit ONLY the caller BEFORE editing module_a.py -- `git add -A`
    # here would be a latent landmine (it would stage module_a.py's edit too
    # the moment this fixture is reordered again), and committing AFTER the
    # edit would absorb it into HEAD, leaving `git diff HEAD` empty and
    # silently zeroing `lines_changed` (the exact fixture-ordering bug this
    # AT itself must not reproduce) -- so the `add` is scoped to the one file
    # it is seeding, never `-A`.
    caller = repo / "caller_of_a.py"
    caller.write_text("import module_a\n", encoding="utf-8")
    _git(repo, "add", "caller_of_a.py")
    _git(repo, "commit", "-q", "-m", "seed a caller of module_a")
    target = repo / "module_a.py"
    big_edit = "".join(f"line_{i} = {i}\n" for i in range(SMALL_MAX_LINES + 2))
    with target.open("a", encoding="utf-8") as handle:
        handle.write(big_edit)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["measures"]["consumer_counts"], (
        "consumer_counts must be a REAL measurement, not the slice-01 "
        "hardcoded {} -- an empty dict here is indistinguishable from "
        "'never computed'"
    )
    assert payload["tier"] == "M", (
        "an empty blast_radius block must fall back to the canonical "
        f"small_max_lines={SMALL_MAX_LINES} default per-key, escalating this "
        f"{SMALL_MAX_LINES + 2}-line change to M"
    )


def test_wrong_type_threshold_value_falls_back_to_default_never_hard_fails(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d, e

    A malformed (WRONG TYPE, not out-of-range) `small_max_lines: "ten"`
    degrades to the canonical default (mirrors `_scan_atdd_pure_int`'s
    existing non-int-degrades-to-default precedent in `carpaccio_format.py`)
    -- NEVER a hard fail (that is reserved for a well-typed, out-of-range
    value, tested separately below). Also requires a REAL `consumer_counts`
    measurement so this cannot pass merely because config-reading (and the
    rest of the slice-02 pipeline) was skipped wholesale.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"small_max_lines": "ten"})
    target = repo / "module_a.py"
    big_edit = "".join(f"line_{i} = {i}\n" for i in range(SMALL_MAX_LINES + 2))
    with target.open("a", encoding="utf-8") as handle:
        handle.write(big_edit)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0, (
        "a wrong-typed value must degrade to default, never hard-fail"
    )
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["consumer_counts"], (
        "consumer_counts must be a REAL measurement, not the slice-01 "
        "hardcoded {} -- an empty dict here is indistinguishable from "
        "'never computed'"
    )
    assert payload["tier"] == "M"


def test_malformed_boundary_globs_entry_falls_back_to_the_default_list(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d, e

    `boundary_globs` is validated for TYPE only (feature-delta): a
    non-string-list value falls back to the DEFAULT LIST (not an empty
    list) -- pinned by touching a file matching a DEFAULT glob (`**/ports/**`)
    and asserting it is STILL flagged L, proving the fallback landed on the
    real default list rather than merely "did not crash" (a `boundary_globs:
    []` degrade would also pass a bare `exit_code == 0` check but would
    silently defeat every default-glob boundary rule).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"boundary_globs": [123, "not-a-real-glob-shape"]})
    target = repo / "src" / "ports" / "thing.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed default-boundary-glob file")
    _touch(target)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "src/ports/thing.py"], capsys
    )

    assert exit_code == 0, "a malformed glob entry must degrade to the default list"
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
    assert payload["measures"]["boundary_files"] == ["src/ports/thing.py"], (
        "a malformed custom boundary_globs entry must fall back to the REAL "
        "default list (which includes **/ports/**), not an empty list"
    )
    assert payload["tier"] == "L"


# --- (e) floor/ceiling validation at load-time (HARD FAIL loud, GDP-3/GDP-6) --


@pytest.mark.parametrize(
    "key,bad_value,which_bound",
    [
        ("small_max_files", 0, "floor"),
        ("small_max_files", 21, "ceiling"),
        ("small_max_lines", 0, "floor"),
        ("small_max_lines", 501, "ceiling"),
        ("small_max_consumers", 0, "floor"),
        ("small_max_consumers", 51, "ceiling"),
        ("large_min_consumers", SMALL_MAX_CONSUMERS, "floor"),
        ("large_min_consumers", 1001, "ceiling"),
    ],
)
def test_out_of_range_threshold_hard_fails_loud_never_clamps(
    tmp_path: Path, capsys, key: str, bad_value: int, which_bound: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: e -- MANDATORY NEGATIVE (the anti-neutralization property the
    tier-cap needs: a consumer repo must not be able to quietly widen a
    threshold and have every commit measure S).

    A present, well-typed threshold OUTSIDE its documented floor/ceiling range
    HARD-FAILS (D4: exit 2, event `BlastRadiusConfigRejected`) -- the process
    refuses to proceed. It NEVER silently clamps to the nearest valid bound
    and NEVER silently falls back to the canonical default (that fallback is
    reserved for an ABSENT or WRONG-TYPE key, tested separately above) --
    GDP-6: neutralizing a threshold must be loud, not absorbed.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {key: bad_value})
    target = repo / "module_a.py"
    _touch(target)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 2, (
        f"a {which_bound}-breaching {key}={bad_value} must hard-fail (exit 2), "
        f"got exit={exit_code}, payload={payload!r}"
    )
    assert payload is not None
    assert payload["event"] != "BlastRadiusMeasured", (
        "a rejected config must never also emit a measurement -- that would be "
        "silently proceeding with a neutralized/clamped threshold"
    )
    reasons = payload.get("reasons", [])
    assert any(key in reason for reason in reasons), (
        f"the rejection must NAME the offending key '{key}' (GDP-3 what)"
    )
    assert any(str(bad_value) in reason for reason in reasons), (
        f"the rejection must NAME the offending VALUE {bad_value} (GDP-3 what)"
    )
    assert any(
        "nwave" in reason.lower() or "des-config" in reason.lower()
        for reason in reasons
    ), "the rejection must name HOW to fix it (points at .nwave/des-config.json)"


def test_absent_threshold_key_never_triggers_the_hard_fail_path(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d, e

    An ABSENT key (not present at all in the `blast_radius` block) is a
    DIFFERENT failure mode from a present-but-out-of-range value -- it falls
    back to the canonical default silently, never triggers
    `BlastRadiusConfigRejected`. Distinguishes "key missing" from "key present
    and bad" (the two `_config_present_and_parseable`-style branches
    `DESConfig` already establishes elsewhere in this codebase).

    Pinned with a REAL discriminating signal (not merely "did not crash"): the
    ONE present key (`small_max_consumers=2`, tighter than the canonical 3)
    is proven ACTUALLY READ by touching a symbol with exactly 3 callers --
    S under the canonical default (3 <= 3) but M under the overridden ceiling
    (3 > 2) -- while every OTHER absent key still defaults (no hard fail, no
    boundary/files/lines escalation).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"small_max_consumers": 2})  # only ONE key present
    producer = _seed_producer_with_callers(repo, "producer", "helper", caller_count=3)
    _touch(producer)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "producer.py"], capsys
    )

    assert exit_code == 0, (
        "every OTHER key (small_max_files, small_max_lines, large_min_consumers) "
        "is absent from this config and must silently default, never hard-fail"
    )
    assert payload is not None
    assert _consumer_value(payload["measures"]["consumer_counts"], "helper") == 3
    assert payload["tier"] == "M", (
        "the ONE present key (small_max_consumers=2) must be ACTUALLY READ -- "
        "3 callers is <= the canonical default (3) but > the configured "
        "override (2), so this can only be M if the override was honored"
    )


# --- cross-field ordering (Vera EXAMINE finding, 2026-07-18) ---------------
#
# D7 (DISTILL-pinned, unspecified by the feature-delta -- see the witness
# docstring below): the per-key floor/ceiling validation above checks each
# threshold in ISOLATION. The feature-delta ALSO declares a cross-field
# invariant between `small_max_consumers` and `large_min_consumers` (line
# 117: `large_min_consumers` must be "Strictly above `small_max_consumers`";
# line 140's floor/ceiling table encodes it as `large_min_consumers`'s
# DYNAMIC floor = `small_max_consumers + 1`). That invariant is currently
# enforced ONLY when `large_min_consumers` is itself present in config --
# `DESConfig._resolve_blast_radius_int`'s absent-key branch returns the raw
# canonical default BEFORE the dynamic floor is ever computed against it, so
# an explicitly-elevated `small_max_consumers` with `large_min_consumers`
# left unset silently resolves an INCOHERENT pair. Vera's live-CLI EXAMINE
# confirmed this empirically (exit 0, ✅ PASS on a config that should be
# rejected). No other pair of keys carries an equivalent ordering constraint
# anywhere in the feature-delta -- this is the only witness the design
# implies.


def test_small_max_consumers_above_the_default_large_min_consumers_hard_fails(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: e -- MANDATORY NEGATIVE (Vera EXAMINE finding, 2026-07-18)

    Configuring ONLY `small_max_consumers=20` (leaving `large_min_consumers`
    unset, so it resolves to its canonical default 10) produces the
    INCOHERENT pair (20, 10): S would tolerate up to 20 consumers while L
    already triggers from 10 -- the M band is inverted, not merely narrow.
    This is exactly the "drive-by-neutralizing misconfiguration" the
    floor/ceiling validation exists to catch loud (feature-delta line 147,
    "a consumer repo must not be able to quietly widen a threshold"), reached
    here via a path the per-key validation alone does not cover: an absent
    key whose SILENT default now conflicts with an explicitly-configured
    sibling. D7 pins the same `BlastRadiusConfigRejected` / exit 2 contract
    as a single-key floor/ceiling breach, naming BOTH keys and their
    EFFECTIVE (resolved) values -- not merely the one that was configured.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"small_max_consumers": 20})
    target = repo / "module_a.py"
    _touch(target)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 2, (
        "small_max_consumers=20 with large_min_consumers left at its default "
        "(10) resolves an INCOHERENT pair (S tolerates up to 20 consumers "
        "while L already triggers from 10) -- this must hard-fail, not "
        f"silently accept it (got exit={exit_code}, payload={payload!r})"
    )
    assert payload is not None
    assert payload.get("event") != "BlastRadiusMeasured", (
        "a rejected cross-field-incoherent config must never also emit a "
        "measurement -- that would be silently proceeding with an inverted "
        "M band"
    )
    reasons = payload.get("reasons", [])
    assert any("small_max_consumers" in reason for reason in reasons), (
        "the rejection must NAME small_max_consumers (GDP-3 what)"
    )
    assert any("large_min_consumers" in reason for reason in reasons), (
        "the rejection must NAME large_min_consumers (GDP-3 what) -- even "
        "though it was never configured, its EFFECTIVE default value is the "
        "one that conflicts and must be surfaced, not silently substituted"
    )
    assert any("20" in reason for reason in reasons), (
        "the rejection must NAME the offending small_max_consumers VALUE"
    )


def test_coherent_ordering_at_the_exact_boundary_passes(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: e -- positive control for the cross-field ordering witness
    above: a coherent pair at the TIGHTEST legal boundary
    (`large_min_consumers == small_max_consumers + 1`, both EXPLICIT) must
    PASS. Proves the ordering fix does not over-reject a legitimate,
    tightly-adjacent configuration -- without this control a validator could
    satisfy the negative witness by rejecting every configured
    `small_max_consumers`/`large_min_consumers` pair unconditionally.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write_config(repo, {"small_max_consumers": 5, "large_min_consumers": 6})
    target = repo / "module_a.py"
    _touch(target)

    exit_code, _stderr, payload = _invoke_in_process(
        repo, ["--repo", str(repo), "--paths", "module_a.py"], capsys
    )

    assert exit_code == 0, (
        "a coherent pair at the exact boundary (large_min_consumers == "
        "small_max_consumers + 1) must PASS -- an ordering fix that also "
        f"rejects THIS is over-tightened (got exit={exit_code}, "
        f"payload={payload!r})"
    )
    assert payload is not None
    assert payload["event"] == "BlastRadiusMeasured"
