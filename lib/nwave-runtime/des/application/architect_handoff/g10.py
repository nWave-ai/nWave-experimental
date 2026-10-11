#!/usr/bin/env python3
"""Internal typed-handoff operations. Public access is through ``des handoff``.

g10.py check FILE... [--targets p1,p2] [--mode auto|interactive] [--dir DIR]
      every defect at once, each with WHAT/WHY/HOW. Exit 0: no defect and every check ran.
      Exit 1: defects. Exit 3: no defect, but some check could not run (it is named). Exit 2: wrong usage.
g10.py run --dir DIR --id ID --tool TOOL --target TARGET --variant VARIANT [options] -- COMMAND...
      run a command and record what was OBSERVED (argv, exit status, duration, output bytes, trace bytes,
      the version printed by argv[0] for quint tools) plus what the caller DECLARES (tool kind, target,
      variant, model id, checks, seed, measure, violation exit); the receipts have one writer: this command.
g10.py record --dir DIR --id ID ... --exit N --result CLASS -- COMMAND...
      store a CLAIM about a run that was not executed here (no artifacts: readers can tell it from a measurement)
g10.py describe                  the grammar, as the architect reads it
g10.py rules                     the rule table (markdown)
g10.py render FILE... [--html OUT]   human view; scenarios are read from their raw traces
g10.py summary FILE...           what is established, what is not
g10.py prompt FILE... --role ROLE [--value N] [--targets p1,p2] [--template FILE]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import typing as t
from pathlib import Path

from . import g10_codec as C
from . import g10_project as P
from . import g10_rules as RU
from . import g10_run as RUN
from . import g10_types as T
from .g10_defect import SKIPPED_AFTER_DECODE, Defect, report


def load_files(paths: t.Sequence[str]) -> tuple[T.Handoff | None, list[Defect]]:
    """Read, decode and merge the files (the architect's sidecar and the receipts the tool wrote)."""
    ds: list[Defect] = []
    parts: list[T.Handoff] = []
    for path in paths:
        doc, bad = C.load_json(path)
        ds += bad
        if bad:
            continue
        ds += C.resolve_authoring(doc, str(Path(os.path.abspath(path)).parent))  # noqa: PTH100 - keep caller's lexical path, not a symlink target
        h, more = C.decode_handoff(doc)
        ds += more
        if h is not None:
            parts.append(h)
    if ds:
        return None, ds
    merged: T.Handoff = {}
    try:
        for p in parts:
            merged = C.merge(merged, p)
    except C.MergeConflict as exc:
        return None, [exc.defect]
    return merged, []


class Usage(Exception):
    """A wrong command line, said in one sentence; exit status 2."""


def _base_dir(args: argparse.Namespace) -> str:
    """The directory of the kept files (artifacts/, traces/). Never guessed from the order of the files."""
    if args.dir:
        return os.path.abspath(args.dir)  # noqa: PTH100 - lexical directory identity is part of the preserved CLI contract
    dirs = {str(Path(os.path.abspath(f)).parent) for f in args.files}  # noqa: PTH100 - preserve distinct caller directories across symlinks
    if len(dirs) > 1:
        raise Usage(
            "the files are in different directories ("
            + ", ".join(sorted(dirs))
            + "); give --dir, the directory of the kept files"
        )
    return dirs.pop()


def _targets(args: argparse.Namespace) -> list[str] | None:
    return (
        [x for x in args.targets.split(",") if x] if args.targets is not None else None
    )


def _loaded(args: argparse.Namespace) -> T.Handoff | None:
    """The merged handoff, or None after printing why it cannot be read (the command then exits 1)."""
    if hasattr(args, "handoff"):
        return args.handoff
    h, ds = load_files(args.files)
    if h is None:
        print(report(ds, SKIPPED_AFTER_DECODE))
    return h


def cmd_check(args: argparse.Namespace) -> int:
    h = _loaded(args)
    if h is None:
        return 1
    ds, skipped = RU.check(h, _targets(args), args.mode, _base_dir(args))
    out = report(ds, "; ".join(skipped) or None)
    runs = P.summary(h)["runs"]
    print(
        out
        + f"\nReceipts: {runs['kept_output']} with a kept output (sha256 checked by R6), {runs['claim']} claims without output."
    )
    return 1 if ds else (3 if skipped else 0)


def cmd_render(args: argparse.Namespace) -> int:
    h = _loaded(args)
    if h is None:
        return 1
    if args.html:
        page = P.render_html(h, _base_dir(args))
        try:
            with open(args.html, "w", encoding="utf-8") as fh:
                fh.write(page)
        except OSError as exc:
            print(
                report(
                    [
                        Defect(
                            "G12",
                            args.html,
                            f"cannot write the page: {exc.strerror}",
                            "the page is the shared view of the scenarios",
                            "give a path in an existing directory that you can write to",
                        )
                    ]
                )
            )
            return 1
        print(f"wrote {args.html}")
    else:
        print(P.render_markdown(h, _base_dir(args)))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    h = _loaded(args)
    if h is None:
        return 1
    print(json.dumps(P.summary(h), indent=1, sort_keys=True))
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    h = _loaded(args)
    if h is None:
        return 1
    try:
        tpl = ""
        if args.template:
            with open(args.template, "rb") as fh:
                tpl = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            report(
                [
                    Defect(
                        "G12",
                        args.template,
                        "cannot read the template: "
                        + (
                            exc.strerror
                            if isinstance(exc, OSError)
                            else "the file is not UTF-8 text"
                        ),
                        "the WHAT of the role comes from its template",
                        "give the path of an existing UTF-8 text file",
                    )
                ]
            )
        )
        return 1
    try:
        print(
            P.compose(
                args.role,
                h,
                tpl,
                value=args.value,
                targets=_targets(args),
                base_dir=_base_dir(args),
            )
        )
    except P.ProjectionError as exc:
        print(report([exc.defect]))
        return 1
    return 0


