#!/bin/bash
# ============================================================
# detect-local-repos.sh - 扫描当前目录下的 git 仓库
# 用法: ./detect-local-repos.sh [扫描目录]
# 输出: JSON 数组，每项包含 name, url, branch, tfs_project
# ============================================================

SCAN_DIR="${1:-.}"

# 找出所有 git 仓库（深度限制 2 层）
REPOS=()
while IFS= read -r -d '' gitdir; do
    REPOS+=("$(dirname "$gitdir")")
done < <(find "$SCAN_DIR" -maxdepth 2 -mindepth 1 -name ".git" -type d -print0 2>/dev/null)

# 没找到仓库
if [ ${#REPOS[@]} -eq 0 ]; then
    echo "[]"
    exit 0
fi

# 收集信息
echo "["
FIRST=1
for repo_path in "${REPOS[@]}"; do
    # 获取 remote URL
    url=$(git -C "$repo_path" remote get-url origin 2>/dev/null || echo "")
    [ -z "$url" ] && continue

    # 只保留 TFS 仓库
    if [[ "$url" != *"/tfs/"*"/_git/"* ]]; then
        continue
    fi

    # 获取仓库名
    name=$(basename "$repo_path")

    # 获取当前分支
    branch=$(git -C "$repo_path" branch --show-current 2>/dev/null || echo "")

    # 转为绝对路径（使用 git -C 兼容 Windows）
    abs_path=$(cd "$repo_path" && pwd)

    # 从 URL 解析 tfs_project: /tfs/{collection}/{project}/_git/{repo}
    tfs_project=$(echo "$url" | sed -n 's|.*/tfs/\([^/]*\/[^/]*\)/_git/.*|\1|p')

    # 输出 JSON 对象
    [ $FIRST -eq 0 ] && echo ","
    FIRST=0
    printf '  {"name": "%s", "url": "%s", "branch": "%s", "tfs_project": "%s"}' \
        "$name" "$url" "$branch" "${tfs_project//\\/\\\\}"
done
echo ""
echo "]"
