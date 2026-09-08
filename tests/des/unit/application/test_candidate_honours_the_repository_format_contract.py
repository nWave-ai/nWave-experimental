"""The candidate carries the FORM the repository declares, or says why it cannot.

The runner integrates through `commit-tree`, so no `pre-commit` stage observes
the bytes a role wrote. Measured 2026-09-05 (`defects.md`, row
`runner-written-files-bypass-the-repository-format-contract`): the run-12
acceptance designer wrote an oracle that this repository's own read-only ruff
check rejects, and the integrated commit would have carried it into CI.

These laws pin the repair to CONSTRUCTION -- the form is normalized before the
commit object exists -- and pin its blast radius to the paths the run actually
changed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    _foreign_bytes,
    _foreign_status,
    _workspace_bytes,
)
from des.domain.integration_commit_message import IntegrationFacts


#: The exact shape ruff recompacted in the run-12 oracle: a single-element list
#: broken across three lines that fits on one. Nothing about its MEANING is
#: wrong, which is the whole point -- a refusal here would bill the model for
#: the software's omission.
RUN_12_SHAPE = '''"""One oracle."""


def test_callers_of_reports_the_real_call_site() -> None:
    payload = {"sites": ["subject.py:12"]}
    assert payload["sites"] == [
        "subject.py:12"
    ]
'''

RUN_12_NORMALIZED = '''"""One oracle."""


def test_callers_of_reports_the_real_call_site() -> None:
    payload = {"sites": ["subject.py:12"]}
    assert payload["sites"] == ["subject.py:12"]
'''

FACTS = IntegrationFacts(
    "carry the declared form into the candidate",
    ("the integrated commit is formatted as the repository declares",),
    ("docs/authority.md#Value",),
)


def git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    )


#: Unsorted imports: ACCEPTED by `ruff format` and REJECTED by `ruff check`
#: with I001, measured 2026-09-05. The half of the declared quality job the
#: formatter alone does not reach.
UNSORTED = "import sys\nimport json\n\n\ndef go():\n    return sys, json\n"
SORTED = "import json\nimport sys\n\n\ndef go():\n    return sys, json\n"

RUFF_DECLARATION = (
    '[project]\nname = "subject"\n\n[tool.ruff]\nline-length = 88\n'
    'extend-exclude = ["generated"]\n\n[tool.ruff.lint]\nselect = ["E", "F", "I"]\n'
)


def repository(tmp_path: Path, *, declares_ruff: bool = True) -> tuple[Path, str]:
    """One committed base, optionally declaring ruff the way this repo does."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "a@b")
    git(tmp_path, "config", "user.name", "a")
    if declares_ruff:
        (tmp_path / "pyproject.toml").write_text(RUFF_DECLARATION, encoding="utf-8")
    else:
        (tmp_path / "README.md").write_text("no declaration\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path, git(tmp_path, "rev-parse", "HEAD").stdout.decode().strip()


def blob(root: Path, candidate: str, path: str) -> str:
    return git(root, "show", f"{candidate}:{path}").stdout.decode("utf-8")


def test_the_candidate_carries_the_declared_form_of_what_the_run_wrote(
    tmp_path,
) -> None:
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    # The committed bytes, not a staged copy: the operator's checkout and the
    # commit must agree, or a Success leaves a dirty `git status` behind.
    assert blob(root, candidate, owned[0]) == RUN_12_NORMALIZED
    assert (root / owned[0]).read_text(encoding="utf-8") == RUN_12_NORMALIZED


def test_a_repository_declaring_no_formatter_has_its_bytes_left_alone(
    tmp_path,
) -> None:
    root, base = repository(tmp_path, declares_ruff=False)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == RUN_12_SHAPE


def test_a_declared_formatter_that_cannot_be_reached_degrades_loud(
    tmp_path, monkeypatch
) -> None:
    # The repository DECLARES a contract and the runner cannot enact it. A
    # silent skip would ship unformatted bytes into CI under a Success.
    monkeypatch.setattr(
        "des.application.delivery_continuation.shutil.which", lambda _: None
    )
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")

    outcome = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "FormatContractUnreachable"
    assert "pyproject.toml [tool.ruff]" in outcome.failure.why
    assert owned[0] in outcome.failure.why
    assert "uv sync" in outcome.failure.how


def test_a_file_the_declared_formatter_cannot_read_degrades_loud(tmp_path) -> None:
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text("def broken(:\n", encoding="utf-8")

    outcome = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "FormatContractUnhonoured"
    assert owned[0] in outcome.failure.why


def test_normalization_never_reaches_an_owned_path_the_run_did_not_change(
    tmp_path,
) -> None:
    # An owned path the roles never touched keeps whatever form the repository
    # already carries: a delivered value never smuggles unrelated repairs in.
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    (root / "tests/test_existing.py").write_text(RUN_12_SHAPE, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "pre-existing unformatted owned file")
    base = git(root, "rev-parse", "HEAD").stdout.decode().strip()
    owned = ("tests/test_existing.py", "tests/test_oracle.py")
    (root / owned[1]).write_text(RUN_12_SHAPE, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[1]) == RUN_12_NORMALIZED
    assert blob(root, candidate, owned[0]) == RUN_12_SHAPE
    assert (root / owned[0]).read_text(encoding="utf-8") == RUN_12_SHAPE


def test_reabsorbed_bytes_are_invisible_to_the_runners_foreign_state_measure(
    tmp_path,
) -> None:
    # `_finalize_request` proves cleanup by comparing FOREIGN status and bytes,
    # both taken with `owned` excluded. The formatter may touch only changed
    # owned paths, so it can never present as drift -- by construction, not by
    # an exemption.
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")
    (root / "unrelated.py").write_text("x = [\n    1\n]\n", encoding="utf-8")
    runner = DeliveryContinuationRunner()
    observed = runner._observed_scope(root)
    assert not isinstance(observed, DeliveryOutcome)
    status, workspace = observed
    baseline_status = _foreign_status(status, owned)
    baseline_bytes = _foreign_bytes(workspace, owned)

    created = runner._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    after = runner._observed_scope(root)
    assert not isinstance(after, DeliveryOutcome)
    final_status, _ = after
    assert _foreign_status(final_status, owned) == baseline_status
    assert _workspace_bytes(root, tuple(baseline_bytes)) == baseline_bytes, (
        "the formatter rewrote a path outside the run's changed owned scope"
    )
    # The unrelated unformatted file is untouched, which is what makes the
    # equality above a discriminating check rather than a vacuous one.
    assert (root / "unrelated.py").read_text(encoding="utf-8") == "x = [\n    1\n]\n"


@pytest.mark.parametrize(
    "suffix, content",
    [(".md", "a  \n"), (".txt", "b\t\n")],
    ids=["markdown", "text"],
)
def test_a_path_the_declared_formatter_does_not_decide_is_carried_verbatim(
    tmp_path, suffix: str, content: str
) -> None:
    root, base = repository(tmp_path)
    owned = (f"notes{suffix}",)
    (root / owned[0]).write_text(content, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == content


def test_the_candidate_carries_the_import_order_the_repository_declares(
    tmp_path,
) -> None:
    # The formatter half alone accepts these bytes; the repository's own quality
    # job rejects them with I001. Honouring one half is not honouring the
    # contract.
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(UNSORTED, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == SORTED


def test_a_path_the_repository_excluded_is_not_rewritten(tmp_path) -> None:
    # ruff ignores its own exclude for an explicitly passed path, so without
    # `--force-exclude` the runner would overrule a boundary the repository drew.
    root, base = repository(tmp_path)
    (root / "generated").mkdir()
    owned = ("generated/thing.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == RUN_12_SHAPE


def test_repairing_writes_no_tool_cache_into_the_repository(tmp_path) -> None:
    # An untracked directory appearing mid-run is read by the next role turn's
    # scope comparison as unattributed drift, in any repository that does not
    # ignore it.
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(UNSORTED, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    assert not (root / ".ruff_cache").exists()


def test_a_lint_finding_the_contract_does_not_admit_is_left_to_the_reviewer(
    tmp_path,
) -> None:
    # An unused import is a claim about the code's MEANING. It is not repaired
    # here and it is not an integration failure either: the whole-diff reviewer
    # and CI answer for it, exactly as they do for a human's commit.
    root, base = repository(tmp_path)
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    unused = "import json\n\n\ndef go():\n    return 1\n"
    (root / owned[0]).write_text(unused, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == unused


def test_an_empty_ruff_config_on_disk_still_declares_the_contract(tmp_path) -> None:
    # Declaration by EXISTENCE: the file has no other purpose, so its empty text
    # is not an absence and must not fall through to the next rung of the read.
    root, base = repository(tmp_path, declares_ruff=False)
    (root / "ruff.toml").write_text("", encoding="utf-8")
    (root / "tests").mkdir()
    owned = ("tests/test_oracle.py",)
    (root / owned[0]).write_text(RUN_12_SHAPE, encoding="utf-8")

    created = DeliveryContinuationRunner()._candidate(root, base, owned, FACTS)

    assert not isinstance(created, DeliveryOutcome)
    candidate, _ = created
    assert blob(root, candidate, owned[0]) == RUN_12_NORMALIZED
