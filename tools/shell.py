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
"""The shell every page shares: PatternFly's page, masthead and sidebar, the
"on this page" rail, the footer, and the records the search reads."""

import html
import re

from markup import BUILD_REPO, CARET, esc

# The footer's own columns, as gahingwoo.com has them. A page not built is
# left out.
FOOTER_PAGES = [("Home", "/"), ("Download", "/download/"), ("Roxora Imager", "/roxora-imager/"),
                ("Boards", "/boards/"), ("Raspberry Pi Imager", "/rpi-imager/"),
                ("About", "/about/")]
FOOTER_DOCS = [("Installing Roxora", "/docs/install/"), ("All documents", "/docs/"),
               ("FAQ", "/faq/")]
# The pages the 404 page lists: title, address, what is there.
SITE_PAGES = [
    ("Home", "/", "What Roxora is, and how far along it is."),
    ("Download", "/download/", "The newest images, with sizes and checksums."),
    ("Roxora Imager", "/roxora-imager/", "The app that downloads, checks and writes an image."),
    ("Boards", "/boards/", "The supported boards and their test status."),
    ("Raspberry Pi Imager", "/rpi-imager/", "Writing Roxora with Raspberry Pi Imager."),
    ("Docs", "/docs/", "Installing, testing, and how Roxora is built."),
    ("FAQ", "/faq/", "Questions people ask about Roxora."),
    ("About", "/about/", "Who makes Roxora and how to reach them."),
    ("Privacy policy", "/privacy/", "What the website and Roxora Imager fetch, and from where."),
    ("Code signing policy", "/code-signing/", "Who may sign Roxora Imager, and what is signed."),
]

# Sidebar navigation. Section title, then (label, href) per item.
NAV = [
    ("Pages", [
        ("Home", "/"),
        ("Download", "/download/"),
        ("Roxora Imager", "/roxora-imager/"),
        ("Boards", "/boards/"),
        ("Raspberry Pi Imager", "/rpi-imager/"),
    ]),
    ("Documentation", [
        ("Docs", "/docs/"),
        ("FAQ", "/faq/"),
    ]),
    ("Project", [
        ("About", "/about/"),
        ("Source code", BUILD_REPO),
    ]),
]


def foot_links(items):
    return "\n".join('                <a href="%s">%s</a>' % (esc(h), esc(l)) for l, h in items)


def search_records(slug, href, heading, fragment):
    """One record per card, built from the page itself: a card is findable
    because it is there, not because someone remembered to index it. An
    element that is not a card (a folded section, the home page's sections)
    gets a record by carrying an id and data-search, its title. Slices run
    from one record's start to the next rather than matching a closing tag,
    which nesting makes unreliable."""
    def text_of(chunk):
        chunk = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", chunk)
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", chunk))).strip()

    starts = [(m.start(), m.group(1), text_of(m.group(2)), True) for m in re.finditer(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*>\s*'
        r'(?:<div class="pf-v6-c-card__header[^>]*>.*?</div>\s*)?'
        r'<div class="pf-v6-c-card__title"><h2 class="pf-v6-c-card__title-text">(.*?)</h2>',
        fragment, re.S)]
    starts += [(m.start(), m.group(1), html.unescape(m.group(2)), False) for m in re.finditer(
        r'<[a-z0-9]+\b[^>]*\bid="([^"]+)"[^>]*\bdata-search="([^"]+)"', fragment)]
    starts.sort()
    # The snippet a result shows is read from "x": the record's prose, without
    # a card's heading (the result's title already says it) and without code
    # blocks and checksums, so a snippet never opens in the middle of a hash.
    # Those are still searched, from "k".
    code = re.compile(r'(?s)<pre\b.*?</pre>|<(code|span|a) class="[^"]*\bhash\b[^"]*"[^>]*>.*?</\1>')
    out = []
    for i, (pos, cid, title, is_card) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(fragment)
        chunk = fragment[pos:end]
        if is_card:
            chunk = re.sub(r'(?s)^.*?</h2>', "", chunk, count=1)
        rec = {"t": title, "u": href + "#" + cid, "p": heading,
               "x": text_of(code.sub(" ", chunk))}
        kept = " ".join(text_of(m.group(0)) for m in code.finditer(chunk))
        if kept:
            rec["k"] = kept
        out.append(rec)
    return out


