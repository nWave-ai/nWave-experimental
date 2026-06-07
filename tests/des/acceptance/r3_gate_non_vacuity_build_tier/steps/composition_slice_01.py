"""Composition root for r3-gate-non-vacuity-build-tier slice-01 (Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): every service method drives the REAL
`des run-contract-gate --feature-id <f> --entering-slice <s>` CLI as a Layer-3
SUBPROCESS black-box -- never a direct
`from des.cli.run_contract_gate import _mode_feature_scoped` + function-boundary
call. `_arch_invariant_paths` / `_collect_node_ids` / `_mode_feature_scoped` are
NEVER imported; the AT observes ONLY the CLI's exit code and its stdout JSON
verdict event. This is the same definition the U2 SubagentStop / G_COMMIT exit
gate invokes (port-to-port).

Genericità (dispatch invariant 2): the CLI is spawned through
`python_for(None)` from `des.runtime.interpreter` (NOT raw `sys.executable`), so
the spawn routes through the sanctioned interpreter-resolution boundary -- the
same boundary the build-tier guards (`test_no_inline_interpreter_spawn.py`)
enforce on production code. Python + filesystem only: no git, no external tool.

TWO DISTINCT PLANES (dispatch invariant 3):

  * Plane (a) -- THIS AT's own `.feature` file lives in the real repo, tagged
    `@feature-r3-gate-non-vacuity-build-tier`, so the R3 feature's OWN future
    exit gate resolves it. The AT step modules import THIS composition.
  * Plane (b) -- the SUT invocation targets a SYNTHETIC tmp repo (`tmp_path`)
    with its OWN distinct synthetic feature id (`arch-probe-fixture`): a
    `.feature` tagged `@feature-arch-probe-fixture` whose parent dir holds a
    PASSING test (the CLEAN feature scope), PLUS a `tests/build/`-class arch
    tier that is CLEAN or BROKEN per the scenario. The SUT never resolves the
    AT's own file -- it is pointed at the synthetic `--repo`.

MECHANISM (verified-from-source at HEAD 479adf700, corrected per feature-delta
§6 ADDENDUM -- Form A): the keystone threat is a RUN-TIME architecture invariant.
The real F-D-09 arch gate is a scans-not-imports AST scanner: it reads
`src/des/**` as TEXT and asserts at run-time; it NEVER imports its subject. The
`--feature-id` mode is COLLECT-ONLY (`_collect_scope_worker.py:135`), so it can
NEVER observe a run-time arch failure. The corrected gate (DDD-1 §6.2)
collect-AND-RUNs the arch-invariant set via a `--run` worker branch; a broken
arch tier is therefore seeded as a tier that PASSES COLLECTION and FAILS AT
RUN-TIME (a real `src/des/badmod` violation that no in-scope test imports, plus a
`tests/build/`-class AST scanner that reads it as text and asserts). The fix
makes `_run_arch_invariant_set` run the arch tier -> a RED arch run ->
`FeatureScopeMalformed` reason `arch-invariant-failed` exit 2 (REFUSED). Today
the arch tier is neither run nor collected, so the verdict is
`FeatureScopeCleared` exit 0 -- the RED witness this AT pins.

env-parity (dispatch invariant 9): the subprocess is spawned with
`NWAVE_FRESHNESS=""` + `PIPENV_DONT_LOAD_ENV=1` explicitly, so a `.env`
`NWAVE_FRESHNESS=skip` can never mask the verdict -- the gate runs under its
REAL condition.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.runtime.interpreter import python_for

from .domain_types_slice_01 import (
    ARCH_PROBE_FEATURE_ID,
    FEATURE_SCOPE_CLEARED_EVENT,
    FEATURE_SCOPE_MALFORMED_EVENT,
    PROBE_SLICE_TAG,
    ArchTierState,
    ArchViolationShape,
    FeatureId,
    GateVerdict,
    SliceTag,
)


# The exit code `_mode_feature_scoped` returns when the non-vacuity floor trips
# (it emits `FeatureScopeMalformed` and returns 2). Exit-code-EXACT: any OTHER
# non-zero is a WRONG failure mode, surfaced as GateVerdict.UNEXPECTED.
_GATE_REFUSE_EXIT = 2


@dataclass
class GateRun:
    """The observable outcome of one `des run-contract-gate --feature-id` run."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def verdict(self) -> GateVerdict:
        """How the gate resolved -- derived EXIT-CODE-EXACT (verified-from-source).

        exit 0 -> CLEARED; exit 2 -> REFUSED (non-vacuity floor); any other
        non-zero -> UNEXPECTED, so a refusal assertion never passes for the
        wrong reason (e.g. an argparse error or an uncaught crash).
        """
        if self.exit_code == 0:
            return GateVerdict.CLEARED
        if self.exit_code == _GATE_REFUSE_EXIT:
            return GateVerdict.REFUSED
        return GateVerdict.UNEXPECTED

    @property
    def event(self) -> str:
        """The structured verdict event name on stdout (empty when none parses).

        The SUT emits exactly one single-line JSON object as its verdict
        (`run_contract_gate._emit`). The freshness-autoskip health line may
        precede it; this returns the LAST JSON object that carries an `event`
        key (the verdict), ignoring health chatter.
        """
        found = ""
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "event" in payload:
                event = payload["event"]
                # Skip the freshness-autoskip health line; keep the verdict.
                if isinstance(event, str) and event in (
                    FEATURE_SCOPE_CLEARED_EVENT,
                    FEATURE_SCOPE_MALFORMED_EVENT,
                ):
                    found = event
        return found


