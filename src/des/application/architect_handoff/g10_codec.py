"""Wire JSON <-> closed values; canonical form and sha; partial merge.

decode is total over JSON and collects EVERY shape defect in one pass. A value that decodes is
well-formed by construction; cross-field and cross-section facts are g10_rules.py's job."""

from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import math
import re
import types
import typing as t
from functools import cache

from des.ports.driven_ports.task_invocation_port import FactId

from . import g10_types as T
from .g10_defect import Defect


BAD = object()  # decode failed here; the defect is already recorded
_MAX_INT = (
    10**15
)  # a count, an exit status or a size never needs more; a bigger int would also break printing and float conversion


def _d(rule: str, where: str, what: str, why: str, how: str) -> Defect:
    return Defect(rule, where, what, why, how)


def _is_text(s: str) -> bool:
    """False for a string with an unpaired surrogate: it cannot be written as UTF-8, hashed, projected or printed."""
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


@cache
def _hints(cls: type) -> dict[str, t.Any]:
    return t.get_type_hints(cls)


def _tag_of(cls: type) -> str | None:
    for f in dc.fields(cls):
        if f.name == "tag":
            return f.default
    return None


def is_union(o: t.Any) -> bool:
    """The origin of `X | Y` or `Optional[X]` (two objects before Python 3.14, one from then on)."""
    return o is t.Union or o is types.UnionType


_PATTERN_HOW = {
    "ID": "start with a letter; use letters, digits, '_' or '-' only (at most 64 characters)",
    "Locator": "write `path`, `path:line`, `path:line-line`, `path:line:col`, `path::symbol` or `CREATE_NEW:<path>::<symbol>`; "
    "the path has no space, no leading '/' and no '..'",
    "RelPath": "write a path of letters, digits, '.', '/', '_', '-', '@' and '+', with no leading '/' and no '..'",
    "Sha": "write 64 lowercase hexadecimal digits (a sha256)",
}
_PATTERN_WHY = {
    "ID": "ids are the join keys that other sections cite",
    "Locator": "a code reference can be checked and projected; prose cannot (E-V2-D-17)",
    "RelPath": "a kept file is found by a path inside the directory of the sidecar",
    "Sha": "an identity is compared byte for byte",
}


