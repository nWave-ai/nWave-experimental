"""Regression: a citation of a REAL Python class (or module-level constant)
must ground, not be branded a phantom component citation (slice-02,
F-fix-delta-grounding-incapacity-is-indeterminate).

Charter: `docs/feature/fix-delta-grounding-incapacity-is-indeterminate/
feature-delta.md` (slice-02 row).

RCA (feature-delta `[REF] Value`, slice-02): `AstAdapter._atoms()`
(`src/des/adapters/driven/codefact/ast_code_fact_adapter.py:186-214`) builds
its atoms list EXCLUSIVELY from `self._parser.functions_in_module(tree)`
(`src/des/testarch/adapters/python_ast.py:146-160`), which walks the module
for `ast.FunctionDef` / `ast.AsyncFunctionDef` ONLY -- a `ClassDef` or a
module-level `Assign` is never visited. The very same parser already exposes
`module_level_symbols_in_module` (`:350-379`), which DOES report top-level
classes (`kind="class"`) alongside functions -- proving the class-atoms fact
is reachable, just not consumed by `_atoms()`. `_component_citation_is_grounded`
(`src/des/cli/validate_feature_delta.py:859-916`, already three-state after
slice-01) queries `CAPABILITY_ATOMS_IN_FILE` and treats a present-but-
unlisted symbol identically to a genuinely absent one: `"absent"` -> the
caller (`:1044-1052`) emits `VERDICT_UNGROUNDED_REUSE_ANALYSIS` ("phantom
component citation") for a citation naming a class or constant that is
RIGHT THERE in the file. This is sister G-8 one level down: the tier
"searched" but only ever looked at functions -- a category-blindness, not a
genuine absence.

Two-oracle contract (feature-delta `[REF] Architecture & Contract Tests`):
  1. PRESENT non-function symbol (class / module-level constant) in a REAL,
     analyzable `.py` file -> grounds (`VERDICT_STRUCTURALLY_ACCEPTED`), NOT
     `VERDICT_UNGROUNDED_REUSE_ANALYSIS`. ACTIVE-RED today for class and
     module-level-constant; function is the already-GREEN control proving
     the harness and grounding path work end to end.
  2. ABSENT symbol in a file that DOES contain a class, a function, and a
     module-level constant (so the fix's widened atom surface is exercised
     and still correctly finds nothing) -> phantom rejection, UNCHANGED.
     Control pin, green today and after.

Driving port: Layer-3 subprocess CLI boundary (`des validate-feature-delta
--require-reuse-analysis --format=json`) -- the real entry point, mirroring
the sibling slice-01 regression `test_delta_grounding_incapacity_indeterminate.py`
harness idiom (read for the idiom, not imported -- this file is self-
contained per the bugs-regression convention).

@contract-shape:bounded-change (class / module-level-constant oracles): a
citation naming a REAL non-function symbol moves the verdict from
`ungrounded-reuse-analysis` (today, phantom) to `structurally-accepted`
(the fix).

@contract-shape:unbounded-preservation (function / absent oracles): the
already-grounded function path and the genuine-absence rejection path must
NOT regress under the fix.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import (
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNGROUNDED_REUSE_ANALYSIS,
)


def _repo_root() -> Path:
    """`tests/bugs/des/<this file>` is 3 directories under the repo root."""
    return Path(__file__).resolve().parents[3]


def _validator_argv(*args: str) -> list[str]:
    """Build the single-entry-point `python -m des validate-feature-delta`
    argv -- the `des <subcommand>` dispatcher form, never a per-module
    invocation of the CLI's implementation file.
    """
    return [sys.executable, "-m", "des", "validate-feature-delta", *args]


def _validator_env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH so `des.*` is importable in the
    subprocess. `NWAVE_FRESHNESS=skip` opts out of the unrelated startup
    freshness gate (this harness runs with `cwd=<tmp_path>`, a self-
    contained fixture project with no `.git/`).
    """
    env = dict(os.environ)
    src = str(_repo_root() / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def _reuse_analysis_feature_delta(existing_component: str, file_cell: str) -> str:
    """A minimal well-formed-SHAPE Reuse Analysis section citing one row.

    CREATE_NEW with a non-empty Justification keeps the row shape-valid
    (DDD-3) so ONLY the content-grounding check can reject it.
    """
    return (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| `{existing_component}` | `{file_cell}` | none | CREATE_NEW | "
        "fixture row for the class-atoms grounding regression AT |\n"
    )


def _run_require_reuse_analysis(
    project_root: Path, existing_component: str, file_cell: str
) -> tuple[int, dict[str, object]]:
    """Write a tmp feature-delta citing (existing_component, file_cell) under
    `project_root` and invoke the real `des validate-feature-delta
    --require-reuse-analysis --format=json` CLI entry point with
    `cwd=project_root`.
    """
    target = project_root / "feature-delta.md"
    target.write_text(
        _reuse_analysis_feature_delta(existing_component, file_cell),
        encoding="utf-8",
    )
    result = subprocess.run(
        _validator_argv("--require-reuse-analysis", "--format=json", str(target)),
        capture_output=True,
        text=True,
        timeout=30,
        env=_validator_env(),
        cwd=project_root,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


#: A single real, analyzable Python source containing all three symbol
#: kinds this regression cares about: a module-level constant assignment, a
#: class, and a function -- so every oracle (present non-function, present
#: function control, absent) queries the SAME file, isolating the variable
#: under test to the CITED SYMBOL rather than the file shape.
_CITED_MODULE_BODY = (
    "LIMIT = 5\n\n\nclass RealThing:\n    pass\n\n\ndef real_function():\n    pass\n"
)


# ---------------------------------------------------------------------------
# Oracle 1 -- PRESENT non-function symbol: a class or a module-level
# constant, genuinely defined in a real, Python-analyzable file. ACTIVE-RED
# today: `_atoms()` only ever walks `functions_in_module`, so a class or a
# constant is invisible to the grounding check and gets phantom-rejected.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cited_symbol",
    [
        pytest.param("RealThing", id="class"),
        pytest.param("LIMIT", id="module-level-constant"),
    ],
)
def test_present_non_function_symbol_citation_grounds(
    tmp_path: Path, cited_symbol: str
) -> None:
    """A citation of a REAL class / module-level constant in a real,
    Python-analyzable file must ground (`VERDICT_STRUCTURALLY_ACCEPTED`) --
    never `VERDICT_UNGROUNDED_REUSE_ANALYSIS` (phantom component citation).

    ACTIVE-RED at HEAD (both parametrize cases): `AstAdapter._atoms()`
    builds its atoms list from `functions_in_module` only
    (`src/des/testarch/adapters/python_ast.py:146-160`) -- a `ClassDef` or a
    module-level `Assign` is never visited, so the genuinely-present
    `RealThing` class and `LIMIT` constant are indistinguishable from a
    symbol that does not exist at all. This assertion fails for the right
    (business) reason: the gate answers the WRONG verdict, not a crash /
    collection error.
    """
    cited_file = "real_module.py"
    (tmp_path / cited_file).write_text(_CITED_MODULE_BODY, encoding="utf-8")

    exit_code, payload = _run_require_reuse_analysis(tmp_path, cited_symbol, cited_file)
    verdict = payload.get("verdict")
    detail = str(payload.get("detail", ""))

    assert verdict != VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
        f"{cited_symbol!r} is a REAL symbol defined in {cited_file!r} -- the "
        f"Python-AST tier IS capable of this file, it simply never looked at "
        f"non-function atoms. It must never be branded "
        f"{VERDICT_UNGROUNDED_REUSE_ANALYSIS!r} (phantom component "
        f"citation); got verdict={verdict!r}, detail={detail!r}"
    )
    assert verdict == VERDICT_STRUCTURALLY_ACCEPTED, (
        f"a citation of a genuinely-present symbol in an analyzable file "
        f"must ground and structurally accept "
        f"({VERDICT_STRUCTURALLY_ACCEPTED!r}); got verdict={verdict!r}, "
        f"detail={detail!r}"
    )
    assert exit_code == 0, (
        f"a grounded, structurally-accepted Reuse Analysis must exit clean "
        f"(no refusal); got exit_code={exit_code}"
    )


