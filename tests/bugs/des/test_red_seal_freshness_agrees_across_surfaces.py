"""Regression guard for the N2 consolidation (fix-runner-helpers-dedup):
the red-seal freshness predicate ("is this `RedObserved` seal still fresh for
this regression file?") now lives ONCE, as the PUBLIC
`des.cli.verify_red_green.red_seal_fresh(repo, regression_test_file) -> bool`
(verify_red_green.py:230). Before the consolidation the same body existed
twice under different private names -- `carpaccio_format._red_seal_is_fresh`
and `carpaccio_slice_gate._red_seal_fresh` -- both already reusing this
module's `_seal_path`/`_content_sha` via aliasing, and a THIRD call-site
(`verify_readiness_pre_dispatch.py`'s `_pytest_regression_seal_clears_
ownership`) importing one of the two copies. That is gone now: both
`carpaccio_format.py` and `carpaccio_slice_gate.py` import and call
`red_seal_fresh` directly (no local wrapper), and `verify_readiness_pre_
dispatch.py` imports it directly too.

Root cause the consolidation closed: a "mirror <sibling>" authoring norm with
no paired extract-the-invariant obligation -- a blind spot the repo's only
prior anti-duplication guard (`test_no_duplicate_emit_json_helper.py`) did
not cover, because it was keyed to ONE previously-burned body shape in ONE
directory rather than to the PROPERTY "the SAME logic must not exist twice
under different names."

Two axes, BOTH pinned here as a GREEN regression guard (not a RED witness --
the consolidation already landed; this file protects it from silently
re-duplicating):

  1. STRUCTURAL: the freshness predicate's BODY -- an alpha-renamed,
     docstring-stripped AST normal form, never a name -- must exist EXACTLY
     ONCE across `src/des/cli/verify_red_green.py` +
     `src/des/cli/carpaccio_format.py` + `src/des/cli/carpaccio_slice_gate.py`
     (the narrow, RCA-named scope; this is NOT a repo-wide duplicate-body
     detector -- other lanes may concurrently be deduplicating other things
     and a general detector would go red on their in-flight work). Keying on
     the alpha-renamed AST shape rather than either retired name means a
     future re-duplication is caught even if it lands under a brand-new
     name: a crafter "fixing" one call-site by re-inlining the freshness
     logic (instead of importing `red_seal_fresh`) would push the hit count
     to 2 and fail this test, regardless of what they call the reintroduced
     copy.

  2. BEHAVIOURAL: probing the SAME sealed file through the three real `des`
     CLI surfaces that consume this fact --
       (a) `des verify-red-green --verify-green` (the canonical tamper check
           `_verify_green` owns, sharing `_seal_path`/`_content_sha` with
           `red_seal_fresh`),
       (b) `des carpaccio-slice-gate` (assertion 5's mechanical-seal escape,
           `_mechanical_seal_satisfied` -> `red_seal_fresh`),
       (c) `des verify-readiness-pre-dispatch` (the `scenario_slice_tags`
           invariant's regression-seal escape -> `red_seal_fresh`)
     -- must AGREE, and must DISCRIMINATE (fresh while untouched, stale the
     instant the SAME sealed file's content changes, unaffected by an
     unrelated file's edit). This is the safety net that keeps the single
     PUBLIC locus behaviour-preserving across all three consumers: a future
     edit that repoints one call-site to a stub, or diverges its semantics
     from the shared predicate, fails here even if the structural check
     above still reports exactly one body. `docs/product/expectations/
     fix-runner-helpers-dedup/red-seal-freshness-agrees-across-surfaces.md`
     is the charter this serves.

Driving surface (Mandate 13, driving-port-only, Layer 3 in-process default):
the REAL `des.cli.verify_red_green.main`, `des.cli.carpaccio_slice_gate.main`
and `des.cli.verify_readiness_pre_dispatch.main` CLI EDGES, driven in-process
via `tests.common.in_process_cli.run_cli_in_process` -- the shared driver
`test_readiness_no_longer_duplicates_carpaccio_at_review_block.py` already
uses for this exact pair of gates.
"""

from __future__ import annotations

import ast
import copy
import sys
import textwrap
from pathlib import Path

