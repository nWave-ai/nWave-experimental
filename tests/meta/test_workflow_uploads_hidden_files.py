"""An artifact upload whose file is dot-prefixed must opt into hidden files.

`actions/upload-artifact` has excluded hidden files by default since v4.4. A
dot-prefixed path therefore uploads NOTHING unless the step sets
`include-hidden-files: true` -- and, with the default `if-no-files-found: warn`,
does so while reporting success.

Measured on CI run 31100008623: all four test shards passed and uploaded their
allure, html-report and test-results artifacts (none dot-prefixed), while zero
`coverage-data-*` artifacts existed. `coverage-combine` then failed with
"Couldn't combine from non-existent path 'coverage-data'" -- naming the combine
job, not the four shards that had silently produced nothing. Because the combine
job only runs when every shard passes, the defect stayed invisible on this
branch behind unrelated red tests for many commits.

This test reads the workflow YAML rather than running a workflow, which is
normally weak evidence. It is legitimate here because the property under test IS
a property of the YAML: `include-hidden-files` is upload-artifact's configuration
surface, not a proxy for behaviour that lives somewhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

#: One `- uses: actions/upload-artifact...` step and the `with:` block after it.
#: Deliberately a line scan rather than a YAML parse: PyYAML is not a runtime
#: dependency of this repository, and the GitHub expression syntax in these
#: files is not the concern here.
_STEP_START = re.compile(r"^\s*-\s+(name|uses):\s")
_UPLOAD_USES = re.compile(r"^\s*uses:\s*actions/upload-artifact@")


def _upload_steps(text: str) -> list[list[str]]:
    """Split a workflow into the line blocks of its upload-artifact steps."""
    lines = text.splitlines()
    steps: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if _STEP_START.match(line):
            if current is not None and any(_UPLOAD_USES.match(x) for x in current):
                steps.append(current)
            current = [line]
            continue
        if current is not None:
            current.append(line)
    if current is not None and any(_UPLOAD_USES.match(x) for x in current):
        steps.append(current)
    return steps


def _uploaded_paths(step: list[str]) -> list[str]:
    """Every path the step uploads, including the block-scalar `path: |` form."""
    paths: list[str] = []
    in_block = False
    for line in step:
        stripped = line.strip()
        if in_block:
            if stripped and not stripped.startswith("#") and ":" not in stripped:
                paths.append(stripped)
                continue
            in_block = False
        if stripped.startswith("path:"):
            value = stripped[len("path:") :].strip()
            if value in {"|", ">", "|-", ">-"}:
                in_block = True
            elif value:
                paths.append(value)
    return paths


def _is_hidden(path: str) -> bool:
    """True when the uploaded file's own name begins with a dot.

    Only the BASENAME matters: a dot-directory in the middle of the path is a
    different exclusion story, and this test refuses to claim more than the one
    failure mode it has actually observed.
    """
    basename = path.rstrip("/").rsplit("/", 1)[-1]
    return basename.startswith(".")


def _workflow_files() -> list[Path]:
    return sorted(_WORKFLOWS.glob("*.yml")) + sorted(_WORKFLOWS.glob("*.yaml"))


def test_the_scan_finds_the_uploads_it_claims_to_check() -> None:
    """Guard the guard: a regex that silently matches nothing always passes.

    Without this, a workflow reformat that breaks `_upload_steps` turns the real
    assertion below into a vacuous pass -- the exact shape of the defect this
    file exists to catch.
    """
    total = sum(
        len(_upload_steps(f.read_text(encoding="utf-8"))) for f in _workflow_files()
    )

    assert total >= 5, (
        f"the upload-artifact scan found only {total} steps across "
        f"{len(_workflow_files())} workflows; the scan is broken, not the workflows"
    )

    ci = _WORKFLOWS / "ci.yml"
    hidden = [
        p
        for step in _upload_steps(ci.read_text(encoding="utf-8"))
        for p in _uploaded_paths(step)
        if _is_hidden(p)
    ]
    assert hidden, (
        "ci.yml no longer uploads any dot-prefixed artifact. If the coverage "
        "data file was deliberately renamed off the hidden-file path, delete "
        "this test with that reason -- do not weaken it into a vacuous pass."
    )


@pytest.mark.parametrize("workflow", _workflow_files(), ids=lambda p: p.name)
def test_hidden_file_uploads_opt_in(workflow: Path) -> None:
    """Every dot-prefixed upload sets include-hidden-files AND fails loudly."""
    for step in _upload_steps(workflow.read_text(encoding="utf-8")):
        hidden = [p for p in _uploaded_paths(step) if _is_hidden(p)]
        if not hidden:
            continue
        body = "\n".join(step)
        name = next(
            (line.strip() for line in step if line.strip().startswith("- name:")),
            "<unnamed step>",
        )

        assert "include-hidden-files: true" in body, (
            f"{workflow.name}: {name} uploads the hidden file(s) {hidden} without "
            f"`include-hidden-files: true`. upload-artifact excludes hidden files "
            f"by default since v4.4, so this step uploads NOTHING and still "
            f"reports success. Add `include-hidden-files: true` to its `with:` block."
        )
        assert "if-no-files-found: error" in body, (
            f"{workflow.name}: {name} uploads hidden file(s) {hidden} without "
            f"`if-no-files-found: error`. A hidden-file upload that finds nothing "
            f"must fail the job that produced nothing, not hand a confusing "
            f"failure to whichever downstream job consumes the missing artifact. "
            f"Add `if-no-files-found: error` to its `with:` block."
        )
