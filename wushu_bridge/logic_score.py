"""武打逻辑评分（中英双语）：把「这段提示词懂不懂武打」量化成 0~1。

为什么需要它，而不是直接用 h3lint 的分数
----------------------------------------
``lint/h3lint.py``（h3lint.js 的忠实移植）是**中文语境**的规则引擎：它用
「格挡／闪避／反击」「于是／随即」这类中文词表判"有没有防守反应""有没有因果链"。
用户 924 条同分布语料是**英文为主**的，那些检查在英文稿上会大量误报——
一份写了 "blocks, sidesteps, rolls low to escape" 的稿子仍会被判
「全文没有任何格挡／闪避／反击的回应动作」。

所以标签分（以及给用户看的诊断）用**两层复合**：

* ``format``  ：h3lint 原分，管壳结构、时间码、平台安全、对白规范；
* ``logic``   ：本模块的武打逻辑分，中英双语判据，管力线/格距/防守/命中反馈/因果/结局。

最终 ``composite = 0.4 * format + 0.6 * logic``。逻辑占大头，因为桥和评分头学的
就是逻辑；壳结构在 H3 那边本来就由模板保证。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import lexicons

SHOT_RE = re.compile(r"\[(?:Shot|镜头|鏡頭)\s*\d+\]")

# 因果 / 承接连接词：武打分镜必须是"上一拍的结果变成下一拍的起因"
CAUSAL_ZH = [
    "于是", "随即", "紧接着", "接着", "随后", "趁", "因此", "导致", "被", "逼得",
    "迫使", "来不及", "结果", "顺势", "借着", "借这个", "反过来", "立刻", "不等",
]
CAUSAL_EN = [
    "then", "after", "as ", "because", "so ", "forcing", "forced", "causing",
    "causes", "follows", "following", "in response", "responds", "which",
    "and then", "before", "drives", "driving", "leaving", "knocked",
    "therefore", "as a result", "which lets", "off the rebound", "riding the",
]

# 结局 / 终结信号
FINISH_ZH = ["终结技", "倒地", "不再起身", "跪地", "单膝", "脱手", "仰面", "侧倒", "失去平衡", "倒下"]
FINISH_EN = [
    "finisher", "finishing blow", "final strike", "falls", "collapses", "sprawls",
    "drops to one knee", "kneels", "does not get up", "can't get up", "knocked down",
    "loses his weapon", "disarmed", "stays down", "pinned",
]

# 时间码 / 镜头时长
TIMECODE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|~|到|至)\s*(\d+(?:\.\d+)?)\s*(?:秒|s\b|seconds?)", re.I)

_TRIGGER_HINT = ("wushu_action", "action,", "【场景】", "scene:")


@dataclass
class LogicCheck:
    id: str
    label: str
    weight: float
    score: float           # 0~1
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "label": self.label, "weight": self.weight,
                "score": round(self.score, 4), "detail": self.detail}


@dataclass
class LogicReport:
    score: float = 0.0
    grade: str = "D"
    checks: List[LogicCheck] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    language: str = "zh"

    def to_text(self) -> str:
        lines = [
            f"武打逻辑分 {self.score*100:.0f}/100（{self.grade}）｜语种 {self.language}"
            f"｜分镜 {self.stats.get('shots', 0)} 个"
        ]
        for c in sorted(self.checks, key=lambda x: x.score):
            if c.score >= 0.85:
                continue
            mark = "x" if c.score < 0.4 else "!"
            lines.append(f"  {mark} {c.label} ({c.score*100:.0f}/100)：{c.detail}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "grade": self.grade,
            "language": self.language,
            "stats": self.stats,
            "checks": [c.to_dict() for c in self.checks],
        }


def _split_shots(text: str) -> List[str]:
    pos = [m.start() for m in SHOT_RE.finditer(text)]
    if not pos:
        return []
    shots = []
    for i, p in enumerate(pos):
        end = pos[i + 1] if i + 1 < len(pos) else len(text)
        shots.append(text[p:end])
    return shots


def _hit(shot: str, words: Sequence[str]) -> bool:
    low = shot.lower()
    return any((w.lower() if w.isascii() else w) in low for w in words)


def _ratio(shots: Sequence[str], words: Sequence[str]) -> Tuple[float, int]:
    if not shots:
        return 0.0, 0
    n = sum(1 for s in shots if _hit(s, words))
    return n / len(shots), n


def _grade(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.78:
        return "B"
    if score >= 0.62:
        return "C"
    return "D"


def score_logic(text: str, mode: str = "final", lang: Optional[str] = None) -> LogicReport:
    """给武打提示词打「逻辑分」（0~1）。``mode='design'`` 时放宽骨架要求。"""
    text = text or ""
    shots = _split_shots(text)
    language = lang or ("zh" if lexicons.is_chinese(text) else "en")

    checks: List[LogicCheck] = []

    # ── 1. 骨架（触发词 / 时长 / 帧数 / 比例）──────────────────────────
    if mode == "design":
        checks.append(LogicCheck("formation", "骨架（设计稿模式不查）", 0.3, 1.0, "已跳过"))
    else:
        head = text[:400].lower()
        hits = [t for t in _TRIGGER_HINT if t.lower() in head]
        has_dur = bool(re.search(r"\d+(?:\.\d+)?\s*(?:seconds?|秒)", text, re.I))
        has_frames = bool(re.search(r"\b\d{2,4}\s*frames?\b|帧", text, re.I))
        s = (0.5 if hits else 0.0) + 0.25 * has_dur + 0.25 * has_frames
        checks.append(LogicCheck(
            "formation", "开工头（触发词/时长/帧数）", 0.7, min(1.0, s),
            f"触发词 {hits or '缺'}，时长 {'有' if has_dur else '缺'}，帧数 {'有' if has_frames else '缺'}",
        ))

    # ── 2. 分镜结构 ────────────────────────────────────────────────────
    if not shots:
        checks.append(LogicCheck("shot-structure", "分镜结构", 1.0, 0.0, "没有找到 [Shot n] / [镜头n] 分镜标记"))
    else:
        tc = sum(1 for s in shots if TIMECODE_RE.search(s))
        has_cam = sum(1 for s in shots if _hit(s, lexicons.CAMERA))
        s = min(1.0, 0.5 * (tc / len(shots)) + 0.5 * (has_cam / len(shots)))
        checks.append(LogicCheck(
            "shot-structure", "分镜结构（分镜/时间码/运镜）", 1.0, s,
            f"{len(shots)} 镜，带时间码 {tc}，带运镜 {has_cam}",
        ))

    # ── 3. 力线 ────────────────────────────────────────────────────────
    r, n = _ratio(shots, lexicons.FORCE_CHAIN)
    checks.append(LogicCheck("force-chain", "力线（蹬地/转腰/重心·weight/hips/momentum）", 1.4, r,
                             f"{n}/{len(shots)} 拍写了发力链"))

    # ── 4. 格距 / 站位 ────────────────────────────────────────────────
    r, n = _ratio(shots, lexicons.DISTANCE)
    checks.append(LogicCheck("distance", "格距与站位", 1.0, r, f"{n}/{len(shots)} 拍交代了距离/位置"))

    # ── 5. 防守反应（英文稿最容易被中文规则误判的一项）────────────────
    r, n = _ratio(shots, lexicons.DEFENSE)
    checks.append(LogicCheck("defense-response", "防守反应（格挡/闪避/翻滚·block/parry/roll）", 1.4, r,
                             f"{n}/{len(shots)} 拍有防守或回避动作"))

    # ── 6. 接触点 / 命中判定 ──────────────────────────────────────────
    r, n = _ratio(shots, lexicons.CONTACT)
    checks.append(LogicCheck("contact-decision", "接触点与命中判定", 1.2, r,
                             f"{n}/{len(shots)} 拍明确了打中/擦过/落空"))

    # ── 7. 打击反馈 ────────────────────────────────────────────────────
    r, n = _ratio(shots, lexicons.FEEDBACK)
    checks.append(LogicCheck("impact-feedback", "打击反馈（火星/踉跄/衣破·sparks/stagger）", 1.4, r,
                             f"{n}/{len(shots)} 拍有可见的物理反馈"))

    # ── 8. 招式具体度 ─────────────────────────────────────────────────
    move_hits = sum(1 for s in shots if _hit(s, lexicons.MOVE_NAMES))
    checks.append(LogicCheck(
        "specific-moves", "招式具体度", 0.8,
        min(1.0, move_hits / max(1, len(shots))) if shots else 0.0,
        f"{move_hits}/{len(shots)} 拍写了具体招式名（而不是「一次攻击」这类泛化写法）",
    ))

    # ── 9. 因果链 ──────────────────────────────────────────────────────
    words = CAUSAL_ZH + CAUSAL_EN
    r, n = _ratio(shots, words)
    checks.append(LogicCheck("causal-chain", "因果链（上一拍的结果=下一拍的起因）", 1.2, r,
                             f"{n}/{len(shots)} 拍有承接/因果连接词"))

    # ── 10. 结局 ───────────────────────────────────────────────────────
    if mode == "design":
        checks.append(LogicCheck("finish-result", "结局（设计稿模式不查）", 0.4, 1.0, "已跳过"))
    elif shots:
        last = shots[-1]
        ok = _hit(last, FINISH_ZH + FINISH_EN)
        checks.append(LogicCheck("finish-result", "死线前有结果", 1.2, 1.0 if ok else 0.0,
                                 "末拍写了终结/倒地/脱手" if ok else "末拍没有结果（死线前必须分出胜负）"))
    else:
        checks.append(LogicCheck("finish-result", "死线前有结果", 1.2, 0.0, "没有分镜可判"))

    # ── 11. 开场不站桩 ────────────────────────────────────────────────
    opening = text[: max(200, len(text) // 5)].lower()
    idle = [w for w in lexicons.LOGIC_HOLES["idle_open"] if w.lower() in opening]
    checks.append(LogicCheck("no-idle-open", "开场不站桩", 0.8, 0.0 if idle else 1.0,
                             f"开场出现{idle}" if idle else "开场直接交手"))

    # ── 12. 逻辑漏洞 ──────────────────────────────────────────────────
    holes = lexicons.logic_hole_hits(text)
    holes.pop("idle_open", None)
    penalty = min(1.0, sum(len(v) for v in holes.values()) / 6.0)
    checks.append(LogicCheck("no-logic-holes", "无逻辑漏洞（慢动作/瞬移/特效/UI/风格反噬）", 0.8, 1.0 - penalty,
                             "干净" if not holes else f"命中：{ {k: v[:3] for k, v in holes.items()} }"))

    # ── 13. 高动态槽位（BUNNY-inspired）──────────────────────────────
    hd_keys = [
        ("ownership", "武器归属（握持/脱手/捡回）", lexicons.OWNERSHIP, 0.7),
        ("occlusion-reid", "遮挡后再识别", lexicons.OCCLUSION, 0.6),
        ("momentum", "动量/击退/反弹继承", lexicons.MOMENTUM, 0.7),
        ("state-carry", "伤势/状态跨镜继承", lexicons.STATE_INHERIT, 0.7),
        ("pursuit", "追击/刹停再交手", lexicons.PURSUIT, 0.5),
        ("facing", "相对朝向/左右", lexicons.FACING, 0.5),
    ]
    for cid, label, words, w in hd_keys:
        r, n = _ratio(shots, words)
        # 高动态槽位：有则加分；全缺不重罚（种子未必条条都有）
        soft = 0.55 + 0.45 * r if n else 0.55
        checks.append(LogicCheck(cid, label, w, soft,
                                 f"{n}/{len(shots)} 拍命中" if shots else "无分镜"))

    # ── 14. 因果链强度：全文 ≥2 个因果连接 + 分镜覆盖 ────────────────
    causal_words = CAUSAL_ZH + CAUSAL_EN
    low = text.lower()
    causal_hits = sum(1 for w in causal_words if (w.lower() if w.isascii() else w) in low)
    r, n = _ratio(shots, causal_words)
    # 强化：既要覆盖率，也要绝对数量 ≥2
    strength = min(1.0, 0.5 * r + 0.5 * min(1.0, causal_hits / 4.0))
    if causal_hits < 2:
        strength = min(strength, 0.35)
    # 覆盖掉旧的 causal-chain check（id 相同则替换）
    checks = [c for c in checks if c.id != "causal-chain"]
    checks.append(LogicCheck(
        "causal-chain", "因果链（≥2 连接词 + 拍间承接）", 1.4, strength,
        f"连接词命中约 {causal_hits}，{n}/{len(shots)} 拍有承接",
    ))

    # ── 15. 多镜状态继承（可选加分项）────────────────────────────────
    if len(shots) >= 2:
        carry_n = sum(1 for s in shots if _hit(s, lexicons.STATE_INHERIT + lexicons.OCCLUSION + lexicons.ENV_CONTINUITY))
        carry_score = min(1.0, 0.4 + 0.6 * (carry_n / len(shots)))
        checks.append(LogicCheck(
            "multi-shot-inherit", "多镜状态/身份/环境继承", 0.6, carry_score,
            f"{carry_n}/{len(shots)} 拍带继承短语",
        ))


    # ── 16. H3 六大翻车硬检查（用户实测失败模式）────────────────────
    def _shot_has(shot: str, words) -> bool:
        return _hit(shot, words)

    # 16a 跳跃无因：出现 JUMP_BARE 却没有 JUMP_CAUSE / force
    jump_bad = 0
    jump_total = 0
    for s in shots:
        if _shot_has(s, lexicons.JUMP_BARE) or _shot_has(s, ["腾空", "跳跃", "leap", "jumps"]):
            jump_total += 1
            if not (_shot_has(s, lexicons.JUMP_CAUSE) or _shot_has(s, lexicons.FORCE_CHAIN)):
                jump_bad += 1
            # 有跳跃也应有落地卸力（同镜或后文）
            if not _shot_has(s, ["落地屈膝", "卸力", "lands with knees", "unload", "landing"]):
                jump_bad += 0.5
    if jump_total:
        jump_score = max(0.0, 1.0 - jump_bad / max(jump_total, 1))
        detail = f"{jump_total} 处跳跃，无因/缺卸力记 {jump_bad}"
    else:
        jump_score = 0.7  # 无跳跃不扣，中性偏过
        detail = "无跳跃镜头"
    checks.append(LogicCheck("jump-with-cause", "跳跃须有蹬地起跳+落地卸力", 1.2, jump_score, detail))

    # 16b 面对面：打斗镜须有朝向对方 / facing lock
    face_n = sum(1 for s in shots if _shot_has(s, lexicons.FACING_LOCK) or _shot_has(s, lexicons.FACING))
    if shots:
        face_score = face_n / len(shots)
        if face_n == 0:
            face_score = 0.15
    else:
        face_score = 0.0
    checks.append(LogicCheck(
        "facing-lock", "打斗须面对面/朝向对方", 1.3, face_score,
        f"{face_n}/{len(shots)} 拍写了朝向/面对面",
    ))

    # 16c 法术须瞄准对手
    spell_shots = [s for s in shots if _shot_has(s, lexicons.SPELL)]
    if spell_shots:
        aimed = sum(1 for s in spell_shots if _shot_has(s, lexicons.SPELL_TARGET) or _shot_has(s, ["toward", "aimed", "朝角色", "对准", "瞄"]))
        # 打向空气 = 明确失败
        air_miss = sum(1 for s in spell_shots if _shot_has(s, ["打向空气", "射向空", "empty air", "into empty"]))
        spell_score = max(0.0, aimed / len(spell_shots) - 0.5 * (air_miss / len(spell_shots)))
        checks.append(LogicCheck(
            "spell-target", "法术/投射须瞄准对手", 1.2, spell_score,
            f"{aimed}/{len(spell_shots)} 拍有瞄准；空放 {air_miss}",
        ))
    else:
        checks.append(LogicCheck("spell-target", "法术/投射须瞄准对手", 0.4, 0.7, "本法无施法，中性"))

    # 16d Shot≥2 须有身份锁
    if len(shots) >= 2:
        later = shots[1:]
        id_n = sum(1 for s in later if _shot_has(s, lexicons.IDENTITY_LOCK) or _shot_has(s, lexicons.OCCLUSION))
        id_score = id_n / len(later)
        if id_n == 0:
            id_score = 0.1
        checks.append(LogicCheck(
            "identity-lock", "切镜后同一张脸/服装/武器锁", 1.3, id_score,
            f"Shot2+ 中 {id_n}/{len(later)} 拍有身份锁",
        ))
    else:
        checks.append(LogicCheck("identity-lock", "切镜后同一张脸/服装/武器锁", 0.4, 0.8, "单镜，放宽"))

    # 16e 每镜开头空间锚：左/右/间距/朝向
    spat_n = 0
    for s in shots:
        head = s[:180]
        if _shot_has(head, lexicons.SPATIAL_OPEN) or _shot_has(head, lexicons.DISTANCE) or _shot_has(head, lexicons.FACING):
            spat_n += 1
    spat_score = (spat_n / len(shots)) if shots else 0.0
    if shots and spat_n < len(shots):
        # 缺空间锚重罚
        spat_score = min(spat_score, 0.45) if spat_n == 0 else spat_score
    checks.append(LogicCheck(
        "spatial-lock", "每镜开头重申左/右/间距/朝向", 1.2, spat_score,
        f"{spat_n}/{len(shots)} 拍开头有空间锚",
    ))

    # 16f 法术击中须有反馈
    hit_spell = []
    for s in shots:
        low = s.lower()
        has_hit = any(w in low for w in ("击中", "命中", "打中", "connects", "hits ", "struck", "impact"))
        has_spell = _shot_has(s, lexicons.SPELL)
        if has_hit and has_spell:
            hit_spell.append(s)
        elif has_spell and any(w in low for w in ("击中", "命中", "hits", "connects")):
            hit_spell.append(s)
    if hit_spell:
        ok_fb = sum(1 for s in hit_spell if _shot_has(s, lexicons.SPELL_FEEDBACK) or _shot_has(s, lexicons.FEEDBACK))
        fb_score = ok_fb / len(hit_spell)
        checks.append(LogicCheck(
            "spell-hit-feedback", "法术击中须有物理反馈", 1.3, fb_score,
            f"{ok_fb}/{len(hit_spell)} 处击中带踉跄/衣破/灼痕等",
        ))
    else:
        checks.append(LogicCheck("spell-hit-feedback", "法术击中须有物理反馈", 0.4, 0.7, "无法术击中事件，中性"))

    total_w = sum(c.weight for c in checks)
    raw = sum(c.weight * max(0.0, min(1.0, c.score)) for c in checks) / max(total_w, 1e-6)
    report = LogicReport(
        score=raw, grade=_grade(raw), checks=checks,
        stats={"shots": len(shots), "chars": len(text),
               "timecodes": sum(1 for s in shots if TIMECODE_RE.search(s))},
        language=language,
    )
    return report


def format_score(text: str, mode: str = "final", opts: Optional[Dict[str, Any]] = None) -> float:
    """h3lint 的壳结构分（0~1）；规则引擎缺失时退回 0.7 中性值。

    对**非中文**文本会自动打开 ``englishAware``：h3lint.js 原版只保留 CJK 做台词
    比对，导致纯英文台词重复检不出来（实测：同一份稿子中文版报
    ``sound-dialogue-repeat``、英文版不报）。用户的语料以英文为主，这里默认修正。

    另外默认打开 ``shotCounting="auto"``：官方 Ref2VA 写法会在
    ``retention_analysis`` 里写 ``(appears in [Shot 1])`` 这类引用，JS 原版会把
    引用也算成镜头数（一份 1 镜的稿子被数成 4 镜，6 条以上直接判 ``shot-many``
    错误）。auto 只在检测到引用式写法时改按"行首分镜块"计数。
    """
    try:
        from .lint import lint_score_01

        o: Dict[str, Any] = dict(opts or {})
        o.setdefault("mode", mode)
        if "englishAware" not in o and not lexicons.is_chinese(text):
            o["englishAware"] = True
        o.setdefault("shotCounting", "auto")
        return float(lint_score_01(text, o))
    except Exception:
        return 0.7


def composite_score(
    text: str,
    mode: str = "final",
    opts: Optional[Dict[str, Any]] = None,
    format_weight: float = 0.4,
) -> float:
    """复合分：``format_weight * 壳结构分 + (1-format_weight) * 武打逻辑分``。"""
    f = format_score(text, mode, opts)
    l = score_logic(text, mode).score
    return float(max(0.0, min(1.0, format_weight * f + (1.0 - format_weight) * l)))
