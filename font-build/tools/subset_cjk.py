#!/usr/bin/env python3
"""Subset the CJK font to only the codepoints JetBrains Mono does NOT cover.

Needed because Noto Sans Mono CJK SC already has 65,535 glyphs (the OpenType
maximum); merging JetBrains' 1,743 glyphs on top would overflow GID space.
After this step the subset has ~44k glyphs, leaving headroom for the merge.

Usage: subset_cjk.py <jetbrains.ttf> <cjk.otf> <out.otf>
"""
import sys
from fontTools import subset
from fontTools.ttLib import TTFont

jb_path, cjk_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

jb_cps = set(TTFont(jb_path).getBestCmap().keys())
cjk = TTFont(cjk_path)
cjk_cps = set(cjk.getBestCmap().keys())

needed = sorted(cjk_cps - jb_cps)
overlap = len(cjk_cps & jb_cps)
print(f"source-han codepoints: {len(cjk_cps)}, overlap with JetBrains: {overlap}, keeping: {len(needed)}")

opts = subset.Options()
opts.notdef_outline = True          # keep a real tofu box
opts.recommended_glyphs = True
opts.name_IDs = ["*"]               # keep name records (rewritten later anyway)
opts.notdef_glyph = True
opts.glyph_names = True             # preserve cid#### names
opts.drop_tables += ["GSUB", "GPOS", "GDEF", "DSIG", "vhea", "vmtx", "VORG", "feat", "morx"]
opts.layout_features = []           # no shaping needed from the CJK side
opts.hinting = True
opts.unicodes = needed

ss = subset.Subsetter(opts)
ss.populate(unicodes=needed)
ss.subset(cjk)

# belt & braces: remove any cmap format-14 subtable left behind
cmap = cjk["cmap"]
cmap.tables = [t for t in cmap.tables if t.format != 14]

cjk.save(out_path)
left = TTFont(out_path)
print(f"saved {out_path}: glyphs={left['maxp'].numGlyphs} cmap={len(left.getBestCmap())}")
