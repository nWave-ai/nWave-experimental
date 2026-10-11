"""Mutants that nobody chose: every control-flow and comparison site of every g10 module, changed one at a time.

tests/mutation_check.py holds mutants I wrote for conditions I knew about; a reviewer's own mutants showed that is not
enough (about a third survived). This script removes the author from the choice: it walks the AST of each `g10*.py`
module and, for each site below, writes ONE changed copy of the module in a scratch copy of this folder and runs the
whole suite (fail-fast) against it. A mutant is KILLED when some test fails and SURVIVES when all tests pass.

  negate-test   `if x:` / `x if c else y` / `while x:`           -> `if not (x):`
  and-or        `a and b`                                          -> `a or b`   (and back)
  compare       ==, !=, <, <=, >, >=, in, not in, is, is not       -> its opposite
  drop-not      `not x`                                            -> `x`
  bool          True / False                                       -> the other
  int           an integer constant n                              -> n + 1
  arith         +, -                                               -> the other
  drop-call     a statement that only calls (`out.append(x)`)     -> `pass`
  drop-sorted   `sorted(x, ...)`                                   -> `list(x)`
  str-compare   `x == "tag"`                                       -> `x == "tag?"`

Not mutated: docstrings, the RULES table text, and annotations. A survivor is NOT automatically a missing test: some
change nothing a caller can see. They are listed with their source line so each can be classified by a person.

Run:  cd analysis/g10 && python3 tests/mutation_auto.py [--module g10_rules.py] [--jobs 6] [--limit N] [--only-op OP]
      [--list] [--results FILE]
Results are appended to --results (JSON lines) as they come, so an interrupted run resumes where it stopped."""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


HERE = str(Path(__file__).resolve().parent)
ROOT = str(Path(HERE).parent)
PY = sys.executable
TESTS = sorted(
    "tests." + file.stem
    for file in Path(HERE).iterdir()
    if file.name.startswith("test_")
    and file.suffix == ".py"
    and file.name != "test_mutation_auto.py"
)  # every suite file of the folder

CMP_FLIP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}


class Site:
    __slots__ = ("index", "line", "module", "op", "text")

    def __init__(self, module: str, op: str, index: int, line: int, text: str):
        self.module, self.op, self.index, self.line, self.text = (
            module,
            op,
            index,
            line,
            text,
        )

    @property
    def key(self) -> str:
        return f"{self.module}:{self.line}:{self.op}:{self.index}"


def _skip_nodes(tree: ast.Module) -> set[int]:
    """ids of nodes whose subtree is never mutated: docstrings, the RULES table and annotations."""
    skip: set[int] = set()

    def mark(n: ast.AST) -> None:
        for x in ast.walk(n):
            skip.add(id(x))

    for n in ast.walk(tree):
        if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            body = n.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                mark(body[0])
        if isinstance(n, ast.arg) and n.annotation is not None:
            mark(n.annotation)
        if (
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.returns is not None
        ):
            mark(n.returns)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in n.decorator_list:
                mark(dec)
        if isinstance(n, ast.AnnAssign):
            mark(n.annotation)
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            if any(isinstance(t, ast.Name) and t.id in ("RULES",) for t in targets):
                mark(n)
    for n in tree.body:  # the `if __name__ == "__main__":` guard
        if (
            isinstance(n, ast.If)
            and isinstance(n.test, ast.Compare)
            and isinstance(n.test.left, ast.Name)
            and n.test.left.id == "__name__"
        ):
            mark(n)
    return skip


