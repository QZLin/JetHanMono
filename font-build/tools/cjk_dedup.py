#!/usr/bin/env python3
"""Group weights by identical CJK preprocessing needs (build dedup, v3).

subset_cjk.py 的输出只取决于二元组 (CJK 源字体内容, 需保留码位集):
    需保留码位集 = cjk_cmap - jb_cmap   (JetBrains 已覆盖的码位不要)
因此当两个字重 (a) 用同一份 CJK 源文件, 且 (b) 其 JBM cmap 得到的保留码位集
完全一致时, 子集化 / CFF→TTF / 步进吸附三个预处理步骤的产物逐字节同源,
只需执行一次, 拼合仍按字重各做各的。

八档输出实际只用 6 份 CJK 源 (ExtraLight/Light 共用 Noto Light,
SemiBold/Bold 共用 Noto Mono Bold); 且 JetBrains Mono 各字重 cmap 覆盖
一致 —— 但此处不做任何假设: 保留码位集按实际 cmap 差集逐一计算,
不同则分组必然不同, 不会错误共享。

分组 id (进入中间产物文件名, 与 build.sh 的指纹增量机制天然兼容):
    gid = <CJK源基名>-<组合指纹前10位>
    组合指纹 = sha256( sha256(CJK源文件字节) + sha256(保留码位集文本) )
任何一侧输入变化 (换 CJK 源 / JBM 字符集变化) 都会落到新 gid, 旧产物作废。

Usage: cjk_dedup.py <jb.ttf> <cjk.otf> [<jb.ttf> <cjk.otf> ...]
Output: 每个输入对一行 TSV:  <weight>\\t<gid>\\t<cjk_basename>
        (<weight> 由 jb 文件名推断, 如 JetBrainsMono-Bold.ttf -> Bold)
"""
import hashlib
import os
import re
import sys

from fontTools.ttLib import TTFont


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def keepset_sha256(jb_path, cjk_path):
    """sha256 over the sorted codepoint set that subsetting would keep."""
    jb_cps = set(TTFont(jb_path, lazy=True).getBestCmap().keys())
    cjk_cps = set(TTFont(cjk_path, lazy=True).getBestCmap().keys())
    needed = sorted(cjk_cps - jb_cps)
    text = ",".join(f"{cp:X}" for cp in needed)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def main(argv):
    if len(argv) < 3 or len(argv) % 2 == 0:
        sys.exit("usage: cjk_dedup.py <jb.ttf> <cjk.otf> [<jb.ttf> <cjk.otf> ...]")
    pairs = [(argv[i], argv[i + 1]) for i in range(1, len(argv), 2)]

    cache = {}  # (cjk_path, keephash) -> gid  (同 CJK 源同保留集 => 同 gid)
    for jb_path, cjk_path in pairs:
        for p in (jb_path, cjk_path):
            if not os.path.isfile(p):
                sys.exit(f"ERROR: file not found: {p}")
        weight = re.sub(r"^JetBrainsMono[-.]", "", os.path.basename(jb_path))
        weight = re.sub(r"\.(ttf|otf)$", "", weight)
        keep = keepset_sha256(jb_path, cjk_path)
        key = (cjk_path, keep)
        gid = cache.get(key)
        if gid is None:
            nk_base = os.path.basename(cjk_path)
            nk_base = re.sub(r"\.(otf|ttf)$", "", nk_base)
            combined = hashlib.sha256(
                (file_sha256(cjk_path)[:32] + keep).encode("ascii")
            ).hexdigest()[:10]
            gid = f"{nk_base}-{combined}"
            cache[key] = gid
        print(f"{weight}\t{gid}\t{os.path.basename(cjk_path)}")


if __name__ == "__main__":
    main(sys.argv)
