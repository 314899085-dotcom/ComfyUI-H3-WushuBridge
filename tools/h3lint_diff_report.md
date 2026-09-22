# h3lint 差分验证报告：JS 原版 vs Python 移植版

- JS 源：`D:\wushulong\H3武斗模拟器-v9.12\h3lint.js`（h3lint-0.3，Node v24.18.0）
- JS 依赖：`D:\wushulong\H3武斗模拟器-v9.12\sim3d\combat-logic.js`（fight-logic-0.2，已随移植内置到 `wushu_bridge/lint/_combat_logic.py`）
- Python：`wushu_bridge/lint/h3lint.py`（VERSION=h3lint-0.3）
- 语料：`tools/h3lint_cases.json`，61 条（`python tools/build_h3lint_cases.py` 生成）
- JS 侧导出键：`AIR_WORDS`, `BASE_SECTIONS`, `BLOOD`, `DIMENSIONS`, `EMPTY_WORDS`, `IDLE_OPEN`, `LEGACY_FIELDS`, `METAL_SOUND`, `REF_SECTIONS`, `SLOWMO`, `TELEPORT`, `VERSION`, `check`, `diagnose`, `diagnoseReport`, `report`

## 总览

| 指标 | 结果 | 验收线 | 判定 |
|---|---|---|---|
| 用例数 | 61 | ≥ 30 | PASS |
| score 最大绝对差 | 15 | ≤ 2 | FAIL |
| score 差值 ≤2 的用例 | 47/61 | 全部 | FAIL |
| grade 一致率 | 77.0% (47/61) | ≥ 90% | FAIL |
| error 级 id 集合完全一致 | 47/61 | 全部 | FAIL |
| 全部 id 集合完全一致 | 47/61 | 参考项 | 见下表 |
| stats 完全一致 | 47/61 | 参考项 | 见下表 |
| report() 文本完全一致（含 msg/hint/at） | 47/61 | 参考项 | 见下表 |
| diagnose_report() 文本完全一致 | 47/61 | 参考项 | 见下表 |

## 逐条结果