def _measure(s: str | None) -> tuple[str, int] | None:
    """Strict ASCII check: str.isdigit is true for non-ASCII digits, which int() then rejects."""
    if s is None:
        return None
    kind, _, value = s.partition("=")
    if (
        kind not in ("states", "cases", "samples")
        or not (1 <= len(value) <= 15)
        or not all(c in "0123456789" for c in value)
        or int(value) < 1
    ):
        raise argparse.ArgumentTypeError(
            f"{s!r} is not a measurement declaration: WHAT: it must be states=N, cases=N or samples=N, N an integer "
            "of 1..15 ASCII digits, N >= 1; WHY: a measure nobody can read back is not a measure; HOW: pass for "
            "example --measure states=1000"
        )
    return kind, int(value)


def _timeout(s: str) -> int:
    try:
        n = int(s)
    except ValueError:
        n = 0
    if not 1 <= n <= 86400:
        raise argparse.ArgumentTypeError(
            f"{s!r} is not a timeout this tool can honour: WHAT: --timeout takes an integer number of seconds in "
            "1..86400; WHY: a timeout that cannot be set would be recorded as one that was; HOW: pass for example "
            "--timeout 600"
        )
    return n


def _cmd(args: argparse.Namespace) -> list[str]:
    c = list(args.command)
    return c[1:] if c[:1] == ["--"] else c


def cmd_run(args: argparse.Namespace) -> int:
    if args.violation_exit is not None and args.tool in (
        "quint_typecheck",
        "quint_run",
        "quint_verify",
    ):
        print(
            "g10.py run: --violation-exit is for tools whose output this tool cannot read; quint evidence is read "
            "from the output (drop --violation-exit)",
            file=sys.stderr,
        )
        return 2
    try:
        run = RUN.execute(
            args.dir,
            args.id,
            args.tool,
            args.target,
            args.variant,
            _cmd(args),
            model_id=args.model,
            model_file=args.model_file,
            checks=[x for x in (args.checks or "").split(",") if x],
            seed=args.seed,
            measure=args.measure,
            trace=args.trace,
            cwd=args.cwd,
            version_argv=(
                args.version_command
                if hasattr(args, "version_command")
                else args.version_argv.split()
                if args.version_argv
                else None
            ),
            timeout_s=args.timeout,
            replace=args.replace,
            violation_exit=args.violation_exit,
            **(
                {"receipt_store": args.receipt_store}
                if hasattr(args, "receipt_store")
                else {}
            ),
        )
    except RUN.RunError as exc:
        print(report([exc.defect]))
        return 1
    print(
        f"recorded {run.id}: exit {run.exit_status} {run.result_class} in {run.duration_s}s; kept {', '.join(a.path for a in run.artifacts)}"
    )
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    try:
        run = RUN.record_authored(
            args.dir,
            args.id,
            args.tool,
            args.tool_version,
            args.target,
            args.variant,
            _cmd(args),
            args.exit,
            args.result,
            model_id=args.model,
            model_sha256=args.model_sha256,
            checks=[x for x in (args.checks or "").split(",") if x],
            seed=args.seed,
            measure=args.measure,
            duration_s=args.duration,
            replace=args.replace,
            **(
                {"receipt_store": args.receipt_store}
                if hasattr(args, "receipt_store")
                else {}
            ),
        )
    except RUN.RunError as exc:
        print(report([exc.defect]))
        return 1
    print(
        f"recorded the CLAIM {run.id}: exit {run.exit_status} {run.result_class} (not executed here)"
    )
    return 0


