"""The retired per-delivery telemetry ledger cannot return."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED_PATH = ".nwave/telemetry/atdd-pure/"


def test_no_per_feature_atdd_ledger_writes() -> None:
    violations = []
    for root_name in ("src", "scripts"):
        for path in (REPO_ROOT / root_name).rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if RETIRED_PATH in text:
                violations.append(path.relative_to(REPO_ROOT))

    assert not violations, f"retired per-delivery ledger returned: {violations}"
