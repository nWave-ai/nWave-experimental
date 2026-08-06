"""
DES Configuration Adapter - Driven Port Implementation.

Loads configuration from .nwave/des-config.json and provides access to settings.
Falls back to safe defaults (audit logging ON) when file is missing or invalid.

Rigor cascade: project config -> global config -> standard defaults.
When a project has a "rigor" key, the entire global rigor block is ignored.

Hexagonal Architecture:
- DRIVEN ADAPTER: Implements configuration port (driven by business logic)
- ON BY DEFAULT: Audit logging enabled unless explicitly disabled in config
"""

import json
import os
from pathlib import Path
from typing import Any, cast

from des.domain.blast_radius import BlastRadiusConfigRejected, BlastRadiusThresholds
from des.domain.nwave_root import resolve_nwave_root
from des.domain.rigor.review_step_registry import (
    REVIEW_STEP_CATALOG,
    ResolvedReviewStepSet,
    ReviewStepResolver,
)


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
            effective_cwd = cwd or resolve_nwave_root()
            # `effective_cwd` may be RELATIVE (e.g. `Path(".")`, exactly what
            # `--repo .` / `--repo-dir .` produce). `_nearest_marker`'s
            # ascend-loop walks up via `.parent` and stops when
            # `current == current.parent` -- but `Path(".").parent ==
            # Path(".")` is pathlib's own behaviour for the trivial relative
            # path, so an un-resolved relative cwd self-loops the exit check
            # on the FIRST iteration and the walk-up never inspects the real
            # repo root. Resolve to absolute HERE, before `_config_path` is
            # built, so every downstream consumer (including
            # `_nearest_marker`) always ascends real directories regardless
            # of whether the caller passed a relative or absolute cwd.
            config_path = effective_cwd.resolve() / ".nwave" / "des-config.json"

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
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
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
    def attribution_enabled(self) -> bool:
        """Global ``attribution.enabled`` (fix-attribution-trailer-never-applied).

        Read from ``~/.nwave/global-config.json`` -> ``attribution.enabled``.
        Defaults to ``False`` when the key, the ``attribution`` block, or the
        whole file is absent/corrupt -- an unconfigured machine must never
        attribute (the install-time default of ``True`` for a *configured*
        install, written by ``attribution_plugin.py``, is preserved because a
        configured install carries the key explicitly).
        """
        attribution = self._global_config_data.get("attribution", {})
        if not isinstance(attribution, dict):
            return False
        enabled = attribution.get("enabled", False)
        return enabled if isinstance(enabled, bool) else False

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

    # ------------------------------------------------------------------
    # Blast-radius thresholds (EXTEND, feature blast-radius-measured-tier
    # slice-02). `_blast_radius()` is a sibling cascade to `_rigor()` /
    # `_housekeeping()`: project -> global -> empty dict, full-block
    # override (a project `blast_radius` key -- even empty -- shadows the
    # entire global block, same discipline as `_rigor()`).
    #
    # Per-key resolution (feature-delta "Floor/ceiling validation"):
    #   - ABSENT key -> the canonical hardcoded default, unchanged.
    #   - PRESENT but WRONG TYPE -> the canonical default (malformed, not
    #     deliberate -- mirrors `_scan_atdd_pure_int`'s non-int-degrades
    #     precedent in `carpaccio_format.py`).
    #   - PRESENT, well-typed, OUTSIDE its floor/ceiling -> HARD FAIL
    #     (`BlastRadiusConfigRejected`, GDP-3/GDP-6) -- never a silent
    #     clamp, never a silent fallback.
    # ------------------------------------------------------------------

    _BLAST_RADIUS_DEFAULTS = BlastRadiusThresholds()

    def _blast_radius(self) -> dict[str, Any]:
        """Return blast_radius sub-config via cascade: project -> global -> {}."""
        if "blast_radius" in self._config_data:
            return cast("dict[str, Any]", self._config_data["blast_radius"])
        return cast("dict[str, Any]", self._global_config_data.get("blast_radius", {}))

    def _resolve_blast_radius_int(
        self, key: str, default: int, *, floor: int, ceiling: int
    ) -> int:
        """Resolve one numeric `blast_radius.<key>` threshold (see class docstring)."""
        block = self._blast_radius()
        if key not in block:
            return default
        value = block[key]
        if not isinstance(value, int) or isinstance(value, bool):
            return default
        if value < floor or value > ceiling:
            raise BlastRadiusConfigRejected(
                f"blast_radius.{key}={value} in .nwave/des-config.json is "
                f"outside its valid range [{floor}, {ceiling}] -- fix the "
                f"value, or remove the key to use the framework default "
                f"({default})"
            )
        return value

    @property
    def blast_radius_small_max_files(self) -> int:
        """Threshold `blast_radius.small_max_files`. Floor 1, ceiling 20."""
        return self._resolve_blast_radius_int(
            "small_max_files",
            self._BLAST_RADIUS_DEFAULTS.small_max_files,
            floor=1,
            ceiling=20,
        )

    @property
    def blast_radius_small_max_lines(self) -> int:
        """Threshold `blast_radius.small_max_lines`. Floor 1, ceiling 500."""
        return self._resolve_blast_radius_int(
            "small_max_lines",
            self._BLAST_RADIUS_DEFAULTS.small_max_lines,
            floor=1,
            ceiling=500,
        )

    @property
    def blast_radius_small_max_consumers(self) -> int:
        """Threshold `blast_radius.small_max_consumers`. Floor 1, ceiling 50."""
        return self._resolve_blast_radius_int(
            "small_max_consumers",
            self._BLAST_RADIUS_DEFAULTS.small_max_consumers,
            floor=1,
            ceiling=50,
        )

    @property
    def blast_radius_large_min_consumers(self) -> int:
        """Threshold `blast_radius.large_min_consumers`.

        Floor is DYNAMIC: `small_max_consumers + 1` (the resolved value, not
        the canonical constant) -- the M band between them must never
        collapse to empty. Ceiling 1000.

        The floor is enforced against the EFFECTIVE resolved value, whether
        it came from an explicit config entry or fell through to the
        canonical default -- `_resolve_blast_radius_int` alone only checks
        the floor on the explicit-value path, so an ABSENT (or malformed)
        `large_min_consumers` key whose silent default now conflicts with an
        explicitly-raised `small_max_consumers` would otherwise slip through
        as a silently incoherent pair (D7).
        """
        small_max = self.blast_radius_small_max_consumers
        floor = small_max + 1
        value = self._resolve_blast_radius_int(
            "large_min_consumers",
            self._BLAST_RADIUS_DEFAULTS.large_min_consumers,
            floor=floor,
            ceiling=1000,
        )
        if value < floor:
            small_source = self._blast_radius_key_source("small_max_consumers")
            large_source = self._blast_radius_key_source("large_min_consumers")
            raise BlastRadiusConfigRejected(
                f"blast_radius.small_max_consumers={small_max} (effective, "
                f"{small_source}) and blast_radius.large_min_consumers="
                f"{value} (effective, {large_source}) in "
                ".nwave/des-config.json are incoherent -- large_min_consumers "
                "must be strictly greater than small_max_consumers so the M "
                "band never collapses to empty. Fix: raise "
                "blast_radius.large_min_consumers above "
                f"{small_max} in .nwave/des-config.json, or lower "
                "blast_radius.small_max_consumers."
            )
        return value

    def _blast_radius_key_source(self, key: str) -> str:
        """Report whether `blast_radius.<key>`'s effective value is explicit
        config or the canonical default -- for GDP-3 rejection messages."""
        block = self._blast_radius()
        if key not in block:
            return "its canonical default"
        raw = block[key]
        if not isinstance(raw, int) or isinstance(raw, bool):
            return "its canonical default (configured value malformed)"
        return "configured"

    @property
    def blast_radius_boundary_globs(self) -> tuple[str, ...]:
        """`blast_radius.boundary_globs` -- TYPE-only validation (feature-delta).

        A non-list, empty list, or a list containing any non-string/empty
        entry is malformed and falls back to the canonical default list
        WHOLESALE (never a partial/filtered list). A well-typed list
        REPLACES the default wholesale (D5) -- never merged/appended.
        """
        block = self._blast_radius()
        value = block.get("boundary_globs")
        if (
            isinstance(value, list)
            and value
            and all(isinstance(entry, str) and entry for entry in value)
        ):
            return tuple(value)
        return self._BLAST_RADIUS_DEFAULTS.boundary_globs

    def resolve_blast_radius_thresholds(self) -> BlastRadiusThresholds:
        """Assemble the full `BlastRadiusThresholds` from the cascade above.

        Raises `BlastRadiusConfigRejected` (propagated from any of the four
        numeric properties) when a present, well-typed value breaches its
        floor/ceiling -- the caller (the application-layer measurement
        orchestration) lets this propagate to the CLI's `BlastRadiusConfigRejected`
        handler unchanged.
        """
        return BlastRadiusThresholds(
            small_max_files=self.blast_radius_small_max_files,
            small_max_lines=self.blast_radius_small_max_lines,
            small_max_consumers=self.blast_radius_small_max_consumers,
            large_min_consumers=self.blast_radius_large_min_consumers,
            boundary_globs=self.blast_radius_boundary_globs,
        )

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
