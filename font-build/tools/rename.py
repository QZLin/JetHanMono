#!/usr/bin/env python3
"""Rename the merged font family to 'JetHan Mono' (Regular/Bold).

Why a rename at all:
  Source Han Mono / Noto Sans Mono CJK OFL declares "Source"/"Noto" as
  Reserved Font Name, so a derivative must not carry those names.
  "JetHan Mono" avoids every reserved string (and JetBrains Mono's OFL
  has no Reserved Font Name clause at all).

This script REBUILDS the name table instead of patching a few IDs, so no
leftover metadata from either upstream survives:

  - deleted leftovers: 7 (trademark - described JetBrains Mono, wrong font),
    11/12 (vendor URL - JetBrains only), 16/17 (duplicated 1/2, redundant
    for a simple RIBBI family), 250+ (JetBrains variable-font axis names
    like "Broken equals ligatures")
  - nameID 0/9/10 now credit BOTH upstream projects (OFL requires the
    copyright notices of the original fonts be preserved)
  - nameID 5 gets its own version, not JetBrains' 2.304

Also writes output/JetHanMono-OFL.txt (both copyright headers + OFL 1.1
body) for distribution compliance.

Usage: rename.py <font.ttf> [more.ttf ...]
"""
import os
import sys
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY = "JetHan Mono"
VERSION = "1.000"
BUILDER = "fontbuild"

COPYRIGHT = (
    "Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)\n"
    "Copyright 2014-2021 Adobe (http://www.adobe.com/)\n"
    "JetHan Mono is a merged derivative of JetBrains Mono and Source Han Mono "
    "(via Noto Sans Mono CJK SC), licensed under the SIL Open Font License 1.1."
)
DESIGNER = (
    "Philipp Nurullin, Konstantin Bulenkov (JetBrains Mono); "
    "Ryoko NISHIZUKA, Paul D. Hunt (Source Han Mono)"
)
DESCRIPTION = (
    "Merged monospace font: JetBrains Mono glyphs (Latin, code, programming "
    "ligatures) take priority; Source Han Mono glyphs fill Chinese/CJK. "
    "Ligatures via JetBrains GSUB (calt) preserved; CJK advances scaled to "
    "1200/1000em = exactly 2x the Latin 600u advance (terminal 2:1), "
    "ink centered with symmetric side bearings."
)

# IDs we fully control (rebuilt from scratch below)
SET_IDS = (0, 1, 2, 3, 4, 5, 6, 9, 10, 13, 14)


def set_name(font, nameID, value):
    """Set one record on Windows(3,1,en-US) + Macintosh(1,0,Roman/English).

    Mac Roman cannot encode arbitrary text (e.g. CJK) - skip the Mac record
    for non-ASCII values rather than risking a save-time encode error.
    """
    name = font["name"]
    name.names = [r for r in name.names if r.nameID != nameID]
    name.setName(value, nameID, 3, 1, 0x409)  # Windows, Unicode BMP, en-US
    if value.isascii():
        name.setName(value, nameID, 1, 0, 0)  # Macintosh, Roman, English


def make_license_text():
    """Both upstream copyright headers + the standard OFL 1.1 body."""
    jb_path = os.path.join(HERE, "..", "downloads", "JetBrainsMono-OFL.txt")
    body = ""
    if os.path.exists(jb_path):
        lines = open(jb_path, encoding="utf-8").read().splitlines()
        # drop JetBrains' own copyright header (first non-empty line(s));
        # the OFL body starts at "This Font Software is licensed..."
        start = next(i for i, l in enumerate(lines) if l.startswith("This Font Software"))
        body = "\n".join(lines[start:]).strip()
    header = (
        "JetHan Mono\n"
        "Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)\n"
        "Copyright 2014-2021 Adobe (http://www.adobe.com/)\n"
        "\n"
        "This Font Software is a merged derivative of JetBrains Mono and\n"
        "Source Han Mono (distributed by Google as Noto Sans Mono CJK SC),\n"
        "renamed to comply with the Reserved Font Names of the original fonts.\n"
    )
    return header + "\n" + body + "\n"


def rename_font(path):
    f = TTFont(path)
    name = f["name"]
    weight = f["OS/2"].usWeightClass
    sub = "Bold" if weight >= 600 else "Regular"
    ps = FAMILY.replace(" ", "") + "-" + sub
    full = f"{FAMILY} {sub}"

    # 1) wipe everything: leftovers (trademark/vendor/axis names) and the
    #    IDs we are about to set
    name.names = [r for r in name.names if r.nameID in SET_IDS]

    # 2) write the full, clean set
    set_name(f, 0, COPYRIGHT)
    set_name(f, 1, FAMILY)                                  # family
    set_name(f, 2, sub)                                     # subfamily
    set_name(f, 3, f"{ps};{VERSION};{BUILDER}")             # unique ID
    set_name(f, 4, full)                                    # full name
    set_name(f, 5, f"Version {VERSION};{BUILDER}")          # version (was JetBrains' 2.304)
    set_name(f, 6, ps)                                      # PostScript name
    set_name(f, 9, DESIGNER)                                # designer
    set_name(f, 10, DESCRIPTION)                            # description
    set_name(f, 13, ("This Font Software is licensed under the SIL Open Font License, "
                     "Version 1.1. This license is available with a FAQ at: "
                     "https://scripts.sil.org/OFL"))
    set_name(f, 14, "https://scripts.sil.org/OFL")

    # NOTE: nameID 7 (trademark), 11/12 (vendor), 16/17 (typographic names,
    # redundant when identical to 1/2) and 256+ (fvar axis labels) are
    # intentionally absent.

    # metric fixup: CJK glyphs are 1200u wide; JetBrains' hhea.advanceWidthMax
    # was 600, which no longer describes the merged font
    amax = max(a for a, _lsb in f["hmtx"].metrics.values())
    f["hhea"].advanceWidthMax = amax

    f.save(path)
    print(f"{path}: family='{FAMILY}' sub='{sub}' ps='{ps}' v={VERSION} "
          f"weightClass={weight} fsSelection={f['OS/2'].fsSelection:#06x} "
          f"macStyle={f['head'].macStyle:#04x} nameRecords={len(name.names)} "
          f"advanceWidthMax={amax}")


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit("usage: rename.py <font.ttf> [more.ttf ...]")

    for p in paths:
        rename_font(p)

    lic = make_license_text()
    lic_path = os.path.join(os.path.dirname(paths[0]) or ".", "JetHanMono-OFL.txt")
    with open(lic_path, "w", encoding="utf-8") as fh:
        fh.write(lic)
    print(f"license file written: {lic_path} ({len(lic)} bytes)")


if __name__ == "__main__":
    main()
