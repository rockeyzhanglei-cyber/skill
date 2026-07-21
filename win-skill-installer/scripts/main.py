#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WinAi Skills & MCP Installer - 精简版
支持：技能搜索/安装、MCP 搜索/安装/卸载
"""

import os
import sys
import re
import json
import subprocess
import argparse
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# 检测 requests + requests_ntlm 可用性
_HAS_REQUESTS_NTLM = False
try:
    import requests
    from requests_ntlm import HttpNtlmAuth
    _HAS_REQUESTS_NTLM = True
except ImportError:
    pass

# 检测 yaml 可用性
_HAS_YAML = False
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    pass

# 默认配置（硬编码兜底）
CACHE_ROOT = Path.home() / ".cache" / "WinCode"
_DEFAULT_CONFIG = {
    "tfs_base_url": "http://tfs2018-web.winning.com.cn:8080/tfs",
    "tfs_collection": "WinCode",
    "tfs_skill_project": "Skill",
    "tfs_mcp_project": "MCP",
    "tfs_host": "tfs2018-web.winning.com.cn:8080",
    "cache_root": CACHE_ROOT,
    "skills_cache": CACHE_ROOT / "skill",
    "mcp_cache": CACHE_ROOT / "mcp",
    "registry_path": CACHE_ROOT / "registry.json",
    "skills_dir": Path.home() / ".claude" / "skills",
    "claude_config": Path.home() / ".claude.json",
}


def _load_yaml_config() -> Dict:
    """从 references/config.yaml 加载配置，路径解析 ~ 为用户目录"""
    script_dir = Path(__file__).resolve().parent
    yaml_path = script_dir.parent / "references" / "config.yaml"
    if not yaml_path.exists() or not _HAS_YAML:
        return {}
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not raw:
        return {}
    cfg = {}
    tfs = raw.get("tfs", {})
    if tfs:
        cfg["tfs_base_url"] = tfs.get("base_url", _DEFAULT_CONFIG["tfs_base_url"])
        cfg["tfs_collection"] = tfs.get("collection", _DEFAULT_CONFIG["tfs_collection"])
        cfg["tfs_skill_project"] = tfs.get("skill_project", _DEFAULT_CONFIG["tfs_skill_project"])
        cfg["tfs_mcp_project"] = tfs.get("mcp_project", _DEFAULT_CONFIG["tfs_mcp_project"])
        cfg["tfs_host"] = tfs.get("host", _DEFAULT_CONFIG["tfs_host"])
    cache = raw.get("cache", {})
    if cache:
        cache_root = Path(cache.get("root", str(CACHE_ROOT))).expanduser()
        cfg["cache_root"] = cache_root
        cfg["skills_cache"] = cache_root / cache.get("skills_dir", "skill")
        cfg["mcp_cache"] = cache_root / cache.get("mcp_dir", "mcp")
        cfg["registry_path"] = cache_root / cache.get("registry", "registry.json")
    install = raw.get("install", {})
    if install:
        cfg["skills_dir"] = Path(install.get("target_dir", str(Path.home() / ".claude" / "skills"))).expanduser()
    cfg["claude_config"] = Path.home() / ".claude.json"
    return cfg


def _build_config() -> Dict:
    """合并 yaml 配置与默认配置，yaml 优先"""
    merged = _DEFAULT_CONFIG.copy()
    yaml_cfg = _load_yaml_config()
    merged.update(yaml_cfg)
    return merged


CONFIG = _build_config()


def _decode_output(data: bytes) -> str:
    """安全解码 subprocess 输出，兼容 Windows GBK 环境"""
    if not data:
        return ''
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('latin-1')


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, check: bool = True,
            timeout: int = 60, shell: bool = False) -> subprocess.CompletedProcess:
    """执行命令（bytes 模式，手动解码，避免 Windows 编码崩溃）

    Args:
        cmd: 命令及参数列表
        cwd: 工作目录
        check: 是否在非零返回码时抛异常
        timeout: 超时秒数
        shell: 是否通过 shell 执行（仅必要时启用，如 Windows mklink）
    """
    # Windows 上 npm/git 等是 .cmd 文件，需要 shell=True
    # Windows 上 npm/git 等是 .cmd 文件，需要 shell=True；
    # curl 是原生可执行文件，shell=True 会吞掉 -u ":" 等空参数，必须 shell=False
    is_curl_cmd = cmd and cmd[0] == 'curl'
    if sys.platform == "win32" and not shell and not is_curl_cmd:
        shell = True
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            check=check,
            shell=shell,
            timeout=timeout,
        )
        result.stdout = _decode_output(result.stdout)
        result.stderr = _decode_output(result.stderr)
        return result
    except subprocess.TimeoutExpired as e:
        print(f"[!] 命令超时({timeout}s): {' '.join(cmd)[:80]}")
        stdout = _decode_output(e.stdout) if e.stdout else ''
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout=stdout, stderr='Timed out')


def get_git_credentials(cli_user: str = "", cli_pass: str = "") -> tuple:
    """获取 TFS 凭据，按优先级尝试多个来源，返回 (username, password)

    优先级：
    1. CLI 参数 (--cred-user / --cred-pass)
    2. 环境变量 (TFS_CRED_USER / TFS_CRED_PASS)
    3. git credential fill（存储的 git 凭据）

    所有来源均失败时打印 [NEED_CREDENTIALS] 标记，供 Claude Code 检测并交互收集凭据。
    """
    # 来源 1：CLI 参数
    if cli_user and cli_pass:
        return cli_user, cli_pass

    # 来源 2：环境变量
    env_user = os.environ.get("TFS_CRED_USER", "")
    env_pass = os.environ.get("TFS_CRED_PASS", "")
    if env_user and env_pass:
        return env_user, env_pass

    # 来源 3：git credential fill
    host = CONFIG["tfs_host"]
    input_data = f"protocol=http\nhost={host}\n\n".encode('utf-8')
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input=input_data,
            capture_output=True,
            timeout=10
        )
        output = _decode_output(result.stdout)
        creds = {}
        for line in output.strip().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                creds[k.strip()] = v.strip()
        username = creds.get('username', '')
        password = creds.get('password', '')
        if username and password:
            return username, password
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # 所有来源均失败 → 打印标记
    print("[NEED_CREDENTIALS] TFS API 认证失败，需要域账户凭据")
    print("  提示：请通过 Claude Code AskUserQuestion 提供域用户名和密码")
    print("  或设置环境变量 TFS_CRED_USER / TFS_CRED_PASS")
    return '', ''


def fetch_repos_from_api(project: str, cli_user: str = "", cli_pass: str = "") -> List[Dict]:
    """通过 TFS REST API 获取仓库列表

    Windows 使用 curl --ntlm（底层走 SSPI，与 TFS 2018 兼容性最好），
    macOS/Linux 先尝试 curl --ntlm，失败则降级到 requests_ntlm。
    """
    username, password = get_git_credentials(cli_user, cli_pass)
    # Windows SSPI 可免凭据；其他平台 curl 也可能走通
    allow_empty_creds = platform.system() == "Windows" or not (username and password)
    if not allow_empty_creds and (not username or not password):
        return []

    url = f"{CONFIG['tfs_base_url']}/{CONFIG['tfs_collection']}/{project}/_apis/git/repositories?api-version=4.1"

    # Windows 直接走 curl --ntlm（SSPI 兼容性最好）
    # 其他平台先尝试 curl --ntlm，失败降级 requests_ntlm
    if platform.system() == "Windows":
        return _fetch_repos_via_curl(project, url, username, password)

    repos = _fetch_repos_via_curl(project, url, username, password)
    if repos:
        return repos

    if _HAS_REQUESTS_NTLM:
        print("  [i] curl --ntlm 不可用，降级到 requests_ntlm...")
        return _fetch_repos_via_requests(project, url, username, password)

    print("[!] 当前系统不支持 NTLM 认证，请安装: pip install requests requests_ntlm")
    return []


def _fetch_repos_via_requests(project: str, url: str, username: str, password: str) -> List[Dict]:
    """使用 requests + requests_ntlm 获取仓库列表（推荐，跨平台兼容）"""
    try:
        session = requests.Session()
        session.auth = HttpNtlmAuth(username, password)
        resp = session.get(url, timeout=30)

        if resp.status_code in (401, 403):
            print("[NEED_CREDENTIALS] 需要 TFS 域账户凭据，请通过 --cred-user/--cred-pass 或环境变量传入")
            return []

        if resp.status_code >= 400:
            print(f"[!] API 调用失败(HTTP {resp.status_code})：项目 '{project}'")
            return []

        if not resp.text.strip():
            print(f"[!] API 返回空响应(项目 '{project}')")
            return []

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            print(f"[!] API 返回非 JSON 数据(项目 '{project}')")
            return []

        repos = []
        for repo in data.get("value", []):
            repos.append({
                "name": repo["name"],
                "id": repo["id"],
                "clone_url": repo["remoteUrl"],
                "default_branch": repo.get("defaultBranch", "refs/heads/master"),
                "project": project,
            })
        print(f"  [OK] 项目 '{project}' 获取到 {len(repos)} 个仓库")
        return repos
    except requests.exceptions.ConnectionError:
        print(f"[!] 无法连接 TFS 服务器(项目 '{project}')")
        return []
    except requests.exceptions.Timeout:
        print(f"[!] 请求超时(项目 '{project}')")
        return []
    except Exception as e:
        print(f"[!] API 异常(项目 '{project}'): {e}")
        return []


def _fetch_repos_via_curl(project: str, url: str, username: str, password: str) -> List[Dict]:
    """使用 curl --ntlm 获取仓库列表

    Windows 走 SSPI（空凭据 -u ":"），与 TFS 2018 兼容性最好。
    其他平台 curl 可能也支持 NTLM（如 Homebrew 版本），尝试失败后由调用方降级。
    """
    # Windows SSPI 可免凭据；其他平台需要显式凭据
    sspi_mode = platform.system() == "Windows" and not (username and password)
    user_pass = f"{username}:{password}" if (username and password) else ":"

    try:
        result = run_cmd([
            "curl", "-s", "-w", "\\n%{http_code}",
            "--connect-timeout", "10", "--max-time", "30",
            "--ntlm", "-u",
            user_pass, url
        ], timeout=45, check=False)
        # 分离 body 和 status code
        output = result.stdout.strip()
        if "\n" in output:
            body, status_str = output.rsplit("\n", 1)
            status_code = int(status_str.strip())
        else:
            body = output
            status_code = 0

        # Windows SSPI 成功则直接返回；显式凭据失败则尝试 SSPI 回退
        if (status_code == 401 or status_code == 403) and not sspi_mode and platform.system() == "Windows":
            print("  [i] 显式凭据认证失败，尝试 Windows SSPI 回退...")
            result = run_cmd([
                "curl", "-s", "-w", "\n%{http_code}",
                "--connect-timeout", "10", "--max-time", "30",
                "--ntlm", "-u", ":", url
            ], timeout=45, check=False)
            output = result.stdout.strip()
            if "\n" in output:
                body, status_str = output.rsplit("\n", 1)
                status_code = int(status_str.strip())
            else:
                body = output
                status_code = 0

        if status_code == 401 or status_code == 403:
            print("[NEED_CREDENTIALS] 需要 TFS 域账户凭据，请通过 --cred-user/--cred-pass 或环境变量传入")
            return []

        if status_code >= 400:
            print(f"[!] API 调用失败(HTTP {status_code})：项目 '{project}'")
            return []

        if not body.strip():
            print(f"[!] API 返回空响应(项目 '{project}')")
            return []

        data = json.loads(body)
        repos = []
        for repo in data.get("value", []):
            repos.append({
                "name": repo["name"],
                "id": repo["id"],
                "clone_url": repo["remoteUrl"],
                "default_branch": repo.get("defaultBranch", "refs/heads/master"),
                "project": project,
            })
        print(f"  [OK] 项目 '{project}' 获取到 {len(repos)} 个仓库")
        return repos
    except json.JSONDecodeError:
        print(f"[!] API 返回非 JSON 数据(项目 '{project}')")
        return []
    except FileNotFoundError:
        print(f"[!] curl 未找到，建议安装: pip install requests requests_ntlm")
        return []
    except Exception as e:
        print(f"[!] API 异常(项目 '{project}'): {e}")
        return []


def load_registry() -> Dict:
    """加载本地 registry.json"""
    registry_path = CONFIG["registry_path"]
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {"skills": [], "mcps": [], "updated_at": ""}


def save_registry(registry: Dict):
    """保存 registry.json"""
    CONFIG["cache_root"].mkdir(parents=True, exist_ok=True)
    registry_path = CONFIG["registry_path"]
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def refresh_registry(cli_user: str = "", cli_pass: str = "") -> bool:
    """刷新 registry（从 API 获取最新仓库列表）

    有本地缓存时：API 失败只输出一行静默提示，不影响功能。
    无本地缓存时：API 失败输出详细排查建议，因为用户无法继续操作。
    """
    has_local_cache = CONFIG["registry_path"].exists()

    skill_repos = fetch_repos_from_api(CONFIG["tfs_skill_project"], cli_user, cli_pass)
    mcp_repos = fetch_repos_from_api(CONFIG["tfs_mcp_project"], cli_user, cli_pass)

    if not skill_repos and not mcp_repos:
        if has_local_cache:
            print("[!] API 刷新跳过（使用本地缓存）")
        else:
            print("[X] 无本地缓存且 API 认证失败，请检查：")
            print("    1. 通过 --cred-user/--cred-pass 提供域账户凭据")
            print("    2. 网络是否能访问 TFS (tfs2018-web.winning.com.cn:8080)")
            print("    3. 账号是否有 WinCode/Skill 和 WinCode/MCP 项目的权限")
        return False

    # 警告：部分项目获取失败
    if not skill_repos:
        print("[!] Skill 列表刷新失败")
    if not mcp_repos:
        print("[!] MCP 列表刷新失败")

    registry = {
        "skills": skill_repos,
        "mcps": mcp_repos,
        "updated_at": datetime.now().isoformat(),
    }

    # 附加已缓存的 SKILL.md 元数据
    _enrich_registry_with_local_metadata(registry)

    save_registry(registry)
    total = len(skill_repos) + len(mcp_repos)
    print(f"[OK] 已更新 registry，共 {total} 个仓库")
    return True


def _enrich_registry_with_local_metadata(registry: Dict):
    """从已缓存的仓库读取 SKILL.md 元数据，填充到 registry"""
    for repo in registry["skills"]:
        local_path = CONFIG["skills_cache"] / repo["name"]
        if local_path.exists():
            skill_md = local_path / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = parts[1]
                        desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
                        if desc_match:
                            repo["description"] = desc_match.group(1).strip()
                        tags_match = re.search(r"^tags:\s*\[(.+)\]$", fm, re.MULTILINE)
                        if tags_match:
                            repo["tags"] = [t.strip() for t in tags_match.group(1).split(",")]


def ensure_repo_cached(name: str, clone_url: str, cache_dir: Path, branch: str = "master") -> Optional[Path]:
    """确保单个仓库已缓存，不存在则 clone"""
    repo_path = cache_dir / name

    if repo_path.exists() and (repo_path / ".git").exists():
        return repo_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"正在克隆 {name}...")
    try:
        branch_ref = branch.replace("refs/heads/", "")
        run_cmd([
            "git", "clone",
            "--branch", branch_ref,
            "--depth", "1",
            clone_url,
            str(repo_path)
        ])
        print(f"  [OK] 克隆成功")
        return repo_path
    except subprocess.CalledProcessError as e:
        print(f"  [X] 克隆失败: {e.stderr}")
        return None


def update_cached_repos() -> List[str]:
    """更新所有已缓存的仓库（git pull），返回有实际变更的仓库名列表"""
    updated = []
    changed = []
    failed = []

    for cache_subdir in [CONFIG["skills_cache"], CONFIG["mcp_cache"]]:
        if not cache_subdir.exists():
            continue
        for item in cache_subdir.iterdir():
            if item.is_dir() and (item / ".git").exists():
                print(f"  更新 {item.name}...")
                try:
                    result = run_cmd(["git", "pull"], cwd=item)
                    updated.append(item.name)
                    # 检测是否有实际文件变更
                    if result.stdout.strip() != "Already up to date.":
                        changed.append(item.name)
                except subprocess.CalledProcessError:
                    try:
                        # 只在浅克隆时才 unshallow，否则直接重试 pull
                        shallow_file = item / ".git" / "shallow"
                        if shallow_file.exists():
                            run_cmd(["git", "fetch", "--unshallow"], cwd=item)
                        run_cmd(["git", "pull"], cwd=item)
                        updated.append(item.name)
                        changed.append(item.name)
                    except subprocess.CalledProcessError as e:
                        print(f"    [!] 更新失败: {e.stderr}")
                        failed.append(item.name)

    if updated:
        unchanged_count = len(updated) - len(changed)
        print(f"[OK] 已检查 {len(updated)} 个仓库，{len(changed)} 个有更新，{unchanged_count} 个无变化")
    if failed:
        print(f"[!] {len(failed)} 个仓库更新失败: {', '.join(failed)}")

    return changed


def is_registry_stale(max_age_hours: int = 24) -> bool:
    """检查 registry 是否过期（超过 max_age_hours 小时）"""
    registry = load_registry()
    updated_at = registry.get("updated_at", "")
    if not updated_at:
        return True
    try:
        last_update = datetime.fromisoformat(updated_at)
        age = datetime.now() - last_update
        return age.total_seconds() > max_age_hours * 3600
    except (ValueError, TypeError):
        return True


def ensure_registry(force_refresh: bool = False, cli_user: str = "", cli_pass: str = "") -> bool:
    """确保 registry 存在且不过期，过期或不存在则从 API 创建"""
    if not force_refresh and CONFIG["registry_path"].exists() and not is_registry_stale():
        return True
    return refresh_registry(cli_user, cli_pass)


# ============== Skills ==============

def list_skills() -> List[Dict]:
    """列出所有可用技能（从 registry）"""
    registry = load_registry()
    return registry.get("skills", [])


def search_skills(keyword: str) -> List[Dict]:
    """搜索技能"""
    all_skills = list_skills()
    keyword_lower = keyword.lower()

    results = []
    for skill in all_skills:
        name_match = keyword_lower in skill["name"].lower()
        desc_match = keyword_lower in skill.get("description", "").lower()
        tag_match = any(keyword_lower in tag.lower() for tag in skill.get("tags", []))

        if name_match or desc_match or tag_match:
            results.append(skill)
    return results


def create_symlink(source: Path, target: Path) -> bool:
    """创建符号链接（跨平台）"""
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            # Python 3.12+ shutil.rmtree 拒绝对软链调用，必须先 unlink
            target.unlink()
        elif target.is_dir():
            if platform.system() == "Windows":
                shutil.rmtree(target)
            else:
                shutil.rmtree(target)
        else:
            target.unlink()

    try:
        if platform.system() == "Windows":
            source_abs = source.resolve()
            target_abs = target.resolve()
            run_cmd(["cmd", "/c", "mklink", "/J", str(target_abs), str(source_abs)],
                    check=False, shell=True)
            if target.exists():
                return True
            target.symlink_to(source_abs)
        else:
            target.symlink_to(source)
        return True
    except Exception as e:
        print(f"[X] 创建链接失败: {e}")
        return False


def install_skill(skill_name: str) -> bool:
    """安装技能（clone + 符号链接）"""
    registry = load_registry()

    # 从 registry 查找
    skill_info = None
    for s in registry.get("skills", []):
        if s["name"].lower() == skill_name.lower():
            skill_info = s
            break

    if not skill_info:
        # 模糊匹配
        for s in registry.get("skills", []):
            if skill_name.lower() in s["name"].lower():
                skill_info = s
                break

    if not skill_info:
        print(f"[X] 未找到技能: {skill_name}")
        return False

    # clone 到缓存
    repo_path = ensure_repo_cached(
        skill_info["name"],
        skill_info["clone_url"],
        CONFIG["skills_cache"],
        skill_info.get("default_branch", "refs/heads/master")
    )

    if not repo_path:
        return False

    # 创建符号链接
    target_path = CONFIG["skills_dir"] / skill_info["name"]
    print(f"安装: {skill_info['name']}")
    print(f"  源: {repo_path}")
    print(f"  目标: {target_path}")

    if create_symlink(repo_path, target_path):
        print(f"[OK] 已安装 {skill_info['name']}")
        # === WinCode 统一管理扩展（zhang.lei@2026-06-17）===
        # 安装/更新后自动同步到 ~/.agents/skills/（真源），并重新挂载到
        # ~/.workbuddy/skills/、~/.codex/skills/user/，实现一个 skill 一份源、
        # 所有 agent 共用。失败时打印警告，不影响主安装流程。
        try:
            import shutil
            unified_dir = Path.home() / ".agents" / "skills" / skill_info["name"]
            unified_dir.parent.mkdir(parents=True, exist_ok=True)

            # === 升级前 diff 保护（zhang.lei@2026-06-17）===
            # 如果真源里已有本地修改过的文件，升级会覆盖用户改动。
            # 这里先做一次 diff，发现冲突就停下来问用户，避免误覆盖。
            local_modified = []
            if unified_dir.exists() and not unified_dir.is_symlink():
                for src_file in Path(repo_path).rglob("*"):
                    if not src_file.is_file():
                        continue
                    rel = src_file.relative_to(repo_path)
                    dst_file = unified_dir / rel
                    if dst_file.is_symlink() or dst_file.exists():
                        try:
                            if dst_file.is_symlink() or dst_file.is_file():
                                # 内容对比
                                if not dst_file.is_symlink() and dst_file.is_file():
                                    if src_file.read_bytes() != dst_file.read_bytes():
                                        local_modified.append(str(rel))
                        except Exception:
                            pass

            if local_modified:
                # 真源里还有未提交的本地修改，必须先问用户
                print()
                print(f"  [!!] 检测到 {skill_info['name']} 在 ~/.agents/skills/ 下有本地修改：")
                for f in local_modified[:10]:
                    print(f"      - {f}")
                if len(local_modified) > 10:
                    print(f"      ... 还有 {len(local_modified) - 10} 个文件")
                print()
                print(f"  本地修改路径: {unified_dir}")
                print(f"  新版本路径:   {repo_path}")
                print()
                print("  选项：")
                print("    [d]  diff - 打开差异查看（推荐先看）")
                print("    [k]  keep  - 保留本地修改，跳过本次同步（安全）")
                print("    [o]  overwrite - 强制覆盖（会丢失本地修改）")
                print("    [b]  backup   - 把本地修改备份到 ~/Desktop/<name>-patch-<时间戳>/ 后再覆盖")
                print()
                try:
                    choice = input("  请选择 [d/k/o/b] (默认 k): ").strip().lower() or "k"
                except (EOFError, KeyboardInterrupt):
                    choice = "k"

                if choice == "d":
                    # 把本地修改的文件 diff 给用户看
                    import subprocess
                    print()
                    for f in local_modified[:5]:
                        src_f = Path(repo_path) / f
                        dst_f = unified_dir / f
                        print(f"  ----- diff: {f} -----")
                        try:
                            subprocess.run(
                                ["diff", "-u", str(dst_f), str(src_f)],
                                check=False,
                            )
                        except Exception as e:
                            print(f"  (diff 失败: {e})")
                    if len(local_modified) > 5:
                        print(f"  ... 还有 {len(local_modified) - 5} 个文件未显示")
                    print()
                    # 看完了再问一次
                    try:
                        choice2 = input("  看完了，请选择 [k/o/b] (默认 k): ").strip().lower() or "k"
                    except (EOFError, KeyboardInterrupt):
                        choice2 = "k"
                    choice = choice2

                if choice == "b":
                    # 备份
                    backup_root = Path.home() / "Desktop" / f"{skill_info['name']}-patch-{int(__import__('time').time())}"
                    backup_root.mkdir(parents=True, exist_ok=True)
                    backup_count = 0
                    for rel in local_modified:
                        try:
                            src_f = unified_dir / rel
                            dst_f = backup_root / rel
                            dst_f.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_f, dst_f)
                            backup_count += 1
                        except Exception:
                            pass
                    print(f"  [backup] 已备份 {backup_count} 个文件到 {backup_root}")
                    # 不 return，继续往下覆盖
                elif choice == "k":
                    print(f"  [skip] 已保留本地修改，跳过本次同步")
                    print(f"  提示：手动去 {unified_dir} 处理冲突后，重跑升级")
                    return True  # 主流程仍算成功
                elif choice == "o":
                    print(f"  [force] 用户选择强制覆盖")
                    # 不 return，继续往下走
                else:
                    print(f"  [skip] 未识别选项，按 keep 处理")
                    return True
            # === diff 保护结束 ===

            # 真源必须是真实目录（不是软链）
            if unified_dir.is_symlink() or unified_dir.exists():
                if unified_dir.is_symlink() or unified_dir.is_dir():
                    shutil.rmtree(unified_dir)
                else:
                    unified_dir.unlink()
            shutil.copytree(repo_path, unified_dir)
            print(f"  [sync] 真源: {unified_dir}")

            # 重新软链到其他 agent 入口
            for agent_dir in (
                Path.home() / ".workbuddy" / "skills",
                Path.home() / ".codex" / "skills" / "user",
            ):
                link = agent_dir / skill_info["name"]
                agent_dir.mkdir(parents=True, exist_ok=True)
                if link.is_symlink() or link.exists():
                    if link.is_symlink() or link.is_dir():
                        if link.is_symlink() or link.is_dir():
                            shutil.rmtree(link)
                    else:
                        link.unlink()
                link.symlink_to(unified_dir)
                print(f"  [sync] 分发: {link} -> {unified_dir}")
        except Exception as sync_err:
            print(f"  [!] 同步到统一目录失败（不影响主安装）: {sync_err}")
        # === 扩展结束 ===
        return True
    return False


# ============== MCP ==============

def list_mcps() -> List[Dict]:
    """列出所有可用 MCP（从 registry）"""
    registry = load_registry()
    return registry.get("mcps", [])


def search_mcps(keyword: str) -> List[Dict]:
    """搜索 MCP"""
    all_mcps = list_mcps()
    keyword_lower = keyword.lower()

    results = []
    for mcp in all_mcps:
        if (keyword_lower in mcp["name"].lower() or
            keyword_lower in mcp.get("description", "").lower()):
            results.append(mcp)
    return results


def load_claude_config() -> Dict:
    """加载 ~/.claude.json"""
    config_path = CONFIG["claude_config"]
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def save_claude_config(config: Dict):
    """保存 ~/.claude.json"""
    config_path = CONFIG["claude_config"]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def list_installed_mcps() -> List[str]:
    """列出已安装的 MCP"""
    config = load_claude_config()
    return list(config.get("mcpServers", {}).keys())


def rebuild_mcp(mcp_dir: Path) -> bool:
    """重新编译单个 MCP（npm install + npm run build）"""
    package_json = mcp_dir / "package.json"
    if not package_json.exists():
        return False

    print(f"  正在重新编译 {mcp_dir.name}...")

    # npm install
    try:
        run_cmd(["npm", "install"], cwd=mcp_dir)
        print(f"    [OK] 依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"    [!] 依赖安装失败: {e.stderr}")

    # npm run build
    try:
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
        if "build" in pkg.get("scripts", {}):
            run_cmd(["npm", "run", "build"], cwd=mcp_dir)
            print(f"    [OK] 编译完成")
    except subprocess.CalledProcessError as e:
        print(f"    [!] 编译失败: {e.stderr}")

    return True


def rebuild_installed_mcps(changed_repos: List[str] = None):
    """检查已安装的 MCP 并重新编译（始终编译所有已安装的 MCP）"""
    installed = list_installed_mcps()
    if not installed:
        return

    mcp_cache = CONFIG["mcp_cache"]
    rebuilt = []

    for name in installed:
        mcp_path = mcp_cache / name
        if mcp_path.exists() and (mcp_path / "package.json").exists():
            if rebuild_mcp(mcp_path):
                rebuilt.append(name)

    if rebuilt:
        print(f"[OK] 已重新编译 {len(rebuilt)} 个 MCP: {', '.join(rebuilt)}")
    else:
        print("[OK] 已安装的 MCP 无需编译")


def install_mcp(mcp_name: str, env_override: Dict = None) -> bool:
    """安装 MCP（clone + npm build + 更新配置）"""
    registry = load_registry()

    # 从 registry 查找
    mcp_info = None
    for m in registry.get("mcps", []):
        if m["name"].lower() == mcp_name.lower():
            mcp_info = m
            break

    if not mcp_info:
        # 模糊匹配
        for m in registry.get("mcps", []):
            if mcp_name.lower() in m["name"].lower():
                mcp_info = m
                break

    if not mcp_info:
        print(f"[X] 未找到 MCP: {mcp_name}")
        return False

    # clone 到缓存
    repo_path = ensure_repo_cached(
        mcp_info["name"],
        mcp_info["clone_url"],
        CONFIG["mcp_cache"],
        mcp_info.get("default_branch", "refs/heads/master")
    )

    if not repo_path:
        return False

    print(f"安装 MCP: {mcp_info['name']}")

    # npm install
    package_json = repo_path / "package.json"
    if package_json.exists():
        print("  正在安装依赖...")
        try:
            run_cmd(["npm", "install"], cwd=repo_path)
            print("  [OK] 依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"  [!] 依赖安装失败: {e.stderr}")

    # npm run build（始终编译，确保 dist/ 是最新的）
    if package_json.exists():
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
        if "build" in pkg.get("scripts", {}):
            print("  正在编译...")
            try:
                run_cmd(["npm", "run", "build"], cwd=repo_path)
                print("  [OK] 编译完成")
            except subprocess.CalledProcessError as e:
                print(f"  [!] 编译失败: {e.stderr}")

    # 更新 ~/.claude.json
    print("  正在更新配置...")
    config = load_claude_config()
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    dist_index = repo_path / "dist" / "index.js"
    if dist_index.exists():
        entry_point = str(dist_index)
    else:
        entry_point = str(repo_path / "index.js")

    mcp_server_name = mcp_info["name"]

    # 获取预设 env 模板，并用命令行传入的值覆盖
    env_config = _get_mcp_env_preset(mcp_server_name, config)
    if env_override:
        if not env_config:
            env_config = {}
        env_config.update(env_override)

    new_config = {
        "command": "node",
        "args": [entry_point],
    }
    if env_config:
        new_config["env"] = env_config

    config["mcpServers"][mcp_server_name] = new_config

    save_claude_config(config)
    print("  [OK] 配置已更新")
    if env_config:
        print(f"  [OK] 已配置 env: {', '.join(env_config.keys())}")
    print(f"\n[OK] MCP {mcp_server_name} 安装成功")
    print("  重启 Claude Code 以生效")
    return True


def _get_mcp_env_preset(mcp_name: str, config: Dict) -> Dict:
    """获取 MCP 的预设 env 配置，优先复用已有配置"""
    existing_env = config.get("mcpServers", {}).get(mcp_name, {}).get("env", {})

    # 预设模板
    presets = {
        "tfs-mcp": {
            "TFS_URL": "http://tfs2018-web.winning.com.cn:8080/tfs",
            "TFS_PAT": "",
            "TFS_COLLECTION": "WINNING-6.0",
        },
        "wiki-mcp": {
            "CONFLUENCE_URL": "https://winwiki.winning.com.cn",
            "CONFLUENCE_TOKEN": "",
        },
        "devops-mcp": {
            "API_OPS_BASE_URL": "http://172.16.7.52:7099/",
            "API_COP_BASE_URL": "http://172.16.9.87:8089/",
            "TFS_KEY": "",
        },
    }

    if mcp_name not in presets:
        return existing_env

    preset = presets[mcp_name].copy()

    # 复用已有配置中的值
    for key in preset:
        if key in existing_env and existing_env[key]:
            preset[key] = existing_env[key]

    # tfs-mcp 特殊处理：如果 PAT 为空，提示用户需要手动配置
    if mcp_name == "tfs-mcp" and not preset.get("TFS_PAT"):
        pass  # PAT 需要用户手动提供

    # devops-mcp：OPS 和 COP 是独立服务，各自有默认地址，无需特殊处理

    # 过滤掉空值，只保留有效配置
    preset = {k: v for k, v in preset.items() if v}

    if not preset:
        print("  [!] 未找到预设 env 配置，请手动配置敏感信息（如 PAT、Token）")

    return preset


def uninstall_mcp(mcp_name: str) -> bool:
    """卸载 MCP（删除缓存 + 更新配置）"""
    mcp_cache = CONFIG["mcp_cache"]

    # 查找已缓存的 MCP
    mcp_path = mcp_cache / mcp_name
    if not mcp_path.exists():
        for item in mcp_cache.iterdir():
            if item.is_dir() and mcp_name.lower() in item.name.lower():
                mcp_path = item
                break

    if not mcp_path.exists():
        print(f"[X] 未找到已安装的 MCP: {mcp_name}")
        return False

    # 删除缓存目录
    print(f"删除: {mcp_path}")
    shutil.rmtree(mcp_path)

    # 更新配置
    config = load_claude_config()
    server_name = mcp_path.name
    if "mcpServers" in config and server_name in config["mcpServers"]:
        del config["mcpServers"][server_name]
        save_claude_config(config)
        print(f"[OK] 已从配置中移除 {server_name}")

    print(f"[OK] MCP {server_name} 已卸载")
    return True


# ============== Main ==============

def main():
    parser = argparse.ArgumentParser(description="WinAi Skills & MCP Installer")
    parser.add_argument("name", nargs="?", help="要安装的技能/MCP名称")
    parser.add_argument("--search", "-s", metavar="KEYWORD", help="搜索技能")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有技能")
    parser.add_argument("--update", "-u", action="store_true", help="更新 registry 和缓存")

    # MCP 相关参数
    parser.add_argument("--mcp", action="store_true", help="操作 MCP 而非技能")
    parser.add_argument("--mcp-search", metavar="KEYWORD", help="搜索 MCP")
    parser.add_argument("--mcp-list", action="store_true", help="列出所有可用 MCP")
    parser.add_argument("--mcp-installed", action="store_true", help="列出已安装的 MCP")
    parser.add_argument("--mcp-uninstall", metavar="NAME", help="卸载 MCP")
    parser.add_argument("--mcp-env", nargs="*", metavar="KEY=VALUE", help="MCP 环境变量，如 TFS_PAT=xxx")

    # 凭据参数（用于 AskUserQuestion 交互收集后传入）
    parser.add_argument("--cred-user", metavar="USER", help="TFS 域用户名（交互兜底）")
    parser.add_argument("--cred-pass", metavar="PASS", help="TFS 域密码（交互兜底）")

    args = parser.parse_args()
    cli_user = getattr(args, "cred_user", "") or ""
    cli_pass = getattr(args, "cred_pass", "") or ""

    # === MCP 操作 ===

    if args.mcp_search:
        if not ensure_registry(cli_user=cli_user, cli_pass=cli_pass):
            return 1
        results = search_mcps(args.mcp_search)
        if not results:
            print(f"未找到匹配 '{args.mcp_search}' 的 MCP")
            return 0
        print(f"\n找到 {len(results)} 个 MCP:\n")
        for mcp in results:
            print(f"  → {mcp['name']}")
            if mcp.get('description'):
                print(f"    {mcp['description']}")
        return 0

    if args.mcp_list:
        if not ensure_registry(cli_user=cli_user, cli_pass=cli_pass):
            return 1
        mcps = list_mcps()
        if not mcps:
            print("没有找到 MCP")
            return 0
        print(f"\n共 {len(mcps)} 个 MCP:\n")
        for i, mcp in enumerate(mcps, 1):
            print(f"  {i}. {mcp['name']}")
            if mcp.get('description'):
                print(f"     {mcp['description']}")
        return 0

    if args.mcp_installed:
        installed = list_installed_mcps()
        if not installed:
            print("未安装任何 MCP")
            return 0
        print(f"\n已安装 {len(installed)} 个 MCP:\n")
        for name in installed:
            print(f"  • {name}")
        return 0

    if args.mcp_uninstall:
        return 0 if uninstall_mcp(args.mcp_uninstall) else 1

    if args.mcp and args.name:
        if not ensure_registry(cli_user=cli_user, cli_pass=cli_pass):
            return 1
        env_override = {}
        if args.mcp_env:
            for item in args.mcp_env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_override[k] = v
        return 0 if install_mcp(args.name, env_override) else 1

    # === 更新操作 ===

    if args.update:
        refresh_registry(cli_user, cli_pass)
        print("\n正在更新已缓存的仓库...")
        changed = update_cached_repos()
        print("\n正在检查已安装的 MCP...")
        rebuild_installed_mcps(changed)
        return 0

    # === Skills 操作 ===

    if not ensure_registry(cli_user=cli_user, cli_pass=cli_pass):
        return 1

    if args.list:
        skills = list_skills()
        if not skills:
            print("没有找到技能")
            return 0
        print(f"\n共 {len(skills)} 个技能:\n")
        for i, skill in enumerate(skills, 1):
            desc = skill.get('description', '')
            if desc:
                print(f"  {i}. {skill['name']} - {desc}")
            else:
                print(f"  {i}. {skill['name']}")
        return 0

    if args.search:
        results = search_skills(args.search)
        if not results:
            print(f"未找到匹配 '{args.search}' 的技能")
            return 0
        print(f"\n找到 {len(results)} 个匹配:\n")
        for skill in results:
            desc = skill.get('description', '')
            if desc:
                print(f"  → {skill['name']} - {desc}")
            else:
                print(f"  → {skill['name']}")
        return 0

    if args.name:
        return 0 if install_skill(args.name) else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
