# JetHan Mono

JetBrains Mono（拉丁 / 代码 / 编程连字）与思源等宽（Noto Sans Mono CJK SC，中文）拼合的等宽字体。

- **严格 2:1 终端对齐**：拉丁步进 600u/1000em，CJK/全角字形步进吸附为 1200u——1 个汉字恰好等于 2 个英文字符宽，表格与混排对齐零漂移。
- **双 CJK 方案分包发行**：居中版（默认，轮廓不缩放+留白居中）与缩放版（轮廓 ×1.2 填满全角格）各出 TTF 与 WOFF2 两个压缩包，字体内名相同，二选一安装。
- **JetBrains Mono 优先**：拉丁、符号与 `calt` 编程连字全部取自 JBM；缺失字符回退思源等宽，中文渲染完整。
- **8 档字重**：Thin 100 / ExtraLight 200 / Light 300 / Regular 400 / Medium 500 / SemiBold 600 / Bold 700 / ExtraBold 800。
- **预览站动态加载**：预览页从 GitHub Latest Release 实时拉取散装 woff2 资产渲染，无需本地内置字体文件。

## 下载（两种 CJK 方案 x 两种格式，各一个压缩包）

两个方案**字体内部名称完全相同**（均为 JetHan Mono，8 档字重命名也一致），区别仅在 CJK 几何——同名家族**不可同时安装**（会互相覆盖/冲突），按观感偏好二选一。

**压缩包（4 个）——包内字体文件不带变体后缀，平铺在包根 + OFL 许可证，解压即用：**

| 压缩包 | 方案 | 格式 | 方案差异 |
|---|---|---|---|
| `JetHanMono-<版本>-Centered.zip` | 居中版（默认 / 推荐） | TTF ×8（桌面安装） | 轮廓**不缩放**，1000u 设计盒水平居中于 1200u 全角格；汉字 = 思源原样字面（"中"墨高 ~919u），全部墨迹在 JBM 行高度量（1020/-300）内 |
| `JetHanMono-<版本>-Scaled.zip` | 缩放版（满格派） | TTF ×8（桌面安装） | 轮廓双轴 **×1.2** 放大恰好填满 1200u 全角格；汉字比上游高 20%（"中"墨高 ~1103u），字面更满，接近传统中文字体；顶部会略超拉丁上伸部 |
| `JetHanMono-<版本>-Centered_woff.zip` | 居中版 | WOFF2 ×8（Web） | 同居中版，Web 嵌入用 |
| `JetHanMono-<版本>-Scaled_woff.zip` | 缩放版 | WOFF2 ×8（Web） | 同缩放版，Web 嵌入用 |

**散装字体（全部 32 个）——压缩包外的单个字体文件名带 `-Centered` / `-Scaled` 后缀：**

```
JetHanMono-<字重>-Centered.ttf   JetHanMono-<字重>-Scaled.ttf
JetHanMono-<字重>-Centered.woff2 JetHanMono-<字重>-Scaled.woff2
```

内容与压缩包内完全一致，仅文件名加方案后缀便于区分（如 `JetHanMono-Bold-Centered.ttf`），需要单档字重时可免解包直接下载；预览站即从 Latest Release 加载这批散装 woff2。

两套方案共用同一套质量门槛（`verify.py` / JBM 全字形不变量 / HarfBuzz 塑形 / 元数据审计），除 CJK 几何外一切一致。

