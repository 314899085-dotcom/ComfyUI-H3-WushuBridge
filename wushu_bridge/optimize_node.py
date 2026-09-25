"""一个节点搞定：Laya 判断 → 优化 conditioning → 复评合格 → 输出。

分工（这是关键，别搞混）
------------------------
* **Laya 判「文本」**：它是文本输入的决策模型，吃的是提示词/剧本这类人话。
* **桥改「conditioning」**：真正的"优化"由残差桥在 5120 维条件空间里做（这才是 conditioning 优化）。
* **JEV 评分头判「conditioning」**：可选，用来兜底——防止文本分涨了但条件向量反而变坏。
* **小模型只负责"写字"**：Laya 不会写字；只有当文本本身逻辑缺失、光靠桥补不回来时，
  才叫小语言模型按"待修项"重写提示词，再重新编码上桥。

所以这一个节点内部的闭环是：

    Laya 判分 ──合格──► 直接输出
        │
        └─不合格─► 桥优化 conditioning ─┐
                   （可选）小模型重写文本 │
                        重新编码 + 上桥  │
                   Laya 复评 ◄───────────┘
                     │分升了 → 接受，继续
                     │没升   → 回退，停（不做无用功）
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import torch

from . import laya_runtime as rt
from . import small_llm as sllm
from .apply import apply_bridge_to_conditioning
from .judge import score_conditioning
from .nodes import (
    _bridge_choices,
    _encode_texts,
    _get_bridge,
    _get_judge,
    _judge_choices,
    _pick_torch_device,
    _ui,
)

LLM_MODES = ["off", "hf", "endpoint"]


def _llm_model_choices() -> List[str]:
    return list(sllm.SMALL_LLM_CHOICES.keys())


class H3WushuOptimize:
    """武打语义优化：Laya 判断 → 优化 conditioning → 合格后输出（一个节点全流程）。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "conditioning": ("CONDITIONING", {"tooltip": "接在 CLIPTextEncode 之后"}),
                "text": ("STRING", {"multiline": True, "default": "",
                                    "tooltip": "提示词原文。Laya 判的就是它；启用小模型重写时也从它出发"}),
                "rules": ("STRING", {"multiline": True, "default": "",
                                     "tooltip": "自定义规则，一行一条，可留空。\n"
                                                "裸规则=是/否；评分:问题|差档|…|好档；选择:问题|选项1|选项2"}),
                "threshold": ("FLOAT", {"default": 0.62, "min": 0.0, "max": 1.0, "step": 0.01,
                                        "tooltip": "合格线。0.62=小改可用，0.80=可直接出片"}),
                "max_rounds": ("INT", {"default": 3, "min": 1, "max": 6,
                                       "tooltip": "最多优化几轮；每轮没提分就立刻停"}),
                "llm_mode": (LLM_MODES, {"default": "off",
                                         "tooltip": "off=只优化 conditioning（推荐先用这个）；\n"
                                                    "hf=下载/加载小模型重写提示词；\n"
                                                    "endpoint=调本机已有的 OpenAI 兼容服务"}),
            },
            "optional": {
                "clip": ("CLIP", {"tooltip": "仅小模型重写后需要重新编码时才要接"}),
                "bridge": (_bridge_choices(), {"tooltip": "残差桥权重（在 conditioning 空间做优化）"}),
                "judge": (_judge_choices(), {"tooltip": "JEV 评分头（可选）：给 conditioning 打分做兜底"}),
                "alpha": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01,
                                    "tooltip": "桥强度；auto 开启时按分数自适应"}),
                "auto_alpha": ("BOOLEAN", {"default": True, "tooltip": "分越低修得越多"}),
                "llm_model": (_llm_model_choices(), {"default": "openbmb/MiniCPM5-2B"}),
                "llm_endpoint_url": ("STRING", {"default": "http://127.0.0.1:8083",
                                                "tooltip": "llm_mode=endpoint 时的服务地址"}),
                "llm_endpoint_model": ("STRING", {"default": "local-model"}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "FLOAT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("conditioning", "score", "pass", "report")
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Wushu Bridge"
    OUTPUT_NODE = True
    DESCRIPTION = ("Laya 判断武打逻辑 → 不达标就用残差桥优化 conditioning"
                   "（必要时叫小模型重写提示词）→ 复评合格后输出。"
                   "只有提分才接受，否则回退。")

    def run(self, conditioning, text, rules, threshold, max_rounds, llm_mode,
            clip=None, bridge="none", judge="none", alpha=0.12, auto_alpha=True,
            llm_model="openbmb/MiniCPM5-2B", llm_endpoint_url="http://127.0.0.1:8083",
            llm_endpoint_model="local-model", device="auto"):
        dev = _pick_torch_device(device)
        log: List[str] = []

        # ── ① Laya 判原文 ────────────────────────────────────────────────
        try:
            res = rt.judge_text(text, custom_rules=rules, device=device)
        except Exception as exc:
            msg = (f"Laya 裁判不可用：{type(exc).__name__}: {exc}\n"
                   f"提示：先跑 tools/setup_laya.py --from ours 装权重。")
            return _ui((conditioning, 0.0, False, msg), msg)

        score = float(res["score"])
        log.append(f"① Laya 判分：{score:.3f}（{res['level']}）｜路由={res.get('routed_to') or '-'}")
        weak = [q for q in rt.RUBRIC_ORDER if (res["subscores"].get(q) or 1.0) < 0.5]
        if weak:
            log.append("   弱项：" + "、".join(weak))
        if res.get("failed"):
            log.append("   未达标规则：" + "、".join(res["failed"]))

        if score >= float(threshold):
            log.append(f"② 已达标（≥{threshold:.2f}），conditioning 原样输出，不做任何改动。")
            report = "\n".join(log)
            return _ui((conditioning, score, True, report), report)

        # ── ② 准备优化器 ────────────────────────────────────────────────
        if bridge == "none":
            log.append("② 没选残差桥权重，无法在 conditioning 空间优化 —— 只出诊断。")
            report = "\n".join(log)
            return _ui((conditioning, score, False, report), report)

        model = _get_bridge(bridge, dev)
        judge_model = _get_judge(judge, dev) if judge and judge != "none" else None
        cond_score = None
        if judge_model is not None:
            cond_score, _per = score_conditioning(judge_model, conditioning)
            log.append(f"   条件空间分（JEV 头）：{cond_score:.3f} —— 作为兜底，别改坏了")
        log.append(f"② 开始优化：桥={os.path.basename(bridge)}｜alpha={alpha}｜auto_alpha={auto_alpha}"
                   f"｜轮数上限={max_rounds}")

        def apply_bridge(cond, s: float):
            a = float(alpha)
            if auto_alpha:
                deficit = max(0.0, 0.75 - float(s)) / 0.75      # 分越低修得越多
                a = float(min(0.25, a + deficit * 0.25))
            out, rep = apply_bridge_to_conditioning(
                cond, model, alpha=a, magnitude_match_mode="per_token",
                token_span="all", tail_ratio=1.0, max_tokens_per_chunk=0,
            )
            return out, a, rep

        # ── ③ 闭环 ──────────────────────────────────────────────────────
        # 验收标准要分两种优化分别看（这里踩过坑，说清楚）：
        #   · 只优化 conditioning（文本没变）→ Laya 的文本分**必然不变**（它判的就是那段文字），
        #     所以必须用 JEV 条件空间分来验收，否则永远判成"没提升"而白白回退。
        #   · 重写了文本 → 用 Laya 文本分验收，同时要求条件空间分不倒退（别改坏）。
        cur_cond, cur_text = conditioning, text
        best_score, best_cond, best_text = score, conditioning, text
        best_cond_score = cond_score
        accepted = 0
        for rnd in range(1, int(max_rounds) + 1):
            log.append(f"── 第 {rnd} 轮 ──")

            # (a) conditioning 空间优化
            try:
                cand_cond, used_alpha, rep = apply_bridge(cur_cond, best_score)
                log.append(f"   桥已在条件空间施加修正（alpha={used_alpha:.3f}）")
            except Exception as exc:
                log.append(f"   桥执行失败：{type(exc).__name__}: {exc}")
                break

            # (b) 需要时叫小模型重写文本
            cand_text = best_text
            text_changed = False
            if llm_mode != "off":
                issues = list(weak) + list(res.get("failed") or [])
                new_text, note = sllm.rewrite_prompt(
                    best_text, issues=issues, custom_rules=rules, mode=llm_mode,
                    repo=llm_model, endpoint_url=llm_endpoint_url,
                    endpoint_model=llm_endpoint_model,
                )
                log.append(f"   小模型：{note}")
                if new_text and new_text.strip() and new_text.strip() != best_text.strip():
                    if clip is None:
                        log.append("   （没接 CLIP，重写结果无法编码，本轮忽略）")
                    else:
                        try:
                            enc = _encode_texts(clip, [new_text])
                            cand_cond, used_alpha, _ = apply_bridge(enc, best_score)
                            cand_text = new_text
                            text_changed = True
                            log.append(f"   重写已重新编码并重新上桥（alpha={used_alpha:.3f}）")
                        except Exception as exc:
                            log.append(f"   重新编码失败：{type(exc).__name__}: {exc}")

            # (c) 复评：条件空间分（能测就测）+ 文本分（文本变了才有意义）
            cand_cond_score = None
            if judge_model is not None:
                cand_cond_score, _ = score_conditioning(judge_model, cand_cond)
            if text_changed:
                try:
                    res2 = rt.judge_text(cand_text, custom_rules=rules, device=device)
                    cand_text_score = float(res2["score"])
                except Exception as exc:
                    log.append(f"   文本复评失败：{type(exc).__name__}: {exc}")
                    break
            else:
                cand_text_score = best_score      # 文本没动，文本分必然一样

            # (d) 验收
            if text_changed:
                ok_text = cand_text_score > best_score + 1e-9
                ok_cond = (cand_cond_score is None) or (cand_cond_score >= float(best_cond_score or 0) - 1e-6)
                accept = ok_text and ok_cond
                why_bad = ("重写后文本分没升" if not ok_text else "条件空间分反而降了")
            else:
                ok_cond = (cand_cond_score is not None) and (cand_cond_score > float(best_cond_score or 0) + 1e-9)
                accept = ok_cond
                why_bad = "条件空间分没有继续变好"
                if cand_cond_score is None:
                    accept = False
                    why_bad = "没选 JEV 评分头，无法判断条件空间是否真的变好"

            parts = [f"文本 {best_score:.3f}→{cand_text_score:.3f}"]
            if cand_cond_score is not None:
                parts.append(f"条件 {float(best_cond_score or 0):.3f}→{cand_cond_score:.3f}")
            log.append("   复评：" + "｜".join(parts) + ("　✓接受" if accept else "　✗回退"))

            if accept:
                accepted += 1
                best_score, best_cond, best_text = cand_text_score, cand_cond, cand_text
                if cand_cond_score is not None:
                    best_cond_score = float(cand_cond_score)
                if text_changed:
                    res = res2
                    weak = [q for q in rt.RUBRIC_ORDER if (res["subscores"].get(q) or 1.0) < 0.5]
                if best_score >= float(threshold):
                    log.append(f"   文本已达标（≥{threshold:.2f}），停止优化。")
                    break
            else:
                log.append(f"   {why_bad} → 丢弃本轮改动并停止（不做无用功）。")
                break

        # ── ④ 结论 ──────────────────────────────────────────────────────
        passed = best_score >= float(threshold)
        log.append("")
        summary = f"结论：文本分 {score:.3f} → {best_score:.3f}（接受 {accepted} 轮）"
        if best_cond_score is not None:
            summary += f"｜条件空间分 {float(cond_score or 0):.3f} → {best_cond_score:.3f}"
        log.append(summary)
        if passed:
            log.append("文本逻辑达标 ✓")
        elif llm_mode == "off":
            log.append("文本逻辑仍未达标 ✗ —— 文本分只能靠**改文字**提升，而这个阶段没启用小模型。")
            log.append("  要提文本分：把 llm_mode 设成 hf（自动下载小模型）或 endpoint（用本机服务），")
            log.append("  并接上 clip（重写后要重新编码）。conditioning 已被优化过，可直接用。")
        else:
            log.append("文本逻辑仍未达标 ✗（小模型试过了，没写出更好的版本）。conditioning 已被优化过。")
        if best_text != text:
            log.append("")
            log.append("── 优化后的提示词 ──")
            log.append(best_text)
        report = "\n".join(log)
        return _ui((best_cond, float(best_score), bool(passed), report), report)


NODE_CLASS_MAPPINGS = {
    "H3WushuOptimize": H3WushuOptimize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3WushuOptimize": "H3 武打语义优化（判断→优化→输出）",
}
