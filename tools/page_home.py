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
"""The home page, a landing page in PatternFly's terms: a Hero with what
Roxora is and the two things to do next, the newest release as a card of
terms and values, the boards as clickable cards, and the install in three
steps. It writes its own page sections; there is no page head."""

import page_boards
import page_download
from markup import beta_label, button, date, esc

# The page's content sheet is its first page section (site.css rounds its
# foot above the footer), so the parts of the home page are bodies of that
# one section, as PatternFly lets a section hold several.
PART = ('<div class="pf-v6-c-page__main-body home-part%s" id="%s" data-search="%s">\n'
        '%s\n</div>\n')


def part(sid, search, inner, cls=""):
    return PART % (" " + cls if cls else "", sid, esc(search), inner)


def section_head(sid, title, more=None):
    """The section's name, with one link beside it to the page that has the
    rest, as patternfly.org's own home page sets its sections."""
    link = ""
    if more:
        link = ('<a class="pf-v6-c-button pf-m-link pf-m-inline" href="%s">'
                '<span class="pf-v6-c-button__text">%s</span></a>' % (esc(more[1]), esc(more[0])))
    return ('<div class="home-section__head"><h2 class="pf-v6-c-title pf-m-2xl" id="%s-title">%s</h2>%s</div>'
            % (sid, esc(title), link))


def hero():
    return (
        '<div class="pf-v6-c-hero home-hero">\n'
        '<div class="pf-v6-c-hero__body">\n'
        '<h1 class="pf-v6-c-title pf-m-3xl home-hero__title" id="what-title">'
        'Plain Ubuntu for Rockchip boards</h1>\n'
        '<p class="home-hero__text">Roxora images boot a standard Ubuntu install on Rockchip '
        'single-board computers. The kernel, bootloader and firmware come from Armbian and '
        'update through apt like everything else.</p>\n'
        '<div class="home-hero__actions">%s%s</div>\n'
        '</div>\n</div>'
        % (button("/download/", "Download", "primary", large=True),
           button("/roxora-imager/", "Get Roxora Imager", "secondary", large=True)))


def dl_group(term, value):
    return ('<div class="pf-v6-c-description-list__group">'
            '<dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text">'
            '%s</span></dt><dd class="pf-v6-c-description-list__description">'
            '<div class="pf-v6-c-description-list__text">%s</div></dd></div>' % (esc(term), value))


def release_card(catalogs):
    """The newest release as terms and values. It says only what the
    catalog says."""
    offer = page_download.offered(catalogs)
    if not offer:
        body = ('<div class="pf-v6-c-card__body">No images have been released yet; the first '
                'ones are being built.</div>')
        title, footer = "Newest release", ""
    else:
        cat = offer[0]
        rel, images = cat["release"], cat["images"]
        boards = len(dict.fromkeys(i["board"] for i in images))
        ubuntu = sorted({page_download.ubuntu_short(i) for i in images}, reverse=True)
        rows = [
            ("Version", esc("Roxora " + rel["version"]) + (" " + beta_label() if rel["prerelease"] else "")),
            ("Released", esc(date(rel["date"]))),
            ("Images", esc("%d, for %d board%s" % (len(images), boards, "" if boards == 1 else "s"))),
            ("Ubuntu", esc(", ".join(ubuntu))),
        ]
        if len(offer) > 1:
            beta = offer[1]["release"]
            rows.append(("Beta", "%s %s, %s" % (esc("Roxora " + beta["version"]), beta_label(),
                                                 esc(date(beta["date"])))))
        body = ('<div class="pf-v6-c-card__body"><dl class="pf-v6-c-description-list '
                'pf-m-auto-fit home-release">%s</dl></div>'
                % "".join(dl_group(t, v) for t, v in rows))
        title = "Newest release"
        footer = ('<div class="pf-v6-c-card__footer"><a class="pf-v6-c-button pf-m-link pf-m-inline" '
                  'href="%s"><span class="pf-v6-c-button__text">Release notes</span></a></div>'
                  % esc(rel["url"]))
    return ('<div class="pf-v6-c-card home-release-card">'
            '<div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text" id="status-title">'
            '%s</h2></div>%s%s</div>' % (title, body, footer))


STEPS = [
    ("Choose", "Pick your board, the Ubuntu version, and a desktop or the command line."),
    ("Write", "Write the image to an SD card. Roxora Imager downloads, checks and writes it "
              "in one go."),
    ("Boot", "Start the board and log in as <code>roxora</code>, password <code>roxora</code>. "
             "You choose a new password straight away."),
]


def steps():
    cards = "".join(
        '<div class="pf-v6-l-grid__item pf-m-4-col-on-lg"><div class="pf-v6-c-card pf-m-full-height home-step">'
        '<div class="pf-v6-c-card__title"><h3 class="pf-v6-c-card__title-text">%s</h3></div>'
        '<div class="pf-v6-c-card__body">%s</div></div></div>' % (esc(t), body)
        for t, body in STEPS)
    return '<div class="pf-v6-l-grid pf-m-gutter home-steps">%s</div>' % cards


def render(boards, catalogs, downloadable):
    return (
        '<section class="pf-v6-c-page__main-section pf-m-limit-width home-sheet" aria-label="Roxora">\n'
        + part("what", "What Roxora is", hero(), "home-part--hero")
        + part("status", "Newest release", release_card(catalogs))
        + part("boards", "Boards", section_head("boards", "Boards", ("All boards", "/boards/"))
               + page_boards.home_cards(boards, downloadable))
        + part("install", "Install", section_head("install", "Install",
                                                  ("Installing Roxora", "/docs/install/"))
               + steps())
        + '</section>')
