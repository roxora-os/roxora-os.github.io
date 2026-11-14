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
"""The Roxora Imager page, a landing page like the home page.

A Hero with the app's icon, what it does, and the download for the
visitor's system as the one primary action (assets/imager.js picks it; the
browser already says what it runs on, nothing is sent anywhere). Without
JavaScript, or on a system it cannot tell, the action goes to the list of
every package. Then a picture of the app beside what it does, every
package by system, the other ways to install, what each system asks on
first start, and a few things worth knowing.

The release offered is the newest one that is not a beta; before there is
one it is the newest beta. A newer beta is mentioned, not offered.
"""

import json
import re

from markup import (IMAGER_REPO, SITE, beta_label, button, code_block, content, date,
                    empty_state, esc, fold, landing_head, landing_part, landing_sheet, link, size)

# Roxora Imager's packages: (system, name, [(architecture key, its name,
# [(format, file name pattern)])]). The first format of an architecture is
# the one the Hero offers. A file the release does not have is left out,
# and so is a system with none.
PLATFORMS = [
    ("windows", "Windows", [
        ("x64", "x64", [("Installer", r"-windows-x64-setup\.exe$"),
                        ("Zip", r"-windows-x64\.zip$")])]),
    ("macos", "macOS", [
        ("arm64", "Apple silicon", [("Disk image", r"-macos-arm64\.dmg$")]),
        ("x86_64", "Intel", [("Disk image", r"-macos-x86_64\.dmg$")])]),
    ("linux", "Linux", [
        ("x86_64", "x86_64", [("AppImage", r"-linux-x86_64\.AppImage$"),
                              (".deb", r"_amd64\.deb$"),
                              (".rpm", r"\.x86_64\.rpm$")]),
        ("arm64", "arm64", [("AppImage", r"-linux-arm64\.AppImage$"),
                            (".deb", r"_arm64\.deb$"),
                            (".rpm", r"\.aarch64\.rpm$")])]),
]
INSTALL_SCRIPT = "curl -fsSL https://raw.githubusercontent.com/roxora-os/imager/main/install.sh | sh"

FEATURES = [
    ("Download and check", "Lists the Roxora images for your board, downloads the one you "
     "choose and checks it against the SHA-256 the release publishes."),
    ("Write and read back", "Writes it to an SD card or USB drive in this computer, then reads "
     "the card back and compares it, so a bad card shows before the board does."),
    ("Write the board over USB", "With the board in Maskrom mode on its USB-C port, writes its "
     "eMMC, SPI flash or SD card directly, and the U-Boot a board needs in its SPI flash."),
]


def packages(assets):
    """{system: (name, [(arch, arch name, [(format, asset)])])}, only what
    the release has."""
    out = {}
    for key, name, archs in PLATFORMS:
        rows = []
        for arch, arch_name, kinds in archs:
            found = [(fmt, a) for fmt, pattern in kinds
                     for a in [next((a for a in assets if re.search(pattern, a["name"])), None)] if a]
            if found:
                rows.append((arch, arch_name, found))
        if rows:
            out[key] = (name, rows)
    return out


def hero(rel, pkgs):
    version = rel["tag"].lstrip("v")
    beta = rel.get("beta")
    newer = ""
    if beta:
        newer = (' A newer beta, %s, is on %s.'
                 % (esc(beta["tag"].lstrip("v")), link(beta["url"], "its release page")))
    # What the Hero's button offers for each system: the first format of
    # each architecture. imager.js reads this.
    offer = {key: {arch: {"url": found[0][1]["url"], "text": "Download for %s" % name,
                          "what": "%s for %s, %s" % (found[0][0], arch_name, size(found[0][1]["size"]))}
                   for arch, arch_name, found in rows}
             for key, (name, rows) in pkgs.items()}
    return (
        '<div class="pf-v6-c-hero landing-hero">\n<div class="pf-v6-c-hero__body">\n'
        '<img class="imager-icon" src="/assets/brand/roxora-imager.svg" width="64" height="64" alt="">\n'
        '<h1 class="pf-v6-c-title pf-m-3xl landing-hero__title" id="what-title">Roxora Imager</h1>\n'
        '<p class="landing-hero__text">Downloads a Roxora image, checks it and writes it to an SD '
        'card, a USB drive or the board itself over USB, then reads it back.</p>\n'
        '<div class="landing-hero__actions">'
        '<a class="pf-v6-c-button pf-m-primary pf-m-display-lg" id="imager-get" href="#downloads">'
        '<span class="pf-v6-c-button__text">Download</span></a>'
        '<a class="pf-v6-c-button pf-m-secondary pf-m-display-lg" id="imager-all" href="#downloads" hidden>'
        '<span class="pf-v6-c-button__text">All downloads</span></a></div>\n'
        '<p class="landing-hero__meta"><span id="imager-what" hidden></span>'
        'Version %s%s, %s. %s.%s</p>\n'
        '<script type="application/json" id="imager-offer">%s</script>\n'
        '</div>\n</div>'
        % (esc(version), " " + beta_label() if rel["prerelease"] else "", esc(date(rel["date"])),
           link(rel["url"], "Release notes"), newer,
           json.dumps(offer, separators=(",", ":")).replace("</", "<\\/")))


