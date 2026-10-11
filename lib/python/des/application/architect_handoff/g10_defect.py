"""One defect = WHAT failed, WHY it matters, HOW to fix it. The report follows E-G08-52:
every independent problem in one pass, numbered, the count first, and the checks that could
not run (because an upstream check failed) declared with the reason."""

from __future__ import annotations

import dataclasses as dc


@dc.dataclass(frozen=True)
class Defect:
    rule: str
    where: str
    what: str
    why: str
    how: str


SKIPPED_AFTER_DECODE = (
    "cross-field and cross-section checks (rules L*, C*, CL*, M*, R*, S*, X*) did not run: "
    "they read decoded values, and decoding failed. Fix the shape defects above first."
)


def report(defects: list[Defect], skipped: str | None = None) -> str:
    tail = [f"Not run: {skipped}"] if skipped else []
    if not defects:
        return "\n".join(["0 defects.", *tail])
    lines = [f"{len(defects)} defect(s)."]
    for i, d in enumerate(defects, 1):
        lines += [
            f"{i}. [{d.rule}] {d.where}",
            f"   WHAT: {d.what}",
            f"   WHY: {d.why}",
            f"   HOW: {d.how}",
        ]
    return "\n".join(lines + tail)
