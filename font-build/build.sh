#!/usr/bin/env bash
# JetHan Mono 一键构建脚本 (v3: 阶段内并行 + CJK 预处理去重 + 阶段耗时统计)
# JetBrains Mono (英文/代码, 优先) + Noto Sans Mono CJK SC (思源等宽同源字体, 补充中文)
#
# 流程: CJK 预处理分组(去重) -> 子集化 -> CFF->TTF -> CJK 步进 1200u
#       -> 拼合 -> 改名/woff2 -> 校验
#
# Windows (Git Bash / MSYS2) 兼容性:
#   - 下方守卫行自动把 CRLF 脚本修复为 LF 后重启 (git autocrlf=true 检出的常见坑)
#   - 自动寻找带 fonttools/brotli/uharfbuzz 的 python3/python/py (可用 PYTHON_BIN 覆盖)
#   - MSYS2_ARG_CONV_EXCL 关闭 Git Bash 对参数的路径改写
#   - 并行池用 POSIX 轮询 (kill -0), 不依赖 bash 5.1 的 `wait -n -p`
#
# 用法:
#   1. bash tools/fetch_sources.sh   (或手动将字体放入 downloads/)
#   2. bash build.sh                 # 全部 8 个罗马字重
#      bash build.sh Medium ExtraBold   # 只构建指定字重 (增量调试)
#      JOBS=4 bash build.sh             # 每阶段最多 4 个任务并行 (阶段间保持屏障)
#      SKIP_WOFF2=1 bash build.sh       # 日常调试: 只出 TTF
#      bash build.sh --verify-only      # 只跑第 6 阶段校验 (CI 的 test job 即此模式)
#
# 环境开关:
#   JOBS=N          每阶段并行任务数 (默认 1=串行; 4核/16GB 建议 2, 8核/16GB 可 3-4,
#                   以 otf2ttf 阶段实际内存峰值为准逐步上调)
#   SKIP_WOFF2=1    跳过 woff2 导出 (调整宽度/查轮廓时 TTF 足够)
#   SKIP_VERIFY=1   跳过校验阶段 (CI 把校验拆到独立 test job)
#   FORCE_BUILD=1   忽略指纹强制全量重建
#
# 产物: output/JetHanMono-<Weight>.ttf/.woff2 (x8) + JetHanMono-OFL.txt
#
# 步骤级增量 (CI 缓存友好):
#   每步执行后把"输入文件联合 sha256"写入 <标记> 文件; 重跑时输入指纹未变
#   + 输出仍在 => 跳过该步。配合 CI actions/cache 持久化 subsetted/
#   converted/ output/ 三个目录, 未改变的步骤跨次运行直接命中 (例如只改
#   rename.py 时, 子集化/转换/吸附/拼合全部跳过, 只重跑改名+woff2)。
#   单次构建内文件哈希按 (路径 + size + mtime) 缓存复用: 同一份被多个字重
#   引用的 Noto OTF 只读盘算一次哈希, 命中缓存时不再反复起 sha256sum 进程。
#   注意 otf2ttf 输出为 <name>.pre.ttf (吸附前的原始转换), scale 从
#   .pre.ttf 复制后原地改写; merge 输出 output/.merged-<Weight>.ttf
#   (改名前的原始拼合), rename 从 .merged 复制后原地改名 —— 输入输出
#   分离才能对"原地覆盖"型步骤做可靠的指纹判断。
#
# CJK 预处理去重 (v3):
#   子集化输出只取决于 (CJK 源字体, 保留码位集 = cjk_cmap - jb_cmap)。
#   tools/cjk_dedup.py 按实际 cmap 差集分组: 八档输出只用 6 份 CJK 源
#   (ExtraLight/Light 共用 Noto Light, SemiBold/Bold 共用 Noto Mono Bold),
#   同组字重共享一份子集化/转换/吸附产物 (文件名 CJK-<gid>.ttf),
#   预处理任务 8 -> 6; gid 含 CJK 源字节指纹 + 保留码位集指纹, 任一变化
#   自然落到新文件。拼合及之后仍按字重独立 (JBM 侧各不相同)。
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
  echo "ERROR: 未找到带 fontTools/brotli/uharfbuzz 的 python。"
  echo "       请先: pip install fonttools brotli uharfbuzz"
  echo "       或用环境变量指定解释器: PYTHON_BIN=/path/to/python bash build.sh"
  exit 1
