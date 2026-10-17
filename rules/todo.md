# TODO/FIXME 标记（todo）

- id：todo
- 权重：15
- 严重度：不标注（issue 不带 severity 字段，计分时由 score.py 按 medium 处理）
- 类型：script

## 命令

```bash
python scripts/todo_scan.py {target} --inventory tmp/inventory.json --out tmp/todo.json
```

前置条件：先运行 inventory.py 生成 tmp/inventory.json，本脚本只扫描其中的源码文件。

## 判定

- 算问题：源码文件中命中正则 `\b(TODO|FIXME|HACK|XXX)\b[:\s]*(.*)` 的每一行，记为一条 issue。
- 算误报：标记词出现在字符串字面量或文档注释中、实际并非待办事项的情况（纯文本正则无法区分语境）。

## 忽略规则

以下文件由脚本自动跳过，不产生 issue：

- 文件名以 README 开头（不区分大小写）的文件
- 路径中含 docs/ 或 examples/ 目录的文件
- inventory 清单之外的任何文件

## 扣分规则

- 每条 issue 扣 3 分（score.py 对无 severity 的 issue 按 medium 档扣分）。
- 本项上限 15 分，扣完为止，不出现负分。

## 建议模板

处理 {file} 第 {line} 行的遗留标记：确认该待办是否仍有效，完成它或删除标记。

## 误报处理

以下情况不计入 issue：

- README*、docs/、examples/ 中的命中（脚本已自动跳过）
- 经人工确认标记词仅为字符串内容而非待办的命中：汇总时不写入 issues
