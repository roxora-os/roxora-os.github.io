#!/usr/bin/env python3
# Copyright (C) 2026 Jiaxing Hu <gahing@gahingwoo.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by the
# Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, see <https://www.gnu.org/licenses/>.
"""Render the site into _site/.

Some pages are fragments in content/<slug>.html holding cards; the rest are
generated from what tools/fetch_upstream.py put in cache/upstream/: the
release catalogs (Download, the Raspberry Pi Imager file), boards.conf
(Boards) and docs/*.md of roxora-os/build (Docs). Each is wrapped in the shell
every page shares (PatternFly's page, masthead, sidebar and the "on this
page" rail) and written as <dir>/index.html. The rail is built from the cards
themselves, so a card added to a fragment appears in it without anything else
being edited.

    python3 tools/fetch_upstream.py
    python3 tools/build.py

Writes _site/: the pages, 404.html, os_list.json, sitemap.xml, robots.txt and
a copy of assets/. Needs the markdown package (pip install markdown).

A build from sample release data (a catalog carrying "_sample", which
fetch_upstream.py --sample produces) goes to output/sample-site/ instead and
never to _site/, which is what the workflow deploys.

Adapted from mabc-ws's build script; the shell is the one gahingwoo.com and
mabc-ws run. The brand files in assets/brand/ are copies from roxora-os/design.
"""

import hashlib
import html
import json
import pathlib
import posixpath
import re
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import os_list  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
UPSTREAM = ROOT / "cache" / "upstream"

SITE = "https://roxora-os.github.io"
NAME = "Roxora"
EMAIL = "oss@gahingwoo.com"
BUILD_REPO = "https://github.com/roxora-os/build"
SOURCE = "https://github.com/roxora-os/roxora-os.github.io"
AUTHOR = "Ga Hing Woo"
AUTHOR_CODE = "https://github.com/gahingwoo"
OS_LIST_URL = SITE + "/os_list.json"

# Ubuntu codenames the boards can name, with their version numbers. A codename
# missing here is shown as it is.
UBUNTU = {"jammy": ("22.04", True), "noble": ("24.04", True),
          "plucky": ("25.04", False), "questing": ("25.10", False),
          "resolute": ("26.04", True)}

# Sidebar navigation. Section title, then (label, href) per item.
NAV = [
    ("Roxora", [
        ("Home", "/"),
        ("Download", "/download/"),
        ("Boards", "/boards/"),
        ("Raspberry Pi Imager", "/rpi-imager/"),
    ]),
    ("Documentation", [
        ("Docs", "/docs/"),
        ("FAQ", "/faq/"),
    ]),
    ("Project", [
        ("About", "/about/"),
        ("Source code", BUILD_REPO),
    ]),
]

CARET = ('<svg class="pf-v6-svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" '
         'role="img" width="1em" height="1em"><path d="M18.71 5.29a.996.996 0 0 0-1.41 0l-7.29 '
         '7.29-7.3-7.29a.987.987 0 0 0-1.41-.02.987.987 0 0 0-.02 1.41l.02.02 7.65 7.65c.29.29.68.44 '
         '1.06.44s.77-.15 1.06-.44l7.65-7.65a.996.996 0 0 0 0-1.41Z"/></svg>')

esc = html.escape


# ---- small pieces of markup ----

def kv(rows):
    """Key/value rows, as Cockpit lays out system information. Values are
    finished HTML; callers escape what they put in."""
    return ('<dl class="pf-v6-c-description-list pf-m-horizontal-on-sm kv">\n' + "\n".join(
        '<div class="pf-v6-c-description-list__group">'
        '<dt class="pf-v6-c-description-list__term">'
        '<span class="pf-v6-c-description-list__text">%s</span></dt>'
        '<dd class="pf-v6-c-description-list__description">'
        '<div class="pf-v6-c-description-list__text">%s</div></dd></div>'
        % (esc(term), value) for term, value in rows) + "\n</dl>")


def card(cid, title, body, rail=None, footer=""):
    """A card. With an id and a rail label it is listed in "On this page"."""
    attrs = ""
    if cid:
        attrs += ' id="%s"' % cid
        if rail is not False:
            attrs += ' data-rail="%s"' % esc(rail or title)
    head = ('  <div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text">%s</h2></div>\n'
            % esc(title)) if title else ""
    foot = ('  <div class="pf-v6-c-card__footer">%s</div>\n' % footer) if footer else ""
    return ('<div class="section">\n<div class="pf-v6-c-card"%s>\n%s'
            '  <div class="pf-v6-c-card__body">%s</div>\n%s</div>\n</div>'
            % (attrs, head, body, foot))


def content(inner):
    return '<div class="pf-v6-c-content">%s</div>' % inner


def link(url, label):
    return '<a href="%s">%s</a>' % (esc(url), esc(label))


def code_block(text):
    return ('<div class="pf-v6-c-code-block"><div class="pf-v6-c-code-block__content">'
            '<pre class="pf-v6-c-code-block__pre"><code class="pf-v6-c-code-block__code">'
            '%s</code></pre></div></div>' % text)


