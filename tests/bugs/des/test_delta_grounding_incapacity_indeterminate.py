"""Regression: `--require-reuse-analysis` grounding INCAPACITY must be
INDETERMINATE, never the phantom/ungrounded verdict (Sister G-8,
F-fix-delta-grounding-incapacity-is-indeterminate).

Charter: `docs/feature/fix-delta-grounding-incapacity-is-indeterminate/
feature-delta.md`.

RCA (feature-delta `[REF] Value`): `_component_citation_is_grounded`
(`src/des/cli/validate_feature_delta.py:848-880`) queries `CodeFactChain` for
`CAPABILITY_ATOMS_IN_FILE` and collapses the result to a bare `bool` --
discarding WHY no atom matched. Its single caller (`:992`) maps `False` to
`VERDICT_UNGROUNDED_REUSE_ANALYSIS` ("phantom component citation"). On a
Python-only floor tier, a citation naming a file NO tier can analyze (a
non-Python source -- `.rs`, `.ts`, ...) always yields an empty atoms list --
identical to a citation whose symbol is genuinely absent from a REAL,
analyzable file. Both collapse to the SAME "invented" verdict today: "I
searched and it isn't there" (genuine absence) is indistinguishable from "I
don't know how to look" (incapacity) -- the #126 silent-wrong class one level
up, empirically confirmed on a pure-Rust dogfood repo (sister Tsunami,
2026-07-12, G-8): every feature-delta there, including shipped/attested
features, gets branded with phantom citations.

Fix direction (feature-delta `[REF] Design reference`, NOT implemented here):
`_component_citation_is_grounded` widens from `bool` to a three-state
outcome (grounded / absent / incapacity) derived from the tier's reason. The
caller maps incapacity to the module's OWN existing indeterminate/degrade-LOUD
precedent -- `VERDICT_INDETERMINATE` (`GateVerdict.INDETERMINATE.value`,
already bound in this module for the registry-sections check's identical
"unreadable input, refuse to fabricate a verdict" case,
`src/des/cli/validate_feature_delta.py:1255,2147`) -- rather than a brand
new bespoke token; "absent" keeps `VERDICT_UNGROUNDED_REUSE_ANALYSIS`
verbatim.

Three-oracle contract (feature-delta `[REF] Architecture & Contract Tests`):
  1. INCAPACITY (no capable tier for the cited file's kind) -> INDETERMINATE,
     detail names WHAT could not be analyzed. ACTIVE-RED today.
  2. ABSENT (capable tier, symbol genuinely missing) -> phantom rejection,
     BYTE-FOR-BYTE UNCHANGED. Control pin, green today and after.
  3. MISSING FILE (citation names a file that does not exist) -> phantom
     rejection, UNCHANGED (a missing file is absence, not incapacity).
     Control pin, green today and after.

Driving port: Layer-3 subprocess CLI boundary (`des validate-feature-delta
--require-reuse-analysis --format=json`) -- the real entry point the fix
wires the widened grounding onto, mirroring the existing
`TestReuseAnalysisContentGrounding` harness idiom in
`tests/des/unit/cli/test_validate_feature_delta.py`. `project_root` (the
`Existing Component | File` resolution base, `Path.cwd()` at
`src/des/cli/validate_feature_delta.py:1729`) is `tmp_path` itself here --
every cited file is a self-contained fixture, no dependency on real repo
non-Python source.

@contract-shape:bounded-change (incapacity oracle): a citation naming a
real-but-incapable-tier file moves the verdict from `ungrounded-reuse-
analysis` (today, phantom) to `indeterminate` (the fix).

@contract-shape:unbounded-preservation (absent / missing-file oracles): the
genuine-absence and missing-file rejection paths must NOT regress under the
fix.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import (
    VERDICT_INDETERMINATE,
    VERDICT_STRUCTURALLY_ACCEPTED,
    VERDICT_UNGROUNDED_REUSE_ANALYSIS,
)


def _repo_root() -> Path:
    """`tests/bugs/des/<this file>` is 3 directories under the repo root."""
    return Path(__file__).resolve().parents[3]


def _validator_argv(*args: str) -> list[str]:
    """Build the single-entry-point `python -m des validate-feature-delta` argv
    -- the `des <subcommand>` dispatcher form (AT-07 / single-entry-point tree
    rule), never a per-module invocation of the CLI's implementation file.
    """
    return [sys.executable, "-m", "des", "validate-feature-delta", *args]


def _validator_env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH so `des.*` is importable in the subprocess.

    `NWAVE_FRESHNESS=skip` opts out of the unrelated `des.runtime.freshness`
    startup gate (`src/des/runtime/freshness.py` §1.8) -- that gate's dev-
    checkout autoskip keys off CWD `.git/` adjacency, and this harness
    intentionally runs with `cwd=<tmp_path>` (a self-contained fixture
    project, no `.git/`) so `Existing Component | File` citations resolve
    against fixtures the regression owns, never real repo files. Without the
    opt-out the CLI exits 78 (EX_CONFIG) before it ever reaches the grounding
    logic under test.
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
    (DDD-3) so ONLY the content-grounding check can reject it -- isolating
    the regression from every pre-existing shape check (mirrors
    `tests/des/unit/cli/test_validate_feature_delta.py
    _reuse_analysis_feature_delta`).
    """
    return (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| `{existing_component}` | `{file_cell}` | none | CREATE_NEW | "
        "fixture row for the grounding-incapacity regression AT |\n"
    )