def picture():
    """The app, light or dark with the page. Screenshots from Roxora
    Imager's own CI (the screenshots artifact of roxora-os/imager)."""
    alt = ("Roxora Imager at its Destination step: write to an SD card or USB drive, or to the "
           "board's storage over USB, with the drives it found listed below.")
    imgs = "".join(
        '<img class="imager-shot imager-shot--%s" src="/assets/imager/roxora-imager-destination-%s.webp" '
        'width="1100" height="760" alt="%s" loading="lazy">' % (t, t, esc(alt) if t == "light" else "")
        for t in ("light", "dark"))
    cards = "".join(
        '<div class="pf-v6-c-card pf-m-compact imager-feature">'
        '<div class="pf-v6-c-card__title"><h3 class="pf-v6-c-card__title-text">%s</h3></div>'
        '<div class="pf-v6-c-card__body">%s</div></div>' % (esc(t), esc(b)) for t, b in FEATURES)
    return ('<div class="imager-about"><figure class="imager-figure">%s</figure>'
            '<div class="imager-features">%s</div></div>' % (imgs, cards))


def downloads(rel, pkgs):
    cards = []
    for key, (name, rows) in pkgs.items():
        groups = "".join(
            '<div class="pf-v6-c-description-list__group">'
            '<dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text">%s</span></dt>'
            '<dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text">%s</div></dd></div>'
            % (esc(arch_name), "".join(
                '<span class="imager-file"><a class="download-link" href="%s">%s</a> '
                '<span class="meta-inline">%s</span></span>'
                % (esc(a["url"]), esc(fmt), esc(size(a["size"]))) for fmt, a in found))
            for arch, arch_name, found in rows)
        cards.append(
            '<div class="pf-v6-l-grid__item"><div class="pf-v6-c-card pf-m-full-height imager-system" '
            'data-platform="%s"><div class="pf-v6-c-card__title"><h3 class="pf-v6-c-card__title-text">%s</h3></div>'
            '<div class="pf-v6-c-card__body"><dl class="pf-v6-c-description-list imager-files">%s</dl></div></div></div>' % (key, esc(name), groups))
    out = ('<div class="pf-v6-l-grid pf-m-gutter pf-m-all-4-col-on-lg">%s</div>' % "".join(cards))
    sums = next((a for a in rel["assets"] if a["name"] == "SHA256SUMS"), None)
    if sums:
        out += ('<p class="imager-sums">%s has the SHA-256 of every file. To check a package, '
                'in the directory that holds it and SHA256SUMS:</p>%s'
                % (link(sums["url"], "SHA256SUMS"), code_block("sha256sum -c --ignore-missing SHA256SUMS")))
    return out


def other_ways():
    return '<div class="pf-v6-c-card"><div class="pf-v6-c-card__body"><div class="folds">%s</div></div></div>' % "\n".join([
        fold("Install script, macOS and Linux", content(
            "<p>The script picks the package for the system, checks it against the SHA-256 "
            "GitHub publishes for it and installs it.</p>") + copy_block(INSTALL_SCRIPT, "the command"),
            fid="install-script", search="Install script"),
        fold("Homebrew, macOS", copy_block(
            "brew trust gahingwoo/tap\nbrew install --cask gahingwoo/tap/roxora-imager", "the commands")
            + content("<p>Update with <code>brew upgrade --cask roxora-imager</code>; the app "
                      "does not update itself.</p>"), fid="homebrew", search="Homebrew"),
        fold("In the browser, nothing to install", content(
            "<p>The same app runs in Chrome or Edge at %s. A browser cannot open a disk, so it "
            "writes a board's eMMC or SPI flash over USB only, not an SD card in the "
            "computer.</p>" % link(SITE + "/imager/", "roxora-os.github.io/imager")),
            fid="web", search="In the browser"),
    ])


