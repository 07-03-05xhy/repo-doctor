# 测试缺失（tests）

- id：tests
- 权重：30
- 严重度：medium
- 类型：script

## 命令

```bash
python scripts/test_map.py {target} --inventory tmp/inventory.json --out tmp/tests.json
```

只做文件名映射：源文件 <前缀>/name.py 的候选测试为 tests/test_name.py 或 tests/<子路径>/test_name.py，不读取任何测试内容。

## 判定

- 算问题：参与检查的 Python 源文件没有任何候选测试文件存在，记为一条 issue（severity 为 medium，line 为 null）。
- 算误报：任一候选测试文件已存在。

## 忽略规则

- tests/ 目录下的文件、test_ 开头的文件、__init__.py：不参与检查。
- 非 Python 文件：本规则不覆盖。

## 扣分规则

- 每条缺失（一个无测试的源文件）按 medium 扣 3 分。
- 本项上限 30 分，扣完为止，不出现负分。

## 建议模板

为 {file} 补充测试：新建对应的 tests/test_*.py 并覆盖主要分支。（本规则 issue 的 line 字段固定为 null，模板不使用 {line} 占位符。）

## 误报处理

以下情况不计入 issue：

- 已有候选测试文件的源文件
- __init__.py、test_*.py、tests/ 目录下文件
- 经人工确认为一次性脚本或入口文件、无需测试的：汇总时不写入 issues，并在 skipped_rules 中说明