def build_parser(*, native: bool = False) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="des handoff" if native else "g10.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("describe").set_defaults(fn=lambda a: print(P.describe_types()) or 0)
    sub.add_parser("rules").set_defaults(fn=lambda a: print(RU.rules_markdown()) or 0)

    def files(p: argparse.ArgumentParser) -> None:
        p.add_argument("files", nargs="*" if native else "+", metavar="FILE")
        p.add_argument(
            "--dir",
            help="directory of the kept files (default: the directory of the first FILE)",
        )

    c = sub.add_parser("check")
    files(c)
    c.add_argument("--targets")
    c.add_argument("--mode", choices=("auto", "interactive"), default="auto")
    c.set_defaults(fn=cmd_check)
    r = sub.add_parser("render")
    files(r)
    r.add_argument("--html")
    r.set_defaults(fn=cmd_render)
    s = sub.add_parser("summary")
    files(s)
    s.set_defaults(fn=cmd_summary)
    p = sub.add_parser("prompt")
    files(p)
    if native:
        from . import ROLE_VIEWS

        p.add_argument("--role", choices=tuple(ROLE_VIEWS), required=True)
        p.add_argument(
            "--root-context", required=True, help="UTF-8 root input, retained verbatim"
        )
        p.add_argument(
            "--template-name", default=None, help="shipped source template name"
        )
        p.add_argument("--template-dir")
        p.add_argument(
            "--skills-dir",
            help="explicit host-installed skill tree for portable instruction paths",
        )
        p.add_argument("--candidate")
        p.add_argument(
            "--role-input", help="sealed reviewer/examiner input from des prepare-role"
        )
        p.add_argument(
            "--phase", choices=("before", "after"), help="explicit prefactoring phase"
        )
    else:
        p.add_argument("--role", choices=P.ROLES, required=True)
    p.add_argument("--value", type=int)
    p.add_argument("--targets")
    p.add_argument("--template")
    p.set_defaults(fn=cmd_prompt)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--dir", required=not native, help="directory of the driven artifacts"
        )
        p.add_argument("--id", required=True)
        p.add_argument("--target", required=True, choices=t.get_args(T.Target))
        p.add_argument("--variant", required=True)
        p.add_argument("--model")
        p.add_argument(
            "--checks", help="comma-separated property names or law ids this run checks"
        )
        p.add_argument("--seed")
        p.add_argument(
            "--measure",
            type=_measure,
            help="states=N | cases=N | samples=N (N: 1..15 ASCII digits, N >= 1)",
        )
        p.add_argument("--replace", action="store_true")
        p.add_argument("command", nargs=argparse.REMAINDER, help="-- COMMAND ...")

    ru = sub.add_parser("run")
    common(ru)
    ru.add_argument("--tool", required=True, choices=t.get_args(T.Tool))
    ru.add_argument(
        "--model-file",
        help="the model file the command reads, relative to --dir; its sha256 is recorded",
    )
    ru.add_argument(
        "--trace",
        help="the trace file the command writes, relative to --dir; it is kept with its sha256",
    )
    ru.add_argument("--cwd")
    ru.add_argument(
        "--version-argv",
        help="command that prints the tool version, DECLARED by you (quint tools default to "
        "the quint that runs: `argv[0] --version`)",
    )
    ru.add_argument(
        "--timeout",
        type=_timeout,
        default=600,
        help="seconds the command may run, 1..86400",
    )
    ru.add_argument(
        "--violation-exit",
        type=int,
        help="the exit status that means a check failed, DECLARED by you (this tool cannot read this tool's "
        "output); refused for quint tools: their evidence is read from the output",
    )
    ru.set_defaults(fn=cmd_run)
    rc = sub.add_parser("record")
    common(rc)
    rc.add_argument("--tool", required=True, choices=t.get_args(T.Tool))
    rc.add_argument("--tool-version", required=True)
    rc.add_argument("--exit", type=int, required=True)
    rc.add_argument("--result", required=True, choices=t.get_args(T.ResultClass))
    rc.add_argument("--model-sha256")
    rc.add_argument("--duration", type=float)
    rc.set_defaults(fn=cmd_record)
    if native:
        from pathlib import Path

        from des.cli._repo_root_arg import add_repo_root_argument

        add_repo_root_argument(ap, "--repo-root", type=Path, default=Path.cwd())
        for child in sub.choices.values():
            add_repo_root_argument(
                child, "--repo-root", type=Path, default=argparse.SUPPRESS
            )
    return ap


def configure_streams() -> None:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):  # the same bytes whatever the locale; a character that cannot be written is escaped, never a traceback
        reconf = getattr(stream, "reconfigure", None)
        if reconf is not None:
            reconf(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str]) -> int:
    configure_streams()
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Usage as exc:
        print(f"g10.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
