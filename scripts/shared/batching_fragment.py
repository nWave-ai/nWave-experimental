"""Load and append the tool-batching guidance fragment for installed agent bodies."""

from pathlib import Path


def load_batching_fragment(nwave_root: Path) -> str:
    """Read nWave/templates/tool-batching-fragment.md and return its stripped content."""
    fragment_path = nwave_root / "templates" / "tool-batching-fragment.md"
    content = fragment_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Batching fragment is empty at {fragment_path}")
    return content


def append_batching_fragment(body: str, fragment: str) -> str:
    """Append fragment to body exactly once, preserving body bytes as the prefix."""
    if f"\n{fragment}\n" in f"\n{body}\n":
        return body
    boundary = "" if not body or body.endswith("\n") else "\n"
    return f"{body}{boundary}{fragment}\n"