def render_nav(current, have):
    """have: the site's own pages in this build. A link to one that was not
    built (the FAQ before docs/faq.md exists) is left out."""
    out = []
    for title, items in NAV:
        items = [(l, h) for l, h in items if not h.startswith("/") or h in have]
        tid = re.sub(r"[^a-z]+", "-", title.lower()).strip("-") + "-title"
        out.append('        <section class="pf-v6-c-nav__section" aria-labelledby="%s">\n'
                   '          <h2 class="pf-v6-c-nav__section-title" id="%s">%s</h2>\n'
                   '          <ul class="pf-v6-c-nav__list" role="list">' % (tid, tid, esc(title)))
        for label, href in items:
            cur = href == current
            out.append('            <li class="pf-v6-c-nav__item">'
                       '<a href="%s" class="pf-v6-c-nav__link%s"%s>'
                       '<span class="pf-v6-c-nav__link-text">%s</span></a></li>'
                       % (href, " pf-m-current" if cur else "",
                          ' aria-current="page"' if cur else "", esc(label)))
        out.append("          </ul>\n        </section>")
    return "\n".join(out)


def cards(fragment):
    """The cards on this page, for the rail: every card that carries an id."""
    return re.findall(
        r'<div class="pf-v6-c-card"[^>]*\bid="([^"]+)"[^>]*data-rail="([^"]+)"', fragment)


def render_rail(sections):
    if not sections:
        return ""
    items = "\n".join(
        '                <li class="pf-v6-c-jump-links__item">'
        '<span class="pf-v6-c-jump-links__link">'
        '<a class="pf-v6-c-button pf-m-link" href="#%s"><span class="pf-v6-c-button__text">'
        '<span class="pf-v6-c-jump-links__link-text">%s</span></span></a></span></li>'
        % (sid, label) for sid, label in sections)
    return """          <aside class="page-rail no-print">
            <nav class="pf-v6-c-jump-links pf-m-vertical pf-m-expandable pf-m-non-expandable-on-xl" aria-label="On this page" id="jump-nav" data-scrollable=".pf-v6-c-page__main">
              <div class="pf-v6-c-jump-links__header" id="jump-header">
                <div class="pf-v6-c-jump-links__toggle">
                  <button class="pf-v6-c-button pf-m-plain" type="button" aria-expanded="false" aria-controls="jump-list" id="jump-toggle">
                    <span class="pf-v6-c-button__icon pf-m-start"><span class="pf-v6-c-jump-links__toggle-icon">%s</span></span>
                    <span class="pf-v6-c-button__text">On this page</span>
                  </button>
                </div>
                <div class="pf-v6-c-jump-links__label">On this page</div>
              </div>
              <ul class="pf-v6-c-jump-links__list" role="list" aria-labelledby="jump-header" id="jump-list">
%s
              </ul>
            </nav>
          </aside>
""" % (CARET, items)


SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<link rel="canonical" href="%(canonical)s">
%(noindex)s
<link rel="icon" href="/assets/brand/roxora-mark.svg" type="image/svg+xml">
<link rel="icon" href="/assets/brand/roxora-mark-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/brand/roxora-avatar-180.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%(name)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:url" content="%(canonical)s">
<meta property="og:image" content="%(site)s/assets/brand/roxora-avatar-500.png">
<meta property="og:image:width" content="500">
<meta property="og:image:height" content="500">
<meta name="twitter:card" content="summary">
<script>
  (function () {
    var saved = null;
    try { saved = localStorage.getItem('theme'); } catch (e) {}
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('pf-v6-theme-dark');
    }
    // What needs JavaScript (the download chooser, copy buttons) is hidden
    // until this says it runs; site.css has the rules.
    document.documentElement.classList.add('js');
  })();
  // Arriving from another of this site's pages, the sidebar's current-item
  // bar grows in as PatternFly's does when an item is clicked, rather than
  // fading with the rest of the page (site.css has the animation).
  addEventListener('pagereveal', function (e) {
    if (!e.viewTransition) return;
    var root = document.documentElement;
    root.classList.add('nav-accent-enter');
    setTimeout(function () { root.classList.remove('nav-accent-enter'); }, 1000);
  });
