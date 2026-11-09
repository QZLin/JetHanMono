#!/usr/bin/env bash
# 下载上游字体源文件到 downloads/（GitHub Actions / 本地均可复用）
#
# 版本可用环境变量覆盖:
#   JB_VERSION  JetBrains Mono 发布 tag（不带 v 前缀），默认 2.304
#   NOTO_TAG    notofonts/noto-cjk 的发布 tag，默认 Sans2.004
#               (Mono 字体随 Sans 发布分发, SC 包为 13_NotoSansMonoCJKsc.zip)
#   FETCH_MAX_TIME  单次 curl 传输超时秒数，默认 90 (CI 友好)；弱网本地可调大
#
# 幂等: 目标文件已存在且足够大时跳过对应下载段。
# Windows (Git Bash) 兼容: 首行 CRLF 自愈守卫 + 无 unzip 时用 python zipfile 兜底。
# 注意: Adobe 思源官方 OFL 保留字体名 'Source'，本合并字体因此命名为 JetHan Mono。
if grep -q "$(printf '\r')" "$0" 2>/dev/null; then echo "[fetch_sources.sh] 检测到 CRLF 行尾, 转换为 LF 并重启..."; tr -d '\r' <"$0" >"$0.tmp" && mv "$0.tmp" "$0" && exec bash "$0" "$@"; fi # CRLF guard: 必须保持单行

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRIPT_DIR/../downloads"
cd "$SCRIPT_DIR/../downloads"

JB_VERSION="${JB_VERSION:-2.304}"
NOTO_TAG="${NOTO_TAG:-Sans2.004}"

# 寻找 python (仅用于无 unzip 环境的解压兜底, 只需标准库)
PYBIN="${PYTHON_BIN:-}"
if [ -z "$PYBIN" ]; then
  for C in python3 python py; do
    if command -v "$C" >/dev/null 2>&1; then PYBIN="$C"; break; fi
  done
fi

# 文件存在且大于 min_bytes 视为有效 (JetBrains ttf 约 270KB, Noto otf 约 16MB)
big_enough() { [ -s "$1" ] && [ "$(stat -c%s "$1")" -gt "$2" ]; }

# 解压: 优先 unzip; Git Bash 等无 unzip 环境回退 python zipfile (等价 unzip -o -j)
extract() { # $1=zip 其余=成员通配模式
  local zip="$1"; shift
  if command -v unzip >/dev/null 2>&1; then
    unzip -o -j "$zip" "$@"
  elif [ -n "$PYBIN" ]; then
    echo "(unzip 不可用, 使用 python zipfile 兜底)"
    "$PYBIN" "$SCRIPT_DIR/tools/unzip_fallback.py" "$zip" "$@"
  else
    echo "ERROR: 解压 $zip 需要 unzip 或 python 其中之一" >&2
    return 1
  fi
}

# 所有 curl 限时(默认 90s, 可用 FETCH_MAX_TIME 覆盖) + 重试 + 断点续传, 避免网络挂起拖死 CI
FETCH_MAX_TIME="${FETCH_MAX_TIME:-90}"
C="curl -fsSL --retry 3 --retry-delay 2 -C - --connect-timeout 15 --max-time ${FETCH_MAX_TIME}"

# 大文件下载: 外层断点续传重试环 (curl 内层 --retry 用尽后 -C - 从断点继续,
# 弱网/SSL 中断下每次重试都有净进展, 不再让单次失败拖死整个脚本)
dl() { # dl <url> <out>
  local url="$1" out="$2" n=0 max="${DL_RETRIES:-30}"
  while true; do
    if $C -o "$out" "$url"; then return 0; fi
    n=$((n+1))
    if [ "$n" -ge "$max" ]; then echo "ERROR: 下载失败 ${n} 次: $url" >&2; return 1; fi
    echo "[dl] 第 ${n}/${max} 次失败, 5s 后从断点重试: $out ($(stat -c%s "$out" 2>/dev/null || echo 0) bytes)"
    sleep 5
  done
}