def empty_state(title, body):
    return ('<div class="pf-v6-c-empty-state pf-m-sm"><div class="pf-v6-c-empty-state__content">'
            '<div class="pf-v6-c-empty-state__header"><div class="pf-v6-c-empty-state__title">'
            '<h3 class="pf-v6-c-empty-state__title-text">%s</h3></div></div>'
            '<div class="pf-v6-c-empty-state__body">%s</div></div></div>' % (esc(title), body))


def table(cls, head, rows):
    """A compact PatternFly table that stacks below md. rows hold finished
    HTML per cell; every cell carries its column's name for the stacked
    layout."""
    th = "".join('<th class="pf-v6-c-table__th" scope="col">%s</th>' % esc(h) for h in head)
    body = "\n".join(
        '<tr class="pf-v6-c-table__tr">%s</tr>' % "".join(
            '<td class="pf-v6-c-table__td" data-label="%s">%s</td>' % (esc(h), cell)
            for h, cell in zip(head, row)) for row in rows)
    return ('<table class="pf-v6-c-table pf-m-compact pf-m-grid-md %s">\n'
            '<thead class="pf-v6-c-table__thead"><tr class="pf-v6-c-table__tr">%s</tr></thead>\n'
            '<tbody class="pf-v6-c-table__tbody">\n%s\n</tbody></table>' % (cls, th, body))


def ubuntu(codename):
    if codename not in UBUNTU:
        return codename
    ver, lts = UBUNTU[codename]
    return "%s%s (%s)" % (ver, " LTS" if lts else "", codename)


def size(n):
    for unit, div in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= div:
            return "%.1f %s" % (n / div, unit)
    return "%d bytes" % n


def board_status(status):
    return {"hardware-tested": "Tested on hardware",
            "ci-only": "CI only: builds and passes the image checks, not yet booted on hardware"
            }.get(status, status)


def and_list(items):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---- upstream data ----

def read_boards():
    rows = []
    for line in (UPSTREAM / "boards.conf").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) != 6:
            sys.exit("boards.conf: cannot read %r" % line)
        rows.append(tuple(parts))
    return rows


def read_releases():
    return json.loads((UPSTREAM / "releases.json").read_text(encoding="utf-8"))


# ---- generated pages ----

def render_status(boards, catalogs):
    names = and_list("the " + n for n in dict.fromkeys(b[5] for b in boards))
    releases = and_list(ubuntu(r) for r in dict.fromkeys(b[2] for b in boards))
    if not catalogs:
        status = ("Early. No images have been released yet. The first images are "
                  "being built for %s on Ubuntu %s." % (names, releases))
    else:
        newest = catalogs[0]
        tested = [i for i in newest["images"] if i["status"] == "hardware-tested"]
        if not tested:
            status = ("Early. Images are built and checked in CI, but none has been "
                      "tested on hardware yet. Releases are pre-releases until they have.")
        elif len(tested) < len(newest["images"]):
            status = ("Early. Some images have been tested on hardware; the rest are "
                      "built and checked in CI only. The Download page says which.")
        else:
            status = "Every image in the newest release has been tested on hardware."
    rows = [("Status", esc(status)),
            ("Boards", esc(and_list(dict.fromkeys(b[5] for b in boards)))),
            ("Ubuntu", esc(releases))]
    if catalogs:
        rel = catalogs[0]["release"]
        rows.append(("Newest release", '%s<span class="meta">%s%s</span>' % (
            link("/download/", rel["version"]), esc(rel["date"]),
            ", pre-release" if rel["prerelease"] else "")))
    return kv(rows)


def render_download(catalogs):
    if not catalogs:
        return card("releases", "Releases", empty_state(
            "No releases yet",
            "Roxora has not published any images. The first ones are being built "
            "for the boards on the %s page. When a release is published it is listed "
            "here and on %s." % (link("/boards/", "Boards"),
                                 link(BUILD_REPO + "/releases", "the releases page"))))

    newest = catalogs[0]
    rel = newest["release"]
    if rel["prerelease"]:
        state = ("Pre-release. The images are built and checked in CI. A release "
                 "stays a pre-release until every image in it has been tested on hardware.")
    else:
        state = "Release. Every image in it has been tested on hardware."
    out = [card("release", "Roxora %s" % rel["version"], kv([
        ("Released", esc(rel["date"])),
        ("Status", esc(state)),
        ("Release notes", link(rel["url"], rel["url"].replace("https://", ""))),
    ]), rail="Release")]

    for img in newest["images"]:
        rows = [
            ("File", '<a href="%s">%s</a>' % (esc(img["url"]), esc(img["file"]))),
            ("Size", '%s<span class="meta">%s bytes compressed, %s written to the card</span>'
             % (esc(size(img["size"])), "{:,}".format(img["size"]), esc(size(img["extract_size"])))),
            ("SHA-256", '<code class="hash">%s</code>' % esc(img["sha256"])),
            ("Ubuntu", esc(ubuntu(img["release"]))),
            ("Kernel", esc("%s, Armbian %s branch" % (img["kernel"], img["branch"]))),
            ("Status", esc(board_status(img["status"]))),
        ]
        if img.get("verify_url"):
            rows.append(("Image checks", link(img["verify_url"], "verify output")))
        cid = "image-%s-%s-%s" % (img["board"], img["release"], img["branch"])
        title = img["board_name"]
        if sum(1 for i in newest["images"] if i["board"] == img["board"]) > 1:
            title += " (%s, %s)" % (img["release"], img["branch"])
        out.append(card(cid, title, kv(rows), rail=title))

    out.append(card("check", "Checking and writing an image", content(
        "<p>Each image has a <code>.sha256</code> file beside it on the release page. "
        "With both in the same directory:</p>" + code_block(
            "sha256sum -c %s.sha256" % esc(newest["images"][0]["file"])) +
        "<p>Write the <code>.img.xz</code> file to an SD card, USB drive, eMMC or NVMe as it "
        "is; the bootloader is inside the image. %s can do this, and so can any tool that "
        "writes compressed raw images. Some boards need a bootloader in their SPI flash "
        "before they boot from an SD card: see %s.</p>"
        "<p>At the first login the user is <code>ubuntu</code> with the password "
        "<code>ubuntu</code>, and you are asked to choose a new password.</p>"
        % (link("/rpi-imager/", "Raspberry Pi Imager"),
           link("/boards/#booting", "Booting from an SD card")))))

    older = catalogs[1:]
    if older:
        out.append(card("earlier", "Earlier releases", kv([
            (c["release"]["version"], '%s<span class="meta">%s%s</span>' % (
                link(c["release"]["url"], "Release notes"), esc(c["release"]["date"]),
                ", pre-release" if c["release"]["prerelease"] else ""))
            for c in older])))
    return "\n".join(out)


