"""Regression -- the missing-manifest-path branch of
``validate_component_manifest`` emits a bare Python traceback instead of a
WHAT/WHY/HOW diagnostic naming the resolved repo root.

THE DEFECT is the ASYMMETRY between two branches of the SAME command:

* YAML that parses but is not a manifest (schema-invalid) -> exit 2, with
  exemplary NAMED messages: ``manifest is malformed: 'schema-version' is a
  required property`` (likewise ``'feature-id'`` and
  ``'unbounded-input-domains'``) -- confirmed empirically against this
  worktree's own CLI before authoring this file.
* A NON-EXISTENT path -> exit 1, with a BARE ``FileNotFoundError`` traceback
  out of ``pathlib.Path.read_text`` -- no WHAT, no WHY, no HOW, and no naming
  of the repo root the path was actually resolved against. Also confirmed
  empirically (see the RCA note below).

That second branch is the one an operator meets FIRST in cross-worktree
dispatch, where a RELATIVE manifest path resolves against the wrong repo
root (this worktree's own dispatch envelope carries a ``DES-PROJECT-ROOT``
marker precisely because relative-path-resolves-against-wrong-tree is a
recurring class of bug in this codebase). No message today names which repo
root the CLI actually resolved the path against, so the actual cause is
invisible from the CLI's own output.

RCA (confirmed empirically, ``scripts/cli/validate_component_manifest.py``):
``validate_manifest()`` calls ``manifest_path.read_text(encoding="utf-8")``
with no existence check and no ``try/except`` around it -- a non-existent
path raises ``FileNotFoundError``, uncaught, all the way out of ``main()``,
producing Python's default uncaught-exception traceback on stderr and exit
code 1 (Python's default for an uncaught exception -- not a deliberate exit
code chosen by this CLI).

Driving surface (Mandate-13 driving-port-only, Layer 3 subprocess): both
tests invoke the REAL CLI as a subprocess (``python -m
scripts.cli.validate_component_manifest``), exactly as
``ComponentManifestComposition.run_validate_cli`` does for the sibling
slice-01 acceptance set -- never the internal ``validate_manifest()``
function directly.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass -- ``scripts/cli/validate_component_manifest.py`` is untouched.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


# Repo root -- the five-level-up parent of this file
# (tests/scripts/cli/component_manifest/steps/test_validator_missing_file_message.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]

_MISSING_RELATIVE_PATH = "docs/feature/some-feature/design/component-manifest.yaml"


@dataclass(frozen=True)
class CliResult:
    """Observable result of one validate_component_manifest invocation."""

    exit_code: int
    stdout: str
    stderr: str


def _run_validate_cli(manifest_arg: str, *, cwd: Path) -> CliResult:
    """Invoke the REAL validate_component_manifest CLI as a subprocess.

    ``cwd`` is parametrised (never pinned to ``_REPO_ROOT``) so a test can
    reproduce the cross-worktree dispatch shape the bug report names: a
    RELATIVE manifest path resolved against whichever tree the process
    happened to be spawned in.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cli.validate_component_manifest",
            manifest_arg,
        ],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return CliResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


# ---------------------------------------------------------------------------
# 1. POSITIVE (the defect) -- missing path emits WHAT/WHY/HOW + resolved root.
# ---------------------------------------------------------------------------