from des.cli import (
    carpaccio_slice_gate,
    verify_readiness_pre_dispatch,
    verify_red_green,
)
from tests.common.in_process_cli import run_cli_in_process


# ---------------------------------------------------------------------------
# 1. STRUCTURAL -- the freshness predicate's body must exist exactly once.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
_SCOPE_FILES = (
    "src/des/cli/verify_red_green.py",
    "src/des/cli/carpaccio_format.py",
    "src/des/cli/carpaccio_slice_gate.py",
)

# Frozen from the CURRENT real body -- the single PUBLIC locus
# `des.cli.verify_red_green.red_seal_fresh` (verify_red_green.py:230) -- under
# a SYNTHETIC reference name (`_reference_red_seal_freshness_shape`) and using
# the module's own internal names (`_red_green_seal_path`, `_red_seal_content_
# sha`) rather than the production identifiers (`_seal_path`, `_content_sha`),
# so the comparison below can never be satisfied by matching a name the
# production source happens to carry. Only the alpha-renamed, docstring-
# stripped SHAPE is compared -- verified structurally identical to the real
# `red_seal_fresh` body because both sets of identifiers are plain `ast.Name`
# nodes and normalize to the same positional placeholders.
_REFERENCE_SRC = """
def _reference_red_seal_freshness_shape(repo: Path, regression_test_file: Path) -> bool:
    try:
        seal = _red_green_seal_path(repo.resolve(), regression_test_file.resolve())
    except ValueError:
        return False
    if not seal.is_file():
        return False
    try:
        record = json.loads(seal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, dict):
        return False
    outcomes = record.get("outcomes")
    if not isinstance(outcomes, dict) or "fail" not in outcomes.values():
        return False
    try:
        current_sha = _red_seal_content_sha(regression_test_file)
    except OSError:
        return False
    return record.get("content_sha256") == current_sha
"""


