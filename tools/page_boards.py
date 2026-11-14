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
"""The Boards page, and the board cards of the home page.

One row per board of boards.conf: its name, SoC and maker, the Ubuntu
versions it has images for and how far they are tested. A row unfolds to the
images one by one, what the board needs before it boots, and a link to the
Download page with the board already chosen.
"""

import os_list
from markup import (BUILD_REPO, EDK2_RK3576, UBUNTU, button, card, esc, fold, kv, link,
                    status_label, table, tested_summary)

# What a board needs before a Roxora image boots on it, and its maker's
# documentation. Keep this in step with docs/install.md of roxora-os/build.
BOARD_NOTES = {
    "radxa-rock-4d": (
        "The boot ROM never starts from an SD card: it looks at SPI flash, UFS and USB, in "
        "that order. U-Boot has to be in the SPI flash first; it then boots a Roxora SD card. "
        "Each release has a U-Boot image for the SPI flash beside the board's image, and "
        "Roxora Imager writes it over USB.",
        ("https://docs.radxa.com/en/rock4/rock4d", "Radxa ROCK 4D documentation")),
    "armsom-cm5-io": (
        "No bootloader step: U-Boot is inside the image. The board starts from eMMC first, "
        "then from the SD card, so an SD card is not used while the eMMC holds a system "
        "that boots.",
        ("https://docs.armsom.org/armsom-cm5-io", "ArmSoM CM5-IO documentation")),
    "generic-rk3576-uefi": (
        "One image for any RK3576 board whose SPI flash holds UEFI firmware, such as "
        "edk2-rk3576. The image has no U-Boot: the firmware starts GRUB from the image's EFI "
        "system partition and hands the kernel the board's device tree. Write the firmware "
        "first, following its own instructions, then the image to an SD card, USB drive, "
        "eMMC or NVMe. It has booted in QEMU, not yet on a board.",
        (EDK2_RK3576, "edk2-rk3576")),
}


def ubuntu_short(codename):
    version, lts = UBUNTU.get(codename, (codename, False))
    return version + (" LTS" if lts else "")


def group(boards):
    """boards.conf rows by board, in the file's order, each board's rows
    with the default image first."""
    out = {}
    for b in boards:
        out.setdefault(b["board"], []).append(b)
    for rows in out.values():
        rows.sort(key=lambda b: (os_list.ubuntu_order(UBUNTU.get(b["release"], ("", False))[0])[:2],
                                 b["branch"] != "edge", b["branch"], os_list.flavor_order(b)))
    return out


def versions(rows):
    return ", ".join(dict.fromkeys(ubuntu_short(b["release"]) for b in rows))


def board_fold(board, rows, downloadable):
    b = rows[0]
    # One table row per Ubuntu release and kernel branch; its flavors share
    # the Images cell, grouped by status.
    images = {}
    for r in rows:
        images.setdefault((r["release"], r["branch"]), []).append(r)
    trs = []
    for (release, branch), same in images.items():
        cell = "".join(
            '<span class="status-group">%s %s</span>' % (
                esc(", ".join(os_list.flavor_name(i) for i in same if i["status"] == status)),
                status_label(status))
            for status in dict.fromkeys(i["status"] for i in same))
        trs.append([esc("Ubuntu " + ubuntu_short(release)), esc(branch), cell])
    note, docs = BOARD_NOTES.get(board, ("", None))
    body = table("board-images", ["Ubuntu", "Kernel", "Images"], trs, [30, 20, None], stack="sm")
    if note:
        body += '<p class="board-note">%s</p>' % esc(note)
    actions = []
    if board in downloadable:
        actions.append(button("/download/?board=%s" % board, "Download for this board", "secondary"))
    else:
        actions.append('<span class="meta">No image released yet.</span>')
    if docs:
        actions.append(link(*docs))
    body += '<div class="board-actions">%s</div>' % "".join(actions)
    summary = ('<span class="board-row__name">%s</span>'
               '<span class="board-row__meta">%s, %s</span>'
               '<span class="board-row__images">Ubuntu %s</span>'
               '<span class="board-row__status">%s</span>'
               % (esc(b["name"]), esc(b["soc"].upper()), esc(b["vendor"]), esc(versions(rows)),
                  tested_summary(r["status"] for r in rows)))
    return fold(summary, body, fid=board, search=b["name"], cls="board-row")


def render(boards, downloadable):
    """downloadable: the boards the Download page offers images for."""
    grouped = group(boards)
    out = [card("boards", "Supported boards",
                '<div class="folds">%s</div>' % "\n".join(
                    board_fold(board, rows, downloadable) for board, rows in grouped.items()),
                rail=False)]
    out.append(card("about-status", "What the words mean", kv([
        ("Tested on hardware", "A maintainer has booted the image on the board and "
         "run the %s." % link("/docs/hardware-test/", "hardware test")),
        ("Checked in CI", "The image builds and passes the automatic image checks in CI. "
         "Nobody has booted it on the board yet."),
        ("Images", "Command line images have no desktop. GNOME images start Ubuntu's GNOME "
         "desktop: the minimal one is Ubuntu's <code>ubuntu-desktop-minimal</code> (the "
         "desktop, Firefox and the basic tools), the other the full "
         "<code>ubuntu-desktop</code> with the office and media applications."),
        ("Kernel", "Armbian's kernel branch. <code>edge</code> follows recent mainline "
         "kernels; <code>vendor</code> is Rockchip's own kernel (Linux 6.1), offered for the "
         "UEFI image."),
        ("Source", "This list is %s in the build repository." % link(
            BUILD_REPO + "/blob/main/boards.conf", "boards.conf")),
    ]), rail=False))
    return "\n".join(out)


def home_cards(boards, downloadable):
    """The boards as PatternFly clickable cards for the home page: the whole
    card is one link, to the board's download (or to its row on the Boards
    page before it has one)."""
    cards = []
    for board, rows in group(boards).items():
        b = rows[0]
        href = "/download/?board=%s" % board if board in downloadable else "/boards/#%s" % board
        tid = "board-card-%s" % board
        cards.append(
            '<div class="pf-v6-l-grid__item"><div class="pf-v6-c-card pf-m-clickable pf-m-full-height board-card">'
            '<div class="pf-v6-c-card__header"><div class="pf-v6-c-card__actions pf-m-no-offset">'
            '<div class="pf-v6-c-card__selectable-actions">'
            '<a class="pf-v6-c-card__clickable-action" href="%s" aria-labelledby="%s"></a>'
            '</div></div><div class="pf-v6-c-card__header-main"><div class="pf-v6-c-card__title">'
            '<h3 class="pf-v6-c-card__title-text" id="%s">%s</h3></div></div></div>'
            '<div class="pf-v6-c-card__body">%s, %s</div>'
            '<div class="pf-v6-c-card__footer">Ubuntu %s</div></div></div>'
            % (href, tid, tid, esc(b["name"]), esc(b["soc"].upper()), esc(b["vendor"]),
               esc(versions(rows))))
    # Three to a row from lg, two from md: the rows stay even and a short
    # list does not leave an empty column on a wide screen, as a gallery would.
    return ('<div class="pf-v6-l-grid pf-m-gutter pf-m-all-6-col-on-md pf-m-all-4-col-on-lg board-cards">'
            '%s</div>' % "\n".join(cards))
