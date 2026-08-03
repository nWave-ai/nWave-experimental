"""Composition root for the mikado-board declared-status-render slice.

slice-01 of `unified-slice-progress-visualization` (DES-1/DES-2/DES-7,
Mandate-12/Mandate-13). Wires the PRODUCTION `des` dispatcher
(``des.cli.__main__.main``) against a tmp_path repository fixture. Business
logic lives here as the single source of truth; step bodies delegate to
``MikadoBoardRenderComposition`` methods and never inline logic.

Driving-Port-Only Boundary (Mandate 13): every non-walking-skeleton scenario
drives ``des.cli.__main__.main`` IN-PROCESS -- the stable, ALREADY-EXISTING
`des` dispatcher entry point. This composition NEVER imports
``des.cli.mikado_board`` (the CREATE_NEW module DELIVER has not shipped yet)
at module top -- P1 of the in-process active-RED pattern
(nw-distill-red-scaffolding). ``mikado-board`` is not a row in
``des.cli.__main__._REGISTRY`` yet, so the dispatcher's own
``parser.parse_known_args`` raises ``SystemExit`` for the unrecognised
subcommand -- a RUNTIME failure inside the in-process call (P3), never a
collection-time ImportError. The walking-skeleton scenario instead forks the
REAL installed CLI as a subprocess (Layer-1, the feature's single
subprocess-e2e), proving the eventual registration is wired end-to-end.

Structured-verdict contract (pins the slice-01 CLI's machine output -- the
contract the crafter MUST implement, not a guess):

    ``des mikado-board render --feature <id> --repo-root <path>
    --format=json`` emits to stdout exactly ONE JSON object (single line)
    carrying a stable ``"verdict"`` token from the closed set::

        rendered | missing-feature-delta | missing-slice-plan
                 | malformed-slice-plan

    On ``rendered`` the object also carries ``"slices"``: a list of
    ``{"slice_id": ..., "declared_status": ..., "source": "slice-plan"}``
    rows in Slice Plan document order. The ``"source"`` field is the
    observable this feature's core claim ("zero independent re-derivation")
    hangs on -- an artifact the SUT itself must ship, not a string the test
    fabricates (protocol-driver contract, Mandate 13).

RED scaffold note: on master neither ``des.cli.mikado_board`` nor a
``mikado-board`` registry row exists -- every scenario below FAILS because
the response carries no ``verdict`` token (-> ``UNRECOGNISED_INVOCATION``),
never because of a missing import at collection time.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import run as _run_subprocess

# Production driving port -- the STABLE `des` dispatcher. It exists on
# master; DELIVER's slice-01 work adds a "mikado-board" row to its
# `_REGISTRY` and creates `des.cli.mikado_board`. Never import that
# not-yet-existing module here (P1, nw-distill-red-scaffolding).
from des.cli.__main__ import main as des_main
from tests.common.state_delta import assert_state_delta, unchanged

from .domain_types import (
    DeclaredStatus,
    FeatureId,
    RenderVerdict,
    SliceId,
    SlicePlanShape,
)


_VERDICT_TOKEN: dict[str, RenderVerdict] = {
    "rendered": RenderVerdict.RENDERED,
    "missing-feature-delta": RenderVerdict.MISSING_FEATURE_DELTA,
    "missing-slice-plan": RenderVerdict.MISSING_SLICE_PLAN,
    "malformed-slice-plan": RenderVerdict.MALFORMED_SLICE_PLAN,
}

_SLICE_PLAN_COLUMNS = (
    "Slice",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)


@dataclass
class RenderResult:
    """Observable outcome of one `des mikado-board render` invocation."""

    exit_code: int
    output: str

    @property
    def _payload(self) -> dict[str, object] | None:
        """The single JSON object the CLI emits to stdout, or ``None``.

        ``None`` when stdout carries no parseable JSON object with a
        ``verdict`` key -- the master state (the CLI does not exist yet, or
        argparse rejected the unrecognised subcommand and printed a usage
        banner instead of JSON).
        """
        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "verdict" in obj:
                    return obj
        return None

    @property
    def verdict(self) -> RenderVerdict:
        payload = self._payload
        if payload is None:
            return RenderVerdict.UNRECOGNISED_INVOCATION
        token = str(payload["verdict"])
        if token not in _VERDICT_TOKEN:
            raise ValueError(
                f"mikado-board render emitted an off-contract verdict token "
                f"{token!r}; expected one of {sorted(_VERDICT_TOKEN)}"
            )
        return _VERDICT_TOKEN[token]

    def declared_status(self, slice_id: str) -> DeclaredStatus | None:
        """The rendered ``declared_status`` for ``slice_id``, or ``None``."""
        payload = self._payload
        if payload is None:
            return None
        for row in payload.get("slices", []):  # type: ignore[union-attr]
            if row.get("slice_id") == slice_id:
                return DeclaredStatus(row["declared_status"])
        return None

    def source_of(self, slice_id: str) -> str | None:
        """The rendered ``source`` field for ``slice_id`` -- the artifact
        this feature's "zero independent re-derivation" claim hangs on."""
        payload = self._payload
        if payload is None:
            return None
        for row in payload.get("slices", []):  # type: ignore[union-attr]
            if row.get("slice_id") == slice_id:
                return row.get("source")
        return None

    def slice_ids_in_order(self) -> tuple[str, ...]:
        payload = self._payload
        if payload is None:
            return ()
        return tuple(row["slice_id"] for row in payload.get("slices", []))  # type: ignore[union-attr]

    def cause_names(self, phrase: str) -> bool:
        """Whether the refusal's WHAT/HOW text names the given phrase."""
        payload = self._payload
        if payload is None:
            return False
        joined = " ".join(str(payload.get(k, "")) for k in ("WHAT", "WHY", "HOW"))
        return phrase in joined

    @property
    def has_how(self) -> bool:
        payload = self._payload
        return bool(payload and str(payload.get("HOW", "")).strip())

    def matches_declarations(self, declarations: str) -> bool:
        """Whether every "slice-NN as ..." pair in ``declarations`` is
        rendered with exactly that declared status."""
        return all(
            self.declared_status(slice_id) == status
            for slice_id, status in _parse_declared_statuses(declarations)
        )

    @property
    def all_sources_are_slice_plan(self) -> bool:
        """Whether every rendered row names the Slice Plan as its source --
        the observable "zero independent re-derivation" pins on."""
        payload = self._payload
        if payload is None:
            return False
        rows = payload.get("slices", [])  # type: ignore[union-attr]
        return bool(rows) and all(row.get("source") == "slice-plan" for row in rows)

    def is_exactly_one(self, slice_id: str, status: DeclaredStatus) -> bool:
        """Whether the rendered response carries EXACTLY ``slice_id``, at
        ``status`` -- the C1 single-row boundary case."""
        return (
            self.slice_ids_in_order() == (slice_id,)
            and self.declared_status(slice_id) == status
        )

    def matches_ordered_run(self, count: int) -> bool:
        """Whether the response renders slice-01..slice-{count}, in that
        exact document order -- the C3 many-rows boundary case."""
        expected = tuple(f"slice-{n:02d}" for n in range(1, count + 1))
        return self.slice_ids_in_order() == expected

    @property
    def refuses_for_missing_feature_delta(self) -> bool:
        return self.verdict is RenderVerdict.MISSING_FEATURE_DELTA and self.cause_names(
            "feature-delta"
        )


