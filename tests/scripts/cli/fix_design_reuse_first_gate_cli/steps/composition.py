"""Composition root for the reuse-first design CLI acceptance slice-01.

F-DESIGN-REUSE-FIRST-GATE-CLI (DDD-1..DDD-7), Mandate-12 + Pillar 3. Wires
the PRODUCTION ``check_reuse_first_design.py`` CLI entry point
(``scripts.cli.check_reuse_first_design.main``) against a tmp_path feature
project. Business logic lives here as the single source of truth; step
bodies delegate to ``ReuseFirstFixture`` methods and never inline logic.

Layer 3 (in-process subprocess-equivalent / FS acceptance): the CLI is the
driving port; the driven ports are the real filesystem (tmp_path for the
feature-delta) plus a fixture-injection ``--git-diff-source=path:<file>``
flag (the synthetic NEW-component oracle for slice-01 -- real git diff
invocation is slice-02 territory). No PBT machinery (Mandate 9/11) -- the
walking-skeleton verdict set is a finite enumerable closed set.

Pure-function contract (DDD-3 unbounded-preservation): the CLI reads the
feature-delta and emits a verdict (exit code + single-line stdout token);
it performs NO filesystem mutation. ``capture_universe`` snapshots the
feature-delta so the @then step state-delta guard proves the read-only
contract (Mandate 8).

Structured-verdict contract (DDD-4): the CLI emits exactly ONE single-line
stdout token::

    reuse_first feature=<id> new_components=<n> justified=<m> verdict=<PASS|FAIL>

The verdict mapping below reads that ``verdict=`` substring -- a STRUCTURED
machine token, never a free-text natural-language stdout substring. An
unknown or absent token raises rather than silently defaulting.

RED scaffold note (Mandate 7): the production
``scripts/cli/check_reuse_first_design.py`` module does not exist on master.
The crafter authors a RED scaffold (``__SCAFFOLD__ = True``; ``main`` raises
``AssertionError``) in A_GREEN_ATS so the import resolves and the
invocation raises a semantic ``AssertionError`` (MISSING_FUNCTIONALITY RED),
not a collection-time ``ModuleNotFoundError``. ``_invoke_cli`` defends the
pre-scaffold state by catching ``ModuleNotFoundError`` and returning the
``UNRECOGNISED_INVOCATION`` verdict; once the scaffold lands, the path is
``AssertionError`` -> ``UNRECOGNISED_INVOCATION`` (still RED-for-the-right
reason at the AT layer); once the implementation lands, the path is the
real stdout token -> PASS / FAIL.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    AddedPathKind,
    BaseBranch,
    FeatureId,
    FeatureShape,
    MethodologyPathKind,
    ReuseFirstVerdict,
    ScopedPath,
)


# Type alias for the feature-shape builder callbacks. Declared at module
# top so the dispatch dict's type is precise and step bodies remain a
# single composition call (Mandate-12 criterion 3).
_BuilderFn = Callable[["ReuseFirstFixture"], None]


# Production module path -- imported lazily inside ``run_check`` so the
# AT module imports cleanly even before the crafter authors the RED scaffold.
_CLI_MODULE = "scripts.cli.check_reuse_first_design"

# The closed `verdict` token set the CLI emits on the single stdout line
# (DDD-4). This mapping IS the structured contract the crafter must
# implement -- the AT reads the token, never a free-text stdout substring.
# An off-contract or absent token raises (see ``CheckResult.verdict``) so a
# wrong token fails loudly.
_VERDICT_TOKEN: dict[str, ReuseFirstVerdict] = {
    "PASS": ReuseFirstVerdict.PASS,
    "FAIL": ReuseFirstVerdict.FAIL,
    "MALFORMED": ReuseFirstVerdict.MALFORMED,
}


@dataclass
class CheckResult:
    """Observable outcome of one check_reuse_first_design CLI invocation.

    The CLI emits exactly ONE single-line stdout token (DDD-4); the verdict
    is read from the ``verdict=<TOKEN>`` substring of that line.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict=`` token of the single-line stdout output.

        Returns the ``verdict=<TOKEN>`` substring's TOKEN, or ``None`` when
        stdout carries no parseable single-line token (the master/RED-scaffold
        state -- the scaffold raises before printing, so no token line
        exists).
        """
        for line in self.stdout.splitlines():
            stripped = line.strip()
            if not stripped.startswith("reuse_first "):
                continue
            # Single-line token shape: reuse_first feature=X new_components=N
            # justified=M verdict=<TOKEN>. Extract the verdict= field.
            for field_token in stripped.split():
                if field_token.startswith("verdict="):
                    return field_token[len("verdict=") :]
        return None

    @property
    def verdict(self) -> ReuseFirstVerdict:
        """Map the CLI output onto the user-observable verdict.

        Reads the structured ``verdict=`` token (the stable machine
        contract), never free-text substrings.

          - No ``verdict=`` token at all -> UNRECOGNISED_INVOCATION: the CLI
            produced no structured output (the master/RED-scaffold state).
          - An off-contract token -> ``ValueError``, failing the test loudly.
        """
        token = self._verdict_token
        if token is None:
            return ReuseFirstVerdict.UNRECOGNISED_INVOCATION
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"check_reuse_first_design CLI emitted an off-contract verdict "
                f"token {token!r}; expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]

    @property
    def new_component_count(self) -> int | None:
        """The ``new_components=`` count of the single-line stdout token (DDD-4).

        slice-02 reads this to assert how many NEW components the detector
        found in the feature's real commit range. Returns ``None`` when no
        structured token line exists (the master/RED-scaffold state) so the
        @then step fails for the right reason rather than silently coercing
        an absent token to zero.
        """
        for line in self.stdout.splitlines():
            stripped = line.strip()
            if not stripped.startswith("reuse_first "):
                continue
            for field_token in stripped.split():
                if field_token.startswith("new_components="):
                    return int(field_token[len("new_components=") :])
        return None


@dataclass
class ReuseFirstFixture:
    """Production-wired composition root for the reuse-first CLI slices.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta is provisioned via ``provision_feature_shape`` so each
    scenario builds exactly the NEW-component-vs-Reuse-Analysis-section
    shape it needs; the CLI is then invoked through its argv entry point
    against that feature.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("reuse-first-cli-demo"))

    # --- paths ---------------------------------------------------------------

    @property
    def _feature_dir(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_dir / "feature-delta.md"

    @property
    def _diff_source_path(self) -> Path:
        """Path of the synthetic git-diff oracle file (DDD-7).

        slice-01 uses ``--git-diff-source=path:<file>`` fixture-injection so
        the AT does not depend on a live git repo state. The file lists one
        NEW class name per line (e.g. ``WidgetService``). slice-02 promotes
        to real ``git diff master...HEAD`` invocation.
        """
        return self.repo_dir / ".reuse-first-cli" / "diff_source.txt"

    # --- Given: feature provisioning ----------------------------------------

    def create_feature(self, feature_id: FeatureId) -> None:
        """Create the feature directory skeleton."""
        self.feature_id = feature_id
        self._feature_dir.mkdir(parents=True, exist_ok=True)

    def provision_feature_shape(self, shape: FeatureShape) -> None:
        """Write the feature-delta + git-diff oracle for the chosen shape."""
        builder = _FEATURE_SHAPE_BUILDERS[shape]
        builder(self)

    def _write_feature_delta(self, body: str) -> None:
        self.feature_delta_path.write_text(body, encoding="utf-8")

    def _write_diff_source(self, new_class_names: list[str]) -> None:
        self._diff_source_path.parent.mkdir(parents=True, exist_ok=True)
        self._diff_source_path.write_text(
            "\n".join(new_class_names) + "\n", encoding="utf-8"
        )

    # --- When: run the CLI --------------------------------------------------

    def run_check(self) -> CheckResult:
        """Invoke the production check_reuse_first_design CLI.

        Uses ``--feature-id <id>`` + ``--repo-root <dir>`` +
        ``--git-diff-source=path:<file>`` to point the CLI at the tmp_path
        feature project. Captures stdout/stderr in-process for token
        reading.

        Defends the pre-scaffold state: if the production module does not
        exist yet (``ModuleNotFoundError``), returns a synthetic
        UNRECOGNISED_INVOCATION result so the AT fails with a semantic
        assertion error in the @then step rather than a collection-time
        import error. Once the crafter authors the scaffold the path
        becomes ``AssertionError`` propagated from the scaffold's ``main``;
        once the implementation lands, the path is the real stdout token.
        """
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
            f"--git-diff-source=path:{self._diff_source_path}",
        ]
        try:
            cli_module = importlib.import_module(_CLI_MODULE)
        except ModuleNotFoundError:
            return CheckResult(
                exit_code=-1,
                stdout="",
                stderr=f"production module {_CLI_MODULE!r} not yet authored",
            )
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exit_code = cli_module.main(argv)
        return CheckResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The CLI has a pure-function contract: it reads the feature-delta and
        the git-diff oracle and MUST NOT mutate either. The universe is the
        feature-delta's existence + bytes + the diff-source's existence +
        bytes -- the state-delta guard proves the read-only contract
        (@contract-shape:unbounded-preservation).
        """
        return {
            "feature_delta.exists": self.feature_delta_path.exists(),
            "feature_delta.bytes": (
                self.feature_delta_path.read_bytes()
                if self.feature_delta_path.exists()
                else None
            ),
            "diff_source.exists": self._diff_source_path.exists(),
            "diff_source.bytes": (
                self._diff_source_path.read_bytes()
                if self._diff_source_path.exists()
                else None
            ),
        }

    # === slice-02: real git-diff-driven detection ===========================
    #
    # slice-02 promotes the detector from the slice-01 fixture-injected name
    # list to the feature's REAL commit range (DDD-7): the fixture provisions
    # a real ``git init`` repository with a base commit on a base branch and a
    # feature commit that adds a class file, then invokes the CLI against the
    # real ``git diff --name-status <base>...HEAD`` range. The base branch and
    # the scoped path are configurable (DDD-7 ``--base-branch`` / ``--scoped
    # -path`` flags). Real driven adapter (filesystem + git subprocess) ->
    # @real-io, example-based, no PBT (Mandate 9 v2 OR-reduction).

    _DEFAULT_BASE_BRANCH = BaseBranch("master")
    _DEFAULT_SCOPED_PATH = ScopedPath("src")

    # The feature branch the NEW-component commit lands on. The base branch
    # stays pinned at the seed commit so ``git diff --name-status <base>...HEAD``
    # is non-empty (the feature commit DIVERGES from the base).
    _FEATURE_BRANCH = "feature"

    def _git(self, *args: str) -> None:
        """Run a git command in the feature repository (real subprocess)."""
        subprocess.run(
            ["git", *args],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def init_repository(self, base_branch: BaseBranch) -> None:
        """Initialise a real git repo with a base commit on ``base_branch``.

        The feature-delta directory (under ``docs/feature/<id>/``) is seeded on
        the base branch so it is NOT itself a NEW added path of the feature's
        commit range -- only the later class-file commit is the feature delta.

        Idempotent under re-invocation: the Background always inits the repo on
        the default base; a scenario that diverges from a NAMED base branch
        re-invokes this with that branch. When the repo already exists, only
        the current branch is renamed to the requested base -- the base commit
        is NOT re-seeded (it already exists).
        """
        if (self.repo_dir / ".git").exists():
            self._git("branch", "-m", str(base_branch))
            self._base_branch = base_branch
            return
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self._git("init", "--initial-branch", str(base_branch))
        self._git("config", "user.email", "reuse-first@example.test")
        self._git("config", "user.name", "Reuse First Fixture")
        # Seed the feature-delta directory on the base branch so the feature's
        # NEW component is the class file added on the feature branch, not the
        # docs scaffolding.
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        (self._feature_dir / ".gitkeep").write_text("", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "base: seed feature directory")
        self._base_branch = base_branch

    def commit_new_component(
        self, class_name: str, added_path_kind: AddedPathKind
    ) -> None:
        """Commit a feature change that adds a NEW class under a path kind.

        Diverges from the base branch first: on the first invocation the fixture
        creates and switches to the feature branch (``git checkout -b feature``)
        off the pinned base commit, so the base branch stays at the seed commit
        and HEAD advances on the feature branch. Then adds
        ``<added_path_kind>/<snake>.py`` declaring ``class <class_name>(`` in a
        feature commit. The real ``git diff --name-status <base>...HEAD``
        therefore reports this file as added (status ``A``); the detector greps
        it for the NEW class. Without the branch divergence
        ``<base>...HEAD`` would be empty (HEAD == base tip) and the detector
        would correctly find zero NEW components.
        """
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if current_branch != self._FEATURE_BRANCH:
            self._git("checkout", "-b", self._FEATURE_BRANCH)
        module_dir = self.repo_dir / str(added_path_kind.value)
        module_dir.mkdir(parents=True, exist_ok=True)
        module_file = module_dir / f"{_snake_case(class_name)}.py"
        module_file.write_text(
            f"class {class_name}(object):\n    pass\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-m", f"feat: add {class_name}")

    def write_reuse_analysis(self, *, naming: str | None) -> None:
        """Author the feature-delta's Reuse Analysis section.

        When ``naming`` is a class name, the section's Existing Component
        column names it (justified). When ``naming`` is ``None``, the section
        names an unrelated component only (the NEW class is unjustified).
        """
        named = naming if naming is not None else "UnrelatedService"
        justification = (
            "concrete justification for the extension"
            if naming is not None
            else "this row does not mention the added component at all"
        )
        rows = (
            f"| {named} | src/{_snake_case(named)}.py | extends existing "
            f"service layer | EXTEND | {justification} |\n"
        )
        self._write_feature_delta(_doc(_reuse_analysis_section(rows)))

    def run_check_on_range(
        self,
        *,
        base_branch: BaseBranch | None = None,
        scoped_path: ScopedPath | None = None,
    ) -> CheckResult:
        """Invoke the CLI against the feature's REAL commit range (DDD-7).

        Drives the slice-02 flags: ``--base-branch`` (the trunk the feature
        diverged from) and ``--scoped-path`` (the source-tree prefix that
        counts as feature code), replacing the slice-01 fixture-injection
        ``--git-diff-source=path:<file>``. The CLI runs the real
        ``git diff --name-status <base>...HEAD`` itself.

        Defends the pre-implementation state the same way slice-01 does: a
        ``ModuleNotFoundError`` (module absent) yields a synthetic
        UNRECOGNISED_INVOCATION result so the @then step fails for the right
        reason rather than at collection time. Once the slice-02 flags exist
        the path is the real stdout token.
        """
        effective_base = base_branch or getattr(
            self, "_base_branch", self._DEFAULT_BASE_BRANCH
        )
        effective_scope = scoped_path or self._DEFAULT_SCOPED_PATH
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
            "--base-branch",
            str(effective_base),
            "--scoped-path",
            str(effective_scope),
        ]
        try:
            cli_module = importlib.import_module(_CLI_MODULE)
        except ModuleNotFoundError:
            return CheckResult(
                exit_code=-1,
                stdout="",
                stderr=f"production module {_CLI_MODULE!r} not yet authored",
            )
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        # The slice-01 CLI argparse shell does not yet accept --base-branch /
        # --scoped-path and still requires --git-diff-source. Before the
        # slice-02 flags land, argparse raises SystemExit(2) on the unknown /
        # missing flags. Catch it and surface a synthetic
        # UNRECOGNISED_INVOCATION result so the @then step fails for the right
        # reason (MISSING_FUNCTIONALITY: a semantic assertion in the Then step
        # that the structured verdict is absent) rather than a raw SystemExit
        # escaping mid-When. Once the slice-02 flags exist the path is the real
        # stdout token.
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                exit_code = cli_module.main(argv)
            except SystemExit as exc:
                return CheckResult(
                    exit_code=exc.code if isinstance(exc.code, int) else -1,
                    stdout=stdout_buf.getvalue(),
                    stderr=(
                        stderr_buf.getvalue()
                        + "slice-02 flags (--base-branch / --scoped-path) "
                        "not yet accepted by the CLI argparse shell"
                    ),
                )
        return CheckResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    def capture_repo_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot of the feature repository (Mandate 8).

        slice-02 runs a real ``git diff`` against the feature repository; the
        read-only contract (DDD-3) is that the invocation mutates nothing the
        architect can observe: not the feature-delta bytes, not the committed
        HEAD, not the working-tree porcelain status. The state-delta guard over
        this universe proves the bounded-change / unbounded-preservation
        contract for the real-git path.
        """
        return {
            "feature_delta.bytes": (
                self.feature_delta_path.read_bytes()
                if self.feature_delta_path.exists()
                else None
            ),
            "repo.head_sha": self._git_head_sha(),
            "repo.porcelain_status": self._git_porcelain_status(),
        }

    def _git_head_sha(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _git_porcelain_status(self) -> str:
        return subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    # === slice-03: methodology file-component detection =====================
    #
    # slice-03 adds a SECOND detection unit (DDD-8 path-kind dispatch): an added
    # file under a methodology-path kind (``nWave/data/**``, ``nWave/skills/**``,
    # ``scripts/cli/**``) is ITSELF a NEW component keyed by its repo-relative
    # path/stem (DDD-10), NOT grepped for ``^class``. It COMPOSES with the
    # class-component unit; ``new_components`` is the UNION (DDD-11). The fixture
    # commits a methodology file analogously to ``commit_new_component`` and the
    # CLI is invoked with the declared ``--methodology-path`` kinds (additive to
    # the ``src/`` code-path default).

    # The declared methodology-path kinds for the current scenario. Drives the
    # ``--methodology-path`` flags on ``run_check_on_range_with_methodology``.
    _declared_methodology_kinds: tuple[MethodologyPathKind, ...] = ()

    def commit_methodology_file(
        self, stem: str, methodology_path_kind: MethodologyPathKind
    ) -> None:
        """Commit a feature change that adds a NEW methodology file (DDD-9).

        Diverges from the base branch first (mirrors ``commit_new_component``):
        on the first invocation the fixture creates and switches to the feature
        branch off the pinned base commit. Then adds
        ``<methodology_path_kind>/<stem>.<ext>`` as a content-free methodology
        artifact (a data SSOT under ``nWave/data``, a skill under
        ``nWave/skills``, or a gate under ``scripts/cli``). The real
        ``git diff --name-status <base>...HEAD`` reports this file as added
        (status ``A``); the file-component detector keys it by path/stem WITHOUT
        a ``^class`` grep (DDD-11: file-components are components by virtue of
        being added, not by content). The declared kind is recorded so the
        invocation passes the matching ``--methodology-path`` flag.
        """
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if current_branch != self._FEATURE_BRANCH:
            self._git("checkout", "-b", self._FEATURE_BRANCH)
        ext = _METHODOLOGY_FILE_EXT[methodology_path_kind]
        module_file = self.repo_dir / str(methodology_path_kind.value) / f"{stem}{ext}"
        module_file.parent.mkdir(parents=True, exist_ok=True)
        module_file.write_text(f"# methodology artifact: {stem}\n", encoding="utf-8")
        self._declared_methodology_kinds = (
            *self._declared_methodology_kinds,
            methodology_path_kind,
        )
        self._git("add", "-A")
        self._git("commit", "-m", f"feat(methodology): add {stem}")

    def write_reuse_analysis_naming(self, *, named: list[str]) -> None:
        """Author the feature-delta's Reuse Analysis section naming components.

        Each entry of ``named`` is the component key (a class name or a
        methodology-file stem/path) the architect declares as justified in the
        Existing Component column (column 1) of a Reuse Analysis row. An empty
        list authors a section naming only an unrelated component (so every
        added component is unjustified -- the FAIL shape).
        """
        entries = named if named else ["UnrelatedService"]
        rows = "".join(
            f"| {entry} | src/{_snake_case(entry)}.py | extends existing "
            f"surface | EXTEND | concrete justification for {entry} |\n"
            for entry in entries
        )
        self._write_feature_delta(_doc(_reuse_analysis_section(rows)))

    def run_check_on_range_with_methodology(
        self,
        *,
        base_branch: BaseBranch | None = None,
        scoped_path: ScopedPath | None = None,
    ) -> CheckResult:
        """Invoke the CLI against the real commit range WITH methodology paths.

        Drives the slice-03 ``--methodology-path`` flag (additive to the
        ``src/`` code-path default, DDD-9): each declared methodology kind is
        passed so the path-kind dispatcher routes added files under it to
        file-component mode (DDD-8). All other slice-02 real-diff behaviour is
        unchanged.

        Defends the pre-implementation state the same way slice-02 does: a
        ``ModuleNotFoundError`` yields a synthetic UNRECOGNISED_INVOCATION; an
        unknown ``--methodology-path`` flag raises ``SystemExit(2)`` from the
        slice-02 argparse shell, caught and surfaced as a synthetic
        UNRECOGNISED_INVOCATION so the @then assertion fires
        (RED-for-the-right-reason at the AT layer) rather than a raw SystemExit
        escaping mid-When. Once the slice-03 flag + dispatcher land the path is
        the real stdout token -> PASS / FAIL with the union count.
        """
        effective_base = base_branch or getattr(
            self, "_base_branch", self._DEFAULT_BASE_BRANCH
        )
        effective_scope = scoped_path or self._DEFAULT_SCOPED_PATH
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
            "--base-branch",
            str(effective_base),
            "--scoped-path",
            str(effective_scope),
        ]
        for kind in self._declared_methodology_kinds:
            argv.extend(["--methodology-path", str(kind.value)])
        try:
            cli_module = importlib.import_module(_CLI_MODULE)
        except ModuleNotFoundError:
            return CheckResult(
                exit_code=-1,
                stdout="",
                stderr=f"production module {_CLI_MODULE!r} not yet authored",
            )
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                exit_code = cli_module.main(argv)
            except SystemExit as exc:
                return CheckResult(
                    exit_code=exc.code if isinstance(exc.code, int) else -1,
                    stdout=stdout_buf.getvalue(),
                    stderr=(
                        stderr_buf.getvalue()
                        + "slice-03 flag (--methodology-path) not yet accepted "
                        "by the CLI argparse shell"
                    ),
                )
        return CheckResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )

    # === slice-06: methodology-path default-wiring closure ==================
    #
    # slice-06 closes the SKILL-vs-IMPL drift: slice-05's skill prose promises
    # "the CLI DEFAULTS to nWave/data, nWave/skills, scripts/cli", but the impl
    # has ``--methodology-path default=None`` -> file-component detection is
    # DEFAULT-OFF -> a caller who OMITS the flag (CI, the post-DESIGN gate
    # wiring) gets a vacuous PASS where a NEW methodology SSOT artifact ships
    # unchallenged. The slice-03/05 ATs all pass ``--methodology-path``
    # explicitly, so the no-flag default-on behaviour was never pinned -- which
    # is WHY the default-off deviation shipped silently. slice-06 invokes the
    # CLI over the SAME real-diff path WITHOUT the flag; GREEN makes the three
    # published-language paths default-ON.

    def run_check_on_range_without_methodology_flag(
        self,
        *,
        base_branch: BaseBranch | None = None,
        scoped_path: ScopedPath | None = None,
    ) -> CheckResult:
        """Invoke the CLI over the real commit range with NO --methodology-path.

        Identical to ``run_check_on_range_with_methodology`` EXCEPT it emits no
        ``--methodology-path`` flag at all -- the no-flag default-wiring path
        (slice-06). On master the flag default is ``None`` -> file-component
        detection is OFF -> a committed methodology file is invisible ->
        vacuous PASS. The slice-06 AT asserts FAIL: GREEN wires the three
        published-language paths (``nWave/data``, ``nWave/skills``,
        ``scripts/cli``) ON by default so the no-flag invocation detects the
        methodology file-component.

        Defends the pre-implementation state the same way the sibling methods
        do: a ``ModuleNotFoundError`` yields a synthetic UNRECOGNISED_INVOCATION
        result; a ``SystemExit`` from the argparse shell is caught and surfaced
        as UNRECOGNISED_INVOCATION so the @then assertion fires
        (RED-for-the-right-reason at the AT layer) rather than a raw SystemExit
        escaping mid-When.
        """
        effective_base = base_branch or getattr(
            self, "_base_branch", self._DEFAULT_BASE_BRANCH
        )
        effective_scope = scoped_path or self._DEFAULT_SCOPED_PATH
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--repo-root",
            str(self.repo_dir),
            "--base-branch",
            str(effective_base),
            "--scoped-path",
            str(effective_scope),
        ]
        # NOTE: deliberately NO --methodology-path flag. This is the contract
        # slice-06 pins -- the published-language default set must be active
        # without the flag.
        try:
            cli_module = importlib.import_module(_CLI_MODULE)
        except ModuleNotFoundError:
            return CheckResult(
                exit_code=-1,
                stdout="",
                stderr=f"production module {_CLI_MODULE!r} not yet authored",
            )
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                exit_code = cli_module.main(argv)
            except SystemExit as exc:
                return CheckResult(
                    exit_code=exc.code if isinstance(exc.code, int) else -1,
                    stdout=stdout_buf.getvalue(),
                    stderr=stderr_buf.getvalue(),
                )
        return CheckResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )


