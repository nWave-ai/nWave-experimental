"""Composition root for f-test-corpus-migration-in-process slice-01 enabler ATs.

Driving-port-only (Mandate-13). Every piece is driven through a REAL production
entry IN-PROCESS (a direct call, stdout captured) -- NEVER a
``subprocess.run([sys.executable, ...])`` fork (the ONE legit fork, the scorecard
@walking_skeleton wiring proof, lives in the WS step file, not here -- so this
shared composition is fork-free and clean for the non-WS scenarios it serves):

  * the per-spawn-site classifier   -> ``axis_b_levers.scan_spawn_sites`` (in-process)
  * the scope-aware enforcement gate -> ``axis_b_levers.check_non_ws_spawn`` (in-process)
  * the EDGE-not-leaf wiring check    -> ``axis_b_levers.check_unwired_entry`` (in-process)
  * the migration scorecard           -> ``at_corpus_migration_scorecard.main(argv)``
    loaded from its file path + driven in-process with stdout captured.
  * the @requires_external resolver    -> a future ``axis_b_levers`` callable reached
    by ``getattr`` at runtime (absent at HEAD).

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD the per-site seams this
feature's DESIGN pins are ABSENT, so every observable RED-fails for the right
reason. Verified against HEAD (2026-06-26):

  * ``scan_spawn_sites`` classifies at FILE level: ``_file_is_walking_skeleton``
    short-circuits the WHOLE file when any ``@walking_skeleton`` text appears, so a
    MIXED file's non-WS forks are EXEMPTED (flagged_sites empty). It exposes NO
    per-SITE ``classified_sites`` surface, NO ``per_site_verdict`` -- so the per-site
    MIGRATE/KEEP decision, the NOT_APPLICABLE/INDETERMINATE per-site verdict, and
    the recipe-conformance/edge surface are all absent -> the named RED.
  * ``check_non_ws_spawn(tests_root)`` scans the whole tree file-level with NO
    ``migration_scope`` parameter -- so a non-WS fork in an un-migrated directory is
    flagged (the ordering-caveat regression), and no scope-follows-migration
    surface exists -> the named RED.
  * ``at_corpus_migration_scorecard.main`` has signature ``main()`` (no ``argv``)
    and NO ``--per-site`` flag -- so driving the future ``main(argv)`` shape raises
    inside the call (TypeError / argparse SystemExit), no per-site JSON is emitted
    -> the named RED.
  * NO ``@requires_external`` degrade-LOUD-SKIP resolver exists on
    ``axis_b_levers`` -> the named RED.

THE ACTIVE-RED MECHANISM (DESIGN P1-P4):
  P1  This module imports ONLY STABLE always-present production entries
      (``scan_spawn_sites`` / ``check_non_ws_spawn`` / ``check_unwired_entry`` +
      the ``axis_b_levers`` module object) at module top -- NEVER an absent per-site
      callable. The absent surfaces are reached by ``getattr`` at RUNTIME inside the
      driving call, so collection imports only present names (no ImportError, never
      BROKEN).
  P2  Each driving call is a DIRECT in-process call. No fork (this module imports no
      ``subprocess``). ``forked_interpreter`` / ``git_invoked`` are structurally
      False.
  P3  The not-yet-built per-site behaviour is reached at RUNTIME: the future report
      fields are absent (``getattr(..., None)``), the future scorecard ``main(argv)``
      shape raises inside the call, the future resolver is ``None`` -- a runtime
      absence surfaced as an empty observable, never a collection error.
  P4  Each Then asserts on the CAPTURED typed observable. At HEAD the per-site
      surface is absent so each assertion is a NAMED semantic ``AssertionError``
      (failure-for-the-right-reason).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks a
different surface shape):

  A1 (per-site classifier): ``scan_spawn_sites`` (or a new ``classify_spawn_sites``)
     returns a report exposing ``.classified_sites`` -- an iterable of records each
     with ``.location`` (``file:line``), ``.decision`` ("keep"/"migrate"),
     ``.enclosing_scenario`` and ``.scenario_tags`` -- plus ``.per_site_verdict``
     ("recognized"/"not-applicable"/"indeterminate") and ``.indeterminate_sites``.
     KEEP iff the enclosing scenario carries ``@walking_skeleton`` (ADR-TEST-003).
  A2 (scope-follows-migration): ``check_non_ws_spawn`` gains a ``migration_scope``
     parameter (a list of migrated directories); the per-site tightening flags only
     WITHIN scope; un-scoped directories are NOT hard-failed (DDD-4 ordering caveat).
  A3 (scorecard): ``at_corpus_migration_scorecard.main(argv)`` accepts ``--per-site``
     emitting JSON with the pinned contract fields ``per_site_non_ws_count`` /
     ``by_scenario`` / ``by_dir`` / ``done`` (resolves OPEN QUESTION 4); ``main(argv)``
     is the in-process entry; file-level mode survives as the gradient tracker.
  A4 (recipe conformance): the per-site report exposes ``recipe_conformant`` /
     ``drives_edge`` / ``zombies_preserved`` for a migrated exemplar (zero non-WS
     forks AND drives the production EDGE AND preserves the sad-path -- DDD-2).
  A5 (@requires_external): a degrade-LOUD-SKIP resolver
     ``axis_b_levers.requires_external_skip_decision(build_capable)`` returns a
     SKIP-LOUD decision + a structured loud reason when build-incapable -- never a
     silent pass, never a hard block (resolves OPEN QUESTION 2).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# P1: import ONLY STABLE always-present production entries. The absent per-site
# surfaces are reached by getattr at RUNTIME inside the call, never imported.
from des.cli import axis_b_levers
from des.cli.axis_b_levers import (
    check_non_ws_spawn,
    check_unwired_entry,
    scan_spawn_sites,
)

from .domain_types import (
    KEEP,
    MIGRATE,
    PerSiteClassification,
    PerSiteVerdict,
    RequiresExternalSkipDecision,
    ScopedGateOutcome,
    ScorecardObservable,
    WsWiringOutcome,
)


_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCORECARD_PATH = _REPO_ROOT / "scripts" / "at_corpus_migration_scorecard.py"

# A wired production EDGE symbol (it has a real caller:
# verify_readiness_pre_dispatch._check_axis_b_levers calls check_non_ws_spawn).
_WIRED_EDGE_SYMBOL = "check_non_ws_spawn"


@dataclass
class CorpusMigrationComposition:
    """Production-wired composition root driving the REAL per-site seams in-process.

    One composition serves every slice-01 piece: each ``given_*`` materialises a
    synthetic corpus, each ``drive_*`` calls the REAL production entry IN-PROCESS,
    and the typed observable a ``Then`` asserts on is stored for read-back.
    """

    _corpus_root: Path | None = field(default=None)
    _classification: PerSiteClassification | None = field(default=None)
    _scoped: ScopedGateOutcome | None = field(default=None)
    _scorecard: ScorecardObservable | None = field(default=None)
    _ws_wiring: WsWiringOutcome | None = field(default=None)
    _skip_decision: RequiresExternalSkipDecision | None = field(default=None)
    _target_language: str = field(default="python")
    _non_ws_marker: str = field(default="")
    _ws_marker: str = field(default="")

    # --- Given: materialise synthetic corpora (real tmp FS, no git, no fork) ---

    def given_corpus(self, tmp_path: Path) -> None:
        self._corpus_root = tmp_path

    def given_target_language(self, language: str) -> None:
        self._target_language = language

    def _write(self, rel: str, text: str) -> Path:
        assert self._corpus_root is not None, "given_corpus must arm the tmp corpus."
        path = self._corpus_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _make_mixed_plain_function_file(self) -> None:
        """A MIXED file: a @walking_skeleton test fork (KEEP) + a plain test fork (MIGRATE).

        The file carries ``@walking_skeleton`` text, so at HEAD ``_file_is_walking_
        skeleton`` exempts the WHOLE file (flagged_sites empty -> both forks hidden).
        Per-site (future) must classify the plain-function fork MIGRATE, the
        WS-function fork KEEP (ADR-TEST-003 resolution-1).
        """
        self._ws_marker = "ws_function_fork"
        self._non_ws_marker = "plain_function_fork"
        self._write(
            "mixed_plain/test_mixed_plain.py",
            "import subprocess\n"
            "import sys\n"
            "import pytest\n\n\n"
            "@pytest.mark.walking_skeleton\n"
            "def test_ws_function_fork():\n"
            "    # KEEP: enclosing test carries @walking_skeleton (legit e2e).\n"
            "    subprocess.run([sys.executable, '-c', 'print(1)'])\n\n\n"
            "def test_plain_function_fork():\n"
            "    # MIGRATE: a non-@walking_skeleton enclosing scenario reaches a fork.\n"
            "    subprocess.run([sys.executable, '-c', 'print(2)'])\n",
        )

    def _make_mixed_bdd_feature(self) -> None:
        """A pytest-bdd MIXED feature: a shared step with an UNCONDITIONAL fork.

        The bound ``.feature`` has a @walking_skeleton scenario AND a non-WS
        scenario, both exercising one shared step whose subprocess is UNCONDITIONAL.
        Resolution (b) [resolves OPEN QUESTION 1]: because a non-WS scenario REACHES
        the fork, the spawn is a MIGRATE target -- the non-WS scenario must not reach
        a fork. (ADR-TEST-003 resolution-2.)
        """
        self._non_ws_marker = "steps_shared_fork"
        self._write(
            "mixed_bdd/mixed.feature",
            "@feature-synthetic\nFeature: Mixed shared-step fork\n\n"
            "  @walking_skeleton\n  Scenario: ws path\n    When the shared step forks\n\n"
            "  Scenario: plain path\n    When the shared step forks\n",
        )
        self._write(
            "mixed_bdd/steps_shared_fork.py",
            "import subprocess\n"
            "import sys\n"
            "from pytest_bdd import scenarios, when\n\n"
            "scenarios('mixed.feature')\n\n\n"
            "@when('the shared step forks')\n"
            "def shared_step():\n"
            "    # UNCONDITIONAL fork reached by BOTH the WS and the non-WS scenario\n"
            "    # -> a MIGRATE target (the non-WS scenario must not reach a fork).\n"
            "    subprocess.run([sys.executable, '-c', 'print(3)'])\n",
        )

    def _make_ws_only_bdd_feature(self) -> None:
        """A pytest-bdd feature whose step is bound ONLY to @walking_skeleton scenarios.

        No non-WS scenario can reach the fork -> KEEP (ADR-TEST-003 resolution-2,
        the KEEP boundary that pins OPEN QUESTION 1's conservative default).
        """
        self._ws_marker = "steps_ws_only_fork"
        self._write(
            "ws_only_bdd/ws_only.feature",
            "@feature-synthetic\n@walking_skeleton\nFeature: WS-only fork\n\n"
            "  @walking_skeleton\n  Scenario: ws path\n    When the ws step forks\n",
        )
        self._write(
            "ws_only_bdd/steps_ws_only_fork.py",
            "import subprocess\n"
            "import sys\n"
            "from pytest_bdd import scenarios, when\n\n"
            "scenarios('ws_only.feature')\n\n\n"
            "@when('the ws step forks')\n"
            "def ws_step():\n"
            "    # KEEP: only @walking_skeleton scenarios exercise this step.\n"
            "    subprocess.run([sys.executable, '-c', 'print(4)'])\n",
        )

    def _make_unparseable_file(self) -> None:
        self._non_ws_marker = "test_unparseable"
        self._write(
            "unparseable/test_unparseable.py",
            "import subprocess\nthis is (not valid python @@@\n",
        )

    def _make_pure_non_ws_file(self, subdir: str, marker: str) -> Path:
        return self._write(
            f"{subdir}/test_{marker}.py",
            "import subprocess\n"
            "import sys\n\n\n"
            f"def test_{marker}():\n"
            "    subprocess.run([sys.executable, '-c', 'print(0)'])\n",
        )

    def _make_migrated_exemplar(self) -> None:
        """A MIGRATED exemplar: drives a production EDGE in-process, NO fork, ZOMBIES kept.

        The recipe output (DDD-2): the shipped EDGE driven in-process (it imports +
        calls a production entry, never ``subprocess``); the sad-path (@error)
        scenario survives 1:1.
        """
        self._non_ws_marker = "test_migrated_exemplar"
        self._write(
            "migrated/test_migrated_exemplar.py",
            "from des.cli.axis_b_levers import check_non_ws_spawn\n\n\n"
            "def test_happy_path_drives_the_edge_in_process(tmp_path):\n"
            "    # EDGE-driven in-process: calls the production entry, no fork.\n"
            "    result = check_non_ws_spawn(tmp_path)\n"
            "    assert result.invariant_id == 'non_ws_spawn'\n\n\n"
            "def test_error_path_zombie_is_preserved(tmp_path):\n"
            "    # ZOMBIES: the sad-path scenario survives the migration 1:1.\n"
            "    result = check_non_ws_spawn(tmp_path)\n"
            "    assert not result.flagged\n",
        )

    # --- In-process per-site classifier driving (A1) -------------------------

    def _classify(self) -> PerSiteClassification:
        """Drive the REAL ``scan_spawn_sites`` in-process; derive the per-site view.

        At HEAD the per-site surface (``classified_sites`` / ``per_site_verdict``) is
        absent, so ``resolution_available`` is False and every per-site observable is
        empty -> the named RED. After DELIVER the future report carries the surface.
        """
        assert self._corpus_root is not None, "given_corpus must arm the tmp corpus."
        report = scan_spawn_sites(self._corpus_root, self._target_language)
        classified = getattr(report, "classified_sites", None)
        per_site_verdict_raw = getattr(report, "per_site_verdict", None)
        resolution_available = classified is not None

        migrate_sites: tuple[str, ...] = ()
        keep_sites: tuple[str, ...] = ()
        indeterminate_sites: tuple[str, ...] = tuple(
            getattr(report, "indeterminate_sites", ()) or ()
        )
        if classified is not None:
            migrate_sites = tuple(
                getattr(s, "location", "")
                for s in classified
                if getattr(s, "decision", "") == MIGRATE
            )
            keep_sites = tuple(
                getattr(s, "location", "")
                for s in classified
                if getattr(s, "decision", "") == KEEP
            )

        verdict = PerSiteVerdict.RECOGNIZED
        if per_site_verdict_raw:
            with contextlib.suppress(ValueError):
                verdict = PerSiteVerdict(per_site_verdict_raw)

        classification = PerSiteClassification(
            migrate_sites=migrate_sites,
            keep_sites=keep_sites,
            verdict=verdict,
            not_applicable_reason=str(getattr(report, "not_applicable_reason", "")),
            indeterminate_sites=indeterminate_sites,
            resolution_available=resolution_available,
            recipe_conformant=bool(getattr(report, "recipe_conformant", False)),
            drives_edge=bool(getattr(report, "drives_edge", False)),
            zombies_preserved=bool(getattr(report, "zombies_preserved", False)),
            forked_interpreter=False,
            git_invoked=False,
            diagnostic=(
                f"file_level_recognized={report.recognized}, "
                f"file_level_flagged_sites={report.flagged_sites}, "
                f"file_level_indeterminate={report.indeterminate_files}, "
                f"per_site_surface_present={resolution_available}"
            ),
        )
        self._classification = classification
        return classification

    # --- Given: arm a synthetic corpus shape (no classification yet) ---------

    def arm_mixed_plain_file(self) -> None:
        self._make_mixed_plain_function_file()

    def arm_mixed_bdd_feature(self) -> None:
        self._make_mixed_bdd_feature()

    def arm_ws_only_bdd_feature(self) -> None:
        self._make_ws_only_bdd_feature()

    def arm_unparseable_file(self) -> None:
        self._make_unparseable_file()

    def arm_non_ws_file(self) -> None:
        self._make_pure_non_ws_file("unknown_lang", "unknown")

    def arm_migrated_exemplar(self) -> None:
        self._make_migrated_exemplar()

    # --- When: classify each spawn-site in-process ---------------------------

    def classify_spawn_sites(self) -> None:
        self._classify()

    # --- per-site observable + convenience predicates ------------------------

    def classification(self) -> PerSiteClassification:
        assert self._classification is not None, (
            "the per-site classifier must be driven (When) before its observable."
        )
        return self._classification

    def non_ws_fork_is_migrate(self) -> bool:
        c = self.classification()
        return c.resolution_available and any(
            self._non_ws_marker in s for s in c.migrate_sites
        )

    def ws_fork_is_keep(self) -> bool:
        c = self.classification()
        return c.resolution_available and any(
            self._ws_marker in s for s in c.keep_sites
        )

    def non_ws_fork_not_keep(self) -> bool:
        """The non-WS fork must NOT be exempted as KEEP (the blind-spot it closes)."""
        c = self.classification()
        return c.resolution_available and not any(
            self._non_ws_marker in s for s in c.keep_sites
        )

    # --- In-process scope-aware gate driving (A2) ----------------------------

    def drive_scoped_gate(self) -> None:
        """Drive ``check_non_ws_spawn`` with a migration scope (future) in-process.

        At HEAD there is no ``migration_scope`` parameter, so the gate scans
        file-level over each subtree: it FLAGS the un-migrated subtree's non-WS fork
        (the ordering-caveat regression) and exposes no scope surface -> the named
        RED for both S7 (scope honoured) and S8 (no hard-fail of un-migrated corpus).
        """
        assert self._corpus_root is not None, "given_corpus must arm the tmp corpus."
        migrated = self._make_pure_non_ws_file("migrated_batch", "migrated_fork")
        unmigrated = self._make_pure_non_ws_file("unmigrated_batch", "unmigrated_fork")
        migrated_dir = migrated.parent
        unmigrated_dir = unmigrated.parent

        scope_honoured = False
        try:
            # A2 future surface: scope the per-site tightening to migrated dirs only.
            scoped = check_non_ws_spawn(
                self._corpus_root, migration_scope=[str(migrated_dir)]
            )
            scope_honoured = True
            flagged_locations = self._flagged_locations(scoped)
            flags_in_migrated = any("migrated_fork" in s for s in flagged_locations)
            hard_fails_unmigrated = any(
                "unmigrated_fork" in s for s in flagged_locations
            )
            diag = f"scoped_flagged={flagged_locations}"
        except TypeError:
            # HEAD: no migration_scope -> the gate over-flags file-level per subtree.
            flags_in_migrated = check_non_ws_spawn(migrated_dir).flagged
            hard_fails_unmigrated = check_non_ws_spawn(unmigrated_dir).flagged
            diag = (
                "HEAD: check_non_ws_spawn has no migration_scope param; "
                f"flags_in_migrated={flags_in_migrated}, "
                f"hard_fails_unmigrated={hard_fails_unmigrated}"
            )

        self._scoped = ScopedGateOutcome(
            flags_in_migrated_dir=flags_in_migrated,
            hard_fails_unmigrated_dir=hard_fails_unmigrated,
            scope_honoured=scope_honoured,
            forked_interpreter=False,
            git_invoked=False,
            diagnostic=diag,
        )

    @staticmethod
    def _flagged_locations(result: object) -> list[str]:
        target = getattr(result, "target", "")
        return [target] if target else []

    def scoped(self) -> ScopedGateOutcome:
        assert self._scoped is not None, (
            "the scope-aware gate must be driven (When) before its observable."
        )
        return self._scoped

    # --- In-process scorecard driving (A3) -----------------------------------

    def _load_scorecard_module(self):
        spec = importlib.util.spec_from_file_location(
            "at_corpus_migration_scorecard", _SCORECARD_PATH
        )
        assert spec is not None and spec.loader is not None, (
            f"the scorecard script must exist at {_SCORECARD_PATH}."
        )
        module = importlib.util.module_from_spec(spec)
        # Register before exec_module (defensive: dataclass/string-annotation safety).
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def drive_scorecard(self, argv: list[str]) -> ScorecardObservable:
        """Drive ``at_corpus_migration_scorecard.main(argv)`` IN-PROCESS (A3).

        At HEAD ``main()`` takes no ``argv`` and ``--per-site`` is unknown -> driving
        the future ``main(argv)`` shape raises (TypeError / argparse SystemExit)
        inside the call, no per-site JSON is emitted -> the named RED.
        """
        module = self._load_scorecard_module()
        out = io.StringIO()
        exit_code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                exit_code = int(module.main(argv))
            except SystemExit as exc:
                exit_code = int(exc.code) if isinstance(exc.code, int) else 2
            except TypeError:
                # HEAD: main() has no argv parameter -> the future entry is absent.
                exit_code = 2
        captured = out.getvalue()
        payload = self._parse_json(captured)
        per_site_count = payload.get("per_site_non_ws_count")
        observable = ScorecardObservable(
            per_site_mode_available="--per-site" in argv and payload != {},
            per_site_non_ws_count=(
                int(per_site_count) if isinstance(per_site_count, int) else None
            ),
            by_scenario=tuple(payload.get("by_scenario", []) or []),
            by_dir=dict(payload.get("by_dir", {}) or {}),
            done=bool(payload.get("done", False)),
            file_level_mode_works=("pure_files" in payload or "mixed_files" in payload),
            json_fields=tuple(sorted(payload.keys())),
            forked_interpreter=False,
            exit_code=exit_code,
            captured_output=captured,
            diagnostic=f"argv={argv}, exit_code={exit_code}, keys={sorted(payload.keys())}",
        )
        self._scorecard = observable
        return observable

    @staticmethod
    def _parse_json(captured: str) -> dict:
        captured = captured.strip()
        with contextlib.suppress(json.JSONDecodeError):
            value = json.loads(captured)
            if isinstance(value, dict):
                return value
        # Tolerate trailing/leading noise: parse the first {...} block.
        start = captured.find("{")
        end = captured.rfind("}")
        if 0 <= start < end:
            with contextlib.suppress(json.JSONDecodeError):
                value = json.loads(captured[start : end + 1])
                if isinstance(value, dict):
                    return value
        return {}

    def drive_scorecard_per_site(self) -> None:
        self.drive_scorecard(["--per-site", "--json"])

    def drive_scorecard_file_level(self) -> None:
        self.drive_scorecard(["--json"])

    def scorecard(self) -> ScorecardObservable:
        assert self._scorecard is not None, (
            "the scorecard must be driven (When) before its observable."
        )
        return self._scorecard

    # --- Recipe-exemplar edge-not-leaf wiring (A4) ---------------------------

    def edge_is_wired(self) -> bool:
        """Drive the wiring lever for the exemplar's EDGE symbol (must be wired).

        The migrated exemplar drives a production EDGE (a wired symbol), not an
        isolated leaf (C13/C14). The recipe-conformance surface that BINDS this to
        the per-site report is the new piece -- absent at HEAD via ``drives_edge``.
        """
        result = check_unwired_entry(
            _WIRED_EDGE_SYMBOL, source_root=_REPO_ROOT / "src" / "des"
        )
        return not result.flagged  # not-flagged == wired (a real EDGE).

    # --- @requires_external degrade-LOUD-SKIP resolver (A5) ------------------

    def drive_requires_external_skip(self, build_capable: bool) -> None:
        """Drive the future @requires_external skip resolver in-process (A5).

        At HEAD ``axis_b_levers`` exposes no ``requires_external_skip_decision`` --
        ``getattr`` returns None -> ``resolver_available`` False, no loud skip ->
        the named RED. After DELIVER the resolver returns a SKIP-LOUD decision +
        structured reason when build-incapable (never silent-pass, never hard-block).
        """
        resolver = getattr(axis_b_levers, "requires_external_skip_decision", None)
        if resolver is None:
            self._skip_decision = RequiresExternalSkipDecision(
                resolver_available=False,
                diagnostic=(
                    "HEAD: axis_b_levers exposes no requires_external_skip_decision "
                    "-> no @requires_external degrade-LOUD-SKIP mechanism."
                ),
            )
            return
        decision = resolver(build_capable)
        self._skip_decision = RequiresExternalSkipDecision(
            skipped=bool(getattr(decision, "skipped", False)),
            loud_reason=str(getattr(decision, "loud_reason", "")),
            silent_pass=bool(getattr(decision, "silent_pass", False)),
            hard_blocked=bool(getattr(decision, "hard_blocked", False)),
            resolver_available=True,
            diagnostic=f"resolver returned {decision!r}",
        )

    def skip_decision(self) -> RequiresExternalSkipDecision:
        assert self._skip_decision is not None, (
            "the @requires_external resolver must be driven (When) before its outcome."
        )
        return self._skip_decision

    # --- diagnostics ---------------------------------------------------------

    def diag(self) -> str:
        if self._classification is not None:
            return f"({self._classification.diagnostic})"
        if self._scoped is not None:
            return f"({self._scoped.diagnostic})"
        if self._scorecard is not None:
            return f"({self._scorecard.diagnostic})"
        if self._skip_decision is not None:
            return f"({self._skip_decision.diagnostic})"
        return "(nothing driven)"
