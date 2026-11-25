#!/usr/bin/env bash
set -euo pipefail
# 获取上一级目录（也就是项目根目录）
PKG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rbnx codegen -p "$PKG_ROOT" --mcp
echo "[voice_nav/build] done."
