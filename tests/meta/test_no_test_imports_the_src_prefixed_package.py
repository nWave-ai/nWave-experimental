"""No test may import `src.des`; the package's one name is `des`.

`[tool.pytest.ini_options] pythonpath = ["src", "."]` puts BOTH `src/` and the
repository root on `sys.path`, so `des.x` and `src.des.x` both import — as two
distinct module objects, with two distinct copies of every class, enum member
and module-level constant inside them.

That is not a supported topology. Production imports `des.*`; the installer
rewrites `from src.des` to `from des`; no source file under `src/`, `scripts/`
or `nWave/` imports the `src`-prefixed form. It exists only because the test
path makes it reachable, and reaching for it produces defects that are invisible
in review because both spellings look correct:

* `except SomeDomainError` matches on class IDENTITY. Raised from one copy and
  caught against the other, the `except` on the very next line does not match.
  CI observed exactly this: `des.cli.phases` let `UnknownPhaseName` escape from
  inside its own `try`, and an unknown phase name was accepted with exit 0.
* a module-level constant read through the second identity is a different
  object, so a test can assert against a copy that production never mutates.

The rule is cheap to obey and removes the whole class rather than one instance
of it. Guarding the CAUSE also retires the per-module workarounds: a regression
test that had to construct the twin identity to reproduce this defect was
deleted when this guard landed, because the condition it needed can no longer
occur.
"""

from __future__ import annotations

import re
from pathlib import Path


_TESTS = Path(__file__).resolve().parents[1]

#: `import src.des...` or `from src.des... import ...`, at statement position.
#: Deliberately anchored with MULTILINE rather than parsing: this must also
#: catch the form inside a function body, which is where both real occurrences
#: lived.
_SRC_IMPORT = re.compile(r"^[ \t]*(?:from|import)[ \t]+src\.des\b", re.MULTILINE)


def test_no_test_module_imports_the_src_prefixed_package() -> None:
    offenders: list[str] = []
    scanned = 0

    for path in sorted(_TESTS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _SRC_IMPORT.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(_TESTS.parent).as_posix()}:{line}")

    # Guard the guard: a scan that walks nothing reports clean forever.
    assert scanned > 100, (
        f"the scan found only {scanned} test modules under {_TESTS}; the scan is "
        f"broken, not the tree"
    )

    assert not offenders, (
        "these tests import the `src`-prefixed package, which loads a SECOND copy "
        "of the module alongside the one production uses, with distinct classes, "
        "enum members and constants:\n  "
        + "\n  ".join(offenders)
        + "\n\nImport `des.<...>` instead — the same module under the one name "
        "production and the installed runtime use. If a test genuinely needs two "
        "identities of one module, build them explicitly with importlib inside "
        "that test and say why; do not acquire the second one by accident from "
        "the pytest path."
    )
