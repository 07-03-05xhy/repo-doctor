# 函数复杂度（complexity）

- id：complexity
- 权重：25
- 严重度：行数 >160 或分支 >30 为 high；超过阈值但未达 high 档为 medium
- 类型：script

## 命令

```bash
python scripts/complexity.py {target} --inventory tmp/inventory.json --out tmp/complexity.json
```

仅解析 Python 文件（ast 模块）；JS/TS 文件本阶段不支持，输出中以 skipped 说明。

## 判定

- 算问题：函数行数 > 80（end_lineno - lineno + 1）或分支数 > 15（If/For/AsyncFor/While/ExceptHandler/With/AsyncWith/BoolOp 节点总数），记为一条 issue。
- 算误报：行数与分支数均未超过阈值；嵌套函数的分支计入外层函数是既定统计口径，不算误报。

## 忽略规则

- 非 Python 文件（.js/.ts/.jsx/.tsx）不参与，输出中记一条 skipped 说明。
- 语法错误无法解析的文件记入 warnings，不产生 issue。

## 扣分规则

- 按 severity 扣分：high 每条 5 分、medium 每条 3 分。
- 本项上限 25 分，扣完为止，不出现负分。

## 建议模板

重构 {file} 第 {line} 行的函数：拆分职责或提取子函数，把行数降到 80 行以内、分支降到 15 个以内。

## 误报处理

以下情况不计入 issue：

- 行数 ≤80 且分支 ≤15 的函数
- 语法错误文件（记入 warnings）
- 经人工确认为自动生成代码且不宜修改的函数：汇总时不写入 issues，并在 skipped_rules 中说明
