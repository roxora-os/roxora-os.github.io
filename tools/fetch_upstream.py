#!/usr/bin/env python3
# Copyright (C) 2026 Ga Hing Woo <gahing@gahingwoo.com>
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
"""Fetch what the site is built from out of roxora-os/build.

    python3 tools/fetch_upstream.py
    python3 tools/fetch_upstream.py --local ../build
    python3 tools/fetch_upstream.py --local ../build --sample ../build/docs/sample-catalog.json

Writes cache/upstream/: boards.conf, docs/*.md, releases.json, which holds
the roxora-catalog.json of every published release, newest first,
imager.json, the newest release of Roxora Imager (roxora-os/imager), and
synced.json, the time of this fetch. The
catalog format is docs/release-contract.md in roxora-os/build.

--local reads boards.conf and docs/ from a checkout instead of GitHub.
--sample uses that catalog file as the only release, for testing; a build
from it refuses to write the live site (see tools/build.py).

Any network or format error exits non-zero. In CI that stops the deploy and
the site that is already live stays up, which is better than replacing it
with one that says there are no releases because GitHub did not answer.
GITHUB_TOKEN, when set, is sent with API requests for the higher rate limit.
"""

import json
import os
import pathlib
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import boards as boards_conf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "cache" / "upstream"
REPO = "roxora-os/build"
API = "https://api.github.com/repos/" + REPO
RAW = "https://raw.githubusercontent.com/%s/main/" % REPO
CATALOG = "roxora-catalog.json"
RELEASES = "https://github.com/%s/releases/" % REPO
DOWNLOAD = RELEASES + "download/"


