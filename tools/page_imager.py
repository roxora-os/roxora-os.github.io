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
"""The Roxora Imager page.

It leads with the packages of the newest release, one block per system.
site.js works out which system the visitor is on and shows that block
alone, with the others one click away; without JavaScript all of them are
listed. The other ways to install and what each system asks on first start
are folded below.
"""

import re

from markup import (IMAGER_REPO, SITE, beta_label, button, card, code_block, content,
                    date, empty_state, esc, fold, link, size)

# Roxora Imager's packages: (system, name, [(architecture, what the button
# says, [(format, file name pattern)])]). The first format of an
# architecture is its button; the others are listed after it. A file the
# release does not have is left out, and so is a system with none.
PLATFORMS = [
    ("windows", "Windows", [
        ("x64", "Download for Windows", [("Installer", r"-windows-x64-setup\.exe$"),
                                         ("Zip", r"-windows-x64\.zip$")])]),
    ("macos", "macOS", [
        ("arm64", "Download for Apple silicon", [("Disk image", r"-macos-arm64\.dmg$")]),
        ("x86_64", "Download for Intel Macs", [("Disk image", r"-macos-x86_64\.dmg$")])]),
    ("linux", "Linux", [
        ("x86_64", "Download AppImage, x86_64", [("AppImage", r"-linux-x86_64\.AppImage$"),
                                                 (".deb", r"_amd64\.deb$"),
                                                 (".rpm", r"\.x86_64\.rpm$")]),
        ("arm64", "Download AppImage, arm64", [("AppImage", r"-linux-arm64\.AppImage$"),
                                               (".deb", r"_arm64\.deb$"),
                                               (".rpm", r"\.aarch64\.rpm$")])]),
]
INSTALL_SCRIPT = "curl -fsSL https://raw.githubusercontent.com/roxora-os/imager/main/install.sh | sh"


def platform_blocks(assets):
    blocks = []
    for key, name, archs in PLATFORMS:
        rows = []
        for arch, text, kinds in archs:
            found = [(label, a) for label, pattern in kinds
                     for a in [next((a for a in assets if re.search(pattern, a["name"])), None)] if a]
            if not found:
                continue
            _, main = found[0]
            others = ", ".join(
                '<span class="platform__other"><a class="download-link" href="%s">%s</a> (%s)</span>'
                % (esc(a["url"]), esc(label), esc(size(a["size"]))) for label, a in found[1:])
            rows.append(
                '<div class="platform__arch" data-arch="%s">%s'
                '<span class="meta"><span class="hash">%s</span>, %s%s</span></div>'
                % (arch, button(main["url"], text, "secondary", cls="download-link"), esc(main["name"]),
                   esc(size(main["size"])), ". Also as " + others if others else ""))
        if rows:
            blocks.append('<div class="platform" data-platform="%s"><h3 class="platform__name">%s</h3>%s</div>'
                          % (key, esc(name), "".join(rows)))
    return blocks


