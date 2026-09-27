"""Derive the acceptance-oracle locator BY CONVENTION -- ``des compile-
contract`` decides where the oracle lives; ATD writes it there, it never
chooses the path (root has no way to obtain that judgment call from ATD
before ATD ever runs, since ATD holds no ``Bash`` and root's compile step
precedes ATD's own dispatch).

Convention: ``<test dir adjacent to the primary EXTEND target>/test_<slug>.py``
-- a Django-shaped project resolves to its app's own ``tests/`` package
(``hc/api/tests/test_maintenance_windows.py``); a flat pytest project falls
back to the repository's own top-level ``tests/`` directory
(``tests/test_<slug>.py``). A tests root whose own Python tests observably
live under tier subdirectories places the oracle in the best-mirroring tier
instead of at top level (a guard-refused top-level file burned a full
crafter round twice, 2026-08-20/21). Neither directory existing is a
construction refusal at the producer (``Blocked``), never a
guessed/invented directory.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable


def _is_python_test_name(name: str) -> bool:
    """The pytest filename convention only -- the projected oracle is a
    pytest file, so only the subject's PYTHON test placement is the
    same-nature convention this module may observe."""
    return any(
        fnmatch.fnmatchcase(name, pattern) for pattern in _TEST_NAME_CONVENTIONS[".py"]
    )


def _observed_tier_dir(
    repo_root: Path, base_dir: str, primary_target: str
) -> str | None:
    """The subdirectory of ``base_dir`` a NEW pytest file belongs in, when
    the subject repo's own placement convention is OBSERVABLY tiered --
    strictly more Python test files live under subdirectories than directly
    in the base (second occurrence 2026-08-21: two auto-compiled slices in
    a row got a top-level ``tests/test_auto_<id>.py`` locator that the
    subject's own conftest collection guard refuses at collection). A few
    pre-migration top-level stragglers do not outvote a dominant tiered
    population. ``None`` when the base's own direct children ARE the
    convention (flat layout) or the base holds no Python tests at all --
    the caller keeps ``base_dir`` unchanged.

    Tier choice is observed, never designated: the candidate directory
    whose own path segments best mirror the primary target's package path
    (where tests of the same nature already live), then the most populated
    one, then the lexicographically first for determinism. Pure filesystem
    observation -- no repo layout is hardcoded and no tool is shelled out
    to.
    """
    base = repo_root / base_dir
    direct = 0
    candidates: dict[str, int] = {}
    for path in sorted(base.rglob("*.py")):
        if any(
            part.startswith(".") or part == "__pycache__"
            for part in path.relative_to(base).parts[:-1]
        ):
            continue
        if not _is_python_test_name(path.name):
            continue
        parent = path.parent
        if parent == base:
            direct += 1
        else:
            rel = parent.relative_to(repo_root).as_posix()
            candidates[rel] = candidates.get(rel, 0) + 1
    if sum(candidates.values()) <= direct:
        return None
    target_segments = frozenset(Path(primary_target).parent.parts)

    def rank(item: tuple[str, int]) -> tuple[int, int, str]:
        tier, count = item
        tier_segments = Path(tier).relative_to(base_dir).parts
        mirror = sum(1 for part in tier_segments if part in target_segments)
        return (-mirror, -count, tier)

    return min(candidates.items(), key=rank)[0]


def resolve_oracle_test_dir(repo_root: Path, primary_target: str) -> str | None:
    """The POSIX repo-relative test directory this delivery's oracle
    belongs in: the primary EXTEND target's own sibling ``tests/`` when it
    already exists, else the repository's top-level ``tests/`` when THAT
    already exists, else ``None`` (no discoverable convention -- the
    workspace fragment must declare one). Within whichever base is chosen,
    an observably TIERED placement convention descends into the observed
    tier (``_observed_tier_dir``) -- never a top-level file the subject's
    own collection guard refuses."""
    sibling = (Path(primary_target).parent / "tests").as_posix()
    for base_dir in (sibling, "tests"):
        if not (repo_root / base_dir).is_dir():
            continue
        tier = _observed_tier_dir(repo_root, base_dir, primary_target)
        return tier if tier is not None else base_dir
    return None


def oracle_slug(delivery_id: str) -> str:
    """The schema-valid ``delivery-id`` (kebab-case) projected into a
    Python-module-safe slug (snake_case) -- the SAME deterministic
    projection for every caller, never a second ad-hoc naming rule."""
    return delivery_id.replace("-", "_")


def resolve_oracle_locator(
    repo_root: Path, primary_target: str, delivery_id: str
) -> str | None:
    """``<test_dir>/test_<slug>.py``, or ``None`` when no test directory
    convention is discoverable (see ``resolve_oracle_test_dir``).

    RED_TO_GREEN only: this PROJECTS a not-yet-existing path for ATD to
    author. GREEN_TO_GREEN never calls this -- see
    ``resolve_existing_oracle_locator``."""
    test_dir = resolve_oracle_test_dir(repo_root, primary_target)
    if test_dir is None:
        return None
    return f"{test_dir}/test_{oracle_slug(delivery_id)}.py"


#: Per-language test/spec FILENAME conventions, keyed by extension --
#: WORD-BOUNDARY anchored, never a bare substring scan (review BLOCK
#: 2026-08-20: ``"test" in stem`` swallowed genuine production files --
#: ``contest.go``, ``latest_config.go``, ``attestation.py`` -- into the
#: oracle-candidate set and OUT of the contract targets). The language
#: families are the SAME ones ``_EXTENSION_TO_PBT_ADAPTER``
#: (``architecture_brief_resolver``) already enumerates -- literal
#: duplication under the same discipline (this module needs a filename
#: FILTER, never authority to invent a new family), plus Ruby, whose
#: RSpec/minitest idiom predates any PBT adapter here. Patterns are
#: ``fnmatch`` shapes matched case-SENSITIVELY against the basename --
#: each convention's own casing is part of the convention
#: (``WidgetTest.java`` yes, ``Latest.java`` no).
_TEST_NAME_CONVENTIONS: dict[str, tuple[str, ...]] = {
    # Python (pytest)
    ".py": ("test_*.py", "*_test.py"),
    # TypeScript / JavaScript (jest, vitest, mocha)
    ".ts": ("*.test.ts", "*.spec.ts"),
    ".tsx": ("*.test.tsx", "*.spec.tsx"),
    ".js": ("*.test.js", "*.spec.js"),
    ".jsx": ("*.test.jsx", "*.spec.jsx"),
    # ES-module / CommonJS variants of the same family -- exactly the ones
    # Vitest's default `include` glob names (`**/*.{test,spec}.?(c|m)[jt]s?(x)`);
    # an ESM-only Node repository's Jest suite is all `*.test.mjs`.
    ".mjs": ("*.test.mjs", "*.spec.mjs"),
    ".cjs": ("*.test.cjs", "*.spec.cjs"),
    ".mts": ("*.test.mts", "*.spec.mts"),
    ".cts": ("*.test.cts", "*.spec.cts"),
    # .NET (xUnit/NUnit naming idiom)
    ".cs": ("*Test.cs", "*Tests.cs"),
    ".fs": ("*Test.fs", "*Tests.fs"),
    # JVM (JUnit/kotest/ScalaTest)
    ".java": ("*Test.java", "*Tests.java"),
    ".kt": ("*Test.kt", "*Tests.kt"),
    ".kts": ("*Test.kts", "*Tests.kts"),
    ".scala": ("*Test.scala", "*Spec.scala", "*Suite.scala"),
    # Rust
    ".rs": ("*_test.rs", "test_*.rs"),
    # Go (the toolchain REQUIRES the suffix)
    ".go": ("*_test.go",),
    # Haskell (hspec/tasty)
    ".hs": ("*Spec.hs", "*Test.hs"),
    # Erlang (common_test / eunit) / Elixir (ExUnit)
    ".erl": ("*_SUITE.erl", "*_tests.erl"),
    ".ex": ("*_test.ex",),
    ".exs": ("*_test.exs",),
    # Ruby (RSpec / minitest)
    ".rb": ("*_spec.rb", "*_test.rb", "test_*.rb"),
}


def is_test_shaped_path(path: str) -> bool:
    """Shape-only test/spec discrimination (``_TEST_NAME_CONVENTIONS``) --
    the SAME rule ``resolve_existing_oracle_locator`` has always applied,
    exported so ``extract_target_citations`` can apply it symmetrically:
    a citation this rule admits is an oracle-binding candidate, never a
    contract target (SF friction report 2026-08-20, sister reproduction:
    a cited Go test was promoted to a RED_TO_GREEN contract target). A
    file whose extension has no known convention is never test-shaped --
    the safe degradation is "production target", not "oracle": a missed
    oracle blocks LOUDLY downstream, a swallowed target vanishes
    silently."""
    name = Path(path).name
    patterns = _TEST_NAME_CONVENTIONS.get(Path(name).suffix)
    if patterns is None:
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def oracle_citation_file_part(citation: str) -> str:
    """The plain file path of an oracle citation -- identical to the
    citation itself unless it carries a ``::Selector`` suffix
    (``pkg/widget_test.go::TestWidget`` -> ``pkg/widget_test.go``). The
    selector is oracle IDENTITY (the start of the OracleIdentity shape
    already recorded in techdebt), preserved in the locator, never part of
    any filesystem lookup."""
    return citation.partition("::")[0]


def resolve_existing_oracle_locator(
    repo_root: Path, citations: Iterable[str]
) -> str | None:
    """GREEN_TO_GREEN's oracle-binding rule: the oracle MUST already exist
    and be committed -- authoring one fresh is a different route
    (RED_TO_GREEN). Picks the first citation, in the brief's own
    first-appearance order, whose own filename already reads as a test/spec
    file (``is_test_shaped_path``) AND whose FILE PART genuinely exists as
    a file in the base tree. A ``path::Selector`` citation binds verbatim
    only when it is itself first; a later selector cannot displace earlier
    public oracle ownership. ``None`` when the brief cites no such file -- the
    caller BLOCKS rather than projecting a guessed, possibly
    wrong-language, possibly nonexistent path (SF friction report
    2026-08-20, item 2a: a Python-shaped ``test_<slug>.py`` locator was
    projected for a GREEN_TO_GREEN Go delivery even though a real,
    already-committed ``widget_test.go`` oracle sat right next to the
    target)."""
    for citation in citations:
        file_part = oracle_citation_file_part(citation)
        if not is_test_shaped_path(file_part):
            continue
        if not (repo_root / file_part).is_file():
            continue
        return citation
    return None


def resolve_cited_oracle_locator(oracle_citations: Iterable[str]) -> str | None:
    """RED_TO_GREEN's explicit-citation rule (SF friction report
    2026-08-20, sister reproduction): a brief that explicitly cites a
    test/spec oracle -- with or without a ``::Selector`` -- has ALREADY
    made the locator judgment call this module otherwise projects by
    convention. Precedence: the first test-shaped citation in the brief's
    own durable order (``extract_oracle_citations``) wins; a citation whose file part is not
    test-shaped is NEVER the oracle. Existence is deliberately NOT
    required here: RED_TO_GREEN's
    oracle may not exist yet -- ATD authors it at exactly this cited path.
    ``None`` when nothing was cited; only then may the caller fall back to
    the Python-only ``tests/test_<slug>.py`` convention (Python subjects)
    or refuse (non-Python subjects, never a wrong-language guess)."""
    for citation in oracle_citations:
        if not is_test_shaped_path(oracle_citation_file_part(citation)):
            # Never a non-test-shaped oracle, selector or not (review
            # BLOCK 2026-08-20: a mis-admitted production file must lose
            # here even if extraction let it through).
            continue
        return citation
    return None