def render_boards(boards):
    short = {"hardware-tested": "Tested on hardware", "ci-only": "CI only"}
    rows = [[esc(name), esc(soc.upper()), esc(branch), esc(ubuntu(release)),
             esc(short.get(status, status))]
            for _board, branch, release, status, soc, name in boards]
    body = table("boards-table", ["Board", "SoC", "Kernel", "Ubuntu", "Status"], rows)
    out = [card("boards", "Supported boards", body, rail="Supported boards")]
    out.append(card("booting", "Booting from an SD card", kv([
        ("Radxa ROCK 4D", "The board's boot ROM never boots from an SD card: it looks at "
         "SPI flash, UFS and USB, in that order. U-Boot has to be in the SPI flash first; "
         "it then boots a Roxora SD card. %s" % link(
             "https://docs.radxa.com/en/rock4/rock4d", "Radxa ROCK 4D documentation")),
        ("ArmSoM CM5-IO", "Boots from eMMC first, then from the SD card. %s" % link(
            "https://docs.armsom.org/armsom-cm5-io", "ArmSoM CM5-IO documentation")),
    ])))
    out.append(card("about-status", "What the status means", kv([
        ("Tested on hardware", "A maintainer has booted the image on the board and "
         "run the hardware test."),
        ("CI only", "The image builds and passes the automatic image checks in CI. "
         "Nobody has booted it on the board yet."),
        ("Kernel", "Armbian's kernel branch. %s follows recent mainline kernels."
         % "<code>edge</code>"),
        ("Source", "This list is %s in the build repository." % link(
            BUILD_REPO + "/blob/main/boards.conf", "boards.conf")),
    ])))
    return "\n".join(out)


# ---- docs from roxora-os/build ----

