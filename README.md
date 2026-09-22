# ComfyUI-H3-WushuBridge · MiniMax H3 武打语义逻辑翻译桥

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
   E:\wushulong\dataset\h3_train\metadata.csv     924 条（列 video,prompt,input_audio,frame_rate）
   E:\wushulong\dataset\clips                     1847 条（924 英 + 923 中，中文版 [镜头n]）
   E:\wushulong\docs\提示词库.md                   37 条
   E:\wushulong\h3_fight_skills                   10 条
   ```

   建 **ref2v** 数据集时再加上这份**官方六段 Ref2VA 成品**（格式 100% 可迁移，
   但内容是文戏，武打逻辑分低，别当武打正例用）：

   ```text
   E:\wushulong\H3武斗模拟器-v9.12\_template_sources\drama\h3-prompts-yajni\examples\晴天收信人_H3独立8秒提示词.md   38 条
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

| 节点 | 输入 → 输出 | 用途 |
|---|---|---|
| H3 武打语义逻辑桥（接在 conditioning 之间） | CONDITIONING → CONDITIONING + report + score | 主力节点，夹在 conditioning 之间 |
| H3 武打逻辑评分（JEV 式） | CONDITIONING → score + report + pass | 不吐字直接给概率，可当筛选/分流开关 |
| H3 武打提示词体检（规则引擎） | STRING → score + grade + report | h3lint 的 Python 版，八维诊断 |
| H3 武打桥 构建数据集 | CLIP + 语料路径 → *.npz | 用 H3 文本编码器把正/负例编码成训练数据 |
| H3 武打桥 采集训练对 | 两条 CONDITIONING → 追加到数据集 | 参考图模式：直接采含 ref token 的真实样本 |
| H3 武打桥 训练残差桥 | dataset → safetensors | 训练桥 |
| H3 武打桥 训练 JEV 评分头 | dataset → safetensors | 训练评分头 |
| H3 武打桥 降级预览 | 正例文本 → 负例文本 | 看训练对长什么样，调降级强度 |
| H3 文本 token 段定位 | 两段 CONDITIONING → start/end | 参考图模式诊断：文本 token 落在哪一段 |
| H3 武打桥 清空缓存 | — | 换权重后清显存缓存 |

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

仓库里的模型（语义桥 + JEV 评分头）**不放在 GitHub**（避免把二进制塞进 git 历史），
而是放在 Hugging Face（**公开仓库**，可直接下载，无需登录）：

**权重仓库**：https://huggingface.co/Jojocodex/h3-wushu-bridge-weights

| 文件 | 大小 | 用途 |
|---|---|---|
| [wushu_bridge_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_wushu_v1.safetensors) | 16MB | **语义桥**（默认 trans 架构 2 层 d=256） |
| [wushu_jev_wushu_v1.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_wushu_v1.safetensors) | 6.7MB | **JEV 评分头**（conditioning → P(武打逻辑合格)） |
| [wushu_bridge_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_bridge_cloud.safetensors) · [wushu_jev_cloud.safetensors](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_jev_cloud.safetensors) | 16MB / 3MB | 早期版本（对照用） |
| [wushu_pairs_v1_pairs.jsonl](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1_pairs.jsonl) · [wushu_pairs_v1.json](https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main/wushu_pairs_v1.json) | 1.6MB / 308KB | 训练对清单（可**重建数据集**） |
| `*_report.json` | 8–18KB | 训练报告（参数量/准确率/AUC/ECE/漂移/逐轮历史） |

**安装（一条命令）**：

```bash
# 装到插件的权重目录（ComfyUI 会自动在这里找）
mkdir -p ComfyUI/models/wushu_bridge && cd ComfyUI/models/wushu_bridge
BASE=https://huggingface.co/Jojocodex/h3-wushu-bridge-weights/resolve/main
curl -L -O $BASE/wushu_bridge_wushu_v1.safetensors
curl -L -O $BASE/wushu_jev_wushu_v1.safetensors
curl -L -O $BASE/wushu_pairs_v1_pairs.jsonl
```

**接线**：
* **H3 武打语义逻辑桥** → `bridge` 选 `wushu_bridge_wushu_v1.safetensors`，`judge` 选 `wushu_jev_wushu_v1.safetensors`；
* **H3 武打逻辑评分（JEV 式）** → `judge` 选 `wushu_jev_wushu_v1.safetensors`，`aggregate=mean`，`threshold=0.5`。

**参考跑参**：`alpha ≈ 0.12`、`magnitude_match=per_token`、`token_span=all`（参考图模式用 `tail`）。

**想自己训练**：见下面「第 2 步 · 训一次」；训练出的权重会写到 `ComfyUI/models/wushu_bridge/`，
与这里下载的完全同构（可直接互相替换）。

## Model download (no training required)

The models (semantic bridge + JEV scoring head) are **not** stored in the GitHub repo (to keep binary blobs out of
git history). They live on Hugging Face in a **public** repo — direct download, no login:

**Weights repo**: https://huggingface.co/Jojocodex/h3-wushu-bridge-weights

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

**Wiring**: bridge node → `bridge = wushu_bridge_wushu_v1.safetensors`, `judge = wushu_jev_wushu_v1.safetensors`;
JEV score node → `judge = wushu_jev_wushu_v1.safetensors`, `aggregate = mean`, `threshold = 0.5`.

**Reference settings**: `alpha ≈ 0.12`, `magnitude_match = per_token`, `token_span = all` (`tail` for reference-image mode).
**Train your own instead**: see “Step 2 · train once” above; the weights land in `ComfyUI/models/wushu_bridge/`
with the same layout, so they are interchangeable with the downloads.


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
