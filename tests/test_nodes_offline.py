"""离线跑通节点逻辑（用假的 CLIP，不需要 ComfyUI / 不需要 H3）。

这里验证的是**用户第一个会碰到的路径**：构建数据集 → 训练桥 → 训练评分头 →
把桥接到 CONDITIONING 上。用假 CLIP 产生 5120 维随机 embedding，只检查
流程、索引、文件落盘、字段透传是否正确。
"""

from __future__ import annotations

import os
import sys

import pytest
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wushu_bridge import nodes  # noqa: E402


class FakeClip:
    """假 H3 文本编码器：token 数随文本长度变化，维度 5120。"""

    def __init__(self, dim: int = 5120, seed: int = 0) -> None:
        self.dim = dim
        self.g = torch.Generator().manual_seed(seed)

    def tokenize(self, text, **kwargs):
        return {"text": text}

    def encode_from_tokens_scheduled(self, tokens):
        text = tokens["text"]
        n_tok = 40 + len(text) % 25
        t = torch.randn(1, n_tok, self.dim, generator=self.g)
        return [[t, {"pooled_output": t[:, 0]}]]


def _unwrap(r):
    """节点可能直接返回元组，也可能返回 ComfyUI 的 {"ui":..., "result":(...)}。

    OUTPUT_NODE 类节点现在会带上 ui 文本（这样报告能在节点上直接看到），
    测试要同时兼容两种形态。
    """
    if isinstance(r, dict) and "result" in r:
        return r["result"]
    return r


@pytest.fixture()
def tmp_dataset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes, "DATASET_DIR", str(tmp_path / "datasets"))
    monkeypatch.setattr(nodes, "BRIDGE_DIR", str(tmp_path / "weights"))
    os.makedirs(nodes.DATASET_DIR, exist_ok=True)
    os.makedirs(nodes.BRIDGE_DIR, exist_ok=True)
    return tmp_path


def test_build_dataset_and_train(tmp_dataset_dir):
    builder = nodes.H3WushuBuildDataset()
    path, report = _unwrap(builder.run(
        clip=FakeClip(),
        mode="t2v",
        output_name="smoke",
        variants_per_source=4,
        intensity=3,
        min_good_score=0.0,
        score_mode="logic",
        include_seeds=True,
        max_pairs=32,
        max_tokens=0,
    ))
    assert os.path.isfile(path), report
    assert os.path.isfile(os.path.splitext(path)[0] + ".json")
    assert os.path.isfile(os.path.splitext(path)[0] + "_pairs.jsonl")
    assert "训练对" in report

    from wushu_bridge.dataset import PairDataset

    ds = PairDataset.load(path)
    assert len(ds) >= 4
    assert ds.meta.dim == 5120
    assert all(a.shape[-1] == 5120 for a in ds.x[:2])

    # 训练桥
    trainer = nodes.H3WushuTrainBridge()
    bridge_path, brep = _unwrap(trainer.run(
        dataset_path=path, arch="trans", out_name="smoke_bridge.safetensors",
        epochs=3, batch_size=4, lr=0.001, hidden=64, layers=1, heads=4,
        anchor_weight=0.1, alpha_min=0.05, alpha_max=0.3, val_ratio=0.25,
        device="cpu", max_seq_tokens=128,
    ))
    assert os.path.isfile(bridge_path), brep
    assert "参数量" in brep

    # 训练评分头
    judge_trainer = nodes.H3WushuTrainJevHead()
    judge_path, jrep = _unwrap(judge_trainer.run(
        dataset_path=path, out_name="smoke_judge.safetensors", hidden=32,
        epochs=5, batch_size=8, lr=0.001, device="cpu", heads=4, dropout=0.0,
    ))
    assert os.path.isfile(judge_path), jrep
    assert "准确率" in jrep


def test_bridge_apply_keeps_metadata(tmp_dataset_dir):
    from wushu_bridge.bridge_model import BridgeConfig, build_bridge, save_bridge

    path = os.path.join(nodes.BRIDGE_DIR, "unit_bridge.safetensors")
    save_bridge(path, build_bridge(BridgeConfig(arch="trans", dim=5120, hidden=64,
                                                layers=1, heads=4, max_tokens=256)))
    node = nodes.H3WushuSemanticBridge()
    cond = [[torch.randn(1, 32, 5120), {"minimax_frame_count": 124, "keep": 1}]]
    out, report, score = _unwrap(node.apply(
        conditioning=cond, bridge="unit_bridge.safetensors", alpha=0.15,
        magnitude_match="per_token", token_span="all", tail_ratio=1.0,
        device="cpu", chunk_tokens=0, allow_dim_mismatch=False,
    ))
    assert out[0][1]["keep"] == 1
    assert out[0][1]["minimax_frame_count"] == 124
    assert out[0][0].shape == cond[0][0].shape
    assert "语义漂移" in report
    assert score == 0.0        # 没给 judge，分数保持 0


def test_harvest_pair_roundtrip(tmp_dataset_dir):
    node = nodes.H3WushuHarvestPair()
    bad = [[torch.randn(1, 20, 5120), {}]]
    good = [[torch.randn(1, 22, 5120), {}]]
    path, report = _unwrap(node.run(bad, good, "harvest.npz", True, bad_score=0.1, good_score=0.9))
    assert os.path.isfile(path)
    assert "已追加 1 对" in report

    from wushu_bridge.dataset import PairDataset

    ds = PairDataset.load(path)
    assert len(ds) == 1 and ds.meta.dim == 5120


