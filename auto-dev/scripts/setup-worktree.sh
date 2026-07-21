#!/bin/bash
# ============================================================
# setup-worktree.sh - Git Worktree 管理脚本
# 用法:
#   ./setup-worktree.sh create  <产品> <需求号> [WORK_DIR] [仓库列表] [--json] [--retry-failed]
#   ./setup-worktree.sh remove  <产品> <需求号> [WORK_DIR]
#   ./setup-worktree.sh list    <产品> [WORK_DIR]
#   ./setup-worktree.sh check   <产品> <需求号> [WORK_DIR]
# ============================================================

set -e

ACTION="${1:?用法: $0 create|remove|list|check <产品> [需求号] [WORK_DIR] [--json]}"

# 解析 --json / --retry-failed 标志（可出现在任意位置）
JSON_OUTPUT=false
RETRY_FAILED=false
_args=()
for arg in "$@"; do
    case "$arg" in
        --json) JSON_OUTPUT=true ;;
        --retry-failed) RETRY_FAILED=true ;;
        *) _args+=("$arg") ;;
    esac
done
set -- "${_args[@]}"

PRODUCT="${2:-}"
TASK_ID="${3:-}"
WORK_DIR="${4:-$(pwd)}"
REPOS="${5:-all}"          # 指定仓库，逗号分隔，默认 all

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PRODUCTS_YAML="$SKILL_DIR/templates/products.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $*"; }

# JSON 输出辅助函数
json_escape() {
    local str="$1"
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    str="${str//$'\n'/\\n}"
    str="${str//$'\t'/\\t}"
    echo "$str"
}

json_output() {
    local status="$1"
    local worktree_base="$2"
    local repos_json="$3"
    local created="$4"
    local skipped="$5"
    local failed="$6"

    cat <<JSONEOF
{
  "status": "$status",
  "worktree_base": "$(json_escape "$worktree_base")",
  "repos": [$repos_json],
  "summary": {"created": $created, "skipped": $skipped, "failed": $failed}
}
JSONEOF
}

# Git 命令辅助函数: JSON 模式下将 stdout 重定向到 stderr，避免污染 JSON 输出
run_git() {
    if [ "$JSON_OUTPUT" = true ]; then
        "$@" >&2
    else
        "$@"
    fi
}

# 计算 worktree 工作目录: {WORK_DIR父目录}/.worktrees/{task_id}-{主目录名}
compute_work_dir() {
    local work_dir="$1"
    local task_id="$2"
    # 统一使用绝对路径
    local abs_work_dir
    if [ -d "$work_dir" ]; then
        abs_work_dir=$(cd "$work_dir" && pwd)
    else
        abs_work_dir="$(cd "$(dirname "$work_dir")" 2>/dev/null && pwd)/$(basename "$work_dir")"
    fi
    local parent_path
    parent_path=$(dirname "$abs_work_dir")
    local dir_name
    dir_name=$(basename "$abs_work_dir")
    echo "${parent_path}/.worktrees/${task_id}-${dir_name}"
}

# 从 products.yaml 获取仓库列表
get_repos() {
    python "$SKILL_DIR/scripts/parse-products.py" "$1" "name,branch,skill"
}