def doc_title(text, fallback):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def render_doc(text, names):
    try:
        import markdown
    except ImportError:
        sys.exit("tools/build.py needs the markdown package: pip install markdown")
    text = re.sub(r"^# .+\n", "", text, count=1, flags=re.M)
    # GitHub nests a list item indented by two spaces; Python-Markdown wants
    # four. Doubling the indent of list items reads the same on both.
    text = re.sub(r"^( +)(?=(?:[-*+]|\d+\.) )", lambda m: m.group(1) * 2, text, flags=re.M)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
                             extension_configs={"toc": {"permalink": False}})

    def fix_link(m):
        href = m.group(1)
        if re.match(r"^[a-z]+:", href) or href.startswith("#"):
            return m.group(0)
        path, _, frag = href.partition("#")
        target = posixpath.normpath(posixpath.join("docs", path))
        if target.startswith("docs/") and target.endswith(".md") and target[5:] in names:
            new = "/docs/%s/" % target[5:-3]
        else:
            new = "%s/blob/main/%s" % (BUILD_REPO, target)
        return 'href="%s"' % (new + ("#" + frag if frag else ""))
    body = re.sub(r'href="([^"]+)"', fix_link, body)

    # Tables and code blocks are PatternFly components, not bare elements.
    body = body.replace("<table>", '<div class="table-scroll"><table class="pf-v6-c-table pf-m-compact">')
    body = body.replace("</table>", "</table></div>")
    body = body.replace("<thead>", '<thead class="pf-v6-c-table__thead">')
    body = body.replace("<tbody>", '<tbody class="pf-v6-c-table__tbody">')
    body = body.replace("<tr>", '<tr class="pf-v6-c-table__tr">')
    body = re.sub(r"<th(\s[^>]*)?>", lambda m: '<th class="pf-v6-c-table__th" scope="col"%s>' % (m.group(1) or ""), body)
    body = re.sub(r"<td(\s[^>]*)?>", lambda m: '<td class="pf-v6-c-table__td"%s>' % (m.group(1) or ""), body)
    body = re.sub(r"<pre><code(?: class=\"[^\"]*\")?>(.*?)</code></pre>",
                  lambda m: code_block(m.group(1)), body, flags=re.S)

    # One card per second-level heading, so the rail lists the sections.
    parts = re.split(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    out = []
    if parts[0].strip():
        out.append(card(None, None, content(parts[0].strip())))
    for i in range(1, len(parts), 3):
        hid, heading, inner = parts[i], html.unescape(re.sub(r"<[^>]+>", "", parts[i + 1])), parts[i + 2]
        out.append(card(hid, heading, content(inner.strip())))
    return "\n".join(out)


def render_docs_index(docs):
    rows = [(title, link("/docs/%s/" % slug, title)) for slug, title, _ in docs]
    body = ('<ul class="doc-list">%s</ul>' % "".join(
        "<li>%s</li>" % link("/docs/%s/" % slug, title) for slug, title, _ in docs)
        if rows else "<p>No documents yet.</p>")
    return card("documents", "Documents", content(
        body + "<p>These pages are rendered from %s in the build repository.</p>"
        % link(BUILD_REPO + "/tree/main/docs", "docs/")))


# ---- the shell ----

def search_records(slug, href, heading, fragment):
    """One record per card, built from the page itself: a card is findable
    because it is there, not because someone remembered to index it. Slices
    run from one card to the next rather than matching a closing tag, which
    nesting makes unreliable."""
    def text_of(chunk):
        chunk = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", chunk)
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", chunk))).strip()

    starts = [(m.start(), m.group(1), text_of(m.group(2))) for m in re.finditer(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*>\s*'
        r'(?:<div class="pf-v6-c-card__header[^>]*>.*?</div>\s*)?'
        r'<div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text">(.*?)</h2>',
        fragment, re.S)]
    out = []
    for i, (pos, cid, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(fragment)
        out.append({"t": title, "u": href + "#" + cid, "p": heading,
                    "x": text_of(fragment[pos:end])})
    return out



def render_nav(current):
    out = []
    for title, items in NAV:
        tid = re.sub(r"[^a-z]+", "-", title.lower()).strip("-") + "-title"
        out.append('        <section class="pf-v6-c-nav__section" aria-labelledby="%s">\n'
                   '          <h2 class="pf-v6-c-nav__section-title" id="%s">%s</h2>\n'
                   '          <ul class="pf-v6-c-nav__list" role="list">' % (tid, tid, esc(title)))
        for label, href in items:
            cur = href == current
            out.append('            <li class="pf-v6-c-nav__item">'
                       '<a href="%s" class="pf-v6-c-nav__link%s"%s>'
                       '<span class="pf-v6-c-nav__link-text">%s</span></a></li>'
                       % (href, " pf-m-current" if cur else "",
                          ' aria-current="page"' if cur else "", esc(label)))
        out.append("          </ul>\n        </section>")
    return "\n".join(out)


def cards(fragment):
    """The cards on this page, for the rail: every card that carries an id."""
    return re.findall(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*data-rail="([^"]+)"', fragment)


def render_rail(sections):
    if not sections:
        return ""
    items = "\n".join(
        '                <li class="pf-v6-c-jump-links__item">'
        '<span class="pf-v6-c-jump-links__link">'
        '<a class="pf-v6-c-button pf-m-link" href="#%s"><span class="pf-v6-c-button__text">'
        '<span class="pf-v6-c-jump-links__link-text">%s</span></span></a></span></li>'
        % (sid, label) for sid, label in sections)
    return """          <aside class="page-rail no-print">
            <nav class="pf-v6-c-jump-links pf-m-vertical pf-m-expandable pf-m-non-expandable-on-xl" aria-label="On this page" id="jump-nav" data-scrollable=".pf-v6-c-page__main">
              <div class="pf-v6-c-jump-links__header" id="jump-header">
                <div class="pf-v6-c-jump-links__toggle">
                  <button class="pf-v6-c-button pf-m-plain" type="button" aria-expanded="false" aria-controls="jump-list" id="jump-toggle">
                    <span class="pf-v6-c-button__icon pf-m-start"><span class="pf-v6-c-jump-links__toggle-icon">%s</span></span>
                    <span class="pf-v6-c-button__text">On this page</span>
                  </button>
                </div>
                <div class="pf-v6-c-jump-links__label">On this page</div>
              </div>
              <ul class="pf-v6-c-jump-links__list" role="list" aria-labelledby="jump-header" id="jump-list">
%s
              </ul>
            </nav>
          </aside>
""" % (CARET, items)


SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="canonical" href="%(canonical)s">
%(noindex)s
<link rel="icon" href="/assets/brand/roxora-mark.svg" type="image/svg+xml">
<link rel="icon" href="/assets/brand/roxora-mark-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/brand/roxora-avatar-180.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%(name)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:url" content="%(canonical)s">
<meta property="og:image" content="%(site)s/assets/brand/roxora-avatar-500.png">
<meta property="og:image:width" content="500">
<meta property="og:image:height" content="500">
<meta name="twitter:card" content="summary">
<script>
  (function () {
    var saved = null;
    try { saved = localStorage.getItem('theme'); } catch (e) {}
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('pf-v6-theme-dark');
    }
  })();
  // Arriving from another of this site's pages, the sidebar's current-item
  // bar grows in as PatternFly's does when an item is clicked, rather than
  // fading with the rest of the page (site.css has the animation).
  addEventListener('pagereveal', function (e) {
    if (!e.viewTransition) return;
    var root = document.documentElement;
    root.classList.add('nav-accent-enter');
    setTimeout(function () { root.classList.remove('nav-accent-enter'); }, 1000);
  });
