# ComfyUI-H3-WushuBridge · MiniMax H3 武打语义逻辑翻译桥

> **v1.1.2**（XYZ 坐标锁定 + 逻辑链 + 六大翻车差向量）：完整打斗/行为因果弧 + BUNNY 风格高动态降级族；TEXT 对见 `wushu_pairs_v2_logic_chains.jsonl`。权重仍为 v1，需本机 H3 CLIP 重训。

**中文** | [English](#english)

把「武打逻辑」直接写进 MiniMax H3 的 conditioning 空间：**夹在 conditioning 节点之间**，
输出更懂武打逻辑的 CONDITIONING。架构对标社区的
[MiniMax-H3-Semantic-Bridge](https://github.com/Speach1sdef178/MiniMax-H3-Semantic-Bridge)，
但训练数据、判据、评分头全部换成**武打专用**，而且**模型极小、能在你自己的机器上原地训练**。

```
CLIPTextEncode(H3) ──► [ H3 武打语义逻辑桥 ] ──► KSampler / H3 采样节点
        │                        ▲
        │                        └─ 只替换 embedding 张量，
        └─ conditioning                 minimax_keyframes / minimax_refs /
           [1, T, 5120] + metadata       minimax_frame_count 等 metadata 原样保留
```

---

## 1. 它和「H3 Semantic Bridge」有什么不同

| | 社区版 Semantic Bridge | 本插件（武打桥） |
|---|---|---|
| 目的 | 通用语义对齐（跨架构蒸馏） | **武打逻辑**：力线、格距、防守反应、命中反馈、死线结局 |
| 桥结构 | `5120→512→512→5120` 逐 token MLP（11MB / fp16） | 同构 MLP **可加载社区权重做对照**，另有跨 token 轻量 Transformer（默认，2 层 d=256，约 8MB/fp16） |
| 训练数据 | 外部教师模型蒸馏 | **你自己的语料** + 规则驱动的定向降级合成，原位训练 |
| 训练位置 | 作者训好再发布 | **在装了 H3 的 ComfyUI 里点一下就跑**（要 H3 文本编码器产 5120 维 embedding） |
| 评分/门控 | 无 | **JEV 式评分头**：不吐字，直接对 CONDITIONING 给「武打逻辑合格概率」 |
| 风险控制 | alpha + 幅度对齐 | 同样有，另加 `auto_alpha`（分低多修）与 `guard`（改坏了自动回退） |
| 参考图模式 | v1 明确不支持 Ref2VA | 默认同样保守（alpha ≤ 0.12 + 只动尾部 token），可另训 ref2v 专用适配器 |

### 为什么是「跨 token」的桥

武打逻辑的本质是**整段自洽**：拳脚只能在 1 格内命中、刃对刃才算格挡、腾空必须有借力依据、
死线前必须有结果。逐 token MLP 天生看不到这些跨句约束；Transformer 桥能看到整条序列，
所以默认用它。想要「同架构对照」或直接加载社区那 11MB 权重时，把 `arch` 切成 `mlp` 即可。

---

## 2. 三个模型各多大

| 组件 | 参数量 | 文件大小 | 说明 |
|---|---|---|---|
| 语义桥 `trans`（默认） | 约 4.2M | fp32 16MB / fp16 8MB | 2 层、d=256、4 头 |
| 语义桥 `mlp`（社区同构） | 约 5.5M | fp32 22MB / **fp16 11MB** | 与社区版逐层一致，可直接加载社区权重 |
| JEV 评分头 | 约 0.8M（hidden=128）/ 1.6M（hidden=256） | 3–7MB | 单次前向出概率，无解码 |

对比：最小的开源 JEV 复刻（Verdict / open-jev-typed-decision-engine 的 ModernBERT-150M）是
1.5 亿参数，NanoJev 是 0.6B。本插件的评分头是 **80 万参数**——因为它在 H3 自己的语义空间里
原位训练，不需要重新理解语言。

---

## 3. 安装

```text
把整个 ComfyUI-H3-WushuBridge 目录放进：
    ComfyUI/custom_nodes/ComfyUI-H3-WushuBridge/
```

依赖只有 `torch / numpy / safetensors`（ComfyUI 环境本来就全有，不用装）。

重启 ComfyUI 后，节点出现在分类 **MiniMax H3/Wushu Bridge** 下。

权重与数据集目录会自动创建：

```text
ComfyUI/models/wushu_bridge/            ← 桥 / 评分头 safetensors
ComfyUI/models/wushu_bridge/datasets/   ← 训练数据集 *.npz
```

**装完先自检**（不需要 H3、不需要显卡，30 秒）：

```bash
python ComfyUI/custom_nodes/ComfyUI-H3-WushuBridge/tools/selftest.py
```

### 菜单里只显示常用节点

插件一共 11 个节点，但**日常出片只用 5 个**，所以默认只把这 5 个交给 ComfyUI：

| 默认显示（在用） | 用途 |
|---|---|
| H3 武打语义逻辑桥 | 接在 conditioning 之间，把武打逻辑写进条件空间 |
| H3 武打提示词体检 | h3lint 八维规则体检（纯 CPU） |
| H3 武打逻辑评分 | JEV 式概率打分 |
| H3 武打编排 | 动作导演编排 |
| H3 武打桥 清空缓存 | 卸载常驻权重 |

另外 6 个是**一次性 / 诊断**工具，默认隐藏：构建数据集、采集训练对、训练残差桥、
训练 JEV 评分头、降级预览、文本 token 段定位。

要动它们（比如重新训一个桥）时，设环境变量再重启 ComfyUI：

```bat
set WUSHU_BRIDGE_NODES=all          :: Windows cmd
```
```powershell
$env:WUSHU_BRIDGE_NODES="all"       # PowerShell
```

取值 `all` / `full` / `train` / `dev` 都算全开；其它值（含默认 `core`）只留常用节点。

> 过滤只影响菜单显示。节点类、权重格式、数据集格式都没动 —— 老 workflow JSON 里
> 已经存了这些节点的话照旧能加载运行（ComfyUI 按类名实例化，不依赖菜单列表）；
> 内部全量表在 `__init__.py` 里另导出为 `ALL_NODE_CLASS_MAPPINGS`。

---

## 4. 三步跑起来

### 第 1 步 · 直接用（还没训练也能用）

把 **`H3 武打语义逻辑桥（接在 conditioning 之间）`** 插到文本编码之后、采样器之前。
没有训练过权重时先跳过；训练完再回来把 `bridge` 指到你的权重。

同时把 **`H3 武打提示词体检（规则引擎）`** 挂上，它会按
h3lint 的八维（内容结构 / 运动节奏 / 音频 / 物理逻辑 / 人物真实感 / 风格一致性 / 对白 / 打斗连贯性）
给提示词打分并列出必改项。

### 第 2 步 · 训一次（一次性，约 20–40 分钟）

1. `H3 武打桥 构建数据集`：接上 H3 的 `CLIP` 加载器（**必须是 H3 那套文本编码器**），
   `corpus_path` 指向你自己的提示词库，跑一次得到 `*.npz`。

   推荐直接从你的同分布语料开始：

   ```text
   D:\wushulong\dataset\h3_train\metadata.csv     924 条（列 video,prompt,input_audio,frame_rate）
   D:\wushulong\dataset\clips                     1847 条（924 英 + 923 中，中文版 [镜头n]）
   D:\wushulong\docs\提示词库.md                   37 条
   D:\wushulong\h3_fight_skills                   10 条
   ```

   建 **ref2v** 数据集时再加上这份**官方六段 Ref2VA 成品**（格式 100% 可迁移，
   但内容是文戏，武打逻辑分低，别当武打正例用）：

   ```text
   D:\wushulong\H3武斗模拟器-v9.12\_template_sources\drama\h3-prompts-yajni\examples\晴天收信人_H3独立8秒提示词.md   38 条
   ```

   > 英文为主是正常的：你的 924 条语料本身以英文为多，本插件的降级算子和词表**中英双语**，
   > 英文词表就是从这批语料里统计出来的（weight / stance / hips / momentum / footwork / parry …）。
   > `dataset\rejected\` 只有 327 个 mp4、prompt 不可恢复，别指望拿它当负例；
   > 负例由规则降级合成（见第 6 节）。

2. `H3 武打桥 训练残差桥`：`dataset_path` 选上一步的产物，`arch=trans`，其余保持默认，跑完得到
   `wushu_bridge_v1.safetensors`。

3. `H3 武打桥 训练 JEV 评分头`：同一个数据集，跑完得到 `wushu_jev_head_v1.safetensors`。

### 第 3 步 · 用起来

在 `H3 武打语义逻辑桥` 上：

* `bridge` = 你刚训出来的桥；`alpha` 从 **0.12** 起（对标社区推荐值）
* `magnitude_match` = `per_token`（推荐）
* `judge` = 你刚训出来的评分头，`auto_alpha` 打开 → 提示词逻辑分低时自动多修一点
* `guard` 打开 → 改完评分反而变低就自动回退，绝不让桥把好稿子改坏

`report` 输出会告诉你每段 conditioning 的 token 数、语义漂移量（1-cos）和前后评分。

---

## 5. 节点清单

**菜单默认只显示 2 个节点**，因为主线只需要一个：

| 节点 | 输入 → 输出 | 用途 |
|---|---|---|
| **H3 武打语义优化（判断→优化→输出）** | CONDITIONING + 提示词 → CONDITIONING + score + pass + report | **就用它**。判断→优化→复评→合格输出，全在一个节点里 |
| H3 武打桥 清空缓存 | — | 换权重/换小模型后清显存 |

### 那一个节点内部在做什么

```
CLIPTextEncode ──►【H3 武打语义优化】──► KSampler
                         │
   Laya 判武打逻辑（15 秒内，本地）
        │达标 ──► conditioning 原样输出，什么都不动
        │
        └不达标 ──► 残差桥在 conditioning 空间施加修正
                     （可选）小模型按"待修项"重写提示词 → 重新编码 → 再上桥
                     复评 ◄──────────────────────────┘
                       │真的变好了 → 接受，继续
                       │没变好     → 回退并停（不做无用功）
```

输出 `pass=False` 时报告会**直接告诉你差在哪、下一步该开什么**（比如"文本分只能靠改文字提升，
请把 llm_mode 设成 hf"）。

### 其余节点（默认收起）

不是不能用，是日常出片用不到 —— 全列出来会把主线淹掉。要看全部：

```powershell
$env:WUSHU_BRIDGE_NODES="all"     # 然后重启 ComfyUI
```

收起的 12 个：单独的语义桥 / JEV 评分 / h3lint 体检 / 武打编排（动作导演）/
Laya 裁判分体版（只判分）/ Laya 优化回路（候选稿排序）/ 建数据集 / 采训练对 /
训桥 / 训评分头 / 降级预览 / token 段定位。老 workflow 里存过的节点照旧能加载运行。

---

## 5.5 Laya 裁判 + 可选小模型（都随插件走，免额外服务）

**[Laya](https://github.com/NandhaKishorM/laya)**（本地、Apache-2.0、非自回归决策模型）
负责**判断**；残差桥负责**改 conditioning**；可选的小语言模型只负责**写字**。
三者分工明确，因为 Laya 只会回答 choice/score/noul 三类问题、**不会生成文本**。

| 角色 | 干什么 | 谁来干 |
|---|---|---|
| 判断 | 这段武打逻辑合不合格、弱项在哪 | **Laya**（文本输入，实测 0.7~2.3 秒/次） |
| 优化 conditioning | 在 5120 维条件空间施加武打逻辑修正 | **残差桥**（插件自带 16MB 权重） |
| 兜底校验 | 防止"文本分涨了但条件向量变坏" | **JEV 评分头**（插件自带 6.5MB） |
| 改文字 | Laya 判出逻辑缺失、光靠桥补不回来时重写提示词 | **可选小模型**（下面有清单） |


* **免 pip 安装**：Laya 本体是纯 Python、8 个文件、76KB，已内嵌在
  `wushu_bridge/vendor/laya/`（依赖 numpy/torch/transformers 等 ComfyUI 本来就有）；
* **免外挂服务**：进程内直接推理，不用另起 HTTP 服务、不用另配 venv；
* **免联网**：权重从本地装配，跑的时候完全离线；
* **用得上 GPU**：直接跑在 ComfyUI 的 torch 上（实测 RTX 3080，判断 0.7~2.3 秒/次）。

### 可选小模型（只在需要"改文字"时才用）

`llm_mode` 三种取值：

| 取值 | 说明 |
|---|---|
| `off`（默认） | 只做 conditioning 空间优化。**先用这个** —— 大多数情况够用，且不用下载任何东西 |
| `hf` | 用下面的小模型重写提示词。没下载过会**自动下**到 `ComfyUI/models/wushu_bridge/llm/<模型名>/`，之后离线可用。需要接上 `clip`（重写后要重新编码） |
| `endpoint` | 调本机已有的 OpenAI 兼容服务（llama.cpp / LM Studio / vLLM）。**不下载、不额外占显存**；填 `llm_endpoint_url` 即可 |

`hf` 模式的模型清单（都是**实测核验过**的存在性/体积/许可/门禁）：

| 模型 | 体积 | 许可 | 门禁 | 说明 |
|---|---|---|---|---|
| **openbmb/MiniCPM5-2B** | 5.03 GB | apache-2.0 | 无 | 默认。同类里最强的小模型之一，写动作描述够用 |
| Qwen/Qwen3-1.7B | 4.06 GB | apache-2.0 | 无 | 最省显存、最快 |
| HuggingFaceTB/SmolLM3-3B | 6.15 GB | apache-2.0 | 无 | |
| microsoft/Phi-4-mini-instruct | 7.67 GB | mit | 无 | |
| Qwen/Qwen3-4B-Instruct-2507 | 8.04 GB | apache-2.0 | 无 | 质量更好 |
| openbmb/MiniCPM4-8B | 16.37 GB | apache-2.0 | 无 | 更大更强 |
| google/gemma-3-1b-it | 2.00 GB | gemma | ⚠️ 需先在模型页同意条款 | 最小 |
| meta-llama/Llama-3.2-1B-Instruct | 2.47 GB | llama3.2 | ⚠️ 需先在模型页同意条款 | |

> 门禁（gated）的两个要先去 HuggingFace 模型页点同意，否则下载会 401。
> 手动预下载也行：`huggingface-cli download openbmb/MiniCPM5-2B --local-dir <上面那个目录>`。

### 装权重（一次性，约 1.5GB）

**一条命令（推荐）**——从本项目的公开权重仓直接拉全套：

```bash
python tools/setup_laya.py --from ours
```

或按情况选来源：

```bash
# 你机器上已经有 HF 缓存（最快，零下载）
python tools/setup_laya.py

# 从 Laya 官方仓下（convaiinnovations/laya）
python tools/setup_laya.py --from upstream

# 权重已在别处，直接指定目录
python tools/setup_laya.py --source /path/to/laya-weights

# 只看会做什么 / 只要英文档 / 装完自检
python tools/setup_laya.py --dry-run
python tools/setup_laya.py --only english
python tools/setup_laya.py --verify
```

权重落点：`ComfyUI/models/wushu_bridge/laya/`（可用 `--target` 改）。
同盘会走硬链接，不额外占空间。

**权重仓库（公开，无需登录）**：
[laya/ 子目录](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/tree/main/laya) —— 里面就是完整的 bundle 布局：

```
laya/
  rl_agent_config.json        ← english 档（根）
  model.safetensors           842.6MB
  tokenizer/  encoder/
  multilingual/               ← 中文档
    rl_agent_config.json
    model.safetensors         643.8MB
    tokenizer/  encoder/
```

两档合计 **1,524MB**。只装这两档是因为武打裁判只用得上它们；Laya 还有第三档
`typed-decisions`（票据/工单那类业务 workflow 用）没放进来，想用可 `--from upstream --only all`。

### 自定义规则怎么写

`custom_rules` 一行一条，`#` 开头是注释。分三种写法 —— 因为 Laya **只吃这三种题型**：

```
# 裸规则 → 是/否题（noul）
命中之后必须能看到受力反馈或位移
跳跃必须有依据，不能无来由起跳

# 评分:问题|最差档|…|最好档  → 有序档位（score）
评分:镜头调度是否具体|完全没写|很模糊|大概能看出|比较具体|非常具体且可执行

# 选择:问题|选项1|选项2  → 选项题（choice）
选择:这一段的收招应该怎么处理|直接停住|缓冲半步|顺势追击
```

### 这两类分数别混

| 分 | 来源 | 用途 |
|---|---|---|
| **rubric 加权分**（节点输出的 `score`） | 固定五问等权：动作逻辑/招式过程/命中反馈/跳跃纪律/可拍性 | 门禁阈值看它（默认 0.62 = 小改可用） |
| **自定义规则分**（报告里的「自定义规则」段） | 你写的规则 | 单独列出，不混进总分，免得随手加两条就把基准分带跑 |

### 诚实说明：Laya 不写字

Laya 是非自回归决策模型，**只回答 choice / score / noul 三类问题，不生成文本**。
所以这两个节点做的是**判断、排序、指方向**，"改稿"仍由你或文本模型出：

```
体检(h3lint) 找出待修项 ──► Laya 挑"最该先修的一条"（正反双序防位置偏置）
你/文本模型 按方向出 N 份候选 ──► Laya 逐一打分排序 ──► 取最高分那份
```

让 8 亿参数的非自回归模型去写字只会得到噪声 —— 分工这样才是对的。

> 两条实测教训写进了实现里，别绕开：
> ① **choice 有严重位置偏置**：同一材料把选项顺序反过来问它会改答案，四个截然不同的
> 状态甚至全选第一个（置信还 0.89~0.93）→ 一律正反双序，两次不一致就按默认顺序走；
> ② **ordinal score 是最弱的 primitive**：好稿/烂稿在"动作逻辑"这一问上几乎不分甚至反向，
> 判别力主要来自 noul 那几条 → 门禁用加权分，别单看某一问。

---

## 6. 训练数据是怎么来的（核心思路）

真正让模型学会"武打逻辑"的不是正例本身，而是**正例与它逻辑缺失版本之间的向量差**。
插件用**确定性规则**把正例定向降级成负例，不需要外部大模型、不需要人工标注：

| 算子 | 干了什么 | 为什么这样降才合理 |
|---|---|---|
| `force_chain` | 抽掉力线句（蹬地/转腰/送胯·weight/hips/momentum） | H3 只知道"挥刀"，不知道力从哪来 |
| `distance` | 抽掉格距与站位 | 距离不对就不该命中 |
| `feedback` | 抽掉打击反馈（火星/踉跄/衣破·sparks/stagger/friction） | 打了没反应＝没打 |
| `contact` | 抽掉接触点与命中判定 | 刃对刃、擦过、劈空全糊在一起 |
| `defense` | 把防守从句换成站桩对望 | 武打片最忌站桩 |
| `moves` | 具体招式泛化成"一次攻击" | 信息量掉了，H3 只能瞎编 |
| `ending` | 破坏死线结局（终结技降级、倒地改后退） | 死线前没结果＝废片 |
| `empty` | 具体描写换成空泛形容（很重/极快·very fast） | 写了等于没写 |
| `holes` | 注入慢动作/剑气/瞬移/血条 UI | 平台安全与物理逻辑反例 |
| `junk` | 掺规则说明文字 | H3 读不懂，会稀释动作 |
| `sound` | 抽掉音景 | 少一层物理感 |
| `order` | 打乱时间码顺序 | 结构反例 |

**只动逻辑层、不动场景与人物**：降级只作用在分镜行（`[Shot n]` / `[镜头n]`），
头部（触发词、时长、帧数、场景、人物、武器）保持不动——这样正负例描述的是同一个事件，
桥学到的是"补逻辑"而不是"换场景"。

一条正例可生成 1~5 级不同残缺程度的负例（`intensity`），让评分头学到的是一条**连续的
逻辑完备度刻度**，而不是 0/1 开关，概率才可信（训练结束会报 ECE 校准误差）。

---

## 6.5 v1.1 · BUNNY 启发的高动态逻辑链

受 [BUNNY H3 Conditioning Bridge V2](https://huggingface.co/JOKER141/BUNNY_H3_Conditioning_Bridge) 高动态语义族启发，
本版把「完整因果弧」与「行为/连续性」写进武打域：

| 家族 | 例子 |
|---|---|
| 打斗完整弧 | 逼近→测距→攻防→接触→力反馈→状态→终结；缠抱拆开；佯攻实打；缴械回收；撞墙反弹；1v2 交接；腾空起落 |
| 行为连续性 | 武器归属、遮挡再识别、换位朝向、追击刹停再交手、掩体碎屑继承、弹刀几何、伤势跨镜、环境仍湿 |

**实现入口**

* 链模板：`wushu_bridge/logic_chains.py`（`CHAINS` / `render_chain` / `validate_chain_coverage`）
* 词表：`lexicons.py` 新增 ownership / occlusion / momentum / pursuit / facing / state_carry …
* 降级：`pairs.HIGH_DYNAMIC_OPS` + 默认 `DEFAULT_OPS`（经典 ∪ 高动态）
* 种子：`seeds.py` 扩到 8 条 T2V + 2 条 Ref2V + 1 条 horde
* TEXT 对：`models/wushu_bridge/datasets/wushu_pairs_v2_logic_chains.jsonl`
* 中文说明：[`docs/逻辑链说明.md`](docs/逻辑链说明.md)

**六大实测翻车 + XYZ 坐标锁**：无因跳跃、未面对面、法术打空气、切镜换人/瞬移、空间锚缺失（**优先显式 `xyz=`**）、法术击中无反馈 —— 见 [`docs/逻辑链说明.md`](docs/逻辑链说明.md) §0 /「XYZ 坐标约定」；算子 `facing_break`/`jump_orphan`/`spell_miss_target`/`identity_drift`/`teleport_cut`/`spell_no_feedback`/`xyz_drift`。

**权重**：随包的 `wushu_bridge_wushu_v1.safetensors` / `wushu_jev_wushu_v1.safetensors` **未在本版重训**。
拉取后请在本机 ComfyUI（H3 CLIP 5120-d）按 `docs/训练流程.md` →「v1.1 逻辑链补训」重建数据集并训 v2 权重。

降级算子对照（v1.1 新增）：

| 算子 | 作用 |
|---|---|
| `ownership` | 打乱/丢掉武器归属与回收 |
| `occlusion` | 去掉遮挡后再识别锁 |
| `facing` | 打乱换位后左右/朝向 |
| `momentum` | 去掉击退→反弹→动量继承 |
| `pursuit` | 去掉追击/刹停再交手因果 |
| `state_carry` | 去掉伤势/状态跨镜继承 |
| `chain_break` | 删掉拍间因果连接词 |

## 7. 诚实的局限

* **v1 面向文生视频 / FL2VA 路径**。参考图（Ref2VA）路径与社区版一样保守：参考图 token 与文本
  token 在打包序列里混在一起，位置不稳定，默认建议 `alpha ≤ 0.12` + `token_span=tail`，
  或先用 `H3 文本 token 段定位` 看看文本段在哪，再决定 `token_span`。
* **残差桥是"引导"不是"重写"**。它只能沿学到的方向平移语义，不能删词加词。如果你需要
  "把一段粗糙描述真的改写成逻辑完备的版本"，那是**文本层**的活（本插件的降级/体检节点 +
  你自己的改写流程），桥是接在后面的条件空间微调。
* **representation 指标不等于观感**。训练报告里的 cosine / drift 只是"有没有往目标方向走"，
  最终还是要你自己出片 A/B：同一 seed、同一提示词，alpha=0 / 0.12 / 0.2 各跑一条比。
* 社区版作者自己也写了：这类适配器"可能帮一部分提示词、对另一部分没差别、偶尔更差"。
  本插件的 `guard` + `auto_alpha` 就是为这个准备的。
* **有一批武打规则在文本层面根本判不了**：格距是否等于攻击距离、每秒攻防额度是否超了、
  真值在 `sim3d/engine.js` 的 60Hz 结算里（用户侧盘点的 R086–R107 共 22 条，纯文本判定=不可能）。
  文本校验器只能管"写没写"（写了格距、写了防守反应），管不了"算得对不对"。
  **这正是本插件走"学出来的条件空间残差"而不是"规则改写文本"的原因**——规则能查的只是表面，
  而 H3 真正吃进去的是那 5120 维语义；桥是在那个空间里把"缺逻辑的写法"往"逻辑完备的写法"推。
* **英文台词重复**：`h3lint.js` 原版做台词比对时只保留 CJK（`replace(/[^\u4e00-\u9fff]/g,"")`），
  所以纯英文稿的 `sound-dialogue-repeat` 永远不报。本插件的移植版为此加了 `englishAware` 开关，
  **对非中文文本默认打开**；
  默认关闭时与 JS 原版逐位一致（61 条用例差分 score 差 0），两者都保留。
* **Ref2VA 的镜头数被数错**：官方 Six-section 写法会在 `retention_analysis` 里写
  `(appears in [Shot 1])` 这类**引用**，而 `h3lint.js` 的 `rxShots` 把引用也当镜头数
  ——一份 **1 镜**的稿子会被数成 4 镜，6 条引用以上直接判 `shot-many` **error**，
  连锁还会让"切镜接续/还是这两人"的段头错位、误报一片。
  本插件加了 `shotCounting` 开关（`raw` / `blocks` / `auto`），**`auto` 为
  非 raw 默认值**：只在检测到引用式写法时改按"行首分镜块"计数。
  Ref2VA 种子建议先跑一次体检看分数，并优先消掉 `shot-many` 这类结构 error；
  默认 `raw` 时仍与 JS 逐位一致。
* **两条负面项硬约束**（来自你的使用指南，插件已按此设计）：
  1. 负面词（站桩对望、拳头挡刀、空手接刃、瞬移、血条 UI 分数、慢动作、剑气）
     **不进正向提示词**，它们属于 ComfyUI 的 negative prompt —— 所以本插件把它们
     当作"降级算子"注入到**负例**里，而种子正例里一个都不出现、也不用否定式措辞。
  2. H3 **没有独立负面栏**，需要"正向点名"：写实人物要正向写皮肤锁，
     并且避开 `film grain` / `35mm` / `flawless skin`（容易被放大成重噪点与油腻脸）。
     这三个词已加入 `lexicons.LOGIC_HOLES["style_risk"]`，逻辑分会自动扣分并报出来。

---

## 8. 目录结构

```text
ComfyUI-H3-WushuBridge/
├─ __init__.py                    ComfyUI 插件入口
├─ wushu_bridge/
│  ├─ nodes.py                    10 个 ComfyUI 节点
│  ├─ bridge_model.py             残差桥架构（mlp 社区同构 / trans 跨 token）+ 权重读写
│  ├─ apply.py                    施加到 CONDITIONING（保留 metadata、幅度对齐、漂移统计）
│  ├─ judge.py                    JEV 式评分头 + 温度校准
│  ├─ train.py                    训练循环（桥 / 评分头）
│  ├─ dataset.py                  *.npz 数据集格式
│  ├─ pairs.py                    语料抽取 + 规则降级合成训练对
│  ├─ logic_score.py              武打逻辑评分（中英双语，0~1）+ 复合分
│  ├─ lexicons.py                 中英双语武打词表（英文词表统计自 924 条同分布语料）
│  ├─ seeds.py                    内置种子正例（文生视频 / 多参考图 / 一打多）
│  └─ lint/                       武打逻辑规则引擎（h3lint.js 的 Python 移植，61 条用例差分零差异）
├─ tools/
│  ├─ selftest.py                 离线自检（不需要 H3）
│  ├─ probe_corpus.py             语料探针：能挖出多少正例、降级长什么样
│  ├─ h3lint_diff_report.md       JS 原版 vs Python 移植版的差分验证报告
│  └─ make_package.py             打成可直接放进 custom_nodes 的 zip
├─ tests/
│  ├─ test_h3lint.py              移植版自身的行为测试
│  ├─ test_h3lint_assertions.py   用**用户项目自带的 45 条断言对**做的阈值验收
│  └─ test_nodes_offline.py       假 CLIP 跑通「建集→训桥→训评分头→应用」
└─ docs/
   ├─ 使用指南.md          ← **完整使用手册**（安装/11 个节点逐个说明/LoRA 配合/实战/排错）
   ├─ 安装与接线.md
   ├─ 训练流程.md
   └─ 部署说明.md
```

**看文档的顺序**：先看 [docs/使用指南.md](docs/使用指南.md)——自包含，
含三层分工、安装验证、节点逐个参数说明、wushu_h3_v2 / v7 两类 LoRA 的配合、
参数速查（含时长↔帧数表）、四个实战场景、排错表，以及兵器表/招式变体/14 条打斗规则附录。

## 9. 两套分制说明（别混）

| 分 | 来源 | 管什么 |
|---|---|---|
| 壳结构分 | `lint/`（h3lint 移植） | 官方壳字段、分镜数/时间码、空泛词、平台安全、对白规范、八维诊断 |
| 武打逻辑分 | `logic_score.py` | 力线、格距、防守反应、接触点、打击反馈、招式具体度、因果链、结局、逻辑漏洞 |
| **复合分**（训练标签） | `0.4 × 壳结构 + 0.6 × 逻辑` | 两者都要；逻辑占大头，因为桥学的就是逻辑 |

之所以必须复合：h3lint 是**中文语境**规则（用「格挡／闪避／反击」「于是／随即」这类词表），
而你的 924 条同分布语料**以英文为主**——一份写了
`blocks, sidesteps, rolls low to escape` 的稿子会被中文规则误判成"没有任何防守反应"。
`logic_score.py` 就是为英文稿补上的那一半，两套分都在
「H3 武打提示词体检」节点的 report 里同时给出。

## 9. 许可与致谢

本插件是独立实现，与 MiniMax / ComfyUI / 社区 Semantic Bridge 项目无隶属关系。
桥的**应用公式与 MLP 结构**参考社区 `MiniMax-H3-Semantic-Bridge`（可加载其权重做对照）；
武打规则判据来自用户既有的 h3lint 规则体系。MiniMax H3 与其衍生权重受上游
MiniMax H3 Community License 约束。

### 内嵌的第三方组件

| 组件 | 版本 | 许可证 | 位置 |
|---|---|---|---|
| [Laya](https://github.com/NandhaKishorM/laya)（Convai Innovations） | 0.3.5 | **Apache-2.0** | `wushu_bridge/vendor/laya/`（原样拷贝，未修改；许可全文见同目录 `LICENSE`） |

Laya 的**模型权重不随本仓库分发**：由用户在首次使用时自行下载，或用
`tools/setup_laya.py` 从本地缓存装配。详见 `wushu_bridge/vendor/README.md`。

---

## 安装来源（本地 / Hugging Face / GitHub）

三种装法任选，装到 `ComfyUI/custom_nodes/` 下并重启 ComfyUI 即可。

**① 从 Hugging Face 克隆**（本仓库默认**私有**，需要你的 HF 令牌）

```bash
# 私有仓库要先带令牌（把 <TOKEN> 换成你的 HF read 令牌）
git clone https://Jojocodex:<TOKEN>@huggingface.co/Jojocodex/ComfyUI-H3-WushuBridge.git
# 或者先登录一次，之后 git 会记住凭据
pip install -U huggingface_hub && huggingface-cli login
git clone https://huggingface.co/Jojocodex/ComfyUI-H3-WushuBridge.git
```

**② 从 GitHub 克隆**（公开，无需令牌）

```bash
git clone https://github.com/314899085-dotcom/ComfyUI-H3-WushuBridge.git
```

**③ 下载 ZIP**：在本页右上角 **Files** 里下载整仓打包，解压后放进 `custom_nodes/` 亦可。

**想把它变公开**：Hugging Face 仓库页 → **Settings** → *Change visibility* → Public（GitHub 侧的私有/公开在仓库 Settings → Danger Zone）。

## Install sources (local / Hugging Face / GitHub)

Pick any of the three; put the folder under `ComfyUI/custom_nodes/` and restart ComfyUI.

**① Clone from Hugging Face** (this repo is **private** by default — your HF token is required)

```bash
git clone https://Jojocodex:<TOKEN>@huggingface.co/Jojocodex/ComfyUI-H3-WushuBridge.git
# or log in once and let git remember the credential
pip install -U huggingface_hub && huggingface-cli login
git clone https://huggingface.co/Jojocodex/ComfyUI-H3-WushuBridge.git
```

**② Clone from GitHub** (public, no token needed)

```bash
git clone https://github.com/314899085-dotcom/ComfyUI-H3-WushuBridge.git
```

**③ ZIP download**: use **Files** on this page to download the repo as an archive, then unzip into `custom_nodes/`.

**Make it public**: Hugging Face repo page → **Settings** → *Change visibility* → Public.


---

## 模型下载（不用自己训练也行）

仓库里的模型（语义桥 + JEV 评分头）**随本仓库一起分发**，放在 `models/wushu_bridge/`；
同时在 Hugging Face 上有一个**公开的权重仓库**（无需登录，带 LFS 版本管理）：

**权重仓库（公开）**：https://huggingface.co/Jojocodex/h3-wushu-bridge-weights

| 文件 | 大小 | 用途 |
|---|---|---|
| [wushu_bridge_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_wushu_v1.safetensors) | 16MB | **语义桥**（默认 trans 架构 2 层 d=256） |
| [wushu_jev_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_wushu_v1.safetensors) | 6.7MB | **JEV 评分头**（conditioning → P(武打逻辑合格)） |
| [wushu_bridge_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_cloud.safetensors) · [wushu_jev_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_cloud.safetensors) | 16MB / 3MB | 早期版本（对照用） |
| [wushu_pairs_v1_pairs.jsonl](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1_pairs.jsonl) · [wushu_pairs_v1.json](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1.json) | 1.6MB / 308KB | 训练对清单（可**重建数据集**） |
| `*_report.json` | 8–18KB | 训练报告（参数量/准确率/AUC/ECE/漂移/逐轮历史） |
| [`laya/`](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/tree/main/laya) 子目录 | **1,524MB** | **内嵌 Laya 决策模型的权重**（english + multilingual 两档），供两个 Laya 裁判节点用 |

> Laya 权重不用手工下载 —— 装完插件跑 `python tools/setup_laya.py --from ours` 即可，
> 详见上面「Laya 裁判」一节。

**安装（一条命令）**：

```bash
# 装到插件的权重目录（ComfyUI 会自动在这里找）
mkdir -p ComfyUI/models/wushu_bridge && cd ComfyUI/models/wushu_bridge
BASE=https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main
curl -L -O $BASE/wushu_bridge_wushu_v1.safetensors
curl -L -O $BASE/wushu_jev_wushu_v1.safetensors
curl -L -O $BASE/wushu_pairs_v1_pairs.jsonl
```

**仓库内镜像**：`models/wushu_bridge/` 下有完全相同的文件（含训练对清单 `datasets/wushu_pairs_v1_pairs.jsonl`
与两份训练报告）。Hugging Face 上的插件仓库默认**私有**，取镜像需按「安装来源」一节带令牌 clone。

**接线**：
* **H3 武打语义逻辑桥** → `bridge` 选 `wushu_bridge_wushu_v1.safetensors`，`judge` 选 `wushu_jev_wushu_v1.safetensors`；
* **H3 武打逻辑评分（JEV 式）** → `judge` 选 `wushu_jev_wushu_v1.safetensors`，`aggregate=mean`，`threshold=0.5`。

**参考跑参**：`alpha ≈ 0.12`、`magnitude_match=per_token`、`token_span=all`（参考图模式用 `tail`）。

**想自己训练**：见下面「第 2 步 · 训一次」；训练出的权重会写到 `ComfyUI/models/wushu_bridge/`，
与这里下载的完全同构（可直接互相替换）。

## Model download (no training required)

The models (semantic bridge + JEV scoring head) **ship with this repo** under `models/wushu_bridge/`.
They are also published in a **public** Hugging Face weights repo — direct download, no login:

**Weights repo (public)**: https://huggingface.co/Jojocodex/h3-wushu-bridge-weights

| File | Size | Purpose |
|---|---|---|
| [wushu_bridge_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_wushu_v1.safetensors) | 16MB | **Semantic bridge** (default trans arch, 2 layers, d=256) |
| [wushu_jev_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_wushu_v1.safetensors) | 6.7MB | **JEV scoring head** (conditioning → P(logic-pass)) |
| [wushu_bridge_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_cloud.safetensors) · [wushu_jev_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_cloud.safetensors) | 16MB / 3MB | earlier versions (reference) |
| [wushu_pairs_v1_pairs.jsonl](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1_pairs.jsonl) · [wushu_pairs_v1.json](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1.json) | 1.6MB / 308KB | training-pair manifest (can **rebuild the dataset**) |
| `*_report.json` | 8–18KB | training reports (params / accuracy / AUC / ECE / drift / history) |

**One-command install**:

```bash
mkdir -p ComfyUI/models/wushu_bridge && cd ComfyUI/models/wushu_bridge
BASE=https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main
curl -L -O $BASE/wushu_bridge_wushu_v1.safetensors
curl -L -O $BASE/wushu_jev_wushu_v1.safetensors
curl -L -O $BASE/wushu_pairs_v1_pairs.jsonl
```

**In-repo mirror**: `models/wushu_bridge/` holds the identical files (plus the training-pair manifest
`datasets/wushu_pairs_v1_pairs.jsonl` and both training reports). The Hugging Face plugin repo is
**private** by default — clone it with a token as shown in the "Install sources" section.

**Wiring**: bridge node → `bridge = wushu_bridge_wushu_v1.safetensors`, `judge = wushu_jev_wushu_v1.safetensors`;
JEV score node → `judge = wushu_jev_wushu_v1.safetensors`, `aggregate = mean`, `threshold = 0.5`.

**Reference settings**: `alpha ≈ 0.12`, `magnitude_match = per_token`, `token_span = all` (`tail` for reference-image mode).
**Train your own instead**: see “Step 2 · train once” above; the weights land in `ComfyUI/models/wushu_bridge/`
with the same layout, so they are interchangeable with the downloads.


---

## 配套 LoRA（语义逻辑的主要服务对象）

本插件的语义逻辑，主要就是为下面这个**武打动作 LoRA** 服务的：

**Wushu Action LoRA — MiniMax H3（FL2VA / Ref2VA）** → https://huggingface.co/Jojocodex/wushu-action-v7-minimax-h3-fl2va-ref2va-lora

* 触发词：`wushu_action`
* 定位：武打动作风格 LoRA（ComfyUI 即插即用），训练语料为专业三段式打标的武打片段
* 仓库内含：E3 主模型（1000 / 2000 步，全量 int8-convrot DiT + bf16 文本编码器）、
  `Minimax h3多参考双采打斗工作流.json`、`招式TAGS完整清单.md`（写提示词用）、`武术打斗提示词skill.md`

**两者怎么配合**

```text
CLIPTextEncode(H3) ──► [ H3 武打语义逻辑桥 ] ──► LoraLoader(wushu_action, 0.8~1.0) ──► 采样
        ▲                        ▲
        │                        └─ 把「打斗逻辑」推进 conditioning（本插件）
        └─ 提示词：触发词 wushu_action + 招式术语（来自 LoRA 仓库的招式 TAGS 清单）
```

* LoRA 放 `ComfyUI/models/loras/`，强度建议 **0.8~1.0**；
* 提示词里保留触发词 `wushu_action`，招式名从 LoRA 仓库的**招式 TAGS 完整清单**里取，
  再用本插件的**体检节点**核对结构与物理，用**评分头**给出"武打逻辑合格概率"；
* 想提升连贯性/物理表现，可再叠加少量强度（0.2~0.4）的运动连贯或物理类 LoRA。

## Companion LoRA (what this logic is built for)

The semantic logic in this plugin is primarily built for the **wushu action LoRA** below:

**Wushu Action LoRA — MiniMax H3 (FL2VA / Ref2VA)** → https://huggingface.co/Jojocodex/wushu-action-v7-minimax-h3-fl2va-ref2va-lora

* Trigger word: `wushu_action`
* A wushu action style LoRA for MiniMax H3 (drop-in for ComfyUI), trained on professionally tagged fight footage
* The repo also ships the E3 main model (1000 / 2000 steps), a multi-reference duel workflow JSON,
  the full move-tag list and a wushu prompt skill doc

**How to combine**

```text
CLIPTextEncode(H3) ──► [ H3 Wushu Semantic Bridge ] ──► LoraLoader(wushu_action, 0.8~1.0) ──► sampler
```

Put the LoRA in `ComfyUI/models/loras/` (strength 0.8–1.0), keep the trigger word `wushu_action`,
take move names from the LoRA repo's tag list, then use this plugin's **lint node** for structure/physics
and the **JEV scoring head** for a P(logic-pass) on the conditioning.


---

# English

**English** | [中文](#comfyui-h3-wushubridge--minimax-h3-武打语义逻辑翻译桥)

## What it is

Writes **fight logic** directly into MiniMax H3's conditioning space: it sits **between conditioning nodes** and
outputs a CONDITIONING that "understands" wushu logic. The architecture follows the community
[MiniMax-H3-Semantic-Bridge](https://github.com/Speach1sdef178/MiniMax-H3-Semantic-Bridge), but the training data,
the criteria and the scoring head are all **fight-specific**, and the models are **tiny — you can train them on your
own machine**.

```text
CLIPTextEncode(H3) ──► [ H3 Wushu Semantic Bridge ] ──► KSampler / H3 sampler
        │                        ▲
        │                        └─ only the embedding tensor is replaced;
        └─ conditioning                 minimax_keyframes / minimax_refs /
           [1, T, 5120] + metadata       minimax_frame_count metadata is preserved
```

## Three packs, three jobs

| Pack | Job |
|---|---|
| **ComfyUI-H3-WushuBridge** (this one) | *How it reads as a fight*: semantic bridge into conditioning, prompt lint (H3LINT), JEV scoring head, training side |
| **ComfyUI-H3-WushuSim** | *What the fight is*: a 60 Hz deterministic duel kernel → frame evidence, action-timing ledger, move library, H3 / LTX-2.5 prompts |
| **ComfyUI-JEV-Orchestrator** | *How it is orchestrated*: capability table, pluggable judges, explainable search with budget and rollback |

## Models (all small)

| Component | Parameters | File size |
|---|---|---|
| Semantic bridge `trans` (default) | ~4.2M | fp32 16MB / fp16 8MB |
| Semantic bridge `mlp` (community-shaped) | ~5.5M | fp32 22MB / **fp16 11MB** — can load community weights |
| JEV scoring head | ~0.8M (hidden=128) / 1.6M (hidden=256) | 3–6MB |

For comparison, the smallest open JEV replication is ~1.5B parameters; this scoring head is **0.8M** because it is
trained in-place inside H3's own semantic space and does not need to re-learn language.

## Install

```text
Copy the whole ComfyUI-H3-WushuBridge folder into:
    ComfyUI/custom_nodes/ComfyUI-H3-WushuBridge/
```

Dependencies are only `torch / numpy / safetensors` (already present in any ComfyUI environment).
After restarting ComfyUI the nodes appear under **MiniMax H3/Wushu Bridge**.
Weights and datasets are created automatically in:

```text
ComfyUI/models/wushu_bridge/             → bridge / judge safetensors
ComfyUI/models/wushu_bridge/datasets/    → training datasets (*.npz)
```

Self-check first (no H3, no GPU, ~30 s):

```bash
python ComfyUI/custom_nodes/ComfyUI-H3-WushuBridge/tools/selftest.py
```

## Three steps

**Step 1 — use it as-is (works before any training).** Add **H3 武打语义逻辑桥** between CLIPTextEncode(H3) and
your sampler; with no trained weights it still applies the built-in logic prior.

**Step 2 — train once (20–40 minutes, one time).**
`H3 武打桥 构建数据集` (uses your H3 text encoder) → `H3 武打桥 训练残差桥` → `H3 武打桥 训练 JEV 评分头`.
Training data comes from your own corpus plus rule-driven directional degradation, so good/bad pairs are generated
locally instead of downloaded.

**Step 3 — use it.**
`H3 武打语义逻辑桥` (alpha ≈ 0.12, tail-only token span) → sampler; `H3 武打提示词体检` for a score and a
per-item report; `H3 武打逻辑评分（JEV 式）` for a direct P(logic-pass) on the CONDITIONING.

## Node list

| Node | Purpose |
|---|---|
| H3 武打语义逻辑桥 | Pushes conditioning toward the fight-logic distribution (metadata preserved) |
| H3 武打逻辑评分（JEV 式） | Reads CONDITIONING with the small head → P(logic-pass) |
| H3 文本 token 段定位 | Token-span diagnostics for reference-image mode |
| H3 武打提示词体检 | Rule-engine lint (structure / physics / continuity / dialogue) |
| H3 武打桥 构建数据集 | Builds the training dataset with your H3 text encoder |
| H3 武打桥 采集训练对 | Harvests pairs from real CONDITIONING |
| H3 武打桥 训练残差桥 | Trains the residual bridge (trans / mlp) |
| H3 武打桥 训练 JEV 评分头 | Trains the JEV scoring head |
| H3 武打桥 降级预览 | Degradation preview to manufacture training pairs |
| H3 武打桥 清空缓存 | Clears the model/dataset cache |
| H3 武打编排（动作导演） | Produces the choreography and the H3 prompt ("what to fight") |

## Two scoring scales (do not mix)

* **H3LINT score** — rule engine on the prompt text (0~1 given by `H3 武打提示词体检`);
* **JEV head score** — a learned probability on the CONDITIONING tensor (0~1 given by the JEV node).
They answer different questions: the first is "is this prompt written correctly", the second is
"does this conditioning look like a real fight to the model".

## Honest limits

* The bridge can only shift what the encoder already encodes — it does not add knowledge;
* With reference-image mode (Ref2VA) keep `alpha` conservative (≤0.12) and only touch the tail tokens;
* The scoring head is trained on your own corpus, so its calibration is only as good as that corpus;
* Everything here is text-side: it cannot fix a bad sampler setting or a broken LoRA.

## License

Same as the rest of this family: MIT (see `LICENSE`).
