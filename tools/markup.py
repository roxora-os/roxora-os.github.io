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
"""Markup and wording the pages share: the site's constants, PatternFly
pieces (cards, key/value rows, tables, labels) and how a size, an Ubuntu
release or a date is written."""

import html
import pathlib
import re
from datetime import datetime

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
EDK2_RK3576 = "https://github.com/gahingwoo/edk2-rk3576"

# Ubuntu codenames the boards can name, with their version numbers. A codename
# missing here is shown as it is.
UBUNTU = {"jammy": ("22.04", True), "noble": ("24.04", True),
          "plucky": ("25.04", False), "questing": ("25.10", False),
          "resolute": ("26.04", True), "stonking": ("26.10", False)}

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
    """Holds those names together in a page's text, leaving tags, code
    blocks and scripts (the Download page's data) alone."""
    parts = re.split(r"(?s)(<pre\b.*?</pre>|<script\b.*?</script>|<[^>]+>)", markup)
    for i in range(0, len(parts), 2):
        parts[i] = NOBREAK.sub(r'<span class="nowrap">\1</span>', parts[i])
    return "".join(parts)


def card(cid, title, body, rail=None, footer="", cls="", extra="", title_after=""):
    """A card. With an id and a rail label it is listed in "On this page";
    rail=False keeps it out. cls adds classes to the section around the
    card, extra adds attributes to the card, and title_after is finished
    HTML that follows the heading in the title row."""
    attrs = extra and " " + extra
    if cid:
        attrs += ' id="%s"' % cid
        if rail is not False:
            attrs += ' data-rail="%s"' % esc(rail or title)
    head = ('  <div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text">%s</h2>%s</div>\n'
            % (esc(title), title_after)) if title else ""
    foot = ('  <div class="pf-v6-c-card__footer">%s</div>\n' % footer) if footer else ""
    return ('<div class="section%s">\n<div class="pf-v6-c-card"%s>\n%s'
            '  <div class="pf-v6-c-card__body">%s</div>\n%s</div>\n</div>'
            % (" " + cls if cls else "", attrs, head, body, foot))


def label(text, color="", outline=False):
    """PatternFly's label. color: green, orange, blue and so on; none is
    the neutral grey."""
    cls = "pf-v6-c-label pf-m-compact"
    if color:
        cls += " pf-m-" + color
    if outline:
        cls += " pf-m-outline"
    return ('<span class="%s"><span class="pf-v6-c-label__content">'
            '<span class="pf-v6-c-label__text">%s</span></span></span>' % (cls, esc(text)))


def beta_label():
    return label("Beta", "orange")


def fold(summary, body, fid=None, opened=False, search=None, cls="", extra=""):
    """A section folded behind its heading. It is the browser's own
    <details>, so it opens without JavaScript. summary is finished HTML.
    With an id and a search title it gets a search record of its own.
    extra adds attributes."""
    attrs = ' class="fold%s"' % (" " + cls if cls else "")
    if extra:
        attrs += " " + extra
    if fid:
        attrs += ' id="%s"' % fid
        if search:
            attrs += ' data-search="%s"' % esc(search)
    if opened:
        attrs += " open"
    return ('<details%s>\n<summary class="fold__toggle"><span class="fold__icon">%s</span>'
            '<span class="fold__text">%s</span></summary>\n'
            '<div class="fold__body">%s</div>\n</details>' % (attrs, CARET, summary, body))


ALERT_ICONS = {
    "warning": ('<svg class="pf-v6-svg" viewBox="0 0 576 512" fill="currentColor" aria-hidden="true" '
                'role="img" width="1em" height="1em"><path d="M569.517 440.013C587.975 472.007 '
                '564.806 512 527.94 512H48.054c-36.937 0-59.999-40.055-41.577-71.987L246.423 '
                '23.985c18.467-32.009 64.72-31.951 83.154 0l239.94 416.028zM288 354c-25.405 0-46 '
                '20.595-46 46s20.595 46 46 46 46-20.595 46-46-20.595-46-46-46zm-43.673-165.346l7.418 '
                '136c.347 6.364 5.609 11.346 11.982 11.346h48.546c6.373 0 11.635-4.982 '
                '11.982-11.346l7.418-136c.375-6.874-5.098-12.654-11.982-12.654h-63.383c-6.884 '
                '0-12.356 5.78-11.981 12.654z"/></svg>'),
    "info": ('<svg class="pf-v6-svg" viewBox="0 0 512 512" fill="currentColor" aria-hidden="true" '
             'role="img" width="1em" height="1em"><path d="M256 8C119.043 8 8 119.083 8 256c0 '
             '136.997 111.043 248 248 248s248-111.003 248-248C504 119.083 392.957 8 256 8zm0 '
             '110c23.196 0 42 18.804 42 42s-18.804 42-42 42-42-18.804-42-42 18.804-42 42-42zm56 '
             '254c0 6.627-5.373 12-12 12h-88c-6.627 0-12-5.373-12-12v-24c0-6.627 5.373-12 '
             '12-12h12v-64h-12c-6.627 0-12-5.373-12-12v-24c0-6.627 5.373-12 12-12h64c6.627 0 12 '
             '5.373 12 12v100h12c6.627 0 12 5.373 12 12v24z"/></svg>'),
}