</script>
<link rel="stylesheet" href="%(pf_css)s">
<link rel="stylesheet" href="%(site_css)s">
</head>
<body>
<div class="pf-v6-c-page">
  <div class="pf-v6-c-skip-to-content">
    <a class="pf-v6-c-button pf-m-primary" href="#main-content"><span class="pf-v6-c-button__text">Skip to content</span></a>
  </div>
  <header class="pf-v6-c-masthead pf-m-display-inline">
    <div class="pf-v6-c-masthead__main">
      <span class="pf-v6-c-masthead__toggle">
        <button class="pf-v6-c-button pf-m-hamburger pf-m-plain" type="button" aria-label="Site navigation" aria-expanded="false" aria-controls="site-sidebar" id="nav-toggle">
          <span class="pf-v6-c-button__icon"><svg viewBox="0 0 10 10" class="pf-v6-c-button--hamburger-icon pf-v6-svg" width="1em" height="1em"><path class="pf-v6-c-button--hamburger-icon--top" d="M1,1 L9,1"/><path class="pf-v6-c-button--hamburger-icon--middle" d="M1,5 L9,5"/><path class="pf-v6-c-button--hamburger-icon--arrow" d="M1,5 L1,5 L1,5"/><path class="pf-v6-c-button--hamburger-icon--bottom" d="M9,9 L1,9"/></svg></span>
        </button>
      </span>
      <div class="pf-v6-c-masthead__brand">
        <a class="pf-v6-c-masthead__logo brand" href="/" aria-label="Roxora home">
          <img class="pf-v6-c-brand brand-mark" src="/assets/brand/roxora-mark.svg" width="120" height="120" alt="">
          <span class="brand-name wordmark">roxora</span>
        </a>
      </div>
    </div>
    <div class="pf-v6-c-masthead__content">
      <div class="search-slot">
        <div class="pf-v6-c-input-group pf-m-search-expandable pf-m-plain site-search" id="site-search">
          <div class="pf-v6-c-input-group__item pf-m-search-input">
            <div class="pf-v6-c-text-input-group">
              <div class="pf-v6-c-text-input-group__main pf-m-icon">
                <span class="pf-v6-c-text-input-group__text">
                  <span class="pf-v6-c-text-input-group__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
                  <input class="pf-v6-c-text-input-group__text-input" type="text" id="search-input"
                         placeholder="Search this site" autocomplete="off" spellcheck="false"
                         aria-label="Search this site" role="combobox" aria-expanded="false"
                         aria-controls="search-results" aria-autocomplete="list"
                         data-index="/assets/search-index.json">
                </span>
              </div>
            </div>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-expand pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-open"
                    aria-label="Search this site" aria-expanded="false">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
            </button>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-action pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-close" aria-label="Close search">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
            </button>
          </div>
        </div>
        <div class="pf-v6-c-menu search-results" id="search-results" hidden>
          <div class="pf-v6-c-menu__content">
            <ul class="pf-v6-c-menu__list" role="listbox" aria-label="Search results" id="search-list"></ul>
          </div>
        </div>
      </div>
      <a class="pf-v6-c-button pf-m-plain" href="https://github.com/roxora-os" aria-label="Roxora on GitHub" title="Roxora on GitHub">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 496 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8zM97.2 352.9c-1.3 1-1 3.3.7 5.2 1.6 1.6 3.9 2.3 5.2 1 1.3-1 1-3.3-.7-5.2-1.6-1.6-3.9-2.3-5.2-1zm-10.8-8.1c-.7 1.3.3 2.9 2.3 3.9 1.6 1 3.6.7 4.3-.7.7-1.3-.3-2.9-2.3-3.9-2-.6-3.6-.3-4.3.7zm32.4 35.6c-1.6 1.3-1 4.3 1.3 6.2 2.3 2.3 5.2 2.6 6.5 1 1.3-1.3.7-4.3-1.3-6.2-2.2-2.3-5.2-2.6-6.5-1zm-11.4-14.7c-1.6 1-1.6 3.6 0 5.9 1.6 2.3 4.3 3.3 5.6 2.3 1.6-1.3 1.6-3.9 0-6.2-1.4-2.3-4-3.3-5.6-2z"/></svg></span>
      </a>
      <button class="pf-v6-c-button pf-m-plain theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg icon-moon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M10.6 2a8 8 0 1 0 7.4 11 6.6 6.6 0 0 1-7.4-11Z"/></svg><svg class="pf-v6-svg icon-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true" role="img" width="1em" height="1em"><circle cx="10" cy="10" r="3.6"/><path d="M10 1.5v2.2M10 16.3v2.2M1.5 10h2.2M16.3 10h2.2M4 4l1.6 1.6M14.4 14.4 16 16M4 16l1.6-1.6M14.4 5.6 16 4"/></svg></span>
      </button>
      <a class="pf-v6-c-button pf-m-primary masthead-give" href="/download/"><span class="pf-v6-c-button__text">Download</span></a>
    </div>
  </header>
  <div class="pf-v6-c-backdrop site-backdrop" id="site-backdrop" hidden></div>
  <aside class="pf-v6-c-page__sidebar" id="site-sidebar">
    <div class="pf-v6-c-page__sidebar-main">
      <div class="pf-v6-c-page__sidebar-body pf-m-page-insets">
        <nav class="pf-v6-c-nav" aria-label="Site">
