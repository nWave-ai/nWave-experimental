"""AXIS-B enforcement levers — the shared, git-free, per-language lever core.

at-in-process-port-default slice-03 (DESIGN §3 "the 6 levels → 6 mechanical
gates" + the subprocess-overuse gate + DDD-1/DDD-9 degrade-LOUD/per-language/
git-free). This module is the ONE production home of the five AXIS-B levers'
detection logic; the three driving gates
(:mod:`des.cli.verify_readiness_pre_dispatch`, :mod:`des.cli.run_contract_gate`,
:mod:`des.cli.carpaccio_slice_gate`) call into it, and the SHIPPED arch-test
``tests/build/test_no_inline_interpreter_spawn.py`` re-uses the widened
per-language spawn scanner here (reuse-first EXTEND seam — one detector, three
consumers).

Every lever is:

  * **git-free** — pure filesystem + AST reads; NEVER a ``git`` shell-out
    (generality / target-machine agnosticism: depend only on Python).
  * **per-language / target-aware** — the spawn detector recognizes Python /
    Rust / Go; an unrecognized language is NOT_APPLICABLE with a loud reason
    (never a false flag); an unparseable file is INDETERMINATE (never a silent
    pass). The F821 lever clears NOT_APPLICABLE on a non-Python target.
  * **degrade-LOUD** — the lever-1 wiring check carries the CodeFactPort
    confidence label with its flag (``binding-resolved`` / ``approx`` /
    ``noisy``); a ``noisy`` callers==0 is advisory, a structural one gates.

The levers scan the *shipping package's own tree* (the nWave ``src/des`` + the
``tests`` corpus) — this is a dogfooding gate that flags real wiring / coverage /
sad-path drift in the codebase it ships with. ``_REPO_ROOT`` is resolved from
this module's filesystem location, so the levers find their scan target
regardless of the (possibly hermetic) workspace a gate is driven against.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.ports.code_fact_port import (
    CAPABILITY_CALLERS_OF,
    CAPABILITY_READS_OF,
    CapabilityDescriptor,
)


# --- The package tree the dogfooding levers scan -----------------------------
# This module lives at ``src/des/cli/axis_b_levers.py``; the repo root is three
# parents up from ``src/des/cli``. Resolving from ``__file__`` (not a passed
# workspace) lets the levers find ``src/des`` + ``tests`` even when a gate is
# driven against a hermetic tmp workspace.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_DES = _REPO_ROOT / "src" / "des"
_TESTS = _REPO_ROOT / "tests"

# --- target-project layout discovery (PATH-genericity, DDD-4 pure resolver) --
# The levers must scan the TARGET project's source + tests roots, not assume
# nWave's own ``tests/`` + ``src/des`` (the hardcoded-globals defect). The
# resolver DISCOVERS the roots from the target in precedence:
#   1. explicit --source-dir / --tests-dir argv,
#   2. the target ``pyproject.toml [tool.pytest.ini_options] testpaths``,
#   3. a ``.nwave/`` layout config (layout.toml: source/tests keys).
# When none resolves it degrades LOUD (NOT_RESOLVABLE + a named reason), never a
# false-PASS on a wrong/empty dir, never a crash. Pure filesystem reads only
# (git-free, target-machine agnostic — depend only on Python).

_LAYOUT_RESOLVED = "resolved"
_LAYOUT_NOT_RESOLVABLE = "not-resolvable"

# Conventional source-root fallbacks tried (in order) when only the tests root
# is declared (e.g. pyproject testpaths names the tests dir, not the source).
_CONVENTIONAL_SOURCE_DIRS = ("src", "lib")


@dataclass(frozen=True)
class LayoutRoots:
    """The resolved (or unresolvable) target-project source + tests roots.

    ``resolution`` is ``resolved`` when both roots were discovered (degrade-LOUD
    ``not-resolvable`` + a named ``reason`` otherwise). ``tests_root`` /
    ``source_root`` are absolute paths INSIDE the target project when resolved;
    empty when not. This is the structured ``layout`` record the gate surfaces.
    """

    resolution: str
    tests_root: Path | None = None
    source_root: Path | None = None
    reason: str = ""


def resolve_layout(
    repo_root: Path,
    source_dir: str | None = None,
    tests_dir: str | None = None,
) -> LayoutRoots:
    """DISCOVER the target project's source + tests roots (pure, git-free).

    Precedence: explicit args -> pyproject testpaths -> .nwave layout config.
    Degrades LOUD (``not-resolvable`` + a named reason) when no layout resolves
    and never crashes on a bare/non-nWave layout.
    """
    tests_root = _resolve_tests_root(repo_root, tests_dir)
    source_root = _resolve_source_root(repo_root, source_dir, tests_root)
    if tests_root is None or source_root is None:
        return LayoutRoots(
            resolution=_LAYOUT_NOT_RESOLVABLE,
            reason=_not_resolvable_reason(tests_root, source_root),
        )
    return LayoutRoots(
        resolution=_LAYOUT_RESOLVED,
        tests_root=tests_root,
        source_root=source_root,
    )


def _resolve_tests_root(repo_root: Path, tests_dir: str | None) -> Path | None:
    """Resolve the tests root: explicit arg -> pyproject testpaths -> .nwave."""
    explicit = _existing_child(repo_root, tests_dir)
    if explicit is not None:
        return explicit
    from_pyproject = _existing_child(repo_root, _pyproject_testpath(repo_root))
    if from_pyproject is not None:
        return from_pyproject
    return _existing_child(repo_root, _nwave_layout_key(repo_root, "tests"))


def _resolve_source_root(
    repo_root: Path, source_dir: str | None, tests_root: Path | None
) -> Path | None:
    """Resolve the source root: explicit arg -> .nwave -> conventional fallback."""
    explicit = _existing_child(repo_root, source_dir)
    if explicit is not None:
        return explicit
    from_nwave = _existing_child(repo_root, _nwave_layout_key(repo_root, "source"))
    if from_nwave is not None:
        return from_nwave
    if tests_root is None:
        return None
    for candidate in _CONVENTIONAL_SOURCE_DIRS:
        child = _existing_child(repo_root, candidate)
        if child is not None:
            return child
    return None


def _existing_child(repo_root: Path, name: str | None) -> Path | None:
    """The ``repo_root/name`` directory iff ``name`` is set and the dir exists."""
    if not name:
        return None
    child = repo_root / name
    return child if child.is_dir() else None


def _pyproject_testpath(repo_root: Path) -> str | None:
    """The first ``[tool.pytest.ini_options] testpaths`` entry, if declared."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        text = pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # Stdlib-only extraction (no tomllib/tomli) so the DES bundle stays
    # dependency-free on Python 3.10+ (tomllib is 3.11+; tomli is external):
    # isolate the [tool.pytest.ini_options] section, then read its testpaths.
    section = re.search(
        r"^\[tool\.pytest\.ini_options\]\s*$(.*?)(?=^\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if section is None:
        return None
    entry = re.search(r"^\s*testpaths\s*=\s*(.+)$", section.group(1), re.MULTILINE)
    if entry is None:
        return None
    # testpaths = "tests"  OR  testpaths = ["tests", ...] -> first quoted token.
    quoted = re.search(r"""["']([^"']+)["']""", entry.group(1))
    return quoted.group(1) if quoted else None


def _nwave_layout_key(repo_root: Path, key: str) -> str | None:
    """The ``source`` / ``tests`` key from ``.nwave/layout.toml``, if present."""
    layout = repo_root / ".nwave" / "layout.toml"
    if not layout.is_file():
        return None
    try:
        text = layout.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # Stdlib-only (no tomllib): read the `key` value under the [layout] section.
    section = re.search(
        r"^\[layout\]\s*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    if section is None:
        return None
    entry = re.search(
        rf"^\s*{re.escape(key)}\s*=\s*(.+)$", section.group(1), re.MULTILINE
    )
    if entry is None:
        return None
    quoted = re.search(r"""["']([^"']+)["']""", entry.group(1))
    return quoted.group(1) if quoted else None


def _not_resolvable_reason(tests_root: Path | None, source_root: Path | None) -> str:
    """The loud, named reason the layout could not be resolved (degrade-LOUD)."""
    missing = []
    if tests_root is None:
        missing.append("tests")
    if source_root is None:
        missing.append("source")
    return (
        "health.gate.layout-unresolvable: the target project declares no "
        f"resolvable {' + '.join(missing)} root "
        "(no --source-dir/--tests-dir arg, no pyproject [tool.pytest.ini_options] "
        "testpaths, no .nwave/layout.toml, no conventional src/lib dir) — "
        "NOT_APPLICABLE (the levers cannot scan a layout they cannot resolve; "
        "this is a named verdict, never a false-PASS on a wrong/empty dir)"
    )


# Languages the spawn detector recognizes (per-language, DDD-9). Anything else
# is NOT_APPLICABLE with a loud reason — never a false flag.
_RECOGNIZED_LANGUAGES = frozenset({"python", "rust", "go"})

# Bare-name Python interpreter literals: python, python3, python3.12, ...
_INTERPRETER_LITERAL = re.compile(r"^python(3(\.\d+)?)?$")
_SUBPROCESS_SPAWNERS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
_OS_EXEC_FUNCS = frozenset(
    {
        "system",
        "popen",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    }
)
_WALKING_SKELETON_TAG = "@walking_skeleton"
# The pytest marker / scenario tag name (without the leading ``@``) the per-site
# classifier reads off a function decorator or a ``.feature`` scenario tag.
_WS_MARKER_NAME = "walking_skeleton"

# The two per-site decisions a spawn-site resolves to (ADR-TEST-003).
KEEP = "keep"  # enclosing scenario carries @walking_skeleton -> legitimate e2e.
MIGRATE = "migrate"  # enclosing scenario is non-WS -> the migration target.

# The per-site total-function verdict over an arbitrary corpus (degrade-LOUD).
_VERDICT_RECOGNIZED = "recognized"
_VERDICT_NOT_APPLICABLE = "not-applicable"
_VERDICT_INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class LeverResult:
    """A single AXIS-B lever's structured verdict.

    ``flagged`` — the lever found a violation; ``structured_event`` — the
    machine-readable token (Q3: a structured event, never a bare exit code);
    ``target`` — the symbol/file/adapter the lever named; ``confidence`` — the
    CodeFactPort label carried with a wiring flag (degrade-LOUD); ``remediation``
    — the human-readable fix line.
    """

    invariant_id: str
    flagged: bool
    structured_event: str = ""
    target: str = ""
    confidence: str = ""
    remediation: str = ""


# --- lever-1 wiring: a produced entry reached by no real dispatch ------------


def check_unwired_entry(
    symbol: str = "_a_deliberately_unwired_leaf_symbol",
    source_root: Path | None = None,
) -> LeverResult:
    """FLAG a produced entry with zero callers AND zero readers (HARDENED OR).

    Consumes the EXISTING ``CodeFactPort`` (ADR-LA-001) — it does NOT add an
    analyzer. The HARDENED OR (``query.reads-of`` OR ``query.callers-of``) avoids
    a false-0 on a registry-dispatched entry: only an entry reached by NEITHER a
    caller NOR a reader is an isolated leaf. The CodeFactPort confidence label is
    carried with the flag (R6 degrade-LOUD): ``binding-resolved`` / ``approx``
    gates, ``noisy`` advises. ``source_root`` threads the RESOLVED target source
    root (PATH-genericity); absent it falls back to the host ``src/des`` global.
    """
    chain = CodeFactChain(root=source_root or _SRC_DES)
    callers = _sites(chain, CAPABILITY_CALLERS_OF, symbol)
    readers = _sites(chain, CAPABILITY_READS_OF, symbol)
    confidence = callers.confidence or readers.confidence
    flagged = not callers.sites and not readers.sites
    if not flagged:
        return LeverResult(invariant_id="unwired_entry", flagged=False)
    return LeverResult(
        invariant_id="unwired_entry",
        flagged=True,
        structured_event="UnwiredEntryFlagged",
        target=symbol,
        confidence=confidence,
        remediation=(
            f"produced entry `{symbol}` has zero callers AND zero readers "
            f"(isolated leaf / theater) — wire it into real dispatch or remove it "
            f"[code-fact confidence: {confidence}]"
        ),
    )


@dataclass(frozen=True)
class _Sites:
    sites: list[str]
    confidence: str


def _sites(chain: CodeFactChain, capability_id: str, symbol: str) -> _Sites:
    """The call/read sites of ``symbol`` via the CodeFactPort chain (degrade-LOUD)."""
    descriptor = CapabilityDescriptor(
        id=capability_id,
        stability="stable",
        contract_version="1.0.0",
        io_schema="sites",
        providing_adapter="code-fact-chain",
    )
    result = chain.query(descriptor, {"symbol": symbol})
    if result is None:
        # The chain found no covering provider (paid-tier-only capability,
        # Tsunami absent). Degrade-LOUD: no sites known, noisy confidence.
        return _Sites(sites=[], confidence="noisy")
    payload = result.payload if isinstance(result.payload, dict) else {}
    sites = payload.get("sites", [])
    return _Sites(
        sites=list(sites) if isinstance(sites, list) else [],
        confidence=result.confidence,
    )


# --- L3 integration-per-adapter / L4 contract-per-port -----------------------


def check_integration_per_adapter(
    source_root: Path | None = None, tests_root: Path | None = None
) -> LeverResult:
    """FLAG a driven adapter with no @real-io @adapter-integration test, no waiver.

    Enumerates concrete adapter classes under the target source root's
    ``adapters/driven/**`` and requires each to be named by ≥1 ``@real-io
    @adapter-integration`` AT (or carry a cited waiver). Silence is the BLOCKER
    (R4): a justified waiver clears. ``source_root`` / ``tests_root`` thread the
    RESOLVED target roots (PATH-genericity); absent they fall back to the host
    globals.
    """
    adapters = _enumerate_concrete_adapters(source_root)
    tested = _adapter_integration_corpus(tests_root)
    for adapter_name in adapters:
        if adapter_name in tested:
            continue
        return LeverResult(
            invariant_id="integration_per_adapter",
            flagged=True,
            structured_event="AdapterIntegrationMissing",
            target=adapter_name,
            remediation=(
                f"driven adapter `{adapter_name}` has no @real-io "
                f"@adapter-integration test and no cited waiver — add one or "
                f"cite a Port-contract waiver"
            ),
        )
    return LeverResult(invariant_id="integration_per_adapter", flagged=False)


def check_contract_per_port(
    source_root: Path | None = None, tests_root: Path | None = None
) -> LeverResult:
    """FLAG a port Protocol with methods, no contract test, no cited waiver.

    ``source_root`` / ``tests_root`` thread the RESOLVED target roots
    (PATH-genericity); absent they fall back to the host globals.
    """
    ports = _enumerate_ports_with_methods(source_root)
    tested = _port_contract_corpus(tests_root)
    for port_name in ports:
        if port_name in tested:
            continue
        return LeverResult(
            invariant_id="contract_per_port",
            flagged=True,
            structured_event="PortContractMissing",
            target=port_name,
            remediation=(
                f"port `{port_name}` has methods but no contract test and no "
                f"cited waiver — add a contract test naming it"
            ),
        )
    return LeverResult(invariant_id="contract_per_port", flagged=False)


def _enumerate_concrete_adapters(source_root: Path | None = None) -> list[str]:
    """Concrete adapter class names under ``<source>/adapters/driven/**`` (pure, DDD-4).

    A concrete adapter is a class that is NOT abstract (no ``ABC`` base, not a
    ``Protocol``) and whose name does not end ``Base``/``Port`` (the interface
    itself is enumerated by L4, not L3). ``source_root`` threads the RESOLVED
    target source root; absent it falls back to the host ``src/des`` global.
    """
    driven = (source_root or _SRC_DES) / "adapters" / "driven"
    return _enumerate_classes(driven, want_protocol=False)


def _enumerate_ports_with_methods(source_root: Path | None = None) -> list[str]:
    """Port Protocol/ABC class names with ≥1 method under ``<source>/ports/**``."""
    ports = (source_root or _SRC_DES) / "ports"
    return _enumerate_classes(ports, want_protocol=True)


def _enumerate_classes(root: Path, *, want_protocol: bool) -> list[str]:
    """Enumerate class names under ``root`` filtered by the abstract/concrete axis."""
    found: list[str] = []
    if not root.is_dir():
        return found
    for source_file in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(
                source_file.read_text(encoding="utf-8"), filename=str(source_file)
            )
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            is_proto = _is_protocol_or_abc(node)
            has_method = _has_method(node)
            if want_protocol:
                if is_proto and has_method:
                    found.append(node.name)
            elif not is_proto and not _looks_like_interface(node.name):
                found.append(node.name)
    return sorted(set(found))


def _is_protocol_or_abc(node: ast.ClassDef) -> bool:
    """True iff the class derives from ``Protocol`` or ``ABC`` (abstract surface)."""
    for base in node.bases:
        name = _base_name(base)
        if name in {"Protocol", "ABC"}:
            return True
    return False


def _looks_like_interface(name: str) -> bool:
    """True iff the class name reads as an interface (``*Base`` / ``*Port``)."""
    return name.endswith("Base") or name.endswith("Port")


def _has_method(node: ast.ClassDef) -> bool:
    """True iff the class body defines ≥1 function (a method, not a bare alias)."""
    return any(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not child.name.startswith("__")
        for child in node.body
    )


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _base_name(base.value)
    return ""


def _adapter_integration_corpus(tests_root: Path | None = None) -> set[str]:
    """Class names named by an ``@real-io`` ``@adapter-integration`` AT or a waiver."""
    return _names_in_test_corpus(marker="@adapter-integration", tests_root=tests_root)


def _port_contract_corpus(tests_root: Path | None = None) -> set[str]:
    """Class names named by a contract test (``contract`` in the test path/name)."""
    return _names_in_test_corpus(marker="contract", tests_root=tests_root)


def _names_in_test_corpus(*, marker: str, tests_root: Path | None = None) -> set[str]:
    """Every identifier mentioned in a test file whose text carries ``marker``.

    A coarse-but-honest corpus: any adapter/port whose name appears in a test
    file that also carries the marker token is treated as covered. A cited waiver
    (the token ``adapter-waiver`` / ``port-waiver`` next to the class name) also
    covers it. Silence is the only BLOCKER (R4). ``tests_root`` threads the
    RESOLVED target tests root; absent it falls back to the host ``tests`` global.
    """
    names: set[str] = set()
    corpus = tests_root or _TESTS
    if not corpus.is_dir():
        return names
    identifier = re.compile(r"\b[A-Z][A-Za-z0-9_]+\b")
    for test_file in corpus.rglob("*.py"):
        try:
            text = test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if marker not in text and "waiver" not in text:
            continue
        names.update(identifier.findall(text))
    return names


# --- spawn-overuse detector (per-language, AST, git-free, degrade-LOUD) ------


@dataclass(frozen=True)
class ClassifiedSite:
    """One per-spawn-site classification record (ADR-TEST-003, DDD-1).

    A spawn-site is KEEP iff its ENCLOSING scenario carries ``@walking_skeleton``,
    else MIGRATE — decided per-SITE, never per-file (the un-gameable contract that
    closes the 45-mixed-file / 155-fork blind spot). ``location`` is
    ``file:line:enclosing`` so a caller can match either the file or the enclosing
    scenario/function by name.
    """

    location: str
    decision: str
    enclosing_scenario: str = ""
    scenario_tags: tuple[str, ...] = ()


@dataclass
class SpawnScanReport:
    """The per-language spawn scan over a test corpus.

    ``recognized`` — the language is one the detector understands; ``flagged_sites``
    — non-``@walking_skeleton`` spawn sites found (the FILE-level gradient view);
    ``indeterminate_files`` — files that failed to parse (degrade-LOUD).

    The per-SITE surface (DDD-1, populated when ``classify_per_site`` is set):
    ``classified_sites`` — one ``ClassifiedSite`` per spawn, KEEP/MIGRATE decided by
    the enclosing scenario's tags; ``per_site_verdict`` — the total-function verdict
    (recognized / not-applicable / indeterminate); ``not_applicable_reason`` — the
    loud reason an unrecognized language cleared NOT_APPLICABLE; ``indeterminate_sites``
    — files the per-site pass could not parse (recorded, never silently dropped);
    ``recipe_conformant`` / ``drives_edge`` / ``zombies_preserved`` — the migrated-
    exemplar recipe-conformance surface (DDD-2).
    """

    language: str
    recognized: bool
    flagged_sites: list[str] = field(default_factory=list)
    indeterminate_files: list[str] = field(default_factory=list)
    classified_sites: list[ClassifiedSite] = field(default_factory=list)
    per_site_verdict: str = _VERDICT_RECOGNIZED
    not_applicable_reason: str = ""
    indeterminate_sites: list[str] = field(default_factory=list)
    recipe_conformant: bool = False
    drives_edge: bool = False
    zombies_preserved: bool = False


def scan_spawn_sites(
    root: Path,
    language: str = "python",
    *,
    file_glob: str = "*.py",
    classify_per_site: bool = True,
) -> SpawnScanReport:
    """Scan ``root`` for non-``@walking_skeleton`` interpreter/process spawns.

    Per-language (DDD-9): Python ``subprocess``/``sys.executable``/``os.exec*``,
    Rust ``Command::new``, Go ``exec.Command``. An unrecognized language is
    NOT_APPLICABLE (``recognized=False``, no false flag). A test whose bound
    ``.feature`` carries ``@walking_skeleton`` is EXEMPT (file-level gradient). An
    unparseable Python file is INDETERMINATE (recorded, never silently dropped).
    git is NEVER invoked — the WS-tag lookup is a pure filesystem read.

    When ``classify_per_site`` is set (the default), a second pass derives the
    per-SITE surface (ADR-TEST-003 / DDD-1): each Python spawn is classified
    KEEP/MIGRATE by its enclosing scenario's tags (un-gameable per-scenario,
    never per-file). Callers that need only the file-level gradient (the readiness
    gate over the large real tests tree) pass ``classify_per_site=False``.
    """
    report = SpawnScanReport(
        language=language, recognized=language in _RECOGNIZED_LANGUAGES
    )
    if not report.recognized:
        report.per_site_verdict = _VERDICT_NOT_APPLICABLE
        report.not_applicable_reason = _not_applicable_language_reason(language)
        return report
    if not root.is_dir():
        return report
    for source_file in sorted(root.rglob(file_glob)):
        if not source_file.is_file():
            continue
        if not _file_is_walking_skeleton(source_file):
            if language == "python":
                _scan_python_spawns(source_file, report)
            elif language == "rust":
                _scan_text_spawns(
                    source_file, report, ("Command::new", "process::Command")
                )
            elif language == "go":
                _scan_text_spawns(source_file, report, ("exec.Command", "os/exec"))
        if classify_per_site and language == "python":
            _classify_python_file(source_file, report)
    if classify_per_site:
        _finalize_per_site(root, report)
    return report


def _not_applicable_language_reason(language: str) -> str:
    """The loud, named reason an unrecognized language cleared NOT_APPLICABLE."""
    return (
        f"health.gate.spawn-scan.not-applicable: the target language `{language}` is "
        "not one the per-language spawn detector recognizes "
        f"({', '.join(sorted(_RECOGNIZED_LANGUAGES))}) — NOT_APPLICABLE (no false "
        "migration flag is raised on an unrecognized language)"
    )


def _finalize_per_site(root: Path, report: SpawnScanReport) -> None:
    """Set the total-function verdict + recipe-conformance surface (degrade-LOUD)."""
    if report.indeterminate_sites:
        report.per_site_verdict = _VERDICT_INDETERMINATE
    else:
        report.per_site_verdict = _VERDICT_RECOGNIZED
    migrate_count = sum(1 for s in report.classified_sites if s.decision == MIGRATE)
    report.drives_edge = _corpus_drives_edge(root)
    report.zombies_preserved = _corpus_preserves_zombies(root)
    report.recipe_conformant = (
        migrate_count == 0 and report.drives_edge and report.zombies_preserved
    )


def _classify_python_file(source_file: Path, report: SpawnScanReport) -> None:
    """Per-SITE classify each Python spawn by its enclosing scenario (ADR-TEST-003)."""
    try:
        text = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        report.indeterminate_sites.append(str(source_file))
        return
    try:
        tree = ast.parse(text, filename=str(source_file))
    except SyntaxError:
        report.indeterminate_sites.append(str(source_file))
        return
    enclosing = _enclosing_functions(tree)
    is_bdd = "scenarios(" in text or "pytest_bdd" in text
    bdd_keep = _bound_features_fully_ws(source_file, text) if is_bdd else False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_spawn_call(node)):
            continue
        func = enclosing.get(node)
        name = func.name if func is not None else "<module>"
        if is_bdd:
            keep = bdd_keep
        else:
            keep = func is not None and _function_is_walking_skeleton(func)
        report.classified_sites.append(
            ClassifiedSite(
                location=f"{source_file}:{node.lineno}:{name}",
                decision=KEEP if keep else MIGRATE,
                enclosing_scenario=name,
                scenario_tags=_function_tags(func) if func is not None else (),
            )
        )


def _is_spawn_call(node: ast.Call) -> bool:
    """True iff ``node`` is an interpreter fork or an ``os.exec*`` spawn."""
    return _is_interpreter_spawn(node) or _is_os_exec_call(node)


def _enclosing_functions(tree: ast.AST) -> dict[ast.AST, ast.FunctionDef]:
    """Map each AST node to its CLOSEST enclosing function (nested wins)."""
    mapping: dict[ast.AST, ast.FunctionDef] = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(func):
                mapping[child] = func  # type: ignore[assignment]
    return mapping


def _function_is_walking_skeleton(func: ast.FunctionDef) -> bool:
    """True iff a function decorator names ``walking_skeleton`` (KEEP boundary)."""
    return any(_decorator_mentions_ws(dec) for dec in func.decorator_list)


def _decorator_mentions_ws(dec: ast.expr) -> bool:
    """True iff a decorator's attribute/name chain mentions ``walking_skeleton``."""
    for node in ast.walk(dec):
        if isinstance(node, ast.Attribute) and node.attr == _WS_MARKER_NAME:
            return True
        if isinstance(node, ast.Name) and node.id == _WS_MARKER_NAME:
            return True
    return False


def _function_tags(func: ast.FunctionDef) -> tuple[str, ...]:
    """The decorator-tail names on a function (a coarse per-scenario tag list)."""
    tags: list[str] = []
    for dec in func.decorator_list:
        tail = _decorator_tail(dec)
        if tail:
            tags.append(tail)
    return tuple(tags)


def _decorator_tail(dec: ast.expr) -> str:
    """The trailing attribute/name of a decorator (``a.b.c`` -> ``c``)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _bound_features_fully_ws(source_file: Path, text: str) -> bool:
    """True iff EVERY ``.feature`` a bdd step file binds is fully walking-skeleton.

    A bdd step's UNCONDITIONAL fork is KEEP only when no non-WS scenario can reach
    it (ADR-TEST-003 resolution-2 / OPEN QUESTION 1). A single non-WS scenario in
    any bound feature makes the spawn a MIGRATE target.
    """
    features = _bound_features(source_file, text)
    if not features:
        return False
    return all(_feature_fully_ws(feature) for feature in features)


def _bound_features(source_file: Path, text: str) -> list[Path]:
    """The sibling ``.feature`` files a bdd step module references by name."""
    return [
        feature
        # gherkin-scope: pytest-bdd's OWN `scenarios("x.feature")` binding is
        # structurally a step-module-to-.feature-file link; no other AT kind
        # has this relationship to discover.
        for feature in sorted(source_file.parent.glob("*.feature"))
        if feature.name in text or feature.stem in text
    ]


def _feature_fully_ws(feature: Path) -> bool:
    """True iff a ``.feature`` carries WS at Feature level or on every scenario."""
    try:
        text = feature.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    feature_level_ws = False
    scenario_ws_flags: list[bool] = []
    pending: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("@"):
            pending.extend(stripped.split())
            continue
        if stripped.startswith("Feature:"):
            feature_level_ws = _WALKING_SKELETON_TAG in pending
            pending = []
            continue
        if stripped.startswith(("Scenario:", "Scenario Outline:")):
            scenario_ws_flags.append(
                feature_level_ws or _WALKING_SKELETON_TAG in pending
            )
            pending = []
            continue
        pending = []
    if feature_level_ws:
        return True
    return bool(scenario_ws_flags) and all(scenario_ws_flags)


def _any_py_file_contains(root: Path, markers: tuple[str, ...]) -> bool:
    """True iff any ``.py`` file under ``root`` contains one of ``markers``.

    The shared corpus-scan shape behind ``_corpus_drives_edge`` /
    ``_corpus_preserves_zombies``: walk every ``.py`` file, degrade-LOUD-skip an
    unreadable one (``OSError`` / ``UnicodeDecodeError``), and report whether any
    readable file's text carries a marker substring.
    """
    for source_file in root.rglob("*.py"):
        try:
            text = source_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(marker in text for marker in markers):
            return True
    return False


def _corpus_drives_edge(root: Path) -> bool:
    """True iff any file in the corpus imports a ``des`` production module (EDGE)."""
    return _any_py_file_contains(root, ("import des", "from des"))


def _corpus_preserves_zombies(root: Path) -> bool:
    """True iff any file in the corpus carries a sad-path (ZOMBIES) scenario."""
    return _any_py_file_contains(root, ("error_path", "@error", "zombie"))


def _scan_python_spawns(source_file: Path, report: SpawnScanReport) -> None:
    """AST-scan one Python file for interpreter/process spawns (degrade-LOUD)."""
    try:
        text = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        report.indeterminate_files.append(str(source_file))
        return
    try:
        tree = ast.parse(text, filename=str(source_file))
    except SyntaxError:
        report.indeterminate_files.append(str(source_file))
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_interpreter_spawn(node) or _is_os_exec_call(node):
            report.flagged_sites.append(f"{source_file}:{node.lineno}")


def _scan_text_spawns(
    source_file: Path, report: SpawnScanReport, needles: tuple[str, ...]
) -> None:
    """Per-language textual spawn scan (Rust/Go have no Python-AST shape here)."""
    try:
        text = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        report.indeterminate_files.append(str(source_file))
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        if any(needle in line for needle in needles):
            report.flagged_sites.append(f"{source_file}:{lineno}")


def _is_interpreter_spawn(call: ast.Call) -> bool:
    """True iff ``call`` is a ``subprocess.*`` spawner forking an interpreter."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_SPAWNERS):
        return False
    if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
        return False
    if not call.args:
        return False
    first_arg = call.args[0]
    if not (isinstance(first_arg, (ast.List, ast.Tuple)) and first_arg.elts):
        return False
    first = first_arg.elts[0]
    return _is_sys_executable(first) or _is_interpreter_literal(first)


def _is_sys_executable(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "executable"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_interpreter_literal(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(_INTERPRETER_LITERAL.match(node.value))
    )


def _is_os_exec_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _OS_EXEC_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    )


def _file_is_walking_skeleton(source_file: Path) -> bool:
    """True iff the test file (or its bound ``.feature``) carries @walking_skeleton.

    Pure filesystem read (no git): a step module bound to a ``.feature`` that
    carries ``@walking_skeleton``, or a file whose own text carries the tag, is
    exempt (subprocess-e2e is reserved for walking skeletons, DDD-5).
    """
    try:
        text = source_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    # A direct @walking_skeleton tag in the file itself exempts it outright.
    if _WALKING_SKELETON_TAG in text:
        return True
    # Otherwise, a step module is exempt iff a bound sibling .feature it
    # references carries the tag (pure FS read; no git).
    return _bound_feature_is_walking_skeleton(source_file, text)


def _bound_feature_is_walking_skeleton(source_file: Path, text: str) -> bool:
    """True iff a sibling ``.feature`` the step file references carries the WS tag."""
    # gherkin-scope: same pytest-bdd sibling-binding fact as _bound_features
    # above -- structurally Gherkin, no other AT kind has this relationship.
    for feature in source_file.parent.glob("*.feature"):
        try:
            feature_text = feature.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _WALKING_SKELETON_TAG not in feature_text:
            continue
        if feature.stem in text or "scenarios(" in text:
            return True
    return False


def check_non_ws_spawn(
    tests_root: Path | None = None,
    *,
    migration_scope: list[str] | None = None,
) -> LeverResult:
    """The readiness-gate ``non_ws_spawn`` invariant: any non-WS spawn in tests/**.

    Always runs the Python scan over the target tests corpus and reports
    ``flagged`` when ≥1 non-``@walking_skeleton`` spawn exists, carrying a
    remediation. ``tests_root`` threads the RESOLVED target tests root
    (PATH-genericity); absent it falls back to the host ``tests`` global. The
    language/WS/NOT_APPLICABLE projection is the caller's (the in-process
    composition derives it from the target language).

    ``migration_scope`` (DDD-4 ordering caveat): when supplied, the gate's BLOCKING
    scope FOLLOWS the migrated directories — only spawns WITHIN a scoped directory
    are flagged, so tightening to per-site never hard-fails the un-migrated corpus.
    Absent, the gate scans the whole tree file-level (the pre-migration default).
    """
    report = scan_spawn_sites(tests_root or _TESTS, "python", classify_per_site=False)
    sites = report.flagged_sites
    if migration_scope is not None:
        scope_paths = [Path(directory).resolve() for directory in migration_scope]
        sites = [site for site in sites if _site_within_scope(site, scope_paths)]
    if not sites:
        return LeverResult(invariant_id="non_ws_spawn", flagged=False)
    head = sites[0]
    return LeverResult(
        invariant_id="non_ws_spawn",
        flagged=True,
        structured_event="NonWalkingSkeletonSpawnFlagged",
        target=head,
        remediation=(
            f"non-@walking_skeleton test spawns an interpreter at {head} "
            f"(+{len(sites) - 1} more) — drive the real port "
            f"in-process; subprocess-e2e is reserved for @walking_skeleton"
        ),
    )


def _site_within_scope(site: str, scope_paths: list[Path]) -> bool:
    """True iff a ``file:line`` spawn-site lives under a migration-scope directory."""
    file_path = Path(site.rsplit(":", 1)[0]).resolve()
    return any(
        scope == file_path or scope in file_path.parents for scope in scope_paths
    )


# --- @requires_external degrade-LOUD-SKIP resolver (DDD-6, resolves Q2) -------


@dataclass(frozen=True)
class RequiresExternalSkipDecision:
    """The @requires_external degrade-LOUD-SKIP decision (never silent, never block).

    A ``@walking_skeleton @requires_external`` build scenario in a build-incapable
    sandbox must SKIP with a loud, structured reason naming the missing capability
    — NEVER silently passed (minted GREEN), NEVER hard-blocked (it is a skip, not a
    failure). A build-capable sandbox runs the scenario (no skip).
    """

    skipped: bool
    loud_reason: str = ""
    silent_pass: bool = False
    hard_blocked: bool = False


def requires_external_skip_decision(
    build_capable: bool,
) -> RequiresExternalSkipDecision:
    """Resolve a @requires_external build scenario for the sandbox's build capability.

    Build-capable: the scenario runs (no skip). Build-incapable: degrade-LOUD-SKIP
    with a structured reason naming the missing capability — never a silent pass,
    never a hard block.
    """
    if build_capable:
        return RequiresExternalSkipDecision(skipped=False)
    return RequiresExternalSkipDecision(
        skipped=True,
        loud_reason=(
            "health.gate.requires-external.skip: this @walking_skeleton "
            "@requires_external build scenario needs an external build capability "
            "(a build toolchain) the sandbox lacks — SKIPPED (degrade-LOUD: a "
            "structured skip naming the missing capability, never a silent pass, "
            "never a hard block)"
        ),
        silent_pass=False,
        hard_blocked=False,
    )


# --- lever-3 coverage-on-executed-path ---------------------------------------

# The runner this lever's coverage scan is written for. The scan looks for
# pytest ATs importing the ``des`` production package — a Python/pytest-only
# dogfood signal. On any other runner (cargo-test / go-test / vitest) the scan
# cannot apply and the lever CLEARS as NOT_APPLICABLE (mirrors the F821 lever's
# target-aware degrade-LOUD), never a false flag.
_PYTEST_RUNNER = "pytest"
_COVERAGE_NOT_APPLICABLE_EVENT = "health.gate.coverage-on-executed-path.not-applicable"


def check_coverage_on_executed_path(
    repo: Path, runner: str = _PYTEST_RUNNER
) -> LeverResult:
    """FLAG a contract-suite run whose driven ATs execute zero production lines.

    Coverage theater: the suite a maintainer points the gate at drives no
    ``src/des`` production line — it asserts on fixtures without exercising the
    production path it claims to cover. The witness is the driven ``repo`` the AT
    supplies: a workspace with NO production-line-covering acceptance test (an
    empty/hermetic project, or a corpus whose ATs reach no production module) is
    theater. The scan is git-free (pure filesystem + text read over the driven
    workspace, no whole-repo subprocess).

    Target-aware (the genericità mandate, mirroring :func:`check_undefined_name`):
    the coverage scan looks for pytest ATs importing the ``des`` package, a
    Python/pytest-only dogfood signal. On a non-pytest target (``cargo-test`` /
    ``go-test`` / ``vitest``) the lever cannot apply: it CLEARS as NOT_APPLICABLE,
    carrying the loud ``health.gate.coverage-on-executed-path.not-applicable``
    reason — the per-language production-coverage check is the responsibility of
    that language's adapter, never a false flag on a non-Python target. ``runner``
    defaults to ``pytest`` so the existing Python path is byte-for-byte unchanged.
    """
    if runner != _PYTEST_RUNNER:
        return LeverResult(
            invariant_id="coverage_on_executed_path",
            flagged=False,
            structured_event=_COVERAGE_NOT_APPLICABLE_EVENT,
            target=str(repo),
            remediation=(
                f"{_COVERAGE_NOT_APPLICABLE_EVENT}: the coverage-on-executed-path "
                f"lever scans for pytest ATs importing `des` production code and "
                f"the target runner is `{runner}` — NOT_APPLICABLE (the "
                f"per-language production-coverage check is the responsibility of "
                f"the `{runner}` language adapter, not this pytest-only dogfood "
                f"lever; it does not false-flag a non-pytest target)"
            ),
        )
    coverage = _suite_covers_production_lines(repo)
    if coverage.covers:
        return LeverResult(invariant_id="coverage_on_executed_path", flagged=False)
    if coverage.unparseable:
        return LeverResult(
            invariant_id="coverage_on_executed_path",
            flagged=False,
            structured_event="health.gate.coverage-on-executed-path.parse-error.indeterminate",
            target=str(repo),
            remediation=(
                "health.gate.coverage-on-executed-path.parse-error.indeterminate: "
                f"{len(coverage.unparseable)} test file(s) under `{repo}` could not "
                f"be parsed ({', '.join(coverage.unparseable[:5])}"
                f"{', ...' if len(coverage.unparseable) > 5 else ''}) — the lever "
                f"cannot determine whether the suite covers production `des` code, "
                f"so it clears INDETERMINATE rather than falsely reporting theater; "
                f"fix the unparseable file(s) and re-run to get a real verdict"
            ),
        )
    return LeverResult(
        invariant_id="coverage_on_executed_path",
        flagged=True,
        structured_event="CoverageOnExecutedPathFlagged",
        target=str(repo),
        remediation=(
            f"the contract suite over `{repo}` drives zero `src/des` production "
            f"lines (coverage theater) — drive the real port in-process so each "
            f"AT executes the production path it claims to cover"
        ),
    )


@dataclass(frozen=True)
class _ProductionCoverageOutcome:
    """The AST-verified verdict of :func:`_suite_covers_production_lines`.

    ``covers`` — at least one test file has a real ``import des``/``from des
    import ...`` AST node. ``unparseable`` — test files that raised
    ``SyntaxError`` (relative paths, for the remediation message); a non-empty
    list on a ``covers=False`` verdict means the true answer is INDETERMINATE,
    not confirmed-theater — the caller must not collapse the two.
    """

    covers: bool
    unparseable: list[str] = field(default_factory=list)


def _suite_covers_production_lines(repo: Path) -> _ProductionCoverageOutcome:
    """AST-verified: does the driven workspace have >=1 AT reaching ``des`` code?

    A production-covering AT has a real ``ast.Import``/``ast.ImportFrom`` node
    whose dotted module head is ``des`` (never a text substring — a module
    merely named like ``destroyer`` or a docstring line quoting the phrase
    must not count, GDP-8). A workspace with NO such import — an empty/hermetic
    project, or a fixture-only corpus — covers zero production lines (theater).
    A file that fails to parse is reported as unparseable (INDETERMINATE),
    never silently skipped as if it had no production import.
    """
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return _ProductionCoverageOutcome(covers=False)
    unparseable: list[str] = []
    for test_file in tests_dir.rglob("test_*.py"):
        try:
            text = test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(text, filename=str(test_file))
        except SyntaxError:
            unparseable.append(str(test_file.relative_to(repo)))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "des" for alias in node.names):
                    return _ProductionCoverageOutcome(covers=True)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] == "des":
                    return _ProductionCoverageOutcome(covers=True)
    return _ProductionCoverageOutcome(covers=False, unparseable=unparseable)