</script>
<link rel="stylesheet" href="%(pf_css)s">
<link rel="stylesheet" href="%(site_css)s">
</head>
<body>
<div class="pf-v6-c-page">
  <div class="pf-v6-c-skip-to-content">
    <a class="pf-v6-c-button pf-m-primary" href="#main-content"><span class="pf-v6-c-button__text">Skip to content</span></a>
  </div>
  <header class="pf-v6-c-masthead pf-m-display-inline">
    <div class="pf-v6-c-masthead__main">
      <span class="pf-v6-c-masthead__toggle">
        <button class="pf-v6-c-button pf-m-hamburger pf-m-plain" type="button" aria-label="Site navigation" aria-expanded="false" aria-controls="site-sidebar" id="nav-toggle">
          <span class="pf-v6-c-button__icon"><svg viewBox="0 0 10 10" class="pf-v6-c-button--hamburger-icon pf-v6-svg" width="1em" height="1em"><path class="pf-v6-c-button--hamburger-icon--top" d="M1,1 L9,1"/><path class="pf-v6-c-button--hamburger-icon--middle" d="M1,5 L9,5"/><path class="pf-v6-c-button--hamburger-icon--arrow" d="M1,5 L1,5 L1,5"/><path class="pf-v6-c-button--hamburger-icon--bottom" d="M9,9 L1,9"/></svg></span>
        </button>
      </span>
      <div class="pf-v6-c-masthead__brand">
        <a class="pf-v6-c-masthead__logo brand" href="/" aria-label="Roxora home">
          <img class="pf-v6-c-brand brand-mark" src="/assets/brand/roxora-mark.svg" width="120" height="120" alt="">
          <span class="brand-name wordmark">roxora</span>
        </a>
      </div>
    </div>
    <div class="pf-v6-c-masthead__content">
      <div class="search-slot">
        <div class="pf-v6-c-input-group pf-m-search-expandable pf-m-plain site-search" id="site-search">
          <div class="pf-v6-c-input-group__item pf-m-search-input">
            <div class="pf-v6-c-text-input-group">
              <div class="pf-v6-c-text-input-group__main pf-m-icon">
                <span class="pf-v6-c-text-input-group__text">
                  <span class="pf-v6-c-text-input-group__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
                  <input class="pf-v6-c-text-input-group__text-input" type="text" id="search-input"
                         placeholder="Search this site" autocomplete="off" spellcheck="false"
                         aria-label="Search this site" role="combobox" aria-expanded="false"
                         aria-controls="search-results" aria-autocomplete="list"
                         data-index="/assets/search-index.json">
                </span>
              </div>
            </div>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-expand pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-open"
                    aria-label="Search this site" aria-expanded="false">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" fill="currentColor" viewBox="0 0 512 512" aria-hidden="true" role="img" width="1em" height="1em"><path d="M505 442.7L405.3 343c-4.5-4.5-10.6-7-17-7H372c27.6-35.3 44-79.7 44-128C416 93.1 322.9 0 208 0S0 93.1 0 208s93.1 208 208 208c48.3 0 92.7-16.4 128-44v16.3c0 6.4 2.5 12.5 7 17l99.7 99.7c9.4 9.4 24.6 9.4 33.9 0l28.3-28.3c9.4-9.4 9.4-24.6.1-34zM208 336c-70.7 0-128-57.2-128-128 0-70.7 57.2-128 128-128 70.7 0 128 57.2 128 128 0 70.7-57.2 128-128 128z"/></svg></span>
            </button>
          </div>
          <div class="pf-v6-c-input-group__item pf-m-search-action pf-m-plain">
            <button class="pf-v6-c-button pf-m-plain" type="button" id="search-close" aria-label="Close search">
              <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
            </button>
          </div>
        </div>
        <div class="pf-v6-c-menu search-results" id="search-results" hidden>
          <div class="pf-v6-c-menu__content">
            <ul class="pf-v6-c-menu__list" role="listbox" aria-label="Search results" id="search-list"></ul>
          </div>
        </div>
      </div>
      <a class="pf-v6-c-button pf-m-plain" href="https://github.com/roxora-os" aria-label="Roxora on GitHub" title="Roxora on GitHub">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 496 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8zM97.2 352.9c-1.3 1-1 3.3.7 5.2 1.6 1.6 3.9 2.3 5.2 1 1.3-1 1-3.3-.7-5.2-1.6-1.6-3.9-2.3-5.2-1zm-10.8-8.1c-.7 1.3.3 2.9 2.3 3.9 1.6 1 3.6.7 4.3-.7.7-1.3-.3-2.9-2.3-3.9-2-.6-3.6-.3-4.3.7zm32.4 35.6c-1.6 1.3-1 4.3 1.3 6.2 2.3 2.3 5.2 2.6 6.5 1 1.3-1.3.7-4.3-1.3-6.2-2.2-2.3-5.2-2.6-6.5-1zm-11.4-14.7c-1.6 1-1.6 3.6 0 5.9 1.6 2.3 4.3 3.3 5.6 2.3 1.6-1.3 1.6-3.9 0-6.2-1.4-2.3-4-3.3-5.6-2z"/></svg></span>
      </a>
      <button class="pf-v6-c-button pf-m-plain theme-toggle" id="theme-toggle" type="button" aria-label="Toggle light and dark theme">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg icon-moon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M10.6 2a8 8 0 1 0 7.4 11 6.6 6.6 0 0 1-7.4-11Z"/></svg><svg class="pf-v6-svg icon-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true" role="img" width="1em" height="1em"><circle cx="10" cy="10" r="3.6"/><path d="M10 1.5v2.2M10 16.3v2.2M1.5 10h2.2M16.3 10h2.2M4 4l1.6 1.6M14.4 14.4 16 16M4 16l1.6-1.6M14.4 5.6 16 4"/></svg></span>
      </button>
