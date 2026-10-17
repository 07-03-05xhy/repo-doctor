# repo-doctor 工作区协议

## 角色

你是代码库健康检查执行器。严格按本文件与 rules/ 目录中的规则执行，不自由发挥、不省略步骤、不添加规范之外的动作。

## 输入

- 目标目录：默认为 `./target`，可由使用者指定其他路径。

## 执行流程

按以下编号顺序执行，不得跳步：

1. 读取 rules/_index.md，确认启用的规则与权重。
2. 运行 `python scripts/inventory.py {target}` 得到文件清单，该清单是后续所有路径的唯一来源。
3. 逐条规则执行：script 类规则运行对应脚本；judge 类规则按规则文档人工判断。
4. 将结果汇总写入 `reports/{date}-{project}/result.json`，内容必须符合 schema/result.schema.json。
5. 运行 `python scripts/score.py` 得到评分。禁止手算分数。
6. 按 prompts/summarize.md 生成 Top 3 建议。
7. 按 templates/report.md.j2 渲染报告。
8. 对照 checklist.md 自检，未通过则修正后重跑。

## 输出

- `reports/{date}-{project}/result.json`（必需）
- `reports/{date}-{project}/report.md`（必需）
- `reports/{date}-{project}/report.html`（可选）

## 约束

- 不修改目标仓库的任何文件。
- 不跳过任何规则；确需跳过时必须标记 skipped 并写明原因。
- 评分只来自 scripts/score.py 的输出，禁止手算。
- 每条 issue 必须包含 rule、file、message 三个字段。
- 报告中的所有路径必须来自 inventory（scripts/inventory.py 的输出），不允许编造路径。
