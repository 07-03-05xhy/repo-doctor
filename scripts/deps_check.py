#!/usr/bin/env python3
"""检查 requirements.txt 与 package.json 中依赖的主版本是否落后于最新发布版。
只读取这两个依赖清单文件；--offline 时不发起任何网络请求。不修改任何文件。"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 网络请求超时时间（秒）
REQUEST_TIMEOUT = 5
# requirements.txt 中第一个版本号（==/>=/<=/~/!=/>/< 之后的数字串）
VERSION_SPEC_RE = re.compile(r"(?:==|>=|<=|~=|!=|>|<)\s*([0-9][^\s,;#]*)")
# 行首包名
PKG_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
# 版本串的第一个数字段（主版本号），容忍开头的 v
MAJOR_RE = re.compile(r"^\s*v?(\d+)")


def parse_requirements(text: str) -> list[tuple[str, str | None]]:
    """解析 requirements.txt，返回 (包名, 版本号或 None) 列表。"""
    deps = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue  # 跳过空行、注释与选项行
        match = PKG_NAME_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        version = None
        if "://" not in line:  # 直接引用（git+https 等）不提取版本号
            spec = VERSION_SPEC_RE.search(line)
            if spec:
                version = spec.group(1)  # 取第一个出现的版本号
        deps.append((name, version))
    return deps


def parse_package_json(text: str) -> list[tuple[str, str | None]]:
    """解析 package.json 的 dependencies，版本号去掉开头的 ^ 或 ~。"""
    data = json.loads(text)
    deps = data.get("dependencies")
    if not isinstance(deps, dict):
        return []
    result = []
    for name, version in deps.items():
        version = str(version).lstrip("^~").strip() or None
        result.append((name, version))
    return result


def major_of(version: str) -> int | None:
    """取版本串的第一个数字段作为主版本号；无法解析时返回 None。"""
    match = MAJOR_RE.match(version)
    return int(match.group(1)) if match else None


def fetch_latest(name: str, registry: str) -> str:
    """查询最新版本号；任何失败都抛异常，由调用方降级为 warning。"""
    if registry == "pypi":
        url = "https://pypi.org/pypi/" + urllib.parse.quote(name, safe="") + "/json"
    else:  # npm，scoped 包保留 @，斜杠编码
        url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@")
    request = urllib.request.Request(url, headers={"User-Agent": "repo-doctor"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    if registry == "pypi":
        return str(data["info"]["version"])
    return str(data["dist-tags"]["latest"])


def decide_issue(name: str, current: str | None, latest: str, dep_file: str) -> tuple[dict | None, dict | None]:
    """按主版本差判定 issue；返回 (issue 或 None, warning 或 None)。"""
    latest_major = major_of(latest)
    if latest_major is None:
        return None, {"package": name, "warning": f"无法解析最新版本号 {latest}，跳过比较"}
    if current is None:
        # 未锁定版本：low，message 注明未锁定
        return {
            "rule": "deps", "file": dep_file, "line": None, "severity": "low",
            "package": name, "current": None, "latest": latest,
            "message": f"依赖 {name} 未锁定版本，最新版本 {latest}",
        }, None
    current_major = major_of(current)
    if current_major is None:
        return None, {"package": name, "warning": f"无法解析当前版本号 {current}，跳过比较"}
    diff = latest_major - current_major
    if diff <= 0:
        return None, None  # 主版本不落后，无 issue
    severity = "medium" if diff == 1 else "high"  # 差 1 为 medium，差 >=2 为 high
    return {
        "rule": "deps", "file": dep_file, "line": None, "severity": severity,
        "package": name, "current": current, "latest": latest,
        "message": f"依赖 {name} 主版本落后：当前 {current}，最新 {latest}",
    }, None


def check(target: Path, inventory: dict) -> dict:
    """读取依赖清单并逐个查询最新版本，返回 issues 与 warnings。"""
    files = inventory.get("files")
    if not isinstance(files, list):
        print("错误：inventory JSON 缺少 files 列表", file=sys.stderr)
        sys.exit(1)
    file_set = {str(f) for f in files}
    # 依赖来源：target 根部的 requirements.txt 与 package.json（以 inventory 为准）
    sources = []
    if "requirements.txt" in file_set:
        sources.append(("requirements.txt", "pypi", parse_requirements))
    if "package.json" in file_set:
        sources.append(("package.json", "npm", parse_package_json))

    issues: list = []
    warnings: list = []
    for dep_file, registry, parser in sources:
        try:
            text = (target / dep_file).read_text(encoding="utf-8", errors="replace")
            deps = parser(text)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"错误：无法解析依赖文件 {dep_file}：{exc}", file=sys.stderr)
            sys.exit(1)
        for name, current in deps:
            try:
                latest = fetch_latest(name, registry)
            except Exception as exc:  # 网络/超时/HTTP/JSON 错误均降级为 warning
                warnings.append({"package": name, "warning": f"查询最新版本失败：{exc}"})
                continue
            issue, warning = decide_issue(name, current, latest, dep_file)
            if issue is not None:
                issues.append(issue)
            if warning is not None:
                warnings.append(warning)
    return {"issues": issues, "warnings": warnings}


def main() -> None:
    parser = argparse.ArgumentParser(description="依赖主版本过期检查")
    parser.add_argument("target", help="目标目录（只读取其根部的依赖清单文件）")
    parser.add_argument("--inventory", required=True, help="inventory.py 输出的 JSON 文件路径")
    parser.add_argument("--out", help="输出 JSON 文件路径（缺省时打印到 stdout）")
    parser.add_argument("--offline", action="store_true", help="离线模式：不发起网络请求，直接跳过")
    args = parser.parse_args()

    if args.offline:
        # 离线模式：固定输出并正常退出
        result = {
            "issues": [],
            "skipped": [{"rule": "deps", "reason": "离线模式：未发起网络请求，依赖检查跳过"}],
            "warnings": [],
        }
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.out:
            out_path = Path(args.out)
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(text, encoding="utf-8")
            except OSError as exc:
                print(f"错误：无法写入输出文件 {args.out}：{exc}", file=sys.stderr)
                sys.exit(1)
        else:
            print(text)
        sys.exit(0)

    target = Path(args.target)
    if not target.is_dir():
        print(f"错误：目标目录不存在或不是目录：{args.target}", file=sys.stderr)
        sys.exit(1)

    try:
        # 用 utf-8-sig 读取，兼容带 BOM 的手写 JSON
        inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        print(f"错误：无法读取 inventory 文件 {args.inventory}：{exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"错误：inventory 文件不是合法 JSON：{exc}", file=sys.stderr)
        sys.exit(1)

    result = check(target, inventory)
    text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        out_path = Path(args.out)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"错误：无法写入输出文件 {args.out}：{exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(text)


if __name__ == "__main__":
    main()
