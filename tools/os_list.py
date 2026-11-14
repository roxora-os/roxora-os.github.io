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
"""The Raspberry Pi Imager repository file, os_list.json.

tools/build.py calls make() to write it from the release catalogs. Run this
file to check a written one against the schema Imager publishes:

    python3 tools/os_list.py check _site/os_list.json

The check needs the jsonschema package (pip install jsonschema). The schema is
doc/json-schema/os-list-schema.json in raspberrypi/rpi-imager, read at the
commit pinned below so that a change upstream shows up as a deliberate bump
here rather than as a failed deploy. It is the format Imager 2 reads from
its default os_list_imagingutility_v4.json and from a custom repository URL.

How Imager uses the file (rpi-imager src/imagewriter.cpp,
filterOsListWithHWTags): "imager.devices" is the list it offers under
"Choose device", and each OS entry is shown only for the devices whose tags
appear in its "devices". Roxora lists its own boards there, tagged with the
Armbian board name, so choosing a board shows the images for that board. No
Raspberry Pi model is in the list, so none can be chosen. Imager does not
detect the hardware on desktop builds; the embedded build matches the Pi it
runs on by name against imager.devices, finds none here, and does not filter.
Nothing stops a card being written for a Pi; it just will not boot there.
"""

import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMAGER_COMMIT = "88d84f3797753c77496da48aafddbdf242c2a948"
SCHEMA_URL = ("https://raw.githubusercontent.com/raspberrypi/rpi-imager/%s/"
              "doc/json-schema/os-list-schema.json" % IMAGER_COMMIT)


def ubuntu_order(version, branch="edge"):
    """Sort key: the newest Ubuntu LTS first (the default to offer), then
    newer Ubuntu before older, then the edge kernel before others. version
    is "26.04" or "24.04"; LTS releases are April releases of even years."""
    m = re.match(r"^(\d+)\.(\d+)", version or "")
    year, month = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    lts = month == 4 and year % 2 == 0
    return (not lts, -(year * 100 + month), branch != "edge", branch)


# Image flavors (images[].flavor in the catalog, FLAVOR in boards.conf), in
# the order they are listed: the name for a title and the one for a sentence.
# A catalog or boards.conf from before the desktop images has no flavor;
# those images are command line images.
FLAVORS = {
    "cli": ("Command line", "command line"),
    "gnome-minimal": ("GNOME minimal", "minimal GNOME desktop"),
    "gnome": ("GNOME", "GNOME desktop"),
}


def flavor(item):
    """The flavor of a catalog image or a boards.conf row."""
    return item.get("flavor") or "cli"


def flavor_name(item, sentence=False):
    f = flavor(item)
    return FLAVORS.get(f, (f, f))[1 if sentence else 0]


def flavor_order(item):
    f = flavor(item)
    return list(FLAVORS).index(f) if f in FLAVORS else len(FLAVORS)


def newest_images(catalogs):
    """One image per board, Ubuntu release, kernel branch and flavor: the
    one from the newest release that has it. Catalogs arrive newest first."""
    seen, out = set(), []
    for cat in catalogs:
        for img in cat["images"]:
            key = (img["board"], img["release"], img["branch"], flavor(img))
            if key in seen:
                continue
            seen.add(key)
            out.append((cat["release"], img))
    out.sort(key=lambda ri: (ri[1]["board"], ubuntu_order(ri[1].get("ubuntu_version"), ri[1]["branch"]),
                             flavor_order(ri[1])))
    return out


def describe(release, img):
    status = ("Tested on hardware." if img["status"] == "hardware-tested"
              else "Built and checked in CI, not yet tested on hardware.")
    return ("Ubuntu %s (%s)%s with the Armbian %s kernel %s. Version %s%s. %s"
            % (img["ubuntu_version"], img["release"],
               "" if flavor(img) == "cli" else ", " + flavor_name(img, sentence=True) + ",",
               img["branch"], img["kernel"],
               release["version"], ", pre-release" if release["prerelease"] else "",
               status)
            + (" Needs UEFI firmware, such as edk2-rk3576, on the board."
               if img.get("firmware") == "uefi" else ""))


