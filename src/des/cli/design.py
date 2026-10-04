"""Construct DESIGN documents and bind host-supplied semantic facts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.application.delivery_steps import DeliverySteps, ReplacementModes
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_next import after_step, moves_after_refusal
from des.cli.step_terminal import (
    StepRefusal,
    read_request,
    refuse,
    resolved_root,
    succeed,
)
from des.domain.design_document import DesignDocument


#: The one form that reads the finding from stdin.  A finding is a role's own
#: prose -- newlines, quotes, whatever it wrote -- so it travels on a stream and
#: never through a shell argument that would have to be escaped to survive.
STDIN = "-"


def _modes(args: argparse.Namespace) -> ReplacementModes:
    """The three replacement/recovery modes this invocation asked for.

    Both document forms -- one value's and the shared section's -- read them off
    the SAME namespace, so they are built once here rather than spelled out again
    at each call.

    NOT exclusive: all three are independent ``store_true`` flags added straight to
    the parser, so any combination is accepted and nothing downstream enforces an
    arity over them.  The one mutually exclusive group in this CLI is ``--value``
    against ``--shared``.
    """
    return ReplacementModes(
        replace_current=args.replace_current,
        migrate_legacy_rendering=args.migrate_legacy_rendering,
        replace_unbound=args.replace_unbound,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des design",
        epilog=DesignDocument.input_description(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_repo_root_argument(parser, "--repo-root", type=Path, required=True)
    intent = parser.add_mutually_exclusive_group(required=True)
    intent.add_argument(
        "--value", type=int, help="the value whose DESIGN facts to bind"
    )
    intent.add_argument(
        "--shared",
        action="store_true",
        help=(
            "construct the one DESIGN section shared by every value of the "
            "Request from host-supplied semantic facts; requires --input -"
        ),
    )
    parser.add_argument("--input", choices=(STDIN,), required=True)
    parser.add_argument("--replace-current", action="store_true")
    parser.add_argument(
        "--migrate-legacy-rendering",
        action="store_true",
        help=(
            "explicitly replace an unbound tracked DESIGN section only when its "
            "complete bytes equal the frozen pre-lint renderer"
        ),
    )
    parser.add_argument(
        "--replace-unbound",
        action="store_true",
        help=(
            "explicitly replace a tracked unbound DESIGN section with a complete "
            "closed manifest and bind its facts"
        ),
    )
    parser.add_argument(
        "--feature",
        default=None,
        help=(
            "feature id ([a-z0-9][a-z0-9-]*) selecting FEATURE document destinations; "
            "optional here: the handover's bound scope is used and a different id is refused"
        ),
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(
            root,
            "des design --repo-root <root> --value N --input - -- after the HOW above",
        )
    own = (
        "des design --repo-root {root} "
        + ("--shared" if args.shared else f"--value {args.value}")
        + " --input -"
    )
    if args.shared:
        return _shared(args, root, own)
    manifest = read_request()
    if isinstance(manifest, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidDesignDocument",
                "stdin must carry one non-empty strict-UTF-8 JSON manifest",
                "pipe closed v1 semantic JSON into `des design --input -`",
            ),
            (own.format(root=root),),
        )
    outcome = DeliverySteps().design_document(
        root, args.value, manifest, modes=_modes(args), feature=args.feature
    )
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(root, own, outcome.failure.what),
            facts=list(outcome.facts),
        )
    return succeed(list(outcome.facts), after_step(root))


def _shared(args: argparse.Namespace, root: Path, own: str) -> int:
    """Construct the shared feature DESIGN: input only, never a provider turn."""
    move = (own.format(root=root),)
    manifest = read_request()
    if isinstance(manifest, StepRefusal):
        return refuse(
            StepRefusal(
                "InvalidDesignDocument",
                "stdin must carry one non-empty strict-UTF-8 JSON manifest",
                "pipe closed v1 semantic JSON into `des design --shared --input -`",
            ),
            move,
        )
    outcome = DeliverySteps().shared_design_document(
        root, manifest, modes=_modes(args), feature=args.feature
    )
    if not outcome.succeeded:
        return refuse(
            StepRefusal(
                outcome.failure.what,
                outcome.failure.why,
                outcome.failure.how,
                outcome.disposition,
            ),
            moves_after_refusal(root, own, outcome.failure.what),
            facts=list(outcome.facts),
        )
    return succeed(list(outcome.facts), after_step(root))