# 创建 worktree
do_create() {
    local product="$PRODUCT"
    local task_id="$TASK_ID"
    local repos_filter="$REPOS"

    if [ -z "$product" ] || [ -z "$task_id" ]; then
        log_error "create 需要: <产品> <需求号>"
        if [ "$JSON_OUTPUT" = true ]; then
            json_output "failed" "" "" 0 0 0
        fi
        exit 1
    fi

    # JSON 模式: stdout 保留给 JSON，log 输出重定向到 stderr
    if [ "$JSON_OUTPUT" = true ]; then
        exec 3>&1
        log_info()  { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
        log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
        log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
        log_step()  { echo -e "${BLUE}[STEP]${NC} $*" >&2; }
    fi

    log_info "创建 worktree: $product / $task_id"
    log_info "WORK_DIR: $WORK_DIR"
    [ "$JSON_OUTPUT" != true ] && echo ""

    # 初始化 DOCS_DIR（用于记录失败仓库）
    local WT_BASE_PRE
    WT_BASE_PRE=$(compute_work_dir "$WORK_DIR" "$task_id")
    local DOCS_DIR
    DOCS_DIR=$(dirname "$WT_BASE_PRE")

    # 非 retry 模式：清除旧的失败记录
    if [ "$RETRY_FAILED" != true ]; then
        rm -f "${DOCS_DIR}/.worktree-failed-repos"
    fi

    # 获取仓库列表
    local ALL_REPOS
    ALL_REPOS=$(get_repos "$product")

    if [ -z "$ALL_REPOS" ]; then
        log_error "未找到产品 '$product' 的仓库配置"
        if [ "$JSON_OUTPUT" = true ]; then
            json_output "failed" "" "" 0 0 0
        fi
        exit 1
    fi

    local SUCCESS=0 FAIL=0 CREATED=0
    local SKIPPED=0
    local REPOS_JSON=""
    local WT_BASE=""

    while IFS='|' read -r repo_name repo_branch repo_skill; do
        # --retry-failed: 只处理上次失败的仓库
        if [ "$RETRY_FAILED" = true ]; then
            local failed_list_file="${DOCS_DIR}/.worktree-failed-repos"
            if [ -f "$failed_list_file" ]; then
                local in_failed_list=false
                while IFS= read -r failed_repo; do
                    if [ "$failed_repo" = "$repo_name" ]; then
                        in_failed_list=true
                        break
                    fi
                done < "$failed_list_file"
                if [ "$in_failed_list" = false ]; then
                    continue  # skip non-failed repos
                fi
            else
                continue  # no failed list file, skip all repos
            fi
        fi

        # 过滤仓库
        if [ "$repos_filter" != "all" ]; then
            local match=0
            IFS=',' read -ra FILTER_ARR <<< "$repos_filter"
            for f in "${FILTER_ARR[@]}"; do
                if [ "$f" = "$repo_name" ]; then match=1; break; fi
            done
            if [ "$match" -eq 0 ]; then
                log_warn "跳过: $repo_name (不在指定列表中)"
                SKIPPED=$((SKIPPED + 1))
                [ -n "$REPOS_JSON" ] && REPOS_JSON="$REPOS_JSON,"
                REPOS_JSON="$REPOS_JSON{\"name\":\"$(json_escape "$repo_name")\",\"status\":\"skipped\",\"reason\":\"filtered\"}"
                continue
            fi
        fi

        local source_repo="$WORK_DIR/$repo_name"
        local work_dir
        work_dir=$(compute_work_dir "$WORK_DIR" "$task_id")
        [ -z "$WT_BASE" ] && WT_BASE="$work_dir"

        local worktree_path="$work_dir/$repo_name"
        local feature_branch="feature/$task_id"

        if [ ! -d "$source_repo" ]; then
            log_error "源仓库不存在: $source_repo (请在产品目录下运行 auto-dev)"
            FAIL=$((FAIL + 1))
            [ -n "$REPOS_JSON" ] && REPOS_JSON="$REPOS_JSON,"
            REPOS_JSON="$REPOS_JSON{\"name\":\"$(json_escape "$repo_name")\",\"status\":\"error\",\"reason\":\"source_not_found\",\"path\":\"$(json_escape "$worktree_path")\",\"branch\":\"$feature_branch\"}"
            continue
        fi

        # 检查 worktree 是否已存在
        if [ -d "$worktree_path" ]; then
            log_warn "已存在: $worktree_path (跳过)"
            SUCCESS=$((SUCCESS + 1))
            SKIPPED=$((SKIPPED + 1))
            [ -n "$REPOS_JSON" ] && REPOS_JSON="$REPOS_JSON,"
            REPOS_JSON="$REPOS_JSON{\"name\":\"$(json_escape "$repo_name")\",\"status\":\"skipped\",\"reason\":\"exists\",\"path\":\"$(json_escape "$worktree_path")\",\"branch\":\"$feature_branch\"}"
            continue
        fi

        log_step "创建 worktree: $repo_name"
        log_info "  源仓库: $source_repo"
        log_info "  分支: $feature_branch (base: $repo_branch)"
        log_info "  目标: $worktree_path"

        mkdir -p "$work_dir"
        cd "$source_repo"

        # 确保 base 分支是最新的
        git fetch origin >/dev/null 2>&1 || true

        # 创建 feature 分支
        if run_git git show-ref --verify --quiet "refs/heads/$feature_branch"; then
            log_info "  本地分支已存在: $feature_branch (直接使用)"
        elif run_git git show-ref --verify --quiet "refs/remotes/origin/$feature_branch"; then
            run_git git branch --track "$feature_branch" "origin/$feature_branch"
            log_info "  从远端创建本地分支: $feature_branch (跟踪 origin/$feature_branch)"
        else
            run_git git branch --no-track "$feature_branch" "origin/$repo_branch" 2>/dev/null || \
            run_git git branch --no-track "$feature_branch" "$repo_branch"
            log_info "  分支已创建: $feature_branch (base: $repo_branch)"
        fi

        # 创建 worktree
        if run_git git worktree add "$worktree_path" "$feature_branch"; then
            log_info "  worktree 创建成功"
            CREATED=$((CREATED + 1))
            SUCCESS=$((SUCCESS + 1))
            [ -n "$REPOS_JSON" ] && REPOS_JSON="$REPOS_JSON,"
            REPOS_JSON="$REPOS_JSON{\"name\":\"$(json_escape "$repo_name")\",\"status\":\"created\",\"path\":\"$(json_escape "$worktree_path")\",\"branch\":\"$feature_branch\"}"
        else
            log_error "  worktree 创建失败"
            FAIL=$((FAIL + 1))
            [ -n "$REPOS_JSON" ] && REPOS_JSON="$REPOS_JSON,"
            REPOS_JSON="$REPOS_JSON{\"name\":\"$(json_escape "$repo_name")\",\"status\":\"failed\",\"path\":\"$(json_escape "$worktree_path")\",\"branch\":\"$feature_branch\"}"
            # 记录失败仓库供 --retry-failed 使用
            if [ -n "${DOCS_DIR:-}" ]; then
                echo "$repo_name" >> "${DOCS_DIR}/.worktree-failed-repos"
            fi
        fi
        [ "$JSON_OUTPUT" != true ] && echo ""
    done <<< "$ALL_REPOS"

    # 输出摘要
    if [ "$JSON_OUTPUT" = true ]; then
        # 判断整体状态
        local overall_status="success"
        [ "$FAIL" -gt 0 ] && [ "$CREATED" -gt 0 ] && overall_status="partial"
        [ "$FAIL" -gt 0 ] && [ "$CREATED" -eq 0 ] && overall_status="failed"
        [ "$SUCCESS" -eq 0 ] && [ "$FAIL" -eq 0 ] && overall_status="failed"

        json_output "$overall_status" "$WT_BASE" "$REPOS_JSON" "$CREATED" "$SKIPPED" "$FAIL"
        exec 1>&3
        exec 3>&-
    else
        echo "===================================="
        log_info "Worktree 创建完成"
        echo "  产品: $product"
        echo "  需求号: $task_id"
        echo "  成功: $SUCCESS (新建: $CREATED)"
        echo "  失败: $FAIL"
        echo "  工作目录: $WT_BASE"
        echo "===================================="
    fi
}

# 删除 worktree
do_remove() {
    local product="$PRODUCT"
    local task_id="$TASK_ID"

    log_info "清理 worktree: $product / $task_id"

    # 获取仓库列表
    local ALL_REPOS
    ALL_REPOS=$(get_repos "$product")

    if [ -z "$ALL_REPOS" ]; then
        log_error "未找到产品 '$product' 的仓库配置"
        exit 1
    fi

    local -A WORK_DIRS

    while IFS='|' read -r repo_name repo_branch repo_skill; do
        local source_repo="$WORK_DIR/$repo_name"
        local work_dir
        work_dir=$(compute_work_dir "$WORK_DIR" "$task_id")

        local wt_dir="$work_dir/$repo_name"
        if [ ! -d "$wt_dir" ]; then
            log_warn "  跳过: $repo_name (worktree 不存在)"
            continue
        fi

        WORK_DIRS["$work_dir"]=1

        local running_pids
        if command -v lsof &>/dev/null; then
            running_pids=$(lsof +D "$wt_dir" 2>/dev/null | grep -v "^COMMAND" | awk '{print $2}' | sort -u)
        else
            running_pids=$(powershell -Command "Get-Process git -ErrorAction SilentlyContinue | Where-Object { \$_.Path -like \"$(cygpath -w "$wt_dir" 2>/dev/null || echo "$wt_dir")*\" } | Select-Object -ExpandProperty Id" 2>/dev/null | tr -d '\r')
        fi
        if [ -n "$running_pids" ]; then
            log_error "目录下有活跃进程，拒绝删除（PID: $running_pids）"
            log_error "请先停止相关进程再执行 remove"
            exit 1
        fi

        log_info "  清理: $repo_name"
        if [ -d "$source_repo" ]; then
            cd "$source_repo"
            git worktree remove "$wt_dir" --force 2>&1 || log_warn "  worktree remove 失败"
            git branch -D "feature/$task_id" 2>/dev/null || true
        fi
    done <<< "$ALL_REPOS"

    # 删除工作目录
    for wd in "${!WORK_DIRS[@]}"; do
        if [ -d "$wd" ]; then
            rm -rf "$wd"
            log_info "已删除: $wd"
        fi
    done
}

# 检查 worktree 完整性
do_check() {
    local product="$PRODUCT"
    local task_id="$TASK_ID"

    if [ -z "$product" ] || [ -z "$task_id" ]; then
        log_error "check 需要: <产品> <需求号>"
        exit 1
    fi

    local ALL_REPOS
    ALL_REPOS=$(get_repos "$product")

    if [ -z "$ALL_REPOS" ]; then
        log_error "未找到产品 '$product' 的仓库配置"
        exit 1
    fi

    local work_dir
    work_dir=$(compute_work_dir "$WORK_DIR" "$task_id")
    local total=0 valid=0 missing=0 broken=0

    while IFS='|' read -r repo_name repo_branch repo_skill; do
        total=$((total + 1))
        local wt_path="$work_dir/$repo_name"
        local feature_branch="feature/$task_id"

        if [ ! -d "$wt_path" ]; then
            log_warn "$repo_name: worktree 目录不存在 ($wt_path)"
            missing=$((missing + 1))
            continue
        fi

        # 检查是否为有效 git 仓库
        if ! (cd "$wt_path" && git rev-parse --git-dir >/dev/null 2>&1); then
            log_error "$repo_name: 不是有效的 git 仓库"
            broken=$((broken + 1))
            continue
        fi

        # 检查分支
        local current_branch
        current_branch=$(cd "$wt_path" && git branch --show-current 2>/dev/null) || current_branch=""
        if [ "$current_branch" != "$feature_branch" ]; then
            log_error "$repo_name: 分支不匹配 (期望: $feature_branch, 实际: $current_branch)"
            broken=$((broken + 1))
            continue
        fi

        valid=$((valid + 1))
        log_info "$repo_name: ✓ ($current_branch)"
    done <<< "$ALL_REPOS"

    echo ""
    log_info "检查结果: $valid/$total 有效, $missing 缺失, $broken 损坏"

    # 退出码
    if [ "$total" -eq 0 ] || [ "$missing" -eq "$total" ]; then
        exit 2  # worktree 不存在
    elif [ "$missing" -gt 0 ] || [ "$broken" -gt 0 ]; then
        exit 1  # 部分损坏
    else
        exit 0  # 完整可用
    fi
}

# 列出 worktree
do_list() {
    local product="$PRODUCT"

    # 获取仓库列表
    local ALL_REPOS
    ALL_REPOS=$(get_repos "$product")

    if [ -z "$ALL_REPOS" ]; then
        log_error "未找到产品 '$product' 的仓库配置"
        exit 1
    fi

    # 计算 worktree 基础路径
    local parent_path
    parent_path=$(dirname "$(cd "$WORK_DIR" && pwd)")
    local scan_dir="${parent_path}/.worktrees"
    local dir_name
    dir_name=$(basename "$(cd "$WORK_DIR" && pwd)")

    log_info "产品 '$product' 的 worktree 列表:"
    log_info "扫描目录: ${scan_dir}/*-${dir_name}"
    echo ""

    local found=0
    for task_dir in "${scan_dir}"/*-"${dir_name}"/; do
        [ -d "$task_dir" ] || continue
        local wt_dir_name
        wt_dir_name="$(basename "$task_dir")"
        # 从 {需求号}-{主目录名} 提取需求号
        local task_id="${wt_dir_name%%-*}"
        [[ "$task_id" =~ ^[0-9]+$ ]] || continue

        local repo_count
        repo_count=$(find "$task_dir" -maxdepth 1 -mindepth 1 -type d | wc -l)
        echo "  $task_id ($repo_count 个仓库)"

        for repo_dir in "$task_dir"/*/; do
            [ -d "$repo_dir" ] || continue
            local repo_name
            repo_name="$(basename "$repo_dir")"
            cd "$repo_dir"
            local branch
            branch="$(git branch --show-current 2>/dev/null || echo 'unknown')"
            local status
            status="$(git status --short 2>/dev/null | wc -l)"
            echo "    - $repo_name [$branch] ${status} changes"
        done
        echo ""
        found=1
    done

    if [ "$found" -eq 0 ]; then
        log_info "暂无 worktree"
    fi
}

case "$ACTION" in
    create) do_create ;;
    remove) do_remove ;;
    list)   do_list ;;
    check)  do_check ;;
    *)
        echo "用法: $0 create|remove|list|check <产品> [需求号] [WORK_DIR] [仓库列表]"
        echo ""
        echo "  create  <产品> <需求号> [WORK_DIR] [仓库]  - 创建 worktree"
        echo "  remove  <产品> <需求号> [WORK_DIR]         - 删除 worktree"
        echo "  list    <产品> [WORK_DIR]                  - 列出所有 worktree"
        echo "  check   <产品> <需求号> [WORK_DIR]         - 检查 worktree 完整性"
        echo ""
        echo "选项:"
        echo "  --json          JSON 格式输出 (create)"
        echo "  --retry-failed  只重试失败的仓库 (create)"
        echo ""
        echo "示例:"
        echo "  $0 create {产品名} 1506090"
        echo "  $0 create {产品名} 1506090 --json"
        echo "  $0 check  {产品名} 1506090"
        echo "  $0 remove {产品名} 1506090"
        echo "  $0 list   {产品名}"
        exit 1
        ;;
esac
