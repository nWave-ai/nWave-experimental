"""A pytest verification says WHICH product files it imported, not just that its
argv names test paths.

MEASURED (run 34, 2026-09-06 03:45; same class run 27).  The examiner refused
candidate 6a8e46cde because two of its three causes "are only exercised inside
pytest runs of test modules whose touches_test_paths is true".  That oracle
drives `des.cli.code_fact.main` in-process: it exercises the product.  The
orchestrator verified the three causes by hand and integrated -- one whole run
and a manual integration spent on a bit that is true for EVERY pytest argv.

Run 24 is the control in the other direction: a declared verification that drove
a stand-in module under the subject's own test tree and imported no product
byte.  The same measurement separates them, and neither answer is a verdict
(`boundary:software-measures-model-decides`).
"""

from __future__ import annotations

import sys
from pathlib import Path

from des.application.delivery_continuation import DeliveryContinuationRunner
from des.domain.exercised_modules import INDETERMINATE, MEASURED


PYPROJECT = (
    '[project]\nname = "native-evidence-subject"\nversion = "0.0.0"\n'
    'requires-python = ">=3.10"\n'
    '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
)

# This is the complete frozen lock for the fixture's dependency-free project.
# Pytest remains supplied by the executing test environment linked below.
UV_LOCK = """version = 1
revision = 3
requires-python = ">=3.10"

[[package]]
name = "native-evidence-subject"
version = "0.0.0"
source = { virtual = "." }
"""

#: The subject ships no installed package, exactly like run 24's: a test reaches
#: its import through `sys.path`, which is why WHERE it reached is the fact.
DRIVES_PRODUCT = (
    "import sys\n"
    "\n"
    "sys.path.insert(0, 'src')\n"
    "\n"
    "from product.value import VALUE\n"
    "\n"
    "\n"
    "def test_value():\n"
    "    assert VALUE == 1\n"
)

DRIVES_STAND_IN = (
    "import sys\n"
    "\n"
    "sys.path.insert(0, 'tests')\n"
    "\n"
    "from support import VALUE\n"
    "\n"
    "\n"
    "def test_value():\n"
    "    assert VALUE == 1\n"
)


def _subject(tmp_path: Path, test_body: str) -> Path:
    root = tmp_path / "subject"
    (root / "src" / "product").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (root / "uv.lock").write_text(UV_LOCK, encoding="utf-8")
    # The disposable project has no dependencies of its own.  Give uv its local
    # project environment from the current test runtime so `uv run pytest`
    # executes the actual command without resolving packages under UV_FROZEN.
    (root / ".venv").symlink_to(
        Path(sys.executable).parent.parent, target_is_directory=True
    )
    (root / "src" / "product" / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "support.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests" / "test_value.py").write_text(test_body, encoding="utf-8")
    return root


def _one(evidence: object):
    assert isinstance(evidence, tuple), evidence
    assert len(evidence) == 1, evidence
    return evidence[0]


def test_a_pytest_run_that_drives_the_product_names_the_module_it_imported(
    tmp_path: Path,
) -> None:
    root = _subject(tmp_path, DRIVES_PRODUCT)

    evidence = DeliveryContinuationRunner()._native(
        root,
        (("pytest", "tests/test_value.py", "-q"),),
        root,
        changed=("src/product/value.py",),
    )

    item = _one(evidence)
    assert item.exit_status == 0, item
    assert item.touches_test_paths is True, item
    assert item.exercised.measure == MEASURED, item
    assert "src/product/value.py" in (item.exercised.paths or ()), item.exercised
    assert item.exercised.changed_targets == ("src/product/value.py",), item.exercised


def test_an_uv_run_pytest_that_drives_the_product_names_the_module_it_imported(
    tmp_path: Path,
) -> None:
    """The declared ``uv run pytest`` shape receives the same session probe."""
    root = _subject(tmp_path, DRIVES_PRODUCT)

    evidence = DeliveryContinuationRunner()._native(
        root,
        (("uv", "run", "pytest", "tests/test_value.py", "-q"),),
        root,
        extra_env={
            "UV_CACHE_DIR": str(root / ".uv-cache"),
            "UV_NO_SYNC": "1",
        },
        changed=("src/product/value.py",),
    )

    item = _one(evidence)
    assert item.exit_status == 0, item
    assert item.exercised.measure == MEASURED, item
    assert item.exercised.changed_targets == ("src/product/value.py",), item.exercised


def test_a_pytest_run_that_drives_only_a_stand_in_names_no_product_module(
    tmp_path: Path,
) -> None:
    """Run 24's shape: the same true `touches_test_paths`, an empty exercise."""
    root = _subject(tmp_path, DRIVES_STAND_IN)

    evidence = DeliveryContinuationRunner()._native(
        root,
        (("pytest", "tests/test_value.py", "-q"),),
        root,
        changed=("src/product/value.py",),
    )

    item = _one(evidence)
    assert item.exit_status == 0, item
    assert item.touches_test_paths is True, item
    assert item.exercised.measure == MEASURED, item
    assert item.exercised.paths == (), item.exercised
    assert item.exercised.changed_targets == (), item.exercised


def test_a_pytest_session_that_never_finished_is_indeterminate_not_empty(
    tmp_path: Path,
) -> None:
    """LOUD, GDP-6: an empty list here would claim the run imported nothing."""
    root = _subject(tmp_path, DRIVES_PRODUCT)

    evidence = DeliveryContinuationRunner()._native(
        root, (("pytest", "--no-such-option"),), root, changed=()
    )

    item = _one(evidence)
    assert item.exit_status not in (0, None), item
    assert item.exercised.measure == INDETERMINATE, item
    assert item.exercised.paths is None, item.exercised
    assert item.exercised.changed_targets is None, item.exercised


def test_a_command_that_is_not_pytest_carries_no_exercise_claim(
    tmp_path: Path,
) -> None:
    root = _subject(tmp_path, DRIVES_PRODUCT)

    evidence = DeliveryContinuationRunner()._native(
        root, (("python", "-c", "print(1)"),), root, changed=()
    )

    item = _one(evidence)
    assert item.exit_status == 0, item
    assert item.exercised.measure == "not-applicable", item
    assert item.exercised.paths is None, item.exercised


def test_the_evidence_record_delivers_all_three_facts(tmp_path: Path) -> None:
    """The judging roles read a record, not a dataclass."""
    root = _subject(tmp_path, DRIVES_PRODUCT)

    evidence = DeliveryContinuationRunner()._native(
        root,
        (("pytest", "tests/test_value.py", "-q"),),
        root,
        changed=("src/product/value.py",),
    )
    assert isinstance(evidence, tuple)

    record = DeliveryContinuationRunner._evidence_records(evidence)[0]
    assert record["touches_test_paths"] is True, record
    assert record["exercised_measure"] == MEASURED, record
    assert "src/product/value.py" in record["exercised_product_modules"], record
    assert record["exercised_changed_targets"] == ("src/product/value.py",), record