def _normal_form(func: ast.FunctionDef) -> str:
    """Alpha-rename every identifier (function name, parameter, local, and
    except-handler name) to a positional placeholder, strip a leading
    docstring, and dump the resulting tree.

    Two functions differing only in WHAT they call their variables (or their
    own name) collapse to the identical string; attribute/method names
    (`.resolve`, `.is_file`, `.get`, ...) and literal constants (`"outcomes"`,
    `"fail"`, `"content_sha256"`) are left untouched because THOSE carry the
    logic, never the naming choice a crafter happened to make.
    """
    func = copy.deepcopy(func)
    mapping: dict[str, str] = {}

    def alias(name: str) -> str:
        return mapping.setdefault(name, f"_id{len(mapping)}")

    class _Renamer(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            node.name = alias(node.name)
            self.generic_visit(node)
            return node

        def visit_arg(self, node: ast.arg) -> ast.AST:
            node.arg = alias(node.arg)
            return node

        def visit_Name(self, node: ast.Name) -> ast.AST:
            node.id = alias(node.id)
            return node

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
            if node.name:
                node.name = alias(node.name)
            self.generic_visit(node)
            return node

    _Renamer().visit(func)

    if (
        func.body
        and isinstance(func.body[0], ast.Expr)
        and isinstance(func.body[0].value, ast.Constant)
        and isinstance(func.body[0].value.value, str)
    ):
        func.body = func.body[1:]

    return ast.dump(func, annotate_fields=False)


def _reference_normal_form() -> str:
    tree = ast.parse(textwrap.dedent(_REFERENCE_SRC))
    (func,) = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    return _normal_form(func)


def _matching_functions_in(path: Path, reference: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _normal_form(node) == reference:
            hits.append(f"{path.relative_to(REPO_ROOT)}:{node.name}")
    return hits


def test_red_seal_freshness_predicate_exists_exactly_once_in_scope():
    """GREEN today, guarding the N2 consolidation: the freshness predicate's
    shape exists exactly ONCE now, as `verify_red_green.red_seal_fresh`,
    across the narrow, RCA-named scope. The property is keyed on the
    alpha-renamed AST shape, never on a name -- so it stays a real detector
    if a future edit re-duplicates the logic under ANY new name (e.g. a
    call-site "fixed" by re-inlining the check instead of importing
    `red_seal_fresh`), not just the two retired names this guarded against
    (`carpaccio_format._red_seal_is_fresh`, `carpaccio_slice_gate.
    _red_seal_fresh`).
    """
    reference = _reference_normal_form()
    hits: list[str] = []
    for rel in _SCOPE_FILES:
        hits.extend(_matching_functions_in(REPO_ROOT / rel, reference))

    assert len(hits) == 1, (
        "the red-seal freshness predicate (seal-path resolve -> is_file -> "
        "json.loads -> outcomes/'fail' membership -> content-sha compare) "
        f"must exist EXACTLY ONCE across {_SCOPE_FILES}; found "
        f"{len(hits)} AST-identical (alpha-renamed) cop{'y' if len(hits) == 1 else 'ies'}: "
        f"{hits}. Move it to ONE public locus (`des.cli.verify_red_green."
        "red_seal_fresh`) and repoint every call-site to import it, rather "
        "than mirroring it under a second name."
    )


# ---------------------------------------------------------------------------
# 2. BEHAVIOURAL -- the three real `des` surfaces must agree, and the
#    agreement must DISCRIMINATE fresh vs stale (never a vacuous pass).
#    GREEN today (the two current copies are functionally identical) -- this
#    is the regression pin the crafter's refactor must keep satisfying.
# ---------------------------------------------------------------------------

_FEATURE_ID = "fix-runner-helpers-dedup-red-seal-freshness"
_SLICE_ID = "slice-01"
_SIBLING_SLICE_ID = "slice-02"
_REGRESSION_REL = "tests/regression/test_red_seal_freshness_fixture.py"

_REGRESSION_SRC = (
    "def test_behavior_applies():\n"
    "    assert True\n"
    "\n"
    "\n"
    "def test_behavior_rejects_bad_input():\n"
    "    assert True\n"
)

_XML_RED = (
    "<testsuite>"
    '<testcase classname="fixture" name="test_behavior_applies">'
    '<failure message="red"/></testcase>'
    '<testcase classname="fixture" name="test_behavior_rejects_bad_input"/>'
    "</testsuite>"
)
_XML_GREEN = (
    "<testsuite>"
    '<testcase classname="fixture" name="test_behavior_applies"/>'
    '<testcase classname="fixture" name="test_behavior_rejects_bad_input"/>'
    "</testsuite>"
)

_CARPACCIO_AT_REVIEW_REJECTED_EXIT = 45
_VERIFY_RED_GREEN_EXIT_OK = 0
_VERIFY_RED_GREEN_EXIT_REFUSED = 1


def _canned_runner(tmp_path: Path, xml: str, tag: str) -> str:
    """A ``--run-cmd`` that copies canned JUnit XML to ``{junit_out}`` --
    same idiom as ``test_red_green_duplicate_testcase_false_pass.py``, no
    pytest-in-pytest."""
    xml_src = tmp_path / f"canned_{tag}.xml"
    xml_src.write_text(xml, encoding="utf-8")
    copier = tmp_path / f"copier_{tag}.py"
    copier.write_text(
        "import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n",
        encoding="utf-8",
    )
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _write_feature_delta(repo: Path) -> None:
    path = repo / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Feature Delta: red-seal freshness fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_SLICE_ID} | Freshness verdict agrees across the seal-consuming "
        "surfaces | pending | | |\n",
        encoding="utf-8",
    )


def _write_sibling_scenario(repo: Path) -> None:
    """A `.feature` file for the SAME feature, tagged to a SIBLING slice
    (`slice-02`, never `slice-01`). This is load-bearing: it makes
    `verify_readiness_pre_dispatch`'s `scenario_slice_tags` invariant a real,
    non-vacuous check for slice-01 (with zero `.feature` files at all, the
    invariant's own vacuous-truth fallback would report `satisfied=True`
    regardless of seal freshness, defeating discrimination) while leaving
    carpaccio's `--at-kind pytest-regression` path for slice-01 entirely
    unaffected (it skips its own Gherkin-scenario discovery for that mode).
    """
    path = repo / "tests" / "acceptance" / _FEATURE_ID / "sibling.feature"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: Sibling slice keeps its own scenario ownership\n\n"
        f"  @{_SIBLING_SLICE_ID}\n"
        "  Scenario: sibling slice owns its own scenario\n"
        "    Given a sibling slice exists\n"
        "    When slice-01 is evaluated for scenario ownership\n"
        "    Then this scenario stays attributed to the sibling slice only\n",
        encoding="utf-8",
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _write_feature_delta(repo)
    _write_sibling_scenario(repo)
    regression = repo / _REGRESSION_REL
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(_REGRESSION_SRC, encoding="utf-8")
    return repo


