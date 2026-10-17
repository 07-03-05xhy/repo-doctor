# 扫描完成自检清单

AI 在宣布扫描完成前，必须逐条核对并勾选；任何一条不满足都必须修正后重检。

- [ ] 所有文件路径都来自 inventory 输出（核对方式：result.json 与 report.md 中的路径逐一能在 tmp/inventory.json 的 files 列表中找到）
- [ ] result.json 通过 schema 校验（核对方式：用 jsonschema 对照 schema/result.schema.json 校验通过）
- [ ] score 由 score.py 生成，非手算（核对方式：score 与 grade 字段来自 tmp/scored.json，即 score.py 的输出文件）
- [ ] 每条 issue 有 rule/file/message（核对方式：遍历 result.json 的 issues，三个字段均非空）
- [ ] skipped 规则都写了原因（核对方式：skipped_rules 每项 reason 非空）
- [ ] report.md 包含评分、分布、Top 3、分组列表（核对方式：检查报告中存在"评分构成""问题分布""Top 3 建议""问题明细"四个小节）
- [ ] 未修改目标仓库（核对方式：扫描期间所有写入只在 tmp/ 与 reports/ 下，目标目录无新增或改动）
