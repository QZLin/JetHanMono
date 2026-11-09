#!/usr/bin/env bash
# JetHan Mono 一键构建脚本
# JetBrains Mono (英文/代码, 优先) + Noto Sans Mono CJK SC (思源等宽同源字体, 补充中文)
#
# 流程: 子集化 -> CFF->TTF -> CJK 步进 1200u -> 拼合 -> 改名/woff2 -> 校验
#
# Windows (Git Bash / MSYS2) 兼容性:
#   - 下方守卫行自动把 CRLF 脚本修复为 LF 后重启 (git autocrlf=true 检出的常见坑)
#   - 自动寻找带 fonttools/brotli/uharfbuzz 的 python3/python/py (可用 PYTHON_BIN 覆盖)
#   - MSYS2_ARG_CONV_EXCL 关闭 Git Bash 对参数的路径改写
#   - 不调用 pyftmerge CLI: 其选项解析只支持 --opt=value 语法, 空格写法
#     (--output-file OUT) 会把输出路径当成第一个输入字体, 导致
#     FileNotFoundError: No such file or directory: 'OUT';
#     拼合统一走 tools/merge_fonts.py (Merger API)
#
# 用法:
#   1. bash tools/fetch_sources.sh   (或手动将字体放入 downloads/)
#   2. bash build.sh                 # 全部 8 个罗马字重
#      bash build.sh Medium ExtraBold   # 只构建指定字重 (增量调试)
# 产物: output/JetHanMono-<Weight>.ttf/.woff2 (x8) + JetHanMono-OFL.txt
#
# 步骤级增量 (CI 缓存友好):
#   每步执行后把"输入文件联合 sha256"写入 <标记> 文件; 重跑时输入指纹未变
#   + 输出仍在 => 跳过该步。配合 CI actions/cache 持久化 subsetted/
#   converted/ output/ 三个目录, 未改变的步骤跨次运行直接命中 (例如只改
#   rename.py 时, 子集化/转换/拉宽/拼合全部跳过, 只重跑改名+woff2)。
#   注意 otf2ttf 输出为 <name>.pre.ttf (scale 前的原始转换), scale 从
#   .pre.ttf 复制后原地拉宽; merge 输出 output/.merged-<Weight>.ttf
#   (rename 前的原始拼合), rename 从 .merged 复制后原地改名 —— 输入输出
#   分离才能对"原地覆盖"型步骤做可靠的指纹判断。
#   FORCE_BUILD=1 忽略指纹强制全量重建。
#
# 字重映射 (JetBrains 8 档 -> CJK 侧来源):
#   思源等宽 (Noto Sans Mono CJK SC) 只有 Regular/Bold 两档字重;
#   其余字重的 CJK 字形来自 Noto Sans CJK SC (Source Han Sans 同源,
#   CJK 字形设计与等宽版一致, 全宽步进同为 1000u, 不影响 2:1 网格)。
#   按 usWeightClass 距离就近映射, 距离平手取更重档 (CJK 同名义字重
#   观感偏轻, 且避免 ExtraBold 回退到与 Bold 重复):
if grep -q "$(printf '\r')" "$0" 2>/dev/null; then echo "[build.sh] 检测到 CRLF 行尾, 自动转换为 LF 并重启..."; tr -d '\r' <"$0" >"$0.tmp" && mv "$0.tmp" "$0" && exec bash "$0" "$@"; fi # CRLF guard: 必须保持单行, 行尾 CR 落进注释才不会破坏解析

set -euo pipefail
cd "$(dirname "$0")"

export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:-*}"  # MSYS2/Git Bash: 参数原样传递

# ---- 寻找可用的 python (需已安装 fonttools/brotli/uharfbuzz) ----
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  for C in python3 python py; do
    if command -v "$C" >/dev/null 2>&1 && "$C" -c "import fontTools, brotli, uharfbuzz" >/dev/null 2>&1; then
      PYTHON_BIN="$C"
      break
    fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: 未找到带 fonttools/brotli/uharfbuzz 的 python。"
  echo "       请先: pip install fonttools brotli uharfbuzz"
  echo "       或用环境变量指定解释器: PYTHON_BIN=/path/to/python bash build.sh"
  exit 1
fi
echo "python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print(sys.executable)'))"

