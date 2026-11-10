#!/usr/bin/env python3
"""重新生成 tools/os2_ranges.py (ulUnicodeRange1-4 位表).

数据源: HarfBuzz hb-ot-os2-unicode-ranges.hh -- OpenType spec OS/2
ulUnicodeRange 的权威机器可读形式. Unicode 新版本可能微调该表,
需要更新时重跑本脚本即可.

用法: python3 gen_os2_ranges.py            # 网络可用, 直接抓 HarfBuzz 源码
      python3 gen_os2_ranges.py <本地.hh>  # 离线, 用已下载的文件
"""
import re
import sys
import urllib.request

URL = ("https://raw.githubusercontent.com/harfbuzz/harfbuzz/main/"
       "src/hb-ot-os2-unicode-ranges.hh")
OUT = __file__.replace("gen_os2_ranges.py", "os2_ranges.py")


def main():
    if len(sys.argv) > 1:
        src = open(sys.argv[1], encoding="utf-8").read()
    else:
        src = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8")

    entries = re.findall(
        r"\{\s*(0x[0-9A-Fa-f]+)\s*,\s*(0x[0-9A-Fa-f]+)\s*,\s*(\d+)\s*\}", src)
    if not entries:
        sys.exit("ERROR: 未从源文件解析出任何区间 (上游格式变了?)")
    bits = {}
    for s, e, b in entries:
        bits.setdefault(int(b), []).append((int(s, 16), int(e, 16)))

    lines = [
        '"""ulUnicodeRange1-4 位表 (自动生成, 勿手改).',
        "",
        "来源: HarfBuzz hb-ot-os2-unicode-ranges.hh -- OpenType spec OS/2",
        "ulUnicodeRange1-4 的权威机器可读形式 (HarfBuzz MIT 许可, 表数据本身",
        "来自 Microsoft OpenType 规范). 由 tools/gen_os2_ranges.py 生成.",
        "",
        "OS2_RANGES: bit -> [(start, end), ...] 该位覆盖的 Unicode 闭区间列表.",
        "bit 0-31 -> ulUnicodeRange1, 32-63 -> range2, 64-95 -> range3, 96-127 -> range4.",
        '"""',
        "",
        "OS2_RANGES = {",
    ]
    for b in sorted(bits):
        rs = ", ".join(f"(0x{s:04X}, 0x{e:04X})" for s, e in bits[b])
        lines.append(f"    {b}: [{rs}],")
    lines += ["}", ""]

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"os2_ranges.py: {len(bits)} bits / {len(entries)} ranges -> {OUT}")


if __name__ == "__main__":
    main()
