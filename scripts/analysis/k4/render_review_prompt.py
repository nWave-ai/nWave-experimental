"""Render the blind reviewer's prompt FROM the rubric, never by hand.

`quality_rubric` says a future prompt generator should render `CRITERIA`
instead of hand-copying the table from the doc. Until this module existed,
every campaign re-typed the dimensions into a throwaway file, so the prompt a
reviewer actually read could drift from the criteria the scores were validated
against, and nothing would notice.

Two things are rendered, and both have to come from code:

* the criteria themselves -- `dimension` and `question` ONLY, the surface
  `quality_rubric` keeps source-blind and shape-blind;
* the verdict contract -- the exact key sets `blind_review._validate_one_verdict`
  enforces, read from that module rather than restated, because four reviewer
  attempts already got that shape wrong.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import blind_review
import quality_rubric


SCALE = (
    "0  the delivery does not do this, or a reader cannot tell that it does\n"
    "1  the delivery does this partially, or does it in one place and not another\n"
    "2  the delivery does this, and a reader can see that it does"
)


def render(bundle: Path) -> str:
    criteria = quality_rubric.CRITERIA
    top = sorted(blind_review._VERDICT_TOP_KEYS)
    lines = [
        "# Judge one delivery, blind",
        "",
        "You are given a change someone made to a codebase. You do not know who",
        "made it or how. Judge ONLY what the packet contains. Do not guess at",
        "process, tooling, or authorship, and do not reward or penalise a",
        "delivery for anything you cannot read in front of you.",
        "",
        f"The packet is at `{bundle}`. Read `REVIEW-THESE.txt` for the ids to",
        "score, then read each delivery under `deliveries/`.",
        "",
        "## Score each criterion 0, 1 or 2",
        "",
        SCALE,
        "",
        "A criterion the packet gives you no material to judge scores 0, and the",
        "evidence line must say that the material is absent. Never score on",
        "what you assume happened off the page.",
        "",
    ]
    for index, criterion in enumerate(criteria, start=1):
        lines.append(f"{index}. **{criterion.dimension}** -- {criterion.question}")
    lines += [
        "",
        "## Answer with one JSON object per delivery id",
        "",
        "```json",
        "{",
        '  "<delivery id>": {',
        '    "criteria": {',
        '      "1": {"score": 0, "evidence": "what you read, or that it is absent"},',
        f'      ...through "{len(criteria)}"',
        "    },",
        f'    "total": 0,          # the sum of the {len(criteria)} scores, exactly',
        '    "blocking_quality_findings": ["..."],   # may be empty',
        '    "summary": "..."',
        "  }",
        "}",
        "```",
        "",
        f"Every verdict carries exactly these top-level keys: {top}.",
        f"`criteria` carries exactly '1'..'{len(criteria)}', each an object with",
        "exactly `score` and `evidence`. `total` must equal the sum of the",
        "scores; a verdict whose total disagrees is refused, not corrected.",
        "Score every id in `REVIEW-THESE.txt`: an id you leave out is a lost",
        "verdict, not a neutral one.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    text = render(args.bundle)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out} -- {len(quality_rubric.CRITERIA)} criteria rendered")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
