"""Regression -- the gates' test-inventory step must cost what counting costs,
not what loading a pile of unused test tooling costs, AND its answer must stay
provably item-by-item identical once it takes the cheaper path.

Charter: docs/product/expectations/fix-gate-collect-spawn-plugin-overhead/
a-gates-test-inventory-costs-counting-not-tooling-load.md

DEFECT (empirically measured against ``des.cli.run_contract_gate
--collect-only --print-digest``, this repo's real driving CLI, pointed at a
throwaway ~10-item synthetic project -- never this repo's own multi-thousand
-item tree):

  - The CLI's collect-only inventory step measured 5.8s-9.6s wall-clock
    (this venv's own contention varied it; NEVER once measured under ~5.8s)
    against a ~10-item synthetic fixture. A bare, autoload-disabled
    ``pytest --collect-only`` on the SAME fixture measured ~0.8s. The gap is
    almost entirely pytest's plugin-autoload machinery: this repo's venv
    carries ~18 third-party ``pytest11`` entry points (allure_pytest, anyio,
    asyncio, describe-it, html, html_fixtures, hypothesispytest, metadata,
    pspec, pytest-bdd, pytest-describe, pytest-split, pytest_cov,
    pytest_mock, respx, timeout, xdist, xdist.looponfail) -- none of which a
    bare item-enumeration reads -- PLUS the digest seam
    (``_collect_scope_with_marker_fallback``) doubling that cost per
    invocation (it always attempts a filtered collect, then a
    marker-agnostic collect).
  - Separately, and more gravely: this repo's OWN inventory step has NO
    defense against a plugin-disabling shortcut silently shrinking the
    answer while still exiting 0. Empirically reproduced against the SAME
    driving CLI: a synthetic project with a ``pytest-describe``-only
    discoverable pair of items reports ``node_id_count: 3`` normally: point
    the identical CLI invocation at the identical fixture with
    ``PYTEST_ADDOPTS="-p no:pytest-describe"`` (simulating a cheap path that
    dropped a collection-needed plugin) and it reports ``node_id_count: 1``
    -- STILL exit 0. The existing ``_assert_parity`` defense (ADR-001) does
    NOT catch this class: it only compares the digested identity set against
    ``collected_count`` from the SAME session, and here both shrink together
    (gap stays 0), so parity holds while the answer is simply wrong.

This file pins the FOUR properties the charter's oracle requires, on SMALL
SYNTHETIC pytest projects (the properties are scale-invariant -- never pinned
against this repo's own tree, per f337ece8e precedent):

1. ANSWER-PRESERVATION, item by item (load-bearing) -- ``test_gate_digest_
   matches_full_autoload_ground_truth_item_by_item``. Compares the driving
   CLI's digest against an INDEPENDENTLY computed ground-truth digest (same
   sha256-of-sorted-node-ids formula, hand-computed here -- NOT imported from
   production) over a full-plugin-autoload bare ``pytest --collect-only``.
   Already GREEN today (today's implementation is expensive but correct) --
   a permanent regression guard the cheap path must keep satisfying, with an
   inline non-vacuity check proving the digest oracle is sensitive to a
   single-item swap, not merely a count comparison in disguise.
2. THE SILENT-WRONG NEGATIVE (the failure mode that matters) -- ``test_gate_
   inventory_never_silently_shrinks_when_a_needed_plugin_is_disabled``. RED
   today (see empirical reproduction above): asserts a shrunk inventory must
   never exit clean.
3. COST -- ``test_gate_collect_only_inventory_step_completes_within_
   counting_cost_ceiling``. RED today: a real bounded subprocess run (never a
   source-text proxy) against a generous-but-meaningful ceiling, comfortably
   below every baseline measurement taken (min 5.8s) and comfortably above
   the measured autoload-disabled floor (~0.8s).
4. PORTABILITY -- ``test_gate_inventory_answer_does_not_depend_on_this_
   machines_installed_plugins``. A genuine cross-machine check (a real second
   venv lacking this repo's dev-only plugins) cannot be fabricated inside
   this repo -- recorded honestly rather than faked. What CAN be checked
   in-repo: ``PYTEST_ADDOPTS`` is standard pytest env-var wiring the worker's
   child process reads regardless of caller, so disabling every third-party
   ``pytest11`` entry point THIS interpreter happens to have installed (
   discovered dynamically via ``importlib.metadata``, never hand-typed --
   the prior perf commit's ``-p no:pytest_pspec``/``-p no:pytest_html`` typos
   are a cautionary tale for hand-typed plugin names) is a faithful proxy for
   "a target machine that never installed them", for a fixture that needs
   none of them.

Driving surface: every property is driven through the real ``des run-
contract-gate --collect-only --print-digest`` CLI subprocess (Layer 3,
Mandate-13) -- no production import. Only stdlib + the CLI's own documented
stdout/stderr contract are read.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Synthetic fixtures (never this repo's own tree -- f337ece8e precedent)
# ---------------------------------------------------------------------------

_COUNTING_ONLY_PYPROJECT = (
    "[tool.pytest.ini_options]\n"
    'testpaths = ["tests"]\n'
    'markers = ["unit: unit marker"]\n'
)
_COUNTING_ONLY_TEST_MODULE = (
    "import pytest\n\n\n"
    "@pytest.mark.unit\n"
    '@pytest.mark.parametrize("n", range(8))\n'
    "def test_case(n):\n"
    "    assert n >= 0\n\n\n"
    "@pytest.mark.unit\n"
    "class TestGroup:\n"
    "    def test_a(self):\n"
    "        assert True\n\n"
    "    def test_b(self):\n"
    "        assert True\n"
)


def _stage_counting_only_project(base: Path) -> Path:
    """A plain, plugin-independent ~10-item project -- needs none of this
    repo's ~18 third-party pytest plugins to collect correctly."""
    repo = base / "counting_only_project"
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(_COUNTING_ONLY_PYPROJECT)
    (repo / "tests" / "test_sample.py").write_text(_COUNTING_ONLY_TEST_MODULE)
    return repo


