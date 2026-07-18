"""Regression: ``composition*.py`` glob in ``_item_depends_on_real_repo`` is a
PREFIX match — it misses sibling modules whose name merely *contains*
``composition`` rather than *starting with* it.

RCA (verified by EXECUTING the real predicate, not by re-implementing it):
``tests/conftest.py:1407`` --

    for path in sorted(test_dir.glob("composition*.py")):

``Path.glob("composition*.py")`` only matches filenames that START with the
literal ``composition``. The repo's own convention in
``tests/des/acceptance/sustainable-test-suite/acceptance/steps/`` produces
``slice_02_composition.py``, ``slice_03_composition.py`` etc. -- composition
modules whose name has a ``slice_NN_`` PREFIX before ``composition``. The
glob's own directory scan never matches them; only the bare ``composition.py``
sibling is found. When such a slice-prefixed composition module drives a
``cwd=<real repo>`` subprocess, the test module sitting next to it never gets
pinned onto the ``real_repo_scan`` xdist group -- exposing it to the exact
worker-race the pin exists to prevent.

FIX SHAPE (do not satisfy this test any other way):

1. The correct fix widens the glob pattern from ``composition*.py`` to
   ``*composition*.py`` (substring match instead of prefix match). Adding the
   specific filenames observed in the real repo (``slice_02_composition.py``,
   ...) to a hardcoded allowlist would make THIS test pass while leaving the
   underlying class of bug open for the next differently-named sibling --
   that is the instance-vs-class mistake this test exists to catch. This test
   uses filenames the production code has never seen (``zz_composition_x.py``
   under a throwaway ``tmp_path`` tree) specifically so a hardcoded-filename
   "fix" CANNOT pass it.
2. The fix must NOT make the predicate return True more broadly in general
   (e.g. "any directory with a .py file", or "always True"). This test
   contains a NEGATIVE assertion: a sibling module whose name also contains
   ``composition`` but which does NOT drive a ``cwd=<real repo>`` subprocess
   must still yield ``False``. An over-broad fix that ignores file *content*
   would pass the positive half and silently over-serialize the whole test
   suite onto one xdist worker -- the exact wall-time regression the human
   has been trying to avoid all day.
3. ``_real_repo_item_cache`` / ``_real_repo_file_cache`` are MODULE-LEVEL
   memoization caches keyed by ``Path``. This test drives the UNCACHED
   ``_compute_item_depends_on_real_repo`` directly (not the memoized
   ``_item_depends_on_real_repo`` wrapper) specifically so repeated calls in
   the same process cannot read a stale cached answer from a prior test/run;
   as an extra guard it also clears both caches before each call and uses
   distinct ``tmp_path`` subtrees for the positive/negative fixtures so no
   path can collide across assertions.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import (
    _compute_item_depends_on_real_repo,
    _real_repo_file_cache,
    _real_repo_item_cache,
)


def _build_fixture_dir(tmp_path: Path, name: str, composition_body: str) -> Path:
    """Create ``<tmp_path>/<name>/`` holding a plain test module plus a
    slice-prefixed ``*composition*.py`` sibling (mirrors the real repo's
    ``.../acceptance/steps/slice_NN_composition.py`` layout: the composition
    module lives directly alongside the test module, not nested one level
    deeper -- that is exactly the layout the current prefix-only glob misses).
    """
    fixture_dir = tmp_path / name
    fixture_dir.mkdir()

    test_module = fixture_dir / "test_something.py"
    test_module.write_text(
        "def test_noop():\n    assert True\n",
        encoding="utf-8",
    )

    composition_module = fixture_dir / "zz_composition_x.py"
    composition_module.write_text(composition_body, encoding="utf-8")

    return test_module


def test_slice_prefixed_composition_sibling_with_real_repo_cwd_is_detected(
    tmp_path: Path,
) -> None:
    """Positive half: a *composition*.py sibling that DOES drive a
    cwd=<real repo> subprocess must be detected even though its filename does
    not START with "composition".
    """
    test_module = _build_fixture_dir(
        tmp_path,
        "positive",
        "import subprocess\n"
        "from pathlib import Path\n"
        "_REPO_ROOT = Path(__file__).resolve().parents[5]\n"
        "\n"
        "\n"
        "def drive():\n"
        '    subprocess.run(["true"], cwd=str(_REPO_ROOT))\n',
    )

    _real_repo_item_cache.clear()
    _real_repo_file_cache.clear()

    assert _compute_item_depends_on_real_repo(test_module) is True, (
        "predicate must detect the cwd=<real repo> marker living in a "
        "slice-prefixed *composition*.py sibling (zz_composition_x.py), "
        "not just a file literally named composition.py"
    )


def test_composition_sibling_without_real_repo_cwd_marker_is_not_detected(
    tmp_path: Path,
) -> None:
    """Negative half: a *composition*.py sibling that does NOT drive a
    cwd=<real repo> subprocess must still yield False. Guards against an
    over-broad fix (e.g. "any composition-named file present" or "always
    True") that would over-serialize the suite onto one xdist worker.
    """
    test_module = _build_fixture_dir(
        tmp_path,
        "negative",
        "import subprocess\n"
        "\n"
        "\n"
        "def drive(tmp_path):\n"
        '    subprocess.run(["true"], cwd=tmp_path)\n',
    )

    _real_repo_item_cache.clear()
    _real_repo_file_cache.clear()

    assert _compute_item_depends_on_real_repo(test_module) is False, (
        "predicate must NOT flag a composition-ish sibling that has no "
        "cwd=<real repo> marker -- an over-broad fix would over-serialize "
        "the whole suite onto one xdist worker"
    )