def test_lint_prompt_node_reports_both_scores():
    node = nodes.H3WushuLintPrompt()
    text = (
        "wushu_action, 10.2 seconds, 243 frames, 16:9, 24fps, 832x480.\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] 0.0-2.0秒。角色A后脚蹬地转腰，踏步拉近1格，出「过肩劈」；"
        "角色B举刀斜挡，刃对刃火星溅起，踉跄后退半步。\n"
        "[Shot 2] 2.0-10.2秒。角色A跟步送刀，终结技「过肩劈」完整刀路；"
        "角色B举刀硬架被震脱手，沿作用线仰面倒地，不再起身。\n"
        "overall_soundscape: 踏湿石、兵刃相交、雨声。\n"
        "non_diegetic_music: None."
    )
    score, grade, report = _unwrap(node.run(text, "final", "auto"))
    assert 0.0 <= score <= 1.0
    assert grade in {"A", "B", "C", "D"}
    assert "复合分" in report and "武打逻辑" in report


def test_degrade_preview_node():
    node = nodes.H3WushuDegradePreview()
    good = ("wushu_action, 5秒, 124 frames.\n"
            "integrated_multimodal_description:\n"
            "[Shot 1] 0.0-5.0秒。角色A后脚蹬地转腰，出「过肩劈」；"
            "角色B举刀格挡，火星溅起，踉跄后退。角色A终结技压制，角色B倒地。")
    bad, report, all_json = _unwrap(node.run(good, 4, 7, ops="", variants=2))
    assert bad and bad != good
    assert "正例分" in report
    assert all_json.strip().startswith("[")


def test_dim_mismatch_message(tmp_dataset_dir):
    from wushu_bridge.bridge_model import BridgeConfig, build_bridge, save_bridge

    save_bridge(os.path.join(nodes.BRIDGE_DIR, "d.safetensors"),
                build_bridge(BridgeConfig(arch="mlp", dim=5120, hidden=32)))
    node = nodes.H3WushuSemanticBridge()
    with pytest.raises(RuntimeError, match="维度不匹配"):
        node.apply(
            conditioning=[[torch.randn(1, 8, 4096), {}]], bridge="d.safetensors",
            alpha=0.1, magnitude_match="per_token", token_span="all", tail_ratio=1.0,
            device="cpu", chunk_tokens=0, allow_dim_mismatch=False,
        )


# ── 语料抽取的判据（都是实测踩出来的坑）────────────────────────────────

def test_reject_unfilled_bracket_skeletons():
    """带【题材】【角色A】的"全例"其实是骨架，不是成片 —— 必须拒收。"""
    from wushu_bridge.pairs import extract_prompts_from_text

    skeleton = (
        "wushu_action, 15 seconds, 362 frames, 16:9, 24fps, 832x480. 【题材】武侠对决。"
        "【角色A】持刀。\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] 【空间轴线】角色A从左侧逼近，出「过肩劈」；角色B举刀格挡，火星溅起。\n"
        "overall_soundscape: 【声音】。\nnon_diegetic_music: None.\n" + "动作描写。" * 40
    )
    assert extract_prompts_from_text(skeleton, "t2v") == []


def test_reject_brace_placeholders():
    """未替换的 {{DURATION}} 模板不是成品提示词。"""
    from wushu_bridge.pairs import extract_prompts_from_text

    tpl = (
        "wushu_action, {{DURATION}}s, {{FRAMES}} frames, 16:9, 24fps, 832x480. {{SCENE}}\n"
        "integrated_multimodal_description:\n{{ACTS}}\n"
        "overall_soundscape: {{SOUND}}\nnon_diegetic_music: None.\n" + "填充。" * 80
    )
    assert extract_prompts_from_text(tpl, "t2v") == []


def test_load_json_prompt_field(tmp_path):
    """结构化 JSON：取 prompt 字段（awesome-h3 那套 15 键 schema）。"""
    import json

    from wushu_bridge.pairs import load_corpus

    body = (
        "wushu_action, 10 seconds, 243 frames, 16:9, 24fps, 832x480.\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] 角色A踏步出刀，角色B举刀格挡，火星溅起，因此后退半步。\n"
        "overall_soundscape: 踏石、刀风。\nnon_diegetic_music: None.\n" + "补白。" * 20
    )
    p = tmp_path / "case.json"
    p.write_text(json.dumps({
        "slug": "x", "title": "标题不该被当成提示词", "description": "简介",
        "category": "action", "prompt": body,
    }, ensure_ascii=False), encoding="utf-8")
    got = load_corpus([str(p)], mode="t2v")
    assert len(got) == 1 and got[0] == body


def test_dominant_block_rule(tmp_path):
    """一文件一条提示词的语料：只留最长的那块，不要把碎片也算成额外正例。"""
    from wushu_bridge.pairs import load_corpus

    body = (
        "wushu_action, 10 seconds, 243 frames, 16:9, 24fps, 832x480.\n"
        "integrated_multimodal_description:\n"
        "[Shot 1] 角色A踏步出刀，角色B举刀格挡，火星溅起，因此后退半步。\n"
        "overall_soundscape: 踏石、刀风。\nnon_diegetic_music: None.\n" + "补白。" * 20
    )
    p = tmp_path / "one_prompt.txt"
    p.write_text(body, encoding="utf-8")
    assert len(load_corpus([str(p)], mode="t2v")) == 1
