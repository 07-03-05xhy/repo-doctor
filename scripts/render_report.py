#!/usr/bin/env python3
"""读取 result.json 与 summarize 输出，渲染 Markdown 报告（优先 jinja2，失败降级内置渲染）。
报告末尾附"修复提示词"小节，由 issues/skipped_rules 确定性生成。
只读取 result.json、summary 与模板文件，不修改任何其他文件。"""
import argparse
import json
import sys
from pathlib import Path

# 阻止导入时生成 __pycache__，保证脚本运行不产生任何文件
sys.dont_write_bytecode = True

# 权重与扣分常量的单一来源是同目录 score.py
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from score import RULE_WEIGHTS, SEVERITY_DEDUCTION
except ImportError as exc:
    print(f"错误：无法从同目录 score.py 导入权重常量：{exc}", file=sys.stderr)
    sys.exit(1)

# 默认模板路径：工作区根的 templates/report.md.j2（与当前工作目录无关）
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "report.md.j2"
# 严重度计数口径：缺失或为 null 计 unmarked
SEVERITY_LEVELS = ("high", "medium", "low")

# 模板上下文共 13 键：project/scanned_at/target/score/grade/rule_rows/severity_counts/
# top_suggestions/issues_by_rule/skipped_rules/inventory/generated_by/fix_prompt

# 修复提示词的固定头（逐字输出，不自由发挥）
FIX_PROMPT_HEADER = (
    "你是代码修复执行器。以下问题由 repo-doctor 扫描产生，请按编号逐条修复。\n"
    "\n"
    "要求：\n"
    "- 只修复下列问题，不做额外重构\n"
    "- 不改变现有功能行为\n"
    "- 每条修复保持最小改动\n"
    "- 修复完成后删除已处理的遗留标记（TODO/FIXME 等）\n"
    "\n"
    "问题清单："
)
# 零 issue 时的整体替代文案
FIX_PROMPT_EMPTY = "本次扫描未发现问题，无需修复。"
# 修复提示词的严重度排序：high > medium > low > 无 severity
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_fix_prompt(issues: list, skipped_rules: list) -> str:
    """从 issues/skipped_rules 确定性生成修复提示词（同输入必同输出）。"""
    if not issues:
        return FIX_PROMPT_EMPTY

    def sort_key(issue: dict) -> tuple:
        # severity 优先；同级按规则权重降序（权重相同按规则名升序；
        # 不在 RULE_WEIGHTS 中的规则排最后按名称升序）；再按 file、line（null 排最后）
        severity = issue.get("severity")
        severity_rank = SEVERITY_ORDER.get(severity, 3)
        rule = str(issue.get("rule") or "")
        if rule in RULE_WEIGHTS:
            rule_key = (0, -RULE_WEIGHTS[rule], rule)
        else:
            rule_key = (1, 0, rule)
        line = issue.get("line")
        line_key = (1, 0) if line is None else (0, line)
        return (severity_rank, *rule_key, str(issue.get("file") or ""), *line_key)

    ordered = sorted((i for i in issues if isinstance(i, dict)), key=sort_key)
    lines = [FIX_PROMPT_HEADER]
    for number, issue in enumerate(ordered, start=1):
        severity = issue.get("severity") or "unmarked"  # 无 severity 的显示口径
        file = str(issue.get("file") or "")
        line = issue.get("line")
        location = f"{file}:{line}" if line is not None else file  # line 为 null 时不带行号
        message = str(issue.get("message") or "")
        entry = f"{number}. [{severity}] {location}（{issue.get('rule')}）：{message}"
        suggestion = issue.get("suggestion")
        if suggestion:  # suggestion 为 null/空时省略"。建议：…"尾巴
            entry += f"。建议：{suggestion}"
        lines.append(entry)
    if skipped_rules:
        # 清单末尾追加跳过规则提示，多条用中文分号分隔
        skipped_text = "；".join(f"{s.get('rule')}（{s.get('reason')}）" for s in skipped_rules)
        lines.append(f"注意：以下规则被跳过，未覆盖：{skipped_text}")
    return "\n".join(lines)


