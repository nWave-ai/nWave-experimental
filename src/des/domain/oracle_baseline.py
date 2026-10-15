"""Immutable source selection for oracle measurements, independent of Git."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class BaselineCommit:
    sha: str
    tree: str

    @classmethod
    def parse(cls, raw: object) -> BaselineCommit | str:
        if not isinstance(raw, dict) or set(raw) != {"sha", "tree"}:
            return "baseline must contain exactly sha and tree; supply the original commit and its tree"
        for key in ("sha", "tree"):
            value = raw[key]
            if (
                not isinstance(value, str)
                or re.fullmatch(r"[0-9a-f]{40}", value) is None
            ):
                return f"baseline {key} must be a full lowercase 40-digit Git identity; resolve the original commit and its tree"
        return cls(raw["sha"], raw["tree"])


class BaselineSource(StrEnum):
    EXPLICIT = "explicit"
    REQUEST = "request"
    WITNESS = "witness"


@dataclass(frozen=True, slots=True)
class SelectedBaseline:
    source: BaselineSource
    revision: str | None
    commit: BaselineCommit | None


def select_oracle_baseline(
    *,
    explicit: str | None,
    request: BaselineCommit | None,
    recorded: BaselineCommit | None,
) -> SelectedBaseline | None:
    if explicit is not None:
        return SelectedBaseline(BaselineSource.EXPLICIT, explicit, None)
    if request is not None:
        return SelectedBaseline(BaselineSource.REQUEST, None, request)
    if recorded is not None:
        return SelectedBaseline(BaselineSource.WITNESS, None, recorded)
    return None


def recorded_baseline(
    history: tuple[dict[str, object], ...],
) -> BaselineCommit | str | None:
    for entry in reversed(history):
        if "baseline" not in entry:
            continue
        raw = entry["baseline"]
        if not isinstance(raw, dict) or set(raw) != {"sha", "tree", "source"}:
            return "recorded baseline must contain sha, tree and source; remeasure with a complete baseline witness"
        if raw["source"] not in tuple(BaselineSource):
            return "recorded baseline source must be explicit, request or witness; restore the original witness record"
        return BaselineCommit.parse({"sha": raw["sha"], "tree": raw["tree"]})
    return None
