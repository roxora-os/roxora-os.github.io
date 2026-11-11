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
"""Read boards.conf from roxora-os/build.

    python3 tools/boards.py cache/upstream/boards.conf

The columns are not fixed: the file names them in a comment line that starts
with BOARD and ends with NAME, for example

    # BOARD          BRANCH  RELEASE  STATUS   SOC     VENDOR  NAME

and that line is what this parser follows. Counting fields cannot tell the
columns apart, because NAME is the rest of the line and holds spaces of its
own ("Radxa ROCK 4D"). Every column but NAME is one word. VENDOR is optional:
a file written before it existed gets the first word of NAME instead.

A file without that header, without a column the site needs, with a line
that has too few fields, or with a NAME that does not start with its VENDOR
(a line that left VENDOR out) stops the build with the line in question,
rather than publishing a Boards page with columns shifted by one.
"""

import sys

REQUIRED = ("BOARD", "BRANCH", "RELEASE", "STATUS", "SOC", "NAME")


def parse(text, where="boards.conf"):
    """Rows of boards.conf as dicts with lower-case keys: board, branch,
    release, status, soc, vendor, name."""
    columns, rows = None, []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            words = line.lstrip("#").split()
            if words and words[0] == "BOARD" and words[-1] == "NAME":
                columns = words
                missing = [c for c in REQUIRED if c not in columns]
                if missing:
                    sys.exit("%s:%d: header has no %s column"
                             % (where, number, ", ".join(missing)))
            continue
        if columns is None:
            sys.exit("%s:%d: data before the '# BOARD ... NAME' header line" % (where, number))
        parts = line.split(None, len(columns) - 1)
        if len(parts) < len(columns):
            sys.exit("%s:%d: %d fields, the header names %d (%s): %r"
                     % (where, number, len(parts), len(columns), " ".join(columns), raw))
        row = {c.lower(): v for c, v in zip(columns, parts)}
        # NAME carries the vendor too ("Radxa ROCK 4D" under Radxa). A line
        # that left VENDOR out would otherwise shift the name's first word
        # into it and read as valid.
        if "vendor" in row and row["name"].split()[0] != row["vendor"]:
            sys.exit("%s:%d: NAME %r does not start with VENDOR %r: %r"
                     % (where, number, row["name"], row["vendor"], raw))
        row.setdefault("vendor", row["name"].split()[0])
        rows.append(row)
    if columns is None:
        sys.exit("%s: no '# BOARD ... NAME' header line naming the columns" % where)
    return rows


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for r in parse(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1]):
        print("%(vendor)-8s %(board)-16s %(branch)-6s %(release)-8s %(status)-15s %(soc)-7s %(name)s" % r)
