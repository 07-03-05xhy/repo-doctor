#!/usr/bin/env python3
"""按文件名映射检查 Python 源文件是否存在对应测试文件，输出缺失清单与比例。
只比对 inventory 的路径列表，不读取任何源文件或测试文件的内容。"""
import argparse
import json
import sys
from pathlib import Path


def is_source_file(rel_path: str) -> bool:
    """判断是否参与检查的源文件：排除 tests 目录、test_ 开头文件、__init__.py。"""
    parts = rel_path.split("/")
    name = parts[-1]
    if name == "__init__.py":
        return False
    if name.startswith("test_"):
        return False
    if "tests" in parts[:-1]:
        return False  # 任何一级目录名为 tests 即排除
    return True


def candidates_of(rel_path: str) -> list[str]:
    """按映射规则生成候选测试文件路径：tests/test_name.py 与 tests/<子路径>/test_name.py。"""
    parts = rel_path.split("/")
    stem = parts[-1][:-3]  # 去掉 .py 后缀
    test_name = f"test_{stem}.py"
    dirs = parts[:-1]
    if "src" in dirs:
        # 路径含 src 目录时，子路径取 src 之后到文件名之间的部分
        sub = dirs[dirs.index("src") + 1:]
    else:
        # 否则子路径为文件所在目录
        sub = dirs
    candidates = [f"tests/{test_name}"]
    if sub:
        candidates.append("tests/" + "/".join(sub) + "/" + test_name)
    return candidates


def check_tests(inventory: dict) -> dict:
    """对 inventory 中的 .py 源文件逐一检查测试映射，返回结果字典。"""
    files = inventory.get("files")
    if not isinstance(files, list):
        print("错误：inventory JSON 缺少 files 列表", file=sys.stderr)
        sys.exit(1)
    file_set = {str(f) for f in files}
    missing: list[str] = []
    checked = 0
    for rel in sorted(file_set):
        if Path(rel).suffix.lower() != ".py":
            continue  # 只处理 .py 文件
        if not is_source_file(rel):
            continue
        checked += 1
        if not any(c in file_set for c in candidates_of(rel)):
            missing.append(rel)
    missing_count = len(missing)
    return {
        "missing": missing,
        "checked": checked,
        "missing_count": missing_count,
        # checked 为 0 时比例为 null，否则保留 4 位小数
        "missing_ratio": round(missing_count / checked, 4) if checked else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="测试缺失映射检查（只做文件名映射）")
    parser.add_argument("target", help="目标目录（仅用于校验，不读取其中文件内容）")
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

    result = check_tests(inventory)
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
