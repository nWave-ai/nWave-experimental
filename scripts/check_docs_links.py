"""Validate links in the docs/ tree.

A comprehensive docs link checker. It is wired into the pre-push hook and CI
(replacing the retired relative-only ``check_markdown_links.py``), and adds
severity (error vs warning), live network checks for GitHub org links, an
opt-in external-URL check, coloured output, and configurable exit semantics.

Checks performed:

1. Internal relative links resolve on disk (file or directory exists).
   Broken => ERROR.
2. ``{{NWAVE_RAW_URL}}/<path>`` placeholders are treated as repo-root-relative
   links: the placeholder expands at release time to a raw URL mirroring the
   repo tree, so ``<path>`` must exist relative to the project root. This is
   validated everywhere the placeholder appears (including inside fenced code
   blocks, where the ``curl | python3`` install snippets live). Missing =>
   ERROR.
3. Absolute GitHub links inside the nWave-ai org => WARNING (prefer a relative
   repo link). When network is available the link's liveness is also checked:
   a 404/401/403/429/timeout stays a WARNING (the repo may be private, or we
   are rate-limited), but a 5xx / DNS / connection failure => ERROR. Links
   matched by the auto-loaded ignore config (``.docs-link-ignore.yaml``,
   ``ignore_urls``) are silenced. Links matched by ``external_org_urls`` cannot
   be relative (another repo, an issue tracker, a CI run): they are still
   checked for liveness, without the "prefer a relative repo link" warning.
4. With ``--check-external``, all other absolute http(s) URLs are checked too:
   401/403/405/429/timeout => WARNING (likely login-walled or bot-blocked),
   404/410/5xx/DNS-failure => ERROR. Links to medium.com and *.medium.com, which
   block automated page loads, are checked through ``/p/<post id>`` instead
   (moved => WARNING, gone => ERROR) and, when that is blocked too, the author
   or publication feed (missing => ERROR). A Medium URL with no post id => ERROR.
   Substack posts (``<publication>.substack.com/p/<slug>``) are checked the same
   way, through the post API (``/api/v1/posts/<slug>``) and the publication feed.
   A Substack post that refuses both checks outright (as it does from GitHub's
   runner) is not reported; a timeout still warns.
5. With ``--check-site-links`` (opt-in), relative links that resolve on disk
   but escape the ``docs/`` site root => ERROR (they 404 on the rendered site).

Anchors (``#fragment``) are stripped before resolving — fragment targets are
not validated (path-only). ``mailto:``/``tel:``/``ftp:``/``data:`` schemes are
out of scope.

Exit codes:
- Any ERROR                       => 1
- No ERROR, warnings present, and ``--warnings-as-errors`` => 1
- Otherwise                       => 0

This script is intentionally excluded from releases (not in
``build_dist.py:UTILITY_SCRIPTS`` and excluded from the public-mirror rsync in
``release-prod.yml``).

Usage:
    python scripts/check_docs_links.py
    python scripts/check_docs_links.py docs/guides
    python scripts/check_docs_links.py --check-external --warnings-as-errors
    python scripts/check_docs_links.py --no-network        # structural only
    python scripts/check_docs_links.py --exclude-dir docs/archive
    python scripts/check_docs_links.py --check-site-links  # site-escape links
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Patterns and constants
# ---------------------------------------------------------------------------

# Markdown link/image: [text](url) and ![alt](url). Captures the URL portion,
# optionally followed by a "title" we ignore. The URL may hold one level of
# balanced parentheses, e.g. https://en.wikipedia.org/wiki/Flow_(psychology).
# Anything that form cannot parse (deeper nesting, unbalanced) falls back to
# "stop at the first )", so the link is still checked and flagged, never skipped.
LINK_PATTERN = re.compile(
    r"!?\[[^\]]*\]\((?P<url>(?:[^()\s]|\([^()\s]*\))+|[^)\s]+)"
    r"(?:\s+\"[^\"]*\")?\)"
)

# {{NWAVE_RAW_URL}}/<path> — the path stops at whitespace or a closing
# delimiter (paren, quote, backtick, bracket). Matched everywhere, including
# fenced code blocks, because the real usage is bare curl commands.
PLACEHOLDER_PATTERN = re.compile(r"\{\{NWAVE_RAW_URL\}\}(?P<path>/[^\s)\"'`\]]*)?")

RAW_URL_PLACEHOLDER = "{{NWAVE_RAW_URL}}"

# Non-http absolute schemes we do not validate.
SKIP_SCHEMES = ("mailto:", "tel:", "ftp://", "ftps://", "data:")

# Hosts that carry org-owned content on GitHub.
GITHUB_HOSTS = ("github.com", "www.github.com", "raw.githubusercontent.com")

# The org whose absolute links warrant a "prefer relative" warning.
NWAVE_ORG = "nwave-ai"

# Default ignore-config path (auto-loaded, no flag required): a repo-root YAML
# file with three keys: `ignore_urls` (substrings that silence org-link
# findings), `external_org_urls` (org links still checked, without the "prefer
# relative" nudge) and `ignore_paths` (dirs/files skipped during scanning).
# Excluded from releases alongside this script.
DEFAULT_IGNORE_FILE = ".docs-link-ignore.yaml"

# HTTP request settings for liveness checks.
USER_AGENT = "nwave-docs-link-check/1.0 (+https://github.com/nWave-ai)"


# ---------------------------------------------------------------------------
# Severity and network-result categories
# ---------------------------------------------------------------------------


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class Category(Enum):
    """Outcome of a liveness probe, abstracted away from raw status codes."""

    OK = "ok"  # 2xx / 3xx
    UNAUTHORIZED = "unauthorized"  # 401 / 403 / 405 / 429 (auth / blocked / rate)
    NOT_FOUND = "not_found"  # 404 / 410
    SERVER_ERROR = "server_error"  # 5xx
    TIMEOUT = "timeout"  # request timed out
    NETWORK_ERROR = "network_error"  # DNS failure, connection refused, ...


@dataclass(frozen=True)
class Finding:
    severity: Severity
    file: str
    line: int
    url: str
    message: str


# ---------------------------------------------------------------------------
# Classification: category -> severity, per link context
# ---------------------------------------------------------------------------


def classify_org(category: Category) -> tuple[Severity, str]:
    """Severity + note for a liveness result on an nWave-ai org link.

    A 404/auth/timeout stays a WARNING (the repo may be private, or we are
    rate-limited / temporarily blocked). A 5xx or network failure is an ERROR
    (the link could not be confirmed live for a non-auth reason).
    """
    if category is Category.OK:
        return Severity.WARNING, ""
    if category in (Category.NOT_FOUND, Category.UNAUTHORIZED, Category.TIMEOUT):
        return (
            Severity.WARNING,
            f" — not confirmed live ({category.value}); may be private or "
            "rate-limited (add to the allowlist if intentional)",
        )
    # SERVER_ERROR / NETWORK_ERROR
    return Severity.ERROR, f" — not live ({category.value})"


def classify_external(category: Category) -> tuple[Severity, str] | None:
    """Severity + note for a liveness result on an external (non-org) URL.

    Returns None when the URL is fine (no finding). Auth / blocked / rate /
    timeout map to WARNING (often login-walled or bot-blocked); not-found /
    server-error / network-failure map to ERROR.
    """
    if category is Category.OK:
        return None
    if category in (Category.UNAUTHORIZED, Category.TIMEOUT):
        return (
            Severity.WARNING,
            f"external link not confirmed live ({category.value}); "
            "may require login or block automated requests",
        )
    return Severity.ERROR, f"external link not live ({category.value})"


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawLink:
    kind: str  # "link" | "placeholder"
    line: int
    value: str  # the url (for "link") or the path after the placeholder


def iter_links(content: str) -> Iterator[RawLink]:
    """Yield links from markdown content.

    - Inline ``[..](url)`` links are skipped inside fenced code blocks.
    - ``{{NWAVE_RAW_URL}}/<path>`` placeholders are yielded everywhere
      (including code blocks) since the install snippets live in code fences.
    """
    in_code_block = False
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        for match in PLACEHOLDER_PATTERN.finditer(line):
            path = match.group("path")
            if path:
                yield RawLink("placeholder", lineno, path)

        if in_code_block:
            continue
        for match in LINK_PATTERN.finditer(line):
            url = match.group("url")
            if RAW_URL_PLACEHOLDER in url:
                # Owned by the placeholder scan above; avoid double-reporting.
                continue
            yield RawLink("link", lineno, url)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def strip_fragment_and_query(value: str) -> str:
    """Drop ``#fragment`` and ``?query`` from a link/path."""
    for sep in ("#", "?"):
        if sep in value:
            value = value.split(sep, 1)[0]
    return value