def alert(kind, title, body, attrs=""):
    """PatternFly's inline alert. kind: warning or info. body is finished
    HTML; attrs go on the alert itself (an id, hidden)."""
    return ('<div class="pf-v6-c-alert pf-m-%s pf-m-inline"%s>'
            '<div class="pf-v6-c-alert__icon">%s</div>'
            '<p class="pf-v6-c-alert__title">%s</p>'
            '<div class="pf-v6-c-alert__description">%s</div></div>'
            % (kind, " " + attrs if attrs else "", ALERT_ICONS[kind], esc(title), body))


def button(href, text, kind="primary", large=False, cls=""):
    """A link that looks like a PatternFly button."""
    return ('<a class="pf-v6-c-button pf-m-%s%s%s" href="%s">'
            '<span class="pf-v6-c-button__text">%s</span></a>'
            % (kind, " pf-m-display-lg" if large else "", " " + cls if cls else "",
               esc(href), esc(text)))


COPY_ICON = ('<svg class="pf-v6-svg" viewBox="0 0 448 512" fill="currentColor" aria-hidden="true" '
             'role="img" width="1em" height="1em"><path d="M320 448v40c0 13.255-10.745 24-24 '
             '24H24c-13.255 0-24-10.745-24-24V120c0-13.255 10.745-24 24-24h72v296c0 30.879 25.121 '
             '56 56 56h168zm0-344V0H152c-13.255 0-24 10.745-24 24v368c0 13.255 10.745 24 24 '
             '24h272c13.255 0 24-10.745 24-24V128H344c-13.2 0-24-10.8-24-24zm120.971-31.029L375.029 '
             '7.029A24 24 0 0 0 358.059 0H352v96h96v-6.059a24 24 0 0 0-7.029-16.97z"/></svg>')


def copyable(text, what, tid=None, mono=True):
    """Text with a button that copies it (PatternFly's inline clipboard
    copy). The button needs JavaScript and is hidden without it; the text
    can still be selected. what names the text for the button's label."""
    return ('<span class="pf-v6-c-clipboard-copy pf-m-inline">'
            '<span class="pf-v6-c-clipboard-copy__text%s"%s>%s</span>'
            '<span class="pf-v6-c-clipboard-copy__actions js-only">'
            '<span class="pf-v6-c-clipboard-copy__actions-item">'
            '<button class="pf-v6-c-button pf-m-plain" type="button" data-copy '
            'aria-label="Copy %s"><span class="pf-v6-c-button__icon">%s</span></button>'
            '</span></span></span>'
            % (" pf-m-code" if mono else "", ' id="%s"' % tid if tid else "", esc(text),
               esc(what), COPY_ICON))


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


SEARCH_ICON = ('<svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" '
               'role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 '
               '44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 '
               '128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 '
               '9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 '
               '128 128 0 70.7-57.2 128-128 128z"/></svg>')


