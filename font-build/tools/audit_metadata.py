#!/usr/bin/env python3
"""JetHan Mono 字体元数据独立审计 (可脱离构建管线运行).

与 verify.py 的 H 段互补: verify 在构建时校验刚生成的字体 (需上游源),
本脚本针对 *实际分发* 的文件 (Release 资产 / 本地 output 目录) 做全套
元数据审计, 不需要任何上游字体, 因此可以:

  - 由 .github/workflows/metadata-audit.yml 定时审计已发布的 Release
  - 手动 workflow_dispatch 审计任意 tag 的分发资产
  - 本地直接运行: python3 tools/audit_metadata.py font-build/output/

契约常量 (VERSION / RELEASE_DATE / MANUFACTURER / ...) 全部从 rename.py
导入 -- 审计与写入共用同一事实来源, rename 改契约则审计自动跟进.

用法:
  python3 audit_metadata.py <目录或字体文件...> [--report report.json]

检查范围 (M1-M15): 字体修订/日期/命名/厂商标识/RIBBI 位/ulUnicodeRange
按 cmap 重算/cmap 双子表与 2:1 网格/垂直度量锁/post 等宽位/跨字重一致性/
woff2 与 ttf 元数据一致/OFL 文本完整性/保留字体名清理.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fontTools.ttLib import TTFont  # noqa: E402
from rename import (  # noqa: E402
    FAMILY, VERSION, RELEASE_DATE, MANUFACTURER, VENDOR_URL, VEND_ID,
    WEIGHT_NAMES, compute_unicode_ranges,
)

# 期望的完整字重集 (目录内 8 个 ttf 齐全时才启用完整性检查)
FULL_WEIGHTS = {100, 200, 300, 400, 500, 600, 700, 800}
RIBBI_WEIGHTS = {400, 700}
RESERVED_STRINGS = ("JetBrains", "Source Han", "Noto")  # RFN/商标, 字体名内禁用

failures = []


def check(prefix, name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {prefix} {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(f"{prefix} {name}: {detail}")
    return ok


def weight_from_filename(fn):
    stem = os.path.basename(fn).rsplit(".", 1)[0]
    if not stem.startswith("JetHanMono-"):
        return None
    return stem.replace("JetHanMono-", "")


def audit_font(path, prefix):
    """对单个字体执行 M1-M12, 返回供跨字重比对的字段摘要."""
    f = TTFont(path)
    is_woff2 = getattr(f, "flavor", None) == "woff2"
    weight = f["OS/2"].usWeightClass
    sub = WEIGHT_NAMES.get(weight)
    name = f["name"]
    ids = {r.nameID for r in name.names}
    head, os2, post, hhea = f["head"], f["OS/2"], f["post"], f["hhea"]

    # ---- M2 版本一致性 ----
    check(prefix, "M2 fontRevision == Version(nameID5)",
          abs(head.fontRevision - float(VERSION)) < 1e-6,
          f"fontRevision={head.fontRevision}")
    check(prefix, "M2b nameID5/3 携带 VERSION",
          (name.getDebugName(5) or "").startswith(f"Version {VERSION}")
          and f";{VERSION};" in (name.getDebugName(3) or ""),
          f"5={name.getDebugName(5)!r} 3={name.getDebugName(3)!r}")

    # ---- M3 日期固定 (可复现构建) ----
    check(prefix, "M3 created/modified == 发布日",
          head.created == head.modified == RELEASE_DATE,
          f"created={head.created} modified={head.modified} expect={RELEASE_DATE}")

    # ---- M4 name ID 完备性 ----
    need = {0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14}
    if weight not in RIBBI_WEIGHTS:
        need |= {16, 17}
    missing = need - ids
    forbidden = {i for i in ids if i in (7, 12) or i >= 250}
    check(prefix, "M4 nameID 集合完整且无遗留",
          not missing and not forbidden,
          f"缺={sorted(missing)} 多余={sorted(forbidden)}")

    # ---- M5 命名契约 ----
    ps = f"JetHanMono-{sub}" if sub else None
    check(prefix, "M5 命名与字重一致",
          sub is not None
          and name.getDebugName(8) == MANUFACTURER
          and name.getDebugName(11) == VENDOR_URL
          and name.getDebugName(6) == ps
          and name.getDebugName(4) == f"{FAMILY} {sub}"
          and (name.getDebugName(17) == sub if weight not in RIBBI_WEIGHTS
               else 17 not in ids)
          and (name.getDebugName(16) == FAMILY if weight not in RIBBI_WEIGHTS
               else 16 not in ids)
          and (name.getDebugName(1) == FAMILY if weight in RIBBI_WEIGHTS
               else name.getDebugName(1) == f"{FAMILY} {sub}")
          and (name.getDebugName(2) == ("Bold" if weight == 700 else "Regular")),
          f"1={name.getDebugName(1)!r} 2={name.getDebugName(2)!r} "
          f"6={name.getDebugName(6)!r} 8={name.getDebugName(8)!r} "
          f"11={name.getDebugName(11)!r}")

    # ---- M6 保留字体名清理 ----
    dirty = []
    for nid in (1, 2, 4, 6, 16, 17):
        v = name.getDebugName(nid) or ""
        if any(rs in v for rs in RESERVED_STRINGS):
            dirty.append(f"{nid}:{v!r}")
    check(prefix, "M6 字体名不含保留字体名/商标", not dirty, f"{dirty}")

    # ---- M7 OS/2 状态位 ----
    fs, mac = os2.fsSelection, head.macStyle
    ribbi_ok = ((weight == 700 and (fs & 0x20) and (mac & 1)) or
                (weight != 700 and (fs & 0x40) and not (fs & 0x20) and not (mac & 1)))
    check(prefix, "M7 fsSelection/macStyle RIBBI 位 + USE_TYPO_METRICS",
          ribbi_ok and bool(fs & 0x80) and os2.version >= 4
          and os2.achVendID == VEND_ID,
          f"fs={fs:#06x} mac={mac:#04x} vend={os2.achVendID!r} os2v={os2.version}")

    # ---- M8 ulUnicodeRange 覆盖全部映射块 ----
    computed = compute_unicode_ranges(f.getBestCmap().keys())
    declared = [os2.ulUnicodeRange1, os2.ulUnicodeRange2,
                os2.ulUnicodeRange3, os2.ulUnicodeRange4]
    miss = [c & ~d for c, d in zip(computed, declared)]
    check(prefix, "M8 ulUnicodeRange ⊇ cmap 实际覆盖",
          not any(miss), f"缺位={[hex(x) for x in miss if x]}")

    # ---- M9 cmap 子表 + 2:1 网格 (woff2 也查, brotli 已装) ----
    if not is_woff2:
        subs = {(t.format, t.platformID, t.platEncID) for t in f["cmap"].tables}
        cmap = f.getBestCmap()
        astral = sum(1 for cp in cmap if cp > 0xFFFF)
        hmtx, glyf = f["hmtx"], f["glyf"]
        ok9 = (4, 3, 1) in subs and (12, 3, 10) in subs and astral > 0
        det = f"subs={sorted(subs)} astral={astral}"
        for cp, label in ((0x4E2D, "中"), (0x6587, "文"), (0x6D4B, "测"),
                          (0x3002, "。"), (0xFF0C, "，")):
            g = cmap.get(cp)
            adv = hmtx[g][0] if g else -1
            ok9 = ok9 and adv == 1200
            det += f" {label}={adv}"
        g_a = cmap.get(ord("a"))
        adv_a = hmtx[g_a][0] if g_a else -1
        ok9 = ok9 and adv_a == 600
        gz = glyf[cmap[0x4E2D]] if cmap.get(0x4E2D) else None
        if gz is not None and gz.numberOfContours > 0:
            lsb = hmtx[cmap[0x4E2D]][1]
            ok9 = ok9 and abs(lsb - (1200 - gz.xMax)) <= 6
            det += f" 中lsb/rsb={lsb}/{1200 - gz.xMax}"
        check(prefix, "M9 cmap fmt4+fmt12, 全宽1200=2x拉丁600, 墨迹居中",
              ok9, det + f" a={adv_a}")

    # ---- M10 垂直度量锁 ----
    check(prefix, "M10 垂直度量锁定 JBM (hhea/typo/win)",
          (hhea.ascent, hhea.descent, hhea.lineGap) == (1020, -300, 0)
          and (os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap) == (1020, -300, 0)
          and os2.usWinAscent == 1020 and os2.usWinDescent == 300
          and hhea.caretSlopeRise == 1,
          f"hhea={hhea.ascent}/{hhea.descent}/{hhea.lineGap} "
          f"typo={os2.sTypoAscender}/{os2.sTypoDescender}/{os2.sTypoLineGap} "
          f"win={os2.usWinAscent}/{os2.usWinDescent} caret={hhea.caretSlopeRise}")

    # ---- M11/M12 等宽声明 + 字宽上限 ----
    real_max = max(a for a, _lsb in hmtx.metrics.values())
    check(prefix, "M11/M12 isFixedPitch, italicAngle=0, advanceWidthMax==hmtx max",
          post.isFixedPitch == 1 and post.italicAngle == 0
          and hhea.advanceWidthMax == real_max,
          f"fixed={post.isFixedPitch} angle={post.italicAngle} "
          f"declared={hhea.advanceWidthMax} real={real_max}")

    return {
        "weight": weight,
        "fontRevision": head.fontRevision,
        "created": head.created, "modified": head.modified,
        "vendID": os2.achVendID,
        "ranges": declared,
        "panose": [os2.panose.bFamilyType, os2.panose.bSerifStyle,
                   os2.panose.bWeight, os2.panose.bProportion,
                   os2.panose.bContrast, os2.panose.bStrokeVariation,
                   os2.panose.bArmStyle, os2.panose.bLetterForm,
                   os2.panose.bMidline, os2.panose.bXHeight],
        "upem": head.unitsPerEm,
        "xHeight": getattr(os2, "sxHeight", None),
        "capHeight": getattr(os2, "sCapHeight", None),
        "vert": (hhea.ascent, hhea.descent, hhea.lineGap),
    }


def audit_cross_weight(summaries, prefix):
    """M13 跨字重共享字段一致性 + 字重集完整性."""
    if len(summaries) < 2:
        return
    fields = ["fontRevision", "created", "modified", "vendID", "ranges",
              "panose", "upem", "xHeight", "capHeight", "vert"]
    def _h(v):
        return tuple(v) if isinstance(v, list) else v
    for fld in fields:
        vals = {_h(s[fld]) for s in summaries.values()}
        check(prefix, f"M13 跨字重一致 {fld}", len(vals) == 1,
              f"{sorted(map(str, vals))[:3]}{'...' if len(vals) > 3 else ''}")
    weights = {s["weight"] for s in summaries.values()}
    check(prefix, "M13 usWeightClass 互不重复", len(weights) == len(summaries),
          f"{sorted(weights)}")
    if FULL_WEIGHTS <= weights:
        check(prefix, "M13 8 字重齐全 (Thin..ExtraBold)",
              weights == FULL_WEIGHTS, f"{sorted(weights)}")


def audit_ofl(path, prefix):
    """M15 OFL 文本: 三段版权 + OFL 1.1 正文."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        check(prefix, "M15 OFL.txt 可读", False, str(e))
        return
    ok = (text.startswith(FAMILY)
          and "Copyright 2026 The JetHan Mono Project Authors" in text
          and "Copyright 2020 The JetBrains Mono Project Authors" in text
          and "Copyright 2014-2021 Adobe" in text
          and "This Font Software is licensed under the SIL Open Font License" in text)
    check(prefix, "M15 OFL.txt 版权与许可正文完整", ok,
          f"{len(text)} bytes")


