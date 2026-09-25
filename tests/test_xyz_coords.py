"""XYZ 坐标锁定：解析 / 降级 / 评分。"""
from __future__ import annotations

import random

from wushu_bridge.xyz_coords import (
    parse_xyz_mentions,
    format_xyz,
    continuity_line,
    coords_consistent,
    strip_xyz,
    mutate_xyz,
    has_footwork,
)
from wushu_bridge.pairs import CRITICAL_FAILURE_OPS, DEFAULT_OPS, OPS_BY_KEY, degrade, DegradeProfile
from wushu_bridge.logic_score import score_logic
from wushu_bridge import lexicons


def test_parse_variants():
    text = (
        "角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2, 0, 0)；"
        "位于 xyz=(-1,0,0)；XYZ(0,1,2)；坐标(1,2,3)；"
        "<Subject 1> at xyz=(-2,0,0)；at (4,5,6)"
    )
    ms = parse_xyz_mentions(text)
    assert len(ms) >= 5
    subs = {m.get("subject") for m in ms}
    assert "角色A" in subs or any(m["x"] == -2 for m in ms)
    assert any(m["x"] == 2 and m["y"] == 0 for m in ms)


def test_format_and_continuity():
    assert "@xyz=" in format_xyz(-2, 0, 0, "zh", "角色A")
    assert "at xyz=" in format_xyz(2, 0, 0, "en", "<Subject 1>")
    zh = continuity_line("zh")
    en = continuity_line("en")
    assert "坐标锁定" in zh and "xyz=" in zh
    assert "coords locked" in en and "xyz=" in en


def test_consistency_and_footwork():
    ok, _ = coords_consistent({"A": (-2, 0, 0)}, {"A": (-1.5, 0, 0)}, max_delta=2.0)
    assert ok
    bad, probs = coords_consistent({"A": (-2, 0, 0)}, {"A": (8, 0, 5)}, max_delta=2.0)
    assert not bad and probs
    assert has_footwork("角色A上步逼近")
    assert has_footwork("A steps in and advances")
    assert not has_footwork("两人举刀对视")


def test_strip_and_mutate():
    t = "角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)"
    assert "xyz=" not in strip_xyz(t)
    out, did = mutate_xyz(t, random.Random(0))
    assert did and out != t


def test_xyz_drift_in_critical_and_default():
    assert "xyz_drift" in CRITICAL_FAILURE_OPS
    assert "xyz_drift" in DEFAULT_OPS
    assert "xyz_drift" in OPS_BY_KEY


def test_xyz_drift_op_mutates_or_strips():
    text = (
        "wushu_action, 10s.\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] 角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)。蹬地直刺。\n"
        "[Shot 2] 角色A@xyz=(-2,0,0) 仍面向 角色B@xyz=(2,0,0)。"
    )
    op = OPS_BY_KEY["xyz_drift"]
    out, did = op.fn(text, random.Random(1), 3)
    assert did
    # either stripped or numbers changed
    assert out != text


def test_lexicon_xyz_lock_slot():
    slots = lexicons.slots_present("坐标锁定：角色A@xyz=(-2,0,0)")
    assert slots.get("xyz_lock", 0) >= 1
    assert any("xyz" in w for w in lexicons.SPATIAL_OPEN)


def test_logic_score_prefers_locked_over_teleport():
    good = """wushu_action, 10.2 seconds, 243 frames, 16:9, 24fps, 832x480.
integrated_multimodal_description:
[Shot 1] medium. 角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)，间距2格。角色A蹬地直刺，角色B斜挡出火星，因此退半步。仍是同一张脸。
[Shot 2] At 00:02. 接上一镜：角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)，间距1格。角色B撩刀反击，角色A刀脊磕住。仍是同一张脸。
[Shot 3] At 00:05. 角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)。终结技斜劈，角色B倒地不再起身。
overall_soundscape: 脚步、兵刃。
non_diegetic_music: None."""
    bad = """wushu_action, 10.2 seconds, 243 frames, 16:9, 24fps, 832x480.
integrated_multimodal_description:
[Shot 1] medium. 角色A@xyz=(-2,0,0) 面向 角色B@xyz=(2,0,0)，间距2格。角色A出刀，角色B斜挡出火星。仍是同一张脸。
[Shot 2] At 00:02. 接上一镜：角色A@xyz=(8,0,5) 面向 角色B@xyz=(-9,0,4)，间距1格。角色B出刀，角色A磕住。仍是同一张脸。
[Shot 3] At 00:05. 角色A@xyz=(0,9,3) 面向 角色B@xyz=(1,-8,2)。终结技，角色B倒地不再起身。
overall_soundscape: 脚步、兵刃。
non_diegetic_music: None."""
    rg = score_logic(good)
    rb = score_logic(bad)
    xg = next(c for c in rg.checks if c.id == "xyz-lock")
    xb = next(c for c in rb.checks if c.id == "xyz-lock")
    assert xg.score > xb.score
    assert xg.score >= 0.7
    assert xb.score <= 0.4


def test_degrade_profile_accepts_xyz_drift():
    text = (
        "wushu_action\nintegrated_multimodal_description:\n"
        "[Shot 1] 角色A@xyz=(-2,0,0) 面向角色B@xyz=(2,0,0)，蹬地刺出，对方斜挡出火星，因此退半步。\n"
        "[Shot 2] 角色A@xyz=(-2,0,0) 终结技，角色B倒地不再起身。"
    )
    out, applied = degrade(text, DegradeProfile(ops=["xyz_drift"], intensity=5), random.Random(3))
    assert "xyz_drift" in applied or out != text  # may no-op if RNG path misses; intensity forces try