# The on-disk file extension each methodology-path kind uses (DDD-9). Content
# is irrelevant to file-component detection (DDD-11 path-keyed), but a
# kind-faithful extension keeps the fixture realistic: data SSOT -> .yaml,
# skill prose -> .md, gate script -> .py.
_METHODOLOGY_FILE_EXT: dict[MethodologyPathKind, str] = {
    MethodologyPathKind.DATA_SSOT: ".yaml",
    MethodologyPathKind.SKILL_PROSE: ".md",
    MethodologyPathKind.CLI_GATE: ".py",
}


def _snake_case(class_name: str) -> str:
    """Map ``WidgetService`` -> ``widget_service`` for the module file name."""
    out: list[str] = []
    for index, char in enumerate(class_name):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


# --- feature-shape fixture builders -----------------------------------------
# Module-level dispatch keeps each Given step body a single typed lookup +
# a single composition call (Mandate-12 criterion 3: no control flow in
# step bodies).


def _reuse_analysis_section(rows: str) -> str:
    """Assemble a canonical Reuse Analysis section per the sibling DDD-8
    normative source (heading + 5-column GFM table)."""
    header = (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|--------------------|------|---------|----------|---------------|\n"
    )
    return header + rows


def _doc(*sections: str) -> str:
    return "# Feature Delta: reuse-first cli fixture\n\n" + "\n\n".join(sections) + "\n"


