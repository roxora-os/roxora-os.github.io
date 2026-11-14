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

The code is split by what it renders: markup.py has the pieces of markup
and the constants, shell.py the shell and the search records, docs.py the
documents, page_home.py, page_download.py, page_boards.py and page_imager.py
a page each, and this file the build itself.

    python3 tools/fetch_upstream.py
    python3 tools/build.py

Writes _site/: the pages, 404.html, os_list.json, sitemap.xml, robots.txt and
a copy of assets/. Needs markdown-it-py (pip install -r tools/requirements.txt).

A build from sample release data (a catalog carrying "_sample", which
fetch_upstream.py --sample produces) goes to output/sample-site/ instead and
never to _site/, which is what the workflow deploys.

Adapted from mabc-ws's build script; the shell is the one gahingwoo.com and
mabc-ws run. The brand files in assets/brand/ are copies from roxora-os/design.
"""

import hashlib
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import boards as boards_conf  # noqa: E402
import os_list  # noqa: E402
import page_boards  # noqa: E402
import page_download  # noqa: E402
import page_home  # noqa: E402
import page_imager  # noqa: E402
from docs import DOC_SUMMARY, doc_title, link_list, render_doc, render_docs_index  # noqa: E402
from markup import (AUTHOR, AUTHOR_CODE, BUILD_REPO, CONTENT, EMAIL, IMAGER_REPO,  # noqa: E402
                    NAME, OS_LIST_URL, ROOT, SITE, SOURCE, TAGLINE, UPSTREAM, and_list, esc,
                    link, nobreak)
from shell import (FOOTER_DOCS, FOOTER_PAGES, SHELL, SITE_PAGES, cards, foot_links,  # noqa: E402
                   doc_section, page_head, render_nav, render_rail, search_records)


# Scripts only one page needs, after site.js.
PAGE_SCRIPTS = {"download": ["/assets/board-filter.js", "/assets/download.js"],
                "boards": ["/assets/board-filter.js"]}


def read_boards():
    path = UPSTREAM / "boards.conf"
    return boards_conf.parse(path.read_text(encoding="utf-8"), "boards.conf")


def read_imager():
    f = UPSTREAM / "imager.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def read_releases():
    return json.loads((UPSTREAM / "releases.json").read_text(encoding="utf-8"))


def read_synced():
    """When fetch_upstream.py read GitHub, for the subtitles of Download and
    Boards, so that a stale page says so."""
    f = UPSTREAM / "synced.json"
    if not f.is_file():
        return None
    when = datetime.strptime(json.loads(f.read_text(encoding="utf-8"))["synced"], "%Y-%m-%d %H:%M")
    return "Synced from GitHub %d %s, %s UTC" % (when.day, when.strftime("%B %Y"),
                                                  when.strftime("%H:%M"))


def build():
    sample_flag = "--sample" in sys.argv[1:]
    if not (UPSTREAM / "releases.json").is_file():
        sys.exit("no cache/upstream/: run tools/fetch_upstream.py first")
    boards = read_boards()
    catalogs = read_releases()
    # Catalogs written before images[].vendor existed: the maker is the first
    # word of the board's name, as boards.conf's own fallback has it.
    for c in catalogs:
        for img in c["images"]:
            img.setdefault("vendor", img["board_name"].split()[0])
    synced = read_synced()
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
    titles = {slug: title for slug, title, _ in docs}

    generated = {
        "{{os-list-url}}": esc(OS_LIST_URL),
        "{{board-names}}": esc(and_list(dict.fromkeys(b["name"] for b in boards))),
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

    def with_synced(subtitle):
        return (subtitle, synced) if synced else subtitle

    # The boards the Download page has images for: the other pages link a
    # board to its download only when there is one.
    downloadable = {i["board"] for c in page_download.offered(catalogs) for i in c["images"]}
    pages.append(("", "/", NAME, "Plain Ubuntu for Rockchip boards", TAGLINE,
                  None, page_home.render(boards, catalogs, downloadable)))
    download_body, _ = page_download.render(catalogs)
    pages.append(("download", "/download/", "Download",
                  with_synced(page_download.subtitle(catalogs)),
                  "Download Roxora images, with their sizes, checksums and test status.",
                  ("All releases", BUILD_REPO + "/releases"), download_body))
    imager = read_imager()
    pages.append(("roxora-imager", "/roxora-imager/", "Roxora Imager",
                  with_synced(page_imager.subtitle(imager)),
                  "Download Roxora Imager, the app that downloads, checks and writes "
                  "Roxora images.", ("All releases", IMAGER_REPO + "/releases"),
                  page_imager.render(imager)))
    pages.append(("boards", "/boards/", "Boards",
                  with_synced("%d boards, %d images" % (
                      len(dict.fromkeys(b["board"] for b in boards)), len(boards))),
                  "The boards Roxora builds images for, with kernel branch, Ubuntu "
                  "release and test status.", None, page_boards.render(boards, downloadable)))
    pages.append(("rpi-imager", "/rpi-imager/", "Raspberry Pi Imager", "Writing Roxora with Imager",
                  "How to point Raspberry Pi Imager at the Roxora repository file to write "
                  "Roxora images.", None, fragment("rpi-imager")))
    pages.append(("docs", "/docs/", "Docs", "From the build repository",
                  "Roxora documentation, rendered from the build repository.", None,
                  render_docs_index(docs)))
    for slug, title, text in docs:
        if slug == "faq":
            continue
        pages.append(("docs/" + slug, "/docs/", title, DOC_SUMMARY.get(slug),
                      "%s: Roxora documentation." % title,
                      ("Source", "%s/blob/main/docs/%s.md" % (BUILD_REPO, slug)),
                      render_doc(text, titles)))
    # One FAQ: docs/faq.md of the build repository. Until it exists there is
    # no FAQ page, rather than a second copy kept here.
    faq = next((d for d in docs if d[0] == "faq"), None)
    if faq:
        pages.append(("faq", "/faq/", "FAQ", "Questions people ask about Roxora",
                      "Questions people ask about Roxora, answered.",
                      ("Source", "%s/blob/main/docs/faq.md" % BUILD_REPO),
                      render_doc(faq[2], titles)))
    pages.append(("about", "/about/", "About", "Who makes Roxora and how to reach them",
                  "Who makes Roxora, how to reach them, and the licence.", None,
                  fragment("about")))
    pages.append(("privacy", "/privacy/", "Privacy policy", "The website and Roxora Imager",
                  "What the Roxora website and Roxora Imager fetch, from where, and what "
                  "they keep.", None, fragment("privacy")))
    pages.append(("code-signing", "/code-signing/", "Code signing policy", "Roxora Imager",
                  "Who may sign Roxora Imager, what is signed, and how.", None,
                  fragment("code-signing")))

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
        home = directory == ""
        rail = cards(body)
        href = "/" + (directory + "/" if directory else "")
        out = SHELL % dict(
            title=esc(NAME if not directory else "%s | %s" % (heading, NAME)),
            description=esc(description),
            canonical=SITE + href, site=SITE, name=NAME, email=EMAIL, source=SOURCE,
            build_repo=BUILD_REPO, author=esc(AUTHOR), year=built.year,
            tagline=esc(TAGLINE),
            pf_css="/assets/patternfly/patternfly-site.css", site_css="/assets/site.css",
            site_js="/assets/site.js", aboutrows=aboutrows,
            page_js="".join('<script src="%s"></script>\n' % src
                            for src in PAGE_SCRIPTS.get(directory, [])),
            noindex='<meta name="robots" content="noindex">\n' if (sample or directory == "404") else "",
            nav=render_nav(current, have),
            # The home page is a landing page: its sections are its own and
            # it has no page head. Its first screen carries Download, so the
            # masthead does not repeat it.
            sections=nobreak(body) if home else doc_section(
                esc(heading), render_rail(rail), page_head(heading, subtitle, action),
                nobreak(body)),
            maincls="home-page" if home else "doc-page" + (" with-rail" if rail else ""),
            download_btn="" if directory in ("download", "") else (
                '      <a class="pf-v6-c-button pf-m-primary masthead-give" href="/download/">'
                '<span class="pf-v6-c-button__text">Download</span></a>\n'),
            foot_pages=foot_links([(label, href) for label, href in FOOTER_PAGES if href in have]),
            foot_docs=foot_links([(label, href) for label, href in FOOTER_DOCS if href in have]))
        # The og:image is an absolute URL on this site; stamp it too.
        out = ASSET.sub(stamp, out)
        return href, out

    have = {"/" + (d + "/" if d else "") for d, *_ in pages}
    written = []
    for directory, current, heading, subtitle, description, action, body in pages:
        href, out = render(directory, current, heading, subtitle, description, action, body)
        target = out_dir / directory / "index.html" if directory else out_dir / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        written.append(href)

    _, out = render("404", None, "Page not found", "No page at this address",
                    "This page does not exist.", None,
                    '<div class="pf-v6-c-card">\n'
                    '  <div class="pf-v6-c-card__body"><div class="pf-v6-c-content">'
                    "<p>The link may be old, or the address mistyped. These are the pages "
                    "of this site; the %s holds everything else.</p></div>\n"
                    '<div class="pf-v6-u-mt-lg">%s</div></div>\n</div>'
                    % (link(BUILD_REPO, "build repository"),
                       link_list([row for row in SITE_PAGES if row[1] in have])))
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
