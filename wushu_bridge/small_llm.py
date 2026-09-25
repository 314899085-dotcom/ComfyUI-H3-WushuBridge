"""可选的小语言模型：只有当 Laya 判「不行」、而 conditioning 空间的桥也修不动时，
才用它把提示词**重写**一遍（Laya 不写字，这一步必须有会写字的模型）。

两种用法
--------
* ``hf``       —— 下载/加载一个 HF 上的小 instruct 模型（transformers + 本机 GPU）
* ``endpoint`` —— 直接调本机已有的 OpenAI 兼容服务（llama.cpp / LM Studio / vLLM），
                  不用下载、不占额外显存；你机器上已经有 minimod 服务的话填地址即可

自动下载
--------
选 ``hf`` 时若本地没有权重，会自动从 HuggingFace 下到
``ComfyUI/models/wushu_bridge/llm/<模型短名>/``（一次，之后离线可用）。

清单都是**实测核验过的**（存在、体积、许可、是否门禁），见 ``SMALL_LLM_CHOICES``。
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 已核验的小模型清单 ──────────────────────────────────────────────────────
# size 是 safetensors 合计（fp16/bf16）；gated=True 的需要先去模型页点同意才能下。
SMALL_LLM_CHOICES: Dict[str, Dict[str, Any]] = {
    "openbmb/MiniCPM5-2B": {
        "label": "MiniCPM5-2B（2B，128K 上下文，Apache-2.0）",
        "size_gb": 5.03, "license": "apache-2.0", "gated": False,
        "note": "同类里最强的小模型之一，4B 以下开源榜首；写动作描述够用",
    },
    "Qwen/Qwen3-1.7B": {
        "label": "Qwen3-1.7B（1.7B，Apache-2.0，最省显存）",
        "size_gb": 4.06, "license": "apache-2.0", "gated": False,
        "note": "想省显存/求快选它",
    },
    "HuggingFaceTB/SmolLM3-3B": {
        "label": "SmolLM3-3B（3B，Apache-2.0）",
        "size_gb": 6.15, "license": "apache-2.0", "gated": False,
    },
    "microsoft/Phi-4-mini-instruct": {
        "label": "Phi-4-mini-instruct（3.8B，MIT）",
        "size_gb": 7.67, "license": "mit", "gated": False,
    },
    "Qwen/Qwen3-4B-Instruct-2507": {
        "label": "Qwen3-4B-Instruct-2507（4B，Apache-2.0，质量更好）",
        "size_gb": 8.04, "license": "apache-2.0", "gated": False,
    },
    "openbmb/MiniCPM4-8B": {
        "label": "MiniCPM4-8B（8B，Apache-2.0，大一些但更强）",
        "size_gb": 16.37, "license": "apache-2.0", "gated": False,
    },
    "google/gemma-3-1b-it": {
        "label": "Gemma-3-1B-it（1B，需先在模型页同意条款）",
        "size_gb": 2.00, "license": "gemma", "gated": True,
    },
    "meta-llama/Llama-3.2-1B-Instruct": {
        "label": "Llama-3.2-1B-Instruct（1B，需先在模型页同意条款）",
        "size_gb": 2.47, "license": "llama3.2", "gated": True,
    },
}

_LOCK = threading.RLock()
_CACHE: Dict[str, Any] = {}


def _models_dir() -> str:
    """ComfyUI 的 models 目录（不在 ComfyUI 里跑就退回插件目录）。"""
    try:
        import folder_paths  # type: ignore

        d = getattr(folder_paths, "models_dir", None)
        if isinstance(d, (list, tuple)):
            d = d[0] if d else None
        if d:
            return str(d)
    except Exception:
        pass
    return os.path.join(_PLUGIN_DIR, "models")


def local_dir_for(repo: str) -> str:
    slug = repo.split("/")[-1]
    return os.path.join(_models_dir(), "wushu_bridge", "llm", slug)


def is_downloaded(repo: str) -> bool:
    d = local_dir_for(repo)
    if not os.path.isdir(d):
        return False
    for f in os.listdir(d):
        if f.endswith((".safetensors", ".bin")) or f == "model.safetensors.index.json":
            return True
    return False


def download(repo: str, quiet: bool = False) -> str:
    """把模型下到 ComfyUI/models/wushu_bridge/llm/<短名>/（已存在就跳过）。"""
    dst = local_dir_for(repo)
    if is_downloaded(repo):
        return dst
    from huggingface_hub import snapshot_download

    os.makedirs(dst, exist_ok=True)
    if not quiet:
        size = SMALL_LLM_CHOICES.get(repo, {}).get("size_gb")
        print(f"[wushu-bridge] 下载小模型 {repo}" + (f"（约 {size} GB）" if size else "") + " ...")
    snapshot_download(repo_id=repo, local_dir=dst,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model",
                                      "tokenizer*", "*.py"])
    return dst


# ── 提示词重写 ──────────────────────────────────────────────────────────────
REWRITE_SYSTEM = (
    "You are a fight-choreography prompt editor for a text-to-video model. "
    "Rewrite the user's martial-arts prompt into the required format. "
    "Keep the same scene and characters. Be concrete about footwork, weight transfer, "
    "contact and physical feedback. Output ONLY the rewritten prompt in English, "
    "no explanation, no markdown fences."
)

REWRITE_TEMPLATE = """Rewrite this martial-arts prompt.

