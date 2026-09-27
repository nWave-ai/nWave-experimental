#!/usr/bin/env python3
"""Give an isolated config dir the SUBSCRIPTION login, not an API-credit fallback.

Measured 2026-08-07, and it corrects an earlier claim in this campaign's own
notes. An empty `CLAUDE_CONFIG_DIR` appeared to be "still authenticated": a probe
against one returned `is_error: false` with real usage. It was not authenticated
by any subscription. It had fallen through to **API-credit billing**, which
happened to carry a small balance at that moment. When the balance ran out, both
arms of the calibration pair died within one second of each other with

    "Credit balance is too low"

after 1451s and $15.04 of credit -- none of it drawn from the Max plan that was
supposed to pay for it.

The lesson is the one this mission keeps re-learning: a probe that SUCCEEDS tells
you the operation worked, never which mechanism made it work. "It authenticated"
and "it authenticated the way I intended" are different claims, and only the
second one was load-bearing.

So the arm's login is copied deliberately, from a named profile:

    seed_auth.py --from ~/.claude-alt --into <config-dir>

Only the `claudeAiOauth` block is copied. The source file also holds MCP OAuth
tokens for unrelated services, and an arm has no business carrying those.

BOTH arms must seed from the SAME profile. Different accounts have different
rate-limit windows, and an arm that happens to start with more headroom is
measured under a condition nobody declared -- the exact confound pairing exists
to remove.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path


# The campaign executes this file by absolute path from each subject checkout.
# Python then exposes this directory rather than the repository root.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.analysis.k4 import subject as k4_subject  # noqa: E402


_CREDENTIALS = ".credentials.json"
_CONFIG = ".claude.json"
_KEEP = "claudeAiOauth"

#: The identity keys, and only these. Measured 2026-08-07: seeding
#: `.credentials.json` ALONE still fell through to API-credit billing, because
#: the login and the ACCOUNT are recorded in two different files -- the token in
#: `.credentials.json`, `oauthAccount` in `.claude.json`. With the token but no
#: account, the CLI has a valid login it cannot attribute to a plan, and bills
#: credit instead.
#:
#: The rest of `.claude.json` is deliberately left behind. It is ~77 KB of
#: project history, MCP servers and per-directory state, and copying it would
#: hand the arm the operator's whole working context -- destroying the isolation
#: this seeding exists to make safe.
_IDENTITY_KEYS = (
    "oauthAccount",
    "userID",
    "hasCompletedOnboarding",
    "lastOnboardingVersion",
)


def _sandbox_settings(config_dir: Path) -> dict[str, object]:
    """The shared fail-closed Claude policy for both isolated arms.

    The setup process runs under the rendered arm environment, so this records
    that exact PATH for Claude's later sandbox bridge.  The treatment installer
    deliberately merges this document and prepends its installed DES shim.

    Claude Code 2.1.271 resolves relative filesystem entries from
    `CLAUDE_CONFIG_DIR`. The actual delivery workspace is therefore the config
    directory's parent and is rendered as an absolute allow path. This derives
    the sandbox boundary from the one config directory the seed owns, rather
    than accepting a second caller-supplied workspace path that could drift.
    """
    workspace = config_dir.resolve().parent
    return {
        "env": {"PATH": os.environ.get("PATH", "")},
        "permissions": {
            "allow": ["Read", "Edit", "Write", "Bash", "Agent"],
            "deny": [
                "Read(/.claude-k4/.credentials.json)",
                "Read(/.claude-k4/.claude.json)",
                "Edit(./.claude-k4/**)",
                "Write(./.claude-k4/**)",
                "WebFetch",
                "WebSearch",
            ],
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "denyRead": [
                    "~/",
                    "/mnt/c/Users",
                    "/root",
                    "./.credentials.json",
                    "./.claude.json",
                ],
                "allowRead": [str(workspace)],
                "denyWrite": ["."],
            },
            "network": {
                "allowedDomains": list(k4_subject.SANDBOX_ALLOWED_NETWORK_DOMAINS)
            },
        },
    }


def seed(
    source_profile: Path,
    config_dir: Path,
    *,
    trust_project: Path | None = None,
) -> int:
    config_dir = config_dir.resolve()
    workspace = config_dir.parent
    if trust_project is not None and trust_project.expanduser().resolve() != workspace:
        sys.stderr.write(
            "WHAT: the trusted project is not the parent of the isolated Claude "
            "config directory.\n"
            f"      trusted project: {trust_project.expanduser().resolve()}\n"
            f"      config parent:   {workspace}\n"
            "WHY:  the rendered sandbox allowRead boundary is derived from the "
            "config parent. Trusting a different path would create two competing "
            "workspace definitions.\n"
            "HOW:  seed `<workspace>/.claude-k4` with `--trust-project <workspace>`.\n"
        )
        return 1
    source = source_profile / _CREDENTIALS
    if not source.is_file():
        sys.stderr.write(
            f"WHAT: no {_CREDENTIALS} in {source_profile}.\n"
            "WHY:  without it the arm falls back to API-credit billing, which is a\n"
            "      different payer, a different quota and a different failure mode\n"
            "      from the plan the campaign is supposed to measure.\n"
            f"HOW:  name a profile that has been logged in, e.g. ~/.claude.\n"
        )
        return 1
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"WHAT: could not read {source}: {exc}\n")
        return 1
    if _KEEP not in document:
        sys.stderr.write(
            f"WHAT: {source} carries no `{_KEEP}` block.\n"
            "WHY:  that block IS the subscription login. Its absence means this\n"
            "      profile is not signed in to a plan, so seeding it would produce an\n"
            "      arm that silently bills somewhere else.\n"
            "HOW:  sign that profile in first, then re-run.\n"
        )
        return 1

    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / _CREDENTIALS
    target.write_text(
        json.dumps({_KEEP: document[_KEEP]}, indent=2) + "\n", encoding="utf-8"
    )
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    source_config = source_profile / _CONFIG
    try:
        config = json.loads(source_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(
            f"WHAT: could not read {source_config}: {exc}\n"
            "WHY:  the login token and the ACCOUNT live in two different files. With\n"
            "      the token but no account, the CLI has a valid login it cannot\n"
            "      attribute to a plan, and bills API credit instead - measured, and\n"
            "      it cost 15 USD of credit before it was understood.\n"
            "HOW:  name a profile that has both files.\n"
        )
        return 1
    identity = {k: config[k] for k in _IDENTITY_KEYS if k in config}
    if "oauthAccount" not in identity:
        sys.stderr.write(
            f"WHAT: {source_config} carries no `oauthAccount`.\n"
            "WHY:  that key is what binds the login to a subscription. Without it the\n"
            "      arm authenticates and then bills the wrong payer.\n"
            "HOW:  sign that profile in interactively once, then re-run.\n"
        )
        return 1
    if trust_project is not None:
        identity["projects"] = {str(workspace): {"hasTrustDialogAccepted": True}}
    (config_dir / _CONFIG).write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8"
    )
    (config_dir / _CONFIG).chmod(stat.S_IRUSR | stat.S_IWUSR)
    (config_dir / "settings.json").write_text(
        json.dumps(_sandbox_settings(config_dir), indent=2) + "\n", encoding="utf-8"
    )

    plan = document[_KEEP].get("subscriptionType", "<unstated>")
    tier = document[_KEEP].get("rateLimitTier", "<unstated>")
    print(f"seeded {config_dir} from {source_profile.name}: plan={plan} tier={tier}")
    print(f"  identity keys carried: {', '.join(sorted(identity))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="source", required=True, type=Path)
    parser.add_argument("--into", dest="config_dir", required=True, type=Path)
    parser.add_argument(
        "--trust-project",
        type=Path,
        help="trust only this isolated campaign checkout",
    )
    args = parser.parse_args(argv)
    return seed(
        args.source.expanduser(),
        args.config_dir.expanduser(),
        trust_project=args.trust_project,
    )


if __name__ == "__main__":
    raise SystemExit(main())