def render(rel):
    """rel: the newest release of roxora-os/imager as fetch_upstream.py
    stored it, or None."""
    if not rel or not rel["assets"]:
        return card("get", "Get Roxora Imager", empty_state(
            "No release yet",
            "Roxora Imager has not published any packages. When it does they are "
            "listed here and on %s." % link(IMAGER_REPO + "/releases", "its releases page")),
            rail=False)
    assets = rel["assets"]
    version = rel["tag"].lstrip("v")
    sums = next((a for a in assets if a["name"] == "SHA256SUMS"), None)

    lead = ('<p class="page-lead">Roxora Imager downloads a Roxora image, checks it, writes it '
            'to an SD card or to the board over USB, and reads it back.</p>'
            '<p class="imager-release">Version %s%s<span class="meta">%s, %s</span></p>'
            % (esc(version), " " + beta_label() if rel["prerelease"] else "",
               esc(date(rel["date"])), link(rel["url"], "release notes")))
    get = (lead
           + '<div class="platforms" id="platforms">'
           '<p class="platforms__mine js-only" id="platforms-mine" hidden>For this computer</p>'
           + "".join(platform_blocks(assets))
           + '<p class="platforms__all js-only" id="platforms-all" hidden>'
           '<button class="pf-v6-c-button pf-m-link pf-m-inline" type="button">'
           '<span class="pf-v6-c-button__text">Other systems</span></button></p></div>')
    out = [card("get", "Get Roxora Imager", get, rail=False)]

    ways = [
        fold("Install script, macOS and Linux", content(
            "<p>The script picks the package for the system, checks it against the SHA-256 "
            "GitHub publishes for it and installs it.</p>") + copy_block(INSTALL_SCRIPT, "the command"),
            fid="install-script", search="Install script"),
        fold("Homebrew, macOS", copy_block(
            "brew trust gahingwoo/tap\nbrew install --cask gahingwoo/tap/roxora-imager", "the commands")
            + content("<p>Update with <code>brew upgrade --cask roxora-imager</code>; the app "
                      "does not update itself.</p>"), fid="homebrew", search="Homebrew"),
    ]
    if sums:
        ways.append(fold("Check a package you downloaded", content(
            "<p>%s has the SHA-256 of every file in the release. With the package in the same "
            "directory:</p>" % link(sums["url"], "SHA256SUMS"))
            + code_block("sha256sum -c --ignore-missing SHA256SUMS"), fid="checksums",
            search="Checksums"))
    ways.append(fold("In the browser, nothing to install", content(
        "<p>The same app runs in Chrome or Edge at %s. A browser cannot open a disk, so it "
        "writes a board's eMMC or SPI flash over USB only, not an SD card in the "
        "computer.</p>" % link(SITE + "/imager/", "roxora-os.github.io/imager")),
        fid="web", search="In the browser"))
    out.append(card("install", "Other ways to install", '<div class="folds">%s</div>' % "\n".join(ways),
                    rail=False))

    # What has been tried on real hardware; keep this in step with the
    # hardware test reports (docs/hardware-test.md in roxora-os/build).
    tested = ("<p>Writing an SD card has been tested on macOS with 0.1.3: the card was written "
              "and read back correctly. Windows, Linux and writing a board over USB (Maskrom) "
              "have not been tested on hardware yet.</p>" if rel["prerelease"] else "")
    first = [
        fold("Windows", content(
            "<p>Windows SmartScreen says <q>Windows protected your PC</q>, because the "
            "installer is not signed. Choose <strong>More info</strong>, then "
            "<strong>Run anyway</strong>.</p>"), fid="first-start-windows", cls="first-start",
            search="First start on Windows"),
        fold("macOS", content(
            "<p>The app is not notarized, so macOS says it cannot be opened. On macOS 15 "
            "and later, open it once and choose <strong>Done</strong>, then in System Settings, "
            "Privacy &amp; Security, choose <strong>Open Anyway</strong>. On macOS 14 and "
            "earlier, right-click the app in Applications and choose <strong>Open</strong>.</p>"),
            fid="first-start-macos", cls="first-start", search="First start on macOS"),
        fold("Linux", content(
            "<p>Install the .deb or .rpm with the package manager, or make the AppImage "
            "executable and run it. Writing an SD card asks for your password.</p>"),
            fid="first-start-linux", cls="first-start", search="First start on Linux"),
    ]
    notes = content(
        "%s<p>The Windows and macOS packages are not signed with a publisher's certificate yet: "
        "see the %s. Drivers for writing a board over USB (Maskrom mode) and the udev rule for "
        "the AppImage are in %s.</p>" % (
            tested, link("/code-signing/", "code signing policy"),
            link(IMAGER_REPO + "/blob/main/docs/install.md", "Installing Roxora Imager")))
    out.append(card("first-start", "First start",
                    '<div class="folds">%s</div>%s' % ("\n".join(first), notes), rail=False))
    return "\n".join(out)


def copy_block(text, what):
    """A code block with a button that copies it."""
    return ('<div class="copy-block">%s<button class="pf-v6-c-button pf-m-secondary pf-m-small js-only" '
            'type="button" data-copy aria-label="Copy %s"><span class="pf-v6-c-button__text">Copy</span>'
            '</button></div>' % (code_block(esc(text)), esc(what)))


def subtitle(rel):
    if not rel:
        return "No release yet"
    return "Version %s%s" % (rel["tag"].lstrip("v"), ", beta" if rel["prerelease"] else "")
