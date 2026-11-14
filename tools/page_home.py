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
"""The home page: what Roxora is, the two things to do next, the state of
the newest release in one line, and the boards."""

import page_boards
import page_download
from markup import beta_label, button, date, esc, label


def status_line(catalogs):
    """One line on the newest release. It counts the images tested on
    hardware and never says more than the catalog does."""
    offer = page_download.offered(catalogs)
    if not offer:
        return "%s No images have been released yet; the first ones are being built." % label("Early")
    cat = offer[0]
    rel, images = cat["release"], cat["images"]
    tested = sum(1 for i in images if i["status"] == "hardware-tested")
    if tested == len(images):
        how = "Every image passed the checks in CI and has been tested on hardware."
    elif tested:
        how = ("Every image passed the checks in CI; %d of %d %s also been tested on hardware."
               % (tested, len(images), "has" if tested == 1 else "have"))
    else:
        how = "Every image passed the checks in CI; none has been tested on hardware yet."
    return ('%s <a href="/download/">Roxora %s</a>, %s. %s' % (
        beta_label() if rel["prerelease"] else label("Release", "blue"),
        esc(rel["version"]), esc(date(rel["date"])), esc(how)))


def render(boards, catalogs, downloadable):
    return (
        '<section class="hero" id="what" data-search="What Roxora is">\n'
        '<p class="hero-lead">Roxora images boot a standard Ubuntu install on Rockchip '
        'single-board computers. Packages, updates and defaults are the ones Ubuntu ships. '
        'The kernel, device tree, bootloader and firmware come from Armbian and update '
        'through apt like everything else.</p>\n'
        '<div class="hero-actions">%s%s</div>\n'
        '<p class="hero-status" id="status" data-search="Status">%s</p>\n'
        '</section>\n'
        '<section class="home-section" id="boards" data-search="Boards">\n'
        '<h2 class="section-title">Boards</h2>\n'
        '%s\n'
        '<p class="home-more"><a href="/boards/">What each board needs to boot</a></p>\n'
        '</section>\n'
        '<section class="home-section" id="install" data-search="Install">\n'
        '<h2 class="section-title">Install</h2>\n'
        '<ol class="steps">'
        '<li><strong>Choose</strong> your board on the <a href="/download/">Download</a> page, '
        'or in <a href="/roxora-imager/">Roxora Imager</a>.</li>'
        '<li><strong>Write</strong> the image to an SD card. Roxora Imager downloads, checks '
        'and writes it in one go.</li>'
        '<li><strong>Boot</strong> the board and log in as <code>roxora</code>, password '
        '<code>roxora</code>. <a href="/docs/install/">Installing Roxora</a> has every step.</li>'
        '</ol>\n'
        '</section>'
        % (button("/download/", "Download", "primary", large=True),
           button("/roxora-imager/", "Get Roxora Imager", "secondary", large=True),
           status_line(catalogs), page_boards.home_cards(boards, downloadable)))
