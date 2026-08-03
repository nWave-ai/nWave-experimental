"""Property test: slice-01 -- declared-status render preserves order + value.

Mandate 9 (PBT input mode is layer-dependent): the underlying projection
(`slice_progress_projection.project_slice_progress`, CREATE_NEW) is a
layer-1 pure function; layers 1-2 get PBT-full treatment (Hypothesis
`@given`, 100+ examples per property). This property drives the SAME
in-process composition the Gherkin scenarios use
(`MikadoBoardRenderComposition.render`) -- never a direct call to the domain
function (Mandate 13, Driving-Port-Only Boundary) -- generating an unbounded
number of well-formed Slice Plans and asserting the rendered response
preserves every slice's declared status, verbatim, in document order.

RED contract: fails today because the response carries no `verdict` token
(`des mikado-board` is not a registered `des` subcommand) -- P1-P4,
nw-distill-red-scaffolding. Never a collection-time import error: this
module imports only the stable composition, never `des.cli.mikado_board`.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from .composition import MikadoBoardRenderComposition
from .domain_types import DeclaredStatus, FeatureId


_slice_plan_rows = st.lists(
    st.sampled_from([DeclaredStatus.PENDING, DeclaredStatus.SHIPPED]),
    min_size=1,
    max_size=25,
)


@given(statuses=_slice_plan_rows)
@settings(max_examples=100)
def test_declared_status_render_preserves_order_and_value(tmp_path_factory, statuses):
    """For ANY well-formed Slice Plan, the render preserves every slice's
    declared status, byte-for-byte, in document order -- zero independent
    re-derivation (DES-1), for an unbounded number of slices.

    # covers: R1
    """
    repo_dir = tmp_path_factory.mktemp("board-render-property")
    composition = MikadoBoardRenderComposition(repo_dir)
    feature_id = FeatureId("property-render-demo")
    declarations = " and ".join(
        f'slice-{n:02d} as "{status.value}"'
        for n, status in enumerate(statuses, start=1)
    )
    composition.declare_statuses(feature_id, declarations)

    result = composition.render()

    expected_ids = tuple(f"slice-{n:02d}" for n in range(1, len(statuses) + 1))
    assert result.slice_ids_in_order() == expected_ids
    assert all(
        result.declared_status(slice_id) == status
        for slice_id, status in zip(expected_ids, statuses, strict=True)
    )
