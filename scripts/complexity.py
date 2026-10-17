#!/usr/bin/env python3
"""对 inventory 清单中的 Python 文件做 AST 复杂度分析，输出超阈值函数的 issue。
只处理 .py 文件（JS/TS 不支持，固定记入 skipped）；不修改任何文件。"""
import argparse
import ast
import json
import sys
from pathlib import Path

# 复杂度阈值（medium）：行数与分支数上限
LINE_THRESHOLD = 80
BRANCH_THRESHOLD = 15
# high 阈值固定为 medium 阈值的两倍（160 行 / 30 分支）
# 计入分支数的 AST 节点类型
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While,
                ast.ExceptHandler, ast.With, ast.AsyncWith, ast.BoolOp)
# 函数节点类型（含异步函数）
FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def analyze_source(rel_path: str, source: str) -> tuple[list, dict | None]:
    """解析单个文件的源码，返回 (issues, warning)。语法错误时不崩溃，返回 warning。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], {"file": rel_path, "warning": "语法错误，跳过解析"}
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, FUNC_NODES):
            continue
        func_lines = node.end_lineno - node.lineno + 1
        # 既定口径：ast.walk 覆盖函数整个子树，嵌套函数的分支计入外层函数
        branches = sum(1 for child in ast.walk(node) if isinstance(child, BRANCH_NODES))
        if func_lines > LINE_THRESHOLD or branches > BRANCH_THRESHOLD:
            # 超过阈值但行数 <=160 且分支 <=30 为 medium，任一再翻倍为 high
            if func_lines > LINE_THRESHOLD * 2 or branches > BRANCH_THRESHOLD * 2:
                severity = "high"
            else:
                severity = "medium"
            issues.append({
                "rule": "complexity",
                "file": rel_path,
                "line": node.lineno,
                "severity": severity,
                "function": node.name,
                "lines": func_lines,
                "branches": branches,
                "line_threshold": LINE_THRESHOLD,
                "branch_threshold": BRANCH_THRESHOLD,
                "message": f"函数 {node.name} 复杂度过高：{func_lines} 行 / {branches} 分支"
                           f"（阈值 {LINE_THRESHOLD} 行 / {BRANCH_THRESHOLD} 分支）",
            })
    return issues, None


def collect(target: Path, inventory: dict) -> dict:
    """按 inventory 的 files 列表逐个解析 .py 文件，汇总 issues 与 warnings。"""
    files = inventory.get("files")
    if not isinstance(files, list):
        print("错误：inventory JSON 缺少 files 列表", file=sys.stderr)
        sys.exit(1)
    issues: list = []
    warnings: list = []
    for rel in files:
        rel_path = str(rel)
        if Path(rel_path).suffix.lower() != ".py":
            continue  # JS/TS 等其他扩展名不处理
        try:
            source = (target / rel_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"错误：无法读取文件 {rel_path}：{exc}", file=sys.stderr)
            sys.exit(1)
        file_issues, warning = analyze_source(rel_path, source)
        issues.extend(file_issues)
        if warning is not None:
            warnings.append(warning)
    return {
        "issues": issues,
        # 固定输出：JS/TS 不做复杂度分析
        "skipped": [{"rule": "complexity",
                     "reason": "JS/TS 文件暂不支持复杂度分析，仅解析 Python"}],
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Python 函数复杂度 AST 分析")
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

    result = collect(target, inventory)
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
