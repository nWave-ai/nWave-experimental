#!/usr/bin/env python3
"""Reject a commit made under a placeholder git identity (IP/authorship guard).

Root cause (2026-06-24): nWave tests set a hermetic placeholder git identity
(``test@example.com``, ``t@t.com``, ``dev@test.com``, ...) either via
``git config`` or via the ``GIT_AUTHOR_EMAIL`` / ``GIT_COMMITTER_EMAIL``
environment variables. A test that does this against the REAL repo (instead of
an isolated tmp repo, or without restoring the prior value / clearing the env)
leaks the placeholder -> every subsequent real commit (``des commit-slice``,
agents, manual) inherits the placeholder author -> months of work get
mis-attributed and the author cannot prove the code is theirs (IP/authorship
proof is broken; see the 5-month ``test@example.com`` / ``t@t.com`` contamination
corrected on ``feature/atdd-pure-staging``).

This pre-commit hook fails the commit (exit 1) when the EFFECTIVE commit identity
matches a placeholder pattern, so a leaked-identity commit is caught at commit
time instead of silently shipping mis-attributed history. It is the
recurrence-proof backstop: it fires no matter which test leaks the identity, and
it checks the env-resolved identity (``git var GIT_AUTHOR_IDENT``), NOT just the
config -- so it also catches ``GIT_AUTHOR_EMAIL`` env-var pollution that
``git config user.email`` would hide.

Conservative by design: the patterns mark only clear TEST placeholders, never a
real contributor (e.g. ``...@users.noreply.github.com``, ``...@nwave.ai``,
``...@fejer.io`` all pass).
"""

from __future__ import annotations

import re
import subprocess
import sys


# Email patterns that mark a git identity as a TEST PLACEHOLDER. Kept narrow to
# avoid false positives on real identities.
_PLACEHOLDER_EMAIL_PATTERNS: tuple[str, ...] = (
    r"@example\.(com|test|org)$",
    r"@test\.(com|local)$",
    r"\.invalid$",
    r"@nwave\.local$",
    r"^t@t(\.|$)",  # t@t.com, t@t, t@t.invalid
    r"^test@",  # test@example.com, test@nwave.ai, test@test.com
    r"^dev@test",
)
_PLACEHOLDER_NAME_PATTERNS: tuple[str, ...] = (
    r"^T$",  # single-letter placeholder
    r"^Test$",
)

# "Name <email> 1700000000 +0200"  ->  ("Name", "email")
_IDENT_RE = re.compile(r"^(?P<name>.*) <(?P<email>[^>]*)> \d+ [+-]\d+$")


def _git_ident(kind: str) -> tuple[str, str]:
    """Return (name, email) for ``git var GIT_<kind>_IDENT`` (env-resolved)."""
    try:
        result = subprocess.run(
            ["git", "var", f"GIT_{kind}_IDENT"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:  # pragma: no cover - git absent
        return ("", "")
    match = _IDENT_RE.match(result.stdout.strip())
    if not match:
        return ("", "")
    return (match.group("name"), match.group("email"))


def _matches(value: str, patterns: tuple[str, ...]) -> bool:
    return bool(value) and any(re.search(p, value, re.IGNORECASE) for p in patterns)


def _is_placeholder(name: str, email: str) -> bool:
    return _matches(email, _PLACEHOLDER_EMAIL_PATTERNS) or _matches(
        name, _PLACEHOLDER_NAME_PATTERNS
    )


def main() -> int:
    author_name, author_email = _git_ident("AUTHOR")
    committer_name, committer_email = _git_ident("COMMITTER")
    if not (
        _is_placeholder(author_name, author_email)
        or _is_placeholder(committer_name, committer_email)
    ):
        return 0
    sys.stderr.write(
        "\n  COMMIT REJECTED: placeholder git identity detected.\n"
        f"    author    = {author_name!r} <{author_email}>\n"
        f"    committer = {committer_name!r} <{committer_email}>\n\n"
        "  This is a TEST placeholder, not a real author -- a non-isolated test\n"
        "  almost certainly leaked it (via git config OR a GIT_AUTHOR_EMAIL env\n"
        "  var). Committing under it mis-attributes your work and breaks\n"
        "  IP/authorship proof.\n\n"
        "  Restore your REAL identity, then re-commit:\n"
        "    git config --local user.name  'Your Name'\n"
        "    git config --local user.email 'you@users.noreply.github.com'\n"
        "    unset GIT_AUTHOR_EMAIL GIT_AUTHOR_NAME \\\n"
        "          GIT_COMMITTER_EMAIL GIT_COMMITTER_NAME\n\n"
        "  (If this is a genuine false positive, refine the patterns in\n"
        "  scripts/hooks/reject_placeholder_git_identity.py.)\n\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