FIRST_START = [
    ("windows", "Windows", "SmartScreen says <q>Windows protected your PC</q>, because the "
     "installer is not signed. Choose <strong>More info</strong>, then <strong>Run "
     "anyway</strong>."),
    ("macos", "macOS", "The app is not notarized, so macOS says it cannot be opened. On macOS 15 "
     "and later, open it once and choose <strong>Done</strong>, then in System Settings, Privacy "
     "&amp; Security, choose <strong>Open Anyway</strong>. On macOS 14 and earlier, right-click "
     "the app in Applications and choose <strong>Open</strong>."),
    ("linux", "Linux", "Install the .deb or .rpm with the package manager, or make the AppImage "
     "executable and run it. Writing an SD card asks for your password."),
]


def first_start():
    return '<div class="pf-v6-l-grid pf-m-gutter pf-m-all-4-col-on-lg">%s</div>' % "".join(
        '<div class="pf-v6-l-grid__item"><div class="pf-v6-c-card pf-m-full-height first-start" '
        'id="first-start-%s" data-platform="%s"><div class="pf-v6-c-card__title">'
        '<h3 class="pf-v6-c-card__title-text">%s</h3></div><div class="pf-v6-c-card__body">%s</div>'
        '</div></div>' % (key, key, esc(name), body) for key, name, body in FIRST_START)


def good_to_know(rel):
    rows = [
        ("Code signing", "The Windows and macOS packages are not signed with a publisher's "
         "certificate yet. The %s says who may sign and what." % link("/code-signing/", "code signing policy")),
        ("Writing over USB", "Maskrom mode needs a driver on Windows and a udev rule for the "
         "AppImage on Linux; %s has both." % link(IMAGER_REPO + "/blob/main/docs/install.md",
                                                  "Installing Roxora Imager")),
    ]
    # What has been tried on real hardware; keep this in step with the
    # hardware test reports (docs/hardware-test.md in roxora-os/build).
    if rel["prerelease"]:
        rows.append(("Tested so far", "Writing an SD card on macOS with 0.1.3: the card was written "
                     "and read back correctly. Windows, Linux and writing a board over USB have not "
                     "been tried on hardware yet."))
    return ('<div class="pf-v6-c-card"><div class="pf-v6-c-card__body">'
            '<dl class="pf-v6-c-description-list pf-m-horizontal-on-md kv">%s</dl></div></div>' % "".join(
                '<div class="pf-v6-c-description-list__group"><dt class="pf-v6-c-description-list__term">'
                '<span class="pf-v6-c-description-list__text">%s</span></dt>'
                '<dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text">'
                '%s</div></dd></div>' % (esc(t), v) for t, v in rows))


def render(rel):
    """rel: the release of roxora-os/imager to offer, as fetch_upstream.py
    stored it, or None."""
    if not rel or not rel["assets"]:
        return landing_sheet("Roxora Imager", [landing_part("get", "Get Roxora Imager", empty_state(
            "No release yet",
            "Roxora Imager has not published any packages. When it does they are "
            "listed here and on %s." % link(IMAGER_REPO + "/releases", "its releases page")))])
    pkgs = packages(rel["assets"])
    return landing_sheet("Roxora Imager", [
        landing_part("what", "Roxora Imager", hero(rel, pkgs), "landing-part--hero"),
        landing_part("about", "What it does", landing_head("about", "What it does") + picture()),
        landing_part("downloads", "Downloads", landing_head(
            "downloads", "Downloads", ("All releases", IMAGER_REPO + "/releases")) + downloads(rel, pkgs)),
        landing_part("install", "Other ways to install",
                     landing_head("install", "Other ways to install") + other_ways()),
        landing_part("first-start", "First start", landing_head("first-start", "First start")
                     + first_start()),
        landing_part("good-to-know", "Good to know", landing_head("good-to-know", "Good to know")
                     + good_to_know(rel)),
    ])


def copy_block(text, what):
    """A code block with a button that copies it."""
    return ('<div class="copy-block">%s<button class="pf-v6-c-button pf-m-secondary pf-m-small js-only" '
            'type="button" data-copy aria-label="Copy %s"><span class="pf-v6-c-button__text">Copy</span>'
            '</button></div>' % (code_block(esc(text)), esc(what)))


def subtitle(rel):
    if not rel:
        return "No release yet"
    return "Version %s%s" % (rel["tag"].lstrip("v"), ", beta" if rel["prerelease"] else "")
