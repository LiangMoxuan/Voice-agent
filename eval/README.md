# eval/ —— 评测与 RSI（C 维护）

## 三集物理隔离（不许混用）

| 集合 | 数量 | 谁能读 | 优化器能否读取 |
|---|---|---|---|
| dev_set | ≥30 条 | 全组 | 可以 |
| fixed_baseline | ≥20 条 | 全组 | **禁止** |
| holdout_set | ≥20 条 | 只有 runner | **禁止** |

## 计划文件

```
eval/
├── cases/             # dev_set 用例 yaml（Day12 起填）
├── cases_holdout/     # holdout，只给 runner 读
├── generator.py       # 用 LLM 按 persona 批量造对抗用例
├── runner.py          # 文本级驱动 Agent，快且稳
├── judge.py           # 规则分 + LLM-as-Judge 分（两者都报）
├── attribution.py     # 失败聚类归因（10 个标签）
├── optimizer.py       # 受约束优化（只许改话术/追问/few-shot/阈值）
├── versions.py        # 版本 + 回归 + 回滚
└── versions/          # v1/v2/bundle.json、scores_baseline.md、registry.json
```

## 发布判定（三条缺一不可）

**规则指标不降 + holdout 不降 + Judge 升** → 才允许 `registry.current = v(n+1)`；
否则标 `rejected`，线上仍跑旧版本。回滚 = 改一行 registry。