def test_missing_manifest_path_emits_what_why_how(tmp_path: Path) -> None:
    """POSITIVE AT (active-RED today): a non-existent manifest path must
    produce a self-explaining diagnostic -- never a bare Python traceback --
    naming (1) the missing path, (2) WHY the manifest gate needs it, (3) a
    concrete remediation, and (4) the RESOLVED REPO ROOT the CLI actually
    used to interpret the (relative) path -- the real cause of this bug
    class is almost always resolution against the wrong tree, and no
    message says so today. Exit code stays 1 (not 2), so missing and
    malformed remain distinguishable branches.

    Reproduces the cross-worktree shape: the manifest path is RELATIVE and
    the CLI is spawned with ``cwd`` set to a tree that is deliberately NOT
    this repo (``wrong_root``) -- exactly the situation a dispatch whose
    relative path resolves against the wrong worktree root would hit.
    """
    wrong_root = tmp_path / "wrong-worktree"
    wrong_root.mkdir()

    result = _run_validate_cli(_MISSING_RELATIVE_PATH, cwd=wrong_root)

    # The core symptom: a bare traceback is not a diagnostic. This is the
    # first assertion to fail today.
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the validator crashed with a bare Python traceback instead of "
        "refusing the missing path with a WHAT/WHY/HOW diagnostic "
        f"(exit {result.exit_code}); stderr:\n{result.stderr}"
    )

    # Missing vs malformed must stay distinguishable exit codes.
    assert result.exit_code == 1, (
        "a non-existent manifest path must exit 1 (distinguishable from "
        f"the malformed-manifest exit 2); got {result.exit_code}: "
        f"{result.stderr}"
    )

    message = result.stderr

    # (1) WHAT -- names the path that could not be found.
    assert _MISSING_RELATIVE_PATH in message, (
        "the diagnostic must name the missing path (WHAT) so the operator "
        f"does not have to re-derive it: stderr:\n{message}"
    )

    # (2) WHY -- explains the manifest gate needs this file.
    assert re.search(r"manifest", message, re.IGNORECASE), (
        f"the diagnostic must explain WHY (the manifest gate needs this "
        f"file): stderr:\n{message}"
    )
    assert re.search(r"(gate|valid|require|need)", message, re.IGNORECASE), (
        f"the diagnostic must state WHY the manifest is required, not just "
        f"name the path: stderr:\n{message}"
    )

    # (3) HOW -- a concrete remediation, not a stack frame.
    assert re.search(
        r"(create|write|author|run|generate|check)", message, re.IGNORECASE
    ), f"the diagnostic must offer a concrete remediation (HOW): stderr:\n{message}"

    # (4) The RESOLVED REPO ROOT actually used -- the point of this bug
    # report: the real cause is almost always resolution against the wrong
    # tree, and no message names it today.
    assert str(wrong_root) in message, (
        "the diagnostic must name the RESOLVED DIRECTORY the CLI actually "
        "used to interpret the path -- this is the missing piece that "
        "would let an operator recognise a cross-worktree resolution "
        f"mistake: expected {wrong_root!s} to appear in stderr:\n{message}"
    )

    # The label attached to the resolved directory must not overclaim:
    # nothing here verifies that directory is actually a repository root,
    # so it must not be labelled "repo root" -- only that it is the
    # current working directory the path was resolved against.
    assert "resolved against repo root" not in message, (
        "the diagnostic must not label the unverified resolved directory "
        "as a 'repo root' -- it is only the current working directory: "
        f"stderr:\n{message}"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE ORACLE -- the malformed branch must stay untouched by the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_malformed_manifest_still_names_properties_and_exits_2(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (must not regress): the fix for the missing-path branch
    must NOT flatten both branches into one generic message. A YAML
    document that PARSES but is not a valid manifest must keep exiting 2
    and keep emitting its own exemplary named-property diagnostics
    (confirmed empirically pre-fix) -- this is what makes the positive AT
    above a specification of the missing-path branch specifically, rather
    than a smoke test that would also pass if both branches were merged.
    """
    manifest = tmp_path / "component-manifest.yaml"
    manifest.write_text("{}\n", encoding="utf-8")

    result = _run_validate_cli(str(manifest), cwd=_REPO_ROOT)

    assert result.exit_code == 2, (
        "a YAML document that parses but is not a valid manifest must "
        f"still exit 2 (malformed); got {result.exit_code}: {result.stderr}"
    )
    for expected in (
        "manifest is malformed: 'schema-version' is a required property",
        "manifest is malformed: 'feature-id' is a required property",
        "manifest is malformed: 'unbounded-input-domains' is a required property",
    ):
        assert expected in result.stderr, (
            "the malformed branch must keep emitting its own named-property "
            f"diagnostic {expected!r} unchanged by the missing-path fix: "
            f"stderr:\n{result.stderr}"
        )
    assert "Traceback (most recent call last)" not in result.stderr, (
        "the malformed branch must remain a clean refusal, never a crash: "
        f"stderr:\n{result.stderr}"
    )
