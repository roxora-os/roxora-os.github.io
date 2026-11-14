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
a copy of assets/. Needs markdown-it-py (pip install -r tools/requirements.txt).

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
import boards as boards_conf  # noqa: E402
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
# One line that says what Roxora is: the footer, the home page's meta and
# Open Graph description, and the About page all use it.
TAGLINE = ("Plain Ubuntu for Rockchip single-board computers, on Armbian's kernels "
           "and bootloaders.")
# Build repository documents for developers rather than for people installing
# Roxora. They are listed after the others on the Docs page.
EDK2_RK3576 = "https://github.com/gahingwoo/edk2-rk3576"
DEV_DOCS = ("adding-a-board", "release-contract", "architecture", "bsp-classification")
# The Docs page lists the user guides in this order; the rest follow by name.
GUIDE_ORDER = ("install", "hardware-test")
# One line per document, for the Docs page and as the document's subtitle.
# A document not listed here has neither.
DOC_SUMMARY = {
    "install": "Download, check and write an image, and log in the first time",
    "hardware-test": "What each board is put through before its image is marked tested",
    "adding-a-board": "From a line in boards.conf to a tested image",
    "architecture": "How an image is put together from Ubuntu and Armbian",
    "bsp-classification": "Each file of Armbian's board support package, kept or removed",
    "release-contract": "What a release contains, and the catalog that tools read",
}

# Ubuntu codenames the boards can name, with their version numbers. A codename
# missing here is shown as it is.
UBUNTU = {"jammy": ("22.04", True), "noble": ("24.04", True),
          "plucky": ("25.04", False), "questing": ("25.10", False),
          "resolute": ("26.04", True), "stonking": ("26.10", False)}

# The footer's own columns, as gahingwoo.com has them. A page not built is
# left out.
FOOTER_PAGES = [("Home", "/"), ("Download", "/download/"), ("Roxora Imager", "/roxora-imager/"),
                ("Boards", "/boards/"), ("Raspberry Pi Imager", "/rpi-imager/"),
                ("About", "/about/")]
FOOTER_DOCS = [("Installing Roxora", "/docs/install/"), ("All documents", "/docs/"),
               ("FAQ", "/faq/")]
# The pages the 404 page lists: title, address, what is there.
SITE_PAGES = [
    ("Home", "/", "What Roxora is, and how far along it is."),
    ("Download", "/download/", "The newest images, with sizes and checksums."),
    ("Roxora Imager", "/roxora-imager/", "The app that downloads, checks and writes an image."),
    ("Boards", "/boards/", "The supported boards and their test status."),
    ("Raspberry Pi Imager", "/rpi-imager/", "Writing Roxora with Raspberry Pi Imager."),
    ("Docs", "/docs/", "Installing, testing, and how Roxora is built."),
    ("FAQ", "/faq/", "Questions people ask about Roxora."),
    ("About", "/about/", "Who makes Roxora and how to reach them."),
    ("Privacy policy", "/privacy/", "What the website and Roxora Imager fetch, and from where."),
    ("Code signing policy", "/code-signing/", "Who may sign Roxora Imager, and what is signed."),
]

