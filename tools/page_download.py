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
"""The Download page.

With JavaScript it is a chooser, after Roxora Imager's Board and Image
steps: pick the board, then the Ubuntu version, the desktop and the kernel,
and the page shows that one file. assets/download.js runs it from the JSON
this module puts in the page, and fills the result card whose markup is
here.

Without JavaScript the chooser is not shown and the list of every file,
which the chooser keeps folded, is open instead.

What is offered: the newest release, and the newest beta when it is newer
than that release. A beta is only shown when the visitor chooses it. The
defaults are the newest Ubuntu LTS, the command line image and the edge
kernel: os_list.ubuntu_order and os_list.flavor_order put those first. The
command line image is the default flavor because it is the smallest, every
board has one, and it is the base the desktop images add to.

A link can name the choice: /download/?board=radxa-rock-4d&ubuntu=26.04
(also kernel=, flavor= and release=). The anchors the old page had,
#image-<board>-<codename>-<branch>, are the ids of the rows in the list of
files, and the chooser reads them too.
"""

import json

import os_list
from markup import (BUILD_REPO, CARET, EDK2_RK3576, UBUNTU, alert, beta_label, board_filter, card,
                    code_block, content, copyable, date, empty_state, esc, fold, kv, link, size,
                    table)

# What the page says about an image's flavor.
FLAVOR_ABOUT = {
    "cli": "Command line, no desktop",
    "gnome-minimal": "Minimal GNOME desktop (ubuntu-desktop-minimal)",
    "gnome": "GNOME desktop (ubuntu-desktop)",
}



def offered(catalogs):
    """The releases the chooser offers, the default first: the newest
    release, then the newest beta if it is newer. Before the first release
    there is only the newest beta. Catalogs arrive newest first."""
    if not catalogs:
        return []
    stable = next((c for c in catalogs if not c["release"]["prerelease"]), None)
    if stable is None:
        return [catalogs[0]]
    return [stable] + ([catalogs[0]] if catalogs[0] is not stable else [])


def ubuntu_short(img):
    """26.04 LTS for an image of the catalog."""
    version = img.get("ubuntu_version") or UBUNTU.get(img["release"], (img["release"],))[0]
    lts = UBUNTU.get(img["release"], (None, not os_list.ubuntu_order(version)[0]))[1]
    return version + (" LTS" if lts else "")


def image_order(catalog):
    """A catalog's images as the pages list them: boards in the catalog's
    order, and for each the default choice first."""
    boards = list(dict.fromkeys(i["board"] for i in catalog["images"]))
    return sorted(catalog["images"], key=lambda i: (
        boards.index(i["board"]), os_list.ubuntu_order(i.get("ubuntu_version"))[:2],
        os_list.flavor_order(i), i["branch"] != "edge", i["branch"]))


def anchor(img):
    """The id of an image's row in the list of files. A command line image
    keeps the anchor it had before the desktop images existed."""
    fl = os_list.flavor(img)
    return "image-%s-%s-%s%s" % (img["board"], img["release"], img["branch"],
                                 "" if fl == "cli" else "-" + fl)


def image_words(img):
    """Ubuntu 26.04 LTS, command line, edge kernel 7.3.4"""
    return "Ubuntu %s, %s, %s kernel %s" % (
        ubuntu_short(img), os_list.flavor_name(img, sentence=True), img["branch"], img["kernel"])


def board_link(board):
    return "/download/?board=%s" % board


# ---- the chooser's data ----

