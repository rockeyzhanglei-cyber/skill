#!/usr/bin/env python3
"""Check if auto-dev has new commits on remote origin/master."""

import json
import os
import subprocess
import sys
import time

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".update-check.json")
CACHE_TTL = 86400  # 1 day
AUTO_UPDATE_THRESHOLD = 5


def run_git(*args):
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )
    return result.stdout.strip(), result.returncode


def get_local_head():
    out, rc = run_git("rev-parse", "HEAD")
    return out if rc == 0 else None


def get_remote_head():
    out, rc = run_git("ls-remote", "origin", "refs/heads/master")
    if rc != 0 or not out:
        return None
    return out.split()[0]


def count_new_commits(local_head, remote_head):
    out, rc = run_git("rev-list", "--count", f"{local_head}..{remote_head}")
    return int(out) if rc == 0 else 0


def read_cache():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def write_cache(remote_head):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "remote_head": remote_head}, f)
    except Exception:
        pass


def main():
    local_head = get_local_head()
    if not local_head:
        return

    cache = read_cache()
    if cache and (time.time() - cache.get("ts", 0)) < CACHE_TTL:
        remote_head = cache.get("remote_head")
    else:
        remote_head = get_remote_head()
        if remote_head:
            write_cache(remote_head)

    if not remote_head or remote_head == local_head:
        return

    run_git("fetch", "origin", "master", "--quiet")
    new_count = count_new_commits("HEAD", "origin/master")

    if new_count > AUTO_UPDATE_THRESHOLD:
        print(f"⚠️⚠️⚠️ auto-dev 落后 {new_count} 个提交，正在自动更新...")
        _, rc = run_git("pull", "--ff-only")
        if rc == 0:
            print(f"✅ auto-dev 已自动更新到最新版本")
            write_cache(None)
        else:
            print(f"❌ auto-dev 自动更新失败，请手动运行 /win-skill-installer 更新")
    else:
        print(f"⚠️⚠️⚠️ auto-dev 有 {new_count} 个新提交可用。运行 /win-skill-installer 更新 auto-dev")


if __name__ == "__main__":
    main()
