# Changelog

## v1.1.1 — H3 六大翻车差向量（优先）

### Added
- 六大实测失败模式：无因跳跃、未面对面、法术打空气、切镜换人/瞬移、空间锚缺失、法术击中无反馈
- 降级：`facing_break` / `jump_orphan` / `spell_miss_target` / `identity_drift` / `teleport_cut` / `spell_no_feedback`
- 词表与 `logic_score` 硬检查；种子 T2V+4 / Ref2V+1；链模板 4 条
- `CRITICAL_FAILURE_OPS` 并入 `DEFAULT_OPS`
- 文档：`docs/逻辑链说明.md` §0「H3 常见翻车 → 桥要学的差向量」

### Unchanged
- safetensors 仍为 v1（需本机 H3 CLIP 重训）

## v1.1.0 — 逻辑链 / 高动态家族（BUNNY-inspired）

### Added
- `wushu_bridge/logic_chains.py`：命名因果链模板（打斗完整弧 + 行为连续性）
- 词表：ownership / occlusion / momentum / pursuit / facing / cover / state_carry / ricochet / env_continuity / aerial / handoff
- 降级算子：`ownership`, `occlusion`, `facing`, `momentum`, `pursuit`, `state_carry`, `chain_break`
- 默认档案 `DEFAULT_OPS` = 经典逻辑 ∪ 高动态
- 种子扩写：T2V 8 条、Ref2V 2 条、horde 1 条（缴械、撞墙、遮挡再识别、追击、1v2、湿街追逐等）
- `tools/build_logic_chain_pairs.py` + `models/wushu_bridge/datasets/wushu_pairs_v2_logic_chains.jsonl`
- 文档：`docs/逻辑链说明.md`；`docs/训练流程.md` 增加 v1.1 补训小节
- 编舞轻量导出：`choreography.list_logic_chain_presets()`

### Scoring
- `logic_score.py`：高动态槽位软分、因果链 ≥2 连接词强化、多镜继承加分
- 多镜状态继承：在 `logic_score.py` 加分（不改 h3lint/JS 契约）

### Unchanged
- **未重训** `wushu_bridge_wushu_v1.safetensors` / `wushu_jev_wushu_v1.safetensors`
  （需要用户 ComfyUI 内 MiniMax H3 CLIP 5120-d；见训练流程补训）

### Kept
- `wushu_pairs_v1_pairs.jsonl`（676 对）保留不删