def chooser_data(offer):
    """What assets/download.js needs, in the order the choices are listed."""
    images, boards, ubuntus, flavors, kernels = [], {}, {}, {}, {}
    for cat in offer:
        for img in image_order(cat):
            boards.setdefault(img["board"], {
                "id": img["board"], "name": img["board_name"], "vendor": img["vendor"],
                "soc": img["soc"].upper()})
            ubuntus[img.get("ubuntu_version") or img["release"]] = (
                os_list.ubuntu_order(img.get("ubuntu_version"))[:2], ubuntu_short(img))
            fl = os_list.flavor(img)
            flavors[fl] = (os_list.flavor_order(img), os_list.flavor_name(img))
            kernels[img["branch"]] = (img["branch"] != "edge", img["branch"])
            entry = {
                "release": cat["release"]["tag"], "board": img["board"],
                "ubuntu": img.get("ubuntu_version") or img["release"],
                "codename": img["release"], "ubuntuName": ubuntu_short(img),
                "flavor": fl, "flavorName": os_list.flavor_name(img, sentence=True),
                "kernel": img["branch"], "kernelVersion": img["kernel"],
                "file": img["file"], "size": size(img["size"]),
                "written": size(img["extract_size"]), "sha256": img["sha256"],
                "anchor": anchor(img),
            }
            # One file to download, or the parts of an image larger than
            # GitHub takes as one release file (release contract).
            if img.get("parts"):
                entry["parts"] = [{"file": p["file"], "url": p["url"], "size": size(p["size"]),
                                   "sha256": p["sha256"]} for p in img["parts"]]
            else:
                entry["url"] = img["url"]
            if img.get("verify_url"):
                entry["verify"] = img["verify_url"]
            if img.get("spi"):
                spi = img["spi"]
                entry["spi"] = {"file": spi["file"], "url": spi["url"],
                                "size": size(spi["size"]), "sha256": spi["sha256"]}
            if img.get("firmware") == "uefi":
                entry["uefi"] = True
            images.append(entry)

    def ordered(d):
        return [[k, v[1]] for k, v in sorted(d.items(), key=lambda kv_: kv_[1][0])]
    return {
        "releases": [{"tag": c["release"]["tag"], "version": c["release"]["version"],
                      "date": date(c["release"]["date"]), "beta": c["release"]["prerelease"],
                      "url": c["release"]["url"]} for c in offer],
        "boards": list(boards.values()),
        "ubuntus": ordered(ubuntus), "flavors": ordered(flavors),
        "kernels": [k for k, _ in ordered(kernels)],
        "images": images,
    }


# ---- step 1: the board ----

def board_step(offer):
    """Search, the vendors with their counts and the boards, as Roxora
    Imager's Board step has them."""
    default = offer[0]
    boards = {}
    for cat in offer:
        for img in image_order(cat):
            boards.setdefault(img["board"], []).append((cat, img))
    vendors = {}
    for imgs in boards.values():
        vendors.setdefault(imgs[0][1]["vendor"], 0)
        vendors[imgs[0][1]["vendor"]] += 1

    rows = []
    for board, imgs in boards.items():
        first = imgs[0][1]
        # What the row says is about the default release when the board is
        # in it; a board only a beta has says so.
        mine = [i for c, i in imgs if c is default] or [i for _, i in imgs]
        versions = list(dict.fromkeys(ubuntu_short(i) for i in mine))
        beta = "" if any(c is default for c, _ in imgs) or not imgs[0][0]["release"]["prerelease"] \
            else " " + beta_label()
        rows.append(
            '<tr class="pf-v6-c-table__tr pf-m-clickable" data-board="%(id)s" data-vendor="%(vendor)s" '
            'data-filter="%(search)s">'
            '<td class="pf-v6-c-table__td pf-v6-c-table__check">'
            '<label class="pf-v6-c-radio pf-m-standalone"><input class="pf-v6-c-radio__input" type="radio" '
            'name="board" value="%(id)s" aria-label="%(name)s"></label></td>'
            '<th class="pf-v6-c-table__th board-name" scope="row">%(name)s'
            '<span class="meta board-soc">%(soc)s</span></th>'
            '<td class="pf-v6-c-table__td board-soc-col">%(soc)s</td>'
            '<td class="pf-v6-c-table__td">Ubuntu %(versions)s%(beta)s</td></tr>' % dict(
                id=esc(board), vendor=esc(first["vendor"]), name=esc(first["board_name"]),
                soc=esc(first["soc"].upper()),
                search=esc(" ".join([first["board_name"], first["vendor"], first["soc"], board]).lower()),
                versions=esc(", ".join(versions)), beta=beta))

    table = (
        '<table class="pf-v6-c-table pf-m-compact board-table" aria-label="Boards" id="board-table" '
        'data-filter-list>'
        '<thead class="pf-v6-c-table__thead"><tr class="pf-v6-c-table__tr">'
        '<td class="pf-v6-c-table__td pf-v6-c-table__check"></td>'
        '<th class="pf-v6-c-table__th" scope="col">Board</th>'
        '<th class="pf-v6-c-table__th board-soc-col" scope="col">SoC</th>'
        '<th class="pf-v6-c-table__th" scope="col">Images</th></tr></thead>\n'
        '<tbody class="pf-v6-c-table__tbody">\n%s\n</tbody></table>' % "\n".join(rows))
    body = ('<p class="step-lead">Choose the board you want to install Roxora on.</p>\n'
            + board_filter(vendors, table))
    # Once a board is chosen the step folds to one line, as the step list of
    # the imager does on a narrow screen.
    summary = ('<span class="step-summary" id="board-summary"></span>'
               '<button class="pf-v6-c-button pf-m-link pf-m-inline step-change" type="button" '
               'id="board-change"><span class="pf-v6-c-button__text">Change</span></button>')
    return card("board", "Board", body, rail=False, cls="chooser-step js-only", title_after=summary)