# ---------------------------------------------------------------------------
# Oracle 2 -- PRESENT function symbol: already-GREEN control. Proves the
# harness (subprocess invocation, tmp feature-delta, grounding path) works
# end to end -- the function-atoms surface was never the bug.
# ---------------------------------------------------------------------------


def test_present_function_symbol_citation_already_grounds(tmp_path: Path) -> None:
    """A citation of a REAL function grounds today AND after the fix
    (control pin) -- `functions_in_module` already reports functions; this
    was never the incapacity.
    """
    cited_file = "real_module.py"
    (tmp_path / cited_file).write_text(_CITED_MODULE_BODY, encoding="utf-8")

    exit_code, payload = _run_require_reuse_analysis(
        tmp_path, "real_function", cited_file
    )

    assert payload.get("verdict") == VERDICT_STRUCTURALLY_ACCEPTED, (
        "a real function symbol in an analyzable file must ground and "
        f"structurally accept; got verdict={payload.get('verdict')!r}"
    )
    assert exit_code == 0, (
        f"a grounded, structurally-accepted Reuse Analysis must exit clean "
        f"(no refusal); got exit_code={exit_code}"
    )


# ---------------------------------------------------------------------------
# Oracle 3 -- ABSENT: a symbol genuinely not defined anywhere in a file that
# DOES contain a constant, a class, and a function (so the fix's widened
# atom surface is exercised and still correctly finds nothing). Byte-for-
# byte UNCHANGED by the fix -- genuine absence still gets the phantom
# rejection. GREEN today AND after (control pin).
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_absent_symbol_still_rejects_absent_symbol_as_phantom(tmp_path: Path) -> None:
    """A citation of a symbol GENUINELY ABSENT from a real, Python-
    analyzable file stays `ungrounded-reuse-analysis` (phantom) --
    byte-for-byte class-identical to today's behavior -- even though the
    same file DOES contain a constant, a class, and a function (proving the
    fix's widened atom surface still correctly reports absence, not a
    false positive).
    """
    cited_file = "real_module.py"
    (tmp_path / cited_file).write_text(_CITED_MODULE_BODY, encoding="utf-8")

    exit_code, payload = _run_require_reuse_analysis(
        tmp_path, "NeverDefinedAnywhereInThisModule", cited_file
    )

    assert payload.get("verdict") == VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
        "a symbol genuinely absent from a Python-analyzable file (the AST "
        "tier IS capable here, and reports a constant/class/function for "
        "the same file) must stay phantom-rejected; got "
        f"verdict={payload.get('verdict')!r}"
    )
    assert exit_code != 0, (
        f"a phantom citation must still REFUSE the feature-delta; got "
        f"exit_code={exit_code}"
    )