# --- lever-2 F821 / undefined-name (target-aware NOT_APPLICABLE) -------------


def check_undefined_name(language: str = "python") -> LeverResult:
    """The ``undefined_name_check`` invariant — target-aware (DDD-2b / F4).

    On a non-Python target the F821 lever cannot apply: it CLEARS as
    NOT_APPLICABLE, carrying the loud ``health.gate.f821-unavailable.indeterminate``
    reason in its remediation — never ruff-hardcoded as a hard requirement, never
    a false flag. On a Python target the lever runs the undefined-name check over
    the test corpus (a present-but-clean corpus clears).
    """
    if language != "python":
        return LeverResult(
            invariant_id="undefined_name_check",
            flagged=False,
            structured_event="health.gate.f821-unavailable.indeterminate",
            remediation=(
                "health.gate.f821-unavailable.indeterminate: the F821/undefined-name "
                f"lever is Python-only and the target is `{language}` — NOT_APPLICABLE "
                f"(the lever cannot apply, it does not hard-fail a non-Python target)"
            ),
        )
    # Python target: the undefined-name check runs in pre-commit over the corpus;
    # the readiness invariant clears here (the pre-commit hook is the enforcer).
    return LeverResult(invariant_id="undefined_name_check", flagged=False)


# --- ZOMBIES-zero sad-path floor (L6) ----------------------------------------


