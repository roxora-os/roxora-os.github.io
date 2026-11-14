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
documents, and this file the generated pages and the build itself.

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
from docs import DOC_SUMMARY, doc_title, link_list, render_doc, render_docs_index  # noqa: E402
from markup import (AUTHOR, AUTHOR_CODE, BUILD_REPO, CONTENT, EDK2_RK3576, EMAIL,  # noqa: E402
                    IMAGER_REPO, NAME, OS_LIST_URL, ROOT, SITE, SOURCE, TAGLINE, UBUNTU,
                    UPSTREAM, and_list, board_status, card, code_block, content, empty_state,
                    esc, kv, link, nobreak, size, table, ubuntu)
from shell import (FOOTER_DOCS, FOOTER_PAGES, SHELL, SITE_PAGES, cards, foot_links,  # noqa: E402
                   page_head, render_nav, render_rail, search_records)


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
            status = ("Early. Every image is built and checked in CI; none has been "
                      "tested on hardware yet.")
        elif len(tested) < len(newest["images"]):
            status = ("Early. Every image is built and checked in CI, and some have also "
                      "been tested on hardware. The Download page says which.")
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


# What the Download page says about an image's flavor.
FLAVOR_ABOUT = {
    "cli": "Command line, no desktop",
    "gnome-minimal": "Minimal GNOME desktop (ubuntu-desktop-minimal)",
    "gnome": "GNOME desktop (ubuntu-desktop)",
}


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
    # A release: every image passed the checks in CI (and the QEMU boot for
    # UEFI images). A beta is a GitHub pre-release. Hardware testing is
    # shown per image.
    tested = sum(1 for i in newest["images"] if i["status"] == "hardware-tested")
    state = ("Beta. Try it if you want what comes next; the newest release is the safer choice. "
             if rel["prerelease"] else "Release. ")
    state += ("Every image passed the automatic checks in CI. %s"
              % ("All of them have also been tested on hardware." if tested == len(newest["images"])
                 else "Images marked Tested on hardware have also been booted on the board; "
                      "the others have not yet."))
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
            os_list.ubuntu_order(i.get("ubuntu_version"), i["branch"]),
            os_list.flavor_order(i))):
        rows = [
            ("File", '<a href="%s">%s</a>' % (esc(img["url"]), esc(img["file"]))),
            ("Size", '%s<span class="meta">%s bytes compressed, %s written to the card</span>'
             % (esc(size(img["size"])), "{:,}".format(img["size"]), esc(size(img["extract_size"])))),
            ("SHA-256", '<code class="hash">%s</code>' % esc(img["sha256"])),
            ("Ubuntu", esc(ubuntu(img["release"]))),
            ("Image", esc(FLAVOR_ABOUT.get(os_list.flavor(img), os_list.flavor_name(img)))),
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
        # A command line image keeps the anchor it had before the desktop
        # images existed. The flavor is in the title when the board has
        # desktop images in this release.
        fl = os_list.flavor(img)
        cid = "image-%s-%s-%s%s" % (img["board"], img["release"], img["branch"],
                                    "" if fl == "cli" else "-" + fl)
        title = img["board_name"]
        same_board = [i for i in newest["images"] if i["board"] == img["board"]]
        if len(same_board) > 1:
            title += " (Ubuntu %s, %s%s)" % (
                img.get("ubuntu_version") or img["release"], img["branch"],
                ", " + os_list.flavor_name(img, sentence=True)
                if any(os_list.flavor(i) != "cli" for i in same_board) else "")
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
        "<p>The first login, on the console, over SSH or on the login screen of a desktop "
        "image, is user <code>roxora</code> with "
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
        # One row per board, kernel branch and Ubuntu release; its images
        # (boards.conf has a line per flavor) share the last cell, grouped
        # by status.
        images = {}
        for b in boards:
            if b["vendor"] == vendor:
                images.setdefault((b["board"], b["branch"], b["release"]), []).append(b)
        rows = []
        for group in sorted(images.values(), key=lambda g: (
                [x["board"] for x in boards].index(g[0]["board"]),
                os_list.ubuntu_order(UBUNTU.get(g[0]["release"], ("", False))[0], g[0]["branch"]))):
            b = group[0]
            group.sort(key=os_list.flavor_order)
            cell = "".join(
                '%s<span class="meta">%s</span>' % (
                    esc(", ".join(os_list.flavor_name(i) for i in group if i["status"] == status)),
                    esc(short.get(status, status)))
                for status in dict.fromkeys(i["status"] for i in group))
            rows.append([esc(b["name"]), esc(b["soc"].upper()), esc(b["branch"]),
                         esc(ubuntu(b["release"])), cell])
        groups.append('<div class="pf-v6-c-content%s"><h3>%s</h3></div>\n%s' % (
            " pf-v6-u-mt-lg" if groups else "", esc(vendor),
            table("boards-table doc-table", ["Board", "SoC", "Kernel", "Ubuntu", "Images"], rows,
                  [None, 15, 15, 20, 25])))
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
        ("Images", "Command line images have no desktop. GNOME images start Ubuntu's GNOME "
         "desktop: the minimal one is Ubuntu's <code>ubuntu-desktop-minimal</code> (the "
         "desktop, Firefox and the basic tools), the other the full "
         "<code>ubuntu-desktop</code> with the office and media applications."),
        ("Kernel", "Armbian's kernel branch. %s follows recent mainline kernels; "
         "%s is Rockchip's own kernel (Linux 6.1), offered for the UEFI image."
         % ("<code>edge</code>", "<code>vendor</code>")),
        ("Source", "This list is %s in the build repository." % link(
            BUILD_REPO + "/blob/main/boards.conf", "boards.conf")),
    ])))
    return "\n".join(out)


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
            page_js="",
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
