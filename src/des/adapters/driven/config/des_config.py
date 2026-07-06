"""
DES Configuration Adapter - Driven Port Implementation.

Loads configuration from .nwave/des-config.json and provides access to settings.
Falls back to safe defaults (audit logging ON) when file is missing or invalid.

Rigor cascade: project config -> global config -> standard defaults.
When a project has a "rigor" key, the entire global rigor block is ignored.

update_check state (frequency, last_checked, skipped_versions) is machine-scoped
and read from / written to the GLOBAL config only -- it is NOT per-project. See
``_update_check`` and ``save_update_check_state``.

Hexagonal Architecture:
- DRIVEN ADAPTER: Implements configuration port (driven by business logic)
- ON BY DEFAULT: Audit logging enabled unless explicitly disabled in config
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.domain.nwave_dir_gitignore import ensure_nwave_gitignore
from des.domain.rigor.review_step_registry import (
    REVIEW_STEP_CATALOG,
    ResolvedReviewStepSet,
    ReviewStepResolver,
)


if TYPE_CHECKING:
    from des.domain.pending_update_flag import PendingUpdateFlag


# Closed set of declarable deliverable types (ADR-PST-002). A declared value
# outside this set is treated as absent -> safe default (``None``).
_KNOWN_DELIVERABLE_TYPES = frozenset({"application", "plugin", "skill"})

# Positive deliverable markers from FS detection. ``"application"`` is the
# absence of a marker, so it resolves to the ``None`` sentinel, NOT itself.
_POSITIVE_DELIVERABLE_MARKERS = frozenset({"plugin", "skill"})


class DESConfig:
    """
    Configuration loader for DES settings.

    Loads configuration from .nwave/des-config.json with on-by-default audit logging.
    Supports global configuration via ~/.nwave/global-config.json for cross-project
    rigor preferences. Does NOT auto-create config files.

    Rigor cascade: project rigor -> global rigor -> standard defaults.
    """

    _DEFAULT_GLOBAL_CONFIG_PATH = Path.home() / ".nwave" / "global-config.json"

    def __init__(
        self,
        config_path: Path | None = None,
        cwd: Path | None = None,
        *,
        global_config_path: Path | None = None,
    ):
        """
        Initialize DESConfig.

        Args:
            config_path: Optional explicit path to project config file
            cwd: Optional working directory (defaults to Path.cwd());
                 used to resolve .nwave/des-config.json when config_path is None
            global_config_path: Optional explicit path to global config file
                (keyword-only; defaults to ~/.nwave/global-config.json)
        """
        if config_path is None:
            effective_cwd = cwd or Path.cwd()
            config_path = effective_cwd / ".nwave" / "des-config.json"

        self._config_path = config_path
        self._config_data = self._load_json_file(self._config_path)

        self._global_config_path = (
            global_config_path
            if global_config_path is not None
            else self._DEFAULT_GLOBAL_CONFIG_PATH
        )
        self._global_config_data = self._load_json_file(self._global_config_path)

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any]:
        """
        Load configuration from a JSON file.

        Returns empty dict when the file is missing, corrupt, or unreadable.
        Pure function: no side effects beyond filesystem read.

        Args:
            path: Path to the JSON file to load

        Returns:
            Configuration dictionary, empty dict if loading fails
        """
        if not path.exists():
            return {}

        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        # Valid JSON that is not an object (``null``, ``[]``, ``123``, ``"x"``)
        # would crash every ``.get(...)`` caller. Coerce to ``{}`` so callers
        # fail open to safe defaults rather than raising on a malformed config.
        return parsed if isinstance(parsed, dict) else {}

    @property
    def skill_tracking_enabled(self) -> bool:
        """
        Check if skill loading tracking is enabled.

        Priority: DES_SKILL_TRACKING env var > config file > default (False).

        Returns:
            True if skill tracking enabled, False otherwise (defaults to False)
        """
        env_override = os.environ.get("DES_SKILL_TRACKING")
        if env_override is not None:
            return env_override.lower() in ("true", "1", "yes")
        strategy = self._config_data.get("skill_tracking", "disabled")
        return strategy != "disabled"

    @property
    def skill_tracking_strategy(self) -> str:
        """
        Get skill tracking strategy.

        Returns:
            Strategy string: "disabled", "passive-logging", or "token-tracking"
        """
        return self._config_data.get("skill_tracking", "disabled")

    @property
    def coverage_map_adoption(self) -> str:
        """Repo-wide coverage-map adoption switch: ``"active"`` | ``"inactive"``.

        fix-feature-end-ws-gate-applicability slice-04 (DDD-3). The feature-end
        cycle reads this from ``repo_root/.nwave/des-config.json`` (the SAME
        repo-level path no individual feature can shadow -- the LOAD-BEARING
        un-per-feature-gameability invariant) to decide whether an absent
        ``distill/coverage-map.md`` may be granted NOT_APPLICABLE.

        Two failure modes degrade in OPPOSITE directions (CONCERN-2): a key that
        is ABSENT from a present-and-parseable config ⇒ ``"inactive"`` (the
        permissive NA, the designed 0/74 pre-adoption default); a config file
        that is MALFORMED / unreadable ⇒ ``"active"`` (hard-verify, degrade
        toward MORE rigour -- an unreadable switch must never silently grant NA).

        The standard ``_load_json_file`` collapses absent and corrupt files to
        ``{}`` (it cannot itself distinguish them), so this property closes the
        gap with an explicit present-and-parseable pre-check rather than reading
        an empty load as "key absent". No second full read path is forked: the
        pre-check only classifies success vs failure of the SAME config file.
        """
        if not self._config_present_and_parseable():
            return "active"
        value = self._config_data.get("coverage_map_adoption", "inactive")
        return value if isinstance(value, str) else "inactive"

    def _config_present_and_parseable(self) -> bool:
        """True iff the project config file exists and parses as a JSON object.

        Distinguishes "key absent" (file present + parseable, returns True) from
        "file malformed/unreadable" (returns False) -- the
        ``_load_json_file:85-91`` absent==corrupt collapse the coverage-map
        adoption switch must NOT conflate. An absent file is also treated as
        present-and-parseable (no config ⇒ the designed inactive default), so
        ONLY a genuinely malformed/unreadable present file returns False.
        """
        if not self._config_path.exists():
            return True
        try:
            json.loads(self._config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        return True

    @property
    def audit_logging_enabled(self) -> bool:
        """
        Check if audit logging is enabled.

        Priority: DES_AUDIT_LOGGING_ENABLED env var > config file > default (True).

        Returns:
            True if audit logging enabled, False otherwise (defaults to True)
        """
        env_override = os.environ.get("DES_AUDIT_LOGGING_ENABLED")
        if env_override is not None:
            return env_override.lower() in ("true", "1", "yes")
        return self._config_data.get("audit_logging_enabled", True)

    # ------------------------------------------------------------------
    # Activation gating (EXTEND, ADR-AG-002 / DDD-3).
    # ``activation_mode`` reads ``activation.mode`` from the GLOBAL config
    # (default ``"opt-in"``). ``enabled_for_repo`` reads ``enabled_for_repo``
    # from the per-project MARKER file ``.nwave/local-config.json`` (NOT
    # ``des-config.json``), returning ``None`` when absent/keyless/corrupt.
    # Both fail-to-default; neither mutates.
    # ------------------------------------------------------------------

    @property
    def activation_mode(self) -> str:
        """Global ``activation.mode`` (``"opt-in"`` | ``"all"``); default ``"opt-in"``."""
        activation = self._global_config_data.get("activation", {})
        if not isinstance(activation, dict):
            return "opt-in"
        mode = activation.get("mode", "opt-in")
        return mode if mode in ("opt-in", "all") else "opt-in"

    @property
    def enabled_for_repo(self) -> bool | None:
        """Per-project marker ``enabled_for_repo`` from ``.nwave/local-config.json``.

        Walk-up resolution (ADR-AG-002, amended 2026-06-18): ascend parent dirs
        from the project dir and use the NEAREST ``.nwave/local-config.json``
        (nearer-wins), stopping at ``$HOME`` — ``$HOME/.nwave/`` is the global
        config home, never a project marker. ``None`` when no marker is found,
        or the nearest marker is key-missing / corrupt.
        """
        marker_path = self._nearest_marker()
        if marker_path is None:
            return None
        marker_data = self._load_json_file(marker_path)
        value = marker_data.get("enabled_for_repo")
        return value if isinstance(value, bool) else None

    @property
    def deliverable_type(self) -> str | None:
        """Resolved project deliverable type (ADR-PST-002) -- RED scaffold.

        DISTILL scaffold (feature plugin-skill-deliverable-type, issue #66).
        Resolution precedence (first match wins), implemented by DELIVER:
          1. declared ``.nwave/des-config.json`` -> ``deliverable_type`` (if in
             the known set ``{application, plugin, skill}``);
          2. declared global ``~/.nwave/global-config.json`` ->
             ``defaults.deliverable_type``;
          3. root-only FS detection (``deliverable_type_detector``) -- fallback
             ONLY when the declaration is FULLY ABSENT;
          4. unknown / typo'd declared value (present-but-bad, project OR global)
             -> SAFE DEFAULT (enforcement ON; returns ``None``) + a config-load
             warning. It does NOT fall through to detection (revised 2026-06-26,
             review non-blocker 2). Mirrors the ``activation_mode`` pattern
             (``des_config.py``: bad value -> hardcoded safe default, no detection
             fallback). A typo'd repo with a root ``skills/`` dir therefore stays
             enforced -- detection must not silently rescue a malformed declaration.

        Returns ``None`` (NOT ``"application"``) when nothing resolves -- the
        unresolved state is distinguishable from a positive ``application``
        declaration (HIGH-1 adapter contract). The enforcement fail-safe does NOT
        depend on this return value: the policy's closed exempt set
        (ADR-PST-001) is the load-bearing guarantee.

        Pure read over a bounded universe ``{declared_project, declared_global,
        ROOT-ONLY dir_listing}`` -- never mutates, never recurses nested dirs.

        Implemented to date (steps 01-01 + 01-03 -- positive resolution path):
          - project declaration in the known set -> that value (authoritative);
          - project declaration PRESENT-but-bad (typo'd) -> safe default ``None``,
            WITHOUT falling through (a malformed declaration is never silently
            rescued -- the typo fail-safe edge is finalised in step 03-02);
          - project declaration ABSENT -> fall through to the global
            ``defaults.deliverable_type`` (machine-wide default);
          - global default in the known set -> that value;
          - nothing resolves -> ``None``.
        Root-only FS detection (precedence step 3) is phase 02 -- the seam is the
        fall-through that currently terminates at ``None`` once the global default
        is exhausted; detection slots in there without disturbing the declared
        branches above.
        """
        declared = self._config_data.get("deliverable_type")
        if declared is not None:
            # Present -> the project's word is authoritative (good or typo'd);
            # a typo'd value never falls through to the global default.
            return declared if declared in _KNOWN_DELIVERABLE_TYPES else None
        # Project silent: the machine-wide default stands in (precedence step 2).
        defaults = self._global_config_data.get("defaults", {})
        global_default = (
            defaults.get("deliverable_type") if isinstance(defaults, dict) else None
        )
        if global_default in _KNOWN_DELIVERABLE_TYPES:
            return global_default
        # Nothing declared (project or global): fall through to root-only FS
        # detection (precedence step 3, ADR-PST-002). Reached ONLY when the
        # declaration is FULLY ABSENT -- a present-but-typo'd value short-circuits
        # to ``None`` above and never arrives here.
        return self._detect_deliverable_type()

    def _detect_deliverable_type(self) -> str | None:
        """Root-only FS detection rung; ``None`` for an unmarked (application) tree.

        Delegates to ``deliverable_type_detector`` over the project root (the
        ``.nwave/des-config.json``'s grandparent). An ``"application"`` detection
        means "no positive marker" -> ``None`` (HIGH-1: the unresolved sentinel,
        distinguishable from a declared ``application``). A positive
        ``plugin``/``skill`` marker resolves to that type.
        """
        from des.adapters.driven.config.deliverable_type_detector import (
            detect_deliverable_type,
        )

        detected = detect_deliverable_type(self._config_path.parent.parent)
        # Only a POSITIVE marker resolves; an ``"application"`` detection means
        # "no positive marker" -> ``None`` (HIGH-1 sentinel). Using
        # ``_KNOWN_DELIVERABLE_TYPES`` here would wrongly return ``"application"``.
        return detected if detected in _POSITIVE_DELIVERABLE_MARKERS else None

    def _nearest_marker(self) -> Path | None:
        """Nearest ``.nwave/local-config.json`` at or above the project dir.

        Starts at the project dir (``.nwave/des-config.json``'s grandparent) and
        ascends while ``dir != Path.home()`` and ``dir != dir.parent``. The first
        directory carrying a ``.nwave/local-config.json`` wins (nearer-wins).
        ``$HOME`` is the stop boundary and is never inspected as a project root.
        """
        home = Path.home()
        current = self._config_path.parent.parent
        while current not in (home, current.parent):
            candidate = current / ".nwave" / "local-config.json"
            if candidate.exists():
                return candidate
            current = current.parent
        return None

    def _rigor(self) -> dict:
        """Return rigor sub-config via cascade: project -> global -> empty dict.

        When the project config contains a "rigor" key (even if empty),
        the entire global rigor block is ignored -- full block override.
        """
        if "rigor" in self._config_data:
            return self._config_data["rigor"]
        return self._global_config_data.get("rigor", {})

    def _update_check(self) -> dict:
        """Return update_check sub-config from the GLOBAL config.

        Update-check cadence/state (frequency, last_checked, skipped_versions)
        is a per-machine concern -- "has this machine asked PyPI recently?" --
        not a per-project one. It therefore lives in
        ``~/.nwave/global-config.json``, independent of the working directory.
        Storing it per-project caused sibling folders to gate independently and
        a folder with a same-day timestamp to self-suppress the update banner.
        """
        return self._global_config_data.get("update_check", {})

    def _housekeeping(self) -> dict:
        """Return housekeeping sub-config dict, defaulting to empty dict."""
        return self._config_data.get("housekeeping", {})

    @property
    def rigor_profile(self) -> str:
        """Get rigor profile name. Default: 'standard'."""
        return self._rigor().get("profile", "standard")

    @property
    def rigor_agent_model(self) -> str:
        """Get agent model from rigor config. Default: 'sonnet'."""
        return self._rigor().get("agent_model", "sonnet")

    @property
    def rigor_reviewer_model(self) -> str:
        """Get reviewer model. Default: 'haiku'."""
        return self._rigor().get("reviewer_model", "haiku")

    @property
    def rigor_human_authorization(self) -> bool:
        """Whether a two-party HUMAN authorization (GO) is required for the
        AT-review verdict. Default: ``False`` (velocity-v2, Ale 2026-07-04).

        Off by default: EXAMINE (the independent examiner) provides the default
        outcome-independence, and the mechanical seal + the AT-completeness check
        provide the AT attestation, so the two-party human GO is an OPT-IN
        compliance layer (regulated industry), not the baseline. When ``True`` the
        readiness gate hard-requires a recorded ``ATReviewVerdict APPROVED``; when
        ``False`` that invariant is advisory (the carpaccio seal-check covers the
        attestation at the same dispatch.pre) -- this closes the beta-tester
        "asked several times per slice" grind.
        """
        return bool(self._rigor().get("human_authorization", False))

    @property
    def rigor_tdd_phases(self) -> tuple[str, ...]:
        """Get TDD phases as tuple.

        Default: canonical 3-phase (RED, GREEN, COMMIT) per ADR-025 (default
        flip 2026-05-18). Existing projects with an explicit ``rigor.tdd_phases``
        list in ``.nwave/des-config.json`` continue to override this default
        unchanged (backward-compat preserved).
        """
        phases = self._rigor().get(
            "tdd_phases",
            ["RED", "GREEN", "COMMIT"],
        )
        return tuple(phases)

    @property
    def rigor_feature_total_at_advisory_threshold(self) -> int:
        """Get the whole-feature AT-volume advisory threshold.

        Read from the rigor cascade (project -> global -> @property default).
        When a feature's total AT count exceeds this threshold, the DISTILL
        Total-AT trigger emits a (never-blocking) advisory proposing
        ``/nw-discuss`` (elephant-carpaccio split). Default: 12 (DD-3 -- the
        default lives in this fallback, NOT hard-wired elsewhere; per-profile
        numbers are a rigor-profile build detail). Distinct locus from
        ``carpaccio_slice_max`` (``config.yaml`` ``atdd_pure.``) so the two
        thresholds never collapse onto one knob (C3).
        """
        return self._rigor().get("feature_total_at_advisory_threshold", 12)

    @property
    def rigor_review_enabled(self) -> bool:
        """Check if peer review is enabled. Default: True."""
        return self._rigor().get("review_enabled", True)

    @property
    def rigor_double_review(self) -> bool:
        """Check if double review is enabled. Default: False."""
        return self._rigor().get("double_review", False)

    # ------------------------------------------------------------------
    # Rigor review-step registry (EXTEND -- feature rigor-review-step-toggles,
    # ADR-RST-001 / DSN-1..DSN-3). DISTILL active-RED scaffold (slice-01):
    # the method EXISTS so collection + the in-process driving call resolve,
    # but the body delegates to the pure-domain resolver. DELIVER (slice-01)
    # reads the ``rigor.review_steps`` overrides + the master
    # ``rigor_review_enabled`` flag and delegates to
    # ``des.domain.rigor.review_step_registry.ReviewStepResolver``.
    # ------------------------------------------------------------------
    def resolve_review_steps(self) -> ResolvedReviewStepSet:
        """Resolve the active DISTILL review-step set for this project.

        Reads the per-step ``rigor.review_steps`` overrides and the
        profile-level ``rigor_review_enabled`` flag, then delegates to the pure
        ``ReviewStepResolver``. Per DSN-3 the precedence is ``enabled = True if
        always_on else (override.enabled if present else review_enabled)``; the
        returned ``ResolvedReviewStepSet.active()`` yields the firing steps
        (each carrying ``.id``).
        """
        overrides = self._rigor().get("review_steps", {})
        return ReviewStepResolver().resolve(
            REVIEW_STEP_CATALOG,
            overrides,
            self.rigor_review_enabled,
            self.rigor_reviewer_model,
        )

    @property
    def rigor_refactor_pass(self) -> bool:
        """Check if refactoring pass is enabled. Default: True."""
        return self._rigor().get("refactor_pass", True)

    @property
    def update_check_frequency(self) -> str | None:
        """Get update check frequency.

        Read from the GLOBAL config (machine-scoped; see ``_update_check``).
        Returns None when the update_check key is entirely absent from the
        global config (indicates first run — no config bootstrapped yet).
        Returns 'daily' when the update_check key exists but frequency sub-key
        is absent.
        """
        update_check = self._global_config_data.get("update_check")
        if update_check is None:
            return None  # key absent = first run, no global config yet
        return update_check.get("frequency", "daily")

    @property
    def installed_package_manager(self) -> str | None:
        """PM recorded at install time, from the GLOBAL config (machine-scoped).

        ``~/.nwave/global-config.json`` -> ``install.package_manager``. Recorded
        by ``nwave-ai install`` from its own interpreter, where detection is
        reliable; consumed by ``/nw-update`` whose ambient interpreter is not.
        Returns None when unrecorded (installed before this existed, or a pip
        install with no PM marker).
        """
        return self._global_config_data.get("install", {}).get("package_manager")

    @property
    def update_check_last_checked(self) -> str | None:
        """Get last update check timestamp (ISO 8601 UTC). Default: None."""
        return self._update_check().get("last_checked", None)

    @property
    def update_check_skipped_versions(self) -> list[str]:
        """Get list of versions skipped by user. Default: empty list."""
        return self._update_check().get("skipped_versions", [])

    @property
    def update_check_latest_available(self) -> str | None:
        """Latest version discovered by the last successful update check.

        Recorded in the GLOBAL config update_check block and consumed by
        ``/nw-update`` to resolve the upgrade target. None when never recorded.
        """
        return self._update_check().get("latest_available")

    @property
    def housekeeping_enabled(self) -> bool:
        """Check if housekeeping is enabled. Default: True."""
        return self._housekeeping().get("enabled", True)

    @property
    def housekeeping_audit_retention_days(self) -> int:
        """Get audit log retention period in days. Default: 7."""
        return self._housekeeping().get("audit_retention_days", 7)

    @property
    def housekeeping_signal_staleness_hours(self) -> int:
        """Get signal file staleness threshold in hours. Default: 4."""
        return self._housekeeping().get("signal_staleness_hours", 4)

    @property
    def housekeeping_skill_log_max_bytes(self) -> int:
        """Get maximum skill log size in bytes before rotation. Default: 1 MiB."""
        return self._housekeeping().get("skill_log_max_bytes", 1_048_576)

    # --- Observability (NWave unified logging) ---

    @property
    def log_level(self) -> str:
        """Log level: NW_LOG_LEVEL env > config log_level > default WARN."""
        env = os.environ.get("NW_LOG_LEVEL")
        if env:
            return env.upper()
        return self._config_data.get("log_level", "WARN").upper()

    @property
    def log_enabled(self) -> bool:
        """Log enabled: NW_LOG env > config log_enabled > default False."""
        env = os.environ.get("NW_LOG")
        if env is not None:
            return env.lower() in ("true", "1", "yes")
        return bool(self._config_data.get("log_enabled", False))

    def save_update_check_state(
        self,
        last_checked: str,
        skipped_versions: list[str],
        frequency: str | None = None,
        latest_available: str | None = None,
    ) -> None:
        """
        Persist update check state to the GLOBAL config file.

        Update-check state is machine-scoped (see ``_update_check``), so it is
        written to ``~/.nwave/global-config.json`` rather than the project
        config. Read-modify-write: preserves all other global config keys.
        Creates update_check key when absent.

        Args:
            last_checked: ISO 8601 UTC timestamp of last check
            skipped_versions: list of version strings user has skipped
            frequency: if None, preserves existing frequency (or leaves default)
            latest_available: latest version discovered by the check; when None,
                any previously stored value is preserved. Consumed by
                ``/nw-update`` to resolve the upgrade target without re-querying.
        """
        current_data: dict[str, Any] = {}
        if self._global_config_path.exists():
            try:
                current_data = json.loads(
                    self._global_config_path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                current_data = {}

        update_check = dict(current_data.get("update_check", {}))
        update_check["last_checked"] = last_checked
        update_check["skipped_versions"] = skipped_versions
        if frequency is not None:
            update_check["frequency"] = frequency
        elif "frequency" not in update_check:
            # Bootstrap default on first save (e.g. after first-run check)
            update_check["frequency"] = "daily"
        if latest_available is not None:
            update_check["latest_available"] = latest_available

        current_data["update_check"] = update_check

        self._global_config_path.parent.mkdir(parents=True, exist_ok=True)
        ensure_nwave_gitignore(self._global_config_path.parent)
        self._global_config_path.write_text(
            json.dumps(current_data, indent=2), encoding="utf-8"
        )

    # --- Pending update flag I/O (deferred self-update) ---

    @property
    def pending_update_path(self) -> Path:
        """Path to the pending-update flag file (~/.nwave/pending-update.json)."""
        return Path.home() / ".nwave" / "pending-update.json"

    def save_pending_update_state(self, flag: "PendingUpdateFlag") -> None:
        """Persist PendingUpdateFlag to pending_update_path as JSON.

        Creates the parent directory and the runtime ``.gitignore`` sentinel
        (invariant: every time we touch ``~/.nwave/`` we ensure it is ignored).
        """
        path = self.pending_update_path
        path.parent.mkdir(parents=True, exist_ok=True)
        ensure_nwave_gitignore(path.parent)
        path.write_text(json.dumps(flag.to_dict(), indent=2), encoding="utf-8")

    def read_pending_update(self) -> "PendingUpdateFlag | None":
        """Read pending-update flag. Returns None if missing or invalid JSON."""
        from des.domain.pending_update_flag import PendingUpdateFlag

        path = self.pending_update_path
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return PendingUpdateFlag.from_dict(payload)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return None

    def clear_pending_update(self) -> None:
        """Remove the pending-update flag file. Idempotent (no error if absent)."""
        path = self.pending_update_path
        try:
            path.unlink()
        except FileNotFoundError:
            pass