# Sidebar navigation. Section title, then (label, href) per item.
NAV = [
    ("Pages", [
        ("Home", "/"),
        ("Download", "/download/"),
        ("Roxora Imager", "/roxora-imager/"),
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

def kv(rows, term_html=False):
    """Key/value rows, as Cockpit lays out system information. Values are
    finished HTML; callers escape what they put in. Terms are text, or
    finished HTML with term_html."""
    return ('<dl class="pf-v6-c-description-list pf-m-horizontal-on-sm kv">\n' + "\n".join(
        '<div class="pf-v6-c-description-list__group">'
        '<dt class="pf-v6-c-description-list__term">'
        '<span class="pf-v6-c-description-list__text">%s</span></dt>'
        '<dd class="pf-v6-c-description-list__description">'
        '<div class="pf-v6-c-description-list__text">%s</div></dd></div>'
        % (term if term_html else esc(term), value) for term, value in rows) + "\n</dl>")


# Names that read as one thing and that a phone would otherwise break at
# their hyphen or slash.
NOBREAK = re.compile(r"(roxora-os/(?:build|imager|hwtool|design)\b|CM5-IO|pre-releases?|GPL-2\.0)")


def nobreak(markup):
    """Holds those names together in a page's text, leaving tags and code
    blocks alone."""
    parts = re.split(r"(?s)(<pre\b.*?</pre>|<[^>]+>)", markup)
    for i in range(0, len(parts), 2):
        parts[i] = NOBREAK.sub(r'<span class="nowrap">\1</span>', parts[i])
    return "".join(parts)


def foot_links(items):
    return "\n".join('                <a href="%s">%s</a>' % (esc(h), esc(l)) for l, h in items)


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


def table(cls, head, rows, widths=None):
    """A compact PatternFly table that stacks below md. rows hold finished
    HTML per cell; every cell carries its column's name for the stacked
    layout. widths: per column a percentage PatternFly has a width
    modifier for, or None for a share of what is left."""
    widths = widths or [None] * len(head)
    th = "".join('<th class="pf-v6-c-table__th%s" scope="col">%s</th>'
                 % (" pf-m-width-%d" % w if w else "", esc(h)) for h, w in zip(head, widths))
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
    return {"hardware-tested": "Tested on hardware", "ci-only": "CI only"}.get(status, status)


def and_list(items):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---- upstream data ----

def read_boards():
    path = UPSTREAM / "boards.conf"
    return boards_conf.parse(path.read_text(encoding="utf-8"), "boards.conf")


def read_imager():
    f = UPSTREAM / "imager.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


# Roxora Imager's packages by platform: (platform, [(label, file name
# pattern)]). A file the release does not have is left out, and a platform
# with none of its files is too.
IMAGER_PACKAGES = [
    ("Windows (x64)", [("Installer", r"-windows-x64-setup\.exe$"), ("Zip", r"-windows-x64\.zip$")]),
    ("macOS (Apple silicon)", [("Disk image", r"-macos-arm64\.dmg$")]),
    ("macOS (Intel)", [("Disk image", r"-macos-x86_64\.dmg$")]),
    ("Linux (x86_64)", [("AppImage", r"-linux-x86_64\.AppImage$"), (".deb", r"_amd64\.deb$"),
                        (".rpm", r"\.x86_64\.rpm$")]),
    ("Linux (arm64)", [("AppImage", r"-linux-arm64\.AppImage$"), (".deb", r"_arm64\.deb$"),
                       (".rpm", r"\.aarch64\.rpm$")]),
]
IMAGER_REPO = "https://github.com/roxora-os/imager"


def render_imager(rel):
    """The Roxora Imager page: the packages of its newest release, read from
    GitHub when the site is built, and what each system asks on first start."""
    if not rel or not rel["assets"]:
        return card("release", "Downloads", empty_state(
            "No release yet",
            "Roxora Imager has not published any packages. When it does they are "
            "listed here and on %s." % link(IMAGER_REPO + "/releases", "its releases page")))
    assets = rel["assets"]
    rows = []
    for platform, kinds in IMAGER_PACKAGES:
        found = []
        for label, pattern in kinds:
            a = next((a for a in assets if re.search(pattern, a["name"])), None)
            if a:
                found.append('%s<span class="meta">%s, %s</span>' % (
                    link(a["url"], a["name"]), esc(label), esc(size(a["size"]))))
        if found:
            rows.append((platform, '<div class="pkg-list">%s</div>' % "".join(
                '<div>%s</div>' % f for f in found)))
    sums = next((a for a in assets if a["name"] == "SHA256SUMS"), None)
    # What has been tried on real hardware; keep this in step with the
    # hardware test reports (docs/hardware-test.md in roxora-os/build).
    state = ("Pre-release. Writing an SD card has been tested on macOS with 0.1.3: the "
             "card was written and read back correctly. Windows, Linux and writing a "
             "board over USB (Maskrom) have not been tested on hardware yet."
             if rel["prerelease"] else "Release.")
    info = [("Released", esc(rel["date"])),
            ("Status", esc(state)),
            ("Release notes", link(rel["url"], "Release notes"))]
    if sums:
        info.append(("Checksums", '%s<span class="meta">SHA-256 of every file in the '
                     'release. With the package in the same directory: '
                     '<code>sha256sum -c --ignore-missing SHA256SUMS</code></span>'
                     % link(sums["url"], "SHA256SUMS")))
    info.append(("Code signing", "The Windows and macOS packages are not signed with a "
                 "publisher's certificate yet. See the %s." % link(
                     "/code-signing/", "code signing policy")))
    out = [card("release", "Roxora Imager %s" % rel["tag"].lstrip("v"), kv(info), rail="Release"),
           card("install", "Install", kv([
               ("macOS and Linux", "The install script picks the package for the system, "
                "checks it against the SHA-256 GitHub publishes for it and installs it:%s"
                % code_block("curl -fsSL https://raw.githubusercontent.com/roxora-os/imager/main/install.sh | sh")),
               ("Homebrew (macOS)", code_block(
                   "brew trust gahingwoo/tap\nbrew install --cask gahingwoo/tap/roxora-imager")
                + '<span class="meta">Update with <code>brew upgrade --cask roxora-imager</code>; '
                'the app does not update itself.</span>'),
               ("By hand", "One of the packages below."),
           ]), rail="Install"),
           card("downloads", "Downloads", kv(rows))]
    out.append(card("first-start", "First start", kv([
        ("Windows", "Windows SmartScreen says <q>Windows protected your PC</q>, because the "
         "installer is not signed. Choose <strong>More info</strong>, then "
         "<strong>Run anyway</strong>."),
        ("macOS", "The app is not notarized, so macOS says it cannot be opened. On macOS 15 "
         "and later, open it once and choose <strong>Done</strong>, then in System Settings, "
         "Privacy &amp; Security, choose <strong>Open Anyway</strong>. On macOS 14 and "
         "earlier, right-click the app in Applications and choose <strong>Open</strong>."),
        ("Linux", "Install the .deb or .rpm with the package manager, or make the AppImage "
         "executable and run it. Writing an SD card asks for your password."),
        ("More", "Drivers for writing a board over USB (Maskrom mode) and the udev rule "
         "for the AppImage are in %s." % link(IMAGER_REPO + "/blob/main/docs/install.md",
                                              "Installing Roxora Imager")),
    ])))
    out.append(card("web", "In the browser", content(
        "<p>The same app runs in Chrome or Edge at %s. A browser cannot open a disk, so it "
        "writes a board's eMMC or SPI flash over USB only, not an SD card in the "
        "computer.</p>" % link(SITE + "/imager/", "roxora-os.github.io/imager"))))
    return "\n".join(out)


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


# ---- generated pages ----

def render_status(boards, catalogs):
    releases = and_list(ubuntu(r) for r in dict.fromkeys(b["release"] for b in boards))
    if not catalogs:
        status = "Early. No images have been released yet; the first ones are being built."
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
    rows = [("Stage", esc(status)),
            ("Boards", esc(and_list(dict.fromkeys(b["name"] for b in boards)))),
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
        state = ("Pre-release. Images marked CI only build and pass the image checks in "
                 "CI but have not been booted on hardware yet. A release stays a "
                 "pre-release until every image in it has been tested on hardware.")
    else:
        state = "Release. Every image in it has been tested on hardware."
    out = [card("release", "Roxora %s" % rel["version"], kv([
        ("Released", esc(rel["date"])),
        ("Status", esc(state)),
        ("Release notes", link(rel["url"], "Release notes")),
        ("Catalog", '%s<span class="meta">The files of this release with their sizes and '
         'checksums, in the format of the %s.</span>' % (
             link("/catalog/%s.json" % rel["tag"], "roxora-catalog.json"),
             link("/docs/release-contract/", "release contract"))),
    ] + ([("How to install", link("/docs/install/", "Installing Roxora"))]
         if (UPSTREAM / "docs" / "install.md").is_file() else [])), rail="Release")]

    for img in sorted(newest["images"], key=lambda i: (
            [x["board"] for x in newest["images"]].index(i["board"]),
            os_list.ubuntu_order(i.get("ubuntu_version"), i["branch"]))):
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
            rows.append(("Image checks", link(img["verify_url"], "Verify output")))
        spi = img.get("spi")
        if spi:
            # The ROCK 4D's boot ROM does not boot from a card, so its release
            # carries a U-Boot image for the SPI flash beside the disk image.
            rows.append(("SPI bootloader",
                         '%s<span class="meta">%s, SHA-256 <code class="hash">%s</code></span>'
                         '<span class="meta">It goes into the board\'s SPI flash, not onto '
                         'the card. See %s.</span>'
                         % (link(spi["url"], spi["file"]), esc(size(spi["size"])),
                            esc(spi["sha256"]),
                            link("/boards/#booting", "Booting"))))
        if img.get("firmware") == "uefi":
            # No U-Boot inside: the board's own UEFI firmware starts GRUB.
            # Right under File: it decides whether the image is of any use.
            rows.insert(1, ("Firmware", "This image has no bootloader of its own. The board "
                         "needs UEFI firmware, such as %s, in its SPI flash first. See %s."
                         % (link(EDK2_RK3576, "edk2-rk3576"),
                            link("/boards/#booting", "Booting"))))
        cid = "image-%s-%s-%s" % (img["board"], img["release"], img["branch"])
        title = img["board_name"]
        if sum(1 for i in newest["images"] if i["board"] == img["board"]) > 1:
            title += " (Ubuntu %s, %s)" % (img.get("ubuntu_version") or img["release"], img["branch"])
        out.append(card(cid, title, kv(rows), rail=title))

    out.append(card("check", "Checking and writing an image", content(
        "<p>Each image has a <code>.sha256</code> file beside it on the release page. "
        "With both in the same directory:</p>" + code_block(
            "sha256sum -c %s.sha256" % esc(newest["images"][0]["file"])) +
        "<p>Write the <code>.img.xz</code> file to an SD card, USB drive, eMMC or NVMe as it "
        "is. %s and %s can do this, and so can any tool that writes compressed raw images. "
        "A board image has its bootloader inside, though some boards need one in their SPI "
        "flash before they boot from an SD card; a UEFI image needs UEFI firmware on the "
        "board. See %s.</p>"
        "<p>The first login, on the console or over SSH, is user <code>roxora</code> with "
        "the password <code>roxora</code>, and you are asked to choose a new password "
        "straight away.</p>"
        % (link("/roxora-imager/", "Roxora Imager"), link("/rpi-imager/", "Raspberry Pi Imager"),
           link("/boards/#booting", "Booting")))))

    older = catalogs[1:]
    if older:
        out.append(card("earlier", "Earlier releases", kv([
            (c["release"]["version"], '%s<span class="meta">%s%s</span>' % (
                link(c["release"]["url"], "Release notes"), esc(c["release"]["date"]),
                ", pre-release" if c["release"]["prerelease"] else ""))
            for c in older])))
    return "\n".join(out)


def render_boards(boards):
    # One table per board maker, in the order boards.conf first names them.
    short = {"hardware-tested": "Tested on hardware", "ci-only": "CI only"}
    groups = []
    for vendor in dict.fromkeys(b["vendor"] for b in boards):
        rows = [[esc(b["name"]), esc(b["soc"].upper()), esc(b["branch"]),
                 esc(ubuntu(b["release"])), esc(short.get(b["status"], b["status"]))]
                for b in sorted((b for b in boards if b["vendor"] == vendor), key=lambda b: (
                    [x["board"] for x in boards].index(b["board"]),
                    os_list.ubuntu_order(UBUNTU.get(b["release"], ("", False))[0], b["branch"])))]
        groups.append('<div class="pf-v6-c-content%s"><h3>%s</h3></div>\n%s' % (
            " pf-v6-u-mt-lg" if groups else "", esc(vendor),
            table("boards-table doc-table", ["Board", "SoC", "Kernel", "Ubuntu", "Status"], rows,
                  [None, 15, 15, 30, 15])))
    body = "\n".join(groups)
    out = [card("boards", "Supported boards", body, rail="Supported boards")]
    out.append(card("booting", "Booting", kv([
        ("Radxa ROCK 4D", "The board's boot ROM never boots from an SD card: it looks at "
         "SPI flash, UFS and USB, in that order. U-Boot has to be in the SPI flash first; "
         "it then boots a Roxora SD card. %s" % link(
             "https://docs.radxa.com/en/rock4/rock4d", "Radxa ROCK 4D documentation")),
        ("ArmSoM CM5-IO", "Boots from eMMC first, then from the SD card. %s" % link(
            "https://docs.armsom.org/armsom-cm5-io", "ArmSoM CM5-IO documentation")),
        ("RK3576 boards with UEFI firmware", "One image for any RK3576 board whose SPI "
         "flash holds UEFI firmware, such as %s. The image has no U-Boot: the firmware "
         "starts GRUB from the image's EFI system partition and hands the kernel the "
         "board's device tree. Write the firmware first, following its own instructions, "
         "then the image to an SD card, USB drive, eMMC or NVMe. It has booted in QEMU, "
         "not yet on a board." % link(EDK2_RK3576, "edk2-rk3576")),
    ])))
    out.append(card("about-status", "What the status means", kv([
        ("Tested on hardware", "A maintainer has booted the image on the board and "
         "run the hardware test."),
        ("CI only", "The image builds and passes the automatic image checks in CI. "
         "Nobody has booted it on the board yet."),
        ("Kernel", "Armbian's kernel branch. %s follows recent mainline kernels; "
         "%s is Rockchip's own kernel (Linux 6.1), offered for the UEFI image."
         % ("<code>edge</code>", "<code>vendor</code>")),
        ("Source", "This list is %s in the build repository." % link(
            BUILD_REPO + "/blob/main/boards.conf", "boards.conf")),
    ])))
    return "\n".join(out)


# ---- docs from roxora-os/build ----

def doc_title(text, fallback):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def slugify(text, seen):
    """The id GitHub gives a heading, so a link to docs/x.md#anchor that
    works on GitHub works here too: lower case, punctuation other than
    hyphens and underscores dropped, spaces turned into hyphens, and -1, -2
    appended to repeats."""
    base = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    slug, n = base, 0
    while slug in seen:
        n += 1
        slug = "%s-%d" % (base, n)
    seen.add(slug)
    return slug


def doc_target(href, titles):
    """Where a link in a document goes on this site, and the title of the
    document it opens (None when it opens something else). A link to
    another document becomes its page here; any other relative link opens
    the file on GitHub."""
    if re.match(r"^[a-z]+:", href) or href.startswith("#"):
        return href, None
    path, _, frag = href.partition("#")
    target = posixpath.normpath(posixpath.join("docs", path))
    slug = target[5:-3] if target.startswith("docs/") and target.endswith(".md") else None
    if slug in titles:
        new = "/faq/" if slug == "faq" else "/docs/%s/" % slug
        title = titles[slug]
    else:
        new, title = "%s/blob/main/%s" % (BUILD_REPO, target), None
    return new + ("#" + frag if frag else ""), title


def render_doc(text, titles):
    """A document from docs/ of the build repository, as GitHub shows it:
    markdown-it is a CommonMark parser, so code indented or fenced inside a
    list item, tables and bare addresses come out as they do there."""
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        sys.exit("tools/build.py needs markdown-it-py: pip install -r tools/requirements.txt")
    md = MarkdownIt("commonmark", {"linkify": True}).enable(["table", "strikethrough", "linkify"])
    # Only addresses written out with their scheme become links, as on
    # GitHub; a file name such as architecture.md is not a domain.
    md.linkify.set({"fuzzy_link": False, "fuzzy_email": False})
    tokens = md.parse(re.sub(r"^# .+\n", "", text, count=1, flags=re.M))

    seen = set()
    labels = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            tok.attrSet("id", slugify(tokens[i + 1].content, seen))
        elif tok.type == "thead_open":
            labels = []
        elif tok.type == "th_open":
            labels.append(re.sub(r"[`*_]", "", tokens[i + 1].content))
        elif tok.type == "tr_open":
            col = 0
        elif tok.type == "td_open":
            # The column's name, which the stacked layout on a phone shows
            # beside each value.
            if col < len(labels):
                tok.attrSet("data-label", labels[col])
            col += 1
        elif tok.type == "inline":
            fix_inline(tok.children or [], titles)
    body = md.renderer.render(tokens, md.options, {})
    # "the GitHub releases of this repository": on this site "this
    # repository" would be the website's own.
    body = re.sub(r"\bthis(\s+)repository\b", r"roxora-os/build", body)

    # Tables and code blocks are PatternFly components, not bare elements.
    # A table stacks into labelled rows below md, as the Boards table does.
    body = re.sub(r"<table>(.*?)</table>", lambda m: doc_table(m.group(1)), body, flags=re.S)
    body = re.sub(r"<pre><code(?: class=\"[^\"]*\")?>(.*?)</code></pre>",
                  lambda m: code_block(m.group(1).rstrip("\n")), body, flags=re.S)

    # One card per second-level heading, so the rail lists the sections.
    parts = re.split(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    out = []
    if parts[0].strip():
        out.append(card(None, None, content(parts[0].strip())))
    for i in range(1, len(parts), 3):
        hid, heading, inner = parts[i], html.unescape(re.sub(r"<[^>]+>", "", parts[i + 1])), parts[i + 2]
        out.append(card(hid, heading, content(inner.strip())))
    return "\n".join(out)


def fix_inline(children, titles):
    """Links and wording that only make sense inside the build repository."""
    for j, tok in enumerate(children):
        if tok.type == "link_open":
            href, title = doc_target(tok.attrGet("href"), titles)
            tok.attrSet("href", href)
            # [hardware-test.md](hardware-test.md) reads as a file on GitHub;
            # here it opens a page, so it is named by the page's title.
            nxt = children[j + 1] if j + 1 < len(children) else None
            if (title and nxt is not None and nxt.type in ("text", "code_inline")
                    and children[j + 2].type == "link_close"
                    and re.fullmatch(r"[\w.-]+\.md", nxt.content)):
                nxt.type, nxt.content = "text", title


def doc_table(inner):
    """A table from a document. Below md it stacks into labelled rows, as
    the Boards table does. From md its layout is fixed: a column whose
    values are all short (Layer, Type) gets a set width and the rest share
    what is left, so tables with the same columns in one card line up with
    each other."""
    def plain(cell):
        return html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
    rows = re.findall(r"<tr>(.*?)</tr>", inner, re.S)
    cells = [re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S) for r in rows]
    ncol = max(len(c) for c in cells)
    widest = [max((len(plain(c[k])) for c in cells if k < len(c)), default=0)
              for k in range(ncol)]
    widths = ["s" if w <= 10 else "m" if w <= 20 else None for w in widest]
    if all(widths) or ncol < 3:
        widths = [None] * ncol
    col = iter(widths)

    def th(m):
        w = next(col, None)
        return '<th class="pf-v6-c-table__th%s" scope="col"%s>' % (
            " doc-col-%s" % w if w else "", m.group(1) or "")
    inner = re.sub(r"<th(\s[^>]*)?>", th, inner)
    # The stacked layout makes each cell a grid of label and value, so a
    # value of text and code mixed is held in one element, or every piece
    # of it becomes a grid item of its own.
    inner = re.sub(r"<td(\s[^>]*)?>(.*?)</td>", lambda m: '<td class="pf-v6-c-table__td"%s>'
                   '<div>%s</div></td>' % (m.group(1) or "", m.group(2)), inner, flags=re.S)
    inner = inner.replace("<thead>", '<thead class="pf-v6-c-table__thead">')
    inner = inner.replace("<tbody>", '<tbody class="pf-v6-c-table__tbody">')
    inner = inner.replace("<tr>", '<tr class="pf-v6-c-table__tr">')
    # A path breaks after a slash before it breaks anywhere else.
    inner = re.sub(r"<code>(.*?)</code>", lambda m: "<code>%s</code>"
                   % m.group(1).replace("/", "/<wbr>"), inner)
    return '<table class="pf-v6-c-table pf-m-compact pf-m-grid-md doc-table">%s</table>' % inner


def link_list(rows):
    """Pages as a key/value list: the title, the address, and one quiet line
    on what is there, as gahingwoo.com's 404 page lists its pages."""
    return kv([(title, '%s<span class="meta">%s</span>' % (
        link(href, (SITE + href).replace("https://", "").rstrip("/")), esc(meta)))
        for title, href, meta in rows])


def render_docs_index(docs):
    """Guides for people using Roxora first, then the documents for
    developers under their own heading, each with its one line."""
    def rows(group):
        return [(title, "/faq/" if slug == "faq" else "/docs/%s/" % slug,
                 DOC_SUMMARY.get(slug, "")) for slug, title, _ in group]

    def listing(entries):
        return kv([(link(href, title), esc(meta)) for title, href, meta in entries],
                  term_html=True)

    def order(slug):
        return (GUIDE_ORDER.index(slug) if slug in GUIDE_ORDER else len(GUIDE_ORDER), slug)
    users = sorted((d for d in docs if d[0] not in DEV_DOCS and d[0] != "faq"),
                   key=lambda d: order(d[0]))
    devs = [d for slug in DEV_DOCS for d in docs if d[0] == slug]
    out = []
    if users:
        faq = [("FAQ", "/faq/", "Questions people ask about Roxora")] if any(
            d[0] == "faq" for d in docs) else []
        out.append(card("guides", "Guides", listing(rows(users) + faq)))
    if devs:
        out.append(card("developers", "For developers", listing(rows(devs))))
    if not out:
        out.append(card("documents", "Documents", content("<p>No documents yet.</p>")))
    return "\n".join(out)


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
    # The snippet a result shows is read from "x": the card's prose, without
    # its heading (the result's title already says it) and without code
    # blocks and checksums, so a snippet never opens in the middle of a hash.
    # Those are still searched, from "k".
    code = re.compile(r'(?s)<pre\b.*?</pre>|<code class="hash">.*?</code>')
    out = []
    for i, (pos, cid, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(fragment)
        chunk = re.sub(r'(?s)^.*?</h2>', "", fragment[pos:end], count=1)
        rec = {"t": title, "u": href + "#" + cid, "p": heading,
               "x": text_of(code.sub(" ", chunk))}
        kept = " ".join(text_of(m) for m in code.findall(chunk))
        if kept:
            rec["k"] = kept
        out.append(rec)
    return out



def render_nav(current, have):
    """have: the site's own pages in this build. A link to one that was not
    built (the FAQ before docs/faq.md exists) is left out."""
    out = []
    for title, items in NAV:
        items = [(l, h) for l, h in items if not h.startswith("/") or h in have]
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
%(download_btn)s    </div>
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
              <p class="foot-title">Pages</p>
              <nav aria-label="Pages">
%(foot_pages)s
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Documentation</p>
              <nav aria-label="Documentation">
%(foot_docs)s
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
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <span class="brand foot-brand">
                <img class="pf-v6-c-brand brand-mark" src="/assets/brand/roxora-mark.svg" width="120" height="120" alt="" loading="lazy">
                <span class="brand-name wordmark">roxora</span>
              </span>
              <p class="foot-about">%(tagline)s Roxora is an independent project, not affiliated with Canonical, Armbian or Rockchip.</p>
              <address>
                <a href="mailto:%(email)s">%(email)s</a><br>
                Report problems with an image on <a href="%(build_repo)s/issues" class="nowrap">roxora-os/build</a>.
              </address>
            </div>
          </div>
        </div>
      </footer>

      <section class="pf-v6-c-page__main-section pf-m-no-fill foot-legal" aria-label="Site information">
        <div class="pf-v6-c-page__main-body">
          <span>Copyright &copy; <span id="year">%(year)s</span> %(author)s</span>
          <span><a href="%(source)s">View page source</a></span>
          <span><a href="/privacy/">Privacy policy</a></span>
          <span><a href="/code-signing/">Code signing policy</a></span>
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
    """The title with its subtitle beside it and the page's one action on
    the same row. A subtitle given as (text, note) puts the note on a line
    of its own under the title, so a long one does not push the action
    off the row."""
    note = ""
    if isinstance(subtitle, tuple):
        subtitle, note = subtitle
    btn = ""
    if action:
        btn = ('              <a class="pf-v6-c-button pf-m-secondary" href="%s">'
               '<span class="pf-v6-c-button__text">%s</span></a>\n' % (esc(action[1]), esc(action[0])))
    sub = ' <span class="subtitle">%s</span>' % esc(subtitle) if subtitle else ""
    title = '<h1 class="page-title" id="page-title">%s%s</h1>' % (esc(heading), sub)
    if note:
        title = '<div>%s<p class="page-note">%s</p></div>' % (title, esc(note))
    return ('            <div class="page-head">\n'
            '              %s\n%s'
            '            </div>\n' % (title, btn))


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
        "{{status}}": render_status(boards, catalogs),
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

    pages.append(("", "/", NAME, "Plain Ubuntu for Rockchip boards", TAGLINE,
                  None, fragment("index")))
    def with_synced(subtitle):
        return (subtitle, synced) if synced else subtitle

    pages.append(("download", "/download/", "Download",
                  with_synced("Roxora %s" % catalogs[0]["release"]["version"]
                              if catalogs else "No releases yet"),
                  "Download Roxora images, with their sizes, checksums and test status.",
                  ("All releases", BUILD_REPO + "/releases"),
                  render_download(catalogs)))
    imager = read_imager()
    pages.append(("roxora-imager", "/roxora-imager/", "Roxora Imager",
                  with_synced("Version %s, pre-release" % imager["tag"].lstrip("v")
                              if imager and imager["prerelease"] else
                              "Version %s" % imager["tag"].lstrip("v") if imager else
                              "No release yet"),
                  "Download Roxora Imager, the app that downloads, checks and writes "
                  "Roxora images.", ("All releases", IMAGER_REPO + "/releases"),
                  render_imager(imager)))
    pages.append(("boards", "/boards/", "Boards", with_synced("%d boards, %d images" % (len(dict.fromkeys(b["board"] for b in boards)), len(boards))),
                  "The boards Roxora builds images for, with kernel branch, Ubuntu "
                  "release and test status.", None, render_boards(boards)))
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
            heading=esc(heading),
            noindex='<meta name="robots" content="noindex">\n' if (sample or directory == "404") else "",
            head=page_head(heading, subtitle, action),
            nav=render_nav(current, have), rail=render_rail(rail),
            railcls=" with-rail" if rail else "",
            content=nobreak(body),
            download_btn="" if directory == "download" else (
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
