"""Fail closed when a final public mirror tree contains private artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.release.verify_plugin_privacy import verify_tree as verify_plugin_tree
from scripts.release.verify_wheel_privacy import verify as verify_wheel_or_tree


def verify(public_tree: Path) -> list[str]:
    """Return violations for the final public mirror tree."""
    target = Path(public_tree)
    violations = verify_wheel_or_tree(target)
    plugin_dir = target / "plugins" / "nw"
    if not plugin_dir.is_dir():
        violations.append("unverifiable public tree layout: missing plugins/nw/")
    else:
        violations.extend(
            f"plugins/nw/{violation}"
            for violation in verify_plugin_tree(plugin_dir, target / "nWave")
        )
    return violations


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <public-tree>", file=sys.stderr)
        sys.exit(1)
    violations = verify(Path(sys.argv[1]))
    if violations:
        print(
            "FAIL: public tree carries private or unverifiable artifacts:",
            file=sys.stderr,
        )
        print("\n".join(f"  {item}" for item in violations), file=sys.stderr)
        sys.exit(1)
    print("PASS: public tree carries no private artifact")


if __name__ == "__main__":
    main()