def _seal_red(repo: Path, tmp_path: Path) -> None:
    exit_code, out, err = run_cli_in_process(
        [
            "--repo",
            str(repo),
            "--test-file",
            _REGRESSION_REL,
            "--record-red",
            "--run-cmd",
            _canned_runner(tmp_path, _XML_RED, "red"),
        ],
        cwd=repo,
        main=verify_red_green.main,
    )
    assert exit_code == _VERIFY_RED_GREEN_EXIT_OK, (
        f"fixture setup failed to seal RED: exit={exit_code}, out={out!r}, err={err!r}"
    )


def _parse_last_json(stdout: str, stderr: str) -> dict[str, object]:
    """The last well-formed JSON object across stdout+stderr -- some of
    these gates co-emit on stderr, mirrors `test_readiness_no_longer_
    duplicates_carpaccio_at_review_block.py`."""
    for chunk in (stdout, stderr):
        for line in reversed(chunk.splitlines()):
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                import json

                return json.loads(stripped)
            except Exception:
                continue
    return {}


def _verify_green_exit(repo: Path, tmp_path: Path) -> int:
    exit_code, _out, _err = run_cli_in_process(
        [
            "--repo",
            str(repo),
            "--test-file",
            _REGRESSION_REL,
            "--verify-green",
            "--run-cmd",
            _canned_runner(tmp_path, _XML_GREEN, "green"),
        ],
        cwd=repo,
        main=verify_red_green.main,
    )
    return exit_code


def _carpaccio_verdict(repo: Path) -> tuple[int, dict[str, object]]:
    exit_code, out, err = run_cli_in_process(
        [
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _SLICE_ID,
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            _REGRESSION_REL,
        ],
        cwd=repo,
        main=carpaccio_slice_gate.main,
    )
    return exit_code, _parse_last_json(out, err)


def _readiness_scenario_tags_satisfied(repo: Path) -> bool:
    _exit_code, out, err = run_cli_in_process(
        [
            "--feature-id",
            _FEATURE_ID,
            "--slice-id",
            _SLICE_ID,
            "--repo-root",
            str(repo),
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            _REGRESSION_REL,
        ],
        cwd=repo,
        main=verify_readiness_pre_dispatch.main,
    )
    report = _parse_last_json(out, err)
    invariants = {
        inv["id"]: inv
        for inv in report.get("invariants", [])  # type: ignore[union-attr]
    }
    tag_invariant = invariants.get("scenario_slice_tags")
    assert tag_invariant is not None, (
        "the readiness gate must always report a scenario_slice_tags "
        f"invariant -- report={report!r}, out={out!r}, err={err!r}"
    )
    return bool(tag_invariant["satisfied"])


def _probe_all(repo: Path, tmp_path: Path) -> dict[str, bool]:
    """One synchronized probe of the SAME sealed file through the three
    surfaces, at ONE point in the repo's history."""
    carpaccio_exit, carpaccio_payload = _carpaccio_verdict(repo)
    carpaccio_fresh = (
        carpaccio_exit == 0
        and carpaccio_payload.get("at_evidence") == "mechanical-seal"
    )
    readiness_fresh = _readiness_scenario_tags_satisfied(repo)
    verify_green_fresh = _verify_green_exit(repo, tmp_path) == _VERIFY_RED_GREEN_EXIT_OK
    return {
        "carpaccio": carpaccio_fresh,
        "readiness": readiness_fresh,
        "verify_green": verify_green_fresh,
        "_carpaccio_exit": carpaccio_exit,
        "_carpaccio_payload": carpaccio_payload,
    }


