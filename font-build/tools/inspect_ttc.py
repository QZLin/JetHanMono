#!/usr/bin/env python3
"""List all faces inside SourceHanMono.ttc and locate SC Regular / Bold."""
import sys
from fontTools.ttLib import TTCollection, TTFont

path = sys.argv[1] if len(sys.argv) > 1 else "downloads/SourceHanMono.ttc"
coll = TTCollection(path, lazy=True)
print(f"faces: {len(coll.fonts)}")
for i, f in enumerate(coll.fonts):
    n = f["name"]
    family = n.getDebugName(16) or n.getDebugName(1)
    sub = n.getDebugName(17) or n.getDebugName(2)
    print(f"  [{i}] {family} / {sub}  upem={f['head'].unitsPerEm} glyphs={f['maxp'].numGlyphs} sfnt={f.sfntVersion!r}")
