# JetHan Mono

JetBrains Mono（拉丁 / 代码 / 编程连字）与思源等宽（Noto Sans Mono CJK SC，中文）拼合的等宽字体。

- **严格 2:1 终端对齐**：拉丁步进 600u/1000em，CJK/全角字形步进吸附为 1200u（字形不缩放、居中留白）——1 个汉字恰好等于 2 个英文字符宽，表格与混排对齐零漂移。
- **JetBrains Mono 优先**：拉丁、符号与 `calt` 编程连字全部取自 JBM；缺失字符回退思源等宽，中文渲染完整。
- **8 档字重**：Thin 100 / ExtraLight 200 / Light 300 / Regular 400 / Medium 500 / SemiBold 600 / Bold 700 / ExtraBold 800。

## CJK 侧字重来源

思源等宽（Noto Sans Mono CJK SC）原版只有 Regular/Bold 两档罗马字重，其余字重的 CJK 字形取自同源设计的 Noto Sans CJK SC（Source Han Sans 同源，全宽步进同为 1000u，缩放后不影响 2:1 网格）：

| JetHan 字重 | CSS | CJK 字形来源 |
|---|---|---|
| Thin | 100 | Noto Sans CJK SC Thin |
| ExtraLight | 200 | Noto Sans CJK SC Light |
| Light | 300 | Noto Sans CJK SC Light |
| Regular | 400 | Noto Sans Mono CJK SC Regular |
| Medium | 500 | Noto Sans CJK SC Medium |
| SemiBold | 600 | Noto Sans Mono CJK SC Bold |
| Bold | 700 | Noto Sans Mono CJK SC Bold |
| ExtraBold | 800 | Noto Sans CJK SC Black |

（ExtraBold 未与 Bold 重复：CJK 同名义字重观感偏轻，按 usWeightClass 距离就近映射、平手取更重档。）

## 构建

```bash
pip install fonttools brotli uharfbuzz
bash font-build/tools/fetch_sources.sh   # 下载上游源字体（3 个包，解压后约 145MB）
cd font-build
bash build.sh                            # 全部 8 档字重
bash build.sh Medium Bold                # 增量构建指定字重
```

产物：`font-build/output/JetHanMono-<Weight>.ttf/.woff2` ×8 + `JetHanMono-OFL.txt`。
构建末尾自动运行 `tools/verify.py` 校验（含区块级宽度不变量：宽格 1200 / 半角 600）与 `tools/shape_test.py` 连字/中文塑形冒烟测试。

## 管线（六步）

子集化 `subset_cjk.py` → CFF→glyf `otf2ttf.py`（cu2qu）→ CJK 步进 1200u `scale_cjk.py` → 拼合 `merge_fonts.py`（fonttools Merger API）→ 命名与元数据 `rename.py` / `export_woff2.py` → 校验 `verify.py` / `shape_test.py`。

## 设计契约

- **JBM 优先且完全一致**：非中文/全角码位的字形、步进与纵向度量（hhea ascent 1020 / descent −300）与原版 JetBrains Mono 一致，CJK 仅作缺失码位补充。
- **CJK 轮廓不缩放**：思源等宽字形保持原始 1000u 设计与原始字高（观感 = 上游原样），仅步进吸附为 1200u（= 2×600u）并把原设计盒水平居中（1000→1200 偏移 +100u，500→600 +50u，920→1200 +140u）；垂直基线关系维持思源原设计。
- **历史注记**：v1.001 曾将 CJK 轮廓等比放大 ×1.2 以"墨迹填满双格"（Maple Mono SC 流派）。但当时观测的 ≥1 格空白不可能由居中产生（1000u 盒放进 1200u 格，居中至多 ~0.33 格/侧），属误诊；放大反使汉字比上游高 20%（"中"墨迹 919u→1103u），故 v3 回退为不缩放方案。

## 目录

```
font-build/
├── build.sh            # 一键构建（8 档字重；Windows Git Bash 兼容，CRLF 自愈）
├── tools/              # 12 个工具脚本（源下载 / 六步管线 / 校验）
├── downloads/          # 上游源字体（fetch_sources.sh 生成，不入库）
└── output/             # 构建产物
.github/workflows/      # GitHub Actions：push 自动构建，artifact + 可选 release
src/app/                # 字体预览 / 下载页（Next.js，含 2:1 对齐演示）
```

## 命名与许可

- **为什么不叫 JetBrains-Source-Han-Mono**：Adobe 的 OFL 1.1 保留字体名 `'Source'`（RFN），且 JetBrains 为注册商标——拼合字体以中性名 **JetHan Mono** 发布。
- 许可：SIL Open Font License 1.1（保留名 "JetHan"）。双上游版权声明与许可证全文见 `font-build/output/JetHanMono-OFL.txt`。