def main():
    ap = argparse.ArgumentParser(description="JetHan Mono 元数据审计")
    ap.add_argument("paths", nargs="+", help="字体文件或目录 (ttf/woff2/OFL)")
    ap.add_argument("--report", help="把结果写入 JSON 文件")
    args = ap.parse_args()

    fonts, woff2s, ofls = {}, {}, None
    for p in args.paths:
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if fn.endswith(".ttf"):
                    fonts[fn] = fp
                elif fn.endswith(".woff2"):
                    woff2s[fn] = fp
                elif "OFL" in fn.upper() and fn.endswith(".txt"):
                    ofls = fp
        elif p.endswith(".ttf"):
            fonts[os.path.basename(p)] = p
        elif p.endswith(".woff2"):
            woff2s[os.path.basename(p)] = p
        elif "OFL" in os.path.basename(p).upper():
            ofls = p

    print(f"== 审计目标: ttf x{len(fonts)}  woff2 x{len(woff2s)}  "
          f"OFL={'有' if ofls else '无'} ==")
    if not fonts:
        sys.exit("ERROR: 未找到任何 .ttf 文件")

    # M1: 表结构健全性 + 逐字体 M2-M12
    summaries = {}
    for fn, fp in sorted(fonts.items()):
        prefix = f"[{fn}]"
        f = TTFont(fp)
        need = {"glyf", "head", "hhea", "OS/2", "name", "post", "cmap", "hmtx", "maxp"}
        check(prefix, "M1 关键表齐全", need <= set(f.keys()),
              f"缺={sorted(need - set(f.keys()))}")
        f.close()
        summaries[fn] = audit_font(fp, prefix)

    # M13: ttf 间跨字重一致性
    audit_cross_weight({k: v for k, v in summaries.items()
                        if not k.endswith(".woff2")}, "[cross]")

    # M14: woff2 与同名 ttf 元数据一致
    for fn, fp in sorted(woff2s.items()):
        twin = fn.replace(".woff2", ".ttf")
        if twin not in fonts:
            continue
        w = audit_font(fp, f"[{fn}]")  # 顺带跑核心检查 (brotli 解码)
        t = summaries[twin]
        same = (w["fontRevision"] == t["fontRevision"]
                and w["created"] == t["created"]
                and w["vendID"] == t["vendID"]
                and w["ranges"] == t["ranges"]
                and w["weight"] == t["weight"])
        check(f"[{fn}]", "M14 woff2 与 ttf 元数据一致", same,
              f"woff2={ {k: w[k] for k in ('fontRevision','vendID')} }")

    if ofls:
        audit_ofl(ofls, "[OFL]")

    print("-" * 70)
    if failures:
        print(f"RESULT: {len(failures)} 项失败")
        for x in failures:
            print(f"  - {x}")
        rc = 1
    else:
        print("RESULT: 全部通过")
        rc = 0
    if args.report:
        json.dump({"failures": failures,
                   "summaries": {k: {f: (v if not isinstance(v, list) else v)
                                     for f, v in s.items()}
                                for k, s in summaries.items()}},
                  open(args.report, "w"), indent=1, default=str)
        print(f"report -> {args.report}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
