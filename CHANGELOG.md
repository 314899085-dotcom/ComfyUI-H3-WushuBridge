# Changelog

## Docs — HF 仓重命名 + 详细模型卡

### Changed
- Hugging Face 仓由 `Jojocodex/h3-wushu-bridge-weights` **重命名**为 [`Jojocodex/ComfyUI-H3-WushuBridge`](https://huggingface.co/Jojocodex/ComfyUI-H3-WushuBridge)（旧名重定向）
- HF 现托管 **完整插件 + 权重**；根 README 换为详细双语模型卡（插件简介 / 权重简介 / 安装 / XYZ / CRITICAL）
- GitHub README：权重仓库与安装来源改写；删除对已移除 cloud / v1 pair 文件的下载指引；GitHub clone URL 统一为 `Jojocodex-dotcom`
- `tools/setup_laya.py`：`OURS_REPO` 指向新仓名

## v1.1.2 — XYZ 坐标锁定（角色站位）

### Added
- 坐标约定：相机相对地面系 X 左(−)/右(+)、Y 近(−)/远(+)、Z 离地（0=站立）；单位「步」
- `wushu_bridge/xyz_coords.py`：解析 / 格式化 / 一致性 / 剥离 / 扰动
- 词表 `XYZ_LOCK_*`；`SPATIAL_OPEN` 纳入 xyz 短语；槽位 `xyz_lock`
- 降级 CRITICAL：`xyz_drift`（权重 1.2）；`teleport_cut` 顺带剥离/扰动 xyz
- 评分：`xyz-lock`（权重 1.3）；`spatial-lock` 说明优先 xyz 锚
- 逻辑链：`xyz_coord_duel`；`face_to_face_duel` / `cross_shot_identity_space` 补 `@xyz=`
- 种子：T2V 中英各 +1，Ref2V +1；既有面对面/切镜种子补 xyz
- 文档：`docs/逻辑链说明.md` §0 与「XYZ 坐标约定」

### Unchanged
- safetensors 仍为 v1（需本机 H3 CLIP 重训）

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
