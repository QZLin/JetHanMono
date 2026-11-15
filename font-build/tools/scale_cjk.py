#!/usr/bin/env python3
"""Snap CJK advance widths to the terminal 2:1 grid (2 x JetBrains Mono latin)
and apply the selected geometry VARIANT.

Since 1.003 the project ships TWO variants as separate zip packages (the font
internal name stays 'JetHan Mono' in both; only the geometry differs).  This
tool implements both off the same pre-conversion input (.pre.ttf):

  centered (default; v3 定案, 默认发行包):
      outlines UNSCALED; the 1000u Source Han design box is centered
      horizontally inside the new cell.  CJK ink keeps the exact upstream
      height (观感 = Source Han 原样, "中" ink height ~919u).
        1000u -> 1200u  dx=+100   ideographs / kana / fullwidth punct
         500u ->  600u  dx=+50    halfwidth forms == latin advance
         920u -> 1200u  dx=+140   Hangul normalized onto the grid
  scaled (v2 geometry; 1.003 起作为独立发行包重新提供):
      outlines scaled x1.2 on BOTH axes so the design box FILLS the cell
      (Maple Mono SC 流派的"满格"观感; "中" ink ~919u -> ~1103u, 比上游高 20%).
        1000u -> 1200u  dx=0      box fills the cell exactly
         500u ->  600u  dx=0
         920u -> 1200u  dx=+48

  Merging at 1000u would give a 1.667:1 latin:CJK ratio and mixed columns
  drift apart; the snapped advance is what makes wide == 1200u == 2 x 600u.
  else unchanged  latin-width & proportional glyphs stay as designed.

Design contract (both variants):
  - JetBrains Mono 优先: 非 CJK/全角码位的字形与度量与 JBM 完全一致
    (rename.py 另把纵向度量锁回 JBM 的 1020/-300);
  - CJK 步进一律吸附到 1200/600 网格; 唯一的自由度就是上面两种变体几何;
  - 垂直方向不做任何额外处理 (基线相对位置 = Source Han 原设计;
    scaled 变体的墨迹顶部会超出 JBM ascent, 这是该方案的已知取舍)。

History:
  v1  advance snap + center, outlines untouched.        (= centered)
  v2  outlines scaled x1.2 on BOTH axes ("ink fills the cell", Maple Mono
      SC style). REVERTED by v3: that fix was based on a misdiagnosis.
      The gap measured back then was >= 1 full latin cell, while centering
      a 1000u box in 1200u can add at most ~0.33 cell of padding per side
      - centering cannot produce a >= 1-cell gap, so the scaling was
      treating the wrong cause and made hanzi 20% taller than upstream
      Source Han (ink 919u -> 1103u for 中). v3 returned to v1 geometry;
      the old wide-gap symptom had unrelated causes (cmap/PANOSE/layout
      era bugs, since fixed) and must not be "fixed" by scaling.
  1.003  用户裁决: 两种方案各有受众, 以两个发行包并线提供 (居中=默认推荐,
      缩放=满格派选择), 字体内名保持一致 —— 本工具以 --variant 切换,
      构建缓存按变体隔离。

Idempotency probe on U+4E2D (中), variant-aware:
  centered: adv==1200 && ink height <= 1000u -> skip (already centered);
            ink > 1000u -> v2-scaled residue, abort loudly.
  scaled:   adv==1200 && 1000u < ink height <= 1200u -> skip (already scaled);
            ink <= 1000u -> centered outlines found (wrong variant input),
            abort; ink > 1200u -> double-scaled, abort.
  Rerun from the .pre.ttf copy (build.sh always does) or FORCE_BUILD=1.

Zero-advance (combining) glyphs are left untouched.

Runs AFTER otf2ttf (glyf outlines exist) and BEFORE the merge.

Usage: scale_cjk.py [--variant centered|scaled] <font.ttf> [more.ttf ...]
"""
import sys

from fontTools.ttLib import TTFont

# old advance -> new advance
WIDTH_MAP = {500: 600, 1000: 1200, 920: 1200}
# 居中: outlines are NEVER scaled.  SCALE stays in the dx formula so the
# centering shift reads uniformly: dx = (new_adv - adv * SCALE) / 2.
# 缩放: outlines scale by 1.2 on both axes; dx becomes 0 for 500/1000u
# glyphs (box fills the cell) and +48 for the 920u Hangul box.
VARIANT_SCALE = {"centered": 1.0, "scaled": 1.2}
# v2-scaled artifacts carry 中 ink height ~1103u; unscaled is ~919u.
V2_INK_TELL = 1000
# scaled 且 ink 超过此值 => 被缩放了两次 (1.2 x 1.2 -> ~1324u), 拒绝
SCALED_INK_MAX = 1200


