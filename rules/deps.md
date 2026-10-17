# 依赖过期（deps）

- id：deps
- 权重：15
- 严重度：主版本落后 1 个为 medium；落后 2 个及以上为 high；未锁定版本为 low
- 类型：script

## 命令

```bash
python scripts/deps_check.py {target} --inventory tmp/inventory.json --out tmp/deps.json
```

离线环境必须改用 `--offline`，此时整条规则标记 skipped（不发起网络请求）。在线时查询 PyPI / npm registry，单次请求超时 5 秒，失败自动降级为 warnings。

## 判定

- 算问题：依赖的最新主版本号高于当前主版本号；或依赖未锁定版本（记 low）。
- 算误报：主版本号相同（次版本或修订号差异不记分）。

## 忽略规则

- --offline 模式：整条规则 skipped，不产生 issue。
- 查询失败的包：记入 warnings，不产生 issue。

## 扣分规则

- 按 severity 扣分：high 每条 5 分、medium 每条 3 分、low 每条 1 分。
- 本项上限 15 分，扣完为止，不出现负分。

## 建议模板

升级 {file} 中的过期依赖到最新主版本，并回归验证兼容性。（本规则 issue 的 line 字段固定为 null，模板不使用 {line} 占位符。）

## 误报处理

以下情况不计入 issue：

- 主版本号相同的依赖
- 查询失败进入 warnings 的依赖
- 经人工确认为有意锁定旧主版本的依赖：汇总时不写入 issues，并在 skipped_rules 中说明