def sites_of(src: str, module: str) -> list[tuple[Site, ast.AST]]:
    tree = ast.parse(src)
    skip = _skip_nodes(tree)
    found: list[tuple[Site, ast.AST]] = []
    lines = src.splitlines()

    def add(op: str, node: ast.AST, extra: int = 0) -> None:
        line = getattr(node, "lineno", 0)
        found.append(
            (
                Site(
                    module,
                    op,
                    extra,
                    line,
                    lines[line - 1].strip() if 0 < line <= len(lines) else "",
                ),
                node,
            )
        )

    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            add("negate-test", node)
        elif isinstance(node, ast.BoolOp):
            add("and-or", node)
        elif isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in CMP_FLIP:
                    add("compare", node, i)
            if (
                len(node.ops) == 1
                and isinstance(node.comparators[0], ast.Constant)
                and isinstance(node.comparators[0].value, str)
                and type(node.ops[0]) in (ast.Eq, ast.NotEq)
            ):
                add("str-compare", node)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            add("drop-not", node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            add("bool", node)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            add("int", node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            add("arith", node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            add("drop-call", node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sorted"
        ):
            add("drop-sorted", node)
    # the same node can be visited under two operators only through different ops; the key keeps them apart
    seen: dict[str, int] = {}
    out = []
    for s, n in found:
        base = f"{s.module}:{s.line}:{s.op}:{s.index}"
        k = seen.get(base, 0)
        seen[base] = k + 1
        s.index = s.index * 100 + k
        out.append((s, n))
    return out


class _Apply(ast.NodeTransformer):
    def __init__(self, target: ast.AST, site: Site):
        self.target, self.site = target, site

    def visit(self, node: ast.AST):
        if node is not self.target:
            return super().visit(node)
        op = self.site.op
        if op == "negate-test":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)  # type: ignore[attr-defined]
            return node
        if op == "and-or":
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()  # type: ignore[attr-defined]
            return node
        if op == "compare":
            i = (
                self.site.index // 100
            )  # the key is operator position * 100 + a counter for nodes that share a line and an operator
            node.ops[i] = CMP_FLIP[type(node.ops[i])]()  # type: ignore[attr-defined]
            return node
        if op == "str-compare":
            c = node.comparators[0]  # type: ignore[attr-defined]
            c.value = c.value + "?"
            return node
        if op == "drop-not":
            return node.operand  # type: ignore[attr-defined]
        if op == "bool":
            return ast.copy_location(ast.Constant(value=not node.value), node)  # type: ignore[attr-defined]
        if op == "int":
            return ast.copy_location(ast.Constant(value=node.value + 1), node)  # type: ignore[attr-defined]
        if op == "arith":
            node.op = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()  # type: ignore[attr-defined]
            return node
        if op == "drop-call":
            return ast.copy_location(ast.Pass(), node)
        if op == "drop-sorted":
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="list", ctx=ast.Load()),
                    args=[node.args[0]],
                    keywords=[],
                ),
                node,
            )  # type: ignore[attr-defined]
        raise AssertionError(op)


def mutate(src: str, module: str, key: str) -> str:
    """The module text with exactly the site `key` changed (the AST is re-read so every call starts from the original)."""
    tree = ast.parse(src)
    for site, node in sites_of(src, module):
        if site.key != key:
            continue
        # sites_of walked its own tree; find the same node by position in the fresh tree
        for n in ast.walk(tree):
            if (
                type(n) is type(node)
                and getattr(n, "lineno", -1) == getattr(node, "lineno", -2)
                and getattr(n, "col_offset", -1) == getattr(node, "col_offset", -2)
            ):
                if site.op == "compare" and not isinstance(n, ast.Compare):
                    continue
                tree = _Apply(n, site).visit(tree)
                ast.fix_missing_locations(tree)
                return ast.unparse(tree)
    raise AssertionError(f"site {key} not found")


def modules() -> list[str]:
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "g10*.py")))