def _build_one_new_component_justified(fixture: ReuseFirstFixture) -> None:
    """AT1 GREEN happy path: one NEW class named in Reuse Analysis."""
    rows = (
        "| WidgetService | src/widget_service.py | extends existing service "
        "layer | EXTEND | concrete justification for the extension |\n"
    )
    fixture._write_feature_delta(_doc(_reuse_analysis_section(rows)))
    fixture._write_diff_source(["WidgetService"])


def _build_one_new_component_unjustified(fixture: ReuseFirstFixture) -> None:
    """AT2 FAIL sad path: one NEW class absent from Reuse Analysis.

    The feature-delta carries a well-formed Reuse Analysis section that
    discusses an UNRELATED component -- ``OrphanService`` (the NEW class
    in the diff source) is NOT named in any row of the section. This is
    the exact recurrence-vector defect the gate-or-residue policy targets:
    a structurally well-formed table that does not justify the actually
    -introduced NEW component.
    """
    rows = (
        "| UnrelatedService | src/unrelated.py | structural reuse | EXTEND "
        "| this row does not mention OrphanService at all |\n"
    )
    fixture._write_feature_delta(_doc(_reuse_analysis_section(rows)))
    fixture._write_diff_source(["OrphanService"])


_FEATURE_SHAPE_BUILDERS: dict[FeatureShape, _BuilderFn] = {
    FeatureShape.ONE_NEW_COMPONENT_JUSTIFIED: _build_one_new_component_justified,
    FeatureShape.ONE_NEW_COMPONENT_UNJUSTIFIED: _build_one_new_component_unjustified,
}