# ---- step 2: the image ----

def toggle_row(key, name, note=""):
    """One choice of the image step. The buttons are filled in by
    download.js: which ones there are depends on the board."""
    return ('<div class="choice" id="choice-%s" hidden>'
            '<span class="choice__label" id="choice-%s-label">%s</span>'
            '<div class="choice__main"><div class="pf-v6-c-toggle-group" role="group" '
            'aria-labelledby="choice-%s-label" data-choice="%s"></div>%s</div></div>'
            % (key, key, esc(name), key, key,
               '<span class="meta">%s</span>' % note if note else ""))


def image_step():
    body = (
        toggle_row("release", "Release",
                   "A beta is what comes next. The newest release is the safer choice.")
        + toggle_row("ubuntu", "Ubuntu")
        + toggle_row("flavor", "Desktop",
                     "Command line is the default: the smallest image, and the one every board "
                     "has. The GNOME images add Ubuntu's desktop.")
        + toggle_row("kernel", "Kernel",
                     "edge follows recent mainline kernels. vendor is Rockchip's own kernel."))
    return card("image", "Image", body, rail=False, cls="chooser-step js-only", extra="hidden")


# ---- step 3: the file ----

def result_step():
    """The one file the choices lead to. download.js fills the elements
    that carry an id."""
    needs_spi = alert(
        "warning", "This board needs U-Boot in its SPI flash first",
        '<p>It does not start from an SD card until its SPI flash holds U-Boot. Unless it '
        'already does, write <a id="dl-spi-link" href="%s"></a> (<span id="dl-spi-size"></span>) '
        'to the SPI flash before the first boot. %s</p>'
        '<p class="hash-line">SHA-256 <code class="hash" id="dl-spi-sha"></code></p>'
        % (BUILD_REPO + "/releases",
           '<a id="dl-spi-more" href="/boards/">How to write it</a>.'),
        'id="dl-spi" hidden')
    needs_uefi = alert(
        "warning", "This image needs UEFI firmware on the board",
        "<p>It has no bootloader of its own. The board's SPI flash must hold UEFI firmware, "
        'such as %s, before it boots. <a id="dl-uefi-more" href="/boards/">About this image</a>.</p>'
        % link(EDK2_RK3576, "edk2-rk3576"),
        'id="dl-uefi" hidden')
    is_beta = alert(
        "info", "This is a beta",
        "<p>It is what comes next and may change. The newest release is the safer choice.</p>",
        'id="dl-beta" hidden')
    # An image in parts: the button leads to Roxora Imager, and the parts
    # are listed for joining by hand. download.js fills the list.
    in_parts = (
        '<div class="result-parts" id="dl-parts" hidden>\n'
        '<p>This image is larger than GitHub takes as one file, so the release has it in '
        '<span id="dl-parts-count"></span> parts. %s 0.1.5 and later downloads them, joins '
        'them and checks the result. To do it by hand, download every part into one '
        'directory:</p>\n'
        '<ol class="parts-list" id="dl-parts-list"></ol>\n'
        '<p>Then join them in order. The SHA-256 below is that of the joined file.</p>\n'
        '%s\n'
        '<p class="meta">On Windows, in the Command Prompt: <code>copy /b</code> with the parts '
        'joined by <code>+</code>, then the file name. %s</p>\n'
        '</div>'
        % (link("/roxora-imager/", "Roxora Imager"),
           code_block('cat <span data-file></span>.part* &gt; <span data-file></span>'),
           link("/docs/install/#desktop-images-come-in-parts", "Installing Roxora has the steps.")))
    body = (
        '<div class="result">\n'
        '<p class="result-name" id="dl-name"></p>\n'
        '<p class="result-sub"><span id="dl-sub"></span> <span class="result-labels" id="dl-labels"></span></p>\n'
        '%s\n%s\n%s\n'
        '<div class="result-action">'
        '<a class="pf-v6-c-button pf-m-primary pf-m-display-lg download-link" id="dl-button" href="%s">'
        '<span class="pf-v6-c-button__text" id="dl-button-text">Download</span></a>'
        '<span class="result-size" id="dl-size"></span></div>\n'
        '%s\n'
        '%s\n'
        '</div>'
        % (is_beta, needs_spi, needs_uefi, BUILD_REPO + "/releases", in_parts,
           kv([("File", '<a id="dl-file" class="hash download-link" href="%s"></a>'
                '<span id="dl-file-name" class="hash" hidden></span>' % (BUILD_REPO + "/releases")),
               ("SHA-256", copyable("", "the SHA-256", tid="dl-sha")),
               ("Release", '<span id="dl-release"></span><span class="meta">'
                '<a id="dl-notes" href="%s">Release notes</a>'
                '<span id="dl-verify-wrap">, <a id="dl-verify" href="%s">image checks</a></span></span>'
                % (BUILD_REPO + "/releases", BUILD_REPO + "/releases"))])))
    return card("result", "Download", body, rail=False, cls="chooser-step js-only", extra="hidden")