def make(catalogs, boards, site):
    """boards: rows of boards.conf as tools/boards.py reads them."""
    devices, tags = [], set()
    for row in boards:
        board, soc, name = row["board"], row["soc"], row["name"]
        if board in tags:
            continue
        tags.add(board)
        devices.append({"name": name, "description": soc.upper(), "tags": [board],
                        "matching_type": "exclusive", "architecture": "armv8"})
    entries = []
    for release, img in newest_images(catalogs):
        if img["board"] not in tags:
            # A board dropped from boards.conf whose last image is still
            # downloadable: it stays choosable until that image ages out.
            tags.add(img["board"])
            devices.append({"name": img["board_name"], "description": img["soc"].upper(),
                            "tags": [img["board"]], "matching_type": "exclusive",
                            "architecture": "armv8"})
        entries.append({
            # A command line image keeps the name it had before the desktop
            # images existed.
            "name": "Roxora %s for %s, Ubuntu %s%s%s" % (
                release["version"], img["board_name"], img["ubuntu_version"],
                "" if img["branch"] == "edge" else ", %s kernel" % img["branch"],
                "" if flavor(img) == "cli" else ", " + flavor_name(img, sentence=True)),
            "description": describe(release, img),
            "icon": site + "/assets/brand/roxora-mark-40.png",
            "website": site + "/download/",
            "url": img["url"],
            "extract_size": img["extract_size"],
            "extract_sha256": img["extract_sha256"],
            "image_download_size": img["size"],
            "image_download_sha256": img["sha256"],
            "release_date": release["date"],
            "devices": [img["board"]],
            "architecture": "armv8",
            # Imager's customisation writes its settings to the image's FAT
            # boot partition, laid out the Raspberry Pi way. Roxora seeds
            # cloud-init from its own root filesystem, and nothing has tested
            # whether Imager's settings would reach it, so the option is not
            # offered rather than offered and possibly ignored.
            "init_format": "none",
        })
    return {"imager": {"devices": devices}, "os_list": entries}


HEX64 = re.compile(r"^[0-9a-f]{64}$")


def check(path):
    try:
        import jsonschema
    except ImportError:
        sys.exit("os_list.py check needs jsonschema: pip install jsonschema")
    with urllib.request.urlopen(SCHEMA_URL, timeout=60) as r:
        schema = json.loads(r.read())
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=str)
    problems = ["schema: %s at %s" % (e.message, "/".join(map(str, e.absolute_path)))
                for e in errors]

    # What the schema leaves open but Imager needs: its notes ask for at least
    # one device per entry, and it refuses to write when extract_sha256 is
    # wrong, so a malformed one is caught here rather than on someone's card.
    tags = {t for d in doc.get("imager", {}).get("devices", []) for t in d["tags"]}
    for i, e in enumerate(doc["os_list"]):
        if not e.get("devices"):
            problems.append("os_list[%d]: no devices" % i)
        for d in e.get("devices", []):
            if d not in tags:
                problems.append("os_list[%d]: device %r is not in imager.devices" % (i, d))
        for k in ("extract_sha256", "image_download_sha256"):
            if not HEX64.match(e.get(k, "")):
                problems.append("os_list[%d]: %s is not a sha256" % (i, k))
        if not e["url"].startswith("https://"):
            problems.append("os_list[%d]: url is not https" % i)
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", e["release_date"]):
            problems.append("os_list[%d]: release_date is not YYYY-MM-DD" % i)

    for p in problems:
        print(p)
    print("%s: %d devices, %d images, %s (schema at rpi-imager %s)"
          % (path, len(tags), len(doc["os_list"]),
             "%d problems" % len(problems) if problems else "valid",
             IMAGER_COMMIT[:12]))
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check":
        sys.exit(check(sys.argv[2]))
    sys.exit(__doc__)
