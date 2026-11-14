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
release or a status is written."""

import html
import pathlib
import re

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
    """Holds those names together in a page's text, leaving tags and code
    blocks alone."""
    parts = re.split(r"(?s)(<pre\b.*?</pre>|<[^>]+>)", markup)
    for i in range(0, len(parts), 2):
        parts[i] = NOBREAK.sub(r'<span class="nowrap">\1</span>', parts[i])
    return "".join(parts)


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

IMAGER_REPO = "https://github.com/roxora-os/imager"
