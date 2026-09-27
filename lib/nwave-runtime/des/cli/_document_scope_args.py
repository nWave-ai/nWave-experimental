"""Required project, epic, feature, or slice choice for document-producing root steps."""

from __future__ import annotations

import argparse

from des.domain.feature_documents import FeatureDocumentsInvalid, require_feature_id


def scope_id(value: str) -> str:
    try:
        return require_feature_id(value)
    except FeatureDocumentsInvalid as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def add_document_scope_arguments(
    parser: argparse.ArgumentParser, *, required: bool = True
) -> None:
    """Make the semantic scope a required sum, never an absent default."""
    scope = parser.add_mutually_exclusive_group(required=required)
    scope.add_argument(
        "--project",
        action="store_true",
        help="select project-scoped authorities",
    )
    scope.add_argument(
        "--feature",
        metavar="ID",
        type=scope_id,
        help="select feature-scoped authorities for lowercase kebab-case ID",
    )

    scope.add_argument(
        "--epic", metavar="ID", type=scope_id, help="select epic-scoped authorities"
    )
    scope.add_argument(
        "--slice",
        nargs=2,
        type=scope_id,
        metavar=("FEATURE_ID", "SLICE_ID"),
        help="select a slice within its feature",
    )


def selected_scope(args):
    from des.domain.document_scope import Epic, Feature, Slice

    if args.epic is not None:
        return Epic(args.epic)
    if args.slice is not None:
        return Slice(*args.slice)
    return Feature(args.feature) if args.feature is not None else None


def scope_arguments(args: argparse.Namespace) -> str:
    """Render the validated selection for a copyable retry or next-step hint."""
    if args.project:
        return "--project"
    if args.epic is not None:
        return f"--epic {args.epic}"
    if args.slice is not None:
        return f"--slice {args.slice[0]} {args.slice[1]}"
    if args.feature is not None:
        return f"--feature {args.feature}"
    raise ValueError("an explicit scope is required")
