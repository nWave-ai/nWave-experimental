"""Active-RED acceptance: the Gate-Scope digest must be RUNNER-AGNOSTIC.

Feature: gate-scope-digest-runner-agnostic (slice-01).

DEFECT (sister instance dogfooding nWave on a PURE RUST repo, 2026-07-10):
`des verify-slice-commit` / `des commit-slice` E2's Gate-Scope digest
computation is pytest-in-process-native -- on a cargo repo every slice mints
`SliceCommitIndeterminate` instead of `SliceCommitVerified` (her workaround:
manual attestation). The rust test-runner adapter itself EXISTS and is correct
(f-rust-test-runner-adapter shipped: `cargo_runner.py` maps exit 0 -> PASS,
exit 4/94 no-match -> RunnerAdapterUnavailable/INDETERMINATE, other-nonzero ->
FAIL). The gap is UPSTREAM: the committed-scope DIGEST step only knows how to
enumerate scope pytest-natively.

PINNED SEAM (tsunami + read, binding-resolved):

  * The defect locus is `des commit-slice` Step 3
    (src/des/cli/commit_slice.py:917):
        digest_result = _committed_scope_digest_value(repo, "HEAD")
    which resolves to `_committed_scope_digest_quiet`
    (src/des/cli/run_contract_gate.py:1362-1404): it derives the digest
    EXCLUSIVELY via `GitCommittedScopeAdapter.committed_contract_files`
    (a `.py`-test-file filter, committed_scope_adapter.py:42-62) followed by
    `_collect_scope` -- pytest's in-process collection worker spawned through
    `pytest_interpreter()`. On a cargo target:
      - pytest-less box (the sister's)  -> InterpreterUnavailable ->
        `SliceCommitIndeterminate` on EVERY slice (the reported symptom);
      - pytest-present box (this one)   -> a VACUOUS empty-scope pytest digest
        (fingerprints ZERO tests), which the runner-aware `--verify-gate-scope`
        leg then refuses as a mismatch -> `SliceCommitUnverified`.
  * The runner-aware digest route ALREADY EXISTS for the CLI digest modes:
    `_maybe_route_digest_through_runner` -> `_digest_whole_tree_through_runner`
    (src/des/cli/run_contract_gate.py:2281-2353) resolves the target's runner
    (`test_runner_port.resolve`, Cargo.toml -> "cargo-test"), enumerates via
    the runner's OWN list facet (`list_cargo_scope`, cargo_runner.py:135) and
    digests through the runner-agnostic `compute_gate_scope_digest`
    (run_contract_gate.py:1141-1144: sha256 of the sorted, newline-joined,
    deduplicated node-id set). `--committed-scope-digest`,
    `--verify-gate-scope` and `--print-digest` all route through it;
    commit-slice's Step-3 trailer mint does NOT.

  PINNED CONTRACT (the fix these ATs make GREEN): `des commit-slice`'s
  Step-3 committed-scope digest must consult the SAME runner-resolution seam
  the digest CLI modes use -- on a "cargo-test" target the trailer digest is
  the runner-enumerate digest (`compute_gate_scope_digest(list_scope(...)
  .node_ids)`); a runner enumerate that raises `RunnerAdapterUnavailable`
  routes into the EXISTING honest-degrade mint
  (`_append_slice_commit_indeterminate`, the DDD-6 lane) -- never a vacuous
  pytest digest, never a fabricated verified pass. The pytest-target path
  stays byte-identical.

DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the REAL entries
`des.cli.commit_slice.main` and `des.cli.run_contract_gate.main` driven in a
CHILD interpreter with a controlled PATH -- NO real cargo required (a fake
chmod+x `cargo` script prepended to PATH wins resolve_tool's rung 1 before the
`~/.cargo/bin` known-location rung; pattern reused from
tests/des/acceptance/rust_test_runner_adapter/steps/
composition_slice_02_cargo_runner.py). Fixtures are disposable tmp git repos;
all git writes target the fixture only.

Active-RED (atdd_pure, no @skip): every import here is stdlib, so the module
COLLECTS cleanly; the POSITIVE ATs fail with a semantic AssertionError because
at HEAD the trailer digest is pytest-native (MISSING_FUNCTIONALITY), never a
collection/import error.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest


# tests/build/gate_scope_digest_runner_agnostic/acceptance/<this file>
#   parents: [0]=acceptance [1]=feature-dir [2]=build [3]=tests [4]=REPO_ROOT
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SRC_ROOT = _REPO_ROOT / "src"

_FEATURE_ID = "gate-scope-digest-runner-agnostic"
_SLICE_ID = "slice-01"

# The deterministic test identities the FAKE cargo's `nextest list` reports.
# `_parse_nextest_list` (cargo_runner.py:206-226) combines the non-indented
# `<binary>:` header with each indented test into `<binary>::<test>`.
_FAKE_NEXTEST_BINARY = "gate_scope_fixture"
_FAKE_NEXTEST_TESTS = ("digest::verifies_alpha", "digest::verifies_beta")
_EXPECTED_CARGO_NODE_IDS = tuple(
    f"{_FAKE_NEXTEST_BINARY}::{test}" for test in _FAKE_NEXTEST_TESTS
)

_GATE_SCOPE_TRAILER_RE = re.compile(r"^Gate-Scope:\s*([0-9a-f]{64})\s*$", re.MULTILINE)
_PLACEHOLDER_DIGEST = "0" * 64
# sha256("") -- the digest `compute_gate_scope_digest([])` mints over an EMPTY
# node-id set. Pinning it by name (not recomputing it inline at the assertion
# site) makes the DEFECT-D assertion self-documenting: a trailer/oracle digest
# that equals THIS value is provably vacuous, never a real fingerprint.
_VACUOUS_DIGEST = hashlib.sha256(b"").hexdigest()

_CHILD_TIMEOUT = 300


# ---------------------------------------------------------------------------
# expected-digest oracle (the documented public contract, not an internal call)
# ---------------------------------------------------------------------------


def _expected_gate_scope_digest(node_ids: tuple[str, ...]) -> str:
    """The documented digest contract (run_contract_gate.py:20-22, 1141-1144).

    SHA-256 of the sorted, newline-joined, deduplicated node-id set. Computed
    locally (stdlib) so the AT never imports production internals in-process.
    """
    joined = "\n".join(sorted(set(node_ids)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# fixtures: disposable git repos + a deterministic FAKE cargo on PATH
# ---------------------------------------------------------------------------


def _git(fixture: Path, *args: str) -> str:
    """Run git against the DISPOSABLE fixture repo only (explicit -C target)."""
    completed = subprocess.run(
        ["git", "-C", str(fixture), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _init_cargo_fixture(root: Path) -> Path:
    """A committed single-lockfile Rust fixture + one UNCOMMITTED slice change.

    Cargo.toml is the single recognized lockfile -> `resolve()` returns the
    "cargo-test" RunnerAdapter (test_runner_port._REGISTRY:220). The staged
    slice change (a new integration-test file) is the PRECONDITION commit-slice
    commits -- never the expected output (no Fixture Theater).
    """
    fixture = root / "cargo-target"
    (fixture / "src").mkdir(parents=True)
    (fixture / "Cargo.toml").write_text(
        '[package]\nname = "gate_scope_fixture"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (fixture / "src" / "lib.rs").write_text(
        "pub fn answer() -> i32 { 42 }\n", encoding="utf-8"
    )
    _git(fixture, "init", "--quiet")
    _git(fixture, "config", "user.name", "fixture")
    _git(fixture, "config", "user.email", "fixture@example.test")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "--quiet", "-m", "chore: fixture baseline")
    # the slice's own change, left for `des commit-slice --all` to stage+commit
    (fixture / "tests").mkdir()
    (fixture / "tests" / "gate_scope_at.rs").write_text(
        "#[test]\nfn verifies_alpha() { assert_eq!(1 + 1, 2); }\n",
        encoding="utf-8",
    )
    return fixture


def _init_pytest_fixture(root: Path) -> Path:
    """A committed single-lockfile Python fixture + one UNCOMMITTED slice change.

    pyproject.toml -> `resolve()` returns the "pytest" RunnerAdapter -- the
    regression-guard target whose digest lane must stay byte-identical.
    """
    fixture = root / "pytest-target"
    fixture.mkdir(parents=True)
    (fixture / "pyproject.toml").write_text(
        '[project]\nname = "gate-scope-py-fixture"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (fixture / "test_truth.py").write_text(
        "def test_truth():\n    assert True\n", encoding="utf-8"
    )
    _git(fixture, "init", "--quiet")
    _git(fixture, "config", "user.name", "fixture")
    _git(fixture, "config", "user.email", "fixture@example.test")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "--quiet", "-m", "chore: fixture baseline")
    (fixture / "test_slice_change.py").write_text(
        "def test_slice_change():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    return fixture


def _plant_fake_cargo(bin_dir: Path, *, list_exit: int) -> None:
    """A REAL chmod+x fake ``cargo`` -- deterministic, no Rust toolchain needed.

    Prepending its dir to PATH makes resolve_tool's rung 1 (shutil.which) win
    BEFORE the `~/.cargo/bin` known-location rung, so the AT is deterministic
    whether or not a real cargo exists on the box.

    ``list_exit`` controls the `nextest list` facet (cargo_runner.py §C1):
      * 0   -> a well-formed 2-test listing (the happy enumerate);
      * 4   -> "no tests to run" empty-scope (adapter -> RunnerAdapterUnavailable);
      * 101 -> a broken enumeration (adapter -> RunnerAdapterUnavailable,
               "refusing to fingerprint an untrustworthy enumeration").
    Any `nextest run` invocation reports GREEN (exit 0) -- the digest lane
    under test ENUMERATES; it never needs a red run here.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if list_exit == 0:
        list_body = (
            f'  echo "{_FAKE_NEXTEST_BINARY}:"\n'
            + "".join(f'  echo "    {test}"\n' for test in _FAKE_NEXTEST_TESTS)
            + "  exit 0\n"
        )
    elif list_exit == 4:
        list_body = '  echo "no tests to run" >&2\n  exit 4\n'
    else:
        list_body = f'  echo "error: could not compile" >&2\n  exit {list_exit}\n'
    script = (
        "#!/bin/sh\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "list" ]; then\n'
        f"{list_body}"
        "fi\n"
        'echo "test result: ok. 2 passed; 0 failed"\n'
        "exit 0\n"
    )
    cargo = bin_dir / "cargo"
    cargo.write_text(script, encoding="utf-8")
    cargo.chmod(cargo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _plant_fake_cargo_empty_listing(bin_dir: Path) -> None:
    """A REAL fake ``cargo`` whose ``nextest list`` exits CLEANLY (0) but lists
    ZERO tests -- DISTINCT from nextest's own exit-4 "no tests matched"
    refusal (``list_exit=4`` above, already mapped by the shipped adapter to
    ``RunnerAdapterUnavailable``).

    This is nextest's OTHER empty-scope shape: a well-formed, successful
    invocation (a crate with zero ``#[test]`` fns, or an enumeration that
    filters everything out) that still exits 0 with blank/whitespace-only
    stdout. ``list_cargo_scope`` (cargo_runner.py:174-199) has NO guard on
    this shape -- it trusts ``_parse_nextest_list`` blindly on any exit-0, so
    today it mints ``ListScope(node_ids=())`` -- a SUCCESS carrying an EMPTY
    scope (DEFECT-D).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "#!/bin/sh\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "list" ]; then\n'
        "  exit 0\n"
        "fi\n"
        'echo "test result: ok. 0 passed; 0 failed"\n'
        "exit 0\n"
    )
    cargo = bin_dir / "cargo"
    cargo.write_text(script, encoding="utf-8")
    cargo.chmod(cargo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _plant_fake_cargo_unparseable_listing(bin_dir: Path) -> None:
    """A REAL fake ``cargo`` whose ``nextest list`` exits 0 but emits bytes that
    are NOT valid UTF-8 (a real-world nextest quirk: a binary/doctest identity
    carrying raw bytes) -- a genuinely UNPARSEABLE listing, distinct from
    every non-zero exit code the shipped adapter already maps to
    ``RunnerAdapterUnavailable``.

    ``list_cargo_scope``'s ``subprocess.run(..., text=True)``
    (cargo_runner.py:166-172) carries no explicit ``encoding``/``errors`` and
    is not wrapped in a ``try``/``except`` -- decoding these bytes raises
    ``UnicodeDecodeError`` INSIDE the runner seam itself, a type
    ``_digest_whole_tree_through_runner``'s
    ``except RunnerAdapterUnavailable`` (run_contract_gate.py:2524) does NOT
    catch (DEFECT-C).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "#!/bin/sh\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "list" ]; then\n'
        "  printf '\\301\\301not-utf8-garbage\\n'\n"
        "  exit 0\n"
        "fi\n"
        'echo "test result: ok. 0 passed; 0 failed"\n'
        "exit 0\n"
    )
    cargo = bin_dir / "cargo"
    cargo.write_text(script, encoding="utf-8")
    cargo.chmod(cargo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _child_env(fake_bin: Path | None) -> dict[str, str]:
    """The child env: in-tree `des` importable + the fake cargo winning PATH."""
    env = dict(os.environ)
    if fake_bin is not None:
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(_SRC_ROOT) + os.pathsep + existing if existing else str(_SRC_ROOT)
    )
    return env


