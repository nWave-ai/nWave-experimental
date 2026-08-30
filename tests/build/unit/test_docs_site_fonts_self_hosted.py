"""The documentation site must serve its webfonts from its own origin.

Production (https://nwave.ai) self-hosts Lato and Quattrocento as woff2 files
under ``/fonts/``. The docs site must do the same: a page that reaches out to
Google Fonts (or any third-party font CDN) diverges from production rendering
and leaks a request to a third party on every page view (PRIVACY.md).

The check is a census, not a spot check: it walks EVERY served asset of the
site source and fails on the first external font host found anywhere. Half a
conversion is worse than none -- the site would then load from two mechanisms.
"""

from __future__ import annotations

import re
from pathlib import Path


DOCS_SITE = Path(__file__).resolve().parents[3] / "scripts" / "docs_site"

# Hosts that serve webfonts to a browser. Any of these appearing in a served
# asset means the rendered page depends on a third-party origin for its type.
EXTERNAL_FONT_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "fonts.bunny.net",
    "use.typekit.net",
    "fast.fonts.net",
    "cdn.jsdelivr.net/npm/@fontsource",
    "use.fontawesome.com",
    "cdnjs.cloudflare.com/ajax/libs/font",
)

# Every file kind that can reach the browser: markup, styles, scripts, and the
# generator itself (it emits inline HTML documents, e.g. the root redirect).
_SERVED_SUFFIXES = {".html", ".css", ".js", ".py", ".svg", ".json", ".md", ".yaml"}

_SELF_HOSTED_FACES = {
    "fonts/lato-v24-latin-regular.woff2": ("Lato", "400"),
    "fonts/lato-v24-latin-700.woff2": ("Lato", "700"),
    "fonts/quattrocento-v18-latin-700.woff2": ("Quattrocento", "700"),
}


def _served_files() -> list[Path]:
    return sorted(
        p
        for p in DOCS_SITE.rglob("*")
        if p.is_file() and p.suffix in _SERVED_SUFFIXES and "__pycache__" not in p.parts
    )


def test_no_served_asset_references_an_external_font_host() -> None:
    offenders: list[str] = []
    for path in _served_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for host in EXTERNAL_FONT_HOSTS:
                if host in line:
                    rel = path.relative_to(DOCS_SITE.parent.parent)
                    offenders.append(f"{rel}:{lineno}: {host}")
    assert not offenders, (
        "WHAT: the docs site loads webfonts from a third-party origin.\n"
        "WHY: production (https://nwave.ai) self-hosts Lato + Quattrocento "
        "under /fonts/; an external font host changes rendering fidelity and "
        "leaks a per-page-view request to a third party.\n"
        "HOW: delete the external <link>/@import and declare the face with "
        "@font-face pointing at scripts/docs_site/static/fonts/*.woff2.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_every_declared_face_is_self_hosted_and_present() -> None:
    css = (DOCS_SITE / "static" / "styles.css").read_text(encoding="utf-8")
    blocks = re.findall(r"@font-face\s*\{[^}]*\}", css)
    assert blocks, "styles.css declares no @font-face: the fonts are not self-hosted."

    declared: dict[str, tuple[str, str]] = {}
    for block in blocks:
        family = re.search(r"font-family:\s*[\"']?([A-Za-z ]+)[\"']?\s*;", block)
        weight = re.search(r"font-weight:\s*(\d+)", block)
        src = re.search(r"url\(\s*[\"']?([^\"')]+)", block)
        assert family and weight and src, f"incomplete @font-face block: {block}"
        url = src.group(1)
        assert not url.startswith(("http://", "https://", "//")), (
            f"@font-face src must be a same-origin path, got: {url}"
        )
        declared[url.lstrip("/").removeprefix("static/")] = (
            family.group(1).strip(),
            weight.group(1),
        )

    assert declared == _SELF_HOSTED_FACES, (
        "The self-hosted face set must match production exactly "
        f"(observed at https://nwave.ai/assets/*.css).\nexpected: "
        f"{_SELF_HOSTED_FACES}\ndeclared: {declared}"
    )

    for rel in _SELF_HOSTED_FACES:
        blob = DOCS_SITE / "static" / rel
        assert blob.is_file(), f"declared but missing font file: {blob}"
        assert blob.read_bytes()[:4] == b"wOF2", f"not a woff2 file: {blob}"
