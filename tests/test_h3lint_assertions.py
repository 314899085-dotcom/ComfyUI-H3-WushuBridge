"""用**用户项目自带的断言对**测本插件的 h3lint 移植版。

来源：`D:\\wushulong\\H3武斗模拟器-v9.12\\tests\\{lint,moves,qi}.test.js` 里
已经写好的断言（盘点报告 §4.4.1「可执行断言对 —— 阈值标定的唯一依据」）。
这些是"可执行规格"，比读文档猜阈值可靠。

为什么单独一个文件：`tests/test_h3lint.py` 用的是我自己造的用例，
本文件用的是**用户侧的验收边界**，两者互补。

注意几个**故意的差异**（都在插件侧默认打开、可用 opts 关掉）：
* `englishAware`：修 JS 只保留 CJK 导致英文台词重复漏报
* `shotCounting="auto"`：修 JS 把 `(appears in [Shot 1])` 引用也当镜头数
本文件里凡是会碰到这两处的用例，都显式关掉它们，以对齐 JS 语义。
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wushu_bridge.lint import h3lint  # noqa: E402
from wushu_bridge.seeds import all_seeds  # noqa: E402

# 与 JS 原版逐位一致的语义（关掉两处实用修正）
RAW = {"mode": "final", "englishAware": False, "shotCounting": "raw"}


def check(text, **opts):
    o = dict(RAW)
    o.update(opts)
    return h3lint.check(text, o)


def ids(res, level=None):
    return [i["id"] for i in res["items"] if level is None or i["level"] == level]


def base() -> str:
    """3 镜合格稿（本插件内置种子，lint 99/A，shots=3、timecodes=2）。"""
    return all_seeds("t2v")[0]


def insert_before_soundscape(text: str, block: str) -> str:
    return text.replace("overall_soundscape:", block + "\noverall_soundscape:", 1)


# ══════════════════════════════════════════════════════════════════
# A. 阈值型（lint.test.js:19-25 / 171 / 173 / 59-65 / 97-103 / 161-164 / 86-89 / 79-84）
# ══════════════════════════════════════════════════════════════════

def test_a1_three_shot_clean_prompt():
    """3 镜合格稿：errors=0、score>=75、shots=3、timecodes=2。"""
    r = check(base())
    assert r["stats"]["errors"] == 0, [i for i in r["items"] if i["level"] == "error"]
    assert r["score"] >= 75
    assert r["stats"]["shots"] == 3
    assert r["stats"]["timecodes"] == 2


def test_a2_four_shots_is_warn():
    """4 镜（3 镜稿 + 1）= shot-many warn。"""
    text = insert_before_soundscape(base(), "[Shot 4] 2.0-3.0秒。角色A踏步出刀，角色B格挡。")
    r = check(text)
    assert r["stats"]["shots"] == 4
    assert "shot-many" in ids(r, "warn")
    assert "shot-many" not in ids(r, "error")


def test_a3_six_shots_is_error():
    """6 镜（3 镜稿 + 3）= shot-many error。"""
    extra = "\n".join(
        f"[Shot {n}] 2.0-3.0秒。角色A踏步出刀，角色B格挡。" for n in (4, 5, 6)
    )
    r = check(insert_before_soundscape(base(), extra))
    assert r["stats"]["shots"] == 6
    assert "shot-many" in ids(r, "error")


def test_a4_metal_sound_when_unarmed():
    """双方徒手却写「兵器相击」= sound-metal error。"""
    text = base().replace("兵刃相交火星", "兵器相击、金属碰撞")
    r = check(text, names=[], weapons=["none", "none"])
    assert "sound-metal" in ids(r, "error"), ids(r)


def test_a5_metal_sound_exempt_when_armed():
    """持械（jian/jian）即豁免 sound-metal。"""
    r = check(base(), names=[], weapons=["jian", "jian"])
    assert "sound-metal" not in ids(r)


def test_a6_air_without_support():
    """写「悬停/半空」但全篇无借力依据 = air-unsupported。"""
    text = base() + "\n角色A在半空悬停。"
    r = check(text)
    # 基础稿里有「蹬」等借力词，这里换一份不含借力词的文本
    text2 = "wushu_action, 5 seconds, 100 frames.\nintegrated_multimodal_description:\n" \
            "[Shot 1] 角色A腾空而起，角色B抬头。\noverall_soundscape: 风。\nnon_diegetic_music: None."
    r2 = check(text2)
    assert "air-unsupported" in ids(r2), ids(r2)
    assert "air-unsupported" not in ids(r), "含蹬地借力词时应豁免"


def test_a7_air_with_support_is_exempt():
    """含「蹬墙借力跃起，凌空劈下」= 不报（任一 AIR_SUPPORT 词即豁免）。"""
    text = "wushu_action, 5 seconds, 100 frames.\nintegrated_multimodal_description:\n" \
           "[Shot 1] 角色A蹬墙借力跃起，凌空劈下，角色B举刀格挡。\n" \
           "overall_soundscape: 风。\nnon_diegetic_music: None."
    assert "air-unsupported" not in ids(check(text))


def test_a8_timecode_range_over_duration():
    """duration=8，末时间码 9.0s = timecode-range（不小于片长）。"""
    text = base().replace("At 00:05.600.", "At 00:09.000.")
    r = check(text, duration=8)
    hits = [i for i in r["items"] if i["id"] == "timecode-range"]
    assert hits and re.search(r"不小于片长", hits[0]["msg"]), ids(r)


def test_a9_timecode_range_ok_when_short():
    """duration=8，末时间码 4.0s = 不报 timecode-range（边界在 2.8s）。"""
    text = base().replace("At 00:05.600.", "At 00:04.000.")
    assert "timecode-range" not in ids(check(text, duration=8))


def test_a10_length_over_maxlen():
    """长度 2500+ = 报 length。"""
    r = check(base() + "打斗。" * 900)
    assert "length" in ids(r)


def test_a11_design_mode_skips_shell_fields():
    """design 模式纯中文设计稿：errors=0（不查官方三段壳）。

    注意：design 模式只是**不查壳字段**，打斗连贯性检查照旧 —— 所以设计稿本身
    要有因果链与防守反击，否则仍会报 fight-no-causal-chain / fight-no-counter。
    """
    text = (
        "角色A从左侧逼近，后脚蹬地转腰，出「过肩劈」；角色B举刀斜挡，刃对刃火星溅起，"
        "因此被压得后退半步。角色A趁着这个空档继续前压，随即撤步换架，"
        "角色B侧身闪避后反手撩刀，两人重新拉开2格。"
    )
    r = check(text, mode="design")
    assert r["stats"]["errors"] == 0, [i for i in r["items"] if i["level"] == "error"]


# ══════════════════════════════════════════════════════════════════
# B. 招式 / 特效型（moves.test.js:10-46）
# ══════════════════════════════════════════════════════════════════

def _shell(body: str) -> str:
    return (
        "wushu_action, 5 seconds, 100 frames, 16:9, 24fps, 832x480.\n"
        "integrated_multimodal_description:\n" + body + "\n"
        "overall_soundscape: 风。\nnon_diegetic_music: None."
    )


def test_b1_move_codebook_and_label_leak():
    """招式定义清单 + 「使用招式A攻击」= move-codebook(warn) + move-label-leak。

    move-codebook 的正则要求「招式A：」**在行首**，所以清单必须单独成行。
    """
    text = _shell(
        "[Shot 1] 角色A踏步上前，举刀横在胸前。\n"
        "招式A：十字剑气。\n"
        "[Shot 2] At 00:03.000. 角色A使用招式A攻击，角色B举剑格挡。"
    )
    r = check(text)
    assert "move-codebook" in ids(r, "warn"), ids(r)
    assert "move-label-leak" in ids(r), ids(r)


def test_b2_move_first_use_single_occurrence_exempt():
    """招式名只出现 1 次且未写效果 = 不报 move-first-use。"""
    text = _shell("[Shot 1] 角色A劈出一记「十字剑气」，角色B举剑格挡后退。")
    assert "move-first-use" not in ids(check(text))


def test_b3_move_first_use_twice_without_effect():
    """出现 2 次、首现无效果 = move-first-use 恰 1 条。"""
    text = _shell(
        "[Shot 1] 角色A劈出「十字剑气」，角色B举剑格挡。\n"
        "[Shot 2] 3.0-5.0秒。角色A再起「十字剑气」，角色B侧身闪避。"
    )
    hits = [i for i in check(text)["items"] if i["id"] == "move-first-use"]
    assert len(hits) == 1, [i["msg"] for i in hits]


def test_b4_move_first_use_with_effect_exempt():
    """首现写全效果 = 不报。"""
    text = _shell(
        "[Shot 1] 角色A使出「十字剑气」：一道血色十字贴地飞出，剑气薄如刀锋，直取角色B咽喉。\n"
        "[Shot 2] 3.0-5.0秒。角色A再起「十字剑气」，角色B侧身闪避。"
    )
    assert "move-first-use" not in ids(check(text))


def test_b5_effect_unanchored():
    """有特效词但没来源与落点 = effect-unanchored。"""
    text = _shell("[Shot 1] 角色A劈出一记「十字剑气」，角色B在右侧中招。")
    assert "effect-unanchored" in ids(check(text))


def test_b6_effect_anchored_is_exempt():
    """写了来源与落点 = 不报。"""
    text = _shell(
        "[Shot 1] 血色十字从剑锋飞出、直取角色B咽喉，擦过肩头后没入身后石墙。"
    )
    assert "effect-unanchored" not in ids(check(text))


def _ref_shell(body: str) -> str:
    return (
        "subject_definitions:\n<Subject 1> the swordsman in <Picture 1>.\n"
        "<Subject 2> the opponent in <Picture 2>.\n"
        "summary:\n[reference generation] two fighters exchange blows.\n"
        "retention_analysis:\n<Subject 1> (appears in [Shot 1]): fully_preserved.\n"
        "detailed_description:\n" + body + "\n"
        "overall_soundscape: wind.\nnon_diegetic_music: None."
    )


def test_b7_effect_subject_info_in_ref_mode():
    """ref 模式 + 特效反复出现且未定义为 <Subject N> = effect-subject(info)。

    注意：`defined` 的判据是「<Subject N> 后面 80 字内出现该特效词」——所以
    特效句里**不能**紧接着写 <Subject N>，否则会被当成已定义。
    """
    body = (
        "[Shot 1] The blade releases a crescent of 剑气 across the courtyard.\n"
        "[Shot 2] At 00:03.000. A second wave of 剑气 follows the same arc."
    )
    r = check(_ref_shell(body))
    assert "effect-subject" in ids(r, "info"), ids(r)


def test_b8_effect_subject_defined_is_exempt():
    """定义为 <Subject 3> = 不报。"""
    body = (
        "[Shot 1] The blade releases a crescent of 剑气 across the courtyard.\n"
        "[Shot 2] At 00:03.000. A second wave of 剑气 follows the same arc.\n"
        "subject_definitions_extra: <Subject 3> is the blood-red 剑气 slash effect emitted by the first fighter."
    )
    assert "effect-subject" not in ids(check(_ref_shell(body)))


# ══════════════════════════════════════════════════════════════════
# C. 等级 / 内力型（qi.test.js:84-100，转发到 h3lint 的 tier-* 检查）
# ══════════════════════════════════════════════════════════════════

_TIER_BASE = _shell(
    "[Shot 1] 角色A举棒横击，角色B举剑格挡，兵器相击火星四溅，两人各自后退半步。"
)


def test_c1_tier3_pure_weapon_no_inner():
    """tier=3 + 纯兵器文本 = 不报 tier-inner。"""
    assert "tier-inner" not in ids(check(_TIER_BASE, tier=3))


def test_c2_tier5_pure_weapon_reports_inner():
    """tier=5 + 同一文本 = tier-inner(warn)。"""
    r = check(_TIER_BASE, tier=5)
    assert "tier-inner" in ids(r, "warn"), ids(r)


def test_c3_tier5_with_inner_energy_exempt():
    """tier=5 + 写了气劲外放 = 不报 tier-inner。"""
    text = _shell(
        "[Shot 1] 角色A棒端迸出一圈气劲把角色B震开半步，角色B举剑格挡。"
    )
    assert "tier-inner" not in ids(check(text, tier=5))


def test_c4_tier7_requires_shape():
    """tier=7 + 只有气劲没有成形的气 = tier-inner-shape。"""
    text = _shell("[Shot 1] 角色A棒端迸出一圈气劲把角色B震开半步。")
    assert "tier-inner-shape" in ids(check(text, tier=7))


def test_c5_tier9_requires_cataclysm():
    """tier=9 + 只有气劲 = tier-cataclysm。"""
    text = _shell("[Shot 1] 角色A棒端迸出一圈气劲把角色B震开半步。")
    assert "tier-cataclysm" in ids(check(text, tier=9))


# ══════════════════════════════════════════════════════════════════
# D. 对白型（lint.test.js:197-245）
# ══════════════════════════════════════════════════════════════════

_DLG_OK_BODY = (
    "[Shot 1] the grey-bearded man with a low, raspy voice (S1) says: "
    "<d>[Chinese] 你昨晚去过城南。</d> The other man steps back and (S2) answers: "
    "<d>[Chinese] 与你无关。</d> Later (S2) says in an off-screen voiceover: "
    "<d>[Chinese] 我记住了。</d> while his lips remain completely closed.\n"
    "[Shot 2] 3.0-5.0秒。角色A在左侧，面向角色B，间距2格，踏步出刀，两人仍是同一张脸、同一套服装与武器。\n"
    "[Shot 3] 5.0-8.0秒。角色B在右侧，朝向角色A，间距2格，举刀格挡，两人仍是同一张脸、同一套服装与武器。"
)


def test_d1_compliant_dialogue():
    """合规对白稿：不报 speaker-before-d / d-lang / voiceover-lips。"""
    r = check(_shell(_DLG_OK_BODY))
    for bad in ("speaker-before-d", "d-lang", "voiceover-lips"):
        assert bad not in ids(r), (bad, ids(r))


def test_d2_missing_speaker_label():
    """删掉 (S1) 编号 = speaker-before-d。"""
    body = _DLG_OK_BODY.replace("(S1) says", "says")
    assert "speaker-before-d" in ids(check(_shell(body)))


def test_d3_missing_language_tag():
    """<d>[Chinese] …</d> → <d>…</d> = d-lang。"""
    body = _DLG_OK_BODY.replace("<d>[Chinese] 你昨晚去过城南。</d>", "<d>你昨晚去过城南。</d>")
    assert "d-lang" in ids(check(_shell(body)))


def test_d4_unclosed_d_tag():
    """删掉一个 </d> = d-unclosed。"""
    body = _DLG_OK_BODY.replace("<d>[Chinese] 与你无关。</d>", "<d>[Chinese] 与你无关。", 1)
    assert "d-unclosed" in ids(check(_shell(body)))


def test_d5_voiceover_without_lips_closed():
    """画外音后没有「嘴唇保持不动」= voiceover-lips。"""
    body = _DLG_OK_BODY.replace(" while his lips remain completely closed.", "")
    assert "voiceover-lips" in ids(check(_shell(body)))


def test_d6_scenetrans_must_be_even():
    """<scenetrans> 出现 1 次报 scenetrans-pair；2 次不报。"""
    one = _shell(_DLG_OK_BODY.replace("[Shot 2] 3.0", "<scenetrans> [Shot 2] 3.0"))
    two = _shell(_DLG_OK_BODY.replace("[Shot 3] 5.0", "<scenetrans> [Shot 3] 5.0")
                 .replace("[Shot 2] 3.0", "<scenetrans> [Shot 2] 3.0"))
    assert "scenetrans-pair" in ids(check(one))
    assert "scenetrans-pair" not in ids(check(two))


# ══════════════════════════════════════════════════════════════════
# E. Ref2VA 字段型（lint.test.js:142-160）
# ══════════════════════════════════════════════════════════════════

def test_e1_official_ref_shell_has_no_field_errors():
    """官方六段合格稿：无 field-* 错误。"""
    r = check(_ref_shell("[Shot 1] A low tracking shot follows <Subject 1>."))
    assert not [i for i in ids(r, "error") if i.startswith("field-")], ids(r)


def test_e2_legacy_retention_field():
    """retention_analysis → preservation_analysis：field-retention_analysis(error) + ref-legacy-field(warn)。"""
    text = _ref_shell("[Shot 1] A low tracking shot follows <Subject 1>.").replace(
        "retention_analysis:", "preservation_analysis:"
    )
    r = check(text)
    assert "field-retention_analysis" in ids(r, "error")
    assert "ref-legacy-field" in ids(r, "warn")


def test_e3_wrong_main_field():
    """detailed_description → integrated_multimodal_description：ref-main-field + field-detailed_description。"""
    text = _ref_shell("[Shot 1] A low tracking shot follows <Subject 1>.").replace(
        "detailed_description:", "integrated_multimodal_description:"
    )
    r = check(text)
    assert "ref-main-field" in ids(r)
    assert "field-detailed_description" in ids(r, "error")


def test_e4_shot1_must_not_carry_timecode():
    """[Shot 1] 带时间码 = shot1-timecode（Ref2VA 同理）。"""
    text = _ref_shell("[Shot 1] 0.0-4.0s. A low tracking shot follows <Subject 1>.")
    assert "shot1-timecode" in ids(check(text))


# ══════════════════════════════════════════════════════════════════
# 插件侧的两处实用修正：不能破坏上面的 JS 语义边界
# ══════════════════════════════════════════════════════════════════

def test_fix1_shotcounting_auto_does_not_change_plain_prompts():
    """shotCounting=auto 只在引用式写法下生效：普通稿的 4/6 镜边界不变。"""
    four = insert_before_soundscape(base(), "[Shot 4] 2.0-3.0秒。角色A踏步出刀。")
    six = insert_before_soundscape(
        base(), "\n".join(f"[Shot {n}] 2.0-3.0秒。角色A踏步出刀。" for n in (4, 5, 6))
    )
    r4 = check(four, shotCounting="auto")
    r6 = check(six, shotCounting="auto")
    assert r4["stats"]["shots"] == 4 and "shot-many" in ids(r4, "warn")
    assert r6["stats"]["shots"] == 6 and "shot-many" in ids(r6, "error")


def test_fix2_reference_style_shots_are_counted_by_blocks():
    """官方引用式写法：raw 会数错（引用也算），auto 只数行首真分镜。"""
    body = _ref_shell("[Shot 1] A low tracking shot follows <Subject 1>.")
    raw = check(body, shotCounting="raw")
    auto = check(body, shotCounting="auto")
    assert raw["stats"]["shots"] > auto["stats"]["shots"]
    assert auto["stats"]["shots"] == 1


def test_fix3_english_dialogue_repeat():
    """englishAware：JS 只保留 CJK → 英文台词重复漏报；打开后能报。

    注意：`sound-dialogue-repeat` 比对的是 **overall_soundscape 段**里有没有复述
    正文 <d> 的台词，所以复述句必须写在声音段里。
    """
    text = (
        "wushu_action, 8 seconds, 200 frames, 16:9, 24fps, 832x480.\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] The fighter (S1) says: <d>[English] Hold your ground.</d> "
        "The clash of steel rings out.\n"
        "overall_soundscape: Feet on wet stone, and he says Hold your ground "
        "over the clash of steel.\n"
        "non_diegetic_music: None."
    )
    assert "sound-dialogue-repeat" not in ids(check(text, englishAware=False))
    assert "sound-dialogue-repeat" in ids(check(text, englishAware=True))
