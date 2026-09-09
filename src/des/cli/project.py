"""Render the owned delivery state as the document a HUMAN reads.

`docs/architecture/adr-ssot-document-model.md`, «Feature Brief — The Human
Layer»: the SSOT files serve agents and the delta files serve the pipeline;
neither is designed for human consumption. The handover and the typed design
facts are exactly that, and `des state` -- the textual projection -- is written
for the orchestrating model. This is the page for the person who has to decide
between an interactive session and an autonomous one.

`docs/product/architecture/ADR-BOARD-001-shared-slice-state-projection.md` fixes
what it may be: a projection function, never a fourth persisted store,
recomputed on every read. So this step writes ONE html file and touches nothing
the delivery owns. The same state renders the same page.

ONE RENDERER AND ONE STYLESHEET. The page goes through
`des.adapters.driven.rendering.nwave_document`, the renderer this repository
already has, with the nWave palette and its dark mode. Emitting HTML here would
be a second answer to "what does an nWave document look like", and a second
answer is a drift waiting to happen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.adapters.driven.rendering.nwave_document import BrandAssetError, build_page
from des.application.delivery_projection import project_markdown
from des.application.delivery_state import read_state
from des.application.delivery_steps import blocked_disposition
from des.application.handover import Blocked, handover_path, stored_handover
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import StepRefusal, refuse, resolved_root, succeed
from des.domain.delivery_disposition import Disposition


#: One direction, because this step reads owned state and buys no turn: its
#: refusals never carry a role's answer, and the shared terminal says so itself.
RENDERED = (
    "open the page and decide how to run this Request: one step at a time with "
    "you reading each terminal, or one composed run"
)

TITLE = "Delivery state"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="des project")
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root, "des project --repo-root <root> --html <out> -- after the HOW above"
        )
    own = "des project --repo-root {root} --html " + str(args.html)
    stored = stored_handover(root)
    if isinstance(stored, Blocked):
        return refuse(
            StepRefusal(
                stored.what,
                stored.why,
                stored.how,
                blocked_disposition(stored),
            ),
            moves_after_refusal(root, own, stored.what),
        )
    if stored is None:
        return refuse(
            StepRefusal(
                "HandoverAbsent",
                "no decomposition is recorded in this repository, so there is no "
                "delivery state to show anyone",
                "decompose one Request first -- pipe it into `des po` on stdin",
            ),
            moves_after_refusal(root, own, "HandoverAbsent"),
        )
    state = read_state(root)
    if isinstance(state, Blocked):
        return refuse(
            StepRefusal(
                state.what,
                state.why,
                state.how,
                blocked_disposition(state),
            ),
            moves_after_refusal(root, own, state.what),
        )
    try:
        page = build_page(
            project_markdown(stored, state),
            str(handover_path(root).relative_to(root)),
            TITLE,
        )
    except BrandAssetError as error:
        return refuse(
            StepRefusal(
                "BrandAssetsInvalid",
                str(error),
                "repair the packaged nWave brand assets and run this projection again",
                Disposition.Indeterminate,
            ),
            moves_after_refusal(root, own, "BrandAssetsInvalid"),
        )
    try:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(page, encoding="utf-8")
    except OSError as error:
        return refuse(
            StepRefusal(
                "ProjectionUnwritable",
                f"the page could not be written to {args.html}: {error}",
                "pass a writable output path, then invoke this step again",
                Disposition.Indeterminate,
            ),
            moves_after_refusal(root, own, "ProjectionUnwritable"),
        )
    return succeed(
        [f"HTML: {args.html}", f"BYTES: {args.html.stat().st_size}"],
        after_step(root),
    )
