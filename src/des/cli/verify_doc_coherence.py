"""``des verify-doc-coherence`` -- the P0.5 evidence-by-execution gate.

Expectation (evolution-plan P0.5): shipped docs cannot overstate the code.
The eval'd seat-booking repo's docs claimed Kysely, StrykerJS, OTel, npm
scripts and a /health endpoint -- none existed in the repo. Written-but-
never-true documentation is worse than honest absence: it is a claim no
inspection re-verifies, so it ships as a lie by default. This gate checks
every mechanically-checkable doc claim against the actual tree.

v1 checks (precision over recall -- every reported claim must be genuinely
false; anything ambiguous is skipped, never guessed):

    (a) npm-script claims  -- ``npm run <script>`` must name a script in
        package.json "scripts"; ``npm ci`` requires package-lock.json.
        No package.json at the repo root -> the arm is N/A, not a failure.
    (b) file-path claims   -- inline-code spans that look like repo-relative
        paths (contain "/", known extension or trailing "/", no placeholder
        chars, and whose top-level directory exists in the repo -- so
        example trees about OTHER projects are never flagged) must exist.
    (c) python -m claims   -- ``python -m <mod>`` must resolve to a module
        in the repo (src-layout aware), unless <mod> is a known external
        (pytest, pip, installed des.*, ...).

Verdicts (degrade-LOUD, never silent-pass; every failure states WHAT failed,
WHY, and HOW to fix -- the standing what/why/how rule):

    0  DocCoherenceVerified      -- every checked claim is true of the tree
    1  DocCoherenceRefused       -- >=1 claim is false; each is listed with
                                    doc file, line, claim, why-false, how-to-fix
    2  DocCoherenceIndeterminate -- no docs found / docs dir missing;
                                    NEVER a pass

Python + stdlib only. Purely filesystem: no git, no npm, no network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument


_EXIT_VERIFIED = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2

_NPM_RUN_RE = re.compile(r"\bnpm run ([A-Za-z0-9:_.@/-]+)")
_NPM_CI_RE = re.compile(r"\bnpm ci\b")
_PYTHON_M_RE = re.compile(r"\bpython[0-9.]*\s+-m\s+([A-Za-z_][A-Za-z0-9_.]*)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")

# Modules legitimately invoked via `python -m` without living in the repo:
# stdlib runnables + ubiquitous dev tools + the installed nWave runtime.
_PYTHON_MODULE_ALLOWLIST = frozenset(
    {
        "build",
        "coverage",
        "ensurepip",
        "http.server",
        "json.tool",
        "mutmut",
        "mypy",
        "pdb",
        "pip",
        "pipx",
        "pre_commit",
        "pytest",
        "ruff",
        "site",
        "timeit",
        "tox",
        "twine",
        "unittest",
        "venv",
    }
)
_PYTHON_MODULE_ALLOWED_PREFIXES = ("des",)

# A span only counts as a file-path CLAIM with a recognizable extension
# (or an explicit trailing "/"): bare words with slashes ("either/or",
# "input/output") never qualify.
_KNOWN_EXTENSIONS = frozenset(
    {
        ".cfg",
        ".cjs",
        ".css",
        ".csv",
        ".env",
        ".go",
        ".html",
        ".ini",
        ".ipynb",
        ".java",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".lock",
        ".md",
        ".mjs",
        ".ps1",
        ".py",
        ".rb",
        ".rs",
        ".sh",
        ".sql",
        ".tf",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
_PATH_FORBIDDEN_CHARS = frozenset("<>{}*$()[]\\\"'|;,?!=&#@ \t")

# Top-level segments that are runtime/config state, not committed-tree
# content: docs referencing `.nwave/<file>` or `.git/<file>` describe what a
# project MAY declare / what the tool creates at runtime -- never a claim
# that this tree ships the file. Widened at runtime (see
# `_load_gitignore_top_level_dirs`) by any top-level dir the TARGET repo's
# own `.gitignore` lists -- runtime state is agnostic to the dir's name.
_RUNTIME_STATE_TOP_LEVEL = frozenset({".git", ".nwave"})

# A claim sharing its line with an explicit negation/future marker is the
# doc being HONEST about absence (a REJECTED alternative, a "NEW"/CREATE_NEW
# planned module, an "is ABSENT" note, an open backlog row) -- never flag it.
#
# Extension point: `_HONEST_ABSENCE_PHRASINGS` below holds path-adjacent,
# precise EN/IT phrasings for the same honest-absence intent (a doc noting
# a claim was renamed/planned/removed). Each entry MUST be precise and
# path-adjacent -- never a bare word like "propose"/"proposed" on its own,
# which would blanket-suppress genuine missing-path claims written in a
# proposal-style sentence (see the RCA guard
# `test_bare_propose_word_does_not_suppress_a_real_missing_path_claim`).
_HONEST_ABSENCE_PHRASINGS: tuple[str, ...] = (
    r"since renamed to",
    r"not created in this tree",
    r"planned path",
    r"planned filename",
    r"not a repo path",
    r"removed;\s*no longer present",
    r"non ancora creato",
)
_NEGATED_LINE_RE = re.compile(
    r"\bNEW\b|\bCREATE_NEW\b|\bREJECTED\b|\bABSENT\b|\bMISSING\b|\bTODO\b"
    r"|\bTBD\b|Status:\s*OPEN"
    r"|\b[Ii]s deleted\b|\b[Ww]as deleted\b|\b[Dd]oes not exist\b"
    r"|\b[Dd]o not exist\b|\b[Nn]ot yet\b"
    r"|" + r"|".join(_HONEST_ABSENCE_PHRASINGS)
)

# A doc whose ADR "Status" section declares it not-current cannot overstate
# the code -- the doc itself says its content is not the present tree.
_DOC_STALE_STATUS_RE = re.compile(
    r"\b(Proposed|Draft|Superseded|Deprecated|Rejected|DESIGNED-NOT-BUILT)\b"
)

# Doc classes that are structurally NOT claims about the current tree
# (forward-looking feature deltas, internal analysis, archived/research
# material, proposals, ADRs, ...). The DEFAULT scan (``--docs`` omitted)
# drops any doc under these repo-relative prefixes; an EXPLICIT ``--docs``
# stays byte-unchanged (operator override).
#
# ``docs/product/backlog.md`` is the one FILE entry: the planning backlog's
# whole genre is not-yet-true work (deferred slices, untracked DISTILLs parked
# in other worktrees, paths a future feature will create), so its honest
# descriptions of absent paths are not claims about this tree. The entry is
# that file and never the ``docs/product/`` folder -- its siblings are product
# SSOT docs that DO describe the current tree.
_NOT_CURRENT_CLAIM_DOC_PREFIXES = frozenset(
    {
        "docs/product/backlog.md",
        "docs/feature/",
        "docs/analysis/",
        "docs/internal/",
        "docs/archive/",
        "docs/research/",
        "docs/evolution/",
        "docs/scenarios/",
        "docs/reports/",
        "docs/proposals/",
        "docs/adrs/",
        "docs/architecture/",
        "docs/product/architecture/",
        "docs/product/expectations/",
        "docs/feedback/",
        "docs/epic/",
        "docs/operations/",
        "docs/requirements/",
        "docs/backlog/",
        "docs/rfc/",
        "docs/spike/",
        "docs/decisions/",
    }
)


def _is_not_current_claim_doc(rel_posix: str) -> bool:
    """True when a doc's repo-relative path is a structurally-not-current-
    tree-claim class (dropped by the DEFAULT scan only)."""
    if any(rel_posix.startswith(prefix) for prefix in _NOT_CURRENT_CLAIM_DOC_PREFIXES):
        return True
    # Tutorial rule: any docs/guides/tutorial-*/ subdir names reader-example
    # paths the reader will create, never a claim about this repo's tree.
    parts = rel_posix.split("/")
    return (
        len(parts) > 2
        and parts[0] == "docs"
        and parts[1] == "guides"
        and parts[2].startswith("tutorial-")
    )


@dataclass(frozen=True)
class _Violation:
    """One doc claim proven false against the actual tree."""

    doc_file: str
    line: int
    claim: str
    why_false: str
    how_to_fix: str


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "DocCoherenceIndeterminate",
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _find_doc_files(repo: Path, docs: str | None) -> list[Path] | None:
    """Resolve the doc set; None means the requested docs location is absent."""
    if docs is not None:
        base = repo / docs
        if base.is_file():
            return [base]
        if not base.is_dir():
            return None
        return sorted(p for p in base.rglob("*.md") if p.is_file())
    files = [p for p in sorted(repo.glob("README*")) if p.is_file()]
    docs_dir = repo / "docs"
    if docs_dir.is_dir():
        files.extend(
            p
            for p in sorted(docs_dir.rglob("*.md"))
            if p.is_file()
            and not _is_not_current_claim_doc(p.relative_to(repo).as_posix())
        )
    return files


def _load_npm_scripts(repo: Path) -> frozenset[str] | None:
    """Script names from package.json, or None when the arm is N/A."""
    package_json = repo / "package.json"
    if not package_json.is_file():
        return None
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Unparseable manifest: treat the arm as N/A rather than guess.
        return None
    scripts = raw.get("scripts") if isinstance(raw, dict) else None
    if not isinstance(scripts, dict):
        return frozenset()
    return frozenset(str(name) for name in scripts)


def _warn_gitignore_unreadable(what: str) -> None:
    """Non-fatal degrade-LOUD notice for an unreadable `.gitignore` (permission
    denied, broken symlink, ...): emit the labeled event + a human WARNING line.
    NOT the fatal `_indeterminate` path -- this only fails to WIDEN exemptions,
    so it stays a WARNING and never touches the exit code (GDP-6, GDP-8)."""
    _emit(
        {
            "event": "DocCoherenceGitignoreUnreadable",
            "what": what,
            "why": (
                "an OSError (permission-denied, broken symlink, ...) "
                "prevented reading .gitignore -- the runtime-state "
                "exemption set could not be widened; unrelated real "
                "path claims are still checked normally."
            ),
            "how": (
                "fix .gitignore's file permissions/symlink, or ignore "
                "this notice -- it only means fewer paths are exempt."
            ),
        }
    )
    print(f"⚠ WARNING — {what}. Only affects the exemption set; checks continue.")


def _load_gitignore_top_level_dirs(repo: Path) -> frozenset[str]:
    """Top-level dir names the repo's OWN `.gitignore` lists -- unioned into
    the runtime-state exemption set (`_RUNTIME_STATE_TOP_LEVEL`) so a
    project's gitignored runtime state need not be hardcoded by name.
    Pure Python (`Path.read_text`), no `git` CLI -- mirrors
    `_load_npm_scripts`'s package.json read.

    No `.gitignore` -> empty (falls back to `_RUNTIME_STATE_TOP_LEVEL`
    alone, byte-identical to before this function existed). Unreadable
    `.gitignore` (OSError) -> degrades LOUD (emits a labeled event, prints a
    human-readable notice) but still returns empty -- this arm only WIDENS
    exemptions, so its failure mode is a resurfaced false-positive, never a
    silently-passed lie (GDP-6).

    Only single-segment, non-glob, non-negated top-level entries qualify
    (e.g. `.tmpstate/` -> `.tmpstate`); nested/negated/glob entries are
    skipped as ambiguous, never guessed.
    """
    gitignore = repo / ".gitignore"
    # A broken symlink (present-but-unresolvable) fails `is_file()` (which
    # follows symlinks) yet is NOT genuinely absent -- degrade LOUD like the
    # permission-denied case below, never silently drop mention of it.
    if gitignore.is_symlink() and not gitignore.exists():
        _warn_gitignore_unreadable(".gitignore could not be read (broken symlink)")
        return frozenset()
    if not gitignore.is_file():
        return frozenset()
    try:
        raw = gitignore.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _warn_gitignore_unreadable(f".gitignore could not be read ({exc})")
        return frozenset()
    top_level: set[str] = set()
    for raw_line in raw.splitlines():
        entry = raw_line.strip()
        if not entry or entry.startswith("#") or entry.startswith("!"):
            continue
        if any(ch in entry for ch in "*?["):
            continue
        name = entry.rstrip("/")
        if not name or "/" in name:
            continue
        top_level.add(name)
    return frozenset(top_level)


def _check_npm_claims(
    line: str,
    lineno: int,
    doc_rel: str,
    repo: Path,
    scripts: frozenset[str],
) -> list[_Violation]:
    violations: list[_Violation] = []
    for match in _NPM_RUN_RE.finditer(line):
        script = match.group(1).rstrip(".,;:")
        if script and script not in scripts:
            violations.append(
                _Violation(
                    doc_file=doc_rel,
                    line=lineno,
                    claim=f"npm run {script}",
                    why_false=(
                        f'package.json "scripts" has no entry "{script}" '
                        "-- the documented command does not exist."
                    ),
                    how_to_fix=(
                        f'add a "{script}" script to package.json, or '
                        "correct/remove the doc claim."
                    ),
                )
            )
    if _NPM_CI_RE.search(line) and not (repo / "package-lock.json").is_file():
        violations.append(
            _Violation(
                doc_file=doc_rel,
                line=lineno,
                claim="npm ci",
                why_false=(
                    "`npm ci` requires a committed package-lock.json and "
                    "the repo has none -- the documented command fails."
                ),
                how_to_fix=(
                    "commit package-lock.json (run `npm install` once), or "
                    "document `npm install` instead."
                ),
            )
        )
    return violations


def _is_checkable_path_claim(
    span: str, repo: Path, runtime_state_top_level: frozenset[str]
) -> bool:
    """Precision guards: only unambiguous repo-relative path claims qualify."""
    if "/" not in span or "://" in span or ".." in span:
        return False
    if span.startswith(("/", "~", "-", "%")):
        return False
    if any(c in _PATH_FORBIDDEN_CHARS for c in span):
        return False
    candidate = span.removeprefix("./")
    if not candidate or candidate.startswith("/"):
        return False
    if not (candidate.endswith("/") or Path(candidate).suffix in _KNOWN_EXTENSIONS):
        return False
    top_level = candidate.split("/", 1)[0]
    # Runtime-state guard: `.nwave/...` / `.git/...` (plus any top-level dir
    # the repo's own `.gitignore` lists) are declared-config / tool-runtime
    # locations, never claims about the committed tree.
    if top_level in runtime_state_top_level:
        return False
    # Example-tree guard: a path whose top-level directory does not exist
    # in this repo is a claim about some OTHER tree, not about this one.
    return (repo / top_level).is_dir()


def _check_path_claims(
    line: str,
    lineno: int,
    doc_rel: str,
    repo: Path,
    runtime_state_top_level: frozenset[str],
) -> list[_Violation]:
    violations: list[_Violation] = []
    for match in _INLINE_CODE_RE.finditer(line):
        span = match.group(1).strip()
        if not _is_checkable_path_claim(span, repo, runtime_state_top_level):
            continue
        candidate = span.removeprefix("./")
        if not (repo / candidate).exists():
            violations.append(
                _Violation(
                    doc_file=doc_rel,
                    line=lineno,
                    claim=span,
                    why_false=(
                        f"the docs reference `{span}` as a repo path and "
                        "no such file/directory exists in the tree."
                    ),
                    how_to_fix=(f"create {span}, or correct/remove the doc reference."),
                )
            )
    return violations


def _module_resolves(repo: Path, module: str) -> bool:
    rel = Path(*module.split("."))
    for base in (repo / "src", repo):
        if (base / rel).with_suffix(".py").is_file():
            return True
        if (base / rel / "__init__.py").is_file():
            return True
        if (base / rel / "__main__.py").is_file():
            return True
    return False


def _check_python_module_claims(
    line: str, lineno: int, doc_rel: str, repo: Path
) -> list[_Violation]:
    violations: list[_Violation] = []
    for match in _PYTHON_M_RE.finditer(line):
        module = match.group(1).rstrip(".")
        top = module.split(".", 1)[0]
        if module in _PYTHON_MODULE_ALLOWLIST or top in _PYTHON_MODULE_ALLOWLIST:
            continue
        if top in _PYTHON_MODULE_ALLOWED_PREFIXES:
            continue
        if not _module_resolves(repo, module):
            violations.append(
                _Violation(
                    doc_file=doc_rel,
                    line=lineno,
                    claim=f"python -m {module}",
                    why_false=(
                        f"module '{module}' resolves to no file in the repo "
                        "(checked <repo>/ and <repo>/src/ layouts) and is "
                        "not a known external tool."
                    ),
                    how_to_fix=(
                        "add the module, fix the module path in the doc, or "
                        "correct/remove the claim."
                    ),
                )
            )
    return violations


@dataclass
class _ScanResult:
    violations: list[_Violation]
    npm_claims: int = 0
    path_claims: int = 0
    python_module_claims: int = 0
    docs_skipped: int = 0
    docs_unreadable: list[str] = field(default_factory=list)


def _doc_declares_itself_not_current(text: str) -> bool:
    """True when the doc's Status section says it is not the present tree."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^#{1,4}\s*Status\b", line):
            for status_line in lines[i + 1 : i + 6]:
                if status_line.lstrip().startswith("#"):
                    break
                if _DOC_STALE_STATUS_RE.search(status_line):
                    return True
            return False
    return False


