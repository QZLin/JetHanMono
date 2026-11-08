#!/usr/bin/env python3
"""Export woff2 copies (brotli-compressed) next to every .ttf given on the CLI.

Replaces the inline heredoc that used to live in build.sh: a separate tool
file is immune to CRLF line-ending issues on Windows checkouts.
"""
import os
import sys

from fontTools.ttLib import TTFont


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: export_woff2.py <font.ttf> [more.ttf ...]")
    for p in sys.argv[1:]:
        f = TTFont(p)
        f.flavor = "woff2"
        out = os.path.splitext(p)[0] + ".woff2"
        f.save(out)
        print(f"woff2: {out} ({os.path.getsize(out) / 1048576:.1f}MB)")


if __name__ == "__main__":
    main()