def dec(
    tp: t.Any,
    v: t.Any,
    path: str,
    ds: list[Defect],
    meta: t.Mapping[str, t.Any] | None = None,
) -> t.Any:
    meta = meta or {}
    if tp is T.FactRef:
        if not isinstance(v, dict) or set(v) != {"ref"}:
            ds.append(
                _d(
                    "DesignFactRefExpected",
                    path,
                    "expected exactly {ref: FactId}",
                    "semantic prose belongs in the fact catalog",
                    "define the fact in facts and cite its id with {ref}",
                )
            )
            if isinstance(v, dict):
                for key in v.keys() - {"ref"}:
                    ds.append(
                        _d(
                            "DesignKeyNotInGrammar",
                            f"{path}.{key}",
                            "unknown field",
                            "FactRef has only ref",
                            "remove the field",
                        )
                    )
            return BAD
        ref = v["ref"]
        if not isinstance(ref, str):
            ds.append(
                _d(
                    "DesignFactRefExpected",
                    path + ".ref",
                    "expected a FactId string",
                    "FactRef must cite one catalog identifier",
                    "write exactly {ref: FactId}",
                )
            )
            return BAD
        if not re.fullmatch(T.ID_RE, ref):
            ds.append(
                _d(
                    "DesignFactIdShape",
                    path + ".ref",
                    "invalid fact identifier",
                    "fact ids are stable join keys",
                    _PATTERN_HOW["ID"],
                )
            )
            return BAD
        return T.FactRef(FactId(ref))
    o = t.get_origin(tp)
    if is_union(o):
        args = t.get_args(tp)
        if type(None) in args and v is None:
            return None
        rest = [a for a in args if a is not type(None)]
        if len(rest) == 1:
            return dec(rest[0], v, path, ds, meta)
        tags = ", ".join(str(_tag_of(a)) for a in rest)
        if not isinstance(v, dict) or "tag" not in v:
            ds.append(
                _d(
                    "G1",
                    path,
                    "a variant without a `tag`",
                    "the grammar is closed: a variant is chosen by its tag",
                    f"add `tag` with one of: {tags}",
                )
            )
            return BAD
        for a in rest:
            if _tag_of(a) == v["tag"]:
                return _dec_record(a, v, path, ds)
        ds.append(
            _d(
                "G1",
                path,
                f"unknown tag {v['tag']!r}",
                "the grammar is closed",
                f"use one of: {tags}",
            )
        )
        return BAD
    if o is t.Literal:
        allowed = t.get_args(tp)
        if isinstance(v, str) and v in allowed:
            return v
        ds.append(
            _d(
                "G2",
                path,
                f"value {v!r} is not allowed",
                "this field takes a closed vocabulary",
                "use one of: " + ", ".join(map(repr, allowed)),
            )
        )
        return BAD
    if o is tuple:
        if not isinstance(v, list):
            ds.append(
                _d(
                    "G3",
                    path,
                    "expected a list",
                    "this field is a collection",
                    "write it as a JSON list",
                )
            )
            return BAD
        if meta.get("nonempty") and not v:
            ds.append(
                _d(
                    "G8",
                    path,
                    "the list is empty",
                    "an empty list here would state nothing and still look complete",
                    "list at least one item, or mark the whole section not_applicable with a reason",
                )
            )
            return BAD
        et = t.get_args(tp)[0]
        items = [
            dec(
                et,
                x,
                f"{path}[{i}]",
                ds,
                {
                    "allow_blank": i > 0,
                    "pattern": T.ARGV_DATA_RE if i > 0 else T.ARGV_EXECUTABLE_RE,
                }
                if meta.get("literal_argv")
                else None,
            )
            for i, x in enumerate(v)
        ]
        list_defects: tuple[str, ...] = ()
        if meta.get("unique_refs"):
            from des.domain.design_document import fact_reference_list_defects

            list_defects = fact_reference_list_defects(
                (item for item in items if item is not BAD), path
            )
            ds.extend(
                _d(
                    problem.split()[0],
                    path,
                    problem,
                    "this semantic reference list retains its unique-entry contract",
                    "keep each FactRef once within this list; the same fact may still be cited in another slot",
                )
                for problem in list_defects
            )
        return BAD if list_defects or any(i is BAD for i in items) else tuple(items)
    if isinstance(tp, t.NewType):
        if not isinstance(v, str) or not T.valid(tp.__name__, v):
            ds.append(
                _d(
                    "G10",
                    path,
                    f"{v!r} is not a valid {tp.__name__}",
                    _PATTERN_WHY[tp.__name__],
                    _PATTERN_HOW[tp.__name__],
                )
            )
            return BAD
        return v
    if tp is str:
        if not isinstance(v, str):
            ds.append(
                _d(
                    "G3",
                    path,
                    "expected a string",
                    "wrong type for this field",
                    "write a JSON string",
                )
            )
            return BAD
        if not _is_text(v):
            ds.append(
                _d(
                    "G13",
                    path,
                    "the string holds an unpaired surrogate, which is not Unicode text",
                    "such a string cannot be written as UTF-8, so it cannot be hashed, projected or printed",
                    "write the text without that character",
                )
            )
            return BAD
        if not v.strip() and not meta.get("allow_blank"):
            ds.append(
                _d(
                    "G7",
                    path,
                    "the string is blank",
                    "a blank value cannot be told from an omission",
                    "write the fact, or `none: <reason>` when there is nothing to say",
                )
            )
            return BAD
        if "pattern" in meta and not re.fullmatch(meta["pattern"], v):
            ds.append(
                _d(
                    "G10",
                    path,
                    f"{v!r} does not match {meta['pattern']}",
                    "this field takes a closed shape",
                    "follow the pattern",
                )
            )
            return BAD
        return v
    if tp is int:
        if not isinstance(v, int) or isinstance(v, bool):
            ds.append(
                _d(
                    "G3",
                    path,
                    "expected an integer",
                    "wrong type for this field",
                    "write a JSON integer",
                )
            )
            return BAD
        if abs(v) > _MAX_INT:
            ds.append(
                _d(
                    "G9",
                    path,
                    "the integer is larger than 10^15 in absolute value",
                    "no count, exit status or size here is that large",
                    "write a smaller integer",
                )
            )
            return BAD
        if meta.get("positive") and v <= 0:
            ds.append(
                _d(
                    "G9",
                    path,
                    f"{v} is not positive",
                    "a bound of zero or less bounds nothing",
                    "write an integer >= 1",
                )
            )
            return BAD
        return v
    if tp is float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            ds.append(
                _d(
                    "G3",
                    path,
                    "expected a number",
                    "wrong type for this field",
                    "write a JSON number",
                )
            )
            return BAD
        if isinstance(v, int) and abs(v) > _MAX_INT:
            ds.append(
                _d(
                    "G9",
                    path,
                    "the number is larger than 10^15 in absolute value",
                    "no duration or measure here is that large",
                    "write a smaller number",
                )
            )
            return BAD
        if not math.isfinite(v) or (meta.get("nonneg") and v < 0):
            ds.append(
                _d(
                    "G9",
                    path,
                    f"{v} is not a finite number >= 0",
                    "a duration or measure cannot be negative or unbounded",
                    "write a finite number >= 0",
                )
            )
            return BAD
        return float(v)
    if dc.is_dataclass(tp):
        return _dec_record(tp, v, path, ds)
    raise TypeError(f"grammar bug: no decoder for {tp!r} at {path}")


