#!/usr/bin/env python3
"""对 inventory 清单中的源码文件做复杂度分析，输出超阈值函数的 issue。
.py 用 AST 精确解析；.js/.ts/.jsx/.tsx 用纯标准库启发式（正则+花括号配对）估算。
只读取目标文件，不修改任何文件。"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

# 复杂度阈值（medium）：行数与分支数上限（Python 与 JS/TS 共用同一阈值）
LINE_THRESHOLD = 80
BRANCH_THRESHOLD = 15
# high 阈值固定为 medium 阈值的两倍（160 行 / 30 分支）
# 计入分支数的 AST 节点类型
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While,
                ast.ExceptHandler, ast.With, ast.AsyncWith, ast.BoolOp)
# 函数节点类型（含异步函数）
FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

# ===== JS/TS 启发式口径（不构建 AST，规则如下）=====
# JS/TS 源码扩展名
JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}
# 任一行超过该字符数视为压缩/打包产物，整个文件跳过分析并记 warning
MINIFY_LINE_LIMIT = 1000
# 函数起点正则 1：function 声明，如 function foo(
RE_FUNC_DECL = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(")
# 函数起点正则 2：箭头函数赋值，如 const foo = async (a, b) =>
RE_ARROW = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")
# 函数起点正则 3：类/对象方法，行首（可有空格）的 name(...) {
RE_METHOD = re.compile(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")
# 方法正则需排除的关键字，防止 if (...) { 等被误判为函数
JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return",
               "else", "do", "with", "new", "class", "const", "let", "var",
               "typeof", "case", "throw", "await", "yield"}
# 分支关键字（在清洗后的代码文本上计数）
RE_BRANCH_WORD = re.compile(r"\b(if|for|while|case|catch)\b")
# 三元 ?（排除 ?. 可选链与 ?? 空值合并：后随 . 或 ?、或前面是 ? 均不计）
RE_TERNARY = re.compile(r"(?<!\?)\?(?![.?])")


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


def sanitize_js(source: str) -> str:
    """把 JS/TS 源码中的字符串与注释内容替换为空格（换行保留），供配对与计数使用。
    简化规则：字符串支持 ' " ` 三种引号并处理 \\ 转义；注释支持 // 与 /* */；
    模板字符串中的 ${...} 嵌套不还原（按普通字符串处理）。"""
    chars = list(source)
    i, n = 0, len(chars)
    state = None  # None=代码, "'" / '"' / '`'=字符串, "//"=行注释, "/*"=块注释
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""
        if state is None:
            if ch == "/" and nxt == "/":
                state = "//"
                chars[i] = chars[i + 1] = " "
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "/*"
                chars[i] = chars[i + 1] = " "
                i += 2
                continue
            if ch in "'\"`":
                state = ch
                chars[i] = " "
                i += 1
                continue
            i += 1
        elif state == "//":
            if ch == "\n":
                state = None
            else:
                chars[i] = " "
            i += 1
        elif state == "/*":
            if ch == "*" and nxt == "/":
                chars[i] = chars[i + 1] = " "
                i += 2
                state = None
            else:
                if ch != "\n":
                    chars[i] = " "
                i += 1
        else:  # 字符串内
            if ch == "\\":  # 跳过转义序列的下一个字符
                chars[i] = " "
                if i + 1 < n and chars[i + 1] != "\n":
                    chars[i + 1] = " "
                i += 2
                continue
            if ch == state:
                chars[i] = " "
                state = None
            elif ch != "\n":
                chars[i] = " "
            i += 1
    return "".join(chars)


def find_js_functions(lines: list[str]) -> list[tuple[str, int]]:
    """逐行匹配三种函数起点，返回 [(函数名, 起点行号(1基))]。
    每行按 声明→箭头→方法 的顺序取第一个命中；方法正则排除关键字。"""
    found = []
    for lineno, line in enumerate(lines, start=1):
        match = RE_FUNC_DECL.search(line)
        if match is None:
            match = RE_ARROW.search(line)
        if match is None:
            match = RE_METHOD.match(line)
            if match is not None and match.group(1) in JS_KEYWORDS:
                match = None  # 关键字误匹配，丢弃
        if match is not None:
            found.append((match.group(1), lineno))
    return found


def match_braces(clean: str, start: int) -> int:
    """在清洗后的文本上从 start 处的 { 逐字符配对，返回配对 } 的字符下标。
    到 EOF 仍未闭合时返回文本末尾（简化处理，视为函数延伸到文件尾）。"""
    depth = 0
    for i in range(start, len(clean)):
        if clean[i] == "{":
            depth += 1
        elif clean[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(clean) - 1


def count_js_branches(span_text: str) -> int:
    """在清洗后的函数跨度文本上统计分支数：
    关键字 if/for/while/case/catch + && 与 || + 三元 ?（排除 ?. 与 ??）。"""
    count = len(RE_BRANCH_WORD.findall(span_text))
    count += span_text.count("&&") + span_text.count("||")
    count += len(RE_TERNARY.findall(span_text))
    return count


def analyze_js(rel_path: str, source: str) -> tuple[list, dict | None]:
    """对单个 JS/TS 文件做启发式复杂度分析，返回 (issues, warning)。"""
    lines = source.splitlines()
    if any(len(line) > MINIFY_LINE_LIMIT for line in lines):
        # 疑似压缩/打包文件：不做分析
        return [], {"file": rel_path,
                    "warning": f"疑似压缩/打包文件（存在超过 {MINIFY_LINE_LIMIT} 字符的长行），跳过分析"}
    clean = sanitize_js(source)
    clean_lines = clean.splitlines()
    # 每行起始字符下标，用于行号与字符位置互转
    offsets = []
    pos = 0
    for line in clean.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(line)
    issues = []
    for name, lineno in find_js_functions(lines):
        clean_line = clean_lines[lineno - 1] if lineno - 1 < len(clean_lines) else ""
        brace_col = clean_line.find("{")
        if brace_col < 0:
            continue  # 箭头函数单表达式（起点行无 {），跳过
        start_idx = offsets[lineno - 1] + brace_col
        end_idx = match_braces(clean, start_idx)
        end_lineno = clean.count("\n", 0, end_idx) + 1
        func_lines = end_lineno - lineno + 1
        branches = count_js_branches(clean[start_idx:end_idx + 1])
        if func_lines > LINE_THRESHOLD or branches > BRANCH_THRESHOLD:
            # 与 Python 同一判定：超阈值但行数 <=160 且分支 <=30 为 medium，否则 high
            if func_lines > LINE_THRESHOLD * 2 or branches > BRANCH_THRESHOLD * 2:
                severity = "high"
            else:
                severity = "medium"
            issues.append({
                "rule": "complexity",
                "file": rel_path,
                "line": lineno,
                "severity": severity,
                "function": name,
                "lines": func_lines,
                "branches": branches,
                "line_threshold": LINE_THRESHOLD,
                "branch_threshold": BRANCH_THRESHOLD,
                "message": f"函数 {name} 复杂度过高：{func_lines} 行 / {branches} 分支"
                           f"（阈值 {LINE_THRESHOLD} 行 / {BRANCH_THRESHOLD} 分支）",
            })
    return issues, None


def collect(target: Path, inventory: dict) -> dict:
    """按 inventory 的 files 列表逐个解析源码文件，汇总 issues 与 warnings。"""
    files = inventory.get("files")
    if not isinstance(files, list):
        print("错误：inventory JSON 缺少 files 列表", file=sys.stderr)
        sys.exit(1)
    issues: list = []
    warnings: list = []
    for rel in files:
        rel_path = str(rel)
        suffix = Path(rel_path).suffix.lower()
        if suffix != ".py" and suffix not in JS_EXTS:
            continue  # 不支持的扩展名不处理
        try:
            source = (target / rel_path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"错误：无法读取文件 {rel_path}：{exc}", file=sys.stderr)
            sys.exit(1)
        if suffix == ".py":
            file_issues, warning = analyze_source(rel_path, source)
        else:
            file_issues, warning = analyze_js(rel_path, source)
        issues.extend(file_issues)
        if warning is not None:
            warnings.append(warning)
    return {
        "issues": issues,
        "skipped": [],  # JS/TS 已支持启发式分析，无固定跳过项
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="函数复杂度分析（Python AST / JS/TS 启发式）")
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
