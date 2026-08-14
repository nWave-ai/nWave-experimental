"""AT -- `des charter-scaffold --seed-mode bug-observable`.

`--seed-mode bug-observable` generates ONE charter scaffold straight from a
bug's observable behaviour: the Intent is PRE-FILLED from the `--observable`
text VERBATIM (user-side), the judgment sections (oracle / start-recipe) are
left as the template's fresh-PO-fill TODO placeholders -- the same skeleton
other seed-modes emit. Idempotent (never overwrites); degrades LOUD (GDP-6)
on a missing/blank `--observable`, never a `.md` garbage file.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving
port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: A plain bug-behaviour sentence (user-side, no design/impl vocabulary) --
#: the `--observable` text a `/nw-bugfix` caller supplies verbatim.
BUG_OBSERVABLE_TEXT = (
    "Clicking Save twice creates two duplicate invoices instead of one"
)

#: The NEW degrade-LOUD verdict token slice-03 adds for `--seed-mode
#: bug-observable` with a missing/blank `--observable`. Mirrors the shipped
#: `missing-feature-delta` / `missing-charter-template` naming convention in
#: `des.cli.charter_scaffold` -- defined LOCALLY here (not imported) because
#: it does not exist in the shipped module yet: this is the DISTILL-authored
#: contract the crafter implements verbatim to reach GREEN.
VERDICT_MISSING_OBSERVABLE = "missing-observable"


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _intent_section(content: str) -> str:
    """Test-local helper (not production code): the body of the `## Intent`
    section, up to the next `##` heading."""
    lines = content.splitlines()
    try:
        start = lines.index("## Intent") + 1
    except ValueError:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("##"):
            break
        body.append(line)
    return "\n".join(body)


def _invoke_bug_observable(
    repo_root: Path,
    capsys,
    feature_id: str,
    observable: str | None,
) -> tuple[int, dict]:
    """Drive the in-process `main()` with `--seed-mode bug-observable`.

    Wraps the call so argparse errors surface as clear `AssertionError`
    instead of unhandled `SystemExit`. `observable=None` omits the flag
    entirely.
    """
    from des.cli.charter_scaffold import main

    argv = ["--seed-mode", "bug-observable", "--feature-id", feature_id]
    if observable is not None:
        argv += ["--observable", observable]
    argv += ["--repo-root", str(repo_root), "--format", "json"]

    try:
        exit_code = main(argv)
    except SystemExit as exc:
        pytest.fail(
            "des charter-scaffold --seed-mode bug-observable was rejected "
            f"by argparse (SystemExit code={exc.code}) -- the '--seed-mode' "
            "/ '--observable' flags do not exist on the CLI"
        )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_bug_observable_generates_one_scaffold_with_observable_verbatim_in_intent(
    charter_template_seeded_repo: Path, capsys
) -> None:
    """Happy path: exactly ONE charter scaffold is created under
    docs/product/expectations/<feature-id>/, its Intent section reads the
    --observable text VERBATIM, and the judgment sections (Preconditions /
    Charter / Expected observations) are left as the template's fresh-PO-fill
    TODO placeholders -- the tool lifts only the observable text, it never
    invents judgment (same contract as the slice-01 Value-statement path).
    """
    tmp_path = charter_template_seeded_repo
    feature_id = "fix-duplicate-invoice"

    exit_code, payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )

    assert exit_code == 0
    assert payload["feature_id"] == feature_id
    assert len(created_files) == 1
    assert payload["created"] == [created_files[0]]

    # Meaningful, not arbitrary: the slug derives from the observable text.
    first_word = BUG_OBSERVABLE_TEXT.split(maxsplit=1)[0].lower()
    assert created_files[0].startswith(first_word)

    content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")
    intent_body = _intent_section(content)
    assert BUG_OBSERVABLE_TEXT in intent_body
    # Uncontaminated by construction: only the observable text was seen.
    assert "src/des" not in content
    assert "class " not in content
    assert "def " not in content

    # Judgment sections untouched -- still the template's TODO placeholders.
    assert (
        "<start recipe: how to run the system from a clean state, seed state>"
        in content
    )
    assert "<observable outcome, user language>" in content
    assert "<negative: what must NOT happen>" in content


def test_bug_observable_second_run_is_idempotent_and_reports_skipped(
    charter_template_seeded_repo: Path, capsys
) -> None:
    """Idempotent re-run: running twice does NOT overwrite / re-create the
    scaffold; the second run reports it in `skipped`, and a fresh-PO edit
    made between runs survives untouched.
    """
    tmp_path = charter_template_seeded_repo
    feature_id = "fix-duplicate-invoice-idempotent"

    first_exit, first_payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, feature_id)
    scaffold_path = next(expectations_dir.glob("*.md"))
    sentinel = "SENTINEL: fresh-PO-authored oracle, must survive re-run\n"
    scaffold_path.write_text(sentinel, encoding="utf-8")

    second_exit, second_payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, BUG_OBSERVABLE_TEXT
    )

    assert second_exit == 0
    assert second_payload["created"] == []
    assert len(second_payload["skipped"]) == 1
    assert scaffold_path.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize(
    "observable",
    [
        pytest.param(None, id="observable_flag_omitted"),
        pytest.param("", id="observable_blank_string"),
        pytest.param("   ", id="observable_whitespace_only"),
    ],
)
def test_bug_observable_missing_observable_never_creates_a_garbage_scaffold(
    charter_template_seeded_repo: Path, capsys, observable: str | None
) -> None:
    """Negative (GDP-6 degrade-LOUD, the slice-01 blank-Value lesson applies
    here too): a missing OR blank --observable with --seed-mode
    bug-observable must NEVER produce a `.md` garbage file / empty-Intent
    scaffold. Instead: a LOUD non-zero reject with a clear message naming
    'observable' -- never a silent no-op.
    """
    tmp_path = charter_template_seeded_repo
    feature_id = "fix-missing-observable"

    exit_code, payload = _invoke_bug_observable(
        tmp_path, capsys, feature_id, observable
    )

    expectations_dir = _expectations_dir(tmp_path, feature_id)

    assert exit_code != 0
    assert payload["verdict"] == VERDICT_MISSING_OBSERVABLE
    assert "observable" in payload["detail"].lower()
    assert payload["created"] == []
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md"))
