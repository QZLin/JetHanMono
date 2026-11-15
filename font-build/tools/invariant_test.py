#!/usr/bin/env python3
"""JetHan Mono 核心不变量测试 (全字形级 JBM 保真证明).

契约: JetHan Mono 是 JetBrains Mono 的"纯增量扩展"——凡 JBM 已提供的
字形/映射/度量/布局行为, 在拼合产物中必须与原版完全一致; CJK 只允许
补充 JBM 未覆盖的码位。本测试把该契约做成自动化硬门槛: 任何构建优化
(并行化/预处理去重/未来架构替换) 都不得削弱这些不变量。

Usage: invariant_test.py <jetbrains.ttf> <merged.ttf>

检查组:
  CMAP  全部 JBM 码位 -> 同名 glyph, 无一丢失/被 CJK 顶替
  ORDER JBM glyph 顺序作为前缀保留 (glyph ID 稳定性的前提)
  GLYF  全部 JBM 字形分解后轮廓逐点一致 (复合字形按分解结果比较,
        对"复合/扁平"表示差异鲁棒, 对几何差异零容忍)
  HMTX  全部 JBM 字形 (advance, lsb) 逐字形一致
  OTL   GSUB/GPOS/GDEF 经 TTX 序列化(按 glyph 名)逐字一致 —— 连字/kerning/
        glyph 分类行为不变; kern/morx/kerx/mort 不得凭空出现
  VMET  纵向度量锁回 JBM: hhea / OS/2 typo / OS/2 win / unitsPerEm / 斜度
  HB    HarfBuzz 全码位塑形: 每个 JBM 码位单独塑形, glyph 名/cluster/
        x_advance/y_advance/x_offset/y_offset 与 JBM 完全一致;
        另加编程连字语料与 calt 关闭语料
  MIX   中英混排: 独立英文片段与 JBM 塑形完全一致; 混排整串中英文簇的
        glyph 名/位移/步进符合契约 (英文 = JBM 原值, CJK = 1200/600 网格)
"""
import re
import sys
from io import StringIO

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

jb_path, mg_path = sys.argv[1], sys.argv[2]
jb = TTFont(jb_path)
mg = TTFont(mg_path)

failures = []