fi
echo "python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print(sys.executable)'))"

# ---- 开关与参数解析 ----
JOBS="${JOBS:-1}"
case "$JOBS" in *[!0-9]*|"") JOBS=1 ;; esac
if [ "$JOBS" -lt 1 ]; then JOBS=1; fi
SKIP_WOFF2="${SKIP_WOFF2:-0}"
SKIP_VERIFY="${SKIP_VERIFY:-0}"
FORCE="${FORCE_BUILD:-0}"
VERIFY_ONLY=0
POSITIONAL=()
for a in "$@"; do
  case "$a" in
    --verify-only) VERIFY_ONLY=1 ;;
    *) POSITIONAL+=("$a") ;;
  esac
done

# ---- 字重清单与映射 (JetBrains 8 档 -> CJK 来源) ----
# 等宽版只有 Regular/Bold; 其余字重 CJK 来自 Noto Sans CJK SC (见文件头注释)
JB_WEIGHTS=(Thin          ExtraLight      Light       Regular                Medium             SemiBold             Bold                ExtraBold)
NK_WEIGHTS=(NotoSansCJKsc-Thin NotoSansCJKsc-Light NotoSansCJKsc-Light NotoSansMonoCJKsc-Regular NotoSansCJKsc-Medium NotoSansMonoCJKsc-Bold NotoSansMonoCJKsc-Bold NotoSansCJKsc-Black)

# 可选位置参数: 只构建指定字重, 如 `bash build.sh Medium ExtraBold`
if [ "${#POSITIONAL[@]}" -gt 0 ]; then
  _jb=(); _nk=()
  for W in "${POSITIONAL[@]}"; do
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
echo "JOBS=$JOBS  SKIP_WOFF2=$SKIP_WOFF2  SKIP_VERIFY=$SKIP_VERIFY  FORCE_BUILD=$FORCE  VERIFY_ONLY=$VERIFY_ONLY"

