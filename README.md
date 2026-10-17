# repo-doctor-workspace

## 这是什么

一个 AI 工作区规范包，不是 CLI 程序。把整个文件夹作为 AI 工作区打开，AI 读取 WORKSPACE.md 后会按规范扫描目标仓库并产出健康检查报告。脚本只做确定性计算（清单统计、规则命中、扣分汇总、报告渲染），评分只能来自 scripts/score.py，禁止 AI 手算。

## 目录结构

```
repo-doctor-workspace/
├─ WORKSPACE.md      # AI 执行协议：角色、输入、8 步流程、输出与约束
├─ AGENTS.md         # 入口声明：读取并严格遵守 WORKSPACE.md
├─ rules/            # 规则文档：_index.md 索引 + 每条规则的判定/扣分/建议规范
├─ prompts/          # 提示词：扫描约束、Top 3 生成规范、修复建议约束
├─ scripts/          # 确定性脚本（7 个）：
│  ├─ inventory.py    # 生成文件清单，是所有路径的唯一来源
│  ├─ todo_scan.py    # TODO/FIXME 等遗留标记扫描
│  ├─ complexity.py   # 函数复杂度统计（行数与分支数）
│  ├─ test_map.py     # 测试缺失检测（源文件与测试文件名映射）
│  ├─ deps_check.py   # 依赖过期检查（支持 --offline）
│  ├─ score.py        # 汇总扣分并输出评分与等级
│  └─ render_report.py # 按模板渲染最终报告
├─ schema/           # result.schema.json：result.json 的结构校验
├─ templates/        # report.md.j2：报告模板（Jinja2）
├─ reports/          # 扫描产物输出目录（按 date-project 归档）
├─ examples/         # 示例项目（demo-project / bad-project）
├─ checklist.md      # 扫描完成前的自检清单
└─ README.md         # 本文件：面向使用者的说明
```

## 如何使用

### Claude Code

1. 把本文件夹作为工作区打开。
2. 把要检查的目标仓库放到 ./target（或在对话中直接指定路径）。
3. 对 AI 说："阅读 WORKSPACE.md 并执行扫描。"

### Codex

1. 把本文件夹作为项目根目录打开。
2. 把要检查的目标仓库放到 ./target（或在对话中直接指定路径）。
3. 让 AI"阅读 WORKSPACE.md 并执行扫描"。

### Cursor

1. 把本文件夹作为工作区打开。
2. 把要检查的目标仓库放到 ./target（或在对话中直接指定路径）。
3. 在对话中让 AI"阅读 WORKSPACE.md 并执行扫描"。

## 如何新增一条规则

1. 在 rules/ 下新建规则文档，参照 todo.md 的六节格式（命令/判定/忽略规则/扣分规则/建议模板/误报处理）。
2. 如需脚本，在 scripts/ 下新增确定性脚本，并在规则文档的"命令"一节中原样引用调用方式。
3. 在 rules/_index.md 的表格中登记该规则并分配权重，保持全部权重合计为 100。
4. 在 scripts/score.py 的 RULE_WEIGHTS 中加入同名规则的权重。
5. 重跑示例项目，确认总分与报告输出正常。

## 如何跑示例

让 AI 对 examples/demo-project（正常小项目）或 examples/bad-project（故意埋问题的项目）执行 WORKSPACE.md 的完整流程即可；也可以手动依次运行 scripts/ 下的脚本，查看 tmp/ 中的中间产物。bad-project 埋入了大量问题，预期得分低于 60（F 档）。