%(nav)s
        </nav>
      </div>
    </div>
  </aside>
  <div class="pf-v6-c-page__main-container" tabindex="-1">
    <main class="pf-v6-c-page__main doc-page%(railcls)s" tabindex="-1" id="main-content">
      <section class="pf-v6-c-page__main-section pf-m-limit-width" aria-label="%(heading)s">
        <div class="pf-v6-c-page__main-body">
%(rail)s          <div class="page-content">
%(head)s%(content)s

          </div>
        </div>
      </section>

      <footer class="pf-v6-c-page__main-section site-footer">
        <div class="pf-v6-c-page__main-body">
          <div class="pf-v6-l-grid pf-m-gutter">
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Roxora</p>
              <nav aria-label="Roxora">
                <a href="/download/">Download</a>
                <a href="/boards/">Boards</a>
                <a href="/rpi-imager/">Raspberry Pi Imager</a>
                <a href="/catalog/index.json">Release catalog</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Documentation</p>
              <nav aria-label="Documentation">
                <a href="/docs/">Docs</a>
                <a href="/faq/">FAQ</a>
                <a href="/about/">About</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Elsewhere</p>
              <nav aria-label="Elsewhere">
                <a href="%(build_repo)s">Build repository</a>
                <a href="%(build_repo)s/releases">Releases</a>
                <a href="%(build_repo)s/issues">Issues</a>
                <a href="https://github.com/roxora-os/design">Logo files</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-12-col-on-sm pf-m-3-col-on-lg">
              <span class="brand foot-brand">
                <img class="pf-v6-c-brand brand-mark" src="/assets/brand/roxora-mark.svg" width="120" height="120" alt="" loading="lazy">
                <span class="brand-name wordmark">roxora</span>
              </span>
              <p class="foot-about">Images for Rockchip boards with Armbian&rsquo;s kernel and bootloader
                and a stock Ubuntu userspace. Not affiliated with Canonical, the Armbian
                project or Rockchip.</p>
              <address>
                <a href="mailto:%(email)s">%(email)s</a><br>
                Issues and pull requests go to the build repository.
              </address>
            </div>
          </div>
        </div>
      </footer>

      <section class="pf-v6-c-page__main-section pf-m-no-fill foot-legal">
        <div class="pf-v6-c-page__main-body">
          <span>Copyright &copy; <span id="year">%(year)s</span> %(author)s. The code behind this site is licensed under <a href="%(source)s/blob/main/LICENSE">GPL-2.0</a>.</span>
          <span><a href="%(source)s">View page source</a></span>
          <span><button class="link-button" type="button" id="about-page-open">About this site</button></span>
          <span><a href="mailto:%(email)s">Contact</a></span>
        </div>
      </section>
    </main>
  </div>
</div>
<div class="pf-v6-c-backdrop about-backdrop" id="about-page" hidden>
  <div class="pf-v6-l-bullseye">
  <div class="pf-v6-c-about-modal-box" role="dialog" aria-modal="true" aria-labelledby="about-page-title">
    <div class="pf-v6-c-about-modal-box__brand">
      <svg class="credit-badge" viewBox="14 0 346 110" role="img" aria-label="Engineered by gahingwoo">
        <g class="credit-badge__mark" transform="translate(14,19) scale(0.257143)">
          <rect x="0" y="0" width="350" height="70"/>
          <rect x="70" y="70" width="70" height="70"/>
          <rect x="210" y="70" width="70" height="70"/>
          <rect x="0" y="210" width="350" height="70"/>
        </g>
        <text class="credit-badge__label" x="124" y="48">Engineered by</text>
        <text class="credit-badge__name" x="123" y="88">gahingwoo</text>
      </svg>
    </div>
    <div class="pf-v6-c-about-modal-box__close">
      <button class="pf-v6-c-button pf-m-plain" type="button" id="about-page-close" data-dialog-close aria-label="Close About this site">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
      </button>
    </div>
    <div class="pf-v6-c-about-modal-box__header">
      <h1 class="pf-v6-c-title pf-m-4xl" id="about-page-title">About this site</h1>
    </div>
    <div class="pf-v6-c-about-modal-box__content">
      <dl class="pf-v6-c-description-list pf-m-horizontal">
%(aboutrows)s
      </dl>
      <p class="pf-v6-c-about-modal-box__strapline">
        Copyright &copy; %(year)s %(author)s. The code behind this site is
        free software under the GNU General Public License, version 2.
      </p>
    </div>
  </div>
  </div>
