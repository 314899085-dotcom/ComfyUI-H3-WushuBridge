"""ComfyUI 契约测试：这些坑都是在真云主机 ComfyUI 上实测踩出来的。

每一条都对应一次真实崩溃，所以必须固化：

1. **ComfyUI 用 `torch.inference_mode()` 包住节点执行**
   （`execution.py:751`）。inference_mode 内的张量不追踪梯度，且
   `torch.enable_grad()` **无法**抵消 —— 训练节点会 100% 崩在
   `element 0 of tensors does not require grad and does not have a grad_fn`。
2. **报告类节点必须是 output 节点**，否则单独放进图里点运行，
   ComfyUI 直接拒绝：`prompt_no_outputs: Prompt has no outputs`。
3. 报告要能在节点上直接看到，必须放进 `ui["text"]`（返回
   `{"ui": {...}, "result": (...)}`），而不是只给 STRING 输出。
"""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wushu_bridge import nodes  # noqa: E402
from wushu_bridge.dataset import PairDataset  # noqa: E402
from wushu_bridge.train import JudgeTrainConfig, TrainConfig, train_bridge, train_judge  # noqa: E402

DIM = 5120


def _toy_dataset(n: int = 16) -> PairDataset:
    rl = np.random.default_rng(0)
    L = rl.normal(0, 1, size=(DIM,)).astype(np.float32)
    L /= np.linalg.norm(L)
    rng = np.random.default_rng(1)
    ds = PairDataset()
    for _ in range(n):
        base = rng.normal(0, 1, size=(48, DIM)).astype(np.float32)
        base /= np.linalg.norm(base, axis=-1, keepdims=True)
        lo, hi = 0.2, 0.9
        ds.add(((base + 1.4 * lo * L[None, :]) * 3).astype(np.float16),
               ((base + 1.4 * hi * L[None, :]) * 3).astype(np.float16),
               lo, hi, {})
    return ds


# ── 坑 1：ComfyUI 的 inference_mode 包装 ────────────────────────────────

def test_train_bridge_inside_inference_mode():
    """模拟 ComfyUI execution.py:751 的 torch.inference_mode() 包装。"""
    ds = _toy_dataset()
    tmp = tempfile.mkdtemp()
    with torch.inference_mode():
        rep = train_bridge(ds, TrainConfig(arch="trans", hidden=64, layers=1, heads=4,
                                           epochs=3, batch_size=4, val_ratio=0.25,
                                           max_seq_tokens=64, patience=3),
                           os.path.join(tmp, "b.safetensors"), log=lambda s: None)
    assert rep["params"] > 0
    assert os.path.isfile(os.path.join(tmp, "b.safetensors"))


def test_train_judge_inside_inference_mode():
    ds = _toy_dataset()
    tmp = tempfile.mkdtemp()
    with torch.inference_mode():
        rep = train_judge(ds, JudgeTrainConfig(hidden=32, epochs=3, batch_size=8),
                          os.path.join(tmp, "j.safetensors"), log=lambda s: None)
    assert rep["params"] > 0
    assert os.path.isfile(os.path.join(tmp, "j.safetensors"))


def test_train_bridge_inside_no_grad():
    """torch.no_grad() 包装（另一种常见写法）也要能训。"""
    ds = _toy_dataset()
    tmp = tempfile.mkdtemp()
    with torch.no_grad():
        rep = train_bridge(ds, TrainConfig(arch="mlp", hidden=32, epochs=2, batch_size=4,
                                           val_ratio=0.25, max_seq_tokens=64, patience=2),
                           os.path.join(tmp, "b2.safetensors"), log=lambda s: None)
    assert rep["params"] > 0


# ── 坑 2 / 3：output 节点与 ui 文本 ────────────────────────────────────

REPORT_NODES = [
    "H3WushuSemanticBridge",
    "H3WushuBuildDataset", "H3WushuTrainBridge", "H3WushuTrainJevHead",
    "H3WushuHarvestPair", "H3WushuLintPrompt", "H3WushuDegradePreview",
    "H3WushuJevScore", "H3WushuLocateTextSpan", "H3WushuClearCache",
]


@pytest.mark.parametrize("name", REPORT_NODES)
def test_report_node_is_output_node(name):
    """报告类节点必须是 output 节点，否则单独运行会被 ComfyUI 拒绝。"""
    cls = nodes.NODE_CLASS_MAPPINGS[name]
    assert getattr(cls, "OUTPUT_NODE", False) is True


def test_inference_bridge_is_also_output_node():
    """语义桥虽然是链路中段节点，但**也要**标成 output 节点。

    为什么：桥的 report（语义漂移、改动前后武打逻辑分）是用户判断"这次改动
    是不是过猛"的唯一依据；不标 output 节点，用户必须再接一个文本显示节点
    才能看到，实测很影响可用性。
    """
    cls = nodes.NODE_CLASS_MAPPINGS["H3WushuSemanticBridge"]
    assert getattr(cls, "OUTPUT_NODE", False) is True


def test_report_nodes_return_ui_text():
    """报告类节点返回 {"ui": {"text": [...]}, "result": (...)}。"""
    node = nodes.H3WushuClearCache()
    r = node.run(True)
    assert isinstance(r, dict) and "ui" in r and "result" in r
    assert isinstance(r["ui"]["text"], list) and r["ui"]["text"]
    assert isinstance(r["result"], tuple)

    dp = nodes.H3WushuDegradePreview()
    good = ("wushu_action, 5秒, 124 frames.\n"
            "integrated_multimodal_description:\n"
            "[Shot 1] 角色A后脚蹬地转腰出「过肩劈」，角色B举刀格挡，火星溅起，踉跄后退。"
            "角色A终结技压制，角色B倒地。")
    r = dp.run(good, 4, 7, ops="", variants=2)
    assert r["ui"]["text"] and r["result"][0] != good


def test_ui_helper_skips_empty_text():
    r = nodes._ui((1, "x"), "有内容", "", None)
    assert r["ui"]["text"] == ["有内容"]
    assert r["result"] == (1, "x")