def run_suite(workdir: str, timeout: int) -> tuple[int, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run(
            [PY, "-B", "-W", "ignore", "-m", "unittest", "-f", *TESTS],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def main() -> int:
    global TESTS
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--module", action="append", help="mutate only this module (repeatable)"
    )
    ap.add_argument("--only-op", action="append")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--list", action="store_true", help="print the sites and stop")
    ap.add_argument(
        "--keys",
        help="a file with one site key per line: run exactly these sites again, whatever --results already holds",
    )
    ap.add_argument(
        "--tests",
        nargs="+",
        help="test modules a mutant must fail (default: every test_*.py of the folder, except this tool's own)",
    )
    ap.add_argument(
        "--results",
        default=os.path.join(tempfile.gettempdir(), "g10-auto-results.jsonl"),
    )
    args = ap.parse_args()
    if args.tests:
        TESTS = list(args.tests)
    mods = args.module or modules()
    sites: list[Site] = []
    for m in mods:
        with open(os.path.join(ROOT, m), encoding="utf-8") as fh:
            sites += [
                s
                for s, _ in sites_of(fh.read(), m)
                if not args.only_op or s.op in args.only_op
            ]
    if args.list:
        for s in sites:
            print(s.key, "|", s.text[:110])
        print(len(sites), "sites")
        return 0
    done: dict[str, dict] = {}
    if os.path.exists(args.results):
        with open(args.results, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    if (
                        r["status"] != "not-applied"
                    ):  # a site this tool could not apply is tried again
                        done[r["key"]] = r
    if args.keys:
        with open(args.keys, encoding="utf-8") as fh:
            wanted = {line.strip() for line in fh if line.strip()}
        sites = [s for s in sites if s.key in wanted]
        missing = sorted(wanted - {s.key for s in sites})
        if missing:
            print(
                "keys that name no site (the module changed, or --module does not cover them):",
                ", ".join(missing[:10]),
            )
            return 2
        done = {}  # the point of --keys is to run these again against the current tests
    todo = [s for s in sites if s.key not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(
        f"{len(sites)} sites, {len(done)} already done, {len(todo)} to run with {args.jobs} jobs",
        flush=True,
    )
    if not todo:
        return report(sites, done)
    tmp = tempfile.mkdtemp(prefix="g10-auto-")
    workers: list[str] = []
    try:
        for i in range(args.jobs):
            w = os.path.join(tmp, f"w{i}", "g10")
            shutil.copytree(
                ROOT,
                w,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "mutants", "*.pyc", ".g10.lock"
                ),
            )
            workers.append(w)
        rc, out = run_suite(workers[0], args.timeout)
        if rc != 0:
            print(
                "BASELINE FAILS on the unmutated copy; no mutant can be judged:\n",
                out[-2000:],
            )
            return 2
        free: list[str] = list(workers)
        lock = threading.Lock()
        sources = {
            m: open(os.path.join(ROOT, m), encoding="utf-8").read() for m in mods
        }

        def one(s: Site) -> dict:
            with lock:
                w = free.pop()
            path = os.path.join(w, s.module)
            t0 = time.monotonic()
            try:
                try:
                    mutated = mutate(sources[s.module], s.module, s.key)
                except Exception as exc:  # a site this tool cannot apply is reported, never silently skipped
                    return {
                        "key": s.key,
                        "status": "not-applied",
                        "why": repr(exc)[:200],
                        "line": s.line,
                        "text": s.text,
                        "op": s.op,
                    }
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(mutated)
                rc, out = run_suite(w, args.timeout)
                status = (
                    "survived"
                    if rc == 0
                    else ("timeout" if rc == 124 and out == "TIMEOUT" else "killed")
                )
                if status == "killed" and (
                    "SyntaxError" in out or "IndentationError" in out
                ):
                    status = "invalid"
                return {
                    "key": s.key,
                    "status": status,
                    "line": s.line,
                    "text": s.text,
                    "op": s.op,
                    "seconds": round(time.monotonic() - t0, 1),
                }
            finally:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(sources[s.module])
                with lock:
                    free.append(w)

        with (
            cf.ThreadPoolExecutor(max_workers=args.jobs) as ex,
            open(args.results, "a", encoding="utf-8") as fh,
        ):
            futs = [ex.submit(one, s) for s in todo]
            for n, f in enumerate(cf.as_completed(futs), 1):
                r = f.result()
                done[r["key"]] = r
                fh.write(json.dumps(r) + "\n")
                fh.flush()
                if n % 25 == 0 or r["status"] in ("survived", "timeout", "not-applied"):
                    print(
                        f"[{n}/{len(todo)}] {r['status']:9} {r['key']}  {r['text'][:80]}",
                        flush=True,
                    )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return report(sites, done)


def report(sites: list[Site], done: dict[str, dict]) -> int:
    mine = [done[s.key] for s in sites if s.key in done]
    by: dict[str, int] = {}
    for r in mine:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(
        "\n" + ", ".join(f"{k}: {v}" for k, v in sorted(by.items())),
        f"of {len(mine)} mutants",
    )
    return (
        1
        if by.get("survived")
        or by.get("timeout")
        or by.get("not-applied")
        or by.get("invalid")
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
