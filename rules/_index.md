# 规则索引

| 规则 | 文件 | 类型 | 权重 | 是否启用 |
|---|---|---|---|---|
| TODO/FIXME 标记 | todo.md | script | 15 | 启用 |
| 函数复杂度 | complexity.md | script | 25 | 启用 |
| 测试缺失 | tests.md | script | 30 | 启用 |
| 依赖过期 | deps.md | script | 15 | 启用 |
| 大文件 | large-files.md | script | 15 | 启用 |

权重合计：100。

## 规模归一化

- 常量 SCALE_REFERENCE=50。
- 源文件数 N ≤ 50 时，各规则扣分口径不变。
- N > 50 时，每条 issue 的扣分乘以 50/N（按问题密度折算），每条规则的扣分合计四舍五入取整。
- 归一化由 scripts/score.py 统一执行，各规则脚本不受影响。
