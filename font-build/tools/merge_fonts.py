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
"""
import argparse
import os
import sys
import time


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

    t0 = time.time()
    merged = Merger().merge(args.fonts)
    merged.save(args.output)
    dt = time.time() - t0
    size = os.path.getsize(args.output) / 1048576
    print(f"merged {len(args.fonts)} fonts -> {args.output}: "
          f"glyphs={merged['maxp'].numGlyphs} size={size:.1f}MB in {dt:.1f}s")


if __name__ == "__main__":
    main()