def is_http(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def github_owner(url: str) -> str | None:
    """Return the lowercased owner segment if ``url`` is a GitHub URL.

    e.g. https://github.com/nWave-ai/nWave/issues/1 -> "nwave-ai".
    Returns None for non-GitHub hosts.
    """
    if not is_http(url):
        return None
    rest = url.split("://", 1)[1]
    host, _, path = rest.partition("/")
    if host.lower() not in GITHUB_HOSTS:
        return None
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    # raw.githubusercontent.com/<owner>/<repo>/<ref>/... — owner is still [0].
    return segments[0].lower()


def is_org_link(url: str) -> bool:
    return github_owner(url) == NWAVE_ORG


# ---------------------------------------------------------------------------
# Ignore config (YAML: ignore_urls + ignore_paths)
# ---------------------------------------------------------------------------

# Parsed with stdlib (no pyyaml) so the checker stays dependency-free — it runs
# under bare `python3` in the pre-push hook and a lightweight CI job that do not
# install deps. The file is still valid YAML for editors/validators; only the
# restricted subset below is understood: top-level `key:` lines and `- item`
# block lists (or an inline `key: value` scalar), with `#` comments.
_CFG_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
_CFG_ITEM_RE = re.compile(r"^-\s+(.*)$")
_IGNORE_KEYS = ("ignore_urls", "ignore_paths", "external_org_urls")


def _cfg_scalar(raw: str) -> str:
    """Strip an inline ` #` comment and surrounding quotes from a scalar."""
    value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def load_ignore_config(path: Path) -> dict[str, list[str]]:
    """Parse the ignore-config. Missing/empty/unreadable => empty config.

    Schema::

        ignore_urls:   # substrings that silence matching absolute-URL findings
          - nWave-ai/nwave-dev
        ignore_paths:  # repo-relative dirs/files skipped during scanning
          - docs/internal
        external_org_urls:  # nWave-ai links that cannot be relative; still checked
          - nWave-ai/nWave/issues
    """
    cfg: dict[str, list[str]] = {key: [] for key in _IGNORE_KEYS}
    if not path.is_file():
        return cfg
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return cfg

    current: str | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        item = _CFG_ITEM_RE.match(stripped)
        if item is not None and current is not None:
            value = _cfg_scalar(item.group(1))
            if value:
                cfg[current].append(value)
            continue
        key = _CFG_KEY_RE.match(stripped)
        if key is not None and key.group(1) in _IGNORE_KEYS:
            current = key.group(1)
            inline = _cfg_scalar(key.group(2))  # inline `key: value` scalar form
            if inline:
                cfg[current].append(inline)
        else:
            current = None  # unrecognized line ends the current list
    return cfg


def load_allowlist(path: Path) -> list[str]:
    """Load `ignore_urls` (lowercased) — substrings matched against URLs.

    Each entry is matched as a case-insensitive substring of an absolute URL —
    a full URL prefix or an ``owner/repo`` slug (e.g. ``nWave-ai/nwave-dev``).
    """
    return [u.lower() for u in load_ignore_config(path)["ignore_urls"]]


def load_ignore_excludes(path: Path) -> list[str]:
    """Load `ignore_paths` — repo-relative dirs/files to skip while scanning."""
    return load_ignore_config(path)["ignore_paths"]


def load_external_org_urls(path: Path) -> list[str]:
    """Load `external_org_urls` (lowercased): nWave-ai links that cannot be relative.

    Matched like `ignore_urls`, but a match only drops the "prefer a relative repo
    link" nudge; the link is still checked for liveness.
    """
    return [u.lower() for u in load_ignore_config(path)["external_org_urls"]]


def is_allowlisted(url: str, allowlist: Sequence[str]) -> bool:
    low = url.lower()
    return any(entry in low for entry in allowlist)


# ---------------------------------------------------------------------------
# Network probe
# ---------------------------------------------------------------------------


def probe_url(url: str, timeout: float) -> Category:
    """Probe a URL with HEAD (falling back to GET) and classify the result.

    A network failure is retried once, so a single transient blip does not read
    as a dead link; a host that fails both attempts is still a NETWORK_ERROR.

    Pure-ish wrapper over urllib so the real network is the only side effect;
    tests inject a stub with the same ``(url, timeout) -> Category`` shape.
    """
    category = _probe_once(url, timeout)
    if category is Category.NETWORK_ERROR:
        category = _probe_once(url, timeout)
    return category


def _probe_once(url: str, timeout: float) -> Category:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url, method=method, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _status_to_category(resp.status)
        except urllib.error.HTTPError as exc:
            category = _status_to_category(exc.code)
            # Some servers reject HEAD with 403/405, or answer it with 404, but
            # serve GET. Retry once; the GET result is the verdict.
            if method == "HEAD" and category in (
                Category.UNAUTHORIZED,
                Category.NOT_FOUND,
            ):
                continue
            return category
        except (TimeoutError, urllib.error.URLError) as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                return Category.TIMEOUT
            return Category.NETWORK_ERROR
        except Exception:
            return Category.NETWORK_ERROR
    return Category.NETWORK_ERROR


def _status_to_category(status: int) -> Category:
    if 200 <= status < 400:
        return Category.OK
    if status in (401, 403, 405, 429):
        return Category.UNAUTHORIZED
    if status in (404, 410):
        return Category.NOT_FOUND
    if 500 <= status < 600:
        return Category.SERVER_ERROR
    # Treat other 4xx as not-found-ish (dead).
    return Category.NOT_FOUND


# ---------------------------------------------------------------------------
# Medium links
# ---------------------------------------------------------------------------

# Medium blocks automated page loads, and even when it does not, a real-looking
# URL with an unknown post id still answers 200. Existence is read instead from
# https://medium.com/p/<post id>, which redirects to the canonical URL for a real
# post and answers 404 otherwise. When that is blocked too, the author or
# publication feed (still served to scripts) shows whether the author exists.
MEDIUM_POST_ID = re.compile(r"-([0-9a-f]{12})$")
MEDIUM_P_PATH = re.compile(r"^/p/([0-9a-f]{12})$")
REDIRECT_STATUSES = (301, 302, 303, 307, 308)


@dataclass(frozen=True)
class MediumRef:
    post_id: str
    feed_url: str | None  # None for /p/<id> links, which name no author


@dataclass(frozen=True)
class PostProbe:
    post: str  # "exists" | "gone" | "blocked"
    canonical: str = ""
    feed: Category | None = None
    detail: str = ""  # when blocked: what the post check got back
    refused: bool = False  # when blocked: the post check was refused, not timed out


MediumProbe = PostProbe  # Medium's name for the shared post probe


def is_medium_link(url: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host in ("medium.com", "www.medium.com") or host.endswith(".medium.com")


def parse_medium_url(url: str) -> MediumRef | None:
    """Post id and feed for a Medium post URL, or None if it names no post."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if host in ("medium.com", "www.medium.com"):
        p_link = MEDIUM_P_PATH.match(parts.path.rstrip("/"))
        if p_link:
            return MediumRef(p_link.group(1), None)
        if len(segments) != 2:
            return None
        owner, slug = segments
        feed = f"https://medium.com/feed/{owner}"
    elif host.endswith(".medium.com"):
        if len(segments) != 1:
            return None
        slug = segments[0]
        feed = f"https://{host}/feed"
    else:
        return None
    post = MEDIUM_POST_ID.search(slug)
    return MediumRef(post.group(1), feed) if post else None


def _same_page(a: str, b: str) -> bool:
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return (pa.hostname, pa.path.rstrip("/")) == (pb.hostname, pb.path.rstrip("/"))


@dataclass(frozen=True)
class PostContext:
    """The external post reference under check: which site, and where to look

    when the post itself cannot be confirmed (the not-found message and the
    author/publication feed to fall back on).
    """

    site: str
    missing: str
    feed_url: str | None


def classify_post(
    url: str,
    probe: PostProbe,
    context: PostContext,
    *,
    quiet_when_refused: bool = False,
) -> tuple[Severity, str] | None:
    """Severity + message for a Medium or Substack link; None when it is fine.

    A post found at another URL => WARNING (it moved). A missing post, or a
    missing author or publication when the post check is blocked => ERROR. A
    blocked post check with the author found => no finding. Both checks blocked
    => WARNING, so an unverifiable link never passes silently, unless
    quiet_when_refused is set and both checks were refused outright.
    """
    site, missing, feed_url = context.site, context.missing, context.feed_url
    if probe.post == "exists":
        if probe.canonical and not _same_page(url, probe.canonical):
            return (
                Severity.WARNING,
                f"{site} article moved; canonical URL is {probe.canonical}",
            )
        return None
    if probe.post == "gone":
        return Severity.ERROR, f"{site} post not found ({missing})"
    if probe.feed is Category.OK:
        return None
    if probe.feed is Category.NOT_FOUND:
        return (
            Severity.ERROR,
            f"{site} author or publication not found ({feed_url})",
        )
    if quiet_when_refused and probe.refused and probe.feed is Category.UNAUTHORIZED:
        # Refused by both checks: the same answer whether or not the post exists.
        return None
    feed_result = probe.feed.value if probe.feed else "none"
    return (
        Severity.WARNING,
        f"{site} link not confirmed; {site} blocked both the post and feed checks "
        f"(post check: {probe.detail or 'blocked'}; feed check: {feed_result})",
    )


def classify_medium(
    url: str, ref: MediumRef, probe: MediumProbe
) -> tuple[Severity, str] | None:
    """Severity + message for a Medium link; None when the link is fine."""
    return classify_post(
        url, probe, PostContext("Medium", f"post id {ref.post_id}", ref.feed_url)
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _status_without_redirect(url: str, timeout: float) -> tuple[int | None, str]:
    """HEAD ``url`` without following redirects: (status, Location) or (None, "")."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location", "")
    except Exception:
        return None, ""


def probe_medium(ref: MediumRef, timeout: float) -> MediumProbe:
    """Whether a Medium post exists, without loading the (blocked) article page."""
    status, location = _status_without_redirect(
        f"https://medium.com/p/{ref.post_id}", timeout
    )
    if status in REDIRECT_STATUSES and location:
        return MediumProbe(post="exists", canonical=location)
    if status in (404, 410):
        return MediumProbe(post="gone")
    feed = probe_url(ref.feed_url, timeout) if ref.feed_url else None
    detail = f"HTTP {status}" if status is not None else "no response"
    return MediumProbe(post="blocked", feed=feed, detail=detail)


# ---------------------------------------------------------------------------
# Substack links
# ---------------------------------------------------------------------------

# Substack blocks automated page loads from some networks, and its article page
# redirects rather than answering 404 for an unknown post. The post API answers
# JSON for a real post and 404 otherwise; when that is blocked too, the
# publication feed shows whether the publication exists. Handled like Medium.
SUBSTACK_POST_PATH = re.compile(r"^/p/([a-z0-9-]+)$")


@dataclass(frozen=True)
class SubstackRef:
    slug: str
    api_url: str
    feed_url: str


def is_substack_link(url: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host.endswith(".substack.com")


def parse_substack_url(url: str) -> SubstackRef | None:
    """Slug, post API and feed of a Substack post URL; None if it is not a post."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    post = SUBSTACK_POST_PATH.match(parts.path.rstrip("/"))
    if not host.endswith(".substack.com") or host == "www.substack.com" or not post:
        return None
    slug = post.group(1)
    return SubstackRef(
        slug, f"https://{host}/api/v1/posts/{slug}", f"https://{host}/feed"
    )


def _substack_post(api_url: str, timeout: float) -> tuple[Category, str, str]:
    """GET a Substack post API URL: (category, canonical URL, what came back).

    Only the post's JSON counts as found; a 200 that is not that JSON is a
    challenge page, so it counts as blocked.
    """
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    not_the_post = (Category.UNAUTHORIZED, "", "HTTP 200 without the post's JSON")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return _status_to_category(exc.code), "", f"HTTP {exc.code}"
    except ValueError:
        return not_the_post
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            return Category.TIMEOUT, "", "timeout"
        return Category.NETWORK_ERROR, "", "no response"
    except Exception:
        return Category.NETWORK_ERROR, "", "no response"
    if not isinstance(data, dict) or "slug" not in data:
        return not_the_post
    return Category.OK, str(data.get("canonical_url") or ""), "HTTP 200"


def probe_substack(ref: SubstackRef, timeout: float) -> PostProbe:
    """Whether a Substack post exists, without loading the article page."""
    category, canonical, detail = _substack_post(ref.api_url, timeout)
    if category is Category.OK:
        return PostProbe(post="exists", canonical=canonical)
    if category is Category.NOT_FOUND:
        return PostProbe(post="gone")
    feed = probe_url(ref.feed_url, timeout)
    refused = category is Category.UNAUTHORIZED
    return PostProbe(post="blocked", feed=feed, detail=detail, refused=refused)


UrlChecker = Callable[[str], Category]
MediumChecker = Callable[[MediumRef], MediumProbe]
SubstackChecker = Callable[[SubstackRef], PostProbe]


# ---------------------------------------------------------------------------
# Core checker
# ---------------------------------------------------------------------------


@dataclass
class Options:
    check_external: bool = False
    check_site_links: bool = False
    network: bool = True
    allowlist: Sequence[str] = ()
    # Links that cannot be relative: still probed, no "prefer relative" nudge.
    external_org_urls: Sequence[str] = ()
    site_roots: tuple[Path, ...] = ()
    # Predicate: given an out-of-root target path, is it private (will 404 on the
    # public site)? None => flag every out-of-root link (used by unit tests).
    site_private: Callable[[Path], bool] | None = None
    timeout: float = 10.0
    workers: int = 8


class LinkChecker:
    """Collects findings across markdown files.

    Network liveness is delegated to ``url_checker``; when ``None`` and
    ``options.network`` is True a real urllib probe is used. Tests pass a stub.
    """

    def __init__(
        self,
        project_root: Path,
        options: Options,
        url_checker: UrlChecker | None = None,
        medium_checker: MediumChecker | None = None,
        substack_checker: SubstackChecker | None = None,
    ) -> None:
        self.root = project_root.resolve()
        self.options = options
        self._url_checker = url_checker
        self._medium_checker = medium_checker
        self._cache: dict[str, Category] = {}
        self._medium_cache: dict[str, MediumProbe] = {}
        self._substack_checker = substack_checker
        self._substack_cache: dict[str, PostProbe] = {}

    # -- liveness ----------------------------------------------------------

    def _check_url(self, url: str) -> Category:
        if url in self._cache:
            return self._cache[url]
        if self._url_checker is not None:
            category = self._url_checker(url)
        else:
            category = probe_url(url, self.options.timeout)
        self._cache[url] = category
        return category

    def _prefetch(self, urls: Iterable[str]) -> None:
        """Warm the cache concurrently for the given URLs."""
        unique = sorted({u for u in urls if u not in self._cache})
        if not unique:
            return
        workers = max(1, min(self.options.workers, len(unique)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = pool.map(self._check_url, unique)
            for url, category in zip(unique, results, strict=True):
                self._cache[url] = category

    # -- per-file checks ---------------------------------------------------

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def check_placeholder(self, src: Path, link: RawLink) -> Finding | None:
        path_part = strip_fragment_and_query(link.value).lstrip("/").rstrip(".,;:")
        if not path_part:
            return None
        target = (self.root / path_part).resolve()
        if target.exists():
            return None
        return Finding(
            Severity.ERROR,
            self._rel(src),
            link.line,
            RAW_URL_PLACEHOLDER + link.value,
            f"placeholder path does not exist at repo root: {path_part}",
        )

    def check_relative(self, src: Path, link: RawLink) -> Finding | None:
        url = link.value
        if url.startswith("#"):
            return None  # pure anchor — path-only checking
        target_str = strip_fragment_and_query(url)
        if not target_str:
            return None
        target = (src.parent / target_str).resolve()
        if not target.exists():
            return Finding(
                Severity.ERROR,
                self._rel(src),
                link.line,
                url,
                f"relative link target does not exist: {target_str}",
            )
        # Guides convention: a folder linked under docs/guides/ must contain a
        # README.md — that is how the site renders it; a bare folder 404s.
        if target.is_dir() and self._guide_folder_missing_readme(target):
            return Finding(
                Severity.ERROR,
                self._rel(src),
                link.line,
                url,
                "guide folder linked but contains no README.md",
            )
        # Site-escape: target exists on disk but resolves outside the published
        # site roots. build_site.py rewrites such links to a GitHub blob URL, so
        # they only break on the published site when the target is private
        # (stripped from the public repo). With no privacy predicate (unit
        # tests), every out-of-root link is flagged.
        if self.options.check_site_links and self._escapes_site(src, target):
            predicate = self.options.site_private
            # A private source page is itself stripped from the public site, so
            # its links can't 404 publicly — skip it.
            if predicate is not None and predicate(src.resolve()):
                return None
            if predicate is None or predicate(target):
                return Finding(
                    Severity.ERROR,
                    self._rel(src),
                    link.line,
                    url,
                    "link resolves outside the docs site root "
                    f"({self._rel(target)}); private target 404s on the site",
                )
        return None

    def _guide_folder_missing_readme(self, target: Path) -> bool:
        """True if ``target`` is a docs/guides/ folder without a README.md."""
        guides = (self.root / "docs" / "guides").resolve()
        t = target.resolve()
        if not (t == guides or guides in t.parents):
            return False
        return not (t / "README.md").is_file()

    def _escapes_site(self, src: Path, target: Path) -> bool:
        """True if ``src`` is under a published root but ``target`` is not."""
        roots = [r.resolve() for r in self.options.site_roots]
        if not roots:
            return False
        src_r = src.resolve()
        if not any(src_r == r or r in src_r.parents for r in roots):
            return False
        return not any(target == r or r in target.parents for r in roots)

    def check_org(self, src: Path, link: RawLink) -> Finding | None:
        url = link.value
        if is_allowlisted(url, self.options.allowlist):
            return None
        # Listed links cannot be relative (another repo, an issue tracker, a CI
        # run): still checked for liveness, but no "prefer relative" nudge.
        external = is_allowlisted(url, self.options.external_org_urls)
        severity = Severity.WARNING
        note = ""
        if self.options.network:
            category = self._check_url(url)
            if external and category is Category.OK:
                return None
            severity, note = classify_org(category)
        elif external:
            return None
        if external:
            message = "nWave-ai link outside this repo" + note
        else:
            message = "absolute nWave-ai org link (prefer a relative repo link)" + note
        return Finding(severity, self._rel(src), link.line, url, message)

    def _check_medium(self, ref: MediumRef) -> MediumProbe:
        if ref.post_id not in self._medium_cache:
            if self._medium_checker is not None:
                probe = self._medium_checker(ref)
            else:
                probe = probe_medium(ref, self.options.timeout)
            self._medium_cache[ref.post_id] = probe
        return self._medium_cache[ref.post_id]

    def check_medium(self, src: Path, link: RawLink) -> Finding | None:
        ref = parse_medium_url(link.value)
        if ref is None:
            message = "not a valid Medium post URL (no 12-character post id)"
            return Finding(
                Severity.ERROR, self._rel(src), link.line, link.value, message
            )
        if not self.options.network:
            return None
        result = classify_medium(link.value, ref, self._check_medium(ref))
        if result is None:
            return None
        severity, message = result
        return Finding(severity, self._rel(src), link.line, link.value, message)

    def _check_substack(self, ref: SubstackRef) -> PostProbe:
        if ref.api_url not in self._substack_cache:
            if self._substack_checker is not None:
                probe = self._substack_checker(ref)
            else:
                probe = probe_substack(ref, self.options.timeout)
            self._substack_cache[ref.api_url] = probe
        return self._substack_cache[ref.api_url]

    def check_substack(self, src: Path, link: RawLink) -> Finding | None:
        ref = parse_substack_url(link.value)
        if ref is None:
            message = "not a Substack post URL (expected .../p/<slug>)"
            return Finding(
                Severity.ERROR, self._rel(src), link.line, link.value, message
            )
        if not self.options.network:
            return None
        result = classify_post(
            link.value,
            self._check_substack(ref),
            PostContext("Substack", f"slug {ref.slug}", ref.feed_url),
            quiet_when_refused=True,
        )
        if result is None:
            return None
        severity, message = result
        return Finding(severity, self._rel(src), link.line, link.value, message)

    def check_external(self, src: Path, link: RawLink) -> Finding | None:
        if self.options.check_external and is_medium_link(link.value):
            return self.check_medium(src, link)
        if self.options.check_external and is_substack_link(link.value):
            return self.check_substack(src, link)
        if not self.options.check_external or not self.options.network:
            return None
        result = classify_external(self._check_url(link.value))
        if result is None:
            return None
        severity, message = result
        return Finding(severity, self._rel(src), link.line, link.value, message)

    def check_link(self, src: Path, link: RawLink) -> Finding | None:
        url = link.value
        if url.startswith(SKIP_SCHEMES):
            return None
        if is_http(url):
            if is_org_link(url):
                return self.check_org(src, link)
            return self.check_external(src, link)
        return self.check_relative(src, link)

    def check_file(self, src: Path) -> list[Finding]:
        try:
            content = src.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        findings: list[Finding] = []
        for link in iter_links(content):
            if link.kind == "placeholder":
                finding = self.check_placeholder(src, link)
            else:
                finding = self.check_link(src, link)
            if finding is not None:
                findings.append(finding)
        return findings

    def check_files(self, files: Sequence[Path]) -> list[Finding]:
        # Prefetch all URLs needing liveness so requests run concurrently.
        if self.options.network:
            self._prefetch(self._collect_network_urls(files))
        findings: list[Finding] = []
        for src in files:
            findings.extend(self.check_file(src))
        findings.sort(key=lambda f: (f.file, f.line))
        return findings

    def _collect_network_urls(self, files: Sequence[Path]) -> list[str]:
        urls: list[str] = []
        for src in files:
            try:
                content = src.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for link in iter_links(content):
                if link.kind != "link" or not is_http(link.value):
                    continue
                if is_org_link(link.value):
                    if not is_allowlisted(link.value, self.options.allowlist):
                        urls.append(link.value)
                elif self.options.check_external and not (
                    is_medium_link(link.value) or is_substack_link(link.value)
                ):
                    urls.append(link.value)
        return urls


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------


def collect_files(paths: Sequence[Path], excluded: Sequence[Path]) -> list[Path]:
    """Collect .md files under the given paths, skipping excluded dirs."""
    excluded_resolved = [e.resolve() for e in excluded]

    def is_excluded(p: Path) -> bool:
        rp = p.resolve()
        return any(rp == e or e in rp.parents for e in excluded_resolved)

    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".md":
            if not is_excluded(path):
                files.append(path)
        elif path.is_dir():
            for md in path.rglob("*.md"):
                if not is_excluded(md):
                    files.append(md)
    return sorted(set(files))


# ---------------------------------------------------------------------------
# Exit code + reporting
# ---------------------------------------------------------------------------


def compute_exit_code(findings: Sequence[Finding], warnings_as_errors: bool) -> int:
    errors = sum(1 for f in findings if f.severity is Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity is Severity.WARNING)
    if errors:
        return 1
    if warnings and warnings_as_errors:
        return 1
    return 0


def _use_color(no_color_flag: bool) -> bool:
    if no_color_flag or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def render(findings: Sequence[Finding], *, use_color: bool) -> str:
    red = "\033[31m" if use_color else ""
    yellow = "\033[33m" if use_color else ""
    reset = "\033[0m" if use_color else ""

    lines: list[str] = []
    for f in findings:
        colour = red if f.severity is Severity.ERROR else yellow
        lines.append(
            f"{colour}{f.severity.value}{reset} {f.file}:{f.line}: {f.message}\n"
            f"    link: {f.url}"
        )

    errors = sum(1 for f in findings if f.severity is Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity is Severity.WARNING)
    summary = (
        f"{red if errors else ''}{errors} error(s){reset if errors else ''}, "
        f"{yellow if warnings else ''}{warnings} warning(s){reset if warnings else ''}"
    )
    if lines:
        return "\n".join(lines) + "\n\n" + summary
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_docs_links.py",
        description="Validate links in the docs/ tree.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan (default: docs/).",
    )
    parser.add_argument(
        "--check-external",
        action="store_true",
        help="Also check non-nWave-ai absolute http(s) URLs for liveness.",
    )
    parser.add_argument(
        "--check-site-links",
        action="store_true",
        help=(
            "Flag relative links that resolve on disk but escape the docs/ "
            "site root (they 404 on the published site). ERROR severity."
        ),
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Skip all network liveness checks (structural checks only).",
    )
    parser.add_argument(
        "--warnings-as-errors",
        "--strict",
        dest="warnings_as_errors",
        action="store_true",
        help="Exit non-zero when warnings are present (even without errors).",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        metavar="DIR",
        help="Directory to skip (repeatable). Relative to CWD or absolute.",
    )
    parser.add_argument(
        "--ignore-file",
        dest="ignore_file",
        metavar="PATH",
        help=f"Ignore file silencing org links (default: <repo>/{DEFAULT_IGNORE_FILE}).",
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout (s)."
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Concurrent request workers."
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable coloured output."
    )
    return parser.parse_args(list(argv))


def _published_roots() -> tuple[str, ...]:
    """Repo-relative published doc roots — the single source is build_site.py.

    Falls back to the known roots if the (dev-only) site generator can't be
    imported, so the checker never hard-fails on that import.
    """
    try:
        from scripts.docs_site.build_site import DOC_ROOTS

        return tuple(DOC_ROOTS)
    except Exception:
        return ("docs/guides", "docs/reference")


def _build_privacy_predicate(
    project_root: Path,
) -> Callable[[Path], bool] | None:
    """Return a predicate: is an out-of-root target private (404s publicly)?

    Consults the same catalog logic the release pipeline uses to strip private
    agents/skills. Returns None when the catalog is unavailable (privacy can't
    be determined, so the checker flags no site-escape link).
    """
    try:
        from scripts.shared.agent_catalog import (
            build_ownership_map,
            detect_command_skills,
            is_public_agent,
            is_public_skill,
            load_private_skills,
            load_public_agents,
        )
    except Exception:
        return None

    nwave = project_root / "nWave"
    public_agents = load_public_agents(nwave, strict=False)
    if not public_agents:
        return None
    ownership = build_ownership_map(nwave / "agents")
    command_skills = detect_command_skills(nwave / "skills")
    private_skills = load_private_skills(nwave, strict=False)

    def is_private(target: Path) -> bool:
        parts = target.parts
        if "skills" in parts:
            i = parts.index("skills")
            if i + 1 < len(parts):
                return not is_public_skill(
                    parts[i + 1],
                    public_agents,
                    ownership,
                    command_skills,
                    private_skills,
                )
        if "agents" in parts:
            return not is_public_agent(target.name, public_agents)
        # Other out-of-root targets (src/, README, ...) ship to the public repo.
        return False

    return is_private


def _network_reachable(timeout: float) -> bool:
    """A quick canary so an offline/airgapped run degrades gracefully."""
    return probe_url("https://github.com", min(timeout, 5.0)) not in (
        Category.NETWORK_ERROR,
        Category.TIMEOUT,
    )


@dataclass(frozen=True)
class LinkCheckRequest:
    """What kind of check to run, and how: flags plus the run mechanics."""

    check_external: bool
    check_site_links: bool
    network: bool
    ignore_path: Path | None = None
    timeout: float = 10.0
    workers: int = 8


def build_link_options(
    project_root: Path, *, request: LinkCheckRequest
) -> tuple[Options, list[Path]]:
    """Build Options + the ignore-file path excludes.

    Shared by run() (CLI) and the weekly reporter so ignore-file loading,
    published-root derivation, and privacy-predicate wiring live in one place.
    """
    ignore_path = request.ignore_path or project_root / DEFAULT_IGNORE_FILE
    excludes = [project_root / p for p in load_ignore_excludes(ignore_path)]
    site_roots: tuple[Path, ...] = ()
    site_private: Callable[[Path], bool] | None = None
    if request.check_site_links:
        site_private = _build_privacy_predicate(project_root)
        # Only enable site-escape checks when the catalog is available to tell
        # public from private. Without it, leave site_roots empty so no
        # site-escape findings fire (rather than flagging every escape) — but
        # say so, so the skipped check is visible rather than silent.
        if site_private is not None:
            site_roots = tuple(project_root / r for r in _published_roots())
        else:
            print(
                "\033[33mNOTICE\033[0m: agent catalog unavailable — skipping "
                "site-escape checks.",
                file=sys.stderr,
            )
    options = Options(
        check_external=request.check_external,
        check_site_links=request.check_site_links,
        network=request.network,
        allowlist=load_allowlist(ignore_path),
        external_org_urls=load_external_org_urls(ignore_path),
        site_roots=site_roots,
        site_private=site_private,
        timeout=request.timeout,
        workers=request.workers,
    )
    return options, excludes


def run(argv: Sequence[str], *, url_checker: UrlChecker | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(__file__).resolve().parent.parent
    ignore_path = (
        Path(args.ignore_file)
        if args.ignore_file
        else project_root / DEFAULT_IGNORE_FILE
    )

    network = not args.no_network
    # When a real probe is used, fail soft if the network is unreachable.
    if network and url_checker is None and not _network_reachable(args.timeout):
        print(
            "\033[33mNOTICE\033[0m: network unreachable — skipping liveness "
            "checks (structural + presence checks only).",
            file=sys.stderr,
        )
        network = False

    options, ignore_excludes = build_link_options(
        project_root,
        request=LinkCheckRequest(
            check_external=args.check_external,
            check_site_links=args.check_site_links,
            network=network,
            ignore_path=ignore_path,
            timeout=args.timeout,
            workers=args.workers,
        ),
    )

    raw_paths = args.paths or ["docs"]
    paths = [
        (project_root / p if not Path(p).is_absolute() else Path(p)) for p in raw_paths
    ]
    cli_excludes = [
        (project_root / d if not Path(d).is_absolute() else Path(d))
        for d in args.exclude_dir
    ]
    files = collect_files(paths, ignore_excludes + cli_excludes)

    checker = LinkChecker(project_root, options, url_checker=url_checker)
    findings = checker.check_files(files)

    print(render(findings, use_color=_use_color(args.no_color)))
    return compute_exit_code(findings, args.warnings_as_errors)


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