@dataclass
class R3GateComposition:
    """Production composition root driving the real `des run-contract-gate` CLI."""

    last_run: GateRun | None = field(default=None)

    # --- fixture builders (synthetic tmp repo; filesystem only, no git) ------

    def make_clean_feature_scope_repo(self, root: Path) -> Path:
        """Materialise a synthetic repo with ONLY a CLEAN feature scope.

        Writes pyproject + the clean `@feature-arch-probe-fixture` scope and NO
        arch tier. The shared clean-feature-scope Given (SSOT in `common_steps`,
        S1) uses this; the subsequent arch Given (slice-specific) then writes the
        arch tier on top. Plane (b): the synthetic repo's feature id is distinct
        from the AT's own, so the SUT never resolves the AT's own file.
        """
        self._write_pyproject(root)
        self._write_clean_feature_scope(root)
        return root

    def make_probe_repo(
        self,
        root: Path,
        arch_tier: ArchTierState,
        violation: ArchViolationShape | None = None,
    ) -> Path:
        """Materialise a synthetic repo with a CLEAN feature scope + arch tier.

        Plane (b): the synthetic repo carries
          * a feature `.feature` tagged `@feature-arch-probe-fixture` + a
            PASSING test under the same dir -- the CLEAN feature scope the gate
            collects today;
          * a `tests/build/` arch tier that is CLEAN (a passing arch test) or
            BROKEN (a collection-time arch violation of the requested shape).

        The feature scope is ALWAYS clean -- the whole point of the keystone is
        that a clean-feature-scope slice must STILL be refused when it breaks
        the arch tier. `arch_tier=BROKEN` requires a `violation` shape.
        """
        self._write_pyproject(root)
        self._write_clean_feature_scope(root)
        if arch_tier is ArchTierState.CLEAN:
            self._write_clean_arch_tier(root)
        else:
            assert violation is not None, "BROKEN arch tier requires a violation shape"
            self._write_broken_arch_tier(root, violation)
        return root

    def _write_pyproject(self, root: Path) -> None:
        """The minimal pytest config so collection over the synthetic repo works."""
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )

    def _write_clean_feature_scope(self, root: Path) -> None:
        """The synthetic feature's CLEAN `.feature` scope (plane b).

        A `.feature` tagged `@feature-arch-probe-fixture` carrying `@slice-01`,
        plus a PASSING test in the same parent dir. This is what
        `_mode_feature_scoped` collects today -- and it is non-vacuous (one
        runnable node-id), so today's verdict is CLEARED.
        """
        scope = root / "tests" / "arch_probe_fixture" / "acceptance"
        scope.mkdir(parents=True, exist_ok=True)
        (scope / "probe.feature").write_text(
            "@feature-arch-probe-fixture\n"
            "Feature: arch probe fixture\n"
            "  @slice-01\n"
            "  Scenario: a clean feature-scope scenario\n"
            "    Given a precondition\n"
            "    When an action occurs\n"
            "    Then an outcome is observed\n"
        )
        (scope / "test_probe.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.acceptance\n"
            "def test_clean_feature_scope():\n"
            "    assert True\n"
        )

    def _write_clean_arch_tier(self, root: Path) -> None:
        """A CLEAN `tests/build/` arch tier -- collects without error."""
        build = root / "tests" / "build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "test_arch_clean.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\n"
            "def test_arch_invariant_holds():\n"
            "    assert True\n"
        )

    def _write_broken_arch_tier(
        self, root: Path, violation: ArchViolationShape
    ) -> None:
        """A BROKEN `tests/build/` arch tier -- a RUN-TIME arch failure (Form A).

        The keystone threat: an architecture-tier test that PASSES COLLECTION and
        FAILS AT RUN-TIME (the scans-not-imports AST gate class). Each shape:

          * seeds a real `src/des/badmod/*.py` carrying the violation that NO
            in-scope test imports (so the worker collects cleanly), AND
          * writes a `tests/build/`-class scanner test that reads `src/des/**`
            as TEXT (`ast.parse` / regex), imports only `ast`/`pathlib`/`re`/
            `pytest` (so it collects cleanly), and `assert`s -- FAILING only when
            it RUNS. This is the exact shape of the real
            `test_des_no_dev_root_imports.py` / `test_no_inline_interpreter_spawn.py`.

        The synthetic scanner carries an EXPLICIT `@pytest.mark.unit` (the real
        repo's `conftest.py:757` auto-marks `tests/build/` -> unit; the synthetic
        tmp repo has no such conftest, so the mark is explicit). The mark is
        LOAD-BEARING: the `--run` worker filters on `-m "unit or integration or
        acceptance"`, so without it the arch set collects zero and the gate
        (correctly) trips the M-1 floor as `arch-scope-zero-collected` instead of
        observing `arch-invariant-failed`.
        """
        build = root / "tests" / "build"
        build.mkdir(parents=True, exist_ok=True)
        des_mod = root / "src" / "des" / "badmod"
        des_mod.mkdir(parents=True, exist_ok=True)
        (des_mod / "__init__.py").write_text("")

        if violation is ArchViolationShape.FORBIDDEN_DEV_ROOT_IMPORT:
            # A real src/des module with a forbidden dev-root import. NO in-scope
            # test imports it -> collection passes. The scanner reads it as TEXT.
            (des_mod / "leaky.py").write_text(
                "from scripts.nonexistent import thing  # forbidden dev-root import\n"
                "\n\ndef use():\n    return thing\n"
            )
            (build / "test_arch_no_dev_root_imports.py").write_text(
                "import ast\n"
                "from pathlib import Path\n"
                "import pytest\n\n"
                "FORBIDDEN_ROOTS = {'scripts', 'tests'}\n\n"
                "@pytest.mark.unit\n"
                "def test_des_has_no_dev_root_imports():\n"
                "    root = Path(__file__).resolve().parent.parent.parent\n"
                "    des_root = root / 'src' / 'des'\n"
                "    violations = []\n"
                "    for mod in sorted(des_root.rglob('*.py')):\n"
                "        tree = ast.parse(mod.read_text(encoding='utf-8'))\n"
                "        for node in ast.walk(tree):\n"
                "            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:\n"
                "                if node.module.split('.', 1)[0] in FORBIDDEN_ROOTS:\n"
                "                    violations.append(f'{mod}:{node.lineno} {node.module}')\n"
                "    assert not violations, 'dev-root imports in src/des: ' + '; '.join(violations)\n"
            )
        elif violation is ArchViolationShape.INLINE_INTERPRETER_SPAWN:
            # A real src/des module with a raw interpreter spawn (F-21 shape).
            (des_mod / "spawner.py").write_text(
                "import subprocess\n\n"
                "def spawn():\n"
                "    subprocess.run(['python3', '-c', 'pass'])  # banned inline spawn\n"
            )
            (build / "test_arch_no_inline_spawn.py").write_text(
                "import ast\n"
                "from pathlib import Path\n"
                "import pytest\n\n"
                "@pytest.mark.unit\n"
                "def test_no_inline_interpreter_spawn_in_des():\n"
                "    root = Path(__file__).resolve().parent.parent.parent\n"
                "    des_root = root / 'src' / 'des'\n"
                "    violations = []\n"
                "    for mod in sorted(des_root.rglob('*.py')):\n"
                "        tree = ast.parse(mod.read_text(encoding='utf-8'))\n"
                "        for node in ast.walk(tree):\n"
                "            if not isinstance(node, ast.Call):\n"
                "                continue\n"
                "            f = node.func\n"
                "            if isinstance(f, ast.Attribute) and f.attr in {'run', 'Popen', 'call'}:\n"
                "                if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)) and node.args[0].elts:\n"
                "                    first = node.args[0].elts[0]\n"
                "                    if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.startswith('python'):\n"
                "                        violations.append(f'{mod}:{node.lineno} {first.value!r}')\n"
                "    assert not violations, 'inline interpreter spawn in src/des: ' + '; '.join(violations)\n"
            )
        else:  # ArchViolationShape.SEEDED_RUNTIME_ASSERTION
            # A generic arch-tier test that collects cleanly and asserts False at
            # run-time -- proving the gate catches the arch tier GENERICALLY.
            (build / "test_arch_seeded_invariant.py").write_text(
                "import pytest\n\n"
                "@pytest.mark.unit\n"
                "def test_seeded_arch_invariant():\n"
                "    # collects cleanly (imports only pytest); fails when RUN\n"
                "    assert False, 'seeded run-time architecture invariant failure'\n"
            )

    # --- driving port: the real `des run-contract-gate` CLI subprocess -------

    def run_feature_scoped_gate(
        self,
        repo: Path,
        feature_id: FeatureId = ARCH_PROBE_FEATURE_ID,
        entering_slice: SliceTag = PROBE_SLICE_TAG,
    ) -> GateRun:
        """Drive `des run-contract-gate --feature-id <f> --entering-slice <s>`.

        Mandate-13 Layer-3 subprocess black-box: spawn the real CLU by module
        (`-m des.cli.run_contract_gate`) and observe ONLY its stdout / stderr /
        exit code. No production gate symbol is imported.

        Genericità (invariant 2): the interpreter is resolved through
        `python_for(None)` (returns `sys.executable` -- the running interpreter
        already has `des` visibility for a `-m des.cli.*` spawn), never trusted
        inline.

        env-parity (invariant 9): `NWAVE_FRESHNESS=""` + `PIPENV_DONT_LOAD_ENV=1`
        are set explicitly so no `.env` freshness mask can fabricate the verdict.
        """
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = ""
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        completed = subprocess.run(
            [
                python_for(None),
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                str(repo),
                "--feature-id",
                str(feature_id),
                "--entering-slice",
                str(entering_slice),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.last_run = GateRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return self.last_run
