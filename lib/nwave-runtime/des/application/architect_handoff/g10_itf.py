"""Quint traces (Informal Trace Format, `quint run --mbt --out-itf=FILE`) -> plain values and deterministic text.

Format observed on quint 0.32.0: {"#meta": {"status": ...}, "vars": [...], "states": [{"#meta": {"index": i},
<var>: <value>, "mbt::actionTaken": "<action>", "mbt::nondetPicks": {...}}]}; integers are {"#bigint": "n"},
sets {"#set": [...]}, maps {"#map": [[k, v], ...]}, tuples {"#tup": [...]}, variants {"tag": T, "value": v}."""

from __future__ import annotations

import dataclasses as dc
import json
import typing as t


class ItfError(Exception):
    """The file is not a Quint ITF trace this tool can read; the message says what is wrong."""


class QSet(tuple):
    pass


class QMap(tuple):  # tuple of (key, value) pairs
    pass


class QTup(tuple):
    pass


@dc.dataclass(frozen=True)
class QVariant:
    tag: str
    value: t.Any


@dc.dataclass(frozen=True)
class State:
    index: int
    action: (
        str | None
    )  # `mbt::actionTaken`; None when the trace was written without --mbt
    vars: t.Mapping[str, t.Any]


@dc.dataclass(frozen=True)
class Trace:
    status: str  # `#meta.status`: ok | violation | ...
    states: tuple[State, ...]


MAX_DEPTH = 100  # a state variable nests less than this; the limit is ours, so the verdict does not depend on the interpreter's stack


def _val(v: t.Any, depth: int = 0) -> t.Any:
    if depth > MAX_DEPTH:
        raise ItfError(
            f"a value in the trace is nested more than {MAX_DEPTH} levels deep"
        )
    d = depth + 1
    if isinstance(v, dict):
        if set(v) == {"#bigint"} and isinstance(v["#bigint"], str):
            try:
                return int(v["#bigint"])
            except ValueError as exc:
                raise ItfError(f"#bigint {v['#bigint']!r} is not an integer") from exc
        if set(v) == {"#set"} and isinstance(v["#set"], list):
            return QSet(_val(x, d) for x in v["#set"])
        if set(v) == {"#tup"} and isinstance(v["#tup"], list):
            return QTup(_val(x, d) for x in v["#tup"])
        if set(v) == {"#map"} and isinstance(v["#map"], list):
            pairs = []
            for p in v["#map"]:
                if not isinstance(p, list) or len(p) != 2:
                    raise ItfError("a #map entry is not a [key, value] pair")
                pairs.append((_val(p[0], d), _val(p[1], d)))
            return QMap(pairs)
        if set(v) == {"tag", "value"} and isinstance(v["tag"], str):
            return QVariant(v["tag"], _val(v["value"], d))
        return {k: _val(x, d) for k, x in v.items()}
    if isinstance(v, list):
        return [_val(x, d) for x in v]
    return v


def parse(doc: t.Any) -> Trace:
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("states"), list)
        or not isinstance(doc.get("#meta"), dict)
    ):
        raise ItfError('not an ITF trace: expected an object with "#meta" and "states"')
    states = []
    for i, s in enumerate(doc["states"]):
        if not isinstance(s, dict):
            raise ItfError(f"state {i} is not an object")
        action = s.get("mbt::actionTaken")
        if action is not None and not isinstance(action, str):
            raise ItfError(f"state {i}: mbt::actionTaken is not a string")
        meta = s.get("#meta")
        index = (
            meta.get("index", i)
            if isinstance(meta, dict) and isinstance(meta.get("index", i), int)
            else i
        )
        states.append(
            State(
                index,
                action,
                {k: _val(x) for k, x in s.items() if not k.startswith(("#", "mbt::"))},
            )
        )
    status = doc["#meta"].get("status")
    return Trace(status if isinstance(status, str) else "unknown", tuple(states))


def load(path: str) -> Trace:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except OSError as exc:
        raise ItfError(f"cannot read {path}: {exc.strerror}") from exc
    except (ValueError, RecursionError) as exc:
        raise ItfError(f"{path} is not valid JSON: {exc}") from exc
    return parse(doc)


def _sorted(items: t.Iterable[t.Any]) -> list[t.Any]:
    items = list(items)
    if all(isinstance(x, int) and not isinstance(x, bool) for x in items):
        return sorted(items)
    return sorted(items, key=fmt)


def fmt(v: t.Any) -> str:
    """Deterministic text of a value: the same value always prints the same bytes."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return v
    if isinstance(v, QSet):
        return "{" + ", ".join(fmt(x) for x in _sorted(v)) + "}"
    if isinstance(v, QMap):
        numeric = all(isinstance(k, int) and not isinstance(k, bool) for k, _ in v)
        pairs = sorted(
            v,
            key=lambda pair: (
                pair[0] if numeric else fmt(pair[0]),
                repr(pair[0]),
                repr(pair[1]),
            ),
        )
        return "{" + ", ".join(f"{fmt(k)} -> {fmt(value)}" for k, value in pairs) + "}"
    if isinstance(v, QTup):
        return "(" + ", ".join(fmt(x) for x in v) + ")"
    if isinstance(v, QVariant):
        return (
            v.tag
            if isinstance(v.value, QTup) and not v.value
            else f"{v.tag}({fmt(v.value)})"
        )
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {fmt(v[k])}" for k in sorted(v)) + "}"
    return json.dumps(v)