def probe_done(font, path, variant):
    """已达标 (中 advance==1200 且墨迹符合该变体几何) => True, 调用方跳过."""
    cmap = font.getBestCmap()
    if 0x4E2D not in cmap:
        return False
    gname = cmap[0x4E2D]
    adv, _lsb = font["hmtx"][gname]
    if adv != WIDTH_MAP[1000]:
        return False
    glyph = font["glyf"][gname]
    if glyph.numberOfContours > 0:
        coords, _ends, _flags = glyph.getCoordinates(font["glyf"])
        ys = [p[1] for p in coords]
        ink = max(ys) - min(ys)
        if variant == "scaled":
            if ink <= V2_INK_TELL:
                sys.exit(
                    f"{path}: 中 advance={adv} but ink height={ink} "
                    f"-> unscaled (centered) outlines found; this file was "
                    f"NOT built with --variant scaled. Rebuild from the "
                    f".pre.ttf copy (build.sh does this) or FORCE_BUILD=1."
                )
            if ink > SCALED_INK_MAX:
                sys.exit(
                    f"{path}: 中 ink height={ink} > {SCALED_INK_MAX} "
                    f"-> double-scaled outlines detected; refusing. "
                    f"Rebuild from the .pre.ttf copy (build.sh does this)."
                )
            return True
        if ink > V2_INK_TELL:
            sys.exit(
                f"{path}: 中 advance={adv} but ink height={ink} "
                f"-> v2-scaled outlines detected; refusing to skip. "
                f"Rebuild from the .pre.ttf copy (build.sh does this) "
                f"or run with FORCE_BUILD=1."
            )
        return True
    return False


def scale_font(path, variant):
    font = TTFont(path)
    scale = VARIANT_SCALE[variant]
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    if probe_done(font, path, variant):
        print(f"{path}: already snapped ({variant}, 中 advance={WIDTH_MAP[1000]}), skip")
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
        # centered: the ORIGINAL design box (adv*SCALE, SCALE=1.0) sits
        #   centered in the new cell; shift = (new - adv)/2  (+100/+50/+140)
        # scaled: the x1.2 box fills the cell exactly; shift = 0 (+48 for 920)
        dx = (new_adv - adv * scale) / 2
        glyph = glyf[name]
        if glyph.numberOfContours > 0:
            coords, _ends, _flags = glyph.getCoordinates(glyf)
            if scale != 1.0:
                # x' = 1.2x + dx, y' = 1.2y (both axes, baseline-anchored)
                coords.scale((scale, scale))
                coords.translate((dx, 0))
                coords.toInt()  # glyf 坐标必须整数 (1.2x 会产生小数)
            else:
                coords.translate((dx, 0))
            glyph.recalcBounds(glyf)
        elif glyph.isComposite():
            # shift xy-offset components (point-matched ones follow their
            # base glyph, which is shifted by this same pass).
            # GOTCHA: fontTools strips ARGS_ARE_XY_VALUES (0x2) from
            # comp.flags at decompile time (recomputed at compile), so
            # testing the flag NEVER fires after a TTFont round-trip.
            # The reliable discriminator is the attribute set: xy-offset
            # components carry .x/.y, point-matched ones .firstPt/.secondPt.
            # (This bug previously left composite CJK glyphs unshifted in
            # all released versions - silent, since spot checks were all
            # simple-contour ideographs.)
            for comp in glyph.components:
                if hasattr(comp, "x"):
                    comp.x = int(round(comp.x * scale + dx))
                    if scale != 1.0:
                        comp.y = int(round(comp.y * scale))
            glyph.recalcBounds(glyf)
        hmtx[name] = (new_adv, glyph.xMin if glyph.numberOfContours else 0)
        stats[(adv, new_adv)] = stats.get((adv, new_adv), 0) + 1
        max_adv = max(max_adv, new_adv)

    if "hhea" in font:
        font["hhea"].advanceWidthMax = max_adv
    font.save(path)
    detail = ", ".join(f"{o}->{n}: {c}" for (o, n), c in sorted(stats.items()))
    print(f"saved {path} (variant={variant}): {detail}; zero-width-kept={n_zero} "
          f"advanceWidthMax={max_adv}")


def main():
    argv = sys.argv[1:]
    variant = "centered"
    if argv and argv[0] == "--variant":
        if len(argv) < 2:
            sys.exit("usage: scale_cjk.py [--variant centered|scaled] <font.ttf> [more.ttf ...]")
        variant = argv[1]
        argv = argv[2:]
    if variant not in VARIANT_SCALE:
        sys.exit(f"ERROR: 未知变体 '{variant}' (可选: {', '.join(VARIANT_SCALE)})")
    if not argv:
        sys.exit("usage: scale_cjk.py [--variant centered|scaled] <font.ttf> [more.ttf ...]")
    for p in argv:
        scale_font(p, variant)


if __name__ == "__main__":
    main()
