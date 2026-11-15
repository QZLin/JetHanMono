#!/usr/bin/env python3
"""Snap CJK advance widths to the terminal 2:1 grid (2 x JetBrains Mono latin)
and CENTER the unscaled Source Han ink inside the new cell (v3).

Design contract (v3, 定案):
  - JetBrains Mono 优先: 非 CJK/全角码位的字形与度量与 JBM 完全一致
    (rename.py 另把纵向度量锁回 JBM 的 1020/-300);
  - CJK 轮廓一律不缩放: 保持 Source Han Mono 原始 1000u 设计,
    方块字占满 em 的天然观感与上游完全相同 (高度不被放大);
  - 唯一的几何调整 = 把原 advance 盒在新的更宽步进里水平居中,
    垂直方向不做任何处理 (基线相对位置 = Source Han 原设计):

      1000u -> 1200u  dx=+100   ideographs / kana / fullwidth punct
       500u ->  600u  dx=+50    halfwidth forms == latin advance
       920u -> 1200u  dx=+140   Hangul normalized onto the grid
       else unchanged  latin-width & proportional glyphs stay as designed

  Merging at 1000u would give a 1.667:1 latin:CJK ratio and mixed columns
  drift apart; the snapped advance is what makes wide == 1200u == 2 x 600u.

History:
  v1  advance snap + center, outlines untouched.
  v2  outlines scaled x1.2 on BOTH axes ("ink fills the cell", Maple Mono
      SC style). REVERTED by v3: that fix was based on a misdiagnosis.
      The gap measured back then was >= 1 full latin cell, while centering
      a 1000u box in 1200u can add at most ~0.33 cell of padding per side
      - centering cannot produce a >= 1-cell gap, so the scaling was
      treating the wrong cause and made hanzi 20% taller than upstream
      Source Han (ink 919u -> 1103u for 中). v3 returns to v1 geometry;
      the old wide-gap symptom had unrelated causes (cmap/PANOSE/layout
      era bugs, since fixed) and must not be "fixed" by scaling.

Idempotency: 中 advance==1200 => skip.  A v2-era file also has adv=1200
but SCALED outlines; the probe detects that (ink height > 1000u) and
aborts loudly instead of silently skipping - rerun from the .pre.ttf
copy (build.sh always does) or FORCE_BUILD=1.

Zero-advance (combining) glyphs are left untouched.

Runs AFTER otf2ttf (glyf outlines exist) and BEFORE the merge.

Usage: scale_cjk.py <font.ttf> [more.ttf ...]   (in place)
"""
import sys

from fontTools.ttLib import TTFont

# old advance -> new advance
WIDTH_MAP = {500: 600, 1000: 1200, 920: 1200}
# v3: outlines are NEVER scaled.  SCALE stays in the dx formula so the
# centering shift reads uniformly: dx = (new_adv - adv * SCALE) / 2.
SCALE = 1.0
# v2-scaled artifacts carry 中 ink height ~1103u; unscaled is ~919u.
V2_INK_TELL = 1000


def scale_font(path):
    font = TTFont(path)
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    cmap = font.getBestCmap()

    # idempotency probe on U+4E2D (中)
    if 0x4E2D in cmap:
        gname = cmap[0x4E2D]
        adv, _lsb = hmtx[gname]
        if adv == WIDTH_MAP[1000]:
            glyph = glyf[gname]
            if glyph.numberOfContours > 0:
                coords, _ends, _flags = glyph.getCoordinates(glyf)
                ys = [p[1] for p in coords]
                ink = max(ys) - min(ys)
                if ink > V2_INK_TELL:
                    sys.exit(
                        f"{path}: 中 advance={adv} but ink height={ink} "
                        f"-> v2-scaled outlines detected; refusing to skip. "
                        f"Rebuild from the .pre.ttf copy (build.sh does this) "
                        f"or run with FORCE_BUILD=1."
                    )
            print(f"{path}: already snapped (中 advance={adv}), skip")
            return

    stats = {}  # (old, new) -> count
    n_zero = 0
    max_adv = 0
    for name in font.getGlyphOrder():
        adv, _lsb = hmtx[name]
        if adv == 0 or name == ".notdef":
            n_zero += 1
            continue
        new_adv = WIDTH_MAP.get(adv)
        if new_adv is None:
            continue  # latin-width / proportional glyphs stay as designed
        # center: the ORIGINAL design box (adv*SCALE wide, SCALE=1.0) sits
        # centered in the new cell; shift = (new - adv)/2
        # 1000->1200: +100, 500->600: +50, 920->1200: +140
        dx = (new_adv - adv * SCALE) / 2
        glyph = glyf[name]
        if glyph.numberOfContours > 0:
            coords, _ends, _flags = glyph.getCoordinates(glyf)
            coords.translate((dx, 0))
            glyph.recalcBounds(glyf)
        elif glyph.isComposite():
            # shift xy-offset components (point-matched ones follow their
            # base glyph, which is shifted by this same pass)
            for comp in glyph.components:
                if comp.flags & 0x0002:  # ARGS_ARE_XY_VALUES
                    comp.x = comp.x * SCALE + dx
            glyph.recalcBounds(glyf)
        hmtx[name] = (new_adv, glyph.xMin if glyph.numberOfContours else 0)
        stats[(adv, new_adv)] = stats.get((adv, new_adv), 0) + 1
        max_adv = max(max_adv, new_adv)

    if "hhea" in font:
        font["hhea"].advanceWidthMax = max_adv
    font.save(path)
    detail = ", ".join(f"{o}->{n}: {c}" for (o, n), c in sorted(stats.items()))
    print(f"saved {path}: {detail}; zero-width-kept={n_zero} "
          f"advanceWidthMax={max_adv}")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: scale_cjk.py <font.ttf> [more.ttf ...]")
    for p in sys.argv[1:]:
        scale_font(p)


if __name__ == "__main__":
    main()
