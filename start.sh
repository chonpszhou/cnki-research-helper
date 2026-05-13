#!/bin/bash
# =============================================================================
# CNKI Research Helper 一键启动脚本
# =============================================================================
# 启动顺序：Chrome Debug → CDP Proxy → CNKI API 服务
# 使用方法: ./start.sh [--port 8080]
# =============================================================================

set -e

API_PORT="${1:-8080}"
PROXY_PORT="3456"
CHROME_PORT="9222"
CHROME_PROFILE="$HOME/Library/Application Support/Google/Chrome-Debug-CNKI"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PDF_DIR="$HOME/Desktop/paper-ai/cnki_papers"

echo "╔══════════════════════════════════════════════╗"
echo "║   CNKI Research Helper — 一键启动            ║"
echo "╚══════════════════════════════════════════════╝"

# ─── 1. 启动 Chrome Debug ──────────────────────────────────────────────────
echo ""
echo "[1/3] 启动 Chrome Debug (端口 $CHROME_PORT)..."

if curl -s --max-time 2 "http://127.0.0.1:$CHROME_PORT/json/version" > /dev/null 2>&1; then
    echo "      ✅ Chrome Debug 已运行 (端口 $CHROME_PORT)"
else
    mkdir -p "$CHROME_PROFILE"
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        --remote-debugging-port="$CHROME_PORT" \
        --user-data-dir="$CHROME_PROFILE" \
        --no-first-run --no-default-browser-check \
        2>/dev/null &
    sleep 3
    if curl -s --max-time 3 "http://127.0.0.1:$CHROME_PORT/json/version" > /dev/null 2>&1; then
        echo "      ✅ Chrome Debug 启动成功"
    else
        echo "      ⚠️  Chrome Debug 启动异常，请手动检查"
    fi
fi

# ─── 2. 启动 CDP Proxy ───────────────────────────────────────────────────
echo ""
echo "[2/3] 启动 CDP Proxy (端口 $PROXY_PORT)..."

if curl -s --max-time 2 "http://127.0.0.1:$PROXY_PORT/health" > /dev/null 2>&1; then
    echo "      ✅ CDP Proxy 已运行 (端口 $PROXY_PORT)"
else
    # 杀掉旧进程
    pkill -f "cdp-proxy.mjs" 2>/dev/null || true
    sleep 1
    node "$SCRIPT_DIR/scripts/cdp-proxy.mjs" "$PROXY_PORT" "$CHROME_PORT" &
    sleep 2
    if curl -s --max-time 3 "http://127.0.0.1:$PROXY_PORT/health" > /dev/null 2>&1; then
        echo "      ✅ CDP Proxy 启动成功"
    else
        echo "      ⚠️  CDP Proxy 启动异常"
    fi
fi

# ─── 3. 启动 CNKI API 服务 ────────────────────────────────────────────────
echo ""
echo "[3/3] 启动 CNKI API 服务 (端口 $API_PORT)..."

# 创建 PDF 保存目录
mkdir -p "$PDF_DIR"

if curl -s --max-time 2 "http://127.0.0.1:$API_PORT/health" > /dev/null 2>&1; then
    echo "      ✅ CNKI API 已运行 (端口 $API_PORT)"
else
    # 杀掉旧进程
    pkill -f "cnki_api.py" 2>/dev/null || true
    sleep 1
    CNKI_PDF_DIR="$PDF_DIR" python3 "$SCRIPT_DIR/scripts/cnki_api.py" --port "$API_PORT" &
    sleep 3
    if curl -s --max-time 3 "http://127.0.0.1:$API_PORT/health" > /dev/null 2>&1; then
        echo "      ✅ CNKI API 启动成功"
    else
        echo "      ⚠️  CNKI API 启动异常，请检查: python3 cnki_api.py --port $API_PORT"
    fi
fi

# ─── 4. 提示手动登录 ─────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  🔑 首次使用需要手动登录 CNKI（一次性操作）："
echo ""
echo "  1. Chrome 会自动打开一个新窗口"
echo "  2. 访问 https://login.cnki.net/ 并登录"
echo "  3. 保持该标签页打开，不要关闭"
echo ""
echo "  以后使用时只需运行本脚本，无需重复登录"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  📡 API 地址: http://127.0.0.1:$API_PORT"
echo "  📁 PDF 目录: $PDF_DIR"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo ""

# 打开 Chrome 登录页面（如果还没登录过）
open "https://login.cnki.net/"

# 保持运行
wait