def check_sad_path_floor(error_path_count: int, total_count: int) -> LeverResult:
    """FLAG a slice whose error-path AT count is below the non-vacuity floor.

    ZOMBIES-zero (L6): every slice must carry mandatory sad-path coverage. A
    slice with ZERO ``@error`` acceptance tests is flagged (target >=40% error/
    edge per ``nw-distill-coverage-obligations``). The witness is the slice's own
    ``.feature`` corpus the AT supplies; an empty/hermetic workspace has zero
    error-path ATs and is flagged.
    """
    if error_path_count > 0:
        return LeverResult(invariant_id="sad_path_floor", flagged=False)
    return LeverResult(
        invariant_id="sad_path_floor",
        flagged=True,
        structured_event="SadPathFloorFlagged",
        target=f"{error_path_count}/{total_count} error-path ATs",
        remediation=(
            "the slice carries zero @error / sad-path acceptance tests "
            "(ZOMBIES-zero floor; target >=40% error/edge) — add the mandatory "
            "sad-path coverage before the slice clears"
        ),
    )


def count_error_path_scenarios(
    repo: Path, feature_id: str, entering_slice: str
) -> tuple[int, int]:
    """Count the ``@error`` scenarios for the entering slice (pure FS read, no git).

    Returns ``(error_path_count, total_count)`` over the feature's ``.feature``
    files filtered to ``@<entering_slice>``. An absent corpus is ``(0, 0)`` —
    the empty workspace the ZOMBIES-zero AT drives flags on zero error-path ATs.
    """
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return (0, 0)
    error_path_count = 0
    total_count = 0
    slice_tag = f"@{entering_slice}"
    # gherkin-scope: KNOWN GAP (not fixed here) -- counts Gherkin @error
    # scenarios only; no pytest-side "@error density" authority exists
    # anywhere in this repo to compose (unlike the .feature-vs-pytest AT-
    # discovery gaps, this is not a same-fact-two-authorities duplicate, it
    # is an unextended metric). Flagged by lane/at-discovery-archtest
    # 2026-07-29 for triage.
    for feature_file in tests_dir.rglob("*.feature"):
        if feature_id not in feature_file.parts:
            continue
        try:
            lines = feature_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        pending = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("@"):
                pending = f"{pending} {stripped}"
                continue
            if stripped.startswith("Scenario:") or stripped.startswith(
                "Scenario Outline:"
            ):
                if slice_tag in pending:
                    total_count += 1
                    if "@error" in pending:
                        error_path_count += 1
                pending = ""
            elif stripped and not stripped.startswith("#"):
                pending = ""
    return (error_path_count, total_count)
