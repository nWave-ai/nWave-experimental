"""Composition root for the future-slice-scaffold collection-scope slice.

Feature: fix-carpaccio-future-slice-scaffold-blocks-commit (C3, cohort S).

Wires the PRODUCTION E2 contract gate -- ``des.cli.run_contract_gate.main`` via
its ``--feature-id`` / ``--entering-slice`` feature-scoped path
(``_mode_feature_scoped``, run_contract_gate.py:1356) -- against a HERMETIC
fixture feature tree built under pytest ``tmp_path``. Layer 3 (subprocess / FS
acceptance): the driving port is ``run_contract_gate.main``; the only driven
port is the real filesystem under ``tmp_path``. Example-only, no PBT machinery
(Mandate 9/11).

CRITICAL fixture discipline (the exact bug class this feature fixes): the
multi-slice fixture feature (slice-01 + the slice-02 active-RED scaffold) lives
ENTIRELY under ``tmp_path`` -- it is NEVER authored as a real
``tests/**/*.feature`` in THIS repo, so it cannot pollute the real suite the
gate collects. The composition builds and (via ``tmp_path`` teardown) discards
the fixture tree.

The fixture is a self-contained, importable mini-package: each slice ships a
real pytest-bdd ``.feature`` + binding so the gate's child collection worker
(``python_for("pytest")`` over the scope dirs) collects genuine node-ids. The
slice-01 binding PASSES; the slice-02 binding raises ``AssertionError`` (an
active-RED scaffold -- the future slice's impl is missing), so when the gate
wrongly RUNS slice-02 it reds and the gate refuses (exit 2). When the gate is
scoped to shipped+entering (the fix) it never collects/runs slice-02 -> exit 0.

Business logic lives here as the single source of truth; step bodies delegate
to ``FutureSliceScaffoldComposition`` methods and never inline logic
(Mandate-12 criterion 3).

Regression contract (atdd_pure active-RED): AC-1/AC-2 FAIL at HEAD because
``_mode_feature_scoped`` collects the whole feature scope (the slice-02 node is
collected and RUN -> exit 2 / present in the collected set). They PASS once the
gate scopes its collection to shipped+entering slices.
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.run_contract_gate import main as run_contract_gate_main

from .domain_types import FeatureId, SliceId, SliceShape


# The fixture feature id its `.feature` files self-identify with via the
# `@feature-<id>` file-level tag (the gate's `_feature_tag_files` resolver
# discovers files by this tag). DISTINCT from THIS AT's own feature id so the
# fixture is unambiguously a hermetic sub-tree, not the real feature.
_FIXTURE_FEATURE_ID = FeatureId("demo-multislice-fixture")

_SLICE_01 = SliceId("slice-01")
_SLICE_02 = SliceId("slice-02")


def _feature_text(feature_id: FeatureId, slice_id: SliceId, scenario: str) -> str:
    """A real Gherkin `.feature` carrying the file-level + per-scenario tags."""
    return (
        f"@feature-{feature_id}\n"
        f"Feature: {feature_id} {slice_id} capability\n"
        f"\n"
        f"  @{slice_id}\n"
        f"  Scenario: {scenario}\n"
        f"    Given the {slice_id} precondition holds\n"
        f"    When the {slice_id} capability runs\n"
        f"    Then the {slice_id} outcome is observed\n"
    )


def _slice01_binding_text(feature_rel: str) -> str:
    """pytest-bdd binding for slice-01 -- a GREEN (shipped) scenario.

    Carries ``pytestmark = pytest.mark.acceptance`` so the contract gate's
    child collection worker (``-m "unit or integration or acceptance"``)
    selects it. The hermetic fixture tree has no directory-based auto-marking
    conftest, so the marker is applied explicitly.
    """
    return (
        "import pytest\n"
        "from pytest_bdd import scenarios, given, when, then\n"
        "\n"
        "pytestmark = pytest.mark.acceptance\n"
        "\n"
        f"scenarios({feature_rel!r})\n"
        "\n"
        '@given("the slice-01 precondition holds")\n'
        "def _given() -> None:\n"
        "    pass\n"
        "\n"
        '@when("the slice-01 capability runs")\n'
        "def _when() -> None:\n"
        "    pass\n"
        "\n"
        '@then("the slice-01 outcome is observed")\n'
        "def _then() -> None:\n"
        "    assert True\n"
    )


def _slice02_scaffold_binding_text(feature_rel: str) -> str:
    """pytest-bdd binding for slice-02 -- an ACTIVE-RED scaffold (impl missing).

    The future slice. Its scenario RUNS and raises ``AssertionError`` (the
    atdd_pure active-RED contract: future-slice ATs are absent OR active-RED,
    never ``@skip``). The fix must NOT collect this node into the
    entering-slice-01 scope -- the future slice's scenario must be EXCLUDED from
    the collected set. The body raises ``AssertionError`` so that if any future
    leg RUNS it (rather than merely collecting it) the active-RED nature is
    visible too.
    """
    return (
        "import pytest\n"
        "from pytest_bdd import scenarios, given, when, then\n"
        "\n"
        "pytestmark = pytest.mark.acceptance\n"
        "\n"
        f"scenarios({feature_rel!r})\n"
        "\n"
        '@given("the slice-02 precondition holds")\n'
        "def _given() -> None:\n"
        "    pass\n"
        "\n"
        '@when("the slice-02 capability runs")\n'
        "def _when() -> None:\n"
        "    pass\n"
        "\n"
        '@then("the slice-02 outcome is observed")\n'
        "def _then() -> None:\n"
        '    raise AssertionError("slice-02 not yet implemented (active-RED scaffold)")\n'
    )


@dataclass
class GateRun:
    """Observable outcome of one feature-scoped E2 contract-gate evaluation."""

    exit_code: int
    output: str

    @property
    def collected_node_count(self) -> int | None:
        """The number of node-ids the gate's feature-scope collection covered.

        Parsed from the gate's ``FeatureScopeCleared`` event
        (``collected_node_ids``). This is the observable that tells whether a
        not-yet-entered future-slice node was pulled into the entering slice's
        scope: at HEAD the whole feature scope is collected (the future-slice
        node is counted); the fix narrows it to the shipped+entering set. ``None``
        when no clear event was emitted (the gate refused before recording it).
        """
        return _parse_collected_node_count(self.output)

    @property
    def collected_slices(self) -> frozenset[str]:
        """The set of `@slice-NN` tags the gate's collection covered.

        Parsed from the gate's structured events. GREEN requires the scoped
        collection to RECORD its per-slice membership (``collected_slice_tags``)
        AND to exclude the future slice. At HEAD the field is unemitted, so this
        returns the empty set -- the include-assertion (entering slice present)
        reds for the right reason: the gate does not yet emit a scoped slice set.
        """
        return _parse_collected_slices(self.output)


@dataclass
class FutureSliceScaffoldComposition:
    """Production-wired composition over a hermetic tmp_path fixture feature tree.

    ``root`` is a tmp_path directory used as the ``--repo`` the gate scopes. The
    fixture feature's ``.feature`` + bindings are written under
    ``root/tests/<fixture>/`` so the gate's ``@feature-`` resolver discovers
    them and its child collection worker collects them -- all hermetic.
    """

    root: Path
    _feature_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self._feature_dir = self.root / "tests" / "demo_multislice"

    # --- Given: build the hermetic fixture feature tree ----------------------

    def build_fixture_tree(self, shape: SliceShape) -> None:
        """Author the hermetic fixture feature tree for the requested shape.

        NON_FINAL_WITH_FUTURE_RED -- slice-01 GREEN + slice-02 active-RED
            scaffold, both on disk under ``tmp_path``.
        FINAL_SINGLE              -- slice-01 only (the final/single slice).
        """
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        (self._feature_dir / "__init__.py").write_text("", encoding="utf-8")
        (self._feature_dir / "conftest.py").write_text("", encoding="utf-8")
        self._author_slice01()
        if shape is SliceShape.NON_FINAL_WITH_FUTURE_RED:
            self._author_slice02_scaffold()

    def _author_slice01(self) -> None:
        feature = self._feature_dir / "slice_01.feature"
        feature.write_text(
            _feature_text(
                _FIXTURE_FEATURE_ID, _SLICE_01, "the slice-01 capability ships"
            ),
            encoding="utf-8",
        )
        (self._feature_dir / "test_slice_01.py").write_text(
            _slice01_binding_text("slice_01.feature"), encoding="utf-8"
        )

    def _author_slice02_scaffold(self) -> None:
        feature = self.future_slice_feature_path
        feature.write_text(
            _feature_text(
                _FIXTURE_FEATURE_ID, _SLICE_02, "the slice-02 capability ships"
            ),
            encoding="utf-8",
        )
        (self._feature_dir / "test_slice_02.py").write_text(
            _slice02_scaffold_binding_text("slice_02.feature"), encoding="utf-8"
        )

    @property
    def future_slice_feature_path(self) -> Path:
        """The slice-02 (future) `.feature` file inside the fixture tree."""
        return self._feature_dir / "slice_02.feature"

    # --- When: drive the production E2 contract gate (driving port) ----------

    def run_contract_gate_for(self, entering_slice: SliceId) -> GateRun:
        """Drive the REAL ``run_contract_gate.main`` feature-scoped path.

        The same surface ``verify_slice_commit._run_contract_gate`` spawns: the
        E2 feature-scoped contract gate, scoped by ``--entering-slice``.
        """
        exit_code, output = self._invoke_cli(
            run_contract_gate_main,
            [
                "--repo",
                str(self.root),
                "--feature-id",
                str(_FIXTURE_FEATURE_ID),
                "--entering-slice",
                str(entering_slice),
            ],
        )
        return GateRun(exit_code=exit_code, output=output)

    # --- universe capture (Mandate 8) ----------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The fix lives in the GATE, not in the AT files: running the gate must
        NOT mutate the future-slice ``.feature`` file (no ``@skip`` token
        added). The universe is the future-slice file's text content -- the
        observable the no-skip-pollution invariant constrains.
        """
        return {
            "future_slice.feature_text": self._read_future_slice_text(),
        }

    def _read_future_slice_text(self) -> str:
        path = self.future_slice_feature_path
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def future_slice_has_skip_marker(self) -> bool:
        """Whether the future-slice `.feature` carries a `@skip`/`@pending` tag."""
        text = self._read_future_slice_text().lower()
        return "@skip" in text or "@pending" in text

    # --- low-level helper ----------------------------------------------------

    @staticmethod
    def _invoke_cli(entry, argv: list[str]) -> tuple[int, str]:
        """Invoke a CLI ``main(argv)`` capturing exit code + combined output."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = entry(argv)
        return exit_code, buffer.getvalue()


def _parse_collected_slices(output: str) -> frozenset[str]:
    """Extract the set of `@slice-NN` tags the gate's collection covered.

    The gate emits JSON events line-by-line. ``FeatureScopeCleared`` carries the
    scoped collection's slice membership (``collected_slice_tags``); a refusal
    payload carries the whole-feature ``collected_slice_tags`` it scanned. Falls
    back to an empty set when no event carries the field (the gate refused
    before recording it -- treated as 'scope unobservable').
    """
    tags: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = event.get("collected_slice_tags")
        if isinstance(raw, list):
            tags |= {str(item) for item in raw}
    return frozenset(tags)


def _parse_collected_node_count(output: str) -> int | None:
    """Extract ``collected_node_ids`` from the gate's FeatureScopeCleared event."""
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "FeatureScopeCleared":
            raw = event.get("collected_node_ids")
            if isinstance(raw, int):
                return raw
    return None
