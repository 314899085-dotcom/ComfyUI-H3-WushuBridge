#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 Laya 权重装配到 ComfyUI 里（优先从本地缓存拷贝，不重新下载）。

装完的目录结构（Router 直接认这个布局）::

    ComfyUI/models/wushu_bridge/laya/          <- english 档（根）
        rl_agent_config.json
        model.safetensors
        tokenizer/
        encoder/config.json
    ComfyUI/models/wushu_bridge/laya/multilingual/    <- 中文档（可选）
        ...

为什么要"装配"而不是让插件自己下：权重已经在 HuggingFace 缓存里了（约 840MB/档），
重新下一遍纯属浪费；而且 ComfyUI 的 models 目录是用户预期放模型的地方，
放这儿以后换插件版本也不会丢。

用法::

    # 自动找 ComfyUI 的 models 目录
    python tools/setup_laya.py

    # 指定目标目录
    python tools/setup_laya.py --target "I:\\ComfyUI_portable_TE_v260619\\ComfyUI\\models"

    # 只要英文档（省一半空间）
    python tools/setup_laya.py --only english

    # 本地缓存没有时允许联网下载
    python tools/setup_laya.py --allow-download

    # 只看会做什么，不动文件
    python tools/setup_laya.py --dry-run

装完自检（不需要 ComfyUI，确认权重能加载）::

    python tools/setup_laya.py --verify
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = "convaiinnovations/laya"
# 与 laya.agent 里的 allow_patterns 一致：一个档真正需要的就这四样
NEEDED = ("rl_agent_config.json", "model.safetensors", "tokenizer", "encoder")
SUBS = ("multilingual", "typed-decisions")


def hf_cache_bundle() -> str:
    """本地 HF 缓存里的 laya 快照目录（没有则空串）。"""
    try:
        from huggingface_hub import constants

        home = os.environ.get("HF_HOME") or constants.HF_HUB_CACHE
        home = os.path.dirname(home) if os.path.basename(home) == "hub" else home
    except Exception:
        home = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    import glob

    pat = os.path.join(home, "hub", "models--" + REPO.replace("/", "--"), "snapshots", "*")
    snaps = sorted(glob.glob(pat), reverse=True)
    for s in snaps:
        if os.path.exists(os.path.join(s, "model.safetensors")):
            return s
    return ""


def _size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for d, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return total


def _hum(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}GB"