@dataclass
class MikadoBoardRenderComposition:
    """Production-wired composition root for the declared-status-render slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root.
    The feature-delta is provisioned directly on disk so each scenario
    builds exactly the Slice Plan shape it needs; the CLI is then invoked
    through its argv entry point against that repository.
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=FeatureId("board-render-demo"))
    _last_before: dict[str, object] | None = field(default=None, repr=False)
    _last_after: dict[str, object] | None = field(default=None, repr=False)

    # --- paths -----------------------------------------------------------

    def _feature_dir(self, feature_id: FeatureId | None = None) -> Path:
        fid = feature_id if feature_id is not None else self.feature_id
        return self.repo_dir / "docs" / "feature" / fid

    def _feature_delta_path(self, feature_id: FeatureId | None = None) -> Path:
        return self._feature_dir(feature_id) / "feature-delta.md"

    @property
    def feature_delta_path(self) -> Path:
        return self._feature_delta_path()

    # --- Given: repository -------------------------------------------------

    def create_repository(self) -> None:
        """Establish an empty repository root -- the Background step."""
        self.repo_dir.mkdir(parents=True, exist_ok=True)

    # --- Given: Slice Plan content ------------------------------------------

    def declare_statuses(self, feature_id: FeatureId, declarations: str) -> None:
        """Write a well-formed Slice Plan from free-text "slice-NN as ...".

        Parses every ``slice-NN as "pending|shipped"`` token out of
        ``declarations`` (any surrounding prose -- "only", "and" -- is
        ignored), in the order they appear, and writes a well-formed
        five-column Slice Plan with exactly those rows.
        """
        self.feature_id = feature_id
        pairs = _parse_declared_statuses(declarations)
        rows = "\n".join(
            f"| {slice_id} | Operator value for {slice_id} | {status.value} | | |"
            for slice_id, status in pairs
        )
        self._write(feature_id, _doc(_slice_plan_section(rows)))

    def declare_many_in_order(self, feature_id: FeatureId, count: int) -> None:
        """Write a well-formed Slice Plan with ``count`` slices, all pending,
        numbered slice-01..slice-{count} in document order."""
        self.feature_id = feature_id
        rows = "\n".join(
            f"| slice-{n:02d} | Operator value {n} | pending | | |"
            for n in range(1, count + 1)
        )
        self._write(feature_id, _doc(_slice_plan_section(rows)))

    def edit_statuses(self, declarations: str) -> None:
        """Re-declare statuses on the CURRENT feature -- proves DES-1's
        composed-fresh-on-every-read contract (no caching to invalidate)."""
        self.declare_statuses(self.feature_id, declarations)

    def omit_feature_delta(self, feature_id: FeatureId) -> None:
        """Ensure the feature directory exists but carries no feature-delta."""
        self.feature_id = feature_id
        self._feature_dir(feature_id).mkdir(parents=True, exist_ok=True)

    def provision_shape(self, feature_id: FeatureId, shape: SlicePlanShape) -> None:
        self.feature_id = feature_id
        builder = _FEATURE_DELTA_BUILDERS[shape]
        self._write(feature_id, builder())

    def _write(self, feature_id: FeatureId, body: str) -> None:
        path = self._feature_delta_path(feature_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    # --- When: render --------------------------------------------------------

    def render(self) -> RenderResult:
        """Invoke the production CLI IN-PROCESS via the stable `des` dispatcher."""
        argv = _render_argv(self.feature_id, self.repo_dir)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                exit_code = des_main(argv)
            except SystemExit as exc:
                exit_code = int(exc.code or 2)
        return RenderResult(exit_code=exit_code, output=buffer.getvalue())

    def render_tracked(self) -> RenderResult:
        """Like ``render()``, but snapshots the universe before/after so
        ``assert_unchanged`` can pin the read-only contract (Mandate 8)."""
        self._last_before = self.capture_universe()
        result = self.render()
        self._last_after = self.capture_universe()
        return result

    def assert_unchanged(self) -> None:
        """Pin that the last tracked render left the feature-delta untouched."""
        assert_state_delta(
            self._last_before or {},
            self._last_after or {},
            universe={"feature_delta.exists", "feature_delta.bytes"},
            expected={
                "feature_delta.exists": unchanged(),
                "feature_delta.bytes": unchanged(),
            },
        )

    def render_via_installed_cli(self) -> RenderResult:
        """Invoke the production CLI as a REAL subprocess -- the feature's
        single `@walking_skeleton` proof that the installed entry is wired."""
        argv = _render_argv(self.feature_id, self.repo_dir)
        completed = _run_subprocess(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
        )
        return RenderResult(
            exit_code=completed.returncode,
            output=completed.stdout + completed.stderr,
        )

    # --- universe --------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The render command has a pure-function, read-only contract (DES-1:
        composed fresh on every read, never a persisted 4th copy; the
        component-manifest's `slice_progress_projection` port-invariant:
        "never mutates the Slice Plan"). The universe is the feature-delta's
        existence and bytes -- the state-delta guard proves the read-only
        contract holds across a render call.
        """
        path = self.feature_delta_path
        return {
            "feature_delta.exists": path.exists(),
            "feature_delta.bytes": path.read_bytes() if path.exists() else None,
        }