def _dec_record(cls: type, v: t.Any, path: str, ds: list[Defect]) -> t.Any:
    if not isinstance(v, dict):
        ds.append(
            _d(
                "G3",
                path,
                f"expected an object for {cls.__name__}",
                "this field is a record",
                "write a JSON object",
            )
        )
        return BAD
    hints = _hints(cls)
    known = {f.name for f in dc.fields(cls)}
    bad = False
    expected = _tag_of(cls)
    if expected is not None and "tag" in v and v["tag"] != expected:
        ds.append(
            _d(
                "G1",
                f"{path}.tag",
                f"tag {v['tag']!r} is not allowed here",
                "this field takes exactly one kind of record",
                f"use tag {expected!r}, or fill the field with that record",
            )
        )
        bad = True
    for k in v:
        if k not in known:
            ds.append(
                _d(
                    "ArchitectHandoffModelTextRetired"
                    if cls is T.Model and k in {"text", "text_file"}
                    else "DesignKeyNotInGrammar",
                    f"{path}.{k}",
                    "unknown field",
                    "the grammar is closed: a field no consumer reads is a fact nobody checks",
                    "remove it, or ask for the field to be added to the grammar",
                )
            )
            bad = True
    kwargs = {}
    for f in dc.fields(cls):
        if f.name == "tag":
            continue
        if f.name in v:
            r = dec(hints[f.name], v[f.name], f"{path}.{f.name}", ds, f.metadata)
            if r is BAD:
                bad = True
            else:
                kwargs[f.name] = r
        elif f.default is dc.MISSING and f.default_factory is dc.MISSING:
            ds.append(
                _d(
                    "G5",
                    f"{path}.{f.name}",
                    "missing field",
                    "every field without a default must be given",
                    f"add `{f.name}`",
                )
            )
            bad = True
    return BAD if bad else cls(**kwargs)


def decode_handoff(doc: t.Any) -> tuple[T.Handoff | None, list[Defect]]:
    ds: list[Defect] = []
    if (
        not isinstance(doc, dict)
        or set(doc) != {"sections"}
        or not isinstance(doc["sections"], list)
    ):
        return None, [
            _d(
                "DesignKeyNotInGrammar",
                "$",
                'the document must be exactly {"sections": [...]}',
                "the grammar is closed",
                "wrap the sections",
            )
        ]
    h: T.Handoff = {}
    for i, e in enumerate(doc["sections"]):
        p = f"$.sections[{i}]"
        if not isinstance(e, dict) or set(e) != {"kind", "scope", "status"}:
            ds.append(
                _d(
                    "DesignKeyNotInGrammar",
                    p,
                    "a section is exactly {kind, scope, status}",
                    "the grammar is closed",
                    "fix the keys",
                )
            )
            continue
        if e["kind"] == "receipts":
            ds.append(
                _d(
                    "ArchitectHandoffSectionRetired",
                    p,
                    "submitted receipts section",
                    "runs belong only in the driven receipt store",
                    "use des handoff run or des handoff record",
                )
            )
            continue
        kind = dec(T.Kind, e["kind"], p + ".kind", ds)
        scope = (
            e["scope"]
            if isinstance(e["scope"], str) and re.fullmatch(T.SCOPE_RE, e["scope"])
            else None
        )
        if scope is None:
            ds.append(
                _d(
                    "G10",
                    p + ".scope",
                    f"scope {e['scope']!r} is not allowed",
                    "a section belongs to the shared design or to one value",
                    "use `shared` or `value:<n>` (n >= 1)",
                )
            )
        st = e["status"]
        status: T.Applicable | T.NotApplicable | None = None
        if not isinstance(st, dict) or st.get("tag") not in (
            "applicable",
            "not_applicable",
        ):
            ds.append(
                _d(
                    "G1",
                    p + ".status",
                    "status needs tag `applicable` or `not_applicable`",
                    "an absent section must say so, with a reason",
                    "set the tag",
                )
            )
        elif st["tag"] == "not_applicable":
            r = _dec_record(T.NotApplicable, st, p + ".status", ds)
            status = None if r is BAD else r
        elif set(st) != {"tag", "payload"}:
            ds.append(
                _d(
                    "DesignKeyNotInGrammar",
                    p + ".status",
                    "applicable is exactly {tag, payload}",
                    "the grammar is closed",
                    "fix the keys",
                )
            )
        elif kind is not BAD:
            pay = _dec_record(T.PAYLOAD[kind], st["payload"], p + ".status.payload", ds)
            status = None if pay is BAD else T.Applicable(payload=pay)
        if kind is BAD or scope is None or status is None:
            continue
        if (kind, scope) in h:
            ds.append(
                _d(
                    "G6",
                    p,
                    f"section {kind}@{scope} appears twice",
                    "a section has one author and one content",
                    "keep one, or merge them by hand",
                )
            )
            continue
        h[(kind, scope)] = T.Entry(kind=kind, scope=scope, status=status)
    return (None if ds else h), ds


