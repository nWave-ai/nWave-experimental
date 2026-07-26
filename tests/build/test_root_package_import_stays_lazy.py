"""The `des` root package must not drag the edge in behind it.

Importing `des` used to cost 111ms on the way to `des.cli.dispatch`, 45ms of which
was `des.adapters.driven` -- pulled in by re-exports written "for backward
compatibility" that had, when measured, ZERO consumers. Every `des` command paid it
before doing any work, and so did every test touching the package.

These tests pin the PROPERTY, not the fix: a future edit that re-adds an eager
re-export puts the cost straight back, and the only thing that notices is a test
asking what the import graph actually contains. The measurement that motivated the
change is not repeated here -- a duration is not a stable assertion on a contended
machine, while what a module imports IS.
"""

from __future__ import annotations

import subprocess
import sys


def _imported_des_modules(statement: str) -> set[str]:
    """Return the `des.*` modules a statement leaves in `sys.modules`.

    Driven through a CHILD interpreter because the parent already has half the
    package imported: asking this process what it loaded would answer a question
    about the test session, not about the statement.
    """
    probe = (
        f"{statement}\n"
        "import sys\n"
        "print('\\n'.join(sorted(m for m in sys.modules if m.startswith('des'))))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        "WHAT: the import probe did not run; "
        f"WHY: `{statement}` failed in a child interpreter, so the import graph "
        "could not be observed at all -- this is an inability to measure, not a "
        "measurement of zero; "
        f"HOW: run `python -c '{statement}'` and fix the import error it reports.\n"
        f"stderr={completed.stderr}"
    )
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def test_importing_the_root_package_loads_no_driven_adapter() -> None:
    """`import des` must not load the concrete edge.

    The declared layering (CLAUDE.md, "Architecture: DES") puts application on
    PORTS and adapters at the edge. Before this pin, touching the root package
    loaded filesystem, git and logging drivers, so the domain could not be used
    without dragging the edge in behind it -- the layering held on paper and not
    at runtime.
    """
    loaded = _imported_des_modules("import des")

    adapters = sorted(m for m in loaded if m.startswith("des.adapters"))
    assert not adapters, (
        "WHAT: `import des` loaded driven adapters: " + ", ".join(adapters) + "; "
        "WHY: an eager re-export in src/des/__init__.py pulls the concrete edge "
        "into every consumer of the package -- it cost 45ms on every CLI "
        "invocation and every test, for a convenience that had zero consumers; "
        "HOW: declare the name in the `_EXPORTS` map in src/des/__init__.py and "
        "let `__getattr__` resolve it on first use, instead of importing it at "
        "module scope."
    )


def test_the_root_package_imports_nothing_of_itself_until_asked() -> None:
    """The lazy contract, stated as a property rather than a line count."""
    loaded = _imported_des_modules("import des")

    submodules = sorted(m for m in loaded if m != "des")
    assert not submodules, (
        "WHAT: `import des` eagerly loaded " + ", ".join(submodules) + "; "
        "WHY: the root package is a facade -- resolving a name must cost that "
        "name's layer, never the whole system's; "
        "HOW: move the import into the `_EXPORTS` map (resolved lazily by "
        "`__getattr__`) rather than importing at module scope."
    )


def test_every_declared_export_still_resolves() -> None:
    """Laziness must not lose a name: the facade's contract is unchanged.

    This is the leg that makes the two above safe to trust. Without it, the
    cheapest way to pass them would be to delete the re-exports -- fast, and a
    silent break for anyone importing them.
    """
    import des

    unresolvable = [name for name in des.__all__ if not hasattr(des, name)]
    assert not unresolvable, (
        "WHAT: names declared in `des.__all__` do not resolve: "
        + ", ".join(unresolvable)
        + "; WHY: a facade that advertises a name it cannot produce breaks its "
        "consumers at the moment they reach for it, far from this file; "
        "HOW: give each name a module in the `_EXPORTS` map in "
        "src/des/__init__.py, or remove it from the exported set."
    )


