"""XYZ 坐标锁定：角色站位的显式空间坐标约定与解析/降级工具。

相机相对地面坐标系（document clearly）
------------------------------------
* **X**：画面左 (−) / 右 (+)
* **Y**：纵深靠近相机 (−) / 远离相机 (+)
* **Z**：离地高度（0 = 站立双脚着地）

单位：抽象「步」bu ≈ 一个武打步距。典型对决：
A 在 ``(-2, 0, 0)``，B 在 ``(+2, 0, 0)``，面对面。

规范写法（种子 / 逻辑链须同时出现中英）
--------------------------------------
* ZH: ``角色A@xyz=(-2,0,0)`` 或 ``位于 xyz=(-2,0,0)``
* EN: ``<Subject 1> at xyz=(-2,0,0)``
* 连续性格：``坐标锁定：A@xyz=(-2,0,0) 面向 B@xyz=(2,0,0)；切镜后重申相同 xyz，仅在位移动作后更新``
* EN: ``coords locked: A@xyz=(-2,0,0) facing B@xyz=(2,0,0); restate same xyz after cuts; update only after explicit footwork``

亦接受：``xyz=(-2, 0, 0)`` / ``XYZ(-2,0,0)`` / ``坐标(-2,0,0)`` / ``at (-2,0,0)``
（靠近主语时）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 主模式：xyz= / @xyz= / XYZ(...) / 坐标(...) / at (-2,0,0)
XYZ_RE = re.compile(
    r"(?:"
    r"(?:@?\s*xyz\s*[:=]\s*)|(?:XYZ\s*)|(?:坐标\s*)|(?:\bat\s+)"
    r")"
    r"[（(]\s*"
    r"(?P<x>[+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"(?P<y>[+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"(?P<z>[+-]?\d+(?:\.\d+)?)\s*"
    r"[）)]",
    re.I,
)

# 主语捕获：角色A / 角色 A / A@ / <Subject 1> / Subject 1 / Fighter A
_SUBJECT_BEFORE = re.compile(
    r"(?:"
    r"角色\s*([ABC1-9])|"
    r"<Subject\s*(\d+)>|"
    r"Subject\s*(\d+)|"
    r"Fighter\s*([ABC1-9])|"
    r"\b([ABC])\b"
    r")\s*$",
    re.I,
)

# 位移动作词：有这些时大跳不算瞬移
FOOTWORK_WORDS = [
    "位移", "上步", "撤步", "踏步", "跟步", "绕步", "滑步", "垫步", "换步",
    "退", "进", "逼近", "拉开", "拉开距离", "压缩间距", "追击", "超步",
    "footwork", "steps", "steps in", "steps back", "advances", "retreats",
    "closes", "sidestep", "side-step", "shuffle", "pivots", "circles",
    "overtakes", "pursuit", "closes the distance", "steps of distance",
]


def format_xyz(x: float, y: float, z: float, lang: str = "zh", subject: Optional[str] = None) -> str:
    """格式化一条 xyz 标注。"""
    def _n(v: float) -> str:
        if abs(v - int(v)) < 1e-9:
            return str(int(v))
        return f"{v:g}"

    triple = f"xyz=({_n(x)},{_n(y)},{_n(z)})"
    zh = lang.lower().startswith("zh")
    if not subject:
        return f"位于 {triple}" if zh else f"at {triple}"
    if zh:
        return f"{subject}@{triple}"
    # EN：Subject / Fighter 用 at xyz=
    return f"{subject} at {triple}"


def continuity_line(lang: str = "zh",
                    a: Tuple[float, float, float] = (-2, 0, 0),
                    b: Tuple[float, float, float] = (2, 0, 0)) -> str:
    """跨镜坐标锁定提示句。"""
    ax, ay, az = a
    bx, by, bz = b
    if lang.lower().startswith("zh"):
        return (
            f"坐标锁定：A@xyz=({_fmt(ax)},{_fmt(ay)},{_fmt(az)}) "
            f"面向 B@xyz=({_fmt(bx)},{_fmt(by)},{_fmt(bz)})；"
            f"切镜后重申相同 xyz，仅在位移动作后更新"
        )
    return (
        f"coords locked: A@xyz=({_fmt(ax)},{_fmt(ay)},{_fmt(az)}) "
        f"facing B@xyz=({_fmt(bx)},{_fmt(by)},{_fmt(bz)}); "
        f"restate same xyz after cuts; update only after explicit footwork"
    )


def _fmt(v: float) -> str:
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return f"{v:g}"


def parse_xyz_mentions(text: str) -> List[Dict[str, Any]]:
    """找出文本中所有 xyz 三元组。

    返回 ``[{subject?, x, y, z, span:(start,end), raw}]``。
    """
    if not text:
        return []
    out: List[Dict[str, Any]] = []
    for m in XYZ_RE.finditer(text):
        try:
            x = float(m.group("x"))
            y = float(m.group("y"))
            z = float(m.group("z"))
        except (TypeError, ValueError):
            continue
        # 向前看最多 24 字符找主语
        head = text[max(0, m.start() - 32):m.start()]
        subject = None
        # 去掉位于/at/@/= 等连接词再抓主语
        head_clean = re.sub(
            r"(?:位于|at|@|:|=|面向|facing)\s*$", "", head, flags=re.I
        ).rstrip(" ：:@=")
        sm = _SUBJECT_BEFORE.search(head_clean)
        if sm:
            subject = next(g for g in sm.groups() if g)
            if subject.upper() in ("A", "B", "C") and "角色" in head:
                subject = f"角色{subject.upper()}"
            elif subject.isdigit():
                subject = f"Subject {subject}"
            else:
                subject = subject.upper() if len(subject) == 1 else subject
        out.append({
            "subject": subject,
            "x": x, "y": y, "z": z,
            "span": (m.start(), m.end()),
            "raw": m.group(0),
        })
    return out


def coords_consistent(
    prev: Sequence[Dict[str, Any]] | Dict[str, Tuple[float, float, float]],
    curr: Sequence[Dict[str, Any]] | Dict[str, Tuple[float, float, float]],
    max_delta: float = 2.0,
) -> Tuple[bool, List[str]]:
    """同主语跨镜坐标是否在 max_delta 内。返回 (ok, 违规描述列表)。"""
    def _index(items) -> Dict[str, Tuple[float, float, float]]:
        if isinstance(items, dict):
            return {str(k): tuple(v) for k, v in items.items()}  # type: ignore
        idx: Dict[str, Tuple[float, float, float]] = {}
        for it in items:
            sub = it.get("subject") or f"anon@{it.get('span')}"
            idx[str(sub)] = (float(it["x"]), float(it["y"]), float(it["z"]))
        return idx

    a = _index(prev)
    b = _index(curr)
    problems: List[str] = []
    for sub, (x0, y0, z0) in a.items():
        if sub not in b:
            continue
        x1, y1, z1 = b[sub]
        dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5
        if dist > max_delta:
            problems.append(
                f"{sub}: ({_fmt(x0)},{_fmt(y0)},{_fmt(z0)})→({_fmt(x1)},{_fmt(y1)},{_fmt(z1)}) Δ={dist:.2f}"
            )
    return (len(problems) == 0, problems)


def has_footwork(text: str) -> bool:
    low = (text or "").lower()
    for w in FOOTWORK_WORDS:
        if w.isascii():
            if w.lower() in low:
                return True
        elif w in text:
            return True
    return False


def strip_xyz(text: str) -> str:
    """去掉所有 xyz / 坐标(...) 标注。"""
    if not text:
        return text
    out = XYZ_RE.sub("", text)
    # 清理多余空白
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" ?([，。；,.])", r"\1", out)
    return out


def mutate_xyz(text: str, rng) -> Tuple[str, bool]:
    """扰动数值三元组：左右互换 / 跳 Z / 大瞬移。

    返回 (新文本, 是否改动)。
    """
    mentions = parse_xyz_mentions(text)
    if not mentions:
        return text, False

    # 从后往前替换，避免 span 漂移
    out = text
    changed = False
    for m in reversed(mentions):
        x, y, z = m["x"], m["y"], m["z"]
        mode = rng.choice(["swap_lr", "jump_z", "teleport"])
        if mode == "swap_lr":
            x = -x
        elif mode == "jump_z":
            z = z + rng.choice([2.0, 3.0, -2.0, 4.0])
        else:  # teleport large jump
            x = x + rng.choice([-5.0, 5.0, -6.0, 6.0])
            y = y + rng.choice([-4.0, 4.0, 3.0, -3.0])
        new_triple = f"({_fmt(x)},{_fmt(y)},{_fmt(z)})"
        raw = m["raw"]
        # 保留前缀形态
        if re.match(r"@?\s*xyz\s*[:=]", raw, re.I):
            prefix = re.match(r"(@?\s*xyz\s*[:=]\s*)", raw, re.I).group(1)  # type: ignore
            replacement = f"{prefix}{new_triple}"
        elif re.match(r"XYZ\s*", raw, re.I):
            replacement = f"XYZ{new_triple}"
        elif raw.startswith("坐标"):
            replacement = f"坐标{new_triple}"
        elif re.match(r"at\s+", raw, re.I):
            replacement = f"at {new_triple}"
        else:
            replacement = f"xyz={new_triple}"
        s, e = m["span"]
        out = out[:s] + replacement + out[e:]
        changed = True
    return out, changed


def subject_coord_map(mentions: Sequence[Dict[str, Any]]) -> Dict[str, Tuple[float, float, float]]:
    """同主语取最后一次出现的坐标。"""
    idx: Dict[str, Tuple[float, float, float]] = {}
    for m in mentions:
        sub = m.get("subject")
        if not sub:
            continue
        idx[str(sub)] = (float(m["x"]), float(m["y"]), float(m["z"]))
    return idx
