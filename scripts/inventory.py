#!/usr/bin/env python3
"""递归遍历目标目录，输出文件清单 JSON（相对 POSIX 路径、按语言统计、跳过的目录）。
对不超过 2MB 的源码文件统计行数；其余文件只记录路径、不读取内容。
只做确定性清单统计，不修改目标目录的任何文件。"""
import argparse
import json
import sys
from pathlib import Path

# 遍历时跳过的目录名
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__", ".next"}
# 源码文件扩展名（小写）
SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx"}
# 扩展名到语言类别的映射
LANG_MAP = {".py": "py", ".js": "js", ".jsx": "js", ".ts": "ts", ".tsx": "ts"}
# 统计行数的文件大小上限（2MB），超过则只记录路径、不读取内容
MAX_LINES_SIZE = 2 * 1024 * 1024


def to_posix_rel(path: Path, base: Path) -> str:
    """把绝对路径转成相对 base 的 POSIX 风格路径（Windows 下也用 / 分隔）。"""
    return path.relative_to(base).as_posix()


def collect(target: Path) -> dict:
    """递归遍历 target，返回清单字典。"""
    files: list[str] = []
    skipped_dirs: list[str] = []
    by_lang = {"py": 0, "js": 0, "ts": 0}
    lines: dict[str, int] = {}

    def walk(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            print(f"错误：无法读取目录 {directory}：{exc}", file=sys.stderr)
            sys.exit(1)
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    # 记录被跳过目录的相对路径
                    skipped_dirs.append(to_posix_rel(entry, target))
                else:
                    walk(entry)
            elif entry.is_file():
                rel = to_posix_rel(entry, target)
                files.append(rel)
                lang = LANG_MAP.get(entry.suffix.lower())
                if lang is not None:
                    by_lang[lang] += 1
                    # 只对不超过 2MB 的源码文件统计行数（键与 files 中的路径一致）
                    try:
                        if entry.stat().st_size <= MAX_LINES_SIZE:
                            content = entry.read_text(encoding="utf-8", errors="replace")
                            lines[rel] = len(content.splitlines())
                    except OSError as exc:
                        print(f"错误：无法读取文件 {rel}：{exc}", file=sys.stderr)
                        sys.exit(1)

    walk(target)
    return {
        "target": str(target),
        "files": files,
        "by_lang": by_lang,
        "source_files": sum(by_lang.values()),
        "skipped_dirs": skipped_dirs,
        "lines": lines,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="递归遍历目标目录并输出文件清单 JSON")
    parser.add_argument("target", help="要扫描的目标目录")
    parser.add_argument("--out", help="输出 JSON 文件路径（缺省时打印到 stdout）")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.is_dir():
        print(f"错误：目标目录不存在或不是目录：{args.target}", file=sys.stderr)
        sys.exit(1)

    result = collect(target)
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
