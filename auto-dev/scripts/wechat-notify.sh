#!/bin/bash
# ============================================================
# wechat-notify.sh - 企业微信 Webhook 通知（shell 入口）
# 委托给 wechat-notify.py 执行
#
# 用法:
#   ./wechat-notify.sh <消息类型> <产品> <需求号> [标题] [扩展JSON文件]
# 消息类型: start | success | fail | progress | summary
# ============================================================

MSG_TYPE="${1:?用法: $0 start|success|fail|progress|summary <产品> <需求号> [标题] [扩展JSON文件]}"
PRODUCT="${2:-未知产品}"
TASK_ID="${3:-未知}"
TITLE="${4:-}"
EXT_FILE="${5:-}"

# 企业微信 Webhook URL
WECHAT_WEBHOOK="${WECHAT_WEBHOOK_URL:-}"

if [ -z "$WECHAT_WEBHOOK" ]; then
    ENV_FILE="$(cd "$(dirname "$0")" && pwd)/../config.env"
    if [ -f "$ENV_FILE" ]; then
        # 安全读取 config.env：仅提取 KEY=VALUE 行，跳过注释和 export 前缀
        while IFS='=' read -r key value; do
            key=$(echo "$key" | sed 's/^export //' | xargs)
            value=$(echo "$value" | xargs)
            case "$key" in
                ''|\#*) continue ;;
            esac
            if [ -z "${!key+x}" ]; then
                export "$key=$value"
            fi
        done < "$ENV_FILE"
    fi
    WECHAT_WEBHOOK="${WECHAT_WEBHOOK_URL:-}"
fi

if [ -z "$WECHAT_WEBHOOK" ]; then
    echo "[通知] 未配置企微Webhook，跳过通知"
    exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 跨平台 Python 检测：封装为函数，避免主流程重复判断
find_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" &>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PY=$(find_python)
if [ -z "$PY" ]; then
    echo "[通知] Python 不可用，跳过通知"
    exit 0
fi

"$PY" "$SCRIPT_DIR/wechat-notify.py" \
    "$MSG_TYPE" "$PRODUCT" "$TASK_ID" "$TITLE" "$TIMESTAMP" "$WECHAT_WEBHOOK" "$EXT_FILE"