# ---- 字重清单与映射 (JetBrains 8 档 -> CJK 来源) ----
# 等宽版只有 Regular/Bold; 其余字重 CJK 来自 Noto Sans CJK SC (见文件头注释)
JB_WEIGHTS=(Thin          ExtraLight      Light       Regular                Medium             SemiBold             Bold                ExtraBold)
NK_WEIGHTS=(NotoSansCJKsc-Thin NotoSansCJKsc-Light NotoSansCJKsc-Light NotoSansMonoCJKsc-Regular NotoSansCJKsc-Medium NotoSansMonoCJKsc-Bold NotoSansMonoCJKsc-Bold NotoSansCJKsc-Black)

# 可选位置参数: 只构建指定字重, 如 `bash build.sh Medium ExtraBold`
if [ "$#" -gt 0 ]; then
  _jb=(); _nk=()
  for W in "$@"; do
    _hit=""
    for i in "${!JB_WEIGHTS[@]}"; do
      if [ "${JB_WEIGHTS[$i]}" = "$W" ]; then _hit=1; _jb+=("$W"); _nk+=("${NK_WEIGHTS[$i]}"); fi
    done
    if [ -z "$_hit" ]; then echo "ERROR: 未知字重 '$W' (可选: ${JB_WEIGHTS[*]})"; exit 1; fi
  done
  JB_WEIGHTS=("${_jb[@]}")
  NK_WEIGHTS=("${_nk[@]}")
fi
echo "构建字重: ${JB_WEIGHTS[*]}"
echo "CJK 映射: ${NK_WEIGHTS[*]}"

cjk_weight() {
  local i
  for i in "${!JB_WEIGHTS[@]}"; do
    [ "${JB_WEIGHTS[$i]}" = "$1" ] && { echo "${NK_WEIGHTS[$i]}"; return; }
  done
  echo "Regular"
}

mkdir -p subsetted converted output

# ---- 步骤级增量助手: 输入指纹未变 + 输出存在 => 跳过 ----
FORCE="${FORCE_BUILD:-0}"
DEPHASH() { # DEPHASH <file...> -> 联合 sha256; 缺失文件也参与 hash => 触发重跑
  local h=""
  local f
  for f in "$@"; do
    if [ -s "$f" ]; then h="$h$(sha256sum "$f" | cut -d' ' -f1)"; else h="$h-"; fi
  done
  printf '%s' "$h" | sha256sum | cut -d' ' -f1
}
STEP_UP2DATE() { # STEP_UP2DATE <output> <dh> <input...>; 返回 0 => 可跳过
  [ "$FORCE" = "1" ] && return 1
  local out="$1" dh="$2"
  shift 2
  [ -s "$out" ] && [ -s "$dh" ] && [ "$(cat "$dh")" = "$(DEPHASH "$@")" ]
}
STEP_MARK() { local dh="$1"; shift; DEPHASH "$@" > "$dh"; }

echo "== 1/6 子集化 CJK (仅保留 JetBrains 未覆盖的码位) =="
for W in "${JB_WEIGHTS[@]}"; do
  NK="$(cjk_weight "$W")"
  if STEP_UP2DATE "subsetted/NotoMonoSC-$W.ttf" "subsetted/.dh-$W.subset" \
       "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "tools/subset_cjk.py"; then
    echo "  [$W] skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] run"
    "$PYTHON_BIN" tools/subset_cjk.py "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "subsetted/NotoMonoSC-$W.ttf"
    STEP_MARK "subsetted/.dh-$W.subset" "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "tools/subset_cjk.py"
  fi
done

echo "== 2/6 CFF -> TrueType 轮廓转换 (cu2qu, 输出 .pre.ttf 供 scale 增量) =="
for W in "${JB_WEIGHTS[@]}"; do
  if STEP_UP2DATE "converted/NotoMonoSC-$W.pre.ttf" "converted/.dh-$W.otf2ttf" \
       "subsetted/NotoMonoSC-$W.ttf" "tools/otf2ttf.py"; then
    echo "  [$W] skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] run"
    "$PYTHON_BIN" tools/otf2ttf.py "subsetted/NotoMonoSC-$W.ttf" -o "converted/NotoMonoSC-$W.pre.ttf" --overwrite
    STEP_MARK "converted/.dh-$W.otf2ttf" "subsetted/NotoMonoSC-$W.ttf" "tools/otf2ttf.py"
  fi
done