# --------------------------------------------------------------------------- reading files
def _no_duplicates(pairs: list[tuple[str, t.Any]]) -> dict[str, t.Any]:
    out: dict[str, t.Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"the key {k!r} appears twice in one object")
        out[k] = v
    return out


def _no_constant(name: str) -> t.Any:
    raise ValueError(f"{name} is not valid JSON")


def load_json(path: str) -> tuple[t.Any, list[Defect]]:
    """Read one JSON file. Every failure is a defect with WHAT/WHY/HOW, never a traceback."""
    why = (
        "the sidecar is the delivered design; a file that cannot be read states nothing"
    )

    def fail(what: str, how: str) -> tuple[None, list[Defect]]:
        return None, [_d("G12", path, what, why, how)]

    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return fail(
            f"cannot read the file: {exc.strerror}",
            "give the path of an existing sidecar file",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return fail("the file is not UTF-8 text", "write the file as UTF-8 JSON")
    try:
        return json.loads(
            text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant
        ), []
    except (ValueError, RecursionError) as exc:
        return fail(
            f"the file is not valid JSON: {exc}",
            "fix the JSON; a key may appear once and NaN or Infinity are not JSON",
        )


# --------------------------------------------------------------------------- canonical form
def enc(o: t.Any, field: str | None = None, *, ordered: bool = False) -> t.Any:
    if dc.is_dataclass(o) and not isinstance(o, type):
        return {
            f.name: enc(getattr(o, f.name), f.name, ordered=ordered)
            for f in dc.fields(o)
        }
    if isinstance(o, dict):
        return {key: enc(value, ordered=ordered) for key, value in o.items()}
    if isinstance(o, tuple):
        items = [enc(x, ordered=ordered) for x in o]
        if ordered or field in T.SEQUENCE_FIELDS:
            return items
        uniq = {json.dumps(i, sort_keys=True, ensure_ascii=False): i for i in items}
        return [uniq[k] for k in sorted(uniq)]
    return o


def canon(o: t.Any) -> str:
    return json.dumps(enc(o), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical(o: t.Any, field: str | None = None) -> t.Any:
    """The same value with every set-valued tuple in the order `enc` prints it. A repeat stays (a repeated id is a defect to report).
    What a rule, a message or a rendering reads then never depends on the order in which the author wrote a list."""
    if dc.is_dataclass(o) and not isinstance(o, type):
        return dc.replace(
            o, **{f.name: canonical(getattr(o, f.name), f.name) for f in dc.fields(o)}
        )
    if isinstance(o, tuple):
        items = tuple(canonical(x) for x in o)
        if field in T.SEQUENCE_FIELDS:
            return items
        return tuple(
            sorted(
                items,
                key=lambda i: json.dumps(enc(i), sort_keys=True, ensure_ascii=False),
            )
        )
    return o


def index_by(items: t.Iterable, key: t.Callable[[t.Any], str]) -> dict[str, t.Any]:
    """key -> item. Two items with one key resolve to the one with the greatest canonical bytes, so a lookup never depends on list order."""
    return {key(x): x for x in sorted(items, key=canon)}


def sha(o: t.Any) -> str:
    return hashlib.sha256(canon(o).encode()).hexdigest()


def to_json(h: T.Handoff) -> dict:
    return {
        "sections": [
            {"kind": k, "scope": s, "status": enc(e.status, ordered=True)}
            for (k, s), e in h.items()
        ]
    }


# --------------------------------------------------------------------------- merge
class MergeConflict(ValueError):
    def __init__(self, defect: Defect):
        super().__init__(f"WHAT: {defect.what}. WHY: {defect.why}. HOW: {defect.how}")
        self.defect = defect


def merge(a: T.Handoff, b: T.Handoff) -> T.Handoff:
    """Disjoint union by (kind, scope). The same key with different content is refused, never overwritten."""
    out = dict(a)
    for k, e in b.items():
        if k in out and sha(out[k]) != sha(e):
            raise MergeConflict(
                _d(
                    "G6",
                    f"{k[0]}@{k[1]}",
                    f"section {k[0]}@{k[1]} has two different contents",
                    "a section has one author; a silent overwrite loses a fact",
                    "keep one of the two, or call replace() with the new entry when the change is intended",
                )
            )
        out[k] = e
    return out


def replace(a: T.Handoff, e: T.Entry) -> T.Handoff:
    out = dict(a)
    out[(e.kind, e.scope)] = e
    return out
