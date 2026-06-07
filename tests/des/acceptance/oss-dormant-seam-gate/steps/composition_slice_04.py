"""Composition root for the dormant-seam gate net-new-delta scoping (slice-04).

The slice-04 value: the gate's blast-radius is the feature's NET-NEW DELTA, not
the whole tree. A symbol that already lived on the static tree is NEVER
retroactively flagged -- so turning the gate on does not warn about the entire
existing codebase (DISCUSS D3, zero retroactive blast; the safety property that
makes the gate adoptable).

  * no retroactive blast: a dormant effectful symbol committed on the BASE ref
    (the static tree, before this change) is OUT of the net-new delta -- the gate
    measures ``git diff --diff-filter=A {base_ref}...HEAD`` (added files since the
    merge-base) -- and is NEVER flagged.
  * discrimination (non-vacuity): in the SAME repo, a NET-NEW added-file dormant
    symbol STILL warns -- the scoping excludes the static tree, it does not silence
    the delta (KPI-1 recall preserved alongside the KPI-3 zero-retroactive-blast
    guardrail).
  * OQ-1 resolution (added-FILE granularity floor): a net-new symbol added to a
    MODIFIED file (a file that already existed on the static tree) is OUT of the
    delta at the added-FILE floor -- ``--diff-filter=A`` returns added files only,
    so a modified file (and any net-new symbol it carries) is not in the delta.
    This is an explicit, honestly-named limitation (the slice-04 OQ-1 contract),
    not a bug; added-LINE resolution is a future hardening concern.

DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
slice-01/02/03 -- the production ``des dormant-seam-gate`` composition-root CLI
invoked as a subprocess black box (``python -m des.cli.dormant_seam_gate``). The
detector ``dormant_seam.detect``, the ``ChangedSymbolPort``, and the git delta read
are NEVER imported-and-called at the step boundary; the SUT is exercised only
through the CLI subprocess. Observable surface: the single-line JSON verdict on
stdout, the loud human warning on stderr, the process exit code.

SUBSTRATE (REUSE + EXTEND): the slice-01/02/03 synthetic-repo builder shape (a real
tmp git repo, a committed base branch, then net-new ADDED ``src/des/`` modules) is
reused, EXTENDED to seed a PRE-EXISTING static-tree symbol via the INITIAL commit
(on the base ref, BEFORE the delta), then the net-new delta in a SECOND commit. The
base-committed symbol is OUT of ``{base_ref}...HEAD`` added-files by construction;
the second-commit added file is IN it. Copied (not imported) from slice-03 so
slice-04 owns its own arrangements (the base-ref pre-existing module, the modified-
file extension) without coupling to slice-03's instance fields.

RED-for-right-reason / GREEN-on-author (verified against shipped slice-01/02/03
production 2026-06-07): the production ALREADY scopes to the net-new delta --
``GitChangedSymbolAdapter`` uses ``git diff --diff-filter=A`` (added files only) and
``_parse_added_src_modules`` parses ONLY files in that delta. A base-committed
(pre-existing) symbol is therefore never parsed and never flagged. slice-04 is a
GREEN-ON-AUTHOR regression PIN: it pins the no-retroactive-blast safety property +
resolves OQ-1's added-FILE granularity, both already satisfied. Reported honestly
as GREEN-on-author -- no production change required; the PIN guards the property
against a future regression (e.g. a change to ``--diff-filter=AM`` that would
suddenly re-flag the static tree).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import DeltaScope, EmissionChannel


# tests/des/acceptance/oss-dormant-seam-gate/steps/composition_slice_04.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production CLI module under test. slice-04 pins the delta-scoping ON it.
GATE_MODULE = "des.cli.dormant_seam_gate"

_FEATURE_ID = "probe-dormant-scoping-feat"

# The PRE-EXISTING static-tree dormant symbol -- committed on the BASE ref (before
# the net-new delta), with NO production call-site. It is dormant, but OUT of the
# net-new delta, so it must NEVER be retroactively flagged. Public + effectful so a
# name-match gate WOULD flag it (the discriminating control).
_PRE_EXISTING_SYMBOL = "preexisting_dormant_residue"
_PRE_EXISTING_MODULE_REL = "src/des/probe_preexisting_module.py"

# The NET-NEW added-file dormant symbol -- added in the SECOND commit (the delta),
# with NO call-site. In the delta -> must STILL warn (the recall / non-vacuity
# control: scoping excludes the static tree, it does not silence the delta).
_NET_NEW_SYMBOL = "netnew_dormant_seam"
_NET_NEW_MODULE_REL = "src/des/probe_netnew_module.py"

# The MODIFIED-file net-new symbol -- a net-new public effectful def APPENDED to the
# pre-existing module (a MODIFIED file, not an ADDED file). At the added-FILE floor
# (OQ-1) it is OUT of the delta -> not flagged. Pins the granularity floor.
_MODIFIED_FILE_ADD_SYMBOL = "added_into_modified_file"

# Tokens binding a warning to the DORMANT verdict (slice-01/02/03 shape reused).
_DORMANT_MARKER_TOKENS: tuple[str, ...] = (
    "dormant-no-call-site",
    "dormant",
    "no production call-site",
    "no call-site",
    "no call site",
    "uncalled",
)

# A block / refuse on stdout is forbidden (KPI-2 guardrail, re-pinned for slice-04).
_BLOCK_TOKENS: tuple[str, ...] = ('"decision": "block"', '"decision":"block"', "refuse")


@dataclass
class DormantSeamScopingComposition:
    """Drives the production dormant-seam-gate CLI for the slice-04 scoping ATs."""

    _tmp: Path | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _feature_dir: Path | None = field(default=None)
    _base_ref: str | None = field(default=None)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _emission_channel: EmissionChannel = field(default=EmissionChannel.STDERR)

    # ---- given ---------------------------------------------------------

    def given_pre_existing_static_tree_seam(self) -> None:
        """A dormant symbol committed on the BASE ref (static tree, before the change).

        It is dormant (no call-site) but OUT of the net-new delta; the gate must
        NEVER retroactively flag it (DISCUSS D3, zero retroactive blast).
        """
        self._build_pre_existing_only_feature()

    def given_net_new_alongside_pre_existing_seam(self) -> None:
        """A net-new dormant seam AND a pre-existing dormant seam in the same repo.

        Discrimination control: the gate must flag ONLY the net-new added-file
        symbol and leave the pre-existing static-tree symbol out of scope (KPI-3),
        while still warning on the net-new one (KPI-1 recall, non-vacuity).
        """
        self._build_discrimination_feature()

    def given_net_new_symbol_in_modified_file(self) -> None:
        """A net-new symbol APPENDED to a pre-existing (MODIFIED) file.

        OQ-1 added-FILE granularity floor: a modified file is not an ADDED file, so
        its net-new symbol is OUT of the delta and not flagged.
        """
        self._build_modified_file_feature()

    # ---- when ----------------------------------------------------------

    def when_developer_runs_the_gate(self) -> None:
        """Invoke the REAL dormant-seam-gate CLI as a subprocess black box."""
        self._run_gate()

    # ---- then ----------------------------------------------------------

    def then_pre_existing_seam_unflagged(self) -> None:
        """The pre-existing static-tree seam is NOT flagged / named (zero retroactive blast)."""
        verdict = self._verdict()
        assert not self._symbol_is_flagged(verdict, _PRE_EXISTING_SYMBOL), (
            f"a dormant symbol ({_PRE_EXISTING_SYMBOL!r}) that already lived on the "
            f"static tree (committed on the base ref, OUT of the net-new delta) must "
            f"NEVER be retroactively flagged -- the gate evaluates only the feature's "
            f"net-new delta ({DeltaScope.PRE_EXISTING_STATIC_TREE.value}), so turning "
            f"the gate on does not mass-re-flag the existing codebase. {self._observed()}"
        )
        warning = self._warning_text()
        assert _PRE_EXISTING_SYMBOL not in warning, (
            f"the pre-existing static-tree seam {_PRE_EXISTING_SYMBOL!r} must not be "
            f"named in the loud warning (it is out of the net-new delta -- zero "
            f"retroactive blast). {self._observed()}"
        )

    def then_only_net_new_flagged_pre_existing_out_of_scope(self) -> None:
        """No retroactive blast + non-vacuity: net-new flagged, pre-existing out of scope."""
        verdict = self._verdict()
        assert self._symbol_is_flagged(verdict, _NET_NEW_SYMBOL), (
            f"the NET-NEW added-file dormant symbol {_NET_NEW_SYMBOL!r} must STILL be "
            f"flagged -- the delta-scoping excludes the static tree, it does not "
            f"silence the delta (KPI-1 recall / non-vacuity: scoping is NOT vacuously "
            f"flag-nothing). {self._observed()}"
        )
        assert not self._symbol_is_flagged(verdict, _PRE_EXISTING_SYMBOL), (
            f"the pre-existing static-tree dormant symbol {_PRE_EXISTING_SYMBOL!r} must "
            f"stay OUT of scope even though a net-new symbol is being flagged in the "
            f"same run (KPI-3 zero retroactive blast -- the gate scopes to the "
            f"net-new delta per symbol, not the whole tree). {self._observed()}"
        )

    def then_net_new_seam_named_in_warning(self) -> None:
        """The net-new seam is named in the loud warning, bound to dormant semantics."""
        warning = self._warning_text()
        assert _NET_NEW_SYMBOL in warning, (
            f"the net-new added-file dormant seam {_NET_NEW_SYMBOL!r} must be named in "
            f"the loud warning (it is in the net-new delta and dormant). "
            f"{self._observed()}"
        )
        assert any(token in warning.lower() for token in _DORMANT_MARKER_TOKENS), (
            f"the net-new {_NET_NEW_SYMBOL!r} must stay bound to the DORMANT verdict "
            f"(one of {_DORMANT_MARKER_TOKENS!r}). {self._observed()}"
        )

    def then_modified_file_symbol_out_of_scope(self) -> None:
        """OQ-1 added-FILE floor: a net-new symbol in a MODIFIED file is out of scope."""
        verdict = self._verdict()
        assert not self._symbol_is_flagged(verdict, _MODIFIED_FILE_ADD_SYMBOL), (
            f"a net-new symbol ({_MODIFIED_FILE_ADD_SYMBOL!r}) added to a MODIFIED "
            f"(pre-existing) file is OUT of the net-new delta at the added-FILE "
            f"granularity floor ({DeltaScope.MODIFIED_FILE_ADD.value}) -- "
            f"`--diff-filter=A` returns ADDED files only, so a modified file's net-new "
            f"symbol is not in scope (OQ-1 resolution: added-FILE floor, not "
            f"added-LINE). This is an explicit limitation, not a bug. {self._observed()}"
        )
        warning = self._warning_text()
        assert _MODIFIED_FILE_ADD_SYMBOL not in warning, (
            f"the modified-file net-new symbol {_MODIFIED_FILE_ADD_SYMBOL!r} must not "
            f"be named in the loud warning (out of scope at the added-FILE floor). "
            f"{self._observed()}"
        )

    def then_exits_zero(self) -> None:
        """Non-halting: every scoping outcome stays exit 0 (KPI-2 guardrail)."""
        completed = self._require_completed()
        assert completed.returncode == 0, (
            "the gate must exit with code zero (non-halting) for every scoping "
            f"outcome; got returncode={completed.returncode}. {self._observed()}"
        )
        assert not any(token in completed.stdout for token in _BLOCK_TOKENS), (
            "no scoping outcome may emit a block / refuse decision on stdout "
            f"(KPI-2 guardrail). {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------

    def _symbol_is_flagged(self, verdict: dict[str, object], symbol: str) -> bool:
        """True iff the bare ``symbol`` name appears in the flagged dormant set."""
        for entry in self._dormant_entries(verdict):
            if isinstance(entry, dict) and entry.get("symbol") == symbol:
                return True
            if entry == symbol:
                return True
        return False

    def _dormant_entries(self, verdict: dict[str, object]) -> list[object]:
        dormant = verdict.get("dormant_symbols")
        return dormant if isinstance(dormant, list) else []

    def _verdict(self) -> dict[str, object]:
        """Parse the single-line JSON DormantSeamVerdict from stdout.

        Raises a semantic AssertionError (RED-for-right-reason) when no parseable
        verdict line exists.
        """
        completed = self._require_completed()
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                return payload
        raise AssertionError(
            "the dormant-seam gate produced no parseable single-line JSON verdict "
            f"on stdout. {self._observed()}"
        )

    def _warning_text(self) -> str:
        """The loud-warning channel (stderr per the OSS hooks-only invariant)."""
        return self._require_completed().stderr

    def _observed(self) -> str:
        completed = self._require_completed()
        return (
            f"gate returncode={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ----------

    def _build_pre_existing_only_feature(self) -> None:
        """base ref carries a dormant symbol; the net-new delta adds nothing new.

        The pre-existing symbol is committed on the base ref and never re-added, so
        it is OUT of ``{base_ref}...HEAD`` added-files. A trailing (allow-empty)
        commit gives HEAD a distinct tip without adding any src file -> the delta is
        genuinely empty of effectful symbols.
        """
        self._ensure_repo_with_pre_existing()
        # An empty net-new delta (no added src file): the only effectful symbol is
        # the base-committed pre-existing one, which is out of scope.
        self._commit_all("net-new delta: no added src file (only pre-existing remains)")

    def _build_discrimination_feature(self) -> None:
        """net-new delta ADDS a dormant file; the base ref still carries the pre-existing one.

        Same repo, two dormant symbols: the net-new added-file one (in scope -> must
        warn) and the pre-existing static-tree one (out of scope -> must not).
        """
        self._ensure_repo_with_pre_existing()
        self._write_module(
            rel=_NET_NEW_MODULE_REL,
            symbol=_NET_NEW_SYMBOL,
            payload="net-new",
        )
        self._commit_all("net-new delta: add a dormant added-file seam")

    def _build_modified_file_feature(self) -> None:
        """net-new delta MODIFIES the pre-existing file, appending a net-new symbol.

        The file already existed on the base ref, so it is a MODIFIED (not ADDED)
        file -- OUT of the ``--diff-filter=A`` added-files delta at the added-FILE
        floor. Its net-new symbol must therefore be out of scope (OQ-1 resolution).
        """
        self._ensure_repo_with_pre_existing()
        assert self._repo_root is not None
        module = self._repo_root / _PRE_EXISTING_MODULE_REL
        existing = module.read_text(encoding="utf-8")
        module.write_text(
            existing + "\n"
            f"def {_MODIFIED_FILE_ADD_SYMBOL}(target: str) -> None:\n"
            '    """Net-new effectful def appended to a pre-existing (MODIFIED) file."""\n'
            '    Path(target).write_text("modified-file-add", encoding="utf-8")\n',
            encoding="utf-8",
        )
        self._commit_all(
            "net-new delta: append a symbol to a pre-existing modified file"
        )

    def _ensure_repo_with_pre_existing(self) -> None:
        """A tmp git repo whose BASE ref already carries a dormant effectful symbol.

        The pre-existing module is committed in the INITIAL commit, then the base
        ref branch is cut -- so anything committed AFTER is the net-new delta against
        that base ref, and the pre-existing symbol is OUT of the delta.
        """
        if self._repo_root is not None:
            return
        self._tmp = Path(tempfile.mkdtemp(prefix="dormant-seam-scoping-at-"))
        self._repo_root = self._tmp
        self._base_ref = "dormant-seam-scoping-base"
        subprocess.run(["git", "init", "-q"], cwd=self._repo_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "at@example.com"],
            cwd=self._repo_root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "at"], cwd=self._repo_root, check=True
        )
        (self._repo_root / "src" / "des").mkdir(parents=True, exist_ok=True)
        (self._repo_root / "src" / "des" / "__init__.py").write_text(
            "", encoding="utf-8"
        )
        # The PRE-EXISTING static-tree dormant symbol: committed on the base ref,
        # BEFORE any net-new delta. It is dormant (no call-site) but out of scope.
        self._write_module(
            rel=_PRE_EXISTING_MODULE_REL,
            symbol=_PRE_EXISTING_SYMBOL,
            payload="pre-existing",
        )
        self._feature_dir = self._repo_root / "docs" / "feature" / _FEATURE_ID
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        (self._feature_dir / "feature-delta.md").write_text(
            f"# Feature Delta -- {_FEATURE_ID}\n", encoding="utf-8"
        )
        self._commit_all("base: static tree carries a pre-existing dormant seam")
        subprocess.run(
            ["git", "branch", self._base_ref], cwd=self._repo_root, check=True
        )

    def _write_module(self, rel: str, symbol: str, payload: str) -> None:
        """Add a module defining one effectful public ``symbol``."""
        assert self._repo_root is not None
        module = self._repo_root / rel
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Probe module carrying one effectful public symbol."""\n'
            "from __future__ import annotations\n"
            "from pathlib import Path\n"
            "\n"
            f"def {symbol}(target: str) -> None:\n"
            '    """Effectful: writes to the filesystem (an I/O side-effect)."""\n'
            f'    Path(target).write_text("{payload}", encoding="utf-8")\n',
            encoding="utf-8",
        )

    def _commit_all(self, message: str) -> None:
        assert self._repo_root is not None
        subprocess.run(["git", "add", "-A"], cwd=self._repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", message, "--allow-empty"],
            cwd=self._repo_root,
            check=True,
        )

    def _run_gate(self) -> None:
        """Run `python -m des.cli.dormant_seam_gate` as a subprocess black box."""
        assert self._repo_root is not None
        assert self._feature_dir is not None
        assert self._base_ref is not None
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = ""
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        env["PYTHONPATH"] = (
            str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        )
        self._completed = subprocess.run(
            [
                sys.executable,
                "-m",
                GATE_MODULE,
                "--feature-dir",
                str(self._feature_dir),
                "--repo-root",
                str(self._repo_root),
                "--delta-base-ref",
                self._base_ref,
            ],
            capture_output=True,
            text=True,
            cwd=str(self._repo_root),
            env=env,
        )

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "the dormant-seam gate must be run (When) before asserting on its "
            "observable verdict surface (Then)"
        )
        return self._completed