def _scan_doc(
    doc: Path,
    repo: Path,
    scripts: frozenset[str] | None,
    result: _ScanResult,
    runtime_state_top_level: frozenset[str],
) -> None:
    doc_rel = str(doc.relative_to(repo)) if doc.is_relative_to(repo) else str(doc)
    try:
        text = doc.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result.docs_unreadable.append(doc_rel)
        _emit(
            {
                "event": "DocCoherenceDocUnreadable",
                "doc_file": doc_rel,
                "what": f"doc '{doc_rel}' could not be read ({exc})",
                "why": (
                    "an OSError (permission-denied, broken symlink, ...) "
                    "prevented reading the doc -- its claims could not be "
                    "checked, so coherence cannot be confirmed."
                ),
                "how": (
                    "fix the file permissions/symlink so the doc is readable, "
                    "or remove it from the scanned doc set."
                ),
            }
        )
        return
    if _doc_declares_itself_not_current(text):
        result.docs_skipped += 1
        _emit(
            {
                "event": "DocCoherenceDocSkipped",
                "doc_file": doc_rel,
                "reason": (
                    "Status section declares the doc not-current "
                    "(Proposed/Draft/Superseded/Deprecated/Rejected/"
                    "DESIGNED-NOT-BUILT) -- it cannot overstate the tree."
                ),
            }
        )
        return
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        # Negation/future guard: a line that itself marks the claim as
        # absent/planned/rejected is honest -- nothing to refute on it.
        if _NEGATED_LINE_RE.search(line):
            continue
        # npm / python -m command claims live mostly INSIDE fenced examples,
        # so those arms scan every line.
        if scripts is not None:
            result.npm_claims += len(_NPM_RUN_RE.findall(line)) + len(
                _NPM_CI_RE.findall(line)
            )
            result.violations.extend(
                _check_npm_claims(line, lineno, doc_rel, repo, scripts)
            )
        result.python_module_claims += len(_PYTHON_M_RE.findall(line))
        result.violations.extend(
            _check_python_module_claims(line, lineno, doc_rel, repo)
        )
        # Path claims come from inline-code spans in PROSE only: fenced
        # blocks hold example trees/commands, a known false-positive pit.
        if not in_fence:
            path_violations = _check_path_claims(
                line, lineno, doc_rel, repo, runtime_state_top_level
            )
            result.path_claims += sum(
                1
                for m in _INLINE_CODE_RE.finditer(line)
                if _is_checkable_path_claim(
                    m.group(1).strip(), repo, runtime_state_top_level
                )
            )
            result.violations.extend(path_violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-doc-coherence",
        description=(
            "Check doc claims (npm scripts, repo paths, python -m modules) "
            "against the actual tree (evidence-by-execution gate, "
            "evolution P0.5)."
        ),
    )
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the repository."
    )
    parser.add_argument(
        "--docs",
        default=None,
        help=(
            "Directory (repo-relative) or file to scan for *.md docs; "
            "default: README* at repo root + docs/ recursively."
        ),
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        return _indeterminate(
            what=f"repo path {repo} is not a directory",
            why="the gate checks doc claims against an actual tree.",
            how="pass --repo pointing at the project root.",
        )

    docs = _find_doc_files(repo, args.docs)
    if docs is None:
        return _indeterminate(
            what=f"--docs location '{args.docs}' does not exist under {repo}",
            why="there is nothing to check; a silent pass here is the disease.",
            how="pass --docs pointing at an existing docs dir or file.",
        )
    if not docs:
        return _indeterminate(
            what="no doc files found (README* at root, docs/**/*.md)",
            why=(
                "the gate verifies that shipped docs do not overstate the "
                "code; with no docs there is nothing honest to verify."
            ),
            how="add docs, or pass --docs pointing at where they live.",
        )

    scripts = _load_npm_scripts(repo)
    if scripts is None:
        _emit(
            {
                "event": "DocCoherenceArmSkipped",
                "arm": "npm-scripts",
                "reason": "no parseable package.json at repo root (N/A)",
            }
        )

    runtime_state_top_level = _RUNTIME_STATE_TOP_LEVEL | _load_gitignore_top_level_dirs(
        repo
    )

    result = _ScanResult(violations=[])
    for doc in docs:
        _scan_doc(doc, repo, scripts, result, runtime_state_top_level)

    if result.docs_unreadable:
        return _indeterminate(
            what=(
                f"{len(result.docs_unreadable)} doc(s) could not be read: "
                f"{', '.join(result.docs_unreadable)}"
            ),
            why=(
                "an unreadable doc's claims cannot be checked -- coherence "
                "cannot be confirmed while a doc went unread."
            ),
            how=(
                "fix the file permissions/symlink for the doc(s) above so "
                "they are readable, or remove them from the scanned set."
            ),
        )

    if result.violations:
        _emit(
            {
                "event": "DocCoherenceRefused",
                "what": (
                    f"{len(result.violations)} doc claim(s) are false of "
                    "the actual tree"
                ),
                "why": (
                    "docs promising absent scripts/files/modules ship a lie "
                    "by default -- written-but-never-true documentation is "
                    "worse than honest absence."
                ),
                "how": (
                    "for each claim below: make it true (add the script/"
                    "file/module) or make the doc honest (fix/remove it)."
                ),
                "violations": [asdict(v) for v in result.violations],
            }
        )
        print(f"✗ REFUSED — {len(result.violations)} false doc claim(s):")
        for v in result.violations:
            print(f"  {v.doc_file}:{v.line} `{v.claim}` — {v.why_false}")
            print(f"    fix: {v.how_to_fix}")
        return _EXIT_REFUSED

    _emit(
        {
            "event": "DocCoherenceVerified",
            "doc_files": len(docs),
            "npm_claims": result.npm_claims,
            "path_claims": result.path_claims,
            "python_module_claims": result.python_module_claims,
            "docs_skipped_not_current": result.docs_skipped,
            "npm_arm": "checked" if scripts is not None else "n/a",
        }
    )
    total = result.npm_claims + result.path_claims + result.python_module_claims
    print(f"✓ PASS — doc↔code coherent ({len(docs)} doc files, {total} checked claims)")
    return _EXIT_VERIFIED


if __name__ == "__main__":
    sys.exit(main())