def build_context(result: dict, top_suggestions: list[str]) -> dict:
    """把 result.json 数据加工成模板上下文（全部确定性计算）。"""
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        print("错误：result.json 中的 issues 必须是数组", file=sys.stderr)
        sys.exit(1)

    # 评分构成：每条规则 earned = max(0, weight - 累计扣分)，severity 缺失按 medium
    rule_rows = []
    for rule, weight in RULE_WEIGHTS.items():
        rule_issues = [i for i in issues if isinstance(i, dict) and i.get("rule") == rule]
        deduction = sum(
            SEVERITY_DEDUCTION.get(i.get("severity") or "medium", SEVERITY_DEDUCTION["medium"])
            for i in rule_issues
        )
        rule_rows.append({
            "rule": rule,
            "earned": max(0, weight - deduction),
            "weight": weight,
            "issue_count": len(rule_issues),
        })

    # 问题分布：high/medium/low/unmarked 四类计数
    severity_counts = {"high": 0, "medium": 0, "low": 0, "unmarked": 0}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = issue.get("severity")
        if severity in SEVERITY_LEVELS:
            severity_counts[severity] += 1
        else:
            severity_counts["unmarked"] += 1

    # 按权重表顺序分组的 issue 明细，只保留有 issue 的规则
    issues_by_rule = []
    for rule in RULE_WEIGHTS:
        group = [
            {
                "file": i.get("file"),
                "line": i.get("line"),
                "message": i.get("message"),
                "suggestion": i.get("suggestion"),
            }
            for i in issues
            if isinstance(i, dict) and i.get("rule") == rule
        ]
        if group:
            issues_by_rule.append({"rule": rule, "issues": group})

    inventory = result.get("inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
    skipped_rules = result.get("skipped_rules", [])
    if not isinstance(skipped_rules, list):
        skipped_rules = []

    return {
        "project": result.get("project", ""),
        "scanned_at": result.get("scanned_at", ""),
        "target": result.get("target", ""),
        "score": result.get("score", 0),
        "grade": result.get("grade", ""),
        "rule_rows": rule_rows,
        "severity_counts": severity_counts,
        "top_suggestions": top_suggestions,
        "issues_by_rule": issues_by_rule,
        "skipped_rules": skipped_rules,
        "fix_prompt": build_fix_prompt(issues, skipped_rules),  # 第 13 键：修复提示词
        "inventory": {
            "files": inventory.get("files", 0),
            "source_files": inventory.get("source_files", 0),
        },
        "generated_by": "repo-doctor",  # 固定标识
    }


def render_builtin(context: dict) -> str:
    """内置纯字符串渲染，产出与模板相同的七部分 Markdown 结构。"""
    lines = []
    # 第一部分：项目名 / 扫描时间 / 评分 / 等级
    lines.append(f"# {context['project']} 健康检查报告")
    lines.append("")
    lines.append(f"- 扫描时间：{context['scanned_at']}")
    lines.append(f"- 扫描目标：{context['target']}")
    lines.append(f"- 评分：{context['score']}")
    lines.append(f"- 等级：{context['grade']}")
    lines.append("")
    # 第二部分：评分构成表
    lines.append("## 评分构成")
    lines.append("")
    lines.append("| 规则 | 得分 | 权重 | 问题数 |")
    lines.append("| --- | --- | --- | --- |")
    for row in context["rule_rows"]:
        lines.append(f"| {row['rule']} | {row['earned']} | {row['weight']} | {row['issue_count']} |")
    lines.append("")
    # 第三部分：问题分布
    counts = context["severity_counts"]
    lines.append("## 问题分布")
    lines.append("")
    lines.append(f"- high：{counts['high']}")
    lines.append(f"- medium：{counts['medium']}")
    lines.append(f"- low：{counts['low']}")
    lines.append(f"- 未标记：{counts['unmarked']}")
    lines.append("")
    # 第四部分：Top 3 建议
    lines.append("## Top 3 建议")
    lines.append("")
    if context["top_suggestions"]:
        for suggestion in context["top_suggestions"]:
            lines.append(f"- {suggestion}")
    else:
        lines.append("- 无")
    lines.append("")
    # 第五部分：按规则分组的问题明细
    lines.append("## 问题明细（按规则分组）")
    lines.append("")
    if context["issues_by_rule"]:
        for group in context["issues_by_rule"]:
            lines.append(f"### {group['rule']}")
            lines.append("")
            for issue in group["issues"]:
                line_no = issue["line"] if issue["line"] is not None else "-"
                lines.append(f"- `{issue['file']}:{line_no}` {issue['message']}")
                if issue["suggestion"]:
                    lines.append(f"  - 建议：{issue['suggestion']}")
            lines.append("")
    else:
        lines.append("- 无问题")
        lines.append("")
    # 第六部分：扫描配置与 skipped 规则
    lines.append("## 扫描配置与跳过的规则")
    lines.append("")
    lines.append(f"- 扫描文件数：{context['inventory']['files']}")
    lines.append(f"- 源码文件数：{context['inventory']['source_files']}")
    lines.append(f"- 生成工具：{context['generated_by']}")
    lines.append("")
    lines.append("### 跳过的规则")
    lines.append("")
    if context["skipped_rules"]:
        for skipped in context["skipped_rules"]:
            lines.append(f"- {skipped.get('rule')}：{skipped.get('reason')}")
    else:
        lines.append("- 无")
    lines.append("")
    # 第七部分：修复提示词（text 围栏包裹，可原样发给 AI）
    lines.append("## 修复提示词")
    lines.append("")
    lines.append("把下面这段提示词原样发给 AI，它会按编号逐条修复上述问题：")
    lines.append("")
    lines.append("```text")
    lines.append(context["fix_prompt"])
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def render(context: dict, template_path: Path, use_jinja2: bool) -> str:
    """渲染报告：优先 jinja2（StrictUndefined），降级内置渲染。"""
    template_exists = template_path.is_file()
    jinja2_module = None
    if use_jinja2:
        try:
            import jinja2 as jinja2_module
        except ImportError:
            jinja2_module = None
    if not use_jinja2 or jinja2_module is None or not template_exists:
        # 降级原因输出到 stderr，不影响退出码
        if not use_jinja2:
            reason = "已指定 --no-jinja2"
        elif jinja2_module is None:
            reason = "jinja2 不可用"
        else:
            reason = f"模板文件不存在：{template_path}"
        print(f"提示：{reason}，使用内置渲染", file=sys.stderr)
        return render_builtin(context)

    # jinja2 渲染：StrictUndefined 让模板契约错误直接暴露
    try:
        template_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"错误：无法读取模板文件 {template_path}：{exc}", file=sys.stderr)
        sys.exit(1)
    try:
        env = jinja2_module.Environment(undefined=jinja2_module.StrictUndefined)
        template = env.from_string(template_text)
        return template.render(**context)
    except jinja2_module.exceptions.UndefinedError as exc:
        print(f"错误：模板变量未定义（契约不一致）：{exc}", file=sys.stderr)
        sys.exit(1)
    except jinja2_module.exceptions.TemplateError as exc:
        print(f"错误：模板渲染失败：{exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="渲染 repo-doctor Markdown 报告")
    parser.add_argument("result", help="扫描结果 result.json 文件路径")
    parser.add_argument("--summary", help="summarize 输出的 Top 3 建议文件（可选）")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                        help="Jinja2 模板路径（缺省为工作区 templates/report.md.j2）")
    parser.add_argument("--out", help="输出 Markdown 文件路径（缺省时打印到 stdout）")
    parser.add_argument("--no-jinja2", action="store_true", help="不使用 jinja2，强制内置渲染")
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

    # Top 3 建议：summary 文件的每一非空行；未提供则为空数组
    top_suggestions: list[str] = []
    if args.summary:
        try:
            summary_text = Path(args.summary).read_text(encoding="utf-8-sig")
        except OSError as exc:
            print(f"错误：无法读取建议文件 {args.summary}：{exc}", file=sys.stderr)
            sys.exit(1)
        top_suggestions = [line.strip() for line in summary_text.splitlines() if line.strip()]

    context = build_context(result, top_suggestions)
    text = render(context, Path(args.template), not args.no_jinja2)

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
