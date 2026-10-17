#!/usr/bin/env python3
"""按 inventory 清单扫描源码文件中的 TODO/FIXME/HACK/XXX 标记，输出 issue JSON 数组。
只读取清单中列出的文件，不自行遍历目录，不修改任何文件。"""
import argparse
import json
import re
import sys
from pathlib import Path

# 标记匹配正则：TODO|FIXME|HACK|XXX 后跟可选冒号/空白和剩余文本
TAG_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s]*(.*)")
# 源码文件扩展名（与 inventory 的 by_lang 对应）
SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx"}


def is_skipped(rel_path: str) -> bool:
    """确定性跳过规则：文件名以 README 开头（不区分大小写），或路径含 docs/、examples/ 目录。"""
    parts = rel_path.split("/")
    name = parts[-1]
    if name.upper().startswith("README"):
        return True
    return "docs" in parts[:-1] or "examples" in parts[:-1]


def scan(target: Path, inventory: dict) -> list:
    """遍历 inventory 的 files 列表，扫描源码文件并返回 issue 列表。"""
    issues = []
    files = inventory.get("files")
    if not isinstance(files, list):
        print("错误：inventory JSON 缺少 files 列表", file=sys.stderr)
        sys.exit(1)
    for rel in files:
        rel_path = str(rel)
        if Path(rel_path).suffix.lower() not in SOURCE_EXTS:
            continue  # 只扫描源码文件
        if is_skipped(rel_path):
            continue
        abs_path = target / rel_path
        try:
            # 用 utf-8 且替换非法字节，避免编码错误中断
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"错误：无法读取文件 {rel_path}：{exc}", file=sys.stderr)
            sys.exit(1)
        for line_no, line in enumerate(content.splitlines(), start=1):
            match = TAG_PATTERN.search(line)
            if match:
                issues.append({
                    "rule": "todo",
                    "file": rel_path,
                    "line": line_no,
                    "tag": match.group(1),
                    "text": match.group(2).strip(),
                })
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="扫描源码文件中的 TODO/FIXME/HACK/XXX 标记")
    parser.add_argument("target", help="目标目录（inventory 中相对路径基于此目录）")
    parser.add_argument("--inventory", required=True, help="inventory.py 输出的 JSON 文件路径")
    parser.add_argument("--out", help="输出 JSON 文件路径（缺省时打印到 stdout）")
    args = parser.parse_args()

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

    issues = scan(target, inventory)
    text = json.dumps(issues, ensure_ascii=False, indent=2)

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