LOGDIR=".build-logs"
mkdir -p subsetted converted output "$LOGDIR/timing"
rm -f "$LOGDIR"/timing/* 2>/dev/null || true

# ---- 步骤级增量助手: 输入指纹未变 + 输出存在 => 跳过 ----
# 单次构建内的文件哈希缓存: key = 路径 + (size:mtime), 任一变化即重算,
# 因此"本步先写文件、下步再把它当输入哈希"的场景天然正确。
declare -A HASH_CACHE=()
filehash() { # filehash <file> -> sha256 (缺失/空文件 => "-")
  local f="$1" st h key
  st="$(stat -c '%s:%Y' "$f" 2>/dev/null || printf 'missing')"
  key="$f|$st"
  h="${HASH_CACHE[$key]-}"
  if [ -n "$h" ]; then printf '%s' "$h"; return 0; fi
  if [ -s "$f" ]; then
    h="$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)"
    if [ -z "$h" ]; then h="-"; fi
  else
    h="-"
  fi
  HASH_CACHE[$key]="$h"
  printf '%s' "$h"
}
DEPHASH() { # DEPHASH <file...> -> 联合 sha256; 缺失文件也参与 hash => 触发重跑
  local h=""
  local f
  for f in "$@"; do
    h="$h$(filehash "$f")"
  done
  printf '%s' "$h" | sha256sum | cut -d' ' -f1
}
STEP_UP2DATE() { # STEP_UP2DATE <output> <dh> <input...>; 返回 0 => 可跳过
  if [ "$FORCE" = "1" ]; then return 1; fi
  local out="$1" dh="$2"
  shift 2
  [ -s "$out" ] && [ -s "$dh" ] && [ "$(cat "$dh")" = "$(DEPHASH "$@")" ]
}
STEP_MARK() { local dh="$1"; shift; DEPHASH "$@" > "$dh"; }

# ---- 耗时统计 ----
report_time() { printf '%s\n' "$3" > "$LOGDIR/timing/${1}__${2}"; }  # <stage> <task> <sec>
fmt_dur() { # 秒 -> h/m/s 可读
  local s="$1"
  if [ "$s" -ge 3600 ]; then printf '%dh%02dm%02ds' $((s / 3600)) $((s % 3600 / 60)) $((s % 60))
  elif [ "$s" -ge 60 ]; then printf '%dm%02ds' $((s / 60)) $((s % 60))
  else printf '%ss' "$s"; fi
}
print_summary() {
  echo ""
  echo "== 各阶段任务耗时 (任务累计; 并行时墙钟见各阶段 [阶段墙钟]) =="
  local stage f s sum n names
  for stage in subset otf2ttf scale merge rename woff2 verify; do
    sum=0; n=0; names=""
    for f in "$LOGDIR"/timing/"$stage"__*; do
      if [ -e "$f" ]; then
        s="$(cat "$f")"
        sum=$((sum + s)); n=$((n + 1))
        names="$names  ${f##*__}=${s}s"
      fi
    done
    if [ "$n" -gt 0 ]; then
      echo "  $stage: ${n} 项, 累计 $(fmt_dur "$sum")  $names"
    fi
  done
}

# ---- 阶段内并行池 (最多 JOBS 个并发; 任一失败即停止派新任务并报告) ----
# 串行模式 (JOBS=1) 直接前台执行, 输出实时可见; 并行模式重定向到
# $LOGDIR/<fn>-<item>.log, 失败时自动回放日志尾部。
POOL_PIDS=(); POOL_ITEMS=(); POOL_FAIL=0; POOL_FN=""
pool_alive() {
  local n=0 i
  for i in "${!POOL_PIDS[@]}"; do
    if [ -n "${POOL_PIDS[$i]}" ] && kill -0 "${POOL_PIDS[$i]}" 2>/dev/null; then n=$((n + 1)); fi
  done
  printf '%s' "$n"
}
pool_reap() {
  local i p
  for i in "${!POOL_PIDS[@]}"; do
    p="${POOL_PIDS[$i]}"
    if [ -n "$p" ] && ! kill -0 "$p" 2>/dev/null; then
      if wait "$p"; then
        echo "  [pool] 完成: ${POOL_ITEMS[$i]}"
      else
        echo "  [pool] 失败: ${POOL_ITEMS[$i]}  (日志尾部: $LOGDIR/${POOL_FN}-${POOL_ITEMS[$i]}.log)" >&2
        tail -n 20 "$LOGDIR/${POOL_FN}-${POOL_ITEMS[$i]}.log" >&2 2>/dev/null || true
        POOL_FAIL=1
      fi
      POOL_PIDS[$i]=""
    fi
  done
}
map_run() { # map_run <fn> <item...>
  local fn="$1"; shift
  POOL_FN="$fn"
  if [ "$JOBS" -le 1 ] || [ "$#" -le 1 ]; then
    local it
    for it in "$@"; do "$fn" "$it"; done
    return 0
  fi
  echo "  (并行执行, JOBS=$JOBS; 各任务日志: $LOGDIR/${fn}-*.log)"
  POOL_PIDS=(); POOL_ITEMS=(); POOL_FAIL=0
  local it
  for it in "$@"; do
    while :; do
      pool_reap
      if [ "$POOL_FAIL" -ne 0 ]; then break; fi
      if [ "$(pool_alive)" -lt "$JOBS" ]; then break; fi
      sleep 0.3
    done
    if [ "$POOL_FAIL" -ne 0 ]; then break; fi
    "$fn" "$it" > "$LOGDIR/${fn}-${it}.log" 2>&1 &
    POOL_PIDS+=("$!"); POOL_ITEMS+=("$it")
  done
  while [ "$(pool_alive)" -gt 0 ]; do sleep 0.3; pool_reap; done
  pool_reap
  return "$POOL_FAIL"
}

# ---- CJK 预处理分组 (去重; 分组结果本身也带指纹缓存) ----
GROUPS_TSV="converted/.groups.tsv"
GROUPS_DH="converted/.dh-groups"
declare -A GID_OF=() NK_OF=() REP_OF=()
GIDS=()

declare -a PAIR_ARGS=()
for i in "${!JB_WEIGHTS[@]}"; do
  PAIR_ARGS+=("downloads/JetBrainsMono-${JB_WEIGHTS[$i]}.ttf" "downloads/${NK_WEIGHTS[$i]}.otf")
done

if STEP_UP2DATE "$GROUPS_TSV" "$GROUPS_DH" "${PAIR_ARGS[@]}" "tools/cjk_dedup.py"; then
  echo "CJK 预处理分组: 命中缓存 ($GROUPS_TSV)"
else
  echo "CJK 预处理分组: 计算 (cmap 差集 + CJK 源字节指纹)..."
  "$PYTHON_BIN" tools/cjk_dedup.py "${PAIR_ARGS[@]}" > "$GROUPS_TSV.tmp"
  mv -f "$GROUPS_TSV.tmp" "$GROUPS_TSV"
  STEP_MARK "$GROUPS_DH" "${PAIR_ARGS[@]}" "tools/cjk_dedup.py"
fi
GROUP_N=0
while IFS=$'\t' read -r W gid nk; do
  if [ -n "${W:-}" ]; then
    GID_OF["$W"]="$gid"
    NK_OF["$gid"]="${nk%.*}"   # 去掉 .otf 扩展名, 与 NK_WEIGHTS 的基名约定一致
    if [ -z "${REP_OF[$gid]-}" ]; then REP_OF["$gid"]="$W"; GIDS+=("$gid"); GROUP_N=$((GROUP_N + 1)); fi
  fi
done < "$GROUPS_TSV"
echo "预处理任务: ${#JB_WEIGHTS[@]} 字重 -> ${GROUP_N} 组"
for gid in "${GIDS[@]}"; do
  echo "  [组] $gid  (代表字重: ${REP_OF[$gid]})"
done

T_TOTAL0=$(date +%s)

# ---------- --verify-only: 只跑第 6 阶段 (CI test job 用) ----------
if [ "$VERIFY_ONLY" = "1" ]; then
  echo ""
  echo "== --verify-only: 只跑校验 (要求 downloads/ + converted CJK 分组产物 + output/ 已就位) =="
  _missing=0
  for W in "${JB_WEIGHTS[@]}"; do
    gid="${GID_OF[$W]}"
    for f in "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" "output/JetHanMono-$W.ttf"; do
      if [ ! -s "$f" ]; then echo "MISSING: $f"; _missing=1; fi
    done
  done
  if [ "$_missing" -ne 0 ]; then
    echo "缺少输入文件: 请先完整构建 (CI 中确认两个 artifact 均已下载到位)" >&2
    exit 1
  fi
  s0=$(date +%s)
  map_run stage_verify "${JB_WEIGHTS[@]}"
  echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"
  print_summary
  echo "完成 (verify-only)! 总耗时 $(fmt_dur "$(( $(date +%s) - T_TOTAL0 ))")"
  exit 0
fi

# ---------- 阶段 1/6: CJK 子集化 (按 gid 去重) ----------
stage_subset() {
  # 注意: local 的多个赋值参数在部分 bash 构建中是"先整体展开再赋值",
  # 依赖同命令前面赋值的展开(如 ${REP_OF[$gid]})会命中未定义变量。
  # 因此依赖查找一律拆成独立命令, 不依赖展开顺序。
  local gid="$1" t0 W NK
  W="${REP_OF[$gid]}"
  NK="${NK_OF[$gid]}"
  local out="subsetted/CJK-$gid.ttf"
  if STEP_UP2DATE "$out" "subsetted/.dh-$gid.subset" \
       "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "tools/subset_cjk.py"; then
    echo "  [$gid] skip (指纹命中, 命中缓存)"
    return 0
  fi
  t0=$(date +%s)
  "$PYTHON_BIN" tools/subset_cjk.py "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "$out"
  STEP_MARK "subsetted/.dh-$gid.subset" "downloads/JetBrainsMono-$W.ttf" "downloads/$NK.otf" "tools/subset_cjk.py"
  report_time subset "$gid" "$(( $(date +%s) - t0 ))"
}

# ---------- 阶段 2/6: CFF -> TrueType 轮廓转换 (cu2qu, 按 gid 去重) ----------
stage_otf2ttf() {
  local gid="$1" t0
  local out="converted/CJK-$gid.pre.ttf"
  if STEP_UP2DATE "$out" "converted/.dh-$gid.otf2ttf" \
       "subsetted/CJK-$gid.ttf" "tools/otf2ttf.py"; then
    echo "  [$gid] skip (指纹命中, 命中缓存)"
    return 0
  fi
  t0=$(date +%s)
  "$PYTHON_BIN" tools/otf2ttf.py "subsetted/CJK-$gid.ttf" -o "$out" --overwrite
  STEP_MARK "converted/.dh-$gid.otf2ttf" "subsetted/CJK-$gid.ttf" "tools/otf2ttf.py"
  report_time otf2ttf "$gid" "$(( $(date +%s) - t0 ))"
}

# ---------- 阶段 3/6: CJK 步进吸附 1200u + 墨迹水平居中 (按 gid 去重) ----------
stage_scale() {
  local gid="$1" t0
  local out="converted/CJK-$gid.ttf"
  if STEP_UP2DATE "$out" "converted/.dh-$gid.scale" \
       "converted/CJK-$gid.pre.ttf" "tools/scale_cjk.py"; then
    echo "  [$gid] skip (指纹命中, 命中缓存)"
    return 0
  fi
  t0=$(date +%s)
  cp -f "converted/CJK-$gid.pre.ttf" "$out"
  "$PYTHON_BIN" tools/scale_cjk.py "$out"
  STEP_MARK "converted/.dh-$gid.scale" "converted/CJK-$gid.pre.ttf" "tools/scale_cjk.py"
  report_time scale "$gid" "$(( $(date +%s) - t0 ))"
}

# ---------- 阶段 4/6: 拼合 (每字重; 第一个字体优先, Merger API) ----------
stage_merge() {
  local W="$1" t0 gid
  gid="${GID_OF[$W]}"
  if [ -z "$gid" ]; then echo "ERROR: 分组映射缺少字重 '$W' (GID_OF)" >&2; return 1; fi
  local out="output/.merged-$W.ttf"
  if STEP_UP2DATE "$out" "output/.dh-$W.merge" \
       "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" "tools/merge_fonts.py"; then
    echo "  [$W] skip (指纹命中, 命中缓存)"
    return 0
  fi
  t0=$(date +%s)
  "$PYTHON_BIN" tools/merge_fonts.py -o "$out" "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf"
  STEP_MARK "output/.dh-$W.merge" "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" "tools/merge_fonts.py"
  report_time merge "$W" "$(( $(date +%s) - t0 ))"
}

# ---------- 阶段 5/6: 改名+度量锁定 / woff2 (每字重) ----------
stage_rename() {
  local W="$1" t0
  local out="output/JetHanMono-$W.ttf"
  if STEP_UP2DATE "$out" "output/.dh-$W.rename" \
       "output/.merged-$W.ttf" "tools/rename.py"; then
    echo "  [$W] rename skip (指纹命中, 命中缓存)"
  else
    t0=$(date +%s)
    cp -f "output/.merged-$W.ttf" "$out"
    "$PYTHON_BIN" tools/rename.py "$out"
    STEP_MARK "output/.dh-$W.rename" "output/.merged-$W.ttf" "tools/rename.py"
    report_time rename "$W" "$(( $(date +%s) - t0 ))"
  fi
  if [ "$SKIP_WOFF2" = "1" ]; then
    echo "  [$W] woff2 跳过 (SKIP_WOFF2=1)"
    return 0
  fi
  local wout="output/JetHanMono-$W.woff2"
  if STEP_UP2DATE "$wout" "output/.dh-$W.woff2" \
       "$out" "tools/export_woff2.py"; then
    echo "  [$W] woff2 skip (指纹命中, 命中缓存)"
  else
    t0=$(date +%s)
    "$PYTHON_BIN" tools/export_woff2.py "$out"
    STEP_MARK "output/.dh-$W.woff2" "$out" "tools/export_woff2.py"
    report_time woff2 "$W" "$(( $(date +%s) - t0 ))"
  fi
}

# ---------- 阶段 6/6: 校验 (静态度量 + HarfBuzz shaping; 每字重) ----------
stage_verify() {
  local W="$1" t0 gid
  gid="${GID_OF[$W]}"
  if [ -z "$gid" ]; then echo "ERROR: 分组映射缺少字重 '$W' (GID_OF)" >&2; return 1; fi
  local vd="output/.dh-$W.verified"
  if STEP_UP2DATE "$vd" "$vd" \
       "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" \
       "output/JetHanMono-$W.ttf" "tools/verify.py" "tools/shape_test.py" \
       "tools/invariant_test.py"; then
    echo "  [$W] skip (产物指纹未变, 校验结论沿用)"
    return 0
  fi
  t0=$(date +%s)
  "$PYTHON_BIN" tools/verify.py "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" "output/JetHanMono-$W.ttf"
  "$PYTHON_BIN" tools/shape_test.py "downloads/JetBrainsMono-$W.ttf" "output/JetHanMono-$W.ttf"
  "$PYTHON_BIN" tools/invariant_test.py "downloads/JetBrainsMono-$W.ttf" "output/JetHanMono-$W.ttf"
  STEP_MARK "$vd" "downloads/JetBrainsMono-$W.ttf" "converted/CJK-$gid.ttf" \
    "output/JetHanMono-$W.ttf" "tools/verify.py" "tools/shape_test.py" \
    "tools/invariant_test.py"
  report_time verify "$W" "$(( $(date +%s) - t0 ))"
}

echo ""
echo "== 1/6 子集化 CJK (仅保留 JetBrains 未覆盖的码位; 按 gid 去重) =="
s0=$(date +%s); map_run stage_subset "${GIDS[@]}"
echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"

echo ""
echo "== 2/6 CFF -> TrueType 轮廓转换 (cu2qu, 输出 .pre.ttf 供 scale 增量) =="
s0=$(date +%s); map_run stage_otf2ttf "${GIDS[@]}"
echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"

echo ""
echo "== 3/6 CJK 步进吸附 1200u + 墨迹水平居中 (不缩放轮廓; 1000u->1200u = 2 x 拉丁 600u) =="
s0=$(date +%s); map_run stage_scale "${GIDS[@]}"
echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"

echo ""
echo "== 4/6 拼合 (第一个字体优先, Merger API; 输出 .merged-* 供 rename 增量) =="
s0=$(date +%s); map_run stage_merge "${JB_WEIGHTS[@]}"
echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"

echo ""
echo "== 5/6 重命名+度量锁定 / woff2 / OFL (均支持指纹跳过) =="
s0=$(date +%s); map_run stage_rename "${JB_WEIGHTS[@]}"
echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"
# OFL 许可证 (依赖 JetBrains OFL 原文 + rename.py)
if STEP_UP2DATE "output/JetHanMono-OFL.txt" "output/.dh-ofl" \
     "downloads/JetBrainsMono-OFL.txt" "tools/rename.py"; then
  echo "  [OFL] skip (输入指纹未变, 命中缓存)"
else
  echo "  [OFL] run"
  "$PYTHON_BIN" tools/rename.py --license-only output
  STEP_MARK "output/.dh-ofl" "downloads/JetBrainsMono-OFL.txt" "tools/rename.py"
fi

echo ""
echo "== 6/6 校验 (静态度量 + HarfBuzz shaping + JBM 不变量) =="
if [ "$SKIP_VERIFY" = "1" ]; then
  echo "  [verify] 跳过 (SKIP_VERIFY=1; CI 由独立 test job 执行)"
else
  s0=$(date +%s); map_run stage_verify "${JB_WEIGHTS[@]}"
  echo "  [阶段墙钟 $(fmt_dur "$(( $(date +%s) - s0 ))")]"
fi

print_summary
echo ""
echo "完成! 产物在 output/, 复制到 web:"
echo "  cp output/JetHanMono-*.ttf output/JetHanMono-*.woff2 output/JetHanMono-OFL.txt ../public/fonts/"
echo "总耗时: $(fmt_dur "$(( $(date +%s) - T_TOTAL0 ))")"