def check(name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def lim(seq, n=6):
    seq = list(seq)
    return f"{len(seq)} 项" + (f": {seq[:n]}" if seq else "")


# ---------- CMAP ----------
jb_cmap = jb.getBestCmap()
mg_cmap = mg.getBestCmap()
missing = [cp for cp in jb_cmap if cp not in mg_cmap]
conflict = [(f"U+{cp:04X}", jb_cmap[cp], mg_cmap[cp])
            for cp in jb_cmap if mg_cmap.get(cp) != jb_cmap[cp]]
check("CMAP1 全部 JBM 码位映射到同名 glyph", not missing and not conflict,
      f"{len(jb_cmap)} 码位, 丢失={lim(missing)} 冲突={lim(conflict)}")

# ---------- ORDER ----------
jb_order = jb.getGlyphOrder()
mg_order = mg.getGlyphOrder()
prefix_ok = (len(mg_order) >= len(jb_order)
             and mg_order[:len(jb_order)] == jb_order)
check("ORDER1 JBM glyph 顺序作为前缀保留 (glyph ID 稳定)", prefix_ok,
      f"jb={len(jb_order)} glyphs, merged={len(mg_order)} glyphs"
      + ("" if prefix_ok else
         f"; 第一处分歧: {next((i for i, (a, b) in enumerate(zip(jb_order, mg_order)) if a != b), min(len(jb_order), len(mg_order)))}"))

# ---------- GLYF ----------
def outline_sig(font, gname):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    try:
        font.getGlyphSet()[gname].draw(pen)
    except Exception:
        return None
    return tuple(pen.value)


glyf_diff = []
for gname in jb_order:
    if outline_sig(jb, gname) != outline_sig(mg, gname):
        glyf_diff.append(gname)
check("GLYF1 全部 JBM 轮廓逐点一致", not glyf_diff,
      f"{len(jb_order)} glyphs, 不一致={lim(glyf_diff)}")

# ---------- HMTX ----------
jb_hmtx, mg_hmtx = jb["hmtx"], mg["hmtx"]
hmtx_diff = [g for g in jb_order
             if tuple(jb_hmtx[g]) != tuple(mg_hmtx[g])]
check("HMTX1 全部 JBM (advance, lsb) 一致", not hmtx_diff,
      f"{len(jb_order)} glyphs, 不一致={lim(hmtx_diff)}")

# ---------- OTL ----------
OTL_TAGS = ("GSUB", "GPOS", "GDEF", "kern", "morx", "kerx", "mort")


def table_xml(font, tag):
    buf = StringIO()
    writer = XMLWriter(buf)
    font[tag].toXML(writer, font)
    return buf.getvalue()


from fontTools.misc.xmlWriter import XMLWriter  # noqa: E402

for tag in OTL_TAGS:
    in_jb, in_mg = tag in jb, tag in mg
    if not in_jb:
        check(f"OTL0 {tag} 不因合并凭空出现", not in_mg,
              f"jb 无, merged {'有' if in_mg else '无'}")
        continue
    if not in_mg:
        check(f"OTL1 {tag} 保留", False, "jb 有, merged 丢失")
        continue
    same = table_xml(jb, tag) == table_xml(mg, tag)
    check(f"OTL1 {tag} 逐字一致 (TTX 序列化, 按 glyph 名)", same)

# ---------- VMET ----------
metrics = [
    ("head.unitsPerEm", jb["head"].unitsPerEm, mg["head"].unitsPerEm),
    ("hhea.ascent", jb["hhea"].ascent, mg["hhea"].ascent),
    ("hhea.descent", jb["hhea"].descent, mg["hhea"].descent),
    ("hhea.lineGap", jb["hhea"].lineGap, mg["hhea"].lineGap),
    ("OS/2.sTypoAscender", jb["OS/2"].sTypoAscender, mg["OS/2"].sTypoAscender),
    ("OS/2.sTypoDescender", jb["OS/2"].sTypoDescender, mg["OS/2"].sTypoDescender),
    ("OS/2.sTypoLineGap", jb["OS/2"].sTypoLineGap, mg["OS/2"].sTypoLineGap),
    ("OS/2.usWinAscent", jb["OS/2"].usWinAscent, mg["OS/2"].usWinAscent),
    ("OS/2.usWinDescent", jb["OS/2"].usWinDescent, mg["OS/2"].usWinDescent),
]
vm_bad = [f"{n}: {a}->{b}" for n, a, b in metrics if a != b]
check("VMET1 纵向度量与 JBM 一致 (行高/基线不变)", not vm_bad, lim(vm_bad))
check("VMET2 USE_TYPO_METRICS 位一致",
      bool(jb["OS/2"].fsSelection & 0x80) == bool(mg["OS/2"].fsSelection & 0x80),
      f"jb={jb['OS/2'].fsSelection:#06x} mg={mg['OS/2'].fsSelection:#06x}")
check("VMET3 italicAngle 一致",
      jb["post"].italicAngle == mg["post"].italicAngle,
      f"jb={jb['post'].italicAngle} mg={mg['post'].italicAngle}")

# ---------- HB (HarfBuzz 全码位塑形) ----------
import uharfbuzz as hb  # noqa: E402


def make_hb_font(path):
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    return hb.Font(face)


def shape(font, text, features=None):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features or {})
    infos = buf.glyph_infos
    poss = buf.glyph_positions
    return [(font.glyph_to_string(i.codepoint), i.cluster,
             p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for i, p in zip(infos, poss)]


jbhb, mghb = make_hb_font(jb_path), make_hb_font(mg_path)

hb_bad = []
for cp in sorted(jb_cmap):
    text = chr(cp)
    if shape(jbhb, text) != shape(mghb, text):
        hb_bad.append(f"U+{cp:04X}")
check("HB1 全码位单字塑形一致 (glyph/cluster/advance/offset)", not hb_bad,
      f"{len(jb_cmap)} 码位, 不一致={lim(hb_bad)}")

LIG_INPUTS = ["->", "=>", "<-", "->>", "==", "===", "!=", "!==", ">=", "<=",
              "&&", "||", "::", "/*", "*/", "//", "www", "..", "...", "#!",
              "</>", "<=>", "|>", "fi", "ff"]
lig_bad = []
for t in LIG_INPUTS:
    if shape(jbhb, t) != shape(mghb, t):
        lig_bad.append(t)
check("HB2 编程连字塑形一致", not lig_bad, f"{len(LIG_INPUTS)} 组, 不一致={lim(lig_bad)}")

calt_off_bad = [t for t in ("->", "===", "fi")
                if shape(jbhb, t, {"calt": False}) != shape(mghb, t, {"calt": False})]
check("HB3 calt 关闭后塑形一致", not calt_off_bad, lim(calt_off_bad))

KITCHEN = ("const value = getUser(123); // Hello, JetBrains Mono 123\n"
           "if (a >= b && c !== d) { return null; } /* #! */")
check("HB4 长代码文本整串塑形一致",
      shape(jbhb, KITCHEN) == shape(mghb, KITCHEN))

# ---------- MIX (中英混排) ----------
def adv_of(font, gname):
    return font["hmtx"][gname][0]


MIXED = [
    "这是一个 const value = getUser(123); 测试。",
    "函数 fn(x) 返回 None；注释 // todo",
    "数组 [1, 2, 3] 与 字典 中ｱ半角",
]

mix_fail = []
for text in MIXED:
    # (1) 独立英文片段: 与 JBM 塑形完全一致
    for frag in re.findall(r"[\x20-\x7E]+", text):
        if shape(jbhb, frag) != shape(mghb, frag):
            mix_fail.append(f"片段 {frag!r} 塑形与 JBM 不一致")
    # (2) 混排整串: 英文簇 = JBM 原字形/度量; CJK 簇 = 1200/600 网格, 无纵向位移
    seq = shape(mghb, text)
    last_cluster = -1
    for gname, cluster, x_adv, y_adv, x_off, y_off in seq:
        if cluster <= last_cluster:
            mix_fail.append(f"{text[:6]!r}: cluster 非单调 ({cluster})")
        last_cluster = cluster
        # uharfbuzz add_str 的 cluster 是字符下标 (非 UTF-8 字节偏移)
        if not (isinstance(cluster, int) and 0 <= cluster < len(text)):
            mix_fail.append(f"{text[:6]!r}: cluster {cluster} 越界")
            continue
        cp = ord(text[cluster])
        if cp in jb_cmap:
            exp_name = jb_cmap[cp]
            if gname != exp_name:
                mix_fail.append(f"U+{cp:04X} glyph {gname!r} != JBM {exp_name!r}")
            if (x_off, y_off, y_adv) != (0, 0, 0):
                mix_fail.append(f"U+{cp:04X} 出现纵向/横向位移 ({x_off},{y_off},{y_adv})")
            if x_adv != adv_of(jb, exp_name):
                mix_fail.append(f"U+{cp:04X} advance {x_adv} != JBM {adv_of(jb, exp_name)}")
        else:
            # CJK 码位的"覆盖完整性"由 verify.py C1 负责; 这里只校验
            # 已覆盖码位的网格步进 (未覆盖的落 .notdef, 不在本测试域)
            if cp not in mg_cmap:
                continue
            wide = (0x2E80 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF
                    or 0xFF01 <= cp <= 0xFF60 or 0x3000 <= cp <= 0x303F)
            half = 0xFF61 <= cp <= 0xFF9F
            if wide and x_adv != 1200:
                mix_fail.append(f"U+{cp:04X} 全角 advance {x_adv} != 1200")
            if half and x_adv != 600:
                mix_fail.append(f"U+{cp:04X} 半角 advance {x_adv} != 600")
check("MIX1 中英混排: 英文片段塑形一致 + 英文簇零位移 + CJK 网格步进",
      not mix_fail, lim(mix_fail, 4))

# ---------- summary ----------
total = len(mg.getGlyphOrder())
print("-" * 60)
print(f"merged glyphs: {total}")
print(f"RESULT: {'ALL INVARIANTS HOLD' if not failures else f'{len(failures)} FAILURES: {failures}'}")
sys.exit(0 if not failures else 1)
