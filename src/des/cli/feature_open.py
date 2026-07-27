"""``des feature-open`` -- create one evidence-aware initial feature context."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from des.application.feature_context_bootstrap import BootstrapContext, render


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feature-open")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--adopt-wip", action="store_true")
    parser.add_argument("--adopt-root")
    return parser


def _inventory(repo: Path, adopt_root: str) -> tuple[dict[str, str], ...]:
    root = (repo / adopt_root).resolve()
    if root == repo or repo not in root.parents or not root.is_dir():
        raise ValueError(
            "--adopt-root must name an existing repository-relative directory"
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    intent = args.intent.strip()
    if not intent:
        raise ValueError("--intent must not be empty")
    if args.adopt_wip != bool(args.adopt_root):
        raise ValueError("--adopt-wip and --adopt-root must be supplied together")
    inventory = _inventory(repo, args.adopt_root) if args.adopt_wip else ()
    state = "ADOPTED_WIP" if args.adopt_wip else "OPEN"
    context = BootstrapContext(args.feature_id, intent, state, inventory)
    body = render(context)
    delta = repo / "docs" / "feature" / args.feature_id / "feature-delta.md"
    if delta.exists():
        print(json.dumps({"error": "feature-context-conflict"}, sort_keys=True))
        return 1
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
