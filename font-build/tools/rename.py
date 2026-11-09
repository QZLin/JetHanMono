#!/usr/bin/env python3
"""Rename the merged font family to 'JetHan Mono' (all weights).

Why a rename at all:
  Source Han Mono / Noto Sans Mono CJK OFL declares "Source"/"Noto" as
  Reserved Font Name, so a derivative must not carry those names.
  "JetHan Mono" avoids every reserved string (and JetBrains Mono's OFL
  has no Reserved Font Name clause at all).

This script REBUILDS the name table instead of patching a few IDs, so no
leftover metadata from either upstream survives:

  - deleted leftovers: 7 (trademark - described JetBrains Mono, wrong font),
    11/12 (vendor URL - JetBrains only), 250+ (JetBrains variable-font axis
    names like "Broken equals ligatures")
  - nameID 0/9/10 now credit BOTH upstream projects (OFL requires the
    copyright notices of the original fonts be preserved)
  - nameID 5 gets its own version, not JetBrains' 2.304

Multi-weight naming follows the Microsoft legacy family/subfamily model:
  - RIBBI styles (Regular/Bold):  nameID 1 = "JetHan Mono",
    nameID 2 = "Regular"/"Bold"  -> apps can style-link them
  - other weights (Thin .. ExtraBold/Black): nameID 1 = "JetHan Mono <Weight>"
    (legacy family), nameID 2 = "Regular" (legacy subfamily), and the
    typographic pair nameID 16 = "JetHan Mono" / 17 = "<Weight>" carries the
    real grouping.  This is exactly how Noto/JetBrains ship their statics.
  - fsSelection REGULAR(0x40)/BOLD(0x20) bits and head.macStyle bold bit are
    enforced per weight so apps don't mis-detect RIBBI status.

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

# usWeightClass -> subfamily/weight name (Microsoft + Google Fonts naming)
WEIGHT_NAMES = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
}
RIBBI = ("Regular", "Bold")

# JetBrains Mono's vertical metrics (upm=1000): hhea 1020/-300/0 and
# OS/2 win/typo identical.  The merged font must copy these EXACTLY so the
# editor line height is indistinguishable from plain JetBrains Mono.
JB_V_ASCENT = 1020
JB_V_DESCENT = -300

# fsSelection bits
FS_ITALIC = 0x0001
FS_BOLD = 0x0020
FS_REGULAR = 0x0040
# head.macStyle bits
MAC_BOLD = 0x0001
MAC_ITALIC = 0x0002

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

# IDs we fully control (rebuilt from scratch below); 16/17 added per weight
SET_IDS = (0, 1, 2, 3, 4, 5, 6, 9, 10, 13, 14, 16, 17)


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
    if weight not in WEIGHT_NAMES:
        sys.exit(f"ERROR: {path}: unknown usWeightClass {weight} - "
                 f"expected one of {sorted(WEIGHT_NAMES)}")
    sub = WEIGHT_NAMES[weight]
    ps = FAMILY.replace(" ", "") + "-" + sub
    full = f"{FAMILY} {sub}"

    # 1) wipe everything: leftovers (trademark/vendor/axis names) and the
    #    IDs we are about to set
    name.names = [r for r in name.names if r.nameID in SET_IDS]

    # 2) write the full, clean set
    set_name(f, 0, COPYRIGHT)
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

    # legacy family/subfamily (1/2) + typographic family/subfamily (16/17)
    if sub in RIBBI:
        set_name(f, 1, FAMILY)            # family
        set_name(f, 2, sub)               # subfamily
    else:
        # non-RIBBI: legacy family must be unique per weight, legacy
        # subfamily folds to "Regular"; 16/17 carry the real grouping
        set_name(f, 1, f"{FAMILY} {sub}")  # legacy family
        set_name(f, 2, "Regular")          # legacy subfamily
        set_name(f, 16, FAMILY)            # typographic family
        set_name(f, 17, sub)               # typographic subfamily

    # NOTE: nameID 7 (trademark), 11/12 (vendor) and 256+ (fvar axis labels)
    # are intentionally absent.

    # 3) fsSelection / macStyle: enforce RIBBI bits per weight so apps
    #    (Windows font picker, LibreOffice, macOS font book) classify right
    #    非 RIBBI 字重的 legacy subfamily 是 "Regular", 同样置 REGULAR 位
    #    (只有 Bold 例外 -> BOLD 位); 保留 USE_TYPO_METRICS(0x80) 等其它位
    fs = f["OS/2"].fsSelection
    fs &= ~(FS_REGULAR | FS_BOLD | FS_ITALIC)
    if weight == 700:
        fs |= FS_BOLD
    else:
        fs |= FS_REGULAR
    f["OS/2"].fsSelection = fs

    mac = f["head"].macStyle
    mac &= ~(MAC_BOLD | MAC_ITALIC)
    if weight == 700:
        mac |= MAC_BOLD
    f["head"].macStyle = mac

    # metric fixup: CJK glyphs are 1200u wide; JetBrains' hhea.advanceWidthMax
    # was 600, which no longer describes the merged font
    amax = max(a for a, _lsb in f["hmtx"].metrics.values())
    f["hhea"].advanceWidthMax = amax

    # vertical metrics: LOCK to the exact JetBrains Mono values.
    # The Merger merges numeric fields with max(), so hhea.ascent picked up
    # the CJK source's 1160 (vs JetBrains' 1020) and usWinAscent likewise,
    # making the editor line height ~10% taller than plain JetBrains Mono.
    # Renderers disagree on WHICH table they honour: engines that respect
    # OS/2 fsSelection USE_TYPO_METRICS(0x80) read sTypo* (already 1020/-300),
    # but Windows DirectWrite inside the JetBrains Runtime and several other
    # stacks read hhea/usWin* directly.  Setting ALL three metric sources to
    # the same JetBrains values makes the line height identical to plain
    # JetBrains Mono no matter which table the engine reads.
    # Safety: CJK ink tops out around y=880-920 and bottoms at ~-140, well
    # inside the 1020/-300 box, so no glyph gets clipped by this.
    os2 = f["OS/2"]
    f["hhea"].ascent = JB_V_ASCENT
    f["hhea"].descent = JB_V_DESCENT
    f["hhea"].lineGap = 0
    os2.sTypoAscender = JB_V_ASCENT
    os2.sTypoDescender = JB_V_DESCENT
    os2.sTypoLineGap = 0
    os2.usWinAscent = JB_V_ASCENT
    os2.usWinDescent = -JB_V_DESCENT
    # keep the USE_TYPO_METRICS bit so typo-metric engines stay consistent

    # fontTools Merger 将 isFixedPitch 清零; 恢复上游 JBM 的 1 (等宽声明,
    # Windows 命令提示符 / gVim / 部分检测器会读取; JetBrains IDE 不读它)
    f["post"].isFixedPitch = 1

    f.save(path)
    n16 = name.getDebugName(16)
    print(f"{path}: family(1)='{name.getDebugName(1)}' sub(2)='{name.getDebugName(2)}' "
          f"typo16={n16!r} typo17={name.getDebugName(17)!r} ps='{ps}' v={VERSION} "
          f"weightClass={weight} fsSelection={fs:#06x} macStyle={mac:#04x} "
          f"nameRecords={len(name.names)} advanceWidthMax={amax} "
          f"hheaAsc={f['hhea'].ascent} hheaDesc={f['hhea'].descent} "
          f"winAsc={os2.usWinAscent} winDesc={os2.usWinDescent}")


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit("usage: rename.py <font.ttf> [more.ttf ...]  |  --license-only <output_dir>")

    # --license-only: just (re)write JetHanMono-OFL.txt, no font touched.
    # Used by build.sh's incremental OFL step so the license has its own
    # dependency fingerprint (JetBrains OFL text + this script) independent
    # of the per-weight rename steps.
    if argv[0] == "--license-only":
        if len(argv) != 2:
            sys.exit("usage: rename.py --license-only <output_dir>")
        out_dir = argv[1]
        if not os.path.isdir(out_dir):
            sys.exit(f"ERROR: output dir not found: {out_dir}")
        lic = make_license_text()
        lic_path = os.path.join(out_dir, "JetHanMono-OFL.txt")
        with open(lic_path, "w", encoding="utf-8") as fh:
            fh.write(lic)
        print(f"license file written: {lic_path} ({len(lic)} bytes)")
        return

    for p in argv:
        rename_font(p)

    lic = make_license_text()
    lic_path = os.path.join(os.path.dirname(argv[0]) or ".", "JetHanMono-OFL.txt")
    with open(lic_path, "w", encoding="utf-8") as fh:
        fh.write(lic)
    print(f"license file written: {lic_path} ({len(lic)} bytes)")


if __name__ == "__main__":
    main()