# ---------------------------------------------------------------------------
# driving port (Layer-3 subprocess over the REAL CLI entries)
# ---------------------------------------------------------------------------


def _drive_cli(
    module: str, argv: list[str], env: dict[str, str]
) -> tuple[int, str, str]:
    """Drive a REAL `des.cli` entry's ``main(argv)`` in a child interpreter.

    A child (not in-process) because the SUT's tool discovery reads the
    process env (PATH for the fake cargo) and itself spawns git + the pytest
    collect worker -- the subprocess boundary is the only honest way to
    control that whole environment (the rust_test_runner_adapter precedent).
    """
    program = (
        f"import sys\nfrom {module} import main\nraise SystemExit(main(sys.argv[1:]))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program, *argv],
        capture_output=True,
        text=True,
        check=False,
        timeout=_CHILD_TIMEOUT,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    return completed.returncode, completed.stdout, completed.stderr


def _commit_slice(
    fixture: Path, env: dict[str, str], *extra: str
) -> tuple[int, str, str]:
    return _drive_cli(
        "des.cli.commit_slice",
        [
            "--repo",
            str(fixture),
            "--message",
            "feat(fixture): land the slice-01 digest lane",
            "--slice-id",
            _SLICE_ID,
            "--all",
            *extra,
        ],
        env,
    )


def _committed_scope_digest_cli(fixture: Path, env: dict[str, str]) -> tuple[int, str]:
    """`run_contract_gate --committed-scope-digest` -- the runner-aware oracle.

    This CLI mode ALREADY routes through `_maybe_route_digest_through_runner`
    (bare digest on stdout), so it is the shipped runner-aware reference the
    commit-slice trailer must cohere with.
    """
    code, stdout, _stderr = _drive_cli(
        "des.cli.run_contract_gate",
        ["--repo", str(fixture), "--committed-scope-digest"],
        env,
    )
    return code, stdout.strip().splitlines()[-1] if stdout.strip() else ""


# ---------------------------------------------------------------------------
# observables
# ---------------------------------------------------------------------------


def _events(*streams: str) -> list[dict[str, object]]:
    """Every single-line JSON event across the captured channels."""
    parsed: list[dict[str, object]] = []
    for stream in streams:
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                parsed.append(payload)
    return parsed


def _has_event(events: list[dict[str, object]], name: str) -> bool:
    return any(event.get("event") == name for event in events)


def _trailer_digest(fixture: Path) -> str | None:
    """HEAD's ``Gate-Scope:`` trailer digest, or None when absent."""
    message = _git(fixture, "log", "-1", "--format=%B")
    match = _GATE_SCOPE_TRAILER_RE.search(message)
    return match.group(1) if match else None


def _ledger_events(fixture: Path) -> list[dict[str, object]]:
    """The fixture's AT-completion ledger records for this feature (if any)."""
    ledger = fixture / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
    if not ledger.is_file():
        return []
    return _events(ledger.read_text(encoding="utf-8"))


def _diag(code: int, stdout: str, stderr: str) -> str:
    return (
        f"\nexit={code}"
        f"\nevents={[e.get('event') for e in _events(stdout, stderr)]}"
        f"\nstdout_tail={stdout.strip()[-800:]!r}"
        f"\nstderr_tail={stderr.strip()[-800:]!r}"
    )


# ---------------------------------------------------------------------------
# AT-1 -- POSITIVE (active-RED today)
# ---------------------------------------------------------------------------


def test_cargo_repo_slice_commit_mints_the_runner_aware_gate_scope_digest(
    tmp_path: Path,
) -> None:
    """A cargo-target slice commit earns the RUNNER-derived Gate-Scope digest.

    Given a committed single-lockfile Rust fixture whose (fake) cargo
    enumerate reports a successful 2-test scope, when the slice lands through
    `des commit-slice`, then the commit succeeds (`SliceCommitted`) and its
    `Gate-Scope:` trailer IS the runner-port digest -- byte-equal to BOTH the
    documented sha256-of-sorted-node-ids contract over the cargo-enumerated
    identities AND the shipped runner-aware `--committed-scope-digest` oracle
    on the same fixture. The E2 verdict lane is therefore Verified-capable,
    never Indeterminate.

    Active-RED at HEAD: Step 3 digests pytest-natively (a VACUOUS empty-scope
    pytest digest on this box), the runner-aware verify leg refuses the
    mismatch, and commit-slice exits 1 with `SliceCommitUnverified` -- the
    incoherence IS the defect.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, list_exit=0)
    fixture = _init_cargo_fixture(tmp_path)
    env = _child_env(fake_bin)

    code, stdout, stderr = _commit_slice(fixture, env)
    events = _events(stdout, stderr)
    trailer = _trailer_digest(fixture)
    expected = _expected_gate_scope_digest(_EXPECTED_CARGO_NODE_IDS)

    assert code == 0 and _has_event(events, "SliceCommitted"), (
        "a cargo-target slice commit must clear `des commit-slice` with a "
        "runner-aware Gate-Scope digest (SliceCommitted); at HEAD the Step-3 "
        "committed-scope digest is pytest-native (a vacuous zero-test pytest "
        "digest / InterpreterUnavailable on a pytest-less box), so the "
        "runner-aware verify leg refuses its own commit." + _diag(code, stdout, stderr)
    )
    assert trailer == expected, (
        "the minted Gate-Scope trailer must be the RUNNER-port digest -- "
        "sha256 of the sorted cargo-enumerated node-id set "
        f"{sorted(_EXPECTED_CARGO_NODE_IDS)} (expected {expected}) -- never a "
        f"pytest-native digest over a Rust tree; got {trailer!r}."
        + _diag(code, stdout, stderr)
    )

    oracle_code, oracle_digest = _committed_scope_digest_cli(fixture, env)
    assert oracle_code == 0 and trailer == oracle_digest, (
        "commit-slice's trailer digest must COHERE with the shipped "
        "runner-aware digest oracle (`run_contract_gate "
        "--committed-scope-digest`) on the same fixture: oracle exit "
        f"{oracle_code}, oracle digest {oracle_digest!r}, trailer {trailer!r}."
        + _diag(code, stdout, stderr)
    )


# ---------------------------------------------------------------------------
# AT-2 / AT-3 -- NEGATIVE invariants (degrade-LOUD, never a fabricated pass)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("list_exit", "flavor"),
    [
        pytest.param(4, "empty-scope (RunnerAdapterUnavailable)", id="list-exit-4"),
        pytest.param(
            101, "broken enumeration (RunnerAdapterUnavailable)", id="list-exit-101"
        ),
    ],
)
def test_cargo_repo_with_untrustworthy_enumerate_still_degrades_loud_never_a_fabricated_digest(
    tmp_path: Path, list_exit: int, flavor: str
) -> None:
    """An un-enumerable cargo scope stays honest: Indeterminate, never verified.

    Given a cargo target whose (fake) cargo enumerate is untrustworthy
    (`nextest list` exit 4 empty-scope / exit 101 broken -- both mapped by the
    shipped adapter to `RunnerAdapterUnavailable`), when the slice lands
    through `des commit-slice --feature-id`, then the outcome is the EXISTING
    honest degrade lane -- a `SliceCommitIndeterminate` record/event (DDD-6,
    the same mint the interpreter-unavailable degrade uses) -- and NEVER a
    clean `SliceCommitted` pass carrying a fabricated digest.

    Active-RED at HEAD: the cargo enumerate is never consulted at all -- Step 3
    silently mints the vacuous pytest digest instead of the honest
    Indeterminate (this box), or the sister's box blanket-Indeterminates for
    the WRONG reason (interpreter absence, not the runner's own verdict).
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, list_exit=list_exit)
    fixture = _init_cargo_fixture(tmp_path)
    env = _child_env(fake_bin)

    code, stdout, stderr = _commit_slice(fixture, env, "--feature-id", _FEATURE_ID)
    events = _events(stdout, stderr)

    # Invariant half: an untrustworthy enumerate must never yield a clean pass.
    assert not (code == 0 and _has_event(events, "SliceCommitted")), (
        f"a cargo target with an untrustworthy enumerate ({flavor}) must NEVER "
        "clear `des commit-slice` as a clean SliceCommitted pass -- the digest "
        "would be fabricated (at HEAD it is a vacuous pytest digest minted "
        "without ever consulting the cargo runner)." + _diag(code, stdout, stderr)
    )

    # Honest-lane half: the degrade is the EXISTING SliceCommitIndeterminate
    # mint (event on the driving channel or record in the fixture's ledger).
    honest = _has_event(events, "SliceCommitIndeterminate") or any(
        record.get("event") == "SliceCommitIndeterminate"
        for record in _ledger_events(fixture)
    )
    assert honest, (
        f"the {flavor} degrade must surface as the honest "
        "`SliceCommitIndeterminate` lane (the DDD-6 mint "
        "`_append_slice_commit_indeterminate` -- ledger record + LOUD event, "
        "reason naming the runner), never a silent refusal and never a "
        "pytest-native digest; at HEAD the runner is never consulted, so no "
        "honest record exists." + _diag(code, stdout, stderr)
    )


# ---------------------------------------------------------------------------
# AT-5 -- NEGATIVE (DEFECT-D: silent-wrong vacuous digest minted as verified)
# ---------------------------------------------------------------------------


def test_empty_cargo_enumeration_degrades_to_indeterminate_not_vacuous_verified(
    tmp_path: Path,
) -> None:
    """DEFECT-D: an exit-0-but-EMPTY cargo enumeration must NEVER mint a clean
    pass carrying the vacuous digest as though it were a real fingerprint.

    Given a cargo target whose (fake) ``cargo nextest list`` exits CLEANLY (0)
    but lists ZERO tests (nextest's OTHER empty-scope shape -- NOT its own
    exit-4 "no tests matched" refusal, which the shipped adapter already maps
    to ``RunnerAdapterUnavailable``), when the slice lands through
    ``des commit-slice --feature-id``, then the outcome must be the EXISTING
    honest ``SliceCommitIndeterminate`` degrade lane -- NEVER a clean
    ``SliceCommitted`` pass whose ``Gate-Scope:`` trailer is the vacuous
    ``sha256("")`` digest. The feature-delta's own Summary requires a
    vacuous-empty scope to refuse/Indeterminate, exactly as the pytest path's
    ``_assert_parity`` already refuses an empty-after-collection scope.

    Active-RED at HEAD: ``list_cargo_scope`` has no explicit empty-node-id
    guard on its exit-0 path -- it trusts ``_parse_nextest_list`` blindly, so
    the empty listing mints ``ListScope(node_ids=())``,
    ``_digest_whole_tree_through_runner`` digests it via
    ``compute_gate_scope_digest([])`` = ``sha256("")``, and ``des
    commit-slice`` mints a clean ``SliceCommitted`` carrying that vacuous
    digest as a "verified" pass -- the incoherence IS the defect.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo_empty_listing(fake_bin)
    fixture = _init_cargo_fixture(tmp_path)
    env = _child_env(fake_bin)

    code, stdout, stderr = _commit_slice(fixture, env, "--feature-id", _FEATURE_ID)
    events = _events(stdout, stderr)
    trailer = _trailer_digest(fixture)

    fabricated_vacuous_pass = (
        code == 0
        and _has_event(events, "SliceCommitted")
        and trailer == _VACUOUS_DIGEST
    )
    assert not fabricated_vacuous_pass, (
        "an exit-0-but-empty cargo enumeration must NEVER mint a clean "
        'SliceCommitted pass carrying the vacuous sha256("") digest as a '
        f"'verified' scope; got code={code}, trailer={trailer!r}, vacuous "
        f"digest={_VACUOUS_DIGEST!r}." + _diag(code, stdout, stderr)
    )

    honest = _has_event(events, "SliceCommitIndeterminate") or any(
        record.get("event") == "SliceCommitIndeterminate"
        for record in _ledger_events(fixture)
    )
    assert honest, (
        "the empty-enumeration degrade must surface as the honest "
        "`SliceCommitIndeterminate` lane (the SAME DDD-6 mint the "
        "RunnerAdapterUnavailable degrade uses), never a silent pass and "
        "never a vacuous digest treated as verified; at HEAD the empty "
        "enumeration is trusted blindly and mints a clean pass instead of "
        "consulting an honest-degrade lane." + _diag(code, stdout, stderr)
    )


# ---------------------------------------------------------------------------
# AT-6 -- NEGATIVE (DEFECT-C: unparseable listing must degrade loud, not crash)
# ---------------------------------------------------------------------------


def test_unparseable_cargo_listing_degrades_loud_not_verified(
    tmp_path: Path,
) -> None:
    """DEFECT-C: a genuinely UNPARSEABLE cargo listing must degrade loud, never
    crash past the honest Indeterminate lane and never fabricate a pass.

    Given a cargo target whose (fake) ``cargo nextest list`` exits 0 but
    emits bytes that are NOT valid UTF-8 (a real-world nextest quirk -- a
    binary/doctest identity carrying raw bytes), when the slice lands through
    ``des commit-slice --feature-id``, then the outcome must be the honest
    ``SliceCommitIndeterminate`` degrade lane -- NEVER an unhandled crash (a
    raw Python traceback / non-JSON exit) and NEVER a fabricated
    ``SliceCommitted`` pass.

    Active-RED at HEAD: ``list_cargo_scope``'s
    ``subprocess.run(..., text=True)`` carries no explicit
    ``encoding``/``errors`` and is not wrapped in a ``try``/``except`` --
    decoding these bytes raises ``UnicodeDecodeError`` INSIDE the runner
    seam, a type ``_digest_whole_tree_through_runner``'s
    ``except RunnerAdapterUnavailable`` does NOT catch, so it propagates
    uncaught out of ``des commit-slice main()`` as an unhandled traceback
    (exit 1, no honest JSON event) instead of the degrade-LOUD lane.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo_unparseable_listing(fake_bin)
    fixture = _init_cargo_fixture(tmp_path)
    env = _child_env(fake_bin)

    code, stdout, stderr = _commit_slice(fixture, env, "--feature-id", _FEATURE_ID)
    events = _events(stdout, stderr)

    assert not (code == 0 and _has_event(events, "SliceCommitted")), (
        "an unparseable (non-UTF-8) cargo enumeration must NEVER clear `des "
        "commit-slice` as a clean SliceCommitted pass -- the digest would be "
        "fabricated or the process would have crashed before reaching it."
        + _diag(code, stdout, stderr)
    )

    honest = _has_event(events, "SliceCommitIndeterminate") or any(
        record.get("event") == "SliceCommitIndeterminate"
        for record in _ledger_events(fixture)
    )
    assert honest, (
        "an unparseable cargo enumeration must surface as the honest "
        "`SliceCommitIndeterminate` degrade lane (the SAME DDD-6 mint the "
        "RunnerAdapterUnavailable degrade uses, naming the runner), never an "
        "unhandled crash (raw traceback, non-JSON exit) and never a silent "
        "refusal; at HEAD the UnicodeDecodeError propagates uncaught out of "
        "`des commit-slice main()`." + _diag(code, stdout, stderr)
    )


# ---------------------------------------------------------------------------
# AT-4 -- pytest-target regression guard (GREEN today, must stay green)
# ---------------------------------------------------------------------------


def test_pytest_repo_slice_commit_digest_lane_is_still_unchanged(
    tmp_path: Path,
) -> None:
    """The pytest-target digest lane stays byte-coherent (no regression).

    Given a committed single-lockfile Python fixture, when the slice lands
    through `des commit-slice`, then the commit clears (`SliceCommitted`), the
    trailer carries a real (non-placeholder) digest, and it coheres with the
    pytest-path `--committed-scope-digest` oracle on the same fixture. Guards
    the fix against perturbing the existing pytest path (the ADD-not-mutate
    discipline: historic Gate-Scope trailers stay verifiable).
    """
    fixture = _init_pytest_fixture(tmp_path)
    env = _child_env(fake_bin=None)

    code, stdout, stderr = _commit_slice(fixture, env)
    events = _events(stdout, stderr)
    trailer = _trailer_digest(fixture)

    assert code == 0 and _has_event(events, "SliceCommitted"), (
        "the EXISTING pytest-target commit-slice lane must keep clearing "
        "unchanged." + _diag(code, stdout, stderr)
    )
    assert trailer is not None and trailer != _PLACEHOLDER_DIGEST, (
        f"the pytest-target trailer must stay a real committed-scope digest; "
        f"got {trailer!r}." + _diag(code, stdout, stderr)
    )

    oracle_code, oracle_digest = _committed_scope_digest_cli(fixture, env)
    assert oracle_code == 0 and trailer == oracle_digest, (
        "the pytest-target trailer must stay byte-coherent with the "
        "`--committed-scope-digest` oracle: oracle exit "
        f"{oracle_code}, oracle digest {oracle_digest!r}, trailer {trailer!r}."
        + _diag(code, stdout, stderr)
    )