def _link_or_copy(src: str, dst: str) -> str:
    """同盘优先硬链接（不占额外空间），跨盘退回复制。返回实际用的方式。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            if os.path.getsize(dst) == os.path.getsize(src):
                return "skip(已存在)"
        except OSError:
            pass
        try:
            os.remove(dst)
        except OSError:
            pass
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def copy_checkpoint(src_root: str, dst_root: str, sub: str, dry: bool) -> int:
    """把一个档（sub 为空=根/english）搬过去，返回字节数。"""
    src = os.path.join(src_root, sub) if sub else src_root
    dst = os.path.join(dst_root, sub) if sub else dst_root
    total = 0
    for name in NEEDED:
        s = os.path.join(src, name)
        if not os.path.exists(s):
            print(f"    [warn] 源里缺 {name}，跳过")
            continue
        if os.path.isfile(s):
            total += os.path.getsize(s)
            if dry:
                print(f"    {name:26s} {_hum(os.path.getsize(s)):>9s}  (dry-run)")
            else:
                how = _link_or_copy(s, os.path.join(dst, name))
                print(f"    {name:26s} {_hum(os.path.getsize(s)):>9s}  {how}")
        else:
            for d, _, fs in os.walk(s):
                rel = os.path.relpath(d, s)
                for f in fs:
                    sp = os.path.join(d, f)
                    dp = os.path.join(dst, name, f) if rel == "." else os.path.join(dst, name, rel, f)
                    total += os.path.getsize(sp)
                    if dry:
                        print(f"    {name}/{f:20s} {_hum(os.path.getsize(sp)):>9s}  (dry-run)")
                    else:
                        how = _link_or_copy(sp, dp)
                        print(f"    {name}/{f:20s} {_hum(os.path.getsize(sp)):>9s}  {how}")
    return total


def find_comfy_models(explicit: str) -> str:
    if explicit:
        return os.path.abspath(explicit)
    try:
        import folder_paths  # type: ignore

        d = getattr(folder_paths, "models_dir", None)
        if isinstance(d, (list, tuple)):
            d = d[0] if d else None
        if d:
            return os.path.abspath(str(d))
    except Exception:
        pass
    # 常见的 portable 布局：<ComfyUI根>/models，且同目录下有 python_embeded
    for base in (r"I:\ComfyUI_portable_TE_v260619\ComfyUI",):
        if os.path.isdir(os.path.join(base, "models")):
            return os.path.abspath(os.path.join(base, "models"))
    raise SystemExit("找不到 ComfyUI 的 models 目录。请用 --target 明确指定。")


def verify(target: str) -> int:
    """确认权重真的能加载（在 ComfyUI python 里跑最准）。"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from wushu_bridge import laya_runtime as rt

    print("权重目录:", target)
    cps = rt.list_checkpoints(target)
    print("可用档:", cps or "（空！）")
    if not cps:
        return 1
    print("加载中（首次会久一点）...")
    t0 = time.time()
    try:
        res = rt.judge_text("这是一段武打材料：A 出拳，B 格挡。" * 3, device="auto", laya_dir=target)
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return 1
    print(f"  [ok] {time.time()-t0:.1f}s  score={res['score']} level={res['level']} "
          f"routed={res['routed_to']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把 Laya 权重装配进 ComfyUI")
    ap.add_argument("--target", default="", help="ComfyUI 的 models 目录（默认自动找）")
    ap.add_argument("--source", default="", help="权重来源目录（默认用本地 HF 缓存）")
    ap.add_argument("--only", default="english,multilingual",
                    help="装哪些档（逗号分隔）：english,multilingual,typed-decisions / all。"
                         "默认 english,multilingual —— 武打裁判只用这两档；"
                         "typed-decisions 是给票据/工单那类业务 workflow 的，武打用不上（多占 840MB）")
    ap.add_argument("--allow-download", action="store_true", help="本地缓存没有时允许联网下载")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不动文件")
    ap.add_argument("--verify", action="store_true", help="只做加载自检")
    args = ap.parse_args()

    models = find_comfy_models(args.target)
    target = os.path.join(models, "wushu_bridge", "laya")

    if args.verify:
        return verify(target)

    src = args.source or hf_cache_bundle()
    if not src:
        if not args.allow_download:
            print("本地 HF 缓存里没有 laya 权重。")
            print("要么先在有网的机器上下载（python -c \"import laya;laya.Agent('convaiinnovations/laya')\"），")
            print("要么用 --allow-download 让它现在下（约 840MB/档）。")
            return 2
        from huggingface_hub import snapshot_download

        print("正在下载权重（可能要几分钟）...")
        src = snapshot_download(REPO, allow_patterns=[n for n in NEEDED] +
                                [f"{s}/{n}" for s in SUBS for n in NEEDED])
        print("下载到:", src)

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    if "all" in only:
        only = []
    cps = [""] + [s for s in SUBS if os.path.isdir(os.path.join(src, s))]
    if only:
        cps = [c for c in cps if (c or "english") in only]

    print("=" * 70)
    print("Laya 权重装配")
    print("  来源:", src)
    print("  目标:", target)
    print("  档位:", [c or "english" for c in cps])
    print("=" * 70)

    grand = 0
    for sub in cps:
        print(f"\n[{sub or 'english'}]")
        grand += copy_checkpoint(src, target, sub, args.dry_run)

    print()
    print(f"合计 {_hum(grand)}" + ("（dry-run，未落盘）" if args.dry_run else ""))
    if not args.dry_run:
        print(f"\n下一步自检：python tools/setup_laya.py --verify --target \"{models}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
