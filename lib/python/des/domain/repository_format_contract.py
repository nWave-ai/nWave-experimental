"""What FORM the repository declares its files must have, read from its config.

The delivery runner integrates through Git PLUMBING (`commit-tree` plus a
compare-and-swap on the ref), so no `pre-commit` stage ever observes the bytes
a role wrote. The repository's CI runs a read-only quality job over the tree, so
a role-written file that job would reject is not a cosmetic blemish: it is a red
build nothing local could have refused. This is the same class as the integrated
commit MESSAGE, closed in `integration_commit_message`, and it is closed the
same way -- by construction, before the commit object exists.

THAT JOB HAS TWO HALVES, and honouring one of them is not honouring the
contract. `scripts/local_ci.py --python-quality` is the entry of both the local
hook and the CI job, and it runs `ruff check --exit-non-zero-on-fix` BEFORE
`ruff format --check`. Measured 2026-09-05, independently reproduced: a file
whose imports are unsorted is ACCEPTED by `ruff format` and REJECTED by
`ruff check` with I001. A repair that ran only the formatter would therefore
integrate a candidate the repository's own job fails -- the defect this module
exists to close, half-closed.

So the repair is the ORDERED PAIR the repository declares: the auto-repairable
FORM rules first, the formatter second, which is also the order ruff itself
prescribes. What is admitted into the first half is deliberately narrow. Import
ORDER is form in exactly the sense line wrapping is: no meaning changes and no
judgement is exercised, which is why the formatter would own it if it could.
Everything else ruff can auto-fix -- an unused import, a simplifiable branch --
is a claim about the code's MEANING, and the model owns those: they stay with
the reviewer and CI, and this module never rewrites them. GDP-10 sets the
boundary there rather than at "every safe fix": I001 is the rule a real defect
was measured on, and no other family has been.

WHY REPAIR AND NOT A REFUSAL. `boundary:software-measures-model-decides` states
the corollary directly: *a rejection for FORM bills the model for the software's
own omission*. The model owns the MEANING of an oracle; the shape of its bytes
-- line breaks, import order, trailing whitespace, a final newline -- is a
normalization no semantic judgement enters. Refusing a delivered value because a
list fitted on one line rather than three would spend a paid turn to punish the
software for not having normalized what only the software can normalize.

WHY NOT `pre-commit run --files`, MEASURED 2026-09-05 in this repository on the
run-12 oracle (`tests/bugs/des/test_graphify_callers_of_answers_the_real_call_
sites.py`), the exact file that produced the defect:

* wall 5.5s with the four pytest hooks skipped, and **zero files modified**;
* the only hook that observed the form, `python-quality`, is declared read-only
  ("same read-only Ruff contract as CI") and merely FAILED;
* that hook carries `pass_filenames: false`, so it re-checked the whole tree
  (1327 files) and ignored the `--files` argument outright -- it does not
  measure the candidate's owned paths at all, which is the pathology
  `defects.md` already records for the pre-push copy of the same check.

So running the repository's hooks converts every unformatted role-written byte
into an `Indeterminate` -- precisely the refusal-for-FORM the boundary clause
forbids -- at several seconds per candidate, plus the always-run pytest gates
that hold a machine-global lock. The hooks are the repository's ENFORCEMENT of
the contract. They are not the contract. The contract is what the repository
DECLARES, and this repository declares its formatting rule where CI, the hook
and the operator all read it from: the ruff configuration.

WHAT IS AND IS NOT TOOL KNOWLEDGE HERE. The DETECTION is a property of the
repository -- does it configure ruff? -- and a repository that configures none
declares no contract, so there is nothing to honour and nothing happens. The
one piece of tool knowledge is the mapping from that declaration to the argv
that enacts it, and it is stated ONCE, here, as data. It is deliberately not
generalized into a formatter registry: no second formatter has ever been
measured in a repository this runner delivers into, and GDP-10 asks for the
incident before the mechanism.

This module stays pure: the caller reads the config files and passes their
text, and the caller resolves the executable, mirroring
`integration_commit_message`, which parses `.gitlint`'s text and leaves file
and environment resolution in the application seam.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


#: Any `[tool.ruff]` table -- the bare table or any of its sub-tables
#: (`[tool.ruff.format]`, `[tool.ruff.lint]`, ...).  A repository that
#: configures ruff at all has declared it as the tool that decides the form of
#: its Python files; which of its tables carries the declaration is an
#: authoring choice, not a different contract.
_RUFF_TABLE = re.compile(r"^[ \t]*\[tool\.ruff(?:\.[A-Za-z0-9_-]+)*\][ \t]*$")

#: A `select` / `extend-select` array anywhere in the configuration text, and
#: the quoted rule prefixes inside one.  Table-agnostic on purpose: the same
#: scan reads `[tool.ruff.lint]` in a `pyproject.toml` and a bare `[lint]` in a
#: `ruff.toml` without a second, independently drifting statement of where the
#: key may sit.
_SELECT_ARRAY = re.compile(r"(?:extend-)?select\s*=\s*\[([^\]]*)\]")
_RULE_PREFIX = re.compile(r"""["']([^"']+)["']""")

#: isort's rule family, and only it: `I`, or `I` followed by digits.  `ISC`
#: shares the initial and is a different family, so the anchor is load-bearing.
_ISORT_PREFIX = re.compile(r"^I[0-9]*$")

#: The extensions the declared formatter is allowed to rewrite.  Narrower than
#: what ruff itself accepts: notebooks are excluded because no role in this
#: runner writes one, so admitting them would be reach without a measurement.
_PYTHON_SUFFIXES = ("py", "pyi")

#: Passed to every repair invocation.
#:
#: `--force-exclude` because ruff IGNORES its own `exclude` / `extend-exclude`
#: for a path handed to it explicitly, which is what this runner always does.
#: Measured 2026-09-05: without the flag a file under `extend-exclude` is
#: rewritten anyway, so the runner would overrule a boundary the repository
#: drew -- and the excluded path is exactly the generated-artifact shape the
#: support-admissibility rule already refuses elsewhere.
#:
#: `--no-cache` because ruff otherwise writes a `.ruff_cache/` directory into
#: the repository root. This repository ignores it; a guest repository need not,
#: and an untracked directory appearing mid-run is observed by the next role
#: turn's scope comparison as unattributed drift -- the same defect class as
#: the runner's own state directory, already closed once.
_REPAIR_FLAGS = ("--force-exclude", "--no-cache")

#: The auto-repairable FORM half, applied before the formatter.  `--fix-only`
#: rather than `--fix`: the latter exits non-zero for leftover violations it
#: could not fix, which are the model's to answer for, and would turn ordinary
#: lint into an integration failure.  `--select I` narrows the run to import
#: order no matter what else the repository selects.
_ISORT_REPAIR = ("check", "--fix-only", *_REPAIR_FLAGS, "--select", "I")
_FORMAT_REPAIR = ("format", *_REPAIR_FLAGS)


@dataclass(frozen=True, slots=True)
class FormatContract:
    """One declared formatter, the declaration that named it, and its reach."""

    tool: str
    #: Ordered argv suffixes; the paths to repair are appended to each.
    repairs: tuple[tuple[str, ...], ...]
    declaration: str
    suffixes: tuple[str, ...]

    def applies_to(self, path: str) -> bool:
        """Whether the declared formatter decides the form of `path`."""
        _, separator, suffix = path.rpartition(".")
        return bool(separator) and suffix in self.suffixes

    def reaches(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        """`paths` in their given order, keeping only what the contract covers."""
        return tuple(path for path in paths if self.applies_to(path))


def declared_format_contract(
    pyproject_text: str | None, ruff_config_text: str | None
) -> FormatContract | None:
    """The repository's declared format contract, or None when it declares none.

    A dedicated `ruff.toml` / `.ruff.toml` is a declaration by EXISTENCE: the
    file has no other purpose, so an EMPTY one declares ruff exactly as loudly
    as a populated one and the caller passes `""`, never None, for it. In
    `pyproject.toml` the declaration is a `[tool.ruff...]` table, matched on
    whole lines so a `[tool.ruffian]` table or the string inside a docstring
    cannot be mistaken for one.

    Detection is deliberately textual rather than a TOML parse. The bundled
    `des/` package carries no TOML dependency and cannot grow one (the bundle
    hygiene contract), `tomllib` does not exist on the declared 3.10 floor, and
    a malformed file must degrade to "no contract declared" rather than raise
    -- a candidate refused by a config parser would be a worse failure than an
    unnormalized line.
    """
    if ruff_config_text is not None:
        return _ruff("ruff.toml", ruff_config_text)
    text = pyproject_text or ""
    for line in text.splitlines():
        if _RUFF_TABLE.match(line):
            return _ruff("pyproject.toml [tool.ruff]", text)
    return None


def _selects_isort(config_text: str) -> bool:
    """Whether the repository's own rule selection covers import order.

    The isort half runs ONLY where the repository asked for it. A repository
    that never selected `I` has not declared unsorted imports a violation, and
    reordering them anyway would write bytes it never asked for into a
    delivered value -- the runner imposing taste, which is the failure this
    whole module argues against.

    The degrade direction is safe by construction: a selection this scan cannot
    read yields False, the isort half is skipped, and the repository's CI
    catches the violation exactly as it does today. Nothing silently wrong is
    ever written; at worst nothing is repaired.
    """
    for body in _SELECT_ARRAY.findall(config_text):
        for prefix in _RULE_PREFIX.findall(body):
            if prefix == "ALL" or _ISORT_PREFIX.match(prefix):
                return True
    return False


def _ruff(declaration: str, config_text: str) -> FormatContract:
    repairs = (
        (_ISORT_REPAIR, _FORMAT_REPAIR)
        if _selects_isort(config_text)
        else (_FORMAT_REPAIR,)
    )
    return FormatContract("ruff", repairs, declaration, _PYTHON_SUFFIXES)