%(download_btn)s    </div>
  </header>
  <div class="pf-v6-c-backdrop site-backdrop" id="site-backdrop" hidden></div>
  <aside class="pf-v6-c-page__sidebar%(sidebarcls)s" id="site-sidebar"%(sidebarattrs)s>
    <div class="pf-v6-c-page__sidebar-main">
      <div class="pf-v6-c-page__sidebar-body pf-m-page-insets">
        <nav class="pf-v6-c-nav" aria-label="Site">
%(nav)s
        </nav>
      </div>
    </div>
  </aside>
  <div class="pf-v6-c-page__main-container" tabindex="-1">
    <main class="pf-v6-c-page__main %(maincls)s" tabindex="-1" id="main-content">
%(sections)s

      <footer class="pf-v6-c-page__main-section site-footer">
        <div class="pf-v6-c-page__main-body">
          <div class="pf-v6-l-grid pf-m-gutter">
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Pages</p>
              <nav aria-label="Pages">
%(foot_pages)s
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Documentation</p>
              <nav aria-label="Documentation">
%(foot_docs)s
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <p class="foot-title">Elsewhere</p>
              <nav aria-label="Elsewhere">
                <a href="%(build_repo)s">Build repository</a>
                <a href="%(build_repo)s/releases">Releases</a>
                <a href="%(build_repo)s/issues">Issues</a>
                <a href="https://github.com/roxora-os/design">Logo files</a>
              </nav>
            </div>
            <div class="pf-v6-l-grid__item pf-m-6-col-on-sm pf-m-3-col-on-lg">
              <span class="brand foot-brand">
                <img class="pf-v6-c-brand brand-mark" src="/assets/brand/roxora-mark.svg" width="120" height="120" alt="" loading="lazy">
                <span class="brand-name wordmark">roxora</span>
              </span>
              <p class="foot-about">%(tagline)s Roxora is an independent project, not affiliated with Canonical, Armbian or Rockchip.</p>
              <address>
                <a href="mailto:%(email)s">%(email)s</a><br>
                Report problems with an image on <a href="%(build_repo)s/issues" class="nowrap">roxora-os/build</a>.
              </address>
            </div>
          </div>
        </div>
      </footer>

      <section class="pf-v6-c-page__main-section pf-m-no-fill foot-legal" aria-label="Site information">
        <div class="pf-v6-c-page__main-body">
          <span>Copyright &copy; <span id="year">%(year)s</span> %(author)s</span>
          <span><a href="%(source)s">View page source</a></span>
          <span><a href="/privacy/">Privacy policy</a></span>
          <span><a href="/code-signing/">Code signing policy</a></span>
          <span><button class="link-button" type="button" id="about-page-open">About this site</button></span>
          <span><a href="mailto:%(email)s">Contact</a></span>
        </div>
      </section>
    </main>
  </div>