echo "== 3/6 CJK 等比缩放 x1.2 并步进对齐 (1000u->1200u = 2 x 拉丁 600u, 墨迹填满两格) =="
for W in "${JB_WEIGHTS[@]}"; do
  if STEP_UP2DATE "converted/NotoMonoSC-$W.ttf" "converted/.dh-$W.scale" \
       "converted/NotoMonoSC-$W.pre.ttf" "tools/scale_cjk.py"; then
    echo "  [$W] skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] run"
    cp -f "converted/NotoMonoSC-$W.pre.ttf" "converted/NotoMonoSC-$W.ttf"
    "$PYTHON_BIN" tools/scale_cjk.py "converted/NotoMonoSC-$W.ttf"
    STEP_MARK "converted/.dh-$W.scale" "converted/NotoMonoSC-$W.pre.ttf" "tools/scale_cjk.py"
  fi
done

echo "== 4/6 拼合 (第一个字体优先, Merger API; 输出 .merged-* 供 rename 增量) =="
for W in "${JB_WEIGHTS[@]}"; do
  if STEP_UP2DATE "output/.merged-$W.ttf" "output/.dh-$W.merge" \
       "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf" "tools/merge_fonts.py"; then
    echo "  [$W] skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] run"
    "$PYTHON_BIN" tools/merge_fonts.py -o "output/.merged-$W.ttf" "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf"
    STEP_MARK "output/.dh-$W.merge" "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf" "tools/merge_fonts.py"
  fi
done

echo "== 5/6 重命名+度量锁定 / woff2 / OFL (均支持指纹跳过) =="
for W in "${JB_WEIGHTS[@]}"; do
  if STEP_UP2DATE "output/JetHanMono-$W.ttf" "output/.dh-$W.rename" \
       "output/.merged-$W.ttf" "tools/rename.py"; then
    echo "  [$W] rename skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] rename run"
    cp -f "output/.merged-$W.ttf" "output/JetHanMono-$W.ttf"
    "$PYTHON_BIN" tools/rename.py "output/JetHanMono-$W.ttf"
    STEP_MARK "output/.dh-$W.rename" "output/.merged-$W.ttf" "tools/rename.py"
  fi
  if STEP_UP2DATE "output/JetHanMono-$W.woff2" "output/.dh-$W.woff2" \
       "output/JetHanMono-$W.ttf" "tools/export_woff2.py"; then
    echo "  [$W] woff2 skip (输入指纹未变, 命中缓存)"
  else
    echo "  [$W] woff2 run"
    "$PYTHON_BIN" tools/export_woff2.py "output/JetHanMono-$W.ttf"
    STEP_MARK "output/.dh-$W.woff2" "output/JetHanMono-$W.ttf" "tools/export_woff2.py"
  fi
done
# OFL 许可证 (依赖 JetBrains OFL 原文 + rename.py)
if STEP_UP2DATE "output/JetHanMono-OFL.txt" "output/.dh-ofl" \
     "downloads/JetBrainsMono-OFL.txt" "tools/rename.py"; then
  echo "  [OFL] skip (输入指纹未变, 命中缓存)"
else
  echo "  [OFL] run"
  "$PYTHON_BIN" tools/rename.py --license-only output
  STEP_MARK "output/.dh-ofl" "downloads/JetBrainsMono-OFL.txt" "tools/rename.py"
fi

echo "== 6/6 校验 (静态度量 + HarfBuzz shaping; 产物指纹未变则沿用上次结论) =="
for W in "${JB_WEIGHTS[@]}"; do
  VD="output/.dh-$W.verified"
  if STEP_UP2DATE "$VD" "$VD" \
       "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf" \
       "output/JetHanMono-$W.ttf" "tools/verify.py" "tools/shape_test.py"; then
    echo "  [$W] skip (产物指纹未变, 校验结论沿用)"
  else
    echo "  [$W] run"
    "$PYTHON_BIN" tools/verify.py "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf" "output/JetHanMono-$W.ttf"
    "$PYTHON_BIN" tools/shape_test.py "downloads/JetBrainsMono-$W.ttf" "output/JetHanMono-$W.ttf"
    STEP_MARK "$VD" "downloads/JetBrainsMono-$W.ttf" "converted/NotoMonoSC-$W.ttf" \
      "output/JetHanMono-$W.ttf" "tools/verify.py" "tools/shape_test.py"
  fi
done

echo "完成! 产物在 output/, 复制到 web:"
echo "  cp output/JetHanMono-*.ttf output/JetHanMono-*.woff2 output/JetHanMono-OFL.txt ../public/fonts/"