</div>
<div class="pf-v6-c-back-to-top pf-m-hidden" id="back-to-top">
  <a class="pf-v6-c-button pf-m-primary" href="#main-content">
    <span class="pf-v6-c-button__text">Back to top</span>
    <span class="pf-v6-c-button__icon pf-m-end"><svg class="pf-v6-svg" viewBox="0 0 448 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M6.101 359.293 25.9 379.092a12 12 0 0 0 16.971 0L224 198.393l181.13 180.698a12 12 0 0 0 16.971 0l19.799-19.799a12 12 0 0 0 0-16.971L232.485 132.908a12 12 0 0 0-16.971 0L6.101 342.322a12 12 0 0 0 0 16.971z"/></svg></span>
  </a>
</div>
<script src="%(site_js)s"></script>
</body>
</html>
"""


def page_head(heading, subtitle, action):
    btn = ""
    if action:
        btn = ('              <a class="pf-v6-c-button pf-m-secondary" href="%s">'
               '<span class="pf-v6-c-button__text">%s</span></a>\n' % (esc(action[1]), esc(action[0])))
    sub = ' <span class="subtitle">%s</span>' % esc(subtitle) if subtitle else ""
    return ('            <div class="page-head">\n'
            '              <h1 class="page-title" id="page-title">%s%s</h1>\n%s'
            '            </div>\n' % (esc(heading), sub, btn))


def build():
    sample_flag = "--sample" in sys.argv[1:]
    if not (UPSTREAM / "releases.json").is_file():
        sys.exit("no cache/upstream/: run tools/fetch_upstream.py first")
    boards = read_boards()
    catalogs = read_releases()
    sample = sample_flag or any("_sample" in c for c in catalogs)
    out_dir = ROOT / ("output/sample-site" if sample else "_site")
    if sample:
        print("SAMPLE release data: writing %s, not _site/" % out_dir.relative_to(ROOT))

    version_file = ROOT / "assets/patternfly/VERSION"
    pf_version = "PatternFly 6"
    if version_file.is_file():
        first = version_file.read_text(encoding="utf-8").splitlines()[0]
        pf_version = "PatternFly " + first.rsplit(" ", 1)[-1]
    built = datetime.now(timezone.utc)

    docs = []
    names = sorted(p.name for p in (UPSTREAM / "docs").glob("*.md"))
    for n in names:
        text = (UPSTREAM / "docs" / n).read_text(encoding="utf-8")
        docs.append((n[:-3], doc_title(text, n[:-3]), text))

    generated = {
        "{{status}}": render_status(boards, catalogs),
        "{{os-list-url}}": esc(OS_LIST_URL),
    }

    # (output dir, nav item, heading, subtitle, description, page head action, body)
    pages = []

    def fragment(slug):
        text = (CONTENT / (slug + ".html")).read_text(encoding="utf-8").rstrip()
        for key, value in generated.items():
            text = text.replace(key, value)
        left = re.findall(r"\{\{[a-z-]+\}\}", text)
        if left:
            sys.exit("content/%s.html: unknown %s" % (slug, ", ".join(left)))
        return text

    pages.append(("", "/", NAME, "Ubuntu userspace with Armbian's hardware support",
                  "Roxora builds images for Rockchip boards that pair Armbian's kernel and "
                  "bootloader with a stock Ubuntu userspace.",
                  ("Download", "/download/"), fragment("index")))
    pages.append(("download", "/download/", "Download",
                  "Roxora %s" % catalogs[0]["release"]["version"] if catalogs else "No releases yet",
                  "Download Roxora images, with their sizes, checksums and test status.",
                  ("All releases", BUILD_REPO + "/releases"), render_download(catalogs)))
    pages.append(("boards", "/boards/", "Boards", "%d supported" % len(boards),
                  "The boards Roxora builds images for, with kernel branch, Ubuntu "
                  "release and test status.", None, render_boards(boards)))
    pages.append(("rpi-imager", "/rpi-imager/", "Raspberry Pi Imager", "Writing Roxora with Imager",
                  "How to point Raspberry Pi Imager at the Roxora repository file to write "
                  "Roxora images.", None, fragment("rpi-imager")))
    pages.append(("docs", "/docs/", "Docs", "From the build repository",
                  "Roxora documentation, rendered from the build repository.", None,
                  render_docs_index(docs)))
    for slug, title, text in docs:
        pages.append(("docs/" + slug, "/docs/", title, None,
                      "%s: Roxora documentation." % title,
                      ("Source", "%s/blob/main/docs/%s.md" % (BUILD_REPO, slug)),
                      render_doc(text, names)))
    pages.append(("faq", "/faq/", "FAQ", "Questions people ask about Roxora",
                  "Why Roxora exists next to Armbian's images and ubuntu-rockchip, and what "
                  "it does not provide.", None, fragment("faq")))
    pages.append(("about", "/about/", "About", None,
                  "Who makes Roxora, how to reach them, and the licence.", None,
                  fragment("about")))

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", out_dir / "assets")

    # A file edited in place is the one thing a browser will go on serving from
    # its cache for a week. Every /assets/ URL in a built page gets a hash of
    # that file's own contents appended, so a changed file is a different URL
    # and an unchanged one keeps being served from the cache.
    seen = {}

    def stamp(match):
        path = match.group(0).lstrip("/")
        if path not in seen:
            f = out_dir / path
            if not f.is_file():
                sys.exit("%s is referenced but does not exist" % match.group(0))
            seen[path] = hashlib.sha256(f.read_bytes()).hexdigest()[:8]
        return "%s?v=%s" % (match.group(0), seen[path])

    ASSET = re.compile(r"/assets/[A-Za-z0-9._/-]+\.[A-Za-z0-9]+")

    # What the site is made of and what it does with a reader, for the About
    # this site dialog, as gahingwoo.com lists it.
    aboutrows = "\n".join(
        '        <div class="pf-v6-c-description-list__group">'
        '<dt class="pf-v6-c-description-list__term">'
        '<span class="pf-v6-c-description-list__text">%s</span></dt>'
        '<dd class="pf-v6-c-description-list__description">'
        '<div class="pf-v6-c-description-list__text">%s</div></dd></div>'
        % (term, value) for term, value in [
            ("Design system", esc(pf_version)),
            ("Analytics", "None. Your visit is not counted."),
            ("Loaded from elsewhere", "Nothing. Fonts, styles and scripts are served from this domain."),
            ("Kept on your device", "Your light or dark choice. Nothing else."),
            ("Search", "Runs in your browser. What you type is not sent anywhere."),
            ("Licence", "GPL-2.0, the code only."),
            ("Built", esc(built.strftime("%Y-%m-%d %H:%M UTC"))),
            ("Made by", link(AUTHOR_CODE, AUTHOR)),
            ("Source", link(SOURCE, SOURCE.replace("https://", ""))),
        ])

    # The search index is written before the pages, so the hash appended to
    # its URL in the masthead is the hash of the file the reader will fetch.
    records = []
    for directory, _current, heading, _sub, _desc, _action, body in pages:
        records += search_records(directory, "/" + (directory + "/" if directory else ""),
                                  heading, body)
    (out_dir / "assets/search-index.json").write_text(
        json.dumps(records, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    def render(directory, current, heading, subtitle, description, action, body):
        rail = cards(body)
        href = "/" + (directory + "/" if directory else "")
        out = SHELL % dict(
            title=esc(NAME if not directory else "%s | %s" % (heading, NAME)),
            description=esc(description),
            canonical=SITE + href, site=SITE, name=NAME, email=EMAIL, source=SOURCE,
            build_repo=BUILD_REPO, author=esc(AUTHOR), year=built.year,
            pf_css="/assets/patternfly/patternfly-site.css", site_css="/assets/site.css",
            site_js="/assets/site.js", aboutrows=aboutrows,
            heading=esc(heading),
            noindex='<meta name="robots" content="noindex">\n' if (sample or directory == "404") else "",
            head=page_head(heading, subtitle, action),
            nav=render_nav(current), rail=render_rail(rail),
            railcls=" with-rail" if rail else "",
            content=body)
        # The og:image is an absolute URL on this site; stamp it too.
        out = ASSET.sub(stamp, out)
        return href, out

    written = []
    for directory, current, heading, subtitle, description, action, body in pages:
        href, out = render(directory, current, heading, subtitle, description, action, body)
        target = out_dir / directory / "index.html" if directory else out_dir / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        written.append(href)

    _, out = render("404", None, "Page not found", None, "This page does not exist.", None,
                    '<div class="pf-v6-c-card" style="max-width: 40rem">\n'
                    '  <div class="pf-v6-c-card__body"><div class="pf-v6-c-content">'
                    "<p>The link may be old, or the address mistyped. The pages of this "
                    "site are listed in the navigation; the %s holds everything else.</p>"
                    "</div></div>\n</div>" % link(BUILD_REPO, "build repository"))
    (out_dir / "404.html").write_text(out, encoding="utf-8")

    # The catalogs, at stable addresses on this site. A release asset on
    # GitHub is served without CORS headers, so a browser page (the web
    # flasher) cannot read roxora-catalog.json from the release itself;
    # GitHub Pages serves these with Access-Control-Allow-Origin: *.
    cat_dir = out_dir / "catalog"
    cat_dir.mkdir()
    for c in catalogs:
        (cat_dir / (c["release"]["tag"] + ".json")).write_text(
            json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if catalogs:
        (cat_dir / "latest.json").write_text(
            json.dumps(catalogs[0], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (cat_dir / "index.json").write_text(json.dumps({
        "schema": 1,
        "latest": catalogs[0]["release"]["tag"] if catalogs else None,
        "releases": [{
            "tag": c["release"]["tag"], "version": c["release"]["version"],
            "date": c["release"]["date"], "prerelease": c["release"]["prerelease"],
            "catalog": "%s/catalog/%s.json" % (SITE, c["release"]["tag"]),
        } for c in catalogs],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    doc = os_list.make(catalogs, boards, SITE)
    (out_dir / "os_list.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    today = built.date().isoformat()
    (out_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join("  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>"
                    % (SITE, href, today) for href in written)
        + "\n</urlset>\n", encoding="utf-8")
    (out_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")
    # GitHub Pages would otherwise run the output through Jekyll.
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    for href in written:
        print(href)
    print("404.html, os_list.json (%d images), catalog/ (%d releases%s), sitemap.xml, "
          "robots.txt -> %s" % (len(doc["os_list"]), len(catalogs),
                                ", latest.json" if catalogs else ", no latest.json",
                                out_dir.relative_to(ROOT)))


if __name__ == "__main__":
    build()
