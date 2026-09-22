# -*- coding: utf-8 -*-
"""tests/test_h3lint.py — wushu_bridge.lint.h3lint 的 pytest 用例。

覆盖：
    (a) 完全合格的样例得高分且 items 里没有 error；
    (b) 各类反例命中预期 id（id 全部取自 Node 原版 h3lint.js 的实测输出）；
    (c) score 落在 0-100、grade 映射单调且阈值正确；
    (d) 与 JS 原版录制的输出（tools/h3lint_js_results.json）逐条一致；
    (e) 模块导出面 / diagnose 八维 / FIGHT_LOGIC 可选降级。

运行：``python -m pytest tests/test_h3lint.py -q``（在 E:\\Wushu\\ComfyUI-H3-WushuBridge 下）
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wushu_bridge.lint import (  # noqa: E402
    check, report, diagnose, diagnose_report, lint_score_01,
    VERSION, DIMENSIONS, BASE_SECTIONS, REF_SECTIONS, LEGACY_FIELDS,
    EMPTY_WORDS, SLOWMO, BLOOD, METAL_SOUND, IDLE_OPEN, AIR_WORDS, TELEPORT,
)

CASES_PATH = ROOT / "tools" / "h3lint_cases.json"
JS_RESULTS_PATH = ROOT / "tools" / "h3lint_js_results.json"

CASES = {c["id"]: c for c in json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]}


def run(case_id, **override):
    c = CASES[case_id]
    opts = dict(c["opts"])
    opts.update(override)
    return check(c["text"], opts)


def ids(res, level=None):
    return sorted({i["id"] for i in res["items"] if level is None or i["level"] == level})


# ── (a) 合格样例 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("case_id", ["ok-base-t2va", "ok-ref2va", "ok-dialogue"])
def test_ok_cases_score_high_without_errors(case_id):
    res = run(case_id)
    assert res["grade"] == "A", (case_id, res["score"], ids(res))
    assert res["score"] >= 90
    assert ids(res, "error") == []
    assert res["stats"]["errors"] == 0
    assert res["items"] == []          # 完全合格 = 一条问题都没有（与 JS 实测一致）
    assert lint_score_01(CASES[case_id]["text"], CASES[case_id]["opts"]) == 1.0


def test_ok_base_is_clean_and_report_text_ok():
    res = run("ok-base-t2va")
    assert "没有发现问题" in report(res)
    assert diagnose(res)["verdict"] == "八维全过"
    assert diagnose_report(res).startswith("八维诊断（八维全过）")


# ── (b) 反例命中预期 id（id 来自 JS 原版实测）────────────────────────────────
COUNTER_EXAMPLES = [
    ("missing-fields", ["field-overall_soundscape", "field-non_diegetic_music"]),
    ("missing-main-field", ["field-integrated_multimodal_description"]),
    ("no-shot", ["no-shot"]),
    ("shot-many-error", ["shot-many"]),
    ("shot1-timecode", ["shot1-timecode"]),
    ("timecode-order", ["timecode-order"]),
    ("timecode-range-over", ["timecode-range"]),
    ("slowmo", ["slowmo"]),
    ("start-slow", ["start-slow"]),
    ("beat-density", ["beat-density"]),
    ("empty-words", ["empty-word"]),
    ("neg-words", ["neg-in-body"]),
    ("blood", ["blood"]),
    ("length", ["length"]),
    ("scenario-hint", ["scenario-hint"]),
    ("placeholder-var", ["placeholder"]),
    ("placeholder-todo", ["placeholder"]),
    ("ruleblock-only", ["ruleblock"]),
    ("move-codebook", ["move-codebook"]),
    ("move-label-leak", ["move-label-leak"]),
    ("move-first-use", ["move-first-use"]),
    ("effect-unanchored", ["effect-unanchored"]),
    ("effect-subject", ["effect-subject"]),
    ("tier-inner", ["tier-inner"]),
    ("tier-inner-shape", ["tier-inner-shape"]),
    ("tier-cataclysm", ["tier-cataclysm"]),
    ("air-unsupported", ["air-unsupported"]),
    ("teleport", ["teleport"]),
    ("sound-metal", ["sound-metal"]),
    ("both-fighters", ["both-fighters"]),
    ("name-mix", ["name-mix"]),
    ("no-subject", ["no-subject"]),
    ("cut-continuity", ["cut-continuity"]),
    ("cut-identity", ["cut-identity"]),
    ("fight-no-counter", ["fight-no-counter"]),
    ("fight-no-causal", ["fight-no-causal-chain"]),
    ("fight-no-filler", ["fight-no-filler-motion", "fight-no-filler"]),
    ("fight-idle", ["fight-no-causal-chain", "fight-idle-unexplained"]),
    ("fight-filler-sparse", ["fight-filler-sparse"]),
    ("d-unclosed", ["d-unclosed"]),
    ("d-lang", ["d-lang"]),
    ("speaker-before-d", ["speaker-before-d"]),
    ("speaker-first", ["speaker-first"]),
    ("voiceover-lips", ["voiceover-lips"]),
    ("scenetrans-pair", ["scenetrans-pair"]),
    ("cutoff-hint", ["cutoff-hint"]),
    ("sound-dialogue-repeat", ["sound-dialogue-repeat"]),
    ("ref-missing-sections", ["field-summary", "field-retention_analysis"]),
    ("ref-legacy-field", ["ref-legacy-field"]),
    ("ref-main-field", ["ref-main-field"]),
    ("ref-subject-missing", ["ref-subject"]),
    ("ref-tags-mismatch", ["ref-tags"]),
    ("ref-recast", ["ref-recast"]),
]


@pytest.mark.parametrize("case_id,expected", COUNTER_EXAMPLES, ids=[c[0] for c in COUNTER_EXAMPLES])
def test_counter_examples_hit_expected_ids(case_id, expected):
    res = run(case_id)
    got = ids(res)
    for e in expected:
        assert e in got, (case_id, "缺 %s" % e, got)
    assert res["items"], case_id


@pytest.mark.parametrize("case_id,level,expected", [
    ("missing-fields", "error", ["field-non_diegetic_music", "field-overall_soundscape"]),
    ("fight-no-filler", "error", ["fight-no-filler", "fight-no-filler-motion"]),
    ("sound-metal", "error", ["sound-metal"]),
    ("slowmo", "warn", ["slowmo"]),
    ("blood", "warn", ["blood"]),
    ("neg-words", "info", ["neg-in-body"]),
    ("scenario-hint", "info", ["scenario-hint"]),
])
def test_counter_example_levels(case_id, level, expected):
    assert ids(run(case_id), level) == expected


def test_weapons_none_triggers_metal_sound_error_only_when_unarmed():
    armed = check(CASES["sound-metal"]["text"], {"mode": "final", "weapons": ["bang"]})
    unarmed = run("sound-metal")
    assert "sound-metal" not in ids(armed)
    assert ids(unarmed, "error") == ["sound-metal"]


def test_voiceover_ok_has_no_dialogue_error():
    assert ids(run("voiceover-ok"), "error") == []


def test_design_mode_skips_official_shell_but_still_checks():
    res = run("design-mode")
    assert not [i for i in ids(res) if i.startswith("field-")]
    assert res["mode"] == "design"


# ── (c) score 范围与 grade 映射 ─────────────────────────────────────────────
def _grade_of(score):
    return "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"


def test_score_range_and_grade_mapping_over_corpus():
    seen = []
    for cid, c in CASES.items():
        res = check(c["text"], c["opts"])
        assert 0 <= res["score"] <= 100, (cid, res["score"])
        assert res["grade"] == _grade_of(res["score"]), (cid, res["score"], res["grade"])
        assert res["stats"]["errors"] == len(ids(res, "error"))
        assert res["stats"]["warns"] == len([i for i in res["items"] if i["level"] == "warn"])
        assert res["stats"]["infos"] == len([i for i in res["items"] if i["level"] == "info"])
        seen.append((res["score"], res["grade"]))
    # 单调性：分数高的，grade 档次不得更差
    rank = {"A": 3, "B": 2, "C": 1, "D": 0}
    for s1, g1 in seen:
        for s2, g2 in seen:
            if s1 > s2:
                assert rank[g1] >= rank[g2], (s1, g1, s2, g2)


@pytest.mark.parametrize("score,grade", [(100, "A"), (90, "A"), (89, "B"), (75, "B"),
                                         (74, "C"), (60, "C"), (59, "D"), (0, "D")])
def test_grade_thresholds_monotonic(score, grade):
    assert _grade_of(score) == grade


def test_empty_text_is_lowest_grade():
    res = check("", {})
    assert res["grade"] == "D"
    assert ids(res, "error") == sorted([
        "field-integrated_multimodal_description", "field-non_diegetic_music",
        "field-overall_soundscape", "no-shot", "fight-no-filler-motion",
        "fight-no-causal-chain", "fight-no-counter"])
    assert res["score"] == 0     # 7 个 error ×15 = 105，扣到 0 为止


def test_score_never_below_zero():
    res = check("\n".join(["[Shot %d] 洪七公与杨过对峙，慢动作，瞬移，腾空，喷血。" % i
                           for i in range(1, 10)]), {"names": ["洪七公", "杨过"]})
    assert res["score"] == 0
    assert len(ids(res, "error")) >= 5


# ── 返回结构与导出面 ────────────────────────────────────────────────────────
def test_result_schema_matches_js():
    res = run("placeholder-var")
    assert set(res) == {"version", "mode", "score", "grade", "items", "stats"}
    assert res["version"] == VERSION == "h3lint-0.3"
    assert set(res["stats"]) == {"length", "shots", "sentences", "timecodes",
                                 "errors", "warns", "infos"}
    for it in res["items"]:
        assert set(it) == {"id", "level", "msg", "hint", "at"}
        assert it["level"] in ("error", "warn", "info")
        assert isinstance(it["msg"], str) and it["msg"]
    assert res["items"][0]["at"] == "{{声音清单}}"


def test_module_exports_match_js():
    for name, val in [("BASE_SECTIONS", BASE_SECTIONS), ("REF_SECTIONS", REF_SECTIONS),
                      ("LEGACY_FIELDS", LEGACY_FIELDS), ("EMPTY_WORDS", EMPTY_WORDS),
                      ("SLOWMO", SLOWMO), ("BLOOD", BLOOD), ("METAL_SOUND", METAL_SOUND),
                      ("IDLE_OPEN", IDLE_OPEN), ("AIR_WORDS", AIR_WORDS), ("TELEPORT", TELEPORT)]:
        assert val, name
    assert BASE_SECTIONS == ["integrated_multimodal_description", "overall_soundscape",
                             "non_diegetic_music"]
    assert len(REF_SECTIONS) == 6 and REF_SECTIONS[0] == "subject_definitions"
    assert LEGACY_FIELDS == [["preservation_analysis", "retention_analysis"]]
    assert callable(report) and callable(diagnose) and callable(diagnose_report)
    assert len(DIMENSIONS) == 8


def test_diagnose_groups_and_unclassified_ids():
    res = run("fight-no-filler")
    d = diagnose(res)
    assert [g["key"] for g in d["groups"]] == ["content", "motion", "audio", "physics",
                                               "character", "style", "dialogue", "continuity"]
    cont = next(g for g in d["groups"] if g["key"] == "continuity")
    assert cont["level"] == "error" and cont["count"] == 2
    assert d["worst"] == "error" and d["verdict"].startswith("需要修改：")
    # 忠实移植的 JS 怪癖：blood / neg-in-body 两个 id 在 JS 的 DIMENSIONS 里没有归属
    known = {i for g in DIMENSIONS for i in g["ids"]}
    assert "blood" not in known and "neg-in-body" not in known


def test_lint_score_01_range():
    for cid, c in CASES.items():
        s = lint_score_01(c["text"], c["opts"])
        assert 0.0 <= s <= 1.0, cid
    assert lint_score_01("") == 0.0


def test_combat_logic_optional_degradation():
    res_on = run("fight-no-filler")
    res_off = run("fight-no-filler", combatLogic=False)
    assert [i for i in ids(res_on) if i.startswith("fight-")]
    assert not [i for i in ids(res_off) if i.startswith("fight-")]
    assert res_off["score"] > res_on["score"]
    # 降级时给一条 info 说明，不静默
    assert ids(res_off, "info") == ["fight-logic-unavailable"] or res_off["items"] == []


# ── (d) 与 JS 原版录制的输出逐条比对 ────────────────────────────────────────
@pytest.mark.skipif(not JS_RESULTS_PATH.exists(),
                    reason="先跑 python tools/run_h3lint_diff.py 生成 JS 基准")
def test_matches_recorded_js_output():
    js = {c["id"]: c for c in json.loads(JS_RESULTS_PATH.read_text(encoding="utf-8"))["cases"]}
    assert set(js) == set(CASES)
    for cid, c in CASES.items():
        py = check(c["text"], c["opts"])
        j = js[cid]
        assert py["score"] == j["score"], cid
        assert py["grade"] == j["grade"], cid
        assert ids(py) == sorted({i["id"] for i in j["items"]}), cid
        assert ids(py, "error") == sorted({i["id"] for i in j["items"] if i["level"] == "error"}), cid
        assert py["stats"] == j["stats"], cid
        assert [i["msg"] for i in py["items"]] == [i["msg"] for i in j["items"]], cid
        assert [i["hint"] for i in py["items"]] == [i["hint"] for i in j["items"]], cid
        assert [i["at"] for i in py["items"]] == [i["at"] for i in j["items"]], cid
        assert report(py) == j["report"], cid
        assert diagnose_report(py) == j["diagnoseReport"], cid
