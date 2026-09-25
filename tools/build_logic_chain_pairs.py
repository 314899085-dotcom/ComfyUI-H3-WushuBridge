#!/usr/bin/env python3
"""从种子 + DEFAULT_OPS（经典逻辑 + 高动态）重建 wushu_pairs_v2_logic_chains.jsonl。

不需要 H3 CLIP / ComfyUI：只生成 TEXT 训练对清单。真正的 .safetensors 仍须在
用户本机 ComfyUI（MiniMax H3 CLIP 5120-d）里用「构建数据集 → 训桥 → 训 JEV」重训。

用法::

    python tools/build_logic_chain_pairs.py
    python tools/build_logic_chain_pairs.py --variants 12 --out models/wushu_bridge/datasets/wushu_pairs_v2_logic_chains.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wushu_bridge.pairs import (  # noqa: E402
    DEFAULT_OPS,
    DegradeProfile,
    build_pairs,
    dump_pairs,
    pairs_stats,
)
from wushu_bridge.seeds import all_seeds  # noqa: E402
from wushu_bridge import logic_chains  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Build v2 logic-chain training pairs from seeds")
    ap.add_argument("--variants", type=int, default=14, help="variants per source seed")
    ap.add_argument("--intensity", type=int, default=5, help="max degrade intensity 1-5")
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument(
        "--out",
        default=os.path.join(
            "models", "wushu_bridge", "datasets", "wushu_pairs_v2_logic_chains.jsonl"
        ),
    )
    ap.add_argument("--include-ref2v", action="store_true", default=True)
    ap.add_argument("--min-good-score", type=float, default=0.35)
    args = ap.parse_args()

    profile = DegradeProfile(ops=list(DEFAULT_OPS), intensity=args.intensity)
    print("DEFAULT_OPS:", DEFAULT_OPS)
    print("chains:", logic_chains.list_chains())
    print("t2v+horde seeds:", len(all_seeds("t2v")))
    print("ref2v seeds:", len(all_seeds("ref2v")))

    # 把逻辑链模板渲染成带 H3 壳的合成正例，扩大高动态覆盖
    synth = []
    for name in logic_chains.list_chains():
        for lang in ("zh", "en"):
            body = logic_chains.render_chain_text(name, lang=lang)
            if lang == "zh":
                prompt = (
                    "wushu_action, 10.2 seconds, 243 frames, 16:9, 24fps, 832x480. "
                    "武打场景，实体地面与掩体。角色A与角色B开场已交手。\n"
                    "integrated_multimodal_description:\n"
                    + body
                    + "\noverall_soundscape: 脚步、兵刃、闷哼、粗喘。\n"
                    "non_diegetic_music: None."
                )
            else:
                prompt = (
                    "wushu_action, 10.2 seconds, 243 frames, 16:9, 24fps, 832x480. "
                    "Wushu duel yard with solid ground and cover. Fighters already engaged.\n"
                    "integrated_multimodal_description:\n"
                    + body
                    + "\noverall_soundscape: footsteps, steel, grunt, breath.\n"
                    "non_diegetic_music: None."
                )
            synth.append(prompt)
    print("synthetic chain prompts:", len(synth))

    pairs = build_pairs(
        sources=synth,
        mode="t2v",
        variants_per_source=args.variants,
        profile=profile,
        include_seeds=True,
        score_mode="logic",
        min_good_score=args.min_good_score,
        seed=args.seed,
    )
    if args.include_ref2v:
        pairs_ref = build_pairs(
            sources=None,
            mode="ref2v",
            variants_per_source=max(4, args.variants // 2),
            profile=profile,
            include_seeds=True,
            score_mode="logic",
            min_good_score=args.min_good_score,
            seed=args.seed + 7,
        )
        pairs = list(pairs) + list(pairs_ref)

    path = dump_pairs(pairs, args.out)
    stats = pairs_stats(pairs)
    meta_path = args.out.replace(".jsonl", "_stats.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pairs_path": path,
                "stats": stats,
                "ops": DEFAULT_OPS,
                "chains": logic_chains.chain_preset_catalog(),
                "note": "TEXT pairs only. Retrain bridge/JEV in ComfyUI with H3 CLIP 5120-d.",
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("wrote", path, "pairs=", stats.get("count"))
    print("op_usage:", json.dumps(stats.get("op_usage", {}), ensure_ascii=False))
    print("stats:", meta_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
