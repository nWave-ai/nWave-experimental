"""Invoke one delivery-convergence fixture through its installed public role.

This is a bounded oracle consumer.  It never stubs a provider judgment and it
does not turn the fixture's semantic expectation into a provider response.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.adapters.driven.task_invocation.codex_task_adapter import CodexTaskAdapter


CASES_PATH = Path(__file__).with_name("cases.json")
NATIVE_ROLES = {
    "nw-user-examiner",
    "nw-acceptance-designer",
    "nw-acceptance-designer-reviewer",
}


def _case_by_id(case_id: str) -> dict[str, object]:
    corpus = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for case in corpus["cases"]:
        if case["id"] == case_id:
            return case
    known = ", ".join(case["id"] for case in corpus["cases"])
    raise ValueError(f"unknown case {case_id!r}; known cases: {known}")


def _raw_structured_judgment(run_root: Path) -> object | None:
    """Read the raw provider response from its immutable adapter turn record.

    The decoded ``ModelRun.outcome`` remains the control value. This projection
    retains the raw structured reply for review and never derives a verdict from
    diagnostic prose.
    """
    records = sorted((run_root / ".nwave" / "des" / "logs" / "turns").glob("*/*.json"))
    if not records:
        return None
    record = json.loads(records[-1].read_text(encoding="utf-8"))
    raw = record.get("provider_stdout")
    if not isinstance(raw, str):
        return raw
    lines = raw.splitlines() or [raw]
    for line in reversed(lines):
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded.get("structured_output", decoded.get("answer", decoded))
    return raw


def _decoded_judgment(run: object) -> dict[str, object]:
    """Project the adapter's authoritative typed outcome without parsing prose."""
    # ``run`` is a ModelRun; keeping this narrow projection local avoids making
    # provider stdout a second semantic channel.
    review_defect = run.review_defect
    return {
        "outcome": run.outcome.value,
        "diagnostic": run.diagnostic,
        "review_defect": (
            None
            if review_defect is None
            else {"owner": review_defect.owner.value, "value": review_defect.value}
        ),
    }


def _fresh_invocation_directory(output_root: Path, case_id: str) -> Path:
    """Create one new evidence directory without overwriting an earlier run."""
    case_root = output_root / case_id
    case_root.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = case_root / f"invocation-{index:04d}"
        try:
            candidate.mkdir()
        except FileExistsError:
            index += 1
            continue
        return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--framework-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", choices=("claude", "codex"), default="claude")
    args = parser.parse_args()

    case = _case_by_id(args.case)
    role = str(case["target"])
    if role not in NATIVE_ROLES:
        print(
            json.dumps(
                {
                    "case": args.case,
                    "outcome": "not-run",
                    "reason": (
                        f"{role} is an installed skill/outer-route concern, not a native "
                        "specialist role selectable by this public role adapter; run it through "
                        "the normal installed outer route described in README.md"
                    ),
                }
            )
        )
        return 3

    run_root = _fresh_invocation_directory(args.output_root, args.case)
    prompt = json.dumps(case["public_input"])
    (run_root / "prompt.json").write_text(prompt + "\n", encoding="utf-8")

    adapter = (
        ClaudeCodeTaskAdapter(
            model=args.model, record_root=run_root, framework_root=args.framework_root
        )
        if args.provider == "claude"
        else CodexTaskAdapter(
            model=args.model, record_root=run_root, framework_root=args.framework_root
        )
    )
    started = time.monotonic()
    try:
        review_values = tuple(case.get("review_defect_values", []))
        run = adapter.invoke(
            role_id=role,
            prompt=prompt,
            cwd=run_root,
            defect_values=review_values,
        )
        expected_outcomes = case.get("expected_provider_outcomes")
        typed_match = (
            None
            if expected_outcomes is None
            else run.outcome.value in expected_outcomes
        )
        result: dict[str, object] = {
            "case": args.case,
            "role": role,
            "provider": args.provider,
            "invocation_directory": str(run_root),
            "expected": case["expected"],
            "outcome": run.outcome.value,
            "typed_judgment_matches_expected": typed_match,
            "decoded_judgment": _decoded_judgment(run),
            "raw_structured_judgment": (
                _raw_structured_judgment(run_root)
                if args.provider == "claude"
                else None
            ),
            "raw_structured_judgment_note": (
                "Claude turn record provider stdout contains the structured reply."
                if args.provider == "claude"
                else "Codex adapter stdout is event transport, not an authoritative answer; "
                "the existing adapter does not retain the terminal answer separately."
            ),
            "issued": run.issued,
            "exit_status": run.exit_status,
            "diagnostic": run.diagnostic,
            "accounting": asdict(run.accounting) if run.accounting else None,
            "seconds": time.monotonic() - started,
            "run_id": adapter.run_id,
        }
    except Exception as error:
        result = {
            "case": args.case,
            "role": role,
            "provider": args.provider,
            "invocation_directory": str(run_root),
            "outcome": "not-run",
            "error": type(error).__name__,
            "detail": str(error),
            "seconds": time.monotonic() - started,
            "run_id": adapter.run_id,
        }
    (run_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    if not result.get("issued") or result.get("exit_status") != 0:
        return 1
    # A process exit says only that the role run completed. Where the fixture
    # declares a typed expectation, fail on a differing semantic outcome.
    return 1 if result.get("typed_judgment_matches_expected") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