# --- argv builder ------------------------------------------------------------


def _render_argv(feature_id: FeatureId, repo_dir: Path) -> list[str]:
    return [
        "mikado-board",
        "render",
        "--feature",
        feature_id,
        "--repo-root",
        str(repo_dir),
        "--format",
        "json",
    ]


# --- declaration parsing -----------------------------------------------------

_DECLARATION_RE = re.compile(r"(slice-\d+)\s+as\s+\"(pending|shipped)\"")


def _parse_declared_statuses(text: str) -> tuple[tuple[SliceId, DeclaredStatus], ...]:
    return tuple(
        (SliceId(slice_id), DeclaredStatus(status))
        for slice_id, status in _DECLARATION_RE.findall(text)
    )


# --- feature-delta fixture builders ------------------------------------------


def _slice_plan_section(rows: str) -> str:
    header = "| " + " | ".join(_SLICE_PLAN_COLUMNS) + " |"
    separator = "|" + "|".join("-" * (len(c) + 2) for c in _SLICE_PLAN_COLUMNS) + "|"
    return f"## Wave: DISCUSS / [REF] Slice Plan\n\n{header}\n{separator}\n{rows}"


def _doc(*sections: str) -> str:
    return "# Feature Delta: declared-status-render fixture\n\n" + "\n\n".join(sections)


def _build_section_absent() -> str:
    return _doc(
        "## Wave: DISCUSS / [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | a commitment | n/a | a substantive consequence here |"
    )


def _build_four_columns() -> str:
    # Drops the Justification column -- only four of the five required
    # columns (ADR-028 D2), a malformed Slice Plan.
    return _doc(
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation |\n"
        "|-------|-----------------|--------|------------|\n"
        "| slice-01 | Operator previews a plan | pending | |"
    )


def _build_zero_rows() -> str:
    # A well-formed five-column header + separator, but ZERO slice rows --
    # the C3 zero-obligation case for the `slices` iterative render output.
    return _doc(_slice_plan_section(""))


_FEATURE_DELTA_BUILDERS: dict[SlicePlanShape, Callable[[], str]] = {
    SlicePlanShape.SECTION_ABSENT: _build_section_absent,
    SlicePlanShape.FOUR_COLUMNS: _build_four_columns,
    SlicePlanShape.ZERO_ROWS: _build_zero_rows,
}