# ---- what to do with the file ----

def write_card(first_file):
    by_hand = (
        "<p>Each file has a <code>.sha256</code> file beside it on the release page. With both "
        "in the same directory, check the download:</p>"
        + code_block('sha256sum -c <span data-file>%s</span>.sha256' % esc(first_file))
        + "<p>Then write it. <code>/dev/sdX</code> is the card (find it with <code>lsblk</code>); "
        "everything on it is erased.</p>"
        + code_block('xz -dc <span data-file>%s</span> | sudo dd of=/dev/sdX bs=4M conv=fsync '
                     'status=progress' % esc(first_file)))
    body = content(
        "<ul>"
        "<li>%s downloads the image, checks it, writes it and reads it back. With it you do not "
        "need to download anything here.</li>"
        "<li>%s can list the Roxora images that are one file to download, or write the file "
        "you downloaded or joined.</li>"
        "<li>Any other tool that writes <code>.img.xz</code> files works, to an SD card, USB "
        "drive, eMMC or NVMe.</li>"
        "</ul>"
        "<p>The first login is user <code>roxora</code> with the password <code>roxora</code>; "
        "you are asked to choose a new password straight away. %s has every step.</p>"
        % (link("/roxora-imager/", "Roxora Imager"), link("/rpi-imager/", "Raspberry Pi Imager"),
           link("/docs/install/", "Installing Roxora"))
    ) + fold("Check and write it from the command line", content(by_hand), fid="by-hand")
    return card("write", "Write it to a card", body, rail=False)


# ---- every file ----