> 历史：v1.001–v1.002 曾在"缩放"与"居中"之间反复；v3 定版居中方案后，应需求自 1.003 起将缩放方案以独立包形式并线提供，两者长期共存、同版本号发布。

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
bash build.sh                            # 全部 8 档字重 x 双变体（默认串行）
VARIANTS=centered bash build.sh          # 只构建居中版（scaled 同理）
bash build.sh Medium Bold                # 增量构建指定字重
JOBS=4 bash build.sh                     # 每阶段最多 4 任务并行（阶段间保持屏障）
SKIP_WOFF2=1 bash build.sh               # 日常调试：只出 TTF
bash build.sh --verify-only              # 只跑校验阶段（CI 的 test job 即此模式）
```

产物：`font-build/output/<variant>/JetHanMono-<Weight>.ttf/.woff2` ×8 + `JetHanMono-OFL.txt`（每变体一套；子集化/CFF→TTF 为共享层只跑一次，变体只影响吸附之后的阶段）。
构建末尾自动运行 `tools/verify.py` 校验（含区块级宽度不变量：宽格 1200 / 半角 600）与 `tools/shape_test.py` 连字/中文塑形冒烟测试；`SKIP_VERIFY=1` 可跳过（CI 中校验独立成 test job）。

### 构建效率设计（v3）

- **步骤级指纹增量**：每步把输入联合 SHA-256 写入标记文件，输入未变直接跳过；单次构建内文件哈希按（路径+size+mtime）缓存复用，命中缓存时不再对被多字重共享的 Noto 源反复算哈希。
- **CJK 预处理去重**：子集化/转换/吸附的产物只取决于（CJK 源字体, 保留码位集 = cjk_cmap − jb_cmap）。ExtraLight/Light、SemiBold/Bold 共用 CJK 源，且各字重 JBM 字符集一致 → 预处理任务 8 份并为 6 份（`tools/cjk_dedup.py` 按 cmap 实际差集分组，不做任何"各字重 cmap 相同"的假设）。拼合及之后仍按字重独立。
- **阶段内并行**：`JOBS=N` 控制每阶段并发任务数（阶段之间保持屏障；任一任务失败立即停止派发、回放失败日志并报出失败字重）。并行池为 POSIX 轮询实现，Git Bash 兼容。
- **阶段耗时统计**：每个任务与每阶段的累计耗时、构建总耗时打印在输出中，用于定位瓶颈再决定下一步优化（如 cu2qu 转换精度实验，属高风险项未默认启用）。

## 管线（六步）

子集化 `subset_cjk.py` → CFF→glyf `otf2ttf.py`（cu2qu）→ **按变体循环**：CJK 步进 1200u `scale_cjk.py`（`--variant centered/scaled`）→ 拼合 `merge_fonts.py`（fonttools Merger API）→ 命名与元数据 `rename.py` / `export_woff2.py` → 校验 `verify.py` / `invariant_test.py`（JBM 保真硬门槛）/ `shape_test.py`。变体指纹以 `DEPHASH_EXTRA` 参与每步增量哈希，居中/缩放产物在 `converted/<variant>/`、`output/<variant>/` 内互不干扰；吸附之前的产物两变体共享。

## 核心设计契约（不可妥协）

JetHanMono is an **additive extension** of JetBrains Mono, not a redesign or modification of its Latin typography:

1. JetBrains Mono is the authoritative base font.
2. Every glyph and character mapping already provided by JetBrains Mono must remain unchanged.
3. Original JetBrains Mono advances, bearings, outlines, OpenType layout behavior, and shaping results must be preserved.
4. CJK fonts may only supply glyphs for codepoints missing from the corresponding JetBrains Mono weight.
5. CJK glyphs must conform to the 2:1 terminal-width grid without modifying existing JetBrains Mono glyph geometry.
6. Mixed Latin/CJK text must preserve the exact shaping and positioning behavior of its Latin portions.
7. Build optimizations must not weaken these invariants.

中文要点：JBM 是唯一基底（全部原始 cmap 码位，不止 ASCII）；CJK 只补充缺失码位（`cjk_cmap − jb_cmap`）；中英混排不得改变英文的任何排版行为；中文适应 JBM 的 2:1 网格而非反向修改 JBM；**构建提速服从契约**（禁止修改 JBM 原字或其 GSUB/GPOS）。

该契约由 `tools/invariant_test.py` 落地为自动化硬门槛（全字形级）：

| 检查组 | 内容 |
|---|---|
| CMAP | 全部 JBM 码位 → 同名 glyph，无丢失/顶替 |
| ORDER | JBM glyph 顺序作为前缀保留（glyph ID 稳定） |
| GLYF | 全部 JBM 轮廓分解后逐点一致 |
| HMTX | 全部 JBM (advance, lsb) 逐字形一致 |
| OTL | GSUB/GPOS/GDEF 按 glyph 名序列化逐字一致；kern/morx 等不凭空出现 |
| VMET | 纵向度量锁回 JBM（行高/基线不变） |
| HB | 全码位 HarfBuzz 塑形（glyph/cluster/advance/offset）+ 连字语料 + calt 开关 |
| MIX | 中英混排：英文片段塑形一致、英文簇零位移、CJK 簇 1200/600 网格 |

## 设计契约（历史沿革）

- **JBM 优先且完全一致**：非中文/全角码位的字形、步进与纵向度量（hhea ascent 1020 / descent −300）与原版 JetBrains Mono 一致，CJK 仅作缺失码位补充。
- **居中版（默认发行包）**：思源等宽字形保持原始 1000u 设计与原始字高（观感 = 上游原样），仅步进吸附为 1200u（= 2×600u）并把原设计盒水平居中（1000→1200 偏移 +100u，500→600 +50u，920→1200 +140u）；垂直基线关系维持思源原设计。
- **缩放版（独立发行包，1.003 起）**：同一管线、同一字体内名，仅把 CJK 轮廓双轴 ×1.2 放大填满全角格（dx=0），供偏好满格字面的用户选择；纵向度量锁与全部质量门槛与居中版一致。
- **历史注记**：v1.001 曾将 CJK 轮廓等比放大 ×1.2 以"墨迹填满双格"（Maple Mono SC 流派）。但当时观测的 ≥1 格空白不可能由居中产生（1000u 盒放进 1200u 格，居中至多 ~0.33 格/侧），属误诊；放大反使汉字比上游高 20%（"中"墨迹 919u→1103u），故 v3 回退为不缩放方案。1.003 起，两种观感以双发行包形式各自成线（几何由 `scale_cjk.py --variant` 定义，居中版默认推荐），不再互相否定。

## 目录

```
font-build/
├── build.sh            # 一键构建（双变体/并行/去重/指纹增量；Windows Git Bash 兼容，CRLF 自愈）
├── tools/              # 13 个工具脚本（源下载 / 分组去重 / 六步管线 / 双变体吸附 / 校验）
├── downloads/          # 上游源字体（fetch_sources.sh 生成，不入库）
└── output/<variant>/   # 构建产物（centered/ 与 scaled/ 各一套，文件名相同）
.github/workflows/      # GitHub Actions：build / test / release 三 job，
                        # 测试为发布质量门槛（dispatch 可选跑、默认勾选）；
                        # release 打 4 个压缩包（居中/缩放 x ttf/woff2，包内无后缀）
                        # + 32 个散装字体（带 -Centered/-Scaled 后缀）；
                        # metadata-audit 逐包审计分发资产
src/app/                # 字体预览 / 下载页（Next.js，含 2:1 对齐演示，
                        # 字体从 GitHub Latest Release 动态加载，默认展示居中版）
```

## 命名与许可

- **为什么不叫 JetBrains-Source-Han-Mono**：Adobe 的 OFL 1.1 保留字体名 `'Source'`（RFN），且 JetBrains 为注册商标——拼合字体以中性名 **JetHan Mono** 发布。居中/缩放两个发行包共用此名（这也是两包不可同装的原因）。
- 许可：SIL Open Font License 1.1（保留名 "JetHan"）。双上游版权声明与许可证全文见压缩包内 / `font-build/output/<variant>/JetHanMono-OFL.txt`。
