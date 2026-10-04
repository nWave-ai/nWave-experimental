"""Run source-blind fixtures through an explicitly eval-owned native Claude role."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

from tests.evals.delivery_convergence.run_probe import invoke_native_role


ROLE = "nw-user-examiner"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--framework-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--model", default="haiku")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    dataset = Path(__file__).with_name("dataset.csv")
    results: list[dict[str, object]] = []
    with dataset.open(newline="") as stream:
        cases = list(csv.DictReader(stream))
    for case in cases:
        root = args.output_root / case["id"]
        root.mkdir()
        prompt = json.dumps(
            {
                "request": case["request"],
                "outcomes": [case["request"]],
                "candidate_sha": "0" * 40,
                "native_evidence": [
                    {
                        "exit": 0,
                        "stdout": case["observed_stdout"],
                        "stderr": "",
                        "origin": "declared-verification",
                        "incomplete": False,
                    }
                ],
                "radius": "whole-request",
            }
        )
        (root / "prompt.json").write_text(prompt + "\n")
        started = time.monotonic()
        try:
            run, envelope, exit_status = invoke_native_role(
                role=ROLE,
                prompt=prompt,
                run_root=root,
                framework_root=args.framework_root,
                model=args.model,
            )
            result = {
                "case": case["id"],
                "expected": case["expected_outcome"],
                "outcome": run.outcome.value,
                "issued": True,
                "exit_status": exit_status,
                "diagnostic": run.diagnostic,
                "run_id": envelope.get("session_id"),
                "accounting": {
                    key: envelope.get(key)
                    for key in ("total_cost_usd", "usage", "modelUsage", "duration_ms")
                },
            }
        except Exception as error:
            result = {
                "case": case["id"],
                "error": type(error).__name__,
                "detail": str(error),
            }
        result.update(seconds=time.monotonic() - started)
        results.append(result)
        (args.output_root / "results.json").write_text(
            json.dumps(
                {
                    "fixture_kind": "synthetic evidence; not product acceptance",
                    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                    "model_selection": args.model,
                    "cases": results,
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps(result), flush=True)
        if "error" in result or not result.get("issued"):
            break
    return int(
        len(results) != len(cases)
        or any(
            "error" in row
            or not row.get("issued")
            or row.get("exit_status") != 0
            or row.get("outcome") != row.get("expected")
            for row in results
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
