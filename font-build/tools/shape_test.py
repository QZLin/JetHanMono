#!/usr/bin/env python3
"""Gold-standard shaping test: HarfBuzz output of the merged font must be
IDENTICAL to original JetBrains Mono for all Latin/code inputs, plus CJK
must resolve to real glyphs (notdef in the original).

Usage: shape_test.py <jetbrains.ttf> <merged.ttf>
"""
import sys
import uharfbuzz as hb

jb_path, mg_path = sys.argv[1], sys.argv[2]

def make_font(path):
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    return hb.Font(face)

jb = make_font(jb_path)
mg = make_font(mg_path)

def shape(font, text, features=None):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    return [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos]

failures = []
def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)

# ---- 1. programming ligatures form in BOTH fonts identically ----
lig_inputs = ["->", "=>", "<-", "->>", "==", "===", "!=", "!==", ">=", "<=", "&&", "||",
              "::", "/*", "*/", "//", "www", "..", "...", "#!", "</>", "<=>", "|>", "fi", "ff"]
all_ok = True
detail_lines = []
for t in lig_inputs:
    a, b = shape(jb, t), shape(mg, t)
    lig_formed = len(b) < len(t) or any(".liga" in g for g in b)
    if a != b or (t in ("->", "=>", "===", "fi", "ff") and not lig_formed and t != "fi" and t != "ff"):
        all_ok = False
        detail_lines.append(f"'{t}': jb={a} mg={b}")
check("1. ligature shaping identical to original JetBrains", all_ok,
      "; ".join(detail_lines) if detail_lines else f"{len(lig_inputs)} inputs matched")
print("    e.g. '->'    ->", shape(mg, "->"))
print("    e.g. '==='   ->", shape(mg, "==="))
print("    e.g. '!=='   ->", shape(mg, "!=="))

# ---- 2. disabling calt restores raw chars in BOTH fonts ----
a, b = shape(jb, "->", {"calt": False}), shape(mg, "->", {"calt": False})
check("2. calt OFF -> no ligature, identical in both", a == b, f"{a} vs {b}")

# ---- 3. plain latin / code text identical ----
samples = [
    "Hello, JetBrains Mono 123",
    "const answer = 42; // 注释",
    "if (a >= b && c !== d) { return null; }",
    "function 获取用户名(id) { return users[id]; }".replace("获取用户名", "").replace("users[id]; }", "users[id]; }"),
    "#[derive(Debug)]",
    "0O 1lI 5S 2Z 8B",
    "https://jetbrains.com/mono?ver=2.304",
]
mismatch = []
for s in samples:
    a, b = shape(jb, s), shape(mg, s)
    # acceptable difference: original .notdef (char not covered) -> real glyph in merged
    if len(a) != len(b) or any(
        x != y and not (x == ".notdef" and y.startswith("cid"))
        for x, y in zip(a, b)
    ):
        mismatch.append((s, a, b))
check("3. plain text/code shaping identical", not mismatch, str(mismatch[:1]))

# ---- 4. CJK resolves to real glyphs in merged (original = notdef) ----
cjk = shape(mg, "中文测试，标点！")
ok = len(cjk) == 8 and all(g not in (".notdef",) for g in cjk)
check("4. CJK + fullwidth punct -> real glyphs (no tofu)", ok, f"{cjk}")

# ---- 5. metrics: Latin 600 / CJK 1200 (exact terminal 2:1) ----
def adv(font, text):
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf)
    return sum(p.x_advance for p in buf.glyph_positions)
check("5. 'a' advance 600 / '中' advance 1200 (== 2 x 600)",
      adv(mg, "a") == 600 and adv(mg, "中") == 1200, f"a={adv(mg,'a')} 中={adv(mg,'中')}")

# ---- 5b. mixed run keeps the 2:1 rhythm per glyph ----
def adv_seq(font, text):
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf)
    return [p.x_advance for p in buf.glyph_positions]
seq = adv_seq(mg, "中a中")
check("5b. '中a中' per-glyph advances 1200/600/1200 (terminal 2:1)",
      seq == [1200, 600, 1200], f"{seq}")

# ---- 6. mixed line shape sanity ----
b = shape(mg, "const 变量 = () => <测试 />;")
ligs = any(".liga" in g for g in b)
check("6. mixed CJK+code line shapes with ligature", len(b) > 10 and ligs, f"{len(b)} glyphs, lig={ligs}")

print("-" * 60)
print(f"RESULT: {'ALL SHAPING CHECKS PASSED' if not failures else f'{len(failures)} FAILURES: {failures}'}")
sys.exit(0 if not failures else 1)
