"""Tests for scripts/check_docs_links.py.

Network is never touched: a stub ``url_checker`` is injected so the liveness
classification logic is exercised deterministically and offline. Structural
checks (relative links, the {{NWAVE_RAW_URL}} placeholder, anchors, exclusions)
run entirely against a temporary file tree.

This test is excluded from releases alongside the script it covers (the script
is not synced to the public mirror, so importing it would fail there).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_docs_links import (
    Category,
    LinkChecker,
    Options,
    Severity,
    classify_external,
    classify_org,
    compute_exit_code,
    github_owner,
    is_allowlisted,
    is_org_link,
    iter_links,
    load_allowlist,
    load_ignore_excludes,
    render,
    strip_fragment_and_query,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_checker(
    root: Path,
    *,
    statuses: dict[str, Category] | None = None,
    options: Options | None = None,
) -> LinkChecker:
    """Build a checker with a stub url_checker driven by ``statuses``."""
    table = statuses or {}

    def stub(url: str) -> Category:
        return table.get(url, Category.OK)

    return LinkChecker(root, options or Options(), url_checker=stub)


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_strip_fragment_and_query():
    assert strip_fragment_and_query("a.md#sec") == "a.md"
    assert strip_fragment_and_query("a.md?x=1") == "a.md"
    assert strip_fragment_and_query("a.md#sec?x=1") == "a.md"
    assert strip_fragment_and_query("#sec") == ""


@pytest.mark.parametrize(
    "url,owner",
    [
        ("https://github.com/nWave-ai/nWave/issues/1", "nwave-ai"),
        ("https://raw.githubusercontent.com/nWave-ai/nWave/main/x", "nwave-ai"),
        ("https://github.com/anthropics/claude-code", "anthropics"),
        ("https://example.com/foo", None),
        ("../relative/path.md", None),
    ],
)
def test_github_owner(url, owner):
    assert github_owner(url) == owner


def test_is_org_link():
    assert is_org_link("https://github.com/nWave-ai/nWave")
    assert not is_org_link("https://github.com/anthropics/claude-code")
    assert not is_org_link("https://example.com")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,severity",
    [
        (Category.OK, Severity.WARNING),  # presence warning only
        (Category.NOT_FOUND, Severity.WARNING),  # may be private
        (Category.UNAUTHORIZED, Severity.WARNING),
        (Category.TIMEOUT, Severity.WARNING),
        (Category.SERVER_ERROR, Severity.ERROR),
        (Category.NETWORK_ERROR, Severity.ERROR),
    ],
)
def test_classify_org(category, severity):
    assert classify_org(category)[0] is severity


@pytest.mark.parametrize(
    "category,expected",
    [
        (Category.OK, None),
        (Category.UNAUTHORIZED, Severity.WARNING),
        (Category.TIMEOUT, Severity.WARNING),
        (Category.NOT_FOUND, Severity.ERROR),
        (Category.SERVER_ERROR, Severity.ERROR),
        (Category.NETWORK_ERROR, Severity.ERROR),
    ],
)
def test_classify_external(category, expected):
    result = classify_external(category)
    if expected is None:
        assert result is None
    else:
        assert result is not None and result[0] is expected


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------


def test_iter_links_skips_inline_links_in_code_blocks():
    content = "See [x](a.md)\n```\n[y](b.md)\n```\n[z](c.md)\n"
    links = [link.value for link in iter_links(content) if link.kind == "link"]
    assert "a.md" in links
    assert "c.md" in links
    assert "b.md" not in links  # inside code fence


def test_iter_links_keeps_balanced_parentheses_in_url():
    # Regression: the URL stopped at the first ")", so this live Wikipedia page
    # was reported by the weekly job as the dead link ".../Hexagonal_architecture_(software".
    url = "https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)"
    content = f'See [hex]({url}), [t](a.md "title") (and [p](https://x.test/p))\n'
    links = [link.value for link in iter_links(content) if link.kind == "link"]
    assert links == [url, "a.md", "https://x.test/p"]


def test_iter_links_never_silently_drops_unbalanced_parentheses():
    # A URL the balanced form cannot parse must still be yielded (and so be
    # checked and flagged), never skipped without a finding.
    content = "[n](https://x.test/a_(b_(c)))\n[u](https://x.test/a_(b)\n"
    lines = [link.line for link in iter_links(content) if link.kind == "link"]
    assert lines == [1, 2]


def test_iter_links_placeholder_found_in_code_block():
    content = "```bash\ncurl -fsSL {{NWAVE_RAW_URL}}/scripts/install/install.sh\n```\n"
    placeholders = [
        link.value for link in iter_links(content) if link.kind == "placeholder"
    ]
    assert placeholders == ["/scripts/install/install.sh"]


def test_iter_links_placeholder_not_double_counted_in_markdown_link():
    content = "[setup]({{NWAVE_RAW_URL}}/docs/setup.py)\n"
    kinds = [link.kind for link in iter_links(content)]
    assert kinds == ["placeholder"]  # link scan skips placeholder-bearing urls


# ---------------------------------------------------------------------------
# Relative links
# ---------------------------------------------------------------------------


def test_relative_link_live(tmp_path):
    write(tmp_path / "docs" / "target.md", "# target")
    src = write(tmp_path / "docs" / "a.md", "[t](target.md)\n")
    findings = make_checker(tmp_path).check_files([src])
    assert findings == []


def test_relative_link_broken_is_error(tmp_path):
    src = write(tmp_path / "docs" / "a.md", "[t](missing.md)\n")
    findings = make_checker(tmp_path).check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR


def test_relative_link_to_directory_is_live(tmp_path):
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    src = write(tmp_path / "docs" / "a.md", "[d](sub)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_anchor_only_link_skipped(tmp_path):
    src = write(tmp_path / "docs" / "a.md", "[s](#section)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_fragment_stripped_before_resolving(tmp_path):
    write(tmp_path / "docs" / "target.md", "# t")
    src = write(tmp_path / "docs" / "a.md", "[t](target.md#heading)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_relative_link_escaping_docs_resolves(tmp_path):
    write(tmp_path / "src" / "mod.py", "x = 1")
    src = write(tmp_path / "docs" / "a.md", "[code](../src/mod.py)\n")
    assert make_checker(tmp_path).check_files([src]) == []


# ---------------------------------------------------------------------------
# Site-escape links (--check-site-links)
# ---------------------------------------------------------------------------


def _site_opts(root: Path, **kw) -> Options:
    return Options(check_site_links=True, site_roots=(root / "docs",), **kw)


def test_site_escape_off_by_default(tmp_path):
    # Target exists on disk but escapes docs/ — silent unless opted in.
    write(tmp_path / "nWave" / "skills" / "x" / "SKILL.md", "# s")
    src = write(tmp_path / "docs" / "a.md", "[s](../nWave/skills/x/SKILL.md)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_site_escape_flagged_when_enabled(tmp_path):
    write(tmp_path / "nWave" / "skills" / "x" / "SKILL.md", "# s")
    src = write(tmp_path / "docs" / "a.md", "[s](../nWave/skills/x/SKILL.md)\n")
    checker = make_checker(tmp_path, options=_site_opts(tmp_path))
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "outside the docs site root" in findings[0].message


def test_site_internal_link_not_flagged(tmp_path):
    write(tmp_path / "docs" / "sub" / "b.md", "# b")
    src = write(tmp_path / "docs" / "a.md", "[b](sub/b.md)\n")
    assert make_checker(tmp_path, options=_site_opts(tmp_path)).check_files([src]) == []


def test_site_escape_only_applies_under_docs(tmp_path):
    # A non-docs source file (e.g. README) escaping is not a site concern.
    write(tmp_path / "src" / "m.py", "x=1")
    src = write(tmp_path / "README.md", "[m](src/m.py)\n")
    assert make_checker(tmp_path, options=_site_opts(tmp_path)).check_files([src]) == []


def test_site_escape_predicate_passes_public_targets(tmp_path):
    # With a privacy predicate, a public out-of-root target is NOT flagged
    # (build_site rewrites it to a resolving GitHub URL).
    write(tmp_path / "nWave" / "skills" / "pub" / "SKILL.md", "# s")
    src = write(tmp_path / "docs" / "a.md", "[s](../nWave/skills/pub/SKILL.md)\n")
    opts = _site_opts(tmp_path, site_private=lambda t: "priv" in t.parts)
    assert make_checker(tmp_path, options=opts).check_files([src]) == []


def test_site_escape_predicate_flags_private_targets(tmp_path):
    write(tmp_path / "nWave" / "skills" / "priv" / "SKILL.md", "# s")
    src = write(tmp_path / "docs" / "a.md", "[s](../nWave/skills/priv/SKILL.md)\n")
    opts = _site_opts(tmp_path, site_private=lambda t: "priv" in t.parts)
    findings = make_checker(tmp_path, options=opts).check_files([src])
    assert len(findings) == 1 and findings[0].severity is Severity.ERROR


def test_site_escape_skips_private_source_page(tmp_path):
    # A private source page is stripped from the public site, so its private
    # link can't 404 publicly — no finding.
    write(tmp_path / "nWave" / "skills" / "priv" / "SKILL.md", "# s")
    src = write(
        tmp_path / "docs" / "priv-page.md", "[s](../nWave/skills/priv/SKILL.md)\n"
    )
    opts = _site_opts(tmp_path, site_private=lambda t: "priv" in str(t))
    assert make_checker(tmp_path, options=opts).check_files([src]) == []


# ---------------------------------------------------------------------------
# Placeholder links (repo-root-relative)
# ---------------------------------------------------------------------------


def test_placeholder_valid_path(tmp_path):
    write(tmp_path / "scripts" / "install" / "install.sh", "#!/bin/sh")
    src = write(
        tmp_path / "docs" / "a.md",
        "```\ncurl {{NWAVE_RAW_URL}}/scripts/install/install.sh\n```\n",
    )
    assert make_checker(tmp_path).check_files([src]) == []


def test_placeholder_missing_path_is_error(tmp_path):
    src = write(
        tmp_path / "docs" / "a.md",
        "```\ncurl {{NWAVE_RAW_URL}}/scripts/nope.sh\n```\n",
    )
    findings = make_checker(tmp_path).check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "repo root" in findings[0].message


def test_bare_placeholder_no_path_skipped(tmp_path):
    src = write(tmp_path / "docs" / "a.md", "The {{NWAVE_RAW_URL}} expands.\n")
    assert make_checker(tmp_path).check_files([src]) == []


# ---------------------------------------------------------------------------
# Org links
# ---------------------------------------------------------------------------


def test_org_link_presence_warning_without_network(tmp_path):
    src = write(tmp_path / "docs" / "a.md", "[r](https://github.com/nWave-ai/nWave)\n")
    checker = make_checker(tmp_path, options=Options(network=False))
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_org_link_404_is_warning(tmp_path):
    url = "https://github.com/nWave-ai/secret"
    src = write(tmp_path / "docs" / "a.md", f"[r]({url})\n")
    checker = make_checker(tmp_path, statuses={url: Category.NOT_FOUND})
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_org_link_server_error_is_error(tmp_path):
    url = "https://github.com/nWave-ai/nWave"
    src = write(tmp_path / "docs" / "a.md", f"[r]({url})\n")
    checker = make_checker(tmp_path, statuses={url: Category.SERVER_ERROR})
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR


def test_org_link_allowlisted_is_silent(tmp_path):
    url = "https://github.com/nWave-ai/nwave-dev"
    src = write(tmp_path / "docs" / "a.md", f"[r]({url})\n")
    checker = make_checker(
        tmp_path,
        statuses={url: Category.NOT_FOUND},
        options=Options(allowlist=["nwave-ai/nwave-dev"]),
    )
    assert checker.check_files([src]) == []


def test_org_link_listed_as_external_has_no_nudge_when_live(tmp_path):
    # nWave-ai links that cannot be relative (another repo, an issue tracker, a CI
    # run) are listed in external_org_urls: no "prefer relative" nudge when live.
    url = "https://github.com/nWave-ai/nWave/issues/31"
    src = write(tmp_path / "docs" / "a.md", f"[i]({url})\n")
    checker = make_checker(
        tmp_path,
        statuses={url: Category.OK},
        options=Options(external_org_urls=["nwave-ai/nwave/issues"]),
    )
    assert checker.check_files([src]) == []


def test_org_link_listed_as_external_is_still_checked(tmp_path):
    dead = "https://github.com/nWave-ai/nwave-dedup/blob/main/gone.md"
    down = "https://github.com/nWave-ai/nwave-dedup"
    src = write(tmp_path / "docs" / "a.md", f"[d]({dead})\n[u]({down})\n")
    checker = make_checker(
        tmp_path,
        statuses={dead: Category.NOT_FOUND, down: Category.SERVER_ERROR},
        options=Options(external_org_urls=["nwave-ai/nwave-dedup"]),
    )
    findings = checker.check_files([src])
    assert [f.severity for f in findings] == [Severity.WARNING, Severity.ERROR]
    assert all("prefer a relative repo link" not in f.message for f in findings)


def test_org_link_listed_as_external_is_silent_offline(tmp_path):
    url = "https://github.com/nWave-ai/nWave/issues"
    src = write(tmp_path / "docs" / "a.md", f"[i]({url})\n")
    checker = make_checker(
        tmp_path,
        options=Options(network=False, external_org_urls=["nwave-ai/nwave/issues"]),
    )
    assert checker.check_files([src]) == []


def test_load_external_org_urls(tmp_path):
    from scripts.check_docs_links import load_external_org_urls

    f = write(
        tmp_path / "ig.yaml",
        "ignore_urls:\n  - nWave-ai/private\n"
        "external_org_urls:\n  - nWave-ai/nWave/issues\n",
    )
    assert load_external_org_urls(f) == ["nwave-ai/nwave/issues"]
    assert load_allowlist(f) == ["nwave-ai/private"]


# ---------------------------------------------------------------------------
# External links
# ---------------------------------------------------------------------------


def test_external_link_skipped_without_flag(tmp_path):
    url = "https://example.com/dead"
    src = write(tmp_path / "docs" / "a.md", f"[e]({url})\n")
    checker = make_checker(tmp_path, statuses={url: Category.NOT_FOUND})
    assert checker.check_files([src]) == []


def test_external_404_is_error_with_flag(tmp_path):
    url = "https://example.com/dead"
    src = write(tmp_path / "docs" / "a.md", f"[e]({url})\n")
    checker = make_checker(
        tmp_path,
        statuses={url: Category.NOT_FOUND},
        options=Options(check_external=True),
    )
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR


def test_external_403_is_warning_with_flag(tmp_path):
    url = "https://paywalled.example.com/article"
    src = write(tmp_path / "docs" / "a.md", f"[e]({url})\n")
    checker = make_checker(
        tmp_path,
        statuses={url: Category.UNAUTHORIZED},
        options=Options(check_external=True),
    )
    findings = checker.check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def _fake_urlopen(head_status: int, get_status: int):
    """Stub urlopen: HEAD and GET answer with the given statuses."""
    import urllib.error

    class _Resp:
        def __init__(self, status: int) -> None:
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake(req, timeout):
        status = head_status if req.get_method() == "HEAD" else get_status
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "stub", {}, None)
        return _Resp(status)

    return fake


def test_probe_falls_back_to_get_when_head_is_404(monkeypatch):
    # Regression: dynatrace.com, dev.doroshev.com and marketplace.visualstudio.com
    # answer HEAD with 404 but GET with 200, so live pages were reported dead.
    from scripts.check_docs_links import probe_url

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(404, 200))
    assert probe_url("https://example.com/live", 1.0) is Category.OK


def test_probe_get_404_after_head_404_stays_not_found(monkeypatch):
    from scripts.check_docs_links import probe_url

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(404, 404))
    assert probe_url("https://example.com/dead", 1.0) is Category.NOT_FOUND


def test_probe_retries_once_after_a_network_error(monkeypatch):
    # Regression: CI run 34961358307 went red on one transient network_error for a
    # live page (www.methodsandtools.com), so a single blip read as a dead link.
    import urllib.error

    from scripts.check_docs_links import probe_url

    ok = _fake_urlopen(200, 200)
    calls = []

    def flaky(req, timeout):
        calls.append(req.get_method())
        if len(calls) == 1:
            raise urllib.error.URLError(ConnectionResetError("reset by peer"))
        return ok(req, timeout)

    monkeypatch.setattr("urllib.request.urlopen", flaky)
    assert probe_url("https://example.com/live", 1.0) is Category.OK


def test_probe_network_error_on_both_attempts_stays_network_error(monkeypatch):
    import urllib.error

    from scripts.check_docs_links import probe_url

    calls = []

    def down(req, timeout):
        calls.append(req.get_method())
        raise urllib.error.URLError(OSError("Name or service not known"))

    monkeypatch.setattr("urllib.request.urlopen", down)
    assert probe_url("https://dead.example.com/", 1.0) is Category.NETWORK_ERROR
    assert calls == ["HEAD", "HEAD"]


# ---------------------------------------------------------------------------
# Medium links: Medium blocks automated page loads, so existence is checked
# through /p/<post id> and, when that is blocked too, the author or publication
# feed.
# ---------------------------------------------------------------------------

POST = "https://medium.com/@user/a-good-read-979c2c7e40b1"


def _medium_checker(root, probe, options=None):
    return LinkChecker(
        root,
        options or Options(check_external=True),
        url_checker=lambda url: Category.OK,
        medium_checker=lambda ref: probe,
    )


def test_is_medium_link_matches_medium_hosts_only():
    from scripts.check_docs_links import is_medium_link

    assert is_medium_link(POST)
    assert is_medium_link("https://kim.medium.com/a-read-48c860070f87")
    assert not is_medium_link("https://notmedium.com/a-read-48c860070f87")
    assert not is_medium_link("https://medium.com.example.org/a-read-48c860070f87")


def test_parse_medium_url_accepts_the_three_post_shapes():
    from scripts.check_docs_links import parse_medium_url

    author = parse_medium_url(POST + "?source=rss")
    assert author.post_id == "979c2c7e40b1"
    assert author.feed_url == "https://medium.com/feed/@user"
    publication = parse_medium_url("https://medium.com/some-pub/a-read-a6d814b9bf56")
    assert publication.feed_url == "https://medium.com/feed/some-pub"
    sub = parse_medium_url("https://kim.medium.com/a-read-48c860070f87")
    assert sub.post_id == "48c860070f87"
    assert sub.feed_url == "https://kim.medium.com/feed"


def test_parse_medium_url_rejects_urls_without_a_post_id():
    from scripts.check_docs_links import parse_medium_url

    for url in (
        "https://medium.com/@user",
        "https://medium.com/@user/a-read-without-an-id",
        "https://kim.medium.com/",
    ):
        assert parse_medium_url(url) is None


def test_medium_post_found_at_the_cited_url_is_silent(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(post="exists", canonical=POST)
    assert _medium_checker(tmp_path, probe).check_files([src]) == []


def test_medium_post_moved_is_a_warning_naming_the_canonical_url(tmp_path):
    from scripts.check_docs_links import MediumProbe

    moved = "https://medium.com/new-pub/a-good-read-979c2c7e40b1"
    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(post="exists", canonical=moved)
    findings = _medium_checker(tmp_path, probe).check_files([src])
    assert [f.severity for f in findings] == [Severity.WARNING]
    assert moved in findings[0].message


def test_medium_post_not_found_is_an_error(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    findings = _medium_checker(tmp_path, MediumProbe(post="gone")).check_files([src])
    assert [f.severity for f in findings] == [Severity.ERROR]


def test_medium_blocked_but_feed_found_is_silent(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(post="blocked", feed=Category.OK)
    assert _medium_checker(tmp_path, probe).check_files([src]) == []


def test_medium_blocked_and_feed_not_found_is_an_error(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(post="blocked", feed=Category.NOT_FOUND)
    findings = _medium_checker(tmp_path, probe).check_files([src])
    assert [f.severity for f in findings] == [Severity.ERROR]


def test_medium_blocked_everywhere_is_a_warning(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(post="blocked", feed=Category.UNAUTHORIZED)
    findings = _medium_checker(tmp_path, probe).check_files([src])
    assert [f.severity for f in findings] == [Severity.WARNING]


def test_medium_url_without_a_post_id_is_an_error_even_offline(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", "[m](https://medium.com/@user/no-id)\n")
    checker = _medium_checker(
        tmp_path,
        MediumProbe(post="exists"),
        Options(check_external=True, network=False),
    )
    findings = checker.check_files([src])
    assert [f.severity for f in findings] == [Severity.ERROR]


def test_probe_medium_reads_the_post_redirect_without_loading_the_page(monkeypatch):
    import scripts.check_docs_links as cdl

    ref = cdl.parse_medium_url(POST)
    monkeypatch.setattr(cdl, "_status_without_redirect", lambda url, t: (302, POST))
    expected = cdl.MediumProbe(post="exists", canonical=POST)
    assert cdl.probe_medium(ref, 1.0) == expected
    monkeypatch.setattr(cdl, "_status_without_redirect", lambda url, t: (404, ""))
    assert cdl.probe_medium(ref, 1.0).post == "gone"


def test_probe_medium_falls_back_to_the_feed_when_blocked(monkeypatch):
    import scripts.check_docs_links as cdl

    ref = cdl.parse_medium_url(POST)
    seen = []

    def feed_probe(url, timeout):
        seen.append(url)
        return Category.OK

    monkeypatch.setattr(cdl, "_status_without_redirect", lambda url, t: (403, ""))
    monkeypatch.setattr(cdl, "probe_url", feed_probe)
    expected = cdl.MediumProbe(post="blocked", feed=Category.OK, detail="HTTP 403")
    assert cdl.probe_medium(ref, 1.0) == expected
    assert seen == ["https://medium.com/feed/@user"]
    monkeypatch.setattr(cdl, "_status_without_redirect", lambda url, t: (None, ""))
    assert cdl.probe_medium(ref, 1.0).detail == "no response"


# ---------------------------------------------------------------------------
# Substack links: handled like Medium. The post API answers 404 for a missing
# post, and the publication feed stands in when that is blocked too.
# ---------------------------------------------------------------------------

SUBSTACK_POST = "https://author.substack.com/p/a-good-read"


def _substack_checker(root, probe, options=None):
    return LinkChecker(
        root,
        options or Options(check_external=True),
        url_checker=lambda url: Category.OK,
        substack_checker=lambda ref: probe,
    )


def test_is_substack_link_matches_substack_hosts_only():
    from scripts.check_docs_links import is_substack_link

    assert is_substack_link(SUBSTACK_POST)
    assert not is_substack_link("https://notsubstack.com/p/a-good-read")
    assert not is_substack_link("https://substack.com.example.org/p/a-good-read")


def test_parse_substack_url_accepts_posts_only():
    from scripts.check_docs_links import parse_substack_url

    ref = parse_substack_url(SUBSTACK_POST + "?utm_source=x")
    assert ref.slug == "a-good-read"
    assert ref.api_url == "https://author.substack.com/api/v1/posts/a-good-read"
    assert ref.feed_url == "https://author.substack.com/feed"
    for url in (
        "https://author.substack.com/",
        "https://author.substack.com/archive",
        "https://author.substack.com/p/",
    ):
        assert parse_substack_url(url) is None


@pytest.mark.parametrize(
    ("probe", "expected"),
    [
        ({"post": "exists", "canonical": SUBSTACK_POST}, []),
        (
            {"post": "exists", "canonical": "https://author.substack.com/p/renamed"},
            [Severity.WARNING],
        ),
        ({"post": "gone"}, [Severity.ERROR]),
        ({"post": "blocked", "feed": Category.OK}, []),
        ({"post": "blocked", "feed": Category.NOT_FOUND}, [Severity.ERROR]),
        ({"post": "blocked", "feed": Category.UNAUTHORIZED}, [Severity.WARNING]),
    ],
)
def test_substack_findings_follow_the_medium_rules(tmp_path, probe, expected):
    from scripts.check_docs_links import PostProbe

    src = write(tmp_path / "docs" / "a.md", f"[s]({SUBSTACK_POST})\n")
    checker = _substack_checker(tmp_path, PostProbe(**probe))
    assert [f.severity for f in checker.check_files([src])] == expected


def test_substack_url_that_is_not_a_post_is_an_error_even_offline(tmp_path):
    from scripts.check_docs_links import PostProbe

    link = "[s](https://author.substack.com/archive)\n"
    src = write(tmp_path / "docs" / "a.md", link)
    checker = _substack_checker(
        tmp_path,
        PostProbe(post="exists"),
        Options(check_external=True, network=False),
    )
    assert [f.severity for f in checker.check_files([src])] == [Severity.ERROR]


def test_probe_substack_reads_the_post_api_then_the_feed(monkeypatch):
    import scripts.check_docs_links as cdl

    def post(result):
        return lambda url, timeout: result

    ref = cdl.parse_substack_url(SUBSTACK_POST)
    found = (Category.OK, SUBSTACK_POST, "HTTP 200")
    monkeypatch.setattr(cdl, "_substack_post", post(found))
    assert cdl.probe_substack(ref, 1.0) == cdl.PostProbe("exists", SUBSTACK_POST)
    gone = (Category.NOT_FOUND, "", "HTTP 404")
    monkeypatch.setattr(cdl, "_substack_post", post(gone))
    assert cdl.probe_substack(ref, 1.0).post == "gone"
    seen = []

    def feed_probe(url, timeout):
        seen.append(url)
        return Category.OK

    blocked = (Category.UNAUTHORIZED, "", "HTTP 403")
    monkeypatch.setattr(cdl, "_substack_post", post(blocked))
    monkeypatch.setattr(cdl, "probe_url", feed_probe)
    expected = cdl.PostProbe(
        "blocked", feed=Category.OK, detail="HTTP 403", refused=True
    )
    assert cdl.probe_substack(ref, 1.0) == expected
    assert seen == ["https://author.substack.com/feed"]
    timed_out = (Category.TIMEOUT, "", "timeout")
    monkeypatch.setattr(cdl, "_substack_post", post(timed_out))
    assert cdl.probe_substack(ref, 1.0).refused is False


def test_substack_post_check_needs_json_to_count_as_found(monkeypatch):
    # A blocked script can get a 200 challenge page; only the post's JSON counts.
    import io
    import json

    import scripts.check_docs_links as cdl

    class _Resp(io.BytesIO):
        status = 200

    def answer(body):
        return lambda req, timeout: _Resp(body)

    api = "https://author.substack.com/api/v1/posts/a-good-read"
    found = json.dumps({"slug": "a-good-read", "canonical_url": SUBSTACK_POST}).encode()
    monkeypatch.setattr("urllib.request.urlopen", answer(found))
    assert cdl._substack_post(api, 1.0)[:2] == (Category.OK, SUBSTACK_POST)
    monkeypatch.setattr("urllib.request.urlopen", answer(b"<html>challenge</html>"))
    category, _, detail = cdl._substack_post(api, 1.0)
    assert category is Category.UNAUTHORIZED
    assert detail == "HTTP 200 without the post's JSON"


def test_substack_post_check_reports_what_it_got(monkeypatch):
    import urllib.error

    import scripts.check_docs_links as cdl

    def refuse(code):
        def fake(req, timeout):
            raise urllib.error.HTTPError(req.full_url, code, "stub", {}, None)

        return fake

    api = "https://author.substack.com/api/v1/posts/a-good-read"
    monkeypatch.setattr("urllib.request.urlopen", refuse(403))
    assert cdl._substack_post(api, 1.0) == (Category.UNAUTHORIZED, "", "HTTP 403")

    def time_out(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", time_out)
    category, _, detail = cdl._substack_post(api, 1.0)
    assert (category, detail) == (Category.TIMEOUT, "timeout")


def test_blocked_everywhere_warning_names_what_each_check_got():
    # Both checks blocked is a WARNING; the message says what each check got back,
    # so a runner that is refused can be told apart from one that times out.
    from scripts.check_docs_links import PostContext, PostProbe, classify_post

    probe = PostProbe("blocked", feed=Category.TIMEOUT, detail="HTTP 403")
    severity, message = classify_post(
        SUBSTACK_POST,
        probe,
        PostContext("Substack", "slug a-good-read", "https://a/feed"),
    )
    assert severity is Severity.WARNING
    assert "post check: HTTP 403" in message
    assert "feed check: timeout" in message


def test_substack_refused_by_both_checks_is_silent(tmp_path):
    # GitHub's runner gets HTTP 403 from Substack's post API and a refused feed on
    # every run (run 34988132512), whether or not the post exists, so a refusal of
    # both checks is not reported for a valid Substack post URL.
    from scripts.check_docs_links import PostProbe

    src = write(tmp_path / "docs" / "a.md", f"[s]({SUBSTACK_POST})\n")
    probe = PostProbe(
        "blocked", feed=Category.UNAUTHORIZED, detail="HTTP 403", refused=True
    )
    assert _substack_checker(tmp_path, probe).check_files([src]) == []


@pytest.mark.parametrize(
    "probe",
    [
        {"detail": "timeout", "refused": False, "feed": Category.UNAUTHORIZED},
        {"detail": "no response", "refused": False, "feed": Category.UNAUTHORIZED},
        {"detail": "HTTP 403", "refused": True, "feed": Category.TIMEOUT},
    ],
)
def test_substack_blocked_without_a_clear_refusal_still_warns(tmp_path, probe):
    from scripts.check_docs_links import PostProbe

    src = write(tmp_path / "docs" / "a.md", f"[s]({SUBSTACK_POST})\n")
    checker = _substack_checker(tmp_path, PostProbe("blocked", **probe))
    assert [f.severity for f in checker.check_files([src])] == [Severity.WARNING]


def test_medium_refused_by_both_checks_still_warns(tmp_path):
    from scripts.check_docs_links import MediumProbe

    src = write(tmp_path / "docs" / "a.md", f"[m]({POST})\n")
    probe = MediumProbe(
        "blocked", feed=Category.UNAUTHORIZED, detail="HTTP 403", refused=True
    )
    findings = _medium_checker(tmp_path, probe).check_files([src])
    assert [f.severity for f in findings] == [Severity.WARNING]


def test_mailto_scheme_skipped(tmp_path):
    src = write(tmp_path / "docs" / "a.md", "[m](mailto:x@example.com)\n")
    checker = make_checker(tmp_path, options=Options(check_external=True))
    assert checker.check_files([src]) == []


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def _f(sev: Severity) -> object:
    from scripts.check_docs_links import Finding

    return Finding(sev, "a.md", 1, "x", "msg")


def test_exit_code_error_is_one():
    assert compute_exit_code([_f(Severity.ERROR)], warnings_as_errors=False) == 1


def test_exit_code_warning_only_is_zero():
    assert compute_exit_code([_f(Severity.WARNING)], warnings_as_errors=False) == 0


def test_exit_code_warning_with_strict_is_one():
    assert compute_exit_code([_f(Severity.WARNING)], warnings_as_errors=True) == 1


def test_exit_code_clean_is_zero():
    assert compute_exit_code([], warnings_as_errors=True) == 0


# ---------------------------------------------------------------------------
# Allowlist loading + exclusions + rendering
# ---------------------------------------------------------------------------


_IGNORE_YAML = (
    "ignore_urls:\n  - nWave-ai/Private\n  - nWave-ai/Other\n"
    "ignore_paths:\n  - docs/research\n  - docs/archive\n"
)


def test_load_allowlist(tmp_path):
    f = write(tmp_path / "ig.yaml", _IGNORE_YAML)
    assert load_allowlist(f) == ["nwave-ai/private", "nwave-ai/other"]


def test_load_allowlist_missing_file(tmp_path):
    assert load_allowlist(tmp_path / "nope.yaml") == []


def test_load_ignore_excludes(tmp_path):
    f = write(tmp_path / "ig.yaml", _IGNORE_YAML)
    assert load_ignore_excludes(f) == ["docs/research", "docs/archive"]


def test_ignore_config_handles_missing_and_partial(tmp_path):
    from scripts.check_docs_links import load_ignore_config

    # Missing file -> every key present, empty.
    assert load_ignore_config(tmp_path / "nope.yaml") == {
        "ignore_urls": [],
        "ignore_paths": [],
        "external_org_urls": [],
    }
    # Only one key present -> the other defaults to empty.
    f = write(tmp_path / "partial.yaml", "ignore_paths:\n  - docs/x\n")
    assert load_allowlist(f) == []
    assert load_ignore_excludes(f) == ["docs/x"]


def test_ignore_config_degrades_on_unrecognized_content(tmp_path):
    from scripts.check_docs_links import load_ignore_config

    empty = {"ignore_urls": [], "ignore_paths": [], "external_org_urls": []}
    # Top-level list (no recognized keys) -> every key present, empty.
    assert load_ignore_config(write(tmp_path / "list.yaml", "- a\n- b\n")) == empty
    # Free text / unknown keys -> empty, never crashes.
    assert (
        load_ignore_config(write(tmp_path / "junk.yaml", "hello\nother: x\n")) == empty
    )


def test_ignore_config_ignores_unknown_keys(tmp_path):
    # An unknown key's list items must not leak into either ignore list.
    f = write(tmp_path / "x.yaml", "other:\n  - a\nignore_paths:\n  - docs/x\n")
    assert load_ignore_excludes(f) == ["docs/x"]
    assert load_allowlist(f) == []


def test_ignore_config_accepts_scalar_value(tmp_path):
    # A bare scalar (missing the YAML list dash) is taken as a single entry,
    # not silently dropped nor iterated char-by-char.
    f = write(tmp_path / "scalar.yaml", "ignore_urls: nWave-ai/Solo\n")
    assert load_allowlist(f) == ["nwave-ai/solo"]


def test_guide_folder_without_readme_is_error(tmp_path):
    (tmp_path / "docs" / "guides" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "guides" / "sub" / "notes.md").write_text("x")
    src = write(tmp_path / "docs" / "guides" / "a.md", "[s](sub)\n")
    findings = make_checker(tmp_path).check_files([src])
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "README.md" in findings[0].message


def test_guide_folder_with_readme_ok(tmp_path):
    (tmp_path / "docs" / "guides" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "guides" / "sub" / "README.md").write_text("# x")
    src = write(tmp_path / "docs" / "guides" / "a.md", "[s](sub)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_non_guide_folder_without_readme_ok(tmp_path):
    # The README convention applies only under docs/guides/.
    (tmp_path / "docs" / "reference" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "reference" / "sub" / "x.md").write_text("x")
    src = write(tmp_path / "docs" / "reference" / "a.md", "[s](sub)\n")
    assert make_checker(tmp_path).check_files([src]) == []


def test_is_allowlisted_substring_case_insensitive():
    assert is_allowlisted(
        "https://github.com/nWave-ai/nwave-dev/blob/x", ["nwave-ai/nwave-dev"]
    )
    assert not is_allowlisted("https://github.com/nWave-ai/nWave", ["nwave-dev"])


def test_exclude_dir(tmp_path):
    write(tmp_path / "docs" / "keep" / "a.md", "[t](missing.md)\n")
    write(tmp_path / "docs" / "skip" / "b.md", "[t](missing.md)\n")
    from scripts.check_docs_links import collect_files

    files = collect_files([tmp_path / "docs"], [tmp_path / "docs" / "skip"])
    names = {p.name for p in files}
    assert names == {"a.md"}


def test_render_contains_severity_and_link():
    out = render([_f(Severity.ERROR)], use_color=False)
    assert "ERROR" in out and "1 error(s)" in out