| 用例 | 说明 | JS | Py | Δ | JS grade | Py grade | error 集合 | id 差异 |
|---|---|---|---|---|---|---|---|---|
| `ok-base-t2va` | 合格文生视频稿：三段壳齐全、3 镜、时间码规范、双人同框 | 100 | 100 | 0 | A | A | 一致 | — |
| `ok-ref2va` | 合格多参考图稿：六段壳齐全、<Subject N>/<Picture N> 对称 | 100 | 100 | 0 | A | A | 一致 | — |
| `ok-dialogue` | 合格对白稿：<d> 有语言标签、说话人编号在 <d> 外 | 85 | 100 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `missing-fields` | 缺 overall_soundscape / non_diegetic_music 两个基础字段 | 70 | 70 | 0 | C | C | 一致 | — |
| `missing-main-field` | 缺基础模式主字段 integrated_multimodal_description | 85 | 85 | 0 | B | B | 一致 | — |
| `design-mode` | design 模式（第1步设计稿）：不查官方三段壳，其余检查照旧 | 99 | 99 | 0 | A | A | 一致 | — |
| `no-shot` | 通篇没有 [Shot N] 分镜 | 85 | 85 | 0 | B | B | 一致 | — |
| `shot-many-error` | 6 镜以上：切得太碎（error） | 84 | 84 | 0 | B | B | 一致 | — |
| `shot-many-warn` | 4 镜：偏多（warn） | 95 | 95 | 0 | A | A | 一致 | — |
| `shot1-timecode` | [Shot 1] 带了时间码（官方规定第一镜不写） | 95 | 95 | 0 | A | A | 一致 | — |
| `timecode-order` | 第二镜时间码大于第三镜：不严格递增 | 85 | 85 | 0 | B | B | 一致 | — |
| `timecode-range-over` | 最后一个切镜时间不小于片长 | 95 | 95 | 0 | A | A | 一致 | — |
| `timecode-range-info` | 最后一个切镜时间不到片长的 35%（info） | 99 | 99 | 0 | A | A | 一致 | — |
| `slowmo` | 慢动作/定格类词出现 4 种（>2） | 95 | 95 | 0 | A | A | 一致 | — |
| `start-slow` | 开场 0~0.5 秒写了对峙空转 | 95 | 95 | 0 | A | A | 一致 | — |
| `beat-density` | 每镜平均句数不足 1.5（一镜装不满） | 99 | 99 | 0 | A | A | 一致 | — |
| `empty-words` | 空泛强度词：极快 / 激烈 / 爆发 | 85 | 85 | 0 | B | B | 一致 | — |
| `neg-words` | 正文出现否定式措辞（不要/禁止） | 99 | 99 | 0 | A | A | 一致 | — |
| `blood` | 血腥/致命直述：喷血 | 95 | 95 | 0 | A | A | 一致 | — |
| `length` | 长度超过 maxLen 红线 | 95 | 95 | 0 | A | A | 一致 | — |
| `scenario-hint` | 正文没有出现情景名（追逐战） | 99 | 99 | 0 | A | A | 一致 | — |
| `placeholder-var` | 未替换的 {{变量}} 占位符 | 85 | 85 | 0 | B | B | 一致 | — |
| `placeholder-todo` | 残留 TODO 标记 | 85 | 85 | 0 | B | B | 一致 | — |
| `placeholder-ruleblock` | 残留【特效等级】规则段（占位符＋规则段双报） | 80 | 80 | 0 | B | B | 一致 | — |
| `ruleblock-only` | 正文里出现【镜头规则】这类规则段（仅 ruleblock） | 95 | 95 | 0 | A | A | 一致 | — |
| `move-codebook` | 定义清单式写法「招式A：…」 | 90 | 90 | 0 | A | A | 一致 | — |
| `move-label-leak` | 用编号指代招式（使用招式A） | 80 | 95 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `move-first-use` | 招式名被引用两次但首现没写效果 | 95 | 95 | 0 | A | A | 一致 | — |
| `effect-unanchored` | 出现特效词但没有来源与落点 | 95 | 95 | 0 | A | A | 一致 | — |
| `effect-subject` | Ref2VA 里反复出现的特效没有定义成 <Subject N> | 99 | 99 | 0 | A | A | 一致 | — |
| `tier-inner` | 5 级高手却看不到任何内力外放 | 95 | 95 | 0 | A | A | 一致 | — |
| `tier-inner-shape` | 7 级只有「内力一震」没有气劲的形 | 99 | 99 | 0 | A | A | 一致 | — |
| `tier-cataclysm` | 9 级绝世档没有天地级异象 | 99 | 99 | 0 | A | A | 一致 | — |
| `air-unsupported` | 写了腾空但全篇没有借力依据 | 95 | 95 | 0 | A | A | 一致 | — |
| `teleport` | 出现瞬移 / 闪现 | 90 | 90 | 0 | A | A | 一致 | — |
| `sound-metal` | 双方徒手却出现剑鸣 | 85 | 85 | 0 | B | B | 一致 | — |
| `both-fighters` | 第 2 镜只提到一名角色 | 95 | 95 | 0 | A | A | 一致 | — |
| `name-mix` | 同时出现「角色A」与角色真名 | 95 | 95 | 0 | A | A | 一致 | — |
| `no-subject` | 有长句看不出主语 | 80 | 95 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `cut-continuity` | 第 2/3 镜开头没有交代接续位置 | 90 | 90 | 0 | A | A | 一致 | — |
| `cut-identity` | 切镜后没有重申「还是这两人」 | 98 | 98 | 0 | A | A | 一致 | — |
| `fight-no-counter` | 全文没有任何格挡/闪避/反击的回应动作 | 85 | 85 | 0 | B | B | 一致 | — |
| `fight-no-causal` | 因果连接词不足 2 个 | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `fight-no-filler` | 没有任何间隙动作（不会走步换架） | 70 | 70 | 0 | C | C | 一致 | — |
| `fight-idle` | 出现静止却没有写原因与动作 | 55 | 70 | 15 | D | C | **不一致** | 仅JS:fight-purposeless-action |
| `fight-filler-sparse` | 4 镜只有三处间隙动作（每镜不到一处） | 90 | 90 | 0 | A | A | 一致 | — |
| `d-unclosed` | <d> 没有闭合 | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `d-lang` | <d> 内缺少语言标签 | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `speaker-before-d` | 台词前面没有说话人编号 (S1) | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `speaker-first` | 第一个出现的说话人是 (S2) | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `voiceover-lips` | 画外音没有紧跟「嘴唇保持不动」 | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `voiceover-ok` | 画外音写法正确（应当没有对白相关 error） | 85 | 100 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `scenetrans-pair` | <scenetrans> 出现奇数次 | 80 | 95 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `cutoff-hint` | 最后一句台词没有收尾标点，像被片尾截断 | 84 | 99 | 15 | B | A | **不一致** | 仅JS:fight-purposeless-action |
| `sound-dialogue-repeat` | overall_soundscape 里重复了台词 | 70 | 85 | 15 | C | B | **不一致** | 仅JS:fight-purposeless-action |
| `ref-missing-sections` | Ref2VA 缺 summary / retention_analysis | 70 | 70 | 0 | C | C | 一致 | — |
| `ref-legacy-field` | 用了旧字段名 preservation_analysis | 80 | 80 | 0 | B | B | 一致 | — |
| `ref-main-field` | Ref2VA 里用了基础模式主字段 | 80 | 80 | 0 | B | B | 一致 | — |
| `ref-subject-missing` | 没有 <Subject N> 标签 | 95 | 95 | 0 | A | A | 一致 | — |
| `ref-tags-mismatch` | Subject 与 Picture 标签数量不一致 | 99 | 99 | 0 | A | A | 一致 | — |
| `ref-recast` | 出现「换脸」这类否定说法 | 99 | 99 | 0 | A | A | 一致 | — |

