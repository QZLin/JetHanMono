#!/usr/bin/env python3
"""Snap CJK advance widths to the terminal 2:1 grid (2 x JetBrains Mono latin).

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
  drift apart.  This step snaps the mono grid so that wide == 1200u ==
  2 x 600u:

      1000u -> 1200u   (dx=+100; ideographs get symmetric ~100u bearings)
       500u ->  600u   (dx=+50;  halfwidth == latin advance)
       920u -> 1200u   (dx=+140; Hangul normalized onto the wide grid)
       else unchanged  (latin-width & proportional glyphs stay as designed)

  Outlines keep their design size; each glyph's ink is shifted so it stays
  CENTERED inside the new, wider cell -> Chinese reads looser, not bigger.
  Zero-advance (combining) glyphs are left untouched.
  Idempotent: a second run detects the already-scaled advance and exits.

Runs AFTER otf2ttf (glyf outlines exist) and BEFORE the merge.

Usage: scale_cjk.py <font.ttf> [more.ttf ...]   (in place)
"""
import sys

from fontTools.ttLib import TTFont

# old advance -> new advance (dx = (new - old) // 2)
WIDTH_MAP = {500: 600, 1000: 1200, 920: 1200}


def scale_font(path):
    font = TTFont(path)
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    cmap = font.getBestCmap()

    # idempotency probe: U+4E2D (中) must be full-width in this font
    probe = hmtx[cmap[0x4E2D]][0] if 0x4E2D in cmap else None
    if probe == WIDTH_MAP[1000]:
        print(f"{path}: already scaled (中 advance={probe}), skip")
        return

    stats = {}  # (old, new) -> count
    n_zero = 0
    max_adv = 0
    for name in font.getGlyphOrder():
        adv, _lsb = hmtx[name]
        max_adv = max(max_adv, adv)
        if adv == 0 or name == ".notdef":
            n_zero += 1
            continue
        new_adv = WIDTH_MAP.get(adv)
        if new_adv is None or new_adv == adv:
            continue  # latin-width / proportional glyphs stay as designed
        dx = (new_adv - adv) // 2
        glyph = glyf[name]
        if glyph.numberOfContours > 0:
            coords, _ends, _flags = glyph.getCoordinates(glyf)
            coords.translate((dx, 0))
            glyph.recalcBounds(glyf)
        elif glyph.isComposite():
            # point-matched components follow their base glyph automatically;
            # only xy-offset components need the explicit shift
            for comp in glyph.components:
                if comp.flags & 0x0002:  # ARGS_ARE_XY_VALUES
                    comp.x += dx
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