def test_every_surface_refuses_a_stale_seal_and_agrees_when_it_is_fresh(
    tmp_path: Path,
) -> None:
    """WITNESS (GREEN today -- the safety net for the refactor):

    1. Right after sealing RED, untouched, ALL THREE surfaces report the
       seal fresh for the regression file.
    2. Editing an UNRELATED file leaves all three verdicts unchanged (still
       fresh) -- the fact is bound to the SEALED FILE's content, never to
       "something in the repo changed."
    3. Editing the SAME sealed file's content flips all three verdicts to
       stale/refused, together -- never just one or two.
    4. The untouched-vs-edited states are genuinely DIFFERENT across every
       surface (the discrimination check: a fixture reporting the same
       verdict regardless of whether the file was touched is a vacuous
       pass, not a real probe).
    """
    repo = _make_repo(tmp_path)
    _seal_red(repo, tmp_path)

    # --- 1. untouched: all three fresh, and they AGREE with each other ---
    fresh_state = _probe_all(repo, tmp_path)
    assert fresh_state["carpaccio"] is True, (
        "carpaccio-slice-gate must report the untouched seal fresh "
        f"(mechanical-seal clear): {fresh_state['_carpaccio_payload']!r}"
    )
    assert fresh_state["readiness"] is True, (
        "verify-readiness-pre-dispatch's scenario_slice_tags invariant must "
        "report the untouched seal fresh"
    )
    assert fresh_state["verify_green"] is True, (
        "verify-red-green --verify-green must SEAL on the untouched file"
    )

    # --- 2. unrelated edit: verdicts for the SEALED file must not move ---
    (repo / "UNRELATED.md").write_text("noise unrelated to the sealed file\n")
    unrelated_edit_state = _probe_all(repo, tmp_path)
    assert unrelated_edit_state["carpaccio"] is True, (
        "editing an unrelated file must not flip carpaccio's verdict for "
        f"the untouched sealed file: {unrelated_edit_state['_carpaccio_payload']!r}"
    )
    assert unrelated_edit_state["readiness"] is True, (
        "editing an unrelated file must not flip readiness's verdict for "
        "the untouched sealed file"
    )
    assert unrelated_edit_state["verify_green"] is True, (
        "editing an unrelated file must not flip verify-red-green's verdict "
        "for the untouched sealed file"
    )

    # --- 3. edit the SEALED file itself: all three must flip to stale ---
    regression = repo / _REGRESSION_REL
    regression.write_text(
        regression.read_text(encoding="utf-8") + "\n# behavior-preserving edit\n",
        encoding="utf-8",
    )
    stale_state = _probe_all(repo, tmp_path)
    assert stale_state["carpaccio"] is False, (
        "carpaccio-slice-gate must refuse the mechanical-seal escape once "
        f"the sealed file's content changed: {stale_state['_carpaccio_payload']!r}"
    )
    assert stale_state["_carpaccio_exit"] == _CARPACCIO_AT_REVIEW_REJECTED_EXIT, (
        "a stale seal with no recorded ATReviewVerdict must hard-refuse "
        f"(exit {_CARPACCIO_AT_REVIEW_REJECTED_EXIT}): "
        f"exit={stale_state['_carpaccio_exit']}, payload={stale_state['_carpaccio_payload']!r}"
    )
    assert stale_state["readiness"] is False, (
        "verify-readiness-pre-dispatch's scenario_slice_tags invariant must "
        "refuse once the sealed file's content changed (the regression-seal "
        "escape must not apply, and the sibling-slice-only .feature file "
        "means the ordinary ownership leg genuinely has zero matching "
        "scenarios for slice-01)"
    )
    assert stale_state["verify_green"] is False, (
        "verify-red-green --verify-green must REFUSE (tamper semantics) "
        "once the sealed file's content changed"
    )

    # --- 4. discrimination: untouched vs same-file-edited must DIFFER ---
    for surface in ("carpaccio", "readiness", "verify_green"):
        assert fresh_state[surface] != stale_state[surface], (
            f"{surface} reported the SAME verdict ({fresh_state[surface]!r}) "
            "both before and after editing the sealed file's content -- the "
            "probe is not discriminating fresh from stale, which makes any "
            "'they agree' assertion vacuous"
        )