def _run_require_reuse_analysis(
    project_root: Path, existing_component: str, file_cell: str
) -> tuple[int, dict[str, object]]:
    """Write a tmp feature-delta citing (existing_component, file_cell) under
    `project_root` and invoke the real `des validate-feature-delta
    --require-reuse-analysis --format=json` CLI entry point with
    `cwd=project_root` -- the SAME resolution base the SUT uses via
    `Path.cwd()` (`src/des/cli/validate_feature_delta.py:1729`), so a
    `project_root`-relative `File` cell grounds exactly as production does.
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


# ---------------------------------------------------------------------------
# Oracle 1 -- INCAPACITY: no capable tier for the cited file's kind.
# ACTIVE-RED today: the AST tier's parse failure on a non-Python file is
# swallowed into an empty atoms list, indistinguishable from genuine absence
# -- the gate answers `ungrounded-reuse-analysis` (phantom), not indeterminate.
# ---------------------------------------------------------------------------

#: Content that is a REAL, plausible source file in its own language but is
#: NOT valid Python syntax -- `ast.parse` raises `SyntaxError` on each,
#: caught by `AstAdapter._parse` and swallowed to an empty atoms list
#: (`src/des/adapters/driven/codefact/ast_code_fact_adapter.py:379-395`).
#: The Python-AST tier is INCAPABLE of this file kind, not merely
#: "found nothing" -- exactly the incapacity class the fix distinguishes.
_INCAPACITY_FIXTURES: dict[str, str] = {
    ".rs": ("pub enum EmptyReason {\n    NoElements,\n    AllFiltered,\n}\n"),
    ".ts": ("export enum EmptyReason {\n    NoElements,\n    AllFiltered,\n}\n"),
}


@pytest.mark.parametrize("suffix", sorted(_INCAPACITY_FIXTURES))
def test_incapacity_citation_yields_indeterminate_verdict(
    tmp_path: Path, suffix: str
) -> None:
    """A citation of a REAL symbol in a REAL but non-Python file (no capable
    CodeFactPort tier for that file kind) must be INDETERMINATE -- never
    branded a phantom/invented citation.

    ACTIVE-RED at HEAD: `_component_citation_is_grounded` only ever queries
    the Python-AST tier via `CAPABILITY_ATOMS_IN_FILE`; a non-Python file's
    parse fails and is swallowed to an empty atoms list, so ANY citation on
    a non-Python file -- including this genuinely REAL `EmptyReason` symbol
    -- is rejected `ungrounded-reuse-analysis` ("phantom component
    citation"). This assertion fails for the right (business) reason: the
    gate answers the WRONG verdict, not a crash / collection error.
    """
    cited_file = f"cited_module{suffix}"
    (tmp_path / cited_file).write_text(_INCAPACITY_FIXTURES[suffix], encoding="utf-8")

    exit_code, payload = _run_require_reuse_analysis(
        tmp_path, "EmptyReason", cited_file
    )
    verdict = payload.get("verdict")
    detail = str(payload.get("detail", ""))

    assert verdict != VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
        f"a {suffix} citation is a grounding INCAPACITY (no CodeFactPort "
        f"tier can analyze that file kind) -- it is NOT an absence, and must "
        f"never be branded {VERDICT_UNGROUNDED_REUSE_ANALYSIS!r} (phantom "
        f"component citation); got verdict={verdict!r}, detail={detail!r}"
    )
    assert verdict != VERDICT_STRUCTURALLY_ACCEPTED, (
        "an incapable-to-ground citation must not be silently accepted "
        f"either (degrade-LOUD, never a fabricated pass); got "
        f"verdict={verdict!r}"
    )
    assert verdict == VERDICT_INDETERMINATE, (
        f"expected the module's own indeterminate/degrade-LOUD verdict "
        f"({VERDICT_INDETERMINATE!r} -- the SAME token this file already "
        f"binds for its registry-sections 'unreadable input' case, "
        f"src/des/cli/validate_feature_delta.py:1255,2147); got "
        f"verdict={verdict!r}, detail={detail!r}"
    )
    assert "phantom" not in detail.lower(), (
        f"the incapacity detail must not use phantom/invented language "
        f"(that framing is reserved for genuine absence); got detail={detail!r}"
    )
    assert cited_file in detail, (
        f"the incapacity detail must name WHAT could not be analyzed (the "
        f"cited file, so a reader knows where to look); got detail={detail!r}"
    )
    assert exit_code != 0, (
        "an indeterminate grounding outcome still refuses the feature-delta "
        f"(non-zero exit -- degrade-LOUD, never a silent pass); got "
        f"exit_code={exit_code}"
    )


# ---------------------------------------------------------------------------
# Oracle 2 -- ABSENT: a capable tier finds no matching atom. Byte-for-byte
# UNCHANGED by the fix -- genuine absence still gets the phantom rejection.
# GREEN today AND after (control pin).
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_absent_symbol_on_capable_tier_still_rejects_as_phantom(
    tmp_path: Path,
) -> None:
    """A citation of a symbol GENUINELY ABSENT from a real, Python-
    analyzable file stays `ungrounded-reuse-analysis` (phantom) --
    byte-for-byte class-identical to today's behavior. A capable tier that
    searched and found nothing is absence, not incapacity; the fix must not
    weaken this path.
    """
    real_module = tmp_path / "real_module.py"
    real_module.write_text("def real_function():\n    pass\n", encoding="utf-8")

    exit_code, payload = _run_require_reuse_analysis(
        tmp_path, "NeverDefinedAnywhereInThisModule", "real_module.py"
    )

    assert payload.get("verdict") == VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
        "a symbol genuinely absent from a Python-analyzable file (the AST "
        "tier IS capable here) must stay phantom-rejected; got "
        f"verdict={payload.get('verdict')!r}"
    )
    assert exit_code != 0, (
        f"a phantom citation must still REFUSE the feature-delta; got "
        f"exit_code={exit_code}"
    )


# ---------------------------------------------------------------------------
# Oracle 3 -- MISSING FILE: the cited file does not exist at all. Byte-for-
# byte UNCHANGED by the fix -- a missing file is absence, not incapacity.
# GREEN today AND after (control pin).
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_missing_file_citation_still_rejects_as_phantom(tmp_path: Path) -> None:
    """A citation naming a file that does not exist at all stays
    `ungrounded-reuse-analysis` -- unchanged. The oracle's third negative:
    a missing file is absence (nothing to analyze because there is no file),
    never incapacity (which presupposes a real file of an unsupported kind).
    """
    exit_code, payload = _run_require_reuse_analysis(
        tmp_path, "AnySymbol", "does_not_exist_anywhere.py"
    )

    assert payload.get("verdict") == VERDICT_UNGROUNDED_REUSE_ANALYSIS, (
        "a citation of a file that does not exist must stay phantom-"
        "rejected (missing file = absence, never incapacity); got "
        f"verdict={payload.get('verdict')!r}"
    )
    assert exit_code != 0, (
        f"a phantom citation must still REFUSE the feature-delta; got "
        f"exit_code={exit_code}"
    )
