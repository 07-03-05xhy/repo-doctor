# 函数复杂度（complexity）

- id：complexity
- 权重：25
- 严重度：行数 >160 或分支 >30 为 high；超过阈值但未达 high 档为 medium
- 类型：script

## 命令

```bash
python scripts/complexity.py {target} --inventory tmp/inventory.json --out tmp/complexity.json
```

Python 文件用 ast 模块解析；JS/TS 文件（.js/.ts/.jsx/.tsx）用启发式解析：识别 function 声明、箭头函数、类方法，以花括号配对确定函数跨度。任一行超过 1000 字符的疑似压缩文件跳过并记入 warnings。

## 判定

- 算问题：函数行数 > 80（end_lineno - lineno + 1）或分支数 > 15（If/For/AsyncFor/While/ExceptHandler/With/AsyncWith/BoolOp 节点总数），记为一条 issue。
- 算误报：行数与分支数均未超过阈值；嵌套函数的分支计入外层函数是既定统计口径，不算误报。
- JS/TS 启发式口径：函数跨度由花括号配对确定；分支数统计 if/for/while/case/catch 关键字与 &&、||、三元 ? 运算符（排除可选链 ?. 与空值合并 ??）；阈值与 Python 相同（行数 >80 或分支 >15 为 medium；行数 >160 或分支 >30 为 high）。

## 忽略规则

- 非 Python/JS/TS 文件（其余扩展名）不参与，输出中记一条 skipped 说明。
- 语法错误无法解析的 Python 文件记入 warnings，不产生 issue。
- 任一行超过 1000 字符的疑似压缩 JS/TS 文件跳过，记入 warnings，不产生 issue。
- JS/TS 启发式可能漏识别动态生成的函数（如 eval 或工厂函数动态拼装的函数），其统计口径与 Python AST 存在差异，属既定限制，不算误报。

## 扣分规则

- 按 severity 扣分：high 每条 5 分、medium 每条 3 分。
- 本项上限 25 分，扣完为止，不出现负分。
- 当源文件数超过 50 时，扣分按 _index.md 的规模归一化规则折算。

## 建议模板

重构 {file} 第 {line} 行的函数：拆分职责或提取子函数，把行数降到 80 行以内、分支降到 15 个以内。

## 误报处理

以下情况不计入 issue：

- 行数 ≤80 且分支 ≤15 的函数
- 语法错误文件（记入 warnings）
- 经人工确认为自动生成代码且不宜修改的函数：汇总时不写入 issues，并在 skipped_rules 中说明
