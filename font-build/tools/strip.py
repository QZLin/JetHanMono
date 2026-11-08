#!/usr/bin/env python3
"""Strip layout/vertical/DSIG tables + cmap14 from a converted CJK TTF.

We only need cmap + glyf + metrics from the CJK font. Removing GSUB/GPOS/GDEF
prevents pyftmerge from running its layout-merging code path (JetBrains Mono
keeps being the sole owner of ligature shaping). Vertical tables are dropped
because the merged font targets horizontal text.
"""
import sys
from fontTools.ttLib import TTFont

src, dst = sys.argv[1], sys.argv[2]
DROP = ["GSUB", "GPOS", "GDEF", "DSIG", "vhea", "vmtx", "VORG", "feat", "morx", "kern"]

f = TTFont(src)
for t in DROP:
    if t in f:
        del f[t]
        print(f"dropped {t}")

cmap = f["cmap"]
before = len(cmap.tables)
cmap.tables = [t for t in cmap.tables if t.format != 14]
if len(cmap.tables) != before:
    print(f"dropped {before - len(cmap.tables)} cmap format-14 (UVS) subtable(s)")

f.save(dst)
print(f"saved {dst}, glyphs={f['maxp'].numGlyphs}")
