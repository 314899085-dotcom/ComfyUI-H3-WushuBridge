"""Laya 决策模型运行时：把 Laya 当成"武打语义裁判"接进插件。

为什么内嵌而不是 pip install
---------------------------
Laya 本体是**纯 Python、76KB、8 个文件**，依赖只有 numpy/torch/safetensors/
transformers/huggingface_hub —— 这些 ComfyUI 环境本来全都有。所以直接把包放在
``wushu_bridge/vendor/laya/``，装插件时零安装步骤，也不会和 ComfyUI 的依赖打架。
（可选：环境变量 ``WUSHU_LAYA_USE_PIP=1`` 改用 pip 装的 laya。）

Laya 能回答什么、不能回答什么
-----------------------------
它**不生成文本**，只回答三类 typed question：

* ``choice``  从给定选项里选一个（带概率）
* ``score``   在有序档位上的期望档位
* ``noul``    "这条件成立吗"的标定概率

所以"让 Laya 优化"的正确形态是：**Laya 负责判断（选哪条方向 / 打多少分 / 过不过门），
真正的"改"由插件用确定性算子执行**。本模块负责判断这一半。

实测得出的两条硬约束（别绕开）
------------------------------
1. **choice 有严重位置偏置**：同一段材料把选项顺序反过来问，答案会变；四个截然不同的
   状态甚至全选第一个选项（置信还 0.89~0.93）。所以 ``pick_direction`` 一律走正反双序，
   两次选同一个才算数，否则回落到默认顺序。
2. **ordinal score 是最弱的 primitive**：好稿/烂稿在"动作逻辑"这一问上几乎不分甚至反向，
   判别力主要来自 ``noul`` 那几条。所以门禁默认用**加权分**（等价于 laya_serve 的
   ``via=rubric``），别单看某一问的 score。

权重放哪
--------
按下面顺序找（第一个能用的就用），目录结构见 ``docs``/README：

1. 环境变量 ``WUSHU_LAYA_DIR`` 指定的目录
2. ``ComfyUI/models/wushu_bridge/laya/``      ← ``tools/setup_laya.py`` 默认装到这
3. 插件目录下 ``models/wushu_bridge/laya/``
4. HuggingFace 缓存里的 ``convaiinnovations/laya`` 快照（离线可用）
"""

from __future__ import annotations

import glob
import json
import os
import sys
import threading
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

# ── 内嵌包优先 ──────────────────────────────────────────────────────────────
_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_laya():
    """优先用内嵌的 laya；用户显式要求时才用 pip 装的那份。"""
    if os.environ.get("WUSHU_LAYA_USE_PIP", "").strip() not in ("1", "true", "yes"):
        if os.path.isdir(os.path.join(_VENDOR_DIR, "laya")):
            if _VENDOR_DIR not in sys.path:
                sys.path.insert(0, _VENDOR_DIR)
    import laya  # noqa: WPS433
    return laya


# ── 默认问句：武打 rubric 五问（与 H3 武斗模拟器的裁判同一套）────────────────
# 五项等权。之所以不让用户一上来就自己写规则，是因为这套是实测过有判别力的。
RUBRIC_ORDER = ["动作逻辑", "招式过程", "命中反馈", "跳跃纪律", "可拍性"]

RUBRIC_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "动作逻辑": {
        "type": "score",
        "instructions": "这段武打里的动作是否连贯、每一步有没有明确目的（进攻/闪躲/脱离/抢位/"
                        "护住/蓄势/格挡/反击），有没有凭空停顿、站桩发呆？",
        "criteria": [
            "完全不成串：动作之间没有因果，或有明显凭空停顿、站桩发呆",
            "能看出在打，但目的含糊、衔接有断点",
            "基本连贯，个别地方要读者自己补因果",
            "连贯且有目的，衔接清楚",
            "每一步都目的明确、衔接干脆，可直接出片",
        ],
    },
    "招式过程": {
        "type": "noul",
        "instructions": "材料里写清了招式的过程（起手/准备 → 有效/打出去 → 收招），"
                        "而不是只有一个瞬间的姿势或只写了结果。",
    },
    "命中反馈": {
        "type": "noul",
        "instructions": "接触之后有受力反馈：格挡、受击、兵器相撞、踉跄、倒地或位移，"
                        "而不是打上去毫无反应。",
    },
    "跳跃纪律": {
        "type": "noul",
        "instructions": "若出现跳跃，跳跃有依据（躲开来招，或跃起重击/迎空拦截），高度与动作匹配"
                        "且落地接下一步；没有无来由的起跳、连跳或悬停。",
    },
    "可拍性": {
        "type": "noul",
        "instructions": "这段内容是可以拍的：镜头（景别/机位/运镜）、光线、物理（重心、兵器、距离）"
                        "都成立，没有自相矛盾或做不到的调度。",
    },
}

