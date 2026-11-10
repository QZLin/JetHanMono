#!/usr/bin/env python3
"""Verify the merged 'JetHan Mono' font.

Usage: verify.py <jetbrains.ttf> <sourcehan_converted.ttf> <merged.ttf>

Checks:
  A. upem consistency
  B. cmap priority  : every JetBrains codepoint still maps to a JetBrains glyph
                      (advance + outline identity), conflicting Source Han
                      mappings must NOT win
  C. CJK coverage   : Source-Han-only codepoints (CJK / fullwidth / CJK punct)
                      exist in the merged cmap; advances scaled to 1200u
                      (== 2 x JetBrains latin 600u, exact terminal 2:1)
  D. CJK outlines   : real contours, not blank
  E. ligatures      : every LigatureSubst mapping of JetBrains GSUB survives in
                      the merged GSUB; ligature glyphs carry outlines
  F. GPOS kerning   : JetBrains PairPos lookups survive
  G. name table     : family renamed correctly
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen

jb_path, sh_path, mg_path = sys.argv[1], sys.argv[2], sys.argv[3]

jb = TTFont(jb_path)
sh = TTFont(sh_path)
mg = TTFont(mg_path)

failures = []

def check(name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)

def outlines(font, gname):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    try:
        font.getGlyphSet()[gname].draw(pen)
    except Exception:
        return None
    return tuple(pen.value)

# ---------- A. upem ----------
check("A1 upem == 1000 in all fonts",
      jb["head"].unitsPerEm == sh["head"].unitsPerEm == mg["head"].unitsPerEm == 1000,
      f"jb={jb['head'].unitsPerEm} sh={sh['head'].unitsPerEm} mg={mg['head'].unitsPerEm}")

# ---------- cmap maps ----------
jb_cmap = jb.getBestCmap()
sh_cmap = sh.getBestCmap()
mg_cmap = mg.getBestCmap()
mg_order = set(mg.getGlyphOrder())

# ---------- B. cmap priority ----------
jb_only_problems = 0
sample_ok = 0
for cp, jb_g in jb_cmap.items():
    mg_g = mg_cmap.get(cp)
    if mg_g != jb_g:
        jb_only_problems += 1
        if jb_only_problems <= 5:
            print(f"    conflict cp=U+{cp:04X} jb={jb_g} merged={mg_g}")
    else:
        sample_ok += 1
check("B1 all JetBrains codepoints keep JetBrains glyphs",
      jb_only_problems == 0,
      f"{len(jb_cmap)} codepoints, {jb_only_problems} conflicts")

# strong spot-checks: advance + outline identity for representative Latin glyphs
for ch in "aAg=@fr->":
    cp = ord(ch)
    g = jb_cmap[cp]
    adv_ok = jb["hmtx"][g][0] == mg["hmtx"][g][0]
    out_ok = outlines(jb, g) == outlines(mg, g)
    check(f"B2 '{ch}' (U+{cp:04X}) advance+outline identical to JetBrains",
          adv_ok and out_ok, f"adv {jb['hmtx'][g][0]}/{mg['hmtx'][g][0]} outline={out_ok}")

# ---------- C. CJK coverage ----------
def cps_in(lo, hi, cmap):
    return sum(1 for c in cmap if lo <= c <= hi)

cjk_ranges = [(0x4E00, 0x9FFF, "CJK Unified Ideographs"),
              (0x3400, 0x4DBF, "CJK Ext A"),
              (0x3000, 0x303F, "CJK Symbols & Punct"),
              (0xFF00, 0xFFEF, "Fullwidth Forms"),
              (0x20000, 0x2A6DF, "CJK Ext B")]
print(f"    {'block':<24}{'jetbrains':>10}{'sourceHan':>11}{'merged':>9}")
for lo, hi, label in cjk_ranges:
    print(f"    {label:<24}{cps_in(lo,hi,jb_cmap):>10}{cps_in(lo,hi,sh_cmap):>11}{cps_in(lo,hi,mg_cmap):>9}")

for lo, hi, label in cjk_ranges:
    need = cps_in(lo, hi, sh_cmap) - cps_in(lo, hi, jb_cmap)
    got = cps_in(lo, hi, mg_cmap) - cps_in(lo, hi, jb_cmap)
    check(f"C1 {label}: Source-Han-only chars all added", got >= need, f"{got}/{need}")

# spot metrics: fullwidth advance 1200 (= 2 x JetBrains latin 600), centered ink
for cp, label in [(0x4E2D, "中"), (0x6587, "文"), (0x6D4B, "测"), (0x3002, "。"), (0xFF0C, "，"), (0x300C, "「")]:
    g = mg_cmap.get(cp)
    adv, lsb = mg["hmtx"][g] if g else (-1, -1)
    gl = mg["glyf"][g] if g else None
    xmin = gl.xMin if gl is not None and gl.numberOfContours > 0 else None
    rsb = (adv - gl.xMax) if xmin is not None else None
    check(f"C2 '{label}' U+{cp:04X} present, advance=1200",
          g is not None and adv == 1200,
          f"adv={adv} lsb={lsb} rsb={rsb}")

# C3: exact 2:1 terminal ratio + centered ideograph
adv_a = mg["hmtx"][jb_cmap[ord('a')]][0]
adv_zhong = mg["hmtx"][mg_cmap[0x4E2D]][0]
check("C3.1 ratio exactly 2:1 (中 advance == 2 x a == 1200)",
      adv_zhong == 2 * adv_a == 1200, f"a={adv_a} 中={adv_zhong}")

zhong_gl = mg["glyf"][mg_cmap[0x4E2D]]
zhong_lsb = mg["hmtx"][mg_cmap[0x4E2D]][1]
zhong_rsb = adv_zhong - zhong_gl.xMax
check("C3.2 '中' ink centered in its 1200u cell",
      abs(zhong_lsb - zhong_rsb) <= 6, f"lsb={zhong_lsb} rsb={zhong_rsb}")

half = mg_cmap.get(0xFF71)  # ｱ halfwidth katakana
if half:
    check("C3.3 halfwidth 'ｱ' advance=600 (== latin)",
          mg["hmtx"][half][0] == 600, f"adv={mg['hmtx'][half][0]}")

# C4: block-wide advance invariant over Source-Han-only codepoints.
# Wide grid = 1200 (== 2 x 600 latin); halfwidth = 600; Hangul normalized
# onto the wide grid; latin-width / proportional leftovers OUTSIDE these
# blocks are intentionally untouched (upstream-faithful).
def expect_adv(cp):
    if (0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF
            or 0x20000 <= cp <= 0x3FFFF          # ideographs incl. Ext B/C/D/E...
            or 0xF900 <= cp <= 0xFAFF
            or 0xFF01 <= cp <= 0xFF5E or 0xFFE0 <= cp <= 0xFFE6
            or 0xFE10 <= cp <= 0xFE6B            # vertical forms
            or 0x2FF0 <= cp <= 0x2FFB or 0x2E80 <= cp <= 0x2FDF  # IDC / radicals
            or 0x3040 <= cp <= 0x30FF            # kana
            or 0x2600 <= cp <= 0x27BF            # misc symbols designed full-width
            or 0x3000 <= cp <= 0x302D or 0x3030 <= cp <= 0x303D):
        return (1200, 0)
    if 0xFF61 <= cp <= 0xFF9F:
        return (600, 0)                          # halfwidth forms
    if (0x1100 <= cp <= 0x11FF or 0xA960 <= cp <= 0xA97F
            or 0xD7B0 <= cp <= 0xD7FF or 0xAC00 <= cp <= 0xD7A3):
        return (1200,)                           # Hangul -> wide grid
    if 0x3100 <= cp <= 0x31FF:
        return (1200, 600, 0)                    # bopomofo (few latin-width finals)
    return None

bad, checked, jb_prio = [], 0, 0
for cp, g in mg_cmap.items():
    if cp in jb_cmap:
        # JetBrains covers this codepoint too -> its 600u glyph/advance wins
        # by design (cmap priority); correctness of that is covered by B1/B2.
        jb_prio += 1
        continue
    exp = expect_adv(cp)
    if exp is None:
        continue
    checked += 1
    if mg["hmtx"][g][0] not in exp:
        bad.append((f"U+{cp:04X}", mg["hmtx"][g][0]))
check("C4 CJK block advances all 1200/600/0 (no odd widths)", not bad,
      f"{checked} codepoints checked, {jb_prio} jb-priority skipped"
      + (f", bad={bad[:6]}" if bad else ""))

# ---------- D. CJK outlines ----------
for cp, label in [(0x4E2D, "中"), (0x6587, "文"), (0x6C49, "汉")]:
    g = mg_cmap[cp]
    glyf = mg["glyf"][g]
    n = glyf.numberOfContours
    check(f"D1 '{label}' has contours ({n})", n and n > 0)

# ---------- E. ligatures ----------
def collect_ligs(font):
    """Return set of (first, components, ligGlyph) over all LigatureSubst subtables."""
    result = set()
    gsub = font.get("GSUB")
    if not gsub:
        return result
    for lookup in gsub.table.LookupList.Lookup:
        for st in lookup.SubTable:
            if hasattr(st, "ligatures"):
                for first, ligs in st.ligatures.items():
                    for lig in ligs:
                        result.add((first, tuple(lig.Component), lig.LigGlyph))
    return result

jb_ligs = collect_ligs(jb)
mg_ligs = collect_ligs(mg)
missing = jb_ligs - mg_ligs
check("E1 all JetBrains ligature substitutions survive", not missing,
      f"{len(jb_ligs)} mappings, {len(missing)} missing")
print(f"    ligature mappings: jb={len(jb_ligs)} merged={len(mg_ligs)}")
some = sorted(jb_ligs)[:8]
print("    sample:", some)

# ligature glyphs have outlines
lig_glyphs = sorted({lig for (_, _, lig) in jb_ligs})
no_ink = [g for g in lig_glyphs
          if g not in mg_order or not mg["glyf"][g].numberOfContours]
check("E2 ligature glyphs present with ink", not no_ink,
      f"{len(lig_glyphs)} ligature glyphs, bad: {no_ink[:5]}")

# feature tags preserved
def feats(font):
    g = font.get("GSUB")
    return sorted({r.FeatureTag for r in g.table.FeatureList.FeatureRecord}) if g else []
jf, mf = feats(jb), feats(mg)
check("E3 GSUB feature set preserved", set(jf) <= set(mf), f"{jf}")

# calt lookups count (JetBrains programming ligatures live in calt)
def lookup_count(font, tag):
    g = font.get("GSUB")
    if not g:
        return 0
    idxs = [r.LookupListIndex for r in g.table.FeatureList.FeatureRecord if r.FeatureTag == tag]
    return len(set(idxs))
check("E4 calt feature present", "calt" in mf)

# ---------- F. GPOS structural integrity ----------
def gpos_lookup_types(font):
    gpos = font.get("GPOS")
    if not gpos or not gpos.table.LookupList:
        return []
    return sorted(l.LookupType for l in gpos.table.LookupList.Lookup)

jb_types, mg_types = gpos_lookup_types(jb), gpos_lookup_types(mg)
# NOTE: JetBrains Mono is monospace -> it ships no kerning PairPos at all.
# The invariant we care about: the merged GPOS equals JetBrains' GPOS.
check("F1 JetBrains GPOS preserved (mono font has no kern pairs)", jb_types == mg_types,
      f"jb={jb_types} merged={mg_types}")

# ---------- G. name table ----------
mg_name = mg["name"]
fam = mg_name.getDebugName(16) or mg_name.getDebugName(1)
check("G1 family name == 'JetHan Mono'", fam == "JetHan Mono", f"got {fam!r}")
check("G2 PostScript name set", bool(mg_name.getDebugName(6)), mg_name.getDebugName(6))

# ---------- H. metadata completeness (rename.py 契约) ----------
# 只依赖合并字体自身; 确保改名步骤写入的元数据契约不回退.
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from os2_ranges import OS2_RANGES  # noqa: E402
from rename import (  # noqa: E402
    VERSION, MANUFACTURER, VENDOR_URL, VEND_ID, RELEASE_DATE,
    compute_unicode_ranges,
)

# head.fontRevision 是 16.16 定点数 (步长 1/65536 ≈ 1.53e-5): 三位小数版本号
# (如 1.001) 会被量化, 比较容差必须 ≥ 一个步长, 否则 1.000 之后所有版本必挂
FIXED16_16_EPS = 2e-5

check("H1 fontRevision == Version(nameID5)",
      abs(mg["head"].fontRevision - float(VERSION)) < FIXED16_16_EPS,
      f"fontRevision={mg['head'].fontRevision} vs 'Version {VERSION}'")
check("H2 nameID5/3 carry VERSION",
      (mg_name.getDebugName(5) or "").startswith(f"Version {VERSION}")
      and f";{VERSION};" in (mg_name.getDebugName(3) or ""),
      f"5={mg_name.getDebugName(5)!r} 3={mg_name.getDebugName(3)!r}")
check("H3 manufacturer/vendor URL set",
      mg_name.getDebugName(8) == MANUFACTURER
      and mg_name.getDebugName(11) == VENDOR_URL,
      f"8={mg_name.getDebugName(8)!r} 11={mg_name.getDebugName(11)!r}")
_have_ids = {r.nameID for r in mg_name.names}
check("H4 no trademark/designer-URL/axis-name leftovers",
      7 not in _have_ids and 12 not in _have_ids
      and not any(i >= 250 for i in _have_ids),
      f"ids>=250: {sorted(i for i in _have_ids if i >= 250)}")
_declared = [mg["OS/2"].ulUnicodeRange1, mg["OS/2"].ulUnicodeRange2,
             mg["OS/2"].ulUnicodeRange3, mg["OS/2"].ulUnicodeRange4]
_computed = compute_unicode_ranges(mg.getBestCmap().keys())
_missing = [d & ~c for d, c in zip(_computed, _declared)]
check("H5 ulUnicodeRange covers every mapped block",
      not any(_missing),
      f"missing bits: {[hex(x) for x in _missing if x]}")
check("H6 created/modified pinned (reproducible builds)",
      mg["head"].created == mg["head"].modified == RELEASE_DATE,
      f"created={mg['head'].created} modified={mg['head'].modified} "
      f"expected={RELEASE_DATE}")
check("H7 achVendID == JetHan Mono's own",
      mg["OS/2"].achVendID == VEND_ID, f"got {mg['OS/2'].achVendID!r}")
check("H8 USE_TYPO_METRICS bit kept",
      bool(mg["OS/2"].fsSelection & 0x80),
      f"fsSelection={mg['OS/2'].fsSelection:#06x}")

# ---------- summary ----------
total = len(mg.getGlyphOrder())
import os
size = os.path.getsize(mg_path)
print("-" * 60)
print(f"merged glyphs: {total}   size: {size/1048576:.1f} MB")
print(f"RESULT: {'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILURES: {failures}'}")
sys.exit(0 if not failures else 1)