_PLUGIN_DEPENDENT_PYPROJECT = (
    "[tool.pytest.ini_options]\n"
    'testpaths = ["tests"]\n'
    'markers = ["unit: unit marker"]\n'
)
_PLUGIN_DEPENDENT_TEST_MODULE = (
    "import pytest\n\n\n"
    "def describe_something():\n"
    "    def it_does_x():\n"
    "        assert True\n\n"
    "    def it_does_y():\n"
    "        assert True\n\n\n"
    "@pytest.mark.unit\n"
    "def test_plain():\n"
    "    assert True\n"
)


def _stage_plugin_dependent_project(base: Path) -> Path:
    """A project whose two ``describe``/``it`` items are ONLY discoverable
    when the ``pytest-describe`` plugin is active -- disabling it does not
    error, it simply makes those two items vanish (empirically verified:
    ``describe_something``/``it_does_x``/``it_does_y`` are plain nested
    functions with no ``test_`` prefix; vanilla pytest never collects them)."""
    repo = base / "plugin_dependent_project"
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(_PLUGIN_DEPENDENT_PYPROJECT)
    (repo / "tests" / "test_describe.py").write_text(_PLUGIN_DEPENDENT_TEST_MODULE)
    return repo


# ---------------------------------------------------------------------------
# Driving-CLI + independent ground-truth helpers
# ---------------------------------------------------------------------------

_RESULT_PREFIX = "GateScopeDigest"