# JetBrains Mono 全部 8 个罗马字重 (无 Italic: Noto Sans Mono CJK 无斜体, 拼合斜体仅拉丁无意义)
if big_enough JetBrainsMono-Thin.ttf 100000 && big_enough JetBrainsMono-ExtraBold.ttf 100000; then
  echo "== JetBrains Mono v${JB_VERSION}: 已存在, 跳过下载 =="
else
  echo "== JetBrains Mono v${JB_VERSION} (8 个字重) =="
  dl "https://github.com/JetBrains/JetBrainsMono/releases/download/v${JB_VERSION}/JetBrainsMono-${JB_VERSION}.zip" jb.zip
  # 通配任意内部目录, 只取静态 ttf (可变字体/woff2 同名文件不存在冲突)
  extract jb.zip \
    '*JetBrainsMono-Thin.ttf' \
    '*JetBrainsMono-ExtraLight.ttf' \
    '*JetBrainsMono-Light.ttf' \
    '*JetBrainsMono-Regular.ttf' \
    '*JetBrainsMono-Medium.ttf' \
    '*JetBrainsMono-SemiBold.ttf' \
    '*JetBrainsMono-Bold.ttf' \
    '*JetBrainsMono-ExtraBold.ttf'
  rm -f jb.zip
fi

# rename.py 拼合许可证文件时需要 JetBrains 的 OFL 原文
if [ ! -s JetBrainsMono-OFL.txt ]; then
  dl "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v${JB_VERSION}/OFL.txt" JetBrainsMono-OFL.txt
fi

# Noto Sans Mono CJK SC 只有 Regular/Bold 两个罗马字重 (思源等宽原版即如此):
# 其余字重的 CJK 字形来自 Noto Sans CJK SC (Source Han Sans 同源,
# CJK 字形设计与等宽版一致, 全宽步进同为 1000u) - 见下方 sans-sc 段
if big_enough NotoSansMonoCJKsc-Regular.otf 1048576 && big_enough NotoSansMonoCJKsc-Bold.otf 1048576; then
  echo "== Noto Sans Mono CJK SC (${NOTO_TAG}): 已存在, 跳过下载 =="
else
  echo "== Noto Sans Mono CJK SC (${NOTO_TAG}) (Regular/Bold) =="
  dl "https://github.com/notofonts/noto-cjk/releases/download/${NOTO_TAG}/13_NotoSansMonoCJKsc.zip" noto-sc.zip
  extract noto-sc.zip \
    '*NotoSansMonoCJKsc-Regular.otf' \
    '*NotoSansMonoCJKsc-Bold.otf'
  rm -f noto-sc.zip
fi

# Noto Sans CJK SC (7 档字重: Thin/DemiLight/Light/Regular/Medium/Bold/Black)
# 为其余 6 个字重 (Thin/ExtraLight/Light/Medium/SemiBold/ExtraBold) 提供 CJK 侧字形
if big_enough NotoSansCJKsc-Thin.otf 1048576 && big_enough NotoSansCJKsc-Black.otf 1048576; then
  echo "== Noto Sans CJK SC (${NOTO_TAG}): 已存在, 跳过下载 =="
else
  echo "== Noto Sans CJK SC (${NOTO_TAG}) (7 个字重) =="
  dl "https://github.com/notofonts/noto-cjk/releases/download/${NOTO_TAG}/08_NotoSansCJKsc.zip" sans-sc.zip
  extract sans-sc.zip \
    '*NotoSansCJKsc-Thin.otf' \
    '*NotoSansCJKsc-DemiLight.otf' \
    '*NotoSansCJKsc-Light.otf' \
    '*NotoSansCJKsc-Regular.otf' \
    '*NotoSansCJKsc-Medium.otf' \
    '*NotoSansCJKsc-Bold.otf' \
    '*NotoSansCJKsc-Black.otf'
  rm -f sans-sc.zip
fi

# Adobe 思源许可证存档 (RFN 'Source' 依据, 供合规审查; 失败不阻断构建)
if [ ! -s SourceHanMono-LICENSE.md ]; then
  dl "https://raw.githubusercontent.com/adobe-fonts/source-han-mono/master/LICENSE.md" SourceHanMono-LICENSE.md || true
fi

echo "== downloads/ 现状 =="
ls -la
