"""武打因果逻辑链模板（BUNNY 高动态家族启发的 WUSHU 域完整弧）。

灵感来源：BUNNY H3 Conditioning Bridge V2 的高动态语义族
（追逐/刹停再追、武器脱手与回收、遮挡后身份恢复、动量继承、撞墙反弹、
多人交接、战斗状态继承、相对朝向等）。本模块把这些概念落到**武打对决**域，
提供：

* 命名链模板（有序 beat + 必填槽位标签）
* ``render_chain``：把模板填成中/英分镜段落
* ``validate_chain_coverage``：对照词表检查文本覆盖了哪些槽位/链步

这些模板用于：种子扩写、训练对正例生成、编舞预设导出、文档对照表。
**不**直接改 CONDITIONING；权重仍须在用户 ComfyUI（H3 CLIP 5120-d）里重训。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import lexicons

# 槽位标签（与 lexicons._SLOT_BUCKETS / 新高动态桶对齐）
SLOT_TAGS = (
    "force", "distance", "defense", "contact", "feedback", "moves",
    "ownership", "occlusion", "facing", "momentum", "pursuit",
    "state_carry", "cover", "ricochet", "env_continuity", "aerial",
    "handoff", "causal",
)


@dataclass
class ChainBeat:
    """链上的一步：中英碎片 + 必填槽位。"""

    id: str
    slots: List[str]
    zh: str
    en: str


@dataclass
class ChainTemplate:
    name: str
    label_zh: str
    label_en: str
    family: str  # "fight" | "behavior"
    beats: List[ChainBeat] = field(default_factory=list)
    notes_zh: str = ""

    def required_slots(self) -> List[str]:
        seen = []
        for b in self.beats:
            for s in b.slots:
                if s not in seen:
                    seen.append(s)
        return seen


def _b(id_: str, slots: Sequence[str], zh: str, en: str) -> ChainBeat:
    return ChainBeat(id=id_, slots=list(slots), zh=zh, en=en)


# ── 命名链模板 ──────────────────────────────────────────────────────────

CHAINS: Dict[str, ChainTemplate] = {
    # A1 基础对决完整弧
    "duel_basic": ChainTemplate(
        name="duel_basic",
        label_zh="对决基础弧：逼近→测距→攻→防/反→接触→力反馈→状态→追击/终结",
        label_en="Basic duel arc: approach→measure→attack→defense/counter→contact→feedback→state→follow/finisher",
        family="fight",
        notes_zh="完整因果弧，每拍上一结果=下一起因。",
        beats=[
            _b("approach", ["force", "distance", "pursuit"],
               "{a}后脚蹬地，踏步把间距从{d0}格拉近到{d1}格",
               "{a} drives the rear foot and steps in from {d0} steps to {d1}"),
            _b("measure", ["distance", "facing"],
               "{a}在{side_a}侧面向{b}，测距确认刃长够得到胸口高度",
               "{a} on the {side_a}, facing {b}, measures blade reach to chest height"),
            _b("attack", ["force", "moves", "contact"],
               "转腰送胯普攻出「{move}」，刀尖走直线刺向{b}",
               "turns the waist into「{move}」, tip driving a straight line at {b}"),
            _b("defense", ["defense", "contact"],
               "{b}举{weapon_b}斜挡，刃对刃撞出火星",
               "{b} raises the {weapon_b} into a diagonal guard; edge meets edge, sparks fly"),
            _b("feedback", ["feedback", "momentum", "causal"],
               "因此{b}被压得后退半步，鞋底在{ground}上打滑",
               "so {b} is pushed back half a step, sole sliding on the {ground}"),
            _b("state", ["state_carry", "causal"],
               "{b}架门被压开，左肩发力仍受限，失衡未完全恢复",
               "{b}'s guard is forced open; the left shoulder stays limited, balance not fully recovered"),
            _b("follow", ["force", "moves", "feedback", "causal"],
               "{a}趁这个空档跟步送刀，终结技「{finisher}」走完整弧线，{b}沿作用线倒地不再起身",
               "{a} presses the opening with finisher「{finisher}」through a full arc; {b} falls along the line of force and does not get up"),
        ],
    ),
    # A2 缠抱 / 拆开 / 惩罚
    "clinch_break_punish": ChainTemplate(
        name="clinch_break_punish",
        label_zh="缠抱→拆开→惩罚",
        label_en="Clinch → break → punish",
        family="fight",
        beats=[
            _b("clinch", ["distance", "contact", "force"],
               "两人贴身缠抱，{a}用肘压住{b}的刀腕，间距收至半格",
               "They clinch at half a step; {a} pins {b}'s wrist with the elbow"),
            _b("break", ["force", "defense", "causal"],
               "{b}沉胯卸力拧身拆开缠抱，因此抽出半步身位",
               "{b} sinks the hips, twists free of the clinch, and gains half a step"),
            _b("punish", ["moves", "contact", "feedback", "causal"],
               "{a}顺势补「{move}」砸向敞露的肋侧，衣料闷响，{b}踉跄侧倒",
               "{a} follows with「{move}」into the open ribs; cloth thuds and {b} staggers sideways"),
        ],
    ),
    # A3 佯攻 → 实打 → 惩罚落空
    "feint_commit_punish": ChainTemplate(
        name="feint_commit_punish",
        label_zh="佯攻→实打→惩罚落空",
        label_en="Feint → commit → punish the miss",
        family="fight",
        beats=[
            _b("feint", ["moves", "facing", "distance"],
               "{a}刀尖虚点{b}胸口作佯攻，身位仍在{d0}格",
               "{a} feints a tip thrust at {b}'s chest while holding {d0} steps"),
            _b("commit", ["force", "moves", "contact"],
               "{b}上当举刀高架，{a}后脚蹬地改走「{move}」实打腰线",
               "{b} bites and raises a high guard; {a} drives the rear foot into a real「{move}」at the waist"),
            _b("punish_miss", ["defense", "feedback", "causal", "momentum"],
               "{b}高架落空，来不及回防，因此被扫中肋侧踉跄，惯性带人偏向{side_b}",
               "{b}'s high guard whiffs; too late to recover, so the sweep lands on the ribs and momentum carries {b} toward the {side_b}"),
        ],
    ),
    # A4 缴械 → 夺回 / 徒手续战
    "disarm_reclaim": ChainTemplate(
        name="disarm_reclaim",
        label_zh="缴械→武器回收或徒手续战",
        label_en="Disarm → reclaim weapon OR continue empty-hand",
        family="fight",
        beats=[
            _b("disarm", ["contact", "ownership", "feedback", "force"],
               "{a}刀脊磕开{b}的握把，{weapon_b}脱手落地，归属从{b}转到地面",
               "{a}'s spine knocks {b}'s grip; the {weapon_b} drops — ownership leaves {b} to the ground"),
            _b("choice", ["ownership", "distance", "pursuit"],
               "{b}撤步测距：要么俯身捡回{weapon_b}，要么改空手架门续战",
               "{b} steps back to measure: either reclaim the {weapon_b} or fight empty-hand"),
            _b("reclaim_or_empty", ["ownership", "force", "moves", "causal"],
               "{b}俯身捡回{weapon_b}，于是握持权回到{b}；{a}趁弯腰空档跟步补刀",
               "{b} stoops and reclaims the {weapon_b}, so ownership returns; {a} presses the stoop with a follow-up cut"),
        ],
    ),
    # A5 撞墙反弹 → 动量继承
    "wall_rebound": ChainTemplate(
        name="wall_rebound",
        label_zh="击退撞墙→反弹→动量继承续打",
        label_en="Knockback off wall → rebound → inherit momentum",
        family="fight",
        beats=[
            _b("knockback", ["feedback", "momentum", "force"],
               "{a}一记重劈把{b}击退，后背撞上实体{wall}，冲击沿脊柱回传",
               "{a}'s heavy cut knocks {b} back into the solid {wall}; impact travels up the spine"),
            _b("rebound", ["momentum", "force", "causal"],
               "因此{b}借墙面反弹前冲，动量未泄，顺势把余势送进下一刀",
               "so {b} rebounds off the wall, momentum intact, and rides it into the next cut"),
            _b("continue", ["moves", "contact", "feedback", "momentum"],
               "{b}带着撞墙余势「{move}」反击，刃面擦过{a}肩甲溅起火星",
               "{b} counters with「{move}」on the rebound; the edge grazes {a}'s shoulder with sparks"),
        ],
    ),
    # A6 多人交接 / 排序
    "multi_handoff": ChainTemplate(
        name="multi_handoff",
        label_zh="多人交接：谁打谁、下一拍谁接手",
        label_en="Multi-opponent handoff / attack ordering",
        family="fight",
        beats=[
            _b("focus", ["facing", "distance", "handoff"],
               "{a}正对{b}，暂时把{c}压在视野边缘，先结算与{b}的这一拍",
               "{a} faces {b}, keeping {c} at the edge of vision, and resolves this beat with {b} first"),
            _b("handoff", ["handoff", "causal", "facing"],
               "{b}被打下后，攻击权交接给{c}：{c}从{side_c}侧上步接手",
               "After {b} is dropped, initiative hands off to {c}, who steps in from the {side_c}"),
            _b("order", ["moves", "contact", "feedback", "handoff"],
               "{a}回身对{c}出「{move}」，明确下一拍目标是{c}而不是已倒地的{b}",
               "{a} turns on {c} with「{move}」— next target is {c}, not the downed {b}"),
        ],
    ),
    # A7 腾空 / 跳跃：起跳力 + 落地卸力
    "aerial_jump": ChainTemplate(
        name="aerial_jump",
        label_zh="腾空攻击：起跳借力→空中轨迹→落地卸力",
        label_en="Aerial / jump attack: takeoff force + landing unload",
        family="fight",
        beats=[
            _b("takeoff", ["force", "aerial", "momentum"],
               "{a}后脚蹬{ground}借力起跳，腰胯上送，双脚离地",
               "{a} drives the rear foot off the {ground} into a jump, hips lifting, both feet leave"),
            _b("air", ["moves", "aerial", "contact"],
               "空中走「{move}」弧线劈下，刃口对准{b}肩线",
               "In air,「{move}」arcs downward with the edge lined on {b}'s shoulder"),
            _b("landing", ["force", "aerial", "feedback", "causal"],
               "落地屈膝卸力，冲击散入地面，于是站稳再跟步，没有踉跄失序",
               "Lands with knees bent to unload; force dumps into the ground, then steps in without staggering"),
        ],
    ),
    # B1 武器归属
    "weapon_ownership": ChainTemplate(
        name="weapon_ownership",
        label_zh="武器归属：谁握持、脱手后谁捡回",
        label_en="Ownership: who holds which weapon; who recovers after drop",
        family="behavior",
        beats=[
            _b("hold", ["ownership"],
               "{a}双手握持{weapon_a}，{b}右手握持{weapon_b}，归属明确",
               "{a} holds {weapon_a} in both hands; {b} holds {weapon_b} in the right — ownership clear"),
            _b("drop", ["ownership", "feedback", "contact"],
               "交锋中{weapon_b}被磕脱手，落地在两人之间的{ground}上",
               "In the clash the {weapon_b} is knocked free and lands on the {ground} between them"),
            _b("recover", ["ownership", "pursuit", "causal"],
               "{b}俯身捡回，于是握持权回到{b}；或{a}抢先踩住刀脊阻止回收",
               "{b} stoops to reclaim so ownership returns; or {a} pins the spine first to deny recovery"),
        ],
    ),
    # B2 遮挡后身份恢复
    "occlusion_reappear": ChainTemplate(
        name="occlusion_reappear",
        label_zh="遮挡后入画：仍是同一张脸/服装/武器",
        label_en="Occlusion then re-ID: same face / costume / weapon",
        family="behavior",
        beats=[
            _b("occlude", ["occlusion", "cover"],
               "{a}被{cover}短暂遮挡出画，面部与兵器暂时不可见",
               "{a} is briefly occluded by the {cover} and leaves frame — face and weapon unseen"),
            _b("reappear", ["occlusion", "ownership", "facing"],
               "{a}从{cover}另一侧入画，仍是同一张脸、同一套服装与武器，朝向未互换",
               "{a} re-enters from the other side of the {cover}, still the same face, costume and weapon, facing unchanged"),
        ],
    ),
    # B3 相对朝向 / 左右
    "facing_swap": ChainTemplate(
        name="facing_swap",
        label_zh="换位后相对朝向与左右锁定",
        label_en="Relative facing / left-right after position swap",
        family="behavior",
        beats=[
            _b("before", ["facing", "distance"],
               "换位前：{a}在左侧面向右，{b}在右侧面向左，间距{d0}格",
               "Before swap: {a} left facing right, {b} right facing left, {d0} steps apart"),
            _b("swap", ["facing", "pursuit", "force"],
               "两人绕步换位，{a}转到原{b}一侧，必须重申新的左右与朝向",
               "They circle-swap; {a} takes {b}'s former side — new left/right and facing must be restated"),
            _b("after", ["facing", "distance", "causal"],
               "换位后：{a}在右侧面向左，{b}在左侧面向右，间距仍{d1}格，没有左右颠倒串人",
               "After swap: {a} right facing left, {b} left facing right, still {d1} steps — no mirrored identity swap"),
        ],
    ),
    # B4 追逐 / 超车 / 刹停再交手
    "pursuit_reengage": ChainTemplate(
        name="pursuit_reengage",
        label_zh="追击→超步→刹停再交手（对决步法版）",
        label_en="Pursuit → overtake → brake and re-engage",
        family="behavior",
        beats=[
            _b("chase", ["pursuit", "distance", "force"],
               "{a}蹬地追击，把间距从{d0}格压缩到{d1}格",
               "{a} drives off in pursuit, closing from {d0} steps to {d1}"),
            _b("overtake", ["pursuit", "facing", "momentum"],
               "{a}外侧超步越过{b}肩线，朝向短暂同向",
               "{a} overtakes on the outside past {b}'s shoulder, briefly matching facing"),
            _b("brake", ["pursuit", "force", "causal", "defense"],
               "于是{a}蹬地刹停回身，重新对面向{b}举刀交手",
               "so {a} plants to brake, turns back, and re-engages facing {b} with the blade up"),
        ],
    ),
    # B5 掩体 / 道具破碎 → 碎屑状态继承
    "cover_debris": ChainTemplate(
        name="cover_debris",
        label_zh="掩体/道具破碎→碎屑状态跨镜继承",
        label_en="Cover / prop break → debris state inheritance",
        family="behavior",
        beats=[
            _b("break", ["cover", "contact", "feedback"],
               "{a}刀劈中{cover}，木柱裂开，碎屑溅落在{ground}上",
               "{a}'s cut splits the {cover}; debris sprays onto the {ground}"),
            _b("inherit", ["cover", "env_continuity", "state_carry", "causal"],
               "下一镜碎屑仍在原位未复原，两人踩过木屑继续交手",
               "Next shot the debris stays where it fell; both fighters step through chips and keep fighting"),
        ],
    ),
    # B6 弹刀 / 反弹几何
    "ricochet_geometry": ChainTemplate(
        name="ricochet_geometry",
        label_zh="弹刀/格开后刃路几何延续",
        label_en="Catch / ricochet geometry — deflected path continues",
        family="behavior",
        beats=[
            _b("deflect", ["ricochet", "contact", "defense"],
               "{b}刀脊格开{a}的来刃，来刃沿入射角反弹改向{side_b}",
               "{b}'s spine deflects {a}'s edge; the blade ricochets along the incidence toward the {side_b}"),
            _b("continue_path", ["ricochet", "momentum", "feedback", "causal"],
               "因此偏转后的刀势擦过灯笼柱溅起火星，路径连续可追，没有瞬移改向",
               "so the deflected arc grazes the lantern post with sparks — path continuous, no teleport turn"),
        ],
    ),
    # B7 战斗状态跨镜继承
    "injury_state_carry": ChainTemplate(
        name="injury_state_carry",
        label_zh="伤势/状态跨镜继承（伤肩仍受限）",
        label_en="Combat-state inheritance across shots",
        family="behavior",
        beats=[
            _b("injure", ["feedback", "state_carry", "contact"],
               "{b}左肩衣料撕裂渗血，这一拍结束后伤肩发力仍受限",
               "{b}'s left shoulder cloth tears and bleeds; after this beat the injured shoulder stays limited"),
            _b("carry", ["state_carry", "defense", "causal"],
               "下一镜{b}举刀仍抬不高伤侧，因此只能侧闪硬吃，架门缺一角",
               "Next shot {b} still cannot raise the injured side high, so only a side-slip absorbs — guard missing a corner"),
        ],
    ),
    # B8 环境连续性
    "env_continuity": ChainTemplate(
        name="env_continuity",
        label_zh="环境连续：湿石仍湿、尘土留痕",
        label_en="Environment continuity: wet stone stays wet; dust from prior hit",
        family="behavior",
        beats=[
            _b("mark", ["env_continuity", "feedback"],
               "上一拍扬起的尘土 / 溅起的水花仍留在{ground}上",
               "Dust / water from the prior hit still marks the {ground}"),
            _b("persist", ["env_continuity", "state_carry", "causal"],
               "下一镜地面仍湿滑，{a}踏步时鞋底打滑，环境状态未重置",
               "Next shot the ground stays wet and slick; {a}'s sole skids — environment not reset"),
        ],
    ),
    # 额外：反击惩罚链（常用组合）
    "counter_punish": ChainTemplate(
        name="counter_punish",
        label_zh="防守反击→惩罚空档",
        label_en="Defense counter → punish the opening",
        family="fight",
        beats=[
            _b("incoming", ["moves", "force", "distance"],
               "{b}上步「{move}」劈来，间距收到{d1}格",
               "{b} steps in with「{move}」, closing to {d1} steps"),
            _b("counter", ["defense", "contact", "causal"],
               "{a}斜挡卸力，因此借反弹空档转守为攻",
               "{a} parries and sheds force, so the rebound opens a counter window"),
            _b("punish", ["moves", "feedback", "force", "causal"],
               "{a}顺势「{finisher}」打进敞门，{b}踉跄失去平衡",
               "{a} rides into「{finisher}」through the open guard; {b} staggers off-balance"),
        ],
    ),
    # 武器交接（主动换手，非缴械）
    "weapon_handoff": ChainTemplate(
        name="weapon_handoff",
        label_zh="主动换手 / 递兵：归属瞬时转移",
        label_en="Active weapon handoff — ownership transfer",
        family="behavior",
        beats=[
            _b("offer", ["ownership", "facing"],
               "{a}将{weapon_a}刀柄朝外递向同伴，握持权准备转移",
               "{a} offers the {weapon_a} hilt-out toward an ally — ownership about to transfer"),
            _b("take", ["ownership", "causal"],
               "同伴接住刀柄，于是握持权从{a}转到同伴，{a}改空手架",
               "The ally catches the hilt, so ownership leaves {a}; {a} switches to empty-hand guard"),
        ],
    ),
}


DEFAULT_FIGHTERS = {"a": "角色A", "b": "角色B", "c": "角色C"}
DEFAULT_FIGHTERS_EN = {"a": "Fighter A", "b": "Fighter B", "c": "Fighter C"}
DEFAULT_WEAPONS = {"weapon_a": "太刀", "weapon_b": "单刀", "weapon_c": "短棍"}
DEFAULT_WEAPONS_EN = {"weapon_a": "tachi", "weapon_b": "saber", "weapon_c": "short staff"}
DEFAULT_SCENE = {
    "ground": "湿石板", "wall": "土墙", "cover": "灯笼柱",
    "side_a": "左", "side_b": "右", "side_c": "右后方",
    "d0": "2", "d1": "1", "move": "过肩劈", "finisher": "斜劈",
}
DEFAULT_SCENE_EN = {
    "ground": "wet stone", "wall": "earthen wall", "cover": "lantern post",
    "side_a": "left", "side_b": "right", "side_c": "rear-right",
    "d0": "2", "d1": "1", "move": "overhead chop", "finisher": "diagonal slash",
}


def list_chains(family: Optional[str] = None) -> List[str]:
    names = []
    for k, c in CHAINS.items():
        if family is None or c.family == family:
            names.append(k)
    return names


def get_chain(name: str) -> ChainTemplate:
    if name not in CHAINS:
        raise KeyError(f"未知逻辑链：{name}，可选 {list(CHAINS)}")
    return CHAINS[name]


def render_chain(
    name: str,
    lang: str = "zh",
    fighters: Optional[Dict[str, str]] = None,
    weapons: Optional[Dict[str, str]] = None,
    scene: Optional[Dict[str, str]] = None,
    as_shots: bool = True,
) -> List[str]:
    """把命名链渲染成有序段落（默认按 beat 合成 shot 段落字符串列表）。"""
    chain = get_chain(name)
    zh = lang.lower().startswith("zh")
    ctx: Dict[str, str] = {}
    ctx.update(DEFAULT_SCENE_EN if not zh else DEFAULT_SCENE)
    ctx.update(DEFAULT_FIGHTERS_EN if not zh else DEFAULT_FIGHTERS)
    ctx.update(DEFAULT_WEAPONS_EN if not zh else DEFAULT_WEAPONS)
    if scene:
        ctx.update(scene)
    if fighters:
        ctx.update(fighters)
    if weapons:
        ctx.update(weapons)

    paragraphs: List[str] = []
    for i, beat in enumerate(chain.beats):
        tmpl = beat.zh if zh else beat.en
        try:
            text = tmpl.format(**ctx)
        except KeyError:
            text = tmpl
        if as_shots:
            prefix = f"[Shot {i + 1}] " if i == 0 else f"[Shot {i + 1}] At 00:{i * 2:02d}.000."
            paragraphs.append(prefix + text + ("。" if zh and not text.endswith(("。", ".", "!", "?", "！", "？")) else ""))
        else:
            paragraphs.append(text)
    return paragraphs


def render_chain_text(
    name: str,
    lang: str = "zh",
    fighters: Optional[Dict[str, str]] = None,
    weapons: Optional[Dict[str, str]] = None,
    scene: Optional[Dict[str, str]] = None,
) -> str:
    return "\n".join(render_chain(name, lang, fighters, weapons, scene, as_shots=True))


# 槽位 → lexicons 桶名映射（coverage 用）
_SLOT_TO_BUCKET = {
    "force": "force_chain",
    "distance": "distance",
    "defense": "defense",
    "contact": "contact",
    "feedback": "feedback",
    "moves": "move_names",
    "ownership": "ownership",
    "occlusion": "occlusion",
    "facing": "facing",
    "momentum": "momentum",
    "pursuit": "pursuit",
    "state_carry": "state_carry",
    "cover": "cover",
    "ricochet": "ricochet",
    "env_continuity": "env_continuity",
    "aerial": "aerial",
    "handoff": "handoff",
    "causal": "causal",
}


def validate_chain_coverage(text: str, chain_name: Optional[str] = None) -> Dict[str, Any]:
    """对照词表（及可选指定链）检查文本覆盖了哪些高动态/武打槽位。"""
    slots = lexicons.slots_present(text)
    # causal 单独用 logic_score 词表近似
    from .logic_score import CAUSAL_ZH, CAUSAL_EN
    low = text.lower()
    causal_n = sum(low.count(w.lower() if w.isascii() else w) for w in (CAUSAL_ZH + CAUSAL_EN))
    slots["causal"] = causal_n

    present = {k: v for k, v in slots.items() if v > 0}
    missing_global = [k for k in (
        "force_chain", "distance", "defense", "contact", "feedback",
        "ownership", "occlusion", "momentum", "pursuit", "state_carry",
        "facing", "cover", "ricochet", "env_continuity", "aerial", "handoff",
    ) if slots.get(k, 0) == 0]

    report: Dict[str, Any] = {
        "slots": slots,
        "present": sorted(present.keys()),
        "missing_high_dynamic": missing_global,
        "coverage_ratio": round(1.0 - len(missing_global) / 16.0, 3),
        "causal_hits": causal_n,
    }

    if chain_name:
        chain = get_chain(chain_name)
        beat_hits = []
        missing_slots = []
        for beat in chain.beats:
            ok_slots = []
            bad_slots = []
            for s in beat.slots:
                bucket = _SLOT_TO_BUCKET.get(s, s)
                # causal 特殊
                n = causal_n if s == "causal" else slots.get(bucket, 0)
                if n > 0:
                    ok_slots.append(s)
                else:
                    bad_slots.append(s)
                    if s not in missing_slots:
                        missing_slots.append(s)
            beat_hits.append({
                "id": beat.id,
                "ok": len(bad_slots) == 0,
                "hit_slots": ok_slots,
                "miss_slots": bad_slots,
            })
        report["chain"] = chain_name
        report["chain_label"] = chain.label_zh
        report["beat_hits"] = beat_hits
        report["chain_missing_slots"] = missing_slots
        report["chain_coverage"] = round(
            sum(1 for b in beat_hits if b["ok"]) / max(1, len(beat_hits)), 3
        )
    return report


def chain_preset_catalog() -> List[Dict[str, Any]]:
    """给编舞节点 / README 用的轻量目录。"""
    out = []
    for name, c in CHAINS.items():
        out.append({
            "name": name,
            "label_zh": c.label_zh,
            "label_en": c.label_en,
            "family": c.family,
            "beats": len(c.beats),
            "slots": c.required_slots(),
        })
    return out


# 编舞可调用的短名列表
CHOREO_CHAIN_PRESETS: List[str] = list(CHAINS.keys())
