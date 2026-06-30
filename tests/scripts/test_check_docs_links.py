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

    # Missing file -> both keys present, empty.
    assert load_ignore_config(tmp_path / "nope.yaml") == {
        "ignore_urls": [],
        "ignore_paths": [],
    }
    # Only one key present -> the other defaults to empty.
    f = write(tmp_path / "partial.yaml", "ignore_paths:\n  - docs/x\n")
    assert load_allowlist(f) == []
    assert load_ignore_excludes(f) == ["docs/x"]


def test_ignore_config_degrades_on_unrecognized_content(tmp_path):
    from scripts.check_docs_links import load_ignore_config

    empty = {"ignore_urls": [], "ignore_paths": []}
    # Top-level list (no recognized keys) -> both keys present, empty.
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