def board_filter(vendors, items, placeholder="Search boards, vendors or SoCs"):
    """Search and a vendor filter over a list of boards, as Roxora Imager's
    Board step has them: the vendors with their counts beside the list on a
    wide screen, a select above it on a phone. vendors maps a vendor to its
    number of boards. items is the list itself: finished HTML holding one
    element per board with data-vendor and data-filter (the words a search
    matches), and one element marked data-filter-list that is hidden when
    nothing matches. assets/board-filter.js does the filtering; without
    JavaScript the controls are not shown and the whole list is."""
    total = sum(vendors.values())
    choices = [("", "All vendors", total)] + [(v, v, n) for v, n in vendors.items()]
    vendor_list = "".join(
        '<li class="pf-v6-c-simple-list__item"><button class="pf-v6-c-simple-list__item-link%s" '
        'type="button" data-vendor="%s"><span>%s</span><span class="vendor-count">%d</span></button></li>'
        % (" pf-m-current" if not v else "", esc(v), esc(name), n) for v, name, n in choices)
    vendor_select = "".join('<option value="%s">%s (%d)</option>' % (esc(v), esc(name), n)
                            for v, name, n in choices)
    return (
        '<div class="board-filter" data-board-filter>\n'
        '<div class="pf-v6-c-text-input-group board-search js-only"><div class="pf-v6-c-text-input-group__main pf-m-icon">'
        '<span class="pf-v6-c-text-input-group__text"><span class="pf-v6-c-text-input-group__icon">%s</span>'
        '<input class="pf-v6-c-text-input-group__text-input" type="search" id="board-search" '
        'placeholder="%s" aria-label="%s" autocomplete="off" spellcheck="false"></span></div></div>\n'
        '<div class="board-pick">\n'
        '<span class="pf-v6-c-form-control vendor-select js-only"><select id="vendor-select" aria-label="Vendor">%s</select>'
        '<span class="pf-v6-c-form-control__utilities"><span class="pf-v6-c-form-control__toggle-icon">%s</span>'
        '</span></span>\n'
        '<nav class="pf-v6-c-simple-list vendor-list js-only" aria-label="Vendors" id="vendor-list">'
        '<ul class="pf-v6-c-simple-list__list" role="list">%s</ul></nav>\n'
        '<div class="board-table-wrap">\n%s\n'
        '<div id="board-none" hidden>%s</div>\n'
        '</div>\n</div>\n</div>'
        % (SEARCH_ICON, esc(placeholder), esc(placeholder), vendor_select, CARET, vendor_list, items,
           empty_state("No board matches",
                       "Roxora has images for the boards listed here. To ask for another "
                       "board, open an issue on %s." % link(BUILD_REPO + "/issues", "roxora-os/build"))))


def table(cls, head, rows, widths=None, stack="md"):
    """A compact PatternFly table that stacks below md. rows hold finished
    HTML per cell, or (id, cells) to give the row an id; every cell carries
    its column's name for the stacked layout. widths: per column a
    percentage PatternFly has a width modifier for, or None for a share of
    what is left."""
    widths = widths or [None] * len(head)
    th = "".join('<th class="pf-v6-c-table__th%s" scope="col">%s</th>'
                 % (" pf-m-width-%d" % w if w else "", esc(h)) for h, w in zip(head, widths))

    def tr(row):
        rid, cells = row if isinstance(row, tuple) else (None, row)
        return '<tr class="pf-v6-c-table__tr"%s>%s</tr>' % (
            ' id="%s"' % esc(rid) if rid else "", "".join(
                '<td class="pf-v6-c-table__td" data-label="%s">%s</td>' % (esc(h), cell)
                for h, cell in zip(head, cells)))
    return ('<table class="pf-v6-c-table pf-m-compact pf-m-grid-%s %s">\n'
            '<thead class="pf-v6-c-table__thead"><tr class="pf-v6-c-table__tr">%s</tr></thead>\n'
            '<tbody class="pf-v6-c-table__tbody">\n%s\n</tbody></table>'
            % (stack, cls, th, "\n".join(tr(r) for r in rows)))


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


def date(iso):
    """2026-11-13 as 13 November 2026."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        return iso
    return "%d %s" % (d.day, d.strftime("%B %Y"))


def and_list(items):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]

IMAGER_REPO = "https://github.com/roxora-os/imager"


# ---- landing pages: the home page and Roxora Imager ----
# A landing page has no page head: a Hero comes first, then its parts. The
# page's content sheet is its first page section (site.css rounds its foot
# above the footer), so the parts are bodies of that one section, as
# PatternFly lets a section hold several.

def landing_sheet(label_, parts):
    return ('<section class="pf-v6-c-page__main-section pf-m-limit-width landing-sheet" '
            'aria-label="%s">\n%s</section>' % (esc(label_), "".join(parts)))


def landing_part(sid, search, inner, cls=""):
    """One part. With its id and search title it is a search record."""
    return ('<div class="pf-v6-c-page__main-body landing-part%s" id="%s" data-search="%s">\n'
            '%s\n</div>\n' % (" " + cls if cls else "", sid, esc(search), inner))


def landing_head(sid, title, more=None):
    """A part's name, with one link beside it to where the rest is, as
    patternfly.org's own home page sets its sections."""
    more_link = ""
    if more:
        more_link = ('<a class="pf-v6-c-button pf-m-link pf-m-inline" href="%s">'
                     '<span class="pf-v6-c-button__text">%s</span></a>' % (esc(more[1]), esc(more[0])))
    return ('<div class="landing-head"><h2 class="pf-v6-c-title pf-m-2xl" id="%s-title">%s</h2>%s</div>'
            % (sid, esc(title), more_link))