def get(url, api=False):
    headers = {"User-Agent": "roxora-site-build"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        sys.exit("fetch_upstream: %s: %s" % (url, e))


def get_json(url, api=False):
    try:
        return json.loads(get(url, api))
    except ValueError as e:
        sys.exit("fetch_upstream: %s: not JSON: %s" % (url, e))


def check_catalog(cat, where):
    """The fields the site reads. A catalog missing one is a broken release,
    and publishing a page with holes in it would hide that."""
    if cat.get("schema") != 1:
        sys.exit("fetch_upstream: %s: catalog schema %r, this site reads 1"
                 % (where, cat.get("schema")))
    for k in ("tag", "version", "date", "prerelease", "url"):
        if k not in cat.get("release", {}):
            sys.exit("fetch_upstream: %s: release.%s missing" % (where, k))
    for i, img in enumerate(cat.get("images", [])):
        for k in ("board", "board_name", "soc", "release", "ubuntu_version",
                  "branch", "kernel", "file", "url", "size", "sha256",
                  "extract_size", "extract_sha256", "status"):
            if k not in img:
                sys.exit("fetch_upstream: %s: images[%d].%s missing" % (where, i, k))
        for k in ("file", "url", "size", "sha256"):
            if "spi" in img and k not in img["spi"]:
                sys.exit("fetch_upstream: %s: images[%d].spi.%s missing" % (where, i, k))


def trusted(cat, where):
    """Keep only what downloads from this repository's own releases. The
    website, the catalog copies under /catalog/ and the Raspberry Pi Imager
    file all link what is kept here, so a catalog that names any other
    address for a file must not get that address onto the site: the image is
    left out (or its SPI image, or its verify output), and the build says so."""
    def ok(url):
        return isinstance(url, str) and url.startswith(DOWNLOAD)
    if not (isinstance(cat["release"]["url"], str)
            and cat["release"]["url"].startswith(RELEASES)):
        print("note: %s: release.url is not a release of %s, replaced" % (where, REPO))
        cat["release"]["url"] = RELEASES.rstrip("/")
    kept = []
    for img in cat.get("images", []):
        if not ok(img["url"]):
            print("note: %s: %s is not downloaded from %s, left out" % (where, img["file"], DOWNLOAD))
            continue
        if "spi" in img and not ok(img["spi"]["url"]):
            print("note: %s: the SPI image of %s is not downloaded from %s, left out"
                  % (where, img["file"], DOWNLOAD))
            del img["spi"]
        if "verify_url" in img and not ok(img["verify_url"]):
            print("note: %s: the verify output of %s is not downloaded from %s, left out"
                  % (where, img["file"], DOWNLOAD))
            del img["verify_url"]
        kept.append(img)
    cat["images"] = kept
    return cat


def releases():
    out, page = [], 1
    while True:
        batch = get_json("%s/releases?per_page=100&page=%d" % (API, page), api=True)
        if not batch:
            break
        for rel in batch:
            if rel.get("draft"):
                continue
            asset = next((a for a in rel.get("assets", []) if a["name"] == CATALOG), None)
            if asset is None:
                # A release still uploading, or one made by hand. It has no
                # catalog to read, so it is not listed; the build says so.
                print("note: %s has no %s, skipped" % (rel["tag_name"], CATALOG))
                continue
            cat = get_json(asset["browser_download_url"])
            check_catalog(cat, rel["tag_name"])
            cat = trusted(cat, rel["tag_name"])
            if not cat["images"]:
                print("note: %s has no image to list, skipped" % rel["tag_name"])
                continue
            if "_sample" in cat:
                sys.exit("fetch_upstream: %s: catalog is marked as sample data" % rel["tag_name"])
            # GitHub's flag is what a visitor sees on the release page, so it
            # wins over the catalog's copy if the two ever disagree.
            cat["release"]["prerelease"] = bool(rel.get("prerelease"))
            out.append(cat)
        page += 1
    out.sort(key=lambda c: (c["release"]["date"], c["release"]["version"]), reverse=True)
    return out


IMAGER = "roxora-os/imager"
IMAGER_DOWNLOAD = "https://github.com/%s/releases/download/" % IMAGER


def imager_release():
    """The newest published release of Roxora Imager, pre-releases
    included, with only the assets that download from its own releases.
    None when there is no release yet."""
    batch = get_json("https://api.github.com/repos/%s/releases?per_page=20" % IMAGER, api=True)
    rel = next((r for r in batch if not r.get("draft")), None)
    if rel is None:
        return None
    assets = []
    for a in rel.get("assets", []):
        url = a.get("browser_download_url", "")
        if not url.startswith(IMAGER_DOWNLOAD):
            print("note: imager %s: %s is not downloaded from %s, left out"
                  % (rel["tag_name"], a.get("name"), IMAGER_DOWNLOAD))
            continue
        assets.append({"name": a["name"], "url": url, "size": a.get("size", 0)})
    url = rel.get("html_url", "")
    if not url.startswith("https://github.com/%s/releases/" % IMAGER):
        url = "https://github.com/%s/releases" % IMAGER
    return {"tag": rel["tag_name"], "name": rel.get("name") or rel["tag_name"],
            "prerelease": bool(rel.get("prerelease")),
            "date": (rel.get("published_at") or "")[:10], "url": url, "assets": assets}


def main(argv):
    local = sample = None
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--local" and args:
            local = pathlib.Path(args.pop(0))
        elif a == "--sample" and args:
            sample = pathlib.Path(args.pop(0))
        else:
            sys.exit(__doc__)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "docs").mkdir(parents=True)

    if local:
        shutil.copy(local / "boards.conf", OUT / "boards.conf")
        names = sorted(p.name for p in (local / "docs").glob("*.md"))
        for n in names:
            shutil.copy(local / "docs" / n, OUT / "docs" / n)
    else:
        (OUT / "boards.conf").write_bytes(get(RAW + "boards.conf"))
        listing = get_json(API + "/contents/docs?ref=main", api=True)
        names = sorted(f["name"] for f in listing
                       if f["type"] == "file" and f["name"].endswith(".md"))
        for n in names:
            (OUT / "docs" / n).write_bytes(get(RAW + "docs/" + n))

    # Read it now, so a malformed boards.conf fails the fetch with the line
    # in question rather than surfacing later in the build.
    boards = boards_conf.parse((OUT / "boards.conf").read_text(encoding="utf-8"))
    print("boards.conf: %d boards, columns understood" % len(boards))

    if sample:
        cat = json.loads(sample.read_text(encoding="utf-8"))
        check_catalog(cat, str(sample))
        cat = trusted(cat, str(sample))
        cats = [cat]
    else:
        cats = releases()
    (OUT / "synced.json").write_text(json.dumps({
        "synced": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}) + "\n",
        encoding="utf-8")
    imager = imager_release()
    (OUT / "imager.json").write_text(json.dumps(imager, indent=1) + "\n", encoding="utf-8")
    print("imager: %s" % (imager["tag"] if imager else "no release"))
    (OUT / "releases.json").write_text(
        json.dumps(cats, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print("boards.conf, %d docs (%s), %d releases%s"
          % (len(names), ", ".join(names) or "none", len(cats),
             " (SAMPLE)" if sample else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
