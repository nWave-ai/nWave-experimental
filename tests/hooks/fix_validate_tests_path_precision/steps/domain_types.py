"""Domain types for the fix-validate-tests-path-precision acceptance slice.

Mandate-12 criterion 1 (SSOT via Types): every domain noun used in the
Gherkin is expressed once here as a typed enum / NewType. Step bodies and
the composition root consume these typed parameters -- no raw ``str`` where
a domain noun exists.

The driving port under test is the pre-commit scope resolver helper at
``scripts/hooks/validate_tests.py::get_targeted_test_dirs``. The domain
nouns are: a staged-file path (a relative POSIX path under the repo root)
and a targeted-test-scope directory (a relative POSIX directory ending
in ``/`` that the pre-commit hook hands to ``pytest`` as a positional
argument).
"""

from __future__ import annotations

from typing import NewType


# A staged file path as ``git diff --cached --name-only`` would emit it:
# POSIX-style, repo-root-relative, no leading ``./``.
StagedFilePath = NewType("StagedFilePath", str)


# A targeted-test-scope directory: POSIX-style, repo-root-relative, with a
# trailing ``/``. The pre-commit hook passes these as positional arguments
# to ``pytest`` so the trailing ``/`` is load-bearing (pytest treats it as
# a directory rather than a node-id stem).
TargetedTestDir = NewType("TargetedTestDir", str)
