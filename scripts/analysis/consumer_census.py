#!/usr/bin/env python3
"""Consumer census for a candidate module: import-shaped AND execution-shaped.

An import-only census reports "clean" on a module that is still reached by CLI
registration, a gate YAML ``module:`` field, a dynamic ``importlib`` load, or a
test that drives the real entry point as a subprocess. All of those are live
consumers. This walks every channel and reports them separately, so a
DELETE/KEEP/BOUNDARY disposition is decided on the whole picture rather than on
the cheapest half of it.

Stdlib only, deliberately. The first version shelled out to ``rg`` and died with
FileNotFoundError, because ``rg`` is a shell function on this box and not a
binary ``shutil.which`` can find -- an instrument that depends on ambient shell
state gives a different answer per environment, which is the failure mode it
exists to prevent. It also mirrors the project's own portability rule: Python is
the only runtime dependency.

Usage:
    opus-consumer-census.py <module-stem> [<module-stem> ...]
    opus-consumer-census.py --self-test
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


#: The tree being decided about. Derived from this file's own location, never
#: hardcoded: a census that scans one checkout while you delete in another
#: measures the wrong tree and says nothing about the one you are cutting.
REPO = Path(__file__).resolve().parents[2]

# Directories whose contents are NOT this tree's consumers. The first five are
# build/cache noise. `.claude` is the one that mattered and the one a plain
# "ignore caches" list misses: `.claude/worktrees/` holds OTHER LANES' complete
# checkouts of this same repository. Measured 2026-08-06 on
# `verify_seal_provenance`: 103 files matched, and 6 of the 7 apparent code
# consumers were the SAME six files, once per lane worktree -- a registration
# row, a gate manifest and a test, counted seven times over. That is a
# false-POSITIVE channel, the mirror of the false-empty this instrument was
# built to prevent: it does not authorise a wrong deletion, it BLOCKS a correct
# one by inventing consumers that live in another tree. A census must scan the
# tree it is deciding about, and nothing else.
# `.tsunami` and `graphify-out` are analysis caches that quote source lines
# verbatim, so they match every needle and attribute the hit to a cache file.
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    ".hypothesis",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".claude",
    ".tsunami",
    "graphify-out",
    ".tla-swarm-model",
}
TEXT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".md",
    ".feature",
    ".cfg",
    ".txt",
    # Shipped templates are installed onto an operator's machine and can carry a
    # command invocation exactly as a skill does. Found 2026-08-06 by the
    # NOT-EXAMINED reporting the moment it was added, which is the point of it.
    ".template",
}


@dataclass(frozen=True)
class Channel:
    """One way a consumer can reach a module, and where to look for it."""

    name: str
    roots: tuple[str, ...]
    pattern: str
    #: Report hits only in files that did NOT match this sibling channel, so a
    #: file already counted as an importer is not counted twice as a mention.
    subtract: str | None = None


CHANNELS: tuple[Channel, ...] = (
    # Two import SHAPES, not one. The dotted-PATH form
    # (`from des.cli.stem import X`, `import des.cli.stem`) and the imported-NAME
    # form (`from des.cli import stem, other`), where the stem is a name in the
    # import list rather than part of the path. Scanning only the first cost two
    # real consumers of `carpaccio_slice_gate`
    # (application/deliver_loop_projection.py:64, cli/at_review_verdict.py:314):
    # missed here, found by an independent AST graph, confirmed in the source.
    # A false-empty on this channel authorises deleting a module still called.
    Channel(
        "static import",
        ("src", "scripts"),
        r"^[ \t]*(?:from|import)[ \t]+[\w.]*\b{stem}\b"
        r"|^[ \t]*from[ \t]+[\w.]+[ \t]+import[ \t]*\(?[^\n]*\b{stem}\b",
    ),
    Channel(
        "dynamic import",
        ("src", "scripts"),
        r"(?:importlib|__import__|import_module)[^\n]*\b{stem}\b",
    ),
    Channel("module string", ("src", "scripts"), r"""["'][\w.]*\.{stem}["']"""),
    Channel("CLI registration", ("src/des/cli/__main__.py",), r"\b{stem}\b"),
    Channel("gate yaml", ("nWave/gates",), r"\b{stem}\b"),
    Channel(
        "flavor/catalog",
        ("nWave/flavors", "nWave/framework-catalog.yaml"),
        r"\b{stem}\b",
    ),
    Channel(
        "installer/build",
        ("scripts/install", "scripts/build_dist.py", "pyproject.toml"),
        r"\b{stem}\b",
    ),
    Channel("pre-commit/CI", (".pre-commit-config.yaml", ".github"), r"\b{stem}\b"),
    # Shipped guidance is an EXECUTION channel, not documentation. A skill, task,
    # template or agent file that tells an agent to run `des feature-end run` is
    # a consumer in exactly the way an import is: delete the verb and the
    # instruction becomes a lie on an installed machine.
    #
    # This channel was missing when the instrument was first committed, and the
    # gap was found by independent review 2026-08-06, not by the instrument. It
    # matters more than its size suggests: the six guidance consumers that
    # reclassified `cli/feature_end` from DELETE to BOUNDARY live HERE, so the
    # census could not see the evidence its own conclusion depended on. They were
    # found by an ad-hoc scan instead, which is luck, not method.
    #
    # It needs the KEBAB alias, not only the module stem: guidance never writes
    # `feature_end`, it writes the operator-facing `des feature-end run`. A
    # channel added here with the underscore pattern alone would report clean and
    # be just as blind.
    #
    # A hit here is a CANDIDATE, never a proven invocation, and the count must not
    # be reported as one. Measured on `feature_end` 2026-08-06: 24 files match, of
    # which 6 actually instruct `des feature-end ...` and 18 merely discuss
    # feature-end RECORDS -- prose that stays true after the verb dies. This
    # channel is deliberately tuned for recall, because a missed instruction ships
    # a lie to an operator while a surplus candidate only costs a reading.
    Channel(
        "shipped guidance",
        ("nWave/skills", "nWave/tasks", "nWave/templates", "nWave/agents"),
        r"\b{stem}\b|\b{kebab}\b",
    ),
    Channel("test import", ("tests",), r"^[ \t]*(?:from|import)[ \t]+[\w.]*\b{stem}\b"),
    Channel("test other", ("tests",), r"\b{stem}\b", subtract="test import"),
)


