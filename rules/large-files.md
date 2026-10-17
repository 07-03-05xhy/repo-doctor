# 大文件（large_files）

- id：large_files
- 权重：15
- 严重度：按行数分级：501–1000 行为 low；1001–2000 行为 medium；2001 行及以上为 high
- 类型：script

## 命令

```bash
python scripts/inventory.py {target} --out tmp/inventory.json
```

行数来源：inventory.json 的 lines 字段（仅对 ≤2MB 的源码文件统计）。对 lines 中每个条目与阈值比较即得 issue，无需其他脚本。

## 判定

- 算问题：lines 字段中行数超过 500 行的源码文件，每个文件记为一条 issue，severity 按上述行数分级。
- 算误报：行数恰为 500 行及以下的文件；未出现在 lines 字段中的文件（二进制或 >2MB，未统计行数）不构成本规则的 issue。

## 忽略规则

- 二进制文件与超过 2MB 的文件：无行数统计，不参与本规则判定。
- 非源码文件（不在 inventory 的源码扩展名范围内）：不参与。

## 扣分规则

- 按 severity 扣分：high 每条 5 分、medium 每条 3 分、low 每条 1 分。
- 本项上限 15 分，扣完为止，不出现负分。
- 当源文件数超过 50 时，扣分按 _index.md 的规模归一化规则折算。

## 建议模板

拆分 {file}：该文件超过 500 行阈值，按职责拆分为多个模块以降低维护成本。（本规则 issue 的 line 字段固定为 null，模板不使用 {line} 占位符。）

## 误报处理

以下情况不计入 issue：

- 行数 ≤500 的文件
- 二进制文件与 >2MB 的文件（无行数统计）
- 经人工确认行数虽超阈值但属于自动生成且不宜拆分的文件：汇总时不写入 issues，并在 skipped_rules 中说明
