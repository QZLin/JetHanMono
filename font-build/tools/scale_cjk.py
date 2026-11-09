#!/usr/bin/env python3
"""Snap CJK advance widths to the terminal 2:1 grid (2 x JetBrains Mono latin)
AND scale the outlines proportionally so the ink FILLS the new cell.

Background:
  JetBrains Mono latin advance = 600/1000em.  Terminals and editors align
  CJK text against latin columns only when one wide (East-Asian Wide/Fullwidth)
  char occupies exactly two latin cells (2:1).  Upstream widths in Noto Sans
  Mono CJK SC (= Source Han Mono design) are:

      full-width ideographs / kana / punct / symbols   1000u
      halfwidth forms (U+FF61-FF9F)                     500u
      Hangul syllables + jamo (1100/AC00/A960/D7B0...)  920u
      latin-width glyphs (e.g. U+FB01 fi)               600u
      proportional leftovers (ext-latin, ligatures)     anything

  Merging at 1000u would give a 1.667:1 latin:CJK ratio and mixed columns
  drift apart.  This step puts every wide glyph onto the mono grid so that
  wide == 1200u == 2 x 600u:

      1000u -> 1200u   (scale x1.2; ink fills the cell like Source Han does)
       500u ->  600u   (scale x1.2; halfwidth == latin advance)
       920u -> 1200u   (scale x1.2 + center; Hangul normalized onto the grid)
       else unchanged  (latin-width & proportional glyphs stay as designed)

WHY SCALE THE OUTLINES TOO (v2, fixes "CJK chars have a ~0.7-cell empty gap
to their right in JetBrains IDEs"):
  v1 only widened the advance and translated the ink to center it, keeping
  the outlines at their 1000u design size.  That leaves the ink filling only
  ~67% of the 1200u box (Source Han fills ~80-96% of its own box), so every
  CJK char gained ~0.33 cell of padding on EACH side - the gap between two
  hanzi's ink grew to 0.66 cell (vs 0.37 in Source Han Mono), and full-width
  punctuation left over a full latin cell of blank space.  Pixel probes
  (PixelProbe.java) confirmed the rendered gap after a hanzi was 6px vs
  Source Han's 2px at the same size.  The fix used by Sarasa Gothic / Maple
  Mono SC is proportional scaling: the CJK em box IS 1.2x the latin cell, so
  the glyphs must be scaled x1.2 on BOTH axes to keep Source Han's ink
  density.  With scale=1.2 the translate is a no-op for 1000u->1200u and
  500u->600u (the ink is already proportionally centered); only 920u Hangul
  gets an explicit +48u centering shift.

Vertical metrics note:
  Dense hanzi ink after scaling stays within the locked JetBrains vertical
  box (ascent 1020 / descent -300).  A handful of rare mark/symbol glyphs
  (〱〲Å｀＾〰 ...) reach slightly above 1020u; no engine clips ink
  vertically in editors, same as Sarasa.

Zero-advance (combining) glyphs are left untouched.
Idempotent: a second run detects the already-scaled advance and exits.

Runs AFTER otf2ttf (glyf outlines exist) and BEFORE the merge.

Usage: scale_cjk.py <font.ttf> [more.ttf ...]   (in place)
"""
import sys

from fontTools.ttLib import TTFont

# old advance -> new advance
WIDTH_MAP = {500: 600, 1000: 1200, 920: 1200}
# CJK em 1000u -> 1200u (2 x JetBrains Mono latin 600u): outlines scale x1.2
# on both axes so ink density matches Source Han Mono exactly.
SCALE = 1.2


def scale_font(path):
    font = TTFont(path)
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    cmap = font.getBestCmap()

    # idempotency probe: U+4E2D (中) must already be full-width AND scaled
    probe = hmtx[cmap[0x4E2D]][0] if 0x4E2D in cmap else None
    if probe == WIDTH_MAP[1000]:
        print(f"{path}: already scaled (中 advance={probe}), skip")
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
        # center: scaled ink spans adv*SCALE wide; shift = (new - adv*SCALE)/2
        # 1000->1200: 0, 500->600: 0, 920->1200: +48
        dx = (new_adv - adv * SCALE) / 2
        glyph = glyf[name]
        if glyph.numberOfContours > 0:
            coords, _ends, _flags = glyph.getCoordinates(glyf)
            coords.transform(((SCALE, 0), (0, SCALE)))
            if dx:
                coords.translate((dx, 0))
            glyph.recalcBounds(glyf)
        elif glyph.isComposite():
            # scale xy-offset components (point-matched ones follow their
            # base glyph, which is scaled by this same pass)
            for comp in glyph.components:
                if comp.flags & 0x0002:  # ARGS_ARE_XY_VALUES
                    comp.x = comp.x * SCALE + dx
                    comp.y = comp.y * SCALE
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