LEVELS: List[Tuple[float, str]] = [
    (0.80, "可直接出片"), (0.62, "小改可用"), (0.45, "需要大改"), (0.0, "明显不能看"),
]


def judge_level(score: float) -> str:
    for lo, label in LEVELS:
        if float(score) >= lo:
            return label
    return LEVELS[-1][1]


# ── 自定义规则 → typed questions ────────────────────────────────────────────
def parse_rules(rules_text: str) -> Dict[str, Dict[str, Any]]:
    """把用户写的规则行转成 Laya 能答的问句。

    支持三种写法（一行一条，``#`` 开头是注释、空行忽略）：

    * 裸规则              ``命中后必须看到受力反馈``
                          → noul 问句（是/否）
    * ``评分:``           ``评分:节奏是否紧凑|很拖|偏慢|适中|紧凑|极紧凑``
                          → score 问句（档位从差到好，第一个是"最差"档）
    * ``选择:``           ``选择:这一段的收招应该怎么处理|直接停住|缓冲半步|顺势追击``
                          → choice 问句

    为什么要分型：Laya 只吃这三种题型。把"你觉得该怎么改"这种开放问题丢给它，
    它只会瞎答（实测：四个完全不同的状态它全选第一个选项）。
    """
    questions: Dict[str, Dict[str, Any]] = {}
    for raw in str(rules_text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("评分:") or line.startswith("评分："):
            body = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
            parts = [p.strip() for p in body.replace("：", ":").split("|") if p.strip()]
            if len(parts) >= 2:
                questions[f"规则·{parts[0][:24]}"] = {
                    "type": "score",
                    "instructions": parts[0],
                    "criteria": parts[1:],
                }
            elif parts:
                questions[f"规则·{parts[0][:24]}"] = {"type": "noul", "instructions": parts[0]}
            continue
        if line.startswith("选择:") or line.startswith("选择："):
            body = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
            parts = [p.strip() for p in body.replace("：", ":").split("|") if p.strip()]
            if len(parts) >= 2:
                questions[f"规则·{parts[0][:24]}"] = {
                    "type": "choice",
                    "instructions": parts[0],
                    "criteria": {str(i): opt for i, opt in enumerate(parts[1:])},
                }
            continue
        # 裸规则 → noul
        questions[f"规则·{line[:24]}"] = {"type": "noul", "instructions": line}
    return questions


def answer_value(a: Dict[str, Any]) -> Optional[float]:
    """把一条答案折成 0~1（choice 求期望档位、score 按档位归一、noul 就是概率）。"""
    if not isinstance(a, dict) or not a:
        return None
    t = a.get("type") or ("choice" if "choice" in a else ("noul" if "noul" in a else "score"))
    if t == "choice":
        probs = [float(x) for x in (a.get("probabilities") or {}).values()]
        n = len(probs)
        if n <= 1:
            return 0.0
        return max(0.0, min(1.0, sum(i * p for i, p in enumerate(probs)) / (n - 1)))
    if t == "score" and "score" in a:
        legend = a.get("legend")
        levels = len(legend) if isinstance(legend, dict) and legend else 0
        if not levels:
            probs = a.get("probabilities")
            levels = len(probs) if isinstance(probs, dict) and probs else 5
        return max(0.0, min(1.0, float(a.get("score") or 0.0) / max(1, levels - 1)))
    return max(0.0, min(1.0, float(a.get("noul") or 0.0)))


def answer_choice(a: Dict[str, Any]) -> str:
    return str((a or {}).get("choice") or "")


# ── 权重目录定位 ────────────────────────────────────────────────────────────
_CHECKPOINT_FILES = ("rl_agent_config.json", "model.safetensors")


def _looks_like_bundle(path: str) -> bool:
    return all(os.path.exists(os.path.join(path, f)) for f in _CHECKPOINT_FILES)


def _comfyui_models_dir() -> Optional[str]:
    """拿 ComfyUI 的 models 目录（不在 ComfyUI 里跑时返回 None）。"""
    try:
        import folder_paths  # type: ignore

        d = getattr(folder_paths, "models_dir", None)
        if isinstance(d, (list, tuple)):
            d = d[0] if d else None
        return str(d) if d else None
    except Exception:
        return None


def _hf_cache_bundle() -> Optional[str]:
    """HuggingFace 缓存里的 laya 快照（离线可用，不需要联网）。"""
    try:
        home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    except Exception:
        return None
    pattern = os.path.join(home, "hub", "models--convaiinnovations--laya", "snapshots", "*")
    for snap in sorted(glob.glob(pattern), reverse=True):
        if _looks_like_bundle(snap):
            return snap
    return None


def find_laya_dir() -> Optional[str]:
    """按优先级找 Laya 权重目录；找不到返回 None（调用方给友好提示）。"""
    cands: List[str] = []
    env = os.environ.get("WUSHU_LAYA_DIR", "").strip()
    if env:
        cands.append(env)
    models_dir = _comfyui_models_dir()
    if models_dir:
        cands.append(os.path.join(models_dir, "wushu_bridge", "laya"))
    cands.append(os.path.join(_PLUGIN_DIR, "models", "wushu_bridge", "laya"))
    for c in cands:
        if c and _looks_like_bundle(c):
            return os.path.abspath(c)
    return _hf_cache_bundle()


def list_checkpoints(laya_dir: str) -> List[str]:
    """该目录下有哪些档：``english``（根）以及 ``multilingual`` / ``typed-decisions``。"""
    out: List[str] = []
    if _looks_like_bundle(laya_dir):
        out.append("english")
    for sub in ("multilingual", "typed-decisions"):
        if _looks_like_bundle(os.path.join(laya_dir, sub)):
            out.append(sub)
    return out


# ── Router 单例（Laya 加载一次几十秒，必须复用）─────────────────────────────
_ROUTER_CACHE: Dict[str, Any] = {}
_ROUTER_LOCK = threading.RLock()


def get_router(device: str = "auto", max_loaded: int = 2, preload: bool = False, laya_dir: str = ""):
    """拿到（并缓存）一个 Router。同一 (设备, 目录) 只建一次。"""
    laya = _import_laya()
    d = laya_dir or find_laya_dir()
    if not d:
        raise RuntimeError(
            "没找到 Laya 权重。先跑一次 tools/setup_laya.py 把权重装到 "
            "ComfyUI/models/wushu_bridge/laya/，或设环境变量 WUSHU_LAYA_DIR 指向权重目录。"
        )
    dev = "" if device in ("", "auto") else device
    key = f"{os.path.abspath(d)}|{dev}|{int(max_loaded)}"
    with _ROUTER_LOCK:
        r = _ROUTER_CACHE.get(key)
        if r is not None:
            return r
        # 本地目录优先 → 别让 huggingface_hub 去做联网元数据检查（网络慢会卡死启动）
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        models: Dict[str, Any] = {"english": (d, None)}
        if _looks_like_bundle(os.path.join(d, "multilingual")):
            models["multilingual"] = (d, "multilingual")
        if _looks_like_bundle(os.path.join(d, "typed-decisions")):
            models["typed-decisions"] = (d, "typed-decisions")
        with warnings.catch_warnings():
            # 权重自带温度超出 [0.5,5]，laya 会警告"置信度未校准" —— 预期内，别刷屏
            warnings.filterwarnings("ignore", message=r".*temperatures outside.*")
            r = laya.Router(models=models, device=dev or None,
                            max_loaded=max(1, int(max_loaded)), preload=bool(preload))
        _ROUTER_CACHE[key] = r
        return r


def clear_router_cache() -> int:
    """卸载常驻的 Laya（ComfyUI 里换设备/换权重后清一下）。"""
    with _ROUTER_LOCK:
        n = len(_ROUTER_CACHE)
        _ROUTER_CACHE.clear()
    return n


# ── 判断 ────────────────────────────────────────────────────────────────────
def _prose_state(text: str, extra_lines: Optional[List[str]] = None, max_chars: int = 2400) -> str:
    """Laya 吃"人话"：先给情境，再给材料。"""
    lines = ["这是一个武打短视频的审片/编排场景，请只根据下面的材料回答后面的问题。"]
    for ln in extra_lines or []:
        if ln:
            lines.append(str(ln))
    body = str(text or "").strip()
    lines.append("材料如下：\n" + body if body else "材料是空的：请按最差情况回答。")
    s = "\n".join(lines)
    return s[: int(max_chars)] if max_chars else s


def judge_text(
    text: str,
    custom_rules: str = "",
    device: str = "auto",
    laya_dir: str = "",
    router_model: str = "",
    timeout_s: float = 0.0,
) -> Dict[str, Any]:
    """给一段武打材料打分（默认 rubric 五问 + 用户自定义规则）。

    返回 ``{"ok", "score", "level", "subscores", "custom", "failed", "routed_to",
    "model", "elapsed_s", "report"}``。
    """
    router = get_router(device=device, laya_dir=laya_dir)
    questions = dict(RUBRIC_QUESTIONS)
    custom = parse_rules(custom_rules)
    questions.update(custom)

    t0 = time.time()
    kw: Dict[str, Any] = {"model": router_model} if router_model else {}
    raw = router.predict(_prose_state(text), questions, **kw)
    elapsed = time.time() - t0

    answers = (raw or {}).get("answers") or {}
    subs: Dict[str, float] = {}
    for qid in questions:
        v = answer_value(answers.get(qid) or {})
        if v is not None:
            subs[qid] = round(v, 4)

    rubric_subs = {k: v for k, v in subs.items() if k in RUBRIC_QUESTIONS}
    custom_subs = {k: v for k, v in subs.items() if k not in RUBRIC_QUESTIONS}
    # 五项等权（rubric 是实测有判别力的那把尺）；自定义规则单独列出，不混进总分，
    # 免得用户随手加两条规则就把基准分带跑（要当门禁用，见节点里的 threshold）。
    score = sum(rubric_subs.values()) / len(rubric_subs) if rubric_subs else 0.0

    failed = sorted([k for k, v in custom_subs.items() if v < 0.5], key=lambda k: custom_subs[k])
    routing = (raw or {}).get("routing") or {}
    out = {
        "ok": True,
        "score": round(score, 4),
        "level": judge_level(score),
        "subscores": subs,
        "custom": custom_subs,
        "failed": failed,
        "routed_to": routing.get("model") or "",
        "model": (raw or {}).get("model", ""),
        "elapsed_s": round(elapsed, 2),
    }
    out["report"] = format_judge_report(out)
    return out


def format_judge_report(res: Dict[str, Any]) -> str:
    lines = [f"Laya 武打裁判：{res['score']:.3f}（{res['level']}）"
             f"｜路由={res.get('routed_to') or '-'}｜{res.get('elapsed_s')}s"]
    lines.append("")
    lines.append("── rubric 五问 ──")
    for q in RUBRIC_ORDER:
        v = res["subscores"].get(q)
        if v is None:
            continue
        lines.append(f"  {q}: {v:.3f}{'   ← 弱项' if v < 0.5 else ''}")
    if res.get("custom"):
        lines.append("")
        lines.append("── 自定义规则 ──")
        for q, v in res["custom"].items():
            lines.append(f"  {q}: {v:.3f}{'   ← 未达标' if v < 0.5 else ''}")
    return "\n".join(lines)


# ── 方向选择（带位置偏置防护）───────────────────────────────────────────────
def pick_direction(
    state_text: str,
    directions: List[Dict[str, str]],
    default_id: str = "",
    device: str = "auto",
    laya_dir: str = "",
    instructions: str = "",
) -> Dict[str, Any]:
    """让 Laya 在候选方向里挑一个"最该先做"的。

    ``directions`` 形如 ``[{"id": "...", "label": "...", "why": "..."}]``。
    正反两种选项顺序各问一次，只有两次选同一个才采纳 —— 位置偏置防护，见模块顶部说明。
    """
    items = [d for d in (directions or []) if str(d.get("id") or "").strip()]
    if not items:
        return {"choice": "", "agreement": True, "tried": 0, "forward": "", "reverse": "",
                "default": default_id, "note": "没有候选方向"}
    ids = [str(d["id"]) for d in items]
    criteria = {str(d["id"]): (str(d.get("label") or d["id"])
                              + (f"（{d['why']}）" if d.get("why") else "")) for d in items}
    instr = instructions or ("下面是这条武打材料体检出来的待修项。只按「哪一条最可能把分数推上去」"
                            "来选，不要挑最容易做的；如果都推不动，选 none。")
    dflt = default_id if default_id in ids else ids[0]

    router = get_router(device=device, laya_dir=laya_dir)
    state = _prose_state(state_text)
    qid = "优先修复"

    def ask(order: List[str]) -> str:
        q = {qid: {"type": "choice", "instructions": instr,
                   "criteria": {k: criteria[k] for k in order}}}
        raw = router.predict(state, q)
        return answer_choice(((raw or {}).get("answers") or {}).get(qid) or {})

    fwd = ask(ids)
    rev = ask(list(reversed(ids)))
    agree = bool(fwd) and fwd == rev
    return {
        "choice": fwd if agree else "",
        "agreement": agree,
        "tried": 2,
        "forward": fwd,
        "reverse": rev,
        "default": dflt,
        "note": ("正反双序一致，采纳模型选择" if agree
                 else f"选项顺序不一致（正序「{fwd}」/ 反序「{rev}」）—— 位置偏置，按默认顺序走「{dflt}」"),
    }