def test_backward_compatibility_aliases_are_the_same_object() -> None:
    """An alias must BE the thing, not merely something like it."""
    import des

    assert des.RealValidator is des.TemplateValidator, (
        "WHAT: `des.RealValidator` is not `des.TemplateValidator`; "
        "WHY: an alias resolved to a distinct object breaks `isinstance` and "
        "identity checks in code that has used the old name for years; "
        "HOW: resolve aliases through `_ALIASES` -> `_EXPORTS` so both names "
        "reach the same attribute of the same module."
    )
    assert des.RealFilesystem is des.RealFileSystem, (
        "WHAT: `des.RealFilesystem` is not `des.RealFileSystem`; "
        "WHY: the two spellings must denote one class, or a caller can hold two "
        "'filesystems' that are not each other; "
        "HOW: resolve through `_ALIASES` in src/des/__init__.py."
    )
    assert des.SystemTime is des.SystemTimeProvider, (
        "WHAT: `des.SystemTime` is not `des.SystemTimeProvider`; "
        "WHY: same reason -- an alias that drifts into a second object is a "
        "second implementation nobody chose; "
        "HOW: resolve through `_ALIASES` in src/des/__init__.py."
    )


def test_an_unknown_name_explains_itself() -> None:
    """A lazy facade must fail better than the eager one it replaced.

    PEP 562 makes it easy to raise a bare `AttributeError`, which tells a reader
    less than the eager import did (that one at least failed at a line naming the
    module). The refusal has to carry WHAT / WHY / HOW like any other gate.
    """
    import des

    try:
        des.NoSuchExport  # noqa: B018 -- the attribute access itself triggers __getattr__
    except AttributeError as exc:
        message = str(exc)
    else:  # pragma: no cover - the attribute must not exist
        raise AssertionError("`des.NoSuchExport` resolved; it must not exist")

    assert "NoSuchExport" in message, (
        "WHAT: the AttributeError does not name what was asked for; "
        "WHY: a reader cannot fix what the error does not mention; "
        "HOW: include the requested name in `__getattr__`'s AttributeError."
    )
    assert "des.domain" in message or "layer package" in message, (
        "WHAT: the AttributeError does not say where the name might live; "
        "WHY: the whole point of the facade shrinking is that callers now import "
        "from layer packages -- the error is where they learn that; "
        "HOW: name the layer packages in `__getattr__`'s AttributeError."
    )


def test_the_console_entry_path_does_not_regrow_the_eager_edge() -> None:
    """The pin the root-package one cannot give: what the USER's command loads.

    `des` on the command line imports `des.cli.__main__`, and Python imports the
    parent package first -- so a lazy root can be green while the entry path
    re-introduces the eager edge, and the user keeps paying. Peer review
    (2026-07-25) named exactly this gap; the numbers agreed: `import des` loads
    0 des.* modules while `import des.cli.__main__` still loads 62.

    This is a CEILING, not the target. The remaining eager load is a known,
    filed debt (techdebt.md: freshness pulls the repo-probe adapter at module
    scope because its constants live there), routed to DESIGN because relocating
    those constants is a layering change with consumers. Until that lands, this
    test's job is to stop the number GROWING -- a ratchet, so the cost cannot
    quietly climb back while the root-package pin reports success.
    """
    loaded = _imported_des_modules("import des.cli.__main__")
    # Measured 2026-07-25 with THIS helper (sys.modules after the import), on the
    # trunk before the fix and on the branch after it: 74 -> 52. The ceiling is
    # the post-fix number, so a regression toward the old cost fails here.
    # It must be measured the way the test measures: an earlier draft pinned 62,
    # a figure taken from counting `-X importtime` output lines -- a ceiling set
    # with one instrument and checked with another is not a ceiling.
    ceiling = 52

    assert len(loaded) <= ceiling, (
        f"WHAT: the console entry path now loads {len(loaded)} des.* modules, "
        f"above the {ceiling} recorded on 2026-07-25; "
        "WHY: every `des <command>` pays this before doing any work, and so does "
        "every test that spawns the CLI -- the cost lands on the user, not just "
        "on the suite; "
        "HOW: find what was added with `python -X importtime -c 'import "
        "des.cli.__main__'` and import it at point of use instead of at module "
        "scope. If the growth is genuinely required, lower the ceiling elsewhere "
        "first -- do NOT raise this number without saying why in the commit."
    )