</div>
<div class="pf-v6-c-backdrop about-backdrop" id="about-page" hidden>
  <div class="pf-v6-l-bullseye">
  <div class="pf-v6-c-about-modal-box" role="dialog" aria-modal="true" aria-labelledby="about-page-title">
    <div class="pf-v6-c-about-modal-box__brand">
      <svg class="credit-badge" viewBox="14 0 346 110" role="img" aria-label="Engineered by gahingwoo">
        <g class="credit-badge__mark" transform="translate(14,19) scale(0.257143)">
          <rect x="0" y="0" width="350" height="70"/>
          <rect x="70" y="70" width="70" height="70"/>
          <rect x="210" y="70" width="70" height="70"/>
          <rect x="0" y="210" width="350" height="70"/>
        </g>
        <text class="credit-badge__label" x="124" y="48">Engineered by</text>
        <text class="credit-badge__name" x="123" y="88">gahingwoo</text>
      </svg>
    </div>
    <div class="pf-v6-c-about-modal-box__close">
      <button class="pf-v6-c-button pf-m-plain" type="button" id="about-page-close" data-dialog-close aria-label="Close About this site">
        <span class="pf-v6-c-button__icon"><svg class="pf-v6-svg" viewBox="0 0 352 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"/></svg></span>
      </button>
    </div>
    <div class="pf-v6-c-about-modal-box__header">
      <h1 class="pf-v6-c-title pf-m-4xl" id="about-page-title">About this site</h1>
    </div>
    <div class="pf-v6-c-about-modal-box__content">
      <dl class="pf-v6-c-description-list pf-m-horizontal">
%(aboutrows)s
      </dl>
      <p class="pf-v6-c-about-modal-box__strapline">
        Copyright &copy; %(year)s %(author)s. The code behind this site is
        free software under the GNU General Public License, version 2.
      </p>
    </div>
  </div>
  </div>
</div>
<div class="pf-v6-c-back-to-top pf-m-hidden" id="back-to-top">
  <a class="pf-v6-c-button pf-m-primary" href="#main-content">
    <span class="pf-v6-c-button__text">Back to top</span>
    <span class="pf-v6-c-button__icon pf-m-end"><svg class="pf-v6-svg" viewBox="0 0 448 512" fill="currentColor" aria-hidden="true" role="img" width="1em" height="1em"><path d="M6.101 359.293 25.9 379.092a12 12 0 0 0 16.971 0L224 198.393l181.13 180.698a12 12 0 0 0 16.971 0l19.799-19.799a12 12 0 0 0 0-16.971L232.485 132.908a12 12 0 0 0-16.971 0L6.101 342.322a12 12 0 0 0 0 16.971z"/></svg></span>
  </a>
</div>
<script src="%(site_js)s"></script>
%(page_js)s</body>
</html>
"""


def doc_section(heading, rail, head, content):
    """The one section of an ordinary page: the page head, the content, and
    the "on this page" rail beside them when there is one."""
    return ('      <section class="pf-v6-c-page__main-section pf-m-limit-width" aria-label="%s">\n'
            '        <div class="pf-v6-c-page__main-body">\n'
            '%s          <div class="page-content">\n'
            '%s%s\n\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n' % (heading, rail, head, content))


def page_head(heading, subtitle, action):
    """The title with its subtitle beside it and the page's one action on
    the same row. A subtitle given as (text, note) puts the note on a line
    of its own under the title, so a long one does not push the action
    off the row."""
    note = ""
    if isinstance(subtitle, tuple):
        subtitle, note = subtitle
    btn = ""
    if action:
        btn = ('              <a class="pf-v6-c-button pf-m-secondary" href="%s">'
               '<span class="pf-v6-c-button__text">%s</span></a>\n' % (esc(action[1]), esc(action[0])))
    sub = ' <span class="subtitle">%s</span>' % esc(subtitle) if subtitle else ""
    title = '<h1 class="page-title" id="page-title">%s%s</h1>' % (esc(heading), sub)
    if note:
        title = '<div>%s<p class="page-note">%s</p></div>' % (title, esc(note))
    return ('            <div class="page-head">\n'
            '              %s\n%s'
            '            </div>\n' % (title, btn))