Required format (two parts):
1) First line: wushu_action, <scene + environment>, <camera movement>, fast continuous pace, no slow motion.
2) Blank line, then 3-5 English sentences describing the full causal action chain
   (initial move -> exchange -> result), including physical feedback such as foot
   slides, weight shift, impact recoil.

Fix these problems (this is the priority):
{issues}

{user_rules}
Original prompt:
{text}
"""


def _endpoint_chat(url: str, model: str, system: str, user: str, timeout: int = 180) -> str:
    """调 OpenAI 兼容端点（llama.cpp server / LM Studio / vLLM）。"""
    base = url.rstrip("/")
    if not base.endswith("/chat/completions"):
        base = base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"
    body = {
        "model": model or "local",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.4, "max_tokens": 700,
    }
    req = urllib.request.Request(base, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 本机服务别走代理
    with opener.open(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return (d["choices"][0]["message"]["content"] or "").strip()


def _hf_rewrite(repo: str, text: str, user: str) -> str:
    """用 transformers 本地模型重写（第一次会加载/下载）。"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    with _LOCK:
        ent = _CACHE.get(repo)
        if ent is None:
            path = download(repo)
            tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                path, torch_dtype=dtype, device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True,
            )
            model.eval()
            ent = (tok, model)
            _CACHE[repo] = ent
        tok, model = ent

    msgs = [{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": user}]
    try:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        prompt = REWRITE_SYSTEM + "\n\n" + user
    ids = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=700, do_sample=True,
                             temperature=0.4, top_p=0.9, pad_token_id=tok.eos_token_id)
    gen = out[0][ids["input_ids"].shape[-1]:]
    return tok.decode(gen, skip_special_tokens=True).strip()


def clear_cache() -> int:
    """卸载常驻的小模型（换模型/省显存时用）。"""
    with _LOCK:
        n = len(_CACHE)
        _CACHE.clear()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return n


def rewrite_prompt(
    text: str,
    issues: Optional[List[str]] = None,
    custom_rules: str = "",
    mode: str = "off",
    repo: str = "openbmb/MiniCPM5-2B",
    endpoint_url: str = "",
    endpoint_model: str = "",
    timeout: int = 180,
) -> Tuple[str, str]:
    """按"待修项"重写提示词。返回 ``(新文本, 说明)``；mode=off 时原样返回。"""
    if mode == "off" or not str(text or "").strip():
        return text, "未启用小模型重写"

    issue_txt = "\n".join(f"- {i}" for i in (issues or [])) or "- (no specific issue listed; tighten the causal chain and physical feedback)"
    rules_txt = ""
    for ln in str(custom_rules or "").splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and not s.startswith(("评分:", "评分：", "选择:", "选择：")):
            rules_txt += f"- {s}\n"
    if rules_txt:
        rules_txt = "Also satisfy these user rules:\n" + rules_txt

    user = REWRITE_TEMPLATE.format(issues=issue_txt, user_rules=rules_txt, text=text)

    if mode == "endpoint":
        if not endpoint_url:
            return text, "选了 endpoint 模式但没填地址"
        try:
            out = _endpoint_chat(endpoint_url, endpoint_model, REWRITE_SYSTEM, user, timeout=timeout)
            return (out or text), f"endpoint 重写完成（{endpoint_url}）"
        except Exception as e:
            return text, f"endpoint 重写失败：{type(e).__name__}: {e}"

    # hf 模式
    try:
        out = _hf_rewrite(repo, text, user)
        return (out or text), f"本地小模型重写完成（{repo}）"
    except Exception as e:
        return text, f"本地小模型重写失败：{type(e).__name__}: {e}"
