"""H3 武打 Laya 裁判 / 优化回路节点。

设计边界（先说清，免得误用）
----------------------------
Laya **不生成文本**，它只回答 typed question（choice / score / noul）。所以这两个节点
不做"自动改写"，它们做的是：

* **裁判**：给材料打分（rubric 五问 + 你的自定义规则），输出分项、弱项、门禁结论；
* **优化回路**：把 N 份候选稿交给 Laya 逐一打分排序，挑出最好的那份，
  再让 Laya 从体检出的待修项里选"最该先修的一条"（带位置偏置防护）。

真正的文字改动来自写候选稿的人或模型（比如你自己改，或让 GLM-5V/GPT 按方向改一版）。
插件负责**判断、排序、指方向**——这样分工才是对的：让 8 亿参数的非自回归决策模型
去写字，只会得到一堆噪声。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from . import laya_runtime as rt
from .nodes import _ui


def _split_candidates(blob: str) -> List[str]:
    """把候选稿切成若干份。

    分隔符：单独一行的 ``---`` / ``===`` / ``###``，或行首的 ``[1]`` ``1.`` ``#1`` 编号。
    只有一份时原样返回。
    """
    text = str(blob or "").strip()
    if not text:
        return []
    seps = ("---", "===", "###", "***")
    lines = text.splitlines()
    # 先看有没有分隔符行
    has_sep = any(ln.strip() in seps for ln in lines)
    if has_sep:
        chunks, cur = [], []
        for ln in lines:
            if ln.strip() in seps:
                if cur:
                    chunks.append("\n".join(cur).strip())
                cur = []
            else:
                cur.append(ln)
        if cur:
            chunks.append("\n".join(cur).strip())
        return [c for c in chunks if c]

    # 再看有没有编号
    import re

    numbered = [ln for ln in lines if re.match(r"^\s*(?:\[(\d+)\]|(\d+)[.、)]|#(\d+))\s*\S", ln)]
    if len(numbered) >= 2:
        chunks, cur = [], []
        for ln in lines:
            if re.match(r"^\s*(?:\[(\d+)\]|(\d+)[.、)]|#(\d+))\s*\S", ln):
                if cur:
                    chunks.append("\n".join(cur).strip())
                cur = [re.sub(r"^\s*(?:\[(\d+)\]|(\d+)[.、)]|#(\d+))\s*", "", ln)]
            else:
                cur.append(ln)
        if cur:
            chunks.append("\n".join(cur).strip())
        return [c for c in chunks if c]

    return [text]


def _lint_directions(text: str, mode: str = "design") -> List[Dict[str, str]]:
    """从 h3lint 体检结果里提取"待修方向"候选（error/warn 各算一条）。"""
    out: List[Dict[str, str]] = []
    try:
        from .lint import h3lint

        opts = {"mode": mode, "englishAware": True}
        res = h3lint.check(text, opts)
    except Exception:
        return out
    for it in (res or {}).get("items", []):
        lvl = str(it.get("level") or "")
        if lvl not in ("error", "warn"):
            continue
        out.append({
            "id": str(it.get("id") or f"item{len(out)}"),
            "label": str(it.get("msg") or ""),
            "why": str(it.get("hint") or lvl),
        })
    return out


class H3WushuLayaJudge:
    """Laya 武打裁判：rubric 五问 + 你的自定义规则，给材料打分并给门禁结论。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "",
                                    "tooltip": "要判的材料：提示词 / 打标稿 / 剧本片段"}),
                "custom_rules": ("STRING", {"multiline": True, "default": "",
                                            "tooltip": "自定义规则，一行一条。\n"
                                                       "裸规则=是/否题；\n"
                                                       "评分:问题|最差档|…|最好档；\n"
                                                       "选择:问题|选项1|选项2"}),
                "threshold": ("FLOAT", {"default": 0.62, "min": 0.0, "max": 1.0, "step": 0.01,
                                        "tooltip": "门禁阈值（rubric 加权分）。0.62 = 小改可用"}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
            },
            "optional": {
                "router_model": (["auto", "english", "multilingual", "typed-decisions"],
                                 {"default": "auto",
                                  "tooltip": "强制用某一档；auto = 让 Laya 按语言自己选"}),
                "laya_dir": ("STRING", {"default": "", "multiline": False,
                                        "tooltip": "权重目录，留空自动找（ComfyUI/models/wushu_bridge/laya）"}),
                "preload": ("BOOLEAN", {"default": True,
                                        "tooltip": "预加载全部档位（换语言时不重载，加载慢一次）"}),
            },
        }

    RETURN_TYPES = ("FLOAT", "BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("score", "pass", "level", "report")
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Wushu Bridge"
    OUTPUT_NODE = True
    DESCRIPTION = ("用内嵌的 Laya 决策模型当武打裁判：rubric 五问 + 自定义规则，"
                   "输出加权分、分项、弱项与门禁结论（不生成文本）")

    def run(self, text, custom_rules, threshold, device,
            router_model="auto", laya_dir="", preload=True):
        if not str(text or "").strip():
            msg = "材料为空，没什么可判的。"
            return _ui((0.0, False, "未判定", msg), msg)
        try:
            # preload 只影响第一次建 Router 时的行为；已缓存的 Router 不会重建
            rt.get_router(device=device, preload=bool(preload), laya_dir=laya_dir)
            res = rt.judge_text(
                text,
                custom_rules=custom_rules,
                device=device,
                laya_dir=laya_dir,
                router_model="" if router_model == "auto" else router_model,
            )
        except Exception as exc:
            msg = f"Laya 裁判不可用：{type(exc).__name__}: {exc}"
            return _ui((0.0, False, "不可用", msg), msg)

        passed = float(res["score"]) >= float(threshold)
        lines = [res["report"], "",
                 f"门禁：{res['score']:.3f} vs 阈值 {threshold:.2f} → {'通过' if passed else '不通过'}"]
        weak = [q for q in rt.RUBRIC_ORDER if (res["subscores"].get(q) or 1.0) < 0.5]
        if weak:
            lines.append("弱项（先用 Laya 优化回路挑一条来修）：" + "、".join(weak))
        if res.get("failed"):
            lines.append("未达标的自定义规则：" + "、".join(res["failed"]))
        report = "\n".join(lines)
        return _ui((float(res["score"]), bool(passed), str(res["level"]), report), report)


class H3WushuLayaOptimize:
    """Laya 优化回路：N 份候选稿逐一打分排序 + 挑出最该先修的方向。

    真正的文字改动由你（或文本模型）提供候选稿；本节点负责判断、排序、指方向。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "",
                                    "tooltip": "原始稿（用来体检出待修方向、以及和候选比较）"}),
                "candidates": ("STRING", {"multiline": True, "default": "",
                                          "tooltip": "候选改写稿，用单独一行的 --- 分隔；留空则只体检+指方向"}),
                "custom_rules": ("STRING", {"multiline": True, "default": "",
                                            "tooltip": "同裁判节点：一行一条规则"}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
            },
            "optional": {
                "lint_mode": (["design", "final"], {"default": "design",
                                                    "tooltip": "体检口径：design=只判逻辑与物理；final=按成品稿判字段"}),
                "max_candidates": ("INT", {"default": 4, "min": 1, "max": 8,
                                           "tooltip": "最多评估几份候选（每份一次 Laya 前向）"}),
                "laya_dir": ("STRING", {"default": "", "multiline": False}),
                "use_model_direction": ("BOOLEAN", {"default": True,
                                                    "tooltip": "让 Laya 选最该先修的一条（正反双序防位置偏置）"}),
            },
        }

    RETURN_TYPES = ("STRING", "FLOAT", "BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("best_text", "best_score", "improved", "direction", "report")
    FUNCTION = "run"
    CATEGORY = "MiniMax H3/Wushu Bridge"
    OUTPUT_NODE = True
    DESCRIPTION = ("Laya 判断 + 排序：给 N 份候选稿打分选最优，并从体检弱项里挑最该先修的一条"
                   "（Laya 不写字，改稿由你或文本模型出）")

    def run(self, text, candidates, custom_rules, device,
            lint_mode="design", max_candidates=4, laya_dir="", use_model_direction=True):
        base = str(text or "").strip()
        cands = _split_candidates(candidates)[: int(max_candidates)]

        # ① 先给原始稿打分（没有候选时它就是唯一被测对象）
        try:
            rt.get_router(device=device, laya_dir=laya_dir)
            base_res = rt.judge_text(base or "（空材料）", custom_rules=custom_rules,
                                     device=device, laya_dir=laya_dir) if base else None
        except Exception as exc:
            msg = f"Laya 不可用：{type(exc).__name__}: {exc}"
            return _ui(("", 0.0, False, "", msg), msg)

        # ② 候选稿逐一打分
        scored: List[Tuple[float, int, str, Dict[str, Any]]] = []
        for i, c in enumerate(cands):
            try:
                r = rt.judge_text(c, custom_rules=custom_rules, device=device, laya_dir=laya_dir)
                scored.append((float(r["score"]), i, c, r))
            except Exception as exc:
                scored.append((-1.0, i, c, {"error": f"{type(exc).__name__}: {exc}"}))
        scored.sort(key=lambda t: (-t[0], t[1]))

        base_score = float(base_res["score"]) if base_res else 0.0
        if scored and scored[0][0] >= 0:
            best_score, best_idx, best_text, best_res = scored[0]
        else:
            best_score, best_idx, best_text, best_res = base_score, -1, base, (base_res or {})

        # ③ 体检出待修方向，让 Laya 挑最该先修的一条
        directions = _lint_directions(base, lint_mode)
        picked: Dict[str, Any] = {"choice": "", "note": "没有体检出待修项"}
        if directions and use_model_direction:
            try:
                picked = rt.pick_direction(base, directions, device=device, laya_dir=laya_dir)
            except Exception as exc:
                picked = {"choice": "", "note": f"方向选择失败：{type(exc).__name__}: {exc}"}
        elif directions:
            picked = {"choice": directions[0]["id"], "note": "未启用模型选择，按体检顺序取第一条"}

        dir_label = ""
        if picked.get("choice"):
            d = next((x for x in directions if x["id"] == picked["choice"]), None)
            dir_label = (d or {}).get("label") or picked["choice"]
        elif directions:
            dir_label = directions[0]["label"]

        improved = bool(best_score > base_score + 1e-9)

        # ④ 报告
        lines: List[str] = []
        lines.append(f"原始稿：{base_score:.3f}" + (f"（{base_res['level']}）" if base_res else ""))
        if scored:
            lines.append("")
            lines.append("── 候选稿排序（Laya 打分）──")
            for sc, i, _c, r in scored:
                mark = "  ← 最优" if i == best_idx else ""
                lvl = r.get("level") or r.get("error") or ""
                lines.append(f"  候选{i+1}: {sc:.3f}  {lvl}{mark}")
            lines.append("")
            lines.append(f"结论：{'候选稿更优，采用候选' if improved else '候选稿没有更好，保留原稿'}"
                         f"（{base_score:.3f} → {best_score:.3f}）")
        else:
            lines.append("（没给候选稿，只做体检与指方向）")
        lines.append("")
        lines.append("── 最该先修的方向 ──")
        if dir_label:
            lines.append(f"  {dir_label}")
            lines.append(f"  依据：{picked.get('note')}")
            if base_res and base_res.get("subscores"):
                weak = sorted(((k, v) for k, v in base_res["subscores"].items() if v < 0.5),
                              key=lambda kv: kv[1])
                if weak:
                    lines.append("  相关弱项：" + "、".join(f"{k}={v:.2f}" for k, v in weak[:4]))
        else:
            lines.append("  体检没有发现 error/warn 级待修项。")
        if len(directions) > 1:
            lines.append("")
            lines.append("  其它待修项（共 %d 条）：" % len(directions))
            for d in directions[:6]:
                lines.append(f"    · {d['label']}")

        report = "\n".join(lines)
        return _ui((best_text, float(best_score), bool(improved), dir_label, report), report)


NODE_CLASS_MAPPINGS = {
    "H3WushuLayaJudge": H3WushuLayaJudge,
    "H3WushuLayaOptimize": H3WushuLayaOptimize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3WushuLayaJudge": "H3 武打 Laya 裁判（自定义规则）",
    "H3WushuLayaOptimize": "H3 武打 Laya 优化回路（排序+指方向）",
}
