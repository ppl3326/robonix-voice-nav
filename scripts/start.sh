#!/usr/bin/env bash
set -euo pipefail
# 获取上一级目录（也就是项目根目录）
PKG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PKG_ROOT"
export PYTHONPATH="$(rbnx path robonix-api):$PKG_ROOT:$PKG_ROOT/rbnx-build/codegen/proto_gen:${PYTHONPATH:-}"
exec python3 scripts/main.py
