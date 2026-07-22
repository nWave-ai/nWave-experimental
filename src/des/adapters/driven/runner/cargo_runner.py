"""The cargo concrete run-adapter -- shells the target's cargo, maps exit codes.

ADR-RTR-001 C1. The cargo half of the run/read split (Principle 12): mirrors
``pytest_runner.run_pytest_scope`` -- shells the TARGET's own cargo over the
feature's declared command and maps the cargo exit code to a pass/fail/
indeterminate verdict. cargo is the TARGET's tool (subprocess), NEVER a nWave
dependency (D3) -- stdlib + the resolved cargo binary only.

``run_cargo_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading cargo binary via the SHARED ``resolve_tool`` discovery
   scale (defeats WSL2 GOTCHA #1 -- cargo in ``~/.cargo/bin`` off the hook PATH).
   Unresolvable after the full scale -> raise ``RunnerAdapterUnavailable`` naming
   the remediation (the LOUD INDETERMINATE channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("cargo", "nextest", "run", "--test", ...)``),
   NOT a node-id list. The leading token is the binary resolved in step 1; the
   rest are the subcommand shelled as-is (the adapter does NOT choose
   nextest-vs-test -- the feature declares its driver, D5).
3. Shell the resolved cargo + the declared subcommand with ``cwd=target_root`` and
   the resolved cargo's directory prepended to a copied ``PATH`` (so the
   subprocess finds its own subcommands, e.g. ``cargo-nextest``).
4. Map the exit code (the §C1 exit-semantics, each pinned by an AT):

   * exit 0                          -> ``RunVerdict(passed=True)``  (PASS)
   * exit 4 (declared command ran 0 tests) -> raise ``RunnerAdapterUnavailable``
     (INDETERMINATE empty-scope -- NOT a vacuous pass)
   * exit 94 (nextest filterset matched no binary names) -> raise
     ``RunnerAdapterUnavailable`` (INDETERMINATE empty-scope -- NOT a cargo-red;
     the feature-scoped selector matched no crate binary, no tests ran)
   * any other non-zero (legit RED, tests executed) -> ``RunVerdict(passed=False)``
     (FAIL -- PROPAGATED, never swallowed into INDETERMINATE)

cargo unresolvable / exit 4 / exit 94 -> INDETERMINATE; a legit RED -> FAIL. NEVER
a pytest fallback, NEVER a silent pass.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text
from des.adapters.driven.runner.pytest_runner import (
    _signal_kill_reason,
    run_timeout_seconds,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.test_runner_port import (
    AtDiscoveryResult,
    ListScope,
    RunnerAdapterUnavailable,
    RunVerdict,
)


if TYPE_CHECKING:
    from des.ports.test_runner_port import RunnerAdapter

_logger = logging.getLogger(__name__)


# The cargo binary name resolved at the head of the declared command.
_CARGO_NAME = "cargo"

# The known install locations cargo lives in off the hook PATH (WSL2 GOTCHA #1):
# the rustup default ``~/.cargo/bin`` and a ``$CARGO_HOME/bin`` override. A cargo
# present here but absent from PATH is USED via the known-location rung, never a
# false INDETERMINATE.
_CARGO_HOME = os.environ.get("CARGO_HOME")
CARGO_KNOWN_LOCATIONS: tuple[str, ...] = (
    *((str(Path(_CARGO_HOME) / "bin"),) if _CARGO_HOME else ()),
    str(Path.home() / ".cargo" / "bin"),
)

# cargo's "no test matched / zero tests run" exit code -> INDETERMINATE empty-scope
# (the cargo analogue of pytest's exit-5 no-collection), carried distinctly from a
# legit RED (any other non-zero exit -> FAIL).
_NO_MATCH_EXIT = 4

# nextest's "filterset matched no binary names" exit code -> INDETERMINATE
# empty-scope, mirroring _NO_MATCH_EXIT. EMPIRICALLY (real cargo 1.95 + nextest
# 0.9.137): when the feature-scoped selector (e.g. ``-E 'binary(/<feature_id>/)'``)
# matches NO crate binary, nextest exits 94 -- no tests ran, so this is an
# empty-scope INDETERMINATE, NOT a test-red. Without this, exit 94 falls into the
# "any other non-zero -> FAIL" arm and is misreported as a false cargo-red.
_NO_BINARY_MATCH_EXIT = 94


def run_cargo_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared cargo command in ``target_root``; map the exit code.

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the cargo binary
    resolved via the shared discovery scale; the rest is the subcommand shelled
    as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for the two
    INDETERMINATE rows (cargo-absent, exit-4 empty-scope).
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _CARGO_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(binary, CARGO_KNOWN_LOCATIONS)
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    try:
        completed = subprocess.run(
            [resolution.path, *subcommand],
            capture_output=True,
            text=True,
            cwd=target_root,
            env=_env_with_cargo_dir(resolution.path, target_root),
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the cargo command did not complete within "
                f"{run_timeout_seconds():.0f}s (a hanging/deadlocking run) -- "
                "INDETERMINATE, never a silent unbounded hang; raise "
                "NWAVE_GATE_RUN_TIMEOUT if this is a legitimate long run"
            ),
        ) from exc

    if completed.returncode == _NO_MATCH_EXIT:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the declared cargo command ran zero tests (exit {_NO_MATCH_EXIT}, "
                "empty-scope) in the target -- INDETERMINATE, not a vacuous pass; "
                "declare a cargo test_command that selects tests and retry"
            ),
        )
    if completed.returncode == _NO_BINARY_MATCH_EXIT:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the feature-scoped selector matched no cargo binary "
                f"(exit {_NO_BINARY_MATCH_EXIT}, empty-scope) in the target -- "
                "INDETERMINATE, not a cargo-red; provide a runner.json with an "
                "explicit test_command that selects the crate's tests and retry"
            ),
        )

    kill_reason = _signal_kill_reason(completed.returncode)
    if kill_reason is not None:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the cargo run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


def list_cargo_scope(
    adapter: RunnerAdapter,
    target_root: Path,
) -> ListScope:
    """Enumerate the crate's whole-tree test scope via ``cargo nextest list``.

    The cargo ENUMERATE facet (ADR-FLOW-011 D5 -- the read counterpart of
    ``run_cargo_scope``): shells the TARGET's own ``cargo nextest list`` over the
    WHOLE crate (no feature ``-E`` filter -- the whole-tree digest fingerprints the
    crate's entire test set) and returns the listed test identities as the node-id
    set the gate digests. The leading ``cargo`` binary is resolved via the SHARED
    discovery scale (WSL2 GOTCHA #1), mirroring ``run_cargo_scope``.

    Exit-map MIRRORS the run facet (never a fabricated digest):

    * cargo unresolvable -> raise ``RunnerAdapterUnavailable`` (the LOUD
      INDETERMINATE channel naming the remediation).
    * exit 4 (zero tests enumerated) -> raise ``RunnerAdapterUnavailable``
      (empty-scope INDETERMINATE -- NOT an empty digest).
    * exit 94 (nextest filterset matched no binary names) -> raise
      ``RunnerAdapterUnavailable`` (empty-scope INDETERMINATE, distinctly reasoned
      -- NOT an empty digest).
    * any other non-zero (the enumeration itself failed) -> raise
      ``RunnerAdapterUnavailable`` -- a digest over an untrustworthy enumeration is
      worse than a LOUD refusal.
    * exit 0 but stdout decodes to ZERO test identities (a well-formed,
      successful invocation over a crate with no matched tests -- distinct from
      nextest's own exit-4 refusal) -> raise ``RunnerAdapterUnavailable``
      (empty-scope INDETERMINATE -- never mint ``compute_gate_scope_digest(())``
      == ``sha256("")`` as a "verified" fingerprint).
    * exit 0 but stdout is not valid UTF-8 (a genuinely unparseable listing,
      e.g. a binary/doctest identity carrying raw bytes) -> raise
      ``RunnerAdapterUnavailable`` -- refusing to fingerprint an unparseable
      enumeration, never an uncaught ``UnicodeDecodeError`` propagating past
      this seam.
    * exit 0, valid UTF-8, non-empty -> the parsed node-id set.
    """
    resolution = resolve_tool(_CARGO_NAME, CARGO_KNOWN_LOCATIONS)
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    try:
        completed = subprocess.run(
            [resolution.path, "nextest", "list"],
            capture_output=True,
            text=True,
            cwd=target_root,
            env=_env_with_cargo_dir(resolution.path, target_root),
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                "`cargo nextest list` did not complete within "
                f"{run_timeout_seconds():.0f}s (a hanging/deadlocking "
                "enumeration) -- INDETERMINATE, never a silent unbounded "
                "hang; raise NWAVE_GATE_RUN_TIMEOUT if this is legitimate"
            ),
        ) from exc
    except UnicodeDecodeError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                "`cargo nextest list` emitted output that could not be decoded "
                f"as UTF-8 ({exc}) -- refusing to fingerprint an unparseable "
                "enumeration"
            ),
        ) from exc

    if completed.returncode == _NO_MATCH_EXIT:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"`cargo nextest list` enumerated zero tests (exit {_NO_MATCH_EXIT}, "
                "empty-scope) in the target -- INDETERMINATE, not an empty digest"
            ),
        )
    if completed.returncode == _NO_BINARY_MATCH_EXIT:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"`cargo nextest list` matched no cargo binary "
                f"(exit {_NO_BINARY_MATCH_EXIT}, empty-scope) in the target -- "
                "INDETERMINATE, not an empty digest; provide a runner.json with an "
                "explicit test_command that selects the crate's tests and retry"
            ),
        )
    if completed.returncode != 0:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"`cargo nextest list` failed (exit {completed.returncode}) -- "
                "refusing to fingerprint an untrustworthy enumeration"
            ),
        )

    node_ids = _parse_nextest_list(completed.stdout)
    if not node_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                "`cargo nextest list` exited 0 but enumerated ZERO test "
                "identities (empty-scope) -- refusing to mint a vacuous "
                "sha256(\"\") digest as a 'verified' fingerprint"
            ),
        )

    return ListScope(node_ids=node_ids, runner=adapter.name)


def _parse_nextest_list(stdout: str) -> tuple[str, ...]:
    """Parse ``cargo nextest list`` default output into stable node-id identities.

    The REAL default output is FLAT: every non-blank line is a complete,
    non-indented ``<binary-id> <test-path>`` pair (space-separated, zero leading
    whitespace, no trailing ``:`` header -- verified against a live run, `cat -A`
    traced). Each line is split on its FIRST space into ``<binary-id>`` and
    ``<test-path>``, then joined as ``<binary-id>::<test-path>`` so the identity
    set is stable and binary-disambiguated -- the cargo analogue of pytest's
    class-aware ``fspath::Class::method`` canonical identity. A line with no
    space (malformed/unparseable) mints no identity. Returns the sorted,
    deduplicated tuple (the order-stable digest input); blank/whitespace-only
    stdout returns ``()`` -- never a fabricated identity from noise.
    """
    identities: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        binary_id, separator, test_path = line.partition(" ")
        if not separator:
            continue
        identities.append(f"{binary_id}::{test_path}")
    return tuple(sorted(set(identities)))


def _env_with_cargo_dir(cargo_path: str, target_root: Path) -> dict[str, str]:
    """A copied env with the resolved cargo's dir prepended to ``PATH``.

    So the shelled cargo finds its own subcommands (``cargo-nextest``) even when
    the resolved cargo was found off PATH (the known-location rung).

    Also reuses a warm ``target/`` build-cache when ``target_root`` is a LINKED
    git worktree with no ``CARGO_TARGET_DIR`` already set (RCA: a fresh/linked
    worktree cold-compiling the whole crate OOMs or empty-scopes the digest).
    An operator/CI-set ``CARGO_TARGET_DIR`` is NEVER overridden; a plain repo or
    any git-resolution failure leaves the env untouched (degrade-LOUD, never a
    guessed dir, never a crash) -- see ``_worktree_target_dir``.
    """
    env = dict(os.environ)
    cargo_dir = str(Path(cargo_path).parent)
    existing = env.get("PATH", "")
    env["PATH"] = cargo_dir + os.pathsep + existing if existing else cargo_dir

    if "CARGO_TARGET_DIR" not in env:
        reused = _worktree_target_dir(target_root)
        if reused is not None:
            env["CARGO_TARGET_DIR"] = str(reused)

    return env


def _worktree_target_dir(target_root: Path) -> Path | None:
    """The main checkout's warm ``target/`` dir when ``target_root`` is a
    LINKED git worktree; ``None`` for a plain repo, absent ``git``, or any
    resolution failure.

    Detection: ``git rev-parse --git-common-dir`` returns an ABSOLUTE path to
    the main checkout's git-dir for a linked worktree, and a RELATIVE ``.git``
    for a plain repo. Never raises past this seam -- a missing ``git``, a
    non-repo ``target_root``, or any other subprocess failure degrades LOUD to
    "no reuse" (logged, never a crash, never a guessed dir).
    """
    try:
        common_dir = git_text(target_root, "rev-parse", "--git-common-dir").strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        _logger.info(
            "cargo_runner: CARGO_TARGET_DIR worktree-reuse skipped for %s "
            "(git-common-dir probe failed: %s) -- leaving env untouched",
            target_root,
            exc,
        )
        return None

    if not common_dir or not Path(common_dir).is_absolute():
        return None

    main_checkout_root = Path(common_dir).resolve().parent
    return main_checkout_root / "target"


# ---------------------------------------------------------------------------
# cargo at-discovery facet (fix-rust-regression-at-kind-wiring) -- relocates
# ``at_review_verdict._count_rust_regression_ats`` /
# ``_rust_regression_content_hash`` VERBATIM (including the already-fixed
# comment-blindness + ``UnicodeDecodeError`` hardening), the Rust mirror of
# ``pytest_runner.discover_pytest_ats``.
# ---------------------------------------------------------------------------

_RUST_TEST_FN_RE = re.compile(
    r"#\[test\]\s*(?:#\[[^\]]*\]\s*)*"
    r"(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)"
)


def _strip_rust_line_comments(source: str) -> str:
    """Strip ``//``-to-EOL line comments before attribute matching.

    Minimal robust line-scan (no Rust parser, no block-comment / string-
    literal awareness -- deliberately out of scope): a ``#[test]`` occurring
    only inside a ``//`` line comment is text, never a real Rust attribute,
    and must never satisfy ``_RUST_TEST_FN_RE``. Newlines are preserved so
    multi-line attribute-then-``fn`` matching is unaffected.
    """
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def discover_cargo_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``#[test]``-attributed AT identities a ``.rs`` regression
    file carries.

    Line/regex scan (no Rust parser, no Python ``ast`` on ``.rs`` source) for
    ``#[test]``-attributed function names -- the Rust community idiom
    (descriptive names, not ``test_``-prefixed). Degrade-LOUD
    (``RunnerAdapterUnavailable``, never a silently-empty discovery) when the
    file cannot be read/decoded or has zero ``#[test]`` functions.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name, reason=f"cannot read {regression_test_file}: {exc}"
        ) from exc
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"cannot read/decode {regression_test_file}: malformed "
                f"(not valid UTF-8): {exc}"
            ),
        ) from exc
    at_ids = _RUST_TEST_FN_RE.findall(_strip_rust_line_comments(text))
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero #[test] functions found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = [
    "CARGO_KNOWN_LOCATIONS",
    "discover_cargo_ats",
    "list_cargo_scope",
    "run_cargo_scope",
]
