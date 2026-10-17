#!/usr/bin/env python3
"""读取 result.json，按固定权重与严重度扣分规则计算总分和等级，补充 score/grade 后输出。
只做确定性计分，不读取除输入 result.json 之外的任何文件，不修改任何文件。"""
import argparse
import json
import sys
from pathlib import Path

# 各规则的初始权重分
RULE_WEIGHTS = {"todo": 15, "complexity": 25, "tests": 30, "deps": 15, "large_files": 15}
# 各严重度的扣分值
SEVERITY_DEDUCTION = {"high": 5, "medium": 3, "low": 1}
# 等级阈值（下限闭区间）：90+→A、80-89→B、70-79→C、60-69→D、<60→F（不出现 E）
GRADE_THRESHOLDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]


def grade_of(total: int) -> str:
    """按阈值把总分映射为等级字母。"""
    for threshold, grade in GRADE_THRESHOLDS:
        if total >= threshold:
            return grade
    return "F"


def main() -> None:
    parser = argparse.ArgumentParser(description="对 result.json 计分并补充 score/grade 字段")
    parser.add_argument("result", help="扫描结果 result.json 文件路径")
    parser.add_argument("--out", help="输出 JSON 文件路径（缺省时打印到 stdout）")
    args = parser.parse_args()

    try:
        # 用 utf-8-sig 读取，兼容带 BOM 的手写 JSON
        result = json.loads(Path(args.result).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        print(f"错误：无法读取结果文件 {args.result}：{exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"错误：结果文件不是合法 JSON：{exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(result, dict):
        print("错误：结果文件顶层必须是 JSON 对象", file=sys.stderr)
        sys.exit(1)

    issues = result.get("issues", [])
    if not isinstance(issues, list):
        print("错误：结果文件中的 issues 必须是数组", file=sys.stderr)
        sys.exit(1)

    # 每个规则从满分（权重）开始，按 issue 严重度扣分
    rule_scores = dict(RULE_WEIGHTS)
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        rule = issue.get("rule")
        if rule not in RULE_WEIGHTS:
            continue  # 未知规则一律忽略
        severity = issue.get("severity", "medium")  # 缺失时按 medium 计
        deduction = SEVERITY_DEDUCTION.get(severity, SEVERITY_DEDUCTION["medium"])
        rule_scores[rule] = max(0, rule_scores[rule] - deduction)  # 每项最低 0 分

    total = sum(rule_scores.values())
    # 在原 dict 上补充/覆盖 score 和 grade，其余字段原样保留
    result["score"] = total
    result["grade"] = grade_of(total)

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
