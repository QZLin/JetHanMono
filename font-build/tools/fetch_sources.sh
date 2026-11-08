#!/usr/bin/env bash
# 下载上游字体源文件到 downloads/（GitHub Actions / 本地均可复用）
#
# 版本可用环境变量覆盖:
#   JB_VERSION  JetBrains Mono 发布 tag（不带 v 前缀），默认 2.304
#   NOTO_TAG    notofonts/noto-cjk 的发布 tag，默认 Sans2.004
#               (Mono 字体随 Sans 发布分发, SC 包为 13_NotoSansMonoCJKsc.zip)
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

# 所有 curl 限时 90s + 重试, 避免网络挂起拖死 CI
C="curl -fsSL --retry 3 --connect-timeout 15 --max-time 90"

if big_enough JetBrainsMono-Regular.ttf 100000 && big_enough JetBrainsMono-Bold.ttf 100000; then
  echo "== JetBrains Mono v${JB_VERSION}: 已存在, 跳过下载 =="
else
  echo "== JetBrains Mono v${JB_VERSION} =="
  $C -o jb.zip \
    "https://github.com/JetBrains/JetBrainsMono/releases/download/v${JB_VERSION}/JetBrainsMono-${JB_VERSION}.zip"
  # 通配任意内部目录, 只取两个静态 ttf (可变字体/woff2 同名文件不存在冲突)
  extract jb.zip '*JetBrainsMono-Regular.ttf' '*JetBrainsMono-Bold.ttf'
  rm -f jb.zip
fi

# rename.py 拼合许可证文件时需要 JetBrains 的 OFL 原文
if [ ! -s JetBrainsMono-OFL.txt ]; then
  $C -o JetBrainsMono-OFL.txt \
    "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v${JB_VERSION}/OFL.txt"
fi

if big_enough NotoSansMonoCJKsc-Regular.otf 1048576 && big_enough NotoSansMonoCJKsc-Bold.otf 1048576; then
  echo "== Noto Sans Mono CJK SC (${NOTO_TAG}): 已存在, 跳过下载 =="
else
  echo "== Noto Sans Mono CJK SC (${NOTO_TAG}) =="
  $C -o noto-sc.zip \
    "https://github.com/notofonts/noto-cjk/releases/download/${NOTO_TAG}/13_NotoSansMonoCJKsc.zip"
  extract noto-sc.zip '*NotoSansMonoCJKsc-Regular.otf' '*NotoSansMonoCJKsc-Bold.otf'
  rm -f noto-sc.zip
fi

# Adobe 思源许可证存档 (RFN 'Source' 依据, 供合规审查; 失败不阻断构建)
if [ ! -s SourceHanMono-LICENSE.md ]; then
  $C -o SourceHanMono-LICENSE.md \
    "https://raw.githubusercontent.com/adobe-fonts/source-han-mono/master/LICENSE.md" || true
fi

echo "== downloads/ 现状 =="
ls -la
