"""``des feature-open`` -- create one evidence-aware initial feature context."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from des.application.feature_context_bootstrap import BootstrapContext, render
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.repo_path_resolver import feature_delta_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feature-open")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--intent", required=True)
    add_repo_root_argument(parser, "--repo", default=".")
    parser.add_argument("--adopt-wip", action="store_true")
    parser.add_argument("--adopt-root")
    return parser


class _Refusal(Exception):
    """One refusal the operator can act on, raised from anywhere in the command.

    Carrying the payload on the exception keeps each refusal next to the check
    that discovers it, while the command boundary stays the single place that
    decides how a refusal reaches stdout (GDP-3: no path may surface as a bare
    traceback).
    """

    def __init__(self, error: str, what: str, why: str, how: str) -> None:
        super().__init__(error)
        self.payload = {
            "event": "FeatureContextRefused",
            "schema_version": "1",
            "error": error,
            "what": what,
            "why": why,
            "how": how,
        }


def _reopen_hint(feature_id: str, suffix: str) -> str:
    """The producing tool re-invoked with the argument that was wrong."""
    return (
        f'des feature-open --feature-id {feature_id} --intent "<one sentence>" {suffix}'
    )


def _inventory(
    repo: Path, adopt_root: str, feature_id: str
) -> tuple[dict[str, str], ...]:
    root = (repo / adopt_root).resolve()
    hint = _reopen_hint(feature_id, "--adopt-wip --adopt-root <subdirectory>")
    if root == repo:
        raise _Refusal(
            "adopt-root-is-repo-root",
            f"--adopt-root resolved to the repository root itself ({adopt_root!r}).",
            "Adopting the whole repository would inventory every file as this feature's "
            "work in progress, so the provenance record would name bytes no one adopted.",
            hint,
        )
    if repo not in root.parents:
        raise _Refusal(
            "adopt-root-outside-repo",
            f"--adopt-root {adopt_root!r} resolved outside the repository ({root}).",
            "An inventory of paths outside the repository cannot be reproduced by another "
            "checkout, so the recorded hashes would not be verifiable evidence.",
            hint,
        )
    if not root.is_dir():
        raise _Refusal(
            "adopt-root-not-a-directory",
            f"--adopt-root {adopt_root!r} is not an existing directory.",
            "The adopted inventory is built by walking a directory; without one there is "
            "nothing to hash and the adoption would silently record an empty provenance.",
            hint,
        )
    return tuple(
        {
            "path": path.relative_to(repo).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "test_status": "UNKNOWN",
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _open(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    intent = args.intent.strip()
    if not intent:
        raise _Refusal(
            "intent-empty",
            "--intent was supplied but holds no non-whitespace text.",
            "The intent is the only sentence the opened context carries into DISCUSS; "
            "an empty one produces a document that states nothing to discuss.",
            _reopen_hint(args.feature_id, "").rstrip(),
        )
    if args.adopt_wip != bool(args.adopt_root):
        given, missing = (
            ("--adopt-wip", "--adopt-root <subdirectory>")
            if args.adopt_wip
            else ("--adopt-root", "--adopt-wip")
        )
        raise _Refusal(
            "adopt-flags-incomplete",
            f"{given} was supplied without {missing}.",
            "Adoption needs both the decision to adopt and the directory to inventory; "
            "one alone would silently open an empty context instead of adopting work.",
            _reopen_hint(args.feature_id, "--adopt-wip --adopt-root <subdirectory>"),
        )
    inventory = (
        _inventory(repo, args.adopt_root, args.feature_id) if args.adopt_wip else ()
    )
    state = "ADOPTED_WIP" if args.adopt_wip else "OPEN"
    context = BootstrapContext(args.feature_id, intent, state, inventory)
    body = render(context)
    delta = feature_delta_path(repo, args.feature_id)
    if delta.exists():
        raise _Refusal(
            "feature-context-conflict",
            f"{delta.relative_to(repo)} already exists for feature "
            f"{args.feature_id!r}.",
            "Overwriting it would erase whatever delivery, review and completion "
            "authority that document already carries.",
            f"des next --feature-id {args.feature_id} "
            "(or open a different --feature-id)",
        )
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode()).hexdigest()
    receipt = {
        "event": "FeatureContextReceipt",
        "schema_version": "1",
        "feature_id": args.feature_id,
        "state": state,
        "feature_delta": str(delta.relative_to(repo)),
        "intent_normalized": intent,
        "next": f"/nw-discuss --feature-id {args.feature_id}",
        "feature_delta_sha256": digest,
        "intent_sha256": hashlib.sha256(intent.encode()).hexdigest(),
        "template_version": "1",
        "template_sha256": hashlib.sha256(
            render(BootstrapContext("", "", "OPEN", ())).encode()
        ).hexdigest(),
        "canonical_body_sha256": digest,
        "inventory": list(inventory),
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    """The command boundary: every refusal leaves here as a payload, never a trace.

    The single ``except`` is what makes the GDP-3 floor a property of the
    command rather than a habit of each check -- a refusal raised anywhere
    below cannot reach the operator as a stack trace.
    """
    args = _parser().parse_args(argv)
    try:
        return _open(args)
    except _Refusal as refusal:
        print(json.dumps(refusal.payload, sort_keys=True))
        return 1
