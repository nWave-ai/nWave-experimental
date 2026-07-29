"""Regression: `feature_delta_path`-shaped path-join defined FOUR times, not
once (SSOT violation, RCA already run -- see `nw-troubleshooter` output).

Four byte-identical (or near-identical) production definitions of "the
feature-delta.md path for {repo, feature_id}" exist today, instead of one:

* ``src/des/domain/repo_path_resolver.py:38`` ``feature_delta_path`` --
  CANONICAL. 7 real external importers (`carpaccio_slice_gate`,
  `carpaccio_precheck`, `at_review_verdict`, the subagent-stop hook, ...),
  pre-existing SSOT-claiming docstring naming it "Single source of truth".
* ``src/des/domain/feature_delta_source.py:59`` ``feature_delta_path`` --
  duplicate. Zero external callers; only used internally at line 206 of the
  same file (``read_feature_delta``).
* ``src/des/application/deliver_loop_projection.py:401``
  ``_feature_delta_path`` -- duplicate, private. One internal caller at line
  156 of the same file.
* ``src/des/adapters/driven/filesystem/feature_delta_filesystem_reader.py:30``
  ``_delta_path`` -- duplicate, private, with its own local constants
  ``_FEATURE_REL_DIR`` / ``_FEATURE_DELTA_FILE`` mirroring the canonical
  module's.

The fix (crafter's job, NOT this test's): delete definitions 2-4 and make
their call sites import ``des.domain.repo_path_resolver.feature_delta_path``
instead -- files 2 and 4 may alias it under their old private name
(``_feature_delta_path`` / ``_delta_path`` respectively) so their one
internal call site needs no further edit; file 2's ``read_feature_delta``
calls the imported name directly.

Driving surface (Layer 3 composition-root default, whole-tree AST scan):
this is a structural/architecture-test -- the SUT is the repository tree
itself under ``src/`` (production code), scanned via the stdlib ``ast``
module. No CLI subprocess boundary is needed for a pure structural fact.
Precedent: ``tests/des/acceptance/declared_facts/
test_slice_02_reuse_heading_predicate.py``'s
``_module_level_reuse_heading_regex_definitions`` helper -- identical shape
(whole-tree AST scan for a name binding, assert the ONLY file carrying it is
the canonical one), applied here to a *function definition* instead of a
module-level assignment.

RED-for-right-reason: this test needs no new symbol and no runtime guard --
it fails TODAY because 3 offending files genuinely define the duplicate
names, a real ``AssertionError`` against current production code, not an
import/collection error.
"""

from __future__ import annotations

import ast
from pathlib import Path

from des.domain import repo_path_resolver


_REPO_ROOT = Path(repo_path_resolver.__file__).resolve().parents[3]

#: The canonical file -- the ONLY file permitted to define any of the three
#: names below (GDP-8: decide on the PROPERTY -- a function definition
#: binding one of these names -- never a text-pattern designation for it).
_CANONICAL_FILE = Path("src/des/domain/repo_path_resolver.py")

#: The three name spellings the duplicate definitions were found under.
_TARGET_NAMES = frozenset({"feature_delta_path", "_feature_delta_path", "_delta_path"})


def _feature_delta_path_function_definitions(root: Path) -> dict[Path, list[int]]:
    """Every ``.py`` file under ``root`` (src/) defining a function (module-
    level, nested, or method -- any ``FunctionDef``/``AsyncFunctionDef``)
    named one of ``_TARGET_NAMES``, mapped to the line numbers found.

    Pure, AST-based scan -- mirrors the reuse-heading-predicate precedent's
    ``_module_level_reuse_heading_regex_definitions`` shape.
    """
    found: dict[Path, list[int]] = {}
    search_root = root / "src"
    if not search_root.is_dir():
        return found
    for py_file in sorted(search_root.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        lines: list[int] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in _TARGET_NAMES
            ):
                lines.append(node.lineno)
        if lines:
            found[py_file.relative_to(root)] = lines
    return found


def test_feature_delta_path_has_exactly_one_definition_in_the_tree() -> None:
    """Positive AT: the ONLY file under ``src/`` defining
    ``feature_delta_path`` / ``_feature_delta_path`` / ``_delta_path`` must
    be the canonical ``src/des/domain/repo_path_resolver.py``.

    Fails for real today: 3 offending files each define their own copy.
    """
    definitions = _feature_delta_path_function_definitions(_REPO_ROOT)

    assert definitions == {_CANONICAL_FILE: [70]}, (
        "expected exactly ONE feature-delta-path definition in the tree, at "
        f"{_CANONICAL_FILE} -- found definitions in "
        f"{sorted(str(p) for p in definitions)!r} "
        "(SSOT violation: four byte-identical/near-identical production "
        "definitions of the feature-delta.md path-join exist instead of "
        "one). Fix: delete the duplicate definitions in "
        "feature_delta_source.py, deliver_loop_projection.py, and "
        "feature_delta_filesystem_reader.py; make their call sites import "
        "des.domain.repo_path_resolver.feature_delta_path instead (aliased "
        "under the old private name where the module's own call site "
        "expects it)."
    )


def test_offending_duplicate_definitions_never_reappear_outside_canonical_file() -> (
    None
):
    """Negative AT: no file OTHER than the canonical
    ``repo_path_resolver.py`` may ever define
    ``feature_delta_path``/``_feature_delta_path``/``_delta_path`` again --
    the specific regression this bug fixes (a duplicate re-introduced under
    a fourth name/location).

    Fails for real today, naming the 3 concrete offenders.
    """
    definitions = _feature_delta_path_function_definitions(_REPO_ROOT)
    offenders = {
        path: lines for path, lines in definitions.items() if path != _CANONICAL_FILE
    }

    assert offenders == {}, (
        "expected ZERO feature-delta-path-shaped function definitions "
        f"outside {_CANONICAL_FILE} -- found: "
        f"{sorted(str(p) for p in offenders)!r}. "
        "Every call site must import "
        "des.domain.repo_path_resolver.feature_delta_path instead of "
        "re-defining its own copy."
    )
