#!/usr/bin/env python3
"""Merge fonts via the fontTools.merge.Merger API (replaces bare pyftmerge CLI).

Why not `pyftmerge --output-file OUT in1 in2`?
  pyftmerge's hand-rolled option parser (fontTools/merge/options.py) only
  accepts `--option=value` syntax.  The space form silently treats OUT as
  the FIRST INPUT FONT (and sets output_file=True), which then fails with

      FileNotFoundError: No such file or directory: 'OUT'

  -- the exact bug the first end-to-end run of this pipeline hit (on MSYS
  bash, but it is platform-independent).  Going through the API with a real
  argparse front-end removes that failure mode and reports missing inputs
  clearly before any merge work starts.

Usage: merge_fonts.py -o OUT.ttf FIRST.ttf SECOND.ttf [...]
  FIRST font wins on cmap/metric conflicts (JetBrains Mono priority).

Layout-table stripping (why):
  fontTools Merger CONCATENATES the GSUB/GPOS/GDEF lookup lists of both
  sources into one table.  That mixed table shapes fine under HarfBuzz,
  but other shaping engines that an IDE may actually use (JDK's built-in
  GlyphLayout, Windows DirectWrite inside JetBrains Runtime, macOS) are
  far less forgiving; a mis-parsed pair-lookup applies bogus kerning
  values and characters get pushed apart by a full extra cell (the gap
  becomes part of the glyph's advance box in the editor selection).
  Equal-width CJK needs NO kerning/GSUB of its own, so the safest merge
  is: keep the FIRST font's layout tables verbatim and drop them from
  every following source.  A table held by only one input is copied
  verbatim by fontTools merge, so the output then contains JetBrains'
  original untouched GSUB/GPOS/GDEF -- byte-equivalent behaviour on
  every engine.
"""
import argparse
import os
import sys
import time

# OpenType layout + legacy kerning tables: keep from FIRST font only.
# (cmap/glyf/hmtx/etc. are unaffected and still merge normally)
STRIP_TAGS = ("GSUB", "GPOS", "GDEF", "kern", "morx", "kerx", "mort")


def main():
    ap = argparse.ArgumentParser(
        description="Merge fonts (Merger API; first font has priority)")
    ap.add_argument("-o", "--output", required=True, help="output font path")
    ap.add_argument("fonts", nargs="+", help="input fonts in priority order")
    args = ap.parse_args()

    for p in args.fonts:
        if not os.path.isfile(p):
            sys.exit(f"ERROR: input font not found: {p}")
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)

    from fontTools.merge import Merger
    from fontTools.ttLib import TTFont

    # strip layout tables from every non-primary source BEFORE merging
    merge_paths = []
    for i, p in enumerate(args.fonts):
        if i == 0:
            merge_paths.append(p)
            continue
        f = TTFont(p)
        dropped = [t for t in STRIP_TAGS if t in f]
        for t in dropped:
            del f[t]
        if dropped:
            print(f"stripped layout tables from source {i} ({p.split('/')[-1]}): "
                  f"{','.join(dropped)}")
        sp = p[:-4] + ".nolayout.ttf" if p.endswith(".ttf") else p + ".nolayout.ttf"
        f.save(sp)
        merge_paths.append(sp)

    t0 = time.time()
    merged = Merger().merge(merge_paths)
    merged.save(args.output)
    dt = time.time() - t0
    size = os.path.getsize(args.output) / 1048576
    print(f"merged {len(args.fonts)} fonts -> {args.output}: "
          f"glyphs={merged['maxp'].numGlyphs} size={size:.1f}MB in {dt:.1f}s")


if __name__ == "__main__":
    main()
