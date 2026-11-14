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
"""The Docs pages: docs/*.md of roxora-os/build, rendered as GitHub shows
them, and the page that lists them."""

import html
import posixpath
import re
import sys

from markup import BUILD_REPO, SITE, card, code_block, content, esc, kv, link

# Build repository documents for developers rather than for people installing
# Roxora. They are listed after the others on the Docs page.
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