def files_table(cat):
    rows = []
    for img in image_order(cat):
        extra = ""
        if img.get("spi"):
            spi = img["spi"]
            extra += ('<span class="meta">SPI bootloader, needed first: %s (%s)</span>'
                      '<span class="meta hash">SHA-256 %s</span>'
                      % (link(spi["url"], spi["file"]), esc(size(spi["size"])), esc(spi["sha256"])))
        if img.get("firmware") == "uefi":
            extra += '<span class="meta">Needs UEFI firmware on the board first.</span>'
        if img.get("parts"):
            # No file of that name is in the release: the parts are, and
            # joined in order they make it.
            name = '<span class="hash">%s</span>' % esc(img["file"])
            extra = ('<span class="meta">In %d parts, to join in order (%s):</span>%s'
                     % (len(img["parts"]),
                        link("/docs/install/#desktop-images-come-in-parts", "how"),
                        "".join('<span class="meta">Part %d: <a class="download-link" href="%s">%s</a> '
                                '(%s)</span><span class="meta hash">SHA-256 %s</span>'
                                % (n, esc(p["url"]), esc(p["file"]), esc(size(p["size"])),
                                   esc(p["sha256"]))
                                for n, p in enumerate(img["parts"], 1)))) + extra
            sha = "SHA-256 of the joined file %s" % img["sha256"]
        else:
            name = '<a class="hash download-link" href="%s">%s</a>' % (esc(img["url"]), esc(img["file"]))
            sha = "SHA-256 %s" % img["sha256"]
        rows.append((anchor(img), [
            '%s<span class="meta">%s</span>' % (esc(img["board_name"]), esc(image_words(img))),
            '%s<span class="meta hash">%s</span>%s' % (name, esc(sha), extra),
            esc(size(img["size"])),
        ]))
    return table("files-table", ["Image", "File", "Size"], rows, stack="lg")


def release_line(cat):
    rel = cat["release"]
    return "Roxora %s%s" % (rel["version"], " beta" if rel["prerelease"] else "")


def files_card(catalogs, offer):
    """Every file of the releases on offer, then the releases before them.
    The first list is open when there is no JavaScript: it is the page then."""
    folds = []
    for n, cat in enumerate(offer):
        rel = cat["release"]
        summary = "%s<span class=\"fold__meta\">%s, %d images</span>" % (
            esc(release_line(cat)), esc(date(rel["date"])), len(cat["images"]))
        about = ('<p class="meta files-about">%s%s, %s.</p>' % (
            "A beta: it is what comes next and may change. " if rel["prerelease"] else "",
            link(rel["url"], "Release notes"),
            link("/catalog/%s.json" % rel["tag"], "catalog")))
        folds.append(fold(summary, about + files_table(cat), fid="files-" + rel["tag"],
                          opened=n == 0, cls="js-closed" if n == 0 else ""))
    older = [c for c in catalogs if not any(c is o for o in offer)]
    if older:
        folds.append(fold(
            'Earlier releases<span class="fold__meta">%d</span>' % len(older),
            kv([(release_line(c), '%s<span class="meta">%s, %d images, %s</span>' % (
                link(c["release"]["url"], "Files and release notes"),
                esc(date(c["release"]["date"])), len(c["images"]),
                link("/catalog/%s.json" % c["release"]["tag"], "catalog"))) for c in older]),
            fid="earlier"))
    # The first list starts open for a browser without JavaScript. With it
    # the chooser is the page, and the list is closed before it is painted.
    close = ('<script>document.querySelectorAll("details.js-closed").forEach('
             'function (d) { d.open = false; });</script>')
    return card("files", "All files", '<div class="folds">%s</div>%s' % ("\n".join(folds), close),
                rail=False, cls="files-section")


def render(catalogs):
    """The page's body and the JSON for download.js (None before the first
    release)."""
    if not catalogs:
        return card("releases", "Releases", empty_state(
            "No releases yet",
            "Roxora has not published any images. The first ones are being built "
            "for the boards on the %s page. When a release is published it is listed "
            "here and on %s." % (link("/boards/", "Boards"),
                                 link(BUILD_REPO + "/releases", "the releases page"))),
            rail=False), None
    offer = offered(catalogs)
    data = chooser_data(offer)
    out = [
        '<p class="nojs-only page-lead">Every file of the newest release is listed below. With '
        'JavaScript on, this page asks for your board and shows the one file for it.</p>',
        '<div class="chooser">',
        board_step(offer), image_step(), result_step(),
        '</div>',
        '<div class="after-chooser">',
        write_card(image_order(offer[0])[0]["file"]),
        files_card(catalogs, offer),
        '</div>',
        '<script type="application/json" id="download-data">%s</script>'
        % json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"),
    ]
    return "\n".join(out), data


def subtitle(catalogs):
    if not catalogs:
        return "No releases yet"
    return release_line(offered(catalogs)[0])
