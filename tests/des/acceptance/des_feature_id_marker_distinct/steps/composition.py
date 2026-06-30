"""Composition root for the des-feature-id-marker-distinct slice (C5, AD-61).

Wires the PRODUCTION surfaces the feature changes:

  * ``des.domain.des_marker_parser.DesMarkerParser`` -- the REAL marker parser.
    AC-1 / AC-4 drive ``parse`` directly (Layer 1-2, a pure no-I/O domain
    surface) and observe the parsed ``feature_id`` / ``project_id`` fields.

  * ``des.adapters.drivers.hooks.pre_tool_use_handler._evaluate_u1_intercept`` --
    the REAL carpaccio dispatch resolution function carrying line 165
    (``feature_id = markers.project_id`` at HEAD; the fix changes it to
    ``markers.feature_id or markers.project_id``). AC-2 / AC-3 drive THIS
    production function over a dispatch prompt and observe the feature-id it
    resolves.

Mandate-13 (driving-port-only) -- how the resolved feature-id is observed
without re-implementing the resolution in the test: ``_evaluate_u1_intercept``
resolves the feature-id, then feeds it into ``intercept_atdd_pure_dispatch(
feature_id=...)`` (the documented M1 U1 intercept driving port). The handler
module imports that symbol into its own namespace and calls it unqualified, so
we record the resolved value by substituting a recorder for
``pre_tool_use_handler.intercept_atdd_pure_dispatch``. Only that downstream
boundary (which itself wraps the carpaccio CLI subprocess -- production-injectable
I/O) is stubbed; the resolution at line 165 is the REAL production code under
test. The test asserts on the production resolution's OUTPUT, never on a
re-derived value.

Business logic lives in the production surfaces above; step bodies delegate to
``FeatureIdResolutionComposition`` methods and never inline logic (Mandate-15 /
Mandate-12 criterion 3).

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD:
  * AC-1 -- ``DesMarkers`` has no ``feature_id`` field and the parser has no
    DES-FEATURE-ID pattern, so the observed parsed feature-id is ``None`` (not
    "feat-X") -> the Then RED-fails for the right reason (missing functionality).
  * AC-2 -- the resolution reads ``markers.project_id`` -> resolves "proj-Y",
    not "feat-X" -> RED.
  * AC-3 / AC-4 -- live-green preservation guards.
The composition imports the production symbols at module load; both already
exist on HEAD (the parser and ``_evaluate_u1_intercept``), so collection never
errors -- the failure is a value AssertionError, never an ImportError.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from des.adapters.drivers.hooks import pre_tool_use_handler
from des.domain.des_marker_parser import DesMarkerParser

from .domain_types import DispatchMarkers, FeatureId, ProjectId


def _marker_line(name: str, value: str) -> str:
    """Render one DES marker in the canonical ``<!-- DES-X : value -->`` shape."""
    return f"<!-- {name} : {value} -->"


def _render_dispatch_prompt(markers: DispatchMarkers) -> str:
    """Render an atdd_pure carpaccio dispatch prompt carrying the requested markers.

    The prompt carries the full atdd_pure dispatch marker set the carpaccio
    resolution recognises (DES-MODE:atdd_pure + DES-PHASE + DES-SLICE), plus the
    feature-id and/or project-id markers under test. A ``None`` identity omits
    its marker line entirely.
    """
    lines = [
        "# DES_METADATA",
        "<!-- DES-VALIDATION : required -->",
        _marker_line("DES-MODE", "atdd_pure"),
        _marker_line("DES-PHASE", "A_GREEN_ATS"),
        _marker_line("DES-SLICE", "slice-01"),
    ]
    if markers.feature_id is not None:
        lines.append(_marker_line("DES-FEATURE-ID", markers.feature_id))
    if markers.project_id is not None:
        lines.append(_marker_line("DES-PROJECT-ID", markers.project_id))
    return "\n".join(lines)


# Sentinel returned by the recorder when the carpaccio resolution never reached
# the intercept (e.g. blocked earlier on a missing feature-id). Distinct from any
# real id so an assertion observing it reports a clear RED reason.
_UNRESOLVED = "<<unresolved>>"


@dataclass
class _ResolvedFeatureIdRecorder:
    """Records the feature-id the REAL resolution feeds into the U1 intercept.

    Substituted for ``pre_tool_use_handler.intercept_atdd_pure_dispatch`` so the
    feature-id resolved at ``pre_tool_use_handler.py:165`` is captured as the
    production code passes it downstream. Returns a non-blocking decision so
    ``_evaluate_u1_intercept`` completes normally (it then returns ``None`` ==
    allow), keeping the focus on the OBSERVED resolved id.
    """

    resolved_feature_id: str = _UNRESOLVED

    def __call__(self, *, feature_id: str, **_kwargs: object) -> object:
        self.resolved_feature_id = feature_id

        class _AllowDecision:
            is_block = False

        return _AllowDecision()


@dataclass
class ParseObservation:
    """Port-exposed observable of a single ``DesMarkerParser.parse`` call.

    The Universe (Mandate-8) is exactly the two parsed identity fields the feature
    governs -- nothing internal. ``getattr`` with a ``None`` default reads
    ``feature_id`` whether or not the field exists yet, so AC-1 observes ``None``
    at HEAD (RED) rather than raising ``AttributeError`` (BROKEN).
    """

    feature_id: str | None
    project_id: str | None


class FeatureIdResolutionComposition:
    """Production-wired composition root for the feature-id-marker-distinct slice.

    Two driving surfaces, both REAL production code:
      * ``DesMarkerParser.parse`` (AC-1 / AC-4).
      * ``pre_tool_use_handler._evaluate_u1_intercept`` (AC-2 / AC-3).
    """

    def __init__(self) -> None:
        self._parser = DesMarkerParser()
        self._markers = DispatchMarkers()

    # --- prompt provisioning (Given) ----------------------------------------

    def given_markers(
        self,
        *,
        feature_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        """Record the feature-id / project-id markers the dispatch prompt carries."""
        self._markers = DispatchMarkers(
            feature_id=FeatureId(feature_id) if feature_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
        )

    # --- driving-port invocations (When) ------------------------------------

    def parse_dispatch(self) -> ParseObservation:
        """Parse the dispatch prompt via the REAL ``DesMarkerParser`` (AC-1 / AC-4)."""
        prompt = _render_dispatch_prompt(self._markers)
        parsed = self._parser.parse(prompt)
        return ParseObservation(
            feature_id=getattr(parsed, "feature_id", None),
            project_id=parsed.project_id,
        )

    def resolve_carpaccio_feature_id(self, monkeypatch: object, cwd: Path) -> str:
        """Run the REAL carpaccio resolution and return the feature-id it resolves.

        Drives ``pre_tool_use_handler._evaluate_u1_intercept`` -- the production
        function carrying the line-165 resolution. The resolved feature-id is
        captured at the production injectable seam (the value fed into
        ``intercept_atdd_pure_dispatch``) via a recorder substituted for that
        symbol in the handler module's namespace. The CWD is pinned to a real
        temp dir so the (untouched) project-root resolution is hermetic.
        """
        recorder = _ResolvedFeatureIdRecorder()
        # mypy: monkeypatch is the pytest fixture; typed as object to keep this
        # module import-light. setattr/chdir are the only methods used.
        monkeypatch.setattr(  # type: ignore[attr-defined]
            pre_tool_use_handler, "intercept_atdd_pure_dispatch", recorder
        )
        monkeypatch.chdir(cwd)  # type: ignore[attr-defined]
        prompt = _render_dispatch_prompt(self._markers)
        # The REAL resolution runs here: parses markers, resolves the feature-id
        # (line 165), and passes it to the (recorded) intercept.
        pre_tool_use_handler._evaluate_u1_intercept(prompt)
        return recorder.resolved_feature_id

    def project_id_preservation_delta(
        self,
    ) -> tuple[dict[str, str | None], dict[str, str | None]]:
        """Before/after parse snapshots witnessing project_id is preserved (AC-4).

        The perturbation is ADDING a DES-FEATURE-ID marker:
          * before -- parse a prompt carrying ONLY the recorded project-id marker;
          * after  -- parse a prompt carrying the recorded feature-id marker
            ALONGSIDE the same project-id marker.
        Both snapshots are taken via the REAL ``DesMarkerParser.parse``. The
        port-exposed Universe is the parsed ``project_id`` field; the Mandate-8
        assertion is that it is ``unchanged()`` across the delta (adding the
        feature-id marker does not change how project_id is parsed).
        """
        project_only = DispatchMarkers(project_id=self._markers.project_id)
        before_parsed = self._parser.parse(_render_dispatch_prompt(project_only))
        after_parsed = self._parser.parse(_render_dispatch_prompt(self._markers))
        before = {"project_id": before_parsed.project_id}
        after = {"project_id": after_parsed.project_id}
        return before, after