## 差异明细

### `ok-dialogue` — 合格对白稿：<d> 有语言标签、说话人编号在 <d> 外
- JS: score=85 grade=B items=fight-purposeless-action
- Py: score=100 grade=A items=（无）
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 362, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- Py stats: `{"length": 362, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 0, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 B（85/100）｜长度 362 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（100/100）｜长度 362 字，分镜 2 个，时间码 1 处
必改 0｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✓打斗连贯性
没有发现问题：结构、节奏、措辞、声音、物理、一致性与安全各项都过关。
```
- diagnose_report() 文本不一致

### `move-label-leak` — 用编号指代招式（使用招式A）
- JS: score=80 grade=B items=fight-purposeless-action, move-label-leak
- Py: score=95 grade=A items=move-label-leak
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 510, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 1, "warns": 1, "infos": 0}`
- Py stats: `{"length": 510, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 0, "warns": 1, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 B（80/100）｜长度 510 字，分镜 3 个，时间码 2 处
必改 1｜建议 1｜提示 0
八维：!内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
! 建议  用编号指代招式（如「使用招式A」）
      → 改成把招式名与效果写出来；编号指代会让模型把它当成画面文字，或干脆出一记普通攻击。
✗ 必改  有 1 处动作没写目的（guard:格挡）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（95/100）｜长度 510 字，分镜 3 个，时间码 2 处
必改 0｜建议 1｜提示 0
八维：!内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✓打斗连贯性
! 建议  用编号指代招式（如「使用招式A」）
      → 改成把招式名与效果写出来；编号指代会让模型把它当成画面文字，或干脆出一记普通攻击。
```
- diagnose_report() 文本不一致

### `no-subject` — 有长句看不出主语
- JS: score=80 grade=B items=fight-purposeless-action, no-subject
- Py: score=95 grade=A items=no-subject
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 522, "shots": 3, "sentences": 8, "timecodes": 2, "errors": 1, "warns": 1, "infos": 0}`
- Py stats: `{"length": 522, "shots": 3, "sentences": 8, "timecodes": 2, "errors": 0, "warns": 1, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 B（80/100）｜长度 522 字，分镜 3 个，时间码 2 处
必改 1｜建议 1｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  !人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
! 建议  有 1 句看不出主语（雨水顺着屋檐落下，地面反光刺眼…）
      → 每句都要点名是谁做的（谁出招、谁挨打、谁位移）。
✗ 必改  有 1 处动作没写目的（attack:刺）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（95/100）｜长度 522 字，分镜 3 个，时间码 2 处
必改 0｜建议 1｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  !人物真实感  ✓风格一致性  ✓对白与说话人  ✓打斗连贯性
! 建议  有 1 句看不出主语（雨水顺着屋檐落下，地面反光刺眼…）
      → 每句都要点名是谁做的（谁出招、谁挨打、谁位移）。
```
- diagnose_report() 文本不一致

### `fight-no-causal` — 因果连接词不足 2 个
- JS: score=70 grade=C items=fight-no-causal-chain, fight-purposeless-action
- Py: score=85 grade=B items=fight-no-causal-chain
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 500, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 500, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 500 字，分镜 3 个，时间码 2 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  因果连接词只有 0 个，看不出上一拍的结果与下一拍的起因
      → 用「借这个空档／因此／顺势」把拍与拍连起来。
✗ 必改  有 7 处动作没写目的（attack:扫、guard:格挡、move:逼近、move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 500 字，分镜 3 个，时间码 2 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  因果连接词只有 0 个，看不出上一拍的结果与下一拍的起因
      → 用「借这个空档／因此／顺势」把拍与拍连起来。
```
- diagnose_report() 文本不一致

### `fight-idle` — 出现静止却没有写原因与动作
- JS: score=55 grade=D items=fight-idle-unexplained, fight-no-causal-chain, fight-purposeless-action
- Py: score=70 grade=C items=fight-idle-unexplained, fight-no-causal-chain
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 506, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 3, "warns": 0, "infos": 0}`
- Py stats: `{"length": 506, "shots": 3, "sentences": 7, "timecodes": 2, "errors": 2, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 D（55/100）｜长度 506 字，分镜 3 个，时间码 2 处
必改 3｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  因果连接词只有 0 个，看不出上一拍的结果与下一拍的起因
      → 用「借这个空档／因此／顺势」把拍与拍连起来。
✗ 必改  出现「不动、纹丝不动」却没有写原因与动作
      → 要么删掉静止，要么写明原因（受击硬直／被压住兵器／换架）并把它写成动作。
✗ 必改  有 7 处动作没写目的（attack:扫、guard:格挡、move:逼近、move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 C（70/100）｜长度 506 字，分镜 3 个，时间码 2 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  因果连接词只有 0 个，看不出上一拍的结果与下一拍的起因
      → 用「借这个空档／因此／顺势」把拍与拍连起来。
✗ 必改  出现「不动、纹丝不动」却没有写原因与动作
      → 要么删掉静止，要么写明原因（受击硬直／被压住兵器／换架）并把它写成动作。
```
- diagnose_report() 文本不一致

### `d-unclosed` — <d> 没有闭合
- JS: score=70 grade=C items=d-unclosed, fight-purposeless-action
- Py: score=85 grade=B items=d-unclosed
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 357, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 357, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 357 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  <d> 与 </d> 数量不等（1/0）
      → 每句台词都要闭合：<d>[Chinese] 原句</d>；漏闭合会把后面的正文吃进台词里。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 357 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  <d> 与 </d> 数量不等（1/0）
      → 每句台词都要闭合：<d>[Chinese] 原句</d>；漏闭合会把后面的正文吃进台词里。
```
- diagnose_report() 文本不一致

### `d-lang` — <d> 内缺少语言标签
- JS: score=70 grade=C items=d-lang, fight-purposeless-action
- Py: score=85 grade=B items=d-lang
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 352, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 352, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 352 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  第 1 句 <d> 内缺少语言标签
      → 官方要求 <d> 内只放语言标签与台词原文（<d>[Chinese] 你来了。</d>），身份与动作写在 <d> 外面。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 352 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  第 1 句 <d> 内缺少语言标签
      → 官方要求 <d> 内只放语言标签与台词原文（<d>[Chinese] 你来了。</d>），身份与动作写在 <d> 外面。
```
- diagnose_report() 文本不一致

### `speaker-before-d` — 台词前面没有说话人编号 (S1)
- JS: score=70 grade=C items=fight-purposeless-action, speaker-before-d
- Py: score=85 grade=B items=speaker-before-d
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 357, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 357, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 357 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  1 句台词前面没有说话人编号 (S1)/(S2)
      → 把身份与编号写在 <d> 外面：the grey-bearded man with a low, raspy voice (S1) says: <d>[Chinese] …</d>。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 357 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  1 句台词前面没有说话人编号 (S1)/(S2)
      → 把身份与编号写在 <d> 外面：the grey-bearded man with a low, raspy voice (S1) says: <d>[Chinese] …</d>。
```
- diagnose_report() 文本不一致

### `speaker-first` — 第一个出现的说话人是 (S2)
- JS: score=70 grade=C items=fight-purposeless-action, speaker-first
- Py: score=85 grade=B items=speaker-first
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 362, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 362, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 362 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  第一个出现的说话人是 (S2)，应为 (S1)
      → 编号从 (S1) 起、全片固定；从不发声的角色不给编号。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 362 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  第一个出现的说话人是 (S2)，应为 (S1)
      → 编号从 (S1) 起、全片固定；从不发声的角色不给编号。
```
- diagnose_report() 文本不一致

### `voiceover-lips` — 画外音没有紧跟「嘴唇保持不动」
- JS: score=70 grade=C items=fight-purposeless-action, voiceover-lips
- Py: score=85 grade=B items=voiceover-lips
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 389, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 389, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 389 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  1 处画外音没有紧跟"嘴唇保持不动"
      → 官方写法：… says in an off-screen voiceover: <d>[Language] …</d> while his lips remain completely closed.
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 389 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  1 处画外音没有紧跟"嘴唇保持不动"
      → 官方写法：… says in an off-screen voiceover: <d>[Language] …</d> while his lips remain completely closed.
```
- diagnose_report() 文本不一致

### `voiceover-ok` — 画外音写法正确（应当没有对白相关 error）
- JS: score=85 grade=B items=fight-purposeless-action
- Py: score=100 grade=A items=（无）
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 429, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- Py stats: `{"length": 429, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 0, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 B（85/100）｜长度 429 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✗打斗连贯性
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（100/100）｜长度 429 字，分镜 2 个，时间码 1 处
必改 0｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✓对白与说话人  ✓打斗连贯性
没有发现问题：结构、节奏、措辞、声音、物理、一致性与安全各项都过关。
```
- diagnose_report() 文本不一致

### `scenetrans-pair` — <scenetrans> 出现奇数次
- JS: score=80 grade=B items=fight-purposeless-action, scenetrans-pair
- Py: score=95 grade=A items=scenetrans-pair
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 375, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 1, "infos": 0}`
- Py stats: `{"length": 375, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 0, "warns": 1, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 B（80/100）｜长度 375 字，分镜 2 个，时间码 1 处
必改 1｜建议 1｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  !对白与说话人  ✗打斗连贯性
! 建议  <scenetrans> 出现 1 次（应为偶数）
      → 台词跨切时要在切点两侧各写一次 <scenetrans>，并说明声音跨切连续。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（95/100）｜长度 375 字，分镜 2 个，时间码 1 处
必改 0｜建议 1｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  !对白与说话人  ✓打斗连贯性
! 建议  <scenetrans> 出现 1 次（应为偶数）
      → 台词跨切时要在切点两侧各写一次 <scenetrans>，并说明声音跨切连续。
```
- diagnose_report() 文本不一致

### `cutoff-hint` — 最后一句台词没有收尾标点，像被片尾截断
- JS: score=84 grade=B items=cutoff-hint, fight-purposeless-action
- Py: score=99 grade=A items=cutoff-hint
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 361, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 1}`
- Py stats: `{"length": 361, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 0, "warns": 0, "infos": 1}`
- report() 文本差异：

```
[JS]
提示词体检 B（84/100）｜长度 361 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 1
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ·对白与说话人  ✗打斗连贯性
· 提示  最后一句台词没有收尾标点，像是被片尾截断
      → 被片尾截断的台词用 <cutoff> 标出（官方 4.4）。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 A（99/100）｜长度 361 字，分镜 2 个，时间码 1 处
必改 0｜建议 0｜提示 1
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ·对白与说话人  ✓打斗连贯性
· 提示  最后一句台词没有收尾标点，像是被片尾截断
      → 被片尾截断的台词用 <cutoff> 标出（官方 4.4）。
```
- diagnose_report() 文本不一致

### `sound-dialogue-repeat` — overall_soundscape 里重复了台词
- JS: score=70 grade=C items=fight-purposeless-action, sound-dialogue-repeat
- Py: score=85 grade=B items=sound-dialogue-repeat
- 仅 JS 命中：`fight-purposeless-action`
- JS stats: `{"length": 373, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 2, "warns": 0, "infos": 0}`
- Py stats: `{"length": 373, "shots": 2, "sentences": 4, "timecodes": 1, "errors": 1, "warns": 0, "infos": 0}`
- report() 文本差异：

```
[JS]
提示词体检 C（70/100）｜长度 373 字，分镜 2 个，时间码 1 处
必改 2｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✗打斗连贯性
✗ 必改  overall_soundscape 里重复了 1 句台词
      → 声音段只写环境声、动作声与非语言人声；台词只出现在正文的 <d> 里（官方 4.6）。
✗ 必改  有 1 处动作没写目的（move:退）
      → 每个动作都要交代它服务于什么（进攻／闪躲／脱离／抢位／护住／蓄势／格挡／反击）；跳跃只能是「为躲开来招」或「为跃起重击／迎空拦截」。写不出目的就删掉这个动作。

[Py]
提示词体检 B（85/100）｜长度 373 字，分镜 2 个，时间码 1 处
必改 1｜建议 0｜提示 0
八维：✓内容与结构  ✓运动与节奏  ✓音频  ✓物理逻辑  ✓人物真实感  ✓风格一致性  ✗对白与说话人  ✓打斗连贯性
✗ 必改  overall_soundscape 里重复了 1 句台词
      → 声音段只写环境声、动作声与非语言人声；台词只出现在正文的 <d> 里（官方 4.6）。
```
- diagnose_report() 文本不一致

## 验收

- score 最大绝对差 **15**（≤2）
- grade 一致率 **77.0%**（≥90%）
- error 级 id 集合一致 **47/61**
- 附：全部 id 集合一致 47/61，stats 一致 47/61，report() 文本一致 47/61，diagnose_report() 一致 47/61
- **结论：未达标，见「差异明细」**