def _invoke_gate_digest(
    repo: Path, env_overrides: dict[str, str] | None = None, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    """Drive the real ``des run-contract-gate --collect-only --print-digest``
    CLI as a child process (Layer 3, no production import)."""
    env = {**os.environ, **(env_overrides or {})}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli.run_contract_gate",
            "--repo",
            str(repo),
            "--collect-only",
            "--print-digest",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _parse_digest_event(stderr: str) -> dict[str, object] | None:
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == _RESULT_PREFIX:
            return payload
    return None


def _sha256_of_ids(ids: list[str]) -> str:
    """Independent re-implementation of the digest formula (sha256 of the
    sorted, deduplicated node-id set) -- hand-rolled here, never imported
    from ``des.cli.run_contract_gate.compute_gate_scope_digest``, so this
    ground truth cannot silently drift in lockstep with a production bug."""
    joined = "\n".join(sorted(set(ids)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _bare_pytest_collect(repo: Path) -> tuple[list[str], int]:
    """Ground truth: a bare, FULL-plugin-autoload ``pytest --collect-only
    -q`` over ``repo`` (only ``-p no:pspec`` -- ``pytest-pspec`` rewrites the
    ``-q`` collect-only summary line format, an unrelated cosmetic collapse
    this repo's own ADR-001 already documents; disabling it is needed only so
    THIS helper can parse the plain nodeid lines, it changes no collected
    item)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:pspec"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    ids = [line.strip() for line in result.stdout.splitlines() if "::" in line]
    return ids, result.returncode


def _installed_third_party_plugin_names() -> list[str]:
    """Every ``pytest11`` entry point THIS interpreter has installed --
    discovered dynamically, never hand-typed (the prior perf commit's
    ``-p no:pytest_pspec``/``-p no:pytest_html`` are wrong registered names
    and silently no-op; hand-typing plugin names is exactly the mistake this
    helper avoids)."""
    return sorted(ep.name for ep in metadata.entry_points(group="pytest11"))


# ---------------------------------------------------------------------------
# 1. ANSWER-PRESERVATION -- load-bearing, item by item (GREEN today, guard)
# ---------------------------------------------------------------------------


def test_gate_digest_matches_full_autoload_ground_truth_item_by_item(
    tmp_path: Path,
) -> None:
    """The driving CLI's digest must equal an independently computed digest
    over a full-plugin-autoload bare pytest collect -- item by item, not
    merely the same count. A single item swapped for another must change the
    digest (proven inline below), so this oracle cannot be satisfied by a
    same-COUNT-different-membership answer."""
    repo = _stage_counting_only_project(tmp_path)

    ground_truth_ids, ground_truth_exit = _bare_pytest_collect(repo)
    assert ground_truth_exit in (0, 5), (
        f"fixture failed to collect cleanly under full autoload (exit "
        f"{ground_truth_exit}) -- fixture bug, not the property under test"
    )
    assert len(ground_truth_ids) == 10, (
        "fixture drifted from its documented ~10-item shape -- fixture bug"
    )
    ground_truth_digest = _sha256_of_ids(ground_truth_ids)

    result = _invoke_gate_digest(repo)
    assert result.returncode == 0, (
        f"WHAT: gate exited {result.returncode} on a healthy synthetic "
        f"project. WHY: this pin needs a successful digest to compare "
        f"against ground truth. stderr={result.stderr!r}"
    )
    gate_digest = result.stdout.strip()
    event = _parse_digest_event(result.stderr)
    assert event is not None, f"no GateScopeDigest event on stderr={result.stderr!r}"

    assert event["node_id_count"] == len(ground_truth_ids), (
        f"WHAT: gate reported node_id_count={event['node_id_count']} vs "
        f"ground-truth count={len(ground_truth_ids)} on the identical "
        f"synthetic project. WHY: the inventory answer must be item-for-item "
        f"identical to a full-plugin-loaded collection, at ANY suite scale. "
        f"HOW: see docs/product/expectations/fix-gate-collect-spawn-plugin-"
        f"overhead/a-gates-test-inventory-costs-counting-not-tooling-load.md."
    )
    assert gate_digest == ground_truth_digest, (
        f"WHAT: gate digest {gate_digest} != ground-truth digest "
        f"{ground_truth_digest} over the same {len(ground_truth_ids)}-item "
        f"synthetic project. WHY: the inventory step's answer must be "
        f"byte-for-byte item-identical to a full plugin-loaded pytest "
        f"collect-only enumeration -- a mismatch means the cheap path "
        f"changed WHICH items are counted, not merely how fast counting "
        f"happens, and every downstream gate verdict is built on this "
        f"digest. HOW: never let the inventory step drop or reorder-as-"
        f"different a canonical item identity; see the charter's item-1 "
        f"requirement."
    )

    # Non-vacuity: prove this oracle actually reacts to a single-item swap --
    # a same-COUNT-different-membership answer must NOT pass silently.
    mutated_ids = ground_truth_ids[:-1] + [
        "tests/test_sample.py::an_item_that_was_never_collected"
    ]
    assert len(mutated_ids) == len(ground_truth_ids)
    mutated_digest = _sha256_of_ids(mutated_ids)
    assert mutated_digest != ground_truth_digest, (
        "digest oracle failed to distinguish a single-item swap at equal "
        "count -- the oracle would be a count comparison in disguise"
    )


# ---------------------------------------------------------------------------
# 2. THE SILENT-WRONG NEGATIVE (RED today)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_gate_inventory_never_silently_shrinks_when_a_needed_plugin_is_disabled(
    tmp_path: Path,
) -> None:
    """If a (possibly cheaper) collection path drops a plugin the inventory
    genuinely needed, the result must never be a smaller item count that
    still exits 0 -- it must refuse loudly (non-zero exit) or flag the gap
    explicitly. Empirically RED today: ``_assert_parity`` (ADR-001) only
    compares the digested identity set against ``collected_count`` from the
    SAME session; here both shrink together (gap stays 0), so today's
    defense does not catch this class."""
    repo = _stage_plugin_dependent_project(tmp_path)

    healthy = _invoke_gate_digest(repo)
    assert healthy.returncode == 0, f"healthy baseline failed: {healthy.stderr!r}"
    healthy_event = _parse_digest_event(healthy.stderr)
    assert healthy_event is not None
    healthy_count = healthy_event["node_id_count"]
    assert healthy_count >= 2, (
        "fixture must contain >=1 plugin-only-discoverable item alongside a "
        "plain one, or this pin cannot distinguish a genuine shrink -- "
        "fixture bug, not the property under test"
    )

    # Simulate a cheap path that dropped the collection-needed plugin
    # (pytest-describe) while still enumerating -- via PYTEST_ADDOPTS, a
    # standard pytest env-var the worker's own child process reads
    # regardless of caller (a test-fixture technique to exercise the
    # property, not a claim about how the eventual fix is implemented).
    deficient = _invoke_gate_digest(
        repo, env_overrides={"PYTEST_ADDOPTS": "-p no:pytest-describe"}
    )
    deficient_event = _parse_digest_event(deficient.stderr)
    deficient_count = (
        deficient_event["node_id_count"] if deficient_event is not None else None
    )

    shrank = deficient_count is not None and deficient_count < healthy_count
    refused_loudly = deficient.returncode != 0

    assert not shrank or refused_loudly, (
        f"WHAT: the inventory shrank from {healthy_count} to "
        f"{deficient_count} items on the identical synthetic project while "
        f"still exiting {deficient.returncode} (a clean/success exit). "
        f"WHY: a smaller inventory that still exits 0 is the silent-wrong "
        f"failure mode -- an absence produced by a missing capability, "
        f"reported as a complete result; every downstream gate verdict is "
        f"built on this count, so a silent shrink corrupts them all without "
        f"a trace. HOW: the inventory step must detect when its collection "
        f"path returns fewer items than the tree can actually produce, and "
        f"refuse/flag loudly (non-zero exit or an explicit incomplete-"
        f"inventory event) rather than emit the smaller count as if it were "
        f"the answer -- see the charter's item-2 negative, docs/product/"
        f"expectations/fix-gate-collect-spawn-plugin-overhead/"
        f"a-gates-test-inventory-costs-counting-not-tooling-load.md."
    )


# ---------------------------------------------------------------------------
# 3. COST (RED today)
# ---------------------------------------------------------------------------

# Generous-but-meaningful: every baseline measurement taken against the
# ~10-item counting-only fixture (this test's own probe, pre-fix, across
# varying box contention) was 5.8s-9.6s, NEVER once under 5.8s; a bare
# autoload-disabled collect-only on the identical fixture measured ~0.8s.
# 4.0s sits comfortably below every observed baseline and comfortably above
# the measured floor.
_COST_CEILING_SECONDS = 4.0


def test_gate_collect_only_inventory_step_completes_within_counting_cost_ceiling(
    tmp_path: Path,
) -> None:
    """A real bounded subprocess run (never a source-text proxy) must
    complete within the ceiling -- it cannot be satisfied by a cosmetic edit
    that does not actually relocate the cost."""
    repo = _stage_counting_only_project(tmp_path)
    try:
        result = _invoke_gate_digest(repo, timeout=_COST_CEILING_SECONDS)
        elapsed_ok = result.returncode == 0
    except subprocess.TimeoutExpired:
        elapsed_ok = False

    assert elapsed_ok, (
        f"WHAT: the collect-only inventory step did not complete within the "
        f"{_COST_CEILING_SECONDS}s ceiling on a ~10-item synthetic project "
        f"(or exited non-zero). WHY: measured baseline (this test's own "
        f"probe, pre-fix, across varying box contention) was 5.8s-9.6s -- "
        f"almost entirely pytest plugin-autoload overhead: this repo's venv "
        f"carries ~18 third-party pytest11 entry points "
        f"({', '.join(_installed_third_party_plugin_names())}) none of "
        f"which a bare item-enumeration reads, PLUS "
        f"_collect_scope_with_marker_fallback doubling that cost per "
        f"invocation (it always attempts a filtered collect, then a "
        f"marker-agnostic collect). A bare, autoload-disabled collect-only "
        f"on the same fixture measured ~0.8s -- the floor this step should "
        f"approach. HOW: make the inventory step's pytest spawn(s) skip "
        f"loading plugins the enumeration never reads, and avoid paying "
        f"that cost twice per invocation -- see docs/product/expectations/"
        f"fix-gate-collect-spawn-plugin-overhead/a-gates-test-inventory-"
        f"costs-counting-not-tooling-load.md."
    )


# ---------------------------------------------------------------------------
# 4. PORTABILITY (GREEN today, capability floor)
# ---------------------------------------------------------------------------


def test_gate_inventory_answer_does_not_depend_on_this_machines_installed_plugins(
    tmp_path: Path,
) -> None:
    """Portability proxy per the charter's item 4.

    A GENUINE portability check would run this repo's gate CLI from an
    interpreter that never installed this repo's ~18 dev-only pytest
    plugins (a real second machine/venv) -- this test cannot fabricate that
    inside this repo; recorded honestly rather than faked, per the dispatch
    instruction. What CAN be checked in-repo: ``PYTEST_ADDOPTS`` is standard
    pytest env-var wiring the worker's own child process reads regardless of
    caller, so disabling every third-party ``pytest11`` entry point THIS
    interpreter happens to have installed (discovered dynamically, never
    hand-typed) is a faithful proxy for "a target machine that never
    installed them" -- for a fixture (deliberately) needing none of them.
    """
    repo = _stage_counting_only_project(tmp_path)

    baseline = _invoke_gate_digest(repo)
    assert baseline.returncode == 0, f"baseline failed: {baseline.stderr!r}"
    baseline_digest = baseline.stdout.strip()

    simulated_absent = " ".join(
        f"-p no:{name}" for name in _installed_third_party_plugin_names()
    )
    result = _invoke_gate_digest(
        repo, env_overrides={"PYTEST_ADDOPTS": simulated_absent}
    )

    assert result.returncode == 0, (
        f"WHAT: the inventory step exited {result.returncode} once this "
        f"repo's own third-party pytest plugins were simulated absent. "
        f"WHY: the gates run against OTHER people's projects on machines "
        f"nWave does not control -- a portable inventory step must not "
        f"assume this machine's particular installed tooling; it must say "
        f"so loudly rather than crash or degrade. stderr={result.stderr!r}"
    )
    assert result.stdout.strip() == baseline_digest, (
        "the inventory answer changed once non-essential third-party "
        "plugins were simulated absent -- the counting-only fixture needs "
        "none of them, so the answer must be identical with or without them"
    )