@dataclass
class ChannelResult:
    hits: int = 0
    files: set[str] = field(default_factory=set)
    #: Files under this channel's roots that the census did NOT read, because
    #: their suffix is outside TEXT_SUFFIXES. An empty `files` is only an
    #: absence claim over what was actually examined.
    unexamined: list[str] = field(default_factory=list)


def _iter_text_files(root: Path, unexamined: list[str] | None = None):
    """Yield the files this census actually reads under `root`.

    Anything whose suffix is not in TEXT_SUFFIXES is NOT examined -- including
    every extensionless file, which is where an executable hook or a launcher
    would live. That is a deliberate scope, but a silent one is indistinguishable
    from a clean result, so callers may pass `unexamined` to collect what was
    skipped and report it alongside the finding.
    """
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if SKIP_DIR_NAMES & set(path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            if unexamined is not None:
                unexamined.append(path.relative_to(REPO).as_posix())
            continue
        yield path


def _scan(pattern: str, roots: tuple[str, ...], exclude: set[str]) -> ChannelResult:
    """Count matching LINES and the files holding them, under every root."""
    compiled = re.compile(pattern, re.MULTILINE)
    result = ChannelResult()
    for root_name in roots:
        for path in _iter_text_files(REPO / root_name, result.unexamined):
            relative = path.relative_to(REPO).as_posix()
            if relative in exclude:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                # An unreadable file is a hole in the census, never a clean
                # result: say so rather than counting it as zero.
                print(f"  !! UNREADABLE {relative}", file=sys.stderr)
                continue
            found = len(compiled.findall(text))
            if found:
                result.hits += found
                result.files.add(relative)
    return result


def _own_files(stem: str) -> set[str]:
    """The candidate's own source files, which are never its own consumers."""
    owned = set()
    for root_name in ("src", "scripts", "tests"):
        for path in _iter_text_files(REPO / root_name):
            if path.stem == stem and path.suffix == ".py":
                owned.add(path.relative_to(REPO).as_posix())
    return owned


def census(stem: str) -> dict[str, ChannelResult]:
    print(f"\n{'=' * 78}\n{stem}\n{'=' * 78}")
    own = _own_files(stem)
    if own:
        print(f"  (own files, excluded: {', '.join(sorted(own))})")
    results: dict[str, ChannelResult] = {}
    for channel in CHANNELS:
        exclude = set(own)
        if channel.subtract:
            exclude |= results[channel.subtract].files
        results[channel.name] = _scan(
            channel.pattern.format(
                stem=re.escape(stem),
                # The operator-facing spelling of the same thing. Every channel
                # gets it whether or not its pattern uses it, so adding a
                # kebab-aware channel later needs no change here.
                kebab=re.escape(stem.replace("_", "-")),
            ),
            channel.roots,
            exclude,
        )
    for channel in CHANNELS:
        outcome = results[channel.name]
        if not outcome.files:
            print(f"  {channel.name:18s} -")
            continue
        print(
            f"  {channel.name:18s} {outcome.hits:4d} hits / {len(outcome.files)} files"
        )
        for relative in sorted(outcome.files)[:6]:
            print(f"                       {relative}")
        if len(outcome.files) > 6:
            print(f"                       ... +{len(outcome.files) - 6} more")

    # An absence is a claim about the instrument. Say how wide the claim is.
    unexamined = sorted({p for r in results.values() for p in r.unexamined})
    if unexamined:
        print(
            f"\n  NOT EXAMINED: {len(unexamined)} file(s) under these roots have a "
            f"suffix outside TEXT_SUFFIXES and were never read. An empty channel "
            f"above is an absence claim over the examined files ONLY."
        )
        for relative in unexamined[:8]:
            print(f"                {relative}")
        if len(unexamined) > 8:
            print(f"                ... +{len(unexamined) - 8} more")
    return results


def _self_test() -> int:
    """Prove the scanner DISCRIMINATES, not merely that it runs.

    A census tool that returns the same shape for a live module and a dead one
    is worthless; these two cases must differ.
    """
    failures = []

    absent = census("this_module_does_not_exist_anywhere_xyzzy")
    if any(r.files for r in absent.values()):
        failures.append("a nonexistent stem reported consumers")

    live = census("commit_slice")
    if not live["static import"].files:
        failures.append("commit_slice reported no static importer")
    if not live["CLI registration"].files:
        failures.append("commit_slice reported no CLI registration")

    # The imported-NAME regression, pinned by its two real counterexamples. Both
    # reach carpaccio_slice_gate through `from des.cli import carpaccio_slice_gate`;
    # the original single-shape pattern reported neither, and an independent AST
    # graph is what surfaced them.
    named = census("carpaccio_slice_gate")["static import"].files
    for expected in (
        "src/des/application/deliver_loop_projection.py",
        "src/des/cli/at_review_verdict.py",
    ):
        if expected not in named:
            failures.append(f"imported-name form missed: {expected}")

    # The shipped-guidance regression, pinned by the counterexample that exposed
    # it. `des feature-end run` is instructed by six installed guidance files;
    # before this channel existed the census reported the module clean, and the
    # consumers that reclassified it BOUNDARY were found by an ad-hoc scan
    # instead. Asserted on the KEBAB spelling, because the underscore stem does
    # not appear in guidance at all -- a channel matching only the stem would
    # pass this test's roots while remaining exactly as blind.
    guidance = census("feature_end")["shipped guidance"].files
    for expected in (
        "nWave/skills/nw-deliver/SKILL.md",
        "nWave/tasks/nw/continue.md",
    ):
        if expected not in guidance:
            failures.append(f"shipped-guidance channel missed: {expected}")

    # The other-lane regression, pinned the same way. Every reported path must
    # belong to THIS tree: a hit under `.claude/worktrees/<lane>/` is another
    # lane's copy of the same file, and counting it invents a consumer that
    # would block a correct deletion. Asserted over every channel of a stem
    # known to exist in several lane worktrees at once -- checking only the
    # channel that happened to leak would not survive the next lane layout.
    for channel, result in census("verify_seal_provenance").items():
        for path in result.files:
            if path.startswith(".claude/") or "/.claude/" in path:
                failures.append(
                    f"[{channel}] counted another lane's worktree copy: {path}"
                )
            if path.startswith((".tsunami/", "graphify-out/")):
                failures.append(
                    f"[{channel}] counted an analysis cache that quotes source: {path}"
                )

    print("\n" + "=" * 78)
    if failures:
        print("SELF-TEST FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(
        "SELF-TEST PASSED: absent stem is empty; a live stem shows import + registration"
    )
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args == ["--self-test"]:
        return _self_test()
    for stem in args:
        census(stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
